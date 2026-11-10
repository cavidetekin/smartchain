"""İlişki haritası (K-146): docs/03 tablosu ile kod birebir; alanlar sözleşmede; zorunlu / isteğe bağlı sözleşmenin zorunluluğundan. Veritabanı gerekmez."""
import re
from pathlib import Path

from app.integration import references as refs
from app.integration.contract import ENTITIES, REF_TEXT, fields as contract_fields, stg_columns
from app.integration.structural import key_fields
from app.validation import catalog as cat

DOCS03 = (Path(__file__).resolve().parents[1] / "docs" / "03-entegrasyon.md").read_text(encoding="utf-8")
HEADER = "| TABLO | ALAN | EBEVEYN | EBEVEYN ANAHTARI | İLİŞKİ | PASİF EBEVEYN | KOD |"
UNIT_FIELDS = {"BaseUom", "FromUom", "ToUom", "ComponentUom", "Uom", "CapacityUnit"}  # referans kontrolüne girmez (K-112)
IN_KEY = {("UomConversion", "MaterialCode"), ("Forecast", "CustomerCode"), ("Forecast", "ProjectCode"), ("Stock", "ProjectCode"),
          ("Stock", "CustomerCode"), ("Stock", "SalesOrderNo")}  # anahtarın parçası olan isteğe bağlı bağlantı (K-153)
EITHER_ONE = {("Routing", "ResourceCode"), ("Routing", "ResourceGroupCode"), ("WorkOrderOperation", "ResourceCode"), ("WorkOrderOperation", "ResourceGroupCode")}


def docs_map() -> list[tuple]:
    text = DOCS03.replace("\r\n", "\n")
    start = text.index(HEADER)
    rows = []
    for line in text[start:].splitlines()[2:]:
        if not line.startswith("|"):
            break
        child, fields, parent, parent_key, kind, inactive, code = [c.strip() for c in line.strip()[1:-1].split("|")]
        rows.append((child, tuple(fields.split(" + ")), parent, tuple(parent_key.split(" + ")), kind, None if inactive == "—" else inactive, code))
    return rows


def code_map() -> list[tuple]:
    return [(r.child, r.child_match, r.parent, r.parent_match, r.kind, r.inactive, f"{r.prefix}.REF_{r.key}") for r in refs.REFERENCES]


def test_docs_table_matches_code():
    assert docs_map() == code_map()


def test_fields_exist_and_parent_key_is_part_of_the_parent_key():
    for r in refs.REFERENCES:
        child = {c.name for c in stg_columns(r.child)}
        parent = {c.name for c in stg_columns(r.parent)}
        assert set(r.child_match) <= child, r
        assert set(r.parent_match) <= parent, r
        assert len(r.fields) == len(r.parent_fields), r
        assert set(r.parent_match) <= set(key_fields(r.parent)), r
        if r.inactive:
            assert "IsActive" in parent, r
            assert r.inactive in (refs.WARNING, refs.INFO), r


def test_required_follows_the_contract():
    """Zorunlu: sözleşmede alan zorunlu (ZOR. E). Zorunlu (doluysa): rota ve iş emri operasyonunda kaynak ve kaynak grubu (biri dolu olmalı) ve
    kaydın anahtarının parçası olan bağlantı (boş yazılsaydı anahtar değişirdi, K-153); doluysa ve yoksa Hata. Öteki isteğe bağlı."""
    for r in refs.REFERENCES:
        required = {f.name: f.required for f in contract_fields(r.child)}[r.fields[0]]
        in_key = r.fields[0] in key_fields(r.child)
        expected = refs.REQUIRED if required else refs.REQUIRED_IF_FILLED if (r.child, r.fields[0]) in EITHER_ONE or in_key else refs.OPTIONAL
        assert r.kind == expected, (r.child, r.fields[0], r.kind)
    assert {(r.child, r.fields[0]) for r in refs.REFERENCES if r.kind == refs.REQUIRED_IF_FILLED} == EITHER_ONE | IN_KEY


def test_required_if_filled_is_an_error_only_when_filled():
    """Kaynağı boşaltılarak yüklenen operasyon kapasite tüketmez: doluysa ve yoksa Hata; boşsa referans kuralı çalışmaz (K-116 kuralı ayrı)."""
    by_key = cat.by_key()
    codes = [(child, f"{prefix}.REF_{key}") for child, prefix in (("Routing", "RTG"), ("WorkOrderOperation", "WOO")) for key in ("RESOURCE", "RESOURCE_GROUP")]
    codes += [("UomConversion", "UOM.REF_MATERIAL"), ("Forecast", "FC.REF_CUSTOMER"), ("Forecast", "FC.REF_PROJECT"), ("Stock", "STK.REF_PROJECT"),
              ("Stock", "STK.REF_CUSTOMER"), ("Stock", "STK.REF_SALES_ORDER")]  # anahtarın parçası: boş yazılsaydı anahtar değişirdi (K-153)
    for key in codes:
        rule = by_key[key]
        assert rule.severity == cat.ERROR and " dolu ve " in rule.condition, rule.code


def test_every_contract_reference_is_mapped():
    """docs/03'te REF olan her alan haritada (lokasyon ortak, birim alanları dışarıda); yeni referans unutulursa düşer."""
    mapped = {(r.child, f) for r in refs.REFERENCES for f in r.fields}
    for e in ENTITIES:
        for c in stg_columns(e.table):
            if "REF" in c.info.get("key", "") and c.name not in UNIT_FIELDS and c.name != "LocationCode":
                assert (e.table, c.name) in mapped, (e.table, c.name)
                assert c.name in REF_TEXT


def test_codes_are_unique_and_rules_exist():
    codes = [f"{r.prefix}.REF_{r.key}" for r in refs.REFERENCES]
    assert len(codes) == len(set(codes))
    by_key = cat.by_key()
    for r in refs.REFERENCES:
        rule = by_key[(r.child, f"{r.prefix}.REF_{r.key}")]
        assert rule.severity == (cat.ERROR if r.is_error else cat.WARNING) and rule.reads == (r.parent,) and rule.append_value
        inactive = by_key.get((r.child, f"{r.prefix}.INACTIVE_{r.key}"))
        assert (inactive is not None) == bool(r.inactive), r
        if inactive:
            assert inactive.severity == r.inactive


def test_inactive_classes_as_decided():
    """K-146: talep, açık arz ve plan yapısı Uyarı; Stok ve Üretim versiyonunda pasif malzeme Bilgi."""
    found = {(r.child, r.fields[0]): r.inactive for r in refs.REFERENCES if r.inactive}
    assert found == {
        ("SalesOrderLine", "MaterialCode"): "Uyarı", ("SalesOrderLine", "CustomerCode"): "Uyarı", ("Forecast", "MaterialCode"): "Uyarı",
        ("WorkOrder", "MaterialCode"): "Uyarı", ("PurchaseOrderLine", "MaterialCode"): "Uyarı", ("PurchaseOrderLine", "SupplierCode"): "Uyarı",
        ("BOM", "ComponentMaterialCode"): "Uyarı", ("Routing", "ResourceCode"): "Uyarı", ("MaterialSupplier", "SupplierCode"): "Uyarı",
        ("Stock", "MaterialCode"): "Bilgi", ("ProductionVersion", "MaterialCode"): "Bilgi",
    }


def test_uom_fields_match_docs06():
    docs06 = (Path(__file__).resolve().parents[1] / "docs" / "06-fonksiyonlar.md").read_text(encoding="utf-8")
    line = docs06[docs06.index("**Birim dönüşümü alanları (ALL.UOM_CONVERSION):**"):].split("\n", 1)[0]
    body = line.split(":**", 1)[1].split(". Malzeme alanı")[0]
    documented = {t.strip(): f.strip() for t, f in (p.split(":") for p in body.split("·"))}
    assert documented == {t: u for t, (u, _) in refs.UOM_FIELDS.items()}
    for table, (uom, material) in refs.UOM_FIELDS.items():
        cols = {c.name for c in stg_columns(table)}
        assert {uom, material} <= cols and re.match(r"(Component)?Uom$", uom)
