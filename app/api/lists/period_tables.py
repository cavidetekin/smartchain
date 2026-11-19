"""Dönem tabloları (K-184, docs/12 "Dönem tablosu standardı"): bir ana kaydın dönem bazındaki özeti. Satırlar veritabanında durmaz; kaynak
her istekte senaryonun dönemleriyle kurulur, değerler önbellekteki günlük ara sonuçtan toplanır (`app/periods`).

Kaynak grubu × dönem (K-185): Kapasite yönetimi'nin "Kapasite özeti" sekmesi ve Kaynak grubu kartının "Dönem özeti".
"""
import sqlalchemy as sa

from app.capacity import compute
from app.periods import cache, periods as period_list

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


# --- Kaynak grubu × dönem (K-185 E) -----------------------------------------------------------------------------------
_MASTER = {"Id": sa.BigInteger(), "ResourceGroupId": sa.BigInteger(), "ResourceGroupCode": sa.Unicode(50), "ResourceGroupName": sa.Unicode(200),
           "CapacityUnit": sa.Unicode(20)}
_VALUES = {"ResourceCount": sa.Integer(), "WorkingDays": sa.Numeric(18, 2), "Downtime": sa.Numeric(18, 4), "WorkableDays": sa.Numeric(18, 4),
           "AvgDailyCapacity": sa.Numeric(18, 4), "TotalDailyCapacity": sa.Numeric(18, 4), "Efficiency": sa.Numeric(18, 6),
           "TotalCapacity": sa.Numeric(18, 4), "AvailableCapacity": sa.Numeric(18, 4), "OvertimeLimit": sa.Numeric(18, 4),
           "RemainingOvertimeMonth": sa.Numeric(18, 2), "RemainingOvertimeYear": sa.Numeric(18, 2)}
_TYPES = {**_MASTER, **PERIOD_TYPES, **_VALUES}

# Brüt = çalışma günü × günlük kapasite (verimliliksiz): ortalama ve toplam günlük kapasitenin ve verimliliğin payı ya da paydası
_SQL = f"""
SELECT CAST(g.Id AS bigint) * 1000 + p.[no] AS Id, g.Id AS ResourceGroupId, g.Code AS ResourceGroupCode, g.Name AS ResourceGroupName, g.CapacityUnit,
       {PERIOD_SELECT},
       COALESCE(mc.n, 0) AS ResourceCount, COALESCE(v.WorkingDays, 0) AS WorkingDays, COALESCE(v.Downtime, 0) AS Downtime,
       CAST(COALESCE(v.WorkingDays - v.Downtime, 0) AS decimal(18,4)) AS WorkableDays,
       CAST(CASE WHEN v.WorkingDays > 0 THEN CAST(v.Gross AS float) / CAST(v.WorkingDays AS float) END AS decimal(18,4)) AS AvgDailyCapacity,
       CAST(CASE WHEN v.WorkedDays > 0 THEN CAST(v.Gross AS float) / v.WorkedDays END AS decimal(18,4)) AS TotalDailyCapacity,
       CAST(CASE WHEN v.Gross > 0 THEN CAST(v.Capacity AS float) / CAST(v.Gross AS float) END AS decimal(18,6)) AS Efficiency,
       COALESCE(v.Capacity, 0) AS TotalCapacity, COALESCE(v.Available, 0) AS AvailableCapacity, COALESCE(v.Overtime, 0) AS OvertimeLimit,
       mc.RemainingMonth AS RemainingOvertimeMonth, mc.RemainingYear AS RemainingOvertimeYear
FROM core.ResourceGroup g
CROSS JOIN OPENJSON(:pt_periods) WITH ({period_list.PERIOD_JSON_SCHEMA}) p
LEFT JOIN (SELECT m.ResourceGroupId, COUNT(*) AS n, SUM(r.RemainingOverTimeMonth) AS RemainingMonth, SUM(r.RemainingOverTimeYear) AS RemainingYear
           FROM ({compute.members_sql()}) m JOIN core.Resource r ON r.Id = m.ResourceId AND r.VersionTo IS NULL
           GROUP BY m.ResourceGroupId) mc ON mc.ResourceGroupId = g.Id
LEFT JOIN (SELECT e.ResourceGroupId, d.[no], SUM(CAST(e.WorkingDay AS decimal(18,4))) AS WorkingDays, SUM(CAST(e.Downtime AS decimal(18,4))) AS Downtime,
                  SUM(CAST(e.WorkingDay * e.DailyCapacity AS decimal(18,4))) AS Gross, SUM(e.Capacity) AS Capacity, SUM(e.AvailableCapacity) AS Available,
                  SUM(e.OvertimeLimit) AS Overtime, COUNT(DISTINCT CASE WHEN e.WorkingDay > 0 THEN e.[Date] END) AS WorkedDays
           FROM ({{effective}}) e
           JOIN OPENJSON(:pt_days) WITH ({period_list.DAY_JSON_SCHEMA}) d ON d.[d] = e.[Date]
           GROUP BY e.ResourceGroupId, d.[no]) v ON v.ResourceGroupId = g.Id AND v.[no] = p.[no]
WHERE g.VersionTo IS NULL
"""


def _resource_group_source(ctx: SourceContext) -> sa.FromClause:
    """Kaynak grubu × senaryonun dönemleri; değerler önbellekteki kaynak grubu × kaynak × gün satırlarından toplanır (K-185).
    Önbellek önce denetlenir: kurulu ve güncelse okunur; değilse (ilk kullanım, ufkun ilerlemesi) eksiği kurulur."""
    found = period_list.read(ctx.session, ctx.scenario_id, ctx.today)
    if found:
        cache.ensure(ctx.session, compute.CACHE, ctx.scenario_id, found[0].start, found[-1].end)
    base = cache.base_of(ctx.session, cache.scenario_row(ctx.session, ctx.scenario_id))
    effective = cache.effective_sql(compute.CACHE).replace(":sid", ":pt_sid").replace(":base", ":pt_base")
    text = sa.text(_SQL.format(effective=effective)).bindparams(
        sa.bindparam("pt_periods", period_list.to_json(found), sa.UnicodeText()), sa.bindparam("pt_days", period_list.days_json(found), sa.UnicodeText()),
        sa.bindparam("pt_sid", ctx.scenario_id, sa.Integer()), sa.bindparam("pt_base", base, sa.Integer()))
    return text.columns(*[sa.column(n, t) for n, t in _TYPES.items()]).subquery("pt")


_CAPACITY = ("AvgDailyCapacity", "TotalDailyCapacity", "TotalCapacity", "AvailableCapacity", "OvertimeLimit")   # grubun kapasite biriminde
RESOURCE_GROUP_PERIODS = ListDefinition(
    name="period-resource-group",
    table="cache.ResourceCapacityDay",   # etiketler tanımdan; tablo adı yalnız alan tanımı aramasında kullanılır
    fields=("ResourceGroupCode", "ResourceGroupName", "CapacityUnit", *PERIOD_FIELDS, *_VALUES),
    default_visible=("ResourceGroupCode", "ResourceGroupName", "CapacityUnit", *PERIOD_FIELDS, *_VALUES),
    default_sort=(("ResourceGroupCode", "asc"), ("PeriodStart", "asc")),
    server_values=frozenset({"ResourceGroupCode", "CapacityUnit", "PeriodType", "Period", "Week", "Month", "Quarter", "Year"}),
    title="Kaynak grubu × dönem", file_slug="kaynak-grubu-donem", function=24,
    decimals={"WorkingDays": 1, "Downtime": 1, "WorkableDays": 1, "Efficiency": 1, "RemainingOvertimeMonth": 2, "RemainingOvertimeYear": 2},
    unit_field="CapacityUnit", unit_decimals=frozenset(_CAPACITY),
    percent=frozenset({"Efficiency"}),
    # Değer tanımı tek yerde (K-184, K-185 E): varsayılan hesaplama. Kaynak sayısı ve ERP'nin kalan fazla mesaisi zamanla toplanmaz (Son dönem
    # değeri); iki günlük kapasite alanı toplanmaz (ortalama); verimlilik kapasiteyle ağırlıklı.
    aggregates={"ResourceCount": "last", "WorkingDays": "sum", "Downtime": "sum", "WorkableDays": "sum", "AvgDailyCapacity": "avg",
                "TotalDailyCapacity": "avg", "Efficiency": "wavg", "TotalCapacity": "sum", "AvailableCapacity": "sum", "OvertimeLimit": "sum",
                "RemainingOvertimeMonth": "last", "RemainingOvertimeYear": "last"},
    aggregate_weights={"Efficiency": "TotalCapacity"},
    versioned=False,
    source=skeleton(_TYPES, "pt"), source_factory=_resource_group_source,
    labels={"ResourceGroupCode": "Kaynak grubu", "ResourceGroupName": "Kaynak grubu adı", "CapacityUnit": "Kapasite birimi", **PERIOD_LABELS,
            "ResourceCount": "Kaynak sayısı", "WorkingDays": "Çalışma günü", "Downtime": "Duruş", "WorkableDays": "Çalışılabilir gün",
            "AvgDailyCapacity": "Ortalama günlük kapasite", "TotalDailyCapacity": "Toplam günlük kapasite", "Efficiency": "Verimlilik",
            "TotalCapacity": "Toplam kapasite", "AvailableCapacity": "Kullanılabilir kapasite", "OvertimeLimit": "Ek mesai limiti",
            "RemainingOvertimeMonth": "Kalan fazla mesai (ay)", "RemainingOvertimeYear": "Kalan fazla mesai (yıl)"},
    notes={**PERIOD_NOTES,
           "ResourceCount": "Gruptaki kaynak sayısı (eşleşmeden)",
           "WorkingDays": "Çalışma düzenindeki çalışma günleri, kaynak × gün (Tam 1, Yarım 0,5)",
           "Downtime": "Fabrika takvimi, bakım ve duruş, çalışan izni; kaynak × gün. Günün çalışma değerini aşmaz, aynı gün bir kez sayılır",
           "WorkableDays": "Çalışma günü − duruş; kaynak × gün",
           "AvgDailyCapacity": "Kaynak başına günlük kapasite; kaynakların değeri farklıysa çalışma gününe göre ağırlıklı",
           "TotalDailyCapacity": "Grubun bir çalışma günündeki toplam kapasitesi; dönem içinde değişiyorsa çalışılan günlerin ortalaması",
           "Efficiency": "Toplam kapasite ÷ verimliliksiz kapasite",
           "TotalCapacity": "Çalışma günü × günlük kapasite × verimlilik (fabrika tatillerini içerir)",
           "AvailableCapacity": "Çalışılabilir × günlük kapasite × verimlilik",
           "OvertimeLimit": "Çalışılabilir gün × günlük ek mesai limiti",
           "RemainingOvertimeMonth": "ERP'den: kaynakların aylık kalan fazla mesaisinin toplamı (saat); dönemlere dağıtılmaz",
           "RemainingOvertimeYear": "ERP'den: kaynakların yıllık kalan fazla mesaisinin toplamı (saat); dönemlere dağıtılmaz"},
    key_fields=("ResourceGroupId",),
    related_table=relations.register_links("period:resource-group", (("ResourceGroupId", "Kaynak grubu"),)),
    order_by=PERIOD_ORDER, period=("ResourceGroupId", "PeriodStart"),
    chart_value="AvailableCapacity",   # grafik ilk açılışta Kullanılabilir kapasite ile gelir (K-186)
    standard_pivot={
        "v": 1, "open": True, "rows": [{"field": "ResourceGroupCode"}], "columns": [{"field": "Period"}], "values_on": "rows",
        "values": [{"id": "d1", "field": "TotalCapacity", "fn": "sum"}, {"id": "d2", "field": "AvailableCapacity", "fn": "sum"},
                   {"id": "d3", "field": "Downtime", "fn": "sum"}],
        "totals": {"rows": False, "columns": False, "subtotals": False}, "sort": {"by": "name", "dir": "asc"}},
    calculated=({"name": "Duruş oranı", "a": {"field": "Downtime", "fn": "sum"}, "op": "div", "b": {"field": "WorkingDays", "fn": "sum"},
                 "percent": True, "decimals": 2},
                {"name": "Kullanılabilirlik", "a": {"field": "AvailableCapacity", "fn": "sum"}, "op": "div", "b": {"field": "TotalCapacity", "fn": "sum"},
                 "percent": True, "decimals": 2}),
)

PERIOD_TABLES = (RESOURCE_GROUP_PERIODS,)
