"""Validasyon zinciri (K-134, K-139, K-140): rules (işlenmiş katman ve veri kuralları) → tablo içi validasyon → tablolar arası validasyon.

Her kural kendi işleminde çalışır: önce kuralın bulguları silinir, sonra işlenmiş katmandan yeniden yazılır. Tablolar arası
kuralı aynı anda iki iş çalıştırmasın diye kural başına uygulama kilidi alınır. Tablo içi işler aynı tabloda sıraya
girer (tablo kilidi). Kuyruğa yazan: Excel'de "Devam", çekimde tablonun okunması, "Yeniden valide et", "Kuralları yeniden uygula" (K-142).
"""
import json
import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.integration.contract import ENTITIES
from app.jobs import queue
from app.jobs.constants import ACTIVE_STATUSES, CHANNEL_PROCESSING, TYPE_VALIDATION
from db.models import metadata

from . import catalog as cat
from . import conditions, current
from .sqlkit import alias, current as is_current, label, row_key, shown, table

log = logging.getLogger("smartchain.validation")

RULE = metadata.tables["adm.ValidationRule"]
CONDITION = metadata.tables["adm.ValidationRuleCondition"]
RUN = metadata.tables["adm.ValidationRun"]
FINDING = metadata.tables["adm.ValidationFinding"]
JOB = metadata.tables["adm.Job"]

QUEUED, RULES, VALIDATING, DONE, FAILED = "Sırada", "Kurallar çalışıyor", "Valide ediliyor", "Bitti", "Valide edilemedi"
ACTIVE_STATES = (QUEUED, RULES, VALIDATING)
SCOPE_TABLE, SCOPE_CROSS = "Tablo içi", "Tablolar arası"
TRIGGER_UPLOAD, TRIGGER_PULL, TRIGGER_BULK, TRIGGER_REVALIDATE = "Yükleme", "Çekim", "Toplu çekim", "Yeniden valide et"
TRIGGER_RULES = "Kural değişikliği"  # "Kuralları yeniden uygula" (K-142)
PASSED, WARNED, FAILED_OUTCOME = "Geçti", "Uyarılı", "Hatalı"
ROW_NEW, ROW_ERROR = "Yeni", "Hatalı"
NAMES = {e.table: e.name for e in ENTITIES}


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _applock(session: Session, resource: str) -> None:
    """İşlem boyunca tutulan kilit (commit ya da rollback bırakır)."""
    session.execute(sa.text("DECLARE @r int; EXEC @r = sp_getapplock @Resource = :r, @LockMode = 'Exclusive', @LockOwner = 'Transaction', @LockTimeout = 600000; "
                            "IF @r < 0 THROW 50001, 'Validasyon kilidi alınamadı.', 1;"), {"r": resource[:255]})


@contextmanager
def _held_lock(session: Session, resource: str) -> Iterator[None]:
    """İş boyunca tutulan kilit: ayrı bağlantıda, oturum düzeyinde; çıkışta bırakılır."""
    conn = session.get_bind().connect()
    try:
        conn.execute(sa.text("DECLARE @r int; EXEC @r = sp_getapplock @Resource = :r, @LockMode = 'Exclusive', @LockOwner = 'Session', @LockTimeout = -1; "
                             "IF @r < 0 THROW 50001, 'Validasyon kilidi alınamadı.', 1;"), {"r": resource[:255]})
        conn.commit()
        yield
    finally:
        try:
            conn.execute(sa.text("EXEC sp_releaseapplock @Resource = :r, @LockOwner = 'Session'"), {"r": resource[:255]})
            conn.commit()
        finally:
            conn.close()


# ------------------------------------------------------------------ kural kataloğu ↔ veritabanı

_synced = False


def sync_rules(session: Session, force: bool = False) -> dict[str, int]:
    """Yapısal ve hazır kurallar katalogdan (K-137, K-139): eksik eklenir; özelleştirilmemiş kuralın adı, mesajı ve koşul metni güncellenir;
    sınıf ve aktiflik kullanıcıda kalır. Katalogdan kalkan hazır kural bulgularıyla silinir. Commit eder."""
    global _synced
    if _synced and not force:
        return {"added": 0, "updated": 0, "removed": 0}
    _applock(session, "validation:sync")
    rows = {(r.EntityName, r.Code): r for r in session.execute(
        sa.select(RULE.c.Id, RULE.c.EntityName, RULE.c.Code, RULE.c.Name, RULE.c.Kind, RULE.c.CheckType, RULE.c.Message, RULE.c.ConditionText, RULE.c.IsCustomized)
        .where(RULE.c.Kind != cat.USER_KIND))}
    added = updated = 0
    wanted = cat.by_key()
    for key, r in wanted.items():
        values = catalog_values(r)
        old = rows.get(key)
        if old is not None and old.IsCustomized:  # düzenlenmiş hazır kural: ad, mesaj ve koşul kullanıcıda (K-139)
            values = {"Kind": r.kind, "CheckType": r.check_type}
        if old is None:
            session.execute(sa.insert(RULE).values(EntityName=r.table, Code=r.code, Severity=r.severity, IsActive=True, IsCustomized=False, **values))
            added += 1
        elif any(getattr(old, k) != v for k, v in values.items()):
            session.execute(sa.update(RULE).where(RULE.c.Id == old.Id).values(**values))
            updated += 1
    gone = [old.Id for key, old in rows.items() if key not in wanted]
    if gone:
        session.execute(sa.delete(FINDING).where(FINDING.c.ValidationRuleId.in_(gone)))
        session.execute(sa.delete(RULE).where(RULE.c.Id.in_(gone)))
    session.commit()
    _synced = True
    return {"added": added, "updated": updated, "removed": len(gone)}


def catalog_values(r: cat.RuleDef) -> dict:
    return {"Name": r.title[:200], "Kind": r.kind, "CheckType": r.check_type, "Message": r.message[:400], "ConditionText": r.condition[:400]}


def _rules(session: Session, entity: str | None = None) -> list[dict]:
    q = sa.select(RULE)
    if entity:
        q = q.where(RULE.c.EntityName == entity)
    return [dict(r) for r in session.execute(q.order_by(RULE.c.Id)).mappings()]


def user_groups(session: Session, rule_id: int) -> list[list[conditions.Condition]]:
    rows = session.execute(sa.select(CONDITION).where(CONDITION.c.ValidationRuleId == rule_id).order_by(CONDITION.c.GroupNo, CONDITION.c.Id)).mappings()
    groups: dict[int, list] = {}
    for r in rows:
        groups.setdefault(r["GroupNo"], []).append(conditions.Condition(r["FieldName"], r["Operator"], r["Value"], r["CompareField"]))
    return [groups[k] for k in sorted(groups)]


def definition(session: Session, rule: dict) -> cat.RuleDef | None:
    """Veritabanı satırının değerlendiricisi: hazır ve yapısal kuralda katalog; kullanıcı kuralında ve düzenlenmiş hazır kuralda koşullar (K-139)."""
    found = cat.by_key().get((rule["EntityName"], rule["Code"])) if rule["Kind"] != cat.USER_KIND else None
    if rule["Kind"] != cat.USER_KIND and not (found is not None and found.editable and rule.get("IsCustomized")):
        return found
    try:
        groups = conditions.check(rule["EntityName"], user_groups(session, rule["Id"]))
    except conditions.ConditionError:
        log.warning("Kural %s koşulu geçersiz, atlandı", rule["Id"])
        return None
    return cat.RuleDef(rule["Code"], rule["EntityName"], rule["Name"], rule.get("ConditionText") or "", rule["Severity"], cat.LOGICAL, rule["Message"],
                       rule["Kind"], groups=tuple(tuple(g) for g in groups))


# ------------------------------------------------------------------ kuralı çalıştırma

FINDING_COLUMNS = ["EntityName", "StagingRowId", "ValidationRuleId", "Severity", "FieldName", "Value", "Message", "RowKey", "RunId"]


def _insert_groups(session: Session, rule: dict, groups, run_id: int) -> None:
    """Koşul grupları: satır başına tek bulgu; alan ve değer ilk tutan gruptan (grubun ilk koşulu)."""
    entity = rule["EntityName"]
    t = alias(entity)
    wheres = [conditions.group_where(t, entity, g) for g in groups]
    field = sa.case(*[(w, sa.literal(label(entity, g[0].field), sa.Unicode)) for w, g in zip(wheres, groups)])
    value = sa.case(*[(w, sa.func.left(shown(t.c[g[0].field]), 255)) for w, g in zip(wheres, groups)])
    sel = sa.select(sa.literal(entity, sa.Unicode), t.c.StagingRowId, sa.literal(rule["Id"]), sa.literal(rule["Severity"], sa.Unicode), field, value,
                    sa.literal(rule["Message"][:400], sa.Unicode), row_key(t, entity), sa.literal(run_id))
    session.execute(sa.insert(FINDING).from_select(FINDING_COLUMNS, sel.where(is_current(t), sa.or_(*wheres))))


def _insert_checks(session: Session, rule: dict, rdef: cat.RuleDef, run_id: int) -> None:
    entity = rule["EntityName"]
    if rdef.groups:
        _insert_groups(session, rule, rdef.groups, run_id)
    for check in rdef.checks:
        t = alias(entity)
        value = sa.func.left(shown(t.c[check.field]), 255) if check.field else sa.null()
        message = sa.literal(rule["Message"], sa.Unicode)
        if rdef.append_value and check.field:
            message = sa.func.concat(message, sa.literal(" ", sa.Unicode), shown(t.c[check.field]))
        sel = sa.select(sa.literal(entity, sa.Unicode), t.c.StagingRowId, sa.literal(rule["Id"]), sa.literal(rule["Severity"], sa.Unicode),
                        sa.literal(label(entity, check.field), sa.Unicode), value, sa.func.left(message, 400), row_key(t, entity), sa.literal(run_id))
        session.execute(sa.insert(FINDING).from_select(FINDING_COLUMNS, sel.where(is_current(t), check.where(t))))


def _insert_hits(session: Session, rule: dict, hits: list[cat.Hit], run_id: int) -> None:
    entity = rule["EntityName"]
    t = alias(entity)
    for start in range(0, len(hits), 500):
        part = hits[start:start + 500]
        keys = dict(session.execute(sa.select(t.c.StagingRowId, row_key(t, entity)).where(t.c.StagingRowId.in_([h[0] for h in part]))).all())
        session.execute(sa.insert(FINDING), [
            {"EntityName": entity, "StagingRowId": sid, "ValidationRuleId": rule["Id"], "Severity": rule["Severity"], "FieldName": field,
             "Value": (value or None) and value[:255], "Message": rule["Message"][:400], "RowKey": keys.get(sid), "RunId": run_id} for sid, field, value in part])


def run_rule(session: Session, rule: dict, run_id: int) -> None:
    """Kuralın bulgularını yeniler; kendi işleminde. Pasif kuralın bulguları silinir."""
    rdef = definition(session, rule)
    if rdef is not None and rdef.check_type == cat.CROSS:
        _applock(session, f"validation:rule:{rule['Id']}")
    session.execute(sa.delete(FINDING).where(FINDING.c.ValidationRuleId == rule["Id"]))
    if rule["IsActive"] and rdef is not None and rdef.runs and current.current_rows(session, rule["EntityName"]):
        missing = [r for r in rdef.reads if r not in rdef.may_be_empty and not current.current_rows(session, r)]
        if missing:
            session.execute(sa.insert(FINDING).values(
                EntityName=rule["EntityName"], StagingRowId=None, ValidationRuleId=rule["Id"], Severity=cat.INFO, FieldName=None, Value=None,
                Message=f"{cat.NO_DATA}: {', '.join(NAMES.get(r, r) for r in missing)}."[:400], RowKey=None, RunId=run_id))
        else:
            _insert_checks(session, rule, rdef, run_id)
            if rdef.python:
                _insert_hits(session, rule, rdef.python(session, rule["EntityName"]), run_id)
    session.commit()


def update_row_status(session: Session, entity: str) -> None:
    """İşlenmiş katmanda Hata bulgusu olan satır Hatalı (load almaz, K-134, K-140); yoksa Yeni. Aktarılmış satıra dokunulmaz."""
    t = table(entity)
    has_error = sa.exists().where(FINDING.c.EntityName == entity, FINDING.c.StagingRowId == t.c.StagingRowId, FINDING.c.Severity == cat.ERROR)
    session.execute(sa.update(t).where(is_current(t), t.c.RowStatus == ROW_NEW, has_error).values(RowStatus=ROW_ERROR))
    session.execute(sa.update(t).where(is_current(t), t.c.RowStatus == ROW_ERROR, ~has_error).values(RowStatus=ROW_NEW))
    session.commit()


def counts(session: Session, entity: str) -> dict:
    """Güncel kayıt ve sınıfa göre bulgulu satır sayısı, hata oranı."""
    rows = session.execute(sa.select(FINDING.c.Severity, sa.func.count(sa.distinct(FINDING.c.StagingRowId)))
                           .where(FINDING.c.EntityName == entity).group_by(FINDING.c.Severity)).all()
    by = {s: n for s, n in rows}
    total = current.current_rows(session, entity)
    errors = by.get(cat.ERROR, 0)
    return {"current_rows": total, "error_rows": errors, "warning_rows": by.get(cat.WARNING, 0), "info_rows": by.get(cat.INFO, 0),
            "error_rate": (errors / total * 100) if total else None}


SEVERITY_RANK = {cat.ERROR: 1, cat.WARNING: 2, cat.INFO: 3}


def rule_counts(session: Session, entity: str) -> list[dict]:
    """Çekmecenin Bulgular görünümü (K-139): kural, sınıf, satır sayısı; ağırdan hafife, çoktan aza. Tablo düzeyi bulguda mesaj."""
    rows = session.execute(sa.select(RULE.c.Id, RULE.c.Name, FINDING.c.Severity, sa.func.count(sa.distinct(FINDING.c.StagingRowId)))
                           .select_from(FINDING.join(RULE, RULE.c.Id == FINDING.c.ValidationRuleId))
                           .where(FINDING.c.EntityName == entity).group_by(RULE.c.Id, RULE.c.Name, FINDING.c.Severity)).all()
    no_data = dict(session.execute(sa.select(FINDING.c.ValidationRuleId, FINDING.c.Message)
                                   .where(FINDING.c.EntityName == entity, FINDING.c.StagingRowId.is_(None))).all())
    out = [{"id": i, "name": n, "severity": s, "rows": r, "message": no_data.get(i)} for i, n, s, r in rows]
    return sorted(out, key=lambda x: (SEVERITY_RANK.get(x["severity"], 9), -x["rows"], x["name"]))


def outcome_of(c: dict) -> str:
    if c["error_rows"]:
        return FAILED_OUTCOME
    return WARNED if c["warning_rows"] else PASSED


# ------------------------------------------------------------------ zincir

def _new_run(session: Session, entity: str | None, scope: str, trigger: str, batch_id: int | None, user_id: int | None, group: int | None) -> int:
    return session.execute(sa.insert(RUN).values(EntityName=entity, Scope=scope, TriggerType=trigger, BatchId=batch_id, GroupId=group,
                                                 State=QUEUED, RequestedBy=user_id, CreatedAt=utcnow()).returning(RUN.c.Id)).scalar_one()


def _enqueue(session: Session, entity: str | None, scope: str, trigger: str, batch_id: int | None, user_id: int | None,
             group: int | None) -> tuple[int, int]:
    """Çalışmayı ve işini yazar, commit etmez: (çalışma, iş)."""
    run_id = _new_run(session, entity, scope, trigger, batch_id, user_id, group)
    name = NAMES.get(entity, entity) if entity else "Bütün tablolar"
    summary = f"Validasyon · {name}" + (" · tablolar arası" if scope == SCOPE_CROSS else "")
    job_id = queue.enqueue(session, TYPE_VALIDATION, CHANNEL_PROCESSING, user_id,
                           {"run_id": run_id, "entity": entity, "scope": scope, "trigger": trigger, "batch_id": batch_id, "group": group},
                           summary=summary, commit=False)
    session.execute(sa.update(RUN).where(RUN.c.Id == run_id).values(JobId=job_id))
    return run_id, job_id


def enqueue(session: Session, entity: str | None, scope: str, trigger: str, batch_id: int | None = None, user_id: int | None = None,
            group: int | None = None) -> int:
    """Çalışmayı ve işini yazar; commit eder. İş Id'si döner."""
    _, job_id = _enqueue(session, entity, scope, trigger, batch_id, user_id, group)
    session.commit()
    return job_id


def enqueue_group(session: Session, entities: list[str], trigger: str, user_id: int | None) -> list[int]:
    """Birden çok tablonun zinciri (Kuralları yeniden uygula · Tümü, K-142): her tablo kendi işinde, hepsi bitince tablolar arası
    validasyon. Grup anahtarı ilk tablonun işidir; bütün işler tek işlemde yazılır."""
    made = [_enqueue(session, e, SCOPE_TABLE, trigger, None, user_id, None) for e in entities]
    group = made[0][1]
    for run_id, job_id in made:
        session.execute(sa.update(RUN).where(RUN.c.Id == run_id).values(GroupId=group))
        payload = json.loads(session.execute(sa.select(JOB.c.Payload).where(JOB.c.Id == job_id)).scalar_one())
        session.execute(sa.update(JOB).where(JOB.c.Id == job_id).values(Payload=json.dumps({**payload, "group": group}, ensure_ascii=False)))
    session.commit()
    return [job_id for _, job_id in made]


def on_received(session: Session, entity: str, batch_id: int, mode: str, trigger: str, user_id: int | None, group: int | None = None) -> int:
    """Parti "Alındı" oldu (K-133, K-134): güncel hâle işlenir, validasyon sıraya girer. Commit eder."""
    current.apply_batch(session, entity, batch_id, mode)
    return enqueue(session, entity, SCOPE_TABLE, trigger, batch_id, user_id, group)


def maybe_start_cross(session: Session, group: int) -> int | None:
    """Toplu çekimde son çıkan tablolar arası işi başlatır: çekim bitti, grubun tablo içi çalışmaları bitti, henüz başlatılmadı."""
    _applock(session, f"validation:group:{group}")
    runs = session.execute(sa.select(RUN.c.Scope, RUN.c.State).where(RUN.c.GroupId == group)).all()
    pull_active = session.execute(sa.select(JOB.c.Status).where(JOB.c.Id == group)).scalar() in ACTIVE_STATUSES
    if not runs or pull_active or any(s == SCOPE_CROSS for s, _ in runs) or any(st in ACTIVE_STATES for _, st in runs):
        session.commit()
        return None
    user = session.execute(sa.select(JOB.c.RequestedBy).where(JOB.c.Id == group)).scalar()
    return enqueue(session, None, SCOPE_CROSS, TRIGGER_BULK, None, user, group)


def _set_run(session: Session, run_id: int, **values) -> None:
    session.execute(sa.update(RUN).where(RUN.c.Id == run_id).values(**values))
    session.commit()


def _finish(session: Session, run_id: int, entity: str | None) -> dict | None:
    if entity is None:
        _set_run(session, run_id, State=DONE, FinishedAt=utcnow())
        return None
    c = counts(session, entity)
    _set_run(session, run_id, State=DONE, FinishedAt=utcnow(), CurrentRows=c["current_rows"], ErrorRows=c["error_rows"],
             WarningRows=c["warning_rows"], InfoRows=c["info_rows"])
    return {**c, "outcome": outcome_of(c)}


def run_table(session: Session, run_id: int, entity: str, related: bool, progress: Callable[[str], None]) -> dict:
    """Tablo içi: rules, tablonun kuralları; tek tablo yüklemesinde bu tabloya dokunan tablolar arası kurallar da (K-134)."""
    sync_rules(session)
    with _held_lock(session, f"validation:table:{entity}"):  # aynı tabloda tek iş
        return _run_table(session, run_id, entity, related, progress)


def _run_table(session: Session, run_id: int, entity: str, related: bool, progress: Callable[[str], None]) -> dict:
    from app.compare import raw as compare
    from . import rules_step
    compare.refresh(session, entity)  # Dünden bugüne (K-160): ham veri karşılaştırması; düşerse validasyon sürer
    _set_run(session, run_id, State=RULES, StartedAt=utcnow())
    progress(RULES)
    rules_step.run(session, entity)
    _set_run(session, run_id, State=VALIDATING)
    progress(VALIDATING)
    affected = {entity}
    for rule in _rules(session, entity):
        rdef = definition(session, rule)
        if rdef is None or rdef.check_type != cat.CROSS:
            run_rule(session, rule, run_id)
    if related:
        wanted = {(r.table, r.code) for r in cat.related_cross(entity)}
        for rule in _rules(session):
            if (rule["EntityName"], rule["Code"]) in wanted:
                run_rule(session, rule, run_id)
                affected.add(rule["EntityName"])
    for name in sorted(affected):
        update_row_status(session, name)
    return _finish(session, run_id, entity)


def run_cross(session: Session, run_id: int, progress: Callable[[str], None]) -> None:
    """Toplu çekimin sonunda bütün tablolar arası kurallar (K-134)."""
    sync_rules(session)
    _set_run(session, run_id, State=VALIDATING, StartedAt=utcnow())
    progress(VALIDATING)
    affected = set()
    for rule in _rules(session):
        rdef = definition(session, rule)
        if rdef is not None and rdef.check_type == cat.CROSS:
            run_rule(session, rule, run_id)
            affected.add(rule["EntityName"])
    for name in sorted(affected):
        update_row_status(session, name)
    _finish(session, run_id, None)


def group_outcomes(session: Session, group: int | None) -> list[dict]:
    """Toplu çekimin tablolarının tablolar arası validasyondan sonraki sonucu: iş panelinin çekim kartı (K-139)."""
    if not group:
        return []
    names = session.execute(sa.select(RUN.c.EntityName).where(RUN.c.GroupId == group, RUN.c.Scope == SCOPE_TABLE).distinct()).scalars().all()
    out = []
    for name in sorted(n for n in names if n):
        c = counts(session, name)
        out.append({"entity": name, "name": NAMES.get(name, name), "outcome": outcome_of(c), "error_rows": c["error_rows"], "warning_rows": c["warning_rows"]})
    return out


def run_job(session: Session, job_id: int, attempt: int, payload: dict, progress: Callable[[str], None]) -> bool:
    """Motor servisinin validasyon işi. Sonuç iş kaydına (Job.Result) yazılır."""
    run_id, entity, scope = payload["run_id"], payload.get("entity"), payload.get("scope", SCOPE_TABLE)
    if scope == SCOPE_CROSS:
        run_cross(session, run_id, progress)
        result = {"entity": None, "outcome": None, "tables": group_outcomes(session, payload.get("group"))}
    else:
        related = payload.get("trigger") != TRIGGER_BULK and not payload.get("group")  # grupta tablolar arası sonda (K-134, K-142)
        c = run_table(session, run_id, entity, related=related, progress=progress)
        result = {"entity": entity, "name": NAMES.get(entity, entity), "outcome": c["outcome"], "error_rows": c["error_rows"], "warning_rows": c["warning_rows"]}
    session.execute(sa.update(JOB).where(JOB.c.Id == job_id).values(Result=json.dumps(result, ensure_ascii=False)))
    text = f"{result.get('name') or 'Tablolar arası'} · {result['outcome'] or 'bitti'}"
    if result.get("outcome") == FAILED_OUTCOME:
        text += f" · {result['error_rows']}"
    elif result.get("outcome") == WARNED:
        text += f" · {result['warning_rows']}"
    ok = queue.finish(session, job_id, attempt, progress=text[:100])
    if payload.get("group"):
        maybe_start_cross(session, payload["group"])
    return ok


def fail_run(session: Session, payload: dict) -> None:
    """İş düştü: çalışma Valide edilemedi, önceki bulgular kalır."""
    session.rollback()
    _set_run(session, payload["run_id"], State=FAILED, FinishedAt=utcnow())
    if payload.get("group"):
        maybe_start_cross(session, payload["group"])
