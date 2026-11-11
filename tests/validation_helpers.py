"""Validasyon testlerinin ortak parçaları (K-133, K-134): temizlik, kirli verinin Excel'le yüklenmesi, işlerin eşzamanlı koşulması."""
from pathlib import Path

import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.main import create_app
from app.data.synthetic.dataset import generate
from app.data.synthetic.excel import write_excel
from app.engine.validation_job import run_validation_job
from app.integration.contract import ENTITIES
from app.jobs import queue
from app.jobs.constants import CHANNEL_PROCESSING
from app.jobs.settings import JobSettings
from app.validation import engine as validation_engine

from auth_helpers import auth


def clean(engine) -> None:
    """stg ve prc, partiler, bulgular, validasyon tabloları, veri kuralları ve işleri; hazır kural tanımları katalogdan yeniden kurulur."""
    with engine.begin() as c:
        for e in ENTITIES:
            c.execute(sa.text(f"DELETE FROM stg.[{e.table}]"))
            c.execute(sa.text(f"DELETE FROM prc.[{e.table}]"))
        c.execute(sa.text("DELETE FROM adm.DataRuleEffect"))
        c.execute(sa.text("DELETE FROM adm.DataRuleCondition"))
        c.execute(sa.text("DELETE FROM adm.DataRule"))
        c.execute(sa.text("DELETE FROM adm.ValidationFinding"))
        c.execute(sa.text("DELETE FROM adm.ValidationRun"))
        c.execute(sa.text("DELETE FROM adm.ValidationRuleCondition"))
        c.execute(sa.text("DELETE FROM adm.ValidationRule"))  # katalog varsayılanlarıyla yeniden kurulur (sınıf, aktiflik)
        c.execute(sa.text("DELETE FROM adm.ImportFinding"))
        c.execute(sa.text("DELETE FROM adm.RawCompareRow"))
        c.execute(sa.text("DELETE FROM adm.RawCompare"))
        c.execute(sa.text("DELETE FROM adm.ImportBatch"))
        c.execute(sa.text("DELETE FROM adm.Job WHERE JobType IN (N'Veri çekme', N'Excel ön kontrol', N'Validasyon', N'Aktarım')"))
        c.execute(sa.text("UPDATE adm.IntegrationEntity SET ErrorThresholdPct = NULL"))
    validation_engine._synced = False


def run_validations(engine, limit: int = 200) -> list[int]:
    """Sıradaki doğrulama işlerini bu süreçte koşar (motor servisi yerine); koşulan işler."""
    done = []
    for _ in range(limit):
        with Session(engine) as s:
            job = queue.claim_next(s, CHANNEL_PROCESSING, JobSettings(limit_processing=100))
        if job is None:
            return done
        run_validation_job(job["Id"], job["Attempt"])
        done.append(job["Id"])
    raise AssertionError("Validasyon işleri bitmedi")


def upload_dirty(client: TestClient, user: dict, folder: Path, tables: list[str] | None = None, mode: str = "Tam") -> dict[str, int]:
    """Kirli Excel'i yükler ve sürdürür; tablo → parti."""
    manifest = write_excel(generate(), folder)
    names = tables or [name[:-5] for name in manifest["files"]]
    out = {}
    for table in names:
        r = client.post(f"/api/imports/{table}?mode={mode}", content=(folder / f"{table}.xlsx").read_bytes(), headers={**auth(user), "X-File-Name": f"{table}.xlsx"})
        assert r.status_code == 200, (table, r.text)
        out[table] = r.json()["batch_id"]
        r = client.post(f"/api/imports/{out[table]}/continue", headers=auth(user))
        assert r.status_code == 200, (table, r.text)
    return out


def findings_by_rule(engine) -> dict[tuple[str, str], int]:
    with engine.connect() as c:
        rows = c.execute(sa.text("SELECT r.EntityName, r.Code, COUNT(*) FROM adm.ValidationFinding f JOIN adm.ValidationRule r ON r.Id = f.ValidationRuleId "
                                 "GROUP BY r.EntityName, r.Code")).all()
    return {(t, code): n for t, code, n in rows}


def new_client() -> TestClient:
    return TestClient(create_app(), raise_server_exceptions=False)
