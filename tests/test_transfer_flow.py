"""Tam aktarım akışı (K-149, K-151, K-153): kirli sentetik veri uçtan uca, API (onay, başlatma, 409, yetki), motor işi (sonuç, iz, ya hep ya hiç)."""
import json

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.api.permissions import END_USER, KEY_USER
from app.engine.transfer_job import run_transfer_job
from app.jobs import queue
from app.jobs.constants import CHANNEL_PROCESSING, TYPE_TRANSFER, TYPE_VALIDATION
from app.jobs.settings import JobSettings
from app.transfer import engine as transfer

from auth_helpers import auth, ensure_user
from test_validation_references import put
from validation_helpers import clean, new_client, run_validations, upload_dirty

pytestmark = pytest.mark.db


def by_entity(result) -> dict:
    return {t["entity"]: t for t in result["tables"]}


@pytest.fixture(scope="module")
def dirty(db_engine, tmp_path_factory):
    clean(db_engine)
    with db_engine.begin() as c:
        user = ensure_user(c, "pytest.aktarim.key", KEY_USER, "Ad")
    upload_dirty(new_client(), user, tmp_path_factory.mktemp("kirli"))
    run_validations(db_engine)
    yield db_engine
    clean(db_engine)


def test_dirty_data_end_to_end(dirty):
    """Temiz hâl core'da (sentetik v0): kirli verinin aktarımında temiz satırlar değişmez; H1–H4 ve Hatalı örnekler aktarılmaz (docs/11)."""
    with Session(dirty) as s:
        r = transfer.run_transfer(s, None)
        v, t = r["data_version"], by_entity(r)
        q = lambda sql, **p: s.execute(sa.text(sql), p).scalar()  # noqa: E731
        try:
            assert all(not x["changed"] for x in r["tables"]), [(x["entity"], x["changed"]) for x in r["tables"] if x["changed"]]
            assert t["Material"]["closed"] == 1 and not q("SELECT COUNT(*) FROM core.Material WHERE Code = N'SAT-040' AND VersionTo IS NULL")  # H4
            assert t["Routing"]["closed"] == q("SELECT COUNT(*) FROM core.Routing WHERE RouteCode = N'R-PRC-033' AND VersionTo = :t", t=v - 1) > 0  # H1 rota
            assert q("SELECT COUNT(*) FROM core.ProductionVersion WHERE MaterialId IN (SELECT Id FROM core.Material WHERE Code = N'PRC-033') "
                     "AND VersionTo IS NULL") == 1                                                  # H1 versiyonu Hatalı: önceki hâli açık
            assert not q("SELECT COUNT(*) FROM core.SalesOrderLine WHERE OrderNo = N'SO-1099'")      # H2
            assert not q("SELECT COUNT(*) FROM core.Material WHERE Code = N'L-MAT-PAS'")             # pasif
            assert not q("SELECT COUNT(*) FROM core.SalesOrderLine WHERE OrderNo = N'V-SO-4'")       # zorunlu müşteri yok (Hata)
            assert q("SELECT COUNT(*) FROM core.SalesOrderLine WHERE OrderNo = N'V-SO-7' AND ProjectId IS NULL AND VersionTo IS NULL") == 1  # isteğe bağlı: boş
            assert t["Forecast"]["not_transferred"] >= 2                                             # boş bağlantı aynı anahtara düştü
            assert q("SELECT COUNT(*) FROM adm.DataVersionEntity WHERE DataVersionId = :v", v=v) == 25
        finally:
            s.rollback()


def test_plan_lists_tables_and_blocks_while_validation_pending(db_engine):
    clean(db_engine)
    put(db_engine, {"Customer": [{"Code": "PL-1", "Name": "Plan", "IsActive": 1}]})
    with db_engine.begin() as c:
        key = ensure_user(c, "pytest.aktarim.plan", KEY_USER, "Ad")
        end = ensure_user(c, "pytest.aktarim.end", END_USER, "Ad")
    client = new_client()
    try:
        body = client.get("/api/transfers/plan", headers=auth(key)).json()
        rows = {x["entity"]: x for x in body["tables"]}
        assert rows["Customer"]["status"] == "Aktarılır" and rows["Material"]["status"] == "Veri gelmedi"
        assert body["blocked"]["tables"] == ["Müşteri"]                                            # validasyonu hiç çalışmadı
        r = client.post("/api/transfers", headers=auth(key))
        assert r.status_code == 409 and r.json()["error"]["code"] == "transfer_blocked"
        assert client.post("/api/transfers", headers=auth(end)).status_code == 403
        assert client.get("/api/transfers/plan", headers=auth(end)).status_code == 403
        with Session(db_engine) as s:
            queue.enqueue(s, TYPE_VALIDATION, CHANNEL_PROCESSING, None, {})
        r = client.post("/api/transfers", headers=auth(key))
        assert r.status_code == 409 and r.json()["error"]["message"] == "Validasyon sürüyor. Bitince aktarımı başlatabilirsiniz."
    finally:
        clean(db_engine)


def _undo(engine, version: int) -> None:
    """Commit edilen test aktarımını geri al: yalnız Müşteri tablosu yazıldı (öteki tablolarda staging boş)."""
    with engine.begin() as c:
        c.execute(sa.text("DELETE FROM core.Customer WHERE VersionFrom = :v"), {"v": version})
        c.execute(sa.text("UPDATE core.Customer SET VersionTo = NULL WHERE VersionTo = :t"), {"t": version - 1})
        c.execute(sa.text("DELETE FROM adm.DataVersionEntity WHERE DataVersionId = :v"), {"v": version})
        c.execute(sa.text("DELETE FROM adm.DataVersion WHERE Id = :v"), {"v": version})


def _claim(engine) -> dict:
    with Session(engine) as s:
        return queue.claim_next(s, CHANNEL_PROCESSING, JobSettings(limit_processing=10))


def test_job_commits_result_audit_and_new_version(db_engine):
    clean(db_engine)
    put(db_engine, {"Customer": [{"Code": "JB-1", "Name": "İş", "IsActive": 1}]})
    with db_engine.begin() as c:
        key = ensure_user(c, "pytest.aktarim.job", KEY_USER, "Ad")
    with Session(db_engine) as s:
        job_id = queue.enqueue(s, TYPE_TRANSFER, CHANNEL_PROCESSING, key, {"user_id": key}, summary="Tam aktarım")
    job = _claim(db_engine)
    assert job["Id"] == job_id
    run_transfer_job(job_id, job["Attempt"])
    client = new_client()
    body = client.get(f"/api/transfers/{job_id}", headers=auth(key)).json()
    version = body["data_version"]
    try:
        assert body["status"] == "Bitti" and by_entity(body)["Customer"]["new"] == 1
        with db_engine.connect() as c:
            assert c.execute(sa.text("SELECT COUNT(*) FROM core.Customer WHERE Code = N'JB-1' AND VersionFrom = :v"), {"v": version}).scalar() == 1
            assert c.execute(sa.text("SELECT MAX(Id) FROM adm.DataVersion")).scalar() == version
            audit_row = c.execute(sa.text("SELECT TOP 1 ObjectKey, NewValue FROM adm.AuditLog WHERE Action = N'Tam aktarım' AND ObjectType = N'DataVersion' "
                                          "ORDER BY Id DESC")).one()
        assert audit_row[0] == str(version) and any(x.startswith("Müşteri: 1 yeni") for x in json.loads(audit_row[1])["transfer_tables"])
    finally:
        _undo(db_engine, version)
        clean(db_engine)


def test_failed_job_rolls_back_everything(db_engine, monkeypatch):
    clean(db_engine)
    put(db_engine, {"Customer": [{"Code": "FL-1", "Name": "Hata", "IsActive": 1}]})
    with Session(db_engine) as s:
        before = s.execute(sa.text("SELECT MAX(Id) FROM adm.DataVersion")).scalar()
        job_id = queue.enqueue(s, TYPE_TRANSFER, CHANNEL_PROCESSING, None, {})
    job = _claim(db_engine)

    def boom(session, entity, run):
        raise RuntimeError("deneme")
    monkeypatch.setattr(transfer, "transfer_table", boom)
    run_transfer_job(job_id, job["Attempt"])
    try:
        with db_engine.connect() as c:
            assert c.execute(sa.text("SELECT Status FROM adm.Job WHERE Id = :i"), {"i": job_id}).scalar() == "Hata"
            assert c.execute(sa.text("SELECT MAX(Id) FROM adm.DataVersion")).scalar() == before
            assert not c.execute(sa.text("SELECT COUNT(*) FROM core.Customer WHERE Code = N'FL-1'")).scalar()
    finally:
        clean(db_engine)
