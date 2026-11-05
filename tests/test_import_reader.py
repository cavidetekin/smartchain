"""Excel okuyucu (fonksiyon 03, K-129): tanıma, sayfalar, boş satır, bozuk ve kötü dosya. Veritabanısız."""
import zipfile
from datetime import datetime

import pytest
from openpyxl import Workbook as OpenWorkbook

from app.integration import contract, reader
from app.integration.reader import BadFile, Workbook, check_package, template_entity
from app.integration.template import write_template

RESOURCE = contract.entity("Resource")


def template(tmp_path, entity=RESOURCE, rows=(), name="t.xlsx"):
    path = tmp_path / name
    write_template(str(path), entity, None, rows=rows)
    return path


def test_template_is_recognised(tmp_path):
    path = template(tmp_path, rows=[{"LocationCode": "L", "Code": "A"}])
    with Workbook(path) as wb:
        identity = wb.identity()
        assert (identity.table, identity.version, identity.first_row) == ("Resource", RESOURCE.version, contract.FIRST_DATA_ROW)
        assert template_entity(identity) is RESOURCE
        assert wb.header(RESOURCE) == [f.name for f in contract.fields("Resource")]
        rows = list(wb.rows(RESOURCE, identity.first_row))
    assert [n for n, _ in rows] == [2] and rows[0][1]["Code"] == "A"


def test_values_keep_their_types(tmp_path):
    path = template(tmp_path, contract.entity("Stock"), rows=[{"LocationCode": "L", "MaterialCode": "001", "LotNo": "=1+1", "Quantity": 1.5, "ExpiryDate": datetime(2026, 11, 4), "IsActive": 1}])
    with Workbook(path) as wb:
        (_, row), = wb.rows(contract.entity("Stock"), 2)
    assert row["MaterialCode"] == "001" and row["LotNo"] == "=1+1" and row["Quantity"] == 1.5 and row["ExpiryDate"] == datetime(2026, 11, 4) and row["IsActive"] == 1


def test_empty_rows_are_skipped_and_numbers_kept(tmp_path):
    path = tmp_path / "bos.xlsx"
    wb = OpenWorkbook()
    ws = wb.active
    ws.append(["LocationCode", "Code", None, "  Name "])
    ws.append(["L", "A", "x", "ad"])
    ws.append([None, None, None, None])
    ws.append(["  ", None, None, None])
    ws.append(["L", "B", None, None])
    wb.save(path)
    with Workbook(path) as book:
        identity = book.identity()
        assert (identity.table, identity.version, identity.first_row) == (None, None, contract.FIRST_DATA_ROW)
        rows = list(book.rows(RESOURCE, identity.first_row))
    assert [n for n, _ in rows] == [2, 5] and rows[0][1] == {"LocationCode": "L", "Code": "A", "Name": "ad"}


def test_other_table_template_is_identified(tmp_path):
    with Workbook(template(tmp_path, contract.entity("Material"))) as wb:
        assert template_entity(wb.identity()).table == "Material"


def test_unknown_table_in_version_sheet(tmp_path):
    path = tmp_path / "yabanci.xlsx"
    wb = OpenWorkbook()
    wb.active.append(["Code"])
    info = wb.create_sheet("_Surum")
    info.append(["Tablo", "Yok"])
    info.append(["Sürüm", "bozuk"])
    wb.save(path)
    with Workbook(path) as book:
        identity = book.identity()
    assert identity.table == "Yok" and identity.version is None and template_entity(identity) is None


def test_no_data_sheet(tmp_path):
    path = tmp_path / "bossayfa.xlsx"
    wb = OpenWorkbook()
    wb.active.title = "_Surum"
    wb.save(path)
    with Workbook(path) as book, pytest.raises(BadFile):
        book.header(RESOURCE)


@pytest.mark.parametrize("content", [b"xlsx degil", b"PK\x03\x04bozuk", b""])
def test_not_an_excel_file(tmp_path, content):
    path = tmp_path / "bozuk.xlsx"
    path.write_bytes(content)
    with pytest.raises(BadFile):
        with Workbook(path):
            pass


def test_zip_without_workbook(tmp_path):
    path = tmp_path / "zip.xlsx"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("a.txt", "b")
    with pytest.raises(BadFile):
        check_package(path)


def test_macro_workbook_is_rejected(tmp_path):
    path = template(tmp_path)
    with zipfile.ZipFile(path, "a") as z:
        z.writestr("xl/vbaProject.bin", b"x")
    with pytest.raises(BadFile, match="Makro"):
        check_package(path)


def test_zip_bomb_is_rejected_before_opening(tmp_path):
    path = template(tmp_path)
    with zipfile.ZipFile(path, "a", zipfile.ZIP_DEFLATED) as z:
        z.writestr("xl/media/sifir.bin", b"\0" * 5_000_000)
    assert path.stat().st_size < 1_000_000
    with pytest.raises(BadFile, match="çok büyük"):
        check_package(path, max_unpacked=1_000_000)
    check_package(path)  # varsayılan sınırın altında


def test_file_is_closed_after_use(tmp_path):
    """Windows'ta açık dosya silinemez; vazgeçme ve temizlik buna bağlı."""
    path = template(tmp_path, rows=[{"LocationCode": "L", "Code": "A"}])
    with Workbook(path) as wb:
        list(wb.rows(RESOURCE, 2))
    path.unlink()
    assert not path.exists() and reader.MAX_UNPACKED_BYTES > 0
