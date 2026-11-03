"""Veri sözlüğü sorguları (adm.FieldDefinition; K-104). Commit çağırana bırakılır."""
import sqlalchemy as sa
from sqlalchemy.orm import Session

from db.models import metadata

FD = metadata.tables["adm.FieldDefinition"]
VIEW = metadata.tables["adm.TableView"]


def get_field(session: Session, table: str, field: str) -> dict | None:
    row = session.execute(sa.select(FD).where(FD.c.TableName == table, FD.c.FieldName == field)).mappings().first()
    return dict(row) if row else None


def label_taken(session: Session, table: str, field: str, label: str) -> bool:
    """Aynı tabloda başka bir alan bu etiketle görünüyor mu (veritabanının büyük/küçük harf duyarsız karşılaştırmasıyla)."""
    return session.execute(sa.select(FD.c.FieldName).where(
        FD.c.TableName == table, FD.c.FieldName != field,
        sa.func.coalesce(FD.c.Label, FD.c.StandardLabel) == label)).first() is not None


def set_label(session: Session, table: str, field: str, label: str | None) -> None:
    session.execute(sa.update(FD).where(FD.c.TableName == table, FD.c.FieldName == field).values(Label=label))


def view_definitions(session: Session, list_names: list[str]) -> list[str]:
    """Bu listelerdeki bütün kayıtlı görünümlerin tanımları (kimin olduğundan bağımsız)."""
    if not list_names:
        return []
    return list(session.execute(sa.select(VIEW.c.Definition).where(VIEW.c.ListName.in_(list_names))).scalars())
