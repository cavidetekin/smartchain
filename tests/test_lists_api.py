"""Liste sorgusu (K-87) yerel SQL Server'da, sentetik v0 ile (docs/11; `python -m app.data.synthetic load`)."""
from datetime import timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.api.db import get_session
from app.api.main import create_app
from app.api.services import lists as service

pytestmark = pytest.mark.db


@pytest.fixture(scope="module")
def api(db_engine):
    with db_engine.connect() as conn:
        synthetic, count = conn.execute(text(
            "SELECT TOP 1 v.IsSynthetic, (SELECT COUNT(*) FROM core.Material m WHERE m.VersionFrom <= v.Id "
            "AND (m.VersionTo IS NULL OR m.VersionTo >= v.Id)) FROM adm.DataVersion v ORDER BY v.Id DESC")).one()
    if not synthetic or count != 200:
        pytest.skip("Sentetik v0 yüklü değil (python -m app.data.synthetic load)")
    return TestClient(create_app(), raise_server_exceptions=False)


def query(api, **body):
    r = api.post("/api/materials/query", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def test_columns_include_labelled_additional_field(api):
    cols = {c["field"]: c for c in api.get("/api/materials/columns").json()}
    assert cols["AdditionalText1"]["label"] == "Malzeme sınıfı"
    assert "AdditionalText2" not in cols
    assert cols["MaterialLevel"]["label"] == "Malzeme seviyesi"


def test_counts_and_chunks_cover_all_rows_once(api):
    seen = []
    for offset in range(0, 200, 70):
        body = query(api, fields=["Code"], offset=offset, limit=70)
        assert (body["total"], body["filtered"], body["offset"]) == (200, 200, offset)
        seen += [r["Code"] for r in body["rows"]]
    assert len(seen) == len(set(seen)) == 200
    assert seen == sorted(seen)


def test_multi_sort(api):
    rows = query(api, fields=["Code", "MaterialLevel"], limit=500,
                 sort=[{"field": "MaterialLevel", "dir": "asc"}, {"field": "Code", "dir": "desc"}])["rows"]
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
    body = query(api, filters=[flt], limit=500)
    if expected is not None:
        assert body["filtered"] == expected
    assert body["total"] == 200 and len(body["rows"]) == body["filtered"]


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


def test_validation_errors(api):
    r = api.post("/api/materials/query", json={"filters": [{"field": "Secret", "op": "equals", "value": "x"}]})
    assert r.status_code == 422
    body = r.json()["error"]
    assert body["code"] == "validation" and body["details"][0]["field"] == "filters.0.field"
    assert api.post("/api/materials/query", json={"limit": 501}).json()["error"]["details"][0]["field"] == "body.limit"


def test_database_unavailable_is_503():
    app = create_app()
    app.dependency_overrides[get_session] = lambda: None
    r = TestClient(app, raise_server_exceptions=False).post("/api/materials/query", json={})
    assert r.status_code == 503 and r.json()["error"]["code"] == "database_unavailable"
