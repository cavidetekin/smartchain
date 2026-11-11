"""Entegrasyon tanımı (fonksiyon 91, ekran 02 ve 23, K-130): yöntem, çekim anahtarı, bağlantı, view, test, önizleme.

Ayarlar anında kaydedilir, denetim izine yazılır. Kaynak yalnız okunur (app/integration/sql_source.py).
"""
import time
from collections.abc import Callable

from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app import __version__
from app.integration import contract, structural
from app.integration.sql_source import INCOMPATIBLE, Source, SourceError, ViewCheck, definition_hash, valid_database

from ..errors import AppError
from ..permissions import Access
from ..repositories import audit, integration as repo, lists as lists_repo
from ..repositories.settings import set_setting
from ..settings import get_settings
from . import auth, authz, flows
from .auth import CurrentUser

OBJECT = "IntegrationEntity"
ACTION_METHOD, ACTION_PULL_OFF, ACTION_PULL_ON, ACTION_DEFINITION = "Yöntem değişikliği", "Çekim kapatma", "Çekim açma", "Entegrasyon tanımı"
PREVIEW_ROWS = 20
MAX_REASON = 400


def entity_of(table: str) -> contract.Entity:
    found = contract.entity(table)
    if found is None:
        raise AppError("entity_not_found", "Tablo bulunamadı.", 404)
    return found


def not_configured() -> AppError:
    return AppError("integration_not_configured", "SQL kaynağı tanımlı değil. Entegrasyon ekranından girin.", 409)


def open_source(session: Session, database: str | None = None) -> Source:
    name = database or repo.read_database(session)
    if not name:
        raise not_configured()
    return Source(session.get_bind().url, name, get_settings().db_connect_timeout)


def _source_failure(exc: SourceError) -> AppError:
    return AppError("integration_source", str(exc), 409)


def save_check(session: Session, table: str, check: ViewCheck) -> None:
    repo.save_entity(session, table, LastCheckAt=repo.utcnow(), LastCheckStatus=check.status, LastCheckMessage=check.message,
                     MatchedColumns=check.matched, ExpectedColumns=check.expected, LastContractHash=contract.contract_hash(table))


def save_definition(session: Session, source: Source, table: str, view: str, check: ViewCheck) -> None:
    """Tanım değiştiyse yeni sürüm (K-130). Şifrelenmiş view'da tanım okunamaz: uyarı, sürüm tutulmaz."""
    definition = source.definition(view)
    if definition is None:
        check.warnings.append(f"View şifrelenmiş: {view}; tanımı okunamaz, sürüm tutulmaz.")
        return
    digest = definition_hash(definition)
    last = repo.last_version(session, table, view)
    if last is None or last["DefinitionHash"] != digest:
        repo.add_version(session, table, view, (last["VersionNo"] + 1) if last else 1, digest, definition, __version__)


def inspect_view(session: Session, source: Source, table: str, view: str, labels) -> ViewCheck:
    """Uyum denetimi ve view sürümü. Denetim başarısız olsa da view varsa tanımı kaydedilir (K-130). Hata fırlatmaz, sonuç check.errors'tadır."""
    try:
        check = source.check_view(table, view, labels)
    except SourceError as exc:
        check = ViewCheck(expected=len(contract.fields(table, labels)), errors=[str(exc)])
    if source.view_exists(view):
        save_definition(session, source, table, view, check)
    save_check(session, table, check)
    return check


def _apply_method(session: Session, user: CurrentUser, entity: contract.Entity, row: dict | None, method: str) -> None:
    old = repo.method_of(row)
    if old != method:
        repo.save_entity(session, entity.table, Method=method, UpdatedBy=user.id, UpdatedAt=repo.utcnow())
        audit.write_audit(session, ACTION_METHOD, user.id, OBJECT, entity.name, {"entity_name": entity.name, "pull_method": method}, {"entity_name": entity.name, "pull_method": old})


def _apply_pull(session: Session, user: CurrentUser, entity: contract.Entity, row: dict | None, enabled: bool, reason: str) -> None:
    if repo.is_pull_enabled(row) != enabled:
        now = repo.utcnow()
        repo.save_entity(session, entity.table, IsPullEnabled=enabled, DisabledReason=None if enabled else reason, DisabledBy=None if enabled else user.id,
                         DisabledAt=None if enabled else now, UpdatedBy=user.id, UpdatedAt=now)
        details = {"entity_name": entity.name}
        if not enabled:
            details["reason"] = reason
        audit.write_audit(session, ACTION_PULL_ON if enabled else ACTION_PULL_OFF, user.id, OBJECT, entity.name, details)


def _apply_view(session: Session, user: CurrentUser, source: Source | None, entity: contract.Entity, row: dict | None, name: str) -> None:
    """View gerçekten var olmalı; boş değer temizler. Atanınca uyum hemen denetlenir."""
    if name == ((row or {}).get("ViewName") or ""):
        return
    repo.save_entity(session, entity.table, ViewName=name or None, UpdatedBy=user.id, UpdatedAt=repo.utcnow())
    if name:
        if not source.view_exists(name):
            raise AppError("integration_view_not_found", f"View bulunamadı: {name}.", 422, [{"field": "view", "problem": f"{entity.name}: bu adla view yok."}])
        inspect_view(session, source, entity.table, name, lists_repo.read_labels(session, entity.table))
    audit.write_audit(session, ACTION_DEFINITION, user.id, OBJECT, entity.name, {"entity_name": entity.name, "view": name or None})


def save_entities(session: Session | None, user: CurrentUser, changes: list[dict]) -> dict:
    """Tablo içi düzenlemelerin toplu kaydı (K-132): tek işlem, biri geçersizse hiçbiri yazılmaz. Yöntem ve view yalnız System owner (fonksiyon 96)."""
    session = auth._require(session)
    checked = []
    for change in changes:
        entity = entity_of(change.get("entity", ""))
        if "method" in change or "view" in change:
            authz.ensure(user, 96, Access.WRITE, details={"target": entity.name})
        if "method" in change and change["method"] not in repo.METHODS:
            raise AppError("integration_bad_method", "Yöntem Excel ya da SQL olmalı.", 422, [{"field": "method", "problem": f"{entity.name}: Excel ya da SQL olmalı."}])
        reason = (change.get("reason") or "").strip()
        if change.get("pull_enabled") is False and not reason:
            raise AppError("integration_reason_required", "Kapatma sebebini yazın.", 422, [{"field": "reason", "problem": f"{entity.name}: kapatma sebebini yazın."}])
        if len(reason) > MAX_REASON:
            raise AppError("validation", "Girilen bilgiler geçersiz.", 422, [{"field": "reason", "problem": f"En çok {MAX_REASON} karakter."}])
        checked.append((entity, change, reason))

    def apply_all(source: Source | None) -> None:
        rows = repo.all_entities(session)
        for entity, change, reason in checked:
            if "method" in change:
                _apply_method(session, user, entity, rows.get(entity.table), change["method"])
                rows = repo.all_entities(session)
            if "pull_enabled" in change:
                _apply_pull(session, user, entity, rows.get(entity.table), change["pull_enabled"], reason)
            if "view" in change:
                _apply_view(session, user, source, entity, rows.get(entity.table), (change["view"] or "").strip())

    def work():
        flows.ensure_idle(session)  # K-163: tablo ayarları akış sürerken değişmez
        if any((change.get("view") or "").strip() for _e, change, _r in checked):
            try:
                with open_source(session) as source:
                    apply_all(source)
            except SourceError as exc:
                raise _source_failure(exc) from exc
        else:
            apply_all(None)
        session.commit()
        return {"saved": len(checked)}

    return auth._db(work)


def read_connection(session: Session | None) -> dict:
    session = auth._require(session)

    def work():
        rows = repo.all_entities(session)
        sql = sum(1 for e in contract.ENTITIES if repo.method_of(rows.get(e.table)) == repo.METHOD_SQL)
        counts = repo.batch_counts(session)
        return {"database": repo.read_database(session), "account": repo.account(session), "last_read": counts["last_read"], "last_upload": counts["last_upload"],
                "sql_tables": sql, "excel_tables": len(contract.ENTITIES) - sql}

    return auth._db(work)


def write_connection(session: Session | None, user: CurrentUser, database: str) -> dict:
    session = auth._require(session)
    name = (database or "").strip()
    if name and not valid_database(name):
        raise AppError("validation", "Girilen bilgiler geçersiz.", 422, [{"field": "database", "problem": "Yalnız harf, rakam ve alt çizgi."}])

    def work():
        set_setting(session, repo.DATABASE_KEY, name)
        audit.write_audit(session, ACTION_DEFINITION, user.id, OBJECT, name or "-", {"database": name or None})
        session.commit()

    auth._db(work)
    return read_connection(session)


def _step(steps: list[dict], key: str, label: str, work: Callable[[], str]) -> bool:
    start = time.perf_counter()
    try:
        detail, ok = work(), True
    except SourceError as exc:
        detail, ok = str(exc), False
    except DBAPIError:
        detail, ok = "Okunamadı.", False
    steps.append({"key": key, "label": label, "ok": ok, "detail": detail, "ms": round((time.perf_counter() - start) * 1000)})
    return ok


def test_connection(session: Session | None) -> dict:
    """Adım adım: erişim, kimlik, sinyal tablosu, view'lar. Kaynak yalnız okunur; sonuç satıra "son denetim" olarak yazılır."""
    session = auth._require(session)

    def work():
        rows = repo.all_entities(session)
        steps: list[dict] = []
        tables: list[dict] = []
        name = repo.read_database(session)
        if not name:
            raise not_configured()
        try:
            with open_source(session, name) as source:
                steps.append({"key": "access", "label": "Sunucu erişimi", "ok": True, "detail": name, "ms": 0})
                if not _step(steps, "identity", "Kimlik", lambda: _identity(source)):
                    return {"database": name, "ok": False, "steps": steps, "tables": []}
                _step(steps, "signal", "Bitti sinyali", lambda: _signal_detail(source))
                for entity in contract.ENTITIES:
                    row = rows.get(entity.table)
                    if repo.method_of(row) != repo.METHOD_SQL or not (row or {}).get("ViewName"):
                        continue
                    tables.append(_check_table(session, source, entity, row["ViewName"]))
                session.commit()
                bad = [t["name"] for t in tables if t["status"] == INCOMPATIBLE]
                steps.append({"key": "views", "label": "View'lar", "ok": not bad, "ms": 0,
                              "detail": f"{len(tables)} view denetlendi" + (f"; uymayan: {', '.join(bad)}" if bad else "")})
        except SourceError as exc:
            steps.append({"key": "access", "label": "Sunucu erişimi", "ok": False, "detail": str(exc), "ms": 0})
        return {"database": name, "ok": all(s["ok"] for s in steps), "steps": steps, "tables": tables}

    return auth._db(work)


def _identity(source: Source) -> str:
    who = source.account()
    if not source.can_read():
        raise SourceError(f"{who} bu kaynağı okuyamıyor.")
    return f"{who} · okuma yetkisi var"


def _signal_detail(source: Source) -> str:
    if not source.has_signal_table():
        raise SourceError("ERP_LoadLog tablosu bulunamadı.")
    return "ERP_LoadLog bulundu"


def _check_table(session: Session, source: Source, entity: contract.Entity, view: str) -> dict:
    """Tekrar eden anahtar alan uyumunu etkilemez, not olarak yazılır."""
    check = inspect_view(session, source, entity.table, view, lists_repo.read_labels(session, entity.table))
    notes = []
    if not check.errors:
        duplicates = source.duplicate_keys(entity.table, view, check.columns)
        if duplicates:
            notes.append(f"Tekrar eden anahtar: {duplicates} kayıt.")
    return {"entity": entity.table, "name": entity.name, "view": view, "status": check.status, "matched": check.matched, "expected": check.expected,
            "errors": check.errors, "warnings": check.warnings, "notes": notes}


def preview(session: Session | None, table: str) -> dict:
    """20 satır, Excel'le aynı kontrol kodundan; hiçbir şey yazılmaz."""
    session = auth._require(session)
    entity = entity_of(table)

    def work():
        row = repo.get_entity(session, table)
        view = (row or {}).get("ViewName")
        if not view:
            raise AppError("integration_view_missing", "Bu tablonun view'ı tanımlı değil.", 409)
        labels = lists_repo.read_labels(session, table)
        checker = structural.RowChecker(table, labels)
        try:
            with open_source(session) as source:
                check = source.check_view(table, view, labels)
                sample = source.sample(view, check.columns, PREVIEW_ROWS) if not check.errors else []
        except SourceError as exc:
            raise _source_failure(exc) from exc
        out = []
        for number, raw in sample:
            _converted, found = checker.check(number, raw)
            out.append({"values": {k: _plain(v) for k, v in raw.items()},
                        "findings": [{"severity": f.severity, "field": f.field, "message": f.message} for f in found]})
        names = {f.name: f.label for f in checker.fields}
        return {"entity": table, "name": entity.name, "view": view, "status": check.status, "errors": check.errors, "warnings": check.warnings,
                "columns": [{"field": c, "label": names.get(c, c)} for c in check.columns], "rows": out}

    return auth._db(work)


def _plain(value):
    return value if value is None or isinstance(value, (str, int, float, bool)) else str(value)


def view_versions(session: Session | None, table: str) -> list[dict]:
    session = auth._require(session)
    entity_of(table)
    return auth._db(lambda: [{"version": r["VersionNo"], "view": r["ViewName"], "seen_at": r["SeenAt"], "app_version": r["AppVersion"], "definition": r["Definition"]}
                             for r in repo.versions(session, table)])

