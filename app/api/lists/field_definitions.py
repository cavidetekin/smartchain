"""Veri sözlüğü listesi (adm.FieldDefinition; ekran 25, fonksiyon 96, K-104). Sürümsüzdür.

Anahtar bileşik olduğu için Id alt sorguda üretilir (liste bileşeni sıralama ve seçim için ister); satır işlemi TableName ve
FieldName ile yapılır, bunlar görünmese de her satırda döner (key_fields).
"""
import sqlalchemy as sa

from db.models import metadata

from .definition import ListDefinition

FD = metadata.tables["adm.FieldDefinition"]

SOURCE = sa.select(
    sa.func.row_number().over(order_by=(FD.c.TableName, FD.c.FieldName)).label("Id"),
    FD.c.TableName, FD.c.FieldName,
    sa.func.coalesce(FD.c.Label, FD.c.StandardLabel).label("DisplayLabel"), FD.c.Description,
    FD.c.FieldClass, FD.c.ManualOverrides, FD.c.EditableInWorkspace, FD.c.IsRequired, FD.c.IfEmpty,
    sa.cast(sa.case((FD.c.FieldName.like("Additional%"), 1), else_=0), sa.Boolean).label("IsAdditional"),
).subquery("fd")

# Değer önceliği listede yok: öncelik sabit, manuel > kural > ERP; bilgiyi Manuel verir (K-172)
FIELDS = ("TableName", "FieldName", "DisplayLabel", "Description", "FieldClass", "ManualOverrides",
          "EditableInWorkspace", "IsRequired", "IfEmpty", "IsAdditional")

FIELD_DEFINITIONS = ListDefinition(
    name="field-definitions",
    table="adm.FieldDefinition",
    title="Veri sözlüğü",
    file_slug="veri-sozlugu",
    function=96,  # Sistem ayarları (K-100)
    versioned=False,
    source=SOURCE,
    key_fields=("TableName", "FieldName"),
    fields=FIELDS,
    # açıklama Alanlar panelinden açılır; Senaryo Aşama 8'e kadar gizli (K-172)
    default_visible=tuple(f for f in FIELDS if f not in ("Description", "EditableInWorkspace")),
    default_sort=(("TableName", "asc"), ("FieldName", "asc")),
    labels={"TableName": "Tablo", "FieldName": "Alan", "DisplayLabel": "Etiket", "Description": "Açıklama", "FieldClass": "Sınıf",
            "ManualOverrides": "Manuel", "EditableInWorkspace": "Senaryo",
            "IsRequired": "Zorunlu", "IfEmpty": "Boşsa", "IsAdditional": "Ek alan"},
    values={"FieldClass": FD.c.FieldClass.info["values"]},
    server_values=frozenset({"TableName"}),
)
