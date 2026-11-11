"""Validasyon ve validasyon kuralları (ekran 02 ve 27, fonksiyon 04 ve 100; K-133…K-139).

Çekmece özeti ve yeniden validasyon fonksiyon 04'tür (Key user ve üstü); kural listesi ve kayıt fonksiyon 100'dür
(System owner ve Admin yazar, Key user okur). Kayıt toplu ve tek işlemdir (K-132): biri geçersizse hiçbiri yazılmaz.
"""
from decimal import Decimal, InvalidOperation

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.integration import contract
from app.jobs.constants import ACTIVE_STATUSES
from app.validation import catalog as cat, conditions, engine, texts
from app.validation.current import current_rows
from db.models import metadata

from ..errors import AppError
from ..permissions import Access
from ..repositories import audit
from . import auth, authz, flows
from .auth import CurrentUser

BATCH = metadata.tables["adm.ImportBatch"]
CONFIG = metadata.tables["adm.IntegrationEntity"]
USER = metadata.tables["adm.AppUser"]
RULE, CONDITION, RUN, FINDING, JOB = engine.RULE, engine.CONDITION, engine.RUN, engine.FINDING, engine.JOB
OBJECT_RULE, OBJECT_ENTITY = "ValidationRule", "IntegrationEntity"
ACTION_REVALIDATE, ACTION_RULE, ACTION_THRESHOLD = "Yeniden validasyon", "Validasyon kuralı", "Hata eşiği"
LOADED = ("Alındı", "Doğrulandı", "Yüklendi")
MAX_NAME, MAX_MESSAGE = 200, 400


def entity_of(table: str) -> contract.Entity:
    found = contract.entity(table)
    if found is None:
        raise AppError("entity_not_found", "Tablo bulunamadı.", 404)
    return found


def _bad(code: str, message: str, problem: str, field: str = "rules") -> AppError:
    return AppError(code, message, 422, [{"field": field, "problem": problem}])


# ------------------------------------------------------------------ çekmece (fonksiyon 04)

def state_of(session: Session, entity: str) -> str | None:
    """Çipin durumu: son çalışma; işi düşmüşse Valide edilemedi (K-134). Hiç çalışmamışsa None."""
    row = session.execute(sa.select(RUN.c.State, JOB.c.Status).select_from(RUN.outerjoin(JOB, JOB.c.Id == RUN.c.JobId))
                          .where(RUN.c.EntityName == entity, RUN.c.Scope == engine.SCOPE_TABLE).order_by(RUN.c.Id.desc()).limit(1)).first()
    if row is None:
        return None
    state, job_status = row
    if state in engine.ACTIVE_STATES and job_status is not None and job_status not in ACTIVE_STATUSES:
        return engine.FAILED
    return state


def summary_of(session: Session, table: str) -> dict:
    entity = entity_of(table)
    c = engine.counts(session, entity.table)
    batch = session.execute(sa.select(BATCH.c.Id, BATCH.c.ReceivedAt, BATCH.c.Method, BATCH.c.LoadType, sa.func.coalesce(USER.c.FullName, USER.c.UserName).label("by"))
                            .select_from(BATCH.outerjoin(USER, USER.c.Id == BATCH.c.UploadedBy))
                            .where(BATCH.c.EntityName == entity.table, BATCH.c.Status.in_(LOADED)).order_by(BATCH.c.Id.desc()).limit(1)).first()
    threshold = session.execute(sa.select(CONFIG.c.ErrorThresholdPct).where(CONFIG.c.EntityName == entity.table)).scalar()
    state = state_of(session, entity.table)
    return {
        "entity": entity.table, "name": entity.name, "state": state,
        "outcome": engine.outcome_of(c) if state == engine.DONE else None,
        "batch": {"id": batch.Id, "received_at": batch.ReceivedAt, "method": batch.Method, "mode": batch.LoadType, "uploaded_by_name": batch.by} if batch else None,
        "current_rows": c["current_rows"], "error_rows": c["error_rows"], "warning_rows": c["warning_rows"], "info_rows": c["info_rows"],
        "error_rate": c["error_rate"], "threshold": float(threshold) if threshold is not None else None,
        "rules": engine.rule_counts(session, entity.table),
    }


def summary(session: Session | None, table: str) -> dict:
    session = auth._require(session)
    return auth._db(lambda: summary_of(session, table))


def revalidate(session: Session | None, user: CurrentUser, table: str) -> dict:
    session = auth._require(session)
    entity = entity_of(table)

    def work():
        if state_of(session, entity.table) in (engine.QUEUED, engine.RULES, engine.VALIDATING):
            raise AppError("validation_running", "Bu tablonun validasyonu sürüyor.", 409)
        if not current_rows(session, entity.table):
            raise AppError("validation_no_data", "Bu tabloda valide edilecek veri yok.", 409)
        audit.write_audit(session, ACTION_REVALIDATE, user.id, OBJECT_ENTITY, entity.name, {"entity_name": entity.name})
        job_id = engine.enqueue(session, entity.table, engine.SCOPE_TABLE, engine.TRIGGER_REVALIDATE, None, user.id)
        return {"job_id": job_id}

    return auth._db(work)


# ------------------------------------------------------------------ kurallar (fonksiyon 100)

def fields(session: Session | None, table: str) -> list[dict]:
    """Koşul editörünün alanları: güncel etiketle; etiketsiz ek alan listelenmez (K-143)."""
    session = auth._require(session)
    entity = entity_of(table)

    def work():
        names, cols = texts.field_labels(session, entity.table), conditions.columns(entity.table)
        return [{"name": n, "label": names[n], "kind": conditions.kind_of(cols[n]), "values": list(cols[n].info.get("values") or [])}
                for n in texts.editor_fields(session, entity.table)]

    return auth._db(work)


def _groups_payload(groups: list[list[conditions.Condition]]) -> list[list[dict]]:
    return [[{"field": c.field, "operator": c.operator, "value": c.value, "compare_field": c.compare_field} for c in g] for g in groups]


def rule_detail(session: Session | None, rule_id: int) -> dict:
    session = auth._require(session)

    def work():
        engine.sync_rules(session)
        row = session.execute(sa.select(RULE).where(RULE.c.Id == rule_id)).mappings().first()
        if row is None:
            raise AppError("validation_rule_not_found", "Kural bulunamadı.", 404)
        rule = dict(row)
        return {"id": rule["Id"], "entity": rule["EntityName"], "code": rule["Code"], "name": rule["Name"], "kind": rule["Kind"],
                "check_type": rule["CheckType"], "severity": rule["Severity"], "message": rule["Message"], "active": rule["IsActive"],
                "locked": rule["Kind"] == cat.STRUCTURAL_KIND, "editable": editable(rule), "customized": bool(rule["IsCustomized"]),
                "groups": _groups_payload(groups_of(session, rule)), "condition": condition_text(session, rule)}

    return auth._db(work)


def editable(rule: dict) -> bool:
    """Pencerede düzenlenir mi: kullanıcı kuralı ya da koşulu editörle ifade edilen hazır kural (K-139)."""
    if rule["Kind"] == cat.USER_KIND:
        return True
    found = cat.by_key().get((rule["EntityName"], rule["Code"]))
    return bool(found and found.editable)


def groups_of(session: Session, rule: dict) -> list[list[conditions.Condition]]:
    if rule["Kind"] == cat.USER_KIND or rule.get("IsCustomized"):
        return engine.user_groups(session, rule["Id"])
    found = cat.by_key().get((rule["EntityName"], rule["Code"]))
    return [list(g) for g in found.groups] if found and found.groups else []


def condition_text(session: Session, rule: dict) -> str:
    groups = groups_of(session, rule)
    if groups:
        return conditions.sentence(rule["EntityName"], groups, texts.field_labels(session, rule["EntityName"]))
    found = cat.by_key().get((rule["EntityName"], rule["Code"]))
    return found.condition if found else (rule.get("ConditionText") or "")


def _parse_groups(entity: str, raw) -> list[list[conditions.Condition]]:
    if not isinstance(raw, list) or not raw:
        raise _bad("validation_rule_bad_condition", "Koşul geçersiz.", "Kuralın koşulu yok.")
    groups = []
    for g in raw:
        if not isinstance(g, list) or not g:
            raise _bad("validation_rule_bad_condition", "Koşul geçersiz.", "Boş koşul grubu.")
        group = []
        for c in g:
            cond = conditions.Condition(str(c.get("field") or ""), str(c.get("operator") or ""),
                                        None if c.get("value") in (None, "") else str(c.get("value")), c.get("compare_field") or None)
            try:
                conditions.validate(entity, cond)
            except conditions.ConditionError as exc:
                raise _bad("validation_rule_bad_condition", "Koşul geçersiz.", str(exc)) from None
            group.append(cond)
        groups.append(group)
    return groups


def _threshold(raw) -> Decimal | None:
    if raw in (None, ""):
        return None
    try:
        value = Decimal(str(raw).replace(",", "."))
    except InvalidOperation:
        raise _bad("validation_threshold_range", "Hata eşiği 0 ile 100 arasında olmalı.", "Sayı girin.", "thresholds") from None
    if not (0 <= value <= 100):
        raise _bad("validation_threshold_range", "Hata eşiği 0 ile 100 arasında olmalı.", "0 ile 100 arasında olmalı.", "thresholds")
    return value.quantize(Decimal("0.01"))


def _write_conditions(session: Session, rule_id: int, groups: list[list[conditions.Condition]]) -> None:
    session.execute(sa.delete(CONDITION).where(CONDITION.c.ValidationRuleId == rule_id))
    for no, group in enumerate(groups, 1):
        for c in group:
            session.execute(sa.insert(CONDITION).values(ValidationRuleId=rule_id, GroupNo=no, FieldName=c.field, Operator=c.operator,
                                                        Value=c.value, CompareField=c.compare_field))


def _next_code(session: Session, entity: str) -> str:
    codes = session.execute(sa.select(RULE.c.Code).where(RULE.c.EntityName == entity, RULE.c.Kind == cat.USER_KIND)).scalars().all()
    numbers = [int(c.split("-", 1)[1]) for c in codes if c.startswith("KUL-") and c.split("-", 1)[1].isdigit()]
    return f"KUL-{max(numbers, default=0) + 1}"


def save_rules(session: Session | None, user: CurrentUser, changes: list[dict], thresholds: list[dict]) -> dict:
    """Toplu kayıt (K-132): kurallar, koşullar ve eşikler tek işlemde. Değişen tablolar "Yeniden valide et" önerisi içindir."""
    session = auth._require(session)
    authz.ensure(user, 100, Access.WRITE)

    def work():
        flows.ensure_idle(session)  # K-163
        engine.sync_rules(session)
        changed: set[str] = set()
        now = engine.utcnow()
        for change in changes:
            rule_id = change.get("id")
            if rule_id is None:  # yeni kullanıcı kuralı
                entity = entity_of(str(change.get("entity") or "")).table
                name = (change.get("name") or "").strip()
                message = (change.get("message") or "").strip()
                if not name or not message:
                    raise _bad("validation", "Girilen bilgiler geçersiz.", "Kural adı ve mesajı boş olamaz.")
                severity = change.get("severity") or cat.WARNING
                if severity not in cat.SEVERITIES:
                    raise _bad("validation", "Girilen bilgiler geçersiz.", "Sınıf Hata, Uyarı ya da Bilgi olmalı.")
                groups = _parse_groups(entity, change.get("groups"))
                if session.execute(sa.select(RULE.c.Id).where(RULE.c.EntityName == entity, RULE.c.Name == name[:MAX_NAME])).first():
                    raise _bad("validation_rule_name_taken", "Bu adla kural var.", f"{name}: bu tabloda aynı adla kural var.")
                new_id = session.execute(sa.insert(RULE).values(
                    EntityName=entity, Code=_next_code(session, entity), Name=name[:MAX_NAME], Kind=cat.USER_KIND, CheckType=cat.LOGICAL,
                    Severity=severity, Message=message[:MAX_MESSAGE], IsActive=bool(change.get("active", True)), IsCustomized=False, UpdatedBy=user.id, UpdatedAt=now,
                    ConditionText=conditions.sentence(entity, groups, texts.field_labels(session, entity))[:400])
                    .returning(RULE.c.Id)).scalar_one()
                _write_conditions(session, new_id, groups)
                audit.write_audit(session, ACTION_RULE, user.id, OBJECT_RULE, f"{entity_of(entity).name} · {name}",
                                  {"entity_name": entity_of(entity).name, "rule_name": name, "severity": severity, "message": message,
                                   "condition": conditions.sentence(entity, groups, texts.field_labels(session, entity)), "active": bool(change.get("active", True))})
                changed.add(entity)
                continue
            row = session.execute(sa.select(RULE).where(RULE.c.Id == int(rule_id))).mappings().first()
            if row is None:
                raise AppError("validation_rule_not_found", "Kural bulunamadı.", 404)
            rule = dict(row)
            entity = rule["EntityName"]
            shown = f"{entity_of(entity).name} · {rule['Name']}"
            if rule["Kind"] == cat.STRUCTURAL_KIND:
                raise _bad("validation_rule_locked", "Yapısal kontrol değiştirilemez.", f"{shown}: yapısal kontrol kilitli.")
            if change.get("delete"):
                if rule["Kind"] != cat.USER_KIND:
                    raise _bad("validation_rule_builtin_delete", "Hazır kural silinemez.", f"{shown}: hazır kural silinemez, kapatılabilir.")
                old_text = condition_text(session, rule)
                session.execute(sa.delete(FINDING).where(FINDING.c.ValidationRuleId == rule["Id"]))
                session.execute(sa.delete(CONDITION).where(CONDITION.c.ValidationRuleId == rule["Id"]))
                session.execute(sa.delete(RULE).where(RULE.c.Id == rule["Id"]))
                audit.write_audit(session, ACTION_RULE, user.id, OBJECT_RULE, shown, {"entity_name": entity_of(entity).name, "rule_name": rule["Name"], "deleted": True},
                                  {"rule_name": rule["Name"], "severity": rule["Severity"], "condition": old_text})
                changed.add(entity)
                continue
            if change.get("reset"):  # İlk hâline döndür (K-139): katalogdaki ad, mesaj, koşul, sınıf ve aktiflik
                found = cat.by_key().get((entity, rule["Code"]))
                if rule["Kind"] != cat.BUILTIN_KIND or found is None:
                    raise _bad("validation", "Girilen bilgiler geçersiz.", f"{shown}: yalnız hazır kural ilk hâline döner.")
                session.execute(sa.delete(CONDITION).where(CONDITION.c.ValidationRuleId == rule["Id"]))
                session.execute(sa.update(RULE).where(RULE.c.Id == rule["Id"]).values(
                    **engine.catalog_values(found), Severity=found.severity, IsActive=True, IsCustomized=False, UpdatedBy=user.id, UpdatedAt=now))
                audit.write_audit(session, ACTION_RULE, user.id, OBJECT_RULE, shown, {"entity_name": entity_of(entity).name, "rule_name": found.title, "reset": True},
                                  {"rule_name": rule["Name"], "severity": rule["Severity"], "active": bool(rule["IsActive"]), "condition": condition_text(session, rule)})
                changed.add(entity)
                continue
            values, old, new = {}, {}, {}
            if "severity" in change and change["severity"] != rule["Severity"]:
                if change["severity"] not in cat.SEVERITIES:
                    raise _bad("validation", "Girilen bilgiler geçersiz.", "Sınıf Hata, Uyarı ya da Bilgi olmalı.")
                values["Severity"], old["severity"], new["severity"] = change["severity"], rule["Severity"], change["severity"]
            if "active" in change and bool(change["active"]) != bool(rule["IsActive"]):
                values["IsActive"], old["active"], new["active"] = bool(change["active"]), bool(rule["IsActive"]), bool(change["active"])
            if any(k in change for k in ("name", "message", "groups")) and editable(rule):
                if rule["Kind"] == cat.BUILTIN_KIND and not rule["IsCustomized"]:  # ilk düzenleme: katalogdaki koşul veritabanına (K-139)
                    _write_conditions(session, rule["Id"], groups_of(session, rule))
                    values["IsCustomized"] = True
                if "name" in change and (change["name"] or "").strip() != rule["Name"]:
                    name = (change["name"] or "").strip()
                    if not name:
                        raise _bad("validation", "Girilen bilgiler geçersiz.", "Kural adı boş olamaz.")
                    if session.execute(sa.select(RULE.c.Id).where(RULE.c.EntityName == entity, RULE.c.Name == name[:MAX_NAME], RULE.c.Id != rule["Id"])).first():
                        raise _bad("validation_rule_name_taken", "Bu adla kural var.", f"{name}: bu tabloda aynı adla kural var.")
                    values["Name"], old["rule_name"], new["rule_name"] = name[:MAX_NAME], rule["Name"], name
                if "message" in change and (change["message"] or "").strip() != rule["Message"]:
                    message = (change["message"] or "").strip()
                    if not message:
                        raise _bad("validation", "Girilen bilgiler geçersiz.", "Mesaj boş olamaz.")
                    values["Message"], old["message"], new["message"] = message[:MAX_MESSAGE], rule["Message"], message
                if "groups" in change:
                    groups = _parse_groups(entity, change["groups"])
                    before = condition_text(session, rule)
                    _write_conditions(session, rule["Id"], groups)
                    after = conditions.sentence(entity, groups, texts.field_labels(session, entity))
                    values["ConditionText"] = after[:400]
                    if after != before:
                        old["condition"], new["condition"] = before, after
            elif any(k in change for k in ("name", "message", "groups")):
                raise _bad("validation", "Girilen bilgiler geçersiz.", f"{shown}: hazır kuralda yalnız sınıf ve aktiflik değişir.")
            if values or old:
                session.execute(sa.update(RULE).where(RULE.c.Id == rule["Id"]).values(UpdatedBy=user.id, UpdatedAt=now, **values))
                audit.write_audit(session, ACTION_RULE, user.id, OBJECT_RULE, shown, {"entity_name": entity_of(entity).name, "rule_name": rule["Name"], **new}, old)
                changed.add(entity)
        for item in thresholds:
            entity = entity_of(str(item.get("entity") or ""))
            value = _threshold(item.get("value"))
            old_value = session.execute(sa.select(CONFIG.c.ErrorThresholdPct).where(CONFIG.c.EntityName == entity.table)).first()
            before = old_value[0] if old_value else None
            if before == value:
                continue
            if old_value is None:
                session.execute(sa.insert(CONFIG).values(EntityName=entity.table, ErrorThresholdPct=value, UpdatedBy=user.id, UpdatedAt=now))
            else:
                session.execute(sa.update(CONFIG).where(CONFIG.c.EntityName == entity.table).values(ErrorThresholdPct=value, UpdatedBy=user.id, UpdatedAt=now))
            audit.write_audit(session, ACTION_THRESHOLD, user.id, OBJECT_ENTITY, entity.name,
                              {"entity_name": entity.name, "error_threshold": float(value) if value is not None else None},
                              {"entity_name": entity.name, "error_threshold": float(before) if before is not None else None})
        session.commit()
        return {"saved": len(changes) + len(thresholds), "changed_entities": sorted(changed)}

    return auth._db(work)
