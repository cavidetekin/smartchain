"""Manuel değer çekirdeği (K-170): hangi alan "Manuel" olabilir, değerin metin biçimi ve SQL ifadeleri. API ve aktarım birlikte kullanır.

Manuel değer `adm.ManualValue`'da metin olarak saklanır; metin, alanın SQL tipinden SQL'de üretilir (`as_text`) ve SQL'de tipine döner
(`from_text`). Böylece kaydetme, aktarım ve kaldırma aynı biçimi kullanır; "alttaki değer değişti" karşılaştırması tipli yapılır.
"""
from datetime import date, datetime
from decimal import Decimal

import sqlalchemy as sa

from db.models import metadata

MANUAL = metadata.tables["adm.ManualValue"]
SOURCE = metadata.tables["adm.FieldValueSource"]
EFFECT = metadata.tables["adm.DataRuleEffect"]
FIELDS = metadata.tables["adm.FieldDefinition"]
RULE = metadata.tables["adm.DataRule"]

ERP, RULE_SOURCE = "ERP", "Kural"
KEY_LENGTH = 60

# Ana veri ve işlem verisi ekranlarının tabloları (K-168, K-169); manuel değer yalnız bunlarda
SCREEN_TABLES = frozenset({
    "Material", "MaterialReference", "ProductionVersion", "BOM", "Routing", "Resource", "ResourceGroup", "ResourceGroupAssignment", "Supplier",
    "MaterialSupplier", "Customer", "Location", "UnitOfMeasure", "UomConversion", "SalesOrderLine", "Forecast", "Project", "ProjectGroup", "Stock",
    "BorrowPayback", "WorkOrder", "WorkOrderComponent", "WorkOrderOperation", "ProductionConfirmation", "PurchaseOrderLine", "EmployeeAbsence",
})
UNVERSIONED = frozenset({"Location", "UnitOfMeasure"})
NOT_MANUAL_SOURCES = frozenset({"Sistem", "Ön hesap", "Yüklemede diğer tablolardan"})
# Kaynağın Kapasite yönetimi'nde girilen alanları (7.3, K-167): ana veride salt okunur, manuel değer değil
RESOURCE_CAPACITY = frozenset({"DailyCapacity", "Quantity", "CapacitySource", "CalendarId", "SubconPlanningType", "SubcontractorId",
                               "SubconFixedLeadTimeDays", "SubconVariableDaysPerUnit"})

KEY_REASON = "Anahtar alana manuel değer girilemez."
RELATION_REASON = "İlişki alanına manuel değer girilemez."
SYSTEM_REASON = "Sistem alanına manuel değer girilemez."
CAPACITY_REASON = "Kapasite yönetimi'nde girilir."
TABLE_REASON = "Manuel değer yalnız ana veri ve işlem verisinde girilir."
ACTIVE_REASON = "Aktif, kaydın aktarımda açık kalıp kalmayacağını belirler; manuel değer girilemez."
# Kod üzerinden ilişki kuran metin alanları (üretim versiyonunun ağacı ve rotası): ilişki alanı sayılır
CODE_RELATIONS = frozenset({("ProductionVersion", "BOMCode"), ("ProductionVersion", "RouteCode")})


def core_table(table: str) -> sa.Table:
    return metadata.tables[f"core.{table}"]


def core_key(table: str) -> tuple[str, ...]:
    """Kaydın tekil anahtarı (kod ve iş anahtarı kolonları); Manuel olamaz."""
    if table == "UnitOfMeasure":
        return ("Code",)
    from app.transfer.mapping import table_map
    return table_map(table).key


def not_manual_reason(table: str, field: str) -> str | None:
    """Alan "Manuel" olamıyorsa nedeni; olabiliyorsa None (K-170)."""
    if table not in SCREEN_TABLES:
        return TABLE_REASON
    col = core_table(table).c.get(field)
    if col is None or (col.info or {}).get("source") in NOT_MANUAL_SOURCES or field in ("Id", "VersionFrom", "VersionTo", "ImportBatchId", "BusinessKey"):
        return SYSTEM_REASON
    if field == "Code" or field in core_key(table):
        return KEY_REASON
    if field.endswith("Id") or (table, field) in CODE_RELATIONS:
        return RELATION_REASON
    if field == "IsActive":  # aktarım pasif kaydı kapatır (K-149)
        return ACTIVE_REASON
    if table == "Resource" and field in RESOURCE_CAPACITY:
        return CAPACITY_REASON
    return None


def kind(col: sa.Column) -> str:
    t = col.type
    if isinstance(t, sa.Boolean):
        return "bool"
    if isinstance(t, sa.DateTime):
        return "datetime"
    if isinstance(t, sa.Date):
        return "date"
    if isinstance(t, sa.Integer):
        return "integer"
    if isinstance(t, sa.Numeric):
        return "number"
    return "text"


def record_key(table: str, t) -> sa.ColumnElement:
    """`ManualValue.RecordKey` ile eşleşen ifade: Id metin olarak (birimde kod)."""
    return t.c.Code if table == "UnitOfMeasure" else sa.cast(t.c.Id, sa.Unicode(KEY_LENGTH))


def as_text(expr, col: sa.Column) -> sa.ColumnElement:
    """Alanın değeri saklanacak metne (SQL'de): bayrak 1/0, tarih yyyy-aa-gg, zaman ISO, sayı veritabanı biçiminde."""
    k = kind(col)
    if k == "bool":
        return sa.cast(sa.cast(expr, sa.Integer), sa.Unicode(1))
    if k == "date":
        return sa.func.convert(sa.literal_column("NVARCHAR(10)"), expr, 23)
    if k == "datetime":
        return sa.func.convert(sa.literal_column("NVARCHAR(30)"), expr, 126)
    if k in ("integer", "number"):
        return sa.cast(expr, sa.Unicode(60))
    return sa.cast(expr, sa.Unicode(200))


def from_text(expr, col: sa.Column) -> sa.ColumnElement:
    """Saklanan metin alanın tipine (SQL'de)."""
    return expr if kind(col) == "text" else sa.cast(expr, col.type)


def differs(a, b, col: sa.Column) -> sa.ColumnElement:
    """Değer farklı mı: boşlar eşit, boşla dolu farklı."""
    return sa.or_(sa.and_(a.is_(None), b.is_not(None)), sa.and_(a.is_not(None), b.is_(None)), sa.and_(a.is_not(None), b.is_not(None), a != b))


def typed(text: str | None, col: sa.Column):
    """Saklanan metin Python değerine (cevapta ipucu için)."""
    if text is None:
        return None
    k = kind(col)
    if k == "bool":
        return text == "1"
    if k == "date":
        return date.fromisoformat(text[:10]).isoformat()
    if k == "datetime":
        return datetime.fromisoformat(text).isoformat(timespec="seconds")
    if k == "integer":
        return int(Decimal(text))
    if k == "number":
        return float(Decimal(text))
    return text


def manual_fields(session, table: str) -> set[str]:
    """Veri sözlüğünde "Manuel: Evet" olan ve Manuel olabilen alanlar."""
    names = session.execute(sa.select(FIELDS.c.FieldName).where(FIELDS.c.TableName == table, FIELDS.c.ManualOverrides == sa.true())).scalars()
    return {n for n in names if not_manual_reason(table, n) is None}


MANUAL_COLUMN = "ManualState"  # listelerdeki "Manuel değer" kolonu (K-170)
MANUAL_LABEL = "Manuel değer"
STATE_SET, STATE_ERP_CHANGED, STATE_RULE_CHANGED = "Var", "Var / ERP Güncellendi", "Var / Kural Güncellendi"
STATES = [STATE_SET, STATE_ERP_CHANGED, STATE_RULE_CHANGED]


def state_column(table: str, t) -> sa.ColumnElement:
    """Kaydın manuel değer durumu (K-172): boş, Var, Var / ERP Güncellendi, Var / Kural Güncellendi (alttaki değer girildiğinden beri
    güncellendiyse; kayıtta ikisi birden varsa ERP)."""
    base = [MANUAL.c.TableName == table, MANUAL.c.RecordKey == record_key(table, t)]
    changed = [*base, MANUAL.c.IsBaseChanged == sa.true()]
    return sa.case((sa.exists().where(*changed, sa.func.coalesce(MANUAL.c.UnderlyingSource, "ERP") != "Kural"), STATE_ERP_CHANGED),
                   (sa.exists().where(*changed), STATE_RULE_CHANGED),
                   (sa.exists().where(*base), STATE_SET), else_=sa.null()).label(MANUAL_COLUMN)
