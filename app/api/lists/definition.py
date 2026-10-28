"""Liste tanımı ve kolon bilgisi (K-87, K-88; docs/08 "Liste sorgusu").

Kolonun etiketi ve değer listesi docs'tan üretilen modelde (`info`), tipi veritabanı tipinden gelir.
"""
import re
from collections.abc import Mapping
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
    title: str = ""                            # Excel Bilgi sayfası ve bildirimdeki ad (ör. "Malzeme listesi")
    file_slug: str = ""                        # dosya adındaki kısa ad: smartchain_<file_slug>_… (K-91)
    # Gösterilecek ondalık (K-88, docs/12): veritabanı ölçeğinden değil, alanın anlamından. Her number alanı ya burada
    # ya da unit_decimals'ta ("ondalık birimden": satırın birimi unit_field'dan, ondalığı UnitOfMeasure.Decimals'tan).
    decimals: Mapping[str, int] = field(default_factory=dict)
    unit_field: str | None = None
    unit_decimals: frozenset[str] = field(default_factory=frozenset)
    # Gruplamada varsayılan ara toplam (K-90): request.AGG_FNS'ten biri; yazılmayan kolonun varsayılanı yok.
    aggregates: Mapping[str, str] = field(default_factory=dict)

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
            "decimals": (None if name in defn.unit_decimals else defn.decimals[name]) if kind == "number"
                        else 0 if kind == "integer" else None,
            "decimals_from_unit": name in defn.unit_decimals,
            "aggregate": defn.aggregates.get(name),
            "default_visible": name in defn.default_visible,
        })
    return out
