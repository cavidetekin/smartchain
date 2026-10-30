"""Rol bazlı yetki uçtan uca (fonksiyon 90; K-99, K-100): dört rol, bugünkü uç noktalar, 403 ve iz, rol değişikliği,
bozuk rol, nesne bağlamı. Sentetik v0 gerekir (liste uçları)."""
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.api.main import create_app
from app.api.permissions import ADMIN, END_USER, KEY_USER, ROLES, SYSTEM_OWNER
from app.jobs import queue
from app.jobs.constants import CHANNEL_INTERACTIVE, TYPE_WORKSPACE

from auth_helpers import auth, delete_users, ensure_user
from test_lists_api import api  # noqa: F401  (fikstür)

pytestmark = pytest.mark.db

PREFIX = "pytest.yetki."


@pytest.fixture
def roles(db_engine, clean_jobs):
    """Her rolden bir şifresiz deneme hesabı: rol → kullanıcı Id."""
    def clean():
        with db_engine.begin() as c:
            ids = [r[0] for r in c.execute(text("SELECT Id FROM adm.AppUser WHERE UserName LIKE :p"), {"p": PREFIX + "%"})]
            delete_users(c, ids)
    clean()
    with db_engine.begin() as c:
        out = {role: ensure_user(c, PREFIX + role.replace(" ", "-").lower(), role) for role in ROLES}
    yield out
    clean()


def audits(db_engine, user_id, action):
    with db_engine.connect() as c:
        return [json.loads(v) if v else None for (v,) in c.execute(text(
            "SELECT NewValue FROM adm.AuditLog WHERE UserId = :u AND Action = :a ORDER BY Id"), {"u": user_id, "a": action})]


@pytest.mark.parametrize("role", ROLES)
def test_reporting_is_open_to_every_role(api, roles, role):  # noqa: F811
    """K-99: liste, görünüm kaydetme, koşullu biçim ve Excel'e aktarım End user dahil herkese açık."""
    h = auth(roles[role])
    rule = {"field": "Name", "condition": {"op": "contains", "value": "mil"}}
    assert api.get("/api/materials/columns", headers=h).status_code == 200
    r = api.post("/api/materials/query", headers=h, json={"limit": 5, "rules": [rule]})
    assert r.status_code == 200 and r.headers["X-Smartchain-Role"] == role
    r = api.post("/api/materials/views", headers=h, json={"name": "pytest Yetki", "definition": {
        "columns": [{"field": "Code"}], "rules": [{"id": "k1", "enabled": True, **rule, "format": {"bold": True}}]}})
    assert r.status_code == 201, r.text
    assert api.post("/api/materials/export", headers=h, json={"fields": ["Code", "Name"]}).status_code == 200
    me = api.get("/api/auth/me", headers=h).json()
    assert me["role"] == role and me["permissions"]["86"] == "full" and len(me["permissions"]) == 98


def test_jobs_own_and_others(db_session, roles, db_engine):
    key, end, admin = roles[KEY_USER], roles[END_USER], roles[ADMIN]
    c = TestClient(create_app(), raise_server_exceptions=False)
    key_job = queue.enqueue(db_session, TYPE_WORKSPACE, CHANNEL_INTERACTIVE, key)
    end_job = queue.enqueue(db_session, TYPE_WORKSPACE, CHANNEL_INTERACTIVE, end)

    # kendi işleri: End user dahil (48 "kendi")
    assert [j["id"] for j in c.get("/api/jobs", headers=auth(end)).json()["jobs"]] == [end_job]
    assert c.get(f"/api/jobs/{end_job}", headers=auth(end)).json()["requested_by_name"] == PREFIX + "end-user"
    # başkasının işi: Key user ve End user 403, Admin görür
    for user in (key, end):
        r = c.get(f"/api/jobs/{key_job if user == end else end_job}", headers=auth(user))
        assert r.status_code == 403 and r.json()["error"]["code"] == "forbidden"
    assert c.get(f"/api/jobs/{key_job}", headers=auth(admin)).status_code == 200
    # herkesin işleri: yalnız Admin ve System owner (93)
    r = c.get("/api/jobs?scope=all", headers=auth(key))
    assert r.status_code == 403
    assert r.json()["error"]["message"] == "Bu işlem için Admin yetkisi gerekir. Yetki için yöneticinize başvurun."
    assert r.json()["error"]["details"] == [{"function": 93, "function_name": "İş kuyruğu yönetimi (öneri)",
                                             "access": "read", "required_role": "Admin"}]
    ids = {j["id"] for j in c.get("/api/jobs?scope=all", headers=auth(roles[SYSTEM_OWNER])).json()["jobs"]}
    assert {key_job, end_job} <= ids
    # iptal: kendi işi herkes, başkasının işi Admin
    r = c.post(f"/api/jobs/{key_job}/cancel", headers=auth(end))
    assert r.status_code == 403 and "Admin yetkisi" in r.json()["error"]["message"]
    assert c.post(f"/api/jobs/{end_job}/cancel", headers=auth(end)).json()["status"] == "İptal"
    assert c.post(f"/api/jobs/{key_job}/cancel", headers=auth(admin)).json()["status"] == "İptal"
    # retler denetim izinde
    denied = audits(db_engine, end, "Yetkisiz istek")
    assert {(d["function"], d["access"]) for d in denied} == {(93, "read"), (93, "write")}
    assert all(d["role"] == END_USER for d in denied)


def test_websocket_for_every_role(roles):
    with TestClient(create_app()) as c:
        for role, user in roles.items():
            with c.websocket_connect("/api/ws", headers=auth(user)) as ws:
                assert ws.receive_json()["type"] == "hello", role


def test_role_change_applies_on_next_request_without_logout(roles, db_engine, db_session):
    admin = roles[ADMIN]
    c = TestClient(create_app(), raise_server_exceptions=False)
    h = auth(admin, fresh=True)
    assert c.get("/api/jobs?scope=all", headers=h).status_code == 200
    with db_engine.begin() as conn:
        conn.execute(text("UPDATE adm.AppUser SET Role = N'Key user' WHERE Id = :u"), {"u": admin})
    r = c.get("/api/jobs?scope=all", headers=h)
    assert r.status_code == 403 and r.headers["X-Smartchain-Role"] == KEY_USER
    me = c.get("/api/auth/me", headers=h)
    assert me.status_code == 200 and me.json()["role"] == KEY_USER and me.json()["permissions"]["93"] == "none"


def test_unknown_role_closes_session(roles, db_engine):
    user = roles[END_USER]
    c = TestClient(create_app(), raise_server_exceptions=False)
    h = auth(user, fresh=True)
    with db_engine.begin() as conn:
        conn.execute(text("UPDATE adm.AppUser SET Role = N'Deneme' WHERE Id = :u"), {"u": user})
    assert c.get("/api/jobs", headers=h).json()["error"]["code"] == "not_authenticated"
    assert c.get("/api/auth/me", headers=h).status_code == 401  # oturum kapandı
    with db_engine.connect() as conn:
        reason = conn.execute(text("SELECT TOP 1 EndReason FROM adm.UserSession WHERE UserId = :u ORDER BY Id DESC"),
                              {"u": user}).scalar()
    assert reason == "Kapatıldı" and audits(db_engine, user, "Geçersiz rol")[0]["role"] == "Deneme"


def test_view_owner_context(api, roles, db_engine):  # noqa: F811
    """Nesne bağlamı: başkasının görünümü salt okunur (Admin ve System owner dahil); ret izde."""
    owner, other = roles[END_USER], roles[SYSTEM_OWNER]
    v = api.post("/api/materials/views", headers=auth(owner),
                 json={"name": "pytest Paylaşılan", "is_shared": True, "definition": {"columns": [{"field": "Code"}]}}).json()
    listed = api.get("/api/materials/views", headers=auth(other)).json()["views"]
    assert any(x["id"] == v["id"] and not x["is_owner"] for x in listed)
    for call in (lambda: api.put(f"/api/materials/views/{v['id']}", headers=auth(other), json={"name": "pytest X"}),
                 lambda: api.delete(f"/api/materials/views/{v['id']}", headers=auth(other))):
        r = call()
        assert r.status_code == 403 and r.json()["error"] == {
            **r.json()["error"], "code": "view_not_owner",
            "message": "Bu görünümü yalnız sahibi değiştirebilir; sizin için salt okunur."}
    [d1, d2] = audits(db_engine, other, "Yetkisiz istek")
    assert d1["reason"] == "sahibi değil" and d1["view_id"] == v["id"] and d2["function"] == 10
