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


@dataclass(frozen=True)
class CellFormat:
    """Hücre biçimi: zemin, yazı rengi (#rrggbb), kalın, ikon. İkonun Excel karşılığı 1.6'da (U-24); şimdi yazılmaz."""
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
