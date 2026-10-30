"""Liste sorgusu (K-87) yerel SQL Server'da, sentetik v0 ile (docs/11; `python -m app.data.synthetic load`)."""
from datetime import timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.api.db import get_session
from app.api.deps import COOKIE, session_user
from app.api.main import create_app
from app.api.services import lists as service

from auth_helpers import token
from conftest import FAKE_USER

pytestmark = pytest.mark.db


@pytest.fixture(scope="module")
def api(db_engine, test_users):
    """Sentetik v0 üzerinde API istemcisi; ilk deneme kullanıcısının oturumuyla (başka kullanıcı: headers=auth(id))."""
    with db_engine.connect() as conn:
        synthetic, count = conn.execute(text(
            "SELECT TOP 1 v.IsSynthetic, (SELECT COUNT(*) FROM core.Material m WHERE m.VersionFrom <= v.Id "
            "AND (m.VersionTo IS NULL OR m.VersionTo >= v.Id)) FROM adm.DataVersion v ORDER BY v.Id DESC")).one()
    if not synthetic or count != 200:
        pytest.skip("Sentetik v0 yüklü değil (python -m app.data.synthetic load)")
    client = TestClient(create_app(), raise_server_exceptions=False)
    client.cookies.set(COOKIE, token(test_users[0]))
    return client


def query(api, **body):
    r = api.post("/api/materials/query", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def all_rows(api, **body) -> list[dict]:
    """Bütün satırlar, parça parça (ListChunkSize)."""
    rows, offset = [], 0
    while True:
        page = query(api, **body, offset=offset)
        rows += page["rows"]
        offset += len(page["rows"])
        if not page["rows"] or offset >= page["filtered"]:
            return rows


def test_columns_include_labelled_additional_field(api):
    body = api.get("/api/materials/columns").json()
    assert body["chunk_size"] == 100
    cols = {c["field"]: c for c in body["columns"]}
    assert (cols["ProductionLeadTimeDays"]["decimals"], cols["SafetyStock"]["decimals"]) == (0, None)
    assert cols["SafetyStock"]["decimals_from_unit"] is True
    assert cols["AdditionalText1"]["label"] == "Malzeme sınıfı"
    assert "AdditionalText2" not in cols
    assert cols["MaterialLevel"]["label"] == "Malzeme seviyesi"


def test_rows_carry_unit_decimals(api, db_engine):
    rows = {r["Code"]: r for r in all_rows(api, fields=["Code", "BaseUom"])}
    assert {r["_unit_decimals"] for r in rows.values() if r["BaseUom"] == "ADET"} == {0}
    assert {r["_unit_decimals"] for r in rows.values() if r["BaseUom"] == "KG"} == {3}
    try:  # Smartchain'de değiştirilen ondalık hemen yansır; bilinmeyen birim 2
        with db_engine.begin() as conn:
            conn.execute(text("UPDATE core.UnitOfMeasure SET Decimals = NULL WHERE Code = 'KG'"))
        assert query(api, fields=["Code"], filters=[{"field": "BaseUom", "op": "in", "values": ["KG"]}])["rows"][0]["_unit_decimals"] == 2
    finally:
        with db_engine.begin() as conn:
            conn.execute(text("UPDATE core.UnitOfMeasure SET Decimals = 3 WHERE Code = 'KG'"))


def test_counts_and_chunks_cover_all_rows_once(api):
    seen = []
    for offset in range(0, 200, 70):
        body = query(api, fields=["Code"], offset=offset, limit=70)
        assert (body["total"], body["filtered"], body["offset"]) == (200, 200, offset)
        seen += [r["Code"] for r in body["rows"]]
    assert len(seen) == len(set(seen)) == 200
    assert seen == sorted(seen)


def test_multi_sort(api):
    rows = all_rows(api, fields=["Code", "MaterialLevel"],
                    sort=[{"field": "MaterialLevel", "dir": "asc"}, {"field": "Code", "dir": "desc"}])
    assert len(rows) == 200
    levels = [r["MaterialLevel"] for r in rows]
    assert levels == sorted(levels, key=["Hammadde", "Nihai ürün", "Yarı mamul"].index)
    ham = [r["Code"] for r in rows if r["MaterialLevel"] == "Hammadde"]
    assert ham == sorted(ham, reverse=True)


def test_turkish_sort_and_case_insensitive_search(api):
    groups = [v["value"] for v in api.post("/api/materials/values", json={"field": "MaterialGroup"}).json()]
    assert groups.index("Conta") < groups.index("Çubuk") < groups.index("Dövme")
    assert groups.index("Bağlantı") < groups.index("İşlenmiş parça") < groups.index("Levha")
    upper = query(api, filters=[{"field": "Name", "op": "contains", "value": "ÇELİK"}])
    lower = query(api, filters=[{"field": "Name", "op": "contains", "value": "çelik"}])
    assert upper["filtered"] == lower["filtered"] == 20


@pytest.mark.parametrize("flt, expected", [
    ({"field": "Name", "op": "starts_with", "value": "rulman"}, 6),
    ({"field": "Name", "op": "equals", "value": "rulman 6204-2rs"}, 1),
    ({"field": "MaterialLevel", "op": "in", "values": ["Nihai ürün", "Yarı mamul"]}, 120),
    ({"field": "IsSellable", "op": "in", "values": [True]}, 10),
    ({"field": "AdditionalText1", "op": "equals", "value": "a"}, 10),
    ({"field": "SafetyStock", "op": "eq", "value": 20}, 6),
    ({"field": "SafetyStock", "op": "gt", "value": 0}, 6),
    ({"field": "ProductionLeadTimeDays", "op": "lt", "value": 3}, None),
])
def test_filter_operators(api, flt, expected):
    body = query(api, filters=[flt])
    if expected is not None:
        assert body["filtered"] == expected
    assert body["total"] == 200 and len(body["rows"]) == min(body["filtered"], 100)
    assert len(all_rows(api, filters=[flt])) == body["filtered"]


def test_not_contains_is_complement_of_contains(api):
    flt = {"field": "Code", "op": "contains", "value": "-01"}
    hit = query(api, filters=[flt])["filtered"]
    miss = query(api, filters=[{**flt, "op": "not_contains"}])["filtered"]
    assert 0 < hit < 200 and hit + miss == 200


def test_number_range_matches_database(api, db_engine):
    with db_engine.connect() as conn:
        expected = conn.execute(text("SELECT COUNT(*) FROM core.Material WHERE VersionTo IS NULL "
                                     "AND MinLot BETWEEN 50 AND 100")).scalar_one()
    assert expected > 0
    assert query(api, filters=[{"field": "MinLot", "op": "between", "min": 50, "max": 100}])["filtered"] == expected
    assert query(api, filters=[{"field": "MinLot", "op": "between", "min": 50}])["filtered"] == expected


def test_filters_combine(api):
    body = query(api, filters=[{"field": "MaterialLevel", "op": "in", "values": ["Hammadde"]},
                               {"field": "Name", "op": "contains", "value": "rulman"}])
    assert body["filtered"] == 6


def test_like_wildcards_are_literal(api):
    for value in ("%", "_", "[", "'"):
        assert query(api, filters=[{"field": "Code", "op": "contains", "value": value}])["filtered"] == 0


def test_date_filters(api, db_engine, monkeypatch):
    with db_engine.connect() as conn:
        updated = conn.execute(text("SELECT MAX(UpdatedAt) FROM core.Material WHERE VersionTo IS NULL")).scalar_one()
    local_day = updated.replace(tzinfo=timezone.utc).astimezone().date()
    day = local_day.isoformat()
    assert query(api, filters=[{"field": "UpdatedAt", "op": "between", "from": day, "to": day}])["filtered"] == 200
    nxt = (local_day + timedelta(days=1)).isoformat()
    assert query(api, filters=[{"field": "UpdatedAt", "op": "between", "from": nxt}])["filtered"] == 0

    def relative(value, today):
        monkeypatch.setattr(service, "today", lambda: today)
        return query(api, filters=[{"field": "UpdatedAt", "op": "relative", "value": value}])["filtered"]

    assert relative("this_week", local_day) == 200
    assert relative("this_week", local_day + timedelta(weeks=2)) == 0
    assert relative("next_4_weeks", local_day - timedelta(weeks=3)) == 200
    assert relative("next_4_weeks", local_day - timedelta(weeks=5)) == 0


def test_values_with_search_and_other_filters(api):
    r = api.post("/api/materials/values", json={
        "field": "MaterialGroup", "search": "ç",
        "filters": [{"field": "MaterialGroup", "op": "in", "values": ["Rulman"]},  # kendi filtresi uygulanmaz
                    {"field": "MaterialLevel", "op": "in", "values": ["Hammadde"]}]})
    assert r.status_code == 200
    assert r.json() == [{"value": "Çubuk", "count": 20}]
    assert api.post("/api/materials/values", json={"field": "Name"}).status_code == 422


def test_chunk_size_comes_from_system_setting(api, db_engine):
    assert len(query(api)["rows"]) == 100  # limit boş: ListChunkSize
    r = api.post("/api/materials/query", json={"limit": 101})
    assert r.status_code == 422 and r.json()["error"]["details"][0]["field"] == "body.limit"
    try:
        with db_engine.begin() as conn:
            conn.execute(text("INSERT INTO adm.SystemSetting (SettingKey, Value) VALUES ('ListChunkSize', '150')"))
        assert api.get("/api/materials/columns").json()["chunk_size"] == 150
        assert len(query(api)["rows"]) == 150
        with db_engine.begin() as conn:
            conn.execute(text("UPDATE adm.SystemSetting SET Value = '900' WHERE SettingKey = 'ListChunkSize'"))
        assert api.get("/api/materials/columns").json()["chunk_size"] == 500  # en çok 500
    finally:
        with db_engine.begin() as conn:
            conn.execute(text("DELETE FROM adm.SystemSetting WHERE SettingKey = 'ListChunkSize'"))


def test_validation_errors(api):
    r = api.post("/api/materials/query", json={"filters": [{"field": "Secret", "op": "equals", "value": "x"}]})
    assert r.status_code == 422
    body = r.json()["error"]
    assert body["code"] == "validation" and body["details"][0]["field"] == "filters.0.field"
    assert api.post("/api/materials/query", json={"limit": 501}).json()["error"]["details"][0]["field"] == "body.limit"


def test_database_unavailable_is_503():
    app = create_app()
    app.dependency_overrides[get_session] = lambda: None
    app.dependency_overrides[session_user] = lambda: FAKE_USER  # oturum denetimi ayrı; burada uç noktanın 503'ü
    r = TestClient(app, raise_server_exceptions=False).post("/api/materials/query", json={})
    assert r.status_code == 503 and r.json()["error"]["code"] == "database_unavailable"
