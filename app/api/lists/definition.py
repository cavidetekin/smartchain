"""Liste tanımı ve kolon bilgisi (K-87, K-88; docs/08 "Liste sorgusu").

Kolonun etiketi ve değer listesi docs'tan üretilen modelde (`info`), tipi veritabanı tipinden gelir.
"""
import re
from dataclasses import dataclass, field

import sqlalchemy as sa

from db.models import metadata

ADDITIONAL = re.compile(r"Additional(Text|Number)\d+$")


@dataclass(frozen=True)
class ListDefinition:
    name: str                                  # adres adı: /api/<name>/…
    table: str                                 # şema.tablo
    fields: tuple[str, ...]                    # paneldeki sıra
    default_visible: tuple[str, ...]
    default_sort: tuple[tuple[str, str], ...]
    server_values: frozenset[str] = field(default_factory=frozenset)  # liste filtresi, değerler sunucudan

    @property
    def sa_table(self) -> sa.Table:
        return metadata.tables[self.table]

    @property
    def table_name(self) -> str:
        return self.table.split(".", 1)[1]


def column_type(col: sa.Column) -> str:
    t = col.type
    if isinstance(t, sa.Boolean):
        return "bool"
    if isinstance(t, sa.DateTime):
        return "datetime"
    if isinstance(t, sa.Date):
        return "date"
    if isinstance(t, sa.Integer):
        return "integer"
    if isinstance(t, sa.Numeric):
        return "number"
    return "text"


def filter_type(defn: ListDefinition, col: sa.Column) -> str:
    kind = column_type(col)
    if kind == "bool" or col.info.get("values") or col.name in defn.server_values:
        return "list"
    return {"integer": "number", "number": "number", "date": "date", "datetime": "date"}.get(kind, "text")


def columns(defn: ListDefinition, labels: dict[str, str]) -> list[dict]:
    """Kolonlar; labels: FieldDefinition.Label (alan → etiket). Etiketsiz ek alan listelenmez (K-88)."""
    table = defn.sa_table
    out = []
    for name in defn.fields:
        col = table.c[name]
        label = labels.get(name) or col.info.get("label")
        if not label or (ADDITIONAL.match(name) and name not in labels):
            continue
        kind = column_type(col)
        values = [True, False] if kind == "bool" else col.info.get("values")
        out.append({
            "field": name, "label": label, "type": kind, "filter": filter_type(defn, col),
            "values": values, "values_from_server": name in defn.server_values,
            "decimals": min(col.type.scale or 0, 2) if kind == "number" else None,
            "default_visible": name in defn.default_visible,
        })
    return out
