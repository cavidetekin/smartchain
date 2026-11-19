"""Pivot, ikinci parça (K-183, geliştirme 7.7b): hesaplanan değer (toplamlardan), değerin kuralları ve "Toplamlara da uygula", Excel'e pivot
şekliyle aktarım, alanın varsayılan hesaplaması. Sentetik v0'da; kendi yazdığını geri alır.

Sabitlenenler: hesaplanan değer her düzeyde o hücrenin toplamlarından hesaplanır (kayıtların oranlarının ortalaması değildir) ve aynı veride
satırlardan ortalama ile yan yana farklı sonuç verir; kural hesaplanmış hücre değerine bakar, ilk tutan kazanır, toplamlar yalnız istenirse;
Excel dosyası ekrandaki şekli taşır (katlı başlık, toplamlar, grup çizgileri, kural rengi, tarih ve yüzde biçimi) ve iz bırakır.
"""
import dataclasses
import io
import json
import re
from datetime import date, datetime

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app.api.lists import definition
from app.api.lists import pivot as pivot_query
from app.api.lists.materials import MATERIALS
from app.api.main import create_app
from app.api.permissions import END_USER, KEY_USER
from app.api.services import export as export_service

from auth_helpers import auth, delete_users, ensure_user

pytestmark = pytest.mark.db

ORDERS = "/api/transaction-sales-order"
MAT = "/api/materials"
ALL = {"rows": True, "columns": True, "subtotals": True}
TEST_ROWS = [{"field": "MaterialLevel", "op": "in", "values": ["PIVOT-CALC"]}]
FILL = "#f7dcd5"


@pytest.fixture(scope="module")
def people(db_engine):
    with db_engine.begin() as c:
        return {KEY_USER: ensure_user(c, "pytest.pc.key", KEY_USER), END_USER: ensure_user(c, "pytest.pc.end", END_USER)}


@pytest.fixture(scope="module")
def api(db_engine, people):
    client = TestClient(create_app(), raise_server_exceptions=False)
    client.headers.update(auth(people[KEY_USER]))
    yield client
    with db_engine.begin() as c:
        c.execute(sa.text("DELETE FROM adm.TableView WHERE Name LIKE N'pytest hesap%'"))


@pytest.fixture(scope="module")
def ratio_rows(db_engine):
    """6. maddenin örneği (K-183): kapasite 100, üretim 90 (%90); kapasite 300, üretim 150 (%50), aynı grupta. Ayrı grupta kapasite 50,
    üretim 5 (%10). Üçüncü grupta kapasite 0, üretim 5 (bölen sıfır). Kapasite SafetyStock'ta, üretim MaxStock'ta, oran ScrapRatio'da durur."""
    rows = [("PC-A", 100, 90, 0.9), ("PC-A", 300, 150, 0.5), ("PC-B", 50, 5, 0.1), ("PC-C", 0, 5, 0.2)]
    with db_engine.begin() as c:
        c.execute(sa.text("DELETE FROM core.Material WHERE Id BETWEEN 9910001 AND 9910009"))
        cols = [x["name"] for x in sa.inspect(c).get_columns("Material", schema="core")]
        fixed = ("Id", "Code", "BusinessKey", "MaterialGroup", "MaterialLevel", "SafetyStock", "MaxStock", "ScrapRatio")
        keep = [x for x in cols if x not in fixed]
        for i, (group, capacity, produced, ratio) in enumerate(rows, 1):
            c.execute(sa.text(f"INSERT INTO core.Material ({', '.join(keep)}, {', '.join(fixed)}) "
                              f"SELECT TOP 1 {', '.join(keep)}, :id, :code, :code, :g, N'PIVOT-CALC', :w, :p, :r FROM core.Material "
                              "WHERE VersionTo IS NULL AND BaseUom = N'ADET' ORDER BY Id"),
                      {"id": 9_910_000 + i, "code": f"PC-{i}", "g": group, "w": capacity, "p": produced, "r": ratio})
    yield
    with db_engine.begin() as c:
        c.execute(sa.text("DELETE FROM core.Material WHERE Id BETWEEN 9910001 AND 9910009"))


def pivot(api, url, **body):
    r = api.post(url + "/pivot", json={"limit": 100, **body})
    assert r.status_code == 200, r.text
    return r.json()


def num(cell):
    return cell["v"] if isinstance(cell, dict) and "v" in cell else cell


CAP = {"id": "cap", "field": "SafetyStock", "fn": "sum"}
PROD = {"id": "prod", "field": "MaxStock", "fn": "sum"}


def calc(op="div", **extra):
    return {"id": "oran", "kind": "calc", "a": "prod", "op": op, "b": "cap", **extra}


def by_key(out):
    return {tuple(r["key"]): [num(c[0]) for c in r["cells"]] for r in out["rows"]}


def test_calculated_value_comes_from_totals_at_every_level(api, ratio_rows):
    """Aynı oran üç yolla yan yana: satırlardan ortalama, ağırlıklı ortalama ve toplamlardan; ara toplam ve genel toplamda da toplamlardan."""
    values = [{"id": "avg", "field": "ScrapRatio", "fn": "avg"}, {"id": "wavg", "field": "ScrapRatio", "fn": "wavg", "weight": "SafetyStock"},
              {"id": "other", "field": "ScrapRatio", "fn": "wavg", "weight": "MaxStock"}, CAP, PROD, calc(percent=True)]
    out = pivot(api, MAT, rows=[{"field": "MaterialGroup"}, {"field": "Code"}], values=values, totals=ALL, filters=TEST_ROWS)
    got = by_key(out)
    assert got[("PC-A", "PC-1")][5] == pytest.approx(0.9) and got[("PC-A", "PC-2")][5] == pytest.approx(0.5)      # yaprakta kaydın kendi oranı
    # ara toplam: ortalama (0,9 + 0,5) / 2 = 0,70; kapasiteyle ağırlıklı (90 + 150) / 400 = 0,60; toplamlardan 240 / 400 = 0,60
    assert got[("PC-A",)] == pytest.approx([0.70, 0.60, 156 / 240, 400, 240, 0.60])
    assert got[("PC-A",)][0] != pytest.approx(got[("PC-A",)][5])                                                 # ortalama ile toplamlardan ayrışır
    assert got[("PC-A",)][2] != pytest.approx(got[("PC-A",)][5])                                                 # ağırlık başka alan olunca ağırlıklı ortalama da ayrışır
    assert got[("PC-B",)][5] == pytest.approx(0.1)
    assert got[("PC-C",)][5] is None and got[("PC-C", "PC-4")][5] is None and got[("PC-C",)][1] is None           # bölen 0: hücre boş
    # genel toplam: 250 / 450 (ara toplam oranlarının ortalaması değil)
    assert got[()][3:] == pytest.approx([450, 250, 250 / 450])
    assert got[()][5] != pytest.approx((0.60 + 0.10) / 2)
    info = {v["id"]: v for v in out["values"]}
    assert info["oran"]["fn"] == "calc" and info["oran"]["percent"] is True and info["oran"]["field"] is None and info["oran"]["decimals"] == 2


def test_operations_sort_and_columns(api, ratio_rows):
    for op, want in (("mul", 240 * 400), ("add", 640), ("sub", -160)):
        out = pivot(api, MAT, rows=[{"field": "MaterialGroup"}], values=[CAP, PROD, calc(op)], filters=TEST_ROWS)
        assert by_key(out)[("PC-A",)][2] == pytest.approx(want) and out["values"][2]["percent"] is False
    # hesaplanan değere göre sıralama: her düzeyde kendi içinde; boş sonda
    out = pivot(api, MAT, rows=[{"field": "MaterialGroup"}, {"field": "Code"}], values=[CAP, PROD, calc()], filters=TEST_ROWS,
                sort={"by": "oran", "dir": "desc"})
    assert [r["key"] for r in out["rows"]][:4] == [["PC-A", "PC-1"], ["PC-A", "PC-2"], ["PC-B", "PC-3"], ["PC-C", "PC-4"]]
    up = pivot(api, MAT, rows=[{"field": "MaterialGroup"}, {"field": "Code"}], values=[CAP, PROD, calc()], filters=TEST_ROWS, sort={"by": "oran", "dir": "asc"})
    assert [r["key"] for r in up["rows"]][:3] == [["PC-B", "PC-3"], ["PC-A", "PC-2"], ["PC-A", "PC-1"]]
    # sütun ekseninde: her sütun hücresi ve "Toplam" sütunu kendi toplamlarından
    wide = pivot(api, MAT, rows=[{"field": "MaterialLevel"}], columns=[{"field": "MaterialGroup"}], values=[CAP, PROD, calc()], totals=ALL, filters=TEST_ROWS)
    keys = [tuple(c["key"]) for c in wide["columns"]]
    cells = [num(c) for c in wide["rows"][0]["cells"][2]]
    assert cells[keys.index(("PC-A",))] == pytest.approx(0.6) and cells[keys.index(("PC-C",))] is None and cells[keys.index(())] == pytest.approx(250 / 450)


def test_calculated_value_is_empty_when_an_operand_has_mixed_units(api):
    out = pivot(api, "/api/master-bom", rows=[{"field": "LocationCode"}],
                values=[{"id": "q", "field": "Quantity", "fn": "sum"}, {"id": "n", "fn": "count"}, {"id": "x", "kind": "calc", "a": "q", "op": "div", "b": "n"},
                        {"id": "y", "kind": "calc", "a": "n", "op": "add", "b": "n"}])
    cells = out["rows"][0]["cells"]
    assert cells[0][0] == {"mixed": True} and cells[2][0] is None and num(cells[3][0]) == 2 * num(cells[1][0])


def rule(rid, op, fill=FILL, **cond):
    return {"id": rid, "enabled": True, "condition": {"op": op, **cond}, "format": {"fill": fill}}


def test_rules_look_at_the_computed_cell_and_totals_only_on_request(api, ratio_rows):
    rules = [rule("k1", "lt", value=0.5), rule("k2", "empty", fill="#d9a521")]
    body = dict(rows=[{"field": "MaterialGroup"}, {"field": "Code"}], totals=ALL, filters=TEST_ROWS)
    out = pivot(api, MAT, values=[CAP, PROD, calc(rules=rules)], **body)
    hits = {tuple(r["key"]): r.get("formats") for r in out["rows"]}
    assert hits[("PC-B", "PC-3")] == {"2": [0]}                      # %10 < %50: ilk kural
    assert hits[("PC-C", "PC-4")] == {"2": [1]}                      # boş hücre: ikinci kural
    assert hits[("PC-A", "PC-1")] is None and hits[("PC-A", "PC-2")] is None      # %50, "küçük" değildir
    assert all(r.get("formats") is None for r in out["rows"] if r["total"])      # toplam satırları: varsayılan kapalı
    out = pivot(api, MAT, values=[CAP, PROD, calc(rules=rules, rules_on_totals=True)], **body)
    hits = {tuple(r["key"]): r.get("formats") for r in out["rows"]}
    assert hits[("PC-B",)] == {"2": [0]} and hits[("PC-C",)] == {"2": [1]} and hits[("PC-A",)] is None
    assert hits[()] is None                                          # genel toplam 250 / 450 = %55,6
    # ilk tutan kazanır; alan değerinde de kural; "Arası" ve "Her zaman"
    out = pivot(api, MAT, values=[{**CAP, "rules": [rule("a", "between", min=100, max=300), rule("b", "always", fill="#002060")]}, PROD], **body)
    hits = {tuple(r["key"]): r.get("formats") for r in out["rows"] if not r["total"]}
    assert hits[("PC-A", "PC-1")] == {"0": [0]} and hits[("PC-A", "PC-2")] == {"0": [0]} and hits[("PC-B", "PC-3")] == {"0": [1]}
    # toplam sütunu: yalnız "Toplamlara da uygula" açıksa
    wide = dict(rows=[{"field": "MaterialLevel"}], columns=[{"field": "MaterialGroup"}], totals=ALL, filters=TEST_ROWS)
    out = pivot(api, MAT, values=[{**CAP, "rules": [rule("a", "gt", value=10)]}], **wide)
    keys = [tuple(c["key"]) for c in out["columns"]]
    leaf = next(r for r in out["rows"] if not r["total"])
    assert leaf["formats"]["0"][keys.index(("PC-A",))] == 0 and leaf["formats"]["0"][keys.index(())] is None and leaf["formats"]["0"][keys.index(("PC-C",))] is None
    out = pivot(api, MAT, values=[{**CAP, "rules": [rule("a", "gt", value=10)], "rules_on_totals": True}], **wide)
    assert all(r["formats"]["0"][keys.index(())] == 0 for r in out["rows"])


@pytest.mark.parametrize("values, where", [
    ([CAP, calc()], "values.1.a"),                                                                                # işlenen pivotta yok
    ([CAP, PROD, calc(), {"id": "z", "kind": "calc", "a": "oran", "op": "add", "b": "cap"}], "values.3.a"),        # hesaplanan değer işlenen olamaz
    ([CAP, PROD, {"id": "oran", "kind": "calc", "a": "prod", "b": "cap"}], "values.2.op"),                         # işlem seçilmemiş
    ([CAP, {"id": "d", "field": "UpdatedAt", "fn": "max"}, {"id": "z", "kind": "calc", "a": "cap", "op": "sub", "b": "d"}], "values.2.b"),   # tarih sonucu
    ([{**CAP, "rules": [rule("a", "contains", value="x")]}], "values.0.rules.0.condition.op"),                   # yalnız sayı koşulları
    ([{**CAP, "rules": [{"id": "a", "enabled": True, "condition": {"op": "gt", "field_ref": "MaxStock"}, "format": {"fill": FILL}}]}], "values.0.rules.0.condition.op"),
    ([{**CAP, "rules": [rule(f"k{i}", "gt", value=i) for i in range(6)]}], "rules"),                             # en çok 5 kural
])
def test_validation(api, values, where):
    r = api.post(MAT + "/pivot", json={"rows": [{"field": "MaterialGroup"}], "values": values, "limit": 10})
    assert r.status_code == 422 and where in r.text, r.text


@pytest.fixture
def exporter(db_engine):
    with db_engine.begin() as c:
        delete_users(c, [ensure_user(c, "pivot.aktaran", END_USER, "Pivot Aktaran")])   # yarıda kalmış koşunun izleri kalmasın
        uid = ensure_user(c, "pivot.aktaran", END_USER, "Pivot Aktaran")
    yield uid
    with db_engine.begin() as c:
        delete_users(c, [uid])


def audits(db_engine, user_id):
    with db_engine.connect() as c:
        return c.execute(sa.text("SELECT ObjectType, ObjectKey, NewValue FROM adm.AuditLog WHERE UserId = :u AND Action = N'Dışa aktarım' ORDER BY Id"),
                         {"u": user_id}).all()


def rgb(color):
    return (color.rgb or "")[-6:].lower() if color is not None and isinstance(color.rgb, str) else ""


def test_excel_has_the_shape_on_screen_and_is_audited(api, exporter, db_engine):
    """Müşteri › Malzeme × ay; dört değer (miktar, sipariş miktarı, en erken tarih, toplamlardan oran) ve bütün toplamlar. End user aktarır (fonksiyon 86)."""
    values = [{"id": "q", "field": "OpenQuantity", "fn": "sum"}, {"id": "o", "field": "OrderedQuantity", "fn": "sum"}, {"id": "d", "field": "RequestedDate", "fn": "min"},
              {"id": "x", "kind": "calc", "a": "q", "op": "div", "b": "o", "percent": True, "rules": [rule("k1", "always")]}]
    body = {"rows": [{"field": "CustomerCode"}, {"field": "MaterialCode"}], "columns": [{"field": "RequestedDate", "bucket": "month"}], "values": values, "totals": ALL}
    names = {"q": "Açık", "o": "Sipariş miktarı · Toplam", "d": "İstek tarihi · En erken", "x": "Açık oranı · Toplamlardan"}
    r = api.post(ORDERS + "/pivot/export", headers=auth(exporter), json={**body, "values_on": "columns", "names": names, "title": "Satış siparişi"})
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/vnd.openxmlformats") and "pivot" in r.headers["content-disposition"]
    wb = load_workbook(io.BytesIO(r.content))
    assert wb.sheetnames == ["Pivot", "Bilgi"]
    ws = wb["Pivot"]
    shown = pivot(api, ORDERS, **body)
    months = [c for c in shown["columns"] if not c["total"]]
    # başlık: üstte dönemler (dört değer boyunca birleşik) ve "Toplam"; altta satır alanları ve değer adları; ikisi de dondurulmuş
    assert ws.freeze_panes == "C3"
    merged = {str(m) for m in ws.merged_cells.ranges if m.min_row <= 2}                           # başlıktaki birleşmeler (satır hücreleri ayrı testte, K-186)
    assert {"A1:B1", "C1:F1"} <= merged and len(merged) == len(months) + 2
    assert re.fullmatch(r"\S{3} \d{4}", ws["C1"].value) and ws.cell(1, 3 + 4 * len(months)).value == "Toplam"
    assert [ws.cell(2, i).value for i in range(1, 7)] == ["Müşteri", "Malzeme", "Açık", "Sipariş miktarı · Toplam", "İstek tarihi · En erken", "Açık oranı · Toplamlardan"]
    assert ws["C1"].font.bold and ws["C2"].font.bold
    # satırlar ekrandaki sırayla ve sayıyla; ilk hücre ekrandaki değer
    assert ws.max_row == 2 + shown["row_count"] and ws.max_column == 2 + 4 * len(shown["columns"])
    first = shown["rows"][0]
    assert ws["A3"].value == first["key"][0] and ws["B3"].value == first["key"][1]
    data = list(ws.iter_rows(min_row=3))
    k = next(i for i, c in enumerate(first["cells"][0]) if c is not None)
    assert data[0][2 + 4 * k].value == pytest.approx(num(first["cells"][0][k]))
    # toplamlar kalın: ara toplam satırı, genel toplam satırı ve "Toplam" sütunu
    labels = [(row[0].value, row[1].value) for row in data]
    assert labels[-1][0] == "Genel toplam" and data[-1][0].font.bold and data[-1][2 + 4 * k].font.bold is not None
    sub = next(i for i, (a, _b) in enumerate(labels) if a and a.endswith(" toplamı"))
    assert data[sub][0].font.bold and all(c.font.bold for c in data[sub] if c.value is not None)
    total_at = 2 + 4 * (len(shown["columns"]) - 1)
    assert all(row[total_at].font.bold for row in data if row[total_at].value is not None)
    plain = next(c for row in data[:sub] for c in row[2:total_at] if isinstance(c.value, (int, float)))
    assert not plain.font.bold
    # en dıştaki sütun gruplarının solunda dikey çizgi: ikinci gruptan başlayarak her grubun ilk değerinde (başlıkta ve hücrelerde), ötekilerde yok
    assert data[0][2].border.left.style != "medium"                                                # ilk grup satır başlıklarına bitişik: ekrandaki gibi çizgisiz
    for start in range(6, 2 + 4 * len(shown["columns"]), 4):
        assert data[0][start].border.left.style == "medium" and ws.cell(2, start + 1).border.left.style == "medium"
        assert data[0][start + 1].border.left.style != "medium"
        top = ws.cell(1, start + 1)
        assert top.border.left.style == "medium" and rgb(top.border.left.color) != rgb(top.fill.fgColor)       # başlıktaki çizgi zeminde görünür
    # tarih değeri Excel'de tarih; yüzde biçimi; sayı biçimi
    dates = [row[4 + 4 * i] for row in data for i in range(len(shown["columns"])) if row[4 + 4 * i].value is not None]
    assert dates and all(isinstance(c.value, (datetime, date)) and c.number_format == "dd.mm.yyyy" for c in dates)
    ratios = [(row, row[5 + 4 * i], i) for row in data for i in range(len(shown["columns"])) if row[5 + 4 * i].value is not None]
    assert ratios and all(c.number_format == "%#,##0.00" and 0 <= c.value <= 1 for _row, c, _i in ratios)
    assert data[0][2 + 4 * k].number_format.startswith("#,##0")
    # kural dolgusu: yalnız toplam olmayan hücrelerde (Toplamlara da uygula kapalı)
    total_rows = {id(row) for i, row in enumerate(data) if shown["rows"][i]["total"]}
    for row, c, i in ratios:
        on_total = id(row) in total_rows or i == len(shown["columns"]) - 1
        assert (rgb(c.fill.fgColor) == FILL[1:]) is (not on_total), (c.coordinate, rgb(c.fill.fgColor))
    # Bilgi sayfası
    info = {row[0].value: row[1].value for row in wb["Bilgi"].iter_rows() if row[0].value}
    assert info["Liste"] == "Satış siparişi" and info["Satırlar"] == "Müşteri › Malzeme" and info["Sütunlar"] == "İstek tarihi (Ay)"
    assert "Açık oranı · Toplamlardan = Açık ÷ Sipariş miktarı · Toplam (toplamlardan)" in info["Değerler"]
    assert info["Değerlerin yeri"] == "Sütunlarda" and info["Toplamlar"] == "Satır toplamı, Sütun toplamı, Ara toplamlar" and info["Dışa aktaran"] == "Pivot Aktaran"
    # iz
    [(obj, key, value)] = audits(db_engine, exporter)
    detail = json.loads(value)
    assert detail["pivot"] is True and detail["format"] == "xlsx" and detail["rows"] == shown["row_count"] and detail["size"] == len(r.content)
    assert key.endswith(".xlsx") and "pivot" in key and obj

    # "Toplamlara da uygula" ve değerler satırlarda: toplamlar da boyanır; değer adı satırda, dönemler yan yana
    on = [*values[:3], {**values[3], "rules_on_totals": True}]
    r = api.post(ORDERS + "/pivot/export", headers=auth(exporter), json={**body, "values": on, "values_on": "rows", "names": names})
    assert r.status_code == 200, r.text
    ws = load_workbook(io.BytesIO(r.content))["Pivot"]
    assert ws.freeze_panes == "D3" and [ws.cell(2, i).value for i in range(1, 4)] == ["Müşteri", "Malzeme", "Değer"]
    assert re.fullmatch(r"\S{3} \d{4}", ws["D1"].value) and ws.max_column == 3 + len(shown["columns"])           # dönemler yan yana, her biri tek sütun
    assert ws.max_row == 2 + 4 * shown["row_count"] and [ws.cell(i, 3).value for i in range(3, 7)] == list(names.values())
    last = list(ws.iter_rows(min_row=ws.max_row))[0]
    assert rgb(last[-1].fill.fgColor) == FILL[1:] and last[-1].font.bold                                       # genel toplam × Toplam sütunu
    assert len(audits(db_engine, exporter)) == 2


def test_export_limits_filters_and_errors(api, exporter, db_engine, monkeypatch, ratio_rows):
    body = {"rows": [{"field": "MaterialGroup"}], "values": [CAP, PROD, calc(percent=True)], "filters": TEST_ROWS, "totals": {"rows": True, "columns": False, "subtotals": False},
            "values_on": "columns", "names": {}}
    r = api.post(MAT + "/pivot/export", headers=auth(exporter), json=body)
    assert r.status_code == 200, r.text
    wb = load_workbook(io.BytesIO(r.content))
    rows = [[c.value for c in row] for row in wb["Pivot"].iter_rows()]
    assert rows[0][0] == "Malzeme grubu" and rows[0][3] == "Hesaplanan değer · Toplamlardan"      # ad gönderilmezse sunucunun adı
    assert rows[1] == ["PC-A", 400, 240, pytest.approx(0.6)] and rows[3] == ["PC-C", 0, 5, None] and rows[4] == ["Genel toplam", 450, 250, pytest.approx(250 / 450)]
    assert "PIVOT-CALC" in {row[0].value: row[1].value for row in wb["Bilgi"].iter_rows() if row[0].value}["Filtreler"]
    monkeypatch.setattr(export_service, "PIVOT_EXPORT_MAX_CELLS", 5)
    big = api.post(MAT + "/pivot/export", headers=auth(exporter), json=body)
    assert big.status_code == 422 and big.json()["error"]["code"] == "export_too_large"
    bad = api.post(MAT + "/pivot/export", headers=auth(exporter), json={**body, "values": [CAP, calc()]})
    assert bad.status_code == 422
    assert len(audits(db_engine, exporter)) == 1                                                  # başarısız aktarım iz bırakmaz


def test_calculated_values_and_rules_are_saved_with_the_view(api, db_engine):
    base = {"v": 1, "columns": [{"field": "OrderNo"}], "pinned": 0, "sort": [], "filters": [], "group_by": []}
    values = [{"id": "d1", "field": "OpenQuantity", "fn": "sum", "rules": [rule("k1", "gt", value=100)]}, {"id": "d2", "field": "OrderedQuantity", "fn": "sum"},
              {"id": "d3", "kind": "calc", "name": "Açık oranı", "a": "d1", "op": "div", "b": "d2", "percent": True, "decimals": 1,
               "rules": [rule("k1", "lt", value=0.5)], "rules_on_totals": True}]
    definition_ = {"v": 1, "open": True, "rows": [{"field": "CustomerCode"}], "columns": [], "values": values, "values_on": "columns",
                   "totals": {"rows": True, "columns": False, "subtotals": False}, "sort": {"by": "d3", "dir": "desc"}}
    saved = api.post(ORDERS + "/views", json={"name": "pytest hesap", "is_shared": False, "definition": {**base, "pivot": definition_}})
    assert saved.status_code == 201, saved.text
    got = {v["name"]: v for v in api.get(ORDERS + "/views").json()["views"]}["pytest hesap"]["definition"]["pivot"]
    assert got["values"][2] == values[2] and got["values"][0]["rules"] == values[0]["rules"] and got["sort"] == {"by": "d3", "dir": "desc"}
    assert "kind" not in got["values"][0] and "rules_on_totals" not in got["values"][0]            # varsayılanlar saklanmaz
    for broken in ({**values[2], "a": "yok"}, {**values[2], "rules": [rule("k1", "contains", value="x")]}):
        bad = api.post(ORDERS + "/views", json={"name": "pytest hesap bozuk", "is_shared": False, "definition": {**base, "pivot": {**definition_, "values": [*values[:2], broken]}}})
        assert bad.status_code == 422 and "definition.pivot.values.2" in bad.text, bad.text
    with db_engine.begin() as c:  # işlenenin alanı sonradan kalkmış gibi: hesaplanan değer de gider, sıralama ada döner
        gone = {**definition_, "values": [values[0], {**values[1], "field": "Gone"}, values[2]]}
        c.execute(sa.text("UPDATE adm.TableView SET Definition = :d WHERE Id = :i"), {"d": json.dumps({**base, "pivot": gone}), "i": saved.json()["id"]})
    again = {v["name"]: v for v in api.get(ORDERS + "/views").json()["views"]}["pytest hesap"]
    assert [v["id"] for v in again["definition"]["pivot"]["values"]] == ["d1"] and again["definition"]["pivot"]["sort"] == {"by": "name", "dir": "asc"}
    assert again["warnings"]


def test_default_calculation_comes_from_the_list_definition(api):
    cols = {c["field"]: c for c in api.get(MAT + "/columns").json()["columns"]}
    assert cols["SafetyStock"]["aggregate"] == "sum" and cols["ScrapRatio"]["aggregate"] == "avg" and cols["ScrapRatio"]["aggregate_weight"] is None
    assert cols["Code"]["aggregate"] is None
    weighted = dataclasses.replace(MATERIALS, aggregates={**MATERIALS.aggregates, "ScrapRatio": "wavg"}, aggregate_weights={"ScrapRatio": "SafetyStock"})
    out = {c["field"]: c for c in definition.columns(weighted, {})}
    assert out["ScrapRatio"]["aggregate"] == "wavg" and out["ScrapRatio"]["aggregate_weight"] == "SafetyStock" and out["SafetyStock"]["aggregate_weight"] is None


# --- 7.9a demo bulguları (K-186): satır hücrelerinin birleşmesi, değerin satır biçimi, satır başlığı genişliği ------------------------------

def test_row_groups_follow_the_screen_rule():
    """Aynı öneki paylaşan ardışık satırlar tek hücre; ara toplam dış düzeyin grubunda, adını taşıdığı kolon ayrı; genel toplam ayrı."""
    row = lambda key, level, total=False: {"key": key, "level": level, "total": total}  # noqa: E731
    rows = [row(["A", "x"], 2), row(["A", "y"], 2), row(["A"], 1, True), row(["B", "x"], 2), row([], 0, True)]
    assert pivot_query.row_groups(rows, 2) == [[2, 1], [0, 1], [1, 1], [1, 1], [1, 1]]
    three = [row(["A", "x", 1], 3), row(["A", "x", 2], 3), row(["A", "x"], 2, True), row(["A", "y", 1], 3), row(["A"], 1, True)]
    assert pivot_query.row_groups(three, 3) == [[4, 2, 1], [0, 0, 1], [0, 1, 1], [0, 1, 1], [1, 1, 1]]   # iç ara toplam dış grubun (A) içinde


def test_excel_merges_row_cells_and_carries_row_format_and_widths(api, exporter):
    """Excel ekrandaki gibi (K-186): satır alanı hücreleri birleşik ve üstte hizalı; değerin satır biçimi satırına ya da sütunlarına; kural tutan
    hücrede kural kazanır; satır başlığı kolonları ekrandaki genişlikte."""
    own = "#ffe8a3"
    values = [{"id": "q", "field": "OpenQuantity", "fn": "sum", "format": {"fill": own, "bold": True}}, {"id": "o", "field": "OrderedQuantity", "fn": "sum"}]
    body = {"rows": [{"field": "CustomerCode"}, {"field": "MaterialCode"}], "columns": [{"field": "RequestedDate", "bucket": "month"}], "values": values}
    shown = pivot(api, ORDERS, **{**body, "values": [{k: v for k, v in x.items() if k != "format"} for x in values]})
    first = shown["rows"][0]["key"][0]
    size = sum(1 for r in shown["rows"] if r["key"][0] == first)
    assert size > 1 and shown["row_count"] <= 100

    r = api.post(ORDERS + "/pivot/export", headers=auth(exporter), json={**body, "values_on": "columns", "widths": {"CustomerCode": 30, "MaterialCode": 6}})
    assert r.status_code == 200, r.text
    ws = load_workbook(io.BytesIO(r.content))["Pivot"]
    merged = {str(m) for m in ws.merged_cells.ranges}
    assert f"A3:A{2 + size}" in merged and ws["A3"].value == first and ws["A3"].alignment.vertical == "top"    # müşteri hücresi malzemeleri boyunca
    assert not any(m.min_col == 2 and m.min_row >= 3 for m in ws.merged_cells.ranges)                         # en içteki alan satır başına tek hücre
    # dış grubun ilk satırının üstünde ince kenarlık (ekrandaki 1 px çizgi); ilk grupta ve grubun içinde yok; dikey ayraç kalın kalır
    second = 3 + size
    assert all(c.border.top.style == "thin" for c in ws[second][:4]) and ws.cell(second, 1).value != first
    assert all(c.border.top.style is None for c in ws[3][:4]) and all(c.border.top.style is None for c in ws[4][1:4])
    assert ws.column_dimensions["A"].width > ws.column_dimensions["B"].width * 3                              # 30 rem ve 6 rem
    data = list(ws.iter_rows(min_row=3))
    q_cells = [row[2 + 2 * i] for row in data for i in range(len(shown["columns"])) if row[2 + 2 * i].value is not None]
    o_cells = [row[3 + 2 * i] for row in data for i in range(len(shown["columns"])) if row[3 + 2 * i].value is not None]
    assert q_cells and all(rgb(c.fill.fgColor) == own[1:] and c.font.bold for c in q_cells)                   # değerin sütunları
    assert o_cells and all(rgb(c.fill.fgColor) != own[1:] and not c.font.bold for c in o_cells)

    # değerler satırlarda: müşteri hücresi malzeme × değer satırları boyunca, malzeme hücresi değer satırları boyunca; biçim değerin satırında
    ruled = [{**values[0], "rules": [rule("k1", "always")]}, values[1]]
    r = api.post(ORDERS + "/pivot/export", headers=auth(exporter), json={**body, "values": ruled, "values_on": "rows", "widths": {"__value": 40}})
    assert r.status_code == 200, r.text
    ws = load_workbook(io.BytesIO(r.content))["Pivot"]
    merged = {str(m) for m in ws.merged_cells.ranges}
    assert f"A3:A{2 + 2 * size}" in merged and "B3:B4" in merged and ws["B3"].alignment.vertical == "top"
    assert ws.column_dimensions["C"].width > 40                                                               # "Değer" kolonu 40 rem
    assert rgb(ws["C3"].fill.fgColor) == own[1:] and ws["C3"].font.bold and rgb(ws["C4"].fill.fgColor) != own[1:]   # değer adı hücresi
    line = [c for c in list(ws.iter_rows(min_row=3, max_row=3))[0][3:] if c.value is not None]
    assert line and all(rgb(c.fill.fgColor) == FILL[1:] and c.font.bold for c in line)                        # kural zemini kazanır; kalın satır biçiminden

    for bad in ({"widths": {"CustomerCode": 200}}, {"values": [{**values[0], "format": {"fill": "kırmızı"}}, values[1]]}):
        assert api.post(ORDERS + "/pivot/export", headers=auth(exporter), json={**body, **bad}).status_code == 422


def test_row_format_and_widths_are_saved_with_the_view(api, db_engine):
    base = {"v": 1, "columns": [{"field": "OrderNo"}], "pinned": 0, "sort": [], "filters": [], "group_by": []}
    values = [{"id": "d1", "field": "OpenQuantity", "fn": "sum", "format": {"fill": "#FFE8A3", "bold": True}},
              {"id": "d2", "field": "OrderedQuantity", "fn": "sum"}]
    definition_ = {"v": 1, "open": True, "rows": [{"field": "CustomerCode"}], "columns": [], "values": values, "values_on": "rows",
                   "totals": {"rows": False, "columns": False, "subtotals": False}, "sort": {"by": "name", "dir": "asc"},
                   "widths": {"CustomerCode": 18.5, "__value": 22, "MaterialCode": 9}}
    saved = api.post(ORDERS + "/views", json={"name": "pytest hesap biçim", "is_shared": False, "definition": {**base, "pivot": definition_}})
    assert saved.status_code == 201, saved.text
    got = {v["name"]: v for v in api.get(ORDERS + "/views").json()["views"]}["pytest hesap biçim"]["definition"]["pivot"]
    assert got["values"][0]["format"] == {"fill": "#ffe8a3", "bold": True} and "format" not in got["values"][1]
    assert got["widths"] == {"CustomerCode": 18.5, "__value": 22}                                                 # satırda olmayan alanın genişliği atılır
    bad = api.post(ORDERS + "/views", json={"name": "pytest hesap bozuk", "is_shared": False, "definition": {**base, "pivot": {**definition_, "widths": {"CustomerCode": 1}}}})
    assert bad.status_code == 422
    empty = {**definition_, "values": [{**values[1], "id": "d1", "format": {"bold": False}}]}                    # boş biçim gönderilmez (istemci saklamaz); sunucu reddeder
    assert api.post(ORDERS + "/views", json={"name": "pytest hesap bozuk", "is_shared": False, "definition": {**base, "pivot": empty}}).status_code == 422
    # biçim ve genişlik yalnız gösterim: pivot isteği bunları taşımasa da aynı sonucu verir
    plain = pivot(api, ORDERS, rows=definition_["rows"], values=[{k: v for k, v in x.items() if k != "format"} for x in values])
    assert plain["row_count"] > 0
