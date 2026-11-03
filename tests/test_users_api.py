"""Kullanıcı yönetimi uçtan uca (fonksiyon 88; K-101, K-102): liste, ekleme, koruma kuralları, etkiler, denetim izi,
geçici şifrenin hiçbir yere yazılmaması, yazı boyutu, ilk hesap. Şifresiz deneme hesaplarıyla (oturum testte açılır)."""
import io
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api import security
from app.api.main import create_app
from app.api.lists.request import ExportRequest, FilterItem
from app.api.lists.users import USERS
from app.api.permissions import ADMIN, END_USER, KEY_USER, SYSTEM_OWNER
from app.api.repositories import users as users_repo
from app.api.services import export as export_service, lists as list_service, users as service

from auth_helpers import auth, delete_users, ensure_user

pytestmark = pytest.mark.db

PREFIX = "pytest.kul."


def clean(engine):
    with engine.begin() as c:
        ids = [r[0] for r in c.execute(text("SELECT Id FROM adm.AppUser WHERE UserName LIKE :p"), {"p": PREFIX + "%"})]
        delete_users(c, ids)
        c.execute(text("DELETE FROM adm.AuditLog WHERE ObjectKey LIKE :p"), {"p": PREFIX + "%"})
        c.execute(text("DELETE FROM adm.LoginThrottle WHERE UserName LIKE :p"), {"p": PREFIX + "%"})
        c.execute(text("DELETE FROM adm.SystemSetting WHERE SettingKey = N'PasswordMinLength'"))


@pytest.fixture
def engine(db_engine):
    clean(db_engine)
    yield db_engine
    clean(db_engine)


@pytest.fixture
def client():
    app = create_app()
    app.state.notifier.close_sessions = AsyncMock()
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def people(engine):
    """Her rolden bir hesap ve bir hedef (End user): ad → Id."""
    with engine.begin() as c:
        return {
            "owner": ensure_user(c, PREFIX + "sahip", SYSTEM_OWNER), "owner2": ensure_user(c, PREFIX + "owner2", SYSTEM_OWNER),
            "admin": ensure_user(c, PREFIX + "admin", ADMIN),
            "admin2": ensure_user(c, PREFIX + "admin2", ADMIN), "key": ensure_user(c, PREFIX + "key", KEY_USER),
            "end": ensure_user(c, PREFIX + "end", END_USER, "Hedef Kullanıcı"),
        }


@pytest.fixture
def only_admins(engine):
    """Deneme dışındaki aktif Admin'ler geçici olarak kapanır: "son aktif Admin" sayılabilsin."""
    with engine.begin() as c:
        others = [r[0] for r in c.execute(text(
            "SELECT Id FROM adm.AppUser WHERE Role = N'Admin' AND IsActive = 1 AND UserName NOT LIKE :p"), {"p": PREFIX + "%"})]
        for i in others:
            c.execute(text("UPDATE adm.AppUser SET IsActive = 0 WHERE Id = :i"), {"i": i})
    yield
    with engine.begin() as c:
        for i in others:
            c.execute(text("UPDATE adm.AppUser SET IsActive = 1 WHERE Id = :i"), {"i": i})


def scalar(engine, sql, **p):
    with engine.connect() as c:
        return c.execute(text(sql), p).scalar_one()


def run(engine, sql, **p):
    with engine.begin() as c:
        c.execute(text(sql), p)


def audit_rows(engine, key):
    with engine.connect() as c:
        return [(a, u, json.loads(o) if o else None, json.loads(n) if n else None) for a, u, o, n in c.execute(text(
            "SELECT Action, UserId, OldValue, NewValue FROM adm.AuditLog WHERE ObjectKey = :k ORDER BY Id"), {"k": key})]


def error(r):
    return r.status_code, r.json()["error"]["code"]


def new_user(client, actor, name="yeni", role=END_USER, **kw):
    return client.post("/api/users", headers=auth(actor), json={
        "full_name": kw.get("full_name", "Yeni Kullanıcı"), "user_name": PREFIX + name, "role": role})


# --- Liste ---

def statuses(client, actor):
    r = client.post("/api/users/query", headers=auth(actor), json={
        "fields": ["FullName", "UserName", "Role", "Status", "LastLoginAt"], "limit": 100,
        "filters": [{"field": "UserName", "op": "starts_with", "value": PREFIX}], "sort": [{"field": "UserName", "dir": "asc"}]})
    assert r.status_code == 200, r.text
    return {row["UserName"].removeprefix(PREFIX): row["Status"] for row in r.json()["rows"]}


def test_list_status_values_and_columns(engine, client, people):
    h = auth(people["owner2"])  # "owner" aşağıda kapatılır
    run(engine, "UPDATE adm.AppUser SET IsActive = 0 WHERE Id = :i", i=people["key"])
    run(engine, "UPDATE adm.AppUser SET LockedUntil = DATEADD(minute, 10, SYSUTCDATETIME()) WHERE Id = :i", i=people["owner"])
    run(engine, "UPDATE adm.AppUser SET MustChangePassword = 1, PasswordChangeReason = N'Sıfırlama' WHERE Id = :i", i=people["end"])
    run(engine, "UPDATE adm.AppUser SET MustChangePassword = 1, PasswordChangeReason = N'Süre doldu' WHERE Id = :i", i=people["admin2"])
    assert statuses(client, people["owner"]) == {
        "key": "Pasif", "sahip": "Kilitli", "end": "İlk giriş bekliyor", "admin2": "Aktif", "admin": "Aktif", "owner2": "Aktif"}
    # Pasif > Kilitli
    run(engine, "UPDATE adm.AppUser SET IsActive = 0 WHERE Id = :i", i=people["owner"])
    assert statuses(client, people["owner2"])["sahip"] == "Pasif"

    cols = {c["field"]: c for c in client.get("/api/users/columns", headers=h).json()["columns"]}
    assert list(cols) == ["FullName", "UserName", "Role", "Status", "LastLoginAt"]
    assert cols["LastLoginAt"]["label"] == "Son giriş" and cols["Status"]["filter"] == "list"
    assert cols["Status"]["values"] == ["Aktif", "Pasif", "Kilitli", "İlk giriş bekliyor"]
    assert cols["Role"]["values"] is None and cols["Role"]["values_from_server"] is True  # row_scope'la süzülür


def test_list_filter_sort_group_values_on_computed_status(engine, client, people):
    h = auth(people["admin"])
    run(engine, "UPDATE adm.AppUser SET IsActive = 0 WHERE Id = :i", i=people["key"])
    only = {"field": "UserName", "op": "starts_with", "value": PREFIX}
    r = client.post("/api/users/query", headers=h, json={
        "fields": ["UserName"], "filters": [only, {"field": "Status", "op": "in", "values": ["Pasif"]}]})
    assert [x["UserName"] for x in r.json()["rows"]] == [PREFIX + "key"]
    r = client.post("/api/users/query", headers=h, json={
        "fields": ["UserName", "Status"], "filters": [only], "sort": [{"field": "Status", "dir": "desc"}]})
    assert r.json()["rows"][0]["Status"] == "Pasif"
    r = client.post("/api/users/groups", headers=h, json={"group_by": ["Status"], "fields": ["UserName"], "filters": [only]})
    assert {g["key"][0]: g["count"] for g in r.json()["groups"]} == {"Aktif": 3, "Pasif": 1}
    r = client.post("/api/users/values", headers=h, json={"field": "Status", "filters": [only]})
    assert {v["value"]: v["count"] for v in r.json()} == {"Aktif": 3, "Pasif": 1}


def test_list_works_without_data_version_and_hides_secrets(engine, client, people, monkeypatch):
    h = auth(people["admin"])
    monkeypatch.setattr(list_service.data_versions, "read_current", lambda s: None)
    assert client.post("/api/users/query", headers=h, json={"limit": 5}).status_code == 200
    assert error(client.post("/api/materials/query", headers=h, json={"limit": 5})) == (404, "no_data_version")
    for field in ("PasswordHash", "FontSize", "IsActive"):
        assert client.post("/api/users/query", headers=h, json={"fields": [field]}).status_code == 422


def test_excel_has_no_data_version_and_no_secret(engine, client, people):
    r = client.post("/api/users/export", headers=auth(people["admin"]), json={
        "fields": ["FullName", "UserName", "Role", "Status", "LastLoginAt"], "scope": {"rows": "filtered", "columns": "all"},
        "filters": [{"field": "UserName", "op": "starts_with", "value": PREFIX}]})
    assert r.status_code == 200, r.text
    assert "smartchain_kullanici_2" in r.headers["content-disposition"] and "veri-v" not in r.headers["content-disposition"]
    book = load_workbook(io.BytesIO(r.content))
    info = {row[0].value: row[1].value for row in book["Bilgi"].iter_rows()}
    assert info["Kaynak"] == "Güncel kayıtlar"
    headers = [c.value for c in next(book.worksheets[0].iter_rows())]
    assert headers == ["Ad soyad", "Kullanıcı adı", "Rol", "Durum", "Son giriş"]


# --- System owner gizli (K-101) ---

ONLY = {"field": "UserName", "op": "starts_with", "value": PREFIX}


def test_system_owner_hidden_from_admin_in_list_values_groups_and_excel(engine, client, people):
    admin, owner = auth(people["admin"]), auth(people["owner"])
    query = {"fields": ["UserName", "Role"], "filters": [ONLY], "limit": 100}
    seen = client.post("/api/users/query", headers=admin, json=query).json()
    assert {r["Role"] for r in seen["rows"]} == {ADMIN, KEY_USER, END_USER}
    assert seen["filtered"] == 4
    full = client.post("/api/users/query", headers=owner, json=query).json()
    assert {r["UserName"] for r in full["rows"]} >= {PREFIX + "sahip", PREFIX + "owner2"} and full["filtered"] == 6
    # toplam sayı da saklar; arama da bulamaz
    assert client.post("/api/users/query", headers=admin, json={"limit": 1}).json()["total"] < \
           client.post("/api/users/query", headers=owner, json={"limit": 1}).json()["total"]
    r = client.post("/api/users/query", headers=admin, json={"fields": ["UserName"], "filters": [
        {"field": "Role", "op": "in", "values": [SYSTEM_OWNER]}]})
    assert r.json()["rows"] == [] and r.json()["filtered"] == 0
    r = client.post("/api/users/values", headers=admin, json={"field": "Role", "filters": [ONLY]})
    assert SYSTEM_OWNER not in {v["value"] for v in r.json()}
    r = client.post("/api/users/values", headers=owner, json={"field": "Role", "filters": [ONLY]})
    assert SYSTEM_OWNER in {v["value"] for v in r.json()}
    r = client.post("/api/users/groups", headers=admin, json={"group_by": ["Role"], "fields": ["UserName"], "filters": [ONLY]})
    assert SYSTEM_OWNER not in {g["key"][0] for g in r.json()["groups"]} and r.json()["filtered"] == 4

    r = client.post("/api/users/export", headers=admin, json={"fields": ["UserName", "Role"], "scope": {"rows": "all", "columns": "visible"}})
    sheet = load_workbook(io.BytesIO(r.content)).worksheets[0]
    names = [row[0].value for row in sheet.iter_rows(min_row=2)]
    assert PREFIX + "admin" in names and PREFIX + "sahip" not in names and SYSTEM_OWNER not in [row[1].value for row in sheet.iter_rows(min_row=2)]
    r = client.post("/api/users/export", headers=owner, json={"fields": ["UserName", "Role"], "scope": {"rows": "all", "columns": "visible"}})
    assert PREFIX + "sahip" in [row[0].value for row in load_workbook(io.BytesIO(r.content)).worksheets[0].iter_rows(min_row=2)]


def test_background_export_plan_uses_role_of_requester(engine, people):
    """Arka plan işi de işi başlatanın rolüyle süzer (rol kayıttan okunur)."""
    req = ExportRequest(fields=["UserName"], filters=[FilterItem(**ONLY)])
    with Session(engine) as s:
        assert export_service._plan(s, USERS, people["admin"], req).rows == 4
        assert export_service._plan(s, USERS, people["owner"], req).rows == 6
        assert export_service._plan(s, USERS, 999999, req).rows == 4  # bilinmeyen: en dar kapsam


def test_system_owner_is_404_for_admin_like_unknown_user(engine, client, people):
    h = auth(people["admin"])
    unknown = client.get("/api/users/999999", headers=h).json()["error"]
    hidden = client.get(f"/api/users/{people['owner']}", headers=h)
    assert hidden.status_code == 404
    assert {k: v for k, v in hidden.json()["error"].items() if k != "trace_id"} == {k: v for k, v in unknown.items() if k != "trace_id"}
    for action, call in CALLS.items():
        r = call(client, people["owner"], h)
        assert error(r) == (404, "user_not_found"), action
    assert scalar(engine, "SELECT COUNT(*) FROM adm.AuditLog WHERE UserId = :u AND Action = N'Yetkisiz istek' "
                          "AND NewValue LIKE N'%hidden_account%'", u=people["admin"]) == 1 + len(CALLS)
    assert client.get(f"/api/users/{people['owner']}", headers=auth(people["owner2"])).status_code == 200


def test_last_admin_count_ignores_system_owners_visibility(engine, client, people, only_admins):
    """Gizlilik sayımı değiştirmez: yalnız Admin'ler sayılır, System owner da aynı kuralı görür."""
    assert CALLS["close"](client, people["admin2"], auth(people["owner"])).status_code == 200
    assert error(CALLS["close"](client, people["admin"], auth(people["owner"]))) == (409, "user_protected")


@pytest.mark.parametrize("role", [KEY_USER, END_USER])
def test_other_roles_are_forbidden_everywhere(engine, client, people, role):
    actor = people["key" if role == KEY_USER else "end"]
    target = people["admin"]
    h = auth(actor)
    for r in (client.get("/api/users/columns", headers=h), client.post("/api/users/query", headers=h, json={}),
              client.post("/api/users/export", headers=h, json={"fields": ["UserName"]}),
              client.get(f"/api/users/{target}", headers=h), new_user(client, actor),
              client.put(f"/api/users/{target}/role", headers=h, json={"role": END_USER}),
              client.put(f"/api/users/{target}/name", headers=h, json={"full_name": "x"}),
              client.post(f"/api/users/{target}/reset-password", headers=h), client.post(f"/api/users/{target}/unlock", headers=h),
              client.post(f"/api/users/{target}/close", headers=h), client.post(f"/api/users/{target}/reopen", headers=h)):
        assert error(r) == (403, "forbidden"), r.url
        assert "Admin yetkisi gerekir" in r.json()["error"]["message"]


# --- Ekleme ---

def test_create_shows_password_once_and_forces_change(engine, client, people):
    r = new_user(client, people["admin"], full_name="  Burak D.  ")
    assert r.status_code == 201, r.text
    assert r.headers["cache-control"] == "no-store"
    out = r.json()
    password = out["temporary_password"]
    assert out["user"]["full_name"] == "Burak D." and out["user"]["role"] == END_USER
    assert out["user"]["status"] == "İlk giriş bekliyor" and "audit" not in out
    with engine.connect() as c:
        must, reason, stored = c.execute(text("SELECT MustChangePassword, PasswordChangeReason, PasswordHash FROM adm.AppUser "
                                              "WHERE UserName = :n"), {"n": PREFIX + "yeni"}).one()
    assert must and reason == "İlk giriş" and password not in stored and security.verify_password(stored, password)

    c = TestClient(create_app(), raise_server_exceptions=False)
    r = c.post("/api/auth/login", json={"user_name": PREFIX + "yeni", "password": password})
    assert r.status_code == 200 and r.json()["must_change_password"] is True
    assert error(c.get("/api/materials/columns")) == (403, "password_change_required")
    assert c.post("/api/auth/password", json={"current_password": password, "new_password": "Yeni-sifre-2026"}).status_code == 204
    # bir daha verilmez: ayrıntıda şifre yok
    detail = client.get(f"/api/users/{out['user']['id']}", headers=auth(people["admin"])).json()
    assert "temporary_password" not in detail and detail["user"]["status"] == "Aktif"


def test_name_conflict_suggests_next_free_counting_inactive(engine, client, people):
    h = people["admin"]
    assert new_user(client, h, "burak").status_code == 201
    r = new_user(client, h, "burak")
    assert error(r) == (409, "user_name_taken")
    assert r.json()["error"]["details"][0]["suggestion"] == PREFIX + "burak2"
    # pasif hesap da doludur
    created = new_user(client, h, "burak2").json()["user"]["id"]
    assert client.post(f"/api/users/{created}/close", headers=auth(h)).status_code == 200
    assert new_user(client, h, "burak").json()["error"]["details"][0]["suggestion"] == PREFIX + "burak3"
    assert new_user(client, h, "burak2").json()["error"]["details"][0]["suggestion"] == PREFIX + "burak3"


@pytest.mark.parametrize("name", ["A", "1abc", "Burak", "şükrü", "a b", "a" * 61, "a'; DROP"])
def test_user_name_format(engine, client, people, name):
    r = client.post("/api/users", headers=auth(people["admin"]), json={"full_name": "X", "user_name": name, "role": END_USER})
    assert error(r) == (422, "validation")


def test_user_name_conflict_ignores_case(engine, client, people):
    run(engine, "INSERT INTO adm.AppUser (UserName, FullName, Role, MustChangePassword) VALUES (:n, N'Eski', N'End user', 0)",
        n=PREFIX + "Eski")
    assert error(new_user(client, people["admin"], "eski")) == (409, "user_name_taken")


def test_full_name_required_and_role_checked(engine, client, people):
    h = auth(people["admin"])
    for body in ({"full_name": "   ", "user_name": PREFIX + "x", "role": END_USER},
                 {"full_name": "X", "user_name": PREFIX + "x", "role": "Sistem sahibi"}):
        assert error(client.post("/api/users", headers=h, json=body)) == (422, "validation")


def test_only_system_owner_grants_system_owner(engine, client, people):
    r = new_user(client, people["admin"], "sahip2", SYSTEM_OWNER)
    assert error(r) == (403, "forbidden") and "System owner yetkisi gerekir" in r.json()["error"]["message"]
    assert r.json()["error"]["details"][0]["required_role"] == SYSTEM_OWNER
    r = client.put(f"/api/users/{people['end']}/role", headers=auth(people["admin"]), json={"role": SYSTEM_OWNER})
    assert error(r) == (403, "forbidden")
    assert scalar(engine, "SELECT Role FROM adm.AppUser WHERE Id = :i", i=people["end"]) == END_USER
    assert new_user(client, people["owner"], "sahip2", SYSTEM_OWNER).status_code == 201
    r = client.put(f"/api/users/{people['end']}/role", headers=auth(people["owner"]), json={"role": SYSTEM_OWNER})
    assert r.status_code == 200, r.text
    detail = client.get(f"/api/users/{people['key']}", headers=auth(people["admin"])).json()
    assert SYSTEM_OWNER not in detail["assignable_roles"]
    detail = client.get(f"/api/users/{people['key']}", headers=auth(people["owner"])).json()
    assert SYSTEM_OWNER in detail["assignable_roles"]


# --- Koruma: yazma ucu ile satır menüsü aynı sonucu verir ---

CALLS = {
    "role": lambda c, i, h: c.put(f"/api/users/{i}/role", headers=h, json={"role": KEY_USER}),
    "name": lambda c, i, h: c.put(f"/api/users/{i}/name", headers=h, json={"full_name": "Yeni Ad"}),
    "reset": lambda c, i, h: c.post(f"/api/users/{i}/reset-password", headers=h),
    "unlock": lambda c, i, h: c.post(f"/api/users/{i}/unlock", headers=h),
    "close": lambda c, i, h: c.post(f"/api/users/{i}/close", headers=h),
    "reopen": lambda c, i, h: c.post(f"/api/users/{i}/reopen", headers=h),
}

REFUSED = [
    ("admin", "admin", "role", 409, "self"), ("admin", "admin", "reset", 409, "self"), ("admin", "admin", "close", 409, "self"),
    ("owner", "owner", "role", 409, "self"), ("owner", "owner", "close", 409, "self"),
    ("owner", "owner2", "role", 409, "system_owner"), ("owner", "owner2", "close", 409, "system_owner"),
    ("admin", "end", "unlock", 409, "not_locked"), ("admin", "end", "reopen", 409, "already_active"),
]


@pytest.mark.parametrize("actor, target, action, status, rule", REFUSED)
def test_refused_actions_match_menu_and_are_audited(engine, client, people, actor, target, action, status, rule):
    before = {"Role": scalar(engine, "SELECT Role FROM adm.AppUser WHERE Id = :i", i=people[target])}
    h = auth(people[actor])
    state = client.get(f"/api/users/{people[target]}", headers=h).json()["actions"][action]
    assert state["allowed"] is False and state["reason"]
    r = CALLS[action](client, people[target], h)
    assert r.status_code == status, r.text
    body = r.json()["error"]
    assert body["message"] == state["reason"]
    assert body["code"] == "user_protected" and body["details"] == [{"rule": rule}]
    with engine.connect() as c:
        denial = c.execute(text("SELECT TOP 1 NewValue FROM adm.AuditLog WHERE UserId = :u AND Action = N'Yetkisiz istek' "
                                "ORDER BY Id DESC"), {"u": people[actor]}).scalar_one()
    assert json.loads(denial)["action"] == action and json.loads(denial)["target"] == PREFIX + ("sahip" if target == "owner" else target)
    assert scalar(engine, "SELECT Role FROM adm.AppUser WHERE Id = :i", i=people[target]) == before["Role"]


def test_inactive_account_allows_only_reopen_and_name(engine, client, people):
    h = auth(people["admin"])
    assert CALLS["close"](client, people["end"], h).status_code == 200
    actions = client.get(f"/api/users/{people['end']}", headers=h).json()["actions"]
    assert {k for k, v in actions.items() if v["allowed"]} == {"reopen", "name"}
    for action in ("role", "reset", "unlock"):
        assert error(CALLS[action](client, people["end"], h)) == (409, "user_protected"), action
    assert CALLS["close"](client, people["end"], h).json()["error"]["details"] == [{"rule": "already_inactive"}]


def test_last_active_admin_cannot_be_closed_or_demoted(engine, client, people, only_admins):
    owner, admin, admin2 = people["owner"], people["admin"], people["admin2"]
    assert CALLS["close"](client, admin2, auth(admin)).status_code == 200  # iki Admin vardı
    for action in ("close", "role"):
        r = CALLS[action](client, admin, auth(owner))
        assert error(r) == (409, "user_protected") and r.json()["error"]["details"] == [{"rule": "last_admin"}]
        assert "Son aktif Admin" in r.json()["error"]["message"]
    actions = client.get(f"/api/users/{admin}", headers=auth(owner)).json()["actions"]
    assert actions["close"]["allowed"] is False and actions["role"]["allowed"] is False
    # başka Admin açılınca kural kalkar
    assert CALLS["reopen"](client, admin2, auth(owner)).status_code == 200
    assert CALLS["role"](client, admin, auth(owner)).status_code == 200


def test_two_admins_closing_each_other_leave_one_active(engine, people, only_admins):
    """Sayım ve yazma aynı işlemde, kilitle (K-101): en az bir Admin aktif kalır."""
    a, b = people["admin"], people["admin2"]
    # Sıra rastgele; her turda ikisi de açılıp yeniden denenir.
    for _ in range(4):
        run(engine, "UPDATE adm.AppUser SET IsActive = 1 WHERE Id IN (:a, :b)", a=a, b=b)
        clients = [TestClient(create_app(), raise_server_exceptions=False) for _ in range(2)]
        for c in clients:
            c.app.state.notifier.close_sessions = AsyncMock()
        heads = [auth(a, fresh=True), auth(b, fresh=True)]
        with ThreadPoolExecutor(2) as pool:
            codes = list(pool.map(lambda args: CALLS["close"](*args).status_code, [(clients[0], b, heads[0]), (clients[1], a, heads[1])]))
        active = scalar(engine, "SELECT COUNT(*) FROM adm.AppUser WHERE Id IN (:a, :b) AND IsActive = 1", a=a, b=b)
        assert active >= 1, codes


# --- Etkiler ve iz ---

def test_close_ends_sessions_and_reopen_keeps_password(engine, client, people):
    target = people["end"]
    run(engine, "UPDATE adm.AppUser SET PasswordHash = :h WHERE Id = :i", h=security.hash_password("Eski-sifre-2026"), i=target)
    assert client.get("/api/auth/me", headers=auth(target, fresh=True)).status_code == 200
    token_headers = auth(target, fresh=True)
    r = CALLS["close"](client, target, auth(people["admin"]))
    assert r.status_code == 200 and r.json()["user"]["status"] == "Pasif" and r.json()["user"]["open_sessions"] == 0
    ended = client.app.state.notifier.close_sessions.await_args.args[0]
    assert len(ended) >= 2  # WebSocket'leri 4401
    assert scalar(engine, "SELECT COUNT(*) FROM adm.UserSession WHERE UserId = :i AND EndReason = N'Kapatıldı'", i=target) >= 2
    assert client.get("/api/auth/me", headers=token_headers).status_code == 401
    assert scalar(engine, "SELECT COUNT(*) FROM adm.AppUser WHERE Id = :i", i=target) == 1  # silinmez

    fresh = TestClient(create_app(), raise_server_exceptions=False)
    login = {"user_name": PREFIX + "end", "password": "Eski-sifre-2026"}
    assert error(fresh.post("/api/auth/login", json=login)) == (403, "account_inactive")
    # pasifken yapılan hatalı denemeler LoginThrottle'da; geri açınca temizlenir
    fresh.post("/api/auth/login", json={**login, "password": "yanlis"})
    assert scalar(engine, "SELECT COUNT(*) FROM adm.LoginThrottle WHERE UserName = :n", n=PREFIX + "end") == 1
    assert CALLS["reopen"](client, target, auth(people["admin"])).json()["user"]["status"] == "Aktif"
    assert scalar(engine, "SELECT COUNT(*) FROM adm.LoginThrottle WHERE UserName = :n", n=PREFIX + "end") == 0
    assert fresh.post("/api/auth/login", json=login).status_code == 200  # şifre değişmedi


def test_role_change_keeps_session_and_applies_next_request(engine, client, people):
    h = auth(people["end"], fresh=True)
    assert client.get("/api/auth/me", headers=h).json()["role"] == END_USER
    assert client.put(f"/api/users/{people['end']}/role", headers=auth(people["admin"]), json={"role": ADMIN}).status_code == 200
    r = client.get("/api/users/columns", headers=h)
    assert r.status_code == 200 and r.headers["X-Smartchain-Role"] == ADMIN
    # aynı rol: değişiklik yok, iz yok
    n = len(audit_rows(engine, PREFIX + "end"))
    assert client.put(f"/api/users/{people['end']}/role", headers=auth(people["admin"]), json={"role": ADMIN}).status_code == 200
    assert len(audit_rows(engine, PREFIX + "end")) == n


def test_reset_keeps_history_ends_sessions(engine, client, people):
    target = people["end"]
    old = "Eski-sifre-2026"
    c = TestClient(create_app(), raise_server_exceptions=False)
    run(engine, "UPDATE adm.AppUser SET PasswordHash = :h WHERE Id = :i", h=security.hash_password("Ilk-sifre-2026"), i=target)
    assert c.post("/api/auth/login", json={"user_name": PREFIX + "end", "password": "Ilk-sifre-2026"}).status_code == 200
    assert c.post("/api/auth/password", json={"current_password": "Ilk-sifre-2026", "new_password": old}).status_code == 204

    r = CALLS["reset"](client, target, auth(people["admin"]))
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    password = r.json()["temporary_password"]
    assert r.json()["user"]["status"] == "İlk giriş bekliyor"
    assert client.app.state.notifier.close_sessions.await_args.args[0]
    assert scalar(engine, "SELECT COUNT(*) FROM adm.UserSession WHERE UserId = :i AND EndReason = N'Şifre değişti'", i=target) == 1
    assert c.get("/api/auth/me").status_code == 401
    assert scalar(engine, "SELECT PasswordChangeReason FROM adm.AppUser WHERE Id = :i", i=target) == "Sıfırlama"

    assert c.post("/api/auth/login", json={"user_name": PREFIX + "end", "password": old}).status_code == 401
    assert c.post("/api/auth/login", json={"user_name": PREFIX + "end", "password": password}).status_code == 200
    r = c.post("/api/auth/password", json={"current_password": password, "new_password": old})
    assert error(r) == (422, "password_policy")  # geçmiş silinmedi (K-98)
    assert {"field": "new_password", "problem": "history"} in r.json()["error"]["details"]


def test_system_owner_unlocks_and_resets_other_system_owner(engine, client, people):
    target = people["owner2"]
    run(engine, "UPDATE adm.AppUser SET LockedUntil = DATEADD(minute, 10, SYSUTCDATETIME()), FailedAttempts = 5 WHERE Id = :i", i=target)
    assert client.post(f"/api/users/{target}/unlock", headers=auth(people["owner"])).status_code == 200
    with engine.connect() as c:
        assert c.execute(text("SELECT LockedUntil, FailedAttempts FROM adm.AppUser WHERE Id = :i"), {"i": target}).one() == (None, 0)
    assert CALLS["reset"](client, target, auth(people["owner"])).status_code == 200


def test_every_action_audited_with_old_and_new_and_no_password(engine, client, people, caplog):
    admin = people["admin"]
    h = auth(admin)
    created = new_user(client, admin, "izli", KEY_USER, full_name="Izli Kullanici").json()
    user_id, first = created["user"]["id"], created["temporary_password"]
    CALLS["name"](client, user_id, h)
    assert client.put(f"/api/users/{user_id}/role", headers=h, json={"role": END_USER}).status_code == 200
    run(engine, "UPDATE adm.AppUser SET LockedUntil = DATEADD(minute, 10, SYSUTCDATETIME()), FailedAttempts = 5 WHERE Id = :i", i=user_id)
    assert CALLS["unlock"](client, user_id, h).status_code == 200
    with caplog.at_level(logging.DEBUG):
        second = CALLS["reset"](client, user_id, h).json()["temporary_password"]
    assert CALLS["close"](client, user_id, h).status_code == 200
    assert CALLS["reopen"](client, user_id, h).status_code == 200

    rows = audit_rows(engine, PREFIX + "izli")
    assert [r[0] for r in rows] == ["Kullanıcı oluşturuldu", "Ad soyad değişikliği", "Rol değişikliği", "Kilit açıldı",
                                    "Şifre sıfırlama", "Kullanıcı kapatıldı", "Kullanıcı geri açıldı"]
    assert all(r[1] == admin for r in rows)
    by = {r[0]: r for r in rows}
    assert by["Kullanıcı oluşturuldu"][3] == {"UserName": PREFIX + "izli", "FullName": "Izli Kullanici", "Role": KEY_USER}
    assert by["Ad soyad değişikliği"][2:] == ({"FullName": "Izli Kullanici"}, {"FullName": "Yeni Ad"})
    assert by["Rol değişikliği"][2:] == ({"Role": KEY_USER}, {"Role": END_USER})
    assert by["Kilit açıldı"][2]["FailedAttempts"] == 5 and by["Kilit açıldı"][3] == {"LockedUntil": None, "FailedAttempts": 0}
    assert by["Şifre sıfırlama"][3]["PasswordChangeReason"] == "Sıfırlama"
    assert by["Kullanıcı kapatıldı"][2:] == ({"IsActive": True}, {"IsActive": False, "ended_sessions": []})
    assert by["Kullanıcı geri açıldı"][2:] == ({"IsActive": False}, {"IsActive": True})

    with engine.connect() as c:
        everything = " ".join(str(v) for row in c.execute(text("SELECT ObjectKey, OldValue, NewValue FROM adm.AuditLog")) for v in row)
    for password in (first, second):
        assert password not in everything and password not in caplog.text


def test_unknown_user(engine, client, people):
    h = auth(people["admin"])
    assert error(client.get("/api/users/999999", headers=h)) == (404, "user_not_found")
    assert error(CALLS["close"](client, 999999, h)) == (404, "user_not_found")


def test_temporary_password_follows_policy(engine, client, people):
    run(engine, "INSERT INTO adm.SystemSetting (SettingKey, Value) VALUES (N'PasswordMinLength', N'20')")
    password = new_user(client, people["admin"], "uzun").json()["temporary_password"]
    assert len(password) == 20
    for _ in range(200):  # kısa kullanıcı adı rastgele içine düşmez
        p = security.temporary_password(security.Policy(), "ab")
        assert security.policy_problems(security.Policy(), "ab", p) == []


# --- Yazı boyutu (U-23) ---

def test_font_size_follows_user(engine, client, people):
    h = auth(people["end"], fresh=True)
    assert client.get("/api/auth/me", headers=h).json()["font_size"] is None
    assert client.put("/api/auth/preferences", headers=h, json={"font_size": 16}).status_code == 204
    assert client.get("/api/auth/me", headers=auth(people["end"], fresh=True)).json()["font_size"] == 16  # başka oturum
    assert client.get("/api/auth/me", headers=auth(people["key"])).json()["font_size"] is None
    assert error(client.put("/api/auth/preferences", headers=h, json={"font_size": 15})) == (422, "validation")
    n = scalar(engine, "SELECT COUNT(*) FROM adm.AuditLog WHERE UserId = :i", i=people["end"])
    assert n == 0  # kişisel tercih ize yazılmaz


def test_font_size_available_while_password_change_pending(engine, client, people):
    run(engine, "UPDATE adm.AppUser SET MustChangePassword = 1 WHERE Id = :i", i=people["end"])
    assert client.put("/api/auth/preferences", headers=auth(people["end"], fresh=True), json={"font_size": 12}).status_code == 204


# --- İlk hesap (K-102) ---

def test_first_account(engine, people, monkeypatch):
    with Session(engine) as s:
        assert service.first_account(s) is None  # System owner var: dokunmaz, şifre yok

    monkeypatch.setattr(service, "FIRST_USER_NAME", PREFIX + "ilk")
    real = users_repo.first_system_owner
    monkeypatch.setattr(users_repo, "first_system_owner", lambda s: None)
    with Session(engine) as s:
        name, password = service.first_account(s)
    assert name == PREFIX + "ilk"
    with engine.connect() as c:
        role, must, reason, full = c.execute(text("SELECT Role, MustChangePassword, PasswordChangeReason, FullName FROM adm.AppUser "
                                                  "WHERE UserName = :n"), {"n": name}).one()
    assert (role, must, reason, full) == (SYSTEM_OWNER, True, "İlk giriş", "Destek ekibi")
    [(action, user_id, _, new)] = audit_rows(engine, name)
    assert (action, user_id, new["source"]) == ("Kullanıcı oluşturuldu", None, "kurulum") and password not in str(new)
    # ad doluysa öneriyle açılır
    with Session(engine) as s:
        assert service.first_account(s)[0] == PREFIX + "ilk2"
    monkeypatch.setattr(users_repo, "first_system_owner", real)

    # --reset: var olan hesaba yeni geçici şifre, oturumlar kapanır, izli
    monkeypatch.setattr(users_repo, "first_system_owner", lambda s: _user(engine, name))
    run(engine, "UPDATE adm.AppUser SET MustChangePassword = 0 WHERE UserName = :n", n=name)
    with Session(engine) as s:
        again, new_password = service.first_account(s, reset=True)
    assert again == name and new_password != password
    stored = scalar(engine, "SELECT PasswordHash FROM adm.AppUser WHERE UserName = :n", n=name)
    assert security.verify_password(stored, new_password) and not security.verify_password(stored, password)
    assert scalar(engine, "SELECT PasswordChangeReason FROM adm.AppUser WHERE UserName = :n", n=name) == "Sıfırlama"
    assert audit_rows(engine, name)[-1][:2] == ("Şifre sıfırlama", None)


def _user(engine, name):
    with engine.connect() as c:
        return dict(c.execute(text("SELECT * FROM adm.AppUser WHERE UserName = :n"), {"n": name}).mappings().one())
