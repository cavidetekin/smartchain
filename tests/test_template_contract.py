"""Veri sözleşmesi ve varlık kataloğu (docs/03, K-110). Veritabanı istemez."""
import json
import re
from datetime import date, datetime
from pathlib import Path

import pytest

from app.data.synthetic.dataset import generate
from app.data.synthetic.excel import to_staging
from app.integration import contract
from app.integration.contract import ENTITIES, MASTER_DATA, TRANSACTION_DATA, contract_hash, fields, stg_columns
from db.models import metadata

ROOT = Path(__file__).resolve().parents[1]
VERSIONS = ROOT / "tests" / "template_versions.json"
TABLES = [e.table for e in ENTITIES]


def catalog_rows() -> list[list[str]]:
    text = (ROOT / "docs" / "03-entegrasyon.md").read_text(encoding="utf-8")
    start = text.index("| VARLIK | AD | SINIF | AÇIKLAMA | DOSYA ADI | SÜRÜM |")
    rows = []
    for line in text[start:].splitlines()[2:]:
        if not line.startswith("|"):
            break
        rows.append([c.strip() for c in line.strip("|").split("|")])
    return rows


def test_catalog_matches_docs():
    """Katalog docs/03'ten üretilir; farklıysa: python db/generate.py."""
    assert catalog_rows() == [[e.table, e.name, e.data_class, e.description, e.slug, str(e.version)] for e in ENTITIES]


def test_descriptions_are_one_short_plain_sentence():
    for e in ENTITIES:
        assert 5 <= len(e.description) <= 70 and not e.description.endswith(".") and "." not in e.description, e.table
        assert not re.search(r"K-\d+|stg\.|[A-Z][a-z]+[A-Z]", e.description), e.table  # karar numarası ve teknik ad yok


def test_catalog_covers_every_staging_table():
    assert sorted(TABLES) == sorted(t.name for t in metadata.sorted_tables if t.schema == "stg") and len(TABLES) == 26
    assert {e.data_class for e in ENTITIES} == {MASTER_DATA, TRANSACTION_DATA}
    assert len({e.slug for e in ENTITIES}) == 26 and all(re.fullmatch(r"[a-z-]+", e.slug) for e in ENTITIES)
    assert contract.entity("Resource").file_name == "smartchain_kaynak_v1.xlsx" and contract.entity("yok") is None


@pytest.mark.parametrize("table", TABLES)
def test_labels_are_short_readable_and_unique(table):
    found = fields(table)
    labels = [f.label for f in found]
    assert all(labels) and all(len(x) <= 40 for x in labels), labels
    assert len(labels) == len(set(labels)), labels
    assert [f.name for f in found if f.label == f.name] == []
    assert not [f.name for f in found if f.name.startswith("Additional")]  # etiketsiz ek alan yok
    assert not [f.name for f in found if re.search(r"K-\d+", f.description)]


def test_required_and_blank_rules():
    """Boşsa satır yüklenmeyen 80 alan zorunludur; her YOKSA kuralının somut karşılığı var."""
    every = [f for t in TABLES for f in fields(t)]
    assert sum(f.required for f in every) == 80 and all(f.blank == contract.BLANK_ROW_REJECTED for f in every if f.required)
    assert sum(1 for f in every if f.values) == 22
    assert contract.blank_text("hata (satır atlanır)") == "Satır yüklenmez" and contract.blank_text("varsayılan Takvim günü") == "Takvim günü kabul edilir"
    assert contract.blank_text("kural ya da elle") == "Veri kuralıyla doldurulur" and contract.blank_text("boş kalır") == "Boş kalır"
    with pytest.raises(ValueError):
        contract.blank_text("yeni bir kural")


def test_every_reference_says_which_table():
    """docs/03'te REF olan her alanın metni var; yeni referans unutulursa düşer."""
    refs = {c.name for t in TABLES for c in stg_columns(t) if "REF" in c.info.get("key", "")}
    assert refs == set(contract.REF_TEXT), refs ^ set(contract.REF_TEXT)
    every = [f for t in TABLES for f in fields(t)]
    assert not [f.name for f in every if f.values and f.ref_text]


def test_resource_example_in_docs():
    found = fields("Resource")
    assert len(found) == 15
    assert [f.name for f in found if f.required] == ["LocationCode", "Code"]
    assert {f.name: f.blank for f in found if f.blank not in ("Satır yüklenmez", "Boş kalır")} == {'ResourceGroupCode': 'Veri kuralıyla doldurulur', 'ResourceType': 'Veri kuralıyla doldurulur', 'ResourceRole': 'Primary kabul edilir', 'IsConstrained': '0 kabul edilir', 'CapacityUnit': 'Veri kuralıyla doldurulur', 'DailyCapacity': 'Veri kuralıyla doldurulur', 'Quantity': 'Veri kuralıyla doldurulur', 'CapacitySource': 'Doğrudan kabul edilir'}
    assert contract.base_counts("Resource") == (15, 2)


def test_out_of_phase_values_stay_in_contract_not_in_template():
    col = next(c for c in stg_columns("Resource") if c.name == "ResourceType")
    assert {"Kalıp", "Fırın"} <= set(col.info["values"])
    assert next(f for f in fields("Resource") if f.name == "ResourceType").values == ("Makine", "İşçi", "Fason", "Diğer")


def test_additional_field_needs_a_label():
    found = {f.name: f for f in fields("Material", {"AdditionalText1": "Malzeme sınıfı", "Code": "Ürün kodu"})}
    assert found["AdditionalText1"].label == "Malzeme sınıfı" and found["Code"].label == "Ürün kodu"
    assert "AdditionalText2" not in found


def test_system_fields_are_not_in_template():
    for table in TABLES:
        assert not {"StagingRowId", "ImportBatchId", "RowStatus", "ErrorText", "Id", "VersionFrom", "VersionTo"} & {f.name for f in fields(table)}


@pytest.mark.parametrize("table", TABLES)
def test_examples_fit_the_field(table):
    """Örnek gerçek: tipi tutar, uzunluğa sığar, listede vardır, referansta kod biçiminde. Boş ya da yer tutucu yok."""
    columns = {c.name: c for c in stg_columns(table)}
    for f in fields(table):
        value = f.example
        assert value not in (None, "") and "ÖRN" not in str(value), f.name
        if f.kind == "text":
            assert isinstance(value, str) and len(value) <= columns[f.name].type.length, f.name
        elif f.kind == "bool":
            assert value in (0, 1), f.name
        elif f.kind == "integer":
            assert isinstance(value, int), f.name
        elif f.kind == "number":
            assert isinstance(value, (int, float)), f.name
        elif f.kind == "date":
            assert isinstance(value, date), f.name
        else:
            assert isinstance(value, datetime), f.name
        if f.values:
            assert value in f.values, f.name


def test_examples_file_has_no_stale_fields():
    saved = json.loads(contract.EXAMPLES.read_text(encoding="utf-8"))
    assert saved.keys() == set(TABLES)
    for table, values in saved.items():
        assert set(values) == {c.name for c in stg_columns(table) if not c.name.startswith("Additional")}, table


def test_additional_field_example_by_kind():
    found = {f.name: f for f in fields("Material", {"AdditionalText1": "Sınıf", "AdditionalNumber1": "Ağırlık"})}
    assert found["AdditionalText1"].example == "Örnek" and found["AdditionalNumber1"].example == 10


def test_contract_change_needs_a_new_version():
    """Sözleşme değişip sürüm artmazsa test düşer. Sürümü docs/03'te artırın, python db/generate.py, sonra bu dosyayı güncelleyin."""
    saved = json.loads(VERSIONS.read_text(encoding="utf-8"))
    current = {e.table: {"version": e.version, "contract": contract_hash(e.table)} for e in ENTITIES}
    assert saved.keys() == current.keys()
    stale = [t for t, c in current.items() if c["contract"] != saved[t]["contract"] and c["version"] <= saved[t]["version"]]
    assert stale == [], f"Sözleşme değişti, sürüm artmadı: {stale}. Yeni özetler: { {t: current[t]['contract'] for t in stale} }"
    assert [t for t, c in current.items() if c["version"] < saved[t]["version"]] == []


def test_synthetic_rows_fit_the_contract():
    """Temiz sentetik veri sözleşmeye uyar: zorunlu dolu, değer listede, Faz 1 dışı değer yok."""
    stg = to_staging(generate(date(2026, 10, 27)))
    for table, rows in stg.items():
        columns = {c.name: c for c in stg_columns(table)}
        for f in fields(table):
            for r in rows:
                value = r.get(f.name)
                if f.required:
                    assert value not in (None, ""), (table, f.name)
                if f.values and value not in (None, ""):
                    assert value in f.values, (table, f.name, value)
                length = getattr(columns[f.name].type, "length", None)
                if length and isinstance(value, str):
                    assert len(value) <= length, (table, f.name)
