"""Sistem olayları ve motorun kalp atışı (ekran 24, fonksiyon 94; K-106). API ve motor servisi birlikte kullanır.

Olay yazılamazsa asıl iş bozulmaz: hata log'a düşer. Yazma işlevleri commit etmez, çağıranın işlemine girer; böylece iş
geri alınırsa olayı da geri alınır. İşe bağlı olmayan aynı olay REPEAT_SECONDS içinde tekrar yazılmaz (hata seli olmasın).
"""
import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

log = logging.getLogger("smartchain.events")

COMPONENT_ENGINE = "Motor"
COMPONENT_APP = "Uygulama"
COMPONENT_QUEUE = "İş kuyruğu"
COMPONENT_EXPORT = "Dışa aktarım"

ENGINE_SERVICE = "Motor"
REPEAT_SECONDS = 60


def _repeated(session: Session, component: str, message: str) -> bool:
    return session.execute(text(
        "SELECT TOP 1 1 FROM adm.SystemEvent WHERE Component = :c AND Message = :m "
        "AND OccurredAt > DATEADD(second, -1 * :s, SYSUTCDATETIME())"),
        {"c": component, "m": message, "s": REPEAT_SECONDS}).first() is not None


def record(session: Session, component: str, message: str, resolution: str | None = None, resolved: bool = False,
           job_id: int | None = None, trace_id: str | None = None, detail: str | None = None) -> bool:
    """Olayı yazar; commit çağırana bırakılır. Yazılamazsa False döner, çağıranın işlemi bozulmaz."""
    message = message[:500]
    try:
        with session.begin_nested():
            if job_id is None and _repeated(session, component, message):
                return False
            session.execute(text(
                "INSERT INTO adm.SystemEvent (OccurredAt, Component, Message, Resolution, IsResolved, JobId, TraceId, Detail) "
                "VALUES (SYSUTCDATETIME(), :component, :message, :resolution, :resolved, :job, :trace, :detail)"),
                {"component": component, "message": message, "resolution": resolution[:200] if resolution else None,
                 "resolved": resolved, "job": job_id, "trace": trace_id, "detail": detail[:1000] if detail else None})
        return True
    except Exception:
        log.exception("Sistem olayı yazılamadı: %s · %s", component, message)
        return False


def purge(session: Session, retention_days: int) -> int:
    """Saklama süresi geçen olayları siler, sayısını döndürür. Kendi işlemini tamamlar."""
    rows = session.execute(text(
        "DELETE FROM adm.SystemEvent OUTPUT deleted.Id WHERE OccurredAt < DATEADD(day, -1 * :days, SYSUTCDATETIME())"),
        {"days": retention_days}).all()
    session.commit()
    if rows:
        log.info("Saklama süresi geçen %s sistem olayı silindi", len(rows))
    return len(rows)


def service_started(session: Session, version: str, name: str = ENGINE_SERVICE) -> bool:
    """Açılış kaydı. Önceki çalışma düzgün kapanmadıysa True. Commit çağırana bırakılır."""
    row = session.execute(text("SELECT StoppedAt FROM adm.ServiceStatus WHERE ServiceName = :n"), {"n": name}).first()
    if row is None:
        session.execute(text(
            "INSERT INTO adm.ServiceStatus (ServiceName, HeartbeatAt, StartedAt, StoppedAt, AppVersion) "
            "VALUES (:n, SYSUTCDATETIME(), SYSUTCDATETIME(), NULL, :v)"), {"n": name, "v": version})
        return False
    session.execute(text(
        "UPDATE adm.ServiceStatus SET HeartbeatAt = SYSUTCDATETIME(), StartedAt = SYSUTCDATETIME(), StoppedAt = NULL, "
        "AppVersion = :v WHERE ServiceName = :n"), {"n": name, "v": version})
    return row.StoppedAt is None


def service_beat(session: Session, name: str = ENGINE_SERVICE) -> None:
    session.execute(text("UPDATE adm.ServiceStatus SET HeartbeatAt = SYSUTCDATETIME() WHERE ServiceName = :n"), {"n": name})


def service_stopped(session: Session, name: str = ENGINE_SERVICE) -> None:
    session.execute(text("UPDATE adm.ServiceStatus SET StoppedAt = SYSUTCDATETIME() WHERE ServiceName = :n"), {"n": name})
