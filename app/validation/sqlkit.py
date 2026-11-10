"""Kuralların ortak SQL parçaları: katmanlar, güncel satırlar, değer biçimi, kayıt anahtarı, alan etiketi (K-133, K-134, K-140).

Validasyon ve veri kuralları işlenmiş katmanı (`prc`) okur; ham katman (`stg`) yalnız güncel hâle işleme ve kopya içindir."""
from functools import lru_cache

import sqlalchemy as sa

from app.integration.contract import fields as contract_fields, stg_columns
from app.integration.structural import key_fields
from db.dictionary import standard_label
from db.models import metadata

ROW_KEY_SEPARATOR = " · "


def table(name: str) -> sa.Table:
    """İşlenmiş katman (K-140): validasyon ve veri kuralları bunu okur."""
    return metadata.tables[f"prc.{name}"]


def raw_table(name: str) -> sa.Table:
    """Ham katman: hiç değişmez; güncel hâli IsCurrent (K-133)."""
    return metadata.tables[f"stg.{name}"]


def alias(name: str, suffix: str = "") -> sa.Alias:
    return table(name).alias(f"{name.lower()}{suffix}")


def current(t) -> sa.ColumnElement:
    """Validasyona giren satırlar. Ham katmanda güncel hâl (IsCurrent, K-133). İşlenmiş katmanda her satır günceldir (K-140);
    IsActive = Hayır olan satır kapsam dışıdır, hiçbir validasyon kuralına girmez; IsActive boşsa girer, zorunlu alan bulgusu alır (K-145)."""
    if "IsCurrent" in t.c:
        return t.c.IsCurrent == sa.true()
    if "IsActive" in t.c:
        return sa.or_(t.c.IsActive.is_(None), t.c.IsActive == sa.true())
    return sa.true()


def present(t) -> sa.ColumnElement:
    """Ebeveyn aranırken bakılan satırlar (K-146): işlenmiş katmanın bütün satırları; pasif ebeveyn de vardır, pasifliğine ayrı kural bakar.
    Ham katmanda güncel hâl."""
    if "IsCurrent" in t.c:
        return t.c.IsCurrent == sa.true()
    return sa.true()


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
    """Alanın standart etiketi (sözleşme); ek alanda "Ek sayı alanı 1" (etiketi veri sözlüğünde, K-59), etiketsiz alanda ad."""
    found = {f.name: f.label for f in contract_fields(entity)}
    return {c.name: found.get(c.name) or standard_label(c.name, None) or c.name for c in stg_columns(entity)}


def label(entity: str, field: str | None) -> str | None:
    return labels(entity).get(field, field) if field else None
