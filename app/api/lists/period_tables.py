"""Dönem tabloları (K-184, docs/12 "Dönem tablosu standardı"): bir ana kaydın dönem bazındaki özeti. Satırlar veritabanında durmaz; kaynak
her istekte senaryonun dönemleriyle kurulur, değerler önbellekteki günlük ara sonuçtan toplanır (`app/periods`).

7.8'de tek tablo: "Kaynak grubu × dönem (deneme)" (deneme sayfası `/donem-tablosu`; 7.9'da Kapasite yönetimi'nin gerçek tablosuyla değişir).
"""
import sqlalchemy as sa

from app.periods import cache, capacity_demo, periods as period_list

from . import relations
from .definition import ListDefinition, SourceContext

# Her dönem tablosunda aynı ad ve sırayla (K-184)
PERIOD_FIELDS = ("PeriodType", "Period", "PeriodStart", "PeriodEnd", "Week", "Month", "Quarter", "Year", "PeriodDays")
PERIOD_LABELS = {"PeriodType": "Dönem tipi", "Period": "Dönem", "PeriodStart": "Dönem başı", "PeriodEnd": "Dönem sonu", "Week": "Hafta", "Month": "Ay",
                 "Quarter": "Çeyrek", "Year": "Yıl", "PeriodDays": "Dönem takvim günü"}
PERIOD_NOTES = {"PeriodDays": "Dönemin takvim günü sayısı (çalışma günü değil)", "Week": "Dönem başının haftası", "Month": "Dönem başının ayı",
                "Quarter": "Dönem başının çeyreği", "Year": "Dönem başının takvim yılı"}
PERIOD_TYPES = {"PeriodType": sa.Unicode(10), "Period": sa.Unicode(20), "PeriodStart": sa.Date(), "PeriodEnd": sa.Date(), "Week": sa.Unicode(12),
                "Month": sa.Unicode(12), "Quarter": sa.Unicode(12), "Year": sa.Unicode(4), "PeriodDays": sa.Integer()}
# Dönem alanları her yerde Dönem başı'na göre sıralanır (alfabetik değil)
PERIOD_ORDER = {f: "PeriodStart" for f in ("PeriodType", "Period", "Week", "Month", "Quarter", "Year")}
PERIOD_SELECT = ("p.[type] AS PeriodType, p.[label] AS Period, p.[start] AS PeriodStart, p.[end] AS PeriodEnd, p.[week] AS Week, p.[month] AS Month, "
                 "p.[quarter] AS Quarter, p.[year] AS Year, p.[days] AS PeriodDays")


def skeleton(types: dict[str, sa.types.TypeEngine], name: str) -> sa.FromClause:
    """Kolon bilgisi için durağan iskelet: aynı kolonlar, satırsız (gerçek kaynak istekte kurulur)."""
    return sa.select(*[sa.cast(sa.null(), t).label(n) for n, t in types.items()]).where(sa.false()).subquery(name)


# --- Kaynak grubu × dönem (deneme) ------------------------------------------------------------------------------------
_MASTER = {"Id": sa.BigInteger(), "ResourceGroupId": sa.BigInteger(), "ResourceGroupCode": sa.Unicode(50), "ResourceGroupName": sa.Unicode(200),
           "CapacityUnit": sa.Unicode(20)}
_VALUES = {"ResourceCount": sa.Integer(), "WorkingDays": sa.Numeric(18, 2), "TotalCapacity": sa.Numeric(18, 4), "AvailableCapacity": sa.Numeric(18, 4),
           "Efficiency": sa.Numeric(18, 6)}
_TYPES = {**_MASTER, **PERIOD_TYPES, **_VALUES}

_SQL = f"""
SELECT CAST(g.Id AS bigint) * 1000 + p.[no] AS Id, g.Id AS ResourceGroupId, g.Code AS ResourceGroupCode, g.Name AS ResourceGroupName, g.CapacityUnit,
       {PERIOD_SELECT},
       COALESCE(mc.n, 0) AS ResourceCount, COALESCE(v.WorkingDay, 0) AS WorkingDays, COALESCE(v.Capacity, 0) AS TotalCapacity,
       COALESCE(v.Available, 0) AS AvailableCapacity, CASE WHEN v.Capacity > 0 THEN v.Available / v.Capacity END AS Efficiency
FROM core.ResourceGroup g
CROSS JOIN OPENJSON(:pt_periods) WITH ({period_list.PERIOD_JSON_SCHEMA}) p
LEFT JOIN (SELECT m.ResourceGroupId, COUNT(DISTINCT m.ResourceId) AS n FROM core.ResourceGroupMember m WHERE m.VersionTo IS NULL
           GROUP BY m.ResourceGroupId) mc ON mc.ResourceGroupId = g.Id
LEFT JOIN (SELECT m.ResourceGroupId, d.[no], SUM(e.WorkingDay) AS WorkingDay, SUM(e.Capacity) AS Capacity, SUM(e.AvailableCapacity) AS Available
           FROM core.ResourceGroupMember m
           JOIN ({{effective}}) e ON e.ResourceId = m.ResourceId
           JOIN OPENJSON(:pt_days) WITH ({period_list.DAY_JSON_SCHEMA}) d ON d.[d] = e.[Date]
           WHERE m.VersionTo IS NULL GROUP BY m.ResourceGroupId, d.[no]) v ON v.ResourceGroupId = g.Id AND v.[no] = p.[no]
WHERE g.VersionTo IS NULL
"""


def _resource_group_source(ctx: SourceContext) -> sa.FromClause:
    """Kaynak grubu × senaryonun dönemleri; değerler önbellekteki kaynak × gün satırlarından, üyelik üzerinden grupta toplanır (K-180).
    Önbellek önce denetlenir: kurulu ve güncelse okunur; değilse (ilk kullanım, ufkun ilerlemesi) eksiği kurulur."""
    found = period_list.read(ctx.session, ctx.scenario_id, ctx.today)
    if found:
        cache.ensure(ctx.session, capacity_demo.CACHE, ctx.scenario_id, found[0].start, found[-1].end)
    base = cache.base_of(ctx.session, cache.scenario_row(ctx.session, ctx.scenario_id))
    effective = cache.effective_sql(capacity_demo.CACHE).replace(":sid", ":pt_sid").replace(":base", ":pt_base")
    text = sa.text(_SQL.format(effective=effective)).bindparams(
        sa.bindparam("pt_periods", period_list.to_json(found), sa.UnicodeText()), sa.bindparam("pt_days", period_list.days_json(found), sa.UnicodeText()),
        sa.bindparam("pt_sid", ctx.scenario_id, sa.Integer()), sa.bindparam("pt_base", base, sa.Integer()))
    return text.columns(*[sa.column(n, t) for n, t in _TYPES.items()]).subquery("pt")


RESOURCE_GROUP_PERIODS = ListDefinition(
    name="period-resource-group-demo",
    table="cache.ResourceCapacityDay",   # etiketler tanımdan; tablo adı yalnız alan tanımı aramasında kullanılır
    fields=("ResourceGroupCode", "ResourceGroupName", "CapacityUnit", *PERIOD_FIELDS, *_VALUES),
    default_visible=("ResourceGroupCode", "ResourceGroupName", "CapacityUnit", *PERIOD_FIELDS, *_VALUES),
    default_sort=(("ResourceGroupCode", "asc"), ("PeriodStart", "asc")),
    server_values=frozenset({"ResourceGroupCode", "CapacityUnit", "PeriodType", "Period", "Week", "Month", "Quarter", "Year"}),
    title="Kaynak grubu × dönem (deneme)", file_slug="kaynak-grubu-donem-deneme", function=10,
    decimals={"WorkingDays": 1, "Efficiency": 1},   # ortalamalar pivotta bir ondalık fazla gösterilir: %98,00
    unit_field="CapacityUnit", unit_decimals=frozenset({"TotalCapacity", "AvailableCapacity"}),
    percent=frozenset({"Efficiency"}),
    # Değer tanımı tek yerde (K-184): varsayılan hesaplama. Kaynak sayısı zamanla toplanmaz (Son dönem değeri); verimlilik kapasiteyle ağırlıklı.
    aggregates={"ResourceCount": "last", "WorkingDays": "sum", "TotalCapacity": "sum", "AvailableCapacity": "sum", "Efficiency": "wavg"},
    aggregate_weights={"Efficiency": "TotalCapacity"},
    versioned=False,
    source=skeleton(_TYPES, "pt"), source_factory=_resource_group_source,
    labels={"ResourceGroupCode": "Kaynak grubu", "ResourceGroupName": "Kaynak grubu adı", "CapacityUnit": "Kapasite birimi", **PERIOD_LABELS,
            "ResourceCount": "Kaynak sayısı", "WorkingDays": "Çalışma günü", "TotalCapacity": "Toplam kapasite", "AvailableCapacity": "Kullanılabilir kapasite",
            "Efficiency": "Verimlilik"},
    notes={**PERIOD_NOTES, "WorkingDays": "Grubun kaynaklarının çalışma günlerinin toplamı (kaynak × gün)",
           "Efficiency": "Kullanılabilir kapasite ÷ toplam kapasite"},
    key_fields=("ResourceGroupId",),
    related_table=relations.register_links("period:resource-group", (("ResourceGroupId", "Kaynak grubu"),)),
    order_by=PERIOD_ORDER, period=("ResourceGroupId", "PeriodStart"),
    standard_pivot={
        "v": 1, "open": True, "rows": [{"field": "ResourceGroupCode"}], "columns": [{"field": "Period"}], "values_on": "rows",
        "values": [{"id": "d1", "field": "ResourceCount", "fn": "last"}, {"id": "d2", "field": "WorkingDays", "fn": "sum"},
                   {"id": "d3", "field": "TotalCapacity", "fn": "sum"}, {"id": "d4", "field": "Efficiency", "fn": "wavg", "weight": "TotalCapacity"},
                   {"id": "d5", "field": "AvailableCapacity", "fn": "sum"}],
        "totals": {"rows": False, "columns": False, "subtotals": False}, "sort": {"by": "name", "dir": "asc"}},
    calculated=({"name": "Ortalama verimlilik", "a": {"field": "AvailableCapacity", "fn": "sum"}, "op": "div",
                 "b": {"field": "TotalCapacity", "fn": "sum"}, "percent": True, "decimals": 2},),
)

PERIOD_TABLES = (RESOURCE_GROUP_PERIODS,)
