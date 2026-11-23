"""Tedarikçi limiti listeleri (ekran 31 ikinci sekme, fonksiyon 103; K-191): Kayıtlar (`supplier-limits`: senaryonun çözümlenmiş kayıtları, iki tür
birlikte) ve Geçerlilik (`supplier-limits-validity`: tedarikçi ve malzeme başına uygulanan aralıklar; kapanışlar birleşmiş). Yazma uçları
`/api/model-constraints/supplier-limits`. Lokasyon tablonun kendi alanıdır, kodun solunda (K-189); İlişkili alanlar: Tedarikçi, Malzeme, Lokasyon.
"""
import sqlalchemy as sa

from app import supplierlimits as rules
from app.params import resolve
from app.periods import cache

from . import relations
from .definition import ListDefinition, SourceContext
from .period_tables import skeleton

FUNCTION = 103
LINKS = (("SupplierId", "Tedarikçi"), ("MaterialId", "Malzeme"), ("LocationId", "Lokasyon"))
_ORIGINS = [resolve.BASE, resolve.DIFF, resolve.OWN]
# sahibin kodları: güncel kayıt yoksa (aktarımla kapanmışsa) son versiyonun kodu
_CODE = "(SELECT TOP 1 x.{col} FROM core.[{table}] x WHERE x.Id = {id} ORDER BY CASE WHEN x.VersionTo IS NULL THEN 0 ELSE 1 END, x.VersionFrom DESC)"
_OWNER = (f"(SELECT l.Code FROM core.Location l WHERE l.Id = z.LocationId) AS LocationCode, "
          f"{_CODE.format(col='Code', table='Supplier', id='z.SupplierId')} AS SupplierCode, {_CODE.format(col='Name', table='Supplier', id='z.SupplierId')} AS SupplierName, "
          f"COALESCE({_CODE.format(col='Code', table='Material', id='z.MaterialId')}, N'{rules.ALL_MATERIALS}') AS MaterialCode, "
          f"{_CODE.format(col='Name', table='Material', id='z.MaterialId')} AS MaterialName, "
          f"CASE WHEN {{kind}} = N'{rules.UPPER}' THEN {_CODE.format(col='BaseUom', table='Material', id='z.MaterialId')} END AS Uom, "   # birim yalnız üst limitte
          # kartta ve zaman çubuğunda süzme: tedarikçi ",s5,", tedarikçi + malzeme ",s5m12,"
          "N',s' + CAST(z.SupplierId AS nvarchar(20)) + N',' + COALESCE(N's' + CAST(z.SupplierId AS nvarchar(20)) + N'm' + CAST(z.MaterialId AS nvarchar(20)) + N',', N'') AS OwnerKeys")
_OWNER_TYPES = {"LocationCode": sa.Unicode(50), "SupplierCode": sa.Unicode(50), "SupplierName": sa.Unicode(200), "MaterialCode": sa.Unicode(50),
                "MaterialName": sa.Unicode(200), "Uom": sa.Unicode(10), "OwnerKeys": sa.Unicode(100), "LocationId": sa.Integer(), "SupplierId": sa.BigInteger(),
                "MaterialId": sa.BigInteger()}
_LABELS = {"LimitType": "Tür", "LocationCode": "Lokasyon", "SupplierCode": "Tedarikçi", "SupplierName": "Tedarikçi adı", "MaterialCode": "Malzeme", "MaterialName": "Malzeme adı",
           "ValidFrom": "Başlangıç", "ValidTo": "Bitiş", "UpperLimit": "Limit", "LimitPeriod": "Limitin dönemi", "Uom": "Birim", "Reason": "Sebep", "Origin": "Kaynağı",
           "IsValid": "Geçerli", "StoredId": "Saklanan satır", "OverriddenFields": "Senaryoda değişen alanlar", "BaseValues": "Baz değerleri", "OwnerKeys": "Sahip anahtarları",
           "LocationId": "Lokasyon no", "SupplierId": "Tedarikçi no", "MaterialId": "Malzeme no", "Status": "Durum", "DailyAverage": "Günlük ortalama",
           "SourceRowId": "Geçerli kayıt", "SourceOrigin": "Geçerli kaydın kaynağı"}
_NOTES = {"Origin": "Baz: Baz senaryodan okunur · Senaryo farkı: Baz satırı bu senaryoda değiştirildi · Senaryo: yalnız bu senaryoda",
          "UpperLimit": "Malzemenin temel biriminde; limitin dönemi başına", "MaterialCode": "Kapanışta boşsa tedarikçinin bütün malzemeleri (Tümü)",
          "DailyAverage": "Limit ÷ limitin döneminin gün sayısı; aralığın ilk gününün değeri (ay, çeyrek ve yılda takvim günü)"}


def _source(select: str, types: dict, name: str):
    def factory(ctx: SourceContext) -> sa.FromClause:
        scenario = cache.scenario_row(ctx.session, ctx.scenario_id)
        binds = [sa.bindparam("sl_sid", ctx.scenario_id, sa.Integer()), sa.bindparam("sl_base", cache.base_of(ctx.session, scenario), sa.Integer()),
                 sa.bindparam("sl_is_base", 1 if scenario["IsBase"] else 0, sa.Integer())]
        return sa.text(select).bindparams(*binds).columns(*[sa.column(n, t) for n, t in types.items()]).subquery(name)
    return factory


# --- Kayıtlar ----------------------------------------------------------------------------------------------------------------------------
_ENTRY_TYPES = {"Id": sa.BigInteger(), "StoredId": sa.BigInteger(), "Origin": sa.Unicode(20), "IsValid": sa.Boolean(), "OverriddenFields": sa.Unicode(400),
                "BaseValues": sa.UnicodeText(), "LimitType": sa.Unicode(15), **_OWNER_TYPES, "ValidFrom": sa.Date(), "ValidTo": sa.Date(),
                "UpperLimit": sa.Numeric(18, 4), "LimitPeriod": sa.Unicode(10), "Reason": sa.Unicode(255)}
_ENTRY_SQL = (f"SELECT z.RowId AS Id, z.StoredId, CASE WHEN :sl_is_base = 1 THEN N'{resolve.BASE}' ELSE z.Origin END AS Origin, z.IsValid, z.OverriddenFields, z.BaseValues, "
              f"z.LimitType, {_OWNER.format(kind='z.LimitType')}, z.LocationId, z.SupplierId, z.MaterialId, z.ValidFrom, z.ValidTo, z.UpperLimit, z.LimitPeriod, z.Reason "
              f"FROM ({resolve.sql(rules.TABLE, valid_only=False, sid=':sl_sid', base=':sl_base', detail=True)}) z")
_ENTRY_SHOWN = ("LimitType", "LocationCode", "SupplierCode", "MaterialCode", "ValidFrom", "ValidTo", "UpperLimit", "LimitPeriod", "Uom", "Reason", "Origin", "IsValid")

SUPPLIER_LIMITS = ListDefinition(
    name="supplier-limits", table=f"param.{rules.TABLE}", function=FUNCTION, versioned=False, title="Tedarikçi limiti", file_slug="tedarikci-limiti",
    source=skeleton(_ENTRY_TYPES, "sl"), source_factory=_source(_ENTRY_SQL, _ENTRY_TYPES, "sl"),
    fields=(*_ENTRY_SHOWN[:3], "SupplierName", "MaterialCode", "MaterialName", *_ENTRY_SHOWN[4:]), default_visible=_ENTRY_SHOWN,
    default_sort=(("SupplierCode", "asc"), ("MaterialCode", "asc"), ("ValidFrom", "asc")),
    server_values=frozenset({"LocationCode", "SupplierCode", "MaterialCode", "Uom"}), unit_field="Uom", unit_decimals=frozenset({"UpperLimit"}),
    values={"Origin": _ORIGINS, "LimitType": [rules.UPPER, rules.CLOSURE], "LimitPeriod": list(rules.PERIODS)},
    labels=_LABELS, notes=_NOTES,
    key_fields=("StoredId", "Origin", "IsValid", "OverriddenFields", "BaseValues", "LocationId", "SupplierId", "MaterialId", "LocationCode"), filter_only=("OwnerKeys",),
    related_table=relations.register_links("supplier-limits", LINKS),
)

# --- Geçerlilik --------------------------------------------------------------------------------------------------------------------------
_VALIDITY_TYPES = {"Id": sa.BigInteger(), **_OWNER_TYPES, "Status": sa.Unicode(15), "ValidFrom": sa.Date(), "ValidTo": sa.Date(), "UpperLimit": sa.Numeric(18, 4),
                   "LimitPeriod": sa.Unicode(10), "DailyAverage": sa.Numeric(18, 4), "Reason": sa.Unicode(255), "SourceRowId": sa.BigInteger(),
                   "SourceOrigin": sa.Unicode(20)}
_VALIDITY_SQL = ("SELECT ROW_NUMBER() OVER (ORDER BY z.LocationId, z.SupplierId, COALESCE(z.MaterialId, 0), z.ValidFrom, z.Status) AS Id, "
                 f"{_OWNER.format(kind='z.Status')}, z.LocationId, z.SupplierId, z.MaterialId, z.Status, z.ValidFrom, z.ValidTo, z.UpperLimit, z.LimitPeriod, z.DailyAverage, z.Reason, z.SourceRowId, "
                 f"CASE WHEN :sl_is_base = 1 THEN N'{resolve.BASE}' ELSE z.SourceOrigin END AS SourceOrigin FROM ({rules.validity_sql(':sl_sid', ':sl_base')}) z")
_VALIDITY_SHOWN = ("LocationCode", "SupplierCode", "MaterialCode", "Status", "ValidFrom", "ValidTo", "UpperLimit", "LimitPeriod", "DailyAverage", "Uom")

SUPPLIER_LIMITS_VALIDITY = ListDefinition(
    name="supplier-limits-validity", table=f"param.{rules.TABLE}", function=FUNCTION, versioned=False, title="Tedarikçi limiti · Geçerlilik",
    file_slug="tedarikci-limiti-gecerlilik",
    source=skeleton(_VALIDITY_TYPES, "slv"), source_factory=_source(_VALIDITY_SQL, _VALIDITY_TYPES, "slv"),
    fields=(*_VALIDITY_SHOWN[:2], "SupplierName", "MaterialCode", "MaterialName", *_VALIDITY_SHOWN[3:], "Reason"), default_visible=_VALIDITY_SHOWN,
    default_sort=(("SupplierCode", "asc"), ("MaterialCode", "asc"), ("ValidFrom", "asc")),
    server_values=frozenset({"LocationCode", "SupplierCode", "MaterialCode", "Uom"}), unit_field="Uom", unit_decimals=frozenset({"UpperLimit", "DailyAverage"}),
    values={"Status": [rules.UPPER, "Kapalı"], "LimitPeriod": list(rules.PERIODS)},
    labels=_LABELS, notes=_NOTES,
    key_fields=("SourceRowId", "SourceOrigin", "LocationId", "SupplierId", "MaterialId", "LocationCode"), filter_only=("OwnerKeys",),
    related_table=relations.register_links("supplier-limits-validity", LINKS),
)

SUPPLIER_LIMIT_LISTS = (SUPPLIER_LIMITS, SUPPLIER_LIMITS_VALIDITY)
