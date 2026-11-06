"""Kuralların ortak SQL parçaları: güncel satırlar, değer biçimi, kayıt anahtarı, alan etiketi (K-133, K-134)."""
from functools import lru_cache

import sqlalchemy as sa

from app.integration.contract import fields as contract_fields, stg_columns
from app.integration.structural import key_fields
from db.models import metadata

ROW_KEY_SEPARATOR = " · "


def table(name: str) -> sa.Table:
    return metadata.tables[f"stg.{name}"]


def alias(name: str, suffix: str = "") -> sa.Alias:
    return table(name).alias(f"{name.lower()}{suffix}")


def current(t) -> sa.ColumnElement:
    return t.c.IsCurrent == sa.true()


def nz(col) -> sa.ColumnElement:
    """Boş bayrak "yok" demektir (BOŞSA, K-138)."""
    return sa.func.coalesce(col, 0)


def one(col) -> sa.ColumnElement:
    return col == sa.true()


def same(a, b) -> sa.ColumnElement:
    """Boş değerler eşit sayılır (anahtar karşılaştırması)."""
    return sa.or_(a == b, sa.and_(a.is_(None), b.is_(None)))


def text(value: str) -> sa.ColumnElement:
    return sa.literal(value, sa.Unicode)


def shown(col) -> sa.ColumnElement:
    """Bulgudaki değerin okunur biçimi: sayı Türkçe, tarih gg.aa.yyyy (K-88)."""
    t = col.type
    if isinstance(t, sa.Boolean):
        return sa.cast(sa.cast(col, sa.Integer), sa.Unicode(5))
    if isinstance(t, (sa.Numeric, sa.Integer)):
        return sa.func.format(sa.cast(col, sa.Float), "G15", "tr-TR")
    if isinstance(t, (sa.Date, sa.DateTime)):
        return sa.func.format(col, "dd.MM.yyyy")
    return sa.cast(col, sa.Unicode(255))


def _key_part(col) -> sa.ColumnElement:
    if isinstance(col.type, (sa.Date, sa.DateTime)):
        return sa.func.convert(sa.literal_column("nvarchar(10)"), col, 104)
    return sa.cast(col, sa.Unicode(200))


def row_key(t, entity: str) -> sa.ColumnElement:
    """Kaydın anahtarı, ön kontroldeki gibi boşlar atlanarak (CONCAT_WS)."""
    keys = key_fields(entity)
    if not keys:
        return sa.null()
    if len(keys) == 1:
        return sa.func.left(_key_part(t.c[keys[0]]), 200)
    return sa.func.left(sa.func.concat_ws(ROW_KEY_SEPARATOR, *[_key_part(t.c[k]) for k in keys]), 200)


@lru_cache(maxsize=None)
def labels(entity: str) -> dict[str, str]:
    """Alanın standart etiketi (sözleşme); etiketsiz alanda ad."""
    found = {f.name: f.label for f in contract_fields(entity)}
    return {c.name: found.get(c.name, c.name) for c in stg_columns(entity)}


def label(entity: str, field: str | None) -> str | None:
    return labels(entity).get(field, field) if field else None
