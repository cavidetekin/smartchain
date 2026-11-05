"""Yapısal kontrol (fonksiyon 03 ön kontrol, K-129): veritabanısız; 3.3 ve 3.4 de aynı kodu kullanır."""
from datetime import date, datetime

import pytest

from app.integration import contract, structural
from app.integration.structural import ERROR, INFO, BadValue, RowChecker, check_columns, convert, duplicate_message, key_fields


def resource(**over):
    return {"LocationCode": "ORM-01", "Code": "A-01", **over}


def label(table, name):
    return next(f.label for f in contract.fields(table) if f.name == name)


def findings(table, raw):
    return RowChecker(table).check(7, raw)


def test_every_table_is_checked_from_the_contract():
    required = 0
    for e in contract.ENTITIES:
        checker = RowChecker(e.table)
        required += sum(f.required for f in checker.fields)
        assert key_fields(e.table), e.table
        row, found = checker.check(1, {})  # boş satır: zorunlusu olanda hata
        assert (row is None) == any(f.required for f in checker.fields) or checker._either, e.table
        assert all(x.row == 1 for x in found)
    assert required == 88


@pytest.mark.parametrize("kind, value, expected", [
    ("text", "001", "001"), ("text", "=1+1", "=1+1"), ("text", 1001.0, "1001"), ("text", 1001, "1001"), ("text", "  A  ", "A"), ("text", "   ", None), ("text", None, None),
    ("text", datetime(2026, 11, 4), "2026-11-04"),
    ("number", 1.5, 1.5), ("number", "1,5", 1.5), ("number", "1.234,5", 1234.5), ("number", "12.5", 12.5), ("number", 3, 3.0),
    ("integer", 3, 3), ("integer", 3.0, 3), ("integer", "12", 12),
    ("bool", 1, 1), ("bool", 0, 0), ("bool", True, 1), ("bool", False, 0), ("bool", "1", 1), ("bool", "Evet", 1), ("bool", "yanlış", 0),
    ("date", datetime(2026, 11, 4), datetime(2026, 11, 4)), ("date", date(2026, 11, 4), datetime(2026, 11, 4)), ("date", "04.11.2026", datetime(2026, 11, 4)), ("date", "2026-11-04", datetime(2026, 11, 4)),
])
def test_convert(kind, value, expected):
    assert convert(kind, value) == expected


@pytest.mark.parametrize("kind, value, check", [
    ("number", "abc", "type"), ("number", "NaN", "type"), ("integer", 1.5, "type"), ("integer", 99999999999, "range"), ("bool", 5, "type"), ("bool", "belki", "type"), ("date", "yarın", "type"), ("date", 45000, "type"),
])
def test_convert_rejects(kind, value, check):
    with pytest.raises(BadValue) as e:
        convert(kind, value)
    assert e.value.check == check and e.value.message


def test_length_and_numeric_range():
    with pytest.raises(BadValue) as e:
        convert("text", "x" * 11, 10)
    assert e.value.check == "length" and "10" in e.value.message
    assert convert("number", 99.9999, whole_digits=2) == 99.9999
    with pytest.raises(BadValue) as e:
        convert("number", 100, whole_digits=2)  # ScrapRatio decimal(6,4): tek değer bütün parçayı düşürürdü
    assert e.value.check == "range"


def test_scrap_ratio_out_of_range_rejects_the_row_only():
    row, found = findings("BOM", {"LocationCode": "L", "MaterialCode": "M", "Code": "B", "ComponentMaterialCode": "C", "Quantity": 1, "ScrapRatio": 123})
    assert row is None and [(x.check, x.field, x.value) for x in found] == [("range", "Fire oranı", "123")]


def test_required_blank_is_an_error_with_key():
    row, found = findings("Resource", {"LocationCode": "ORM-01", "Name": "Ad"})
    assert row is None and [(x.severity, x.check, x.field, x.row) for x in found] == [(ERROR, "required", label("Resource", "Code"), 7)]


def test_rule_filled_field_is_not_rejected_before_rules():
    """K-117, 3.4 notu: CapacityUnit boşsa ön kontrol reddetmez, kontrolü veri kurallarından sonradır."""
    row, found = findings("Resource", resource())
    assert row is not None and row["CapacityUnit"] is None and not found


def test_either_pair():
    base = {"LocationCode": "L", "RouteCode": "R", "OperationNo": 10, "SequenceNo": 1, "Consumption": 1}
    row, found = findings("Routing", base)
    assert row is None and found[0].check == "either" and "Kaynak" in found[0].message and "Kaynak grubu" in found[0].message
    assert findings("Routing", {**base, "ResourceGroupCode": "G"})[0] is not None
    assert findings("Routing", {**base, "ResourceCode": "A"})[0] is not None


def test_value_outside_the_list_is_only_information():
    row, found = findings("Routing", {"LocationCode": "L", "RouteCode": "R", "OperationNo": 10, "SequenceNo": 1, "Consumption": 1, "ResourceCode": "A", "ResourceRole": "Ana"})
    assert row["ResourceRole"] == "Ana" and [(x.severity, x.check, x.value) for x in found] == [(INFO, "value_list", "Ana")]


def test_raw_fields_have_no_list():
    """K-127: ham alanlar listesiz, boşsa boş kalır, satır atılmaz."""
    row, found = findings("SalesOrderLine", {"LocationCode": "L", "OrderNo": "S", "LineNo": 1, "CustomerCode": "C", "MaterialCode": "M", "OpenQuantity": 1, "RequestedDate": "04.11.2026", "Type": "Karantina"})
    assert row is not None and row["Type"] == "Karantina" and row["Status"] is None and not found


def test_several_problems_in_one_row():
    row, found = findings("Resource", resource(Code=None, IsMachine="belki", RemainingOverTimeYear="x"))
    assert row is None and {x.field for x in found} == {label("Resource", n) for n in ("Code", "IsMachine", "RemainingOverTimeYear")} and all(x.severity == ERROR for x in found)


def test_columns():
    fields = [f.name for f in contract.fields("Resource")]
    assert check_columns("Resource", fields) == []
    missing = check_columns("Resource", [n for n in fields if n != "Code"])
    assert [(x.severity, x.check, x.field) for x in missing] == [(ERROR, "missing_column", "Code")] and "Şablonu yeniden indirin" in missing[0].message
    assert [x.check for x in check_columns("Resource", [*fields, "Hata", None, ""])] == ["unknown_column"]
    assert [(x.severity, x.check) for x in check_columns("Resource", [*fields, "AdditionalText1"])] == [(INFO, "unlabelled_column")]
    assert check_columns("Resource", [*fields, "AdditionalText1"], {"AdditionalText1": "Etiket"}) == []
    assert [x.check for x in check_columns("Resource", [*fields, "Code"])] == ["repeated_column"]


def test_non_stockable_is_optional_and_not_defaulted():
    """K-113 eki: eski şablonda kolon yok, yükleme durmaz; boş değer boş kalır; ön kontrol kural uygulamaz."""
    fields = [f.name for f in contract.fields("Material")]
    assert "IsNonStockable" in fields
    assert check_columns("Material", [n for n in fields if n != "IsNonStockable"]) == []
    base = {"LocationCode": "L", "Code": "A", "Name": "Ad", "BaseUom": "ADET"}
    row, found = findings("Material", base)
    assert row is not None and row["IsNonStockable"] is None and not found
    assert findings("Material", {**base, "IsNonStockable": 1})[0]["IsNonStockable"] == 1


def test_duplicate_message_and_key():
    assert duplicate_message([201, 202]) == "Aynı kayıt 201 ve 202. satırlarda"
    assert duplicate_message([1, 2, 3]) == "Aynı kayıt 1, 2 ve 3. satırlarda"
    assert RowChecker("Material").row_key({"LocationCode": "FAB01", "Code": "SAT-040"}) == "FAB01 · SAT-040"  # anahtarın tamamı
    assert key_fields("Material") == ["LocationCode", "Code"]
    assert key_fields("BOM")[-2:] == ["OperationNo", "SequenceNo"]
    sql = str(structural.duplicate_query("Material", 5).compile(compile_kwargs={"literal_binds": True}))
    assert "PARTITION BY" in sql and "ImportBatchId" in sql
