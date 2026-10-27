"""Grup ağacı (K-90): yaprak grup satırlarından üst grupları ve ara toplamları kurar.

Toplam üst gruplarda toplanır; ortalama ağırlıklıdır (boş olmayan değer sayısıyla). Birimden ondalıklı (miktar)
kolonlarda grupta birden çok birim varsa değer verilmez ve kolon mixed_units'te listelenir (K-88). Birim, satırlarda
gizli son düzeydir ("u"); aynı grup anahtarı birim başına birden çok satırda gelebilir.
"""
from collections.abc import Callable, Mapping


class _Node:
    __slots__ = ("key", "count", "sums", "counts", "units", "children")

    def __init__(self, key: list):
        self.key = key
        self.count = 0
        self.sums: dict[str, float] = {}
        self.counts: dict[str, int] = {}
        self.units: dict[str, set] = {}
        self.children: dict | None = None

    def add(self, row: Mapping, fields: list[str], unit_fields: set[str]):
        self.count += int(row["n"])
        for f in fields:
            s, c = row[f"s_{f}"], int(row[f"c_{f}"] or 0)
            if c:
                self.sums[f] = self.sums.get(f, 0) + float(s)
                self.counts[f] = self.counts.get(f, 0) + c
            if f in unit_fields and c:  # birim gizli düzey ("u"): değeri olan satırların birimleri
                self.units.setdefault(f, set()).add(row.get("u"))


def _aggregates(node: _Node, aggregates: Mapping[str, str], unit_decimals: Mapping) -> tuple[dict, list[str], dict]:
    """Ara toplamlar, birimi karışık kolonlar ve tek birimli miktar kolonlarının ondalığı (birim bilinmiyorsa 2)."""
    out, mixed, decimals = {}, [], {}
    for f, kind in aggregates.items():
        units = node.units.get(f, set())
        if len(units) > 1:
            out[f] = None
            mixed.append(f)
            continue
        if units:
            d = unit_decimals.get(next(iter(units)))
            decimals[f] = 2 if d is None else int(d)
        out[f] = None if not node.counts.get(f) else (node.sums[f] if kind == "sum" else node.sums[f] / node.counts[f])
    return out, mixed, decimals


def build_tree(leaves: list[Mapping], depth: int, aggregates: Mapping[str, str], unit_fields: set[str],
               to_json: Callable = lambda v: v, unit_decimals: Mapping | None = None) -> dict:
    """leaves: groups_query satırları (sıralı). Sıra korunur: üst grup ilk göründüğü yerde durur."""
    fields = list(aggregates)
    root = _Node([])
    root.children = {}
    for row in leaves:
        values = [to_json(row[f"g{i}"]) for i in range(depth)]
        root.add(row, fields, unit_fields)
        node = root
        for d in range(depth):
            if node.children is None:
                node.children = {}
            k = tuple(values[: d + 1])
            if k not in node.children:
                node.children[k] = _Node(list(k))
            node = node.children[k]
            node.add(row, fields, unit_fields)

    units = unit_decimals or {}

    def out(node: _Node) -> dict:
        aggs, mixed, decimals = _aggregates(node, aggregates, units)
        item = {"key": node.key, "count": node.count, "aggregates": aggs, "mixed_units": mixed, "unit_decimals": decimals}
        if node.children:
            item["children"] = [out(c) for c in node.children.values()]
        return item

    aggs, mixed, decimals = _aggregates(root, aggregates, units)
    leaf_groups = len({tuple(to_json(row[f"g{i}"]) for i in range(depth)) for row in leaves})
    return {"groups": [out(c) for c in root.children.values()], "aggregates": aggs, "mixed_units": mixed,
            "unit_decimals": decimals, "leaf_groups": leaf_groups}
