"""Kayıtlı görünüm sorguları (adm.TableView, adm.TableViewDefault, adm.TableViewStandard; K-89, K-162)."""
import sqlalchemy as sa
from sqlalchemy.orm import Session

from db.models import metadata

VIEW = metadata.tables["adm.TableView"]
DEFAULT = metadata.tables["adm.TableViewDefault"]
STANDARD = metadata.tables["adm.TableViewStandard"]
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


def get_standard(session: Session, list_name: str) -> dict | None:
    """Şirket Standart'ı (K-162) ve kaydedenin adı."""
    name = sa.func.coalesce(USER.c.FullName, USER.c.UserName).label("UpdatedByName")
    row = session.execute(sa.select(STANDARD, name).select_from(STANDARD.join(USER, USER.c.Id == STANDARD.c.UpdatedBy))
                          .where(STANDARD.c.ListName == list_name)).mappings().first()
    return dict(row) if row else None


def save_standard(session: Session, list_name: str, definition: str, known: str, user_id: int, at) -> None:
    values = {"Definition": definition, "KnownFields": known, "UpdatedAt": at, "UpdatedBy": user_id}
    if session.execute(sa.update(STANDARD).where(STANDARD.c.ListName == list_name).values(**values)).rowcount == 0:
        session.execute(sa.insert(STANDARD).values(ListName=list_name, **values))


def delete_standard(session: Session, list_name: str) -> bool:
    return session.execute(sa.delete(STANDARD).where(STANDARD.c.ListName == list_name)).rowcount > 0


def now(session: Session):
    return session.execute(sa.text("SELECT SYSUTCDATETIME()")).scalar_one()
