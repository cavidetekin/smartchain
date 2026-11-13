"""Liste sorgusu (K-87, docs/08): kolonlar, parça parça satırlar ve sayılar, liste filtresi değerleri."""
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from ..errors import DB_UNAVAILABLE, AppError
from ..lists.definition import ListDefinition, columns as column_list
from ..lists.query import DEFAULT_UNIT_DECIMALS, SELECTION_MAX, UNIT, UNIT_DECIMALS, Builder, ListQueryError
from ..lists.groups import build_tree
from ..lists.request import GroupsRequest, IdsRequest, QueryRequest, ValuesRequest
from app.manual import manual_fields

from ..repositories import data_versions, export as export_repo, lists as repo
from . import manual_values


RULES = "_rules"  # satırda tutan kurallar (K-95, docs/08)


def today() -> date:
    """Göreli tarih filtresinin "bugün"ü: API sunucusunun yerel tarihi (docs/08). Testte değiştirilir."""
    return date.today()


def _json(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):  # veritabanında UTC (SYSUTCDATETIME)
        return value.replace(tzinfo=timezone.utc).isoformat(timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    return value


def _run(session: Session | None, work):
    if session is None:
        raise AppError("database_unavailable", DB_UNAVAILABLE, 503)
    try:
        return work()
    except ListQueryError as exc:
        raise AppError("validation", "Girilen bilgiler geçersiz.", 422, exc.details) from exc
    except DBAPIError as exc:
        raise AppError("database_unavailable", DB_UNAVAILABLE, 503) from exc


def _builder(session: Session, defn: ListDefinition, role: str | None = None, user_id: int | None = None) -> Builder:
    """role, user_id: oturumdaki kullanıcı (row_scope); verilmezse en dar kapsam."""
    if not defn.versioned:
        return Builder(defn, repo.read_labels(session, defn.table_name), None, today(), role, user_id)
    current = data_versions.read_current(session)
    if current is None:
        raise AppError("no_data_version", "Henüz veri yüklenmedi.", 404)
    return Builder(defn, repo.read_labels(session, defn.table_name), current["Id"], today(), role, user_id)


def columns(session: Session | None, defn: ListDefinition) -> dict:
    def work():
        limits = export_repo.read_settings(session)
        return {"chunk_size": repo.read_chunk_size(session),
                "columns": column_list(defn, repo.read_labels(session, defn.table_name),
                                       manual=frozenset(manual_fields(session, defn.manual_table)) if defn.manual_table else frozenset()),
                "export": {"title": defn.title or defn.name, "file_slug": defn.file_slug or defn.name,
                           "sync_max_rows": limits["ExportSyncMaxRows"], "max_rows": limits["ExportMaxRows"],
                           "file_hours": limits["ExportFileHours"]}}
    return _run(session, work)


def query(session: Session | None, defn: ListDefinition, req: QueryRequest, role: str | None = None,
          user_id: int | None = None) -> dict:
    def work():
        b = _builder(session, defn, role, user_id)
        rows_q = b.rows_query(req, repo.read_chunk_size(session))
        rules_valid = b.rule_columns(req.rules)  # doğrulama (422) satırlar okunmadan
        rows = [{k: _json(v) for k, v in r.items()} for r in repo.fetch_rows(session, rows_q)]
        for field_name, fn in defn.value_format.items():
            for r in rows:
                if field_name in r:
                    r[field_name] = fn(r[field_name])
        if defn.row_format:  # satıra bağlı okunur biçim (K-173)
            defn.row_format(rows)
        if req.rules:  # tutan kuralların istekteki sırası (K-95); dönen satırlarda ayrı sorguyla
            hit = {}
            if rows and rules_valid:
                for r in repo.fetch_rows(session, b.rules_by_id_query([r["Id"] for r in rows], req.rules)):
                    hit[r["Id"]] = [i for i in range(len(req.rules)) if r[f"_r{i}"]]
            for r in rows:
                r[RULES] = hit.get(r["Id"], [])
        if defn.manual_table:  # hücre kaynağı: manuel değer ve kural (K-170)
            manual_values.annotate(session, defn.manual_table, rows)
        if defn.unit_field:  # her satırda temel birimin ondalığı (K-88); birim bilinmiyorsa 2
            units = repo.read_unit_decimals(session)
            for r in rows:
                d = units.get(r.pop(UNIT))
                r[UNIT_DECIMALS] = DEFAULT_UNIT_DECIMALS if d is None else int(d)
        total = repo.fetch_count(session, b.total_query())
        narrowed = req.filters or req.group_key
        filtered = repo.fetch_count(session, b.filtered_query(req.filters, req.group_key)) if narrowed else total
        return {"rows": rows, "offset": req.offset, "filtered": filtered, "total": total}
    return _run(session, work)


def ids(session: Session | None, defn: ListDefinition, req: IdsRequest, role: str | None = None, user_id: int | None = None) -> dict:
    """Filtredeki satırların kimlikleri (çoklu seçim, K-171), en çok SELECTION_MAX."""
    def work():
        b = _builder(session, defn, role, user_id)
        found = [r["Id"] for r in repo.fetch_rows(session, b.ids_query(req.filters, SELECTION_MAX))]
        return {"ids": [str(i) for i in found[:SELECTION_MAX]], "truncated": len(found) > SELECTION_MAX}
    return _run(session, work)


def values(session: Session | None, defn: ListDefinition, req: ValuesRequest, role: str | None = None,
           user_id: int | None = None) -> list[dict]:
    def work():
        b = _builder(session, defn, role, user_id)
        rows = repo.fetch_rows(session, b.values_query(req.field, req.search, req.filters))
        return [{"value": _json(r["value"]), "count": int(r["count"])} for r in rows]
    return _run(session, work)


def groups(session: Session | None, defn: ListDefinition, req: GroupsRequest, role: str | None = None,
           user_id: int | None = None) -> dict:
    """Grup ağacı, satır sayıları ve ara toplamlar (K-90)."""
    def work():
        b = _builder(session, defn, role, user_id)
        max_groups = repo.read_max_groups(session)
        specs = b.aggregate_specs(req.fields, req.aggregates)
        # birim gizli düzey olabilir: satır sayısı yaprak grup sayısından fazla olabilir; üst sınır geniş tutulur
        q, fields = b.groups_query(req.group_by, req.filters, req.sort, specs, (max_groups + 1) * 20)
        leaves = repo.fetch_rows(session, q)
        units = repo.read_unit_decimals(session) if defn.unit_field else {}
        unit_relevant = {f for f, spec in specs.items() if b.unit_relevant(f, spec)}
        tree = build_tree(leaves, len(fields), {f: s.fn for f, s in specs.items()}, unit_relevant, _json, units)
        tree["aggregate_specs"] = {f: s.model_dump(exclude_none=True) for f, s in specs.items()}
        if tree["leaf_groups"] > max_groups:
            raise AppError("too_many_groups", f"En çok {max_groups} grup gösterilebilir.", 422)
        tree["total"] = repo.fetch_count(session, b.total_query())  # "120 / 840" sayacı (U-12)
        tree["filtered"] = sum(g["count"] for g in tree["groups"])
        return tree
    return _run(session, work)
