"""Veri aktarım geçmişi ve Veri aktarım raporu (fonksiyon 08; K-151, K-156): tam, kısmi ve hatayla biten aktarım listede; sayılar
DataVersionEntity toplamından; rapor iş sonucuna bağlı kalmaz; Excel; yetki. Test veritabanında (K-103); commit edilen aktarımlar geri alınır."""
import io
import json

import openpyxl
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.api.permissions import END_USER, KEY_USER
from app.engine.transfer_job import run_transfer_job
from app.jobs import queue
from app.jobs.constants import CHANNEL_PROCESSING, TYPE_TRANSFER
from app.jobs.settings import JobSettings

from auth_helpers import auth, ensure_user
from test_validation_references import put
from validation_helpers import clean, new_client

pytestmark = pytest.mark.db


def _run(engine, payload: dict) -> int:
    with Session(engine) as s:
        job_id = queue.enqueue(s, TYPE_TRANSFER, CHANNEL_PROCESSING, payload.get("user_id"), payload, summary="Aktarım")
    with Session(engine) as s:
        job = queue.claim_next(s, CHANNEL_PROCESSING, JobSettings(limit_processing=10))
    assert job["Id"] == job_id
    run_transfer_job(job_id, job["Attempt"])
    return job_id


@pytest.fixture(scope="module")
def history(db_engine):
    """Üç aktarım: tam (Müşteri HX-1 yeni), kısmi (İzin, Stok; veri yok) ve hatayla biten."""
    clean(db_engine)
    put(db_engine, {"Customer": [{"Code": "HX-1", "Name": "Geçmiş", "IsActive": 1}]})
    with db_engine.begin() as c:
        key = ensure_user(c, "pytest.gecmis.key", KEY_USER, "Geçmiş Key")
        end = ensure_user(c, "pytest.gecmis.end", END_USER, "Ad")
    full = _run(db_engine, {"user_id": key})
    partial = _run(db_engine, {"user_id": key, "mode": "Kısmi", "groups": ["Stok", "İzin"]})
    with Session(db_engine) as s:
        failed = queue.enqueue(s, TYPE_TRANSFER, CHANNEL_PROCESSING, key, {"user_id": key}, summary="Tam aktarım")
    with Session(db_engine) as s:
        job = queue.claim_next(s, CHANNEL_PROCESSING, JobSettings(limit_processing=10))
        queue.fail(s, failed, job["Attempt"], "Tam aktarım tamamlanamadı; önceki veri versiyonu geçerli.")
    with db_engine.connect() as c:
        versions = dict(c.execute(sa.text("SELECT JobId, Id FROM adm.DataVersion WHERE JobId IN (:a, :b)"), {"a": full, "b": partial}).all())
    yield {"key": key, "end": end, "full": full, "partial": partial, "failed": failed, "versions": versions}
    with db_engine.begin() as c:
        v = versions[full]
        c.execute(sa.text("DELETE FROM core.Customer WHERE VersionFrom = :v"), {"v": v})
        c.execute(sa.text("UPDATE core.Customer SET VersionTo = NULL WHERE VersionTo = :t"), {"t": v - 1})
        for version in versions.values():
            c.execute(sa.text("DELETE FROM adm.DataVersionEntity WHERE DataVersionId = :v"), {"v": version})
            c.execute(sa.text("DELETE FROM adm.DataVersion WHERE Id = :v"), {"v": version})
    clean(db_engine)


def _rows(client, user, ids) -> dict:
    body = {"fields": ["Id", "TransferType", "Groups", "RequesterName", "DataVersionId", "Status", "NewCount", "ChangedCount", "ClosedCount",
                       "NotTransferredCount", "DurationSeconds", "ErrorText"], "limit": 50,
            "sort": [{"field": "StartedAt", "dir": "desc"}]}
    r = client.post("/api/transfer-history/query", headers=auth(user), json=body)
    assert r.status_code == 200, r.text
    return {row["Id"]: row for row in r.json()["rows"] if row["Id"] in ids}


def test_history_lists_full_partial_and_failed(history, db_engine):
    h, client = history, new_client()
    rows = _rows(client, h["key"], [h["full"], h["partial"], h["failed"]])
    full, partial, failed = rows[h["full"]], rows[h["partial"]], rows[h["failed"]]
    assert (full["TransferType"], full["Groups"], full["Status"], full["DataVersionId"]) == ("Tam", None, "Bitti", h["versions"][h["full"]])
    assert full["NewCount"] >= 1 and full["RequesterName"] == "Geçmiş Key" and full["DurationSeconds"] is not None
    assert (partial["TransferType"], partial["Groups"], partial["DataVersionId"]) == ("Kısmi", "Stok, İzin", h["versions"][h["partial"]])
    assert (partial["NewCount"], partial["ClosedCount"]) == (None, None)                     # veri gelmedi: sayı yok
    assert (failed["Status"], failed["DataVersionId"], failed["NewCount"]) == ("Hata", None, None) and "tamamlanamadı" in failed["ErrorText"]
    with db_engine.connect() as c:
        synthetic = c.execute(sa.text("SELECT COUNT(*) FROM adm.DataVersion WHERE IsSynthetic = 1 AND JobId IS NOT NULL")).scalar()
    assert synthetic == 0                                                                   # sentetik versiyonun işi yok: listede görünmez


def test_report_reads_version_entities_not_job_result(history, db_engine):
    h, client = history, new_client()
    with db_engine.begin() as c:
        c.execute(sa.text("UPDATE adm.Job SET Result = NULL WHERE Id = :i"), {"i": h["full"]})     # rapor iş sonucuna bağlı değil
    body = client.get(f"/api/transfers/{h['full']}", headers=auth(h["key"])).json()
    tables = {t["entity"]: t for t in body["tables"]}
    assert body["data_version"] == h["versions"][h["full"]] and body["transfer_type"] == "Tam" and body["requested_by_name"] == "Geçmiş Key"
    assert len(tables) == 25 and tables["Customer"]["new"] == 1 and tables["Forecast"]["note"] == "Veri gelmedi; mevcut veri korunur."
    assert [t["entity"] for t in body["tables"]][:2] == ["Location", "Material"]               # aktarım sırasıyla
    partial = client.get(f"/api/transfers/{h['partial']}", headers=auth(h["key"])).json()
    assert partial["transfer_type"] == "Kısmi" and partial["groups"] == ["Stok", "İzin"]
    assert {t["entity"] for t in partial["tables"]} == {"Stock", "BorrowPayback", "EmployeeAbsence"}
    failed = client.get(f"/api/transfers/{h['failed']}", headers=auth(h["key"])).json()
    assert failed["status"] == "Hata" and failed["tables"] == [] and "tamamlanamadı" in failed["error"]


def test_report_excel_has_rows_info_and_audit(history, db_engine):
    h, client = history, new_client()
    r = client.get(f"/api/transfers/{h['partial']}/excel", headers=auth(h["key"]))
    assert r.status_code == 200 and "veri-aktarim-raporu" in r.headers["content-disposition"]
    wb = openpyxl.load_workbook(io.BytesIO(r.content))
    data = [row for row in wb["Veri"].iter_rows(values_only=True)]
    assert data[0] == ("Tablo", "Yeni", "Güncellenen", "Silinen", "Aktarılmayan", "Not") and len(data) == 4
    info = dict(row[:2] for row in wb["Bilgi"].iter_rows(values_only=True))
    assert info["Tür"] == "Kısmi · Stok, İzin" and info["Veri versiyonu"] == f"v{h['versions'][h['partial']]}"
    with db_engine.connect() as c:
        row = c.execute(sa.text("SELECT TOP 1 ObjectType, NewValue FROM adm.AuditLog WHERE ObjectType = N'transfer-report' ORDER BY Id DESC")).one()
    assert json.loads(row[1])["rows"] == 3


def test_end_user_cannot_see_history_or_report(history):
    h, client = history, new_client()
    assert client.post("/api/transfer-history/query", headers=auth(h["end"]), json={"fields": ["Id"]}).status_code == 403
    assert client.get(f"/api/transfers/{h['full']}", headers=auth(h["end"])).status_code == 403
    assert client.get(f"/api/transfers/{h['full']}/excel", headers=auth(h["end"])).status_code == 403
