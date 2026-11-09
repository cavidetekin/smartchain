"""Validasyon performansı (K-134): 200.000 satırlık Malzeme'nin tablo içi doğrulaması ve "Veri işleme" kanalında paralel iş sayısı.

Satırlar doğrudan stg'ye, güncel hâlde yazılır (çekim ve ön kontrol ölçülmez; docs/08'de ayrı ölçüm). Her ölçüm ortancadır.
Paralel ölçüm: sekiz büyük tablonun tablo içi işleri N ayrı süreçte (motor servisi gibi); toplam duvar saati. Ayrıca: pytest -m perf.
"""
import multiprocessing
import statistics
import time

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.integration import contract
from app.integration.contract import stg_columns
from app.jobs import queue
from app.jobs.constants import CHANNEL_PROCESSING
from app.jobs.settings import JobSettings
from app.validation import engine

from validation_helpers import clean

pytestmark = [pytest.mark.db, pytest.mark.perf]

SINGLE_ROWS = 200_000
PARALLEL_ROWS = 50_000
PARALLEL_TABLES = ("Material", "BOM", "Routing", "Stock", "SalesOrderLine", "WorkOrder", "PurchaseOrderLine", "MaterialSupplier")
WORKERS = (1, 2, 4, 8)
RUNS = 3
SINGLE_LIMIT_SECONDS = 120


def _expression(field, length) -> str:
    if field.values:
        return f"N'{field.values[0]}'"
    if field.kind == "text":
        return f"LEFT(N'{field.name[:6]}-' + CONVERT(nvarchar(10), n), {length or 20})"
    if field.kind == "bool":
        return "CAST(n % 2 AS bit)"
    if field.kind == "integer":
        return "n % 100"
    if field.kind == "number":
        return "CAST(CASE WHEN n % 97 = 0 THEN -1 ELSE 0.5 + (n % 100) * 0.01 END AS decimal(18, 4))"  # her 97. satırda negatif: bulgu da yazılır
    return "DATEADD(day, n % 300, CAST('2026-01-01' AS date))"


def fill(eng, table: str, rows: int) -> None:
    lengths = {c.name: getattr(c.type, "length", None) for c in stg_columns(table)}
    fields = contract.fields(table)
    with eng.begin() as c:
        batch = c.execute(sa.text("INSERT INTO adm.ImportBatch (Method, EntityName, LoadType, ReceivedAt, Status, [RowCount], ErrorCount) OUTPUT inserted.Id "
                                  "VALUES (N'SQL', :t, N'Tam', SYSUTCDATETIME(), N'Alındı', :n, 0)"), {"t": table, "n": rows}).scalar_one()
        names = ", ".join(f"[{f.name}]" for f in fields)
        values = ", ".join(_expression(f, lengths[f.name]) for f in fields)
        c.execute(sa.text(f"INSERT INTO stg.[{table}] (ImportBatchId, SourceRowNo, IsCurrent, {names}) "
                          f"SELECT {batch}, n, 1, {values} FROM (SELECT TOP ({rows}) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS n "
                          "FROM sys.all_objects a CROSS JOIN sys.all_objects b CROSS JOIN sys.all_objects c) x"))


def reset_findings(eng) -> None:
    with eng.begin() as c:
        c.execute(sa.text("DELETE FROM adm.ValidationFinding"))
        c.execute(sa.text("DELETE FROM adm.ValidationRun"))
        c.execute(sa.text("DELETE FROM adm.Job WHERE JobType = N'Validasyon'"))


def _worker(limit: int) -> None:
    """Motor servisinin bir süreci gibi: kanaldan iş alır, bitene kadar koşar."""
    from app.api.db import get_engine
    from app.engine.validation_job import run_validation_job
    eng = get_engine()
    while True:
        with Session(eng) as s:
            job = queue.claim_next(s, CHANNEL_PROCESSING, JobSettings(limit_processing=limit))
        if job is None:
            return
        run_validation_job(job["Id"], job["Attempt"])


@pytest.fixture(scope="module")
def big(db_engine):
    clean(db_engine)
    yield db_engine
    clean(db_engine)


def test_single_table_200k(big):
    fill(big, "Material", SINGLE_ROWS)
    times = []
    for _ in range(RUNS):
        reset_findings(big)
        with Session(big) as s:
            run_id = engine._new_run(s, "Material", engine.SCOPE_TABLE, engine.TRIGGER_REVALIDATE, None, None, None)
            s.commit()
            start = time.perf_counter()
            result = engine.run_table(s, run_id, "Material", related=False, progress=lambda _t: None)
            times.append(time.perf_counter() - start)
    median = statistics.median(times)
    print(f"\nMalzeme {SINGLE_ROWS:,} satır tablo içi doğrulama: ortanca {median:.1f} sn ({', '.join(f'{t:.1f}' for t in times)}); "
          f"Hata {result['error_rows']:,}, Uyarı {result['warning_rows']:,}")
    assert result["current_rows"] == SINGLE_ROWS and result["error_rows"] > 0
    assert median < SINGLE_LIMIT_SECONDS
    with big.begin() as c:
        c.execute(sa.text("DELETE FROM stg.Material"))


def test_parallel_jobs(big):
    for table in PARALLEL_TABLES:
        fill(big, table, PARALLEL_ROWS)
    ctx = multiprocessing.get_context("spawn")
    results = {}
    for n in WORKERS:
        times = []
        for _ in range(RUNS):
            reset_findings(big)
            with Session(big) as s:
                for table in PARALLEL_TABLES:
                    engine.enqueue(s, table, engine.SCOPE_TABLE, engine.TRIGGER_BULK)
            start = time.perf_counter()
            workers = [ctx.Process(target=_worker, args=(n,)) for _ in range(n)]
            for w in workers:
                w.start()
            for w in workers:
                w.join()
            times.append(time.perf_counter() - start)
            with big.connect() as c:
                assert c.execute(sa.text("SELECT COUNT(*) FROM adm.ValidationRun WHERE State = N'Bitti'")).scalar() == len(PARALLEL_TABLES)
        results[n] = statistics.median(times)
    best = min(results, key=results.get)
    print(f"\n{len(PARALLEL_TABLES)} tablo × {PARALLEL_ROWS:,} satır, paralel iş → ortanca: "
          + ", ".join(f"{n}: {t:.1f} sn" for n, t in results.items()) + f"; en hızlı {best}")
    assert results[best] <= results[1]
