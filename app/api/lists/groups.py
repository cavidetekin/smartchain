"""Grup ağacı (K-90): yaprak grup satırlarından üst grupları ve ara toplamları kurar.

Yaprak satırı her ara toplam için ölçü taşır: k_ katkı veren satır sayısı, s_ pay, d_ payda, v_ en küçük / en büyük.
Üst gruplar alt gruplardan tam türetilir: toplam ve sayı toplanır, ortalamalar payı ve paydası toplanarak (ağırlıklı)
birleşir, en küçük / en büyük karşılaştırılır. Birim, satırlarda gizli son düzeydir ("u"); aynı grup anahtarı birim
başına birden çok satırda gelebilir. Birime bağlı ara toplamda katkı veren satırların birimi farklıysa değer verilmez ve
kolon mixed_units'te listelenir (K-88).
"""
from collections.abc import Callable, Mapping

RATIO = {"avg", "avg_nonzero", "wavg"}


class _Node:
    __slots__ = ("key", "count", "k", "s", "d", "v", "units", "children")

    def __init__(self, key: list):
        self.key = key
        self.count = 0
        self.k: dict[str, int] = {}
        self.s: dict[str, float] = {}
        self.d: dict[str, float] = {}
        self.v: dict[str, float] = {}
        self.units: dict[str, set] = {}
        self.children: dict | None = None

    def add(self, row: Mapping, fns: Mapping[str, str], unit_fields: set[str]):
        self.count += int(row["n"])
        for f, fn in fns.items():
            k = int(row.get(f"k_{f}") or 0)
            if not k:
                continue
            self.k[f] = self.k.get(f, 0) + k
            if f in unit_fields:
                self.units.setdefault(f, set()).add(row.get("u"))
            if fn in ("sum", *RATIO):
                self.s[f] = self.s.get(f, 0.0) + float(row[f"s_{f}"] or 0)
                self.d[f] = self.d.get(f, 0.0) + float(row[f"d_{f}"] or 0)
            elif fn in ("min", "max") and row.get(f"v_{f}") is not None:
                v = float(row[f"v_{f}"])
                old = self.v.get(f)
                self.v[f] = v if old is None else (min(old, v) if fn == "min" else max(old, v))


def _aggregates(node: _Node, fns: Mapping[str, str], unit_decimals: Mapping) -> tuple[dict, list[str], dict]:
    """Ara toplamlar, birimi karışık kolonlar ve tek birimli miktar kolonlarının ondalığı (birim bilinmiyorsa 2)."""
    out, mixed, decimals = {}, [], {}
    for f, fn in fns.items():
        units = node.units.get(f, set())
        if len(units) > 1:
            out[f] = None
            mixed.append(f)
            continue
        if units:
            d = unit_decimals.get(next(iter(units)))
            decimals[f] = 2 if d is None else int(d)
        if fn == "count":
            out[f] = node.k.get(f, 0)
        elif not node.k.get(f):
            out[f] = None
        elif fn == "sum":
            out[f] = node.s[f]
        elif fn in RATIO:
            out[f] = node.s[f] / node.d[f] if node.d.get(f) else None  # ağırlıklar toplamı 0: boş
        else:
            out[f] = node.v.get(f)
    return out, mixed, decimals


def build_tree(leaves: list[Mapping], depth: int, fns: Mapping[str, str], unit_fields: set[str],
               to_json: Callable = lambda v: v, unit_decimals: Mapping | None = None) -> dict:
    """leaves: groups_query satırları (sıralı); fns: alan → ara toplam türü; unit_fields: birim kuralına giren alanlar.
    Sıra korunur: üst grup ilk göründüğü yerde durur."""
    root = _Node([])
    root.children = {}
    for row in leaves:
        values = [to_json(row[f"g{i}"]) for i in range(depth)]
        root.add(row, fns, unit_fields)
        node = root
        for d in range(depth):
            if node.children is None:
                node.children = {}
            k = tuple(values[: d + 1])
            if k not in node.children:
                node.children[k] = _Node(list(k))
            node = node.children[k]
            node.add(row, fns, unit_fields)

    units = unit_decimals or {}

    def out(node: _Node) -> dict:
        aggs, mixed, decimals = _aggregates(node, fns, units)
        item = {"key": node.key, "count": node.count, "aggregates": aggs, "mixed_units": mixed, "unit_decimals": decimals}
        if node.children:
            item["children"] = [out(c) for c in node.children.values()]
        return item

    aggs, mixed, decimals = _aggregates(root, fns, units)
    leaf_groups = len({tuple(to_json(row[f"g{i}"]) for i in range(depth)) for row in leaves})
    return {"groups": [out(c) for c in root.children.values()], "aggregates": aggs, "mixed_units": mixed,
            "unit_decimals": decimals, "leaf_groups": leaf_groups}
