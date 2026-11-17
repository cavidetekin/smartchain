"""Liste sorgusu istek gövdeleri (docs/08, K-87). Yapı burada, anlam (alan, operatör, tip) query.py'de doğrulanır."""
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MAX_LIMIT = 500             # ListChunkSize'ın üst sınırı (docs/02)
DEFAULT_CHUNK_SIZE = 100
DEFAULT_MAX_GROUPS = 1000  # ListMaxGroups (K-90)


class SortItem(BaseModel):
    field: str
    dir: Literal["asc", "desc"] = "asc"


class FilterItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    field: str
    op: str
    value: Any = None
    values: list[Any] | None = None
    min: float | None = None
    max: float | None = None
    from_: date | None = Field(default=None, alias="from")
    to: date | None = None
    empty: bool = False      # liste filtresinde: değerler ya da boş (U-13)


# --- Koşullu biçim kuralları (U-24, K-95, K-96; docs/08 "Koşullu biçim kuralları") -------------------------------

MAX_RULES = 20
ICONS = ("arrow_up", "arrow_down", "dot", "warning", "check", "cross", "flag", "star")
HEX_COLOR = r"^#[0-9a-fA-F]{6}$"


class RuleCondition(BaseModel):
    """Kuralın koşulu: filtreyle aynı değer alanları; sayı ve tarihte gt/lt/eq için sabit değer yerine field_ref."""
    model_config = ConfigDict(populate_by_name=True)

    op: str
    value: Any = None
    values: list[Any] | None = None
    min: float | None = None
    max: float | None = None
    from_: date | None = Field(default=None, alias="from")
    to: date | None = None
    field_ref: str | None = None
    empty_as_zero: bool | None = None  # sayı alanı karşılaştırmasında boşları 0 say (boşsa varsayılan: evet)


class RuleFormat(BaseModel):
    fill: str | None = Field(default=None, pattern=HEX_COLOR)
    color: str | None = Field(default=None, pattern=HEX_COLOR)
    bold: bool = False
    icon: Literal["arrow_up", "arrow_down", "dot", "warning", "check", "cross", "flag", "star"] | None = None
    icon_color: str | None = Field(default=None, pattern=HEX_COLOR)  # ekranda ikonun rengi; Excel'de yazı rengi

    @field_validator("fill", "color", "icon_color")
    @classmethod
    def _lower(cls, v: str | None) -> str | None:
        return v.lower() if v else v

    @model_validator(mode="after")
    def _some(self):
        if not (self.fill or self.color or self.bold or self.icon):
            raise ValueError("En az bir biçim seçilmeli (zemin, yazı rengi, kalın ya da ikon)")
        return self


class RuleSpec(BaseModel):
    """Sorguda kural: yalnız alan ve koşul (biçim istemcide)."""
    field: str
    condition: RuleCondition


class FormatRule(RuleSpec):
    """Görünümde ve Excel'e aktarımda kural: sıra listedeki sıradır (üstteki kazanır)."""
    id: str = Field(min_length=1, max_length=40)
    enabled: bool = True
    format: RuleFormat


class GroupKeyItem(BaseModel):
    """Grubun satırları (K-90): alan = değer; değer null ise boş grup."""
    field: str
    value: Any = None


class QueryRequest(BaseModel):
    fields: list[str] | None = None
    sort: list[SortItem] = []
    filters: list[FilterItem] = []
    offset: int = Field(default=0, ge=0)
    limit: int | None = Field(default=None, ge=1, le=MAX_LIMIT)  # boşsa ListChunkSize
    group_key: list[GroupKeyItem] = []
    rules: list[RuleSpec] = Field(default=[], max_length=MAX_RULES)  # satır başına _rules (K-95)


# Ara toplam türleri (K-90, docs/08): toplam, ortalama (boşlar / sıfırlar hariç), ağırlıklı ortalama, en küçük,
# en büyük, dolu satır sayısı, yok.
AGG_FNS = ("sum", "avg", "avg_nonzero", "wavg", "min", "max", "count", "none")
AggFn = Literal["sum", "avg", "avg_nonzero", "wavg", "min", "max", "count", "none"]


class AggSpec(BaseModel):
    fn: AggFn
    weight: str | None = None  # yalnız wavg: ağırlık alanı (sayı)


class GroupsRequest(BaseModel):
    group_by: list[str] = Field(min_length=1, max_length=4)
    fields: list[str] | None = None  # görünen kolonlar: varsayılan ara toplamlar yalnız bunlar için
    aggregates: dict[str, AggSpec] | None = None  # verilirse tam bu türler (görünen kolonlar için istemci gönderir)
    filters: list[FilterItem] = []
    sort: list[SortItem] = []


class IdsRequest(BaseModel):
    filters: list[FilterItem] = []


class ValuesRequest(BaseModel):
    field: str
    search: str = ""
    filters: list[FilterItem] = []


# --- Grafik (K-178, docs/08 "Grafik") ------------------------------------------------------------------------------

ChartBucket = Literal["day", "week", "month", "quarter", "year"]  # saat kırılımı yok
ChartFn = Literal["sum", "avg", "min", "max", "count"]
CHART_MAX_SERIES = 8
CHART_MAX_REF_LINES = 6
CHART_MAX_CATEGORIES = 30  # kategori ekseninde gösterilecek değer sayısının üst sınırı ve varsayılanı
COLOR = r"^#[0-9A-Fa-f]{6}$"


class ChartAxis(BaseModel):
    field: str
    bucket: ChartBucket | None = None  # tarih alanında zorunlu, kategori alanında yok


class ChartSeriesSpec(BaseModel):
    id: str = Field(min_length=1, max_length=20)
    field: str | None = None  # "count" (satır sayısı) alan istemez
    fn: ChartFn


class ChartRequest(BaseModel):
    filters: list[FilterItem] = []
    x: ChartAxis
    split: str | None = None
    order: Literal["value", "name"] = "value"  # kategori ekseninde; tarih ekseni eskiden yeniye
    series: list[ChartSeriesSpec] = Field(min_length=1, max_length=CHART_MAX_SERIES)
    limit: int = Field(default=CHART_MAX_CATEGORIES, ge=1, le=CHART_MAX_CATEGORIES)  # kategori ekseninde en büyük kaç değer; kalanı "Diğer"
    scenario_id: int | None = None  # hafta başlangıcı bu senaryonun parametresinden (verilmezse kullanıcının seçili senaryosu)


class ChartLabels(BaseModel):
    show: bool = False
    decimals: int = Field(default=0, ge=0, le=4)
    zero: bool = False  # "Sıfır değerleri göster": kapalıyken 0 değerinin etiketi çıkmaz


class ChartThreshold(BaseModel):
    value: float
    color: str = Field(pattern=COLOR)
    line: bool = False  # "Eşik çizgisini göster": kapalıyken yalnız eşik üstü renk uygulanır


class ChartSeries(ChartSeriesSpec):
    """Görünümdeki seri: toplama ve görünüş ayarları."""
    type: Literal["bar", "line", "smooth", "step", "area"] = "bar"  # smooth: eğimli (monoton) çizgi
    axis: Literal["primary", "secondary"] = "primary"
    color: str | None = Field(default=None, pattern=COLOR)  # boşsa paletten sırayla
    labels: ChartLabels = ChartLabels()
    threshold: ChartThreshold | None = None


class ChartBars(BaseModel):
    mode: Literal["group", "stack", "percent"] = "group"
    horizontal: bool = False
    totals: bool = False  # yığılmışta çubuğun üstünde toplam
    width: Literal["thin", "medium", "thick"] = "medium"  # çubuk genişliği: bütün çubuk serileri için ortak


class ChartValueAxis(BaseModel):
    title: str = Field(default="", max_length=60)
    min: float | None = None
    max: float | None = None
    unit: str = Field(default="", max_length=20)
    grid: bool = True


class ChartCategoryAxis(BaseModel):
    title: str = Field(default="", max_length=60)


class ChartAxes(BaseModel):
    x: ChartCategoryAxis = ChartCategoryAxis()
    primary: ChartValueAxis = ChartValueAxis()
    secondary: ChartValueAxis = ChartValueAxis(grid=False)


class ChartRefLine(BaseModel):
    id: str = Field(min_length=1, max_length=20)
    kind: Literal["value", "avg", "min", "max"]
    value: float | None = None   # kind "value"
    series: str | None = None    # öteki türlerde serinin kimliği
    name: str = Field(default="", max_length=40)
    color: str | None = Field(default=None, pattern=COLOR)
    show_name: bool = True
    show_value: bool = True


class ChartLegend(BaseModel):
    show: bool = True
    position: Literal["top", "bottom", "right"] = "top"


class ChartDefinition(BaseModel):
    """Tablonun grafiği, görünümün parçası (K-178). Anahtar yoksa grafik kapalıdır."""
    v: Literal[1] = 1
    open: bool = True
    layout: Literal["split", "full"] = "split"
    height: float = Field(default=0.45, ge=0.15, le=0.85)  # bölünmüş görünümde grafiğin payı
    x: ChartAxis
    split: str | None = None
    order: Literal["value", "name"] = "value"
    limit: int = Field(default=CHART_MAX_CATEGORIES, ge=1, le=CHART_MAX_CATEGORIES)
    series: list[ChartSeries] = Field(min_length=1, max_length=CHART_MAX_SERIES)
    bars: ChartBars = ChartBars()
    axes: ChartAxes = ChartAxes()
    ref_lines: list[ChartRefLine] = Field(default=[], max_length=CHART_MAX_REF_LINES)
    legend: ChartLegend = ChartLegend()
    title: str = Field(default="", max_length=80)
    title_align: Literal["left", "center", "right"] = "left"
    title_size: Literal["small", "medium", "large"] = "medium"


# --- Kayıtlı görünüm (K-89, docs/08 "Görünümler") ---------------------------------------------------------------

MIN_WIDTH_REM, MAX_WIDTH_REM = 4.0, 60.0


class ViewColumn(BaseModel):
    field: str
    width: float | None = Field(default=None, ge=MIN_WIDTH_REM, le=MAX_WIDTH_REM)  # rem; boşsa tipin varsayılanı


class ViewDefinition(BaseModel):
    """Görünüm içeriği, sürüm 1. Göreli tarih filtresi göreli saklanır (op relative), tarih değil."""
    v: Literal[1] = 1
    columns: list[ViewColumn] = Field(min_length=1)
    pinned: int = Field(default=0, ge=0)
    sort: list[SortItem] = []
    filters: list[FilterItem] = []
    group_by: list[str] = Field(default=[], max_length=4)
    aggregates: dict[str, AggSpec] = {}  # varsayılandan farklı seçilen ara toplam türleri (K-90)
    rules: list[FormatRule] = Field(default=[], max_length=MAX_RULES)  # koşullu biçim, sıralı (K-95)
    chart: ChartDefinition | None = None  # tablonun grafiği (K-178); yoksa grafik kapalı


class ViewCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    is_shared: bool = False
    definition: ViewDefinition


class ViewUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    is_shared: bool | None = None
    definition: ViewDefinition | None = None


class StandardUpdate(BaseModel):
    """Şirket Standart'ı (K-162)."""
    definition: ViewDefinition


class DefaultViewRequest(BaseModel):
    view_id: int | None = None


# --- Dışa aktarım (K-91, docs/08 "Dışa aktarım") ------------------------------------------------------------------

class ExportScope(BaseModel):
    rows: Literal["filtered", "all"] = "filtered"      # ekrandaki filtrelerle ya da filtresiz
    columns: Literal["visible", "all"] = "visible"     # görünen alanlar ya da listenin bütün alanları
    # Gruplama, ara toplamlar ve Bilgi sayfası her zaman (K-91); seçenek değil.


class ExportRequest(BaseModel):
    """Ekrandaki görünüm durumu ve kapsam."""
    fields: list[str] = Field(min_length=1)
    widths: dict[str, float] = {}                      # rem
    sort: list[SortItem] = []
    filters: list[FilterItem] = []
    group_by: list[str] = Field(default=[], max_length=4)
    aggregates: dict[str, AggSpec] | None = None
    rules: list[FormatRule] = Field(default=[], max_length=MAX_RULES)  # aktif ve görünen kolonların kuralları
    scope: ExportScope = ExportScope()
