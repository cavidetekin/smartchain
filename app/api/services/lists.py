"""Liste sorgusu (K-87, docs/08): kolonlar, parça parça satırlar ve sayılar, liste filtresi değerleri."""
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from ..errors import AppError
from ..lists.definition import ListDefinition, columns as column_list
from ..lists.query import Builder, ListQueryError
from ..lists.request import QueryRequest, ValuesRequest
from ..repositories import data_versions, lists as repo

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


def columns(session: Session | None, defn: ListDefinition) -> list[dict]:
    return _run(session, lambda: column_list(defn, repo.read_labels(session, defn.table_name)))


def query(session: Session | None, defn: ListDefinition, req: QueryRequest) -> dict:
    def work():
        b = _builder(session, defn)
        rows = [{k: _json(v) for k, v in r.items()} for r in repo.fetch_rows(session, b.rows_query(req))]
        total = repo.fetch_count(session, b.total_query())
        filtered = repo.fetch_count(session, b.filtered_query(req.filters)) if req.filters else total
        return {"rows": rows, "offset": req.offset, "filtered": filtered, "total": total}
    return _run(session, work)


def values(session: Session | None, defn: ListDefinition, req: ValuesRequest) -> list[dict]:
    def work():
        b = _builder(session, defn)
        rows = repo.fetch_rows(session, b.values_query(req.field, req.search, req.filters))
        return [{"value": _json(r["value"]), "count": int(r["count"])} for r in rows]
    return _run(session, work)
