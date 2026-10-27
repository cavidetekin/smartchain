"""PlanningData'nın SQL uygulaması: core.* tablolarını veri versiyonuna göre salt okunur verir (K-58, K-63)."""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.orm import Session

from db.models import metadata


class SqlPlanningData:
    def __init__(self, session: Session, data_version_id: int):
        self.session = session
        self.data_version_id = data_version_id

    def read(self, table: str, columns: Sequence[str] | None = None) -> list[dict]:
        name = table if "." in table else f"core.{table}"
        if not name.startswith("core."):
            raise ValueError(f"Motor yalnız core tablolarını okur: {table}")
        t = metadata.tables.get(name)
        if t is None:
            raise ValueError(f"Bilinmeyen tablo: {table}")
        if columns:
            unknown = [c for c in columns if c not in t.c]
            if unknown:
                raise ValueError(f"{name}: bilinmeyen alan {', '.join(unknown)}")
            q = sa.select(*(t.c[c] for c in columns))
        else:
            q = sa.select(t)
        if "VersionFrom" in t.c:
            v = self.data_version_id
            q = q.where(t.c.VersionFrom <= v, sa.or_(t.c.VersionTo.is_(None), t.c.VersionTo >= v))
        if "Id" in t.c:
            q = q.order_by(t.c.Id)
        return [dict(r) for r in self.session.execute(q).mappings()]
