"""Akış çalıştırma (K-163): zamanlayıcı ve durum makinesi. Motor servisi her turda `tick` çağırır.

Zamanlama: akışın son saati geldiyse ve o saat için çalıştırma yoksa yazılır. Saatinden sonra `FlowWaitMinutes` içindeyse "Bekliyor"
(servis o sürede geri geldiyse akış yine başlar); daha geçse "Başlamadı: servis kapalıydı". Başka akış sürüyorsa "Başlamadı".

Adımlar sabit: Başlangıç (elle başlatılmış veri işi bitene kadar bekler) → Veri çekme → Validasyon → Aktarım → Temizlik. Her adım bugünkü
işlerle yürür; çalıştırma yalnız iş kaydına bakar. Teknik hata aktarımdan önce durdurur; veri bulgusu durdurmaz (eşik aşan tablo aktarılmaz,
notu raporda). Kesinti (servis yeniden başladı, veritabanı bağlantısı koptu) çalışan akışı "Durdu: akış yarıda kesildi" yapar; aktarım işi
henüz bitmediyse iptal edilir, akış kaldığı yerden sürmez.
"""
import json
import logging
from datetime import datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.integration import contract
from app.jobs import queue
from app.jobs.constants import (ACTIVE_STATUSES, CHANNEL_PROCESSING, CHANNEL_PULL, STATUS_CANCELLED, STATUS_DONE, TYPE_CLEANUP, TYPE_PRECHECK, TYPE_PULL,
                                TYPE_TRANSFER, TYPE_VALIDATION)
from app.jobs.settings import FLOW_DEFAULTS, read_int_settings
from app.transfer.groups import group_tables
from db.models import metadata

from . import schedule

log = logging.getLogger("smartchain.flows")

FLOW = metadata.tables["adm.Flow"]
RUN = metadata.tables["adm.FlowRun"]
JOB = metadata.tables["adm.Job"]
VRUN = metadata.tables["adm.ValidationRun"]
DATA_RULE = metadata.tables["adm.DataRule"]

WAITING, RUNNING, DONE, STOPPED, NOT_STARTED = "Bekliyor", "Çalışıyor", "Bitti", "Durdu", "Başlamadı"
ACTIVE = (WAITING, RUNNING)
STATES = (WAITING, RUNNING, DONE, STOPPED, NOT_STARTED)
STEP_START, STEP_PULL, STEP_VALIDATION, STEP_TRANSFER, STEP_CLEANUP = "Başlangıç", "Veri çekme", "Validasyon", "Aktarım", "Temizlik"
STEPS = (STEP_START, STEP_PULL, STEP_VALIDATION, STEP_TRANSFER, STEP_CLEANUP)
SCHEDULED, MANUAL = "Zamanlanmış", "Elle"
SCOPE_ALL, SCOPE_SELECTED = "Tümü", "Seçilen"
MODE_FULL, MODE_PARTIAL = "Tam", "Kısmi"
SCHEDULER_SERVICE = "Zamanlayıcı"
REFRESH_RETRY_SECONDS = 60  # ERP yenilemesi sürerken tabloyu yeniden deneme aralığı
MISSED_HOURS = 24  # daha eski kaçırılan saat geçmişe yazılmaz

BUSY_TEXT = {TYPE_TRANSFER: "Aktarım", TYPE_CLEANUP: "Ham veri temizliği", TYPE_PULL: "Veri çekme", TYPE_PRECHECK: "Excel ön kontrolü",
             TYPE_VALIDATION: "Validasyon"}  # öncelik sırası
INTERRUPTED_RESTART = "Servis yeniden başladı; akış yarıda kesildi."
INTERRUPTED_DB = "Veritabanı bağlantısı koptu; akış yarıda kesildi."
MISSED = "Servis kapalıydı; akış saatinde başlamadı."
PULL_FAILED_STATES = ("Hata", "Hatalı", "Tamamlanmadı")  # pull.ERROR, imports FAILED, INCOMPLETE
REFRESHING = "Veri güncellemesi devam ediyor"


def settings(session: Session) -> dict[str, int]:
    return read_int_settings(session, FLOW_DEFAULTS)


# ------------------------------------------------------------------ okuma

def active_run(session: Session) -> dict | None:
    row = session.execute(sa.select(RUN).where(RUN.c.State.in_(ACTIVE)).order_by(RUN.c.Id)).mappings().first()
    return dict(row) if row else None


def busy(session: Session) -> str | None:
    """Süren veri işi (elle başlatılmış ya da akışın): adı; yoksa None."""
    types = session.execute(sa.select(JOB.c.JobType).where(JOB.c.JobType.in_(BUSY_TEXT), JOB.c.Status.in_(ACTIVE_STATUSES)).distinct()).scalars().all()
    return next((text for t, text in BUSY_TEXT.items() if t in types), None)


def _job(session: Session, job_id: int | None) -> dict | None:
    if not job_id:
        return None
    row = session.execute(sa.select(JOB.c.Id, JOB.c.Status, JOB.c.Result, JOB.c.ErrorText).where(JOB.c.Id == job_id)).mappings().first()
    return dict(row) if row else None


def pull_tables(session: Session, scope: str, chosen: list[str] | None) -> list[str]:
    """Akışın çekeceği SQL tabloları, tanımlı sırayla. Excel tabloları çekilmez."""
    from app.api.repositories import integration as repo
    rows = repo.all_entities(session)
    sql = [e.table for e in contract.ENTITIES if repo.method_of(rows.get(e.table)) == repo.METHOD_SQL]
    if scope == SCOPE_SELECTED:
        wanted = set(chosen or ())
        return [t for t in sql if t in wanted]
    return sql


def transfer_tables(mode: str, groups: list[str] | None) -> set[str] | None:
    """Aktarıma girecek tablolar; tamda None (bütün tablolar)."""
    return group_tables(groups or ()) if mode == MODE_PARTIAL else None


def failed_rules(session: Session, tables: set[str] | None = None) -> dict[str, int]:
    """Aktif ve son çalışmasında "Çalışmadı" olan veri kuralları, tablo başına sayı (K-163)."""
    from app.validation import data_rule
    q = (sa.select(DATA_RULE.c.EntityName, sa.func.count()).where(DATA_RULE.c.IsActive == sa.true(), DATA_RULE.c.LastRunStatus == data_rule.FAILED)
         .group_by(DATA_RULE.c.EntityName))
    if tables is not None:
        q = q.where(DATA_RULE.c.EntityName.in_(sorted(tables) or [""]))
    return {e: n for e, n in session.execute(q).all()}


def _grouped(errors: list[tuple[str, dict]]) -> str:
    """Aynı nedenle düşen tablolar tek parçada: "Malzeme, Stok: SQL kaynağına bağlanılamadı"; üçten çoksa "… ve 21 tablo"."""
    by_reason: dict[str, list[str]] = {}
    for entity, t in errors:
        by_reason.setdefault(t["reason"] or t["status"], []).append(entity)
    parts = []
    for reason, tables in by_reason.items():
        names = _names(tables[:3]) + (f" ve {len(tables) - 3} tablo" if len(tables) > 3 else "")
        parts.append(f"{names}: {reason}")
    return "; ".join(parts)


def _names(tables) -> str:
    names = {e.table: e.name for e in contract.ENTITIES}
    return ", ".join(names.get(t, t) for t in tables)


# ------------------------------------------------------------------ yazma

def _set(session: Session, run_id: int, **values) -> None:
    if "Detail" in values and not isinstance(values["Detail"], str):
        values["Detail"] = json.dumps(values["Detail"], ensure_ascii=False, default=str)
    if "Reason" in values and values["Reason"]:
        values["Reason"] = values["Reason"][:400]
    session.execute(sa.update(RUN).where(RUN.c.Id == run_id).values(**values))


def _end(session: Session, run: dict, state: str, now: datetime, reason: str | None = None, **values) -> None:
    _set(session, run["Id"], State=state, EndedAt=now, Reason=reason, **values)
    log.log(logging.INFO if state == DONE else logging.WARNING, "Akış %s (%s) %s: %s", run["FlowName"], run["Id"], state, reason or "")


def insert_run(session: Session, flow: dict, trigger: str, scheduled_utc: datetime, state: str = WAITING, reason: str | None = None,
               requested_by: int | None = None, now: datetime | None = None) -> int:
    ended = (now or schedule.utcnow()) if state not in ACTIVE else None
    return session.execute(sa.insert(RUN).values(
        FlowId=flow["Id"], FlowName=flow["Name"], TriggerType=trigger, ScheduledAt=scheduled_utc, State=state, Step=STEP_START,
        Reason=reason[:400] if reason else None, EndedAt=ended, RequestedBy=requested_by).returning(RUN.c.Id)).scalar_one()


def _abort(session: Session, job_id: int | None, reason: str) -> None:
    """Akışın işi sıradaysa ya da sürüyorsa iptal (aktarım dahil; elle iptal bunu yapamaz, K-107). Süren işin süreci sonucu yazamaz:
    kalp atışı reddedilir, motor süreci sonlandırır; aktarım işlemi geri alınır."""
    if job_id:
        session.execute(sa.update(JOB).where(JOB.c.Id == job_id, JOB.c.Status.in_(ACTIVE_STATUSES))
                        .values(Status=STATUS_CANCELLED, EndedAt=sa.func.sysutcdatetime(), UpdatedAt=sa.func.sysutcdatetime(), CancelReason=reason[:200]))


def interrupt(session: Session, reason: str, now: datetime | None = None) -> list[int]:
    """Çalışan akışlar yarıda kesildi: aktarım ve temizlik işi bitmediyse iptal; çalıştırma Durdu. Commit eder."""
    now = now or schedule.utcnow()
    stopped = []
    for run in session.execute(sa.select(RUN).where(RUN.c.State == RUNNING)).mappings().all():
        run = dict(run)
        values = {}
        for key in ("TransferJobId", "CleanupJobId"):
            _abort(session, run[key], reason)
        transfer = _job(session, run["TransferJobId"])
        if transfer and transfer["Status"] == STATUS_DONE and not run["DataVersionId"]:
            values["DataVersionId"] = json.loads(transfer["Result"] or "{}").get("data_version")
        _end(session, run, STOPPED, now, reason, **values)
        stopped.append(run["Id"])
    session.commit()
    return stopped


# ------------------------------------------------------------------ zamanlama

def schedule_due(session: Session, now: datetime, cfg: dict[str, int] | None = None) -> list[int]:
    """Saati gelen akışların çalıştırmalarını yazar. Commit etmez."""
    cfg = cfg or settings(session)
    wait = timedelta(minutes=cfg["FlowWaitMinutes"])
    now_local = schedule.utc_to_local(now)
    made = []
    for flow in session.execute(sa.select(FLOW).where(FLOW.c.IsActive == sa.true()).order_by(FLOW.c.RunTime, FLOW.c.Id)).mappings().all():
        flow = dict(flow)
        due_local = schedule.last_due(flow["RunTime"], schedule.parse_days(flow["Days"]), now_local)
        if due_local is None:
            continue
        due = schedule.local_to_utc(due_local)
        if due < flow["UpdatedAt"] or now - due > timedelta(hours=MISSED_HOURS):
            continue  # saat, akış kaydedilmeden önceydi
        exists = session.execute(sa.select(RUN.c.Id).where(RUN.c.FlowId == flow["Id"], RUN.c.TriggerType == SCHEDULED, RUN.c.ScheduledAt == due)).first()
        if exists:
            continue
        if now - due > wait:
            made.append(insert_run(session, flow, SCHEDULED, due, NOT_STARTED, MISSED, now=now))
            continue
        other = active_run(session)
        if other:
            made.append(insert_run(session, flow, SCHEDULED, due, NOT_STARTED, f"{other['FlowName']} sürüyordu.", now=now))
            continue
        made.append(insert_run(session, flow, SCHEDULED, due))
    return made


# ------------------------------------------------------------------ adımlar

def _snapshot(flow: dict) -> dict:
    return {"pull_scope": flow["PullScope"], "pull_tables": json.loads(flow["PullTables"] or "[]"), "mode": flow["TransferMode"],
            "groups": json.loads(flow["TransferGroups"] or "[]"), "cleanup": bool(flow["Cleanup"])}


def _enqueue_pull(session: Session, run: dict, tables: list[str]) -> int:
    return queue.enqueue(session, TYPE_PULL, CHANNEL_PULL, None, {"entities": tables, "read_anyway": [], "user_id": None, "flow_run": run["Id"]},
                         summary=f"Veri çekme · {run['FlowName']}"[:200], commit=False)


def _start(session: Session, run: dict, now: datetime, cfg: dict[str, int]) -> None:
    name = busy(session)
    if name:
        if now - run["ScheduledAt"] > timedelta(minutes=cfg["FlowWaitMinutes"]):
            _end(session, run, NOT_STARTED, now, f"{name} {cfg['FlowWaitMinutes']} dakikada bitmedi.")
        return
    flow = session.execute(sa.select(FLOW).where(FLOW.c.Id == run["FlowId"])).mappings().one()
    detail = _snapshot(dict(flow))
    tables = pull_tables(session, detail["pull_scope"], detail["pull_tables"])
    detail["pulled"] = tables
    values = {"State": RUNNING, "StartedAt": now, "Detail": detail}
    if tables:
        values.update(Step=STEP_PULL, PullJobId=_enqueue_pull(session, run, tables))
    else:
        values.update(Step=STEP_VALIDATION)
        detail["note"] = "Çekilecek SQL tablosu yok."
    _set(session, run["Id"], **values)


def _pull(session: Session, run: dict, detail: dict, now: datetime, cfg: dict[str, int]) -> None:
    job = _job(session, run["PullJobId"])
    if job is None or job["Status"] in ACTIVE_STATUSES:
        return
    if job["Status"] != STATUS_DONE:
        _end(session, run, STOPPED, now, f"Veri çekme işi tamamlanamadı (iş {job['Id']}).")
        return
    results = json.loads(job["Result"] or "[]")
    if detail.get("handled") != job["Id"]:
        detail.setdefault("tables", {}).update({r["entity"]: {"status": r["status"], "reason": r.get("reason")} for r in results})
        detail["handled"] = job["Id"]
    errors = [(e, t) for e, t in detail.get("tables", {}).items() if t["status"] in PULL_FAILED_STATES]
    if errors:
        _end(session, run, STOPPED, now, f"Veri çekilemedi · {_grouped(errors)}", Detail=detail)
        return
    refreshing = [e for e, t in detail.get("tables", {}).items() if t["status"] == REFRESHING]
    if refreshing:
        since = datetime.fromisoformat(detail.setdefault("refresh_since", now.isoformat()))
        if now - since >= timedelta(minutes=cfg["FlowRefreshWaitMinutes"]):
            _end(session, run, STOPPED, now, f"ERP veri güncellemesi {cfg['FlowRefreshWaitMinutes']} dakikada bitmedi: {_names(refreshing)}.", Detail=detail)
            return
        retry = detail.setdefault("retry_at", (now + timedelta(seconds=REFRESH_RETRY_SECONDS)).isoformat())
        if now >= datetime.fromisoformat(retry):
            detail.pop("retry_at")
            detail["repulls"] = detail.get("repulls", 0) + 1
            _set(session, run["Id"], PullJobId=_enqueue_pull(session, run, refreshing), Detail=detail)
        else:
            _set(session, run["Id"], Detail=detail)
        return
    _set(session, run["Id"], Step=STEP_VALIDATION, Detail=detail)


def _validation(session: Session, run: dict, detail: dict, now: datetime) -> None:
    from app.api.services import transfer as transfer_service
    from app.validation import engine as validation
    if busy(session) or session.execute(sa.select(VRUN.c.Id).where(VRUN.c.State.in_(validation.ACTIVE_STATES))).first():
        return
    failed = session.execute(sa.select(VRUN.c.EntityName).where(VRUN.c.State == validation.FAILED, VRUN.c.CreatedAt >= run["StartedAt"])).scalars().all()
    if failed:
        _end(session, run, STOPPED, now, f"Validasyon tamamlanamadı: {_names(sorted({f or 'Tablolar arası' for f in failed}))}.")
        return
    tables = transfer_tables(detail["mode"], detail["groups"])
    rules = failed_rules(session, tables)
    if rules:
        text = ", ".join(f"{_names([e])} ({n})" for e, n in sorted(rules.items()))
        _end(session, run, STOPPED, now, f"Çalışmayan veri kuralı var: {text}.")
        return
    blocked = transfer_service.blocked(session, tables)
    if blocked:
        _end(session, run, STOPPED, now, blocked["reason"] + (f" Tablolar: {', '.join(blocked['tables'])}." if blocked["tables"] else ""))
        return
    partial = detail["mode"] == MODE_PARTIAL
    payload = {"user_id": None, "flow_run": run["Id"], "flow_name": run["FlowName"]}
    summary = transfer_service.FULL_NAME
    if partial:
        payload.update(mode=MODE_PARTIAL, groups=detail["groups"])
        summary = f"{transfer_service.PARTIAL_NAME} · {', '.join(detail['groups'])}"
    job_id = queue.enqueue(session, TYPE_TRANSFER, CHANNEL_PROCESSING, None, payload, summary=f"{summary} · {run['FlowName']}"[:200], commit=False)
    _set(session, run["Id"], Step=STEP_TRANSFER, TransferJobId=job_id)


def _transfer(session: Session, run: dict, detail: dict, now: datetime) -> None:
    from app.cleanup import raw
    job = _job(session, run["TransferJobId"])
    if job is None or job["Status"] in ACTIVE_STATUSES:
        return
    if job["Status"] != STATUS_DONE:
        _end(session, run, STOPPED, now, f"Aktarım tamamlanamadı; önceki veri versiyonu geçerli (iş {job['Id']}).")
        return
    version = json.loads(job["Result"] or "{}").get("data_version")
    if not detail.get("cleanup"):
        _end(session, run, DONE, now, None, DataVersionId=version)
        return
    if raw.retention_days(session) is None:
        _end(session, run, DONE, now, "Ham veri temizliği atlandı: saklama süresi tanımlı değil.", DataVersionId=version)
        return
    job_id = queue.enqueue(session, TYPE_CLEANUP, CHANNEL_PROCESSING, None, {"user_id": None, "flow_run": run["Id"]},
                           summary=f"Ham veri temizliği · {run['FlowName']}"[:200], commit=False)
    _set(session, run["Id"], Step=STEP_CLEANUP, CleanupJobId=job_id, DataVersionId=version)


def _cleanup(session: Session, run: dict, now: datetime) -> None:
    job = _job(session, run["CleanupJobId"])
    if job is None or job["Status"] in ACTIVE_STATUSES:
        return
    if job["Status"] != STATUS_DONE:
        _end(session, run, STOPPED, now, f"Ham veri temizliği tamamlanamadı; aktarım yapıldı (iş {job['Id']}).")
        return
    _end(session, run, DONE, now)


def advance(session: Session, now: datetime, cfg: dict[str, int] | None = None) -> None:
    """Süren çalıştırmayı bir adım ilerletir. Commit etmez."""
    cfg = cfg or settings(session)
    run = active_run(session)
    if run is None:
        return
    if run["State"] == WAITING:
        _start(session, run, now, cfg)
        return
    detail = json.loads(run["Detail"] or "{}")
    step = run["Step"]
    if step == STEP_PULL:
        _pull(session, run, detail, now, cfg)
    elif step == STEP_VALIDATION:
        _validation(session, run, detail, now)
    elif step == STEP_TRANSFER:
        _transfer(session, run, detail, now)
    elif step == STEP_CLEANUP:
        _cleanup(session, run, now)


def tick(session: Session, now: datetime | None = None) -> None:
    """Zamanlayıcının bir turu: saati gelenleri yaz, süreni ilerlet. Commit eder."""
    now = now or schedule.utcnow()
    cfg = settings(session)
    schedule_due(session, now, cfg)
    session.commit()
    advance(session, now, cfg)
    session.commit()
    # Bir adım bittiyse sıradaki adımı aynı turda başlat (ör. çekecek tablo yoksa doğrudan validasyon)
    advance(session, now, cfg)
    session.commit()
