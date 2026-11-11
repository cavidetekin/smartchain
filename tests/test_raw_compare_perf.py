"""Dünden bugüne performansı (K-160): 25 tablo × 50.000 satır, iki günlük hâl; satırların %10'unda bir alan değişik.

Satırlar doğrudan ham katmana yazılır. Her ölçüm aynı işlemde yapılıp geri alınır; ortanca. Ayrıca: pytest -m perf -k raw_compare.
"""
import statistics
import time
from datetime import datetime

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.compare import raw as compare
from app.integration.contract import ENTITIES, stg_columns
from app.integration.structural import key_fields

from test_validation_perf import PARALLEL_ROWS, fill
from validation_helpers import clean

pytestmark = [pytest.mark.db, pytest.mark.perf]

RUNS = 3
LIMIT_SECONDS = 600
DAY1, DAY2 = datetime(2030, 1, 10, 9), datetime(2030, 1, 11, 9)


def _text_field(entity: str) -> str | None:
    keys = set(key_fields(entity))
    return next((c.name for c in stg_columns(entity) if isinstance(c.type, sa.Unicode) and c.name not in keys and not c.name.startswith("Additional") and (c.type.length or 0) >= 5), None)


@pytest.fixture(scope="module")
def two_days(db_engine):
    clean(db_engine)
    for e in ENTITIES:
        fill(db_engine, e.table, PARALLEL_ROWS)
        with db_engine.begin() as c:
            c.execute(sa.text(f"UPDATE stg.[{e.table}] SET IsCurrent = 0, SupersededAt = :d"), {"d": DAY2})
            c.execute(sa.text("UPDATE adm.ImportBatch SET AppliedAt = :d WHERE EntityName = :e"), {"d": DAY1, "e": e.table})
        fill(db_engine, e.table, PARALLEL_ROWS)
        field = _text_field(e.table)
        with db_engine.begin() as c:
            c.execute(sa.text("UPDATE adm.ImportBatch SET AppliedAt = :d WHERE EntityName = :e AND AppliedAt IS NULL"), {"d": DAY2, "e": e.table})
            if field:
                c.execute(sa.text(f"UPDATE stg.[{e.table}] SET [{field}] = LEFT(N'X' + ISNULL([{field}], N''), 5) WHERE IsCurrent = 1 AND SourceRowNo % 10 = 0"))
    yield db_engine
    clean(db_engine)


def test_raw_compare_50k(two_days):
    totals, slowest, changed = [], 0.0, 0
    for _ in range(RUNS):
        with Session(two_days) as s:
            start = time.perf_counter()
            for e in ENTITIES:
                began = time.perf_counter()
                compare.compute(s, e.table)
                slowest = max(slowest, time.perf_counter() - began)
            totals.append(time.perf_counter() - start)
            changed = s.execute(sa.select(sa.func.sum(compare.SUMMARY.c.ChangedCount))).scalar() or 0
            s.rollback()
    m = statistics.median(totals)
    print(f"\nDünden bugüne, {len(ENTITIES)} tablo × {PARALLEL_ROWS:,} satır: toplam ortanca {m:.1f} sn ({', '.join(f'{t:.1f}' for t in totals)}), en yavaş tablo {slowest:.1f} sn; güncellenen {changed:,}")
    assert changed > 0
    assert m < LIMIT_SECONDS
