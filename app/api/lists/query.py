"""Liste sorgusu kurucu (K-87): alan ve operatör beyaz listeden, değerler parametreyle.

Metin karşılaştırma ve sıralama Türkçe, büyük/küçük harf duyarsız (Turkish_100_CI_AS). Metin araması
(LIKE) Türkçe büyük harfe çevrilmiş değerlerin ikili karşılaştırmasıdır: anlam aynı, 50.000 satırda ~3 kat hızlı.
"""
from datetime import date, datetime, time, timedelta, timezone

import sqlalchemy as sa

from .definition import ListDefinition, column_type, columns, filter_type
from .request import FilterItem, QueryRequest, SortItem

TURKISH = "Turkish_100_CI_AS"
BINARY = "Latin1_General_100_BIN2"
RELATIVE = ("this_week", "next_4_weeks")
UNIT_DECIMALS = "_unit_decimals"
UNIT = "_unit"
DEFAULT_UNIT_DECIMALS = 2  # birim bilinmiyorsa (docs/02 UnitOfMeasure.Decimals)
OPS = {
    "text": ("contains", "not_contains", "equals", "starts_with"),
    "list": ("in",),
    "number": ("between", "eq", "gt", "lt"),
    "date": ("between", "relative"),
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
            if not f.values:
                return bad("En az bir değer seçilmeli", "values")
            if column_type(col) == "bool":
                if any(not isinstance(v, bool) for v in f.values):
                    return bad("Evet/Hayır değeri true ya da false olmalı", "values")
            elif any(not isinstance(v, str) for v in f.values):
                return bad("Değerler metin olmalı", "values")
            return col.in_(f.values)

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

    # --- sorgular ------------------------------------------------------------------------------------------
    def rows_query(self, req: QueryRequest, chunk_size: int) -> sa.Select:
        """Parça satırları; limit boşsa parça büyüklüğü, büyükse hata (ListChunkSize, docs/08)."""
        limit = req.limit or chunk_size
        problems = [{"field": "body.limit", "problem": f"En çok {chunk_size} satır istenebilir (ListChunkSize)"}]             if limit > chunk_size else []
        cols = self.select_columns(req.fields)
        where = self.where(req.filters)
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

    def filtered_query(self, filters: list[FilterItem]) -> sa.Select:
        """Filtreli sayı; filtre yoksa sorulmaz (toplamla aynı)."""
        return sa.select(sa.func.count()).select_from(self.table).where(self.version_clause(), *self.where(filters))

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
        order = turkish(col) if column_type(col) == "text" else col
        return (sa.select(col.label("value"), sa.func.count().label("count"))
                .where(self.version_clause(), col.is_not(None), *where)
                .group_by(col).order_by(order).limit(limit))
