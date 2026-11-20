"""Kapasite yönetimi listeleri (ekran 30, fonksiyon 24; K-185, 7.9b): Kaynak grubu ve Kaynak sekmeleri (aktarılan veri, salt okunur) ve beş giriş
tablosu (senaryonun çözümlenmiş satırları; K-176). Giriş listelerinin kaynağı istek başına senaryoya göre kurulur (`source_factory`, K-184).

Giriş satırının kimliği (`Id`) çözümleme katmanındaki `RowId`'dir: Baz satırında Baz'ın, kendi satırında kendi kimliği; yazma uçları
(`/api/capacity/<giriş>`) bu kimlikle çalışır. Çalışan izni (ERP) Bakım ve duruşlar'da salt okunur satırdır: kimliği negatiftir.
"""
import sqlalchemy as sa

from app.capacity import compute, validity
from app.params import resolve
from app.periods import cache

from .definition import ListDefinition, SourceContext
from .period_tables import skeleton

FUNCTION = 24
ERP = "ERP"                                    # çalışan izni satırının "Kaynağı"
LEAVE_TYPE = "Çalışan izni"
DAY_TEXT = {1: "Tam", 0.5: "Yarım", 0: "—"}    # tablodaki yazım; pencerede üçüncü seçenek "Çalışılmıyor"
DAY_VALUE_TEXT = {0: "Çalışılmıyor", 0.5: "Yarım gün"}
DOWNTIME_TYPES = ("Planlı bakım", "Arıza", "Diğer")
DAY_LABELS = dict(zip(resolve.DAYS, ("Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz")))

# --- Kaynak grubu ve Kaynak (aktarılan veri) -------------------------------------------------------------------------------------------

_GROUP_TYPES = {"Id": sa.BigInteger(), "Code": sa.Unicode(50), "Name": sa.Unicode(200), "Type": sa.Unicode(50), "IsCritical": sa.Boolean(),
                "CapacityUnit": sa.Unicode(20), "ResourceCount": sa.Integer()}
_GROUP_SQL = f"""
SELECT g.Id, g.Code, g.Name, g.[Type], g.IsCritical, g.CapacityUnit, COALESCE(mc.n, 0) AS ResourceCount
FROM core.ResourceGroup g
LEFT JOIN (SELECT m.ResourceGroupId, COUNT(*) AS n FROM ({compute.members_sql()}) m GROUP BY m.ResourceGroupId) mc ON mc.ResourceGroupId = g.Id
WHERE g.VersionTo IS NULL
"""
_RESOURCE_TYPES = {"Id": sa.BigInteger(), "Code": sa.Unicode(50), "Name": sa.Unicode(200), "Groups": sa.Unicode(400), "ProductionLocation": sa.Unicode(100),
                   "IsActive": sa.Boolean(), "RemainingOvertimeMonth": sa.Numeric(9, 2), "RemainingOvertimeYear": sa.Numeric(9, 2), "GroupKeys": sa.Unicode(400),
                   "CapacityUnit": sa.Unicode(20)}
_RESOURCE_SQL = f"""
SELECT r.Id, r.Code, r.Name, mg.Groups, r.ProductionLocation, COALESCE(r.IsActive, 1) AS IsActive,
       r.RemainingOverTimeMonth AS RemainingOvertimeMonth, r.RemainingOverTimeYear AS RemainingOvertimeYear, mg.GroupKeys, mg.CapacityUnit
FROM core.Resource r
OUTER APPLY (SELECT STRING_AGG(CAST(g.Code AS nvarchar(max)), N', ') WITHIN GROUP (ORDER BY g.Code) AS Groups,
                    N',' + STRING_AGG(CAST(m.ResourceGroupId AS nvarchar(max)), N',') + N',' AS GroupKeys,
                    CASE WHEN MIN(g.CapacityUnit) = MAX(g.CapacityUnit) THEN MIN(g.CapacityUnit) END AS CapacityUnit
             FROM ({compute.members_sql()}) m JOIN core.ResourceGroup g ON g.Id = m.ResourceGroupId AND g.VersionTo IS NULL
             WHERE m.ResourceId = r.Id) mg
WHERE r.VersionTo IS NULL
"""


def _static(sql: str, types: dict, name: str) -> sa.FromClause:
    return sa.text(sql).columns(*[sa.column(n, t) for n, t in types.items()]).subquery(name)


RESOURCE_GROUPS = ListDefinition(
    name="capacity-resource-groups", table="core.ResourceGroup", function=FUNCTION, versioned=False,
    title="Kaynak grupları (kapasite)", file_slug="kapasite-kaynak-gruplari",
    source=_static(_GROUP_SQL, _GROUP_TYPES, "cap_groups"),
    fields=("Code", "Name", "Type", "IsCritical", "CapacityUnit", "ResourceCount"),
    default_visible=("Code", "Name", "Type", "IsCritical", "CapacityUnit", "ResourceCount"),
    default_sort=(("Code", "asc"),),
    server_values=frozenset({"Type", "CapacityUnit"}),
    labels={"Code": "Kaynak grubu", "Name": "Ad", "Type": "Tip", "IsCritical": "Kritik", "CapacityUnit": "Kapasite birimi", "ResourceCount": "Kaynak sayısı"},
)

RESOURCES = ListDefinition(
    name="capacity-resources", table="core.Resource", function=FUNCTION, versioned=False,
    title="Kaynaklar (kapasite)", file_slug="kapasite-kaynaklar",
    source=_static(_RESOURCE_SQL, _RESOURCE_TYPES, "cap_resources"),
    fields=("Code", "Name", "Groups", "ProductionLocation", "IsActive", "RemainingOvertimeMonth", "RemainingOvertimeYear"),
    default_visible=("Code", "Name", "Groups", "ProductionLocation", "IsActive", "RemainingOvertimeMonth", "RemainingOvertimeYear"),
    default_sort=(("Code", "asc"),),
    server_values=frozenset({"ProductionLocation"}),
    decimals={"RemainingOvertimeMonth": 2, "RemainingOvertimeYear": 2},
    labels={"Code": "Kaynak", "Name": "Ad", "Groups": "Kaynak grupları", "ProductionLocation": "Üretim yeri", "IsActive": "Aktif",
            "RemainingOvertimeMonth": "Kalan fazla mesai (ay)", "RemainingOvertimeYear": "Kalan fazla mesai (yıl)", "GroupKeys": "Grup anahtarları",
            "CapacityUnit": "Kapasite birimi"},
    notes={"RemainingOvertimeMonth": "ERP'den (saat)", "RemainingOvertimeYear": "ERP'den (saat)"},
    filter_only=("GroupKeys",), key_fields=("CapacityUnit",),
)

# --- Giriş tabloları -------------------------------------------------------------------------------------------------------------------

_COMMON = {"Id": sa.BigInteger(), "StoredId": sa.BigInteger(), "Origin": sa.Unicode(20), "IsValid": sa.Boolean(), "OverriddenFields": sa.Unicode(400),
           "BaseValues": sa.UnicodeText()}
_OWNER = {"Level": sa.Unicode(10), "Code": sa.Unicode(50), "ResourceGroupId": sa.BigInteger(), "ResourceId": sa.BigInteger(), "OwnerKeys": sa.Unicode(400),
          "CapacityUnit": sa.Unicode(20)}
_COMMON_LABELS = {"Origin": "Kaynağı", "IsValid": "Geçerli", "Level": "Seviye", "Code": "Kod", "CapacityUnit": "Birim", "ValidFrom": "Başlangıç", "ValidTo": "Bitiş",
                  "StartDate": "Başlangıç", "EndDate": "Bitiş", "OwnerKeys": "Sahip anahtarları", "ResourceId": "Kaynak no", "ResourceGroupId": "Kaynak grubu no",
                  "StoredId": "Saklanan satır", "OverriddenFields": "Senaryoda değişen alanlar", "BaseValues": "Baz değerleri"}
_NOTES = {"Origin": "Baz: Baz senaryodan okunur · Senaryo farkı: Baz satırı bu senaryoda değiştirildi · Senaryo: yalnız bu senaryoda",
          "Level": "Kayıt gruba mı kaynağa mı girildi; kaynakta kayıt varsa o geçerlidir, yoksa grubunki"}
KEYS = ("StoredId", "Origin", "IsValid", "OverriddenFields", "BaseValues")
OWNER_KEYS = ("ResourceGroupId", "ResourceId")

# kaynağın tek kapasite birimi (bütün grupları aynı birimdeyse)
_UNIT = (f"COALESCE(g.CapacityUnit, (SELECT CASE WHEN MIN(g2.CapacityUnit) = MAX(g2.CapacityUnit) THEN MIN(g2.CapacityUnit) END FROM ({compute.members_sql()}) m2 "
         "JOIN core.ResourceGroup g2 ON g2.Id = m2.ResourceGroupId AND g2.VersionTo IS NULL WHERE m2.ResourceId = z.ResourceId))")
# Sahip anahtarları (kartta süzme): grup kaydı ",g12,"; kaynak kaydı ",r5,g12,g15," (kaynağın kendisi ve grupları)
_GROUP_KEYS = ("CASE WHEN z.ResourceId IS NULL THEN N',g' + CAST(z.ResourceGroupId AS nvarchar(20)) + N',' ELSE N',r' + CAST(z.ResourceId AS nvarchar(20)) + N',' + "
               "COALESCE((SELECT STRING_AGG(N'g' + CAST(m3.ResourceGroupId AS nvarchar(max)), N',') + N',' "
               f"FROM ({compute.members_sql()}) m3 WHERE m3.ResourceId = z.ResourceId), N'') END")
_OWNER_SELECT = (f"CASE WHEN z.ResourceId IS NULL THEN N'Grup' ELSE N'Kaynak' END AS [Level], COALESCE(r.Code, g.Code) AS Code, z.ResourceGroupId, z.ResourceId, "
                 f"{_GROUP_KEYS} AS OwnerKeys, {_UNIT} AS CapacityUnit")
_OWNER_JOIN = ("LEFT JOIN core.Resource r ON r.Id = z.ResourceId AND r.VersionTo IS NULL "
               "LEFT JOIN core.ResourceGroup g ON g.Id = z.ResourceGroupId AND g.VersionTo IS NULL")
# Baz senaryoda (ve Baz'ı izlemeyen senaryoda) kendi satırı: Baz'da "Baz", ötekinde "Senaryo"
_ORIGIN = "CASE WHEN :cap_is_base = 1 THEN N'Baz' ELSE z.Origin END AS Origin"
_HEAD = f"z.RowId AS Id, z.StoredId, {_ORIGIN}, z.IsValid, z.OverriddenFields, z.BaseValues"


def _case(column: str, mapping: dict) -> str:
    whens = " ".join(f"WHEN {column} = {value} THEN N'{text}'" for value, text in mapping.items())
    return f"CASE {whens} END"


def _source(select: str, types: dict, name: str):
    """İstekte kaynağı kuran işlev: senaryonun çözümlenmiş satırları (geçersiz yapılanlar dahil; ekranda görünür ve geri alınabilir)."""
    def factory(ctx: SourceContext) -> sa.FromClause:
        scenario = cache.scenario_row(ctx.session, ctx.scenario_id)
        binds = [sa.bindparam("cap_sid", ctx.scenario_id, sa.Integer()), sa.bindparam("cap_base", cache.base_of(ctx.session, scenario), sa.Integer())]
        if ":cap_is_base" in select:
            binds.append(sa.bindparam("cap_is_base", 1 if scenario["IsBase"] else 0, sa.Integer()))
        return sa.text(select).bindparams(*binds).columns(*[sa.column(n, t) for n, t in types.items()]).subquery(name)
    return factory


def _resolved(table: str) -> str:
    return resolve.sql(table, valid_only=False, sid=":cap_sid", base=":cap_base", detail=True)


def _entry(name: str, table: str, title: str, slug: str, values: dict, select: str, labels: dict, *, decimals=None, unit_decimals=(), lists=None,
           owner: bool = True, start: str = "ValidFrom", extra_sql: str = "", sort=None, wrap=None) -> ListDefinition:
    types = {**_COMMON, **(_OWNER if owner else {}), **values}
    head = f"{_HEAD}, {_OWNER_SELECT}, " if owner else f"{_HEAD}, "
    sql = f"SELECT {head}{select} FROM ({_resolved(table)}) z {_OWNER_JOIN if owner else ''}{extra_sql}"
    if wrap is not None:   # listenin üstüne hesaplanan kolon (ör. "Gün")
        sql = wrap(sql)
    shown = (*(("Level", "Code") if owner else ()), *[f for f in values if f not in ("CapacityUnit",)], "Origin", "IsValid")
    if owner and "CapacityUnit" in labels:           # Birim, değerin hemen ardında
        at = shown.index(labels["CapacityUnit"]) + 1
        shown = (*shown[:at], "CapacityUnit", *shown[at:])
    return ListDefinition(
        name=name, table=f"param.{table}", function=FUNCTION, versioned=False, title=title, file_slug=slug,
        source=skeleton(types, "cap"), source_factory=_source(sql, types, "cap"),
        fields=shown, default_visible=shown,
        default_sort=sort or ((("Level", "asc"), ("Code", "asc"), (start, "asc")) if owner else ((start, "asc"),)),
        server_values=frozenset({"Code", "CapacityUnit"} if owner else set()),
        decimals=decimals or {}, unit_field="CapacityUnit" if unit_decimals else None, unit_decimals=frozenset(unit_decimals),
        values={"Origin": ["Baz", "Senaryo farkı", "Senaryo", ERP], "Level": ["Grup", "Kaynak"], **(lists or {})},
        labels={**_COMMON_LABELS, **{k: v for k, v in labels.items() if k != "CapacityUnit"}}, notes=_NOTES,
        key_fields=(*KEYS, *(OWNER_KEYS if owner else ())), filter_only=("OwnerKeys",) if owner else (),
    )


_DAYS_SQL = ", ".join(f"{_case('z.[' + d + ']', {'1': 'Tam', '0.5': 'Yarım', '0': '—'})} AS [{d}]" for d in resolve.DAYS)
WORK_PATTERNS = _entry(
    "capacity-work-patterns", "WorkPattern", "Çalışma düzeni", "kapasite-calisma-duzeni",
    {"ValidFrom": sa.Date(), "ValidTo": sa.Date(), "DailyCapacity": sa.Numeric(18, 4), **{d: sa.Unicode(10) for d in resolve.DAYS}},
    f"z.ValidFrom, z.ValidTo, z.DailyCapacity, {_DAYS_SQL}",
    {"DailyCapacity": "Günlük kapasite", "CapacityUnit": "DailyCapacity", **DAY_LABELS},
    unit_decimals=("DailyCapacity",), lists={d: list(DAY_TEXT.values()) for d in resolve.DAYS})

EFFICIENCY = _entry(
    "capacity-efficiency", "ResourceEfficiency", "Verimlilik", "kapasite-verimlilik",
    {"ValidFrom": sa.Date(), "ValidTo": sa.Date(), "EfficiencyPct": sa.Numeric(6, 2)},
    "z.ValidFrom, z.ValidTo, z.EfficiencyPct", {"EfficiencyPct": "Verimlilik (%)"}, decimals={"EfficiencyPct": 2})

OVERTIME_LIMITS = _entry(
    "capacity-overtime-limits", "OvertimeLimit", "Ek mesai limitleri", "kapasite-ek-mesai-limitleri",
    {"ValidFrom": sa.Date(), "ValidTo": sa.Date(), "DailyLimit": sa.Numeric(18, 4)},
    "z.ValidFrom, z.ValidTo, z.DailyLimit", {"DailyLimit": "Günlük limit", "CapacityUnit": "DailyLimit"}, unit_decimals=("DailyLimit",))

# Bakım ve duruşlar: elle girilenler ve ERP'den gelen çalışan izinleri (salt okunur; kimliği negatif). "Gün" (K-188): kaydın kayıp günü
def _with_lost_days(sql: str) -> str:
    """Listenin satırlarına "Gün" eklenir: kayıp gün bütün kayıtlar için bir kez hesaplanır ve kimlikle birleştirilir."""
    rows = ("SELECT d.RowId AS Id, d.ResourceId, d.ResourceGroupId, d.StartDate, d.EndDate, CAST(NULL AS decimal(9,2)) AS Hours "
            f"FROM ({resolve.sql('ResourceDowntime', valid_only=False, sid=':cap_sid', base=':cap_base')}) d "
            "UNION ALL SELECT -ab.Id, ab.ResourceId, CAST(NULL AS bigint), ab.StartDate, ab.EndDate, ab.HoursPerDay FROM core.EmployeeAbsence ab WHERE ab.VersionTo IS NULL")
    lost = validity.lost_days_sql(rows, sid=":cap_sid", base=":cap_base")
    return f"SELECT u.*, CAST(COALESCE(ld.LostDays, 0) AS decimal(18,4)) AS LostDays FROM ({sql}) u LEFT JOIN ({lost}) ld ON ld.Id = u.Id"


_LEAVE_SQL = (f" UNION ALL SELECT -ab.Id AS Id, CAST(NULL AS bigint) AS StoredId, N'{ERP}' AS Origin, CAST(1 AS bit) AS IsValid, CAST(NULL AS varchar(400)) AS OverriddenFields, "
              "CAST(NULL AS nvarchar(max)) AS BaseValues, N'Kaynak' AS [Level], r.Code, CAST(NULL AS bigint) AS ResourceGroupId, ab.ResourceId, "
              "N',r' + CAST(ab.ResourceId AS nvarchar(20)) + N',' + COALESCE((SELECT STRING_AGG(N'g' + CAST(m4.ResourceGroupId AS nvarchar(max)), N',') + N',' "
              f"FROM ({compute.members_sql()}) m4 WHERE m4.ResourceId = ab.ResourceId), N'') AS OwnerKeys, "
              f"CAST(NULL AS nvarchar(20)) AS CapacityUnit, N'{LEAVE_TYPE}' AS DowntimeType, CAST(ab.AbsenceType AS nvarchar(255)) AS Reason, ab.StartDate, ab.EndDate "
              "FROM core.EmployeeAbsence ab JOIN core.Resource r ON r.Id = ab.ResourceId AND r.VersionTo IS NULL WHERE ab.VersionTo IS NULL")
DOWNTIME = _entry(
    "capacity-downtime", "ResourceDowntime", "Bakım ve duruşlar", "kapasite-bakim-ve-duruslar",
    {"DowntimeType": sa.Unicode(20), "Reason": sa.Unicode(255), "StartDate": sa.Date(), "EndDate": sa.Date(), "LostDays": sa.Numeric(18, 4)},
    "CAST(z.DowntimeType AS nvarchar(20)) AS DowntimeType, CAST(z.Reason AS nvarchar(255)) AS Reason, z.StartDate, z.EndDate",
    {"DowntimeType": "Tip", "Reason": "Sebep", "LostDays": "Gün"}, decimals={"LostDays": 1},
    lists={"DowntimeType": [*DOWNTIME_TYPES, LEAVE_TYPE]}, start="StartDate", extra_sql=_LEAVE_SQL, wrap=_with_lost_days,
    sort=(("StartDate", "asc"), ("Code", "asc")))

FACTORY_CALENDAR = _entry(
    "capacity-factory-calendar", "FactoryCalendar", "Fabrika takvimi", "kapasite-fabrika-takvimi",
    {"StartDate": sa.Date(), "EndDate": sa.Date(), "Name": sa.Unicode(100), "DayValue": sa.Unicode(20)},
    f"z.StartDate, z.EndDate, CAST(z.Name AS nvarchar(100)) AS Name, {_case('z.DayValue', {'0': 'Çalışılmıyor', '0.5': 'Yarım gün'})} AS DayValue",
    {"Name": "Ad", "DayValue": "Çalışma"}, lists={"DayValue": list(DAY_VALUE_TEXT.values())}, owner=False, start="StartDate")

ENTRY_LISTS = (WORK_PATTERNS, EFFICIENCY, OVERTIME_LIMITS, DOWNTIME, FACTORY_CALENDAR)

# --- Geçerlilik (7.9c, K-188): kaynak grubu × kaynak × aralık; salt okunur -------------------------------------------------------------

_VALIDITY_HEAD = {"Id": sa.BigInteger(), "ResourceGroupId": sa.BigInteger(), "ResourceId": sa.BigInteger(), "GroupCode": sa.Unicode(50), "Code": sa.Unicode(50),
                  "ValidFrom": sa.Date(), "ValidTo": sa.Date()}
_VALIDITY_TAIL = {"CapacityUnit": sa.Unicode(20), "SourceRecord": sa.Unicode(120), "SourceRowId": sa.BigInteger(), "SourceSpan": sa.Unicode(160),
                  "SourceLevel": sa.Unicode(10), "SourceOrigin": sa.Unicode(20), "OwnerKeys": sa.Unicode(100)}
_DATE = "CONVERT(nvarchar(10), {0}, 104)"
_SPAN = (f"CASE WHEN v.RecTo IS NULL THEN {_DATE.format('v.RecFrom')} + NCHAR(39) + N'dan itibaren' ELSE {_DATE.format('v.RecFrom')} + N' – ' + {_DATE.format('v.RecTo')} END")


def _validity(kind: str, title: str, slug: str, values: dict, select: str, labels: dict, *, decimals=None, unit_decimals=(), lists=None) -> ListDefinition:
    table, fields = validity.KINDS[kind]
    types = {**_VALIDITY_HEAD, **values, **_VALIDITY_TAIL}
    sql = (f"SELECT ROW_NUMBER() OVER (ORDER BY v.ResourceGroupId, v.ResourceId, v.ValidFrom) AS Id, v.ResourceGroupId, v.ResourceId, g.Code AS GroupCode, r.Code, "
           f"v.ValidFrom, v.ValidTo, {select}, g.CapacityUnit, src.Label + N' · ' + {_DATE.format('v.RecFrom')} AS SourceRecord, v.RowId AS SourceRowId, "
           f"src.Label + N' · ' + {_SPAN} AS SourceSpan, CASE WHEN v.lvl = 0 THEN N'Kaynak' ELSE N'Grup' END AS SourceLevel, "
           "CASE WHEN :cap_is_base = 1 THEN N'Baz' ELSE v.Origin END AS SourceOrigin, "
           "N',g' + CAST(v.ResourceGroupId AS nvarchar(20)) + N',r' + CAST(v.ResourceId AS nvarchar(20)) + N',' AS OwnerKeys "
           f"FROM ({validity.intervals_sql(table, fields, ':cap_sid', ':cap_base')}) v "
           "JOIN core.Resource r ON r.Id = v.ResourceId AND r.VersionTo IS NULL JOIN core.ResourceGroup g ON g.Id = v.ResourceGroupId AND g.VersionTo IS NULL "
           "CROSS APPLY (SELECT CASE WHEN v.lvl = 0 THEN N'Kaynak ' + r.Code ELSE N'Grup ' + g.Code END AS Label) src")
    shown = ["GroupCode", "Code", "ValidFrom", "ValidTo", *values, "SourceRecord"]
    if unit_decimals:                                   # Birim, değerin hemen ardında
        shown.insert(shown.index(unit_decimals[0]) + 1, "CapacityUnit")
    return ListDefinition(
        name=f"capacity-{kind}-validity", table=f"param.{table}", function=FUNCTION, versioned=False, title=f"{title} · Geçerlilik", file_slug=f"{slug}-gecerlilik",
        source=skeleton(types, "capv"), source_factory=_source(sql, types, "capv"),
        fields=tuple(shown), default_visible=tuple(shown),
        default_sort=(("GroupCode", "asc"), ("Code", "asc"), ("ValidFrom", "asc")),
        server_values=frozenset({"GroupCode", "Code", "CapacityUnit", "SourceRecord"}),
        decimals=decimals or {}, unit_field="CapacityUnit" if unit_decimals else None, unit_decimals=frozenset(unit_decimals), values=lists or {},
        labels={"GroupCode": "Kaynak grubu", "Code": "Kaynak", "ValidFrom": "Başlangıç", "ValidTo": "Bitiş", "CapacityUnit": "Birim", "SourceRecord": "Geçerli kayıt",
                "SourceRowId": "Geçerli kayıt no", "SourceSpan": "Geçerli kaydın aralığı", "SourceLevel": "Geçerli kaydın seviyesi",
                "SourceOrigin": "Geçerli kaydın kaynağı", "OwnerKeys": "Sahip anahtarları", "ResourceId": "Kaynak no",
                "ResourceGroupId": "Kaynak grubu no", **labels},
        notes={"SourceRecord": "Değerin geldiği kayıt: seviyesi, kodu ve başlangıcı"},
        key_fields=("SourceRowId", "SourceSpan", "SourceLevel", "SourceOrigin", "ResourceGroupId", "ResourceId"), filter_only=("OwnerKeys",),
    )


_VDAYS_SQL = ", ".join(f"{_case('v.[' + d + ']', {'1': 'Tam', '0.5': 'Yarım', '0': '—'})} AS [{d}]" for d in resolve.DAYS)
VALIDITY_LISTS = (
    _validity("work-patterns", "Çalışma düzeni", "kapasite-calisma-duzeni", {"DailyCapacity": sa.Numeric(18, 4), **{d: sa.Unicode(10) for d in resolve.DAYS}},
              f"v.DailyCapacity, {_VDAYS_SQL}", {"DailyCapacity": "Günlük kapasite", **DAY_LABELS}, unit_decimals=("DailyCapacity",),
              lists={d: list(DAY_TEXT.values()) for d in resolve.DAYS}),
    _validity("efficiency", "Verimlilik", "kapasite-verimlilik", {"EfficiencyPct": sa.Numeric(6, 2)}, "v.EfficiencyPct", {"EfficiencyPct": "Verimlilik (%)"},
              decimals={"EfficiencyPct": 2}),
    _validity("overtime-limits", "Ek mesai limitleri", "kapasite-ek-mesai-limitleri", {"DailyLimit": sa.Numeric(18, 4)}, "v.DailyLimit", {"DailyLimit": "Günlük limit"},
              unit_decimals=("DailyLimit",)),
)
CAPACITY_LISTS = (RESOURCE_GROUPS, RESOURCES, *ENTRY_LISTS, *VALIDITY_LISTS)
