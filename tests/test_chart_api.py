"""Tablonun grafiği için toplama ve görünümde grafik (K-178, docs/08 "Grafik"). Sentetik v0 ile; saf kısımlar veritabanısız."""
from collections import defaultdict
from datetime import date, datetime, timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy import text

from app.api.lists import MATERIALS
from app.api.lists import chart as chart_query
from app.api.lists.query import Builder
from app.api.lists.request import ChartRequest
from app.api.services import lists as list_service

from test_lists_api import all_rows, api, query  # noqa: F401
from auth_helpers import auth, delete_users, ensure_user

ORDERS = "/api/transaction-sales-order"
MAT = "/api/materials"
STOCK = "/api/transaction-stock"


def chart(api, base=MAT, status=200, headers=None, **body):
    r = api.post(f"{base}/chart", json=body, headers=headers)
    assert r.status_code == status, r.text
    return r.json()


def rows_of(api, base, filters=()):
    out, offset = [], 0
    while True:
        r = api.post(f"{base}/query", json={"filters": list(filters), "offset": offset}).json()
        out += r["rows"]
        offset += len(r["rows"])
        if not r["rows"] or offset >= r["filtered"]:
            return out


# ------------------------------------------------------------------ saf: birleştirme, sınırlar, dönemler

def builder():
    return Builder(MATERIALS, {}, version=0, today=date(2026, 11, 17))


def leaf(x, n, s=None, p=None, lo=None, hi=None, d=None):
    """Tek alanlı yaprak: n satır, toplamı s (dolu satır d; verilmezse n)."""
    d = (n if s is not None else 0) if d is None else d
    return {"x": x, "p": p, "n": n, "s0": s, "d0": d, "lo0": lo if lo is not None else (s / d if d else None), "hi0": hi if hi is not None else (s / d if d else None)}


def request(**kw):
    base = {"x": {"field": "MaterialGroup"}, "series": [{"id": "a", "field": "StockCoverageDays", "fn": "sum"}]}
    return ChartRequest.model_validate({**base, **kw})


def test_top_categories_and_other_are_recomputed_from_the_rest():
    leaves = [leaf(f"G{i:02d}", 1, float(100 - i), lo=float(100 - i), hi=float(100 - i)) for i in range(40)]
    req = request(series=[{"id": "sum", "field": "StockCoverageDays", "fn": "sum"}, {"id": "avg", "field": "StockCoverageDays", "fn": "avg"},
                          {"id": "min", "field": "StockCoverageDays", "fn": "min"}, {"id": "max", "field": "StockCoverageDays", "fn": "max"},
                          {"id": "n", "fn": "count"}])
    out = chart_query.assemble(builder(), req, leaves, "Pazartesi")
    keys = [v["key"] for v in out["x"]["values"]]
    assert keys[:3] == ["G00", "G01", "G02"] and len(keys) == 31 and keys[-1] == chart_query.OTHER and out["x"]["other"]   # en büyük 30 + Diğer
    rest = [float(100 - i) for i in range(30, 40)]
    got = {s["id"]: s["data"][0][-1] for s in out["series"]}
    assert got == {"sum": sum(rest), "avg": sum(rest) / 10, "min": min(rest), "max": max(rest), "n": 10}                    # ortalama da kalan satırlardan
    assert out["rows"] == 40
    five = chart_query.assemble(builder(), request(limit=5), leaves, "Pazartesi")                                       # gösterilecek değer sayısı
    assert [v["key"] for v in five["x"]["values"]] == ["G00", "G01", "G02", "G03", "G04", chart_query.OTHER]
    assert five["series"][0]["data"][0][-1] == sum(float(100 - i) for i in range(5, 40))


def test_order_by_name_keeps_the_largest_and_sorts_them_in_turkish():
    leaves = [leaf("Zil", 1, 5.0), leaf("çelik", 1, 9.0), leaf("Cam", 1, 7.0), leaf("İp", 1, 3.0), leaf("ısı", 1, 2.0), leaf(None, 1, 8.0)]
    by_value = chart_query.assemble(builder(), request(), leaves, "Pazartesi")
    assert [v["key"] for v in by_value["x"]["values"]] == ["çelik", None, "Cam", "Zil", "İp", "ısı"]
    by_name = chart_query.assemble(builder(), request(order="name"), leaves, "Pazartesi")
    assert [v["key"] for v in by_name["x"]["values"]] == ["Cam", "çelik", "ısı", "İp", "Zil", None]                      # boş sonda


def test_split_is_limited_by_series_count_and_matrix_is_split_by_x():
    leaves = [leaf("A", 1, float(i), p=f"P{i:02d}") for i in range(1, 21)] + [leaf("B", 2, 50.0, p="P20")]
    one = chart_query.assemble(builder(), request(split="Brand"), leaves, "Pazartesi")
    assert len(one["split"]["values"]) == 12 and one["split"]["other"] and one["split"]["values"][0]["key"] == "P20"    # 11 + Diğer
    assert [v["key"] for v in one["x"]["values"]] == ["A", "B"]
    data = one["series"][0]["data"]
    assert data[0] == [20.0, 50.0] and data[-1] == [sum(range(1, 10)), 0.0]                                             # Diğer: P01…P09
    four = request(split="Brand", series=[{"id": str(i), "field": "StockCoverageDays", "fn": "sum"} for i in range(4)])
    assert len(chart_query.assemble(builder(), four, leaves, "Pazartesi")["split"]["values"]) == 6                      # 4 seri × 6 = 24


def test_date_axis_fills_gaps_and_limits_periods():
    req = request(x={"field": "UpdatedAt", "bucket": "month"}, series=[{"id": "s", "field": "StockCoverageDays", "fn": "sum"},
                                                                    {"id": "a", "field": "StockCoverageDays", "fn": "avg"}, {"id": "n", "fn": "count"}])
    leaves = [leaf(date(2026, 11, 1), 2, 10.0), leaf(datetime(2027, 2, 1), 1, 4.0), leaf(None, 3)]
    out = chart_query.assemble(builder(), req, leaves, "Pazartesi")
    assert [v["key"] for v in out["x"]["values"]] == ["2026-11-01", "2026-12-01", "2027-01-01", "2027-02-01", None]     # boş dönemler eksende, tarihsiz sonda
    assert out["x"]["kind"] == "date" and not out["x"]["other"]
    assert {s["id"]: s["data"][0] for s in out["series"]} == {"s": [10.0, 0.0, 0.0, 4.0, 0.0], "a": [5.0, None, None, 4.0, None], "n": [2, 0, 0, 1, 3]}
    daily = request(x={"field": "UpdatedAt", "bucket": "day"})
    with pytest.raises(chart_query.TooManyPeriods):
        chart_query.assemble(builder(), daily, [leaf(date(2025, 1, 1), 1, 1.0), leaf(date(2026, 12, 31), 1, 1.0)], "Pazartesi")


def test_next_period():
    assert chart_query.next_period(date(2026, 11, 16), "week") == date(2026, 11, 23)
    assert chart_query.next_period(date(2026, 12, 1), "month") == date(2027, 1, 1)
    assert chart_query.next_period(date(2026, 10, 1), "quarter") == date(2027, 1, 1)
    assert chart_query.next_period(date(2026, 1, 1), "year") == date(2027, 1, 1)


def test_mixed_units_blank_the_series_but_not_count():
    req = request(series=[{"id": "q", "field": "SafetyStock", "fn": "sum"}, {"id": "n", "fn": "count"}])
    leaves = [{**leaf("A", 2, 10.0), "u": "AD"}, {**leaf("A", 1, 3.0), "u": "KG"}, {**leaf("B", 4, None), "u": "M"}]   # M: katkı vermiyor (boş)
    out = chart_query.assemble(builder(), req, leaves, "Pazartesi")
    assert out["series"][0] == {"id": "q", "data": None, "mixed_units": True}
    assert out["series"][1]["data"] == [[4, 3]] and [v["key"] for v in out["x"]["values"]] == ["B", "A"]               # sıra: çizilen ilk seri (adet)
    single = chart_query.assemble(builder(), req, [{**leaf("A", 2, 10.0), "u": "AD"}, {**leaf("B", 4, None), "u": "M"}], "Pazartesi")
    assert single["series"][0] == {"id": "q", "data": [[10.0, 0.0]], "mixed_units": False}


@pytest.mark.parametrize("body, where", [
    ({"x": {"field": "Yok"}}, "x.field"),
    ({"x": {"field": "UpdatedAt"}}, "x.bucket"),                                            # tarihte dönem zorunlu
    ({"x": {"field": "MaterialGroup", "bucket": "month"}}, "x.bucket"),
    ({"x": {"field": "StockCoverageDays"}}, "x.field"),                                     # ondalıklı sayı eksen olamaz
    ({"split": "MaterialGroup"}, "split"),                                                  # eksenle aynı alan
    ({"split": "UpdatedAt"}, "split"),
    ({"series": [{"id": "a", "field": "Name", "fn": "sum"}]}, "series.0.field"),            # metinde yalnız adet
    ({"series": [{"id": "a", "fn": "sum"}]}, "series.0.field"),
    ({"series": [{"id": "a", "fn": "count"}, {"id": "a", "fn": "count"}]}, "series"),
])
def test_validation(body, where):
    req = request(**body)
    assert where in [p["field"] for p in chart_query.problems(builder(), req.x, req.split, req.series)]


# ------------------------------------------------------------------ veritabanıyla

pytestmark_db = pytest.mark.db


@pytest.mark.db
@pytest.mark.parametrize("day, bucket, week_start, expected", [
    ("2026-11-18", "day", 0, "2026-11-18"),
    ("2026-11-18", "week", 0, "2026-11-16"),      # Çarşamba → Pazartesi
    ("2026-11-16", "week", 0, "2026-11-16"),
    ("2026-11-22", "week", 0, "2026-11-16"),      # Pazar haftanın son günü
    ("2026-11-18", "week", 6, "2026-11-15"),      # hafta Pazar başlarsa
    ("2026-11-15", "week", 6, "2026-11-15"),
    ("2026-11-18", "week", 3, "2026-11-12"),      # Perşembe
    ("2026-11-18", "month", 0, "2026-11-01"),
    ("2026-11-18", "quarter", 0, "2026-10-01"),
    ("2026-03-31", "quarter", 0, "2026-01-01"),
    ("2026-11-18", "year", 0, "2026-01-01"),
])
def test_bucket_expression(db_engine, day, bucket, week_start, expected):
    expr = chart_query._bucket_expr(sa.cast(sa.literal(day), sa.Date), bucket, week_start)
    with db_engine.connect() as conn:
        assert str(conn.execute(sa.select(expr)).scalar_one())[:10] == expected


@pytest.mark.db
def test_category_chart_matches_the_rows(api):
    rows = all_rows(api, fields=["MaterialLevel", "StockCoverageDays"])
    out = chart(api, x={"field": "MaterialLevel"}, order="name",
                series=[{"id": "n", "fn": "count"}, {"id": "avg", "field": "StockCoverageDays", "fn": "avg"},
                        {"id": "max", "field": "StockCoverageDays", "fn": "max"}, {"id": "sum", "field": "StockCoverageDays", "fn": "sum"}])
    groups = defaultdict(list)
    for r in rows:
        groups[r["MaterialLevel"]].append(r["StockCoverageDays"])
    keys = [v["key"] for v in out["x"]["values"]]
    assert set(keys) == set(groups) and out["rows"] == len(rows) and out["split"] is None
    data = {s["id"]: dict(zip(keys, s["data"][0])) for s in out["series"]}
    for k, values in groups.items():
        full = [v for v in values if v is not None]
        assert data["n"][k] == len(values)
        assert data["sum"][k] == pytest.approx(sum(full))
        assert data["avg"][k] == (pytest.approx(sum(full) / len(full)) if full else None)
        assert data["max"][k] == (pytest.approx(max(full)) if full else None)


@pytest.mark.db
def test_filters_scope_and_split_are_the_same_as_the_list(api):
    flt = [{"field": "IsSellable", "op": "in", "values": [True]}]
    rows = all_rows(api, fields=["MaterialLevel", "MaterialType"], filters=flt)
    out = chart(api, filters=flt, x={"field": "MaterialLevel"}, split="MaterialType", series=[{"id": "n", "fn": "count"}])
    assert out["rows"] == len(rows) == query(api, filters=flt)["filtered"]                                               # filtre eşliği
    xs, ps = [v["key"] for v in out["x"]["values"]], [v["key"] for v in out["split"]["values"]]
    got = {(p, x): out["series"][0]["data"][i][j] for i, p in enumerate(ps) for j, x in enumerate(xs)}
    want = defaultdict(int)
    for r in rows:
        want[(r["MaterialType"], r["MaterialLevel"])] += 1
    assert {k: v for k, v in got.items() if v} == dict(want)
    bools = chart(api, x={"field": "IsSellable"}, series=[{"id": "n", "fn": "count"}])
    assert {v["label"] for v in bools["x"]["values"]} <= {"Evet", "Hayır", None} and sum(bools["series"][0]["data"][0]) == query(api)["total"]


@pytest.mark.db
def test_unit_mixing_looks_at_the_filtered_rows_not_the_whole_table(api):
    """Karışık birim kontrolü grafiğe giren satırlara (tablonun filtresinden sonra kalanlara) bakar, tablonun tamamına değil (K-178).
    Stok miktarı malzemenin birimiyle tutulur: filtresiz toplanamaz (uyarı, boş seri); tek birimli satırlara süzülünce toplanır ve çizilir."""
    unit_of = {r["Code"]: r["BaseUom"] for r in all_rows(api, fields=["Code", "BaseUom"])}
    rows = [r for r in rows_of(api, STOCK) if r["Quantity"] is not None]
    by_unit = defaultdict(list)
    for r in rows:
        by_unit[unit_of[r["MaterialCode"]]].append(r)
    assert len(by_unit) > 1, f"sentetik stokta birden çok birim olmalı: {set(by_unit)}"
    series = [{"id": "q", "field": "Quantity", "fn": "sum"}, {"id": "n", "fn": "count"}]

    def stock(codes):
        return chart(api, STOCK, filters=[{"field": "MaterialCode", "op": "in", "values": sorted(codes)}] if codes else [], x={"field": "MaterialCode"}, series=series)

    # filtresiz: birimler karışık → seri boş ve uyarı; adet etkilenmez
    mixed = stock(None)
    assert mixed["series"][0] == {"id": "q", "data": None, "mixed_units": True}
    assert mixed["series"][1]["mixed_units"] is False and mixed["rows"] >= len(rows)
    # tek birime süzülmüş (o birimdeki bütün malzemeler): toplanır ve çizilir, uyarı yok
    for unit, part in by_unit.items():
        one = stock({r["MaterialCode"] for r in part})
        assert one["series"][0]["mixed_units"] is False and one["series"][0]["data"] is not None, unit
        assert sum(v or 0 for v in one["series"][0]["data"][0]) == pytest.approx(sum(r["Quantity"] for r in part))
    # iki ayrı birimden birer malzeme: yine karışık
    first, second = [part[0]["MaterialCode"] for part in list(by_unit.values())[:2]]
    assert stock({first, second})["series"][0]["mixed_units"] is True


@pytest.mark.db
@pytest.mark.parametrize("name, index", [("Pazartesi", 0), ("Cumartesi", 5)])
def test_weekly_orders_follow_the_scenario_week_start(api, monkeypatch, name, index):
    monkeypatch.setattr(list_service, "week_start", lambda session, user_id, scenario_id: name)
    rows = rows_of(api, ORDERS)
    if not rows:
        pytest.skip("Satış siparişi yok")
    want = defaultdict(int)
    for r in rows:
        d = date.fromisoformat(r["RequestedDate"]) if r["RequestedDate"] else None
        want[None if d is None else (d - timedelta(days=(d.weekday() - index) % 7)).isoformat()] += 1
    out = chart(api, ORDERS, x={"field": "RequestedDate", "bucket": "week"}, series=[{"id": "n", "fn": "count"}])
    keys = [v["key"] for v in out["x"]["values"]]
    assert out["week_start"] == name and out["rows"] == len(rows)
    assert {k: v for k, v in zip(keys, out["series"][0]["data"][0]) if v} == dict(want)
    dated = [k for k in keys if k is not None]
    assert dated == sorted(dated) and all(date.fromisoformat(k).weekday() == index for k in dated)                       # eskiden yeniye, hafta başı
    assert all((date.fromisoformat(b) - date.fromisoformat(a)).days == 7 for a, b in zip(dated, dated[1:]))             # boş haftalar da var


@pytest.mark.db
def test_datetime_is_reduced_to_the_day_shown_by_the_filter(api):
    """Tarih-saat alanı güne indirgenir; gün sınırı filtredekiyle aynıdır: bir günün çubuğu, o günün filtresindeki satır sayısıdır."""
    out = chart(api, x={"field": "UpdatedAt", "bucket": "day"}, series=[{"id": "n", "fn": "count"}])
    assert out["x"]["values"] and all(len(v["key"]) == 10 for v in out["x"]["values"] if v["key"])                       # saat yok
    for v, n in list(zip(out["x"]["values"], out["series"][0]["data"][0]))[:3]:
        if v["key"]:
            flt = [{"field": "UpdatedAt", "op": "between", "from": v["key"], "to": v["key"]}]
            assert query(api, filters=flt)["filtered"] == n


@pytest.mark.db
def test_errors_and_permissions(api, db_engine):
    assert chart(api, status=422, x={"field": "Yok"}, series=[{"id": "n", "fn": "count"}])["error"]["code"] == "validation"
    assert chart(api, status=422, x={"field": "MaterialLevel"}, series=[])["error"]["code"] == "validation"
    nine = [{"id": str(i), "fn": "count"} for i in range(9)]
    assert chart(api, status=422, x={"field": "MaterialLevel"}, series=nine)["error"]["code"] == "validation"           # en çok 8 seri
    with db_engine.begin() as conn:
        end = ensure_user(conn, "pytest.grafik.end", "End user")
    try:
        ok = chart(api, headers=auth(end), x={"field": "MaterialLevel"}, series=[{"id": "n", "fn": "count"}])           # End user okur
        assert ok["rows"] > 0
        r = api.post("/api/users/chart", headers=auth(end), json={"x": {"field": "Role"}, "series": [{"id": "n", "fn": "count"}]})
        assert r.status_code == 403                                                                                     # listeyi göremeyen grafiğini de göremez
    finally:
        with db_engine.begin() as conn:
            delete_users(conn, [end])


# ------------------------------------------------------------------ görünümde grafik

CHART = {"x": {"field": "MaterialLevel"}, "series": [{"id": "s1", "field": "StockCoverageDays", "fn": "avg", "type": "line", "axis": "secondary",
                                                      "color": "#2E7D7A", "labels": {"show": True, "decimals": 1},
                                                      "threshold": {"value": 30, "color": "#F7DCD5"}},
                                                     {"id": "s2", "fn": "count"}],
         "bars": {"mode": "stack", "horizontal": True}, "ref_lines": [{"id": "r1", "kind": "avg", "series": "s1", "name": "Ortalama"}],
         "layout": "full", "height": 0.6, "title": "Seviye"}
VIEW = {"columns": [{"field": "Code"}, {"field": "Name"}]}


@pytest.fixture
def views(api, db_engine, test_users):
    def clean():
        with db_engine.begin() as conn:
            conn.execute(text("DELETE d FROM adm.TableViewDefault d JOIN adm.TableView v ON v.Id = d.ViewId WHERE v.Name LIKE N'pytest grafik%'"))
            conn.execute(text("DELETE FROM adm.TableView WHERE Name LIKE N'pytest grafik%'"))
    clean()
    yield test_users
    clean()


def save(api, name, definition, status=201, shared=False):
    r = api.post(f"{MAT}/views", json={"name": name, "is_shared": shared, "definition": definition})
    assert r.status_code == status, r.text
    return r.json()


@pytest.mark.db
def test_chart_is_saved_with_the_view_and_shared(api, views):
    v = save(api, "pytest grafik A", {**VIEW, "chart": CHART}, shared=True)
    got = v["definition"]["chart"]
    assert (got["v"], got["open"], got["layout"], got["height"], got["order"], got["split"], got["limit"]) == (1, True, "full", 0.6, "value", None, 30)
    assert got["series"][0] == {"id": "s1", "field": "StockCoverageDays", "fn": "avg", "type": "line", "axis": "secondary", "color": "#2E7D7A",
                                "labels": {"show": True, "decimals": 1, "zero": False}, "threshold": {"value": 30.0, "color": "#F7DCD5", "line": False}}
    assert got["series"][1] == {"id": "s2", "field": None, "fn": "count", "type": "bar", "axis": "primary", "color": None,
                                "labels": {"show": False, "decimals": 0, "zero": False}, "threshold": None}             # varsayılanlar dolu döner
    assert got["bars"] == {"mode": "stack", "horizontal": True, "totals": False, "width": "medium"} and got["legend"] == {"show": True, "position": "top"}
    assert (got["title_align"], got["title_size"], got["ref_lines"][0]["show_name"], got["ref_lines"][0]["show_value"]) == ("left", "medium", True, True)
    assert "panel" not in got                                                                                            # panelin açık ya da kapalı olması saklanmaz
    rich = {**CHART, "limit": 10, "title_align": "center", "title_size": "large", "bars": {"mode": "stack", "totals": True, "width": "thick"},
            "series": [{"id": "s1", "fn": "count", "type": "smooth", "labels": {"show": True, "zero": True}, "threshold": {"value": 5, "color": "#F7EBC4", "line": True}}],
            "ref_lines": [{"id": "r1", "kind": "value", "value": 3, "show_name": False, "show_value": True}]}
    r = save(api, "pytest grafik A2", {**VIEW, "chart": rich})["definition"]["chart"]
    assert r["bars"]["width"] == "thick"                                                                                 # çubuk genişliği görünümle saklanır
    assert (r["limit"], r["title_align"], r["title_size"], r["bars"]["totals"], r["series"][0]["type"], r["series"][0]["labels"]["zero"],
            r["series"][0]["threshold"]["line"], r["ref_lines"][0]["show_name"]) == (10, "center", "large", True, "smooth", True, True, False)
    assert got["axes"]["secondary"]["grid"] is False and got["ref_lines"][0]["series"] == "s1" and got["title"] == "Seviye"
    other = api.get(f"{MAT}/views", headers=auth(views[1])).json()["views"]                                             # paylaşılan görünümde grafik de gelir
    assert next(x for x in other if x["id"] == v["id"])["definition"]["chart"] == got
    plain = save(api, "pytest grafik B", VIEW)
    assert "chart" not in plain["definition"]                                                                           # anahtarsız görünüm: grafik kapalı
    cleared = api.put(f"{MAT}/views/{v['id']}", json={"definition": VIEW}).json()
    assert "chart" not in cleared["definition"]


@pytest.mark.db
@pytest.mark.parametrize("change, where", [
    ({"x": {"field": "Yok"}}, "definition.chart.x.field"),
    ({"series": [{"id": "s1", "field": "Name", "fn": "sum"}]}, "definition.chart.series.0.field"),
    ({"ref_lines": [{"id": "r", "kind": "avg", "series": "yok"}]}, "definition.chart.ref_lines.0.series"),
    ({"ref_lines": [{"id": "r", "kind": "value"}]}, "definition.chart.ref_lines.0.value"),
])
def test_invalid_chart_is_rejected(api, views, change, where):
    out = save(api, "pytest grafik X", {**VIEW, "chart": {**CHART, **change}}, status=422)
    assert where in [d["field"] for d in out["error"]["details"]]


@pytest.mark.db
@pytest.mark.parametrize("change", [
    {"series": [{"id": "s1", "fn": "count", "color": "kirmizi"}]}, {"series": [{"id": "s1", "fn": "count", "type": "pie"}]},
    {"height": 0.99}, {"bars": {"mode": "ust uste"}}, {"series": []}, {"x": {"field": "UpdatedAt", "bucket": "hour"}},   # saat kırılımı yok
    {"limit": 31}, {"limit": 0}, {"title_size": "dev"}, {"title_align": "ust"}, {"bars": {"width": "cok kalin"}},
])
def test_chart_shape_is_validated(api, views, change):
    assert save(api, "pytest grafik Y", {**VIEW, "chart": {**CHART, **change}}, status=422)["error"]["code"] == "validation"


@pytest.mark.db
def test_stored_chart_is_adapted_when_fields_disappear(api, views, db_engine):
    v = save(api, "pytest grafik C", {**VIEW, "chart": {**CHART, "split": "MaterialType"}})
    def stored(change):
        with db_engine.begin() as conn:
            raw = conn.execute(text("SELECT Definition FROM adm.TableView WHERE Id = :i"), {"i": v["id"]}).scalar_one()
            conn.execute(text("UPDATE adm.TableView SET Definition = :d WHERE Id = :i"), {"d": change(raw), "i": v["id"]})
        return next(x for x in api.get(f"{MAT}/views").json()["views"] if x["id"] == v["id"])
    got = stored(lambda raw: raw.replace('"field": "StockCoverageDays"', '"field": "EskiAlan"').replace('"split": "MaterialType"', '"split": "EskiKirilim"'))
    chart_out = got["definition"]["chart"]
    assert [s["id"] for s in chart_out["series"]] == ["s2"] and chart_out["split"] is None and chart_out["ref_lines"] == []  # serisi giden çizgi de gider
    assert len(got["warnings"]) == 2 and all("artık listede yok" in w for w in got["warnings"])
    gone = stored(lambda raw: raw.replace('"field": "MaterialLevel"', '"field": "EskiEksen"'))
    assert "chart" not in gone["definition"] and any("grafik görünümden çıkarıldı" in w for w in gone["warnings"])
