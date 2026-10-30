"""Giriş ve oturum sorguları (adm.AppUser, adm.UserSession, adm.PasswordHistory, adm.LoginThrottle; K-97, K-98).

Zaman karşılaştırmaları veritabanı saatiyle (SYSUTCDATETIME) yapılır; API ile veritabanı arasındaki saat farkı etkilemez.
Commit çağırana bırakılır.
"""
from datetime import datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.jobs.settings import read_int_settings
from db.models import metadata
from ..security import Policy

USER = metadata.tables["adm.AppUser"]
SESSION = metadata.tables["adm.UserSession"]
HISTORY = metadata.tables["adm.PasswordHistory"]
THROTTLE = metadata.tables["adm.LoginThrottle"]

POLICY_KEYS = {
    "PasswordMinLength": "min_length", "PasswordRequireLetterAndDigit": "require_letter_and_digit",
    "PasswordHistoryCount": "history_count", "PasswordMaxAgeDays": "max_age_days",
    "SessionIdleMinutes": "idle_minutes", "SessionWarningMinutes": "warning_minutes",
    "LoginMaxFailedAttempts": "lock_after", "LoginLockMinutes": "lock_minutes",
}
_DEFAULTS = {key: int(getattr(Policy(), attr)) for key, attr in POLICY_KEYS.items()}


def read_policy(session: Session) -> Policy:
    """SystemSetting'ten; satır yoksa ya da bozuksa varsayılan. Bayrak 0 olabilir, diğerleri en az 1."""
    values = read_int_settings(session, _DEFAULTS, minimum=0)
    for key, value in values.items():
        if value < 1 and key != "PasswordRequireLetterAndDigit":
            values[key] = _DEFAULTS[key]
    v = {POLICY_KEYS[k]: value for k, value in values.items()}
    v["require_letter_and_digit"] = bool(v["require_letter_and_digit"])
    # Uyarı süresi hareketsizlik sınırından kısa olmalı; değilse sınırın yarısı.
    if v["warning_minutes"] >= v["idle_minutes"]:
        v["warning_minutes"] = max(1, v["idle_minutes"] // 2) if v["idle_minutes"] > 1 else 0
    return Policy(**v)


def now(session: Session) -> datetime:
    return session.execute(sa.select(sa.func.sysutcdatetime())).scalar_one()


# --- Kullanıcı ---

def find_user(session: Session, user_name: str) -> dict | None:
    row = session.execute(sa.select(USER).where(USER.c.UserName == user_name)).mappings().first()
    return dict(row) if row else None


def get_user(session: Session, user_id: int) -> dict | None:
    row = session.execute(sa.select(USER).where(USER.c.Id == user_id)).mappings().first()
    return dict(row) if row else None


def update_user(session: Session, user_id: int, **values) -> None:
    session.execute(sa.update(USER).where(USER.c.Id == user_id).values(**values))


# --- Bilinmeyen ya da pasif hesap adına sayaç ---

def get_throttle(session: Session, user_name: str) -> dict | None:
    row = session.execute(sa.select(THROTTLE).where(THROTTLE.c.UserName == user_name)).mappings().first()
    return dict(row) if row else None


def save_throttle(session: Session, user_name: str, attempts: int, locked_until: datetime | None, at: datetime) -> None:
    values = {"FailedAttempts": attempts, "LockedUntil": locked_until, "UpdatedAt": at}
    if session.execute(sa.update(THROTTLE).where(THROTTLE.c.UserName == user_name).values(**values)).rowcount == 0:
        session.execute(sa.insert(THROTTLE).values(UserName=user_name, **values))


def delete_throttle(session: Session, user_name: str) -> None:
    session.execute(sa.delete(THROTTLE).where(THROTTLE.c.UserName == user_name))


def purge_throttle(session: Session, older_than: datetime) -> None:
    session.execute(sa.delete(THROTTLE).where(THROTTLE.c.UpdatedAt < older_than,
                                              sa.or_(THROTTLE.c.LockedUntil.is_(None), THROTTLE.c.LockedUntil < older_than)))


# --- Oturum ---

def insert_session(session: Session, token_hash: bytes, user_id: int, at: datetime, address: str | None,
                   agent: str | None) -> int:
    return session.execute(sa.insert(SESSION).values(
        TokenHash=token_hash, UserId=user_id, CreatedAt=at, LastActivityAt=at,
        ClientAddress=(address or None) and address[:45], UserAgent=(agent or None) and agent[:200],
    ).returning(SESSION.c.Id)).scalar_one()


def session_with_user(session: Session, token_hash: bytes) -> dict | None:
    """Oturum, kullanıcısı ve veritabanı saati tek sorguda."""
    q = (sa.select(SESSION.c.Id.label("SessionId"), SESSION.c.UserId, SESSION.c.LastActivityAt, SESSION.c.EndedAt,
                   USER.c.UserName, USER.c.FullName, USER.c.Role, USER.c.IsActive, USER.c.MustChangePassword,
                   USER.c.PasswordChangeReason, USER.c.PasswordExpiresAt,
                   sa.func.sysutcdatetime().label("Now"))
         .select_from(SESSION.join(USER, USER.c.Id == SESSION.c.UserId))
         .where(SESSION.c.TokenHash == token_hash))
    row = session.execute(q).mappings().first()
    return dict(row) if row else None


def touch_session(session: Session, session_id: int) -> None:
    session.execute(sa.update(SESSION).where(SESSION.c.Id == session_id)
                    .values(LastActivityAt=sa.func.sysutcdatetime()))


def end_session(session: Session, session_id: int, reason: str) -> bool:
    """Açık oturumu kapatır; zaten kapalıysa False."""
    return session.execute(sa.update(SESSION).where(SESSION.c.Id == session_id, SESSION.c.EndedAt.is_(None))
                           .values(EndedAt=sa.func.sysutcdatetime(), EndReason=reason)).rowcount > 0


def end_user_sessions(session: Session, user_id: int, reason: str, keep: int | None = None) -> list[int]:
    """Kullanıcının açık oturumlarını kapatır (keep hariç); kapananların Id'leri."""
    cond = [SESSION.c.UserId == user_id, SESSION.c.EndedAt.is_(None)]
    if keep is not None:
        cond.append(SESSION.c.Id != keep)
    ids = [r[0] for r in session.execute(sa.select(SESSION.c.Id).where(*cond))]
    if ids:
        session.execute(sa.update(SESSION).where(SESSION.c.Id.in_(ids))
                        .values(EndedAt=sa.func.sysutcdatetime(), EndReason=reason))
    return ids


def idle_sessions(session: Session, idle_minutes: int) -> list[dict]:
    """Hareketsizlik sınırını geçmiş, henüz kapanmamış oturumlar."""
    q = (sa.select(SESSION.c.Id, SESSION.c.UserId, USER.c.UserName)
         .select_from(SESSION.join(USER, USER.c.Id == SESSION.c.UserId))
         .where(SESSION.c.EndedAt.is_(None),
                SESSION.c.LastActivityAt < sa.func.dateadd(sa.text("minute"), -idle_minutes, sa.func.sysutcdatetime())))
    return [dict(r) for r in session.execute(q).mappings()]


def closed_among(session: Session, ids: list[int]) -> set[int]:
    """Verilen oturumlardan kapanmış olanlar ya da kullanıcısı pasif olanlar."""
    if not ids:
        return set()
    q = (sa.select(SESSION.c.Id).select_from(SESSION.join(USER, USER.c.Id == SESSION.c.UserId))
         .where(SESSION.c.Id.in_(ids), sa.or_(SESSION.c.EndedAt.is_not(None), USER.c.IsActive == sa.false())))
    return {r[0] for r in session.execute(q)}


# --- Şifre geçmişi ---

def recent_hashes(session: Session, user_id: int, count: int) -> list[str]:
    q = (sa.select(HISTORY.c.PasswordHash).where(HISTORY.c.UserId == user_id)
         .order_by(HISTORY.c.CreatedAt.desc(), HISTORY.c.Id.desc()).limit(count))
    return [r[0] for r in session.execute(q)]


def add_history(session: Session, user_id: int, password_hash: str, at: datetime, keep: int) -> None:
    session.execute(sa.insert(HISTORY).values(UserId=user_id, PasswordHash=password_hash, CreatedAt=at))
    keep_ids = sa.select(HISTORY.c.Id).where(HISTORY.c.UserId == user_id) \
        .order_by(HISTORY.c.CreatedAt.desc(), HISTORY.c.Id.desc()).limit(max(keep, 1))
    session.execute(sa.delete(HISTORY).where(HISTORY.c.UserId == user_id, HISTORY.c.Id.not_in(keep_ids.scalar_subquery())))


def clear_history(session: Session, user_id: int) -> None:
    session.execute(sa.delete(HISTORY).where(HISTORY.c.UserId == user_id))


def expires_at(at: datetime, policy: Policy) -> datetime:
    return at + timedelta(days=policy.max_age_days)
