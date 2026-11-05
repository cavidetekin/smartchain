"""Yükleme bulguları (ekran 02, fonksiyon 03, K-129): arayüz partiyi sabit filtreyle verir (baseFilters)."""
from db.models import metadata

from .definition import ListDefinition

T = metadata.tables["adm.ImportFinding"]

FIELDS = ("RowNo", "RowKey", "FieldName", "Value", "Message", "Severity", "ImportBatchId")

IMPORT_FINDINGS = ListDefinition(
    name="import-findings",
    table="adm.ImportFinding",
    title="Ön kontrol bulguları",
    file_slug="on-kontrol-bulgulari",
    function=3,  # Excel ile yükleme (K-100)
    versioned=False,
    source=T,
    fields=FIELDS,
    default_visible=("RowNo", "RowKey", "FieldName", "Value", "Message", "Severity"),
    default_sort=(("RowNo", "asc"),),
    labels={"RowNo": "Satır", "RowKey": "Kayıt", "FieldName": "Alan", "Value": "Değer", "Message": "Sorun", "Severity": "Önem", "ImportBatchId": "Parti"},
    values={"Severity": ["Hata", "Uyarı", "Bilgi"]},
)
