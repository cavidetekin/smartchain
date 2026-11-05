"""Excel yükleme performansı (K-129): eşikteki dosya istek içinde kalmalı; 200.000 satır iş kuyruğunda ölçülür. Ayrıca: pytest -m perf."""
import io
import time
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.main import create_app
from app.api.permissions import KEY_USER
from app.api.repositories import imports as repo
from app.api.services import imports as service
from app.integration import contract
from app.integration.contract import stg_columns
from app.integration.template import write_template
from app.jobs.settings import IMPORT_DEFAULTS

from auth_helpers import auth, delete_users, ensure_user

pytestmark = [pytest.mark.db, pytest.mark.perf]

TABLE = "Material"  # en geniş tablo
TARGET_SYNC_SECONDS = 15
PREFIX = "pytest.yukleme-perf."


def body(rows: int) -> bytes:
    entity = contract.entity(TABLE)
    found = contract.fields(TABLE)
    lengths = {c.name: getattr(c.type, "length", None) for c in stg_columns(TABLE)}

    def value(f, i):
        if f.values:
            return f.values[i % len(f.values)]
        if f.kind == "text":
            return f"{f.name[:6]}-{i:06d}"[:lengths[f.name] or 20]
        if f.kind == "bool":
            return i % 2
        if f.kind == "integer":
            return i % 100
        if f.kind == "number":
            return 0.5 + (i % 100) * 0.01
        return date(2026, 1, 1) + timedelta(days=i % 300)

    buffer = io.BytesIO()
    write_template(buffer, entity, None, rows=[{f.name: value(f, i) for f in found} for i in range(rows)])
    return buffer.getvalue()


@pytest.fixture
def user(db_engine):
    def clean():
        with db_engine.begin() as c:
            c.execute(text(f"DELETE FROM stg.[{TABLE}]"))
            c.execute(text("DELETE FROM adm.ImportFinding"))
            c.execute(text("DELETE FROM adm.ImportBatch"))
            delete_users(c, [r[0] for r in c.execute(text("SELECT Id FROM adm.AppUser WHERE UserName LIKE :p"), {"p": PREFIX + "%"})])

    clean()
    with db_engine.begin() as c:
        out = ensure_user(c, PREFIX + "key", KEY_USER, "Ad")
    yield out
    clean()


def test_threshold_file_stays_under_target_in_the_request(user):
    """Bulgu yazımı ve API dahil. Aşarsa ImportSyncMaxMb düşürülür (plan 3.2)."""
    data = body(40000)
    assert len(data) <= IMPORT_DEFAULTS["ImportSyncMaxMb"] * 1024 * 1024
    client = TestClient(create_app(), raise_server_exceptions=False)
    start = time.perf_counter()
    r = client.post(f"/api/imports/{TABLE}", content=data, headers={**auth(user), "X-File-Name": "m.xlsx"})
    seconds = time.perf_counter() - start
    print(f"\n40.000 satır, {len(data) / 1e6:.1f} MB, API dahil: {seconds:.1f} sn")
    assert r.status_code == 200 and r.json()["valid"] == 40000
    assert seconds < TARGET_SYNC_SECONDS


def test_value_outside_list_in_every_row_does_not_flood(db_engine, user):
    """ERP'nin kendi değerleri: her satır liste dışı olsa da bilgi alan ve değer başına tektir."""
    buffer = io.BytesIO()
    write_template(buffer, contract.entity("Location"), None, rows=[{"Code": f"L-{i}", "Name": "Ad", "Type": "Özel"} for i in range(5000)])
    client = TestClient(create_app(), raise_server_exceptions=False)
    r = client.post("/api/imports/Location", content=buffer.getvalue(), headers={**auth(user), "X-File-Name": "l.xlsx"})
    assert r.status_code == 200 and r.json()["valid"] == 5000 and r.json()["notes"] == 1
    with db_engine.begin() as c:
        c.execute(text("DELETE FROM stg.Location"))


def test_largest_file_finishes_as_a_job(db_engine, user, monkeypatch):
    """İşin kendisi: 200.000 satır bellekte toplanmadan okunur ve yazılır."""
    data = body(IMPORT_DEFAULTS["ImportMaxRows"])
    path = service._folder() / "perf.xlsx"
    path.write_bytes(data)
    with Session(db_engine) as s:
        batch_id = repo.create_batch(s, TABLE, "Değişen", "perf.xlsx", user, contract.entity(TABLE).version)
        repo.set_batch(s, batch_id, FilePath=str(path))
        s.commit()
        start = time.perf_counter()
        service.run_precheck(s, batch_id)
        seconds = time.perf_counter() - start
    print(f"\n200.000 satır, {len(data) / 1e6:.1f} MB, iş: {seconds:.1f} sn")
    with db_engine.connect() as c:
        assert c.execute(text(f"SELECT COUNT(*) FROM stg.[{TABLE}] WHERE ImportBatchId = :b"), {"b": batch_id}).scalar() == 200000
    path.unlink(missing_ok=True)
