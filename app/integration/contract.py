"""Veri sözleşmesi (docs/03, K-46, K-110): tablo kataloğu ve şablon alanları. Veritabanı bilmez; etiketleri çağıran verir.

Alan bilgisi docs/03'ten üretilen modelde (`stg` kolon info). `FieldDefinition` yalnız etiket verir (K-104'te `stg` yok).
"""
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

import sqlalchemy as sa

from db.dictionary import description, is_additional
from db.models import ENTITY_CATALOG, metadata

FIRST_DATA_ROW = 2
STG_EXCLUDED = frozenset({"StagingRowId", "ImportBatchId", "RowStatus", "ErrorText", "SourceRowNo", "IsCurrent"})
ERROR_COLUMN = "Hata"  # hata raporunun son kolonu (K-129)
MASTER_DATA, TRANSACTION_DATA = "Ana veri", "İşlem verisi"
EXAMPLES = Path(__file__).with_name("template_examples.json")   # sentetik veriden türetilmiş sabit örnekler
EXAMPLE_TEXT, EXAMPLE_NUMBER = "Örnek", 10                      # etiketlenen ek alanlar

UNIT_CODE = "Birim kodu; yeni kod yüklemede oluşur"  # birim şablonu yok, kod yüklemede oluşur (K-112)
BLANK_ROW_REJECTED = "Satır yüklenmez"
AFTER_RULES = "hata (kurallardan sonra)"          # BOŞSA (K-138): kuralla dolabilir, dolmazsa validasyonda Hata
LEAD_TIME_AFTER_RULES = "tedarik süresi doluysa hata (kurallardan sonra)"
EITHER = "alternatif "   # iki alandan biri dolu olmalı (K-116); kontrolü validasyonda (RTG.NO_RESOURCE, WOO.NO_RESOURCE)
BLANK_MEANINGS = {      # docs/03 BOŞSA → şablonun "Boş bırakılırsa" satırı
    "yok": "Yok sayılır",
    "sınırsız": "Sınır yok",
    "bilinmiyor": "Bilinmiyor; planda kullanılmaz",
    "temel birim": "Temel birimde kabul edilir",
    "tam gün": "Tam gün kabul edilir",
    "ilk operasyon": "İlk operasyonda gerekir",
    "motor seçer": "Plan hesabı seçer",
    "gruptan": "Proje grubunun değeri geçerli",
    "müşteriden": "Müşterinin değeri geçerli",
    "bütün malzemeler": "Bütün malzemelere uygulanır",
}

# Referans alanı → hangi tablonun kodu (docs/03 ANAHTAR = REF; yeni referans eklenince test düşer).
REF_TEXT = {
    "LocationCode": "Lokasyon tablosundaki kod", "BaseUom": UNIT_CODE, "FromUom": UNIT_CODE,
    "ToUom": UNIT_CODE, "ComponentUom": UNIT_CODE, "Uom": UNIT_CODE, "CapacityUnit": UNIT_CODE, "MaterialCode": "Malzeme tablosundaki kod",
    "ComponentMaterialCode": "Malzeme tablosundaki kod", "ResourceCode": "Kaynak tablosundaki kod",
    "ResourceGroupCode": "Kaynak grubu tablosundaki kod",
    "SubcontractorCode": "Tedarikçi tablosundaki kod", "SupplierCode": "Tedarikçi tablosundaki kod",
    "CustomerCode": "Müşteri tablosundaki kod", "ProjectCode": "Proje tablosundaki kod",
    "LendingProjectCode": "Proje tablosundaki kod", "BorrowingProjectCode": "Proje tablosundaki kod", "ProjectGroupCode": "Proje grubu tablosundaki kod",
    "SalesOrderNo": "Satış siparişi tablosundaki sipariş numarası", "SalesOrderLineNo": "Satış siparişi tablosundaki satır numarası",
    "SalesOrderLineItemNo": "Satış siparişi tablosundaki alt satır numarası",
    "WorkOrderNo": "İş emri tablosundaki numara", "ParentWorkOrderNo": "İş emri tablosundaki numara",
    "ProductionVersionCode": "Üretim versiyonu tablosundaki kod", "ReferenceProductionVersionCode": "Üretim versiyonu tablosundaki kod",
    "ReferenceMaterialCode": "Malzeme tablosundaki kod",
}


@dataclass(frozen=True)
class Entity:
    table: str
    name: str
    data_class: str
    description: str
    slug: str
    version: int

    @property
    def file_name(self) -> str:
        return f"smartchain_{self.slug}_v{self.version}.xlsx"


# docs/03 "Varlık kataloğu"ndan üretilir (K-64). Sözleşme değişince sürüm orada artar (tests/template_versions.json).
ENTITIES: tuple[Entity, ...] = tuple(Entity(*row) for row in ENTITY_CATALOG)
_BY_TABLE = {e.table: e for e in ENTITIES}


def entity(table: str) -> Entity | None:
    return _BY_TABLE.get(table)


@dataclass(frozen=True)
class TemplateField:
    name: str
    label: str
    description: str                # etiketle aynıysa ya da yalnız değer listesiyse boş
    kind: str                       # text | number | integer | date | datetime | bool
    type_text: str
    required: bool                  # boşsa satır yüklenmez
    blank: str                      # boş bırakılırsa ne olur
    values: tuple[str, ...]         # Smartchain değerleri
    ref_text: str                   # referansta hangi tablonun kodu
    example: object


def stg_columns(table: str) -> list[sa.Column]:
    """Şablona girebilecek kolonlar (sistem alanları hariç), docs/03'teki sırayla."""
    return [c for c in metadata.tables[f"stg.{table}"].columns if c.name not in STG_EXCLUDED]


def _kind(col: sa.Column) -> tuple[str, str]:
    t = col.type
    if isinstance(t, sa.Boolean):
        return "bool", "1 = Evet, 0 = Hayır"
    if isinstance(t, sa.DateTime):
        return "datetime", "Tarih ve saat"
    if isinstance(t, sa.Date):
        return "date", "Tarih"
    if isinstance(t, sa.Integer):
        return "integer", "Tam sayı"
    if isinstance(t, sa.Numeric):
        return "number", "Sayı"
    return "text", f"Metin, en çok {t.length}" if getattr(t, "length", None) else "Metin"


def _standard_label(table: str, col: sa.Column) -> str | None:
    core = metadata.tables[f"core.{table}"].c.get(col.name)
    return (core.info.get("label") if core is not None else None) or col.info.get("label")


def blank_text(missing: str) -> str:
    """docs/03 BOŞSA → kullanıcının okuyacağı somut sonuç (K-138). Bilinmeyen değer test düşürür."""
    if missing == "hata (satır atlanır)":
        return BLANK_ROW_REJECTED
    if missing == AFTER_RULES:
        return "Veri kuralıyla doldurulur; dolmazsa satır yüklenmez"
    if missing == LEAD_TIME_AFTER_RULES:
        return "Tedarik süresi doluysa veri kuralıyla doldurulur; dolmazsa satır yüklenmez"
    if missing.startswith(EITHER):
        return f"{missing.removeprefix(EITHER)} da boşsa satır yüklenmez"
    if missing in BLANK_MEANINGS:
        return BLANK_MEANINGS[missing]
    raise ValueError(f"Bilinmeyen BOŞSA: {missing!r}")


def _description(col: sa.Column, label: str) -> str:
    """Etiketle aynıysa ya da yalnız değer listesiyse boş; ek alanda teknik not yok."""
    if is_additional(col.name):
        return ""
    text = description(col.name, col.comment) or ""
    values = col.info.get("values") or []
    return "" if text == label or (values and text == " | ".join(values)) else text


@lru_cache(maxsize=1)
def _examples() -> dict[str, dict]:
    return json.loads(EXAMPLES.read_text(encoding="utf-8"))


def _example(table: str, name: str, kind: str):
    """Tip korunur: sayı sayı, tarih tarih olarak yazılır."""
    if is_additional(name):
        return EXAMPLE_NUMBER if kind == "number" else EXAMPLE_TEXT
    value = _examples()[table][name]
    if kind == "datetime":
        return datetime.fromisoformat(value)
    return date.fromisoformat(value) if kind == "date" else value


def fields(table: str, labels: Mapping[str, str] | None = None) -> list[TemplateField]:
    """Şablonun alanları. labels: FieldDefinition.Label (alan → etiket). Etiketsiz ek alan şablona girmez (K-88)."""
    labels = labels or {}
    out = []
    for col in stg_columns(table):
        label = labels.get(col.name) or (None if is_additional(col.name) else _standard_label(table, col))
        if not label:
            continue
        kind, type_text = _kind(col)
        blank = blank_text(col.info.get("missing", ""))
        out.append(TemplateField(
            name=col.name, label=label, description=_description(col, label), kind=kind, type_text=type_text,
            required=blank == BLANK_ROW_REJECTED, blank=blank,
            values=tuple(col.info.get("values") or ()),
            ref_text=REF_TEXT.get(col.name, "") if "REF" in col.info.get("key", "") else "",
            example=_example(table, col.name, kind)))
    return out


def base_counts(table: str) -> tuple[int, int]:
    """(ek alan hariç alan sayısı, zorunlu alan sayısı)."""
    found = fields(table)
    return len(found), sum(f.required for f in found)


def contract_hash(table: str) -> str:
    """Sözleşmenin özeti: alan, tip, zorunlu, ön kontrolde boşsa satır atlanır mı, liste, anahtar; bütün ek alanlar dahil.
    Etiket ve BOŞSA'nın açıklama metni girmez (K-138): eşleşme teknik adla, Açıklama sayfası yeni metni hemen gösterir."""
    parts = [(c.name, str(c.type), bool(c.info.get("required")), blank_text(c.info.get("missing", "")) == BLANK_ROW_REJECTED,
              c.info.get("values") or [], c.info.get("key", ""))
             for c in stg_columns(table)]
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]
