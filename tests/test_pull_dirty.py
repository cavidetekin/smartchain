"""Aynı kirli veri iki yoldan aynı sonucu verir (K-130): Excel ve SQL partilerinde stg satırları ve bulgular birebir.

SourceRowNo karşılaştırılmaz: Excel'de dosya satırı, SQL'de okuma sırası. Kayıt anahtarla bulunur.
"""
from collections import Counter
from pathlib import Path

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.main import create_app
from app.api.permissions import KEY_USER
from app.data.synthetic.dataset import generate
from app.data.synthetic.excel import write_excel
from app.engine.pull_job import run_pull_job
from app.integration.contract import stg_columns
from app.jobs import queue
from app.jobs.constants import CHANNEL_PULL
from app.jobs.settings import JobSettings

from auth_helpers import auth, delete_users, ensure_user
from integration_helpers import _written, integration_db  # noqa: F401

pytestmark = pytest.mark.db

PREFIX = "pytest.ikiyol."
SKIP = {"ImportBatchId", "StagingRowId", "SourceRowNo", "RowStatus", "ErrorText"}
FILE_LEVEL = {"no_template_info", "old_template", "view_column", "unknown_column", "unlabelled_column"}


def clean(engine, tables):
    with engine.begin() as c:
        for table in tables:
            c.execute(sa.text(f"DELETE FROM stg.[{table}]"))
        c.execute(sa.text("DELETE FROM adm.ImportFinding"))
        c.execute(sa.text("DELETE FROM adm.ImportBatch"))
        c.execute(sa.text("DELETE FROM adm.Job WHERE JobType IN (N'Veri çekme', N'Excel ön kontrol', N'Validasyon')"))
        c.execute(sa.text("DELETE FROM adm.ValidationFinding"))
        c.execute(sa.text("DELETE FROM adm.ValidationRun"))
        c.execute(sa.text("DELETE FROM adm.AuditLog WHERE Action IN (N'Veri çekme', N'Excel yükleme', N'Yöntem değişikliği', N'Entegrasyon tanımı')"))
        c.execute(sa.text("DELETE FROM adm.IntegrationViewVersion"))
        c.execute(sa.text("DELETE FROM adm.IntegrationEntity"))
        delete_users(c, [r[0] for r in c.execute(sa.text("SELECT Id FROM adm.AppUser WHERE UserName LIKE :p"), {"p": PREFIX + "%"})])


def rows_of(engine, table, batch_id):
    names = [c.name for c in stg_columns(table)]
    columns = ", ".join(f"[{n}]" for n in names)
    with engine.connect() as c:
        return Counter(tuple(r) for r in c.execute(sa.text(f"SELECT {columns} FROM stg.[{table}] WHERE ImportBatchId = :b"), {"b": batch_id}))


def findings_of(engine, batch_id):
    with engine.connect() as c:
        rows = c.execute(sa.text("SELECT Severity, CheckCode, FieldName, [Value], RowKey FROM adm.ImportFinding WHERE ImportBatchId = :b"), {"b": batch_id}).all()
    return Counter(tuple(r) for r in rows if r.CheckCode not in FILE_LEVEL)


def test_excel_and_sql_give_identical_results(integration_db, tmp_path: Path):  # noqa: F811
    engine = integration_db
    ds = generate()
    manifest = write_excel(ds, tmp_path)
    tables = [name[:-5] for name in manifest["files"]]
    clean(engine, tables)
    with engine.begin() as c:
        user = ensure_user(c, PREFIX + "key", KEY_USER, "Ad")
        owner = ensure_user(c, PREFIX + "sahip", "System owner", "Sahip")
    client = TestClient(create_app(), raise_server_exceptions=False)
    try:
        excel = {}
        for table in tables:
            r = client.post(f"/api/imports/{table}?mode=Tam", content=(tmp_path / f"{table}.xlsx").read_bytes(), headers={**auth(user), "X-File-Name": f"{table}.xlsx"})
            assert r.status_code == 200, (table, r.text)
            excel[table] = r.json()["batch_id"]
            assert client.post(f"/api/imports/{excel[table]}/continue", headers=auth(user)).status_code == 200
        for table in tables:
            assert client.put("/api/integration/entities", json={"changes": [{"entity": table, "method": "SQL"}]}, headers=auth(owner)).status_code == 200
            r = client.put("/api/integration/entities", json={"changes": [{"entity": table, "view": f"View_{table}"}]}, headers=auth(owner))
            assert r.status_code == 200, (table, r.text)
        job = client.post("/api/pulls", json={}, headers=auth(user)).json()["job_id"]
        with Session(engine) as s:
            attempt = queue.claim_next(s, CHANNEL_PULL, JobSettings())["Attempt"]
        run_pull_job(job, attempt)
        result = {t["entity"]: t for t in client.get(f"/api/pulls/{job}", headers=auth(user)).json()["tables"]}
        for table in tables:
            assert result[table]["status"] == "Alındı", (table, result[table])
            sql = result[table]["batch_id"]
            assert rows_of(engine, table, excel[table]) == rows_of(engine, table, sql), table
            assert findings_of(engine, excel[table]) == findings_of(engine, sql), table
        material = result["Material"]
        assert (material["read"], material["valid"], material["errors"]) == (214, 212, 2)  # H4; 10 hazır kural örneği, 1 pasif ebeveyn yardımcısı ve 2 veri kuralı örneği dahil (docs/11)
        with engine.connect() as c:
            assert c.execute(sa.text("SELECT COUNT(*) FROM stg.SalesOrderLine WHERE MaterialCode = N'MAM-099' AND ImportBatchId = :b"),
                             {"b": result["SalesOrderLine"]["batch_id"]}).scalar() > 0  # H2 referans kontrolü 4.4'te
    finally:
        clean(engine, tables)
