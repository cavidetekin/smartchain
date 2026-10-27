"""Kayıtlı görünüm sorguları (adm.TableView, adm.TableViewDefault; K-89)."""
import sqlalchemy as sa
from sqlalchemy.orm import Session

from db.models import metadata

VIEW = metadata.tables["adm.TableView"]
DEFAULT = metadata.tables["adm.TableViewDefault"]
USER = metadata.tables["adm.AppUser"]


def user_exists(session: Session, user_id: int) -> bool:
    return session.execute(sa.select(USER.c.Id).where(USER.c.Id == user_id)).first() is not None


def _select():
    owner = sa.func.coalesce(USER.c.FullName, USER.c.UserName).label("OwnerName")
    return sa.select(VIEW, owner).select_from(VIEW.join(USER, USER.c.Id == VIEW.c.OwnerUserId))


def list_views(session: Session, list_name: str, user_id: int) -> list[dict]:
    """Kullanıcının kendi görünümleri ve başkalarının paylaşılanları; ada göre (Türkçe)."""
    q = (_select().where(VIEW.c.ListName == list_name,
                         sa.or_(VIEW.c.OwnerUserId == user_id, VIEW.c.IsShared == sa.true()))
         .order_by(VIEW.c.Name.collate("Turkish_100_CI_AS")))
    return [dict(r) for r in session.execute(q).mappings()]


def get_view(session: Session, list_name: str, view_id: int) -> dict | None:
    row = session.execute(_select().where(VIEW.c.Id == view_id, VIEW.c.ListName == list_name)).mappings().first()
    return dict(row) if row else None


def insert_view(session: Session, values: dict) -> int:
    return session.execute(sa.insert(VIEW).values(**values).returning(VIEW.c.Id)).scalar_one()


def update_view(session: Session, view_id: int, values: dict) -> None:
    session.execute(sa.update(VIEW).where(VIEW.c.Id == view_id).values(**values))


def delete_view(session: Session, view_id: int) -> None:
    """Görünümü siler; onu varsayılan seçmiş kullanıcılar Standart'a döner."""
    session.execute(sa.delete(DEFAULT).where(DEFAULT.c.ViewId == view_id))
    session.execute(sa.delete(VIEW).where(VIEW.c.Id == view_id))


def read_default(session: Session, user_id: int, list_name: str) -> int | None:
    return session.execute(sa.select(DEFAULT.c.ViewId).where(DEFAULT.c.UserId == user_id,
                                                           DEFAULT.c.ListName == list_name)).scalar()


def set_default(session: Session, user_id: int, list_name: str, view_id: int | None) -> None:
    session.execute(sa.delete(DEFAULT).where(DEFAULT.c.UserId == user_id, DEFAULT.c.ListName == list_name))
    if view_id is not None:
        session.execute(sa.insert(DEFAULT).values(UserId=user_id, ListName=list_name, ViewId=view_id))


def now(session: Session):
    return session.execute(sa.text("SELECT SYSUTCDATETIME()")).scalar_one()
