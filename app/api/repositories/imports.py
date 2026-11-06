"""Excel yükleme sorguları (fonksiyon 03, K-129): parti, bulgu, ham veri."""
from collections.abc import Iterable, Sequence
from datetime import datetime, timezone

import pyodbc
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.integration import structural
from app.integration.contract import TemplateField
from app.jobs.settings import IMPORT_DEFAULTS, read_int_settings
from db.models import metadata

BATCH = metadata.tables["adm.ImportBatch"]
FINDING = metadata.tables["adm.ImportFinding"]

METHOD_EXCEL = "Excel"
PENDING, RECEIVED, FAILED, INCOMPLETE, CANCELLED = "Ön kontrol", "Alındı", "Hatalı", "Tamamlanmadı", "Vazgeçildi"
ROW_NEW = "Yeni"

_NO_LENGTH = 255


def read_settings(session: Session) -> dict[str, int]:
    return read_int_settings(session, IMPORT_DEFAULTS)


def create_batch(session: Session, table: str, mode: str, file_name: str, user_id: int, version: int | None) -> int:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    result = session.execute(sa.insert(BATCH).values(
        Method=METHOD_EXCEL, EntityName=table, LoadType=mode, ReceivedAt=now, Status=PENDING,
        UploadedBy=user_id, FileName=file_name[:255], TemplateVersion=version).returning(BATCH.c.Id))
    return result.scalar_one()


def set_batch(session: Session, batch_id: int, **values) -> None:
    session.execute(sa.update(BATCH).where(BATCH.c.Id == batch_id).values(**values))


def get_batch(session: Session, batch_id: int) -> dict | None:
    row = session.execute(sa.select(BATCH).where(BATCH.c.Id == batch_id)).mappings().first()
    return dict(row) if row else None


def status_of(session: Session, batch_id: int) -> str | None:
    return session.execute(sa.select(BATCH.c.Status).where(BATCH.c.Id == batch_id)).scalar_one_or_none()


def open_batches(session: Session, table: str, user_id: int) -> list[dict]:
    """Kullanıcının bu tablodaki açık ön kontrolleri, yeniden eskiye. Okunan SQL partisi ön kontrol değildir (K-130)."""
    rows = session.execute(sa.select(BATCH).where(BATCH.c.EntityName == table, BATCH.c.UploadedBy == user_id, BATCH.c.Status == PENDING, BATCH.c.Method == METHOD_EXCEL)
                           .order_by(BATCH.c.Id.desc())).mappings().all()
    return [dict(r) for r in rows]


def clear_batch_rows(session: Session, table: str, batch_id: int, findings: bool = True) -> None:
    t = metadata.tables[f"stg.{table}"]
    session.execute(sa.delete(t).where(t.c.ImportBatchId == batch_id))
    if findings:
        session.execute(sa.delete(FINDING).where(FINDING.c.ImportBatchId == batch_id))


def _size(field: TemplateField, length: int | None):
    if field.kind == "text":
        return (pyodbc.SQL_WVARCHAR, length or _NO_LENGTH, 0)
    if field.kind in ("integer", "bool"):
        return (pyodbc.SQL_INTEGER, 0, 0)
    if field.kind == "number":
        return (pyodbc.SQL_FLOAT, 0, 0)
    return (pyodbc.SQL_TYPE_TIMESTAMP, 27, 7)


def _bulk(session: Session, statement: str, sizes: Sequence, rows: Sequence[Sequence]) -> None:
    """fast_executemany kolon tiplerini açıkça ister: boş değerle başlayan kolonda tip tahmini satırı düşürür (K-129)."""
    if not rows:
        return
    cursor = session.connection().connection.cursor()
    try:
        cursor.fast_executemany = True
        cursor.setinputsizes(list(sizes))
        cursor.executemany(statement, list(rows))
    finally:
        cursor.close()


def insert_rows(session: Session, table: str, found: Sequence[TemplateField], batch_id: int, rows: Iterable[tuple[int, dict]]) -> None:
    """Geçerli satırlar; RowStatus Yeni, SourceRowNo Excel satırı."""
    t = metadata.tables[f"stg.{table}"]
    names = [f.name for f in found]
    columns = ", ".join(f"[{n}]" for n in ["ImportBatchId", "RowStatus", "SourceRowNo", *names])
    marks = ", ".join("?" * (3 + len(names)))
    sizes = [(pyodbc.SQL_BIGINT, 0, 0), (pyodbc.SQL_WVARCHAR, 15, 0), (pyodbc.SQL_INTEGER, 0, 0),
             *[_size(f, getattr(t.c[f.name].type, "length", None)) for f in found]]
    data = [(batch_id, ROW_NEW, number, *[row.get(n) for n in names]) for number, row in rows]
    _bulk(session, f"INSERT INTO stg.[{table}] ({columns}) VALUES ({marks})", sizes, data)


def insert_findings(session: Session, batch_id: int, findings: Iterable[structural.Finding]) -> None:
    data = [(batch_id, f.row, f.severity, f.check, (f.field or None) and f.field[:200], f.value, f.message[:400], f.key) for f in findings]
    sizes = [(pyodbc.SQL_BIGINT, 0, 0), (pyodbc.SQL_INTEGER, 0, 0), (pyodbc.SQL_WVARCHAR, 10, 0), (pyodbc.SQL_WVARCHAR, 30, 0),
             (pyodbc.SQL_WVARCHAR, 200, 0), (pyodbc.SQL_WVARCHAR, 255, 0), (pyodbc.SQL_WVARCHAR, 400, 0), (pyodbc.SQL_WVARCHAR, 200, 0)]
    _bulk(session, "INSERT INTO adm.ImportFinding (ImportBatchId, RowNo, Severity, CheckCode, FieldName, [Value], Message, RowKey) "
                   "VALUES (?, ?, ?, ?, ?, ?, ?, ?)", sizes, data)


def remove_duplicates(session: Session, table: str, batch_id: int) -> list[structural.Finding]:
    """Tekrar eden anahtarın bütün satırları ham veriden çıkar (K-129); bulguları döner."""
    if not structural.has_key(table):
        return []
    rows = session.execute(structural.duplicate_query(table, batch_id)).mappings().all()
    if not rows:
        return []
    keys = structural.key_fields(table)
    groups: dict[int, list] = {}
    for r in rows:
        groups.setdefault(r["grp"], []).append(r)
    out = []
    for group in groups.values():
        first = group[0]
        message = structural.duplicate_message([r["SourceRowNo"] for r in group])
        row_key = " · ".join(str(first[k]) for k in keys if first[k] is not None)[:200] or None
        out += [structural.Finding(structural.ERROR, "duplicate_key", message, r["SourceRowNo"], key=row_key) for r in group]  # alan ve değer boş
    t = metadata.tables[f"stg.{table}"]
    ids = [r["StagingRowId"] for r in rows]
    for start in range(0, len(ids), 1000):
        session.execute(sa.delete(t).where(t.c.StagingRowId.in_(ids[start:start + 1000])))
    return out


def counts(session: Session, batch_id: int) -> dict[str, int]:
    """Hatalı satır sayısı, uyarı ve bilgi sayısı (dosya düzeyi dahil)."""
    errors = session.execute(sa.select(sa.func.count(sa.distinct(FINDING.c.RowNo)))
                             .where(FINDING.c.ImportBatchId == batch_id, FINDING.c.Severity == structural.ERROR)).scalar_one()
    notes = session.execute(sa.select(sa.func.count()).select_from(FINDING)
                            .where(FINDING.c.ImportBatchId == batch_id, FINDING.c.Severity != structural.ERROR)).scalar_one()
    return {"errors": errors, "notes": notes}


def file_findings(session: Session, batch_id: int) -> list[dict]:
    rows = session.execute(sa.select(FINDING.c.Severity, FINDING.c.Message).where(FINDING.c.ImportBatchId == batch_id, FINDING.c.RowNo.is_(None))
                           .order_by(FINDING.c.Id)).all()
    return [{"severity": r.Severity, "message": r.Message} for r in rows]


def error_messages(session: Session, batch_id: int) -> dict[int, list[str]]:
    """Excel satırı → hata metinleri."""
    rows = session.execute(sa.select(FINDING.c.RowNo, FINDING.c.FieldName, FINDING.c.Message)
                           .where(FINDING.c.ImportBatchId == batch_id, FINDING.c.Severity == structural.ERROR, FINDING.c.RowNo.is_not(None))
                           .order_by(FINDING.c.RowNo, FINDING.c.Id)).all()
    out: dict[int, list[str]] = {}
    for r in rows:
        out.setdefault(r.RowNo, []).append(f"{r.FieldName}: {r.Message}" if r.FieldName else r.Message)
    return out
