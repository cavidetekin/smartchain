"""Parametre kataloğu (fonksiyon 22, 23; K-175): senaryonun taşıdığı planlama parametreleri, başlıkları ve başlangıç değerleri.

Değerler `param.PlanningSetting`'te anahtar–değer olarak durur (metin): Evet/Hayır "1" / "0", seçenek ekrandaki adıyla, sayı düz yazımla, boş sayı
satırsız. Katalog docs/06 fonksiyon 22'deki tabloyla aynıdır; test ikisini karşılaştırır. Hedefler ve dönem dizisi ayrı tablolardadır
(`ObjectiveDefinition`, `TimeBucketDefinition`); başlangıç satırları da buradadır.
"""
from dataclasses import dataclass

BOOL, CHOICE, INT, NUMBER = "bool", "choice", "int", "number"
YES, NO = "1", "0"
LP, MILP = "LP", "MILP"
BASE_NAME = "Baz"

AXIS_PLAN, AXIS_REPORT = "Plan", "Rapor"
DAY, WEEK, MONTH, QUARTER, YEAR = "Gün", "Hafta", "Ay", "Çeyrek", "Yıl"
SPAN_UNITS = (DAY, WEEK, MONTH, QUARTER, YEAR)  # kapsam birimi (dönem dizisi)
FIX_UNITS = (DAY, WEEK, MONTH)                    # sabit dönemin birimi
PLAN_BUCKETS = (DAY, WEEK, MONTH, QUARTER, YEAR)  # plan ekseninde de çeyrek ve yıl (7.1 demo bulgusu)
REPORT_BUCKETS = PLAN_BUCKETS
RANK = {DAY: 1, WEEK: 2, MONTH: 3, QUARTER: 4, YEAR: 5}  # kabalık sırası
WEEKDAYS = ("Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar")
PLAN_START_TODAY, PLAN_START_DATA = "Bugün", "Veri versiyonunun tarihi"


@dataclass(frozen=True)
class Param:
    key: str
    label: str
    kind: str
    default: str | None
    options: tuple[str, ...] = ()
    minimum: float | None = None
    maximum: float | None = None
    nullable: bool = False                         # boş bırakılabilir sayı (boş = sınırsız)
    enabled_when: tuple[str, str] | None = None    # (anahtar, değer): öteki parametre bu değerdeyken düzenlenir
    hint: str | None = None                        # alan adının ipucu
    unit_key: str | None = None                    # değerin birimini taşıyan parametre: ekranda aynı satırda (ör. sabit dönem)


@dataclass(frozen=True)
class Sub:
    key: str
    title: str
    params: tuple[Param, ...] = ()
    table: str | None = None  # "buckets" | "report": form yerine tablo


@dataclass(frozen=True)
class Section:
    key: str
    title: str
    subs: tuple[Sub, ...] = ()
    table: str | None = None  # "objectives"


def _b(key, label, default, **kw):
    return Param(key, label, BOOL, default, **kw)


def _c(key, label, options, default, **kw):
    return Param(key, label, CHOICE, default, options=tuple(options), **kw)


_MILP = ("ModelType", MILP)
_LOT_HINT = "Yalnız MILP modelde uygulanır."

SECTIONS: tuple[Section, ...] = (
    Section("model", "Model", (
        Sub("model-tipi", "Model tipi", (
            _c("ModelType", "Model tipi", (LP, MILP), LP),
            _b("ProductionMinLot", "Üretimde minimum lot", NO, enabled_when=_MILP, hint=_LOT_HINT),
            _b("ProductionLotMultiple", "Üretimde lot katı", NO, enabled_when=_MILP, hint=_LOT_HINT),
            _b("ProductionMaxLot", "Üretimde maksimum lot", NO, enabled_when=_MILP, hint=_LOT_HINT),
            _b("RoundPurchaseToLot", "Satın alma önerisini sipariş lotuna yuvarla", YES,
               hint="Satın alma kararı modelde süreklidir; öneri sonradan sipariş lotuna yuvarlanır (K-27)."),
        )),
        Sub("cozum", "Çözüm", (
            Param("OptimalityGapPct", "Optimality gap (%)", NUMBER, "1", minimum=0, maximum=100),
            _b("MrpWarmStart", "MRP ile başlangıç çözümü", YES),
        )),
    )),
    Section("hedefler", "Hedefler", table="objectives"),
    Section("talep", "Talep", (
        Sub("kapsam", "Plana giren talep", (
            _b("IncludeFirmOrders", "Kesin sipariş", YES),
            _b("IncludeQuotes", "Teklif", NO),
            _b("IncludeOnHold", "Beklemedeki sipariş", NO),
            _b("IncludeForecast", "Tahmin", YES),
        )),
        Sub("karsilama", "Karşılama", (
            _c("PastDueDemand", "Geçmiş tarihli açık talep", ("Gecikmiş say", "Bugüne çek"), "Gecikmiş say"),
            _b("AllowPartialFulfillment", "Kısmi karşılama", YES),
            Param("MaxLatenessDays", "En fazla gecikebilecek gün", INT, None, minimum=0, nullable=True, hint="Boş: sınırsız."),
        )),
    )),
    Section("malzeme", "Malzeme", (
        Sub("kisit-ve-stok", "Kısıt ve stok", (
            _b("MaterialConstraint", "Malzeme kısıtı", YES),
            _b("UseQualityStock", "Kalitedeki stok kullanılabilir", NO),
            _c("MaxStockMode", "Maksimum stok", ("Kısıt", "Yalnız uyarı"), "Yalnız uyarı"),
        )),
        Sub("guvenlik-stogu", "Güvenlik stoğu", (
            _c("SafetyStockMode", "Güvenlik stoğu", ("Dikkate alma", "Esnek hedef", "Kesin kısıt"), "Esnek hedef"),
            _c("SafetyStockBasis", "Güvenlik stoğu ve stok gün kapsamı ikisi de doluysa", ("Büyük olan", "Yalnız miktar", "Yalnız gün"), "Büyük olan"),
        )),
        Sub("tedarik", "Tedarik", (
            _c("SupplierSelectionRule", "Tedarikçi seçim kuralı", ("En kısa tedarik süresi", "Öncelik"), "Öncelik"),
            _c("OpenSupplyDate", "Açık arzın tarihi", ("Teyit tarihi", "İstenen tarih"), "Teyit tarihi", hint="Teyit tarihi boşsa istenen tarih kullanılır."),
            _c("PastDueSupply", "Tarihi geçmiş açık arz", ("Bugüne çek", "Plana alma"), "Bugüne çek"),
        )),
    )),
    Section("kapasite", "Kapasite", (
        Sub("kapasite", "Kapasite", (
            _c("ResourceConstraint", "Kaynak kısıtı", ("Kısıtsız", "Kısıtlı", "Kısmi"), "Kısıtlı"),
            _b("UseOvertime", "Fazla mesai", NO),
            _b("UseSubcontracting", "Fason", NO),
            _b("LaborConstraint", "İşçi kısıtı", NO),
        )),
    )),
    Section("planlama-ufku", "Planlama ufku", (
        Sub("ufuk-ve-donemler", "Ufuk ve dönemler", table="buckets"),
        Sub("raporlama-ekseni", "Raporlama ekseni", (
            _b("ReportAxisSameAsPlan", "Raporlama ekseni planla aynı", YES),
        ), table="report"),
        Sub("takvim-ayarlari", "Takvim ayarları", (
            _c("WeekStart", "Hafta başlangıcı", WEEKDAYS, "Pazartesi"),
            _c("PlanStart", "Plan başlangıcı", (PLAN_START_TODAY, PLAN_START_DATA), PLAN_START_TODAY),
            _c("BucketDate", "Dönem içi tarih", ("Dönem başı", "Dönem sonu"), "Dönem sonu"),
        )),
    )),
    Section("plan-kararliligi", "Plan kararlılığı", (
        Sub("plan-kararliligi", "Plan kararlılığı", (
            Param("FixPeriod", "Sabit dönem", INT, "0", minimum=0, unit_key="FixPeriodUnit",
                  hint="Hafta ve Ay'da içinde bulunulan hafta ya da ay sayıya dahildir; sabit dönem takvim sınırında biter. 0: sabit dönem yok."),
            _c("FixPeriodUnit", "Sabit dönem birimi", FIX_UNITS, DAY),
            _c("OpenWorkOrders", "Açık iş emirleri", ("Sabit", "Yalnız öteleme önerisi", "Serbest"), "Yalnız öteleme önerisi"),
            _c("OpenPurchaseOrders", "Açık satın alma siparişleri", ("Sabit", "Öneri üret"), "Sabit"),
            _b("KeepLockedRecords", "Sabitlenmiş kararlar korunsun", YES),
        )),
    )),
    # fonksiyon 26 (K-190): kendi uçları ve tablosu; alt başlıklar uyarı kategorileridir (WARNING_CATEGORIES ile aynı adlar, aşağıda doğrulanır)
    Section("uyari-esikleri", "Uyarı eşikleri", (
        Sub("talep", "Talep", table="warnings"), Sub("malzeme", "Malzeme", table="warnings"), Sub("kapasite", "Kapasite", table="warnings"),
        Sub("plan-kalitesi", "Plan kalitesi", table="warnings"),
    )),
)

PARAMS: tuple[Param, ...] = tuple(p for s in SECTIONS for sub in s.subs for p in sub.params)
BY_KEY: dict[str, Param] = {p.key: p for p in PARAMS}
assert len(BY_KEY) == len(PARAMS), "parametre anahtarı yinelendi"
DEFAULTS: dict[str, str] = {p.key: p.default for p in PARAMS if p.default is not None}


@dataclass(frozen=True)
class Objective:
    code: str
    label: str
    seconds: int | None   # başlangıç süre bütçesi; None: kurulumda kapalı
    tolerance: float | None


# Başlangıç sırası listedeki sıradır. Öncelik grupları 7.4'te gelir: o zamana kadar talep hedefleri tek gruptur (PriorityGroup boş).
OBJECTIVES: tuple[Objective, ...] = (
    Objective("UNMET_DEMAND", "Karşılanmayan talep", 300, 0),
    Objective("LATENESS", "Gecikme", 300, 0),
    Objective("UNMET_FORECAST", "Karşılanmayan tahmin", 120, 2),
    Objective("FORECAST_LATENESS", "Tahmin gecikmesi", 120, 2),
    Objective("SAFETY_STOCK", "Güvenlik stoğunun altı", 60, 5),
    Objective("OVERTIME", "Fazla mesai", 60, 5),
    Objective("SUBCONTRACT", "Fason", 60, 5),
    Objective("ALTERNATIVE", "Alternatif önceliği", 60, 5),
    Objective("EARLY_BUILD", "Erken üretim ve stok", 60, 5),
    Objective("PLAN_DEVIATION", "Önceki plandan sapma", None, None),
    Objective("OVER_TARGET_LOAD", "Hedef doluluğun üstü", None, None),
)
OBJECTIVE_LABELS: dict[str, str] = {o.code: o.label for o in OBJECTIVES}

# Başlangıç dönem dizisi (plan ekseni): içinde bulunulan ay + 2 ay haftalık, sonra 6 ay aylık
DEFAULT_BUCKETS: tuple[tuple[str, int, str], ...] = ((WEEK, 3, MONTH), (MONTH, 6, MONTH))


# --- Uyarı eşikleri (fonksiyon 26; K-190) ---------------------------------------------------------------------------------------------------
# Katalog kodda sabittir: kullanıcı uyarı ekleyip silemez; eşik, önem ve aktiflik senaryonun verisidir (param.WarningThreshold).
SEVERITIES: tuple[str, ...] = ("Düşük", "Orta", "Yüksek", "Kritik")
TIERS: tuple[str, ...] = ("low", "medium", "high", "critical")                      # API alanları, SEVERITIES sırasıyla
TIER_COLUMNS: dict[str, str] = {"low": "ThresholdLow", "medium": "ThresholdMedium", "high": "ThresholdHigh", "critical": "ThresholdCritical"}
WARNING_CATEGORIES: tuple[str, ...] = ("Talep", "Malzeme", "Kapasite", "Plan kalitesi")
ABOVE, BELOW = "above", "below"       # yön: değer eşikten büyük / küçük olunca (eşik dahil değil)
UNIT_DAY, UNIT_PCT = "gün", "%"


@dataclass(frozen=True)
class Warning:
    code: str
    category: str
    label: str
    unit: str | None = None                                        # None: eşiksiz uyarı
    direction: str | None = None
    defaults: tuple[float | None, ...] = (None, None, None, None)  # başlangıç eşikleri: Düşük, Orta, Yüksek, Kritik
    severity: str | None = None                                    # eşiksiz uyarının başlangıç önemi

    @property
    def has_threshold(self) -> bool:
        return self.unit is not None


WARNINGS: tuple[Warning, ...] = (
    Warning("ORDER_LATE", "Talep", "Gecikme", UNIT_DAY, ABOVE, (5, 10, 15, 20)),
    Warning("OTIF_RATE", "Talep", "OTIF oranı", UNIT_PCT, BELOW, (95, 90, 85, 80)),
    Warning("FILL_RATE", "Talep", "Karşılama oranı", UNIT_PCT, BELOW, (98, 95, 90, 80)),
    Warning("ORDER_UNMET", "Talep", "Karşılanmayan sipariş", severity="Kritik"),
    Warning("FORECAST_UNMET", "Talep", "Karşılanmayan tahmin", severity="Orta"),
    Warning("MAT_SHORTAGE", "Malzeme", "Malzeme eksiği", UNIT_DAY, BELOW, (60, 30, 14, 7)),
    Warning("MAT_BELOW_SAFETY", "Malzeme", "Güvenlik stoğunun altı", UNIT_PCT, BELOW, (100, 75, 50, 25)),
    Warning("MAT_EXCESS", "Malzeme", "Fazla stok", UNIT_PCT, ABOVE, (100, 125, 150, None)),
    Warning("PURCHASE_LATE", "Malzeme", "Geciken satın alma önerisi", UNIT_DAY, ABOVE, (1, 7, 14, 30)),
    Warning("SHELF_LIFE", "Malzeme", "Raf ömrü", UNIT_DAY, BELOW, (90, 60, 30, 7)),
    Warning("CAP_OVERLOAD", "Kapasite", "Aşırı yük", UNIT_PCT, ABOVE, (None, 100, 110, 125)),
    Warning("CAP_OVER_TARGET", "Kapasite", "Hedef doluluğun üstü", UNIT_PCT, ABOVE, (100, 110, None, None)),
    Warning("CAP_LOW_LOAD", "Kapasite", "Düşük doluluk", UNIT_PCT, BELOW, (40, 20, None, None)),
    Warning("OVERTIME_USE", "Kapasite", "Ek mesai kullanımı", UNIT_PCT, ABOVE, (50, 80, 100, None)),
    Warning("PLAN_TIME_LIMIT", "Plan kalitesi", "Süre bütçesi doldu", severity="Orta"),
    Warning("PLAN_RELAXED", "Plan kalitesi", "Kısıt gevşetildi", severity="Yüksek"),
    Warning("PLAN_FALLBACK", "Plan kalitesi", "Yedek yöntem çalıştı", severity="Yüksek"),
)
WARNING_BY_CODE: dict[str, Warning] = {w.code: w for w in WARNINGS}
assert len(WARNING_BY_CODE) == len(WARNINGS), "uyarı kodu yinelendi"
assert all(w.category in WARNING_CATEGORIES and (w.severity in SEVERITIES) != w.has_threshold for w in WARNINGS)
assert tuple(sub.title for s in SECTIONS if s.key == "uyari-esikleri" for sub in s.subs) == WARNING_CATEGORIES
