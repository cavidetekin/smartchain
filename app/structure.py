"""Ürün yapısının ortak koşulları (K-200): hangi üretim versiyonu ve hangi ağaç satırı "kenar" sayılır.

Tanım alokasyon kuralındakiyle aynıdır (`app/allocation/rules.py`, K-199): güncel ve aktif her üretim versiyonu, ağacına `BOMCode` ile bağlanır (K-115);
kendi aktif versiyonu olmayan malzeme benzetildiği ürünün ağacını kullanır (K-126). Geçerlilik tarihi süzülmez. İfadeler SQL metnidir; takma adlar
çağıranındır. Şimdilik yalnız Üretim akışı kullanır; alokasyon kuralı ve talep zinciri kendi kopyalarını taşır (GELISTIRME_ADIMLARI "Bekleyen kontroller").
"""


def active(alias: str) -> str:
    """Güncel ve aktif kayıt (`IsActive` boşsa aktif sayılır)."""
    return f"{alias}.VersionTo IS NULL AND ISNULL({alias}.IsActive, 1) = 1"


def bom_of(version: str, bom: str) -> str:
    """Üretim versiyonunun güncel ağaç satırları (K-115): ağaç kodu, lokasyon ve malzeme eşleşir."""
    return (f"{bom}.Code = {version}.BOMCode AND {bom}.LocationId = {version}.LocationId AND {bom}.MaterialId = {version}.MaterialId "
            f"AND {bom}.VersionTo IS NULL")


def reference_of(reference: str, version: str) -> str:
    """Benzetilen ürün kaydının gösterdiği üretim versiyonları (K-126): versiyon verilmişse o, verilmemişse benzetilen ürünün bütün versiyonları."""
    return (f"(({reference}.ReferenceProductionVersionId IS NOT NULL AND {version}.Id = {reference}.ReferenceProductionVersionId) "
            f"OR ({reference}.ReferenceProductionVersionId IS NULL AND {version}.MaterialId = {reference}.ReferenceMaterialId))")


def has_own_version(material: str, location: str, version: str = "o") -> str:
    """Malzemenin kendi aktif üretim versiyonu var mı (varsa benzetilen ürüne bakılmaz, K-126). `material` ve `location`: malzemenin kimliği ve
    lokasyonu (ifade); lokasyon koşulu tekil indeksle aramayı sağlar (malzeme kimliği zaten lokasyona özgüdür)."""
    return (f"EXISTS (SELECT 1 FROM core.ProductionVersion {version} WHERE {version}.LocationId = {location} AND {version}.MaterialId = {material} "
            f"AND {active(version)})")
