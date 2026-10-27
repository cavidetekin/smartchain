"""Liste sorguları (K-87): sorgu kurucunun ürettiği sorguları çalıştırır; FieldDefinition etiketlerini okur."""
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.jobs.settings import read_int_settings
from db.models import metadata

from ..lists.request import DEFAULT_CHUNK_SIZE, MAX_LIMIT


def read_chunk_size(session: Session) -> int:
    """SystemSetting ListChunkSize (docs/02): varsayılan 100, en çok 500."""
    return min(read_int_settings(session, {"ListChunkSize": DEFAULT_CHUNK_SIZE})["ListChunkSize"], MAX_LIMIT)


def read_labels(session: Session, table_name: str) -> dict[str, str]:
    """FieldDefinition.Label (K-88): alan → etiket; boş etiketler atlanır."""
    fd = metadata.tables["adm.FieldDefinition"]
    rows = session.execute(sa.select(fd.c.FieldName, fd.c.Label)
                           .where(fd.c.TableName == table_name, fd.c.Label.is_not(None), fd.c.Label != ""))
    return {name: label.strip() for name, label in rows if label.strip()}


def read_unit_decimals(session: Session) -> dict[str, int | None]:
    """UnitOfMeasure.Decimals (K-88): birim kodu → ondalık. Küçük tablo; her sorguda bir kez okunur."""
    uom = metadata.tables["core.UnitOfMeasure"]
    return {code: decimals for code, decimals in session.execute(sa.select(uom.c.Code, uom.c.Decimals))}


def fetch_rows(session: Session, query: sa.Select) -> list[dict]:
    return [dict(r) for r in session.execute(query).mappings()]


def fetch_count(session: Session, query: sa.Select) -> int:
    return int(session.execute(query).scalar_one() or 0)
