"""Veri sözlüğünün kurulumu (K-104): core ve param alanları docs/02'den, geçişle; System owner'ın değeri ezilmez."""
import re

import pytest
from sqlalchemy import text

from app.data.synthetic.dataset import generate as generate_data
from app.data.synthetic.load import load
from db import dictionary, generate
from db.models import metadata

SPEC = [t for t in generate.build_spec() if t["schema"] in ("core", "param")]
EXPECTED = {(t["name"], f["name"]): (t, f) for t in SPEC for f in t["fields"] if f["source"] != dictionary.SYSTEM_SOURCE}


def test_fields_match_docs():
    rows = {(r["TableName"], r["FieldName"]): r for r in dictionary.fields(metadata)}
    assert set(rows) == set(EXPECTED) and len(rows) > 400
    assert not [k for k in rows if k[1] in ("VersionFrom", "VersionTo", "BusinessKey")]
    for key, (table, field) in EXPECTED.items():
        row = rows[key]
        assert row["FieldClass"] == table["cls"], key
        assert row["IsRequired"] == field["required"], key
        assert row["EditableInWorkspace"] == field["workspace"], key
        assert (row["DefaultValue"] or "") == field["default"], key


def test_only_core_and_param_with_no_name_clash():
    names = [t["name"] for t in SPEC]
    assert len(names) == len(set(names))
    assert {t.schema for t in metadata.tables.values() if t.info.get("field_class")} == {"core", "param"}


def test_standard_label():
    assert dictionary.standard_label("AdditionalText3", None) == "Ek metin alanı 3"
    assert dictionary.standard_label("AdditionalNumber2", None) == "Ek sayı alanı 2"
    assert dictionary.standard_label("Name", "Malzeme adı") == "Malzeme adı"
    assert dictionary.standard_label("Status", None) == "Status"
    assert len(dictionary.standard_label("X", "a" * 300)) == dictionary.LABEL_LENGTH


UNIT = re.compile(r" \((%|gün|iş günü|dk|saat|adam-saat)\)$")


def test_standard_labels_are_short_and_turkish():
    """K-104: en çok 40 karakter, aynı tabloda tekrar yok, alan adına düşmez, parantezde yalnız birim."""
    seen = set()
    for f in dictionary.fields(metadata):
        table, field, label = f["TableName"], f["FieldName"], f["StandardLabel"]
        assert len(label) <= 40, (table, field, label)
        assert label != field, (table, field)
        assert "(" not in UNIT.sub("", label), (table, field, label)
        assert (table, label) not in seen, (table, label)
        seen.add((table, label))


def test_descriptions_come_from_docs_for_the_screen():
    """K-104: her alanda açıklama; tek satıra sığar, karar numarası ve ek alanın teknik notu yok."""
    rows = {(r["TableName"], r["FieldName"]): r["Description"] for r in dictionary.fields(metadata)}
    assert all(rows.values())
    assert max(len(v) for v in rows.values()) <= metadata.tables["adm.FieldDefinition"].c.Description.type.length
    assert not [k for k, v in rows.items() if re.search(r"K-\d", v) or "FieldDefinition" in v]
    assert rows[("Resource", "CapacityUnit")] == "Kapasite birimi (Saat, Adet, Ton…); rotadaki tüketim aynı birimde kabul edilir"
    assert rows[("UnitOfMeasure", "Decimals")] == "Miktar ondalığı; ERP'den gelmez, Smartchain'de tutulur"
    assert rows[("Material", "AdditionalText1")] == "Ek metin alanları"
    assert rows[("Material", "ShelfLifeDays")] == "Raf ömrü; şimdilik yalnız uyarı için kullanılır"
    assert rows[("ProductionVersion", "RouteCode")] == "Rota kodu"
    assert rows[("Routing", "LaborTime")] == "Toplam işçilik süresi; işçilik esası Toplam olduğunda kullanılır"
    assert rows[("PlanningSetting", "SettingKey")] == "Parametre adı"
    assert metadata.tables["core.Material"].c.ShelfLifeDays.info["label"] == "Raf ömrü (gün)"


def test_label_and_description_are_separate():
    """K-88: ETİKET doluysa etiket odur; açıklama veritabanı yorumunda, değer listesi yerinde kalır."""
    constrained = metadata.tables["core.Resource"].c.IsConstrained
    assert constrained.info["label"] == "Kısıtlı kaynak" and "sonsuz kapasite" in constrained.comment
    status = metadata.tables["core.SalesOrderLine"].c.Status
    assert status.info["label"] == "Sipariş durumu" and status.info["values"] == ["Açık", "Kapandı", "İptal"]
    assert metadata.tables["core.Material"].c.LotSizePolicy.info["label"] == "Lot politikası"
    assert metadata.tables["core.Material"].c.Name.info["label"] == "Malzeme adı"  # ETİKET boşsa AÇIKLAMA'dan


@pytest.mark.db
def test_every_field_is_in_the_dictionary(db_engine):
    """Yeni kolon eklenip geçişte sync unutulursa bu test düşer."""
    with db_engine.connect() as c:
        stored = {(r[0], r[1]) for r in c.execute(text("SELECT TableName, FieldName FROM adm.FieldDefinition"))}
    missing = set(EXPECTED) - stored
    assert not missing, f"Sözlükte yok; geçişe db/dictionary.sync ekleyin: {sorted(missing)[:10]}"
    extra = stored - set(EXPECTED)
    assert not extra, f"Docs'ta yok: {sorted(extra)[:10]}"


@pytest.mark.db
def test_sync_is_idempotent_and_keeps_owner_values(db_engine):
    with db_engine.connect() as conn:
        trans = conn.begin()
        try:
            assert dictionary.sync(conn, metadata) == {"added": 0, "updated": 0}
            conn.execute(text("UPDATE adm.FieldDefinition SET IsRequired = 1, Label = N'Özel', StandardLabel = N'eski', Description = N'eski' "
                              "WHERE TableName = N'Material' AND FieldName = N'Name'"))
            conn.execute(text("DELETE FROM adm.FieldDefinition WHERE TableName = N'Material' AND FieldName = N'MinLot'"))
            assert dictionary.sync(conn, metadata) == {"added": 1, "updated": 1}
            row = conn.execute(text("SELECT IsRequired, Label, StandardLabel, Description FROM adm.FieldDefinition "
                                    "WHERE TableName = N'Material' AND FieldName = N'Name'")).one()
            assert tuple(row) == (True, "Özel", "Malzeme adı", "Malzeme adı")
            assert conn.execute(text("SELECT COUNT(*) FROM adm.FieldDefinition WHERE TableName = N'Material' "
                                     "AND FieldName = N'MinLot'")).scalar_one() == 1
        finally:
            trans.rollback()


@pytest.mark.db
def test_synthetic_load_writes_label_only_when_empty(db_engine):
    where = "WHERE TableName = N'Material' AND FieldName = N'AdditionalText1'"
    def label():
        with db_engine.connect() as c:
            return c.execute(text(f"SELECT Label FROM adm.FieldDefinition {where}")).scalar_one()
    data = generate_data()
    try:
        with db_engine.begin() as c:
            c.execute(text(f"UPDATE adm.FieldDefinition SET Label = NULL {where}"))
        load(db_engine, data)
        assert label() == "Malzeme sınıfı"
        with db_engine.begin() as c:
            c.execute(text(f"UPDATE adm.FieldDefinition SET Label = N'pytest Özel' {where}"))
        load(db_engine, data)
        assert label() == "pytest Özel"
    finally:
        with db_engine.begin() as c:
            c.execute(text(f"UPDATE adm.FieldDefinition SET Label = N'Malzeme sınıfı' {where}"))
