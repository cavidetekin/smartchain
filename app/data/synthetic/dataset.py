"""Sentetik veri seti v0'ın tek tanımı (docs/11, K-78, K-79). Bellekte üretir; veritabanına ve dosyaya dokunmaz.

Satırlar ana tabloların (core.*) alan adlarıyla; Id'ler tablo başına 1'den. LocationId = 1 ve ParameterSetId = 1
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
BOTTLENECK_PRODUCTS = ("MAM-001", "MAM-002", "MAM-003")
BOTTLENECK_HOURS = 3.0          # bu mamullerin gövde parçasının 5 eksende birim süresi
LIGHT_M5_HOURS = 0.3
LATE_MATERIAL, LATE_SUPPLIER, LATE_PRODUCT, LATE_ORDER = "HAM-012", "TED-04", "MAM-008", "SO-1027"
LATE_LEAD_DAYS = 56
LIMIT_SUPPLIER, LIMIT_MATERIAL, LIMIT_QTY = "TED-05", "SAT-003", 400
IMPOSSIBLE_ORDER, IMPOSSIBLE_PRODUCT = "SO-1040", "MAM-010"
MAINTENANCE_RESOURCE, LEAVE_WORKER, SICK_WORKER = "T-02", "W-007", "W-015"
ISOLATED_MATERIAL = "SAT-040"   # yalnız Material'da geçer (kirli hâlde tekrar eden anahtar, H4)
NO_ROUTE_PART = "PRC-033"       # kirli hâlde rotası çıkarılır (H1)

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
    _params(b)
    ds.tables = {k: v for k, v in b.t.items() if not k.startswith("param.")}
    ds.params = {k.split(".", 1)[1]: v for k, v in b.t.items() if k.startswith("param.")}
    _business_keys(ds)
    return ds


# --- Kuruluş: lokasyon, birim, takvim, vardiya, kaynak, çalışan ---

def _organisation(b: _Builder, rng: random.Random) -> None:
    ds = b.ds
    b.add("Location", Code=LOCATION_CODE, Name="Örnek Makina A.Ş. · Merkez fabrika", Type="Tesis",
          Country="Türkiye", CountryCode="TR", City="Kocaeli")
    for code, name in [("ADET", "Adet"), ("KG", "Kilogram"), ("M", "Metre"), ("SAAT", "Saat")]:
        b.add("UnitOfMeasure", with_id=False, Code=code, Name=name)

    cal = b.add("Calendar", Code="STD", Name="Standart · hafta içi")
    d = ds.start - timedelta(days=HISTORY_DAYS)
    while d <= ds.horizon_end:
        b.add("CalendarDay", with_id=False, CalendarId=cal["Id"], Date=d, IsWorkingDay=d.weekday() < 5,
              WorkingFraction=1.0 if d.weekday() < 5 else 0.0)
        d += timedelta(days=1)
    b.add("Shift", LocationId=1, Code="S1", StartTime=time(7, 0), EndTime=time(15, 0), BreakMinutes=30)
    b.add("Shift", LocationId=1, Code="S2", StartTime=time(15, 0), EndTime=time(23, 0), BreakMinutes=30)

    groups = [("TORNA", "CNC torna"), ("ISL3", "3 eksen işleme"), ("ISL5", "5 eksen işleme"),
              ("TASLAMA", "Taşlama"), ("MONTAJ", "Montaj"), ("KALITE", "Kalite kontrol")]
    for code, name in groups:
        b.add("ResourceGroup", LocationId=1, Code=code, Name=name)
    for code, name in [("CG-CNC", "CNC operatörü"), ("CG-MON", "Montajcı"), ("CG-KAL", "Kalite teknisyeni")]:
        b.add("CompetenceGroup", LocationId=1, Code=code, Name=name)

    machines = ([(f"T-0{i}", f"CNC torna {i}", "TORNA", 15.0) for i in range(1, 5)]
                + [(f"M3-0{i}", f"3 eksen işleme merkezi {i}", "ISL3", 15.0) for i in range(1, 4)]
                + [("M5-01", "5 eksen işleme merkezi", "ISL5", 15.0)]
                + [(f"G-0{i}", f"Silindirik taşlama {i}", "TASLAMA", 15.0) for i in range(1, 3)]
                + [(f"A-0{i}", f"Montaj hattı {i}", "MONTAJ", 15.0) for i in range(1, 3)]
                + [("Q-01", "Kalite kontrol istasyonu", "KALITE", 7.5)])
    for code, name, group, daily in machines:
        b.add("Resource", LocationId=1, Code=code, Name=name, ResourceGroupId=b.id("ResourceGroup", group),
              ResourceType="Makine", ResourceRole="Primary", IsConstrained=True, CapacityUnit="Saat",
              DailyCapacity=daily, Quantity=1, CalendarId=cal["Id"])
    # Fason kaynaklar tedarikçiye bağlanır (_suppliers'ta SupplierId yazılır).
    for code, name, lead in [("F-ISIL", "Fason ısıl işlem", 5), ("F-KAPLA", "Fason kaplama", 4)]:
        b.add("Resource", LocationId=1, Code=code, Name=name, ResourceGroupId=None, ResourceType="Fason",
              ResourceRole="Primary", IsConstrained=False, CapacityUnit="Saat", DailyCapacity=24.0, Quantity=1,
              CalendarId=cal["Id"], SubconPlanningType="Tedarik süresi", SubconFixedLeadTimeDays=lead,
              SubconVariableDaysPerUnit=0.0)

    b.add("ResourceCapacityProfile", ResourceId=b.id("Resource", "G-02"), ValidFrom=ds.day(9), ValidTo=ds.day(10, 6),
          DailyCapacity=7.5)
    b.add("ResourceCapacityProfile", ResourceId=b.id("Resource", "T-04"), ValidFrom=ds.day(12), ValidTo=ds.day(13, 6),
          DailyCapacity=22.5)
    # Durum 5: planlı bakım, hafta 2 Salı–Çarşamba.
    b.add("ResourceDowntime", ResourceId=b.id("Resource", MAINTENANCE_RESOURCE), DowntimeType="Bakım",
          StartAt=datetime.combine(ds.day(2, 1), time(0, 0)), EndAt=datetime.combine(ds.day(2, 3), time(0, 0)),
          AffectedQuantity=1, DurationDays=2.0, Note="Planlı bakım: iş mili rulmanları")
    b.add("ResourceDowntime", ResourceId=b.id("Resource", "G-01"), DowntimeType="Bakım",
          StartAt=datetime.combine(ds.day(8, 4), time(0, 0)), EndAt=datetime.combine(ds.day(8, 5), time(0, 0)),
          AffectedQuantity=1, DurationDays=1.0, Note="Yıllık bakım")

    s1, s2 = b.id("Shift", "S1"), b.id("Shift", "S2")
    valid = dict(ValidFrom=ds.start - timedelta(days=HISTORY_DAYS), ValidTo=ds.horizon_end)
    b.add("ShiftPlan", CompetenceGroupId=b.id("CompetenceGroup", "CG-MON"), ShiftId=s1, Headcount=6, **valid)
    b.add("ShiftPlan", CompetenceGroupId=b.id("CompetenceGroup", "CG-MON"), ShiftId=s2, Headcount=4, **valid)
    b.add("ShiftPlan", CompetenceGroupId=b.id("CompetenceGroup", "CG-KAL"), ShiftId=s1, Headcount=2, **valid)

    names = set()
    for i in range(1, 26):
        while True:
            name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
            if name not in names:
                names.add(name)
                break
        if i <= 10:
            group, comps = rng.choice(["TORNA", "ISL3", "ISL5"]), ["CG-CNC"] + (["CG-MON"] if i in (3, 8) else [])
        elif i <= 20:
            group, comps = "MONTAJ", ["CG-MON"]
        elif i <= 23:
            group, comps = "KALITE", ["CG-KAL"]
        else:
            group, comps = "MONTAJ", ["CG-MON", "CG-KAL"]
        w = b.add("Worker", LocationId=1, Code=f"W-{i:03d}", Name=name, ResourceGroupId=b.id("ResourceGroup", group),
                  IsActive=True)
        for c in comps:
            b.add("WorkerCompetence", with_id=False, WorkerId=w["Id"], CompetenceGroupId=b.id("CompetenceGroup", c))
    # Durum 5: izin (hafta 3, bütün hafta) ve rapor (hafta 1, Salı–Çarşamba); ayrıca ileride bir izin.
    for code, start, end, kind in [(LEAVE_WORKER, ds.day(3, 0), ds.day(3, 5), "İzin"),
                                   (SICK_WORKER, ds.day(1, 1), ds.day(1, 3), "Rapor"),
                                   ("W-021", ds.day(9, 3), ds.day(9, 5), "İzin")]:
        b.add("WorkerAbsence", WorkerId=b.id("Worker", code), StartAt=datetime.combine(start, time(0, 0)),
              EndAt=datetime.combine(end, time(0, 0)), AbsenceType=kind)


# --- Malzemeler ---

def _materials(b: _Builder, rng: random.Random) -> None:
    def mat(code, name, level, group, uom, producible, lead=None, **extra):
        row = dict(LocationId=1, Code=code, Name=name, BaseUom=uom, MaterialGroup=group,
                   MaterialLevel=level, IsPurchasable=not producible, IsProducible=producible,
                   IsSellable=level == "Nihai ürün", DefaultProcurement="Üretim" if producible else "Satın alma",
                   Ownership="Kendi", IsProjectTracked=False, IsPhantom=False,
                   ProductionLeadTimeDays=lead if producible else None,
                   GoodsReceiptDays=None if producible else 1,
                   LotSizePolicy="Lot-for-lot" if producible else None)
        return b.add("Material", **{**row, **extra})

    for code, name, _ in FINISHED:
        lead = 3
        mat(code, name, "Nihai ürün", "Mamul", "ADET", True, lead,
            IsProjectTracked=code == "MAM-006")
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
            mat(LATE_MATERIAL, "Dövme flanş Ø200 S355", "Hammadde", "Dövme", "ADET", False)
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
        mat(f"SAT-{i:03d}", name, "Hammadde", group, "ADET", False,
            SafetyStock=20 if group == "Rulman" else None, MinLot=50 if group == "Bağlantı" else None)
    # H4 için yalnız Material'da geçen malzeme: müşteri temin, satın alınmaz, hiçbir yerde kullanılmaz.
    m = mat(ISOLATED_MATERIAL, "Müşteri temin etiket seti", "Hammadde", "Aksesuar", "ADET", False)
    m.update(IsPurchasable=False, Ownership="Müşteri", GoodsReceiptDays=None)

    for code, factor in [("HAM-001", 5.55), ("HAM-002", 7.55), ("HAM-003", 9.86), ("HAM-004", 12.48)]:
        b.add("UomConversion", MaterialId=b.id("Material", code), FromUom="M", ToUom="KG", Factor=factor)


# --- Ürün ağacı ve rota ---

def _structure(b: _Builder, rng: random.Random) -> None:
    res = lambda code: b.id("Resource", code)  # noqa: E731
    sat_pool = [f"SAT-{i:03d}" for i in range(1, 40) if i != 3]
    ham_pool = [f"HAM-{i:03d}" for i in range(1, 41) if f"HAM-{i:03d}" != LATE_MATERIAL]
    cg_mon = b.id("CompetenceGroup", "CG-MON")
    light_m5 = {"PRC-026", "PRC-042", "PRC-050", "PRC-063", "PRC-071"}  # 5 eksende kısa işlenen parçalar

    def version(code):
        return b.add("ProductionVersion", MaterialId=b.id("Material", code), Code="V1", IsDefault=True,
                     BaseQuantity=1.0, RouteCode=f"R-{code}", ValidFrom=b.ds.start - timedelta(days=365))

    def bom(pv, comp, qty, op=None):
        b.add("BOM", ProductionVersionId=pv["Id"], ComponentMaterialId=b.id("Material", comp), Quantity=qty,
              ScrapPct=None, IsFixedQuantity=False, OpNo=op)

    def op(code, no, name, resource, cons, **extra):
        b.add("Routing", RouteCode=f"R-{code}", OpNo=no, SeqNo=1, OperationName=name, ResourceId=res(resource),
              ResourceRole="Primary", Consumption=round(cons, 3), ResourceNumber=1,
              IsSubcontracted=resource.startswith("F-"), **extra)

    n_alt = n_prc = 0
    for fcode, _, _ in FINISHED:
        pv_f = version(fcode)
        op(fcode, 10, "Son montaj", rng.choice(["A-01", "A-02"]), rng.uniform(1.0, 2.0),
           LaborType="Yetkinlik grubu", LaborRefId=cg_mon, LaborBasis="Ekip", CrewSize=2)
        op(fcode, 20, "Son kontrol", "Q-01", 0.3, LaborType="Yok")
        for sat in rng.sample(sat_pool, rng.choice([2, 3])):
            bom(pv_f, sat, rng.choice([2, 4, 6, 8]), 10)
        for a in range(3):
            n_alt += 1
            acode = f"ALT-{n_alt:03d}"
            bom(pv_f, acode, 1, 10)
            pv_a = version(acode)
            op(acode, 10, "Alt montaj", rng.choice(["A-01", "A-02"]), rng.uniform(0.5, 1.2),
               LaborType="Yetkinlik grubu", LaborRefId=cg_mon, LaborBasis="Ekip", CrewSize=2)
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
        b.add("Supplier", Code=code, Name=name, IsSubcontractor=sub)
    b.find("Resource", "F-ISIL")["SupplierId"] = b.id("Supplier", "TED-07")
    b.find("Resource", "F-KAPLA")["SupplierId"] = b.id("Supplier", "TED-08")

    by_group = {"Çubuk": "TED-01", "Levha": "TED-02", "Bağlantı": "TED-03", "Rulman": LIMIT_SUPPLIER,
                "Conta": "TED-06", "Aksesuar": "TED-03", "Dövme": LATE_SUPPLIER}
    for m in b.t["Material"]:
        if not m["IsPurchasable"]:
            continue
        lead = LATE_LEAD_DAYS if m["Code"] == LATE_MATERIAL else rng.choice([7, 10, 14, 14, 21])
        b.add("MaterialSupplier", MaterialId=m["Id"], SupplierId=b.id("Supplier", by_group[m["MaterialGroup"]]),
              Priority=1, QuotaPct=None, LeadTimeDays=lead, LeadTimeBasis="Takvim günü",
              MinOrderQty=m.get("MinLot"), OrderMultiple=None, MaxOrderQty=None)
        if m["MaterialGroup"] in ("Çubuk", "Conta") and rng.random() < 0.3:  # ikinci tedarikçi
            b.add("MaterialSupplier", MaterialId=m["Id"],
                  SupplierId=b.id("Supplier", "TED-02" if m["MaterialGroup"] == "Çubuk" else "TED-03"),
                  Priority=2, QuotaPct=30.0, LeadTimeDays=lead + 7, LeadTimeBasis="Takvim günü")

    for code, name, prio, partial in [("MUS-A", "Akdeniz Pompa Sistemleri", 1, False),
                                      ("MUS-B", "Kuzey Enerji Ekipmanları", 2, True),
                                      ("MUS-C", "Orta Anadolu Makine", 3, True)]:
        b.add("Customer", Code=code, Name=name, Priority=prio, AllowPartialDelivery=partial)
    b.add("ProjectGroup", Code="PG-01", Name="Enerji santrali projeleri", IsolationRule="Ortaktan beslenir")
    b.add("Project", Code="PRJ-01", Name="Santral A pompa paketi", ProjectGroupId=1,
          IsolationRule="Ortaktan beslenir", Priority=1, IsClosed=False)
    b.add("Project", Code="PRJ-02", Name="Arıtma tesisi redüktörleri", ProjectGroupId=1,
          IsolationRule="Tam izolasyon", Priority=2, IsClosed=False)


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
        b.add("SalesOrderLine", LocationId=1, OrderNo=no, LineNo=1, LineItemNo=None, Type="Kesin",
              CustomerId=b.id("Customer", cust), MaterialId=b.id("Material", fg),
              ProjectId=b.id("Project", prj) if prj else None, OpenQty=float(qty), RequestedDate=due,
              ConfirmedDate=due if rng.random() < 0.6 else None, Priority=None, AllowPartialDelivery=None,
              Status="Açık")
    for no, fg, qty, week in [("SO-1041", "MAM-004", 30, 9), ("SO-1042", "MAM-007", 15, 12)]:  # teklif (K-60)
        b.add("SalesOrderLine", LocationId=1, OrderNo=no, LineNo=1, LineItemNo=None, Type="Teklif",
              CustomerId=b.id("Customer", "MUS-B"), MaterialId=b.id("Material", fg), ProjectId=None,
              OpenQty=float(qty), RequestedDate=ds.day(week, 4), ConfirmedDate=None, Status="Açık")


# --- Stok ---

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
            b.add("Stock", LocationId=1, MaterialId=m["Id"], Warehouse="ANA", LotNo=None, StockStatus="Serbest",
                  ProjectId=None, Quantity=qty)
    mid = lambda c: b.id("Material", c)  # noqa: E731
    b.add("Stock", LocationId=1, MaterialId=mid("HAM-005"), Warehouse="ANA", LotNo="L-2410-07", StockStatus="Kalitede",
          ProjectId=None, Quantity=200.0, QualityEntryDate=ds.generated_on + timedelta(days=3))  # K-9
    b.add("Stock", LocationId=1, MaterialId=mid("SAT-015"), Warehouse="ANA", LotNo="L-2409-21", StockStatus="Bloke",
          ProjectId=None, Quantity=60.0)
    b.add("Stock", LocationId=1, MaterialId=mid("MAM-004"), Warehouse="MAMUL", LotNo=None, StockStatus="Serbest",
          ProjectId=None, Quantity=5.0)
    b.add("Stock", LocationId=1, MaterialId=mid("MAM-006"), Warehouse="MAMUL", LotNo=None, StockStatus="Serbest",
          ProjectId=b.id("Project", "PRJ-01"), Quantity=3.0)


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
        wo = b.add("WorkOrder", LocationId=1, OrderNo=no, MaterialId=m["Id"], OrderType="Üretim",
                   Status="Başladı" if started else "Yayınlandı", OrderQty=float(qty), OpenQty=open_qty,
                   StartDate=ds.start - timedelta(days=rng.choice([5, 8, 12])) if started else ds.day(week, 0),
                   DueDate=ds.day(week, 4), ProjectId=None,
                   SalesOrderLineId=so_mam004["Id"] if no == "WO-5001" else None,
                   ParentWorkOrderId=None,
                   LastActivityDate=ds.generated_on - timedelta(days=1) if started else None)
        for line in (r for r in b.t["BOM"] if r["ProductionVersionId"] == pv["Id"]):
            required = round(line["Quantity"] * qty, 4)
            issued = required if started else 0.0
            b.add("WorkOrderComponent", WorkOrderId=wo["Id"], MaterialId=line["ComponentMaterialId"],
                  RequiredQty=required, IssuedQty=issued, RemainingQty=round(required - issued, 4))
        for i, r in enumerate(x for x in b.t["Routing"] if x["RouteCode"] == pv["RouteCode"]):
            planned = round(r["Consumption"] * qty, 4)
            done = round(planned / 2, 4) if started and i == 0 else 0.0
            b.add("WorkOrderOperation", WorkOrderId=wo["Id"], OpNo=r["OpNo"], SeqNo=r["SeqNo"],
                  ResourceId=r["ResourceId"], PlannedConsumption=planned, ConfirmedConsumption=done,
                  RemainingConsumption=round(planned - done, 4), Status="Açık")
            if done:
                start = datetime.combine(ds.start - timedelta(days=3), time(8, 0))
                b.add("ProductionConfirmation", WorkOrderId=wo["Id"], OpNo=r["OpNo"], SeqNo=r["SeqNo"],
                      ResourceId=r["ResourceId"], ConfirmedQty=float(qty - open_qty), ActualConsumption=round(done, 3),
                      StartAt=start, EndAt=start + timedelta(hours=max(1, round(done))))
    # Alt montaj iş emri, mamul iş emrinin alt kırılımı.
    parent = next(w for w in b.t["WorkOrder"] if w["OrderNo"] == "WO-5001")
    child = next(w for w in b.t["WorkOrder"] if w["OrderNo"] == "WO-5002")
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
        b.add("PurchaseOrderLine", LocationId=1, OrderNo=no or f"PO-{n}", LineNo=1, OrderType=kind,
              SupplierId=supplier_id, MaterialId=material_id, OpenQty=float(qty), RequestedDate=req,
              ConfirmedDate=conf, ProjectId=None, WorkOrderId=wo, Status="Açık")

    for m in rng.sample(candidates, 20):
        req = ds.day(rng.randint(1, 6), rng.randint(0, 4))
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
    fason_part = next(r for r in b.t["Routing"] if r["ResourceId"] == b.id("Resource", "F-ISIL"))["RouteCode"][2:]
    po(b.id("Material", fason_part), 40, ds.day(2, 3), ds.day(2, 3), b.id("Supplier", "TED-07"), kind="Fason")
    kaplama = next(r for r in b.t["Routing"] if r["ResourceId"] == b.id("Resource", "F-KAPLA"))["RouteCode"][2:]
    po(b.id("Material", kaplama), 25, ds.day(3, 1), None, b.id("Supplier", "TED-08"), kind="Fason")
    n = 2059
    po(b.id("Material", "SAT-020"), 300, ds.day(2, 1), ds.day(2, 1), supplier_of[b.id("Material", "SAT-020")])  # PO-2060 (H3)


def limit_month(ds: Dataset) -> tuple[date, date]:
    """Durum 3'ün ayı: üretim gününden 4 hafta sonranın ayı."""
    d = ds.start + timedelta(days=28)
    first = d.replace(day=1)
    nxt = (first + timedelta(days=32)).replace(day=1)
    return first, nxt - timedelta(days=1)


# --- Parametre seti ---

def _params(b: _Builder) -> None:
    ds = b.ds
    b.add("param.ParameterSet", Name=SET_NAME, IsDefault=False)
    b.add("param.PlanningSetting", with_id=False, ParameterSetId=1, SettingKey="ModelType", Value="LP")
    b.add("param.TimeBucketDefinition", with_id=False, ParameterSetId=1, Seq=1, BucketType="Hafta", Count=HORIZON_WEEKS)
    for seq, (criterion, direction) in enumerate([("Dönem", "Artan"), ("Müşteri önceliği", "Artan"),
                                                  ("Proje önceliği", "Artan"), ("Teslim tarihi", "Artan")], 1):
        b.add("param.PriorityRule", with_id=False, ParameterSetId=1, Seq=seq, Criterion=criterion, Direction=direction)
    first, last = limit_month(ds)
    b.add("param.SupplierLimit", ParameterSetId=1, SupplierId=b.id("Supplier", LIMIT_SUPPLIER),
          MaterialId=b.id("Material", LIMIT_MATERIAL), ValidFrom=first, ValidTo=last, UpperLimit=float(LIMIT_QTY))


# --- İş anahtarı (BusinessKey) ---

def _iso(v) -> str:
    return "" if v is None else (v.isoformat() if hasattr(v, "isoformat") else str(v))


def _business_keys(ds: Dataset) -> None:
    c = ds.code
    pv = lambda id_: ds.by_id("ProductionVersion", id_)  # noqa: E731
    wo = lambda id_: ds.by_id("WorkOrder", id_)["OrderNo"]  # noqa: E731
    keys = {
        "BOM": lambda r: f"{c('Material', pv(r['ProductionVersionId'])['MaterialId'])}|"
                         f"{pv(r['ProductionVersionId'])['Code']}|{c('Material', r['ComponentMaterialId'])}",
        "CalendarDay": lambda r: f"{c('Calendar', r['CalendarId'])}|{_iso(r['Date'])}",
        "ProductionVersion": lambda r: f"{c('Material', r['MaterialId'])}|{r['Code']}",
        "Routing": lambda r: f"{r['RouteCode']}|{r['OpNo']}|{r['SeqNo']}|{c('Resource', r['ResourceId'])}",
        "MaterialSupplier": lambda r: f"{c('Material', r['MaterialId'])}|{c('Supplier', r['SupplierId'])}",
        "UomConversion": lambda r: f"{c('Material', r['MaterialId'])}|{r['FromUom']}|{r['ToUom']}",
        "ResourceCapacityProfile": lambda r: f"{c('Resource', r['ResourceId'])}|{_iso(r['ValidFrom'])}",
        "ResourceDowntime": lambda r: f"{c('Resource', r['ResourceId'])}|{_iso(r['StartAt'])}",
        "ShiftPlan": lambda r: f"{c('CompetenceGroup', r['CompetenceGroupId'])}|{c('Shift', r['ShiftId'])}|"
                               f"{_iso(r['ValidFrom'])}",
        "WorkerCompetence": lambda r: f"{c('Worker', r['WorkerId'])}|{c('CompetenceGroup', r['CompetenceGroupId'])}",
        "WorkerAbsence": lambda r: f"{c('Worker', r['WorkerId'])}|{_iso(r['StartAt'])}",
        "SalesOrderLine": lambda r: f"{r['OrderNo']}|{r['LineNo']}|{_iso(r['LineItemNo'])}",
        "Stock": lambda r: f"{c('Material', r['MaterialId'])}|{r['Warehouse']}|{_iso(r['LotNo'])}|{r['StockStatus']}|"
                           f"{c('Project', r['ProjectId']) or ''}",
        "WorkOrder": lambda r: r["OrderNo"],
        "WorkOrderComponent": lambda r: f"{wo(r['WorkOrderId'])}|{c('Material', r['MaterialId'])}",
        "WorkOrderOperation": lambda r: f"{wo(r['WorkOrderId'])}|{r['OpNo']}|{r['SeqNo']}",
        "PurchaseOrderLine": lambda r: f"{r['OrderNo']}|{r['LineNo']}",
        "ProductionConfirmation": lambda r: f"{wo(r['WorkOrderId'])}|{r['OpNo']}|{r['SeqNo']}|{_iso(r['StartAt'])}",
    }
    for table, rows in ds.tables.items():
        if table in ("Location", "UnitOfMeasure"):
            continue  # versiyonsuz
        fn = keys.get(table, lambda r: r["Code"])
        for r in rows:
            r["BusinessKey"] = fn(r)
