"""Şifre ve oturum ayarları (K-105) ve yetki matrisi uçları (K-100; 2.4)."""
import io
import json

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api import security
from app.api.main import create_app
from app.api.permissions import ADMIN, END_USER, KEY_USER, SYSTEM_OWNER
from app.api.repositories import auth as auth_repo

from auth_helpers import auth, delete_users, ensure_user

pytestmark = pytest.mark.db

PREFIX = "pytest.ayar."
URL = "/api/settings/login-policy"
PASSWORD = "Baslangic-2026"


def clean(engine):
    with engine.begin() as c:
        delete_users(c, [r[0] for r in c.execute(text("SELECT Id FROM adm.AppUser WHERE UserName LIKE :p"), {"p": PREFIX + "%"})])
        c.execute(text("DELETE FROM adm.LoginThrottle WHERE UserName LIKE :p"), {"p": PREFIX + "%"})
        c.execute(text("DELETE FROM adm.SystemSetting"))
        c.execute(text("DELETE FROM adm.AuditLog WHERE ObjectType = N'SystemSetting' OR ObjectKey LIKE N'smartchain_yetki%'"))


@pytest.fixture
def people(db_engine):
    clean(db_engine)
    with db_engine.begin() as c:
        out = {r: ensure_user(c, PREFIX + r.replace(" ", "-").lower(), r) for r in (SYSTEM_OWNER, ADMIN, KEY_USER, END_USER)}
    yield out
    clean(db_engine)


@pytest.fixture
def client():
    return TestClient(create_app(), raise_server_exceptions=False)


def stored(engine, key):
    with engine.connect() as c:
        return c.execute(text("SELECT Value FROM adm.SystemSetting WHERE SettingKey = :k"), {"k": key}).scalar()


def test_read_defaults_and_limits(client, people):
    body = client.get(URL, headers=auth(people[SYSTEM_OWNER])).json()
    assert body["values"]["PasswordMinLength"] == 10 and body["values"]["PasswordRequireLetterAndDigit"] is True
    assert body["values"] == body["defaults"]  # kayıtlı ayar yoksa bütün alanlar varsayılanla gelir
    assert (body["values"]["PasswordHistoryCount"], body["values"]["LoginLockMinutes"], body["values"]["SessionWarningMinutes"]) == (5, 15, 5)
    assert body["defaults"]["SessionIdleMinutes"] == 30
    assert body["limits"]["PasswordHistoryCount"] == {"min": 1, "max": 24}
    assert set(body["values"]) == set(auth_repo.POLICY_KEYS)


def test_only_changed_keys_written_and_audited(db_engine, client, people):
    owner = people[SYSTEM_OWNER]
    r = client.put(URL, headers=auth(owner), json={"PasswordMinLength": 12, "SessionIdleMinutes": 30, "PasswordRequireLetterAndDigit": False})
    assert r.status_code == 200, r.text
    assert r.json()["values"]["PasswordMinLength"] == 12 and r.json()["values"]["PasswordRequireLetterAndDigit"] is False
    assert stored(db_engine, "PasswordMinLength") == "12" and stored(db_engine, "PasswordRequireLetterAndDigit") == "0"
    assert stored(db_engine, "SessionIdleMinutes") is None  # değişmedi, yazılmadı
    with db_engine.connect() as c:
        rows = c.execute(text("SELECT Action, UserId, ObjectKey, OldValue, NewValue FROM adm.AuditLog WHERE ObjectType = N'SystemSetting' ORDER BY Id")).all()
    assert [r[2] for r in rows] == ["PasswordMinLength", "PasswordRequireLetterAndDigit"]
    assert rows[0][:2] == ("Ayar değişikliği", owner)
    assert json.loads(rows[0][3]) == {"Value": 10} and json.loads(rows[0][4]) == {"Value": 12}


@pytest.mark.parametrize("body", [
    {"PasswordMinLength": 7}, {"PasswordMinLength": 129}, {"PasswordHistoryCount": 0}, {"PasswordMaxAgeDays": 0},
    {"LoginMaxFailedAttempts": 21}, {"LoginLockMinutes": 0}, {"SessionIdleMinutes": 0}, {"SessionWarningMinutes": 0},
])
def test_limits_refused_and_nothing_written(db_engine, client, people, body):
    r = client.put(URL, headers=auth(people[SYSTEM_OWNER]), json={**body, "PasswordMaxAgeDays": body.get("PasswordMaxAgeDays", 100)})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation"
    assert stored(db_engine, "PasswordMaxAgeDays") is None


def test_warning_must_be_shorter_than_idle(db_engine, client, people):
    h = auth(people[SYSTEM_OWNER])
    for body in ({"SessionWarningMinutes": 30}, {"SessionIdleMinutes": 5}, {"SessionIdleMinutes": 10, "SessionWarningMinutes": 10}):
        r = client.put(URL, headers=h, json=body)
        assert r.status_code == 422, body
        assert r.json()["error"]["details"][0]["field"] == "SessionWarningMinutes"
    assert client.put(URL, headers=h, json={"SessionIdleMinutes": 10, "SessionWarningMinutes": 2}).status_code == 200


def test_unknown_key_refused(client, people):
    assert client.put(URL, headers=auth(people[SYSTEM_OWNER]), json={"ListChunkSize": 5}).status_code == 422


def test_changes_take_effect(db_engine, client, people):
    h = auth(people[SYSTEM_OWNER])
    assert client.put(URL, headers=h, json={"SessionIdleMinutes": 45, "PasswordMinLength": 20, "LoginMaxFailedAttempts": 2}).status_code == 200
    me = client.get("/api/auth/me", headers=h).json()
    assert me["session"]["idle_minutes"] == 45 and me["policy"]["min_length"] == 20

    with Session(db_engine) as s:
        user_id = s.execute(text("INSERT INTO adm.AppUser (UserName, FullName, Role, MustChangePassword) OUTPUT inserted.Id "
                                 "VALUES (:n, N'Deneme', N'End user', 0)"), {"n": PREFIX + "giris"}).scalar_one()
        now = auth_repo.now(s)
        auth_repo.update_user(s, user_id, PasswordHash=security.hash_password(PASSWORD), PasswordChangedAt=now,
                              PasswordExpiresAt=auth_repo.expires_at(now, security.Policy()))
        s.commit()
    c = TestClient(create_app(), raise_server_exceptions=False)
    assert c.post("/api/auth/login", json={"user_name": PREFIX + "giris", "password": "yanlis"}).status_code == 401
    r = c.post("/api/auth/login", json={"user_name": PREFIX + "giris", "password": "yanlis"})
    assert r.json()["error"]["code"] == "account_locked"  # iki denemede kilit

    with db_engine.begin() as conn:
        conn.execute(text("UPDATE adm.AppUser SET LockedUntil = NULL, FailedAttempts = 0 WHERE Id = :i"), {"i": user_id})
    assert c.post("/api/auth/login", json={"user_name": PREFIX + "giris", "password": PASSWORD}).status_code == 200
    r = c.post("/api/auth/password", json={"current_password": PASSWORD, "new_password": "Kisa-sifre-26"})
    assert r.status_code == 422 and {"field": "new_password", "problem": "min_length"} in r.json()["error"]["details"]


@pytest.mark.parametrize("role", [ADMIN, KEY_USER, END_USER])
def test_policy_only_system_owner(client, people, role):
    h = auth(people[role])
    assert client.get(URL, headers=h).status_code == 403
    assert client.put(URL, headers=h, json={"PasswordMinLength": 12}).status_code == 403


# --- yetki matrisi ---

@pytest.mark.parametrize("role", [SYSTEM_OWNER, ADMIN])
def test_matrix_open_to_admin_and_owner(client, people, role):
    body = client.get("/api/permissions/matrix", headers=auth(people[role])).json()
    assert body["roles"] == [SYSTEM_OWNER, ADMIN, KEY_USER, END_USER]
    assert len(body["groups"]) == 17 and len(body["functions"]) == 100


@pytest.mark.parametrize("role", [KEY_USER, END_USER])
def test_matrix_closed_to_others(client, people, role):
    h = auth(people[role])
    assert client.get("/api/permissions/matrix", headers=h).status_code == 403
    assert client.get("/api/permissions/matrix/export", headers=h).status_code == 403


def test_matrix_excel_and_trace(db_engine, client, people):
    admin = people[ADMIN]
    r = client.get("/api/permissions/matrix/export", headers=auth(admin))
    assert r.status_code == 200, r.text
    assert "smartchain_yetki-matrisi_" in r.headers["content-disposition"]
    book = load_workbook(io.BytesIO(r.content))
    rows = list(book.worksheets[0].iter_rows(values_only=True))
    assert rows[0] == ("No", "Fonksiyon", "Grup", SYSTEM_OWNER, ADMIN, KEY_USER, END_USER)
    assert len(rows) == 101
    by_no = {row[0]: row for row in rows[1:]}
    assert by_no[86][6] == "Tam" and by_no[96][4] == "Yok" and by_no[22][6] == "Yok" and by_no[90][4] == "Salt okunur"
    assert by_no[50][5] == "Sahibi" and by_no[98][5] == "Kendi" and by_no[10][2] == "Ana veri" and by_no[16][2] == "Veri kuralları"
    assert {row[0] for row in book["Bilgi"].iter_rows(values_only=True)} >= {"Liste", "Dışa aktaran"}
    with db_engine.connect() as c:
        row = c.execute(text("SELECT UserId, ObjectType FROM adm.AuditLog WHERE Action = N'Dışa aktarım' AND ObjectType = N'permissions'")).first()
    assert tuple(row) == (admin, "permissions")
