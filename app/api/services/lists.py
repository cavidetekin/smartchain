"""Liste sorgusu (K-87, docs/08): kolonlar, parça parça satırlar ve sayılar, liste filtresi değerleri."""
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from ..errors import AppError
from ..lists.definition import ListDefinition, columns as column_list
from ..lists.query import DEFAULT_UNIT_DECIMALS, UNIT, UNIT_DECIMALS, Builder, ListQueryError
from ..lists.groups import build_tree
from ..lists.request import GroupsRequest, QueryRequest, ValuesRequest
from ..repositories import data_versions, export as export_repo, lists as repo

DB_DOWN = "Veritabanına bağlanılamıyor; liste okunamadı."


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
        raise AppError("database_unavailable", DB_DOWN, 503)
    try:
        return work()
    except ListQueryError as exc:
        raise AppError("validation", "Gönderilen veri geçersiz.", 422, exc.details) from exc
    except DBAPIError as exc:
        raise AppError("database_unavailable", DB_DOWN, 503) from exc


def _builder(session: Session, defn: ListDefinition) -> Builder:
    current = data_versions.read_current(session)
    if current is None:
        raise AppError("no_data_version", "Henüz veri yüklenmedi.", 404)
    return Builder(defn, repo.read_labels(session, defn.table_name), current["Id"], today())


def columns(session: Session | None, defn: ListDefinition) -> dict:
    def work():
        limits = export_repo.read_settings(session)
        return {"chunk_size": repo.read_chunk_size(session),
                "columns": column_list(defn, repo.read_labels(session, defn.table_name)),
                "export": {"title": defn.title or defn.name, "file_slug": defn.file_slug or defn.name,
                           "sync_max_rows": limits["ExportSyncMaxRows"], "max_rows": limits["ExportMaxRows"],
                           "file_hours": limits["ExportFileHours"]}}
    return _run(session, work)


def query(session: Session | None, defn: ListDefinition, req: QueryRequest) -> dict:
    def work():
        b = _builder(session, defn)
        rows_q = b.rows_query(req, repo.read_chunk_size(session))
        rows = [{k: _json(v) for k, v in r.items()} for r in repo.fetch_rows(session, rows_q)]
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


def values(session: Session | None, defn: ListDefinition, req: ValuesRequest) -> list[dict]:
    def work():
        b = _builder(session, defn)
        rows = repo.fetch_rows(session, b.values_query(req.field, req.search, req.filters))
        return [{"value": _json(r["value"]), "count": int(r["count"])} for r in rows]
    return _run(session, work)


def groups(session: Session | None, defn: ListDefinition, req: GroupsRequest) -> dict:
    """Grup ağacı, satır sayıları ve ara toplamlar (K-90)."""
    def work():
        b = _builder(session, defn)
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
            raise AppError("too_many_groups", f"Gruplama {max_groups} grubu aşıyor; daha az alanla gruplayın ya da "
                                              "filtreleyin.", 422)
        tree["total"] = repo.fetch_count(session, b.total_query())  # "120 / 840" sayacı (U-12)
        tree["filtered"] = sum(g["count"] for g in tree["groups"])
        return tree
    return _run(session, work)
