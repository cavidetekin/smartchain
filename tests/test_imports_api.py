"""Excel yükleme API'si (ekran 02, fonksiyon 03, K-129): rol, iki yol, devam, vazgeç, hata raporu, iz, tekrar eden anahtar."""
import io
import time
from pathlib import Path
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook as OpenWorkbook, load_workbook
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.main import create_app
from app.api.permissions import ADMIN, END_USER, KEY_USER, SYSTEM_OWNER
from app.api.repositories import imports as repo
from app.api.services import imports as service
from app.engine.import_job import run_import_job
from app.engine.service import EngineService
from app.integration import contract
from app.integration.template import write_template
from app.jobs import queue
from app.jobs.constants import CHANNEL_EXCEL, STATUS_DONE, STATUS_FAILED, TYPE_PRECHECK
from app.jobs.settings import JobSettings

from auth_helpers import auth, delete_users, ensure_user

pytestmark = pytest.mark.db

PREFIX = "pytest.yukleme."
TRIGGER = "adm.TR_AuditLog_Yukleme"
ROLES = (SYSTEM_OWNER, ADMIN, KEY_USER, END_USER)
ENTITY = "Resource"


def clean(engine):
    with engine.begin() as c:
        c.execute(text(f"DROP TRIGGER IF EXISTS {TRIGGER}"))
        c.execute(text("DELETE FROM stg.Resource"))
        c.execute(text("DELETE FROM stg.Material"))
        c.execute(text("DELETE FROM adm.ImportFinding"))
        c.execute(text("DELETE FROM adm.ImportBatch"))
        c.execute(text("DELETE FROM adm.Job WHERE JobType = N'Excel ön kontrol'"))
        c.execute(text("DELETE FROM adm.AuditLog WHERE ObjectType = N'ImportBatch'"))
        c.execute(text("DELETE FROM adm.SystemEvent WHERE Component = N'Denetim izi'"))
        ids = [r[0] for r in c.execute(text("SELECT Id FROM adm.AppUser WHERE UserName LIKE :p"), {"p": PREFIX + "%"})]
        delete_users(c, ids)


@pytest.fixture
def people(db_engine):
    clean(db_engine)
    with db_engine.begin() as c:
        out = {r: ensure_user(c, PREFIX + r.replace(" ", "-").lower(), r, f"Ad {r}") for r in ROLES}
    yield out
    clean(db_engine)


@pytest.fixture
def client():
    return TestClient(create_app(), raise_server_exceptions=False)


def xlsx(rows=(), entity=ENTITY) -> bytes:
    buffer = io.BytesIO()
    write_template(buffer, contract.entity(entity), None, rows=rows)
    return buffer.getvalue()


GOOD = [{"LocationCode": "ORM-01", "Code": f"A-{i}", "Name": f"Ad {i}", "IsMachine": 1} for i in range(3)]
MIXED = [*GOOD, {"LocationCode": "ORM-01", "Name": "Kodsuz"}, {"LocationCode": "ORM-01", "Code": "B-1", "IsMachine": "belki"}]


def label(name, table=ENTITY):
    return next(f.label for f in contract.fields(table) if f.name == name)


def upload(client, user, body, entity=ENTITY, mode="Değişen", name="kaynak.xlsx"):
    return client.post(f"/api/imports/{entity}?mode={quote(mode)}", content=body, headers={**auth(user), "X-File-Name": quote(name)})


def stg_rows(engine, table="Resource"):
    with engine.connect() as c:
        return c.execute(text(f"SELECT * FROM stg.[{table}] ORDER BY SourceRowNo")).mappings().all()


def batch_row(engine, batch_id):
    with engine.connect() as c:
        return c.execute(text("SELECT * FROM adm.ImportBatch WHERE Id = :i"), {"i": batch_id}).mappings().one()


def findings(client, user, batch_id):
    body = {"fields": ["RowNo", "RowKey", "FieldName", "Value", "Message", "Severity"], "sort": [{"field": "RowNo", "dir": "asc"}],
            "filters": [{"field": "ImportBatchId", "op": "eq", "value": batch_id}], "offset": 0, "limit": 100}
    r = client.post("/api/import-findings/query", json=body, headers=auth(user))
    assert r.status_code == 200, r.text
    return r.json()["rows"]


def audit_rows(engine):
    with engine.connect() as c:
        return c.execute(text("SELECT Action, UserId, ObjectType, ObjectKey, NewValue FROM adm.AuditLog WHERE ObjectType = N'ImportBatch' ORDER BY Id")).all()


@pytest.mark.parametrize("role, allowed", [(SYSTEM_OWNER, True), (ADMIN, True), (KEY_USER, True), (END_USER, False)])
def test_roles(client, people, role, allowed):
    r = upload(client, people[role], xlsx(GOOD))
    assert r.status_code == (200 if allowed else 403)
    assert client.get("/api/imports/pending/Resource", headers=auth(people[role])).status_code == (200 if allowed else 403)
    assert client.get("/api/import-findings/columns", headers=auth(people[role])).status_code == (200 if allowed else 403)


def test_small_file_returns_the_summary(db_engine, client, people):
    r = upload(client, people[KEY_USER], xlsx(MIXED), name="kaynak v3.xlsx")
    assert r.status_code == 200, r.text
    s = r.json()
    assert (s["status"], s["checked"], s["read"], s["valid"], s["errors"], s["name"], s["file_name"], s["mode"]) == ("Ön kontrol", True, 5, 3, 2, "Kaynak", "kaynak v3.xlsx", "Değişen")
    assert s["template_version"] == s["current_version"] == contract.entity(ENTITY).version and s["job"] is None
    rows = stg_rows(db_engine)
    assert [(r["SourceRowNo"], r["Code"], r["ImportBatchId"]) for r in rows] == [(i + 2, f"A-{i}", s["batch_id"]) for i in range(3)]
    assert all("RowStatus" not in r for r in rows)  # satır durumu işlenmiş katmanda (K-140)
    b = batch_row(db_engine, s["batch_id"])
    assert (b["Method"], b["EntityName"], b["LoadType"], b["FileName"], b["UploadedBy"], b["TemplateVersion"], b["RowCount"], b["ErrorCount"]) == ("Excel", ENTITY, "Değişen", "kaynak v3.xlsx", people[KEY_USER], s["template_version"], 5, 2)
    assert Path(b["FilePath"]).name == f"{s['batch_id']}.xlsx" and Path(b["FilePath"]).exists()
    found = findings(client, people[KEY_USER], s["batch_id"])
    assert [(f["RowNo"], f["FieldName"], f["Severity"]) for f in found] == [(5, label("Code"), "Hata"), (6, label("IsMachine"), "Hata")]
    assert found[1]["Value"] == "belki" and found[1]["RowKey"] == "ORM-01 · B-1" and found[1]["Message"] == "1 ya da 0 bekleniyor."


def test_mode_is_kept_and_validated(db_engine, client, people):
    s = upload(client, people[KEY_USER], xlsx(GOOD), mode="Tam").json()
    assert s["mode"] == "Tam" and batch_row(db_engine, s["batch_id"])["LoadType"] == "Tam"
    r = upload(client, people[KEY_USER], xlsx(GOOD), mode="Ekle")
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation"


@pytest.mark.parametrize("body, code, status", [
    (b"xlsx degil", "import_bad_file", 422),
    (None, "import_wrong_entity", 422),
])
def test_rejected_files_open_no_batch(db_engine, client, people, body, code, status):
    r = upload(client, people[KEY_USER], body if body is not None else xlsx(entity="Material"))
    assert r.status_code == status and r.json()["error"]["code"] == code
    with db_engine.connect() as c:
        assert c.execute(text("SELECT COUNT(*) FROM adm.ImportBatch")).scalar() == 0
    if code == "import_wrong_entity":
        assert r.json()["error"]["message"] == "Bu dosya Kaynak tablosu içermemektedir."


def test_missing_required_column(client, people):
    wb = OpenWorkbook()
    wb.active.title = "Kaynak"
    wb.active.append(["LocationCode", "Name"])
    wb.active.append(["L", "Ad"])
    buffer = io.BytesIO()
    wb.save(buffer)
    r = upload(client, people[KEY_USER], buffer.getvalue())
    assert r.status_code == 422 and r.json()["error"]["code"] == "import_missing_columns"
    assert [d["field"] for d in r.json()["error"]["details"]] == ["Code"] and "Şablonu yeniden indirin" in r.json()["error"]["message"]


def test_unknown_entity_and_size_limit(client, people, monkeypatch):
    r = upload(client, people[KEY_USER], xlsx(GOOD), entity="Yok")
    assert r.status_code == 404 and r.json()["error"]["code"] == "entity_not_found"
    monkeypatch.setattr(repo, "read_settings", lambda s: {"ImportSyncMaxMb": 5, "ImportMaxMb": 0, "ImportMaxRows": 10})
    r = upload(client, people[KEY_USER], xlsx(GOOD))
    assert r.status_code == 413 and r.json()["error"]["code"] == "import_too_large" and "0 MB" in r.json()["error"]["message"]


def test_no_template_info_and_unknown_column_are_notes(db_engine, client, people):
    wb = OpenWorkbook()
    wb.active.append(["LocationCode", "Code", "Fazladan", "AdditionalText1"])
    wb.active.append(["L", "A", "x", "y"])
    buffer = io.BytesIO()
    wb.save(buffer)
    s = upload(client, people[KEY_USER], buffer.getvalue()).json()
    assert s["valid"] == 1 and s["template_version"] is None and s["notes"] == 3
    assert {f["severity"] for f in s["file_findings"]} == {"Uyarı", "Bilgi"} and any("Kaynak olarak okundu" in f["message"] for f in s["file_findings"])
    assert any("Fazladan" in f["message"] for f in s["file_findings"]) and any("AdditionalText1" in f["message"] for f in s["file_findings"])
    assert stg_rows(db_engine)[0]["AdditionalText1"] is None


def test_material_v3_file_without_non_stockable_is_accepted(client, people, db_engine):
    """K-113 eki: v3 dosyasında kolon yok; eski sürüm uyarısıyla yüklenir, değer boş kalır."""
    book = load_workbook(io.BytesIO(xlsx([{"LocationCode": "ORM-01", "Code": "A-1", "Name": "Ad", "BaseUom": "ADET"}], "Material")))
    sheet = book[contract.entity("Material").name]
    sheet.delete_cols([c.value for c in sheet[1]].index("IsNonStockable") + 1)
    for row in book["_Surum"].iter_rows():
        if row[0].value == "Sürüm":
            row[1].value = 3
    buffer = io.BytesIO()
    book.save(buffer)
    s = upload(client, people[KEY_USER], buffer.getvalue(), "Material", name="malzeme.xlsx").json()
    assert s["template_version"] == 3 and s["current_version"] == 4 and s["valid"] == 1 and s["errors"] == 0
    assert any("v3" in f["message"] for f in s["file_findings"])
    assert stg_rows(db_engine, "Material")[0]["IsNonStockable"] is None


def test_old_template_version_warns(client, people):
    buffer = io.BytesIO()
    wb_path = xlsx(GOOD)
    book = load_workbook(io.BytesIO(wb_path))
    info = book["_Surum"]
    for row in info.iter_rows():
        if row[0].value == "Sürüm":
            row[1].value = 1
    book.save(buffer)
    s = upload(client, people[KEY_USER], buffer.getvalue()).json()
    assert s["template_version"] == 1 and s["valid"] == 3 and any("v1" in f["message"] and "yeniden indirmeniz" in f["message"] for f in s["file_findings"])


def test_value_outside_list_is_noted_once_per_value(db_engine, client, people):
    rows = [{"LocationCode": "L", "RouteCode": "R", "OperationNo": i, "SequenceNo": 1, "Consumption": 1, "ResourceCode": "A", "ResourceRole": "Ana" if i < 3 else "Yan"} for i in range(1, 6)]
    s = upload(client, people[KEY_USER], xlsx(rows, "Routing"), "Routing").json()
    assert (s["valid"], s["errors"], s["notes"]) == (5, 0, 2)
    assert [(f["RowNo"], f["Value"]) for f in findings(client, people[KEY_USER], s["batch_id"])] == [(2, "Ana"), (4, "Yan")]
    with db_engine.begin() as c:
        c.execute(text("DELETE FROM stg.Routing"))


def test_duplicate_key_rejects_both_rows(db_engine, client, people):
    """K-129: iki satır da ham veriye girmez, sistem seçmez."""
    rows = [*GOOD, {"LocationCode": "ORM-01", "Code": "A-1", "Name": "Başka ad"}]
    s = upload(client, people[KEY_USER], xlsx(rows)).json()
    assert (s["read"], s["valid"], s["errors"]) == (4, 2, 2)
    assert [r["Code"] for r in stg_rows(db_engine)] == ["A-0", "A-2"]
    found = findings(client, people[KEY_USER], s["batch_id"])
    assert [f["RowNo"] for f in found] == [3, 5] and {f["Message"] for f in found} == {"Aynı kayıt 3 ve 5. satırlarda"} and found[0]["RowKey"] == "ORM-01 · A-1"
    assert found[0]["FieldName"] is None and found[0]["Value"] is None  # alan ve değer boş


def test_same_key_in_two_batches_is_allowed(db_engine, client, people):
    """stg'de partiye bağlı tekil indeks yok: aynı anahtar sonraki partide gelir (K-129); tekillik yalnız güncel hâlde (K-133)."""
    first = upload(client, people[KEY_USER], xlsx(GOOD)).json()
    assert client.post(f"/api/imports/{first['batch_id']}/continue", headers=auth(people[KEY_USER])).status_code == 200
    second = upload(client, people[ADMIN], xlsx(GOOD)).json()
    assert second["valid"] == 3 and len(stg_rows(db_engine)) == 6
    with db_engine.connect() as c:
        assert c.execute(text("SELECT COUNT(*) FROM sys.indexes i JOIN sys.tables t ON t.object_id = i.object_id "
                              "WHERE SCHEMA_NAME(t.schema_id) = N'stg' AND i.is_unique = 1 AND i.is_primary_key = 0 "
                              "AND NOT (i.has_filter = 1 AND i.filter_definition = N'([IsCurrent]=(1))')")).scalar() == 0


def test_continue_writes_trace_and_changes_status(db_engine, client, people):
    s = upload(client, people[KEY_USER], xlsx(MIXED)).json()
    r = client.post(f"/api/imports/{s['batch_id']}/continue", headers=auth(people[KEY_USER]))
    assert r.status_code == 200 and r.json()["status"] == "Alındı"
    (action, user, kind, key, new), = audit_rows(db_engine)
    assert (action, user, kind, key) == ("Excel yükleme", people[KEY_USER], "ImportBatch", "kaynak.xlsx") and '"valid": 3' in new and '"errors": 2' in new and '"mode": "Ekle / güncelle"' in new
    again = client.post(f"/api/imports/{s['batch_id']}/continue", headers=auth(people[KEY_USER]))
    assert again.status_code == 409 and again.json()["error"]["code"] == "import_not_pending"


def test_continue_rolled_back_when_trace_fails(db_engine, client, people):
    s = upload(client, people[KEY_USER], xlsx(GOOD)).json()
    with db_engine.begin() as c:
        c.execute(text(f"CREATE TRIGGER {TRIGGER} ON adm.AuditLog INSTEAD OF INSERT AS THROW 50001, 'yok', 1"))
    r = client.post(f"/api/imports/{s['batch_id']}/continue", headers=auth(people[KEY_USER]))
    assert r.status_code == 503 and r.json()["error"]["code"] == "audit_failed"
    assert batch_row(db_engine, s["batch_id"])["Status"] == "Ön kontrol"


def test_only_the_uploader_continues_or_cancels(client, people):
    s = upload(client, people[KEY_USER], xlsx(GOOD)).json()
    for action in ("continue", "cancel"):
        r = client.post(f"/api/imports/{s['batch_id']}/{action}", headers=auth(people[ADMIN]))
        assert r.status_code == 403 and r.json()["error"]["code"] == "import_not_owner"
    assert client.get(f"/api/imports/{s['batch_id']}", headers=auth(people[ADMIN])).status_code == 200


def test_cancel_removes_rows_and_file(db_engine, client, people):
    s = upload(client, people[KEY_USER], xlsx(GOOD)).json()
    path = Path(batch_row(db_engine, s["batch_id"])["FilePath"])
    r = client.post(f"/api/imports/{s['batch_id']}/cancel", headers=auth(people[KEY_USER]))
    assert r.status_code == 200 and r.json()["status"] == "Vazgeçildi" and not path.exists() and not stg_rows(db_engine)
    assert client.get("/api/imports/pending/Resource", headers=auth(people[KEY_USER])).json() is None


def test_all_rows_bad(db_engine, client, people):
    s = upload(client, people[KEY_USER], xlsx([{"LocationCode": "L"}, {"LocationCode": "L"}])).json()
    assert (s["status"], s["read"], s["valid"], s["errors"]) == ("Hatalı", 2, 0, 2) and not stg_rows(db_engine)
    assert client.post(f"/api/imports/{s['batch_id']}/continue", headers=auth(people[KEY_USER])).status_code == 409
    assert client.get(f"/api/imports/{s['batch_id']}/error-report", headers=auth(people[KEY_USER])).status_code == 200


def test_empty_file(client, people):
    s = upload(client, people[KEY_USER], xlsx()).json()
    assert (s["status"], s["read"], s["valid"]) == ("Hatalı", 0, 0)


def test_too_many_rows(db_engine, client, people, monkeypatch):
    monkeypatch.setattr(repo, "read_settings", lambda s: {"ImportSyncMaxMb": 5, "ImportMaxMb": 100, "ImportMaxRows": 2})
    s = upload(client, people[KEY_USER], xlsx(GOOD)).json()
    assert s["status"] == "Hatalı" and not stg_rows(db_engine) and any("en çok 2 satır" in f["message"] for f in s["file_findings"])


def test_error_report_keeps_original_values_and_can_be_reuploaded(db_engine, client, people):
    s = upload(client, people[KEY_USER], xlsx(MIXED)).json()
    r = client.get(f"/api/imports/{s['batch_id']}/error-report", headers=auth(people[KEY_USER]))
    assert r.status_code == 200 and f"hata-raporu_{s['batch_id']}" in r.headers["content-disposition"]
    ws = load_workbook(io.BytesIO(r.content))["Kaynak"]
    header = [c.value for c in ws[1]]
    data = [dict(zip(header, [c.value for c in row])) for row in ws.iter_rows(min_row=2)]
    assert header[-1] == "Hata" and [d["Name"] for d in data] == ["Kodsuz", None]
    assert data[1]["IsMachine"] == "belki" and data[1]["Hata"].startswith(f"{label('IsMachine')}: 1 ya da 0") and data[0]["Hata"] == f"{label('Code')}: Zorunlu alan boş."
    assert audit_rows(db_engine)[-1][0] == "Hata raporu indirme"
    again = upload(client, people[KEY_USER], r.content).json()  # düzeltilmeden yeniden: aynı hatalar, Hata kolonu tanınmayan kolon bilgisi
    assert again["errors"] == 2 and any("Hata" in f["message"] for f in again["file_findings"])


def test_error_report_file_gone(db_engine, client, people):
    s = upload(client, people[KEY_USER], xlsx(MIXED)).json()
    Path(batch_row(db_engine, s["batch_id"])["FilePath"]).unlink()
    r = client.get(f"/api/imports/{s['batch_id']}/error-report", headers=auth(people[KEY_USER]))
    assert r.status_code == 410 and r.json()["error"]["code"] == "import_file_gone"


def test_new_upload_replaces_own_open_batch(db_engine, client, people):
    first = upload(client, people[KEY_USER], xlsx(GOOD)).json()
    second = upload(client, people[KEY_USER], xlsx(GOOD[:1])).json()
    assert batch_row(db_engine, first["batch_id"])["Status"] == "Vazgeçildi" and len(stg_rows(db_engine)) == 1
    assert client.get("/api/imports/pending/Resource", headers=auth(people[KEY_USER])).json()["batch_id"] == second["batch_id"]
    other = upload(client, people[ADMIN], xlsx(GOOD)).json()
    assert batch_row(db_engine, second["batch_id"])["Status"] == "Ön kontrol" and other["read"] == 3  # başkasınınki kapanmaz


def test_unknown_batch(client, people):
    assert client.get("/api/imports/999999", headers=auth(people[KEY_USER])).status_code == 404


# --- Büyük dosya: iş kuyruğu -----------------------------------------------------------------------------------------


@pytest.fixture
def large(monkeypatch):
    """Eşik 0: her dosya iş olur."""
    monkeypatch.setattr(repo, "read_settings", lambda s: {"ImportSyncMaxMb": 0, "ImportMaxMb": 100, "ImportMaxRows": 200000})


def claim(db_engine):
    with Session(db_engine) as s:
        job = queue.claim_next(s, CHANNEL_EXCEL, JobSettings())
    assert job is not None and job["JobType"] == TYPE_PRECHECK
    return job


def job_of(db_engine, job_id):
    with Session(db_engine) as s:
        return queue.get_job(s, job_id, JobSettings())


def test_large_file_becomes_a_job_with_the_same_result(db_engine, client, people, large):
    r = upload(client, people[KEY_USER], xlsx(MIXED))
    assert r.status_code == 202, r.text
    batch_id, job_id = r.json()["batch_id"], r.json()["job_id"]
    waiting = client.get(f"/api/imports/{batch_id}", headers=auth(people[KEY_USER])).json()
    assert (waiting["checked"], waiting["read"], waiting["valid"], waiting["job"]["id"]) == (False, None, None, job_id)
    assert client.get("/api/imports/pending/Resource", headers=auth(people[KEY_USER])).json()["batch_id"] == batch_id
    assert client.post(f"/api/imports/{batch_id}/continue", headers=auth(people[KEY_USER])).status_code == 409
    job = claim(db_engine)
    assert job["Id"] == job_id and job["Channel"] == "Excel" and "Kaynak" in job["Summary"]
    run_import_job(job_id, job["Attempt"])
    assert job_of(db_engine, job_id)["Status"] == STATUS_DONE
    s = client.get(f"/api/imports/{batch_id}", headers=auth(people[KEY_USER])).json()
    assert (s["checked"], s["read"], s["valid"], s["errors"]) == (True, 5, 3, 2) and [r["Code"] for r in stg_rows(db_engine)] == ["A-0", "A-1", "A-2"]
    public = client.get(f"/api/jobs/{job_id}", headers=auth(people[KEY_USER])).json()
    assert public["import_batch_id"] == batch_id and "Payload" not in public  # "Sonucu aç"


def test_job_reports_opening_before_rows(db_engine, client, people, large):
    """İş #535: dosya açılırken ilerleme boştu, pencere "sırada" yazıyordu."""
    batch_id = upload(client, people[KEY_USER], xlsx(GOOD)).json()["batch_id"]
    stages = []
    with Session(db_engine) as s:
        service.run_precheck(s, batch_id, stages.append)
    assert stages[0] == "Dosya açılıyor" and stages[-1] == "3 satır"


def test_large_file_is_not_opened_in_the_request(db_engine, client, people, large, monkeypatch):
    """Açılış metin tablosunu okur: büyük dosya istekte açılmaz; yanlış dosya işte anlaşılır, parti Hatalı olur."""
    r = upload(client, people[KEY_USER], xlsx(GOOD, "Material"))  # küçük dosyada 422 olan yanlış tablo
    assert r.status_code == 202
    assert upload(client, people[KEY_USER], b"xlsx degil").status_code == 422  # paket denetimi açmadan
    batch_id = r.json()["batch_id"]
    with Session(db_engine) as s:
        service.run_precheck(s, batch_id)
    summary = client.get(f"/api/imports/{batch_id}", headers=auth(people[KEY_USER])).json()
    assert (summary["status"], summary["read"], summary["valid"]) == ("Hatalı", 0, 0)
    assert [f["message"] for f in summary["file_findings"]] == ["Bu dosya Kaynak tablosu içermemektedir."]


def test_job_retry_does_not_double_rows(db_engine, client, people, large):
    batch_id = upload(client, people[KEY_USER], xlsx(MIXED)).json()["batch_id"]
    with Session(db_engine) as s:
        service.run_precheck(s, batch_id)
        service.run_precheck(s, batch_id)
    assert len(stg_rows(db_engine)) == 3
    assert len(findings(client, people[KEY_USER], batch_id)) == 2


def test_failed_job_marks_batch_incomplete(db_engine, client, people, large, monkeypatch):
    batch_id = upload(client, people[KEY_USER], xlsx(GOOD)).json()["batch_id"]
    job = claim(db_engine)

    def explode(*_a, **_k):
        raise RuntimeError("düştü")

    monkeypatch.setattr(service.repo, "remove_duplicates", explode)
    run_import_job(job["Id"], job["Attempt"])
    assert job_of(db_engine, job["Id"])["Status"] == STATUS_FAILED
    assert batch_row(db_engine, batch_id)["Status"] == "Tamamlanmadı" and not stg_rows(db_engine)


def test_crashed_job_is_seen_on_read(db_engine, client, people, large):
    """Süreç düştü, iş Hata oldu: okunurken parti Tamamlanmadı olur."""
    batch_id = upload(client, people[KEY_USER], xlsx(GOOD)).json()["batch_id"]
    job = claim(db_engine)
    with Session(db_engine) as s:
        queue.fail(s, job["Id"], job["Attempt"], "süreç düştü")
    assert client.get(f"/api/imports/{batch_id}", headers=auth(people[KEY_USER])).json()["status"] == "Tamamlanmadı"


def test_engine_service_runs_the_precheck_in_its_own_process(db_engine, db_session, client, people, large):
    r = upload(client, people[KEY_USER], xlsx(MIXED)).json()
    svc = EngineService(db_engine, job_settings=JobSettings(), channels=(CHANNEL_EXCEL,))
    svc.start()
    try:
        end = time.monotonic() + 60
        while time.monotonic() < end:
            svc.poll_once()
            db_session.expire_all()
            job = queue.get_job(db_session, r["job_id"], JobSettings())
            if job["Status"] == STATUS_DONE and not svc.running:
                break
            time.sleep(0.2)
        assert job["Status"] == STATUS_DONE, job
    finally:
        svc.shutdown()
    s = client.get(f"/api/imports/{r['batch_id']}", headers=auth(people[KEY_USER])).json()
    assert (s["read"], s["valid"], s["errors"]) == (5, 3, 2) and "5 satır okundu" in job["Progress"]


def test_cancel_queued_job(db_engine, client, people, large):
    r = upload(client, people[KEY_USER], xlsx(GOOD)).json()
    assert client.post(f"/api/imports/{r['batch_id']}/cancel", headers=auth(people[KEY_USER])).json()["status"] == "Vazgeçildi"
    assert job_of(db_engine, r["job_id"])["Status"] == "İptal" and not Path(batch_row(db_engine, r["batch_id"])["FilePath"]).exists()


def test_cancel_while_running_stops_at_next_chunk(db_engine, client, people, large, monkeypatch):
    monkeypatch.setattr(service, "CHUNK_ROWS", 1)
    batch_id = upload(client, people[KEY_USER], xlsx(GOOD)).json()["batch_id"]
    job = claim(db_engine)
    r = client.post(f"/api/imports/{batch_id}/cancel", headers=auth(people[KEY_USER]))  # iş çalışıyor: dosya ve satırları iş temizler
    assert r.json()["status"] == "Vazgeçildi" and Path(batch_row(db_engine, batch_id)["FilePath"]).exists()
    run_import_job(job["Id"], job["Attempt"])
    assert not Path(batch_row(db_engine, batch_id)["FilePath"]).exists() and not stg_rows(db_engine)
    assert job_of(db_engine, job["Id"])["Status"] == STATUS_DONE


# --- Liste --------------------------------------------------------------------------------------------------------


def test_last_load_time_only_for_received_batches(client, people):
    h = auth(people[KEY_USER])

    def last():
        body = {"fields": ["Name", "LastLoadAt"], "filters": [{"field": "Name", "op": "equals", "value": "Kaynak"}], "sort": [], "offset": 0, "limit": 5}
        return client.post("/api/data-entities/query", json=body, headers=h).json()["rows"][0]["LastLoadAt"]

    assert last() is None
    s = upload(client, people[KEY_USER], xlsx(GOOD)).json()
    assert last() is None  # ön kontrol sayılmaz
    client.post(f"/api/imports/{s['batch_id']}/continue", headers=h)
    assert last() is not None
    columns = client.get("/api/data-entities/columns", headers=h).json()["columns"]
    column = next(c for c in columns if c["field"] == "LastLoadAt")
    assert column["label"] == "Son yükleme zamanı" and "ham veriye" in column["note"]
    assert next(c for c in columns if c["field"] == "Name")["note"] is None  # açıklama yoksa ipucu yok


def test_excel_channel_in_job_filter(client, people):
    columns = client.get("/api/job-queue/columns", headers=auth(people[ADMIN])).json()["columns"]
    assert "Excel" in next(c for c in columns if c["field"] == "Channel")["values"] and "Excel ön kontrol" in next(c for c in columns if c["field"] == "JobType")["values"]
