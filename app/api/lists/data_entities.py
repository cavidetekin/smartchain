"""Tablo listesi (ekran 02, fonksiyon 02, K-110): veri tablosu yok, katalog sabit değerli alt sorguya çevrilir.

Böylece ortak tablo kendiliğinden sıralar, süzer, Excel'e aktarır. Alan sayısına etiketli ek alanlar (K-88) sonradan eklenir.
"""
import sqlalchemy as sa

from app.integration.contract import ENTITIES, MASTER_DATA, TRANSACTION_DATA, base_counts
from db.models import metadata

from .definition import ListDefinition

FD = metadata.tables["adm.FieldDefinition"]


def _text(value: str) -> sa.ColumnElement:
    return sa.literal_column("N'" + value.replace("'", "''") + "'", sa.Unicode)


def _number(value: int) -> sa.ColumnElement:
    return sa.literal_column(str(int(value)), sa.Integer)


def _row(order: int, entity) -> sa.Select:
    field_count, required_count = base_counts(entity.table)
    return sa.select(_number(order).label("Id"), _text(entity.table).label("Entity"), _text(entity.name).label("Name"),
                     _text(entity.data_class).label("EntityClass"), _text(entity.description).label("Description"),
                     _number(entity.version).label("Version"),
                     _number(field_count).label("BaseFieldCount"), _number(required_count).label("RequiredCount"))


_catalog = sa.union_all(*[_row(i, e) for i, e in enumerate(ENTITIES, 1)]).subquery("catalog")
_labelled = (sa.select(sa.func.count()).select_from(FD)
             .where(FD.c.TableName == _catalog.c.Entity, FD.c.FieldName.like("Additional%"), FD.c.Label.is_not(None), FD.c.Label != "")
             .correlate(_catalog).scalar_subquery())

SOURCE = sa.select(_catalog.c.Id, _catalog.c.Id.label("CatalogOrder"), _catalog.c.Entity, _catalog.c.Name, _catalog.c.EntityClass, _catalog.c.Description, _catalog.c.Version,
                   (_catalog.c.BaseFieldCount + _labelled).label("FieldCount"), _catalog.c.RequiredCount).subquery("de")

FIELDS = ("Name", "EntityClass", "Description", "Version", "FieldCount", "RequiredCount", "CatalogOrder", "Entity")

DATA_ENTITIES = ListDefinition(
    name="data-entities",
    table="stg.*",
    title="Tablolar",
    file_slug="tablolar",
    function=2,  # Excel şablonu indirme (K-100)
    versioned=False,
    source=SOURCE,
    key_fields=("Entity", "Name", "Version"),  # satır menüsü bunları okur, kolon gizli olsa da
    fields=FIELDS,
    default_visible=tuple(f for f in FIELDS if f != "Entity"),
    default_sort=(("CatalogOrder", "asc"),),  # referans verisinden işlem verisine (docs/03)
    labels={"Name": "Tablo", "EntityClass": "Kategori", "Description": "Açıklama", "Version": "Sürüm", "FieldCount": "Toplam alan", "RequiredCount": "Zorunlu alan",
            "Entity": "Teknik tablo adı", "CatalogOrder": "Yükleme sırası"},
    values={"EntityClass": [MASTER_DATA, TRANSACTION_DATA]},
)
