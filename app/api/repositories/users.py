"""Kullanıcı yönetimi sorguları (adm.AppUser, adm.UserSession; fonksiyon 88, K-101). Commit çağırana bırakılır."""
import sqlalchemy as sa
from sqlalchemy.orm import Session

from ..lists.query import like_escape
from ..lists.users import SOURCE
from ..permissions import ADMIN, SYSTEM_OWNER
from .auth import SESSION, USER


def get_status(session: Session, user_id: int) -> str | None:
    return session.execute(sa.select(SOURCE.c.Status).where(SOURCE.c.Id == user_id)).scalar_one_or_none()


def open_sessions(session: Session, user_id: int) -> int:
    return session.execute(sa.select(sa.func.count()).select_from(SESSION)
                           .where(SESSION.c.UserId == user_id, SESSION.c.EndedAt.is_(None))).scalar_one()


def active_admins(session: Session, lock: bool = False) -> list[int]:
    """Aktif Admin'ler. lock: işlem bitene kadar kilitler; iki Admin birbirini aynı anda kapatamaz (K-101)."""
    q = sa.select(USER.c.Id).where(USER.c.Role == ADMIN, USER.c.IsActive == sa.true())
    if lock:
        q = q.with_hint(USER, "WITH (UPDLOCK, HOLDLOCK)", "mssql")
    return list(session.execute(q).scalars())


def first_system_owner(session: Session) -> dict | None:
    row = session.execute(sa.select(USER).where(USER.c.Role == SYSTEM_OWNER).order_by(USER.c.Id)).mappings().first()
    return dict(row) if row else None


def names_like(session: Session, prefix: str) -> set[str]:
    """Bu önekle başlayan kullanıcı adları (pasifler dahil), küçük harfle."""
    rows = session.execute(sa.select(USER.c.UserName).where(USER.c.UserName.like(like_escape(prefix) + "%", escape="\\")))
    return {name.lower() for name in rows.scalars()}


def insert_user(session: Session, user_name: str, full_name: str, role: str) -> int:
    return session.execute(sa.insert(USER).values(UserName=user_name, FullName=full_name, Role=role, IsActive=True)
                           .returning(USER.c.Id)).scalar_one()
