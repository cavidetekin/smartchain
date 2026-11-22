"""Motor arayüzü: baştan sabittir; sahte motor (0.5) ve gerçek motor (Aşama 10) aynı sözleşmeyi uygular.

Giriş: PlanRun, parametre seti ve salt okunur veri erişimi (PlanningData). Çıkış: PlanResult; motor
veritabanına yazmaz, sonucu writer.py planning.* tablolarına tek işlemde yazar (K-70).
Sözleşme: docs/09-motor-arayuzu.md.
"""
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Protocol

# PlanRun.Status (docs/02)
RUN_QUEUED = "Sırada"
RUN_RUNNING = "Çalışıyor"
RUN_DONE = "Bitti"
RUN_PARTIAL = "Kısmen"
RUN_FAILED = "Hata"

# Motor adımları (fonksiyon 29–39); iş süreci her geçişte ilerleme yazar (K-71).
STAGES = ("Ön hesap", "MRP patlatma", "Model kurma", "Çözüm", "Son hesap", "Uyarı ve metrik")

# Pegging'de motorun önerdiği planlı siparişe bağ (SupplyId yazıcıda gerçek Id olur).
SUPPLY_PLANNED_ORDER = "Planlı sipariş"


@dataclass(frozen=True)
class PlanRunInfo:
    id: int
    data_version_id: int
    scenario_definition_id: int  # senaryo tanımı: hesabın parametreleri (K-175)
    scenario_id: int | None = None
    workspace_id: int | None = None


@dataclass(frozen=True)
class TimeBucket:
    seq: int
    bucket_type: str  # dönem tipi: Gün | Hafta | Ay (raporlama ekseninde ayrıca Çeyrek | Yıl)
    count: int        # kapsam
    span_unit: str = ""  # kapsam birimi: Gün | Hafta | Ay (takvim kuralları app/params/horizon.py)


@dataclass(frozen=True)
class Objective:
    """Leksikografik hedef (K-175): motor aktif hedefleri sırayla çözer."""
    seq: int
    code: str
    priority_group: int | None
    time_budget_seconds: int
    tolerance_pct: float  # üst hedeften verilebilecek en çok ödün; 0 = katı


@dataclass(frozen=True)
class PriorityRule:
    seq: int
    criterion: str
    direction: str  # Artan | Azalan


@dataclass(frozen=True)
class ScenarioParameters:
    """Senaryonun parametrelerinin tamamı (K-175): her senaryo kendi parametrelerini taşır."""
    id: int    # ScenarioDefinition.Id
    name: str
    settings: dict[str, str] = field(default_factory=dict)  # PlanningSetting: SettingKey → Value (katalog başlangıç değerleriyle tamamlanmış)
    time_buckets: tuple[TimeBucket, ...] = ()    # plan ekseni
    report_buckets: tuple[TimeBucket, ...] = ()  # raporlama ekseni (planla aynıysa plan dizisi)
    objectives: tuple[Objective, ...] = ()       # aktif hedefler, sırasıyla
    priority_rules: tuple[PriorityRule, ...] = ()
    allocation_rules: tuple[dict, ...] = ()  # AllocationRule satırları (alan adları docs/02)


class PlanningData(Protocol):
    """Salt okunur veri erişimi: PlanRun'un veri versiyonundaki core.* satırları."""

    data_version_id: int

    def read(self, table: str, columns: Sequence[str] | None = None) -> list[dict]:
        """table: 'Material' ya da 'core.Material'. Versiyonlu tabloda yalnız bu versiyonda geçerli satırlar."""
        ...

    def period_values(self, name: str, date_from: date, date_to: date) -> list[dict]:
        """Dönem değerlerinin tek hesabı (docs/09, K-184, K-188): planın senaryosu için gün bazında satırlar. name: 'resource-capacity-day'
        (kaynak grubu × kaynak × gün kapasite). Ekrandaki önbellek aynı hesapla kurulur."""
        ...

    def model_constraints(self) -> list[dict]:
        """Model kısıtları (docs/09, K-189): planın senaryosunda geçerli {ResourceGroupId, UnconstrainedCapacityFactor, TargetUtilizationPct};
        yalnız kritik ve güncel kaynak grupları. Kritik olmayan grubun saklı değeri dönmez."""
        ...

    def warning_thresholds(self) -> list[dict]:
        """Uyarı eşikleri (docs/09, K-190): planın senaryosundaki aktif uyarılar {Code, Category, Unit, Direction, Low, Medium, High, Critical,
        Severity}. Yön `above`: değer > eşik; `below`: değer < eşik (eşik dahil değil); önem, tutulan en yüksek kademedir."""
        ...


@dataclass(frozen=True)
class EngineInput:
    plan_run: PlanRunInfo
    parameters: ScenarioParameters
    data: PlanningData
    time_budget_seconds: int


@dataclass
class PlanResult:
    """Motorun çıktısı. Satırlar docs/02 alan adlarıyla dict; Id, PlanRunId ve UpdatedAt'i yazıcı doldurur.

    planned_orders satırına 'ref' verilebilir; pegging satırı 'supply_ref' ile o planlı siparişe bağlanır
    (SupplyType = 'Planlı sipariş', SupplyId yazıcıda gerçek Id olur).
    """

    engine_used: str  # LP | MILP | Kurallı | Kısıtsız MRP
    solver: str | None = None
    status: str = RUN_DONE  # Bitti | Kısmen
    planned_orders: list[dict] = field(default_factory=list)
    supply_recommendations: list[dict] = field(default_factory=list)
    demand_fulfillment: list[dict] = field(default_factory=list)
    capacity_loads: list[dict] = field(default_factory=list)
    pegging: list[dict] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)  # PlanMetric: MetricCode → Value
    solver_log: dict | None = None  # SolverLog: ModelSize, SolveSeconds, Gap, Iterations


Progress = Callable[[str], None]


class EngineError(Exception):
    """Motorun iş diliyle açıklanan hatası (ör. çözümsüz model). Mesaj kullanıcıya gösterilir."""


class Engine(Protocol):
    name: str

    def run(self, inp: EngineInput, progress: Progress) -> PlanResult:
        ...
