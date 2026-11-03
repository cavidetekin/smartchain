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
    FD.c.FieldClass, FD.c.ValuePriority, FD.c.ManualOverrides, FD.c.EditableInWorkspace, FD.c.IsRequired, FD.c.DefaultValue,
    sa.cast(sa.case((FD.c.FieldName.like("Additional%"), 1), else_=0), sa.Boolean).label("IsAdditional"),
).subquery("fd")

FIELDS = ("TableName", "FieldName", "DisplayLabel", "Description", "FieldClass", "ValuePriority", "ManualOverrides",
          "EditableInWorkspace", "IsRequired", "DefaultValue", "IsAdditional")

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
    default_visible=tuple(f for f in FIELDS if f != "Description"),  # açıklama Alanlar panelinden açılır
    default_sort=(("TableName", "asc"), ("FieldName", "asc")),
    labels={"TableName": "Tablo", "FieldName": "Alan", "DisplayLabel": "Etiket", "Description": "Açıklama", "FieldClass": "Sınıf",
            "ValuePriority": "Değer önceliği", "ManualOverrides": "Manuel", "EditableInWorkspace": "Senaryo",
            "IsRequired": "Zorunlu", "DefaultValue": "Varsayılan değer", "IsAdditional": "Ek alan"},
    values={"FieldClass": FD.c.FieldClass.info["values"], "ValuePriority": FD.c.ValuePriority.info["values"]},
    server_values=frozenset({"TableName"}),
)
