"""Liste sorgusu (K-87) ve alan etiketi (K-88): veritabanısız testler."""
from datetime import date

import pytest
from sqlalchemy.dialects import mssql

from app.api.lists import LISTS, MATERIALS
from app.api.lists.definition import columns
from app.api.lists.query import Builder, ListQueryError, like_escape, relative_range
from app.api.lists.request import FilterItem, QueryRequest, SortItem
from db import generate


def sql(q) -> str:
    return str(q.compile(dialect=mssql.dialect()))


def builder(labels=None):
    return Builder(MATERIALS, labels or {}, version=7, today=date(2026, 10, 29))


# --- K-88 etiket kuralı ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("desc, label", [
    ("Malzeme kodu", "Malzeme kodu"),
    ("Raf ömrü (gün); Faz 1'de yalnız uyarı", "Raf ömrü (gün)"),
    ("Malzeme seviyesi: Hammadde | Yarı mamul | Nihai ürün", "Malzeme seviyesi"),
    ("Hammadde | Yarı mamul", ""),  # ön eksiz değer listesi: etiket yok
])
def test_label_rule(desc, label):
    assert generate.field_label({"name": "X", "desc": desc}) == label


def test_additional_field_label_comes_from_field_definition():
    assert generate.field_label({"name": "AdditionalText3", "desc": "Ek metin alanları; etiketi FieldDefinition'da"}) == ""


def test_label_check_rejects_missing_and_long_labels():
    spec = [{"schema": "core", "name": "Material", "versioned": False, "fields": [
        {"name": "A", "desc": "Hammadde | Yarı mamul"}, {"name": "B", "desc": "x" * 41}, {"name": "C", "desc": "Kod"}]}]
    problems = generate.label_problems(spec)
    assert [p.split(":")[0] for p in problems] == ["core.Material.A", "core.Material.B"]


def test_docs_labels_are_complete():
    assert generate.label_problems(generate.build_spec()) == []


def test_list_tables_match_list_definitions():
    assert {tuple(d.table.split(".")) for d in LISTS} <= generate.LIST_TABLES


# --- kolonlar ---------------------------------------------------------------------------------------------------

def test_columns_types_filters_and_labels():
    cols = {c["field"]: c for c in columns(MATERIALS, {})}
    assert cols["Code"]["label"] == "Malzeme kodu"
    assert (cols["Code"]["type"], cols["Code"]["filter"]) == ("text", "text")
    assert cols["MaterialLevel"]["filter"] == "list"
    assert cols["MaterialLevel"]["values"] == ["Hammadde", "Yarı mamul", "Nihai ürün"]
    assert (cols["MaterialGroup"]["filter"], cols["MaterialGroup"]["values_from_server"]) == ("list", True)
    assert (cols["IsSellable"]["type"], cols["IsSellable"]["values"]) == ("bool", [True, False])
    assert (cols["SafetyStock"]["type"], cols["SafetyStock"]["decimals"]) == ("number", None)
    assert cols["SafetyStock"]["decimals_from_unit"] and cols["MinLot"]["decimals_from_unit"]
    assert (cols["AssemblyScrapPct"]["decimals"], cols["AssemblyScrapPct"]["decimals_from_unit"]) == (1, False)
    assert (cols["ProductionLeadTimeDays"]["decimals"], cols["GoodsReceiptDays"]["decimals"]) == (0, 0)  # gün
    assert (cols["ShelfLifeDays"]["decimals"], cols["Code"]["decimals"]) == (0, None)
    assert (cols["ShelfLifeDays"]["type"], cols["ShelfLifeDays"]["filter"]) == ("integer", "number")
    assert (cols["UpdatedAt"]["type"], cols["UpdatedAt"]["filter"]) == ("datetime", "date")
    assert not any(f.startswith("Additional") for f in cols)  # etiketsiz ek alan görünmez


def test_field_definition_label_shows_additional_field_and_overrides_standard():
    cols = {c["field"]: c for c in columns(MATERIALS, {"AdditionalText1": "Malzeme sınıfı", "Name": "Tanım"})}
    assert cols["AdditionalText1"]["label"] == "Malzeme sınıfı"
    assert cols["Name"]["label"] == "Tanım"
    assert "AdditionalText2" not in cols


# --- sorgu kurucu -----------------------------------------------------------------------------------------------

def test_unknown_field_and_wrong_operator_are_rejected():
    b = builder()
    with pytest.raises(ListQueryError) as e:
        b.where([FilterItem(field="Password", op="equals", value="x"), FilterItem(field="Name", op="gt", value=1),
                 FilterItem(field="SafetyStock", op="contains", value="1")])
    assert [d["field"] for d in e.value.details] == ["filters.0.field", "filters.1.op", "filters.2.op"]
    with pytest.raises(ListQueryError):
        b.order_by([SortItem(field="Nope")])
    with pytest.raises(ListQueryError):
        b.select_columns(["Code", "AdditionalText2"])  # etiketsiz ek alan istenemez


@pytest.mark.parametrize("item, problem_part", [
    (FilterItem(field="Name", op="contains", value=" "), "value"),
    (FilterItem(field="MaterialLevel", op="in", values=[]), "values"),
    (FilterItem(field="IsSellable", op="in", values=["evet"]), "values"),
    (FilterItem(field="SafetyStock", op="between"), "min"),
    (FilterItem(field="SafetyStock", op="eq", value="10"), "value"),
    (FilterItem(field="UpdatedAt", op="relative", value="last_year"), "value"),
    (FilterItem(field="UpdatedAt", op="between"), "from"),
])
def test_missing_or_wrong_values_are_rejected(item, problem_part):
    with pytest.raises(ListQueryError) as e:
        builder().where([item])
    assert e.value.details[0]["field"] == f"filters.0.{problem_part}"


def test_values_are_parameters_and_like_is_escaped():
    q = builder().rows_query(QueryRequest(filters=[FilterItem(field="Name", op="contains", value="50%_[x]'; DROP")]), 100)
    text = sql(q)
    assert "DROP" not in text and "COLLATE Turkish_100_CI_AS" in text and "ESCAPE" in text
    assert "upper(" in text.lower() and "Latin1_General_100_BIN2" in text
    assert like_escape("50%_[x]") == "50\\%\\_\\[x]"


def test_sort_is_turkish_and_stable():
    text = sql(builder().rows_query(QueryRequest(sort=[SortItem(field="MaterialLevel"), SortItem(field="SafetyStock", dir="desc")]), 100))
    order = text.split("ORDER BY", 1)[1]
    assert order.index("MaterialLevel") < order.index("SafetyStock") < order.index("Id")
    assert '"MaterialLevel" COLLATE Turkish_100_CI_AS' in order or "MaterialLevel] COLLATE Turkish_100_CI_AS" in order


def test_default_fields_and_sort():
    q = builder().rows_query(QueryRequest(), 100)
    names = [c.name for c in q.selected_columns]
    assert names[0] == "Id" and names[1:-1] == list(MATERIALS.default_visible) and names[-1] == "_unit"


@pytest.mark.parametrize("today, value, expected", [
    (date(2026, 10, 29), "this_week", (date(2026, 10, 26), date(2026, 11, 2))),     # perşembe → pazartesi
    (date(2026, 10, 26), "next_4_weeks", (date(2026, 10, 26), date(2026, 11, 23))),
    (date(2026, 11, 1), "this_week", (date(2026, 10, 26), date(2026, 11, 2))),      # pazar aynı haftada
])
def test_relative_ranges_are_iso_weeks(today, value, expected):
    assert relative_range(value, today) == expected


@pytest.mark.parametrize("defn", LISTS, ids=lambda d: d.name)
def test_every_number_field_declares_decimals(defn):
    """docs/12: ondalık liste tanımından; veritabanı ölçeğinden alınmaz."""
    from app.api.lists.definition import column_type
    numbers = {f for f in defn.fields if column_type(defn.sa_table.c[f]) == "number"}
    fixed, unit = set(defn.decimals), set(defn.unit_decimals)
    assert fixed & unit == set()                      # ikisi birden olmaz
    assert numbers - fixed - unit == set()            # hiçbiri olmaz
    assert fixed | unit <= numbers
    assert not unit or defn.unit_field in defn.sa_table.c


def test_limit_defaults_to_chunk_size_and_is_bounded_by_it():
    q = builder().rows_query(QueryRequest(), 150)
    assert q._limit_clause.value == 150
    with pytest.raises(ListQueryError) as e:
        builder().rows_query(QueryRequest(limit=151), 150)
    assert e.value.details[0]["field"] == "body.limit"


def test_limit_is_bounded():
    with pytest.raises(ValueError):
        QueryRequest(limit=501)
    with pytest.raises(ValueError):
        QueryRequest(offset=-1)
