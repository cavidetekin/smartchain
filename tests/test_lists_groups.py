"""Gruplama ve ara toplam (K-90), boş değer filtresi (U-13): birim testleri ve sentetik v0 ile veritabanı testleri."""
import pytest
from sqlalchemy import text

from app.api.lists.groups import build_tree

from test_lists_api import all_rows, api, query  # noqa: F401  (fikstür ve yardımcılar)


def leaf(g, n, s=None, c=0, unit=None):
    return {**{f"g{i}": v for i, v in enumerate(g)}, "n": n, "s_Q": s, "c_Q": c, "u": unit, "s_D": s, "c_D": c}


# --- birim: ağaç ve ara toplamlar -------------------------------------------------------------------------------

def test_tree_sums_weighted_average_and_mixed_units():
    leaves = [leaf(["A", "x"], 2, 10, 2, "ADET"), leaf(["A", "y"], 3, 6, 1, "KG"), leaf(["B", None], 1, None, 0, "KG")]
    t = build_tree(leaves, 2, {"Q": "sum", "D": "avg"}, {"Q"})
    a, b = t["groups"]
    assert (a["key"], a["count"], b["key"], b["count"]) == (["A"], 5, ["B"], 1)
    assert [ch["key"] for ch in a["children"]] == [["A", "x"], ["A", "y"]]
    assert a["children"][0]["aggregates"] == {"Q": 10.0, "D": 5.0}
    assert a["aggregates"] == {"Q": None, "D": 16 / 3} and a["mixed_units"] == ["Q"]  # ADET + KG: toplam yok
    assert a["children"][0]["unit_decimals"] == {"Q": 2}  # birim ondalığı verilmedi: 2
    assert b["aggregates"] == {"Q": None, "D": None} and b["children"][0]["key"] == ["B", None]
    assert t["aggregates"]["D"] == 16 / 3 and t["leaf_groups"] == 3


def test_unit_level_rows_merge_into_one_group():
    """Birim gizli düzey: aynı grup iki birimde iki satır gelir, tek grup olur; değersiz birim karışıklık sayılmaz."""
    leaves = [leaf(["A"], 2, 10, 2, "ADET"), leaf(["A"], 3, None, 0, "KG"), leaf(["B"], 1, 4, 1, "ADET"),
              leaf(["B"], 1, 1.5, 1, "KG")]
    t = build_tree(leaves, 1, {"Q": "sum"}, {"Q"})
    a, b = t["groups"]
    assert (a["count"], a["aggregates"]["Q"], a["mixed_units"]) == (5, 10.0, [])
    assert build_tree(leaves, 1, {"Q": "sum"}, {"Q"}, unit_decimals={"ADET": 0})["groups"][0]["unit_decimals"] == {"Q": 0}
    assert (b["count"], b["aggregates"]["Q"], b["mixed_units"]) == (2, None, ["Q"])
    assert t["leaf_groups"] == 2


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
