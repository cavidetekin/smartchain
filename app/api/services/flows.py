"""Zamanlanmış işler (ekran 25 · Zamanlanmış işler sekmesi, fonksiyon 92; K-163, K-164): tanım, bekleme süreleri, şimdi çalıştır, durum çipi,
kilit, zamanlayıcı satırı.

System owner tanımlar ve elle başlatır (92 yazma); Admin salt okunur görür (92 okuma, istisna). Durum çipi Key user ve üstüne (01 okuma).
Zamanlanmış iş sürerken veri işleri ve kural kaydetme 409 `flow_running` (`ensure_idle`).
"""
import json
from datetime import datetime, timedelta, timezone

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.flows import runner, schedule
from app.integration import contract
from app.transfer.groups import GROUPS
from db.models import metadata

from ..errors import AppError
from ..permissions import Access, allows
from ..repositories import audit, integration as integration_repo, system_health as health_repo
from . import auth, login_policy
from .auth import CurrentUser

FLOW, RUN = runner.FLOW, runner.RUN
DISMISSAL = metadata.tables["adm.FlowRunDismissal"]
USER = metadata.tables["adm.AppUser"]
OBJECT = "Flow"
CREATED, CHANGED, RUN_NOW = "Zamanlanmış iş tanımlandı", "Zamanlanmış iş değiştirildi", "Zamanlanmış iş elle başlatıldı"
LATE_SECONDS = 120  # saati gelen zamanlanmış iş bu sürede başlamadıysa zamanlayıcı "Gecikti"
LATE = "Gecikti"
NAMES = {e.table: e.name for e in contract.ENTITIES}
MASTER_GROUP = "Ana veri"  # Veri çekimi seçiminde aktarım gruplarına girmeyen tablolar (K-164)
SETTING_LIMITS = {"FlowWaitMinutes": (5, 720), "FlowRefreshWaitMinutes": (5, 720)}


def iso(value: datetime | None) -> str | None:
    return value.replace(tzinfo=timezone.utc).isoformat(timespec="seconds") if value else None


def running_message(run: dict) -> str:
    at = schedule.hhmm(run["StartedAt"] or run["ScheduledAt"])
    return f"Zamanlanmış iş sürüyor: {run['FlowName']} (başlama {at})"


def ensure_idle(session: Session) -> None:
    """Zamanlanmış iş sürerken (bekliyor ya da çalışıyor) veri işi ve kural kaydı başlamaz (K-163)."""
    run = runner.active_run(session)
    if run:
        raise AppError("flow_running", running_message(run), 409)


def check_idle(session: Session | None) -> None:
    """Router'dan, işlem açmadan önce (ör. dosya alınmadan)."""
    session = auth._require(session)
    auth._db(lambda: ensure_idle(session))


# ------------------------------------------------------------------ okuma

def _run_out(r: dict | None) -> dict | None:
    if r is None:
        return None
    return {"id": r["Id"], "flow_id": r["FlowId"], "flow_name": r["FlowName"], "trigger": r["TriggerType"], "state": r["State"], "step": r["Step"],
            "reason": r["Reason"], "scheduled_at": iso(r["ScheduledAt"]), "started_at": iso(r["StartedAt"]), "ended_at": iso(r["EndedAt"]),
            "data_version_id": r["DataVersionId"], "transfer_job_id": r["TransferJobId"]}


def _flow_out(session: Session, f: dict, now_local: datetime) -> dict:
    days = schedule.parse_days(f["Days"])
    nxt = schedule.next_due(f["RunTime"], days, now_local) if f["IsActive"] else None
    last = session.execute(sa.select(RUN).where(RUN.c.FlowId == f["Id"]).order_by(RUN.c.Id.desc()).limit(1)).mappings().first()
    return {"id": f["Id"], "name": f["Name"], "is_active": bool(f["IsActive"]), "run_time": f["RunTime"], "days": days, "days_text": schedule.days_text(days),
            "pull_scope": f["PullScope"], "pull_tables": json.loads(f["PullTables"] or "[]"), "transfer_mode": f["TransferMode"],
            "transfer_groups": json.loads(f["TransferGroups"] or "[]"), "cleanup": bool(f["Cleanup"]), "updated_at": iso(f["UpdatedAt"]),
            "updated_by_name": f["UpdatedByName"], "next_at": iso(schedule.local_to_utc(nxt)) if nxt else None, "last": _run_out(dict(last) if last else None)}


def _options(session: Session) -> dict:
    """Pencerenin seçenekleri: tablolar ve yöntemleri; aktarım grupları; Veri çekimi kümeleri (Ana veri + aktarım grupları, K-164)."""
    rows = integration_repo.all_entities(session)
    method = {e.table: integration_repo.method_of(rows.get(e.table)) for e in contract.ENTITIES}
    sql = [e.table for e in contract.ENTITIES if method[e.table] == integration_repo.METHOD_SQL]
    grouped = {t for tables in GROUPS.values() for t in tables}
    sets = {MASTER_GROUP: [e.table for e in contract.ENTITIES if e.table not in grouped], **{g: list(t) for g, t in GROUPS.items()}}
    table = lambda t: {"entity": t, "name": NAMES[t], "method": method[t]}  # noqa: E731
    return {"tables": [table(e.table) for e in contract.ENTITIES], "sql_tables": sql,
            "groups": [{"name": g, "tables": [table(t) for t in tables], "sql_tables": [t for t in sql if t in tables]} for g, tables in GROUPS.items()],
            "pull_sets": [{"name": g, "tables": [table(t) for t in tables]} for g, tables in sets.items()]}


def next_run(flow: dict, now: datetime | None = None) -> datetime | None:
    """Sıradaki saat (UTC); pasifte yok (K-164)."""
    if not flow["IsActive"]:
        return None
    nxt = schedule.next_due(flow["RunTime"], schedule.parse_days(flow["Days"]), schedule.utc_to_local(now or schedule.utcnow()))
    return schedule.local_to_utc(nxt) if nxt else None


def list_flows(session: Session | None, user: CurrentUser) -> dict:
    session = auth._require(session)

    def work():
        name = sa.func.coalesce(USER.c.FullName, USER.c.UserName).label("UpdatedByName")
        rows = session.execute(sa.select(FLOW, name).select_from(FLOW.join(USER, USER.c.Id == FLOW.c.UpdatedBy)).order_by(FLOW.c.RunTime, FLOW.c.Name)).mappings().all()
        now_local = schedule.utc_to_local(schedule.utcnow())
        return {"flows": [_flow_out(session, dict(r), now_local) for r in rows], "options": _options(session),
                "running": _run_out(runner.active_run(session)), "can_edit": allows(user.role, 92, Access.WRITE),
                "settings": runner.settings(session), "limits": {k: {"min": lo, "max": hi} for k, (lo, hi) in SETTING_LIMITS.items()}}

    return auth._db(work)


def save_settings(session: Session | None, user: CurrentUser, changes: dict[str, int | None]) -> dict:
    """İki bekleme süresi (K-164): yalnız değişenler yazılır, iz Sistem ayarlarıyla aynı; boş bırakılamaz."""
    session = auth._require(session)

    def work():
        missing = [{"field": k, "problem": "Boş bırakılamaz."} for k, v in changes.items() if v is None]
        if missing:
            raise _invalid(missing)
        login_policy.apply_changes(session, user, runner.settings(session), changes, SETTING_LIMITS)

    auth._db(work)
    return list_flows(session, user)


# ------------------------------------------------------------------ tanım

def _invalid(problems: list[dict]) -> AppError:
    return AppError("validation", "Girilen bilgiler geçersiz.", 422, problems)


def _clean(session: Session, body: dict, flow_id: int | None) -> dict:
    problems = []
    name = (body.get("name") or "").strip()
    if not name:
        problems.append({"field": "name", "problem": "Ad boş bırakılamaz."})
    elif len(name) > 100:
        problems.append({"field": "name", "problem": "Ad en çok 100 karakter."})
    elif session.execute(sa.select(FLOW.c.Id).where(FLOW.c.Name == name, FLOW.c.Id != (flow_id or 0))).first():
        problems.append({"field": "name", "problem": "Bu adla bir zamanlanmış iş var."})
    run_time = (body.get("run_time") or "").strip()
    if not schedule.valid_time(run_time):
        problems.append({"field": "run_time", "problem": "Saat SS:DD biçiminde olmalı (ör. 02:00)."})
    days = schedule.parse_days(",".join(str(d) for d in body.get("days") or []))
    if not days:
        problems.append({"field": "days", "problem": "En az bir gün seçin."})
    scope = body.get("pull_scope")
    tables = [e.table for e in contract.ENTITIES if e.table in set(body.get("pull_tables") or [])]
    unknown = set(body.get("pull_tables") or []) - {e.table for e in contract.ENTITIES}
    if scope not in (runner.SCOPE_ALL, runner.SCOPE_SELECTED):
        problems.append({"field": "pull_scope", "problem": "Tümü ya da Seçilen olmalı."})
    elif unknown:
        problems.append({"field": "pull_tables", "problem": f"Bilinmeyen tablo: {', '.join(sorted(unknown))}."})
    elif scope == runner.SCOPE_SELECTED and not tables:
        problems.append({"field": "pull_tables", "problem": "En az bir SQL tablosu seçin."})
    mode = body.get("transfer_mode")
    groups = [g for g in GROUPS if g in set(body.get("transfer_groups") or [])]
    bad_groups = set(body.get("transfer_groups") or []) - set(GROUPS)
    if mode not in (runner.MODE_FULL, runner.MODE_PARTIAL):
        problems.append({"field": "transfer_mode", "problem": "Tam ya da Kısmi olmalı."})
    elif bad_groups:
        problems.append({"field": "transfer_groups", "problem": f"Bilinmeyen grup: {', '.join(sorted(bad_groups))}."})
    elif mode == runner.MODE_PARTIAL and not groups:
        problems.append({"field": "transfer_groups", "problem": "Kısmi aktarımda en az bir grup seçin."})
    if problems:
        raise _invalid(problems)
    return {"Name": name, "IsActive": bool(body.get("is_active", True)), "RunTime": run_time, "Days": schedule.format_days(days), "PullScope": scope,
            "PullTables": json.dumps(tables if scope == runner.SCOPE_SELECTED else [], ensure_ascii=False), "TransferMode": mode,
            "TransferGroups": json.dumps(groups if mode == runner.MODE_PARTIAL else [], ensure_ascii=False), "Cleanup": bool(body.get("cleanup"))}


def _conflict(session: Session, values: dict, flow_id: int | None) -> None:
    """Aynı gün ve saatte iki aktif zamanlanmış iş olmaz (K-163)."""
    if not values["IsActive"]:
        return
    days = set(schedule.parse_days(values["Days"]))
    for other in session.execute(sa.select(FLOW).where(FLOW.c.IsActive == sa.true(), FLOW.c.RunTime == values["RunTime"], FLOW.c.Id != (flow_id or 0))).mappings():
        common = sorted(days & set(schedule.parse_days(other["Days"])))
        if common:
            raise AppError("flow_conflict", f"Aynı gün ve saatte başka bir zamanlanmış iş var: {other['Name']} ({schedule.days_text(common)} {values['RunTime']}).", 409)


def _audit_values(values: dict) -> dict:
    return {k: (json.loads(v) if k in ("PullTables", "TransferGroups") else v) for k, v in values.items()}


def save(session: Session | None, user: CurrentUser, body: dict, flow_id: int | None = None) -> dict:
    session = auth._require(session)

    def work():
        old = None
        if flow_id is not None:
            old = session.execute(sa.select(FLOW).where(FLOW.c.Id == flow_id)).mappings().first()
            if old is None:
                raise AppError("flow_not_found", "Zamanlanmış iş bulunamadı.", 404)
        values = _clean(session, body, flow_id)
        _conflict(session, values, flow_id)
        stamp = {"UpdatedAt": schedule.utcnow(), "UpdatedBy": user.id, "NextRunAt": next_run(values)}
        if old is None:
            new_id = session.execute(sa.insert(FLOW).values(**values, **stamp).returning(FLOW.c.Id)).scalar_one()
            audit.write_audit(session, CREATED, user.id, OBJECT, values["Name"], _audit_values(values))
        else:
            new_id = flow_id
            changed = {k: v for k, v in values.items() if old[k] != v}
            if changed:
                session.execute(sa.update(FLOW).where(FLOW.c.Id == flow_id).values(**values, **stamp))
                audit.write_audit(session, CHANGED, user.id, OBJECT, values["Name"], _audit_values(changed),
                                  _audit_values({k: old[k] for k in changed}))
        session.commit()
        return {"id": new_id}

    result = auth._db(work)
    return {**list_flows(session, user), **result}


def run_now(session: Session | None, user: CurrentUser, flow_id: int) -> dict:
    """Şimdi çalıştır (K-163): çalıştırma "Bekliyor" yazılır; zamanlayıcı aynı kurallarla başlatır."""
    session = auth._require(session)

    def work():
        flow = session.execute(sa.select(FLOW).where(FLOW.c.Id == flow_id)).mappings().first()
        if flow is None:
            raise AppError("flow_not_found", "Zamanlanmış iş bulunamadı.", 404)
        ensure_idle(session)
        run_id = runner.insert_run(session, dict(flow), runner.MANUAL, schedule.utcnow(), requested_by=user.id)
        audit.write_audit(session, RUN_NOW, user.id, OBJECT, flow["Name"], {"run": run_id})
        session.commit()
        return {"run_id": run_id}

    return auth._db(work)


# ------------------------------------------------------------------ durum çipi

def _alerts(session: Session, user_id: int) -> list[dict]:
    """Zamanlanmış iş başına son biten çalıştırma Durdu ya da Başlamadı ise ve kullanıcı kapatmadıysa (K-163)."""
    ranked = sa.select(RUN, sa.func.row_number().over(partition_by=RUN.c.FlowId, order_by=RUN.c.Id.desc()).label("rn")) \
        .where(RUN.c.State.not_in(runner.ACTIVE)).subquery()
    dismissed = sa.select(DISMISSAL.c.FlowRunId).where(DISMISSAL.c.UserId == user_id)
    rows = session.execute(sa.select(ranked).where(ranked.c.rn == 1, ranked.c.State.in_((runner.STOPPED, runner.NOT_STARTED)),
                                                   ranked.c.Id.not_in(dismissed)).order_by(ranked.c.Id.desc())).mappings().all()
    return [{**_run_out(dict(r)), "at": iso(r["EndedAt"] or r["ScheduledAt"])} for r in rows]


def status(session: Session | None, user: CurrentUser) -> dict:
    session = auth._require(session)

    def work():
        run = runner.active_run(session)
        return {"running": {**_run_out(run), "message": running_message(run)} if run else None, "alerts": _alerts(session, user.id),
                "can_view_history": allows(user.role, 92, Access.READ)}

    return auth._db(work)


def dismiss(session: Session | None, user: CurrentUser, run_id: int) -> None:
    session = auth._require(session)

    def work():
        if session.execute(sa.select(RUN.c.Id).where(RUN.c.Id == run_id)).first() is None:
            raise AppError("flow_run_not_found", "Çalıştırma bulunamadı.", 404)
        if session.execute(sa.select(DISMISSAL.c.FlowRunId).where(DISMISSAL.c.FlowRunId == run_id, DISMISSAL.c.UserId == user.id)).first() is None:
            session.execute(sa.insert(DISMISSAL).values(FlowRunId=run_id, UserId=user.id, DismissedAt=schedule.utcnow()))
        session.commit()

    auth._db(work)


# ------------------------------------------------------------------ Sistem sağlığı

def scheduler_row(session: Session, engine_state: str, running: str, stopped: str) -> dict:
    """Zamanlayıcı satırı (K-163): son kontrol, sıradaki zamanlanmış iş, son zamanlanmış iş. Motor durmuşsa durmuş; saati gelen zamanlanmış iş 2 dakikada başlamadıysa "Gecikti"."""
    row = health_repo.engine_status(session, runner.SCHEDULER_SERVICE)
    now = schedule.utcnow()
    now_local = schedule.utc_to_local(now)
    wait = timedelta(minutes=runner.settings(session)["FlowWaitMinutes"])
    late, nxt = None, None
    for f in session.execute(sa.select(FLOW).where(FLOW.c.IsActive == sa.true())).mappings():
        days = schedule.parse_days(f["Days"])
        due_local = schedule.last_due(f["RunTime"], days, now_local)
        if due_local is not None:
            due = schedule.local_to_utc(due_local)
            if due >= f["UpdatedAt"] and timedelta(seconds=LATE_SECONDS) < now - due <= wait and session.execute(
                    sa.select(RUN.c.Id).where(RUN.c.FlowId == f["Id"], RUN.c.TriggerType == runner.SCHEDULED, RUN.c.ScheduledAt == due)).first() is None:
                late = f["Name"]
        n = schedule.next_due(f["RunTime"], days, now_local)
        if n is not None and (nxt is None or n < nxt[1]):
            nxt = (f["Name"], n)
    last = session.execute(sa.select(RUN).where(RUN.c.State.not_in(runner.ACTIVE)).order_by(RUN.c.Id.desc()).limit(1)).mappings().first()
    if engine_state == stopped or row is None or row["StoppedAt"] is not None:
        state = stopped
    elif engine_state != running:
        state = engine_state
    else:
        state = LATE if late else running
    return {"key": "scheduler", "status": state, "checked_at": iso(row["HeartbeatAt"]) if row else None, "late": late,
            "next": {"name": nxt[0], "at": iso(schedule.local_to_utc(nxt[1]))} if nxt else None,
            "last": {"name": last["FlowName"], "state": last["State"], "at": iso(last["EndedAt"] or last["ScheduledAt"])} if last else None,
            "running": _run_out(runner.active_run(session))}
