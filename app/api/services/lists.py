"""Liste sorgusu (K-87, docs/08): kolonlar, parça parça satırlar ve sayılar, liste filtresi değerleri."""
from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from ..errors import DB_UNAVAILABLE, AppError
from ..lists.definition import ListDefinition, SourceContext, columns as column_list
from ..lists import relations
from ..lists.query import DEFAULT_UNIT_DECIMALS, FIELD_DECIMALS, SELECTION_MAX, UNIT, UNIT_DECIMALS, Builder, ListQueryError
from ..lists import chart as chart_query
from ..lists import pivot as pivot_query
from ..lists.groups import build_tree
from ..lists.request import ChartRequest, ChartSelection, GroupsRequest, IdsRequest, PivotRequest, PointsRequest, QueryRequest, ValuesRequest
from app.params import scenarios as scenario_service, service as params
from app.params.horizon import week_start_index
from app.manual import manual_fields

from ..repositories import data_versions, export as export_repo, lists as repo
from . import manual_values


RULES = "_rules"  # satırda tutan kurallar (K-95, docs/08)


def today() -> date:
    """Göreli tarih filtresinin "bugün"ü: API sunucusunun yerel tarihi (docs/08). Testte değiştirilir."""
    return date.today()


def _json(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):  # veritabanında UTC (SYSUTCDATETIME)
        return value.replace(tzinfo=timezone.utc).isoformat(timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    return value


def _run(session: Session | None, work):
    if session is None:
        raise AppError("database_unavailable", DB_UNAVAILABLE, 503)
    try:
        return work()
    except ListQueryError as exc:
        raise AppError("validation", "Girilen bilgiler geçersiz.", 422, exc.details) from exc
    except DBAPIError as exc:
        raise AppError("database_unavailable", DB_UNAVAILABLE, 503) from exc


def labels_of(session: Session) -> relations.Labels:
    """Tablo → alan etiketleri (FieldDefinition); ilişki ve hedef alan adları için, istek boyunca bir kez okunur."""
    cache: dict[str, dict[str, str]] = {}

    def read(table: str) -> dict[str, str]:
        if table not in cache:
            cache[table] = repo.read_labels(session, table)
        return cache[table]
    return read


def scenario_of(session: Session, user_id: int | None, req=None) -> int:
    """İsteğin senaryosu: gövdedeki `scenario_id`; verilmezse kullanıcının seçili senaryosu, o da yoksa Baz (K-184)."""
    try:
        return scenario_service.resolve(session, user_id, getattr(req, "scenario_id", None))["Id"]
    except scenario_service.ScenarioError as exc:
        raise AppError("not_found", "Senaryo bulunamadı.", 404) from exc


def _builder(session: Session, defn: ListDefinition, role: str | None = None, user_id: int | None = None, req=None) -> Builder:
    """role, user_id: oturumdaki kullanıcı (row_scope); verilmezse en dar kapsam. req: isteğin gövdesi; içinde geçen ilişkili alanların
    ilişkileri kaynağa birleştirilir (K-182)."""
    if defn.source_factory is not None:  # dönem tablosu (K-184): kaynak, isteğin senaryosuna göre kurulur
        defn = replace(defn, source=defn.source_factory(SourceContext(session, scenario_of(session, user_id, req), today())))
    related = relations.scan(req.model_dump(mode="json")) if req is not None and defn.related_table else ()
    extra = {"related": related, "labels_of": labels_of(session)} if related else {}
    if not defn.versioned:
        return Builder(defn, repo.read_labels(session, defn.table_name), None, today(), role, user_id, **extra)
    current = data_versions.read_current(session)
    if current is None:
        raise AppError("no_data_version", "Henüz veri yüklenmedi.", 404)
    return Builder(defn, repo.read_labels(session, defn.table_name), current["Id"], today(), role, user_id, **extra)


def _related_decimals(session: Session, b: Builder, rows: list[dict]) -> None:
    """İlişkili miktar alanlarının ondalığı satırda (K-182): hedef kaydın biriminden; birim bilinmiyorsa 2."""
    wanted = {f: u for f, u in b.related_units.items() if rows and u in rows[0]}
    if not wanted:
        return
    units = repo.read_unit_decimals(session)
    for r in rows:
        r[FIELD_DECIMALS] = {f: DEFAULT_UNIT_DECIMALS if units.get(r[u]) is None else int(units[r[u]]) for f, u in wanted.items()}
    for u in set(wanted.values()):
        for r in rows:
            r.pop(u, None)


def columns(session: Session | None, defn: ListDefinition) -> dict:
    def work():
        limits = export_repo.read_settings(session)
        return {"chunk_size": repo.read_chunk_size(session),
                "columns": column_list(defn, repo.read_labels(session, defn.table_name),
                                       manual=frozenset(manual_fields(session, defn.manual_table)) if defn.manual_table else frozenset()),
                "relations": relations.headings(defn, labels_of(session)),  # İlişkili alanların başlıkları (K-182)
                # Dönem tablosu (K-184): İlk · Son dönem değeri sunulur; ürünün Standart'ı pivot; hazır hesaplanan değerler
                **({"period_table": True} if defn.period else {}),
                # Kaynağı senaryoya göre kurulan liste (K-185): arayüz isteklere seçili senaryoyu ekler
                **({"scenario_list": True} if defn.source_factory else {}),
                **({"standard_pivot": dict(defn.standard_pivot)} if defn.standard_pivot else {}),
                **({"chart_value": defn.chart_value} if defn.chart_value else {}),
                **({"calculated_values": [dict(c) for c in defn.calculated]} if defn.calculated else {}),
                "export": {"title": defn.title or defn.name, "file_slug": defn.file_slug or defn.name,
                           "sync_max_rows": limits["ExportSyncMaxRows"], "max_rows": limits["ExportMaxRows"],
                           "file_hours": limits["ExportFileHours"]}}
    return _run(session, work)


def related(session: Session | None, defn: ListDefinition, path: str) -> dict:
    """Bir ilişkinin alanları ve alt ilişkileri (Alanlar paneli, K-182)."""
    def work():
        found = relations.catalog(defn, path, labels_of(session))
        if found is None:
            raise AppError("not_found", "İlişki bulunamadı.", 404)
        return found
    return _run(session, work)


def query(session: Session | None, defn: ListDefinition, req: QueryRequest, role: str | None = None,
          user_id: int | None = None) -> dict:
    def work():
        b = _builder(session, defn, role, user_id, req)
        apply_selection(session, b, req.chart_selection, user_id)
        rows_q = b.rows_query(req, repo.read_chunk_size(session))
        rules_valid = b.rule_columns(req.rules)  # doğrulama (422) satırlar okunmadan
        rows = [{k: _json(v) for k, v in r.items()} for r in repo.fetch_rows(session, rows_q)]
        for field_name, fn in defn.value_format.items():
            for r in rows:
                if field_name in r:
                    r[field_name] = fn(r[field_name])
        if defn.row_format:  # satıra bağlı okunur biçim (K-173)
            defn.row_format(rows)
        if req.rules:  # tutan kuralların istekteki sırası (K-95); dönen satırlarda ayrı sorguyla
            hit = {}
            if rows and rules_valid:
                for r in repo.fetch_rows(session, b.rules_by_id_query([r["Id"] for r in rows], req.rules)):
                    hit[r["Id"]] = [i for i in range(len(req.rules)) if r[f"_r{i}"]]
            for r in rows:
                r[RULES] = hit.get(r["Id"], [])
        if defn.manual_table:  # hücre kaynağı: manuel değer ve kural (K-170)
            manual_values.annotate(session, defn.manual_table, rows)
        if defn.unit_field:  # her satırda temel birimin ondalığı (K-88); birim bilinmiyorsa 2
            units = repo.read_unit_decimals(session)
            for r in rows:
                d = units.get(r.pop(UNIT))
                r[UNIT_DECIMALS] = DEFAULT_UNIT_DECIMALS if d is None else int(d)
        _related_decimals(session, b, rows)
        total = repo.fetch_count(session, b.total_query())
        narrowed = req.filters or req.group_key or req.chart_selection
        filtered = repo.fetch_count(session, b.filtered_query(req.filters, req.group_key)) if narrowed else total
        return {"rows": rows, "offset": req.offset, "filtered": filtered, "total": total}
    return _run(session, work)


def ids(session: Session | None, defn: ListDefinition, req: IdsRequest, role: str | None = None, user_id: int | None = None) -> dict:
    """Filtredeki satırların kimlikleri (çoklu seçim, K-171), en çok SELECTION_MAX."""
    def work():
        b = _builder(session, defn, role, user_id, req)
        apply_selection(session, b, req.chart_selection, user_id)
        found = [r["Id"] for r in repo.fetch_rows(session, b.ids_query(req.filters, SELECTION_MAX))]
        return {"ids": [str(i) for i in found[:SELECTION_MAX]], "truncated": len(found) > SELECTION_MAX}
    return _run(session, work)


def values(session: Session | None, defn: ListDefinition, req: ValuesRequest, role: str | None = None,
           user_id: int | None = None) -> list[dict]:
    def work():
        b = _builder(session, defn, role, user_id, req)
        rows = repo.fetch_rows(session, b.values_query(req.field, req.search, req.filters))
        return [{"value": _json(r["value"]), "count": int(r["count"])} for r in rows]
    return _run(session, work)


def groups(session: Session | None, defn: ListDefinition, req: GroupsRequest, role: str | None = None,
           user_id: int | None = None) -> dict:
    """Grup ağacı, satır sayıları ve ara toplamlar (K-90)."""
    def work():
        b = _builder(session, defn, role, user_id, req)
        apply_selection(session, b, req.chart_selection, user_id)
        max_groups = repo.read_max_groups(session)
        specs = b.aggregate_specs(req.fields, req.aggregates)
        # birim gizli düzey olabilir: satır sayısı yaprak grup sayısından fazla olabilir; üst sınır geniş tutulur
        q, fields = b.groups_query(req.group_by, req.filters, req.sort, specs, (max_groups + 1) * 20)
        leaves = repo.fetch_rows(session, q)
        units = repo.read_unit_decimals(session) if defn.unit_field or b.related_units else {}
        unit_relevant = {f for f, spec in specs.items() if b.unit_relevant(f, spec)}
        tree = build_tree(leaves, len(fields), {f: s.fn for f, s in specs.items()}, unit_relevant, _json, units)
        tree["aggregate_specs"] = {f: s.model_dump(exclude_none=True) for f, s in specs.items()}
        if tree["leaf_groups"] > max_groups:
            raise AppError("too_many_groups", f"En çok {max_groups} grup gösterilebilir.", 422)
        tree["total"] = repo.fetch_count(session, b.total_query())  # "120 / 840" sayacı (U-12)
        tree["filtered"] = sum(g["count"] for g in tree["groups"])
        return tree
    return _run(session, work)


def week_start(session: Session, user_id: int | None, scenario_id: int | None) -> str:
    """Hafta başlangıcı: isteğin senaryosunun (verilmezse kullanıcının seçili senaryosunun) Planlama ufku ayarı; senaryo yoksa Pazartesi (K-178)."""
    try:
        scenario = scenario_service.resolve(session, user_id, scenario_id)
    except scenario_service.ScenarioError:
        return "Pazartesi"
    return params.read_settings(session, scenario["Id"]).get("WeekStart") or "Pazartesi"


def apply_selection(session: Session, b: Builder, sel: ChartSelection | None, user_id: int | None) -> None:
    """Grafik seçimini (K-179) sorgu kurucusuna koşul olarak koyar: satır, grup, kimlik ve dışa aktarım sorguları bu koşulla çalışır."""
    if sel is None:
        return
    weekly = sel.x.bucket == "week" or any(w.bucket == "week" for w in sel.within)
    start = week_start(session, user_id, sel.scenario_id) if weekly else "Pazartesi"
    b.selection = chart_query.selection_clause(b, sel, week_start_index(start))


def chart(session: Session | None, defn: ListDefinition, req: ChartRequest, role: str | None = None, user_id: int | None = None) -> dict:
    """Tablonun grafiği için toplama (K-178): listeyle aynı filtre, versiyon ve satır kapsamı."""
    def work():
        b = _builder(session, defn, role, user_id, req)
        weekly = req.x.bucket == "week" or any(w.bucket == "week" for w in req.within)
        start = week_start(session, user_id, req.scenario_id) if weekly else "Pazartesi"
        ws = week_start_index(start)
        leaves = repo.fetch_rows(session, chart_query.query(b, req, ws))
        # Benzersiz say (K-179): seri başına ek sorgu
        distinct = {s.id: repo.fetch_rows(session, chart_query.distinct_query(b, req, s, ws)) for s in req.series if s.fn == "distinct"}
        try:
            out = chart_query.assemble(b, req, leaves, start, distinct)
        except chart_query.TooManyPeriods as exc:
            raise AppError("too_many_periods", chart_query.TOO_MANY_PERIODS, 422) from exc
        return {**out, "x": {**out["x"], "values": [{**v, "key": _json(v["key"])} for v in out["x"]["values"]]}}
    return _run(session, work)


def pivot(session: Session | None, defn: ListDefinition, req: PivotRequest, role: str | None = None, user_id: int | None = None,
          unlimited: bool = False) -> dict:
    """Pivot (K-183): listeyle aynı filtre, versiyon ve satır kapsamı. Satırlar parça parça; toplamlar kayıtlardan, veritabanında.
    unlimited: dışa aktarım büyük parçalarla okur (ListChunkSize sınırı ekranın isteği içindir)."""
    def work():
        b = _builder(session, defn, role, user_id, req)
        problems = pivot_query.problems(b, req.rows, req.columns, req.values, req.sort.by)
        if problems:
            raise ListQueryError(problems)
        apply_selection(session, b, req.chart_selection, user_id)
        weekly = any(a.bucket == "week" for a in (*req.rows, *req.columns))
        start = week_start(session, user_id, req.scenario_id) if weekly else "Pazartesi"
        chunk = repo.read_chunk_size(session)
        if (req.limit or chunk) > chunk and not unlimited:
            raise ListQueryError([{"field": "body.limit", "problem": f"En çok {chunk} satır istenebilir (ListChunkSize)"}])
        p = pivot_query.Pivot(b, req.model_copy(update={"limit": req.limit or chunk}), week_start_index(start))
        try:
            leaf_columns = repo.fetch_rows(session, p.columns_query()) if req.columns else []
            columns = p.columns(p.leaf_columns(leaf_columns))
        except pivot_query.PivotTooLarge as exc:
            raise AppError("pivot_too_large", str(exc), 422) from exc
        except chart_query.TooManyPeriods as exc:
            raise AppError("too_many_periods", chart_query.TOO_MANY_PERIODS, 422) from exc
        rows = repo.fetch_rows(session, p.rows_query())
        cells = repo.fetch_rows(session, p.cells_query()) if rows else []
        row_count = int(rows[0]["cnt"]) if rows else repo.fetch_count(session, p.count_query())
        units = repo.read_unit_decimals(session) if p.unit_of else {}
        return {"row_fields": pivot_query.axis_info(b, req.rows), "column_fields": pivot_query.axis_info(b, req.columns),
                "columns": [{**c, "key": [_json(k) for k in c["key"]]} for c in columns], "values": p.value_info(),
                "rows": p.assemble(columns, rows, cells, units, _json), "offset": req.offset, "row_count": row_count, "week_start": start}
    return _run(session, work)


def points(session: Session | None, defn: ListDefinition, req: PointsRequest, role: str | None = None, user_id: int | None = None) -> dict:
    """Dağılım grafiğinin noktaları (K-179): listeyle aynı filtre, versiyon ve satır kapsamı; en çok `limit` nokta, aşımda eşit aralıklı örnekleme.
    Bir eksendeki alanın birimi karışıksa nokta dönmez."""
    def work():
        b = _builder(session, defn, role, user_id, req)
        info = chart_query.points_summary(b, req, repo.fetch_rows(session, chart_query.points_summary_query(b, req)))
        found = [] if any(info["mixed_units"].values()) or not info["rows"] else repo.fetch_rows(session, chart_query.points_query(b, req, info["rows"]))
        out = chart_query.assemble_points(req, info, found)
        if out["colors"]:
            out["colors"]["values"] = [{**v, "key": _json(v["key"])} for v in out["colors"]["values"]]
        return {**out, "label_field": chart_query.label_field(b)}
    return _run(session, work)
