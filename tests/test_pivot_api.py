"""Pivot (K-183, geliştirme 7.7a): satır × sütun × değer; toplama veritabanında, satırlar parça parça. Sentetik v0'da; kendi yazdığını geri alır.

Sabitlenenler: hücreler satır sorgusuyla tutar; ara toplam ve genel toplam kayıtlardan (ortalamaların ortalaması değil) ve yüklenen parçadan
bağımsız; değere göre sıralama parçalar arasında doğru; satırlardan ortalama ile ağırlıklı ortalama aynı veride farklı sonuç verir.
"""
import json
from collections import defaultdict

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.api.permissions import END_USER, KEY_USER

from auth_helpers import auth, ensure_user

pytestmark = pytest.mark.db

ORDERS = "/api/transaction-sales-order"
QTY = {"id": "q", "field": "OpenQuantity", "fn": "sum"}
ALL = {"rows": True, "columns": True, "subtotals": True}


@pytest.fixture(scope="module")
def people(db_engine):
    with db_engine.begin() as c:
        return {KEY_USER: ensure_user(c, "pytest.pv.key", KEY_USER), END_USER: ensure_user(c, "pytest.pv.end", END_USER)}


@pytest.fixture(scope="module")
def api(db_engine, people):
    client = TestClient(create_app(), raise_server_exceptions=False)
    client.headers.update(auth(people[KEY_USER]))
    yield client
    with db_engine.begin() as c:
        c.execute(sa.text("DELETE FROM adm.TableView WHERE Name LIKE N'pytest pivot%'"))


def pivot(api, url, **body):
    r = api.post(url + "/pivot", json={"limit": 100, **body})
    assert r.status_code == 200, r.text
    return r.json()


def whole(api, url, **body):
    """Bütün görüntü satırları (parça parça okunur)."""
    first = pivot(api, url, **body)
    rows, offset = list(first["rows"]), 100
    while offset < first["row_count"]:
        rows += pivot(api, url, **body, offset=offset)["rows"]
        offset += 100
    assert len(rows) == first["row_count"]
    return first, rows


def records(api, url, fields, filters=()):
    out, offset = [], 0
    while True:
        r = api.post(url + "/query", json={"fields": fields, "filters": list(filters), "offset": offset, "limit": 100}).json()
        out += r["rows"]
        offset += 100
        if offset >= r["filtered"]:
            return out


def num(cell):
    return cell["v"] if isinstance(cell, dict) and "v" in cell else cell


def test_cells_subtotals_and_totals_match_the_records(api):
    """Müşteri › Malzeme × ay: toplam, benzersiz say, say, en düşük, en yüksek ve ortalama; her düzeyde kayıtlardan."""
    values = [QTY, {"id": "o", "field": "OrderNo", "fn": "distinct"}, {"id": "n", "fn": "count"}, {"id": "lo", "field": "OpenQuantity", "fn": "min"},
              {"id": "hi", "field": "OpenQuantity", "fn": "max"}, {"id": "avg", "field": "OpenQuantity", "fn": "avg"}]
    head, rows = whole(api, ORDERS, rows=[{"field": "CustomerCode"}, {"field": "MaterialCode"}], columns=[{"field": "RequestedDate", "bucket": "month"}],
                       values=values, totals=ALL)
    recs = records(api, ORDERS, ["CustomerCode", "MaterialCode", "RequestedDate", "OpenQuantity", "OrderNo"])
    month = lambda r: r["RequestedDate"][:7] + "-01"  # noqa: E731
    cols = head["columns"]
    assert [c["key"] for c in cols if not c["total"]] == [[m] for m in sorted({month(r) for r in recs})] and cols[-1] == {"key": [], "level": 0, "total": True}
    assert [v["id"] for v in head["values"]] == ["q", "o", "n", "lo", "hi", "avg"] and head["values"][0]["from_unit"] and head["values"][2]["decimals"] == 0

    def expect(sub):
        qty = [r["OpenQuantity"] for r in sub if r["OpenQuantity"] is not None]
        if not sub:
            return [None] * 6
        return [sum(qty) if qty else None, len({r["OrderNo"] for r in sub}), len(sub), min(qty, default=None), max(qty, default=None),
                sum(qty) / len(qty) if qty else None]

    seen = defaultdict(int)
    for row in rows:
        seen[row["level"]] += 1
        mine = [r for r in recs if [r["CustomerCode"], r["MaterialCode"]][: row["level"]] == row["key"]]
        for s, c in enumerate(cols):
            sub = mine if c["total"] else [r for r in mine if month(r) == c["key"][0]]
            got = [num(row["cells"][k][s]) for k in range(6)]
            assert got == pytest.approx(expect(sub)), (row["key"], c["key"])
    customers = {r["CustomerCode"] for r in recs}
    assert seen[0] == 1 and seen[1] == len(customers) and seen[2] == len({(r["CustomerCode"], r["MaterialCode"]) for r in recs})
    assert rows[-1]["level"] == 0 and rows[-1]["total"]                                   # genel toplam en sonda
    last_of_a = max(i for i, r in enumerate(rows) if r["key"][:1] == ["MUS-A"])
    assert rows[last_of_a]["total"] and rows[last_of_a]["level"] == 1                     # ara toplam grubunun sonunda


def test_pages_are_consistent_and_totals_do_not_depend_on_the_page(api):
    body = dict(rows=[{"field": "CustomerCode"}, {"field": "MaterialCode"}], columns=[{"field": "RequestedDate", "bucket": "month"}], values=[QTY], totals=ALL)
    one = pivot(api, ORDERS, **body)
    small = []
    for offset in range(0, one["row_count"], 5):
        part = api.post(ORDERS + "/pivot", json={**body, "offset": offset, "limit": 5}).json()
        assert part["row_count"] == one["row_count"] and part["columns"] == one["columns"]
        small += part["rows"]
    assert small == one["rows"]                                                            # parça sınırı sırayı ve toplamları değiştirmez
    beyond = api.post(ORDERS + "/pivot", json={**body, "offset": 10_000, "limit": 5}).json()
    assert beyond["rows"] == [] and beyond["row_count"] == one["row_count"]
    assert api.post(ORDERS + "/pivot", json={**body, "limit": 500}).status_code in (200, 422)  # ListChunkSize üstü reddedilir (ayar 500 değilse)
    hidden = pivot(api, ORDERS, **{**body, "totals": {"rows": False, "columns": False, "subtotals": False}})
    assert all(not r["total"] for r in hidden["rows"]) and all(not c["total"] for c in hidden["columns"])
    assert [r for r in one["rows"] if not r["total"]][0]["cells"][0][:-1] == hidden["rows"][0]["cells"][0]


def test_sort_by_value_is_hierarchical_and_survives_paging(api):
    """Gruplar kendi toplamına, yapraklar kendi değerine göre; sıralama parçalamadan önce bütün veride."""
    body = dict(rows=[{"field": "CustomerCode"}, {"field": "MaterialCode"}], columns=[{"field": "RequestedDate", "bucket": "month"}], values=[QTY],
                totals={"rows": False, "columns": True, "subtotals": True}, sort={"by": "q", "dir": "desc"})
    _, rows = whole(api, ORDERS, **body)
    paged = []
    for offset in range(0, len(rows), 7):
        paged += api.post(ORDERS + "/pivot", json={**body, "offset": offset, "limit": 7}).json()["rows"]
    assert paged == rows
    total = lambda r: num(r["cells"][0][-1])  # noqa: E731
    groups = [r for r in rows if r["total"]]
    assert [total(g) for g in groups] == sorted((total(g) for g in groups), reverse=True) and len(groups) >= 3
    for g in groups:
        leaves = [total(r) for r in rows if not r["total"] and r["key"][0] == g["key"][0]]
        assert leaves == sorted(leaves, reverse=True) and sum(leaves) == pytest.approx(total(g))
    asc = pivot(api, ORDERS, **{**body, "sort": {"by": "q", "dir": "asc"}})["rows"]
    assert [total(r) for r in asc if r["total"]][0] == min(total(g) for g in groups)
    names = pivot(api, ORDERS, rows=[{"field": "CustomerCode"}], values=[QTY], sort={"by": "name", "dir": "desc"})["rows"]
    assert [r["key"][0] for r in names] == sorted((r["key"][0] for r in names), reverse=True)


@pytest.fixture
def ratio_rows(db_engine):
    """6. maddenin örneği (K-183): kapasite 100 ve oran %90; kapasite 300 ve oran %50 (aynı grupta), ayrı grupta kapasite 50 ve oran %10."""
    with db_engine.begin() as c:
        cols = [x["name"] for x in sa.inspect(c).get_columns("Material", schema="core")]
        keep = [x for x in cols if x not in ("Id", "Code", "BusinessKey", "MaterialGroup", "MaterialLevel", "SafetyStock", "ScrapRatio")]
        for i, (group, weight, ratio) in enumerate([("PV-A", 100, 0.9), ("PV-A", 300, 0.5), ("PV-B", 50, 0.1)], 1):
            c.execute(sa.text(f"INSERT INTO core.Material ({', '.join(keep)}, Id, Code, BusinessKey, MaterialGroup, MaterialLevel, SafetyStock, ScrapRatio) "
                              f"SELECT TOP 1 {', '.join(keep)}, :id, :code, :code, :g, N'PIVOT-TEST', :w, :r FROM core.Material WHERE VersionTo IS NULL AND BaseUom = N'ADET' ORDER BY Id"),
                      {"id": 9_900_000 + i, "code": f"PV-{i}", "g": group, "w": weight, "r": ratio})
    yield
    with db_engine.begin() as c:
        c.execute(sa.text("DELETE FROM core.Material WHERE Id BETWEEN 9900001 AND 9900003"))


def test_average_and_weighted_average_differ_on_the_same_data(api, ratio_rows):
    """Satırlardan iki hesap aynı veride farklı sonuç verir; ara toplam ve genel toplam kayıtlardan (ortalamaların ortalaması değil)."""
    values = [{"id": "avg", "field": "ScrapRatio", "fn": "avg"}, {"id": "wavg", "field": "ScrapRatio", "fn": "wavg", "weight": "SafetyStock"},
              {"id": "w", "field": "SafetyStock", "fn": "sum"}]
    out = pivot(api, "/api/materials", rows=[{"field": "MaterialGroup"}, {"field": "Code"}], values=values, totals=ALL,
                filters=[{"field": "MaterialLevel", "op": "in", "values": ["PIVOT-TEST"]}])
    by_key = {tuple(r["key"]): [num(c[0]) for c in r["cells"]] for r in out["rows"]}
    assert by_key[("PV-A",)] == pytest.approx([0.70, 0.60, 400])            # ortalama (0,9 + 0,5) / 2; ağırlıklı (90 + 150) / 400
    assert by_key[("PV-A",)][0] != pytest.approx(by_key[("PV-A",)][1])
    assert by_key[("PV-B",)] == pytest.approx([0.10, 0.10, 50])
    # genel toplam kayıtlardan: ortalama (0,9 + 0,5 + 0,1) / 3 = 0,5 (grup ortalamalarının ortalaması 0,4 olurdu); ağırlıklı 245 / 450
    assert by_key[()] == pytest.approx([0.5, 245 / 450, 450])
    assert by_key[()][0] != pytest.approx((0.70 + 0.10) / 2)
    info = {v["id"]: v for v in out["values"]}
    assert info["avg"]["percent"] and info["wavg"]["percent"] and info["wavg"]["weight"] == "SafetyStock" and info["w"]["from_unit"]


def test_earliest_and_latest_on_date_fields(api):
    """Tarih alanında En erken · En geç (K-183 demo kararı): hücrede, ara toplamda ve genel toplamda kayıtlardan; sıralama da tarihle."""
    values = [{"id": "ilk", "field": "RequestedDate", "fn": "min"}, {"id": "son", "field": "RequestedDate", "fn": "max"}, {"id": "n", "fn": "count"}]
    out, rows = whole(api, ORDERS, rows=[{"field": "CustomerCode"}, {"field": "MaterialCode"}], values=values, totals=ALL, sort={"by": "ilk", "dir": "asc"})
    recs = records(api, ORDERS, ["CustomerCode", "MaterialCode", "RequestedDate"])
    for row in rows:
        days = [r["RequestedDate"] for r in recs if [r["CustomerCode"], r["MaterialCode"]][: row["level"]] == row["key"]]
        assert [row["cells"][0][0], row["cells"][1][0], row["cells"][2][0]] == [min(days), max(days), len(days)], row["key"]
    assert [v["type"] for v in out["values"]] == ["date", "date", "number"]
    firsts = [r["cells"][0][0] for r in rows if r["total"] and r["level"] == 1]
    assert firsts == sorted(firsts)                                                        # müşteriler ilk sipariş tarihine göre
    bad = api.post(ORDERS + "/pivot", json={"rows": [{"field": "CustomerCode"}], "values": [{"id": "x", "field": "RequestedDate", "fn": "sum"}]})
    assert bad.status_code == 422 and "Tarih alanında yalnız En erken, En geç, Say ve Benzersiz say" in bad.text
    text = api.post(ORDERS + "/pivot", json={"rows": [{"field": "CustomerCode"}], "values": [{"id": "x", "field": "OrderNo", "fn": "min"}]})
    assert text.status_code == 422                                                         # metin alanında yalnız Say ve Benzersiz say


def test_same_field_on_an_axis_and_as_a_value_with_totals_and_a_filter(api):
    """Demo bulgusu: İstek tarihi hem sütunda (ay) hem değerde (En erken); üç toplam açık; tabloda "içermez" filtresi. Pivot çizilir."""
    body = dict(rows=[{"field": "CustomerCode"}, {"field": "MaterialCode"}], columns=[{"field": "RequestedDate", "bucket": "month"}],
                values=[QTY, {"id": "o", "field": "OrderNo", "fn": "distinct"}, {"id": "ilk", "field": "RequestedDate", "fn": "min"}], totals=ALL,
                filters=[{"field": "Uom", "op": "not_contains", "value": "PALET"}])
    out, rows = whole(api, ORDERS, **body)
    recs = records(api, ORDERS, ["CustomerCode", "MaterialCode", "RequestedDate"], body["filters"])
    cols = out["columns"]
    for row in rows:
        mine = [r["RequestedDate"] for r in recs if [r["CustomerCode"], r["MaterialCode"]][: row["level"]] == row["key"]]
        for s, c in enumerate(cols):
            days = mine if c["total"] else [x for x in mine if x[:7] + "-01" == c["key"][0]]
            assert row["cells"][2][s] == (min(days) if days else None), (row["key"], c["key"])
    assert rows[-1]["total"] and rows[-1]["cells"][2][-1] == min(r["RequestedDate"] for r in recs)
    same_row = pivot(api, ORDERS, rows=[{"field": "CustomerCode"}], values=[{"id": "n", "field": "CustomerCode", "fn": "distinct"}], totals=ALL)
    assert [r["cells"][0][0] for r in same_row["rows"]] == [1] * (len(same_row["rows"]) - 1) + [len(same_row["rows"]) - 1]   # satır alanı değer olarak da


def test_mixed_units_only_on_own_quantity_fields(api):
    """Listenin kendi miktar alanında birim tek değilse hücre işaretli boş; "Say" etkilenmez; ilişkili miktar alanında denetlenmez (K-183)."""
    out = pivot(api, "/api/master-bom", rows=[{"field": "LocationCode"}], values=[{"id": "q", "field": "Quantity", "fn": "sum"}, {"id": "n", "fn": "count"}])
    assert out["rows"][0]["cells"][0][0] == {"mixed": True} and out["rows"][0]["cells"][1][0] > 100
    per_part = pivot(api, "/api/master-bom", rows=[{"field": "ComponentMaterialCode"}], values=[{"id": "q", "field": "Quantity", "fn": "sum"}])
    assert {r["cells"][0][0]["d"] for r in per_part["rows"]} >= {0, 3}                      # bileşen tek birimde: adet ondalıksız, kg 3 ondalık
    related = pivot(api, "/api/transaction-work-order-operation", rows=[{"field": "ResourceGroupCode"}],
                    values=[{"id": "q", "field": "WorkOrderId/OpenQuantity", "fn": "sum"}, {"id": "c", "field": "PlannedConsumption", "fn": "sum"}], totals=ALL)
    assert all(not (isinstance(c, dict) and c.get("mixed")) for r in related["rows"] for c in r["cells"][0])
    assert related["rows"][0]["cells"][0][0]["d"] == 0 and related["rows"][0]["cells"][1][0]["d"] == 2      # adet ondalıksız, saat 2 ondalık


def test_related_fields_as_row_column_and_value(api):
    body = dict(rows=[{"field": "MaterialId/MaterialGroup"}], columns=[{"field": "CustomerId/Name"}], values=[QTY, {"id": "m", "field": "MaterialId/Name", "fn": "distinct"}],
                totals=ALL)
    out = pivot(api, ORDERS, **body)
    recs = records(api, ORDERS, ["OpenQuantity", "MaterialId/MaterialGroup", "CustomerId/Name", "MaterialId/Name"])
    assert {tuple(r["key"]) for r in out["rows"] if not r["total"]} == {(r["MaterialId/MaterialGroup"],) for r in recs}
    grand = out["rows"][-1]
    assert num(grand["cells"][0][-1]) == pytest.approx(sum(r["OpenQuantity"] or 0 for r in recs)) and grand["cells"][1][-1] == len({r["MaterialId/Name"] for r in recs})
    assert [f["field"] for f in out["row_fields"] + out["column_fields"]] == ["MaterialId/MaterialGroup", "CustomerId/Name"]


def test_column_axis_two_fields_periods_and_limits(api, monkeypatch):
    out = pivot(api, ORDERS, rows=[{"field": "CustomerCode"}], columns=[{"field": "RequestedDate", "bucket": "quarter"}, {"field": "MaterialCode"}],
                values=[QTY], totals=ALL)
    cols = out["columns"]
    quarters = [c["key"][0] for c in cols if c["level"] == 2]
    assert quarters == sorted(quarters) and len(set(quarters)) >= 2
    for q in set(quarters):  # her üst başlığın sonunda ara toplam sütunu
        mine = [i for i, c in enumerate(cols) if c["key"][:1] == [q]]
        assert cols[mine[-1]] == {"key": [q], "level": 1, "total": True} and all(cols[i]["level"] == 2 for i in mine[:-1])
    assert cols[-1] == {"key": [], "level": 0, "total": True}
    row = out["rows"][0]
    for q in set(quarters):
        leaf = [num(row["cells"][0][i]) or 0 for i, c in enumerate(cols) if c["key"][:1] == [q] and c["level"] == 2]
        sub = num(row["cells"][0][next(i for i, c in enumerate(cols) if c["key"] == [q] and c["total"])])
        assert sum(leaf) == pytest.approx(sub or 0)
    # verisiz dönem de sütundur: bir ayı süzünce aradaki ay boş sütun olarak kalır
    months = [c["key"][0] for c in pivot(api, ORDERS, rows=[{"field": "CustomerCode"}], columns=[{"field": "RequestedDate", "bucket": "month"}], values=[QTY])["columns"]]
    assert len(months) >= 3
    gap = pivot(api, ORDERS, rows=[{"field": "CustomerCode"}], columns=[{"field": "RequestedDate", "bucket": "month"}], values=[QTY],
                filters=[{"field": "RequestedDate", "op": "between", "from": months[0], "to": months[0][:8] + "28"}])
    assert [c["key"][0] for c in gap["columns"]] == months[:1]
    days = pivot(api, ORDERS, rows=[{"field": "CustomerCode"}], columns=[{"field": "RequestedDate", "bucket": "day"}], values=[{"id": "n", "fn": "count"}])
    assert any(c.get("empty") for c in days["columns"]) and all(v is None for r in days["rows"] for i, v in enumerate(r["cells"][0]) if days["columns"][i].get("empty"))
    too_many = api.post("/api/materials/pivot", json={"rows": [{"field": "MaterialGroup"}], "columns": [{"field": "Code"}], "values": [{"id": "n", "fn": "count"}]})
    assert too_many.status_code == 422 and too_many.json()["error"]["code"] == "pivot_too_large" and "Sütun sayısı çok fazla" in too_many.json()["error"]["message"]
    from app.api.lists import pivot as pivot_query
    monkeypatch.setattr(pivot_query, "MAX_VALUE_COLUMNS", 6)
    wide = api.post(ORDERS + "/pivot", json={"rows": [{"field": "CustomerCode"}], "columns": [{"field": "RequestedDate", "bucket": "month"}],
                                             "values": [QTY, {"id": "n", "fn": "count"}]})
    assert wide.status_code == 422 and "değer sütunu" in wide.json()["error"]["message"]


def test_pivot_pickers_share_one_rule(api):
    """K-183: "Manuel değer" kolonu ve sistem alanları (son değişiklik zamanı) pivot seçicilerinde sunulmaz; kural kolon bilgisinde tek işarettir."""
    for url in (ORDERS, "/api/materials", "/api/master-resource-group-member", "/api/master-location"):
        cols = {c["field"]: c for c in api.get(url + "/columns").json()["columns"]}
        hidden = {f for f, c in cols.items() if not c["pivot"]}
        assert hidden == {"ManualState", "UpdatedAt"} & set(cols) and "ManualState" in hidden, url
    related = api.get(ORDERS + "/related", params={"path": "CustomerId"}).json()["fields"]
    assert related and all(f["pivot"] for f in related) and not any(f["field"].endswith(("UpdatedAt", "ManualState")) for f in related)
    other = api.get("/api/data-entities/columns").json()["columns"]
    assert all(c["pivot"] for c in other)                                                   # çekirdek dışı listelerde kural uygulanmaz


def test_filters_selection_and_permissions(api, people):
    full = pivot(api, ORDERS, rows=[{"field": "CustomerCode"}], values=[QTY], totals=ALL)
    one = pivot(api, ORDERS, rows=[{"field": "CustomerCode"}], values=[QTY], totals=ALL, filters=[{"field": "CustomerCode", "op": "in", "values": ["MUS-B"]}])
    assert [r["key"] for r in one["rows"]] == [["MUS-B"], []] and one["rows"][-1]["cells"] == one["rows"][0]["cells"]
    assert one["rows"][0]["cells"] == next(r["cells"] for r in full["rows"] if r["key"] == ["MUS-B"])
    picked = pivot(api, ORDERS, rows=[{"field": "MaterialCode"}], values=[QTY], totals=ALL,
                   chart_selection={"x": {"field": "CustomerCode"}, "items": [{"x": "MUS-B"}]})
    assert picked["rows"][-1]["cells"] == one["rows"][-1]["cells"]                        # grafik seçimi pivota da uygulanır
    assert api.post(ORDERS + "/pivot", headers=auth(people[END_USER]), json={"rows": [{"field": "CustomerCode"}], "values": [QTY]}).status_code == 200
    empty = pivot(api, ORDERS, rows=[{"field": "CustomerCode"}], values=[QTY], totals=ALL, filters=[{"field": "CustomerCode", "op": "in", "values": ["YOK"]}])
    assert empty["rows"] == [] and empty["row_count"] == 0


@pytest.mark.parametrize("body, text", [
    ({"rows": [{"field": "Nope"}], "values": [QTY]}, "Bilinmeyen alan: Nope"),
    ({"rows": [{"field": "OpenQuantity"}], "values": [QTY]}, "satır ya da sütun olamaz"),
    ({"rows": [{"field": "RequestedDate"}], "values": [QTY]}, "dönem tipi seçilmeli"),
    ({"rows": [{"field": "CustomerCode", "bucket": "month"}], "values": [QTY]}, "Dönem tipi yalnız tarih alanında"),
    ({"rows": [{"field": "CustomerCode"}], "columns": [{"field": "CustomerCode"}], "values": [QTY]}, "iki kez kullanılamaz"),
    ({"rows": [{"field": "CustomerCode"}], "values": [{"id": "x", "field": "OrderNo", "fn": "sum"}]}, "yalnız sayı alanında"),
    ({"rows": [{"field": "CustomerCode"}], "values": [{"id": "x", "field": "OpenQuantity", "fn": "wavg"}]}, "Ağırlıklı ortalama için başka bir sayı alanı"),
    ({"rows": [{"field": "CustomerCode"}], "values": [{"id": f"d{i}", "field": "OrderNo", "fn": "distinct"} for i in range(4)]}, "En çok 3"),
    ({"rows": [{"field": "CustomerCode"}], "values": [QTY, QTY]}, "tekil olmalı"),
    ({"rows": [{"field": "CustomerCode"}], "values": [QTY], "sort": {"by": "zz", "dir": "asc"}}, "Bilinmeyen değer: zz"),
    ({"rows": [], "values": [QTY]}, ""),
    ({"rows": [{"field": "CustomerCode"}], "values": []}, ""),
])
def test_validation(api, body, text):
    r = api.post(ORDERS + "/pivot", json=body)
    assert r.status_code == 422 and text in r.text


def test_pivot_is_saved_with_the_view_and_adapted(api, db_engine):
    base = {"v": 1, "columns": [{"field": "OrderNo"}], "pinned": 0, "sort": [], "filters": [], "group_by": []}
    plain = api.post(ORDERS + "/views", json={"name": "pytest pivot yok", "is_shared": False, "definition": base})
    definition = {"v": 1, "open": True, "rows": [{"field": "CustomerCode"}, {"field": "MaterialId/MaterialGroup"}],
                  "columns": [{"field": "RequestedDate", "bucket": "week"}],
                  "values": [{"id": "d1", "field": "OpenQuantity", "fn": "wavg", "weight": "OrderedQuantity", "decimals": 1}, {"id": "d2", "fn": "count", "name": "Sipariş sayısı"}],
                  "values_on": "rows", "totals": {"rows": True, "columns": False, "subtotals": True}, "sort": {"by": "d1", "dir": "desc"}}
    saved = api.post(ORDERS + "/views", json={"name": "pytest pivot", "is_shared": False, "definition": {**base, "pivot": definition}})
    assert plain.status_code == 201 and saved.status_code == 201, saved.text
    listed = api.get(ORDERS + "/views").json()
    by_name = {v["name"]: v for v in listed["views"]}
    assert "pivot" not in by_name["pytest pivot yok"]["definition"]                        # eski görünüm olduğu gibi
    got = by_name["pytest pivot"]["definition"]["pivot"]
    assert got["rows"] == [{"field": "CustomerCode"}, {"field": "MaterialId/MaterialGroup"}] and got["values_on"] == "rows" and got["sort"] == {"by": "d1", "dir": "desc"}
    assert got["values"][0] == {"id": "d1", "field": "OpenQuantity", "fn": "wavg", "weight": "OrderedQuantity", "decimals": 1}
    assert got["values"][1] == {"id": "d2", "fn": "count", "name": "Sipariş sayısı"}        # değerin özel adı görünümle saklanır
    assert "MaterialId/MaterialGroup" in {c["field"] for c in listed["related_columns"]}   # pivotun ilişkili alanı tanınır
    bad = api.post(ORDERS + "/views", json={"name": "pytest pivot bozuk", "is_shared": False,
                                            "definition": {**base, "pivot": {**definition, "rows": [{"field": "OpenQuantity"}]}}})
    assert bad.status_code == 422 and "definition.pivot.rows.0.field" in bad.text
    with db_engine.begin() as c:  # alan sonradan kalkmış gibi
        gone = {**definition, "rows": [{"field": "CustomerCode"}, {"field": "Gone"}], "values": [{"id": "d1", "field": "Gone2", "fn": "sum"}, {"id": "d2", "fn": "count"}]}
        c.execute(sa.text("UPDATE adm.TableView SET Definition = :d WHERE Id = :i"), {"d": json.dumps({**base, "pivot": gone}), "i": saved.json()["id"]})
    again = {v["name"]: v for v in api.get(ORDERS + "/views").json()["views"]}["pytest pivot"]
    assert again["definition"]["pivot"]["rows"] == [{"field": "CustomerCode"}] and [v["id"] for v in again["definition"]["pivot"]["values"]] == ["d2"]
    assert again["definition"]["pivot"]["sort"] == {"by": "name", "dir": "asc"} and len(again["warnings"]) == 2
    with db_engine.begin() as c:  # hiç satır alanı kalmazsa pivot kaldırılır
        c.execute(sa.text("UPDATE adm.TableView SET Definition = :d WHERE Id = :i"),
                  {"d": json.dumps({**base, "pivot": {**definition, "rows": [{"field": "Gone"}]}}), "i": saved.json()["id"]})
    removed = {v["name"]: v for v in api.get(ORDERS + "/views").json()["views"]}["pytest pivot"]
    assert "pivot" not in removed["definition"] and any("pivot görünümden çıkarıldı" in w for w in removed["warnings"])
