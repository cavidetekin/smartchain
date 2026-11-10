"""Ham veri temizliği performansı (K-156): 25 tablo × 50.000 güncel olmayan satır, partiler saklama süresinden eski.

Satırlar doğrudan ham katmana yazılır. Her ölçüm aynı işlemde yapılıp geri alınır; ortanca. Ayrıca: pytest -m perf -k cleanup.
"""
import statistics
import time

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.cleanup import raw
from app.integration.contract import ENTITIES

from test_validation_perf import PARALLEL_ROWS, fill
from validation_helpers import clean

pytestmark = [pytest.mark.db, pytest.mark.perf]

RUNS = 3
DAYS = 7
LIMIT_SECONDS = 1800


@pytest.fixture(scope="module")
def old(db_engine):
    clean(db_engine)
    for e in ENTITIES:
        fill(db_engine, e.table, PARALLEL_ROWS)
    with db_engine.begin() as c:
        for e in ENTITIES:
            c.execute(sa.text(f"UPDATE stg.[{e.table}] SET IsCurrent = 0"))
        c.execute(sa.text("UPDATE adm.ImportBatch SET ReceivedAt = DATEADD(day, -10, SYSUTCDATETIME())"))
    yield db_engine
    clean(db_engine)


def test_cleanup_50k(old):
    times, rows = [], 0
    for _ in range(RUNS):
        with Session(old) as s:
            start = time.perf_counter()
            summary, _paths = raw.run(s, DAYS)
            times.append(time.perf_counter() - start)
            rows = summary.rows
            s.rollback()
    m = statistics.median(times)
    print(f"\nHam veri temizliği, {len(ENTITIES)} tablo × {PARALLEL_ROWS:,} satır: ortanca {m:.1f} sn ({', '.join(f'{t:.1f}' for t in times)}); "
          f"silinen {rows:,} satır")
    assert rows == len(ENTITIES) * PARALLEL_ROWS
    assert m < LIMIT_SECONDS
