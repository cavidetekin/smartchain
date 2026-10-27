"""Liste sorguları (K-87): sorgu kurucunun ürettiği sorguları çalıştırır; FieldDefinition etiketlerini okur."""
import sqlalchemy as sa
from sqlalchemy.orm import Session

from db.models import metadata


def read_labels(session: Session, table_name: str) -> dict[str, str]:
    """FieldDefinition.Label (K-88): alan → etiket; boş etiketler atlanır."""
    fd = metadata.tables["adm.FieldDefinition"]
    rows = session.execute(sa.select(fd.c.FieldName, fd.c.Label)
                           .where(fd.c.TableName == table_name, fd.c.Label.is_not(None), fd.c.Label != ""))
    return {name: label.strip() for name, label in rows if label.strip()}


def fetch_rows(session: Session, query: sa.Select) -> list[dict]:
    return [dict(r) for r in session.execute(query).mappings()]


def fetch_count(session: Session, query: sa.Select) -> int:
    return int(session.execute(query).scalar_one() or 0)
