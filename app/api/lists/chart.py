"""Tablonun grafiği için toplama (K-178, docs/08 "Grafik"): listeyle aynı filtre, veri versiyonu ve satır kapsamı.

Tek sorgu yatay eksen, kırılım ve (gerekirse) birim düzeyinde yaprak ölçüleri verir (satır sayısı, pay, payda, en küçük, en büyük); "en büyük N +
Diğer", boş dönemlerin doldurulması ve birim karışıklığı Python'da bulunur. Ölçüler birleştirilebilir olduğundan "Diğer" kalan satırlardan doğru
hesaplanır (ortalama, en küçük ve en büyük dahil). Saat kırılımı yoktur: tarih-saat alanı API sunucusunun yerel gününe indirgenir (filtredeki gün
sınırıyla aynı).
"""
from datetime import date, datetime, timedelta

import sqlalchemy as sa

from .definition import column_type
from .query import PARALLEL_HINT, Builder, ListQueryError
from .request import ChartAxis, ChartRequest, ChartSeriesSpec

MAX_SPLIT = 11        # kırılımda en büyük 11 + "Diğer"
MAX_PERIODS = 400
MAX_DRAWN = 24        # seri × kırılım
TOO_MANY_PERIODS = "Dönem sayısı çok fazla; daha büyük bir dönem seçin."


class TooManyPeriods(Exception):
    """Dönem sayısı MAX_PERIODS'u aştı (422 too_many_periods)."""
OTHER = "__other__"   # "Diğer" anahtarı (etiketi arayüz yazar)
DATE_KINDS = ("date", "datetime")
CATEGORY_KINDS = ("text", "bool", "integer")
NUMERIC_KINDS = ("number", "integer")
TR_ORDER = {ch: i for i, ch in enumerate("0123456789aâbcçdefgğhıiîjklmnoöpqrsştuüûvwxyz")}


def tr_key(text: str) -> list[int]:
    """Türkçe sıralama anahtarı (büyük/küçük harf duyarsız)."""
    folded = str(text).replace("İ", "i").replace("I", "ı").lower()
    return [TR_ORDER.get(ch, 1000 + ord(ch)) for ch in folded]


def problems(b: Builder, x: ChartAxis, split: str | None, series: list[ChartSeriesSpec], where: str = "") -> list[dict]:
    """Alan, dönem ve toplama doğrulaması; istek ve kayıtlı görünüm aynı kuralla (422)."""
    out: list[dict] = []

    def kind_of(name: str | None, at: str) -> str | None:
        if name not in b.columns:
            out.append({"field": at, "problem": f"Bilinmeyen alan: {name}"})
            return None
        return column_type(b.table.c[name])

    kind = kind_of(x.field, f"{where}x.field")
    if kind in DATE_KINDS and x.bucket is None:
        out.append({"field": f"{where}x.bucket", "problem": "Tarih alanında dönem seçilmeli"})
    elif kind is not None and kind not in DATE_KINDS:
        if x.bucket is not None:
            out.append({"field": f"{where}x.bucket", "problem": "Dönem yalnız tarih alanında seçilir"})
        if kind not in CATEGORY_KINDS:
            out.append({"field": f"{where}x.field", "problem": f"{x.field} yatay eksen olamaz"})
    if split is not None:
        kind = kind_of(split, f"{where}split")
        if kind is not None and kind not in CATEGORY_KINDS:
            out.append({"field": f"{where}split", "problem": f"{split} kırılım olamaz"})
        if split == x.field:
            out.append({"field": f"{where}split", "problem": "Kırılım yatay eksenle aynı alan olamaz"})
    if len({s.id for s in series}) != len(series):
        out.append({"field": f"{where}series", "problem": "Seri kimlikleri tekil olmalı"})
    for i, s in enumerate(series):
        if s.fn == "count":
            continue
        kind = kind_of(s.field, f"{where}series.{i}.field")
        if kind is not None and kind not in NUMERIC_KINDS:
            out.append({"field": f"{where}series.{i}.field", "problem": f"{s.field} sayı alanı değil; yalnız Adet seçilebilir"})
    return out


def _bucket_expr(day: sa.ColumnElement, bucket: str, week_start: int) -> sa.ColumnElement:
    """Dönemin ilk günü. 01.01.1900 Pazartesi'dir: hafta, o günden sayılan gün farkının 7'ye bölümünden bulunur."""
    if bucket == "day":
        return day
    if bucket == "week":
        diff = sa.func.datediff(sa.literal_column("day"), sa.literal_column("'19000101'"), day) - sa.literal_column(str(int(week_start)))
        return sa.cast(sa.func.dateadd(sa.literal_column("day"), -(diff % sa.literal_column("7")), day), sa.Date)
    year = sa.func.year(day)
    if bucket == "month":
        return sa.func.datefromparts(year, sa.func.month(day), 1)
    if bucket == "quarter":
        return sa.func.datefromparts(year, (sa.func.datepart(sa.literal_column("quarter"), day) - 1) * 3 + 1, 1)
    return sa.func.datefromparts(year, 1, 1)


def next_period(start: date, bucket: str) -> date:
    if bucket == "day":
        return start + timedelta(days=1)
    if bucket == "week":
        return start + timedelta(days=7)
    months = {"month": 1, "quarter": 3, "year": 12}[bucket]
    m = start.month - 1 + months
    return date(start.year + m // 12, m % 12 + 1, 1)


def query(b: Builder, req: ChartRequest, week_start: int) -> sa.Select:
    found = problems(b, req.x, req.split, req.series)
    if found:
        raise ListQueryError(found)
    where = b.where(req.filters)
    t = b.table
    xcol = t.c[req.x.field]
    xexpr = _bucket_expr(b._local_day(xcol), req.x.bucket, week_start) if req.x.bucket else b.group_expr(xcol)
    cols = [xexpr.label("x")]
    if req.split:
        cols.append(b.group_expr(t.c[req.split]).label("p"))
    with_unit = bool(b.defn.unit_field) and any(unit_relevant(b, s) for s in req.series)
    if with_unit:
        cols.append(t.c[b.defn.unit_field].label("u"))
    fields = list(dict.fromkeys(s.field for s in req.series if s.fn != "count"))
    cols += [t.c[f].label(f"c{i}") for i, f in enumerate(fields)]
    inner = sa.select(*cols).where(b.base_clause(), *where).subquery()
    keys = [inner.c.x] + ([inner.c.p] if req.split else []) + ([inner.c.u] if with_unit else [])
    measures = [sa.func.count().label("n")]
    for i, _ in enumerate(fields):
        c = inner.c[f"c{i}"]
        measures += [sa.func.sum(c).label(f"s{i}"), sa.func.count(c).label(f"d{i}"), sa.func.min(c).label(f"lo{i}"), sa.func.max(c).label(f"hi{i}")]
    return sa.select(*keys, *measures).group_by(*keys).with_statement_hint(PARALLEL_HINT, "mssql")


def unit_relevant(b: Builder, s: ChartSeriesSpec) -> bool:
    """Birim karışıklığı bu seriyi geçersiz kılar mı (K-88, K-90): birimden ondalıklı alan; adet hariç."""
    return s.fn != "count" and s.field in b.defn.unit_decimals


class _Cell:
    """Birleştirilebilir ölçüler: satır sayısı, pay, payda, en küçük, en büyük."""
    __slots__ = ("n", "s", "d", "lo", "hi")

    def __init__(self):
        self.n, self.s, self.d, self.lo, self.hi = 0, 0.0, 0, None, None

    def add(self, n, s, d, lo, hi):
        self.n += n
        if d:
            self.s += float(s)
            self.d += d
            self.lo = float(lo) if self.lo is None else min(self.lo, float(lo))
            self.hi = float(hi) if self.hi is None else max(self.hi, float(hi))

    def value(self, fn: str):
        if fn == "count":
            return self.n
        if fn == "sum":
            return self.s
        if not self.d:
            return None
        return {"avg": self.s / self.d, "min": self.lo, "max": self.hi}[fn]


def _as_date(v) -> date:
    return v.date() if isinstance(v, datetime) else v


def assemble(b: Builder, req: ChartRequest, leaves: list[dict], week_start_name: str) -> dict:
    """Yaprak ölçülerinden cevap: eksen değerleri, kırılım değerleri, seri matrisleri."""
    fields = list(dict.fromkeys(s.field for s in req.series if s.fn != "count"))
    index = {f: i for i, f in enumerate(fields)}
    is_date = req.x.bucket is not None
    xkind = column_type(b.table.c[req.x.field])

    def measures(leaf: dict, s: ChartSeriesSpec):
        if s.fn == "count":
            return leaf["n"], 0, 0, None, None
        i = index[s.field]
        return leaf["n"], leaf[f"s{i}"] or 0, leaf[f"d{i}"], leaf[f"lo{i}"], leaf[f"hi{i}"]

    # birim karışıklığı (seri düzeyinde): katkı veren satırlarda birden çok birim
    mixed = []
    for s in req.series:
        units = {leaf.get("u") for leaf in leaves if unit_relevant(b, s) and leaf[f"d{index[s.field]}"]} if unit_relevant(b, s) else set()
        mixed.append(len(units) > 1)
    rank = next((s for s, m in zip(req.series, mixed) if not m), ChartSeriesSpec(id="_n", fn="count"))  # büyüklük sırası: ilk çizilen seri

    def ranked(key_of) -> list:
        """Anahtarlar büyüklük sırasıyla (azalan); eşitlikte ada göre."""
        totals: dict = {}
        for leaf in leaves:
            totals.setdefault(key_of(leaf), _Cell()).add(*measures(leaf, rank))
        def order(k):
            v = totals[k].value(rank.fn)
            return (-(v if v is not None else float("-inf")), k is None, tr_key("" if k is None else k))
        return sorted(totals, key=order)

    # yatay eksen
    x_other = False
    if is_date:
        days = sorted({_as_date(leaf["x"]) for leaf in leaves if leaf["x"] is not None})
        xs: list = []
        if days:
            d = days[0]
            while d <= days[-1]:
                xs.append(d)
                if len(xs) > MAX_PERIODS:
                    raise TooManyPeriods()
                d = next_period(d, req.x.bucket)
        if any(leaf["x"] is None for leaf in leaves):
            xs.append(None)  # tarihi boş satırlar: "(Boş)" son sırada
        x_of = lambda leaf: None if leaf["x"] is None else _as_date(leaf["x"])  # noqa: E731
    else:
        keys = ranked(lambda leaf: leaf["x"])
        kept = keys[:req.limit]  # gösterilecek değer sayısı (varsayılan ve üst sınır 30); kalanı "Diğer"
        x_other = len(keys) > req.limit
        if req.order == "name":
            kept = sorted(kept, key=lambda k: (k is None, k if isinstance(k, (int, bool)) and k is not None else tr_key("" if k is None else k)))
        xs = kept + ([OTHER] if x_other else [])
        keep = set(kept)
        x_of = lambda leaf: leaf["x"] if leaf["x"] in keep else OTHER  # noqa: E731

    # kırılım
    split = None
    p_of = lambda leaf: None  # noqa: E731
    ps: list = [None]
    if req.split:
        keys = ranked(lambda leaf: leaf["p"])
        room = min(MAX_SPLIT + 1, max(1, MAX_DRAWN // len(req.series)))
        p_other = len(keys) > room
        kept = keys[:room - 1] if p_other else keys
        ps = kept + ([OTHER] if p_other else [])
        keep_p = set(kept)
        p_of = lambda leaf: leaf["p"] if leaf["p"] in keep_p else OTHER  # noqa: E731
        split = {"field": req.split, "values": [_value(k, column_type(b.table.c[req.split])) for k in ps], "other": p_other}

    xi = {k: i for i, k in enumerate(xs)}
    pi = {k: i for i, k in enumerate(ps)}
    series = []
    for s, is_mixed in zip(req.series, mixed):
        if is_mixed:
            series.append({"id": s.id, "data": None, "mixed_units": True})
            continue
        cells = [[_Cell() for _ in xs] for _ in ps]
        for leaf in leaves:
            cells[pi[p_of(leaf)]][xi[x_of(leaf)]].add(*measures(leaf, s))
        series.append({"id": s.id, "data": [[c.value(s.fn) for c in row] for row in cells], "mixed_units": False})
    return {"x": {"kind": "date" if is_date else "category", "bucket": req.x.bucket, "values": [_value(k, xkind) for k in xs], "other": x_other},
            "split": split, "series": series, "rows": sum(leaf["n"] for leaf in leaves), "week_start": week_start_name}


def _value(key, kind: str) -> dict:
    if key == OTHER and not isinstance(key, bool):
        return {"key": OTHER, "label": None}
    if isinstance(key, bool):
        return {"key": key, "label": "Evet" if key else "Hayır"}
    if isinstance(key, (date, datetime)):
        return {"key": _as_date(key).isoformat(), "label": None}
    return {"key": key, "label": None if key is None else str(key)}
