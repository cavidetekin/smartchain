"""Liste sorgusu performans hedefi (docs/12, K-87): 50.000 satırda ilk parça ve sayılar ortanca 300 ms altında.

Satırlar bir işlem içinde T-SQL ile üretilir, ölçülür ve işlem geri alınır; veritabanında iz kalmaz.
"""
import statistics
import time

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.lists import MATERIALS
from app.api.lists.request import FilterItem, QueryRequest, SortItem, ValuesRequest
from app.api.services import lists as service

pytestmark = [pytest.mark.db, pytest.mark.perf]

ROWS = 50_000
TARGET_MS = 300
RUNS = 5

GENERATE = text("""
INSERT INTO core.Material (Id, VersionFrom, LocationId, Code, Name, BaseUom, MaterialGroup, MaterialLevel,
                           SafetyStock, AdditionalText1, BusinessKey, UpdatedAt)
SELECT 1000000 + n, :v, :loc, CONCAT('PERF-', RIGHT('00000' + CAST(n AS varchar(6)), 6)),
       CONCAT(CHOOSE(n % 4 + 1, N'Çelik mil ', N'Rulman ', N'Sac levha ', N'İşlenmiş kapak '), n),
       N'ADET', CHOOSE(n % 6 + 1, N'Çubuk', N'Levha', N'Rulman', N'Conta', N'Dövme', N'İşlenmiş parça'),
       CHOOSE(n % 3 + 1, N'Hammadde', N'Yarı mamul', N'Nihai ürün'), n % 500, CHOOSE(n % 3 + 1, 'A', 'B', 'C'),
       CONCAT('PERF-', n), SYSUTCDATETIME()
FROM (SELECT TOP (:rows) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS n
      FROM sys.all_objects a CROSS JOIN sys.all_objects b) x
""")


def median_ms(work) -> float:
    times = []
    for _ in range(RUNS):
        start = time.perf_counter()
        work()
        times.append((time.perf_counter() - start) * 1000)
    return statistics.median(times)


@pytest.fixture
def big_session(db_engine):
    conn = db_engine.connect()
    trans = conn.begin()
    session = Session(bind=conn)
    try:
        v, loc = conn.execute(text("SELECT TOP 1 Id, LocationId FROM adm.DataVersion ORDER BY Id DESC")).one()
        conn.execute(GENERATE, {"v": v, "loc": loc, "rows": ROWS})
        yield session
    finally:
        session.close()
        trans.rollback()
        conn.close()


def test_first_chunk_and_counts_under_target(big_session):
    req = QueryRequest(
        filters=[FilterItem(field="Name", op="contains", value="çelik"),
                 FilterItem(field="MaterialLevel", op="in", values=["Hammadde", "Yarı mamul"])],
        sort=[SortItem(field="MaterialGroup"), SortItem(field="SafetyStock", dir="desc")], limit=100)
    body = service.query(big_session, MATERIALS, req)
    assert body["total"] >= ROWS and body["filtered"] > 0 and len(body["rows"]) == 100
    ms = median_ms(lambda: service.query(big_session, MATERIALS, req))
    print(f"\nsorgu (50.000 satır, filtre + 2 sıralama + 100 satır + sayılar): ortanca {ms:.0f} ms")
    assert ms < TARGET_MS


def test_last_chunk_under_target(big_session):
    req = QueryRequest(sort=[SortItem(field="Name", dir="desc")], offset=ROWS - 100, limit=100)
    ms = median_ms(lambda: service.query(big_session, MATERIALS, req))
    print(f"\nson parça (offset {ROWS - 100}): ortanca {ms:.0f} ms")
    assert ms < TARGET_MS


def test_values_under_target(big_session):
    req = ValuesRequest(field="MaterialGroup", search="U", filters=[FilterItem(field="Name", op="contains", value="MİL")])
    assert service.values(big_session, MATERIALS, req)
    ms = median_ms(lambda: service.values(big_session, MATERIALS, req))
    print(f"\ndeğerler: ortanca {ms:.0f} ms")
    assert ms < TARGET_MS
