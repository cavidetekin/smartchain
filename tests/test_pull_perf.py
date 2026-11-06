"""SQL çekim performansı (K-130): 200.000 satırlık view Excel işinden hızlı okunmalı; her ölçüm ortanca (docs/08). Ayrıca: pytest -m perf."""
import statistics
import time

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.api.permissions import KEY_USER
from app.api.services import pull
from app.integration import contract
from app.integration.contract import stg_columns
from app.jobs import queue
from app.jobs.constants import CHANNEL_PULL, TYPE_PULL
from app.jobs.settings import JobSettings

from auth_helpers import delete_users, ensure_user
from integration_helpers import _written, integration_db, run_sql  # noqa: F401

pytestmark = [pytest.mark.db, pytest.mark.perf]

TABLE = "Material"
ROWS = 200_000
RUNS = 3
EXCEL_JOB_SECONDS = 60  # docs/08: 200.000 satır Excel işi, ortanca 52,6 sn
PREFIX = "pytest.cekim-perf."


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
        return "CAST(0.5 + (n % 100) * 0.01 AS decimal(18, 4))"
    return "DATEADD(day, n % 300, CAST('2026-01-01' AS date))"


@pytest.fixture
def big_view(integration_db):  # noqa: F811
    lengths = {c.name: getattr(c.type, "length", None) for c in stg_columns(TABLE)}
    items = ", ".join(f"{_expression(f, lengths[f.name])} AS [{f.name}]" for f in contract.fields(TABLE))
    run_sql(f"SELECT {items} INTO dbo.ERP_PerfMaterial FROM (SELECT TOP ({ROWS}) ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) AS n "
            "FROM sys.all_objects a CROSS JOIN sys.all_objects b) x")
    run_sql("CREATE VIEW dbo.View_PerfMaterial AS SELECT * FROM dbo.ERP_PerfMaterial")
    with integration_db.begin() as c:
        user = ensure_user(c, PREFIX + "key", KEY_USER, "Ad")
        c.execute(sa.text("INSERT INTO adm.IntegrationEntity (EntityName, Method, ViewName) VALUES (:t, N'SQL', N'View_PerfMaterial')"), {"t": TABLE})
    yield user
    run_sql("DROP VIEW dbo.View_PerfMaterial")
    run_sql("DROP TABLE dbo.ERP_PerfMaterial")
    with integration_db.begin() as c:
        c.execute(sa.text(f"DELETE FROM stg.[{TABLE}]"))
        c.execute(sa.text("DELETE FROM adm.ImportFinding"))
        c.execute(sa.text("DELETE FROM adm.ImportBatch"))
        c.execute(sa.text("DELETE FROM adm.Job WHERE JobType = :t"), {"t": TYPE_PULL})
        delete_users(c, [r[0] for r in c.execute(sa.text("SELECT Id FROM adm.AppUser WHERE UserName LIKE :p"), {"p": PREFIX + "%"})])


def test_view_of_200000_rows(big_view, db_engine):
    times = []
    for _ in range(RUNS):
        with db_engine.begin() as c:
            c.execute(sa.text(f"DELETE FROM stg.[{TABLE}]"))
        payload = {"entities": [TABLE], "read_anyway": [TABLE], "user_id": big_view}
        with Session(db_engine) as s:
            job = queue.enqueue(s, TYPE_PULL, CHANNEL_PULL, big_view, payload)
            s.commit()
            attempt = queue.claim_next(s, CHANNEL_PULL, JobSettings())["Attempt"]
            start = time.perf_counter()
            assert pull.run_job(s, job, attempt, payload, lambda _text: None)
            times.append(time.perf_counter() - start)
        with db_engine.connect() as c:
            assert c.execute(sa.text(f"SELECT COUNT(*) FROM stg.[{TABLE}]")).scalar() > 0
    seconds = statistics.median(times)
    print(f"\n200.000 satırlık view: ortanca {seconds:.1f} sn ({', '.join(f'{x:.1f}' for x in times)})")
    assert seconds < EXCEL_JOB_SECONDS
