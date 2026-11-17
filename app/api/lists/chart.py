"""Tablonun grafiği için toplama (K-178, docs/08 "Grafik"): listeyle aynı filtre, veri versiyonu ve satır kapsamı.

Tek sorgu yatay eksen, kırılım ve (gerekirse) birim düzeyinde yaprak ölçüleri verir (satır sayısı, pay, payda, en küçük, en büyük); "en büyük N +
Diğer", boş dönemlerin doldurulması ve birim karışıklığı Python'da bulunur. Ölçüler birleştirilebilir olduğundan "Diğer" kalan satırlardan doğru
hesaplanır (ortalama, en küçük ve en büyük dahil). Saat kırılımı yoktur: tarih-saat alanı API sunucusunun yerel gününe indirgenir (filtredeki gün
sınırıyla aynı).
"""
from datetime import date, datetime, timedelta

import sqlalchemy as sa

from .definition import column_type
from .query import PARALLEL_HINT, Builder, ListQueryError, turkish_upper
from .request import CHART_MAX_DISTINCT, ChartAxis, ChartRequest, ChartScatter, ChartSelection, ChartSeriesSpec, ChartWithin, PointsRequest

MAX_SPLIT = 11        # kırılımda en büyük 11 + "Diğer"
MAX_FACETS = 12       # küçük grafiklerde en büyük 12 + "Diğer" (K-179)
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


def problems(b: Builder, x: ChartAxis, split: str | None, series: list[ChartSeriesSpec], where: str = "", facet: str | None = None) -> list[dict]:
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
    if facet is not None:  # küçük grafiklere böl (K-179)
        kind = kind_of(facet, f"{where}facet")
        if kind is not None and kind not in CATEGORY_KINDS:
            out.append({"field": f"{where}facet", "problem": f"{facet} küçük grafiklere bölemez"})
        if facet in (x.field, split):
            out.append({"field": f"{where}facet", "problem": "Küçük grafik alanı yatay eksenle ya da kırılımla aynı olamaz"})
    if len({s.id for s in series}) != len(series):
        out.append({"field": f"{where}series", "problem": "Seri kimlikleri tekil olmalı"})
    for i, s in enumerate(series):
        if s.fn == "count":
            continue
        kind = kind_of(s.field, f"{where}series.{i}.field")
        if s.fn == "distinct":  # Benzersiz say: listenin bütün alanlarında
            continue
        if kind is not None and kind not in NUMERIC_KINDS:
            out.append({"field": f"{where}series.{i}.field", "problem": f"{s.field} sayı alanı değil; yalnız Say ya da Benzersiz say seçilebilir"})
    if sum(1 for s in series if s.fn == "distinct") > CHART_MAX_DISTINCT:
        out.append({"field": f"{where}series", "problem": f"En çok {CHART_MAX_DISTINCT} Benzersiz say serisi olabilir"})
    return out


NOT_MEASURED = ("count", "distinct")  # yaprak ölçüsü istemeyen hesaplamalar (satır sayısı; ayrı sorguyla sayılan farklı değer)


def x_expr(b: Builder, axis: ChartAxis, week_start: int) -> sa.ColumnElement:
    """Yatay eksenin (ya da inilen dönemin) ifadesi: toplamada, inişte ve grafik seçiminde aynı (K-179)."""
    col = b.table.c[axis.field]
    return _bucket_expr(b._local_day(col), axis.bucket, week_start) if axis.bucket else b.group_expr(col)


def within_clauses(b: Builder, field: str, within: list[ChartWithin], week_start: int) -> list[sa.ColumnElement]:
    """İniş: yalnız verilen dönem(ler)in satırları."""
    return [x_expr(b, ChartAxis(field=field, bucket=w.bucket), week_start).in_(w.keys) for w in within]


def inside(start: date, bucket: str, within: list[ChartWithin]) -> bool:
    """Boşluk doldurmada: dönem, inilen dönemlerin içinde mi (her adımda en az biriyle kesişiyor mu). Bitişik olmayan dönemlerin arası çizilmez."""
    end = next_period(start, bucket)
    return all(any(start < next_period(k, w.bucket) and end > k for k in w.keys) for w in within)


def selection_clause(b: Builder, sel: ChartSelection, week_start: int) -> sa.ColumnElement:
    """Grafik seçiminin koşulu (K-179): öğeler "ya da" ile; kırılımda her öğe dönem ve parça. Toplama sorgusuyla aynı ifadeler, böylece bir çubuğun
    değeri ile bu koşulla dönen satırlar birebir tutar. "Diğer" seçilemez."""
    found = problems(b, sel.x, sel.split, [], "chart_selection.", sel.facet)
    if not sel.items and not sel.within:
        found.append({"field": "chart_selection.items", "problem": "Seçim boş olamaz"})
    if any(w.bucket and column_type(b.table.c[sel.x.field]) not in DATE_KINDS for w in sel.within if sel.x.field in b.columns):
        found.append({"field": "chart_selection.within", "problem": "İniş yalnız tarih ekseninde"})
    if found:
        raise ListQueryError(found)
    xe = x_expr(b, sel.x, week_start)
    pe = b.group_expr(b.table.c[sel.split]) if sel.split else None
    fe = b.group_expr(b.table.c[sel.facet]) if sel.facet else None

    def match(expr, key, as_date: bool, where: str):
        if key == OTHER and not isinstance(key, bool):
            found.append({"field": where, "problem": "Diğer seçilemez"})
            return sa.false()
        if key is None:
            return expr.is_(None)
        if as_date:
            try:
                return expr == date.fromisoformat(str(key)[:10])
            except ValueError:
                found.append({"field": where, "problem": f"Geçersiz dönem: {key}"})
                return sa.false()
        return expr == key

    items = []
    for i, item in enumerate(sel.items):
        parts = [match(xe, item.x, sel.x.bucket is not None, f"chart_selection.items.{i}.x")]
        if pe is not None:
            parts.append(match(pe, item.p, False, f"chart_selection.items.{i}.p"))
        if fe is not None:
            parts.append(match(fe, item.f, False, f"chart_selection.items.{i}.f"))
        items.append(sa.and_(*parts))
    if found:
        raise ListQueryError(found)
    return sa.and_(*within_clauses(b, sel.x.field, sel.within, week_start), *([sa.or_(*items)] if items else []))


def distinct_query(b: Builder, req: ChartRequest, s: ChartSeriesSpec, week_start: int) -> sa.Select:
    """Benzersiz say (K-179): (yatay eksen, kırılım, değer) üçlüleri, tekil. Sayım Python'da, gösterilen değere ya da "Diğer"e eşlenerek yapılır:
    böylece "Diğer" kalan satırlardaki farklı değer sayısıdır. Metinde Türkçe ve büyük/küçük harf duyarsız; boş değer sayılmaz."""
    t = b.table
    col = t.c[s.field]
    value = turkish_upper(col) if column_type(col) == "text" else col
    cols = ([x_expr(b, req.x, week_start).label("x")] + ([b.group_expr(t.c[req.split]).label("p")] if req.split else [])
            + ([b.group_expr(t.c[req.facet]).label("f")] if req.facet else []) + [value.label("v")])
    where = [*b.where(req.filters), *within_clauses(b, req.x.field, req.within, week_start), sa.not_(b.is_empty(col))]
    return sa.select(*cols).where(b.base_clause(), *where).distinct()


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
    found = problems(b, req.x, req.split, req.series, facet=req.facet)
    if found:
        raise ListQueryError(found)
    where = [*b.where(req.filters), *within_clauses(b, req.x.field, req.within, week_start)]
    t = b.table
    cols = [x_expr(b, req.x, week_start).label("x")]
    if req.split:
        cols.append(b.group_expr(t.c[req.split]).label("p"))
    if req.facet:
        cols.append(b.group_expr(t.c[req.facet]).label("f"))
    with_unit = bool(b.defn.unit_field) and any(unit_relevant(b, s) for s in req.series)
    if with_unit:
        cols.append(t.c[b.defn.unit_field].label("u"))
    fields = list(dict.fromkeys(s.field for s in req.series if s.fn not in NOT_MEASURED))
    cols += [t.c[f].label(f"c{i}") for i, f in enumerate(fields)]
    inner = sa.select(*cols).where(b.base_clause(), *where).subquery()
    keys = [inner.c.x] + ([inner.c.p] if req.split else []) + ([inner.c.f] if req.facet else []) + ([inner.c.u] if with_unit else [])
    measures = [sa.func.count().label("n")]
    for i, _ in enumerate(fields):
        c = inner.c[f"c{i}"]
        measures += [sa.func.sum(c).label(f"s{i}"), sa.func.count(c).label(f"d{i}"), sa.func.min(c).label(f"lo{i}"), sa.func.max(c).label(f"hi{i}")]
    return sa.select(*keys, *measures).group_by(*keys).with_statement_hint(PARALLEL_HINT, "mssql")


def unit_relevant(b: Builder, s: ChartSeriesSpec) -> bool:
    """Birim karışıklığı bu seriyi geçersiz kılar mı (K-88, K-90): birimden ondalıklı alan; Say ve Benzersiz say hariç."""
    return s.fn not in NOT_MEASURED and s.field in b.defn.unit_decimals


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


def assemble(b: Builder, req: ChartRequest, leaves: list[dict], week_start_name: str, distinct: dict[str, list[dict]] | None = None) -> dict:
    """Yaprak ölçülerinden cevap: eksen değerleri, kırılım değerleri, seri matrisleri. distinct: Benzersiz say serilerinin (x, p, v) üçlüleri."""
    distinct = distinct or {}
    fields = list(dict.fromkeys(s.field for s in req.series if s.fn not in NOT_MEASURED))
    index = {f: i for i, f in enumerate(fields)}
    is_date = req.x.bucket is not None
    xkind = column_type(b.table.c[req.x.field])

    def measures(leaf: dict, s: ChartSeriesSpec):
        if s.fn in NOT_MEASURED:
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
        if rank.fn == "distinct":  # farklı değer sayısı birleştirilemez: anahtar başına değer kümesi
            seen: dict = {key_of(leaf): set() for leaf in leaves}
            for r in distinct.get(rank.id, []):
                seen.setdefault(key_of(r), set()).add(r["v"])
            return sorted(seen, key=lambda k: (-len(seen[k]), k is None, tr_key("" if k is None else k)))
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
            have = set(days)
            while d <= days[-1]:
                if d in have or inside(d, req.x.bucket, req.within):
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
        keys = ranked(lambda leaf: leaf.get("p"))
        room = min(MAX_SPLIT + 1, max(1, MAX_DRAWN // len(req.series)))
        p_other = len(keys) > room
        kept = keys[:room - 1] if p_other else keys
        ps = kept + ([OTHER] if p_other else [])
        keep_p = set(kept)
        p_of = lambda leaf: leaf.get("p") if leaf.get("p") in keep_p else OTHER  # noqa: E731
        split = {"field": req.split, "values": [_value(k, column_type(b.table.c[req.split])) for k in ps], "other": p_other}

    # küçük grafikler (K-179): en büyük 12 değer + "Diğer"; yatay eksen ve kırılım ortak
    facets = None
    f_of = lambda leaf: None  # noqa: E731
    fs: list = [None]
    if req.facet:
        keys = ranked(lambda leaf: leaf.get("f"))
        f_other = len(keys) > MAX_FACETS
        kept = keys[:MAX_FACETS]
        fs = kept + ([OTHER] if f_other else [])
        keep_f = set(kept)
        f_of = lambda leaf: leaf.get("f") if leaf.get("f") in keep_f else OTHER  # noqa: E731
        facets = {"field": req.facet, "values": [_value(k, column_type(b.table.c[req.facet])) for k in fs], "other": f_other}

    xi = {k: i for i, k in enumerate(xs)}
    pi = {k: i for i, k in enumerate(ps)}
    fi = {k: i for i, k in enumerate(fs)}
    shape = (lambda grid: grid) if req.facet else (lambda grid: grid[0])  # küçük grafik varsa veri: küçük grafik × kırılım × yatay eksen
    series = []
    for s, is_mixed in zip(req.series, mixed):
        if is_mixed:
            series.append({"id": s.id, "data": None, "mixed_units": True})
            continue
        if s.fn == "distinct":  # gösterilen değere ya da "Diğer"e eşlenmiş kümeler: "Diğer" kalan satırlardaki farklı değer sayısı
            sets = [[[set() for _ in xs] for _ in ps] for _ in fs]
            for r in distinct.get(s.id, []):
                sets[fi[f_of(r)]][pi[p_of(r)]][xi[x_of(r)]].add(r["v"])
            series.append({"id": s.id, "data": shape([[[len(c) for c in row] for row in grid] for grid in sets]), "mixed_units": False})
            continue
        cells = [[[_Cell() for _ in xs] for _ in ps] for _ in fs]
        for leaf in leaves:
            cells[fi[f_of(leaf)]][pi[p_of(leaf)]][xi[x_of(leaf)]].add(*measures(leaf, s))
        series.append({"id": s.id, "data": shape([[[c.value(s.fn) for c in row] for row in grid] for grid in cells]), "mixed_units": False})
    return {"x": {"kind": "date" if is_date else "category", "bucket": req.x.bucket, "values": [_value(k, xkind) for k in xs], "other": x_other},
            "split": split, "facets": facets, "series": series, "rows": sum(leaf["n"] for leaf in leaves), "week_start": week_start_name}


def _value(key, kind: str) -> dict:
    if key == OTHER and not isinstance(key, bool):
        return {"key": OTHER, "label": None}
    if isinstance(key, bool):
        return {"key": key, "label": "Evet" if key else "Hayır"}
    if isinstance(key, (date, datetime)):
        return {"key": _as_date(key).isoformat(), "label": None}
    return {"key": key, "label": None if key is None else str(key)}


# --- Dağılım (K-179): satır başına nokta ---------------------------------------------------------------------------

def scatter_problems(b: Builder, sc: ChartScatter | PointsRequest, where: str = "") -> list[dict]:
    out: list[dict] = []
    for name, at in ((sc.x, "x"), (sc.y, "y")):
        if name not in b.columns:
            out.append({"field": f"{where}{at}", "problem": f"Bilinmeyen alan: {name}"})
        elif column_type(b.table.c[name]) not in NUMERIC_KINDS:
            out.append({"field": f"{where}{at}", "problem": f"{name} sayı alanı değil"})
    if sc.color is not None:
        if sc.color not in b.columns:
            out.append({"field": f"{where}color", "problem": f"Bilinmeyen alan: {sc.color}"})
        elif column_type(b.table.c[sc.color]) not in CATEGORY_KINDS:
            out.append({"field": f"{where}color", "problem": f"{sc.color} renk kırılımı olamaz"})
    return out


def _points_where(b: Builder, req: PointsRequest) -> list[sa.ColumnElement]:
    t = b.table
    return [*b.where(req.filters), t.c[req.x].is_not(None), t.c[req.y].is_not(None)]


def points_summary_query(b: Builder, req: PointsRequest) -> sa.Select:
    """Renk değeri (ve birim) başına satır sayısı: toplam nokta, renk sırası ve birim karışıklığı buradan."""
    found = scatter_problems(b, req)
    if found:
        raise ListQueryError(found)
    t = b.table
    cols = []
    if req.color:
        cols.append(b.group_expr(t.c[req.color]).label("c"))
    if b.defn.unit_field and (req.x in b.defn.unit_decimals or req.y in b.defn.unit_decimals):
        cols.append(t.c[b.defn.unit_field].label("u"))
    inner = sa.select(*cols, sa.literal(1).label("one")).where(b.base_clause(), *_points_where(b, req)).subquery()
    keys = [inner.c[c.name] for c in cols]
    return sa.select(*keys, sa.func.count().label("n")).group_by(*keys)


def label_field(b: Builder) -> str | None:
    """Noktanın ipucundaki kayıt adı: listenin varsayılan sırasındaki ilk metin alanı (ör. sipariş no, malzeme kodu); yoksa görünür ilk metin alanı."""
    is_text = lambda f: f in b.columns and column_type(b.table.c[f]) == "text"  # noqa: E731
    ordered = next((f for f, _ in b.defn.default_sort if is_text(f)), None)
    return ordered or next((f for f, c in b.columns.items() if c["default_visible"] and is_text(f)), None)


def points_query(b: Builder, req: PointsRequest, rows: int) -> sa.Select:
    """Noktalar, listenin varsayılan sırasıyla. Satır sayısı sınırı aşıyorsa eşit aralıkla örneklenir (ilk N değil): tam `limit` nokta."""
    t = b.table
    name = label_field(b)
    rn = sa.func.row_number().over(order_by=b.order_by([]))
    cols = [t.c[req.x].label("x"), t.c[req.y].label("y"), rn.label("rn")]
    if req.color:
        cols.append(b.group_expr(t.c[req.color]).label("c"))
    if name:
        cols.append(t.c[name].label("name"))
    inner = sa.select(*cols).where(b.base_clause(), *_points_where(b, req)).subquery()
    q = sa.select(*[c for c in inner.c if c.name != "rn"]).order_by(inner.c.rn)
    if rows > req.limit:
        q = q.where((sa.cast(inner.c.rn, sa.BigInteger) * req.limit) % rows < req.limit)
    return q


def points_summary(b: Builder, req: PointsRequest, summary: list[dict]) -> dict:
    """Özetten: satır sayısı, renk değerleri (en büyük 11 + "Diğer", satır sayısına göre) ve birimi karışık eksenler."""
    rows = sum(r["n"] for r in summary)
    units = {r.get("u") for r in summary} if summary and "u" in summary[0] else set()
    mixed = {axis: len(units) > 1 and getattr(req, axis) in b.defn.unit_decimals for axis in ("x", "y")}
    colors = None
    kept: list = []
    if req.color:
        counts: dict = {}
        for r in summary:
            counts[r["c"]] = counts.get(r["c"], 0) + r["n"]
        keys = sorted(counts, key=lambda k: (-counts[k], k is None, tr_key("" if k is None else k)))
        other = len(keys) > MAX_SPLIT + 1
        kept = keys[:MAX_SPLIT] if other else keys
        colors = {"field": req.color, "values": [_value(k, column_type(b.table.c[req.color])) for k in kept + ([OTHER] if other else [])], "other": other}
    return {"rows": rows, "mixed_units": mixed, "colors": colors, "kept": kept}


def assemble_points(req: PointsRequest, info: dict, found: list[dict]) -> dict:
    index = {k: i for i, k in enumerate(info["kept"])}
    other = len(info["kept"])
    points = [[float(r["x"]), float(r["y"]), index.get(r.get("c"), other) if req.color else 0, r.get("name")] for r in found]
    return {"points": points, "colors": info["colors"], "rows": info["rows"], "shown": len(points), "mixed_units": info["mixed_units"]}
