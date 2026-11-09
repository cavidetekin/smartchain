"""İşlenmiş katman (K-140): ham katmanın güncel satırlarının kopyası; her çalıştırmada baştan kurulur, kurallar bunun üzerinde çalışır.

Kopya çağıranın işleminde yapılır (commit çağıranındır): iş düşerse işlenmiş katman önceki hâlinde kalır.
"""
import sqlalchemy as sa
from sqlalchemy.orm import Session

from db.models import metadata

from .sqlkit import current, raw_table, table

EFFECT = metadata.tables["adm.DataRuleEffect"]
ROW_NEW = "Yeni"


def rebuild(session: Session, entity: str) -> int:
    """prc.<Tablo> boşaltılır, stg.<Tablo>'nun güncel satırları kopyalanır, tablonun kural izi silinir. Kopyalanan satır sayısı."""
    p, r = table(entity), raw_table(entity)
    names = [c.name for c in p.columns if c.name != "RowStatus"]
    session.execute(sa.delete(p))
    added = session.execute(sa.insert(p).from_select([*names, "RowStatus"],
                                                     sa.select(*[r.c[n] for n in names], sa.literal(ROW_NEW, sa.Unicode(15))).where(current(r)))).rowcount
    session.execute(sa.delete(EFFECT).where(EFFECT.c.EntityName == entity))
    return added
