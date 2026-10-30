"""Giriş ve oturum (fonksiyon 89; K-97, K-98): yerel SQL Server ile.

Deneme hesapları "pytest.giris" önekiyle açılır; oturumları, şifre geçmişi, sayaçları ve izleri her testten sonra silinir.
"""
import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api import security
from app.api.deps import COOKIE
from app.api.main import create_app
from app.api.repositories import auth as repo
from app.api.services import auth as service
from app.api.settings import get_settings

from auth_helpers import delete_users

pytestmark = pytest.mark.db

PASSWORD = "Baslangic-2026"
NAME = "pytest.giris"
UNKNOWN = "pytest.giris.yok"


def client() -> TestClient:
    return TestClient(create_app(), raise_server_exceptions=False)


def login(c: TestClient, name: str, password: str, **headers):
    return c.post("/api/auth/login", json={"user_name": name, "password": password}, headers=headers)


def body(r) -> tuple:
    """Hata cevabının takip numarası dışındaki her şeyi (sızdırmama karşılaştırması)."""
    e = r.json()["error"]
    return r.status_code, e["code"], e["message"], e["details"]


def run(engine, sql, **p):
    with engine.begin() as c:
        return c.execute(text(sql), p)


def rows(engine, sql, **p) -> list[tuple]:
    with engine.connect() as c:
        return [tuple(r) for r in c.execute(text(sql), p)]


def scalar(engine, sql, **p):
    with engine.connect() as c:
        return c.execute(text(sql), p).scalar()


def audits(engine, key):
    with engine.connect() as c:
        return [tuple(r) for r in c.execute(text(
            "SELECT Action, UserId, NewValue FROM adm.AuditLog WHERE ObjectKey = :k ORDER BY Id"), {"k": key})]


def clean(engine):
    with engine.begin() as c:
        ids = [r[0] for r in c.execute(text("SELECT Id FROM adm.AppUser WHERE UserName LIKE N'pytest.giris%'"))]
        delete_users(c, ids)
        c.execute(text("DELETE FROM adm.AuditLog WHERE ObjectKey LIKE N'pytest.giris%'"))
        c.execute(text("DELETE FROM adm.LoginThrottle WHERE UserName LIKE N'pytest.giris%'"))
        c.execute(text("DELETE FROM adm.SystemSetting WHERE SettingKey LIKE N'Password%' OR SettingKey LIKE N'Session%' "
                       "OR SettingKey LIKE N'Login%'"))


def make_user(engine, name=NAME, password=PASSWORD, must_change=False, active=True, role="Key user") -> int:
    with Session(engine) as s:
        user_id = s.execute(text(
            "INSERT INTO adm.AppUser (UserName, FullName, Role, IsActive, MustChangePassword) OUTPUT inserted.Id "
            "VALUES (:n, N'Pytest Giriş', :r, :a, 0)"), {"n": name, "r": role, "a": active}).scalar_one()
        if password:
            if must_change:
                service.set_temporary_password(s, user_id, password)
            else:
                now = repo.now(s)
                repo.update_user(s, user_id, PasswordHash=security.hash_password(password), PasswordChangedAt=now,
                                 PasswordExpiresAt=repo.expires_at(now, security.Policy()))
        s.commit()
    return user_id


@pytest.fixture
def engine(db_engine):
    clean(db_engine)
    yield db_engine
    clean(db_engine)


@pytest.fixture
def user(engine):
    return make_user(engine)


# --- giriş, çerez, iz ---

def test_login_sets_session_cookie_and_audits(engine, user, monkeypatch):
    c = client()
    r = login(c, NAME, PASSWORD)
    assert r.status_code == 200, r.text
    me = r.json()
    assert (me["id"], me["user_name"], me["role"], me["must_change_password"]) == (user, NAME, "Key user", False)
    assert me["session"] == {"idle_minutes": 30, "warning_minutes": 5}
    assert me["policy"] == {"min_length": 10, "require_letter_and_digit": True, "history_count": 5,
                            "lock_after": 5, "lock_minutes": 15}
    cookie = r.headers["set-cookie"]
    assert cookie.startswith(f"{COOKIE}=") and "HttpOnly" in cookie and "Path=/api" in cookie
    assert "SameSite=strict" in cookie and "Max-Age" not in cookie and "expires" not in cookie.lower()
    token = c.cookies[COOKIE]
    stored = scalar(engine, "SELECT TokenHash FROM adm.UserSession WHERE UserId = :u", u=user)
    assert stored == security.token_hash(token) and token.encode() not in stored
    assert scalar(engine, "SELECT LastLoginAt FROM adm.AppUser WHERE Id = :u", u=user) is not None
    assert [a[0] for a in audits(engine, NAME)] == ["Giriş"]
    assert c.get("/api/auth/me").json()["id"] == user
    assert c.get("/api/materials/columns").status_code == 200

    monkeypatch.setattr(get_settings(), "session_cookie_secure", True)
    assert "Secure" in login(client(), NAME, PASSWORD).headers["set-cookie"]


def test_wrong_password_counts_down_then_locks(engine, user):
    c = client()
    for remaining in (4, 3, 2, 1):
        r = login(c, NAME, "Yanlis-sifre-1")
        assert body(r) == (401, "login_failed", "Kullanıcı adı ya da şifre hatalı.",
                           [{"remaining_attempts": remaining, "lock_after": 5, "lock_minutes": 15}])
    r = login(c, NAME, "Yanlis-sifre-1")
    assert body(r)[:2] == (403, "account_locked") and r.json()["error"]["details"] == [{"minutes_left": 15}]
    assert "15 dk" in r.json()["error"]["message"] and "yöneticinize" in r.json()["error"]["message"]
    assert scalar(engine, "SELECT CASE WHEN LockedUntil > SYSUTCDATETIME() THEN 1 ELSE 0 END FROM adm.AppUser "
                          "WHERE Id = :u", u=user) == 1
    assert body(login(c, NAME, PASSWORD))[:2] == (403, "account_locked")  # doğru şifre de kilitte reddedilir
    actions = [a[0] for a in audits(engine, NAME)]
    assert actions.count("Başarısız giriş") == 6 and actions.count("Hesap kilitlendi") == 1

    run(engine, "UPDATE adm.AppUser SET LockedUntil = DATEADD(minute, -1, SYSUTCDATETIME()) WHERE Id = :u", u=user)
    r = login(c, NAME, "Yanlis-sifre-1")  # süre doldu: sayaç baştan
    assert r.json()["error"]["details"][0]["remaining_attempts"] == 4
    assert login(c, NAME, PASSWORD).status_code == 200
    assert scalar(engine, "SELECT FailedAttempts FROM adm.AppUser WHERE Id = :u", u=user) == 0


def test_unknown_user_gets_identical_responses(engine, user):
    """Hesabın varlığı sızmaz: bilinmeyen kullanıcı adı aynı mesaj, kalan deneme ve kilit dizisini alır (K-98)."""
    real = [body(login(client(), NAME, "Yanlis-sifre-1")) for _ in range(6)]
    fake = [body(login(client(), UNKNOWN, "Yanlis-sifre-1")) for _ in range(6)]
    assert fake == real
    assert real[-1][:2] == (403, "account_locked")
    assert scalar(engine, "SELECT FailedAttempts FROM adm.LoginThrottle WHERE UserName = :n", n=UNKNOWN) == 0
    assert [a[1] for a in audits(engine, UNKNOWN)][:1] == [None]


def test_inactive_account(engine):
    user = make_user(engine, active=False)
    r = login(client(), NAME, PASSWORD)
    assert body(r) == (403, "account_inactive", "Hesap kapalı. Yöneticinize başvurun.", [])
    assert scalar(engine, "SELECT FailedAttempts FROM adm.AppUser WHERE Id = :u", u=user) == 0
    assert scalar(engine, "SELECT COUNT(*) FROM adm.LoginThrottle WHERE UserName = :n", n=NAME) == 0
    r = login(client(), NAME, "Yanlis-sifre-1")  # şifre yanlışsa bilinmeyen kullanıcı gibi
    assert body(r)[:3] == (401, "login_failed", "Kullanıcı adı ya da şifre hatalı.")
    assert r.json()["error"]["details"][0]["remaining_attempts"] == 4


def test_account_without_password_cannot_log_in(engine):
    make_user(engine, password=None)
    for attempt in ("", "x", PASSWORD):
        r = login(client(), NAME, attempt or "a")
        assert body(r)[:2] == (401, "login_failed")


def test_session_required_everywhere_but_health_and_login(engine):
    c = client()
    for method, path in (("GET", "/api/auth/me"), ("POST", "/api/auth/activity"), ("POST", "/api/auth/logout"),
                         ("GET", "/api/jobs"), ("GET", "/api/data-versions/current"), ("GET", "/api/materials/columns"),
                         ("POST", "/api/materials/query"), ("GET", "/api/materials/views")):
        r = c.request(method, path, json={} if method == "POST" else None)
        assert (r.status_code, r.json()["error"]["code"]) == (401, "not_authenticated"), path
    assert c.get("/api/health").status_code in (200, 503)
    c.cookies.set(COOKIE, "bozuk")
    assert c.get("/api/auth/me").status_code == 401


# --- çıkış, hareketsizlik, etkinlik ---

def test_logout_ends_session(engine, user):
    c = client()
    login(c, NAME, PASSWORD)
    token = c.cookies[COOKIE]
    r = c.post("/api/auth/logout")
    assert r.status_code == 204 and f'{COOKIE}=""' in r.headers["set-cookie"]
    assert scalar(engine, "SELECT EndReason FROM adm.UserSession WHERE UserId = :u", u=user) == "Çıkış"
    c.cookies.set(COOKIE, token)  # eski anahtarla yeniden denenirse
    assert c.get("/api/auth/me").json()["error"]["code"] == "not_authenticated"
    assert [a[0] for a in audits(engine, NAME)] == ["Giriş", "Çıkış"]


def test_idle_session_expires(engine, user):
    c = client()
    login(c, NAME, PASSWORD)
    run(engine, "UPDATE adm.UserSession SET LastActivityAt = DATEADD(minute, -31, SYSUTCDATETIME()) WHERE UserId = :u",
        u=user)
    r = c.get("/api/materials/columns")
    assert body(r) == (401, "session_expired", "Oturumunuz 30 dakika hareketsizlik nedeniyle kapandı.", [])
    assert scalar(engine, "SELECT EndReason FROM adm.UserSession WHERE UserId = :u", u=user) == "Zaman aşımı"
    logout = [a for a in audits(engine, NAME) if a[0] == "Çıkış"]
    assert len(logout) == 1 and "Zaman aşımı" in logout[0][2]
    assert c.get("/api/auth/me").json()["error"]["code"] == "not_authenticated"


def test_only_user_activity_extends_session(engine, user):
    c = client()
    login(c, NAME, PASSWORD)

    def idle_seconds():
        return scalar(engine, "SELECT DATEDIFF(second, LastActivityAt, SYSUTCDATETIME()) FROM adm.UserSession "
                              "WHERE UserId = :u", u=user)

    run(engine, "UPDATE adm.UserSession SET LastActivityAt = DATEADD(minute, -10, SYSUTCDATETIME()) WHERE UserId = :u",
        u=user)
    for path in ("/api/materials/columns", "/api/jobs", "/api/auth/me"):
        assert c.get(path).status_code == 200
    c.post("/api/materials/query", json={})
    assert idle_seconds() >= 600  # arka plan istekleri uzatmaz
    assert c.get("/api/auth/me").json()["idle_seconds_left"] <= 20 * 60
    r = c.post("/api/auth/activity")
    assert r.status_code == 200 and r.json() == {"idle_seconds_left": 1800}
    assert idle_seconds() < 5
    run(engine, "INSERT INTO adm.SystemSetting (SettingKey, Value) VALUES (N'SessionIdleMinutes', N'3'), "
                "(N'SessionWarningMinutes', N'1')")
    assert c.get("/api/auth/me").json()["session"] == {"idle_minutes": 3, "warning_minutes": 1}


# --- şifre ---

def test_first_login_must_change_password(engine):
    user = make_user(engine, password="Gecici12345", must_change=True)
    c = client()
    me = login(c, NAME, "Gecici12345").json()
    assert (me["must_change_password"], me["password_change_reason"]) == (True, "İlk giriş")
    for path in ("/api/materials/columns", "/api/jobs", "/api/data-versions/current"):
        r = c.get(path)
        assert (r.status_code, r.json()["error"]["code"]) == (403, "password_change_required"), path
    with pytest.raises(Exception), c.websocket_connect("/api/ws"):
        pass
    assert c.get("/api/auth/me").status_code == 200 and c.post("/api/auth/activity").status_code == 200
    r = c.post("/api/auth/password", json={"current_password": "Gecici12345", "new_password": "Yeni-sifre-2026"})
    assert r.status_code == 204, r.text
    assert c.get("/api/materials/columns").status_code == 200
    [row] = rows(engine, "SELECT MustChangePassword, PasswordChangeReason, DATEDIFF(day, PasswordChangedAt, "
                         "PasswordExpiresAt) FROM adm.AppUser WHERE Id = :u", u=user)
    assert row == (False, None, 90)
    [(_, _, value)] = [a for a in audits(engine, NAME) if a[0] == "Şifre değişikliği"]
    assert '"reason": "İlk giriş"' in value


@pytest.mark.parametrize("new, problems", [
    ("Kisa-1", ["min_length"]),
    ("sadeceharfler-uzun", ["letter_and_digit"]),
    ("PYTEST.GIRIS-2026x", ["contains_user_name"]),
    ("kisa", ["min_length", "letter_and_digit"]),
    (PASSWORD, ["same_as_current"]),
])
def test_password_policy(engine, user, new, problems):
    c = client()
    login(c, NAME, PASSWORD)
    r = c.post("/api/auth/password", json={"current_password": PASSWORD, "new_password": new})
    assert r.status_code == 422 and r.json()["error"]["code"] == "password_policy"
    assert [d["problem"] for d in r.json()["error"]["details"]] == problems
    assert new not in r.text  # girilen şifre cevapta yok


def test_turkish_user_name_rule_and_disabled_letter_digit(engine):
    p = security.Policy()
    assert security.policy_problems(p, "ilker", "XİLKER-2026-abc") == ["contains_user_name"]
    assert security.policy_problems(p, "IŞIK", "ışık-2026-abcd") == ["contains_user_name"]
    run(engine, "INSERT INTO adm.SystemSetting (SettingKey, Value) VALUES (N'PasswordRequireLetterAndDigit', N'0'), "
                "(N'PasswordMinLength', N'0'), (N'SessionIdleMinutes', N'10'), (N'SessionWarningMinutes', N'10')")
    with Session(engine) as s:
        policy = repo.read_policy(s)
    assert (policy.require_letter_and_digit, policy.min_length) == (False, 10)  # 0 bayrakta geçerli, uzunlukta değil
    assert (policy.idle_minutes, policy.warning_minutes) == (10, 5)  # uyarı sınırdan kısa olmalı
    assert security.policy_problems(policy, "x", "sadeceharfler") == []


def test_password_history(engine, user):
    c = client()
    login(c, NAME, PASSWORD)
    passwords = [f"Gecmis-sifre-{i}" for i in range(1, 7)]
    current = PASSWORD
    for p in passwords[:5]:
        assert c.post("/api/auth/password", json={"current_password": current, "new_password": p}).status_code == 204
        current = p
    r = c.post("/api/auth/password", json={"current_password": current, "new_password": passwords[0]})
    assert [d["problem"] for d in r.json()["error"]["details"]] == ["history"]
    assert c.post("/api/auth/password", json={"current_password": current, "new_password": passwords[5]}).status_code == 204
    # geçmişte en çok 5 kayıt; en eski (1.) düştü, artık kabul
    assert scalar(engine, "SELECT COUNT(*) FROM adm.PasswordHistory WHERE UserId = :u", u=user) == 5
    r = c.post("/api/auth/password", json={"current_password": passwords[5], "new_password": passwords[0]})
    assert r.status_code == 204, r.text


def test_expired_password_must_change(engine, user):
    run(engine, "UPDATE adm.AppUser SET PasswordExpiresAt = DATEADD(day, -1, SYSUTCDATETIME()) WHERE Id = :u", u=user)
    c = client()
    me = login(c, NAME, PASSWORD).json()
    assert (me["must_change_password"], me["password_change_reason"]) == (True, "Süre doldu")
    assert c.get("/api/materials/columns").json()["error"]["code"] == "password_change_required"
    r = c.post("/api/auth/password", json={"current_password": PASSWORD, "new_password": "Yenilenen-2026"})
    assert r.status_code == 204 and c.get("/api/materials/columns").status_code == 200


def test_password_change_ends_other_sessions(engine, user):
    a, b = client(), client()
    login(a, NAME, PASSWORD)
    login(b, NAME, PASSWORD)  # aynı kullanıcı iki tarayıcıda
    assert a.get("/api/auth/me").status_code == 200 and b.get("/api/auth/me").status_code == 200
    assert a.post("/api/auth/password", json={"current_password": PASSWORD, "new_password": "Degisti-2026"}).status_code == 204
    assert a.get("/api/auth/me").status_code == 200
    assert b.get("/api/auth/me").json()["error"]["code"] == "not_authenticated"
    reasons = rows(engine, "SELECT EndReason FROM adm.UserSession WHERE UserId = :u ORDER BY Id", u=user)
    assert reasons == [(None,), ("Şifre değişti",)]


def test_wrong_current_password_does_not_lock(engine, user):
    c = client()
    login(c, NAME, PASSWORD)
    for _ in range(6):
        r = c.post("/api/auth/password", json={"current_password": "Yanlis-sifre-1", "new_password": "Yeni-sifre-2026"})
        assert body(r)[:2] == (401, "current_password_wrong")
    assert scalar(engine, "SELECT FailedAttempts FROM adm.AppUser WHERE Id = :u", u=user) == 0
    assert c.get("/api/auth/me").status_code == 200
    assert [a[0] for a in audits(engine, NAME)].count("Başarısız şifre değişikliği") == 6


# --- köken, gizlilik ---

def test_origin_check(engine, user, monkeypatch):
    assert body(login(client(), NAME, PASSWORD, origin="http://evil.example"))[:2] == (403, "bad_origin")
    assert login(client(), NAME, PASSWORD, origin="http://testserver").status_code == 200  # Host ile aynı
    monkeypatch.setattr(get_settings(), "allowed_origins", "http://localhost:5173, http://smartchain.local")
    assert login(client(), NAME, PASSWORD, origin="http://localhost:5173").status_code == 200
    assert login(client(), NAME, PASSWORD, origin="http://testserver").status_code == 403
    c = client()
    login(c, NAME, PASSWORD)
    assert c.get("/api/materials/columns", headers={"origin": "http://evil.example"}).status_code == 200  # GET serbest
    assert c.post("/api/materials/query", json={}, headers={"origin": "http://evil.example"}).status_code == 403


def test_password_never_logged_or_stored(engine, caplog):
    make_user(engine, password="Gizli-gecici-77", must_change=True)
    c = client()
    with caplog.at_level(logging.DEBUG):
        login(c, NAME, "Yanlis-gizli-88")
        login(c, NAME, "Gizli-gecici-77")
        c.post("/api/auth/password", json={"current_password": "Gizli-gecici-77", "new_password": "Gizli-yeni-99x"})
        r = c.post("/api/auth/login", json={"user_name": NAME, "password": "Uzun-gizli-" + "x" * 300})
    assert r.status_code == 422 and "Uzun-gizli" not in r.text
    with engine.connect() as conn:
        stored = " ".join(str(v) for row in conn.execute(text(
            "SELECT NewValue, OldValue FROM adm.AuditLog WHERE ObjectKey = :k"), {"k": NAME}) for v in row)
        stored += " ".join(conn.execute(text("SELECT h.PasswordHash FROM adm.PasswordHistory h JOIN adm.AppUser u "
                                             "ON u.Id = h.UserId WHERE u.UserName = :k"), {"k": NAME}).scalars())
    for secret in ("Yanlis-gizli-88", "Gizli-gecici-77", "Gizli-yeni-99x"):
        assert secret not in caplog.text and secret not in stored


# --- yardımcılar ---

def test_argon2_hash_format():
    h1, h2 = security.hash_password("Ayni-sifre-1"), security.hash_password("Ayni-sifre-1")
    assert h1.startswith("$argon2id$v=19$m=19456,t=2,p=1$") and h1 != h2 and len(h1) <= 200
    assert security.verify_password(h1, "Ayni-sifre-1") and not security.verify_password(h1, "ayni-sifre-1")
    assert not security.verify_password(None, "x") and not security.verify_password("bozuk", "x")
    assert not security.needs_rehash(h1)
    from argon2 import PasswordHasher
    assert security.needs_rehash(PasswordHasher(time_cost=1, memory_cost=8192).hash("x"))
    assert security.token_hash("kısa") is None and len(security.token_hash(security.new_token())) == 32


def test_temporary_password_meets_policy():
    for _ in range(50):
        p = security.temporary_password()
        assert len(p) == 12 and security.policy_problems(security.Policy(), "sahip", p) == []


def test_synthetic_users_command(engine, monkeypatch, tmp_path):
    from app.data.synthetic import users
    monkeypatch.setattr(users, "USERS", [(NAME, "Pytest Sentetik", "End user")])
    first = users.reset_users(engine)
    second = users.reset_users(engine)  # yeniden çalıştırma: aynı hesap, yeni geçici şifre
    assert first[0][0] == second[0][0] == NAME and first[0][2] != second[0][2]
    me = login(client(), NAME, second[0][2]).json()
    assert (me["role"], me["must_change_password"], me["password_change_reason"]) == ("End user", True, "İlk giriş")
    assert login(client(), NAME, first[0][2]).status_code == 401
    path = tmp_path / ".local" / "gecici-sifreler.txt"
    users.write_file(path, second)
    assert second[0][2] in path.read_text(encoding="utf-8") and "repoya" in path.read_text(encoding="utf-8")


def test_local_secrets_stay_out_of_git_and_package():
    root = Path(__file__).resolve().parents[1]
    assert ".local/" in (root / ".gitignore").read_text(encoding="utf-8")
    build = (root / "installer" / "build.ps1").read_text(encoding="utf-8-sig")
    assert ".local" not in build and "Copy-Tree (Join-Path $Root 'app')" in build
