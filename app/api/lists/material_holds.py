"""Malzeme blokajı listeleri (ekran 31 üçüncü sekme, fonksiyon 99; K-193): Kayıtlar (`material-holds`: senaryonun çözümlenmiş kayıtları) ve
Geçerlilik (`material-holds-validity`: malzeme × tedarik biçimi × plan dönemi; yalnız blokajlı günü olan dönemler, kapalı ya da açık). Yazma uçları
`/api/model-constraints/material-holds`. Lokasyon tablonun kendi alanıdır, kodun solunda (K-189); İlişkili alanlar: Malzeme, Lokasyon.
"""
import sqlalchemy as sa

from app import materialholds as rules
from app.params import resolve
from app.periods import cache

from . import relations
from .definition import ListDefinition, SourceContext
from .period_tables import PERIOD_FIELDS, PERIOD_LABELS, PERIOD_NOTES, PERIOD_ORDER, PERIOD_TYPES, skeleton

FUNCTION = 99
LINKS = (("MaterialId", "Malzeme"), ("LocationId", "Lokasyon"))
_ORIGINS = [resolve.BASE, resolve.DIFF, resolve.OWN]
# malzemenin kodu ve adı: güncel kayıt yoksa (aktarımla kapanmışsa) son versiyonunki
_CODE = "(SELECT TOP 1 x.{col} FROM core.Material x WHERE x.Id = z.MaterialId ORDER BY CASE WHEN x.VersionTo IS NULL THEN 0 ELSE 1 END, x.VersionFrom DESC)"
_OWNER = (f"(SELECT l.Code FROM core.Location l WHERE l.Id = z.LocationId) AS LocationCode, {_CODE.format(col='Code')} AS MaterialCode, {_CODE.format(col='Name')} AS MaterialName, "
          "N',m' + CAST(z.MaterialId AS nvarchar(20)) + N',' AS OwnerKeys")      # kartta ve zaman çubuğunda süzme: malzeme ",m12,"
_OWNER_TYPES = {"LocationCode": sa.Unicode(50), "MaterialCode": sa.Unicode(50), "MaterialName": sa.Unicode(200), "OwnerKeys": sa.Unicode(100), "LocationId": sa.Integer(),
                "MaterialId": sa.BigInteger()}
_LABELS = {"LocationCode": "Lokasyon", "MaterialCode": "Malzeme", "MaterialName": "Malzeme adı", "HoldType": "Tür", "StartDate": "Başlangıç", "EndDate": "Bitiş",
           "ClosePct": "Dönemi kapatma oranı (%)", "Reason": "Sebep", "Origin": "Kaynağı", "IsValid": "Geçerli", "StoredId": "Saklanan satır",
           "OverriddenFields": "Senaryoda değişen alanlar", "BaseValues": "Baz değerleri", "OwnerKeys": "Sahip anahtarları", "LocationId": "Lokasyon no", "MaterialId": "Malzeme no",
           "Supply": "Tedarik", "BlockedDays": "Blokajlı gün", "Ratio": "Oran (%)", "Threshold": "Eşik (%)", "Status": "Durum", "Records": "Kayıt sayısı", "SourceRowId": "İlk kayıt",
           **PERIOD_LABELS}
_NOTES = {"Origin": "Baz: Baz senaryodan okunur · Senaryo farkı: Baz satırı bu senaryoda değiştirildi · Senaryo: yalnız bu senaryoda",
          "ClosePct": "Blokaj plan döneminin takvim günlerinin en az bu oranını kapsıyorsa dönem kapalıdır", "EndDate": "Boşsa süresiz (ufkun sonuna kadar)",
          "Supply": "Tedarik biçimi: Üretim ve Satın alma ayrı hesaplanır", "BlockedDays": "Dönemde blokajlı takvim günü; üst üste binen kayıtlarda gün bir kez sayılır",
          "Ratio": "Blokajlı gün ÷ dönemin takvim günü", "Threshold": "Dönemi kapatma oranı; döneme dokunan kayıtların en düşüğü",
          "Status": "Oran eşiğe eşit ya da ondan büyükse Kapalı", "Records": "Döneme dokunan kayıt sayısı", **PERIOD_NOTES}


def _binds(ctx: SourceContext) -> list[sa.BindParameter]:
    scenario = cache.scenario_row(ctx.session, ctx.scenario_id)
    return [sa.bindparam("mh_sid", ctx.scenario_id, sa.Integer()), sa.bindparam("mh_base", cache.base_of(ctx.session, scenario), sa.Integer()),
            sa.bindparam("mh_is_base", 1 if scenario["IsBase"] else 0, sa.Integer())]


# --- Kayıtlar ----------------------------------------------------------------------------------------------------------------------------
_ENTRY_TYPES = {"Id": sa.BigInteger(), "StoredId": sa.BigInteger(), "Origin": sa.Unicode(20), "IsValid": sa.Boolean(), "OverriddenFields": sa.Unicode(400),
                "BaseValues": sa.UnicodeText(), **_OWNER_TYPES, "HoldType": sa.Unicode(25), "StartDate": sa.Date(), "EndDate": sa.Date(), "ClosePct": sa.Numeric(5, 2),
                "Reason": sa.Unicode(255)}
_ENTRY_SQL = (f"SELECT z.RowId AS Id, z.StoredId, CASE WHEN :mh_is_base = 1 THEN N'{resolve.BASE}' ELSE z.Origin END AS Origin, z.IsValid, z.OverriddenFields, z.BaseValues, "
              f"{_OWNER}, z.LocationId, z.MaterialId, z.HoldType, z.StartDate, z.EndDate, z.ClosePct, z.Reason "
              f"FROM ({resolve.sql(rules.TABLE, valid_only=False, sid=':mh_sid', base=':mh_base', detail=True)}) z")
_ENTRY_SHOWN = ("LocationCode", "MaterialCode", "HoldType", "StartDate", "EndDate", "ClosePct", "Reason", "Origin", "IsValid")


def _entry_source(ctx: SourceContext) -> sa.FromClause:
    return sa.text(_ENTRY_SQL).bindparams(*_binds(ctx)).columns(*[sa.column(n, t) for n, t in _ENTRY_TYPES.items()]).subquery("mh")


MATERIAL_HOLDS = ListDefinition(
    name="material-holds", table=f"param.{rules.TABLE}", function=FUNCTION, versioned=False, title="Malzeme blokajı", file_slug="malzeme-blokaji",
    source=skeleton(_ENTRY_TYPES, "mh"), source_factory=_entry_source,
    fields=(*_ENTRY_SHOWN[:2], "MaterialName", *_ENTRY_SHOWN[2:]), default_visible=_ENTRY_SHOWN,
    default_sort=(("MaterialCode", "asc"), ("StartDate", "asc")),
    server_values=frozenset({"LocationCode", "MaterialCode"}), decimals={"ClosePct": 2},
    values={"Origin": _ORIGINS, "HoldType": list(rules.TYPES)},
    labels=_LABELS, notes=_NOTES,
    key_fields=("StoredId", "Origin", "IsValid", "OverriddenFields", "BaseValues", "LocationId", "MaterialId", "LocationCode"), filter_only=("OwnerKeys",),
    related_table=relations.register_links("material-holds", LINKS),
)

# --- Geçerlilik (dönem bazında) ------------------------------------------------------------------------------------------------------------
_VALIDITY_TYPES = {"Id": sa.BigInteger(), **_OWNER_TYPES, "Supply": sa.Unicode(15), **PERIOD_TYPES, "BlockedDays": sa.Integer(), "Ratio": sa.Numeric(6, 2),
                   "Threshold": sa.Numeric(5, 2), "Status": sa.Unicode(10), "Records": sa.Integer(), "SourceRowId": sa.BigInteger()}
_VALIDITY_SQL = ("SELECT CAST(z.MaterialId AS bigint) * 10000 + z.PeriodNo * 2 + CASE WHEN z.Supply = N'{production}' THEN 0 ELSE 1 END AS Id, "
                 "{owner}, z.LocationId, z.MaterialId, z.Supply, {period}, z.BlockedDays, z.Ratio, z.ClosePct AS Threshold, "
                 "CASE WHEN z.Closed = 1 THEN N'{closed}' ELSE N'{open}' END AS Status, z.Records, z.SourceRowId FROM ({rows}) z").format(
    production=rules.PRODUCTION, owner=_OWNER, period=", ".join(f"z.{f}" for f in PERIOD_FIELDS), closed=rules.CLOSED, open=rules.OPEN,
    rows=rules.periods_sql(":mh_sid", ":mh_base", ":mh_periods", ":mh_days"))
_VALIDITY_SHOWN = ("LocationCode", "MaterialCode", "Supply", "Period", "PeriodStart", "PeriodEnd", "BlockedDays", "Ratio", "Threshold", "Status")


def _validity_source(ctx: SourceContext) -> sa.FromClause:
    found = rules.period_binds(ctx.session, ctx.scenario_id, ctx.today, prefix="mh_")
    binds = [b for b in _binds(ctx) if b.key != "mh_is_base"]
    binds += [sa.bindparam("mh_periods", found["mh_periods"], sa.UnicodeText()), sa.bindparam("mh_days", found["mh_days"], sa.UnicodeText())]
    return sa.text(_VALIDITY_SQL).bindparams(*binds).columns(*[sa.column(n, t) for n, t in _VALIDITY_TYPES.items()]).subquery("mhv")


MATERIAL_HOLDS_VALIDITY = ListDefinition(
    name="material-holds-validity", table=f"param.{rules.TABLE}", function=FUNCTION, versioned=False, title="Malzeme blokajı · Geçerlilik",
    file_slug="malzeme-blokaji-gecerlilik",
    source=skeleton(_VALIDITY_TYPES, "mhv"), source_factory=_validity_source,
    fields=(*_VALIDITY_SHOWN[:2], "MaterialName", "Supply", *PERIOD_FIELDS, "BlockedDays", "Ratio", "Threshold", "Status", "Records"), default_visible=_VALIDITY_SHOWN,
    default_sort=(("MaterialCode", "asc"), ("PeriodStart", "asc"), ("Supply", "asc")),
    server_values=frozenset({"LocationCode", "MaterialCode", "PeriodType", "Period", "Week", "Month", "Quarter", "Year"}),
    decimals={"Ratio": 1, "Threshold": 2},
    values={"Supply": list(rules.SUPPLIES), "Status": [rules.OPEN, rules.CLOSED]},
    labels=_LABELS, notes=_NOTES,
    # zaman çubuğu satırları çizer: gereken alanlar kolon kapatılsa da döner
    key_fields=("SourceRowId", "LocationId", "MaterialId", "LocationCode", "MaterialCode", "Supply", "Period", "PeriodStart", "PeriodEnd", "PeriodDays", "BlockedDays", "Ratio", "Threshold",
                "Status"),
    filter_only=("OwnerKeys",),
    related_table=relations.register_links("material-holds-validity", LINKS),
    order_by=PERIOD_ORDER,
)

MATERIAL_HOLD_LISTS = (MATERIAL_HOLDS, MATERIAL_HOLDS_VALIDITY)
