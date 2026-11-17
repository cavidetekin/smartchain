"""Grafik, üçüncü bölüm (7.4c, K-179): küçük çoğullar, dağılım noktaları, grafiğin dışa aktarımı, görünümde tür. Sentetik v0 ile."""
import base64
import io
import json
import struct
import zipfile
import zlib
from datetime import date

import pytest
from openpyxl import load_workbook
from sqlalchemy import text

from app.api.lists import chart as chart_query
from app.api.lists.request import ChartRequest, PointsRequest
from app.api.services import export as export_service

from test_chart_api import MAT, ORDERS, STOCK, _filtered, builder, chart, leaf, rows_of
from test_lists_api import api, query  # noqa: F401
from auth_helpers import auth, delete_users, ensure_user


def png(width=4, height=3) -> bytes:
    """Geçerli küçük bir PNG (tek renk)."""
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + b"\xff\xff\xff" * width for _ in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


PNG64 = base64.b64encode(png()).decode()


def images(content: bytes) -> list[bytes]:
    """Dosyaya gömülü görseller (Excel dosyası bir zip'tir)."""
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        return [z.read(n) for n in z.namelist() if n.startswith("xl/media/")]


# ------------------------------------------------------------------ saf: küçük grafikler

def test_facets_keep_twelve_and_fold_the_rest_into_other():
    leaves = [{**leaf("A", 1, float(100 - i)), "f": f"F{i:02d}"} for i in range(14)] + [{**leaf("B", 1, 5.0), "f": "F00"}]
    req = ChartRequest.model_validate({"x": {"field": "MaterialGroup"}, "facet": "MaterialLevel",
                                       "series": [{"id": "a", "field": "StockCoverageDays", "fn": "sum"}, {"id": "n", "fn": "count"}]})
    out = chart_query.assemble(builder(), req, leaves, "Pazartesi")
    keys = [v["key"] for v in out["facets"]["values"]]
    assert keys == [f"F{i:02d}" for i in range(12)] + [chart_query.OTHER] and out["facets"]["other"] is True      # büyüklük sırası; ilk seri
    assert [v["key"] for v in out["x"]["values"]] == ["A", "B"]                                                  # yatay eksen ortak
    a, n = (s["data"] for s in out["series"])
    assert len(a) == 13 and all(len(grid) == 1 and len(grid[0]) == 2 for grid in a)                              # küçük grafik × kırılım × yatay eksen
    assert a[0][0] == [100.0, 5.0] and a[1][0] == [99.0, 0.0]
    assert a[12][0] == [88.0 + 87.0, 0.0] and n[12][0] == [2, 0]                                                 # "Diğer" kalan satırlardan
    plain = chart_query.assemble(builder(), ChartRequest.model_validate({**req.model_dump(), "facet": None}), leaves, "Pazartesi")
    assert plain["facets"] is None and plain["series"][0]["data"] == [[sum(100.0 - i for i in range(14)), 5.0]]   # küçük grafik yoksa iki boyut


def test_distinct_is_counted_per_facet():
    leaves = [{"x": "A", "f": "F1", "n": 3}, {"x": "A", "f": "F2", "n": 2}]
    rows = [{"x": "A", "f": "F1", "v": "K1"}, {"x": "A", "f": "F1", "v": "K2"}, {"x": "A", "f": "F2", "v": "K1"}]
    req = ChartRequest.model_validate({"x": {"field": "MaterialGroup"}, "facet": "MaterialLevel", "series": [{"id": "d", "field": "Code", "fn": "distinct"}]})
    out = chart_query.assemble(builder(), req, leaves, "Pazartesi", {"d": rows})
    assert [v["key"] for v in out["facets"]["values"]] == ["F1", "F2"] and out["series"][0]["data"] == [[[2]], [[1]]]


@pytest.mark.parametrize("body, where", [
    ({"x": {"field": "MaterialGroup"}, "facet": "MaterialGroup", "series": [{"id": "n", "fn": "count"}]}, "facet"),        # yatay eksenle aynı
    ({"x": {"field": "MaterialGroup"}, "split": "MaterialLevel", "facet": "MaterialLevel", "series": [{"id": "n", "fn": "count"}]}, "facet"),
    ({"x": {"field": "MaterialGroup"}, "facet": "SafetyStock", "series": [{"id": "n", "fn": "count"}]}, "facet"),          # kategori değil
    ({"x": {"field": "MaterialGroup"}, "facet": "Yok", "series": [{"id": "n", "fn": "count"}]}, "facet"),
])
def test_facet_validation(body, where):
    req = ChartRequest.model_validate(body)
    assert where in [p["field"] for p in chart_query.problems(builder(), req.x, req.split, req.series, facet=req.facet)]


def test_scatter_validation():
    fields = lambda **kw: [p["field"] for p in chart_query.scatter_problems(builder(), PointsRequest.model_validate(kw))]  # noqa: E731
    assert fields(x="SafetyStock", y="StockCoverageDays", color="MaterialLevel") == []
    assert fields(x="Code", y="StockCoverageDays") == ["x"]                                  # sayı alanı değil
    assert fields(x="SafetyStock", y="Yok") == ["y"]
    assert fields(x="SafetyStock", y="StockCoverageDays", color="SafetyStock") == ["color"]  # kategori değil


def test_points_summary_ranks_colours_and_flags_mixed_units():
    b = builder()
    req = PointsRequest(x="SafetyStock", y="StockCoverageDays", color="MaterialGroup")
    summary = [{"c": f"G{i:02d}", "u": "adet", "n": 20 - i} for i in range(14)] + [{"c": None, "u": "kg", "n": 1}]
    info = chart_query.points_summary(b, req, summary)
    keys = [v["key"] for v in info["colors"]["values"]]
    assert info["rows"] == sum(20 - i for i in range(14)) + 1
    assert keys == [f"G{i:02d}" for i in range(11)] + [chart_query.OTHER] and info["colors"]["other"]             # en büyük 11 + "Diğer"
    assert info["mixed_units"] == {"x": True, "y": False}                                                          # yalnız birimden ondalıklı eksen
    out = chart_query.assemble_points(req, info, [{"x": 1, "y": 2, "c": "G00", "name": "A"}, {"x": 3, "y": 4, "c": "G13", "name": "B"}])
    assert out["points"] == [[1.0, 2.0, 0, "A"], [3.0, 4.0, 11, "B"]] and out["shown"] == 2                        # kalan renk "Diğer" sırasında
    single = chart_query.points_summary(b, PointsRequest(x="SafetyStock", y="StockCoverageDays"), [{"u": "adet", "n": 5}])
    assert single["colors"] is None and single["mixed_units"] == {"x": False, "y": False}


def test_image_must_be_a_small_png():
    assert export_service.decode_image(None) is None
    assert export_service.decode_image(PNG64) == png()
    assert export_service.decode_image("data:image/png;base64," + PNG64) == png()
    for bad in ("düz yazı", base64.b64encode(b"GIF89a....").decode()):
        with pytest.raises(Exception) as exc:
            export_service.decode_image(bad)
        assert exc.value.code == "chart_image_invalid"
    big = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * (export_service.IMAGE_MAX_BYTES + 1)).decode()
    with pytest.raises(Exception) as exc:
        export_service.decode_image(big)
    assert exc.value.code == "chart_image_too_large"


# ------------------------------------------------------------------ veritabanıyla

N = [{"id": "n", "fn": "count"}]


@pytest.mark.db
def test_facets_add_up_to_the_unfaceted_chart(api):
    """Küçük grafiklerin toplamı bölünmemiş grafiktir; kırılımla birlikte de; yatay eksen ortaktır."""
    base = chart(api, ORDERS, x={"field": "RequestedDate", "bucket": "month"}, series=N)
    out = chart(api, ORDERS, x={"field": "RequestedDate", "bucket": "month"}, facet="CustomerCode", series=N)
    assert base["facets"] is None and out["facets"]["field"] == "CustomerCode" and len(out["facets"]["values"]) >= 2
    assert out["x"] == base["x"] and out["rows"] == base["rows"]
    grids = out["series"][0]["data"]
    assert len(grids) == len(out["facets"]["values"])
    assert [sum(g[0][j] for g in grids) for j in range(len(base["x"]["values"]))] == base["series"][0]["data"][0]
    both = chart(api, ORDERS, x={"field": "RequestedDate", "bucket": "month"}, facet="CustomerCode", split="MaterialCode", series=N)
    total = [sum(row[j] for g in both["series"][0]["data"] for row in g) for j in range(len(base["x"]["values"]))]
    assert total == base["series"][0]["data"][0]
    bad = api.post(f"{ORDERS}/chart", json={"x": {"field": "RequestedDate", "bucket": "month"}, "facet": "RequestedDate", "series": N})
    assert bad.status_code == 422


@pytest.mark.db
def test_selection_in_a_small_chart_matches_its_bar(api):
    """Küçük grafikteki bir çubuğun değeri, o çubuk seçilince tabloda kalan satır sayısıdır; "Diğer" küçük grafiği seçilemez."""
    out = chart(api, ORDERS, x={"field": "RequestedDate", "bucket": "month"}, facet="CustomerCode", series=N)
    sel = {"x": {"field": "RequestedDate", "bucket": "month"}, "facet": "CustomerCode"}
    checked = 0
    for f, grid in zip(out["facets"]["values"], out["series"][0]["data"]):
        for x, n in zip(out["x"]["values"], grid[0]):
            if n and f["key"] != chart_query.OTHER and x["key"]:
                assert _filtered(api, ORDERS, {**sel, "items": [{"x": x["key"], "f": f["key"]}]}) == n, (f, x)
                checked += 1
    assert checked >= 2
    first = out["facets"]["values"][0]["key"]
    whole = sum(out["series"][0]["data"][0][0])
    assert _filtered(api, ORDERS, {**sel, "items": [{"x": x["key"], "f": first} for x in out["x"]["values"] if x["key"]]}) == whole
    bad = api.post(f"{ORDERS}/query", json={"chart_selection": {**sel, "items": [{"x": out["x"]["values"][0]["key"], "f": chart_query.OTHER}]}})
    assert bad.status_code == 422


@pytest.mark.db
def test_points_are_the_rows_and_sampling_is_evenly_spaced(api):
    """Dağılım: satır başına nokta (iki değeri de dolu satırlar); sınır aşılınca tam `limit` nokta, eşit aralıkla ve listenin sırasıyla."""
    body = {"x": "OrderedQuantity", "y": "OpenQuantity"}
    r = api.post(f"{ORDERS}/chart/points", json=body)
    assert r.status_code == 200, r.text
    full = r.json()
    rows = [x for x in rows_of(api, ORDERS) if x["OrderedQuantity"] is not None and x["OpenQuantity"] is not None]
    assert full["rows"] == full["shown"] == len(full["points"]) == len(rows) > 12
    assert full["colors"] is None and all(p[2] == 0 for p in full["points"])
    assert sorted((p[0], p[1]) for p in full["points"]) == sorted((float(x["OrderedQuantity"]), float(x["OpenQuantity"])) for x in rows)
    assert full["label_field"] == "OrderNo" and sorted(p[3] for p in full["points"]) == sorted(x["OrderNo"] for x in rows)   # kayıt adı: sipariş no
    few = api.post(f"{ORDERS}/chart/points", json={**body, "limit": 10}).json()
    assert few["rows"] == len(rows) and few["shown"] == len(few["points"]) == 10                                 # tam sınır kadar
    at = []
    cursor = 0
    for p in few["points"]:                                                                                       # sıralı alt küme
        cursor = next(i for i in range(cursor, len(full["points"])) if full["points"][i] == p)
        at.append(cursor)
        cursor += 1
    gaps = {b - a for a, b in zip(at, at[1:])}
    step = len(rows) / 10
    assert gaps <= {int(step), int(step) + 1}, gaps                                                               # ilk 10 değil: eşit aralık
    coloured = api.post(f"{ORDERS}/chart/points", json={**body, "color": "CustomerCode"}).json()
    names = [v["key"] for v in coloured["colors"]["values"]]
    assert len(names) >= 2 and all(0 <= p[2] < len(names) for p in coloured["points"])
    counts: dict = {}
    for x in rows:
        counts[x["CustomerCode"]] = counts.get(x["CustomerCode"], 0) + 1
    assert [counts[k] for k in names] == sorted(counts.values(), reverse=True)                                    # renkler satır sayısına göre
    filtered = api.post(f"{ORDERS}/chart/points", json={**body, "filters": [{"field": "CustomerCode", "op": "in", "values": [names[0]]}]}).json()
    assert filtered["rows"] == counts[names[0]]                                                                   # tablonun filtresiyle
    assert api.post(f"{ORDERS}/chart/points", json={"x": "CustomerCode", "y": "OpenQuantity"}).status_code == 422


@pytest.mark.db
def test_points_are_not_drawn_when_an_axis_has_mixed_units(api):
    """Sentetik stokta birden çok birim var (test_chart_api): miktar ekseni karışık, nokta dönmez; tek malzemeye süzülünce çizilir."""
    out = api.post(f"{STOCK}/chart/points", json={"x": "Quantity", "y": "Quantity"}).json()
    assert out["mixed_units"] == {"x": True, "y": True} and out["points"] == [] and out["shown"] == 0 and out["rows"] > 0
    code = rows_of(api, STOCK)[0]["MaterialCode"]
    one = api.post(f"{STOCK}/chart/points", json={"x": "Quantity", "y": "Quantity", "filters": [{"field": "MaterialCode", "op": "in", "values": [code]}]}).json()
    assert one["mixed_units"] == {"x": False, "y": False} and one["shown"] == one["rows"] >= 1 and one["label_field"] == "MaterialCode"


def _audits(db_engine, user_id):
    with db_engine.connect() as c:
        return c.execute(text("SELECT ObjectType, ObjectKey, NewValue FROM adm.AuditLog WHERE UserId = :u AND Action = N'Dışa aktarım' ORDER BY Id"),
                         {"u": user_id}).all()


@pytest.fixture
def exporter(db_engine):
    with db_engine.begin() as c:
        delete_users(c, [ensure_user(c, "grafik.aktaran", "End user", "Grafik Aktaran")])  # yarıda kalmış koşunun izleri kalmasın
        uid = ensure_user(c, "grafik.aktaran", "End user", "Grafik Aktaran")
    yield uid
    with db_engine.begin() as c:
        delete_users(c, [uid])


@pytest.mark.db
def test_chart_excel_has_data_info_and_image_and_is_audited(api, exporter, db_engine):
    """Grafiğin verisi Excel'e: Veri (toplanmış veri), Bilgi ve Grafik sayfaları; End user da aktarır; iz "Dışa aktarım"."""
    req = {"x": {"field": "RequestedDate", "bucket": "month"}, "split": "CustomerCode", "series": [{"id": "q", "field": "OpenQuantity", "fn": "sum"}, {"id": "n", "fn": "count"}]}
    data = chart(api, ORDERS, **req)
    r = api.post(f"{ORDERS}/chart/export", headers=auth(exporter), json={"kind": "xy", "chart": req, "image": PNG64, "title": "Açık miktar"})
    assert r.status_code == 200, r.text
    name = r.headers["content-disposition"].split("''")[1]
    assert "_grafik_" in name and name.endswith(".xlsx")
    wb = load_workbook(io.BytesIO(r.content))
    assert wb.sheetnames == ["Veri", "Bilgi", "Grafik"] and images(r.content) == [png()]
    rows = [list(x) for x in wb["Veri"].iter_rows(values_only=True)]
    parts = [v["key"] for v in data["split"]["values"]]
    drawn = [s for s in data["series"] if not s["mixed_units"]]
    assert rows[0][0].endswith("(Ay)") and len(rows[0]) == 1 + len(parts) * len(drawn)
    assert len(rows) - 1 == len(data["x"]["values"])
    first = next(i for i, v in enumerate(data["x"]["values"]) if v["key"])
    assert rows[1 + first][0].date() == date.fromisoformat(data["x"]["values"][first]["key"])                    # dönem tarih olarak
    count = next(s for s in data["series"] if s["id"] == "n")
    assert [rows[1 + j][-len(parts):] for j in range(len(rows) - 1)] == [[count["data"][p][j] for p in range(len(parts))] for j in range(len(rows) - 1)]
    info = {k: v for k, v in wb["Bilgi"].iter_rows(min_row=2, values_only=True)}
    assert info["Grafik"] == "Çubuk ve çizgi · Açık miktar" and info["Kırılım"] and info["Filtreler"] == "yok" and "Say" in info["Seriler"]
    [(obj, key, value)] = _audits(db_engine, exporter)
    details = json.loads(value)
    assert (obj, key) == ("transaction-sales-order", name)
    assert (details["chart"], details["format"], details["chart_image"], details["rows"]) == ("Çubuk ve çizgi", "xlsx", True, len(rows) - 1)
    # küçük grafiklerle: başta küçük grafiğin kolonu
    faceted = {"x": {"field": "RequestedDate", "bucket": "month"}, "facet": "CustomerCode", "series": N}
    wb = load_workbook(io.BytesIO(api.post(f"{ORDERS}/chart/export", headers=auth(exporter), json={"kind": "xy", "chart": faceted}).content))
    assert wb.sheetnames == ["Veri", "Bilgi"]                                                                     # görsel verilmediyse Grafik sayfası yok
    rows = [list(x) for x in wb["Veri"].iter_rows(values_only=True)]
    out = chart(api, ORDERS, **faceted)
    assert len(rows) - 1 == len(out["facets"]["values"]) * len(out["x"]["values"]) and sum(x[2] for x in rows[1:]) == out["rows"]
    assert rows[1][0] == out["facets"]["values"][0]["key"]


@pytest.mark.db
def test_scatter_excel_and_png_log(api, exporter, db_engine):
    body = {"x": "OrderedQuantity", "y": "OpenQuantity", "color": "CustomerCode"}
    points = api.post(f"{ORDERS}/chart/points", json=body).json()
    r = api.post(f"{ORDERS}/chart/export", headers=auth(exporter), json={"kind": "scatter", "points": body})
    assert r.status_code == 200, r.text
    wb = load_workbook(io.BytesIO(r.content))
    rows = [list(x) for x in wb["Veri"].iter_rows(values_only=True)]
    assert len(rows) - 1 == points["shown"] and len(rows[0]) == 4
    assert [(x[1], x[2]) for x in rows[1:]] == [(p[0], p[1]) for p in points["points"]]
    info = {k: v for k, v in wb["Bilgi"].iter_rows(min_row=2, values_only=True)}
    assert info["Grafik"] == "Dağılım" and "nokta" in info["Noktalar"]
    log = api.post(f"{ORDERS}/chart/export-log", headers=auth(exporter), json={"kind": "pie"})
    assert log.status_code == 200 and log.json()["file_name"].endswith(".png") and "_grafik_" in log.json()["file_name"]
    found = _audits(db_engine, exporter)
    assert [json.loads(v)["format"] for _, _, v in found] == ["xlsx", "png"] and found[1][1] == log.json()["file_name"]
    assert json.loads(found[1][2])["chart"] == "Pasta"
    assert api.post(f"{ORDERS}/chart/export", headers=auth(exporter), json={"kind": "scatter"}).status_code == 422       # istek eksik
    assert api.post(f"{ORDERS}/chart/export", headers=auth(exporter), json={"kind": "xy", "chart": {"x": {"field": "Yok"}, "series": N}}).status_code == 422
    bad = api.post(f"{ORDERS}/chart/export", headers=auth(exporter), json={"kind": "scatter", "points": body, "image": "bozuk"})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "chart_image_invalid"
    assert len(_audits(db_engine, exporter)) == 2                                                                 # başarısız aktarım iz bırakmaz


@pytest.mark.db
def test_table_export_can_carry_the_chart_image(api, exporter, db_engine):
    """Tablonun Excel'ine "Grafiği ekle": dosyada "Grafik" sayfası; izde chart_image; bozuk görsel 422."""
    body = {"fields": ["Code", "Name"], "chart_image": PNG64}
    r = api.post(f"{MAT}/export", headers=auth(exporter), json=body)
    assert r.status_code == 200, r.text
    wb = load_workbook(io.BytesIO(r.content))
    assert wb.sheetnames == ["Veri", "Bilgi", "Grafik"] and images(r.content) == [png()]
    plain = load_workbook(io.BytesIO(api.post(f"{MAT}/export", headers=auth(exporter), json={"fields": ["Code", "Name"]}).content))
    assert plain.sheetnames == ["Veri", "Bilgi"]
    assert [json.loads(v)["chart_image"] for _, _, v in _audits(db_engine, exporter)] == [True, False]
    bad = api.post(f"{MAT}/export", headers=auth(exporter), json={**body, "chart_image": base64.b64encode(b"png degil").decode()})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "chart_image_invalid"


def _view(api, name, chart_def):
    body = {"name": name, "is_shared": False, "definition": {"v": 1, "columns": [{"field": "Code"}], "chart": chart_def}}
    return api.post(f"{MAT}/views", json=body)


@pytest.mark.db
def test_view_keeps_kind_facet_pie_and_scatter(api, db_engine):
    """Görünümde yeni alanlar saklanır; eski kayıt (anahtarsız) çubuk ve çizgi okunur; pasta tarih ekseninde ve eksik dağılım kaydedilemez."""
    base = {"x": {"field": "MaterialLevel"}, "series": [{"id": "s1", "fn": "count"}]}
    made = []
    try:
        r = _view(api, "grafik tür pasta", {**base, "kind": "donut", "facet": "MaterialGroup", "facet_scale": "own", "pie": {"label": "value"}})
        assert r.status_code == 201, r.text
        made.append(r.json()["id"])
        saved = r.json()["definition"]["chart"]
        assert (saved["kind"], saved["facet"], saved["facet_scale"], saved["pie"], saved["scatter"]) == ("donut", "MaterialGroup", "own", {"label": "value"}, None)
        r = _view(api, "grafik tür dağılım", {**base, "kind": "scatter", "scatter": {"x": "SafetyStock", "y": "StockCoverageDays", "color": "MaterialLevel", "point_color": "#4F5BD5"}})
        assert r.status_code == 201, r.text
        made.append(r.json()["id"])
        assert r.json()["definition"]["chart"]["scatter"] == {"x": "SafetyStock", "y": "StockCoverageDays", "color": "MaterialLevel", "point_color": "#4F5BD5"}
        r = _view(api, "grafik tür eski", base)
        assert r.status_code == 201, r.text
        made.append(r.json()["id"])
        old = r.json()["definition"]["chart"]
        assert (old["kind"], old["facet"], old["facet_scale"], old["pie"], old["scatter"]) == ("xy", None, "shared", {"label": "percent"}, None)
        for bad, where in [
            ({"x": {"field": "UpdatedAt", "bucket": "month"}, "series": base["series"], "kind": "pie"}, "definition.chart.kind"),
            ({**base, "kind": "scatter"}, "definition.chart.scatter"),
            ({**base, "kind": "scatter", "scatter": {"x": "Code", "y": "StockCoverageDays"}}, "definition.chart.scatter.x"),
            ({**base, "facet": "MaterialLevel"}, "definition.chart.facet"),
        ]:
            r = _view(api, "grafik tür bozuk", bad)
            assert r.status_code == 422 and where in [d["field"] for d in r.json()["error"]["details"]], (where, r.text)
    finally:
        with db_engine.begin() as c:
            c.execute(text("DELETE FROM adm.TableView WHERE Name LIKE N'grafik tür %'"))
