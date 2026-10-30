"""Biçim tanımı (K-92; U-19, U-24'e hazırlık): Excel'deki sayı/tarih biçim kodları ve hücre biçimleri.

Sayı ve tarih kuralları kolon tanımından gelir (K-87, K-88): ekran (format.ts) ve Excel aynı tanımı okur. Renkler tokens.css'te
tek yerde (K-85); derlemede app/shared/design-tokens.json üretilir, buradan okunur. Hücre biçimi tek yapıdır (CellFormat);
1.6'da kullanıcının koşullu biçimleri (U-24) de bu yapıya çevrilip aynı yazıcıdan geçer.
"""
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

TOKENS = Path(__file__).resolve().parents[3] / "app" / "shared" / "design-tokens.json"

DATE_FORMAT = "dd.mm.yyyy"
DATETIME_FORMAT = "dd.mm.yyyy hh:mm"
DEFAULT_UNIT_DECIMALS = 2  # birim bilinmiyorsa (docs/02 UnitOfMeasure.Decimals)
# Koşullu biçim ikonları (K-96): ekranda lucide ikonu, Excel'de biçim kodunun önündeki karakter (değer sayı/tarih kalır).
# Karakterler birbirinden ayırt edilir (1.6 demosu): ok ↑ / ↓, uyarı ▲ (dolu üçgen).
ICON_CHARS = {"arrow_up": "↑", "arrow_down": "↓", "dot": "●", "warning": "▲", "check": "✓", "cross": "✗",
              "flag": "⚑", "star": "★"}


@dataclass(frozen=True)
class CellFormat:
    """Hücre biçimi: zemin, yazı rengi (#rrggbb), kalın, ikon (ICON_CHARS adı; Excel'de biçim kodu öneki)."""
    fill: str | None = None
    color: str | None = None
    bold: bool = False
    icon: str | None = None

    def merged(self, other: "CellFormat | None") -> "CellFormat":
        """Üstüne başka biçim koyar (ör. 1.6'da kural biçimi); boş özellikler alttakini korur."""
        if other is None:
            return self
        return CellFormat(fill=other.fill or self.fill, color=other.color or self.color,
                          bold=self.bold or other.bold, icon=other.icon or self.icon)


@lru_cache
def tokens() -> dict[str, str]:
    """design-tokens.json'daki renkler (ad → #rrggbb)."""
    return json.loads(TOKENS.read_text(encoding="utf-8"))["colors"]


def color(name: str) -> str:
    return tokens()[name]


def number_format(decimals: int) -> str:
    """Excel sayı biçim kodu: binlik ayırıcı ve sabit ondalık. Excel Türkçe bölgede 1.234,5 gösterir."""
    return "#,##0" + ("." + "0" * decimals if decimals > 0 else "")


def column_number_format(col: dict, unit_decimals: int | None = None) -> str | None:
    """Kolonun Excel biçim kodu; sayı dışı alanlarda tarih biçimi ya da None (metin)."""
    kind = col["type"]
    if kind == "integer":
        return number_format(0)
    if kind == "number":
        if col.get("decimals_from_unit"):
            return number_format(DEFAULT_UNIT_DECIMALS if unit_decimals is None else unit_decimals)
        return number_format(col.get("decimals") or 0)
    if kind == "date":
        return DATE_FORMAT
    if kind == "datetime":
        return DATETIME_FORMAT
    return None


def with_icon(number_format: str | None, icon: str | None) -> str | None:
    """İkonlu biçim kodu (K-96): ikon değerin ters tarafında, doldurma boşluğuyla (* ) hücre kenarına itilir.
    Sayıda başta: "▲"* #,##0; metin ve tarihte sonda: @* "▲", dd.mm.yyyy* "▲". Değer sayı ya da tarih kalır."""
    if not icon:
        return number_format
    char = f'"{ICON_CHARS[icon]}"'
    if number_format is None or number_format in (DATE_FORMAT, DATETIME_FORMAT):
        return f"{number_format or '@'}* {char}"
    return f"{char}* {number_format}"


# --- Okunurluk (K-96): ui/contrast.ts ile aynı hesap; yazı rengi seçilmemişse zemine göre okunur yazı rengi ---

READABLE = 4.5


def _channels(hex_color: str) -> list[int]:
    return [int(hex_color[i:i + 2], 16) for i in (1, 3, 5)]


def luminance(hex_color: str) -> float:
    c = [x / 255 for x in _channels(hex_color)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def mix(hex_color: str, amount: float) -> str:
    """Beyaza (amount > 0) ya da siyaha (amount < 0) doğru karıştırır (ui/contrast.ts mix ile aynı, aynı yuvarlama)."""
    def one(x: int) -> int:
        v = x + (255 - x) * amount if amount >= 0 else x * (1 + amount)
        return max(0, min(255, int(v + 0.5)))  # JS Math.round (pozitif sayılarda yarım yukarı)
    return "#" + "".join(f"{one(x):02x}" for x in _channels(hex_color))


def suggest_text(fill: str, default_text: str) -> str:
    """Zemine okunur yazı rengi: varsayılan yazı rengi ya da beyazdan okunuru (en yüksek kontrast), ikisi de değilse
    zeminin tonundan koyulaştırılmış ya da açılmış ilk okunur renk."""
    ok = [c for c in (default_text, "#ffffff") if contrast(c, fill) >= READABLE]
    if ok:
        return max(ok, key=lambda c: contrast(c, fill))
    dark = luminance(fill) > 0.18
    for i in range(10, 20):  # %50 … %95, %5 adım (ui/contrast.ts ile aynı)
        c = mix(fill, -i / 20 if dark else i / 20)
        if contrast(c, fill) >= READABLE:
            return c
    return "#000000" if dark else "#ffffff"


def rule_format(fmt) -> CellFormat:
    """Kural biçimi (request.RuleFormat) → CellFormat. Yazı rengi seçilmemişse zemine göre okunur yazı rengi (K-96);
    ikonun kendi rengi Excel'e taşınmaz (hücrede tek yazı rengi)."""
    color = fmt.color or (suggest_text(fmt.fill, color_of("text")) if fmt.fill else None)
    return CellFormat(fill=fmt.fill, color=color, bold=fmt.bold, icon=fmt.icon)


def color_of(name: str) -> str:
    return tokens()[name]


def aggregate_number_format(col: dict, fn: str, unit_decimals: int | None) -> str:
    """Ara toplamın biçimi (K-90): sayı ondalıksız, ortalamalar kolonun ondalığından bir fazla."""
    if fn == "count":
        return number_format(0)
    if col.get("decimals_from_unit"):
        base = DEFAULT_UNIT_DECIMALS if unit_decimals is None else unit_decimals
    else:
        base = col.get("decimals") or 0
    return number_format(base + 1 if fn in ("avg", "avg_nonzero", "wavg") else base)


def header_format() -> CellFormat:
    return CellFormat(fill=color("table-head-bg"), color=color("table-head-text"), bold=True)


def group_format(depth: int) -> CellFormat:
    """Grup başlık satırı: 1. düzey koyu ton ve kalın, alt düzeyler açık ton (K-85)."""
    return CellFormat(fill=color("table-group-1-bg" if depth == 0 else "table-group-2-bg"), color=color("text"), bold=depth == 0)


def occupancy_format(level: str) -> CellFormat:
    """Doluluk hücresi (K-85): low, normal, high, risk, over; ekrandaki .sc-occ--* ile aynı değişkenler."""
    return CellFormat(fill=color(f"occ-{level}-bg"), color=color(f"occ-{level}-text"), bold=level == "over")
