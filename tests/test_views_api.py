"""Kayıtlı görünümler (K-89): veritabanıyla. Geçici ikinci kullanıcı ve "pytest " önekli görünümler temizlenir."""
import json
from datetime import date, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.api.main import create_app
from app.api.services import lists as list_service

from test_lists_api import api, query  # noqa: F401
from auth_helpers import auth, delete_users, ensure_user

pytestmark = pytest.mark.db

DEFINITION = {"columns": [{"field": "Code", "width": 8}, {"field": "Name"}], "pinned": 1,
              "sort": [{"field": "Code", "dir": "desc"}], "filters": [], "group_by": ["MaterialLevel"]}


@pytest.fixture
def users(db_engine, test_users):
    """İlk deneme kullanıcısı (api istemcisinin oturumu) ve geçici ikinci kullanıcı; görünümler sonra temizlenir."""
    def clean(conn):
        conn.execute(text("DELETE d FROM adm.TableViewDefault d JOIN adm.TableView v ON v.Id = d.ViewId "
                          "WHERE v.Name LIKE N'pytest %'"))
        conn.execute(text("DELETE FROM adm.TableViewDefault WHERE UserId IN (SELECT Id FROM adm.AppUser WHERE UserName = 'pytest-ikinci')"))
        conn.execute(text("DELETE FROM adm.TableView WHERE Name LIKE N'pytest %'"))
        delete_users(conn, [r[0] for r in conn.execute(text("SELECT Id FROM adm.AppUser WHERE UserName = 'pytest-ikinci'"))])
    with db_engine.begin() as conn:
        clean(conn)
        other = ensure_user(conn, "pytest-ikinci", "End user", "İkinci Kullanıcı")
    yield test_users[0], other
    with db_engine.begin() as conn:
        clean(conn)


def create(api, user, name, definition=DEFINITION, shared=False):
    r = api.post("/api/materials/views", headers=auth(user), json={"name": name, "is_shared": shared, "definition": definition})
    assert r.status_code == 201, r.text
    return r.json()


def listed(api, user):
    return api.get("/api/materials/views", headers=auth(user)).json()


def test_create_update_delete(api, users):
    me, _ = users
    v = create(api, me, "pytest A")
    assert v["definition"] == {"v": 1, **{**DEFINITION, "columns": [{"field": "Code", "width": 8.0}, {"field": "Name"}]},
                               "aggregates": {}, "rules": []}
    assert v["is_owner"] and v["warnings"] == []
    r = api.put(f"/api/materials/views/{v['id']}", headers=auth(me), json={"name": "pytest B", "is_shared": True})
    assert r.status_code == 200 and (r.json()["name"], r.json()["is_shared"]) == ("pytest B", True)
    assert api.delete(f"/api/materials/views/{v['id']}", headers=auth(me)).status_code == 204
    assert all(x["id"] != v["id"] for x in listed(api, me)["views"])


def test_name_taken_and_not_owner(api, users):
    me, other = users
    v = create(api, me, "pytest Ad", shared=True)
    r = api.post("/api/materials/views", headers=auth(me), json={"name": "pytest Ad", "definition": DEFINITION})
    assert r.status_code == 409 and r.json()["error"]["code"] == "view_name_taken"
    create(api, other, "pytest Ad")  # başka kullanıcı aynı adı kullanabilir
    for call in (lambda: api.put(f"/api/materials/views/{v['id']}", headers=auth(other), json={"name": "pytest X"}),
                 lambda: api.delete(f"/api/materials/views/{v['id']}", headers=auth(other))):
        r = call()
        assert r.status_code == 403 and r.json()["error"]["code"] == "view_not_owner"
    r = TestClient(create_app()).get("/api/materials/views")  # oturumsuz istek (K-97)
    assert r.status_code == 401 and r.json()["error"]["code"] == "not_authenticated"


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
    assert api.put("/api/materials/views/default", headers=auth(other), json={"view_id": v["id"]}).status_code == 200
    assert listed(api, other)["default_view_id"] == v["id"]
    assert api.put("/api/materials/views/default", headers=auth(other), json={"view_id": None}).status_code == 200
    assert listed(api, other)["default_view_id"] is None
    personal = create(api, me, "pytest Gizli")
    r = api.put("/api/materials/views/default", headers=auth(other), json={"view_id": personal["id"]})
    assert r.status_code == 404  # başkasının kişisel görünümü seçilemez
    api.put("/api/materials/views/default", headers=auth(me), json={"view_id": v["id"]})
    api.delete(f"/api/materials/views/{v['id']}", headers=auth(me))
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
    r = api.post("/api/materials/views", headers=auth(users[0]), json={"name": "pytest Bozuk", "definition": definition})
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
    assert got["warnings"] == ["'OldField' artık listede yok; görünümden çıkarıldı."]


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
    agg = {"StockCoverageDays": {"fn": "wavg", "weight": "SafetyStock"}, "SafetyStock": {"fn": "max"}}
    v = create(api, users[0], "pytest Ara toplam", {**DEFINITION, "aggregates": agg})
    assert v["definition"]["aggregates"] == agg
    got = next(x for x in listed(api, users[0])["views"] if x["id"] == v["id"])
    assert got["definition"]["aggregates"] == agg


def test_views_are_per_list(api, users):
    v = create(api, users[0], "pytest Liste")
    assert api.put(f"/api/othername/views/{v['id']}", headers=auth(users[0]), json={"name": "x"}).status_code == 404


# --- Şirket Standart'ı (K-162) ---

@pytest.fixture
def roles(db_engine):
    """Admin, Key user ve End user; şirket Standart'ı ve onların varsayılanları sonra temizlenir."""
    names = {"Admin": "pytest-std-admin", "Key user": "pytest-std-key", "End user": "pytest-std-end"}

    def clean(conn):
        conn.execute(text("DELETE FROM adm.TableViewStandard WHERE ListName = N'materials'"))
        ids = [r[0] for r in conn.execute(text("SELECT Id FROM adm.AppUser WHERE UserName LIKE 'pytest-std-%'"))]
        if ids:
            conn.execute(text(f"DELETE FROM adm.TableViewDefault WHERE UserId IN ({','.join(map(str, ids))})"))
            conn.execute(text(f"DELETE FROM adm.TableView WHERE OwnerUserId IN ({','.join(map(str, ids))})"))
        delete_users(conn, ids)
    with db_engine.begin() as conn:
        clean(conn)
        out = {role: ensure_user(conn, name, role, f"Ad {role}") for role, name in names.items()}
    yield out
    with db_engine.begin() as conn:
        clean(conn)


STANDARD = {"columns": [{"field": "Name", "width": 12}, {"field": "Code"}, {"field": "MaterialGroup"}], "pinned": 0, "sort": [], "filters": [], "group_by": []}


def test_company_standard_saved_by_admin_opens_for_everyone_without_default(api, roles, db_engine):
    admin, key, end = roles["Admin"], roles["Key user"], roles["End user"]
    before = listed(api, end)
    assert before["standard"] is None and before["can_edit_standard"] is False and listed(api, admin)["can_edit_standard"] is True
    for user in (key, end):
        r = api.put("/api/materials/views/standard", headers=auth(user), json={"definition": STANDARD})
        assert r.status_code == 403 and r.json()["error"]["code"] == "view_standard_forbidden"
    r = api.put("/api/materials/views/standard", headers=auth(admin), json={"definition": STANDARD})
    assert r.status_code == 200, r.text
    got = listed(api, end)
    assert [c["field"] for c in got["standard"]["definition"]["columns"]] == ["Name", "Code", "MaterialGroup"]
    assert got["standard"]["updated_by_name"] == "Ad Admin" and got["default_view_id"] is None
    own = create(api, end, "pytest kendi")                                                   # kendi varsayılanı olan: onunki açılır
    api.put("/api/materials/views/default", headers=auth(end), json={"view_id": own["id"]})
    assert listed(api, end)["default_view_id"] == own["id"]
    with db_engine.connect() as c:
        actions = [r[0] for r in c.execute(text("SELECT Action FROM adm.AuditLog WHERE ObjectKey = N'materials · Standart' ORDER BY Id"))]
    assert actions[-1] == "Standart görünüm değiştirildi"


def test_fields_added_later_follow_product_default_and_hidden_stay_hidden(api, roles, db_engine):
    admin = roles["Admin"]
    api.put("/api/materials/views/standard", headers=auth(admin), json={"definition": STANDARD})
    with db_engine.begin() as c:   # ürün güncellemesini taklit: MaterialLevel (varsayılan görünür) ve Brand (varsayılan gizli) kayıt anında yokmuş
        known = [f for f in api.get("/api/materials/columns", headers=auth(admin)).json()["columns"]]
        names = [k["field"] for k in known if k["field"] not in ("MaterialLevel", "Brand")]
        c.execute(text("UPDATE adm.TableViewStandard SET KnownFields = :k WHERE ListName = N'materials'"), {"k": json.dumps(names)})
    fields = [c["field"] for c in listed(api, admin)["standard"]["definition"]["columns"]]
    assert fields[:3] == ["Name", "Code", "MaterialGroup"] and "MaterialLevel" in fields      # yeni ve varsayılan görünür: eklendi
    assert "Brand" not in fields and "BaseUom" not in fields                                   # yeni ama gizli; Standart'ta gizlenmiş: gizli kalır


def test_reset_to_product_standard(api, roles, db_engine):
    admin, key = roles["Admin"], roles["Key user"]
    api.put("/api/materials/views/standard", headers=auth(admin), json={"definition": STANDARD})
    assert api.delete("/api/materials/views/standard", headers=auth(key)).status_code == 403
    assert api.delete("/api/materials/views/standard", headers=auth(admin)).status_code == 204
    assert listed(api, key)["standard"] is None
    with db_engine.connect() as c:
        last = c.execute(text("SELECT TOP 1 Action FROM adm.AuditLog WHERE ObjectKey = N'materials · Standart' ORDER BY Id DESC")).scalar()
    assert last == "Standart görünüm ürün hâline döndü"
