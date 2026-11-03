"""Kullanıcı yönetimi (fonksiyon 88, K-101) ve kurulumda ilk hesap (K-102).

Koruma kuralları tek yerdedir (`refusal`): hem satır menüsünün izinlerini (`detail`) hem yazma uçlarını besler; arayüzdeki
pasif düğme ile sunucu reddi ayrışamaz. Geçici şifre yalnız commit başarılıysa döner; veritabanına özeti yazılır, başka
hiçbir yere yazılmaz.
"""
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import permissions as perm, security
from ..errors import AppError
from ..lists.users import LOCKED
from ..permissions import ADMIN, SYSTEM_OWNER, Access
from ..repositories import audit, auth as auth_repo, users as repo
from . import auth, authz
from .auth import CurrentUser

FN = 88
OBJECT = "Kullanıcı"

CREATED = "Kullanıcı oluşturuldu"
ROLE_CHANGED = "Rol değişikliği"
NAME_CHANGED = "Ad soyad değişikliği"
PASSWORD_RESET = "Şifre sıfırlama"
UNLOCKED = "Kilit açıldı"
CLOSED = "Kullanıcı kapatıldı"
REOPENED = "Kullanıcı geri açıldı"

ACTIONS = ("role", "name", "reset", "unlock", "close", "reopen")

FIRST_USER_NAME = "smartchain"
FIRST_FULL_NAME = "Destek ekibi"


@dataclass(frozen=True)
class Refusal:
    rule: str
    message: str
    required_role: str | None = None  # dolu: yetki reddi (403 forbidden); boş: koruma kuralı (409 user_protected)


_SELF = {
    "role": "Kendi rolünüzü değiştiremezsiniz.",
    "reset": "Kendi şifrenizi kullanıcı menüsünden değiştirin.",
    "close": "Kendinizi kapatamazsınız.",
}
_OWNER = {
    "role": "System owner hesabının rolü değiştirilemez.",
    "close": "System owner hesabı kapatılamaz.",
}
_LAST_ADMIN = {
    "role": "Son aktif Admin'in rolü değiştirilemez. Önce başka bir Admin açın.",
    "close": "Son aktif Admin kapatılamaz. Önce başka bir Admin açın.",
}
_INACTIVE = "Hesap kapalı. Önce geri açın."


def _owner_only() -> Refusal:
    return Refusal("system_owner", perm.role_message(SYSTEM_OWNER), SYSTEM_OWNER)


def refusal(action: str, actor: CurrentUser, target: dict, status: str, admins: list[int],
            new_role: str | None = None) -> Refusal | None:
    """Bu işlem yapılamıyorsa nedeni; yapılabiliyorsa None (K-101). Yetki matrisi require ile denetlenmiş olur."""
    own = target["Id"] == actor.id
    owner = target["Role"] == SYSTEM_OWNER
    active = bool(target["IsActive"])
    last_admin = target["Role"] == ADMIN and active and len(admins) <= 1
    if action == "name":
        return None
    if action == "reopen":
        return Refusal("already_active", "Hesap zaten açık.") if active else None
    if action in _SELF and own:
        return Refusal("self", _SELF[action])
    if action == "close":
        if owner:
            return Refusal("system_owner", _OWNER[action])
        if not active:
            return Refusal("already_inactive", "Hesap zaten kapalı.")
        return Refusal("last_admin", _LAST_ADMIN[action]) if last_admin else None
    if not active:
        return Refusal("inactive", _INACTIVE)
    if action == "role":
        if owner:
            return Refusal("system_owner", _OWNER[action])
        if last_admin and new_role != ADMIN:
            return Refusal("last_admin", _LAST_ADMIN[action])
        return _owner_only() if new_role == SYSTEM_OWNER and actor.role != SYSTEM_OWNER else None
    if action == "reset":
        return None
    if action == "unlock":
        return None if status == LOCKED else Refusal("not_locked", "Hesap kilitli değil.")
    raise ValueError(action)


def _refuse(session: Session, actor: CurrentUser, action: str, target_name: str, found: Refusal) -> AppError:
    session.rollback()  # kilitler bırakılır, ret izi kendi oturumunda yazılır
    authz.record_denial(actor, FN, Access.WRITE, {"action": action, "reason": found.rule, "target": target_name})
    if found.required_role:
        return AppError("forbidden", found.message, 403, [{
            "function": FN, "function_name": perm.FUNCTIONS[FN].name, "access": Access.WRITE.value,
            "required_role": found.required_role}])
    return AppError("user_protected", found.message, 409, [{"rule": found.rule}])


def _target(session: Session, user_id: int) -> dict:
    row = auth_repo.get_user(session, user_id)
    if row is None:
        raise AppError("user_not_found", "Kullanıcı bulunamadı.", 404)
    return row


def _visible(session: Session, actor: CurrentUser, user_id: int, access: Access) -> dict:
    """System owner hesabı Admin için yokmuş gibidir (K-101): bilinmeyen hesapla aynı 404; deneme ize yazılır."""
    row = _target(session, user_id)
    if row["Role"] == SYSTEM_OWNER and actor.role != SYSTEM_OWNER:
        authz.record_denial(actor, FN, access, {"reason": "hidden_account", "target_id": user_id})
        raise AppError("user_not_found", "Kullanıcı bulunamadı.", 404)
    return row


def _iso(value: datetime | None) -> str | None:
    return value.replace(tzinfo=timezone.utc).isoformat(timespec="seconds") if value else None


def _public(session: Session, row: dict) -> dict:
    return {"id": row["Id"], "user_name": row["UserName"], "full_name": row["FullName"], "role": row["Role"],
            "status": repo.get_status(session, row["Id"]), "is_active": bool(row["IsActive"]),
            "last_login_at": _iso(row["LastLoginAt"]), "open_sessions": repo.open_sessions(session, row["Id"])}


def assignable_roles(actor: CurrentUser) -> list[str]:
    """System owner rolünü yalnız System owner verir (fonksiyon 88)."""
    return [r for r in perm.ROLES if r != SYSTEM_OWNER or actor.role == SYSTEM_OWNER]


def detail(session: Session | None, actor: CurrentUser, user_id: int) -> dict:
    """Satır menüsü: güncel kayıt ve her işlemin izni, nedeni. Rolde "System owner verilebilir mi" assignable_roles'ta."""
    session = auth._require(session)

    def work():
        row = _visible(session, actor, user_id, Access.READ)
        status, admins = repo.get_status(session, user_id), repo.active_admins(session)
        actions = {}
        for action in ACTIONS:
            found = refusal(action, actor, row, status, admins)
            actions[action] = {"allowed": found is None, "reason": found.message if found else None,
                               "required_role": found.required_role if found else None}
        return {"user": _public(session, row), "actions": actions, "assignable_roles": assignable_roles(actor)}

    return auth._db(work)


def suggest_user_name(session: Session, user_name: str) -> str:
    """burak doluysa burak2; burak2 doluysa burak3. Pasif hesaplar da sayılır (K-101)."""
    base = user_name.rstrip("0123456789") or user_name
    taken = repo.names_like(session, base)
    n = 2
    while True:
        candidate = f"{base[:60 - len(str(n))]}{n}"
        if candidate.lower() not in taken:
            return candidate
        n += 1


def _taken(session: Session, user_name: str) -> AppError:
    return AppError("user_name_taken", "Bu kullanıcı adı kullanılıyor.", 409, [{
        "field": "user_name", "problem": "Bu kullanıcı adı kullanılıyor.",
        "suggestion": suggest_user_name(session, user_name)}])


def create(session: Session | None, actor: CurrentUser, full_name: str, user_name: str, role: str) -> dict:
    session = auth._require(session)

    def work():
        if role == SYSTEM_OWNER and actor.role != SYSTEM_OWNER:
            raise _refuse(session, actor, "create", user_name, _owner_only())
        if auth_repo.find_user(session, user_name) is not None:
            raise _taken(session, user_name)
        password = security.temporary_password(auth_repo.read_policy(session), user_name)
        try:
            user_id = repo.insert_user(session, user_name, full_name, role)
            auth.set_temporary_password(session, user_id, password)
            audit.write_audit(session, CREATED, actor.id, OBJECT, user_name,
                              {"UserName": user_name, "FullName": full_name, "Role": role})
            session.commit()
        except IntegrityError as exc:  # aynı anda açıldıysa benzersiz indeks yakalar
            session.rollback()
            raise _taken(session, user_name) from exc
        return {"user": _public(session, _target(session, user_id)), "temporary_password": password}

    return auth._db(work)


def _guarded(session: Session, actor: CurrentUser, action: str, user_id: int, new_role: str | None = None) -> dict:
    """Hedefi okur, son Admin sayımını işlem içinde kilitler, kuralı uygular."""
    row = _visible(session, actor, user_id, Access.WRITE)
    admins = repo.active_admins(session, lock=action in ("role", "close"))
    found = refusal(action, actor, row, repo.get_status(session, user_id), admins, new_role)
    if found:
        raise _refuse(session, actor, action, row["UserName"], found)
    return row


def _done(session: Session, user_id: int) -> dict:
    session.commit()
    return {"user": _public(session, _target(session, user_id))}


def change_role(session: Session | None, actor: CurrentUser, user_id: int, role: str) -> dict:
    session = auth._require(session)

    def work():
        row = _guarded(session, actor, "role", user_id, role)
        if row["Role"] == role:
            return _done(session, user_id)
        auth_repo.update_user(session, user_id, Role=role)
        audit.write_audit(session, ROLE_CHANGED, actor.id, OBJECT, row["UserName"], {"Role": role}, {"Role": row["Role"]})
        return _done(session, user_id)

    return auth._db(work)


def change_name(session: Session | None, actor: CurrentUser, user_id: int, full_name: str) -> dict:
    session = auth._require(session)

    def work():
        row = _guarded(session, actor, "name", user_id)
        if row["FullName"] == full_name:
            return _done(session, user_id)
        auth_repo.update_user(session, user_id, FullName=full_name)
        audit.write_audit(session, NAME_CHANGED, actor.id, OBJECT, row["UserName"],
                          {"FullName": full_name}, {"FullName": row["FullName"]})
        return _done(session, user_id)

    return auth._db(work)


def _reset(session: Session, row: dict, actor_id: int | None, source: dict | None = None) -> tuple[str, list[int]]:
    """Yeni geçici şifre; oturumlar kapanır, şifre geçmişi korunur (K-98, K-101). Commit çağırana bırakılır."""
    password = security.temporary_password(auth_repo.read_policy(session), row["UserName"])
    auth.set_temporary_password(session, row["Id"], password, auth.REASON_RESET, keep_history=True)
    ended = auth_repo.end_user_sessions(session, row["Id"], auth.END_PASSWORD)
    audit.write_audit(session, PASSWORD_RESET, actor_id, OBJECT, row["UserName"],
                      {"MustChangePassword": True, "PasswordChangeReason": auth.REASON_RESET, "ended_sessions": ended,
                       **(source or {})},
                      {"MustChangePassword": bool(row["MustChangePassword"])})
    return password, ended


def reset_password(session: Session | None, actor: CurrentUser, user_id: int) -> tuple[dict, list[int]]:
    """(cevap, kapanan oturumlar); kapananların WebSocket'lerini yönlendirici kapatır."""
    session = auth._require(session)

    def work():
        row = _guarded(session, actor, "reset", user_id)
        password, ended = _reset(session, row, actor.id)
        return {**_done(session, user_id), "temporary_password": password}, ended

    return auth._db(work)


def unlock(session: Session | None, actor: CurrentUser, user_id: int) -> dict:
    session = auth._require(session)

    def work():
        row = _guarded(session, actor, "unlock", user_id)
        auth_repo.update_user(session, user_id, FailedAttempts=0, LockedUntil=None)
        audit.write_audit(session, UNLOCKED, actor.id, OBJECT, row["UserName"],
                          {"LockedUntil": None, "FailedAttempts": 0},
                          {"LockedUntil": row["LockedUntil"], "FailedAttempts": row["FailedAttempts"]})
        return _done(session, user_id)

    return auth._db(work)


def close(session: Session | None, actor: CurrentUser, user_id: int) -> tuple[dict, list[int]]:
    """(cevap, kapanan oturumlar). Kullanıcı silinmez, pasif olur."""
    session = auth._require(session)

    def work():
        row = _guarded(session, actor, "close", user_id)
        auth_repo.update_user(session, user_id, IsActive=False)
        ended = auth_repo.end_user_sessions(session, user_id, auth.END_CLOSED)
        audit.write_audit(session, CLOSED, actor.id, OBJECT, row["UserName"],
                          {"IsActive": False, "ended_sessions": ended}, {"IsActive": True})
        return _done(session, user_id), ended

    return auth._db(work)


def reopen(session: Session | None, actor: CurrentUser, user_id: int) -> dict:
    """Geri açma şifreyi değiştirmez; kilit ve sayaçlar temizlenir (pasifken yapılan denemeler LoginThrottle'da)."""
    session = auth._require(session)

    def work():
        row = _guarded(session, actor, "reopen", user_id)
        auth_repo.update_user(session, user_id, IsActive=True, FailedAttempts=0, LockedUntil=None)
        auth_repo.delete_throttle(session, row["UserName"])
        audit.write_audit(session, REOPENED, actor.id, OBJECT, row["UserName"], {"IsActive": True}, {"IsActive": False})
        return _done(session, user_id)

    return auth._db(work)


def first_account(session: Session, reset: bool = False) -> tuple[str, str] | None:
    """Kurulumda ilk hesap (K-102): System owner yoksa açar. Varsa dokunmaz (None); reset=True ise o hesaba yeni geçici
    şifre verir (unutulan şifre). (kullanıcı adı, geçici şifre) döner; commit eder, şifre bundan sonra gösterilmelidir."""
    owner = repo.first_system_owner(session)
    source = {"source": "kurulum"}
    if owner is not None:
        if not reset:
            return None
        password, _ = _reset(session, owner, None, source)
        session.commit()
        return owner["UserName"], password
    user_name = FIRST_USER_NAME
    if auth_repo.find_user(session, user_name) is not None:
        user_name = suggest_user_name(session, user_name)
    password = security.temporary_password(auth_repo.read_policy(session), user_name)
    user_id = repo.insert_user(session, user_name, FIRST_FULL_NAME, SYSTEM_OWNER)
    auth.set_temporary_password(session, user_id, password)
    audit.write_audit(session, CREATED, None, OBJECT, user_name,
                      {"UserName": user_name, "FullName": FIRST_FULL_NAME, "Role": SYSTEM_OWNER, **source})
    session.commit()
    return user_name, password
