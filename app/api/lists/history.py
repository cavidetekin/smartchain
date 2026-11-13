"""Kaydın geçmişi (`adm.FieldChange`; fonksiyon 14, K-171, K-173): detay kartının Geçmiş sekmesi, liste sözleşmesiyle. Sürümsüzdür.

Kayıt `TableName` ve `RecordKey` ile süzülür (yalnız süzmede). Kolonlar: Tarih, Veri (v64), Alan (veri sözlüğündeki etiket), Eski değer, Yeni
değer, Kaynak ("Aktarım · Tam · Kural: <ad>", "Manuel değer · <kişi>" …). Değerler okurken alanın tipine ve ondalığına göre biçimlenir
(`row_format`); süzme ve sıralama saklanan metinde. System owner'ın adı "Smartchain" (K-108).
Çoklu seçimde (K-171) `record-history-many`: aynı kaynak, başta "Kayıt" kolonu (kaydın kodu; sipariş satırında "SO-1 / 2").
"""
from functools import cache

import sqlalchemy as sa

from app.manual import core_table
from app.history import CLOSED, CREATED, DATA_VERSION, FIELD_CHANGE, MANUAL_REMOVE, MANUAL_SOURCE, TRANSFER, format_value
from db.models import metadata

from ..permissions import SYSTEM_OWNER
from .audit_log import SUPPORT_NAME
from .definition import ListDefinition
from .master_data import BY_NAME

USER = metadata.tables["adm.AppUser"]
RULE = metadata.tables["adm.DataRule"]
FIELDS_DEF = metadata.tables["adm.FieldDefinition"]

RECORD_CREATED, RECORD_CLOSED = "Kayıt oluştu", "Kayıt kapandı"
NO_FIELD = "—"


def _lit(text: str) -> sa.ColumnElement:
    return sa.literal_column("N'" + text.replace("'", "''") + "'", sa.Unicode)


fc, dv, u, r, fd = FIELD_CHANGE, DATA_VERSION, USER, RULE, FIELDS_DEF
LABEL_KEYS = ("Code", "OrderNo", "PurchaseOrderNo", "WorkOrderNo", "ConfirmationNo", "RouteCode")  # kartın label_of'uyla aynı sıra


def _record_label() -> sa.ColumnElement:
    """Kaydın kodu (K-171): tablo başına son versiyonun kodu; sipariş satırında "kod / satır", kodu olmayan tabloda iş anahtarı."""
    whens = []
    for table in sorted({d.table_name for d in BY_NAME.values()}):
        t = core_table(table)
        key = next((k for k in LABEL_KEYS if k in t.c), None)
        if key:
            label = sa.cast(t.c[key], sa.Unicode(200))
            if key.endswith("OrderNo") and "LineNo" in t.c:
                label = label + _lit(" / ") + sa.cast(t.c.LineNo, sa.Unicode(20))
        elif "BusinessKey" in t.c:
            label = sa.func.replace(t.c.BusinessKey, "|", " · ")
        else:
            continue
        match = t.c.Id == sa.try_cast(fc.c.RecordKey, sa.Integer) if "Id" in t.c else t.c.Code == fc.c.RecordKey
        order = [t.c.VersionFrom.desc()] if "VersionFrom" in t.c else []
        whens.append((fc.c.TableName == table, sa.select(label).where(match).order_by(*order).limit(1).scalar_subquery()))
    return sa.func.coalesce(sa.case(*whens, else_=None), fc.c.RecordKey)
_person = sa.case((u.c.Id.is_(None), _lit("")), (u.c.Role == SYSTEM_OWNER, _lit(SUPPORT_NAME)), else_=sa.func.coalesce(u.c.FullName, u.c.UserName))
_by = sa.case((u.c.Id.is_(None), _lit("")), else_=_lit(" · ") + _person)  # kişi yoksa ayraç da yok
_note = sa.case((fc.c.Note.is_(None), _lit("")), else_=_lit(" · ") + sa.func.lower(sa.func.left(fc.c.Note, 1)) + sa.func.substring(fc.c.Note, 2, 100))
_transfer = (_lit(TRANSFER + " · ") + sa.func.coalesce(dv.c.LoadType, _lit("Tam"))
             + sa.case((r.c.Name.is_(None), _lit("")), else_=_lit(" · Kural: ") + r.c.Name) + _note)
SOURCE = sa.select(
    fc.c.Id, fc.c.TableName, fc.c.RecordKey, fc.c.FieldName, fc.c.At, _record_label().label("RecordLabel"),
    sa.case((fc.c.DataVersionId.is_(None), _lit("")), else_=_lit("v") + sa.cast(fc.c.DataVersionId, sa.Unicode(20))).label("DataVersion"),
    sa.case((fc.c.FieldName.is_(None), _lit(NO_FIELD)), else_=sa.func.coalesce(fd.c.Label, fd.c.StandardLabel, fc.c.FieldName)).label("FieldLabel"),
    fc.c.OldValue,
    sa.case((fc.c.ChangeType == CREATED, _lit(RECORD_CREATED)), (fc.c.ChangeType == CLOSED, _lit(RECORD_CLOSED)), else_=fc.c.NewValue).label("NewValue"),
    sa.case((fc.c.Source == TRANSFER, _transfer),
            (fc.c.Source == MANUAL_SOURCE, _lit(MANUAL_SOURCE) + _by),
            (fc.c.Source == MANUAL_REMOVE, _lit("Manuel değer kaldırıldı") + _by),
            else_=fc.c.Source + _by).label("SourceText"),
).select_from(
    fc.outerjoin(dv, dv.c.Id == fc.c.DataVersionId).outerjoin(u, u.c.Id == fc.c.UserId).outerjoin(r, r.c.Id == fc.c.DataRuleId)
      .outerjoin(fd, sa.and_(fd.c.TableName == fc.c.TableName, fd.c.FieldName == fc.c.FieldName))
).subquery("fc_history")

FIELDS = ("At", "DataVersion", "FieldLabel", "OldValue", "NewValue", "SourceText")


@cache
def _formats() -> dict[str, tuple[dict[str, int], frozenset[str]]]:
    """Tablo → (alanın ondalığı, yüzde alanlar): ana veri ve işlem verisi listelerinden (K-88)."""
    from .master_data import BY_NAME
    return {d.table_name: (dict(d.decimals), d.percent) for d in BY_NAME.values()}


def format_rows(rows: list[dict]) -> None:
    """Eski ve yeni değer alanın biçimiyle (kayıt olayı satırında değer yok)."""
    formats = _formats()
    for row in rows:
        table, field = row.get("TableName"), row.get("FieldName")
        if not table or not field:
            continue
        decimals, percent = formats.get(table, ({}, frozenset()))
        for name in ("OldValue", "NewValue"):
            if name in row:
                row[name] = format_value(table, field, row[name], decimals, percent)


RECORD_HISTORY = ListDefinition(
    name="record-history",
    table="adm.FieldChange",
    title="Değişiklik geçmişi",
    file_slug="degisiklik-gecmisi",
    function=14,
    versioned=False,
    source=SOURCE,
    fields=FIELDS,
    default_visible=FIELDS,
    default_sort=(("At", "desc"),),
    labels={"At": "Tarih", "DataVersion": "Veri", "FieldLabel": "Alan", "OldValue": "Eski değer", "NewValue": "Yeni değer", "SourceText": "Kaynak",
            "TableName": "Tablo", "RecordKey": "Kayıt", "FieldName": "Alan adı"},
    server_values=frozenset({"FieldLabel", "SourceText", "TableName", "RecordKey"}),
    filter_only=("TableName", "RecordKey"),
    key_fields=("TableName", "FieldName"),
    row_format=format_rows,
)

# Çoklu seçimde Geçmiş (K-171): başta Kayıt kolonu; görünümleri ayrı.
RECORD_HISTORY_MANY = ListDefinition(
    name="record-history-many",
    table="adm.FieldChange",
    title="Değişiklik geçmişi",
    file_slug="degisiklik-gecmisi",
    function=14,
    versioned=False,
    source=SOURCE,
    fields=("RecordLabel", *FIELDS),
    default_visible=("RecordLabel", *FIELDS),
    default_sort=(("At", "desc"),),
    labels={**RECORD_HISTORY.labels, "RecordLabel": "Kayıt"},
    server_values=RECORD_HISTORY.server_values | {"RecordLabel"},
    filter_only=("TableName", "RecordKey"),
    key_fields=("TableName", "FieldName"),
    row_format=format_rows,
)
