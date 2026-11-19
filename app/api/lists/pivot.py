"""Pivot (K-183, docs/08): tablonun satırlarından çapraz özet; satır alanları × sütun alanları × değerler.

Toplama veritabanında yapılır, ekrana yalnız istenen satır parçası gelir (satır sınırı yok):
- Görüntü satırları satır alanlarının `ROLLUP`'ıdır: her yaprak satır, her ara toplam ve genel toplam bir satırdır. Kapalı toplam düzeyleri
  çıkarılır, kalanlar hiyerarşik sıralanır (ada ya da bir değerin satır toplamına göre; her düzey kendi içinde) ve numaralanır; parça bu
  numaralar üzerindendir. Sıralama parçadan önce bütün veride yapıldığı için parça sınırları sırayı bozmaz.
- Hücreler, parçadaki her görüntü satırı için o satırın **bütün kayıtlarından** sütun alanlarının `GROUPING SETS`'iyle hesaplanır: ara toplam
  ve genel toplam yüklenen parçadan bağımsızdır; ortalama pay ve paydadan, benzersiz say kayıtlardan gelir (ortalamaların ortalaması yok).
- Sütun ekseni parçalanmaz; sınır yalnız oradadır (yaprak sütun, çizilen değer sütunu, dönem).

Filtre, satır kapsamı, veri versiyonu ve ilişkili alan birleştirmeleri liste sorgusunun kurucusundan (`Builder`) gelir.
"""
from datetime import date, timedelta

import sqlalchemy as sa

from app.periods import periods as period_list

from .chart import DATE_KINDS, MAX_PERIODS, TooManyPeriods, _bucket_expr, next_period, tr_key
from .query import PARALLEL_HINT, Builder, turkish
from .request import PERIOD_FNS, PIVOT_RULE_OPS, PivotAxis, PivotRequest, PivotValueSpec

MAX_LEAF_COLUMNS = 200      # yaprak sütun (sütun alanlarının değer birleşimi)
MAX_VALUE_COLUMNS = 400     # çizilen değer sütunu: sütun (toplamlar dahil) × değer
MAX_DISTINCT = 3
AXIS_KINDS = ("text", "bool", "integer", *DATE_KINDS)   # satır ve sütun alanı: kategori ya da tarih (ondalıklı sayı olamaz)
NUMERIC_KINDS = ("number", "integer")
RATIO = ("avg", "wavg")     # bir ondalık fazla gösterilir
NOT_MEASURED = ("count", "distinct")
DEFAULT_DECIMALS = 2


class PivotTooLarge(ValueError):
    """Sütun ekseni sınırı aşıldı: pivot çizilmez, neden kullanıcıya söylenir (422 pivot_too_large)."""


def problems(b: Builder, rows: list[PivotAxis], columns: list[PivotAxis], values: list[PivotValueSpec], sort_by: str,
             where: str = "") -> list[dict]:
    """Alan ve hesaplama doğrulaması; görünüm kaydı da aynı denetimi kullanır (`where`: alan yolunun öneki)."""
    out: list[dict] = []

    def bad(at: str, text: str) -> None:
        out.append({"field": f"{where}{at}", "problem": text})

    seen: set[str] = set()
    for name, axes in (("rows", rows), ("columns", columns)):
        for i, a in enumerate(axes):
            col = b.columns.get(a.field)
            if col is None:
                bad(f"{name}.{i}.field", f"Bilinmeyen alan: {a.field}")
                continue
            if a.field in seen:
                bad(f"{name}.{i}.field", f"Alan iki kez kullanılamaz: {col['label']}")
            seen.add(a.field)
            if col["type"] not in AXIS_KINDS:
                bad(f"{name}.{i}.field", f"{col['label']} satır ya da sütun olamaz (ondalıklı sayı)")
            elif col["type"] in DATE_KINDS and not a.bucket:
                bad(f"{name}.{i}.bucket", f"{col['label']} için dönem tipi seçilmeli")
            elif col["type"] not in DATE_KINDS and a.bucket:
                bad(f"{name}.{i}.bucket", f"Dönem tipi yalnız tarih alanında: {col['label']}")
    ids = [v.id for v in values]
    if len(set(ids)) != len(ids):
        bad("values", "Değer kimlikleri tekil olmalı")
    if sum(1 for v in values if v.fn == "distinct") > MAX_DISTINCT:
        bad("values", f"En çok {MAX_DISTINCT} \"Benzersiz say\" değeri eklenebilir")
    fields = {v.id: v for v in values if v.kind == "field"}
    for i, v in enumerate(values):
        for j, rule in enumerate(v.rules):
            if rule.condition.op not in PIVOT_RULE_OPS or rule.condition.field_ref:
                bad(f"values.{i}.rules.{j}.condition.op", "Pivot kuralında yalnız sayı koşulları kullanılır")
        if v.kind == "calc":
            # hesaplanan değer (toplamlardan): iki alan değerinin sonucu; tarih sonuçlu değer hesaba girmez
            for side in ("a", "b"):
                other = fields.get(getattr(v, side) or "")
                if other is None:
                    bad(f"values.{i}.{side}", "Hesaplanan değer için pivottaki bir değer seçilmeli")
                elif other.fn in ("min", "max") and b.columns.get(other.field or "", {}).get("type") in DATE_KINDS:
                    bad(f"values.{i}.{side}", "Tarih sonuçlu değer hesaplamada kullanılamaz")
            if v.op is None:
                bad(f"values.{i}.op", "İşlem seçilmeli")
            continue
        if v.fn == "count":
            continue
        col = b.columns.get(v.field or "")
        if col is None:
            bad(f"values.{i}.field", f"Bilinmeyen alan: {v.field}" if v.field else "Alan seçilmeli")
            continue
        if v.fn in PERIOD_FNS and not b.defn.period:
            bad(f"values.{i}.fn", "İlk dönem değeri ve Son dönem değeri yalnız dönem tablolarında kullanılır")
            continue
        if v.fn in ("min", "max") and col["type"] in DATE_KINDS:
            continue  # tarih alanında en erken ve en geç (K-183 demo kararı); toplam ve ortalama yok
        if v.fn != "distinct" and col["type"] not in NUMERIC_KINDS:
            bad(f"values.{i}.fn", f"Tarih alanında yalnız En erken, En geç, Say ve Benzersiz say: {col['label']}" if col["type"] in DATE_KINDS
                else f"Bu hesaplama yalnız sayı alanında: {col['label']}")
        if v.fn == "wavg":
            weight = b.columns.get(v.weight or "")
            if weight is None or weight["type"] not in NUMERIC_KINDS or v.weight == v.field:
                bad(f"values.{i}.weight", "Ağırlıklı ortalama için başka bir sayı alanı seçilmeli")
    if sort_by != "name" and sort_by not in ids:
        bad("sort.by", f"Bilinmeyen değer: {sort_by}")
    return out


class Pivot:
    """Bir pivot isteğinin sorguları ve cevabın kurulması."""

    def __init__(self, b: Builder, req: PivotRequest, week_start: int):
        self.b, self.req = b, req
        t = b.table
        self.R, self.C = len(req.rows), len(req.columns)
        self.index = {v.id: k for k, v in enumerate(req.values)}
        rx = [self._axis(a, week_start) for a in req.rows]
        cx = [self._axis(a, week_start) for a in req.columns]
        cols = [x.label(f"r{i}") for i, x in enumerate(rx)] + [x.label(f"c{i}") for i, x in enumerate(cx)]
        # Sıra alanı (K-184): başlıklar o alanın gruptaki en küçüğüne göre sıralanır (Dönem, Dönem başı'na göre)
        self.row_ordered = [not a.bucket and b.ordered(a.field) for a in req.rows]
        self.col_ordered = [not a.bucket and b.ordered(a.field) for a in req.columns]
        cols += [b.order_col(t.c[a.field]).label(f"or{i}") for i, a in enumerate(req.rows) if self.row_ordered[i]]
        cols += [b.order_col(t.c[a.field]).label(f"oc{i}") for i, a in enumerate(req.columns) if self.col_ordered[i]]
        self.col_order: dict[tuple[int, tuple], object] = {}
        self.unit_of: dict[int, str] = {}   # değer sırası → taban sorgudaki birim kolonu
        self.checked: set[int] = set()      # birim karışıklığı denetlenen değerler (listenin kendi miktar alanları)
        units: dict[str, str] = {}          # kaynak birim kolonu → taban sorgudaki ad
        for k, v in enumerate(req.values):
            if v.kind == "calc" or v.fn == "count":
                continue
            src = t.c[v.field]
            cols.append((sa.func.nullif(src, sa.literal_column("N''")) if b.columns[v.field]["type"] == "text" else src).label(f"a{k}"))
            if v.fn in PERIOD_FNS:
                # İlk · Son dönem değeri (K-184): her toplama düzeyi (satır öneki i × sütun öneki j) için, o düzeyin hücresinde ana kaydın
                # ilk (son) dönemindeki değer işaretlenir; hücrenin sonucu işaretli değerlerin toplamıdır (ana kayıtlar arasında toplanır).
                master, start = t.c[b.defn.period[0]], t.c[b.defn.period[1]]
                by = start.asc() if v.fn == "first" else start.desc()
                for i in range(self.R + 1):
                    for j in range(self.C + 1):
                        first = sa.func.row_number().over(partition_by=[*rx[:i], *cx[:j], master], order_by=by) == 1
                        cols.append(sa.case((first, src)).label(f"f{k}_{i}_{j}"))
            if v.fn == "wavg":
                cols.append(t.c[v.weight].label(f"w{k}"))
            if v.fn in NOT_MEASURED or not b.columns[v.field]["decimals_from_unit"]:
                continue
            own = v.field in b.defn.unit_decimals and b.defn.unit_field
            source = b.defn.unit_field if own else b.related_units.get(v.field)
            if source:
                self.unit_of[k] = units.setdefault(source, f"u{len(units)}")
                if own:
                    self.checked.add(k)
        cols += [t.c[source].label(name) for source, name in units.items()]
        where = [b.base_clause(), *b.where(req.filters)]
        self.base = sa.select(*cols).where(*where).cte("pv")
        self.r = [self.base.c[f"r{i}"] for i in range(self.R)]
        self.c = [self.base.c[f"c{i}"] for i in range(self.C)]

    def _axis(self, a: PivotAxis, week_start: int) -> sa.ColumnElement:
        col = self.b.table.c[a.field]
        return _bucket_expr(self.b._local_day(col), a.bucket, week_start) if a.bucket else self.b.group_expr(col)

    def _kind(self, a: PivotAxis) -> str:
        return self.b.columns[a.field]["type"]

    # --- hesaplama --------------------------------------------------------------------------------------------
    def measure(self, k: int, src: sa.FromClause, level=None) -> sa.ColumnElement:
        """Değerin grubun kayıtlarından hesabı (her düzeyde aynı ifade: ara toplam ve genel toplam da kayıtlardan). level(i, j): sorgunun o
        satırı (satır öneki i, sütun öneki j) düzeyinde mi (koşul; o düzey sorguda yoksa None); İlk · Son dönem değeri düzeye göre seçilir."""
        v = self.req.values[k]
        if v.kind == "calc":  # toplamlardan: o grubun a ve b sonuçlarından (kayıtların oranlarından değil); bölen 0 ya da biri boşsa boş
            a, b = (sa.cast(self.measure(self.index[x], src, level), sa.Float) for x in (v.a, v.b))
            return {"div": lambda: a / sa.func.nullif(b, 0), "mul": lambda: a * b, "add": lambda: a + b, "sub": lambda: a - b}[v.op]()
        if v.fn == "count":
            return sa.func.count()
        a = src.c[f"a{k}"]
        if v.fn == "distinct":
            return sa.func.count(sa.distinct(turkish(a) if self.b.columns[v.field]["type"] == "text" else a))
        if v.fn == "sum":
            return sa.func.sum(a)
        if v.fn in PERIOD_FNS:
            whens = [(cond, sa.func.sum(src.c[f"f{k}_{i}_{j}"])) for i in range(self.R + 1) for j in range(self.C + 1)
                     if (cond := level(i, j)) is not None]
            return sa.case(*whens)
        if v.fn in ("min", "max"):
            return getattr(sa.func, v.fn)(a)
        if v.fn == "avg":
            return sa.cast(sa.func.sum(a), sa.Float) / sa.func.nullif(sa.func.count(a), 0)
        w = src.c[f"w{k}"]
        both = sa.and_(a.is_not(None), w.is_not(None))
        return (sa.cast(sa.func.sum(sa.case((both, a * w))), sa.Float)
                / sa.func.nullif(sa.cast(sa.func.sum(sa.case((both, w))), sa.Float), 0))

    # --- görüntü satırları ------------------------------------------------------------------------------------
    def _page(self) -> sa.CTE:
        """Sıralı ve numaralı görüntü satırları (rn): yapraklar, açık ara toplamlar ve açık genel toplam."""
        req, base, r = self.req, self.base, self.r
        by_value = req.sort.by != "name"
        k = next((i for i, v in enumerate(req.values) if v.id == req.sort.by), 0)
        g = [sa.func.grouping(x).label(f"g{i}") for i, x in enumerate(r)]
        grouped = sum((sa.func.grouping(x) for x in r[1:]), sa.func.grouping(r[0]))  # toplanmış satır alanı sayısı

        def level(i: int, j: int):  # satır toplamı sütunların tamamındadır (sütun öneki 0)
            return (grouped == self.R - i) if j == 0 else None
        idx_cols = [*r, *g] + ([self.measure(k, base, level).label("sv")] if by_value else [])
        idx_cols += [sa.func.min(base.c[f"or{i}"]).label(f"on{i}") for i in range(self.R) if self.row_ordered[i]]
        idx = sa.select(*idx_cols).select_from(base).group_by(sa.func.rollup(*r)).cte("idx")
        ir = [idx.c[f"r{i}"] for i in range(self.R)]
        ig = [idx.c[f"g{i}"] for i in range(self.R)]
        desc = req.sort.dir == "desc"

        order: list[tuple[sa.ColumnElement, bool]] = []  # (sıra ifadesi, azalan mı)
        for i in range(self.R):
            order.append((ig[i], False))  # o düzeyin toplam satırı grubunun sonunda
            if by_value:
                # grubun sıra değeri: o düzeyin toplam satırındaki (yaprakta satırın kendi) sonucu; boş sonda
                is_level = sa.and_(*[ig[j] == (0 if j <= i else 1) for j in range(self.R)])
                value = sa.func.max(sa.case((is_level, idx.c.sv))).over(partition_by=[*ig[: i + 1], *ir[: i + 1]])
                order += [(sa.case((value.is_(None), 1), else_=0), False), (value, desc)]
            if self.row_ordered[i]:  # sıra alanı: düzeyin anahtarlarında ortak değer (alt satırların hepsi aynı sırada dursun)
                name = sa.func.min(idx.c[f"on{i}"]).over(partition_by=[*ir[: i + 1], *ig[: i + 1]])
            else:
                name = turkish(ir[i]) if self._kind(req.rows[i]) == "text" else ir[i]
            order += [(sa.case((ir[i].is_(None), 1), else_=0), False), (name, desc and not by_value)]
        # pencere değerleri süzmeden önce hesaplanır: sıra ifadeleri iç sorguda, süzme ve numaralama dışarıda
        keyed = sa.select(*ir, *ig, *[o.label(f"o{n}") for n, (o, _) in enumerate(order)]).cte("keyed")
        ordering = [keyed.c[f"o{n}"].desc() if d else keyed.c[f"o{n}"].asc() for n, (_, d) in enumerate(order)]
        kr = [keyed.c[f"r{i}"] for i in range(self.R)]
        kg = [keyed.c[f"g{i}"] for i in range(self.R)]
        visible = [x for x in (
            None if req.totals.rows else kg[0] == 0,
            None if req.totals.subtotals or self.R == 1 else sa.or_(kg[-1] == 0, kg[0] == 1),
        ) if x is not None]
        return (sa.select(*kr, *kg, sa.func.row_number().over(order_by=ordering).label("rn"), sa.func.count().over().label("cnt"))
                .where(*visible).cte("page"))

    def rows_query(self) -> sa.Select:
        page, req = self._page(), self.req
        return (sa.select(page).where(page.c.rn > req.offset, page.c.rn <= req.offset + req.limit).order_by(page.c.rn)
                .with_statement_hint(PARALLEL_HINT, "mssql"))

    def count_query(self) -> sa.Select:
        page = self._page()
        return sa.select(sa.func.count()).select_from(page)

    def cells_query(self) -> sa.Select:
        """Parçadaki her görüntü satırı × her sütun düzeyi için değerler: satırın bütün kayıtlarından."""
        page, base, req = self._page(), self.base, self.req
        match = [sa.or_(page.c[f"g{i}"] == 1, base.c[f"r{i}"] == page.c[f"r{i}"], sa.and_(base.c[f"r{i}"].is_(None), page.c[f"r{i}"].is_(None)))
                 for i in range(self.R)]
        cols: list[sa.ColumnElement] = [page.c.rn, *self.c, *[sa.func.grouping(x).label(f"gc{j}") for j, x in enumerate(self.c)]]
        row_level = self.R - sum((sa.func.max(page.c[f"g{i}"]) for i in range(1, self.R)), sa.func.max(page.c.g0))
        col_level = self.C - sum((sa.func.grouping(x) for x in self.c[1:]), sa.func.grouping(self.c[0])) if self.C else None

        def level(i: int, j: int):
            if col_level is None:
                return (row_level == i) if j == 0 else None
            return sa.and_(row_level == i, col_level == j)
        for k, v in enumerate(req.values):
            cols.append(self.measure(k, base, level).label(f"v{k}"))
            if k in self.unit_of:
                unit = sa.case((base.c[f"a{k}"].is_not(None), base.c[self.unit_of[k]]))
                cols += [sa.func.min(unit).label(f"ua{k}"), sa.func.max(unit).label(f"ub{k}")]
        levels = [self.C] + (list(range(self.C - 1, 0, -1)) if req.totals.subtotals else []) + ([0] if req.totals.columns and self.C else [])
        sets = [sa.tuple_(page.c.rn, *self.c[:n]) for n in levels]
        group = [sa.func.grouping_sets(*sets)] if self.C else [page.c.rn]
        return (sa.select(*cols).select_from(page.join(base, sa.and_(*match)))
                .where(page.c.rn > req.offset, page.c.rn <= req.offset + req.limit).group_by(*group)
                .with_statement_hint(PARALLEL_HINT, "mssql"))

    def columns_query(self) -> sa.Select | None:
        """Yaprak sütun anahtarları (sınırdan bir fazla: aşım anlaşılır)."""
        if not self.C:
            return None
        order = [sa.func.min(self.base.c[f"oc{j}"]).label(f"ocm{j}") for j in range(self.C) if self.col_ordered[j]]
        return sa.select(*self.c, *order).select_from(self.base).group_by(*self.c).limit(MAX_LEAF_COLUMNS + 1)

    def leaf_columns(self, rows: list[dict]) -> list[tuple]:
        """Sorgu satırlarından yaprak anahtarları; sıra alanlı sütunlarda her önekin sıra değeri (o önekin yapraklarındaki en küçük)."""
        for r in rows:
            key = tuple(r[f"c{j}"] for j in range(self.C))
            for j in range(self.C):
                if self.col_ordered[j] and r[f"ocm{j}"] is not None:
                    at = (j, key[: j + 1])
                    self.col_order[at] = min(self.col_order.get(at, r[f"ocm{j}"]), r[f"ocm{j}"])
        return [tuple(r[f"c{j}"] for j in range(self.C)) for r in rows]

    # --- cevap ------------------------------------------------------------------------------------------------
    def _sorted(self, keys: list[tuple]) -> list[tuple]:
        def part(key, i, kind):
            v = key[i]
            if v is None:
                return (1, "")
            if self.col_ordered[i] and (i, key[: i + 1]) in self.col_order:   # sıra alanı (K-184): Dönem, Dönem başı sırasıyla
                return (0, self.col_order[(i, key[: i + 1])])
            return (0, tr_key(v) if kind == "text" else v)
        kinds = [self._kind(a) for a in self.req.columns]
        return sorted(keys, key=lambda key: tuple(part(key, i, kinds[i]) for i in range(len(key))))

    def columns(self, leaves: list[tuple]) -> list[dict]:
        """Sütun başlıkları soldan sağa: yapraklar, üst başlığın sonunda ara toplamı, en sağda genel toplam. Dıştaki tarih alanında veri
        aralığındaki verisiz dönemler de sütundur (`empty`)."""
        req = self.req
        if not self.C:
            return [{"key": [], "level": 0, "total": False}]
        if len(leaves) > MAX_LEAF_COLUMNS:
            raise PivotTooLarge(f"Sütun sayısı çok fazla ({MAX_LEAF_COLUMNS}'den çok). Daha büyük bir dönem seçin, alan çıkarın ya da süzün.")
        keys = self._sorted([tuple(x) for x in leaves])
        outer = req.columns[0]
        if outer.bucket and keys:
            days = sorted({k[0] for k in keys if k[0] is not None})
            have, filled, day = {k[0] for k in keys}, [], days[0] if days else None
            while day is not None and day <= days[-1]:
                if day not in have:
                    filled.append((day, *([None] * (self.C - 1))))
                day = next_period(day, outer.bucket)
                if len(have) + len(filled) > MAX_PERIODS:
                    raise TooManyPeriods()
            empty = set(filled)
            keys = self._sorted(keys + filled)
        else:
            empty = set()
        out: list[dict] = []

        def close(prefix: tuple, upto: int) -> None:
            """Biten üst başlıkların ara toplam sütunları (içten dışa)."""
            for n in range(len(prefix), upto, -1):
                out.append({"key": list(prefix[:n]), "level": n, "total": True})

        previous: tuple | None = None
        for key in keys:
            if req.totals.subtotals and previous is not None:
                same = next((i for i in range(self.C - 1) if key[i] != previous[i]), self.C - 1)
                close(previous[: self.C - 1], same)
            out.append({"key": list(key), "level": self.C, "total": False, **({"empty": True} if key in empty else {})})
            previous = key
        if req.totals.subtotals and previous is not None:
            close(previous[: self.C - 1], 0)
        if req.totals.columns:
            out.append({"key": [], "level": 0, "total": True})
        if len(out) * len(req.values) > MAX_VALUE_COLUMNS:
            raise PivotTooLarge(f"Sütun sayısı çok fazla ({len(out) * len(req.values)} / {MAX_VALUE_COLUMNS} değer sütunu). "
                                "Daha büyük bir dönem seçin, alan ya da değer çıkarın ya da süzün.")
        return out

    def value_info(self) -> list[dict]:
        out = []
        for k, v in enumerate(self.req.values):
            if v.kind == "calc":
                out.append({"id": v.id, "fn": "calc", "field": None, "weight": None, "decimals": DEFAULT_DECIMALS, "percent": v.percent,
                            "from_unit": False, "type": "number"})
                continue
            col = self.b.columns.get(v.field or "", {})
            if v.fn in NOT_MEASURED:
                decimals, percent = 0, False
            else:
                base = col.get("decimals")
                decimals = (0 if col.get("type") == "integer" else DEFAULT_DECIMALS) if base is None else base
                percent = bool(col.get("percent"))
            dated = v.fn in ("min", "max") and col.get("type") in DATE_KINDS
            out.append({"id": v.id, "fn": v.fn, "field": v.field, "weight": v.weight, "decimals": decimals, "percent": percent and not dated,
                        "from_unit": k in self.unit_of, "type": col.get("type") if dated else "number"})
        return out

    def assemble(self, columns: list[dict], rows: list[dict], cells: list[dict], unit_decimals: dict, to_json) -> list[dict]:
        """Parçanın satırları: anahtar, düzey, toplam mı ve değer × sütun hücreleri."""
        position = {tuple(c["key"]): i for i, c in enumerate(columns) if not c.get("empty")}
        grid: dict[int, list[list]] = {r["rn"]: [[None] * len(columns) for _ in self.req.values] for r in rows}
        for cell in cells:
            level = next((j for j in range(self.C) if cell[f"gc{j}"]), self.C)
            at = position.get(tuple(cell[f"c{j}"] for j in range(level)))
            if at is None or cell["rn"] not in grid:
                continue
            order = sorted(range(len(self.req.values)), key=lambda k: self.req.values[k].kind == "calc")  # hesaplananlar sonda: işlenenler hazır
            for k in order:
                value = to_json(cell[f"v{k}"])
                v = self.req.values[k]
                if v.kind == "calc" and any(_is_mixed(grid[cell["rn"]][self.index[x]][at]) for x in (v.a, v.b)):
                    value = None                      # işlenenlerden biri karışık birimli: hesaplanan değer de boş
                if value is not None and k in self.unit_of:
                    a, b = cell[f"ua{k}"], cell[f"ub{k}"]
                    if a != b and k in self.checked:
                        value = {"mixed": True}       # listenin kendi miktar alanı: farklı birimler toplanmaz
                    elif a == b:
                        d = unit_decimals.get(a)
                        value = {"v": value, "d": DEFAULT_DECIMALS if d is None else int(d)}
                grid[cell["rn"]][k][at] = value
        out = []
        for r in rows:
            level = next((i for i in range(self.R) if r[f"g{i}"]), self.R)
            item = {"key": [to_json(r[f"r{i}"]) for i in range(level)], "level": level, "total": level < self.R, "cells": grid[r["rn"]]}
            formats = self._formats(item, columns)
            if formats:
                item["formats"] = formats
            out.append(item)
        return out

    def _formats(self, row: dict, columns: list[dict]) -> dict[str, list]:
        """Değerlerin kuralları hesaplanmış hücrede (K-183): ilk tutan etkin kuralın sırası; toplam hücreleri yalnız "Toplamlara da uygula"da."""
        out = {}
        for k, v in enumerate(self.req.values):
            rules = [r for r in v.rules if r.enabled]
            if not rules:
                continue
            hits = [None if (row["total"] or c["total"]) and not v.rules_on_totals else rule_hit(row["cells"][k][s], rules) for s, c in enumerate(columns)]
            if any(h is not None for h in hits):
                out[str(k)] = hits
        return out


def _is_mixed(cell) -> bool:
    return isinstance(cell, dict) and bool(cell.get("mixed"))


def cell_number(cell):
    """Hücrenin sayı değeri; boş, karışık birim ya da tarih ise None."""
    if isinstance(cell, dict):
        return cell.get("v")
    return cell if isinstance(cell, (int, float)) and not isinstance(cell, bool) else None


def rule_hit(cell, rules: list) -> int | None:
    """İlk tutan kuralın sırası. Koşullar yalnız sayı: Büyük, Küçük, Arası, Eşit, Boş, Her zaman. Karışık birimli ve tarih hücresine kural yok."""
    if _is_mixed(cell) or isinstance(cell, str):
        return None
    value = cell_number(cell)
    for i, rule in enumerate(rules):
        c = rule.condition
        if c.op == "always" or (c.op == "empty" and value is None):
            return i
        if value is None or c.op == "empty":
            continue
        if ((c.op == "gt" and c.value is not None and value > float(c.value)) or (c.op == "lt" and c.value is not None and value < float(c.value))
                or (c.op == "eq" and c.value is not None and value == float(c.value))
                or (c.op == "between" and c.min is not None and c.max is not None and c.min <= value <= c.max)):
            return i
    return None


MONTHS = period_list.MONTHS


def key_label(value, kind: str, bucket: str | None) -> str:
    """Satır ve sütun anahtarının yazısı (Excel; ekrandaki etiketlerle aynı): dönem, Evet / Hayır, boşta "(Boş)"."""
    if value is None or value == "":
        return "(Boş)"
    if bucket:  # dönem etiketleri tek işlevden (K-184): dönem tablosunun Dönem alanıyla aynı yazım; anahtar dönemin ilk günüdür
        day = date.fromisoformat(str(value)[:10])
        return period_list.label(period_list.KIND_OF_BUCKET[bucket], day, day.weekday())
    if isinstance(value, bool):
        return "Evet" if value else "Hayır"
    return str(value)


def axis_info(b: Builder, axes: list[PivotAxis]) -> list[dict]:
    return [{"field": a.field, "type": b.columns[a.field]["type"], "bucket": a.bucket} for a in axes]
