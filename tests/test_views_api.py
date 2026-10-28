"""Kayıtlı görünümler (K-89): veritabanıyla. Geçici ikinci kullanıcı ve "pytest " önekli görünümler temizlenir."""
from datetime import date, timedelta, timezone

import pytest
from sqlalchemy import text

from app.api.services import lists as list_service

from test_lists_api import api, query  # noqa: F401

pytestmark = pytest.mark.db

DEFINITION = {"columns": [{"field": "Code", "width": 8}, {"field": "Name"}], "pinned": 1,
              "sort": [{"field": "Code", "dir": "desc"}], "filters": [], "group_by": ["MaterialLevel"]}


@pytest.fixture
def users(db_engine):
    """Kullanıcı 3 (demo) ve geçici ikinci kullanıcı; görünümler sonra temizlenir."""
    def clean(conn):
        conn.execute(text("DELETE d FROM adm.TableViewDefault d JOIN adm.TableView v ON v.Id = d.ViewId "
                          "WHERE v.Name LIKE N'pytest %'"))
        conn.execute(text("DELETE FROM adm.TableViewDefault WHERE UserId IN (SELECT Id FROM adm.AppUser WHERE UserName = 'pytest-ikinci')"))
        conn.execute(text("DELETE FROM adm.TableView WHERE Name LIKE N'pytest %'"))
        conn.execute(text("DELETE FROM adm.AppUser WHERE UserName = 'pytest-ikinci'"))
    with db_engine.begin() as conn:
        clean(conn)
        other = conn.execute(text("INSERT INTO adm.AppUser (UserName, FullName, Role, PasswordHash) OUTPUT inserted.Id "
                                  "VALUES ('pytest-ikinci', N'İkinci Kullanıcı', 'End user', 0x00)")).scalar_one()
    yield 3, other
    with db_engine.begin() as conn:
        clean(conn)


def create(api, user, name, definition=DEFINITION, shared=False):
    r = api.post(f"/api/materials/views?user_id={user}", json={"name": name, "is_shared": shared, "definition": definition})
    assert r.status_code == 201, r.text
    return r.json()


def listed(api, user):
    return api.get(f"/api/materials/views?user_id={user}").json()


def test_create_update_delete(api, users):
    me, _ = users
    v = create(api, me, "pytest A")
    assert v["definition"] == {"v": 1, **{**DEFINITION, "columns": [{"field": "Code", "width": 8.0}, {"field": "Name"}]},
                               "aggregates": {}}
    assert v["is_owner"] and v["warnings"] == []
    r = api.put(f"/api/materials/views/{v['id']}?user_id={me}", json={"name": "pytest B", "is_shared": True})
    assert r.status_code == 200 and (r.json()["name"], r.json()["is_shared"]) == ("pytest B", True)
    assert api.delete(f"/api/materials/views/{v['id']}?user_id={me}").status_code == 204
    assert all(x["id"] != v["id"] for x in listed(api, me)["views"])


def test_name_taken_and_not_owner(api, users):
    me, other = users
    v = create(api, me, "pytest Ad", shared=True)
    r = api.post(f"/api/materials/views?user_id={me}", json={"name": "pytest Ad", "definition": DEFINITION})
    assert r.status_code == 409 and r.json()["error"]["code"] == "view_name_taken"
    create(api, other, "pytest Ad")  # başka kullanıcı aynı adı kullanabilir
    for call in (lambda: api.put(f"/api/materials/views/{v['id']}?user_id={other}", json={"name": "pytest X"}),
                 lambda: api.delete(f"/api/materials/views/{v['id']}?user_id={other}")):
        r = call()
        assert r.status_code == 403 and r.json()["error"]["code"] == "view_not_owner"
    assert api.get("/api/materials/views?user_id=987654").status_code == 404


def test_shared_visible_to_others_personal_not(api, users):
    me, other = users
    create(api, me, "pytest Kişisel")
    shared = create(api, me, "pytest Paylaşılan", shared=True)
    seen = {x["name"]: x for x in listed(api, other)["views"]}
    assert "pytest Kişisel" not in seen
    assert seen["pytest Paylaşılan"]["is_owner"] is False and seen["pytest Paylaşılan"]["owner_name"]
    assert seen["pytest Paylaşılan"]["id"] == shared["id"]


def test_default_view(api, users):
    me, other = users
    v = create(api, me, "pytest Varsayılan", shared=True)
    assert api.put(f"/api/materials/views/default?user_id={other}", json={"view_id": v["id"]}).status_code == 200
    assert listed(api, other)["default_view_id"] == v["id"]
    assert api.put(f"/api/materials/views/default?user_id={other}", json={"view_id": None}).status_code == 200
    assert listed(api, other)["default_view_id"] is None
    personal = create(api, me, "pytest Gizli")
    r = api.put(f"/api/materials/views/default?user_id={other}", json={"view_id": personal["id"]})
    assert r.status_code == 404  # başkasının kişisel görünümü seçilemez
    api.put(f"/api/materials/views/default?user_id={me}", json={"view_id": v["id"]})
    api.delete(f"/api/materials/views/{v['id']}?user_id={me}")
    assert listed(api, me)["default_view_id"] is None  # silinince varsayılan Standart'a döner


@pytest.mark.parametrize("definition, field", [
    ({"columns": [{"field": "Nope"}]}, "definition.columns.0.field"),
    ({"columns": [{"field": "Code"}], "pinned": 2}, "definition.pinned"),
    ({"columns": [{"field": "Code"}], "sort": [{"field": "Nope"}]}, "definition.sort.0.field"),
    ({"columns": [{"field": "Code"}], "filters": [{"field": "Name", "op": "gt", "value": 1}]}, "definition.filters.0.op"),
    ({"columns": [{"field": "Code"}], "group_by": ["Nope"]}, "definition.group_by.0"),
    ({"columns": [{"field": "Code"}], "aggregates": {"Name": {"fn": "sum"}}}, "definition.aggregates.Name"),
    ({"columns": [{"field": "Code"}], "aggregates": {"SafetyStock": {"fn": "wavg"}}}, "definition.aggregates.SafetyStock.weight"),
])
def test_invalid_definition(api, users, definition, field):
    r = api.post(f"/api/materials/views?user_id={users[0]}", json={"name": "pytest Bozuk", "definition": definition})
    assert r.status_code == 422 and r.json()["error"]["details"][0]["field"] == field


def test_removed_field_is_dropped_with_warning(api, users, db_engine):
    v = create(api, users[0], "pytest Eski")
    raw = ('{"v": 1, "columns": [{"field": "Code"}, {"field": "OldField"}], "pinned": 2, '
           '"sort": [{"field": "OldField", "dir": "asc"}], "filters": [{"field": "OldField", "op": "empty"}], "group_by": []}')
    with db_engine.begin() as conn:
        conn.execute(text("UPDATE adm.TableView SET Definition = :d WHERE Id = :i"), {"d": raw, "i": v["id"]})
    got = next(x for x in listed(api, users[0])["views"] if x["id"] == v["id"])
    assert got["definition"]["columns"] == [{"field": "Code"}] and got["definition"]["pinned"] == 1
    assert got["definition"]["sort"] == [] and got["definition"]["filters"] == []
    assert got["warnings"] == ["'OldField' alanı artık listede yok; görünümden çıkarıldı."]


def test_relative_date_filter_is_stored_relative(api, users, db_engine, monkeypatch):
    """K-89: "bu hafta" tarih olarak değil göreli saklanır; görünüm başka hafta açılınca o haftaya göre çalışır."""
    flt = {"field": "UpdatedAt", "op": "relative", "value": "this_week"}
    v = create(api, users[0], "pytest Bu hafta", {**DEFINITION, "filters": [flt]})
    with db_engine.connect() as conn:
        stored = conn.execute(text("SELECT Definition FROM adm.TableView WHERE Id = :i"), {"i": v["id"]}).scalar_one()
        updated = conn.execute(text("SELECT MAX(UpdatedAt) FROM core.Material WHERE VersionTo IS NULL")).scalar_one()
    assert '"op": "relative"' in stored and '"this_week"' in stored
    assert str(date.today().year) not in stored  # tarih yok
    filters = next(x for x in listed(api, users[0])["views"] if x["id"] == v["id"])["definition"]["filters"]
    load_day = updated.replace(tzinfo=timezone.utc).astimezone().date()
    monkeypatch.setattr(list_service, "today", lambda: load_day)
    assert query(api, filters=filters)["filtered"] == 200
    monkeypatch.setattr(list_service, "today", lambda: load_day + timedelta(weeks=3))
    assert query(api, filters=filters)["filtered"] == 0


def test_aggregate_choice_is_saved_with_view(api, users):
    agg = {"ProductionLeadTimeDays": {"fn": "wavg", "weight": "SafetyStock"}, "SafetyStock": {"fn": "max"}}
    v = create(api, users[0], "pytest Ara toplam", {**DEFINITION, "aggregates": agg})
    assert v["definition"]["aggregates"] == agg
    got = next(x for x in listed(api, users[0])["views"] if x["id"] == v["id"])
    assert got["definition"]["aggregates"] == agg


def test_views_are_per_list(api, users):
    v = create(api, users[0], "pytest Liste")
    assert api.put(f"/api/othername/views/{v['id']}?user_id={users[0]}", json={"name": "x"}).status_code == 404
