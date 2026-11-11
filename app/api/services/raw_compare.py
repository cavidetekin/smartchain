"""Dünden bugüne özeti (ekran 28, fonksiyon 101; K-160): ana sayfanın okuyacağı toplamlar."""
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.compare import raw as compare
from db.models import metadata

from . import auth

SUMMARY = metadata.tables["adm.RawCompare"]


def summary(session: Session | None) -> dict:
    session = auth._require(session)

    def work():
        row = session.execute(sa.select(sa.func.count(), sa.func.sum(SUMMARY.c.NewCount), sa.func.sum(SUMMARY.c.MissingCount), sa.func.sum(SUMMARY.c.ChangedCount),
                                        sa.func.max(SUMMARY.c.TodayAt)).where(SUMMARY.c.State == compare.READY)).one()
        return {"tables": int(row[0] or 0), "new": int(row[1] or 0), "missing": int(row[2] or 0), "changed": int(row[3] or 0), "today_at": row[4]}

    return auth._db(work)
