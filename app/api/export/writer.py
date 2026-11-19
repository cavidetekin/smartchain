"""Excel yazıcısı (K-91, K-92): XlsxWriter (BSD-2-Clause, saf Python) sabit bellek kipinde (constant_memory).

Satırlar geldikçe diske yazılır; 500.000 satırda bellek sabit. Veri sayfası: başlık dondurulur, otomatik filtre açık,
kolon genişlikleri ekrandan; grup başlık satırları ekrandaki tonlarla, ara toplamlar değer olarak (formül değil). Bilgi
sayfası: kaynak, filtreler, kim, ne zaman, sürüm. Her hücre CellFormat, sayı biçim kodu ve girintiyle tek biçim
önbelleğinden yazılır; 1.6'da koşullu biçimler (U-24) hücreye aynı yoldan uygulanır (cell_format).

Metin her zaman metin olarak yazılır: "=" ile başlayan değer formüle, adres bağlantıya çevrilmez (formül enjeksiyonu yok).
"""
import io
from collections.abc import Callable, Iterable, Mapping
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


def write_info(wb: Workbook, fmts: "_Formats", pairs: list[tuple[str, str]]) -> None:
    """Bilgi sayfası: kaynak, filtreler, kim, ne zaman, sürüm."""
    ws = wb.add_worksheet("Bilgi")
    ws.set_column(0, 0, 22)
    ws.set_column(1, 1, 90)
    key = fmts.get(CellFormat(bold=True, color=formats.header_format().color), None)
    ws.write_string(0, 0, "Alan")
    ws.write_string(0, 1, "Değer")
    for n, (k, v) in enumerate(pairs, start=1):
        ws.write_string(n, 0, k, key)
        ws.write_string(n, 1, v)


def write_image(wb: Workbook, image: bytes) -> None:
    """"Grafik" sayfası (K-179): grafik görsel olarak (PNG, ekrandaki ayarla; 2× çözünürlük yarı ölçekle yerleşir). Düzenlenebilir Excel grafiği yok."""
    ws = wb.add_worksheet("Grafik")
    ws.hide_gridlines(2)
    ws.insert_image(1, 1, "grafik.png", {"image_data": io.BytesIO(image), "x_scale": 0.5, "y_scale": 0.5})


def write_chart_workbook(target: "str | BinaryIO", header: list[str], rows: Iterable[list], number_formats: list[str | None],
                         info: list[tuple[str, str]], image: bytes | None) -> int:
    """Grafiğin verisi (K-179): "Veri" (toplanmış veri ya da dağılımın noktaları), "Bilgi" ve görsel verildiyse "Grafik" sayfası.
    Sayılar sayı, dönemler tarih; metin her zaman metin. Yazılan satır sayısını döndürür."""
    wb = Workbook(target, WORKBOOK_OPTIONS)
    ws = wb.add_worksheet("Veri")
    fmts = _Formats(wb)
    head = fmts.get(formats.header_format(), None)
    for i, title in enumerate(header):
        ws.set_column(i, i, 20)
        ws.write_string(0, i, title, head)
    ws.freeze_panes(1, 0)
    styles = [fmts.get(None, nf) for nf in number_formats]
    day = fmts.get(None, "dd.mm.yyyy")
    written = 0
    for r, row in enumerate(rows, start=1):
        for c, v in enumerate(row):
            if v is None:
                continue
            if isinstance(v, str):
                ws.write_string(r, c, v)
            elif isinstance(v, (datetime, date)):
                ws.write_datetime(r, c, v, day)
            else:
                ws.write_number(r, c, v, styles[c])
        written += 1
    if header:
        ws.autofilter(0, 0, written, len(header) - 1)
    write_info(wb, fmts, info)
    if image is not None:
        write_image(wb, image)
    wb.close()
    return written


def write_pivot_workbook(target: "str | BinaryIO", model: dict, info: list[tuple[str, str]]) -> int:
    """Pivot ekrandaki şekliyle (K-183): "Pivot" ve "Bilgi" sayfaları. Katlı başlıklar birleştirilmiş hücrelerle; satır başlıkları ve başlık
    satırları dondurulur; toplamlar kalın; en dıştaki sütun gruplarının solunda dikey çizgi; kural dolgusu; tarih ve yüzde biçimleri.

    model: {row_labels, column_labels, values: [{name, num_format, date}], values_on, header: [[(metin, colspan, rowspan, grup başı)]],
    columns: [{total, start}], rows: [{labels, total, cells[değer][sütun], formats{değer: [CellFormat|None]}}]}.
    Birleştirme satır sırası dışı yazdığı için sabit bellek kipi kullanılmaz (hücre sayısı çağıranda sınırlıdır). Yazılan satır sayısı döner."""
    wb = Workbook(target, {k: v for k, v in WORKBOOK_OPTIONS.items() if k != "constant_memory"})
    ws = wb.add_worksheet("Pivot")
    head = formats.header_format()
    cache: dict[tuple, object] = {}

    def fmt(bold=False, fill=None, color=None, num=None, left=False, header=False, align=None, top=False, over=False):
        key = (bold, fill, color, num, left, header, align, top, over)
        if key not in cache:
            spec: dict = {}
            if bold:
                spec["bold"] = True
            if fill:
                spec.update(bg_color=fill, pattern=1)
            if color:
                spec["font_color"] = color
            if num:
                spec["num_format"] = num
            if header:
                spec.update(bg_color=head.fill, font_color=head.color, bold=True, border=1, border_color=head.fill, valign="vcenter")
            if left:  # kenarlığın tamamından sonra yazılır (biçim anahtarları sırayla uygulanır); başlıkta çizgi yazı renginde ki zeminde görünsün
                spec.update(left=2, left_color=head.color if header else head.fill)
            if align:
                spec["align"] = align
            if top:
                spec["valign"] = "top"
            if over:  # en dıştaki satır grubunun ilk satırı: üstünde ince kenarlık (ekrandaki 1 px çizgi, K-186)
                spec.update(top=1, top_color=head.fill)
            cache[key] = wb.add_format(spec)
        return cache[key]

    values, on_rows = model["values"], model["values_on"] == "rows"
    R, V = len(model["row_labels"]), len(values)
    left_cols = R + (1 if on_rows else 0)
    span = 1 if on_rows else V
    levels = model["header"]                     # sütun alanı katları (yoksa boş)
    ws.set_column(0, max(left_cols - 1, 0), 22)
    for j, rem in enumerate(model.get("widths") or []):   # satır başlığı kolonları ekrandaki genişlikte (K-186)
        if rem is not None:
            ws.set_column(j, j, width_chars(rem))
    ws.set_column(left_cols, left_cols + len(model["columns"]) * span, 16)
    r = 0
    for level in levels:
        c = left_cols
        if r == 0 and left_cols:
            text = " › ".join(model["column_labels"])
            if len(levels) > 1 or left_cols > 1:
                ws.merge_range(0, 0, len(levels) - 1, left_cols - 1, text, fmt(header=True, align="left"))
            else:
                ws.write_string(0, 0, text, fmt(header=True, align="left"))
        occupied = model["occupied"][r]          # üst kattan uzanan (rowspan) hücrelerin kapladığı sütunlar
        for text, colspan, rowspan, start in level:
            while c in occupied:
                c += 1
            style = fmt(header=True, left=start, align="center")
            if colspan > 1 or rowspan > 1:
                ws.merge_range(r, c, r + rowspan - 1, c + colspan - 1, text, style)
            else:
                ws.write_string(r, c, text, style)
            c += colspan
        r += 1
    for j, label in enumerate(model["row_labels"]):
        ws.write_string(r, j, label, fmt(header=True, align="left"))
    if on_rows:
        ws.write_string(r, R, "Değer", fmt(header=True, align="left"))
    for s, col in enumerate(model["columns"]):
        for k in range(span):
            text = "" if on_rows else values[k]["name"]
            ws.write_string(r, left_cols + s * span + k, text, fmt(header=True, left=col["start"] and k == 0, align="right"))
    header_rows = r + 1
    ws.freeze_panes(header_rows, left_cols)
    written = 0
    lines = V if on_rows else 1                  # bir görüntü satırının Excel satırı sayısı
    for row in model["rows"]:
        for sub in range(lines):
            y = header_rows + written
            over = bool(row.get("group_start")) and sub == 0
            for j, label in enumerate(row["labels"]):
                if sub:
                    continue
                height = (row.get("spans") or [1] * R)[j] * lines   # satır alanı hücresi grubu boyunca birleşir, değer üstte (K-186)
                if height > 1:
                    ws.merge_range(y, j, y + height - 1, j, label, fmt(bold=row["total"], top=True, over=over))
                elif label or over:
                    ws.write_string(y, j, label, fmt(bold=row["total"], over=over))
            own = values[sub].get("format") if on_rows else None   # değerin satır biçimi (K-186)
            if on_rows:
                ws.write_string(y, R, values[sub]["name"], fmt(bold=row["total"] or bool(own and own.bold), fill=own.fill if own else None,
                                                             color=own.color if own else None, over=over))
            for s, col in enumerate(model["columns"]):
                for k in ([sub] if on_rows else range(V)):
                    x = left_cols + s * span + (0 if on_rows else k)
                    value = row["cells"][k][s]
                    rule = (row.get("formats", {}).get(k) or [None] * len(model["columns"]))[s]
                    base = values[k].get("format")
                    rule = base.merged(rule) if base else rule     # kural tutan hücrede kuralın biçimi kazanır
                    bold = row["total"] or col["total"] or bool(rule and rule.bold)
                    left = col["start"] and (on_rows or k == 0)
                    fill, color = (rule.fill, rule.color) if rule else (None, None)
                    if value is None:
                        if left or fill or over:
                            ws.write_blank(y, x, None, fmt(fill=fill, left=left, over=over))
                    elif isinstance(value, str):     # karışık birim
                        ws.write_string(y, x, value, fmt(bold=bold, fill=fill, color=color, left=left, align="right", over=over))
                    elif isinstance(value, (datetime, date)):
                        ws.write_datetime(y, x, value, fmt(bold=bold, fill=fill, color=color, left=left, num=values[k]["num_format"], over=over))
                    else:
                        ws.write_number(y, x, value, fmt(bold=bold, fill=fill, color=color, left=left, num=row["num_formats"][k][s], over=over))
            written += 1
    write_info(wb, _Formats(wb), info)
    wb.close()
    return written


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
        self.image: bytes | None = None  # "Grafiği ekle" (K-179): "Grafik" sayfası
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

    def data_row(self, row: Mapping, unit_decimals: int | None = None, indent: int = 0,
                 field_decimals: Mapping[str, int | None] | None = None) -> None:
        """field_decimals: alanın kendi biriminin ondalığı (ilişkili miktar alanı, K-182); verilmişse satırın biriminin yerine geçer."""
        r = self.rows
        for i, col in enumerate(self.columns):
            value = self.value(col, row.get(col["field"]))
            fmt = self.cell_format(col, row, value) if self.cell_format else None
            own = field_decimals is not None and col["field"] in field_decimals
            decimals = field_decimals[col["field"]] if own else unit_decimals
            nf = formats.column_number_format(col, decimals) if self._unit_cols[i] else self._number_formats[i]
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
            write_info(self.wb, self.formats, self.info)
        if self.image is not None:
            write_image(self.wb, self.image)
        self.wb.close()
