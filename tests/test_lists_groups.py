"""Gruplama ve ara toplam (K-90), boş değer filtresi (U-13): birim testleri ve sentetik v0 ile veritabanı testleri."""
import pytest
from sqlalchemy import text

from app.api.lists.groups import build_tree

from test_lists_api import all_rows, api, query  # noqa: F401  (fikstür ve yardımcılar)


def leaf(g, n, unit=None, **m):
    """Yaprak satırı: m ölçüleri (k_X, s_X, d_X, v_X)."""
    return {**{f"g{i}": v for i, v in enumerate(g)}, "n": n, "u": unit, **m}


# --- birim: ağaç ve ara toplamlar -------------------------------------------------------------------------------

def test_each_function_combines_exactly_upwards():
    """Üst grup alt gruplardan tam türetilir: toplam/sayı toplanır, ortalamalar pay ve paydayla, en küçük/büyük karşılaştırılır."""
    leaves = [leaf(["A", "x"], 3, k_Q=2, s_Q=10, d_Q=2, k_M=2, v_M=4), leaf(["A", "y"], 2, k_Q=2, s_Q=2, d_Q=1, k_M=1, v_M=1),
              leaf(["B", "z"], 1, k_Q=0, s_Q=None, d_Q=0, k_M=0, v_M=None)]
    for fn, a, b in [("sum", 12.0, None), ("avg", 4.0, None), ("avg_nonzero", 4.0, None), ("wavg", 4.0, None),
                     ("count", 4, 0)]:
        t = build_tree(leaves, 2, {"Q": fn}, set())
        assert (t["groups"][0]["aggregates"]["Q"], t["groups"][1]["aggregates"]["Q"]) == (a, b), fn
    t = build_tree(leaves, 2, {"M": "min"}, set())
    assert [t["groups"][0]["aggregates"]["M"], t["groups"][0]["children"][0]["aggregates"]["M"]] == [1.0, 4.0]
    assert build_tree(leaves, 2, {"M": "max"}, set())["aggregates"]["M"] == 4.0


def test_weighted_average_zero_weight_is_empty():
    t = build_tree([leaf(["A"], 2, k_W=2, s_W=0, d_W=0)], 1, {"W": "wavg"}, set())
    assert t["groups"][0]["aggregates"]["W"] is None


def test_mixed_units_hide_value_but_not_count():
    leaves = [leaf(["A"], 2, "ADET", k_Q=2, s_Q=10, d_Q=2), leaf(["A"], 1, "KG", k_Q=1, s_Q=1.5, d_Q=1),
              leaf(["B"], 1, "KG", k_Q=0, s_Q=None, d_Q=0), leaf(["B"], 2, "ADET", k_Q=2, s_Q=4, d_Q=2)]
    t = build_tree(leaves, 1, {"Q": "sum"}, {"Q"}, unit_decimals={"ADET": 0})
    a, b = t["groups"]
    assert (a["count"], a["aggregates"]["Q"], a["mixed_units"]) == (3, None, ["Q"])
    assert (b["count"], b["aggregates"]["Q"], b["mixed_units"], b["unit_decimals"]) == (3, 4.0, [], {"Q": 0})  # değersiz KG sayılmaz
    assert t["leaf_groups"] == 2
    t = build_tree(leaves, 1, {"Q": "count"}, set())  # sayı birim kuralına girmez
    assert [g["aggregates"]["Q"] for g in t["groups"]] == [3, 2]


def test_tree_keeps_server_order():
    t = build_tree([leaf(["Z"], 1), leaf(["A"], 1), leaf([None], 1)], 1, {}, set())
    assert [g["key"] for g in t["groups"]] == [["Z"], ["A"], [None]]
    assert "children" not in t["groups"][0]


# --- veritabanı -------------------------------------------------------------------------------------------------

needs_db = pytest.mark.db


def groups(api, **body):
    r = api.post("/api/materials/groups", json=body)
    assert r.status_code == 200, r.text
    return r.json()


@needs_db
def test_two_levels_counts_match_rows(api):
    t = groups(api, group_by=["MaterialLevel", "MaterialGroup"])
    assert sum(g["count"] for g in t["groups"]) == 200
    for g in t["groups"]:
        assert g["count"] == sum(ch["count"] for ch in g["children"])
        assert g["count"] == query(api, fields=["Code"], group_key=[{"field": "MaterialLevel", "value": g["key"][0]}])["filtered"]
    ham = next(g for g in t["groups"] if g["key"] == ["Hammadde"])
    rulman = next(ch for ch in ham["children"] if ch["key"] == ["Hammadde", "Rulman"])
    assert rulman["count"] == 6 and rulman["aggregates"]["SafetyStock"] == 120.0  # 6 × 20 ADET
    assert rulman["unit_decimals"]["SafetyStock"] == 0
    assert (t["filtered"], t["total"]) == (200, 200)


@needs_db
def test_group_order_follows_sort_and_is_turkish(api):
    asc = [g["key"][0] for g in groups(api, group_by=["MaterialGroup"])["groups"]]
    assert asc.index("Conta") < asc.index("Çubuk") < asc.index("Dövme")
    desc = [g["key"][0] for g in groups(api, group_by=["MaterialLevel"], sort=[{"field": "MaterialLevel", "dir": "desc"}])["groups"]]
    assert desc == ["Yarı mamul", "Nihai ürün", "Hammadde"]


@needs_db
def test_weighted_average_matches_database(api, db_engine):
    with db_engine.connect() as conn:
        avg = float(conn.execute(text("SELECT AVG(ProductionLeadTimeDays) FROM core.Material WHERE VersionTo IS NULL "
                                      "AND MaterialLevel = N'Yarı mamul'")).scalar_one())
    t = groups(api, group_by=["MaterialLevel", "MaterialGroup"])
    yarim = next(g for g in t["groups"] if g["key"] == ["Yarı mamul"])
    assert yarim["aggregates"]["ProductionLeadTimeDays"] == pytest.approx(avg)


@needs_db
def test_mixed_units_have_no_quantity_total(api, db_engine):
    try:
        with db_engine.begin() as conn:  # bir KG malzemeye geçici güvenlik stoğu: Hammadde grubunda ADET + KG
            conn.execute(text("UPDATE core.Material SET SafetyStock = 1.5 WHERE Code = 'HAM-001' AND VersionTo IS NULL"))
        t = groups(api, group_by=["MaterialLevel"])
        ham = next(g for g in t["groups"] if g["key"] == ["Hammadde"])
        assert ham["aggregates"]["SafetyStock"] is None and "SafetyStock" in ham["mixed_units"]
        assert "SafetyStock" in t["mixed_units"]
    finally:
        with db_engine.begin() as conn:
            conn.execute(text("UPDATE core.Material SET SafetyStock = NULL WHERE Code = 'HAM-001' AND VersionTo IS NULL"))


@needs_db
def test_empty_group_is_last_and_rows_read_by_null_key(api, db_engine):
    try:
        with db_engine.begin() as conn:
            conn.execute(text("UPDATE core.Material SET MaterialGroup = NULL WHERE Code IN ('SAT-001', 'SAT-002') AND VersionTo IS NULL"))
            conn.execute(text("UPDATE core.Material SET MaterialGroup = N'' WHERE Code = 'SAT-003' AND VersionTo IS NULL"))
        t = groups(api, group_by=["MaterialGroup"])
        assert t["groups"][-1]["key"] == [None] and t["groups"][-1]["count"] == 3  # boş metin de boş grupta
        rows = all_rows(api, fields=["Code"], group_key=[{"field": "MaterialGroup", "value": None}])
        assert sorted(r["Code"] for r in rows) == ["SAT-001", "SAT-002", "SAT-003"]
        assert query(api, filters=[{"field": "MaterialGroup", "op": "empty"}])["filtered"] == 3
        both = query(api, filters=[{"field": "MaterialGroup", "op": "in", "values": ["Rulman"], "empty": True}])
        assert both["filtered"] == 3 + 3  # SAT-001…003 boşaldı; kalan 3 rulman + 3 boş
        values = api.post("/api/materials/values", json={"field": "MaterialGroup"}).json()
        assert values[0] == {"value": None, "count": 3}
    finally:
        with db_engine.begin() as conn:
            conn.execute(text("UPDATE core.Material SET MaterialGroup = N'Rulman' WHERE Code IN ('SAT-001', 'SAT-002', 'SAT-003') AND VersionTo IS NULL"))


@needs_db
@pytest.mark.parametrize("flt, expected", [
    ({"field": "MaxStock", "op": "empty"}, 200),
    ({"field": "ProductionLeadTimeDays", "op": "empty"}, 80),
    ({"field": "Name", "op": "empty"}, 0),
    ({"field": "UpdatedAt", "op": "empty"}, 0),
])
def test_empty_operator_every_type(api, flt, expected):
    assert query(api, filters=[flt])["filtered"] == expected


@needs_db
def test_group_key_rows_belong_to_group_and_chunks_complete(api):
    key = [{"field": "MaterialLevel", "value": "Yarı mamul"}, {"field": "MaterialGroup", "value": "İşlenmiş parça"}]
    rows = all_rows(api, fields=["Code", "MaterialLevel", "MaterialGroup"], group_key=key)
    assert len(rows) == 80 and {(r["MaterialLevel"], r["MaterialGroup"]) for r in rows} == {("Yarı mamul", "İşlenmiş parça")}


@needs_db
def test_too_many_groups(api, db_engine):
    try:
        with db_engine.begin() as conn:
            conn.execute(text("INSERT INTO adm.SystemSetting (SettingKey, Value) VALUES ('ListMaxGroups', '5')"))
        r = api.post("/api/materials/groups", json={"group_by": ["MaterialGroup"]})
        assert r.status_code == 422 and r.json()["error"]["code"] == "too_many_groups"
        assert api.post("/api/materials/groups", json={"group_by": ["MaterialLevel"]}).status_code == 200
    finally:
        with db_engine.begin() as conn:
            conn.execute(text("DELETE FROM adm.SystemSetting WHERE SettingKey = 'ListMaxGroups'"))


@needs_db
def test_group_validation(api):
    assert api.post("/api/materials/groups", json={"group_by": []}).status_code == 422
    assert api.post("/api/materials/groups", json={"group_by": ["Nope"]}).status_code == 422
    assert api.post("/api/materials/groups", json={"group_by": ["Code", "Code"]}).status_code == 422


@needs_db
def test_each_aggregate_function_matches_database(api, db_engine):
    """Her tür için sonuç doğrudan SQL'le karşılaştırılır (K-90). Geçici veri: bir sıfır süre ve bazı satırlara ağırlık."""
    level = "Yarı mamul"
    where = "VersionTo IS NULL AND MaterialLevel = N'Yarı mamul'"
    try:
        with db_engine.begin() as conn:
            conn.execute(text(f"UPDATE core.Material SET ProductionLeadTimeDays = 0 WHERE Code = 'ALT-001' AND VersionTo IS NULL"))
            conn.execute(text(f"UPDATE core.Material SET MaxStock = Id % 5 + 1 WHERE {where} AND Id % 2 = 0"))
            row = conn.execute(text(f"""SELECT SUM(ProductionLeadTimeDays), AVG(ProductionLeadTimeDays),
                SUM(ProductionLeadTimeDays) / NULLIF(SUM(CASE WHEN ProductionLeadTimeDays <> 0 THEN 1 END), 0),
                MIN(ProductionLeadTimeDays), MAX(ProductionLeadTimeDays), COUNT(ProductionLeadTimeDays),
                SUM(ProductionLeadTimeDays * MaxStock) / SUM(CASE WHEN ProductionLeadTimeDays IS NOT NULL THEN MaxStock END)
                FROM core.Material WHERE {where}""")).one()
        expected = dict(zip(["sum", "avg", "avg_nonzero", "min", "max", "count", "wavg"], row))
        for fn, want in expected.items():
            spec = {"fn": fn, "weight": "MaxStock"} if fn == "wavg" else {"fn": fn}
            t = groups(api, group_by=["MaterialLevel"], aggregates={"ProductionLeadTimeDays": spec})
            got = next(g for g in t["groups"] if g["key"] == [level])["aggregates"]["ProductionLeadTimeDays"]
            assert got == pytest.approx(float(want)), fn
        assert expected["avg_nonzero"] != expected["avg"]  # sıfır gerçekten fark yaratıyor
    finally:
        with db_engine.begin() as conn:
            conn.execute(text("UPDATE core.Material SET ProductionLeadTimeDays = 2 WHERE Code = 'ALT-001' AND VersionTo IS NULL"))
            conn.execute(text(f"UPDATE core.Material SET MaxStock = NULL WHERE {where}"))


@needs_db
def test_weighted_average_with_empty_weight_is_empty(api):
    t = groups(api, group_by=["MaterialLevel"], aggregates={"ProductionLeadTimeDays": {"fn": "wavg", "weight": "MaxStock"}})
    assert all(g["aggregates"]["ProductionLeadTimeDays"] is None for g in t["groups"])  # MaxStock hep boş
    assert t["aggregate_specs"] == {"ProductionLeadTimeDays": {"fn": "wavg", "weight": "MaxStock"}}


@needs_db
def test_default_aggregates_come_from_list_definition(api):
    t = groups(api, group_by=["MaterialLevel"], fields=["Code", "SafetyStock", "ProductionLeadTimeDays"])
    assert t["aggregate_specs"] == {"SafetyStock": {"fn": "sum"}, "ProductionLeadTimeDays": {"fn": "avg"}}
    t = groups(api, group_by=["MaterialLevel"], aggregates={"SafetyStock": {"fn": "none"}})
    assert t["aggregate_specs"] == {} and t["groups"][0]["aggregates"] == {}


@needs_db
@pytest.mark.parametrize("aggregates, field", [
    ({"Name": {"fn": "sum"}}, "aggregates.Name"),
    ({"SafetyStock": {"fn": "wavg"}}, "aggregates.SafetyStock.weight"),
    ({"SafetyStock": {"fn": "wavg", "weight": "Name"}}, "aggregates.SafetyStock.weight"),
    ({"SafetyStock": {"fn": "wavg", "weight": "SafetyStock"}}, "aggregates.SafetyStock.weight"),
])
def test_invalid_aggregates(api, aggregates, field):
    r = api.post("/api/materials/groups", json={"group_by": ["MaterialLevel"], "aggregates": aggregates})
    assert r.status_code == 422 and r.json()["error"]["details"][0]["field"] == field
    assert api.post("/api/materials/groups", json={"group_by": ["MaterialLevel"],
                                                   "aggregates": {"SafetyStock": {"fn": "median"}}}).status_code == 422
