"""Excel şablonu dosyası (fonksiyon 02, K-110): gerçek dosya üretilip openpyxl ile okunur. Veritabanı istemez."""
import io
from datetime import date, datetime

import pytest
from openpyxl import load_workbook

from app import __version__
from app.api.export import formats
from app.integration import contract
from app.integration.contract import ENTITIES, FIRST_DATA_ROW, fields
from app.integration.template import NOTE_HEADERS, NOTES_INTRO, write_template


def build(table="Resource", labels=None, **kw):
    buffer = io.BytesIO()
    write_template(buffer, contract.entity(table), labels, **kw)
    buffer.seek(0)
    return load_workbook(buffer)


def column_of(ws, name):
    return next(c.column_letter for c in ws[1] if c.value == name)


def notes(wb) -> dict[str, dict]:
    ws = wb["Açıklama"]
    headers = [c.value for c in ws[2]]
    return {r[0]: dict(zip(headers, r)) for r in ws.iter_rows(min_row=3, values_only=True)}


def rgb(hex_color: str) -> str:
    return "FF" + hex_color.lstrip("#").upper()


@pytest.mark.parametrize("entity", ENTITIES, ids=lambda e: e.table)
def test_every_table_builds(entity):
    wb = build(entity.table)
    assert wb.sheetnames == [entity.name, "Açıklama", "_Surum"]
    assert wb["_Surum"].sheet_state == "hidden" and wb.active.title == entity.name
    ws = wb[entity.name]
    assert FIRST_DATA_ROW == 2
    assert [c.value for c in ws[1]] == [f.name for f in fields(entity.table)]
    assert ws.max_row == 1 and ws.freeze_panes == "A2"  # 2. satır veri satırı
    assert not ws.data_validations.dataValidation  # zorlama yok (K-58)
    info = dict(wb["_Surum"].iter_rows(values_only=True))
    assert info["Tablo"] == entity.table and info["Sürüm"] == entity.version and info["İlk veri satırı"] == 2 and info["Smartchain"] == __version__


def test_required_headers_are_dark():
    ws = build()["Kaynak"]
    required, other = ws[f"{column_of(ws, 'Code')}1"], ws[f"{column_of(ws, 'Name')}1"]
    assert required.fill.fgColor.rgb == rgb(formats.color("indigo-900")) and required.font.color.rgb == rgb(formats.color("surface"))
    assert other.fill.fgColor.rgb == rgb(formats.color("indigo-100")) and other.font.color.rgb == rgb(formats.color("indigo-900"))
    darks = [c.value for c in ws[1] if c.fill.fgColor.rgb == rgb(formats.color("indigo-900"))]
    assert darks == [f.name for f in fields("Resource") if f.required] == ["LocationCode", "Code"]


def test_notes_sheet_layout():
    wb = build()
    ws = wb["Açıklama"]
    assert ws["A1"].value == NOTES_INTRO == "Koyu başlıklı alanlar zorunludur."
    assert tuple(c.value for c in ws[2]) == NOTE_HEADERS == ("Alan", "Etiket", "Açıklama", "Tip", "Boş bırakılırsa", "Smartchain değerleri", "Örnek")
    assert ws.freeze_panes == "A3"
    assert list(notes(wb)) == [f.name for f in fields("Resource")]


def test_description_empty_when_it_repeats():
    found = notes(build())
    assert found["Code"]["Etiket"] == "Kaynak kodu" and found["Code"]["Açıklama"] is None
    assert found["ResourceType"]["Açıklama"] is None  # yalnız değer listesiydi
    assert found["DailyCapacity"]["Açıklama"] == "Bir adet kaynağın bir çalışma günündeki kapasitesi"


def test_blank_column_is_concrete():
    found = notes(build())
    assert found["Code"]["Boş bırakılırsa"] == "Satır yüklenmez"
    assert found["ResourceRole"]["Boş bırakılırsa"] == "Primary kabul edilir"
    assert found["IsConstrained"]["Boş bırakılırsa"] == "0 kabul edilir"
    assert found["ResourceType"]["Boş bırakılırsa"] == "Veri kuralıyla doldurulur"
    assert found["Name"]["Boş bırakılırsa"] == "Boş kalır"


def test_smartchain_values():
    found = notes(build())
    assert found["ResourceType"]["Smartchain değerleri"] == "Makine, İşçi, Fason, Diğer. ERP'deki farklı değerler veri kuralıyla çevrilir."
    assert found["ResourceGroupCode"]["Smartchain değerleri"] == "Kaynak grubu tablosundaki kod"
    assert found["CapacityUnit"]["Smartchain değerleri"] == "Birim tablosundaki kod"
    assert found["Name"]["Smartchain değerleri"] is None


def test_types_and_examples():
    found = notes(build())
    assert found["IsConstrained"]["Tip"] == "1 = Evet, 0 = Hayır" and found["Code"]["Tip"] == "Metin, en çok 50"
    assert found["Code"]["Örnek"] == "TORNA-01"
    assert isinstance(found["DailyCapacity"]["Örnek"], (int, float)) and isinstance(found["Quantity"]["Örnek"], int)
    assert not [r for r in found.values() if "ÖRN" in str(r["Örnek"])]
    day = notes(build("ProductionVersion"))["ValidTo"]["Örnek"]
    assert day == datetime(2026, 12, 31)


def test_additional_field_appears_with_its_label_version_stays():
    wb = build("Material", labels={"AdditionalNumber1": "Birim ağırlık"})
    assert "AdditionalNumber1" in [c.value for c in wb["Malzeme"][1]] and "AdditionalNumber2" not in [c.value for c in wb["Malzeme"][1]]
    extra = notes(wb)["AdditionalNumber1"]
    assert extra["Etiket"] == "Birim ağırlık" and extra["Açıklama"] is None and extra["Örnek"] == 10
    assert dict(wb["_Surum"].iter_rows(values_only=True))["Sürüm"] == 1


def test_rows_are_typed_and_text_stays_text():
    rows = [{"Code": "=1+1", "Name": "001", "IsConstrained": True, "DailyCapacity": -5.5, "Quantity": 3}]
    ws = build(rows=rows)["Kaynak"]
    value = lambda name: ws[f"{column_of(ws, name)}{FIRST_DATA_ROW}"]  # noqa: E731
    assert value("Code").value == "=1+1" and value("Code").data_type == "s"
    assert value("Name").value == "001" and value("Name").number_format == "@"
    assert value("IsConstrained").value == 1 and value("DailyCapacity").value == -5.5 and value("Quantity").value == 3


def test_dates_keep_their_format():
    moment = datetime(2026, 11, 4, 8, 30)
    ws = build("WorkerAbsence", rows=[{"WorkerCode": "W-1", "StartAt": moment}])["İşçi izni"]
    cell = ws[f"{column_of(ws, 'StartAt')}{FIRST_DATA_ROW}"]
    assert cell.value == moment and cell.number_format == "dd.mm.yyyy hh:mm"
    ws = build("ProductionVersion", rows=[{"MaterialCode": "M-1", "ValidFrom": date(2026, 11, 4)}])["Üretim versiyonu"]
    cell = ws[f"{column_of(ws, 'ValidFrom')}{FIRST_DATA_ROW}"]
    assert cell.value == datetime(2026, 11, 4) and cell.number_format == "dd.mm.yyyy"
