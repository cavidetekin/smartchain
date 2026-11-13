"""Eski geçmişin bir kerelik doldurulması (K-173; geçiş 0055).

Versiyonlu tablolarda: her kaydın ilk versiyonu "Kayıt oluştu", ardışık versiyonlar arasında değişen alanlar "Değişti", son versiyonu kapanan
kayıt "Kayıt kapandı" (kaynak aktarım; zaman ve kullanıcı veri versiyonundan). Manuel değer gören hücrelerin (bugün manuel değeri olan ya da
denetim izinde manuel değer kaydı olan) farkı yazılmaz: yerinde güncelleme versiyon satırını değiştirdiği için fark aktarıma ait değildir;
manuel değer satırları denetim izinden eklenir. Lokasyon ve Birim versiyonsuzdur: yalnız "Kayıt oluştu" (ilk veri versiyonuyla).
"""
import json
from decimal import Decimal

import sqlalchemy as sa

from app.manual import KEY_LENGTH, MANUAL, SCREEN_TABLES, UNVERSIONED, as_text, core_table
from db.models import metadata

from . import CHANGED, CLOSED, CREATED, DATA_VERSION, FIELD_CHANGE, MANUAL_REMOVE, MANUAL_SOURCE, TRANSFER, VALUE_LENGTH, tracked_columns

AUDIT = metadata.tables["adm.AuditLog"]
MANUAL_OBJECT = "Manuel değer"
SAVE_ACTION, REMOVE_ACTION = "Manuel değer girildi", "Manuel değer kaldırıldı"
CELLS = sa.Table("#fc_manual", sa.MetaData(), sa.Column("TableName", sa.Unicode(60)), sa.Column("RecordKey", sa.Unicode(KEY_LENGTH)),
                 sa.Column("FieldName", sa.Unicode(60)))


def _differs(a, b) -> sa.ColumnElement:
    return sa.or_(a != b, sa.and_(a.is_(None), b.is_not(None)), sa.and_(a.is_not(None), b.is_(None)))


def _value_text(value) -> str | None:
    """Denetim izindeki JSON değeri saklanan metne (as_text ile aynı biçim)."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, float):
        return format(Decimal(repr(value)), "f")
    return str(value)[:VALUE_LENGTH]


def _manual_audit(conn) -> list[dict]:
    """Denetim izindeki manuel değer kayıtları: tablo, kayıt (JSON'daki kimlik ya da nesnedeki koddan tek eşleşme), alan, eski ve yeni değer."""
    from app.api.lists.master_data import BY_NAME
    by_list = {name: d.table_name for name, d in BY_NAME.items()}
    by_title = {d.title: d.table_name for d in BY_NAME.values()}
    out = []
    rows = conn.execute(sa.select(AUDIT).where(AUDIT.c.ObjectType == MANUAL_OBJECT, AUDIT.c.Action.in_([SAVE_ACTION, REMOVE_ACTION])).order_by(AUDIT.c.Id)).mappings().all()
    for r in rows:
        try:
            new, old = json.loads(r["NewValue"] or "{}"), json.loads(r["OldValue"] or "{}")
        except ValueError:
            continue
        title, _, code = (r["ObjectKey"] or "").partition(" · ")
        table = by_list.get(new.get("list")) or by_title.get(title)
        field = new.get("field")
        if not table or not field:
            continue
        key = new.get("record")
        if key is None and code:
            t = core_table(table)
            if "Code" not in t.c:
                continue
            ids = conn.execute(sa.select((t.c.Id if "Id" in t.c else t.c.Code)).where(t.c.Code == code).distinct()).scalars().all()
            if len(ids) != 1:
                continue
            key = ids[0]
        if key is None:
            continue
        out.append({"TableName": table, "RecordKey": str(key), "FieldName": field, "OldValue": _value_text(old.get("Value")),
                    "NewValue": _value_text(new.get("Value")), "At": r["At"], "UserId": r["UserId"],
                    "Source": MANUAL_SOURCE if r["Action"] == SAVE_ACTION else MANUAL_REMOVE})
    return out


def backfill(conn) -> dict[str, int]:
    """Tek işlemde; geçmiş zaten varsa (tablo boş değilse) bir şey yapmaz."""
    if conn.execute(sa.select(sa.func.count()).select_from(FIELD_CHANGE)).scalar():
        return {}
    counts: dict[str, int] = {}
    manual = _manual_audit(conn)
    CELLS.create(bind=conn)
    try:
        cells = {(m["TableName"], m["RecordKey"], m["FieldName"]) for m in manual}
        cells |= {(r.TableName, r.RecordKey, r.FieldName) for r in conn.execute(sa.select(MANUAL.c.TableName, MANUAL.c.RecordKey, MANUAL.c.FieldName))}
        if cells:
            conn.execute(sa.insert(CELLS), [{"TableName": t, "RecordKey": k, "FieldName": f} for t, k, f in cells])
        first = conn.execute(sa.select(DATA_VERSION.c.Id, DATA_VERSION.c.CreatedAt).order_by(DATA_VERSION.c.Id).limit(1)).first()
        cols = ["TableName", "RecordKey", "ChangeType", "DataVersionId", "At", "Source", "UserId"]
        for table in sorted(SCREEN_TABLES):
            t = core_table(table)
            if table in UNVERSIONED:
                key = t.c.Id if "Id" in t.c else t.c.Code
                sel = sa.select(sa.literal(table), sa.cast(key, sa.Unicode(KEY_LENGTH)), sa.literal(CREATED), sa.literal(first.Id if first else None, sa.BigInteger),
                                sa.literal(first.CreatedAt, sa.DateTime) if first else sa.func.sysutcdatetime(), sa.literal(TRANSFER), sa.null())
                counts[table] = conn.execute(sa.insert(FIELD_CHANGE).from_select(cols, sel)).rowcount
                continue
            n = 0
            starts = sa.select(t.c.Id, sa.func.min(t.c.VersionFrom).label("V")).group_by(t.c.Id).subquery("fc_first")
            dv = DATA_VERSION.alias("fc_dv")
            sel = (sa.select(sa.literal(table), sa.cast(starts.c.Id, sa.Unicode(KEY_LENGTH)), sa.literal(CREATED), starts.c.V,
                             sa.func.coalesce(dv.c.CreatedAt, sa.func.sysutcdatetime()), sa.literal(TRANSFER), dv.c.CreatedBy)
                   .select_from(starts.outerjoin(dv, dv.c.Id == starts.c.V)))
            n += conn.execute(sa.insert(FIELD_CHANGE).from_select(cols, sel)).rowcount
            p, x = t.alias("fc_p"), t.alias("fc_n")
            pair = sa.and_(x.c.Id == p.c.Id, x.c.VersionFrom == p.c.VersionTo + 1)
            for f in tracked_columns(table):
                col = t.c[f]
                seen = sa.exists().where(CELLS.c.TableName == table, CELLS.c.RecordKey == sa.cast(p.c.Id, sa.Unicode(KEY_LENGTH)), CELLS.c.FieldName == f)
                sel = (sa.select(sa.literal(table), sa.cast(p.c.Id, sa.Unicode(KEY_LENGTH)), sa.literal(CHANGED), x.c.VersionFrom,
                                 sa.func.coalesce(dv.c.CreatedAt, sa.func.sysutcdatetime()), sa.literal(TRANSFER), dv.c.CreatedBy,
                                 sa.literal(f), as_text(p.c[f], col), as_text(x.c[f], col))
                       .select_from(p.join(x, pair).outerjoin(dv, dv.c.Id == x.c.VersionFrom))
                       .where(_differs(p.c[f], x.c[f]), ~seen))
                n += conn.execute(sa.insert(FIELD_CHANGE).from_select([*cols, "FieldName", "OldValue", "NewValue"], sel)).rowcount
            later = t.alias("fc_later")
            closed = (sa.select(sa.literal(table), sa.cast(p.c.Id, sa.Unicode(KEY_LENGTH)), sa.literal(CLOSED), p.c.VersionTo + 1,
                                sa.func.coalesce(dv.c.CreatedAt, sa.func.sysutcdatetime()), sa.literal(TRANSFER), dv.c.CreatedBy)
                      .select_from(p.outerjoin(dv, dv.c.Id == p.c.VersionTo + 1))
                      .where(p.c.VersionTo.is_not(None), ~sa.exists().where(later.c.Id == p.c.Id, later.c.VersionFrom > p.c.VersionFrom)))
            n += conn.execute(sa.insert(FIELD_CHANGE).from_select(cols, closed)).rowcount
            counts[table] = n
        if manual:
            for m in manual:  # o anki güncel veri versiyonu
                m["DataVersionId"] = conn.execute(sa.select(sa.func.max(DATA_VERSION.c.Id)).where(DATA_VERSION.c.CreatedAt <= m["At"])).scalar()
                m["ChangeType"] = CHANGED
            conn.execute(sa.insert(FIELD_CHANGE), manual)
            counts["manual"] = len(manual)
    finally:
        CELLS.drop(bind=conn)
    return counts
