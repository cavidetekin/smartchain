"""Liste sorgusu kurucu (K-87): alan ve operatör beyaz listeden, değerler parametreyle.

Metin karşılaştırma ve sıralama Türkçe, büyük/küçük harf duyarsız (Turkish_100_CI_AS). Metin araması
(LIKE) Türkçe büyük harfe çevrilmiş değerlerin ikili karşılaştırmasıdır: anlam aynı, 50.000 satırda ~3 kat hızlı.
"""
from datetime import date, datetime, time, timedelta, timezone

import sqlalchemy as sa

from .definition import ListDefinition, column_type, columns, filter_type
from .request import AggSpec, FilterItem, GroupKeyItem, QueryRequest, SortItem

TURKISH = "Turkish_100_CI_AS"
BINARY = "Latin1_General_100_BIN2"
RELATIVE = ("this_week", "next_4_weeks")
# Gruplamada SQL Server maliyet tahmini seri plan seçiyor; paralel plan 50.000 satırda ~4 kat hızlı (K-90, docs/08).
PARALLEL_HINT = "OPTION (USE HINT('ENABLE_PARALLEL_PLAN_PREFERENCE'))"
UNIT_DECIMALS = "_unit_decimals"
UNIT = "_unit"
DEFAULT_UNIT_DECIMALS = 2  # birim bilinmiyorsa (docs/02 UnitOfMeasure.Decimals)
OPS = {  # her tipte "empty": değeri boş olanlar (U-13)
    "text": ("contains", "not_contains", "equals", "starts_with", "empty"),
    "list": ("in", "empty"),
    "number": ("between", "eq", "gt", "lt", "empty"),
    "date": ("between", "relative", "empty"),
}


class ListQueryError(ValueError):
    """Geçersiz alan, operatör ya da değer. details: [{field, problem}] (422)."""

    def __init__(self, details: list[dict]):
        super().__init__("; ".join(f"{d['field']}: {d['problem']}" for d in details))
        self.details = details


def like_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_").replace("[", "\\[")


def turkish(col: sa.ColumnElement) -> sa.ColumnElement:
    return col.collate(TURKISH)


def turkish_upper(expr: sa.ColumnElement) -> sa.ColumnElement:
    return sa.func.upper(expr.collate(TURKISH)).collate(BINARY)


def turkish_like(col: sa.ColumnElement, pattern: str) -> sa.ColumnElement:
    """Türkçe, büyük/küçük harf duyarsız LIKE ("İ/i", "I/ı" doğru); kaçış karakteri ters bölü."""
    return turkish_upper(col).like(turkish_upper(sa.literal(pattern, sa.Unicode)), escape="\\")


def utc_midnight(day: date) -> datetime:
    """Yerel gece yarısının UTC karşılığı (veritabanındaki zaman alanları UTC, saat dilimsiz)."""
    return datetime.combine(day, time()).astimezone(timezone.utc).replace(tzinfo=None)


def week_start(today: date) -> date:
    return today - timedelta(days=today.weekday())


def relative_range(value: str, today: date) -> tuple[date, date]:
    """[başlangıç, bitiş) — ISO hafta, Pazartesi başlar."""
    start = week_start(today)
    return start, start + timedelta(weeks=1 if value == "this_week" else 4)


class Builder:
    """Bir liste tanımı ve görünür kolonlarıyla sorgu parçaları kurar."""

    def __init__(self, defn: ListDefinition, labels: dict[str, str], version: int, today: date):
        self.defn = defn
        self.table = defn.sa_table
        self.columns = {c["field"]: c for c in columns(defn, labels)}
        self.version = version
        self.today = today

    # --- doğrulama -----------------------------------------------------------------------------------------
    def _col(self, name: str, where: str, problems: list[dict]) -> sa.Column | None:
        if name not in self.columns:
            problems.append({"field": where, "problem": f"Bilinmeyen alan: {name}"})
            return None
        return self.table.c[name]

    def version_clause(self) -> sa.ColumnElement:
        t, v = self.table, self.version
        return sa.and_(t.c.VersionFrom <= v, sa.or_(t.c.VersionTo.is_(None), t.c.VersionTo >= v))

    def select_columns(self, fields: list[str] | None) -> list[sa.Column]:
        problems: list[dict] = []
        names = fields if fields else [f for f, c in self.columns.items() if c["default_visible"]]
        cols = [self._col(n, "fields", problems) for n in names]
        if problems:
            raise ListQueryError(problems)
        return [self.table.c.Id] + [c for c in cols if c is not None and c.name != "Id"]

    def order_by(self, sort: list[SortItem]) -> list[sa.ColumnElement]:
        problems: list[dict] = []
        items = sort or [SortItem(field=f, dir=d) for f, d in self.defn.default_sort]
        out = []
        for i, s in enumerate(items):
            col = self._col(s.field, f"sort.{i}.field", problems)
            if col is None:
                continue
            expr = turkish(col) if column_type(col) == "text" else col
            out.append(expr.desc() if s.dir == "desc" else expr.asc())
        if problems:
            raise ListQueryError(problems)
        if not any(s.field == "Id" for s in items):
            out.append(self.table.c.Id.asc())  # kararlı parçalar
        return out

    def where(self, filters: list[FilterItem], skip_field: str | None = None) -> list[sa.ColumnElement]:
        problems: list[dict] = []
        out = []
        for i, f in enumerate(filters):
            if f.field == skip_field:
                continue
            where = f"filters.{i}"
            col = self._col(f.field, f"{where}.field", problems)
            if col is None:
                continue
            clause = self._filter(col, f, where, problems)
            if clause is not None:
                out.append(clause)
        if problems:
            raise ListQueryError(problems)
        return out

    def _filter(self, col: sa.Column, f: FilterItem, where: str, problems: list[dict]):
        kind = filter_type(self.defn, col)
        if f.op not in OPS[kind]:
            problems.append({"field": f"{where}.op", "problem": f"{f.field} alanında '{f.op}' kullanılamaz "
                                                                 f"({', '.join(OPS[kind])})"})
            return None

        def bad(problem: str, part: str = "value"):
            problems.append({"field": f"{where}.{part}", "problem": problem})

        if f.op == "empty":
            return self.is_empty(col)

        if kind == "text":
            if not isinstance(f.value, str) or not f.value.strip():
                return bad("Metin girilmeli")
            v = f.value.strip()
            c = turkish(col)
            if f.op == "equals":
                return c == v
            if f.op == "starts_with":
                return turkish_like(col, like_escape(v) + "%")
            pattern = "%" + like_escape(v) + "%"
            if f.op == "contains":
                return turkish_like(col, pattern)
            return sa.or_(col.is_(None), sa.not_(turkish_like(col, pattern)))

        if kind == "list":
            values = f.values or []
            if not values and not f.empty:
                return bad("En az bir değer ya da boş seçilmeli", "values")
            if column_type(col) == "bool":
                if any(not isinstance(v, bool) for v in values):
                    return bad("Evet/Hayır değeri true ya da false olmalı", "values")
            elif any(not isinstance(v, str) for v in values):
                return bad("Değerler metin olmalı", "values")
            parts = ([col.in_(values)] if values else []) + ([self.is_empty(col)] if f.empty else [])
            return sa.or_(*parts)

        if kind == "number":
            if f.op == "between":
                if f.min is None and f.max is None:
                    return bad("En az ve en çok değerden biri girilmeli", "min")
                parts = ([col >= f.min] if f.min is not None else []) + ([col <= f.max] if f.max is not None else [])
                return sa.and_(*parts)
            if isinstance(f.value, bool) or not isinstance(f.value, (int, float)):
                return bad("Sayı girilmeli")
            return {"eq": col == f.value, "gt": col > f.value, "lt": col < f.value}[f.op]

        # tarih: [başlangıç, bitiş) aralığına çevrilir; zamanlı alanda gün sonuna kadar
        if f.op == "relative":
            if f.value not in RELATIVE:
                return bad(f"Göreli seçim {', '.join(RELATIVE)} olmalı")
            start, end = relative_range(f.value, self.today)
        else:
            if f.from_ is None and f.to is None:
                return bad("Başlangıç ya da bitiş tarihi girilmeli", "from")
            start, end = f.from_, (f.to + timedelta(days=1) if f.to else None)
        if column_type(col) == "datetime":  # zaman alanları UTC; gün sınırı API sunucusunun yerel gece yarısı
            start, end = (utc_midnight(d) if d else None for d in (start, end))
        lo, hi = start, end
        parts = ([col >= lo] if lo is not None else []) + ([col < hi] if hi is not None else [])
        return sa.and_(*parts)

    def is_empty(self, col: sa.Column) -> sa.ColumnElement:
        """Boş: NULL; metinde boş metin de (U-13)."""
        return sa.or_(col.is_(None), col == "") if column_type(col) == "text" else col.is_(None)

    def group_expr(self, col: sa.Column) -> sa.ColumnElement:
        """Grup değeri: metinde boş metin de boş gruba (NULL) düşer."""
        # boş metin sabit yazılır: parametre olursa SELECT ile GROUP BY'daki ifade SQL Server'da farklı sayılır
        return sa.func.nullif(col, sa.literal_column("N''")) if column_type(col) == "text" else col

    def group_key_clauses(self, keys: list[GroupKeyItem]) -> list[sa.ColumnElement]:
        problems: list[dict] = []
        out = []
        for i, k in enumerate(keys):
            col = self._col(k.field, f"group_key.{i}.field", problems)
            if col is not None:
                out.append(self.is_empty(col) if k.value is None else col == k.value)
        if problems:
            raise ListQueryError(problems)
        return out

    # --- sorgular ------------------------------------------------------------------------------------------
    def rows_query(self, req: QueryRequest, chunk_size: int) -> sa.Select:
        """Parça satırları; limit boşsa parça büyüklüğü, büyükse hata (ListChunkSize, docs/08)."""
        limit = req.limit or chunk_size
        problems = ([{"field": "body.limit", "problem": f"En çok {chunk_size} satır istenebilir (ListChunkSize)"}]
                    if limit > chunk_size else [])
        cols = self.select_columns(req.fields)
        where = self.where(req.filters) + self.group_key_clauses(req.group_key)
        order = self.order_by(req.sort)
        if problems:
            raise ListQueryError(problems)
        q = sa.select(*cols)
        if self.defn.unit_field:  # satırın birimi (K-88): ondalığı serviste UnitOfMeasure'dan eklenir
            q = q.add_columns(self.table.c[self.defn.unit_field].label(UNIT))
        return q.where(self.version_clause(), *where).order_by(*order).offset(req.offset).limit(limit)

    def total_query(self) -> sa.Select:
        """Filtresiz sayı (güncel versiyondaki bütün kayıtlar)."""
        return sa.select(sa.func.count()).select_from(self.table).where(self.version_clause())

    def filtered_query(self, filters: list[FilterItem], group_key: list[GroupKeyItem] = ()) -> sa.Select:
        """Filtreli sayı (grubun satırlarında grup içi); filtre yoksa sorulmaz (toplamla aynı)."""
        where = self.where(filters) + self.group_key_clauses(list(group_key))
        return sa.select(sa.func.count()).select_from(self.table).where(self.version_clause(), *where)

    def values_query(self, field_name: str, search: str, filters: list[FilterItem], limit: int = 100) -> sa.Select:
        problems: list[dict] = []
        col = self._col(field_name, "field", problems)
        if col is not None and self.columns[field_name]["filter"] != "list":
            problems.append({"field": "field", "problem": f"{field_name} liste filtresi değil"})
        if problems:
            raise ListQueryError(problems)
        where = self.where(filters, skip_field=field_name)  # kendi filtresi seçenekleri daraltmaz
        if search.strip():
            where.append(turkish_like(col, "%" + like_escape(search.strip()) + "%"))
        g = self.group_expr(col)
        inner = (sa.select(g.label("value"), sa.func.count().label("count"))
                 .where(self.version_clause(), *where).group_by(g).subquery())
        v = inner.c.value
        order = [sa.case((v.is_(None), 0), else_=1), turkish(v) if column_type(col) == "text" else v]
        return sa.select(inner).order_by(*order).limit(limit + 1)  # boş (U-13) başta, sonra ilk 100 değer

    def groups_query(self, group_by: list[str], filters: list[FilterItem], sort: list[SortItem],
                     specs: dict[str, AggSpec], limit: int) -> tuple[sa.Select, list[str]]:
        """Yaprak gruplar (K-90): grup değerleri, satır sayısı ve her ara toplam için yaprak ölçüleri:
        k_ katkı veren satır sayısı (birim karışıklığı ve "sayı" için), s_ pay, d_ payda (ortalamalar), v_ en küçük /
        en büyük. Birimden ondalıklı kolon (ya da ağırlık) varsa birim gizli son düzeydir ("u"); karışıklık Python'da
        bulunur. Sıra: grup alanı sıralamadaysa onun yönü, değilse artan, Türkçe; boş grup en sonda."""
        problems: list[dict] = []
        cols = [self._col(f, f"group_by.{i}", problems) for i, f in enumerate(group_by)]
        if len(set(group_by)) != len(group_by):
            problems.append({"field": "group_by", "problem": "Aynı alan iki kez seçilemez"})
        if problems:
            raise ListQueryError(problems)
        where = self.where(filters)
        keys = [self.group_expr(c).label(f"g{i}") for i, c in enumerate(cols)]
        measures = [sa.func.count().label("n")]
        for f, spec in specs.items():
            measures += self._measures(f, spec)
        grouping = [self.group_expr(c) for c in cols]
        if self.defn.unit_field and any(self.unit_relevant(f, spec) for f, spec in specs.items()):
            unit = self.table.c[self.defn.unit_field]
            keys.append(unit.label("u"))
            grouping.append(unit)
        inner = (sa.select(*keys, *measures).where(self.version_clause(), *where).group_by(*grouping).subquery())
        dirs = {s.field: s.dir for s in sort}
        order = []
        for i, c in enumerate(cols):
            g = inner.c[f"g{i}"]
            order.append(sa.case((g.is_(None), 1), else_=0))
            expr = turkish(g) if column_type(c) == "text" else g
            order.append(expr.desc() if dirs.get(group_by[i]) == "desc" else expr.asc())
        q = sa.select(inner).order_by(*order).limit(limit).with_statement_hint(PARALLEL_HINT, "mssql")
        return q, [c.name for c in cols]

    def _measures(self, f: str, spec: AggSpec) -> list[sa.ColumnElement]:
        c = self.table.c[f]
        if spec.fn == "wavg":
            w = self.table.c[spec.weight]
            both = sa.and_(c.is_not(None), w.is_not(None))
            return [sa.func.count(sa.case((both, 1))).label(f"k_{f}"),
                    sa.func.sum(sa.case((both, c * w))).label(f"s_{f}"),
                    sa.func.sum(sa.case((both, w))).label(f"d_{f}")]
        out = [sa.func.count(c).label(f"k_{f}")]
        if spec.fn in ("sum", "avg"):
            out += [sa.func.sum(c).label(f"s_{f}"), sa.func.count(c).label(f"d_{f}")]
        elif spec.fn == "avg_nonzero":
            out += [sa.func.sum(c).label(f"s_{f}"), sa.func.count(sa.case((c != 0, 1))).label(f"d_{f}")]
        elif spec.fn in ("min", "max"):
            out.append(getattr(sa.func, spec.fn)(c).label(f"v_{f}"))
        return out

    def unit_relevant(self, f: str, spec: AggSpec) -> bool:
        """Birim karışıklığı bu ara toplamı geçersiz kılar mı (K-88, K-90): miktar alanı ya da miktar ağırlığı; sayı hariç."""
        units = self.defn.unit_decimals
        return spec.fn != "count" and (f in units or (spec.fn == "wavg" and spec.weight in units))

    def aggregate_specs(self, fields: list[str] | None, specs: dict[str, AggSpec] | None,
                        where: str = "aggregates") -> dict[str, AggSpec]:
        """Ara toplam türleri: verilmezse görünen kolonlarda liste tanımının varsayılanı. "none" atılır.
        Yalnız sayı alanları; ağırlıklı ortalamada ağırlık başka bir sayı alanı olmalı (422)."""
        if specs is None:
            return {f: AggSpec(fn=fn) for f, fn in self.defn.aggregates.items()
                    if f in self.columns and (fields is None or f in fields)}
        problems: list[dict] = []
        numeric = {f for f, c in self.columns.items() if c["type"] in ("number", "integer")}
        out = {}
        for f, spec in specs.items():
            if f not in numeric:
                problems.append({"field": f"{where}.{f}", "problem": f"Ara toplam yalnız sayı alanında: {f}"})
            elif spec.fn == "wavg" and (spec.weight not in numeric or spec.weight == f):
                problems.append({"field": f"{where}.{f}.weight", "problem": "Ağırlıklı ortalama için başka bir sayı alanı seçilmeli"})
            elif spec.fn != "none":
                out[f] = spec if spec.fn == "wavg" else AggSpec(fn=spec.fn)
        if problems:
            raise ListQueryError(problems)
        return out
