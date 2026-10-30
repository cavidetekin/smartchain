"""Giriş, oturum ve şifre (fonksiyon 89; K-97, K-98).

- Giriş cevabı hesabın varlığını sızdırmaz: bilinmeyen, şifresiz ya da (şifre yanlışken) pasif hesap adına denemeler
  adm.LoginThrottle'da gerçek hesaptaki sayaçla aynı biçimde işler. "Hesap kapalı" yalnız şifre doğruysa söylenir.
- Oturum hareketsizlik sınırını geçince bir sonraki istekte (ya da izleyicinin taramasında) "Zaman aşımı" ile kapanır.
- Şifre hiçbir yere düz metin olarak yazılmaz.
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from .. import security
from ..errors import AppError
from ..repositories import audit, auth as repo

log = logging.getLogger("smartchain.auth")

DB_DOWN = "Veritabanına bağlanılamıyor; oturum denetlenemedi."
USER_NAME_MAX = 60

# Denetim izi eylemleri (K-98)
LOGIN = "Giriş"
LOGIN_FAILED = "Başarısız giriş"
LOCKED = "Hesap kilitlendi"
LOGOUT = "Çıkış"
PASSWORD_CHANGED = "Şifre değişikliği"
PASSWORD_CHANGE_FAILED = "Başarısız şifre değişikliği"
OBJECT = "Kullanıcı"

# Oturum kapanış sebepleri (UserSession.EndReason)
END_LOGOUT = "Çıkış"
END_TIMEOUT = "Zaman aşımı"
END_PASSWORD = "Şifre değişti"
END_CLOSED = "Kapatıldı"

REASON_FIRST = "İlk giriş"
REASON_RESET = "Sıfırlama"
REASON_EXPIRED = "Süre doldu"


@dataclass(frozen=True)
class CurrentUser:
    id: int
    user_name: str
    full_name: str | None
    role: str
    session_id: int
    must_change_password: bool
    password_change_reason: str | None
    idle_seconds_left: int


def _require(session: Session | None) -> Session:
    if session is None:
        raise AppError("database_unavailable", DB_DOWN, 503)
    return session


def _db(work):
    try:
        return work()
    except DBAPIError as exc:
        raise AppError("database_unavailable", DB_DOWN, 503) from exc


def _minutes_left(until: datetime, now: datetime) -> int:
    return max(1, -(-int((until - now).total_seconds()) // 60))  # yukarı yuvarlanmış dakika


def _locked_error(minutes: int) -> AppError:
    return AppError("account_locked",
                    f"Hesap kilitli. {minutes} dk sonra yeniden deneyin ya da yöneticinize başvurun.",
                    403, [{"minutes_left": minutes}])


def _failed_error(remaining: int, policy: security.Policy) -> AppError:
    return AppError("login_failed", "Kullanıcı adı ya da şifre hatalı.", 401,
                    [{"remaining_attempts": remaining, "lock_after": policy.lock_after,
                      "lock_minutes": policy.lock_minutes}])


def _client(address: str | None, agent: str | None) -> dict:
    return {"address": address, "user_agent": (agent or "")[:200] or None}


def login(session: Session | None, user_name: str, password: str, address: str | None,
          agent: str | None) -> tuple[str, CurrentUser]:
    """Başarılıysa (oturum anahtarı, kullanıcı); değilse AppError (login_failed, account_locked, account_inactive)."""
    session = _require(session)
    name = user_name.strip()[:USER_NAME_MAX]

    def work():
        policy = repo.read_policy(session)
        now = repo.now(session)
        user = repo.find_user(session, name) if name else None
        if user is not None and user["PasswordHash"] and user["IsActive"]:
            return _login_real(session, policy, now, user, password, address, agent)
        # Bilinmeyen, şifresiz ya da pasif hesap: aynı sayaç ve aynı mesajlar (K-98).
        throttle = repo.get_throttle(session, name) or {"FailedAttempts": 0, "LockedUntil": None}
        user_id = user["Id"] if user else None
        if throttle["LockedUntil"] and throttle["LockedUntil"] > now:
            security.verify_password(None, password)
            _audit_failed(session, user_id, name, "locked", None, address, agent)
            session.commit()
            raise _locked_error(_minutes_left(throttle["LockedUntil"], now))
        if user is not None and user["PasswordHash"] and security.verify_password(user["PasswordHash"], password):
            # Pasif hesap, şifre doğru: "hesap kapalı"; sayaç artmaz.
            _audit_failed(session, user_id, name, "inactive", None, address, agent)
            session.commit()
            raise AppError("account_inactive", "Hesap kapalı. Yöneticinize başvurun.", 403)
        if user is None or not user["PasswordHash"]:
            security.verify_password(None, password)
        attempts = (0 if throttle["LockedUntil"] else throttle["FailedAttempts"]) + 1
        locked_until = now + timedelta(minutes=policy.lock_minutes) if attempts >= policy.lock_after else None
        repo.save_throttle(session, name, 0 if locked_until else attempts, locked_until, now)
        return _after_failure(session, policy, now, user_id, name, attempts, locked_until, address, agent)

    return _db(work)


def _login_real(session, policy, now, user, password, address, agent):
    name = user["UserName"]
    locked = user["LockedUntil"]
    if locked and locked > now:
        security.verify_password(None, password)
        _audit_failed(session, user["Id"], name, "locked", None, address, agent)
        session.commit()
        raise _locked_error(_minutes_left(locked, now))
    if not security.verify_password(user["PasswordHash"], password):
        attempts = (0 if locked else (user["FailedAttempts"] or 0)) + 1
        locked_until = now + timedelta(minutes=policy.lock_minutes) if attempts >= policy.lock_after else None
        repo.update_user(session, user["Id"], FailedAttempts=0 if locked_until else attempts, LockedUntil=locked_until)
        return _after_failure(session, policy, now, user["Id"], name, attempts, locked_until, address, agent)

    values = {"FailedAttempts": 0, "LockedUntil": None, "LastLoginAt": now}
    if security.needs_rehash(user["PasswordHash"]):
        values["PasswordHash"] = security.hash_password(password)
    if not user["MustChangePassword"] and user["PasswordExpiresAt"] and user["PasswordExpiresAt"] <= now:
        values.update(MustChangePassword=True, PasswordChangeReason=REASON_EXPIRED)
    repo.update_user(session, user["Id"], **values)
    repo.delete_throttle(session, name)
    token = security.new_token()
    session_id = repo.insert_session(session, security.token_hash(token), user["Id"], now, address, agent)
    audit.write_audit(session, LOGIN, user["Id"], OBJECT, name, {**_client(address, agent), "session_id": session_id})
    session.commit()
    must = bool(values.get("MustChangePassword", user["MustChangePassword"]))
    reason = values.get("PasswordChangeReason", user["PasswordChangeReason"]) if must else None
    return token, CurrentUser(user["Id"], name, user["FullName"], user["Role"], session_id, must,
                              reason or (REASON_FIRST if must else None), policy.idle_minutes * 60)


def _after_failure(session, policy, now, user_id, name, attempts, locked_until, address, agent):
    _audit_failed(session, user_id, name, "password", max(policy.lock_after - attempts, 0), address, agent)
    if locked_until:
        audit.write_audit(session, LOCKED, user_id, OBJECT, name, {"locked_until": locked_until, **_client(address, agent)})
        session.commit()
        raise _locked_error(policy.lock_minutes)
    session.commit()
    raise _failed_error(policy.lock_after - attempts, policy)


def _audit_failed(session, user_id, name, reason, remaining, address, agent):
    audit.write_audit(session, LOGIN_FAILED, user_id, OBJECT, name or "(boş)",
                      {"reason": reason, "remaining_attempts": remaining, **_client(address, agent)})


def authenticate(session: Session | None, token: str | None) -> CurrentUser:
    """Çerezdeki anahtarla oturumu ve kullanıcıyı doğrular (her istek). Hareketsizlik sınırı geçtiyse oturumu kapatır."""
    digest = security.token_hash(token) if token else None
    if digest is None:
        raise AppError("not_authenticated", "Oturum açmanız gerekiyor.", 401)
    session = _require(session)

    def work():
        row = repo.session_with_user(session, digest)
        if row is None or row["EndedAt"] is not None:
            raise AppError("not_authenticated", "Oturum açmanız gerekiyor.", 401)
        if not row["IsActive"]:
            repo.end_session(session, row["SessionId"], END_CLOSED)
            session.commit()
            raise AppError("not_authenticated", "Oturum açmanız gerekiyor.", 401)
        policy = repo.read_policy(session)
        left = policy.idle_minutes * 60 - int((row["Now"] - row["LastActivityAt"]).total_seconds())
        if left <= 0:
            _end_idle(session, row["SessionId"], row["UserId"], row["UserName"], policy)
            session.commit()
            raise AppError("session_expired",
                           f"Oturumunuz {policy.idle_minutes} dakika hareketsizlik nedeniyle kapandı.", 401)
        expired = bool(row["PasswordExpiresAt"] and row["PasswordExpiresAt"] <= row["Now"])
        must = bool(row["MustChangePassword"]) or expired
        reason = (row["PasswordChangeReason"] or REASON_FIRST) if row["MustChangePassword"] else (REASON_EXPIRED if expired else None)
        return CurrentUser(row["UserId"], row["UserName"], row["FullName"], row["Role"], row["SessionId"], must,
                           reason, left)

    return _db(work)


def _end_idle(session: Session, session_id: int, user_id: int, user_name: str, policy: security.Policy) -> None:
    if repo.end_session(session, session_id, END_TIMEOUT):
        audit.write_audit(session, LOGOUT, user_id, OBJECT, user_name,
                          {"reason": END_TIMEOUT, "session_id": session_id, "idle_minutes": policy.idle_minutes})


def expire_idle_sessions(session: Session) -> list[int]:
    """İzleyicinin taraması: hareketsizlik sınırını geçmiş açık oturumları kapatır; kapananların Id'leri."""
    policy = repo.read_policy(session)
    rows = repo.idle_sessions(session, policy.idle_minutes)
    for r in rows:
        _end_idle(session, r["Id"], r["UserId"], r["UserName"], policy)
    repo.purge_throttle(session, repo.now(session) - timedelta(days=1))
    session.commit()
    return [r["Id"] for r in rows]


def me(session: Session | None, user: CurrentUser) -> dict:
    session = _require(session)
    policy = _db(lambda: repo.read_policy(session))
    return public(user, policy)


def public(user: CurrentUser, policy: security.Policy) -> dict:
    return {
        "id": user.id, "user_name": user.user_name, "full_name": user.full_name, "role": user.role,
        "must_change_password": user.must_change_password, "password_change_reason": user.password_change_reason,
        "idle_seconds_left": user.idle_seconds_left,
        "session": {"idle_minutes": policy.idle_minutes, "warning_minutes": policy.warning_minutes},
        "policy": policy.public(),
    }


def activity(session: Session | None, user: CurrentUser) -> dict:
    session = _require(session)

    def work():
        repo.touch_session(session, user.session_id)
        session.commit()
        return {"idle_seconds_left": repo.read_policy(session).idle_minutes * 60}

    return _db(work)


def logout(session: Session | None, user: CurrentUser) -> None:
    session = _require(session)

    def work():
        if repo.end_session(session, user.session_id, END_LOGOUT):
            audit.write_audit(session, LOGOUT, user.id, OBJECT, user.user_name,
                              {"reason": END_LOGOUT, "session_id": user.session_id})
        session.commit()

    _db(work)


def change_password(session: Session | None, user: CurrentUser, current: str, new: str) -> list[int]:
    """Şifreyi değiştirir; kullanıcının diğer oturumlarını kapatır ve onların Id'lerini döndürür."""
    session = _require(session)

    def work():
        policy = repo.read_policy(session)
        row = repo.get_user(session, user.id)
        if row is None or not security.verify_password(row["PasswordHash"], current):
            # Oturum içinde yanlış mevcut şifre kilit sayacına girmez; yalnız iz (K-98).
            audit.write_audit(session, PASSWORD_CHANGE_FAILED, user.id, OBJECT, user.user_name,
                              {"reason": "current_password_wrong", "session_id": user.session_id})
            session.commit()
            raise AppError("current_password_wrong", "Mevcut şifre hatalı.", 401)
        problems = security.policy_problems(policy, user.user_name, new)
        if new == current:
            problems.append("same_as_current")
        elif any(security.verify_password(h, new) for h in repo.recent_hashes(session, user.id, policy.history_count)):
            problems.append("history")
        if problems:
            raise AppError("password_policy", "Yeni şifre politikaya uymuyor.", 422,
                           [{"field": "new_password", "problem": p} for p in problems])
        now = repo.now(session)
        new_hash = security.hash_password(new)
        reason = user.password_change_reason if user.must_change_password else "Kullanıcı isteği"
        repo.update_user(session, user.id, PasswordHash=new_hash, MustChangePassword=False, PasswordChangeReason=None,
                         PasswordChangedAt=now, PasswordExpiresAt=repo.expires_at(now, policy))
        repo.add_history(session, user.id, new_hash, now, policy.history_count)
        repo.touch_session(session, user.session_id)
        ended = repo.end_user_sessions(session, user.id, END_PASSWORD, keep=user.session_id)
        audit.write_audit(session, PASSWORD_CHANGED, user.id, OBJECT, user.user_name,
                          {"reason": reason, "session_id": user.session_id, "ended_sessions": ended})
        session.commit()
        return ended

    return _db(work)


def open_session(session: Session, user_id: int, address: str | None = None, agent: str | None = None) -> str:
    """Şifre sormadan oturum açar: yalnız testler ve geliştirme script'leri için (anahtar döner)."""
    token = security.new_token()
    repo.insert_session(session, security.token_hash(token), user_id, repo.now(session), address, agent)
    session.commit()
    return token


def set_temporary_password(session: Session, user_id: int, password: str, reason: str = REASON_FIRST) -> None:
    """Geçici şifre: bir sonraki girişte değiştirilmeli; geçmiş ve kilit temizlenir (sentetik veri; 2.3'te sıfırlama)."""
    repo.update_user(session, user_id, PasswordHash=security.hash_password(password), MustChangePassword=True,
                     PasswordChangeReason=reason, PasswordChangedAt=None, PasswordExpiresAt=None, FailedAttempts=0,
                     LockedUntil=None)
    repo.clear_history(session, user_id)
