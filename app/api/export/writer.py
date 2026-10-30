"""Excel yazıcısı (K-91, K-92): XlsxWriter (BSD-2-Clause, saf Python) sabit bellek kipinde (constant_memory).

Satırlar geldikçe diske yazılır; 500.000 satırda bellek sabit. Veri sayfası: başlık dondurulur, otomatik filtre açık,
kolon genişlikleri ekrandan; grup başlık satırları ekrandaki tonlarla, ara toplamlar değer olarak (formül değil). Bilgi
sayfası: kaynak, filtreler, kim, ne zaman, sürüm. Her hücre CellFormat, sayı biçim kodu ve girintiyle tek biçim
önbelleğinden yazılır; 1.6'da koşullu biçimler (U-24) hücreye aynı yoldan uygulanır (cell_format).

Metin her zaman metin olarak yazılır: "=" ile başlayan değer formüle, adres bağlantıya çevrilmez (formül enjeksiyonu yok).
"""
from collections.abc import Callable, Mapping
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import BinaryIO

from xlsxwriter import Workbook

from . import formats
from .formats import CellFormat

REM_PX = 13          # standart yazı boyutunda 1rem (U-23); Excel çıktısı yazı boyutundan etkilenmez
EXCEL_CHAR_PX = 7    # Excel genişlik birimi ≈ 7 px (varsayılan yazı tipi)
DEFAULT_WIDTH_CHARS = 14

YES, NO = "Evet", "Hayır"

WORKBOOK_OPTIONS = {
    "constant_memory": True,        # satır satır diske; bellek satır sayısından bağımsız
    "strings_to_formulas": False,   # "=…" metni formül olmaz
    "strings_to_urls": False,       # adres metni bağlantı olmaz
    "strings_to_numbers": False,
}


def width_chars(rem: float | None) -> float:
    return DEFAULT_WIDTH_CHARS if rem is None else round(rem * REM_PX / EXCEL_CHAR_PX, 1)


def local_datetime(v: datetime) -> datetime:
    """Veritabanındaki zaman UTC (saat dilimsiz); Excel'e yerel saat yazılır."""
    return v.replace(tzinfo=timezone.utc).astimezone().replace(tzinfo=None)


class _Formats:
    """(CellFormat, sayı biçimi, girinti) → XlsxWriter biçimi; aynı biçim bir kez üretilir."""

    def __init__(self, wb: Workbook):
        self.wb = wb
        self.cache: dict[tuple, object] = {}

    def get(self, fmt: CellFormat | None, number_format: str | None, indent: int = 0):
        key = (fmt, number_format, indent)
        if key not in self.cache:
            props: dict = {}
            if fmt is not None:
                if fmt.fill:
                    props.update(pattern=1, bg_color=fmt.fill)
                if fmt.color:
                    props["font_color"] = fmt.color
                if fmt.bold:
                    props["bold"] = True
            number_format = formats.with_icon(number_format, fmt.icon if fmt is not None else None)
            if number_format:
                props["num_format"] = number_format
            if indent:
                props["indent"] = indent
            self.cache[key] = self.wb.add_format(props) if props else None
        return self.cache[key]


class XlsxWriter:
    """Kolonlar (liste kolon tanımları, K-87) ve genişliklerle (rem) veri sayfası; Bilgi sayfası.

    target: dosya yolu ya da yazılabilir ikili akış. Satırlar geldikçe yazılır; save() dosyayı kapatır.
    """

    def __init__(self, target: str | BinaryIO, columns: list[dict], widths: Mapping[str, float | None] | None = None,
                 cell_format: Callable[[dict, Mapping, object], CellFormat | None] | None = None):
        self.columns = columns
        self.wb = Workbook(target, WORKBOOK_OPTIONS)
        self.ws = self.wb.add_worksheet("Veri")
        self.formats = _Formats(self.wb)
        self.rows = 0
        self.info: list[tuple[str, str]] | None = None
        # 1.6 (U-24): satır ve değere göre ek biçim; 1.5'te yok
        self.cell_format = cell_format
        # Kolon başına sabit veri biçimi (birim ondalığına bağlı olanlar satırda seçilir)
        self._unit_cols = [bool(c.get("decimals_from_unit")) for c in columns]
        self._number_formats = [formats.column_number_format(c) for c in columns]
        widths = widths or {}
        for i, c in enumerate(columns):
            self.ws.set_column(i, i, width_chars(widths.get(c["field"])))
        self.ws.freeze_panes(1, 0)

    # --- hücreler ---------------------------------------------------------------------------------------------

    def _write(self, row: int, col: int, value, style) -> None:
        if value is None:
            if style is not None:
                self.ws.write_blank(row, col, None, style)
        elif isinstance(value, bool):
            self.ws.write_string(row, col, YES if value else NO, style)
        elif isinstance(value, str):
            self.ws.write_string(row, col, value, style)
        elif isinstance(value, (datetime, date)):
            self.ws.write_datetime(row, col, value, style)
        else:
            self.ws.write_number(row, col, value, style)

    # --- satırlar ---------------------------------------------------------------------------------------------

    def header(self) -> None:
        style = self.formats.get(formats.header_format(), None)
        for i, c in enumerate(self.columns):
            self.ws.write_string(self.rows, i, c["label"], style)
        self.rows += 1

    @staticmethod
    def value(col: dict, v):
        """Ekrandaki değerin Excel karşılığı: sayı sayı, tarih tarih, evet/hayır yazıyla (K-92)."""
        if v is None or v == "":
            return None
        kind = col["type"]
        if kind in ("number", "integer"):
            if kind == "integer":
                return int(v)
            return float(v) if isinstance(v, (Decimal, int, float)) else v
        if kind == "bool":
            return YES if v else NO
        if kind == "datetime" and isinstance(v, datetime):
            return local_datetime(v)
        if kind == "date" and isinstance(v, datetime):
            return v.date()
        return v

    def data_row(self, row: Mapping, unit_decimals: int | None = None, indent: int = 0) -> None:
        r = self.rows
        for i, col in enumerate(self.columns):
            value = self.value(col, row.get(col["field"]))
            fmt = self.cell_format(col, row, value) if self.cell_format else None
            nf = formats.column_number_format(col, unit_decimals) if self._unit_cols[i] else self._number_formats[i]
            self._write(r, i, value, self.formats.get(fmt, nf, indent if i == 0 else 0))
        self.rows += 1

    def group_row(self, label: str, depth: int, count: int, aggregates: Mapping[str, float | None],
                  fns: Mapping[str, str], unit_decimals: Mapping[str, int], count_text: str) -> None:
        """Grup başlığı: ilk kolonda ad ve satır sayısı (düzeye göre girintili), ara toplamlar kendi kolonlarında."""
        fmt = formats.group_format(depth)
        r = self.rows
        for i, col in enumerate(self.columns):
            if i == 0:
                self.ws.write_string(r, 0, f"{label} · {count_text}", self.formats.get(fmt, None, depth))
                continue
            f = col["field"]
            v = aggregates.get(f) if f in fns else None
            nf = formats.aggregate_number_format(col, fns[f], unit_decimals.get(f)) if v is not None else None
            self._write(r, i, v, self.formats.get(fmt, nf))
        self.rows += 1

    def info_sheet(self, pairs: list[tuple[str, str]]) -> None:
        """Bilgi sayfası kaydederken yazılır (sabit bellek kipinde sayfalar sırayla yazılır)."""
        self.info = pairs

    # --- kaydetme ---------------------------------------------------------------------------------------------

    def save(self) -> None:
        if self.columns:
            self.ws.autofilter(0, 0, max(0, self.rows - 1), len(self.columns) - 1)
        if self.info is not None:
            ws = self.wb.add_worksheet("Bilgi")
            ws.set_column(0, 0, 22)
            ws.set_column(1, 1, 90)
            key = self.formats.get(CellFormat(bold=True, color=formats.header_format().color), None)
            ws.write_string(0, 0, "Alan")
            ws.write_string(0, 1, "Değer")
            for n, (k, v) in enumerate(self.info, start=1):
                ws.write_string(n, 0, k, key)
                ws.write_string(n, 1, v)
        self.wb.close()
