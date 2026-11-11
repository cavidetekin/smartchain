"""Dünden bugüne (fonksiyon 101; K-133, K-159, K-160): tablonun ham verideki son hâli ile önceki günün son hâlinin karşılaştırması.

Parti ile parti değil, tablonun iki hâli karşılaştırılır; bu yüzden Ekle / güncelle yüklemesi "gelmeyen" üretmez.
Bugün: güncel hâl (`IsCurrent = 1`). Dün anı: son verinin gününden önceki günlerde işlenen son partinin zamanı (`AppliedAt`; gün sunucunun yerel günü).
Dün: partisi o andan önce işlenmiş ve o anda güncel hâlden çıkmamış satırlar (`SupersededAt`).

Sonuç tablo başına saklanır (`RawCompare`, `RawCompareRow`); tablo validasyon işinin başında hesaplanır, güncelse atlanır.
"""
import logging
import re
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.integration.contract import stg_columns
from app.integration.structural import key_fields
from app.validation.sqlkit import labels as standard_labels
from db.models import metadata

log = logging.getLogger("smartchain.compare")

READY, NO_PREVIOUS, FAILED = "Hazır", "Önceki veri yok", "Hesaplanamadı"
NEW, MISSING, CHANGED = "Yeni", "Gelmeyen", "Güncellenen"
FULL = "Tam"
LOAD_FULL, LOAD_CHANGED, LOAD_MIXED = "Tam", "Ekle / güncelle", "Karma"
BATCH = metadata.tables["adm.ImportBatch"]
SUMMARY = metadata.tables["adm.RawCompare"]
ROW = metadata.tables["adm.RawCompareRow"]
FIELD_DEFINITION = metadata.tables["adm.FieldDefinition"]
ADDITIONAL = re.compile(r"Additional(Text|Number)\d+$")
BIN = "Latin1_General_100_BIN2"   # aktarımla aynı: büyük/küçük harf farkı değişikliktir


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def day_start_utc(at: datetime) -> datetime:
    """UTC zamanın düştüğü yerel günün başlangıcı, UTC olarak (gün sunucunun yerel günü)."""
    local = at.replace(tzinfo=timezone.utc).astimezone()
    return local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc).replace(tzinfo=None)


def _latest(session: Session, entity: str, before: datetime | None = None) -> datetime | None:
    query = sa.select(sa.func.max(BATCH.c.AppliedAt)).where(BATCH.c.EntityName == entity)
    if before is not None:
        query = query.where(BATCH.c.AppliedAt < before)
    return session.execute(query).scalar()


def moments(session: Session, entity: str) -> tuple[datetime | None, datetime | None]:
    """(son veri zamanı, dün anı). Aynı gün gelen yeni yükleme dün anını değiştirmez (K-160)."""
    today_at = _latest(session, entity)
    if today_at is None:
        return None, None
    return today_at, _latest(session, entity, day_start_utc(today_at))


def baseline_at(session: Session, entity: str) -> datetime | None:
    """Dün anı: temizlik bundan sonra güncel hâlden çıkan satırları silmez (K-160)."""
    return moments(session, entity)[1]


def _today_load(session: Session, entity: str, today_at: datetime) -> str:
    kinds = set(session.execute(sa.select(BATCH.c.LoadType).where(BATCH.c.EntityName == entity, BATCH.c.AppliedAt >= day_start_utc(today_at),
                                                                  BATCH.c.AppliedAt <= today_at).distinct()).scalars())
    if len(kinds) > 1:
        return LOAD_MIXED
    return LOAD_FULL if kinds == {FULL} else LOAD_CHANGED


def _quote(text: str) -> str:
    return text.replace("'", "''")


def _join_key(keys: list[str]) -> str:
    """Eşleştirme anahtarı: boş alan konumu korunur; harf duyarlılığı güncel hâle işlemeyle aynı (veritabanı harmanlaması)."""
    return "CONCAT(" + ", NCHAR(31), ".join(f"CONVERT(nvarchar(200), t.[{k}])" for k in keys) + ", NCHAR(31)) COLLATE DATABASE_DEFAULT"


def _row_key(columns: dict[str, sa.Column], keys: list[str]) -> str:
    """Ekranda görünen kayıt: boş alanlar atlanır (validasyondaki kayıt anahtarıyla aynı biçim)."""
    parts = [f"CONVERT(nvarchar(10), t.[{k}], 104)" if isinstance(columns[k].type, (sa.Date, sa.DateTime)) else f"CAST(t.[{k}] AS nvarchar(200))" for k in keys]
    if len(parts) == 1:
        return f"LEFT({parts[0]}, 200)"
    return f"LEFT(CONCAT_WS(N' · ', {', '.join(parts)}), 200)"


def _text_of(column: sa.Column, ref: str) -> str:
    """Değerin okunur metni (Türkçe sayı ve tarih)."""
    kind = column.type
    if isinstance(kind, sa.Boolean):
        return f"CASE {ref} WHEN 1 THEN N'Evet' WHEN 0 THEN N'Hayır' END"
    if isinstance(kind, sa.Date):
        return f"FORMAT({ref}, N'dd.MM.yyyy')"
    if isinstance(kind, sa.Integer):
        return f"CONVERT(nvarchar(30), {ref})"
    if isinstance(kind, sa.Numeric):
        return f"FORMAT({ref}, N'#,##0.####', N'tr-TR')"
    return f"LEFT({ref}, 400)"


def _differs(column: sa.Column) -> str:
    """Boşlar eşit; boşla dolu farklıdır. Metinde büyük/küçük harf farkı değişikliktir."""
    name = column.name
    collate = f" COLLATE {BIN}" if isinstance(column.type, sa.Unicode) else ""
    return f"CASE WHEN o.[{name}]{collate} = n.[{name}]{collate} THEN 0 WHEN o.[{name}] IS NULL AND n.[{name}] IS NULL THEN 0 ELSE 1 END"


def _compared(session: Session, entity: str, keys: list[str]) -> list[tuple[sa.Column, str]]:
    """Karşılaştırılan alanlar ve etiketleri: anahtar dışı; etiketsiz ek alan karşılaştırılmaz (K-88, K-160)."""
    custom = dict(session.execute(sa.select(FIELD_DEFINITION.c.FieldName, FIELD_DEFINITION.c.Label)
                                  .where(FIELD_DEFINITION.c.TableName == entity, FIELD_DEFINITION.c.Label.is_not(None), FIELD_DEFINITION.c.Label != "")).all())
    standard = standard_labels(entity)
    out = []
    for column in stg_columns(entity):
        if column.name in keys or (ADDITIONAL.match(column.name) and column.name not in custom):
            continue
        out.append((column, (custom.get(column.name) or standard.get(column.name) or column.name)[:200]))
    return out


def _write_summary(session: Session, entity: str, **values) -> None:
    session.execute(sa.delete(SUMMARY).where(SUMMARY.c.EntityName == entity))
    session.execute(sa.insert(SUMMARY).values(EntityName=entity, ComputedAt=utcnow(), **values))


def compute(session: Session, entity: str) -> None:
    """Tablonun karşılaştırmasını yeniden yazar; commit çağıranındır."""
    today_at, yesterday_at = moments(session, entity)
    session.execute(sa.delete(ROW).where(ROW.c.EntityName == entity))
    if today_at is None:
        session.execute(sa.delete(SUMMARY).where(SUMMARY.c.EntityName == entity))
        return
    t = metadata.tables[f"stg.{entity}"]
    load = _today_load(session, entity, today_at)
    if yesterday_at is None:
        rows = session.execute(sa.select(sa.func.count()).select_from(t).where(t.c.IsCurrent == sa.true())).scalar_one()
        _write_summary(session, entity, TodayAt=today_at, YesterdayAt=None, TodayLoad=load, TodayRows=rows, State=NO_PREVIOUS)
        return
    keys = key_fields(entity)
    columns = {c.name: c for c in t.c}
    join_key, row_key = _join_key(keys), _row_key(columns, keys)
    table = f"stg.[{entity}]"
    params = {"e": entity, "b": yesterday_at}
    run = lambda sql, **extra: session.execute(sa.text(sql), {**params, **extra})  # noqa: E731
    run("DROP TABLE IF EXISTS #rc_new")
    run("DROP TABLE IF EXISTS #rc_old")
    try:
        for name in ("#rc_new", "#rc_old"):  # açıkça: parametreli SELECT INTO'nun geçici tablosu kendi kapsamında kalır
            run(f"CREATE TABLE {name} (Id bigint NOT NULL, K nvarchar(2200) COLLATE DATABASE_DEFAULT NOT NULL, RowKey nvarchar(200) COLLATE DATABASE_DEFAULT NULL)")
        run(f"INSERT INTO #rc_new (Id, K, RowKey) SELECT t.StagingRowId, {join_key}, {row_key} FROM {table} t WHERE t.IsCurrent = 1")
        run(f"""INSERT INTO #rc_old (Id, K, RowKey) SELECT d.Id, d.K, d.RowKey FROM (
                    SELECT t.StagingRowId AS Id, {join_key} AS K, {row_key} AS RowKey,
                           ROW_NUMBER() OVER (PARTITION BY {join_key} ORDER BY t.StagingRowId DESC) AS Rn
                    FROM {table} t JOIN adm.ImportBatch b ON b.Id = t.ImportBatchId
                    WHERE b.AppliedAt <= :b AND (t.IsCurrent = 1 OR t.SupersededAt > :b)) d WHERE d.Rn = 1""")
        added = run(f"""INSERT INTO adm.RawCompareRow (EntityName, Kind, StagingRowId, RowKey)
                        SELECT :e, N'{NEW}', n.Id, COALESCE(n.RowKey, N'') FROM #rc_new n WHERE NOT EXISTS (SELECT 1 FROM #rc_old o WHERE o.K = n.K)""").rowcount
        missing = run(f"""INSERT INTO adm.RawCompareRow (EntityName, Kind, StagingRowId, RowKey)
                          SELECT :e, N'{MISSING}', o.Id, COALESCE(o.RowKey, N'') FROM #rc_old o WHERE NOT EXISTS (SELECT 1 FROM #rc_new n WHERE n.K = o.K)""").rowcount
        fields = _compared(session, entity, keys)
        values = ", ".join(f"(N'{_quote(label)}', CASE WHEN {_differs(c)} = 1 THEN {_text_of(c, f'o.[{c.name}]')} END, "
                           f"CASE WHEN {_differs(c)} = 1 THEN {_text_of(c, f'n.[{c.name}]')} END, {_differs(c)})" for c, label in fields)
        run(f"""INSERT INTO adm.RawCompareRow (EntityName, Kind, StagingRowId, RowKey, FieldLabel, OldValue, NewValue)
                SELECT :e, N'{CHANGED}', a.Id, COALESCE(a.RowKey, N''), v.Label, v.Old, v.New
                FROM #rc_new a JOIN #rc_old z ON z.K = a.K
                JOIN {table} n ON n.StagingRowId = a.Id JOIN {table} o ON o.StagingRowId = z.Id
                CROSS APPLY (VALUES {values}) v(Label, Old, New, D) WHERE v.D = 1""")
        counts = run("SELECT (SELECT COUNT(*) FROM #rc_old), (SELECT COUNT(*) FROM #rc_new)").one()
    finally:
        run("DROP TABLE IF EXISTS #rc_new")
        run("DROP TABLE IF EXISTS #rc_old")
    changed = session.execute(sa.select(sa.func.count(sa.distinct(ROW.c.StagingRowId))).where(ROW.c.EntityName == entity, ROW.c.Kind == CHANGED)).scalar_one()
    _write_summary(session, entity, TodayAt=today_at, YesterdayAt=yesterday_at, TodayLoad=load, YesterdayRows=counts[0], TodayRows=counts[1],
                   NewCount=added, MissingCount=missing, ChangedCount=changed, State=READY)


def refresh(session: Session, entity: str) -> None:
    """Sonuç güncel değilse hesaplar ve commit eder. Hesap düşerse validasyon sürer, satırda "Hesaplanamadı" yazar (K-160)."""
    latest = _latest(session, entity)
    if latest is None:
        return
    row = session.execute(sa.select(SUMMARY.c.TodayAt, SUMMARY.c.State).where(SUMMARY.c.EntityName == entity)).first()
    if row is not None and row.TodayAt == latest and row.State != FAILED:
        return
    try:
        compute(session, entity)
        session.commit()
    except Exception:
        log.exception("Dünden bugüne hesabı düştü: %s", entity)
        session.rollback()
        session.execute(sa.delete(ROW).where(ROW.c.EntityName == entity))
        _write_summary(session, entity, TodayAt=latest, TodayLoad=_today_load(session, entity, latest), TodayRows=0, State=FAILED)
        session.commit()
