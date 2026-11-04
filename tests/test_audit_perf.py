"""Denetim izi performansı (K-108): süresiz saklandığı için tablo büyür. Veri işlem içinde eklenir, sonunda geri alınır."""
import statistics
import time

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.lists.audit_log import AUDIT_LOG
from app.api.lists.request import QueryRequest
from app.api.permissions import ADMIN
from app.api.services import lists as service

pytestmark = [pytest.mark.db, pytest.mark.perf]

ROWS = 200_000
RUNS = 5
TARGET_MS = 300


def median_ms(work) -> float:
    times = []
    for _ in range(RUNS):
        start = time.perf_counter()
        work()
        times.append((time.perf_counter() - start) * 1000)
    return statistics.median(times)


@pytest.fixture
def big_log(db_engine):
    with Session(db_engine) as s:
        s.execute(text(
            f"INSERT INTO adm.AuditLog (At, Action, ObjectType, ObjectKey, NewValue) "
            f"SELECT TOP {ROWS} DATEADD(second, -1 * ROW_NUMBER() OVER (ORDER BY (SELECT NULL)), SYSUTCDATETIME()), N'İş iptali', N'Job', "
            "CONCAT(N'perf-', ROW_NUMBER() OVER (ORDER BY (SELECT NULL))), N'{\"status\": \"İptal\"}' "
            "FROM sys.all_objects a CROSS JOIN sys.all_objects b"))
        yield s
        s.rollback()


def test_first_chunk_and_counts(big_log):
    ms = median_ms(lambda: service.query(big_log, AUDIT_LOG, QueryRequest(limit=100), ADMIN, 1))
    print(f"\ndenetim izi ({ROWS} satır, ilk parça + sayılar): ortanca {ms:.0f} ms")
    assert ms < TARGET_MS


def test_object_key_search(big_log):
    body = QueryRequest(limit=100, filters=[{"field": "ObjectShown", "op": "contains", "value": "perf-1999"}])
    ms = median_ms(lambda: service.query(big_log, AUDIT_LOG, body, ADMIN, 1))
    print(f"\ndenetim izi nesne araması: ortanca {ms:.0f} ms")
    assert ms < TARGET_MS * 3
