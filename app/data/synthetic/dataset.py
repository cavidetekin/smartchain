"""Sentetik veri seti v0'ın tek tanımı (docs/11, K-78, K-79). Bellekte üretir; veritabanına ve dosyaya dokunmaz.

Satırlar ana tabloların (core.*) alan adlarıyla; Id'ler tablo başına 1'den. LocationId = 1 ve ScenarioDefinitionId = 1
yer tutucudur, yükleyici gerçek Id'yi yazar. Versiyon alanlarını (VersionFrom …) yükleyici ekler; BusinessKey burada.

Tarihler üretim gününe göre: hafta 1, üretim gününün Pazartesi'siyle başlar (K-79). Rastgelelik yalnız ad, miktar
ve küçük sapmalarda; bilerek konmuş durumlar (situations.py) elle yazılıdır. Aynı tohum + aynı gün = aynı veri.
"""
import random
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

SEED = 22  # MDD adım 22
SET_NAME = "Sentetik v0"
LOCATION_CODE = "ORM-01"
HORIZON_WEEKS = 13
# Sentetik senaryolar (docs/11, K-177): Baz'dan kopyalanır; ad, Baz'ı izler, gece çalışsın, parametre farkları, süre bütçesi böleni
SCENARIOS = (
    ("Fazla mesaili", True, True, {"UseOvertime": True}, 1),
    ("Kısıtsız kapasite", True, True, {"ResourceConstraint": "Kısıtsız"}, 2),
    ("MILP deneme", False, False, {"ModelType": "MILP", "ProductionMinLot": True, "ProductionLotMultiple": True}, 1),
)
# Model kısıtları (K-189): kaynak grubu, kısıtsız kapasite çarpanı, hedef doluluk (%). "Kısıtsız kapasite" senaryosunun farkları yüklemede yazılır
MODEL_CONSTRAINTS = (("TORNA", None, 85.0), ("ISL3", None, 90.0), ("MONTAJ", 1.5, None))
MODEL_CONSTRAINT_DIFF = ("MONTAJ", 2.0)        # "Kısıtsız kapasite": Baz'daki çarpanın farkı
# Uyarı eşikleri (K-190): "Kısıtsız kapasite" senaryosunda farklı eşik (Düşük, Orta, Yüksek, Kritik) ve kapalı bir uyarı
WARNING_THRESHOLD_CHANGE = ("CAP_OVERLOAD", (None, 110, 125, 150))
WARNING_THRESHOLD_OFF = "CAP_LOW_LOAD"
MODEL_CONSTRAINT_OWN = ("TASLAMA", 1.25)       # "Kısıtsız kapasite": senaryonun kendi değeri (Baz'da yok)
HISTORY_DAYS = 21

FINISHED = [  # kod, ad, kısa ad
    ("MAM-001", "Pompa gövdesi PG-80", "PG-80"),
    ("MAM-002", "Redüktör R-120", "R-120"),
    ("MAM-003", "Bağlantı ünitesi BU-50", "BU-50"),
    ("MAM-004", "Pompa gövdesi PG-100", "PG-100"),
    ("MAM-005", "Redüktör R-160", "R-160"),
    ("MAM-006", "Kaplin ünitesi KU-40", "KU-40"),
    ("MAM-007", "Valf bloğu VB-25", "VB-25"),
    ("MAM-008", "Flanşlı basınç gövdesi FG-200", "FG-200"),
    ("MAM-009", "Dişli kutusu DK-90", "DK-90"),
    ("MAM-010", "Tahrik ünitesi TU-30", "TU-30"),
]
ASSEMBLIES = ["Gövde montajı", "Mil grubu", "Kapak montajı"]
PART_NAMES = [["Gövde", "Taban plakası", "Burç"], ["Mil", "Dişli", "Pul"], ["Kapak", "Flanş"]]
PARTS_PER_ASSEMBLY = [3, 3, 2]  # 10 mamul × (3 + 3 + 2) = 80 işlenmiş parça

# Bilerek konmuş durumlar (docs/11; situations.py denetler)
BOTTLENECK_RESOURCE = "M5-01"
BOTTLENECK_GROUP = "ISL5"  # darboğaz kaynağın grubu: tek üyeli, plan ve yük grup düzeyinde (K-180)
# Rotalar kaynağı değil grubunu gösterir: kaynak kodunun ön eki → grup
RESOURCE_GROUPS = {"T-": "TORNA", "M3-": "ISL3", "M5-": BOTTLENECK_GROUP, "G-": "TASLAMA", "A-": "MONTAJ", "Q-": "KALITE"}


def resource_group(resource_code: str) -> str:
    """Kaynağın tezgâh grubu; fason kaynak kendi kodundaki gruptadır."""
    return next((g for prefix, g in RESOURCE_GROUPS.items() if resource_code.startswith(prefix)), resource_code)
BOTTLENECK_PRODUCTS = ("MAM-001", "MAM-002", "MAM-003")
BOTTLENECK_HOURS = 3.0          # bu mamullerin gövde parçasının 5 eksende birim süresi
LIGHT_M5_HOURS = 0.3
LABOR_GROUP = "CG-MON"  # işçilik satırlarının grubu: montajcı yetkinliği (K-116, K-117)
LATE_MATERIAL, LATE_SUPPLIER, LATE_PRODUCT, LATE_ORDER = "HAM-012", "TED-04", "MAM-008", "SO-1027"
LATE_LEAD_DAYS = 56
LIMIT_SUPPLIER, LIMIT_MATERIAL, LIMIT_QTY = "TED-05", "SAT-003", 400
IMPOSSIBLE_ORDER, IMPOSSIBLE_PRODUCT = "SO-1040", "MAM-010"
MAINTENANCE_RESOURCE, LEAVE_WORKER, SICK_WORKER = "T-02", "W-007", "W-015"
NON_STOCKABLE = ("ALT-013", "SAT-030")   # stok tutulamaz (K-113): üretilen ve satın alınan; ikisinde de stok yok
ISOLATED_MATERIAL = "SAT-040"   # yalnız Material'da geçer (kirli hâlde tekrar eden anahtar, H4)
NO_ROUTE_PART = "PRC-033"       # kirli hâlde rotası çıkarılır (H1)
# Veri kalitesi durumları (6.5, K-174; docs/11 durum 6–9): generate'in sonunda eklenir, mevcut satırların Id'leri ve tohum sırası değişmez
DEEP_MATERIAL, DEEP_SUPPLIER = "HAM-022", "TED-02"       # 6: tedarik süresi ikisi de boş, MAM-002'nin üç seviye altında
NO_DEMAND_MATERIAL = "ALT-099"                            # 7: hiçbir talebin ağacında değil; ağacında bileşen miktarı 0
PAST_DUE_ORDER, DUE_TODAY_ORDER = "SO-1043", "SO-1044"    # 9: teslim tarihi dün / bugün, açık
CONFLICT_DAILY = 7.0                                      # CG-KAL günlük kapasitesi: CG-MON'dan (7,5) farklı; ikisine üye işçide çelişki (K-185)
FASON_NO_CAPACITY = "F-KAPLA"                             # fason grup ve kaynağı: çalışma düzeni yok (kritik değil: Normal uyarı)
NO_CAPACITY_RESOURCE = "T-05"                             # 9: kritik, günlük kapasitesi boş (K-117)
FORECAST_PRODUCT = "MAM-001"                              # tahmin: gelecek iki ay
REFERENCE_PRODUCT, REFERENCE_SOURCE = "MAM-011", "MAM-001"  # kendi versiyonu yok; MAM-001'in ağacı ve rotası izlenir

FIRST_NAMES = ["Ahmet", "Ayşe", "Mehmet", "Fatma", "Mustafa", "Zeynep", "Ali", "Elif", "Hasan", "Emine", "Hüseyin",
               "Hatice", "İbrahim", "Merve", "Murat", "Selin", "Emre", "Derya", "Burak", "Gamze", "Kemal", "Esra",
               "Serkan", "Tuğba", "Volkan"]
LAST_NAMES = ["Yılmaz", "Kaya", "Demir", "Şahin", "Çelik", "Yıldız", "Aydın", "Öztürk", "Arslan", "Doğan", "Kılıç",
              "Aslan", "Çetin", "Koç", "Kurt", "Özdemir", "Polat", "Erdoğan", "Güneş", "Aksoy"]


def monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def add_business_days(d: date, n: int) -> date:
    while n > 0:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d


@dataclass
class Dataset:
    seed: int
    generated_on: date
    start: date                                         # hafta 1 Pazartesi
    tables: dict[str, list[dict]] = field(default_factory=dict)   # core tablo → satırlar
    params: dict[str, list[dict]] = field(default_factory=dict)   # param tablo → satırlar
    lead_days: dict[int, int] = field(default_factory=dict)       # malzeme Id → üretim süresi; tabloda yok, senaryoların iç hesabı (K-12)

    @property
    def horizon_end(self) -> date:
        return self.start + timedelta(days=7 * HORIZON_WEEKS - 1)

    def day(self, week: int, weekday: int = 0) -> date:
        return self.start + timedelta(days=7 * (week - 1) + weekday)

    def week_of(self, d: date) -> int:
        return (d - self.start).days // 7 + 1

    def rows(self, table: str) -> list[dict]:
        return self.tables.get(table, [])

    def get(self, table: str, **match) -> dict:
        found = [r for r in self.rows(table) if all(r.get(k) == v for k, v in match.items())]
        if len(found) != 1:
            raise KeyError(f"{table} {match}: {len(found)} satır")
        return found[0]

    def by_id(self, table: str, id_: int) -> dict:
        return self._index(table)[id_]

    def code(self, table: str, id_: int | None) -> str | None:
        return None if id_ is None else self.by_id(table, id_)["Code"]

    def _index(self, table: str) -> dict:
        cache = self.__dict__.setdefault("_idx", {})
        if table not in cache:
            cache[table] = {r["Id"]: r for r in self.rows(table)}
        return cache[table]


class _Builder:
    def __init__(self, ds: Dataset):
        self.ds = ds
        self.t = defaultdict(list)

    def add(self, table: str, with_id: bool = True, **row) -> dict:
        rows = self.t[table]
        if with_id:
            row = {"Id": len(rows) + 1, **row}
        rows.append(row)
        return row

    def find(self, table: str, code: str) -> dict:
        for r in self.t[table]:
            if r.get("Code") == code:
                return r
        raise KeyError(f"{table} {code}")

    def id(self, table: str, code: str) -> int:
        return self.find(table, code)["Id"]


def generate(on: date | None = None, seed: int = SEED) -> Dataset:
    on = on or date.today()
    ds = Dataset(seed=seed, generated_on=on, start=monday(on))
    rng = random.Random(seed)
    b = _Builder(ds)
    _organisation(b, rng)
    _materials(b, rng)
    _structure(b, rng)
    _suppliers(b, rng)
    _orders(b, rng)
    _stock(b, rng)
    _work_orders(b, rng)
    _purchase_orders(b, rng)
    _keep_open_dates_current(b)
    _quality(b)
    _params(b)
    ds.tables = {k: v for k, v in b.t.items() if not k.startswith("param.")}
    ds.params = {k.split(".", 1)[1]: v for k, v in b.t.items() if k.startswith("param.")}
    _business_keys(ds)
    return ds


# --- Kuruluş: lokasyon, birim, takvim, vardiya, kaynak, çalışan ---

def _organisation(b: _Builder, rng: random.Random) -> None:
    ds = b.ds
    b.add("Location", Code=LOCATION_CODE, Name="Örnek Makina A.Ş. · Merkez fabrika", Type="PLANT",  # ERP ham tipi (K-143)
          IsFactory=True, IsDepot=True, IsSubcontractor=False, IsActive=True,
          Country="Türkiye", CountryCode="TR", City="Kocaeli")
    # Decimals: miktar ondalığı (K-88); ERP'den gelmez, Smartchain'de tutulur.
    for code, name, decimals in [("ADET", "Adet", 0), ("KG", "Kilogram", 3), ("M", "Metre", 2), ("SAAT", "Saat", 2)]:
        b.add("UnitOfMeasure", with_id=False, Code=code, Name=name, Decimals=decimals)

    def group(code, name, kind, flag, critical):
        """Kaynak grubu planlama birimidir (K-180): tip bayrağı, kritiklik, kapasite birimi ve fasoncu gruptadır."""
        flags = dict(IsEmployee=False, IsMachine=False, IsFurnace=False, IsMold=False, IsOther=False, IsSubcontractor=False)
        b.add("ResourceGroup", LocationId=1, Code=code, Name=name, Type=kind, **{**flags, flag: True}, IsActive=True, IsCritical=critical,
              CapacityUnit="SAAT", SubcontractorId=None)

    for code, name in [("TORNA", "CNC torna"), ("ISL3", "3 eksen işleme"), (BOTTLENECK_GROUP, "5 eksen işleme"),
                       ("TASLAMA", "Taşlama"), ("MONTAJ", "Montaj"), ("KALITE", "Kalite kontrol")]:
        group(code, name, "Makine grubu", "IsMachine", True)
    # İşçi grubu (yetkinlik grubu) IsEmployee bayraklı gruptur (K-180).
    for code, name in [("CG-CNC", "CNC operatörü"), (LABOR_GROUP, "Montajcı"), ("CG-KAL", "Kalite teknisyeni")]:
        group(code, name, "Yetkinlik", "IsEmployee", True)
    # Fason grupları: kaynağıyla aynı kodda tek üyeli grup (kaynağını grup olarak veren müşteri örneği); kritik değil
    for code, name in [("F-ISIL", "Fason ısıl işlem"), ("F-KAPLA", "Fason kaplama")]:
        group(code, name, "Fason", "IsSubcontractor", False)

    def resource(code, name, kind, daily, **extra):
        """Kaynak: kimlik ve ham tip (yalnız bilgi). Günlük kapasite kaynakta durmaz (K-185): çalışma düzenindedir (`_capacity`); `daily` oraya
        taşınan eski değerdir, belge olarak kalır."""
        return b.add("Resource", LocationId=1, Code=code, Name=name, ResourceType=kind, IsActive=True, **extra)

    def assign(resource_row, group_code):
        b.add("ResourceGroupMember", LocationId=1, ResourceGroupId=b.id("ResourceGroup", group_code), ResourceId=resource_row["Id"])

    machines = ([(f"T-0{i}", f"CNC torna {i}", "TORNA", 15.0) for i in range(1, 5)]
                + [(f"M3-0{i}", f"3 eksen işleme merkezi {i}", "ISL3", 15.0) for i in range(1, 4)]
                + [(BOTTLENECK_RESOURCE, "5 eksen işleme merkezi", BOTTLENECK_GROUP, 15.0)]
                + [(f"G-0{i}", f"Silindirik taşlama {i}", "TASLAMA", 15.0) for i in range(1, 3)]
                + [(f"A-0{i}", f"Montaj hattı {i}", "MONTAJ", 15.0) for i in range(1, 3)]
                + [("Q-01", "Kalite kontrol istasyonu", "KALITE", 7.5)])
    for code, name, group_code, daily in machines:
        assign(resource(code, name, "Makine", daily, ProductionLocation="Hol 1"), group_code)
    # Fason kaynak kendi grubundadır; grup tedarikçiye bağlanır (_suppliers'ta SubcontractorId yazılır).
    for code, name, lead in [("F-ISIL", "Fason ısıl işlem", 5), ("F-KAPLA", "Fason kaplama", 4)]:
        assign(resource(code, name, "Fason", 24.0), code)  # fason parametreleri (tedarik süresi) bu adımda yok (K-185)
    names = set()
    for i in range(1, 26):
        while True:
            name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
            if name not in names:
                names.add(name)
                break
        # İşçi yalnız işçi (yetkinlik) gruplarına üyedir: gruptaki kaynak sayısı kapasiteyi belirler, tezgâh grubunu şişirmemeli (K-180)
        if i <= 10:
            rng.choice(["TORNA", "ISL3", "ISL5"])  # eski "bağlı olduğu tezgâh grubu" seçimi: rastgele dizi değişmesin diye tüketilir
            comps = ["CG-CNC"] + (["CG-MON"] if i in (3, 8) else [])
        elif i <= 20:
            comps = ["CG-MON"]
        elif i <= 23:
            comps = ["CG-KAL"]
        else:
            comps = ["CG-MON", "CG-KAL"]
        w = resource(f"W-{i:03d}", name, "İşçi", 7.5)  # işçiler kaynaktır (K-117)
        for c in comps:
            assign(w, c)
    # Durum 5: izin (hafta 3, bütün hafta) ve rapor (hafta 1, Salı–Çarşamba); ayrıca ileride bir izin.
    for code, start, end, kind in [(LEAVE_WORKER, ds.day(3, 0), ds.day(3, 5), "İzin"),
                                   (SICK_WORKER, ds.day(1, 1), ds.day(1, 3), "Rapor"),
                                   ("W-021", ds.day(9, 3), ds.day(9, 5), "İzin")]:
        # Bitiş günü dahil (K-117); W-021 günde 4 saat kısmi devamsızlık.
        b.add("EmployeeAbsence", LocationId=1, ResourceId=b.id("Resource", code), AbsenceType=kind, StartDate=start,
              EndDate=end - timedelta(days=1), HoursPerDay=4.0 if code == "W-021" else None)

    _capacity(b)


def _capacity(b: _Builder) -> None:
    """Kapasite girişleri (K-185; Baz senaryoya yüklenir): çalışma düzeni, verimlilik, ek mesai limiti, bakım ve duruş, fabrika takvimi.

    Bilerek konmuş durumlar: grup seviyesinde düzen (çoğu grup) · kaynak seviyesinde düzen (TORNA'da grup kaydı yok, tezgâhların kendi kaydı
    var; Q-01 Cumartesi yarım gün) · geçici kayıt (G-02 hafta 9–10 yarı kapasite, T-04 hafta 12–13 yüksek kapasite: başlangıcı en ileri olan
    geçerlidir, bitince öncekine dönülür) · planlı bakım ve arıza (kaynak ve grup seviyesinde) · fabrika takvimi (yarım gün, tatil, toplu izin)
    · verimlilik (grupta %85, kaynakta geçici %110) · ek mesai limiti (işçi grupları) · iki grupta çelişen değer (CG-KAL günlük 7,0; CG-MON 7,5:
    ikisine de üye işçiler) · çalışma düzeni olmayan kaynaklar (T-05: kritik TORNA'da, kendi kaydı yok; F-KAPLA: fason, grubunda kayıt yok)."""
    ds = b.ds
    since = ds.start - timedelta(days=HISTORY_DAYS)

    def owner(group=None, resource=None) -> dict:
        return {"ResourceGroupId": b.id("ResourceGroup", group) if group else None, "ResourceId": b.id("Resource", resource) if resource else None}

    def pattern(daily, start=since, end=None, sat=0.0, **who):
        b.add("param.WorkPattern", ScenarioDefinitionId=1, **owner(**who), ValidFrom=start, ValidTo=end, DailyCapacity=daily,
              DayMon=1.0, DayTue=1.0, DayWed=1.0, DayThu=1.0, DayFri=1.0, DaySat=sat, DaySun=0.0, IsValid=True)

    for code, daily in [("ISL3", 15.0), (BOTTLENECK_GROUP, 15.0), ("TASLAMA", 15.0), ("MONTAJ", 15.0), ("KALITE", 7.5),
                        ("CG-CNC", 7.5), (LABOR_GROUP, 7.5), ("CG-KAL", CONFLICT_DAILY), ("F-ISIL", 24.0)]:
        pattern(daily, group=code)
    for i in range(1, 5):                                       # TORNA: grup kaydı yok, tezgâhların kendi kaydı
        pattern(15.0, resource=f"T-0{i}")
    pattern(7.5, resource="Q-01", sat=0.5)                      # kaynak seviyesinde farklı günler: Cumartesi yarım
    pattern(7.5, start=ds.day(9), end=ds.day(10, 6), resource="G-02")     # geçici: iki hafta yarı kapasite
    pattern(22.5, start=ds.day(12), end=ds.day(13, 6), resource="T-04")   # geçici: iki hafta yüksek kapasite (kendi kaydının üstüne)

    b.add("param.ResourceEfficiency", ScenarioDefinitionId=1, **owner(group="TASLAMA"), ValidFrom=since, ValidTo=None, EfficiencyPct=85.0, IsValid=True)
    b.add("param.ResourceEfficiency", ScenarioDefinitionId=1, **owner(resource="A-01"), ValidFrom=ds.day(4), ValidTo=ds.day(8, 6), EfficiencyPct=110.0,
          IsValid=True)
    for code, limit in [(LABOR_GROUP, 2.0), ("CG-CNC", 1.5)]:
        b.add("param.OvertimeLimit", ScenarioDefinitionId=1, **owner(group=code), ValidFrom=since, ValidTo=None, DailyLimit=limit, IsValid=True)
    # Model kısıtları (docs/11, K-189): iki kritik grupta hedef doluluk, birinde kısıtsız kapasite çarpanı; kritik olmayan grupta değer yok
    for code, factor, target in MODEL_CONSTRAINTS:
        b.add("param.ResourceGroupConstraint", ScenarioDefinitionId=1, ResourceGroupId=b.id("ResourceGroup", code), UnconstrainedCapacityFactor=factor,
              TargetUtilizationPct=target, IsValid=True)

    def downtime(kind, reason, start, end, **who):
        b.add("param.ResourceDowntime", ScenarioDefinitionId=1, **owner(**who), StartDate=start, EndDate=end, DowntimeType=kind, Reason=reason, IsValid=True)

    downtime("Planlı bakım", "Planlı bakım: iş mili rulmanları", ds.day(2, 1), ds.day(2, 2), resource=MAINTENANCE_RESOURCE)   # durum 5: hafta 2 Salı–Çarşamba
    downtime("Planlı bakım", "Yıllık bakım", ds.day(8, 4), ds.day(8, 4), resource="G-01")
    downtime("Arıza", "Mil arızası", ds.day(5, 2), ds.day(5, 3), resource="M3-02")
    downtime("Planlı bakım", "Ölçüm cihazlarının kalibrasyonu", ds.day(11, 0), ds.day(11, 0), group="KALITE")

    eve = date(ds.start.year if ds.start <= date(ds.start.year, 12, 31) else ds.start.year + 1, 12, 31)
    for name, start, end, value in [("Yılbaşı arifesi", eve, eve, 0.5), ("Yılbaşı", eve + timedelta(days=1), eve + timedelta(days=1), 0.0),
                                    ("Yıllık toplu izin", ds.day(16, 0), ds.day(16, 4), 0.0)]:
        b.add("param.FactoryCalendar", ScenarioDefinitionId=1, StartDate=start, EndDate=end, Name=name, DayValue=value, IsValid=True)

# --- Malzemeler ---

MATERIAL_TYPE = {"Nihai ürün": "MAM", "Yarı mamul": "YRM", "Hammadde": "HAM"}
# Satın alınan malzeme grubu → (marka, kutu içi, palet içi); hayali değerler (K-113).
PURCHASED_PACK = {"Rulman": ("Ayaz", 10, 500), "Bağlantı": ("Demir", 100, 5000)}

# Ek alan örneği (K-59, K-88; tablo bileşeni denemesi 1.3): Material.AdditionalText1 "Malzeme sınıfı".
MATERIAL_CLASS = {"Nihai ürün": "A", "Yarı mamul": "B", "Hammadde": "C"}
FIELD_DEFINITIONS = [dict(TableName="Material", FieldName="AdditionalText1", FieldClass="Ana veri",
                          EditableInWorkspace=False, Label="Malzeme sınıfı")]

def _materials(b: _Builder, rng: random.Random) -> None:
    def mat(code, name, level, group, uom, producible, lead=None, **extra):
        row = dict(LocationId=1, Code=code, Name=name, BaseUom=uom, MaterialGroup=group,
                   MaterialLevel=level, MaterialType=MATERIAL_TYPE[level], PlannerCode="PLN-1" if producible else "PLN-2",
                   MRPGroup="URETIM" if producible else "SATINALMA", IsActive=True, IsCritical=False,
                   IsPurchasable=not producible, IsProducible=producible, IsSellable=level == "Nihai ürün",
                   IsSubcontractable=False, DefaultSupplyType="Üretim" if producible else "Satın alma",
                   IsCustomerSupplied=False, IsCustomTracked=False, IsPhantom=False, IsNonStockable=code in NON_STOCKABLE,
                   StockCoverageDays=lead if producible else None,
                   GoodsReceiptDays=None if producible else 1,
                   LotSizePolicy="Lot-for-lot" if producible else None,
                   AdditionalText1=MATERIAL_CLASS[level])
        added = b.add("Material", **{**row, **extra})
        if producible and lead:
            b.ds.lead_days[added["Id"]] = lead
        return added

    for code, name, _ in FINISHED:
        lead = 3
        mat(code, name, "Nihai ürün", "Mamul", "ADET", True, lead,
            IsCustomTracked=code == "MAM-006")
    n_alt = n_prc = 0
    for f, (fcode, _, short) in enumerate(FINISHED):
        for a, aname in enumerate(ASSEMBLIES):
            n_alt += 1
            mat(f"ALT-{n_alt:03d}", f"{aname} · {short}", "Yarı mamul", "Alt montaj", "ADET", True,
                3 if fcode == IMPOSSIBLE_PRODUCT else 2)
            for p in range(PARTS_PER_ASSEMBLY[a]):
                n_prc += 1
                base = PART_NAMES[a][p]
                if fcode == LATE_PRODUCT and a == 2 and p == 1:
                    base = "Dövme flanşlı kapak"
                mat(f"PRC-{n_prc:03d}", f"{base} · {short}", "Yarı mamul", "İşlenmiş parça", "ADET", True,
                    4 if fcode == IMPOSSIBLE_PRODUCT else rng.choice([2, 3, 3, 4]))

    grades = ["C45", "42CrMo4", "304", "S355", "16MnCr5"]
    n = 0
    for i in range(20):  # çubuk
        n += 1
        if n == 12:
            mat(LATE_MATERIAL, "Dövme flanş Ø200 S355", "Hammadde", "Dövme", "ADET", False, IsCritical=True)
            n += 1
        mat(f"HAM-{n:03d}", f"Çelik çubuk Ø{30 + 5 * (i % 10)} {grades[i % 5]}", "Hammadde", "Çubuk", "KG", False)
    while n < 40:  # levha
        n += 1
        mat(f"HAM-{n:03d}", f"Sac levha {[6, 8, 10, 12, 15, 20][n % 6]} mm {grades[n % 5]}", "Hammadde", "Levha",
            "KG", False)

    purchased = ([("Rulman 6204-2RS", "Rulman"), ("Rulman 6206-2RS", "Rulman"), ("Rulman 6205-2RS", "Rulman"),
                  ("Rulman 6305-ZZ", "Rulman"), ("Rulman 32008 konik", "Rulman"), ("Rulman 51105 eksenel", "Rulman")]
                 + [(f"Cıvata M{m}×{l} 8.8", "Bağlantı") for m, l in [(8, 25), (10, 30), (12, 40), (16, 50)]]
                 + [(f"Somun M{m} 8", "Bağlantı") for m in (8, 10, 12, 16)]
                 + [(f"Pim Ø{d}×{l}", "Bağlantı") for d, l in [(6, 30), (8, 40)]]
                 + [(f"O-ring {d}×3", "Conta") for d in (40, 60, 80, 100)]
                 + [(f"Yağ keçesi {d}×{d + 20}×8", "Conta") for d in (30, 40, 50)]
                 + [(f"Düz conta DN{d}", "Conta") for d in (50, 80, 100)]
                 + [(f"Segman Ø{d}", "Bağlantı") for d in (25, 30, 35, 40)]
                 + [("Kama 8×7×40", "Bağlantı"), ("Gres nipeli M8", "Bağlantı"), ("Havalandırma tapası", "Aksesuar"),
                    ("Yağ seviye göstergesi", "Aksesuar"), ("Etiket plakası", "Aksesuar"), ("Kaldırma halkası M12", "Aksesuar"),
                    ("Rondela M10", "Bağlantı"), ("Rondela M12", "Bağlantı"), ("Yaylı pim Ø5×30", "Bağlantı")])
    assert len(purchased) == 39
    for i, (name, group) in enumerate(purchased[:39], 1):
        brand, box, pallet = PURCHASED_PACK.get(group, (None, None, None))
        mat(f"SAT-{i:03d}", name, "Hammadde", group, "ADET", False,
            SafetyStock=20 if group == "Rulman" else None, MinLot=50 if group == "Bağlantı" else None,
            Brand=brand, QtyPerBox=box, QtyPerPallet=pallet, IsCritical=group == "Rulman")
    # H4 için yalnız Material'da geçen malzeme: müşteri temin, satın alınmaz, hiçbir yerde kullanılmaz.
    m = mat(ISOLATED_MATERIAL, "Müşteri temin etiket seti", "Hammadde", "Aksesuar", "ADET", False)
    m.update(IsPurchasable=False, IsCustomerSupplied=True, GoodsReceiptDays=None)

    for code, factor in [("HAM-001", 5.55), ("HAM-002", 7.55), ("HAM-003", 9.86), ("HAM-004", 12.48)]:
        b.add("UomConversion", MaterialId=b.id("Material", code), FromUom="M", FromUomName="Metre", ToUom="KG", ToUomName="Kilogram", Factor=factor)


# --- Ürün ağacı ve rota ---

def _structure(b: _Builder, rng: random.Random) -> None:
    grp = lambda resource: b.id("ResourceGroup", resource_group(resource))  # noqa: E731  # rota kaynağın grubunu gösterir (K-180)
    sat_pool = [f"SAT-{i:03d}" for i in range(1, 40) if i != 3]
    ham_pool = [f"HAM-{i:03d}" for i in range(1, 41) if f"HAM-{i:03d}" != LATE_MATERIAL]
    light_m5 = {"PRC-026", "PRC-042", "PRC-050", "PRC-063", "PRC-071"}  # 5 eksende kısa işlenen parçalar

    def version(code):
        return b.add("ProductionVersion", LocationId=1, MaterialId=b.id("Material", code), Code="V1", Name="Standart üretim",
                     Type="Standart", IsActive=True, Priority=1, BaseQuantity=1.0, BOMCode=f"B-{code}", RouteCode=f"R-{code}",
                     ValidFrom=b.ds.start - timedelta(days=365))

    def bom(pv, comp, qty, op=None):
        b.add("BOM", LocationId=1, MaterialId=pv["MaterialId"], Code=pv["BOMCode"], ComponentMaterialId=b.id("Material", comp),
              OperationNo=op, SequenceNo=1, Quantity=qty, ScrapRatio=None, IsPhantom=False, IsLotBasedUsage=False)

    def op(code, no, name, resource, cons, **extra):
        if resource.startswith("F-"):  # fason operasyonu olan malzeme fasona verilebilir
            next(m for m in b.t["Material"] if m["Code"] == code)["IsSubcontractable"] = True
        return b.add("Routing", LocationId=1, RouteCode=f"R-{code}", OperationNo=no, SequenceNo=1, OperationName=name, ResourceGroupId=grp(resource),
                     ResourceRole="Primary", Consumption=round(cons, 3), ResourceNumber=1,
                     IsSubcontracted=resource.startswith("F-"), IsActive=True, IsLotBasedUsage=False, **extra)

    def crew(row, people=2):
        """İşçilik ayrı satır (K-116, K-180): işçi grubu, Secondary, kişi sayısı, süre ana satırla aynı."""
        b.add("Routing", LocationId=1, RouteCode=row["RouteCode"], OperationNo=row["OperationNo"], SequenceNo=2, OperationName=row["OperationName"],
              ResourceGroupId=b.id("ResourceGroup", LABOR_GROUP), ResourceRole="Secondary", Consumption=row["Consumption"],
              ResourceNumber=people, IsSubcontracted=False, IsActive=True, IsLotBasedUsage=False)

    n_alt = n_prc = 0
    for fcode, _, _ in FINISHED:
        pv_f = version(fcode)
        crew(op(fcode, 10, "Son montaj", rng.choice(["A-01", "A-02"]), rng.uniform(1.0, 2.0)))
        op(fcode, 20, "Son kontrol", "Q-01", 0.3)
        for sat in rng.sample(sat_pool, rng.choice([2, 3])):
            bom(pv_f, sat, rng.choice([2, 4, 6, 8]), 10)
        for a in range(3):
            n_alt += 1
            acode = f"ALT-{n_alt:03d}"
            bom(pv_f, acode, 1, 10)
            pv_a = version(acode)
            crew(op(acode, 10, "Alt montaj", rng.choice(["A-01", "A-02"]), rng.uniform(0.5, 1.2)))
            extra_sat = rng.sample(sat_pool, rng.choice([1, 2]))
            if a == 1:
                extra_sat = ["SAT-003"] + extra_sat[:1]  # rulman 6205: her mil grubunda (durum 3)
            if acode == "ALT-012" and "SAT-010" not in extra_sat:
                extra_sat.append("SAT-010")  # kirli hâlde negatif miktar (H3) bu satıra konur
            for sat in extra_sat:
                bom(pv_a, sat, 2 if sat == "SAT-003" else rng.choice([2, 4, 6]), 10)
            for p in range(PARTS_PER_ASSEMBLY[a]):
                n_prc += 1
                pcode = f"PRC-{n_prc:03d}"
                bom(pv_a, pcode, 1, 10)
                pv_p = version(pcode)
                if fcode == LATE_PRODUCT and a == 2 and p == 1:
                    bom(pv_p, LATE_MATERIAL, 1)  # durum 2: uzun temin süreli dövme flanş
                    op(pcode, 10, "İşleme", "M3-01", rng.uniform(0.6, 1.0))
                    continue
                bom(pv_p, rng.choice(ham_pool), round(rng.uniform(1.5, 12.0), 1))
                if fcode in BOTTLENECK_PRODUCTS and a == 0 and p == 0:
                    op(pcode, 10, "5 eksen işleme", BOTTLENECK_RESOURCE, BOTTLENECK_HOURS)  # durum 1
                elif pcode in light_m5:
                    op(pcode, 10, "5 eksen işleme", BOTTLENECK_RESOURCE, LIGHT_M5_HOURS)
                else:
                    machine = rng.choice(["T-01", "T-02", "T-03", "T-04", "M3-01", "M3-02", "M3-03"])
                    op(pcode, 10, "Tornalama" if machine.startswith("T") else "Frezeleme", machine,
                       rng.uniform(0.2, 0.8))
                r = rng.random()
                if r < 0.3:
                    op(pcode, 20, "Taşlama", rng.choice(["G-01", "G-02"]), rng.uniform(0.1, 0.3))
                if r > 0.85:
                    op(pcode, 30, "Isıl işlem (fason)", "F-ISIL", 1.0)
                elif r > 0.75:
                    op(pcode, 30, "Kaplama (fason)", "F-KAPLA", 1.0)


# --- Tedarikçi ve müşteri ---

def _suppliers(b: _Builder, rng: random.Random) -> None:
    for code, name, sub in [("TED-01", "Anadolu Çubuk Ticaret", False), ("TED-02", "Marmara Levha Sanayi", False),
                            ("TED-03", "Bağlantı Elemanları Ltd.", False), (LATE_SUPPLIER, "Ege Dövme Sanayi", False),
                            (LIMIT_SUPPLIER, "Rulman Dağıtım A.Ş.", False), ("TED-06", "Sızdırmazlık Elemanları", False),
                            ("TED-07", "Isıl İşlem Hizmetleri", True), ("TED-08", "Yüzey Kaplama Atölyesi", True)]:
        b.add("Supplier", Code=code, Name=name, IsSubcontractor=sub, IsActive=True, Country="Türkiye", City="Kocaeli" if sub else "İstanbul")
    b.find("ResourceGroup", "F-ISIL")["SubcontractorId"] = b.id("Supplier", "TED-07")  # fasoncu kaynak grubundadır (K-180)
    b.find("ResourceGroup", "F-KAPLA")["SubcontractorId"] = b.id("Supplier", "TED-08")

    by_group = {"Çubuk": "TED-01", "Levha": "TED-02", "Bağlantı": "TED-03", "Rulman": LIMIT_SUPPLIER,
                "Conta": "TED-06", "Aksesuar": "TED-03", "Dövme": LATE_SUPPLIER}
    for m in b.t["Material"]:
        if not m["IsPurchasable"]:
            continue
        lead = LATE_LEAD_DAYS if m["Code"] == LATE_MATERIAL else rng.choice([7, 10, 14, 14, 21])
        first = b.add("MaterialSupplier", LocationId=1, MaterialId=m["Id"], SupplierId=b.id("Supplier", by_group[m["MaterialGroup"]]), IsActive=True,
              Priority=1, QuotaRatio=None, FixedLeadTimeDays=lead, VariableLeadTimeDays=None, LeadTimeBasis="Takvim günü",
              MinimumOrderQuantity=m.get("MinLot"), OrderLotSize=None, MaximumOrderQuantity=None)
        if m["MaterialGroup"] in ("Çubuk", "Conta") and rng.random() < 0.3:  # ikinci tedarikçi
            b.add("MaterialSupplier", LocationId=1, MaterialId=m["Id"], IsActive=True,
                  SupplierId=b.id("Supplier", "TED-02" if m["MaterialGroup"] == "Çubuk" else "TED-03"),
                  Priority=2, QuotaRatio=0.30, FixedLeadTimeDays=lead + 7, LeadTimeBasis="Takvim günü")
            first["QuotaRatio"] = 0.70  # kota toplamı 1 (MS.QUOTA_SUM, K-137)

    for code, name, prio, partial in [("MUS-A", "Akdeniz Pompa Sistemleri", 1, False),
                                      ("MUS-B", "Kuzey Enerji Ekipmanları", 2, True),
                                      ("MUS-C", "Orta Anadolu Makine", 3, True)]:
        b.add("Customer", Code=code, Name=name, Priority=prio, AllowPartialDelivery=partial, CustomerGroup="Yurt içi", IsActive=True,
              Country="Türkiye", Region="Marmara", City="İstanbul", IsCustomTracked=code == "MUS-A")
    b.add("ProjectGroup", Code="PG-01", Name="Enerji santrali projeleri", TrackingRule="Ortaktan beslenir", Priority=1, IsActive=True)
    b.add("Project", Code="PRJ-01", Name="Santral A pompa paketi", ProjectGroupId=1,
          TrackingRule="Ortaktan beslenir", Priority=1, IsActive=True)
    b.add("Project", Code="PRJ-02", Name="Arıtma tesisi redüktörleri", ProjectGroupId=1,
          TrackingRule="Tam izolasyon", Priority=2, IsActive=True)


# --- Satış siparişleri ---

def _orders(b: _Builder, rng: random.Random) -> None:
    ds = b.ds
    # (sipariş, mamul, adet, hafta, müşteri, proje) — bilerek konmuş durumlar elle; geri kalanı tohumla.
    fixed = {
        "SO-1001": ("MAM-002", 14, 1, "MUS-A", None), "SO-1003": ("MAM-001", 15, 2, "MUS-A", None),
        "SO-1011": ("MAM-001", 18, 3, "MUS-A", None), "SO-1012": ("MAM-002", 17, 3, "MUS-A", None),
        "SO-1013": ("MAM-003", 18, 4, "MUS-A", None), "SO-1014": ("MAM-001", 17, 4, "MUS-B", None),
        "SO-1015": ("MAM-002", 18, 5, "MUS-A", None), "SO-1016": ("MAM-003", 17, 5, "MUS-B", None),
        "SO-1020": ("MAM-006", 6, 6, "MUS-B", "PRJ-01"), "SO-1021": ("MAM-006", 4, 9, "MUS-B", "PRJ-01"),
        LATE_ORDER: (LATE_PRODUCT, 8, 5, "MUS-C", None), "SO-1030": ("MAM-005", 10, 7, "MUS-B", "PRJ-02"),
        "SO-1033": ("MAM-001", 10, 8, "MUS-C", None), "SO-1036": ("MAM-002", 12, 11, "MUS-A", None),
    }
    fillers = ["MAM-004", "MAM-005", "MAM-006", "MAM-007", "MAM-009"]
    for n in range(1, 41):
        no = f"SO-{1000 + n}"
        if no == IMPOSSIBLE_ORDER:  # durum 4: termin üretim günü + 2 iş günü
            fg, qty, due, cust, prj = IMPOSSIBLE_PRODUCT, 20, add_business_days(ds.generated_on, 2), "MUS-C", None
        elif no in fixed:
            fg, qty, week, cust, prj = fixed[no]
            due = ds.day(week, 4)
        else:
            fg, qty = rng.choice(fillers), rng.choice([5, 8, 10, 12, 15, 20, 25])
            due, cust, prj = ds.day(rng.randint(1, HORIZON_WEEKS), 4), rng.choice(["MUS-A", "MUS-B", "MUS-C"]), None
        b.add("SalesOrderLine", LocationId=1, OrderNo=no, LineNo=1, LineItemNo=0, Type="Kesin", IsQuote=False,
              CustomerId=b.id("Customer", cust), MaterialId=b.id("Material", fg),
              ProjectId=b.id("Project", prj) if prj else None, OpenQuantity=float(qty), OrderedQuantity=float(qty),
              DeliveredQuantity=0.0, Uom=None, IsActive=True, IsOnHold=False, IsCustomTracked=bool(prj), RequestedDate=due,
              ConfirmedDate=due if rng.random() < 0.6 else None, Priority=None, AllowPartialDelivery=None,
              Status="Açık")
    for no, fg, qty, week in [("SO-1041", "MAM-004", 30, 9), ("SO-1042", "MAM-007", 15, 12)]:  # teklif (K-60)
        b.add("SalesOrderLine", LocationId=1, OrderNo=no, LineNo=1, LineItemNo=0, Type="Teklif", IsQuote=True,
              CustomerId=b.id("Customer", "MUS-B"), MaterialId=b.id("Material", fg), ProjectId=None,
              OpenQuantity=float(qty), OrderedQuantity=float(qty), DeliveredQuantity=0.0, Uom=None, IsActive=True, IsOnHold=False,
              IsCustomTracked=False, RequestedDate=ds.day(week, 4), ConfirmedDate=None, Status="Açık")


# --- Stok ---

def _stock_flags(status: str, tracked: bool = False) -> dict:
    """Sahada bayrakları veri kuralı doldurur (K-121); burada ham durumla uyumlu yazılır."""
    return {"IsAvailable": status == "Serbest", "IsInQuality": status == "Kalitede", "IsBlocked": status == "Bloke",
            "IsActive": True, "IsCustomTracked": tracked}


def _stock(b: _Builder, rng: random.Random) -> None:
    ds = b.ds
    for m in b.t["Material"]:
        code = m["Code"]
        if not m["IsPurchasable"] or code == LATE_MATERIAL:
            continue
        if code == LIMIT_MATERIAL:
            qty = 50.0
        elif m["MaterialGroup"] in ("Çubuk", "Levha"):
            qty = float(rng.choice([0, 80, 150, 300, 600]))
        else:
            qty = float(rng.choice([0, 40, 100, 250, 500]))
        if qty:
            b.add("Stock", LocationId=1, MaterialId=m["Id"], Warehouse="ANA", LotNo=None, Status="Serbest",
                  ProjectId=None, Quantity=qty, **_stock_flags("Serbest"))
    mid = lambda c: b.id("Material", c)  # noqa: E731
    b.add("Stock", LocationId=1, MaterialId=mid("HAM-005"), Warehouse="ANA", LotNo="L-2410-07", Status="Kalitede",
          ProjectId=None, Quantity=200.0, QualityEntryDate=ds.generated_on - timedelta(days=4),
          ExpectedAcceptanceDate=ds.generated_on + timedelta(days=3), **_stock_flags("Kalitede"))  # K-9
    b.add("Stock", LocationId=1, MaterialId=mid("SAT-015"), Warehouse="ANA", LotNo="L-2409-21", Status="Bloke",
          ProjectId=None, Quantity=60.0, **_stock_flags("Bloke"))
    b.add("Stock", LocationId=1, MaterialId=mid("MAM-004"), Warehouse="MAMUL", LotNo=None, Status="Serbest",
          ProjectId=None, Quantity=5.0, **_stock_flags("Serbest"))
    b.add("Stock", LocationId=1, MaterialId=mid("MAM-006"), Warehouse="MAMUL", LotNo=None, Status="Serbest",
          ProjectId=b.id("Project", "PRJ-01"), Quantity=3.0, **_stock_flags("Serbest", tracked=True))
    # Devreye almada açık, ERP'de doğrudan yapılmış ödünç (K-119).
    b.add("BorrowPayback", LocationId=1, MaterialId=mid("MAM-006"), LendingProjectId=b.id("Project", "PRJ-01"),
          BorrowingProjectId=b.id("Project", "PRJ-02"), BorrowedQuantity=2.0, PaidBackQuantity=0.0,
          BorrowDate=ds.start - timedelta(days=14), PaybackDueDate=ds.day(3, 0))


# --- İş emirleri ---

def _work_orders(b: _Builder, rng: random.Random) -> None:
    ds = b.ds
    so_mam004 = next(s for s in b.t["SalesOrderLine"] if s["MaterialId"] == b.id("Material", "MAM-004"))
    plan = [  # (iş emri, malzeme, adet, başladı mı, bitiş haftası)
        ("WO-5001", "MAM-004", 10, False, 2), ("WO-5002", "ALT-010", 10, True, 1), ("WO-5003", "PRC-025", 10, True, 1),
        ("WO-5004", "PRC-004", 20, True, 1), ("WO-5005", "PRC-012", 15, False, 2), ("WO-5006", "ALT-016", 12, False, 3),
        ("WO-5007", "PRC-041", 12, True, 2), ("WO-5008", "PRC-055", 25, False, 3), ("WO-5009", "ALT-019", 8, True, 2),
        ("WO-5010", "PRC-060", 30, False, 4), ("WO-5011", "PRC-068", 10, True, 1), ("WO-5012", "MAM-009", 6, False, 4),
    ]
    pv_by_mat = {pv["MaterialId"]: pv for pv in b.t["ProductionVersion"]}
    for no, code, qty, started, week in plan:
        m = b.find("Material", code)
        pv = pv_by_mat[m["Id"]]
        open_qty = float(qty // 2) if started else float(qty)
        wo = b.add("WorkOrder", LocationId=1, WorkOrderNo=no, MaterialId=m["Id"], ProductionVersionId=pv["Id"], ProductionOrderType="Üretim",
                   Status="Başladı" if started else "Yayınlandı", Priority=None, OrderedQuantity=float(qty), OpenQuantity=open_qty,
                   CompletedQuantity=float(qty) - open_qty, ScrapQuantity=0.0, Uom=None,
                   StartDate=ds.start - timedelta(days=rng.choice([5, 8, 12])) if started else ds.day(week, 0),
                   DueDate=ds.day(week, 4), ProjectId=None, CustomerId=so_mam004["CustomerId"] if no == "WO-5001" else None,
                   SalesOrderLineId=so_mam004["Id"] if no == "WO-5001" else None,
                   ParentWorkOrderId=None,
                   LastActivityDate=ds.generated_on - timedelta(days=1) if started else None,
                   IsFixed=False, IsReleased=True, IsStarted=started, IsProduction=True, IsSubcontract=False, IsRework=False,  # K-121
                   IsOnHold=False, IsCustomTracked=False)
        for line in (r for r in b.t["BOM"] if r["MaterialId"] == m["Id"] and r["Code"] == pv["BOMCode"]):
            required = round(line["Quantity"] * qty, 4)
            issued = required if started else 0.0
            b.add("WorkOrderComponent", LocationId=1, WorkOrderId=wo["Id"], MaterialId=line["ComponentMaterialId"],
                  OperationNo=line["OperationNo"], SequenceNo=line["SequenceNo"], RequiredQuantity=required, IssuedQuantity=issued,
                  RemainingQuantity=round(required - issued, 4), UnitUsage=line["Quantity"], Uom=None, ScrapRatio=line["ScrapRatio"],
                  IsLotBasedUsage=line["IsLotBasedUsage"], IsPhantom=line["IsPhantom"])
        for i, r in enumerate(x for x in b.t["Routing"] if x["RouteCode"] == pv["RouteCode"] and x["ResourceRole"] == "Primary"):
            planned = round(r["Consumption"] * qty, 4)
            done = round(planned / 2, 4) if started and i == 0 else 0.0
            b.add("WorkOrderOperation", LocationId=1, WorkOrderId=wo["Id"], OperationNo=r["OperationNo"], SequenceNo=r["SequenceNo"],
                  OperationName=r["OperationName"], ResourceGroupId=r["ResourceGroupId"],
                  ResourceRole=r["ResourceRole"], ResourceNumber=r["ResourceNumber"], PlannedConsumption=planned, ConfirmedConsumption=done,
                  RemainingConsumption=round(planned - done, 4), Status="Açık", IsCompleted=False, IsLotBasedUsage=r["IsLotBasedUsage"],
                  IsSubcontracted=r["IsSubcontracted"], IsActive=r["IsActive"], ProductionLocation=r.get("ProductionLocation"),
                  TransferQuantity=r.get("TransferQuantity"), WaitingTimeHours=r.get("WaitingTimeHours"), TransferTimeHours=r.get("TransferTimeHours"))
            if done:
                b.add("ProductionConfirmation", LocationId=1, ConfirmationNo=f"T-{no}", WorkOrderId=wo["Id"], MaterialId=m["Id"],  # K-125
                      ConfirmedQuantity=float(qty - open_qty), StartDate=ds.start - timedelta(days=3), EndDate=ds.start - timedelta(days=3))
    # Alt montaj iş emri, mamul iş emrinin alt kırılımı.
    parent = next(w for w in b.t["WorkOrder"] if w["WorkOrderNo"] == "WO-5001")
    child = next(w for w in b.t["WorkOrder"] if w["WorkOrderNo"] == "WO-5002")
    child["ParentWorkOrderId"] = parent["Id"]


# --- Satın alma ve fason siparişleri ---

def _purchase_orders(b: _Builder, rng: random.Random) -> None:
    ds = b.ds
    supplier_of = {}
    for ms in b.t["MaterialSupplier"]:
        if ms["Priority"] == 1:
            supplier_of[ms["MaterialId"]] = ms["SupplierId"]
    candidates = [m for m in b.t["Material"] if m["IsPurchasable"]
                  and m["Code"] not in (LATE_MATERIAL, LIMIT_MATERIAL)]
    n = 2000

    def po(material_id, qty, req, conf, supplier_id, kind="Satın alma", wo=None, no=None):
        nonlocal n
        n += 1
        b.add("PurchaseOrderLine", LocationId=1, PurchaseOrderNo=no or f"PO-{n}", LineNo=1, OrderType=kind,
              SupplierId=supplier_id, MaterialId=material_id, OpenQuantity=float(qty), OrderedQuantity=float(qty), ReceivedQuantity=0.0,
              Uom=None, RequestedDate=req, ConfirmedDate=conf, ProjectId=None, CustomerId=None, SalesOrderLineId=None, WorkOrderId=wo, Status="Açık",
              IsPurchaseRequest=kind == "Satın alma talebi", IsPurchase=kind == "Satın alma", IsSubcontract=kind == "Fason",  # K-121
              IsActive=True, IsCustomTracked=False)

    earliest = add_business_days(ds.generated_on, 1)
    for m in rng.sample(candidates, 20):
        # en erken üretim gününden sonraki ilk iş günü: hafta 1'in geçmiş günü beklenmeyen PO.PAST_DUE vermesin (docs/11)
        req = max(ds.day(rng.randint(1, 6), rng.randint(0, 4)), earliest)
        po(m["Id"], rng.choice([50, 100, 200, 400]), req, req if rng.random() < 0.7 else None, supplier_of[m["Id"]])
    # Durum 3: limit ayında teyitli siparişler limiti dolduruyor.
    month_start, month_end = limit_month(ds)
    sat = b.id("Material", LIMIT_MATERIAL)
    sup = b.id("Supplier", LIMIT_SUPPLIER)
    first = max(month_start + timedelta(days=3), ds.generated_on + timedelta(days=1))
    second = max(month_start + timedelta(days=14), first)
    po(sat, 250, first, first, sup, no="PO-2041")
    po(sat, LIMIT_QTY - 250, second, second, sup, no="PO-2042")
    n = 2049
    po(b.id("Material", "SAT-021"), 200, ds.day(4, 2), None, b.id("Supplier", "TED-06"), kind="Satın alma talebi")
    fason_part = next(r for r in b.t["Routing"] if r["ResourceGroupId"] == b.id("ResourceGroup", "F-ISIL"))["RouteCode"][2:]
    po(b.id("Material", fason_part), 40, ds.day(2, 3), ds.day(2, 3), b.id("Supplier", "TED-07"), kind="Fason", wo=_subcon_work_order(b, "F-ISIL"))
    kaplama = next(r for r in b.t["Routing"] if r["ResourceGroupId"] == b.id("ResourceGroup", "F-KAPLA"))["RouteCode"][2:]
    po(b.id("Material", kaplama), 25, ds.day(3, 1), None, b.id("Supplier", "TED-08"), kind="Fason", wo=_subcon_work_order(b, "F-KAPLA"))
    n = 2059
    po(b.id("Material", "SAT-020"), 300, ds.day(2, 1), ds.day(2, 1), supplier_of[b.id("Material", "SAT-020")])  # PO-2060 (H3)


def _copy(b: _Builder, table: str, row: dict, **values) -> dict:
    """Var olan satırın kopyası (yeni Id ile)."""
    data = {k: v for k, v in row.items() if k not in ("Id", "BusinessKey")}
    return b.add(table, **{**data, **values})


def _first_of_month(d: date, months_ahead: int) -> date:
    m = d.month - 1 + months_ahead
    return date(d.year + m // 12, m % 12 + 1, 1)


def _keep_open_dates_current(b: _Builder) -> None:
    """Üretim günü haftanın sonuna gelince (Cumartesi, Pazar) hafta 1'in geçmiş günü beklenmeyen "tarihi geçmiş" uyarısı vermesin (docs/11): açık
    siparişin ve iş emrinin hafta 1'de üretim gününden önceye düşen tarihi üretim gününe çekilir. Bilerek geçmiş bırakılan sipariş (durum 9) bu
    adımdan sonra eklenir; geçmişe ait başlangıç tarihlerine (başlamış iş emri) dokunulmaz. Satın alma tarihleri kendi yerinde aynı kuralla üretilir."""
    ds, on = b.ds, b.ds.generated_on
    for row in b.t["SalesOrderLine"]:
        for field in ("RequestedDate", "ConfirmedDate"):
            if row.get(field) is not None and ds.start <= row[field] < on:
                row[field] = on
    for row in b.t["WorkOrder"]:
        if row.get("DueDate") is not None and ds.start <= row["DueDate"] < on:
            row["DueDate"] = on


def _quality(b: _Builder) -> None:
    """Veri kalitesi durumları (6.5, K-174, docs/11 durum 6–9) ve talep zinciri için tahmin ve benzetilen ürün."""
    ds = b.ds
    on = ds.generated_on
    # 6: zincirin derininde tedarik süresi ikisi de boş (MS.NO_LEADTIME)
    for row in b.t["MaterialSupplier"]:
        if row["MaterialId"] == b.id("Material", DEEP_MATERIAL) and row["SupplierId"] == b.id("Supplier", DEEP_SUPPLIER):
            row["FixedLeadTimeDays"] = None
            row["VariableLeadTimeDays"] = None
    # 7: talebi olmayan yarı mamul, ağacında bileşen miktarı 0 (BOM.ZERO_QTY)
    alt = b.find("Material", "ALT-004")
    new_alt = _copy(b, "Material", alt, Code=NO_DEMAND_MATERIAL, Name="Yedek montaj (talebi yok)")
    pv_src = next(r for r in b.t["ProductionVersion"] if r["MaterialId"] == alt["Id"])
    pv = _copy(b, "ProductionVersion", pv_src, MaterialId=new_alt["Id"], BOMCode=f"B-{NO_DEMAND_MATERIAL}", RouteCode=f"R-{NO_DEMAND_MATERIAL}")
    bom_src = next(r for r in b.t["BOM"] if r["MaterialId"] == alt["Id"])
    _copy(b, "BOM", bom_src, MaterialId=new_alt["Id"], Code=pv["BOMCode"], ComponentMaterialId=b.id("Material", "HAM-001"), Quantity=0.0)
    for row in [r for r in b.t["Routing"] if r["RouteCode"] == pv_src["RouteCode"]]:
        _copy(b, "Routing", row, RouteCode=pv["RouteCode"])
    # 9: teslim tarihi geçmiş ve bugün olan açık siparişler (SO.PAST_DUE: dün olan bugün, bugün olan yarın)
    so_src = next(r for r in b.t["SalesOrderLine"] if r["Type"] == "Kesin")
    for no, when in ((PAST_DUE_ORDER, on - timedelta(days=1)), (DUE_TODAY_ORDER, on)):
        _copy(b, "SalesOrderLine", so_src, OrderNo=no, LineNo=1, LineItemNo=0, MaterialId=b.id("Material", "MAM-004"), ProjectId=None,
              IsCustomTracked=False, OpenQuantity=5.0, OrderedQuantity=5.0, DeliveredQuantity=0.0, RequestedDate=when, ConfirmedDate=None)
    # 9: kritik gruba üye, günlük kapasitesi boş tezgâh (K-117, K-180)
    t04 = b.find("Resource", "T-04")
    t05 = _copy(b, "Resource", t04, Code=NO_CAPACITY_RESOURCE, Name="Torna T-05 (kapasitesi tanımsız)")  # ne kendisinde ne grubunda çalışma düzeni var
    for row in [r for r in b.t["ResourceGroupMember"] if r["ResourceId"] == t04["Id"]]:  # T-04'ün grubunda (talep zincirinde)
        _copy(b, "ResourceGroupMember", row, ResourceId=t05["Id"])
    # Tahmin: gelecek iki ay (ay başı), planlama ufku içinde
    for months, qty in ((1, 40.0), (2, 30.0)):
        b.add("Forecast", LocationId=1, MaterialId=b.id("Material", FORECAST_PRODUCT), CustomerId=None, ProjectId=None,
              Period=_first_of_month(on, months), Type="Tahmin", Quantity=qty, Uom=None, DeliveryPoint="Başı", IsActive=True)
    # Benzetilen ürün: kendi versiyonu olmayan mamul, MAM-001'in ağacı ve rotasıyla; tahmini var
    src = b.find("Material", REFERENCE_SOURCE)
    ref = _copy(b, "Material", src, Code=REFERENCE_PRODUCT, Name="Pompa gövdesi PG-80 özel (benzetilen)")
    b.add("MaterialReference", LocationId=1, MaterialId=ref["Id"], ReferenceMaterialId=src["Id"], ReferenceProductionVersionId=None,
          ValidFrom=None, ValidTo=None, TimeFactor=None)
    b.add("Forecast", LocationId=1, MaterialId=ref["Id"], CustomerId=None, ProjectId=None, Period=_first_of_month(on, 1), Type="Tahmin",
          Quantity=10.0, Uom=None, DeliveryPoint="Başı", IsActive=True)


def _subcon_work_order(b, resource_code: str) -> int | None:
    """Fason siparişin bağlı iş emri (PO.SUBCON_NO_WO, K-137): o fason grubunu kullanan operasyonu olan iş emri, yoksa fason operasyonu olan ilk iş emri."""
    fason = {b.id("ResourceGroup", c) for c in ("F-ISIL", "F-KAPLA")}
    ops = b.t["WorkOrderOperation"]
    own = b.id("ResourceGroup", resource_group(resource_code))
    found = next((o for o in ops if o.get("ResourceGroupId") == own), None) or next((o for o in ops if o.get("ResourceGroupId") in fason), None)
    return found["WorkOrderId"] if found else None


def limit_month(ds: Dataset) -> tuple[date, date]:
    """Durum 3'ün ayı: üretim gününden 4 hafta sonranın ayı."""
    d = ds.start + timedelta(days=28)
    first = d.replace(day=1)
    nxt = (first + timedelta(days=32)).replace(day=1)
    return first, nxt - timedelta(days=1)


# --- Senaryoya bağlı satırlar (Baz senaryoya yüklenir, K-175) ---

def _params(b: _Builder) -> None:
    ds = b.ds
    for seq, (criterion, direction) in enumerate([("Dönem", "Artan"), ("Müşteri önceliği", "Artan"),
                                                  ("Proje önceliği", "Artan"), ("Teslim tarihi", "Artan")], 1):
        b.add("param.PriorityRule", with_id=False, ScenarioDefinitionId=1, Seq=seq, Criterion=criterion, Direction=direction)
    first, last = limit_month(ds)
    b.add("param.SupplierLimit", ScenarioDefinitionId=1, SupplierId=b.id("Supplier", LIMIT_SUPPLIER),
          MaterialId=b.id("Material", LIMIT_MATERIAL), ValidFrom=first, ValidTo=last, UpperLimit=float(LIMIT_QTY))


# --- İş anahtarı (BusinessKey) ---

def _iso(v) -> str:
    return "" if v is None else (v.isoformat() if hasattr(v, "isoformat") else str(v))


def _business_keys(ds: Dataset) -> None:
    c = ds.code
    wo = lambda id_: ds.by_id("WorkOrder", id_)["WorkOrderNo"]  # noqa: E731
    so_line = lambda id_: "|" if id_ is None else "{OrderNo}|{LineNo}".format(**ds.by_id("SalesOrderLine", id_))  # noqa: E731
    keys = {
        "Material": lambda r: f"{LOCATION_CODE}|{r['Code']}",  # K-113
        "BOM": lambda r: f"{LOCATION_CODE}|{c('Material', r['MaterialId'])}|{r['Code']}|{c('Material', r['ComponentMaterialId'])}|"
                         f"{r['OperationNo'] or ''}|{r['SequenceNo']}",  # K-115
        "ProductionVersion": lambda r: f"{LOCATION_CODE}|{c('Material', r['MaterialId'])}|{r['Code']}",  # K-114
        "Routing": lambda r: f"{LOCATION_CODE}|{r['RouteCode']}|{r['OperationNo']}|{r['SequenceNo']}",  # K-116
        "MaterialSupplier": lambda r: f"{LOCATION_CODE}|{c('Material', r['MaterialId'])}|{c('Supplier', r['SupplierId'])}",  # K-118
        "UomConversion": lambda r: f"{c('Material', r['MaterialId'])}|{r['FromUom']}|{r['ToUom']}",
        "BorrowPayback": lambda r: f"{LOCATION_CODE}|{c('Material', r['MaterialId'])}|{c('Project', r['LendingProjectId'])}|"
                                   f"{c('Project', r['BorrowingProjectId'])}|{_iso(r['BorrowDate'])}",  # K-119
        "Resource": lambda r: f"{LOCATION_CODE}|{r['Code']}",  # K-117
        "ResourceGroup": lambda r: f"{LOCATION_CODE}|{r['Code']}",
        "ResourceGroupMember": lambda r: f"{LOCATION_CODE}|{c('ResourceGroup', r['ResourceGroupId'])}|{c('Resource', r['ResourceId'])}",
        "EmployeeAbsence": lambda r: f"{LOCATION_CODE}|{c('Resource', r['ResourceId'])}|{r['AbsenceType']}|{_iso(r['StartDate'])}",
        "SalesOrderLine": lambda r: f"{LOCATION_CODE}|{r['OrderNo']}|{r['LineNo']}|{_iso(r['LineItemNo'])}",  # K-120
        "Stock": lambda r: f"{LOCATION_CODE}|{c('Material', r['MaterialId'])}|{r['Warehouse']}|{_iso(r['LotNo'])}|{r['Status']}|"
                           f"{c('Project', r['ProjectId']) or ''}|{c('Customer', r.get('CustomerId')) or ''}|{so_line(r.get('SalesOrderLineId'))}",  # K-123
        "WorkOrder": lambda r: f"{LOCATION_CODE}|{r['WorkOrderNo']}",  # K-124
        "WorkOrderComponent": lambda r: f"{LOCATION_CODE}|{wo(r['WorkOrderId'])}|{c('Material', r['MaterialId'])}|{_iso(r['OperationNo'])}|{_iso(r['SequenceNo'])}",
        "WorkOrderOperation": lambda r: f"{LOCATION_CODE}|{wo(r['WorkOrderId'])}|{r['OperationNo']}|{r['SequenceNo']}",
        "PurchaseOrderLine": lambda r: f"{LOCATION_CODE}|{r['PurchaseOrderNo']}|{r['LineNo']}",  # K-125
        "Forecast": lambda r: f"{LOCATION_CODE}|{c('Material', r['MaterialId'])}|{c('Customer', r['CustomerId']) or ''}|"
                          f"{c('Project', r['ProjectId']) or ''}|{_iso(r['Period'])}|{r['Type'] or ''}",  # 6.5
        "MaterialReference": lambda r: f"{LOCATION_CODE}|{c('Material', r['MaterialId'])}|{c('Material', r['ReferenceMaterialId'])}|{_iso(r['ValidFrom'])}",
        "ProductionConfirmation": lambda r: f"{LOCATION_CODE}|{r['ConfirmationNo']}",
    }
    for table, rows in ds.tables.items():
        if table in ("Location", "UnitOfMeasure"):
            continue  # versiyonsuz
        fn = keys.get(table, lambda r: r["Code"])
        for r in rows:
            r["BusinessKey"] = fn(r)
