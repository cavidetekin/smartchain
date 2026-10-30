"""İş kuyruğu işlemleri (fonksiyon 47, 93; K-67, K-68).

Her yazma işlevi kendi işlemini (transaction) tamamlar. Çalışmaya alma ve takılan işi geri alma
uygulama kilidiyle (sp_getapplock) sıraya konur; böylece aynı anda istek gelse de kanal sınırı aşılmaz.
Okuma işlevleri işi dict olarak döndürür; alanlar adm.Job adlarıyla, ek olarak QueuePosition,
DurationSeconds ve IsStale (kalp atışı eşiği aşıldı mı).
"""
import json
import logging
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from .constants import (CHANNELS, JOB_TYPES, STATUS_CANCELLED, STATUS_DONE,
                        STATUS_FAILED, STATUS_QUEUED, STATUS_RUNNING)
from .settings import JobSettings

log = logging.getLogger("smartchain.jobs")

LOCK_TIMEOUT_MS = 10_000
STALE_PROGRESS = "Yanıt vermedi, yeniden sıraya alındı"
STALE_ERROR = "İş yanıt vermedi; deneme hakkı bitti."
CRASH_PROGRESS = "İş süreci beklenmedik bitti, yeniden sıraya alındı"
CRASH_ERROR = "İş süreci beklenmedik bitti; deneme hakkı bitti."

# Sıra numarası kanal içinde: önce öncelik (büyük önce), sonra istek sırası (Id).
JOB_SELECT = """
WITH q AS (
    SELECT Id, ROW_NUMBER() OVER (PARTITION BY Channel ORDER BY ISNULL(Priority, 0) DESC, Id) AS QueuePosition
    FROM adm.Job WHERE Status = :queued
)
SELECT j.Id, j.JobType, j.Channel, j.Priority, j.Status, j.RequestedBy, j.Payload, j.Progress,
       j.HeartbeatAt, j.Attempt, j.ErrorText, j.CreatedAt, j.StartedAt, j.EndedAt, j.UpdatedAt,
       q.QueuePosition, COALESCE(u.FullName, u.UserName) AS RequestedByName,
       DATEDIFF(second, j.StartedAt, ISNULL(j.EndedAt, SYSUTCDATETIME())) AS DurationSeconds,
       CAST(CASE WHEN j.Status = :running
                  AND j.HeartbeatAt < DATEADD(second, -1 * :timeout, SYSUTCDATETIME())
                 THEN 1 ELSE 0 END AS bit) AS IsStale
FROM adm.Job j LEFT JOIN q ON q.Id = j.Id LEFT JOIN adm.AppUser u ON u.Id = j.RequestedBy
"""


class JobNotFound(LookupError):
    pass


class JobNotCancellable(Exception):
    def __init__(self, status: str):
        super().__init__(status)
        self.status = status


def _select(session: Session, settings: JobSettings, where: str, params: dict, order: str = "j.Id") -> list[dict]:
    sql = f"{JOB_SELECT} WHERE {where} ORDER BY {order}"
    params = {"queued": STATUS_QUEUED, "running": STATUS_RUNNING,
              "timeout": settings.heartbeat_timeout_seconds, **params}
    return [dict(r) for r in session.execute(text(sql), params).mappings()]


def _lock(session: Session) -> None:
    """Kuyruk kilidi; işlem (transaction) bitince kendiliğinden bırakılır."""
    result = session.execute(text(
        "DECLARE @r int; "
        "EXEC @r = sp_getapplock @Resource = N'adm.Job', @LockMode = 'Exclusive', "
        "@LockOwner = 'Transaction', @LockTimeout = :ms; SELECT @r"), {"ms": LOCK_TIMEOUT_MS}).scalar()
    if result is None or result < 0:
        raise TimeoutError(f"İş kuyruğu kilidi alınamadı (sp_getapplock {result})")


def _touch_queued(session: Session, channel: str) -> None:
    """Sıradaki işlerin sıra numarası değişti; UpdatedAt'i yenile ki sahiplerine bildirim gitsin (K-69)."""
    session.execute(text("UPDATE adm.Job SET UpdatedAt = SYSUTCDATETIME() WHERE Channel = :ch AND Status = :queued"),
                    {"ch": channel, "queued": STATUS_QUEUED})


def db_now(session: Session) -> datetime:
    return session.execute(text("SELECT SYSUTCDATETIME()")).scalar_one()


def enqueue(session: Session, job_type: str, channel: str, requested_by: int | None = None,
            payload: dict | None = None, priority: int | None = None) -> int:
    """İşi 'Sırada' olarak yazar, Id döndürür."""
    if job_type not in JOB_TYPES:
        raise ValueError(f"Bilinmeyen iş türü: {job_type}")
    if channel not in CHANNELS:
        raise ValueError(f"Bilinmeyen kanal: {channel}")
    job_id = session.execute(text(
        "INSERT INTO adm.Job (JobType, Channel, Priority, Status, RequestedBy, Payload, Attempt, CreatedAt, UpdatedAt) "
        "OUTPUT inserted.Id "
        "VALUES (:type, :ch, :prio, :queued, :by, :payload, 0, SYSUTCDATETIME(), SYSUTCDATETIME())"),
        {"type": job_type, "ch": channel, "prio": priority, "queued": STATUS_QUEUED, "by": requested_by,
         "payload": json.dumps(payload, ensure_ascii=False) if payload is not None else None}).scalar_one()
    session.commit()
    log.info("İş %s sıraya girdi: %s / %s", job_id, job_type, channel)
    return job_id


def claim_next(session: Session, channel: str, settings: JobSettings) -> dict | None:
    """Kanalda yer varsa sıradaki işi 'Çalışıyor' yapıp döndürür; yer ya da iş yoksa None (K-68)."""
    try:
        _lock(session)
        running = session.execute(text("SELECT COUNT(*) FROM adm.Job WHERE Channel = :ch AND Status = :running"),
                                  {"ch": channel, "running": STATUS_RUNNING}).scalar_one()
        if running >= settings.limit(channel):
            session.rollback()
            return None
        job_id = session.execute(text(
            "UPDATE adm.Job SET Status = :running, StartedAt = SYSUTCDATETIME(), EndedAt = NULL, "
            "HeartbeatAt = SYSUTCDATETIME(), Attempt = ISNULL(Attempt, 0) + 1, Progress = NULL, ErrorText = NULL, "
            "UpdatedAt = SYSUTCDATETIME() "
            "OUTPUT inserted.Id "
            "WHERE Id = (SELECT TOP 1 Id FROM adm.Job WHERE Channel = :ch AND Status = :queued "
            "            ORDER BY ISNULL(Priority, 0) DESC, Id)"),
            {"running": STATUS_RUNNING, "queued": STATUS_QUEUED, "ch": channel}).scalar()
        if job_id is None:
            session.rollback()
            return None
        _touch_queued(session, channel)
        session.commit()
    except Exception:
        session.rollback()
        raise
    log.info("İş %s çalışmaya alındı (%s)", job_id, channel)
    return get_job(session, job_id, settings)


def heartbeat(session: Session, job_id: int, attempt: int, progress: str | None = None) -> bool:
    """Yaşam sinyali. İlerleme verilirse bildirim de gider. False: iş artık bu denemenin değil (iptal, geri alındı)."""
    if progress is None:
        sql = "UPDATE adm.Job SET HeartbeatAt = SYSUTCDATETIME() "
    else:
        sql = "UPDATE adm.Job SET HeartbeatAt = SYSUTCDATETIME(), Progress = :progress, UpdatedAt = SYSUTCDATETIME() "
    row = session.execute(text(sql + "OUTPUT inserted.Id WHERE Id = :id AND Status = :running AND Attempt = :attempt"),
                          {"id": job_id, "attempt": attempt, "running": STATUS_RUNNING, "progress": progress}).first()
    session.commit()
    return row is not None


def set_progress(session: Session, job_id: int, attempt: int, progress: str) -> bool:
    """Yalnız ilerleme (adım geçişi); kalp atışını motor servisi yazar (K-71). False: iş artık bu denemenin değil."""
    row = session.execute(text(
        "UPDATE adm.Job SET Progress = :progress, UpdatedAt = SYSUTCDATETIME() "
        "OUTPUT inserted.Id WHERE Id = :id AND Status = :running AND Attempt = :attempt"),
        {"progress": progress, "id": job_id, "attempt": attempt, "running": STATUS_RUNNING}).first()
    session.commit()
    return row is not None


def _end(session: Session, job_id: int, attempt: int, status: str, error: str | None, commit: bool) -> bool:
    # Satır sayısı yerine OUTPUT: bağlantıdaki NOCOUNT ayarından bağımsız doğrulama.
    ok = session.execute(text(
        "UPDATE adm.Job SET Status = :status, EndedAt = SYSUTCDATETIME(), ErrorText = :error, "
        "UpdatedAt = SYSUTCDATETIME() OUTPUT inserted.Id WHERE Id = :id AND Status = :running AND Attempt = :attempt"),
        {"status": status, "error": error, "id": job_id, "attempt": attempt,
         "running": STATUS_RUNNING}).first() is not None
    if commit:
        session.commit()
    if not ok:
        log.warning("İş %s (deneme %s) %s yapılamadı: artık çalışmıyor", job_id, attempt, status)
    return ok


def finish(session: Session, job_id: int, attempt: int, progress: str | None = None, commit: bool = True) -> bool:
    """İşi Bitti yapar. commit=False: çağıran başka yazmalarla birlikte tek işlemde commit eder (motor, K-70)."""
    if progress is not None:
        session.execute(text("UPDATE adm.Job SET Progress = :p WHERE Id = :id AND Status = :running AND Attempt = :a"),
                        {"p": progress, "id": job_id, "a": attempt, "running": STATUS_RUNNING})
    return _end(session, job_id, attempt, STATUS_DONE, None, commit)


def fail(session: Session, job_id: int, attempt: int, error: str, commit: bool = True) -> bool:
    return _end(session, job_id, attempt, STATUS_FAILED, error, commit)


def cancel(session: Session, job_id: int) -> None:
    """Sıradaki işi iptal eder. Çalışan iş iptal edilmez (durdurma motorda, fonksiyon 93/34)."""
    try:
        row = session.execute(text(
            "UPDATE adm.Job SET Status = :cancelled, EndedAt = SYSUTCDATETIME(), UpdatedAt = SYSUTCDATETIME() "
            "OUTPUT inserted.Channel WHERE Id = :id AND Status = :queued"),
            {"cancelled": STATUS_CANCELLED, "id": job_id, "queued": STATUS_QUEUED}).first()
        if row is None:
            status = session.execute(text("SELECT Status FROM adm.Job WHERE Id = :id"), {"id": job_id}).scalar()
            session.rollback()
            if status is None:
                raise JobNotFound(job_id)
            raise JobNotCancellable(status)
        _touch_queued(session, row.Channel)
        session.commit()
    except (JobNotFound, JobNotCancellable):
        raise
    except Exception:
        session.rollback()
        raise
    log.info("İş %s iptal edildi", job_id)


def _requeue_where(session: Session, settings: JobSettings, where: str, params: dict,
                   progress: str, error: str) -> list:
    """Çalışan işi geri alır: deneme hakkı varsa Sırada, yoksa Hata (K-67). Kuyruk kilidiyle, tek işlemde."""
    try:
        _lock(session)
        rows = session.execute(text(
            "UPDATE adm.Job SET "
            "  Status = CASE WHEN ISNULL(Attempt, 0) < :max THEN :queued ELSE :failed END, "
            "  StartedAt = CASE WHEN ISNULL(Attempt, 0) < :max THEN NULL ELSE StartedAt END, "
            "  EndedAt = CASE WHEN ISNULL(Attempt, 0) < :max THEN NULL ELSE SYSUTCDATETIME() END, "
            "  Progress = CASE WHEN ISNULL(Attempt, 0) < :max THEN :progress ELSE Progress END, "
            "  ErrorText = CASE WHEN ISNULL(Attempt, 0) < :max THEN NULL ELSE :error END, "
            "  UpdatedAt = SYSUTCDATETIME() "
            f"OUTPUT inserted.Id, inserted.Channel, inserted.Status WHERE Status = :running AND {where}"),
            {"max": settings.max_attempts, "queued": STATUS_QUEUED, "failed": STATUS_FAILED,
             "progress": progress, "error": error, "running": STATUS_RUNNING, **params}).all()
        for channel in {r.Channel for r in rows}:
            _touch_queued(session, channel)
        session.commit()
    except Exception:
        session.rollback()
        raise
    return rows


def requeue_stale(session: Session, settings: JobSettings) -> list[int]:
    """Kalp atışı eşiği aşılan işleri geri alır (K-67)."""
    rows = _requeue_where(session, settings,
                          "(HeartbeatAt IS NULL OR HeartbeatAt < DATEADD(second, -1 * :timeout, SYSUTCDATETIME()))",
                          {"timeout": settings.heartbeat_timeout_seconds}, STALE_PROGRESS, STALE_ERROR)
    for r in rows:
        log.warning("İş %s yanıt vermedi → %s", r.Id, r.Status)
    return [r.Id for r in rows]


def requeue(session: Session, job_id: int, attempt: int, settings: JobSettings) -> str | None:
    """İş süreci beklenmedik bitti (K-71): işi hemen geri alır. Yeni durumu döndürür; iş artık bu denemenin değilse None."""
    rows = _requeue_where(session, settings, "Id = :id AND Attempt = :attempt", {"id": job_id, "attempt": attempt},
                          CRASH_PROGRESS, CRASH_ERROR)
    if not rows:
        return None
    log.warning("İş %s (deneme %s) süreci beklenmedik bitti → %s", job_id, attempt, rows[0].Status)
    return rows[0].Status


def get_job(session: Session, job_id: int, settings: JobSettings) -> dict | None:
    rows = _select(session, settings, "j.Id = :id", {"id": job_id})
    return rows[0] if rows else None


def list_jobs(session: Session, settings: JobSettings, user_id: int | None = None) -> list[dict]:
    """Çalışan, sıradaki ve son 24 saatte biten işler: önce çalışan, sonra sıra, sonra en son biten."""
    where = ("(j.Status IN (:queued, :running) "
             " OR j.EndedAt >= DATEADD(hour, -24, SYSUTCDATETIME()))")
    params = {}
    if user_id is not None:
        where += " AND j.RequestedBy = :user"
        params["user"] = user_id
    order = ("CASE j.Status WHEN :running THEN 0 WHEN :queued THEN 1 ELSE 2 END, "
             "j.Channel, q.QueuePosition, j.EndedAt DESC, j.Id DESC")
    return _select(session, settings, where, params, order)


def changed_since(session: Session, settings: JobSettings, since: datetime) -> list[dict]:
    return _select(session, settings, "j.UpdatedAt > :since", {"since": since}, "j.UpdatedAt, j.Id")


def counters(session: Session, settings: JobSettings) -> dict:
    """Kanal başına çalışan, sıradaki ve sınır (ör. etkileşim 2 / 3)."""
    rows = session.execute(text(
        "SELECT Channel, Status, COUNT(*) AS N FROM adm.Job WHERE Status IN (:queued, :running) "
        "GROUP BY Channel, Status"), {"queued": STATUS_QUEUED, "running": STATUS_RUNNING}).all()
    result = {ch: {"running": 0, "queued": 0, "limit": settings.limit(ch)} for ch in CHANNELS}
    for ch, status, n in rows:
        if ch in result:
            result[ch]["running" if status == STATUS_RUNNING else "queued"] = n
    return result

