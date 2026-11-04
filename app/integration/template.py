"""Excel şablonu üreticisi (fonksiyon 02, K-110). Veritabanı bilmez: etiketleri çağıran verir (API, kirli Excel).

1. satır teknik ad, veri 2. satırdan; zorunlu alanın başlığı koyu. Zorlama yok (K-58): açılır liste ve Excel doğrulaması konmaz,
değerler Açıklama sayfasında yazar. Metin her zaman metin yazılır (formül enjeksiyonu yok, K-91).
"""
from collections.abc import Iterable, Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import BinaryIO

from xlsxwriter import Workbook

from app import __version__
from app.api.export import formats
from app.api.export.writer import WORKBOOK_OPTIONS, _Formats

from .contract import FIRST_DATA_ROW, Entity, TemplateField, fields

NOTES_SHEET, VERSION_SHEET = "Açıklama", "_Surum"
NOTES_INTRO = "Koyu başlıklı alanlar zorunludur."
VALUES_NOTE = "ERP'deki farklı değerler veri kuralıyla çevrilir."
NOTE_HEADERS = ("Alan", "Etiket", "Açıklama", "Tip", "Boş bırakılırsa", "Smartchain değerleri", "Örnek")
NOTE_WIDTHS = (26, 30, 56, 20, 28, 52, 20)
NOTE_HEADER_ROW = 1
COLUMN_WIDTH = 24
NUMBER_FORMATS = {"text": "@", "date": formats.DATE_FORMAT, "datetime": formats.DATETIME_FORMAT, "integer": "0"}


def smartchain_values(field: TemplateField) -> str:
    """Değer listesi ve çevrilme notu; referansta hangi tablonun kodu."""
    if field.values:
        return f"{', '.join(field.values)}. {VALUES_NOTE}"
    return field.ref_text


def _write_cell(ws, row: int, col: int, value, style) -> None:
    if value is None or value == "":
        return
    if isinstance(value, bool):
        ws.write_number(row, col, int(value), style)
    elif isinstance(value, str):
        ws.write_string(row, col, value, style)
    elif isinstance(value, (datetime, date)):
        ws.write_datetime(row, col, value, style)
    elif isinstance(value, (int, float, Decimal)):
        ws.write_number(row, col, value, style)
    else:
        ws.write_string(row, col, str(value), style)


def _write_notes(wb: Workbook, found: list[TemplateField], header, styles: Mapping[str, object]) -> None:
    ws = wb.add_worksheet(NOTES_SHEET)
    wrap = wb.add_format({"text_wrap": True, "valign": "top"})
    example_styles = {kind: wb.add_format({"num_format": fmt, "valign": "top", "align": "left"}) for kind, fmt in NUMBER_FORMATS.items() if kind != "text"}
    ws.write_string(0, 0, NOTES_INTRO)
    for i, (title, width) in enumerate(zip(NOTE_HEADERS, NOTE_WIDTHS)):
        ws.write_string(NOTE_HEADER_ROW, i, title, header)
        ws.set_column(i, i, width)
    for row, f in enumerate(found, NOTE_HEADER_ROW + 1):
        for col, value in enumerate((f.name, f.label, f.description, f.type_text, f.blank, smartchain_values(f))):
            if value:
                ws.write_string(row, col, value, wrap)
        _write_cell(ws, row, len(NOTE_HEADERS) - 1, f.example, example_styles.get(f.kind, wrap))
    ws.freeze_panes(NOTE_HEADER_ROW + 1, 0)


def write_template(target: str | BinaryIO, entity: Entity, labels: Mapping[str, str] | None = None,
                   extra_info: Iterable[tuple[str, object]] = (), rows: Iterable[Mapping] = ()) -> list[TemplateField]:
    """Şablonu yazar, alanlarını döndürür. rows: kirli Excel'in satırları; hatalı değer de yazılır."""
    found = fields(entity.table, labels)
    wb = Workbook(target, {**WORKBOOK_OPTIONS, "constant_memory": False})
    styles = _Formats(wb)
    required_header = styles.get(formats.template_header_format(required=True), None)
    other_header = styles.get(formats.template_header_format(required=False), None)
    column_styles = {kind: wb.add_format({"num_format": fmt}) for kind, fmt in NUMBER_FORMATS.items()}

    ws = wb.add_worksheet(entity.name)
    _write_notes(wb, found, styles.get(formats.header_format(), None), column_styles)
    for col, f in enumerate(found):
        ws.set_column(col, col, COLUMN_WIDTH, column_styles.get(f.kind))
        ws.write_string(0, col, f.name, required_header if f.required else other_header)
    ws.freeze_panes(FIRST_DATA_ROW - 1, 0)
    for row, data in enumerate(rows, FIRST_DATA_ROW - 1):
        for col, f in enumerate(found):
            _write_cell(ws, row, col, data.get(f.name), column_styles.get(f.kind))

    info = wb.add_worksheet(VERSION_SHEET)
    info.set_column(0, 1, 28)
    pairs = [("Tablo", entity.table), ("Sürüm", entity.version), ("İlk veri satırı", FIRST_DATA_ROW), ("Smartchain", __version__), *extra_info]
    for row, (key, value) in enumerate(pairs):
        info.write_string(row, 0, key)
        _write_cell(info, row, 1, value, None)
    info.hide()
    ws.activate()
    wb.close()
    return found
