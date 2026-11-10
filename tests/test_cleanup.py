"""Ham veri temizliği (fonksiyon 09; K-129, K-133, K-156): süreden eski partide güncel olmayan ham satırlar, ön kontrol bulguları ve dosya silinir;
terk edilen ön kontrol "Vazgeçildi" olur; güncel satırlar, işlenmiş katman, genç partiler ve parti kaydı kalır. Süre boşsa çalışmaz. Yalnız System
owner başlatır; Admin ve Key user sonucu görür. Saklama süresi ayarı boş bırakılabilir. Test veritabanında (K-103)."""
import json

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.api.permissions import ADMIN, END_USER, KEY_USER, SYSTEM_OWNER
from app.cleanup import raw
from app.engine.cleanup_job import NO_RETENTION, run_cleanup_job
from app.jobs import queue
from app.jobs.constants import CHANNEL_PROCESSING, TYPE_CLEANUP, TYPE_VALIDATION
from app.jobs.settings import JobSettings

from auth_helpers import auth, ensure_user
from test_validation_references import put
from validation_helpers import clean, new_client

pytestmark = pytest.mark.db
DAYS = 7


def _setting(engine, days: int | None) -> None:
    with engine.begin() as c:
        c.execute(sa.text("DELETE FROM adm.SystemSetting WHERE SettingKey = N'RawDataRetentionDays'"))
        if days is not None:
            c.execute(sa.text("INSERT INTO adm.SystemSetting (SettingKey, Value) VALUES (N'RawDataRetentionDays', :v)"), {"v": str(days)})


def _batch(engine, code: str) -> int:
    with engine.connect() as c:
        return c.execute(sa.text("SELECT ImportBatchId FROM stg.Customer WHERE Code = :c"), {"c": code}).scalar_one()


@pytest.fixture
def staged(db_engine, tmp_path):
    """A (eski, Alındı): CA-1 güncel, CA-2 güncel değil, dosyası ve bulgusu var. C (eski, terk edilen ön kontrol): CC-1, dosyası var.
    D (genç): CD-1 güncel değil, dosyası ve bulgusu var."""
    clean(db_engine)
    put(db_engine, {"Customer": [{"Code": "CA-1", "Name": "A1", "IsActive": 1}, {"Code": "CA-2", "Name": "A2", "IsActive": 1}]})
    put(db_engine, {"Customer": [{"Code": "CC-1", "Name": "C1", "IsActive": 1}]})
    put(db_engine, {"Customer": [{"Code": "CD-1", "Name": "D1", "IsActive": 1}]})
    a, cb, d = _batch(db_engine, "CA-1"), _batch(db_engine, "CC-1"), _batch(db_engine, "CD-1")
    files = {}
    for name, batch in (("a", a), ("c", cb), ("d", d)):
        path = tmp_path / f"{name}.xlsx"
        path.write_bytes(b"x" * 1000)
        files[name] = path
        with db_engine.begin() as c:
            c.execute(sa.text("UPDATE adm.ImportBatch SET FilePath = :p, FileName = :n WHERE Id = :b"), {"p": str(path), "n": path.name, "b": batch})
    with db_engine.begin() as c:
        c.execute(sa.text("UPDATE stg.Customer SET IsCurrent = 0 WHERE Code IN (N'CA-2', N'CC-1', N'CD-1')"))
        c.execute(sa.text("UPDATE adm.ImportBatch SET Status = N'Ön kontrol' WHERE Id = :b"), {"b": cb})
        c.execute(sa.text("UPDATE adm.ImportBatch SET ReceivedAt = DATEADD(day, -10, SYSUTCDATETIME()) WHERE Id IN (:a, :c)"), {"a": a, "c": cb})
        for batch in (a, d):
            c.execute(sa.text("INSERT INTO adm.ImportFinding (ImportBatchId, RowNo, Severity, CheckCode, Message) VALUES (:b, 3, N'Hata', N'T', N'Test')"),
                      {"b": batch})
    yield {"a": a, "c": cb, "d": d, "files": files}
    _setting(db_engine, None)
    clean(db_engine)


def _state(engine) -> dict:
    with engine.connect() as c:
        q = lambda sql, **p: c.execute(sa.text(sql), p).all()  # noqa: E731
        return {"stg": sorted(r[0] for r in q("SELECT Code FROM stg.Customer")),
                "prc": c.execute(sa.text("SELECT COUNT(*) FROM prc.Customer")).scalar(),
                "findings": sorted(r[0] for r in q("SELECT ImportBatchId FROM adm.ImportFinding")),
                "batches": {r[0]: (r[1], r[2], r[3] is not None) for r in q("SELECT Id, Status, FilePath, RawDeletedAt FROM adm.ImportBatch")}}


def _run_job(engine, user_id=None) -> dict:
    with Session(engine) as s:
        job_id = queue.enqueue(s, TYPE_CLEANUP, CHANNEL_PROCESSING, user_id, {"user_id": user_id}, summary="Ham veri temizliği")
    with Session(engine) as s:
        job = queue.claim_next(s, CHANNEL_PROCESSING, JobSettings(limit_processing=10))
    assert job["Id"] == job_id
    run_cleanup_job(job_id, job["Attempt"])
    with engine.connect() as c:
        status, progress, result = c.execute(sa.text("SELECT Status, Progress, Result FROM adm.Job WHERE Id = :i"), {"i": job_id}).one()
    return {"status": status, "progress": progress, "result": json.loads(result)}


def test_cleanup_deletes_old_raw_data_and_keeps_current_state(staged, db_engine):
    s = staged
    _setting(db_engine, DAYS)
    before = _state(db_engine)
    with Session(db_engine) as session:
        preview = raw.preview(session, DAYS)
    assert (preview["batches"], preview["abandoned"], preview["rows"], preview["files"], preview["size"]) == (2, 1, 2, 2, 2000)
    assert preview["tables"] == [{"entity": "Customer", "name": "Müşteri", "rows": 2}]
    assert _state(db_engine) == before                                                     # önizleme bir şey değiştirmez
    job = _run_job(db_engine)
    r = job["result"]
    assert job["status"] == "Bitti" and (r["batches"], r["abandoned"], r["rows"], r["files"], r["size"]) == (2, 1, 2, 2, 2000)
    assert job["progress"] == "Ham veri temizliği bitti · 2 yükleme · 2 eski satır · 2 dosya"
    after = _state(db_engine)
    assert after["stg"] == ["CA-1", "CD-1"]                                                 # güncel satır (eski partide de) ve genç parti kalır
    assert after["prc"] == before["prc"] and after["findings"] == [s["d"]]
    assert after["batches"][s["a"]] == ("Alındı", None, True)
    assert after["batches"][s["c"]] == ("Vazgeçildi", None, True)                           # terk edilen ön kontrol
    assert after["batches"][s["d"]] == before["batches"][s["d"]] and after["batches"][s["d"]][2] is False
    assert not s["files"]["a"].exists() and not s["files"]["c"].exists() and s["files"]["d"].exists()
    again = _run_job(db_engine)["result"]                                                   # ikinci kez: işlenmiş partiye dokunulmaz
    assert (again["batches"], again["rows"], again["files"]) == (0, 0, 0)


def test_cleanup_without_retention_changes_nothing(staged, db_engine):
    _setting(db_engine, None)
    before = _state(db_engine)
    job = _run_job(db_engine)
    assert job["status"] == "Bitti" and job["result"] == {"note": NO_RETENTION} and _state(db_engine) == before
    assert staged["files"]["a"].exists()


def test_cleanup_api_permissions_and_blocks(staged, db_engine):
    with db_engine.begin() as c:
        people = {r: ensure_user(c, f"pytest.temizlik.{r.replace(' ', '-').lower()}", r, f"Ad {r}") for r in (SYSTEM_OWNER, ADMIN, KEY_USER, END_USER)}
    client = new_client()
    _setting(db_engine, None)
    r = client.post("/api/cleanup", headers=auth(people[SYSTEM_OWNER]))
    assert r.status_code == 409 and r.json()["error"]["code"] == "cleanup_no_retention"
    assert client.get("/api/cleanup/plan", headers=auth(people[SYSTEM_OWNER])).json()["blocked"].startswith("Saklama süresi tanımlı değil")
    _setting(db_engine, DAYS)
    plan = client.get("/api/cleanup/plan", headers=auth(people[SYSTEM_OWNER])).json()
    assert plan["blocked"] is None and plan["preview"]["batches"] == 2
    for role in (ADMIN, KEY_USER):
        assert client.get("/api/cleanup", headers=auth(people[role])).status_code == 200      # sonucu görür
        assert client.get("/api/cleanup/plan", headers=auth(people[role])).status_code == 403
        assert client.post("/api/cleanup", headers=auth(people[role])).status_code == 403
    assert client.get("/api/cleanup", headers=auth(people[END_USER])).status_code == 403
    with Session(db_engine) as s:
        queue.enqueue(s, TYPE_VALIDATION, CHANNEL_PROCESSING, None, {})
    r = client.post("/api/cleanup", headers=auth(people[SYSTEM_OWNER]))
    assert r.status_code == 409 and r.json()["error"]["message"] == "Validasyon sürüyor. Bitince temizliği başlatabilirsiniz."
    with db_engine.begin() as c:
        c.execute(sa.text("DELETE FROM adm.Job WHERE JobType = N'Validasyon'"))
    r = client.post("/api/cleanup", headers=auth(people[SYSTEM_OWNER]))
    assert r.status_code == 202
    state = client.get("/api/cleanup", headers=auth(people[KEY_USER])).json()
    assert state["retention_days"] == DAYS and state["last"]["job_id"] == r.json()["job_id"] and state["last"]["status"] == "Sırada"
    r = client.post("/api/transfers", headers=auth(people[ADMIN]))                          # temizlik sıradayken aktarım başlamaz
    assert r.status_code == 409 and r.json()["error"]["message"].startswith("Temizlik sürüyor")
    with db_engine.begin() as c:
        c.execute(sa.text("DELETE FROM adm.Job WHERE JobType = N'Temizlik'"))
        audit_row = c.execute(sa.text("SELECT TOP 1 NewValue FROM adm.AuditLog WHERE Action = N'Ham veri temizliği' ORDER BY Id DESC")).scalar()
    assert json.loads(audit_row) == {"retention_days": DAYS}


def test_retention_setting_can_be_empty(db_engine):
    with db_engine.begin() as c:
        owner = ensure_user(c, "pytest.temizlik.ayar", SYSTEM_OWNER, "Ad")
    client = new_client()
    _setting(db_engine, None)
    try:
        body = client.get("/api/settings/health", headers=auth(owner)).json()
        assert body["values"]["RawDataRetentionDays"] is None and "RawDataRetentionDays" in body["optional"]
        assert body["limits"]["RawDataRetentionDays"] == {"min": 1, "max": 30}
        assert client.put("/api/settings/health", headers=auth(owner), json={"RawDataRetentionDays": 31}).status_code == 422
        assert client.put("/api/settings/health", headers=auth(owner), json={"RawDataRetentionDays": 7}).json()["values"]["RawDataRetentionDays"] == 7
        assert client.put("/api/settings/health", headers=auth(owner), json={"RawDataRetentionDays": None}).json()["values"]["RawDataRetentionDays"] is None
        assert client.put("/api/settings/health", headers=auth(owner), json={"DiskWarnPercent": None}).status_code == 422
        with db_engine.connect() as c:
            rows = c.execute(sa.text("SELECT TOP 2 OldValue, NewValue FROM adm.AuditLog WHERE ObjectKey = N'RawDataRetentionDays' ORDER BY Id DESC")).all()
        assert [json.loads(n)["Value"] for _, n in rows] == [None, 7]
    finally:
        _setting(db_engine, None)


def test_retention_days_reads_only_valid_values(db_engine):
    with Session(db_engine) as s:
        for raw_value, expected in (("7", 7), ("0", None), ("31", None), ("abc", None)):
            s.execute(sa.text("DELETE FROM adm.SystemSetting WHERE SettingKey = N'RawDataRetentionDays'"))
            s.execute(sa.text("INSERT INTO adm.SystemSetting (SettingKey, Value) VALUES (N'RawDataRetentionDays', :v)"), {"v": raw_value})
            assert raw.retention_days(s) == expected, raw_value
        s.rollback()
