"""Veri çekme ve entegrasyon tanımı (fonksiyon 01 ve 91, ekran 02 ve 23, K-130). İş, motor servisinin çağırdığı işlevle koşar."""
import io
import json

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.api.main import create_app
from app.api.permissions import ADMIN, END_USER, KEY_USER, SYSTEM_OWNER
from app.engine.pull_job import run_pull_job
from app.integration.sql_source import Source
from app.integration.template import write_template
from app.integration import contract
from app.jobs import queue
from app.jobs.constants import CHANNEL_PULL, TYPE_PULL
from app.jobs.settings import JobSettings

from auth_helpers import auth, delete_users, ensure_user
from integration_helpers import DATABASE, clean_settings, integration_db, run_sql, _written  # noqa: F401

pytestmark = pytest.mark.db

PREFIX = "pytest.cekim."
ROLES = (SYSTEM_OWNER, ADMIN, KEY_USER, END_USER)


def clean(engine):
    with engine.begin() as c:
        c.execute(sa.text("DELETE FROM adm.IntegrationViewVersion"))
        c.execute(sa.text("DELETE FROM adm.IntegrationEntity"))
        for table in ("Material", "Stock", "BOM", "Resource"):
            c.execute(sa.text(f"DELETE FROM stg.[{table}]"))
        c.execute(sa.text("DELETE FROM adm.ImportFinding"))
        c.execute(sa.text("DELETE FROM adm.ImportBatch"))
        c.execute(sa.text("DELETE FROM adm.Job WHERE JobType IN (N'Veri çekme', N'Excel ön kontrol')"))
        c.execute(sa.text("DELETE FROM adm.AuditLog WHERE ObjectType IN (N'IntegrationEntity', N'Job') AND Action IN (N'Veri çekme', N'Yöntem değişikliği', N'Çekim kapatma', N'Çekim açma', N'Entegrasyon tanımı')"))
        delete_users(c, [r[0] for r in c.execute(sa.text("SELECT Id FROM adm.AppUser WHERE UserName LIKE :p"), {"p": PREFIX + "%"})])


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


@pytest.fixture
def setup(integration_db, people, client):  # noqa: F811
    """Malzeme SQL ve view'lı."""
    use_sql(client, people, "Material")
    return people


def save(client, headers, entity, **fields):
    return client.put("/api/integration/entities", json={"changes": [{"entity": entity, **fields}]}, headers=headers)


def use_sql(client, people, table, view=None):
    owner = auth(people[SYSTEM_OWNER])
    assert save(client, owner, table, method="SQL").status_code == 200
    r = save(client, owner, table, view=view or f"View_{table}")
    assert r.status_code == 200, r.text


def pull(client, people, **body):
    r = client.post("/api/pulls", json=body, headers=auth(people[KEY_USER]))
    assert r.status_code == 202, r.text
    return r.json()["job_id"]


def run(engine, job_id):
    with Session(engine) as s:
        job = queue.claim_next(s, CHANNEL_PULL, JobSettings())
        assert job["Id"] == job_id
        attempt = job["Attempt"]
    run_pull_job(job_id, attempt)


def result(client, people, job_id):
    r = client.get(f"/api/pulls/{job_id}", headers=auth(people[KEY_USER]))
    assert r.status_code == 200, r.text
    return r.json()


def table_of(data, entity):
    return next(t for t in data["tables"] if t["entity"] == entity)


def pull_one(engine, client, people, **body):
    job = pull(client, people, **{"entities": ["Material"], **body})
    run(engine, job)
    return table_of(result(client, people, job), "Material")


def stg_count(engine, table="Material"):
    with engine.connect() as c:
        return c.execute(sa.text(f"SELECT COUNT(*) FROM stg.[{table}]")).scalar()


def batches(engine):
    with engine.connect() as c:
        return c.execute(sa.text("SELECT * FROM adm.ImportBatch ORDER BY Id")).mappings().all()


def audits(engine, action):
    with engine.connect() as c:
        return c.execute(sa.text("SELECT * FROM adm.AuditLog WHERE Action = :a ORDER BY Id"), {"a": action}).mappings().all()


def signal_again():
    run_sql("INSERT INTO dbo.ERP_LoadLog (EntityName, StartedAt, FinishedAt) VALUES (NULL, SYSUTCDATETIME(), SYSUTCDATETIME())")


# --- Yetki ---

@pytest.mark.parametrize("method, path, body, allowed", [
    ("put", "/api/integration/entities", {"changes": [{"entity": "Material", "method": "SQL"}]}, {SYSTEM_OWNER}),
    ("put", "/api/integration/entities", {"changes": [{"entity": "Material", "view": ""}]}, {SYSTEM_OWNER}),
    ("put", "/api/integration/connection", {"database": DATABASE}, {SYSTEM_OWNER}),
    ("put", "/api/integration/entities", {"changes": [{"entity": "Material", "pull_enabled": True}]}, {SYSTEM_OWNER, ADMIN}),
    ("get", "/api/integration/connection", None, {SYSTEM_OWNER, ADMIN}),
    ("post", "/api/integration/test", {}, {SYSTEM_OWNER, ADMIN}),
    ("get", "/api/integration/entities/Material/view-versions", None, {SYSTEM_OWNER, ADMIN}),
    ("get", "/api/pulls/plan", None, {SYSTEM_OWNER, ADMIN, KEY_USER}),
])
def test_roles(integration_db, people, client, method, path, body, allowed):  # noqa: F811
    for role in ROLES:
        kwargs = {"headers": auth(people[role])}
        if body is not None:
            kwargs["json"] = body
        status = getattr(client, method)(path, **kwargs).status_code
        assert (status == 403) == (role not in allowed), (role, path, status)


def test_end_user_cannot_start_a_pull(integration_db, people, client):  # noqa: F811
    assert client.post("/api/pulls", json={}, headers=auth(people[END_USER])).status_code == 403


# --- Yöntem, çekim, view ---

def test_default_is_excel_without_a_row(integration_db, people, client):  # noqa: F811
    r = client.post("/api/data-entities/query", json={"limit": 50}, headers=auth(people[KEY_USER]))
    assert r.status_code == 200, r.text
    material = next(x for x in r.json()["rows"] if x["Entity"] == "Material")
    assert material["Method"] == "Excel" and material["IsPullEnabled"] is True and material["Warning"] is None


def test_empty_method_counts_as_excel(integration_db, people, client):  # noqa: F811
    with integration_db.begin() as c:
        c.execute(sa.text("INSERT INTO adm.IntegrationEntity (EntityName, Method) VALUES (N'Material', NULL)"))
    plan = client.get("/api/pulls/plan", headers=auth(people[KEY_USER])).json()
    material = next(t for t in plan["tables"] if t["entity"] == "Material")
    assert material["method"] == "Excel" and material["state"] == "Atlandı" and material["reason"] == "Yöntemi Excel"


def test_method_is_saved_and_audited(integration_db, people, client):  # noqa: F811
    r = save(client, auth(people[SYSTEM_OWNER]), "Material", method="SQL")
    assert r.status_code == 200
    rows = audits(integration_db, "Yöntem değişikliği")
    assert len(rows) == 1 and json.loads(rows[0]["NewValue"])["pull_method"] == "SQL" and json.loads(rows[0]["OldValue"])["pull_method"] == "Excel"
    save(client, auth(people[SYSTEM_OWNER]), "Material", method="SQL")
    assert len(audits(integration_db, "Yöntem değişikliği")) == 1  # değişmeyen değer iz yazmaz
    q = client.post("/api/data-entities/query", json={"limit": 50}, headers=auth(people[KEY_USER])).json()
    assert next(x for x in q["rows"] if x["Entity"] == "Material")["Warning"] == "View tanımlı değil"


@pytest.mark.parametrize("value", ["API", "", "excel"])
def test_api_is_not_a_method_in_phase_one(integration_db, people, client, value):  # noqa: F811
    r = save(client, auth(people[SYSTEM_OWNER]), "Material", method=value)
    assert r.status_code == 422 and r.json()["error"]["code"] == "integration_bad_method"


def test_pull_switch_needs_a_reason(integration_db, people, client):  # noqa: F811
    admin = auth(people[ADMIN])
    r = save(client, admin, "Material", pull_enabled=False, reason="  ")
    assert r.status_code == 422 and r.json()["error"]["code"] == "integration_reason_required"
    assert save(client, admin, "Material", pull_enabled=False, reason="ERP bakımı").status_code == 200
    row = client.post("/api/data-entities/query", json={"limit": 50}, headers=auth(people[KEY_USER])).json()["rows"]
    material = next(x for x in row if x["Entity"] == "Material")
    assert material["IsPullEnabled"] is False and material["DisabledReason"] == "ERP bakımı" and material["DisabledByName"] == f"Ad {ADMIN}" and material["DisabledAt"]
    assert json.loads(audits(integration_db, "Çekim kapatma")[0]["NewValue"])["reason"] == "ERP bakımı"
    assert save(client, admin, "Material", pull_enabled=True).status_code == 200
    with integration_db.connect() as c:
        again = c.execute(sa.text("SELECT DisabledReason, IsPullEnabled FROM adm.IntegrationEntity WHERE EntityName = N'Material'")).one()
    assert again.DisabledReason is None and again.IsPullEnabled and len(audits(integration_db, "Çekim açma")) == 1


def test_view_must_exist(integration_db, people, client):  # noqa: F811
    owner = auth(people[SYSTEM_OWNER])
    r = save(client, owner, "Material", view="View_Yok")
    assert r.status_code == 422 and r.json()["error"]["code"] == "integration_view_not_found"
    r = save(client, owner, "Material", view="View_Material")
    assert r.status_code == 200 and r.json()["saved"] == 1
    r = client.post("/api/integration-entities/query", json={"limit": 50}, headers=auth(people[ADMIN]))
    assert r.status_code == 200, r.text
    material = next(x for x in r.json()["rows"] if x["Entity"] == "Material")
    assert material["ViewName"] == "View_Material" and material["LastCheckStatus"] == "Uyumlu" and material["ColumnMatch"].split(" / ")[0] == material["ColumnMatch"].split(" / ")[1]


def test_connection_rule_and_card(integration_db, people, client):  # noqa: F811
    owner = auth(people[SYSTEM_OWNER])
    r = client.put("/api/integration/connection", json={"database": "x]; DROP DATABASE y"}, headers=owner)
    assert r.status_code == 422
    card = client.put("/api/integration/connection", json={"database": DATABASE}, headers=owner).json()
    assert card["database"] == DATABASE and card["excel_tables"] == 25 and card["sql_tables"] == 0 and card["account"]


def test_not_configured(db_engine, people, client):
    clean_settings(db_engine)
    r = client.post("/api/pulls", json={}, headers=auth(people[KEY_USER]))
    assert r.status_code == 409 and r.json()["error"]["code"] == "integration_not_configured"
    assert client.post("/api/integration/test", json={}, headers=auth(people[ADMIN])).status_code == 409


def test_save_is_all_or_nothing(integration_db, people, client):  # noqa: F811
    """K-132: biri geçersizse hiçbiri yazılmaz; iz de yazılmaz."""
    r = client.put("/api/integration/entities", headers=auth(people[SYSTEM_OWNER]), json={"changes": [
        {"entity": "Material", "method": "SQL"}, {"entity": "Stock", "method": "SQL", "view": "View_Yok"}]})
    assert r.status_code == 422 and r.json()["error"]["code"] == "integration_view_not_found"
    with integration_db.connect() as c:
        assert c.execute(sa.text("SELECT COUNT(*) FROM adm.IntegrationEntity")).scalar() == 0
    assert not audits(integration_db, "Yöntem değişikliği")


def test_save_several_changes_at_once(integration_db, people, client):  # noqa: F811
    r = client.put("/api/integration/entities", headers=auth(people[SYSTEM_OWNER]), json={"changes": [
        {"entity": "Material", "method": "SQL", "view": "View_Material"}, {"entity": "Stock", "pull_enabled": False, "reason": "Sayım"}]})
    assert r.status_code == 200 and r.json()["saved"] == 2
    with integration_db.connect() as c:
        rows = {x.EntityName: x for x in c.execute(sa.text("SELECT EntityName, Method, ViewName, IsPullEnabled, DisabledReason FROM adm.IntegrationEntity"))}
    assert rows["Material"].Method == "SQL" and rows["Material"].ViewName == "View_Material" and not rows["Stock"].IsPullEnabled and rows["Stock"].DisabledReason == "Sayım"
    assert len(audits(integration_db, "Yöntem değişikliği")) == 1 and len(audits(integration_db, "Entegrasyon tanımı")) == 1 and len(audits(integration_db, "Çekim kapatma")) == 1


def test_admin_cannot_change_method_in_a_mixed_save(integration_db, people, client):  # noqa: F811
    r = client.put("/api/integration/entities", headers=auth(people[ADMIN]), json={"changes": [{"entity": "Stock", "pull_enabled": False, "reason": "Sayım"}, {"entity": "Material", "method": "SQL"}]})
    assert r.status_code == 403
    with integration_db.connect() as c:
        assert c.execute(sa.text("SELECT COUNT(*) FROM adm.IntegrationEntity")).scalar() == 0


# --- Test ve önizleme ---

def test_connection_test_reports_steps_and_only_reads(integration_db, people, client):  # noqa: F811
    use_sql(client, people, "Material")
    use_sql(client, people, "Stock")
    before = run_sql("SELECT COUNT(*) FROM dbo.ERP_Material")[0][0]
    r = client.post("/api/integration/test", json={}, headers=auth(people[ADMIN]))
    assert r.status_code == 200, r.text
    body = r.json()
    assert [s["key"] for s in body["steps"]] == ["access", "identity", "signal", "views"] and body["ok"] is True
    material = next(t for t in body["tables"] if t["entity"] == "Material")
    assert material["notes"] == ["Tekrar eden anahtar: 1 kayıt."] and material["status"] == "Uyumlu" and not material["warnings"]  # H4 alan uyumunu etkilemez
    assert stg_count(integration_db) == 0 and run_sql("SELECT COUNT(*) FROM dbo.ERP_Material")[0][0] == before


def test_connection_test_names_the_failing_step(integration_db, people, client):  # noqa: F811
    with integration_db.begin() as c:
        c.execute(sa.text("UPDATE adm.SystemSetting SET Value = N'YokBoyleBir_test' WHERE SettingKey = N'IntegrationDatabase'"))
    body = client.post("/api/integration/test", json={}, headers=auth(people[ADMIN])).json()
    assert body["ok"] is False and body["steps"][-1]["key"] == "access" and "bağlanılamadı" in body["steps"][-1]["detail"]


def test_preview_checks_rows_and_writes_nothing(integration_db, people, client):  # noqa: F811
    use_sql(client, people, "Material")
    r = client.post("/api/integration/entities/Material/preview", json={}, headers=auth(people[ADMIN]))
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["rows"]) == 20 and body["columns"][0]["field"] == "LocationCode" and body["rows"][0]["values"]["Code"]
    assert stg_count(integration_db) == 0 and not batches(integration_db)
    assert client.post("/api/integration/entities/Stock/preview", json={}, headers=auth(people[ADMIN])).status_code == 409


def test_view_versions(integration_db, people, client):  # noqa: F811
    use_sql(client, people, "Material")
    admin = auth(people[ADMIN])
    assert [v["version"] for v in client.get("/api/integration/entities/Material/view-versions", headers=admin).json()] == [1]
    client.post("/api/integration/test", json={}, headers=admin)
    assert len(client.get("/api/integration/entities/Material/view-versions", headers=admin).json()) == 1  # değişmedi
    original = run_sql("SELECT OBJECT_DEFINITION(OBJECT_ID('dbo.View_Material'))")[0][0]
    changed = original.replace("CREATE VIEW", "ALTER VIEW", 1) + "\n-- demo"
    run_sql(changed)
    try:
        client.post("/api/integration/test", json={}, headers=admin)
        found = client.get("/api/integration/entities/Material/view-versions", headers=admin).json()
        assert [v["version"] for v in found] == [2, 1] and "-- demo" in found[0]["definition"] and "-- demo" not in found[1]["definition"]
    finally:
        run_sql(original.replace("CREATE VIEW", "ALTER VIEW", 1))


def test_definition_is_saved_even_if_check_fails(integration_db, people, client, db_engine):  # noqa: F811
    """Demo 8a: view zorunlu kolonu kaybetti, denetim başarısız; yine de yeni sürüm."""
    use_sql(client, people, "Material")
    original = run_sql("SELECT OBJECT_DEFINITION(OBJECT_ID('dbo.View_Material'))")[0][0]
    admin = auth(people[ADMIN])
    run_sql(original.replace("CREATE VIEW", "ALTER VIEW", 1).replace("t.[ITEM_CODE] AS [Code],", "t.[ITEM_CODE] AS [CodeX],"))
    try:
        body = client.post("/api/integration/test", json={}, headers=admin).json()
        assert next(t for t in body["tables"] if t["entity"] == "Material")["status"] == "Hatalı"
        found = client.get("/api/integration/entities/Material/view-versions", headers=admin).json()
        assert [v["version"] for v in found] == [2, 1] and "CodeX" in found[0]["definition"]
        signal_again()
        assert pull_one(db_engine, client, people)["status"] == "Hata"
        assert len(client.get("/api/integration/entities/Material/view-versions", headers=admin).json()) == 2  # aynı tanım yeni sürüm olmaz
    finally:
        run_sql(original.replace("CREATE VIEW", "ALTER VIEW", 1))


# --- Çekim ---

def test_pull_reads_view_into_staging(setup, client, db_engine):
    table = pull_one(db_engine, client, setup)
    assert (table["status"], table["read"], table["valid"], table["errors"]) == ("Alındı", 214, 212, 2)  # kirli Malzeme: hazır kural, pasif ebeveyn ve veri kuralı örnekleri dahil (docs/11)
    assert stg_count(db_engine) == 212
    with db_engine.connect() as c:
        assert c.execute(sa.text("SELECT COUNT(*) FROM stg.Material WHERE Code = N'SAT-040'")).scalar() == 0  # H4
    batch = batches(db_engine)[-1]
    assert (batch["Method"], batch["LoadType"], batch["Status"], batch["SourceObject"], batch["UploadedBy"]) == ("SQL", "Tam", "Alındı", "View_Material", setup[KEY_USER])
    assert batch["SignalId"] and batch["FileName"] is None
    with db_engine.connect() as c:
        row = c.execute(sa.text("SELECT LastPullStatus, LastPullAt FROM adm.IntegrationEntity WHERE EntityName = N'Material'")).one()
    assert row.LastPullStatus == "Alındı" and row.LastPullAt


def test_findings_list_reads_sql_batch(setup, client, db_engine):
    """2. demo: Bulgular penceresi SQL partisinde 422 veriyordu; pencerenin gönderdiği filtre gerçek listeyle sınanır."""
    table = pull_one(db_engine, client, setup)
    r = client.post("/api/import-findings/query", headers=auth(setup[KEY_USER]),
                    json={"limit": 50, "filters": [{"field": "ImportBatchId", "op": "eq", "value": table["batch_id"]}]})
    assert r.status_code == 200, r.text
    errors = [x for x in r.json()["rows"] if x["Severity"] == "Hata"]  # bilgi: liste dışı değer örneği (V-MAT-8)
    assert {x["RowKey"] for x in errors} == {"ORM-01 · SAT-040"} and len(errors) == 2
    bad = client.post("/api/import-findings/query", headers=auth(setup[KEY_USER]), json={"limit": 50, "filters": [{"field": "ImportBatchId", "op": "equals", "value": str(table["batch_id"])}]})
    assert bad.status_code == 422  # eski filtre: sayı alanında metin işlemi


def test_pull_writes_nothing_to_the_source(setup, client, db_engine):
    tables = "SELECT t.name, SUM(p.rows) FROM sys.tables t JOIN sys.partitions p ON p.object_id = t.object_id AND p.index_id IN (0, 1) GROUP BY t.name ORDER BY t.name"
    before = [tuple(r) for r in run_sql(tables)]
    views = run_sql("SELECT COUNT(*) FROM sys.views")[0][0]
    pull_one(db_engine, client, setup)
    assert [tuple(r) for r in run_sql(tables)] == before and run_sql("SELECT COUNT(*) FROM sys.views")[0][0] == views


def test_channel_and_type(setup, client, db_engine):
    job = pull(client, setup)
    with db_engine.connect() as c:
        row = c.execute(sa.text("SELECT JobType, Channel, Summary FROM adm.Job WHERE Id = :i"), {"i": job}).one()
    assert (row.JobType, row.Channel) == (TYPE_PULL, CHANNEL_PULL) == ("Veri çekme", "Veri çekme") and "25 tablo" in row.Summary
    assert json.loads(audits(db_engine, "Veri çekme")[-1]["NewValue"])["entities"] == "Bütün tablolar"


def test_second_pull_is_refused(setup, client):
    pull(client, setup)
    r = client.post("/api/pulls", json={}, headers=auth(setup[KEY_USER]))
    assert r.status_code == 409 and r.json()["error"]["code"] == "pull_running"


def test_plan_lists_every_table_with_reason(setup, client):
    use_sql(client, setup, "Stock")
    with_owner = auth(setup[ADMIN])
    save(client, with_owner, "Stock", pull_enabled=False, reason="Sayım")
    save(client, auth(setup[SYSTEM_OWNER]), "BOM", method="SQL")
    plan = client.get("/api/pulls/plan", headers=auth(setup[KEY_USER])).json()
    states = {t["entity"]: (t["state"], t["reason"]) for t in plan["tables"]}
    assert len(plan["tables"]) == 25
    assert states["Material"] == ("Okunacak", None) and states["Resource"] == ("Atlandı", "Yöntemi Excel")
    assert states["Stock"] == ("Atlandı", "Çekim kapalı") and states["BOM"] == ("Atlandı", "View tanımsız")


def test_skipped_tables_get_their_reason(setup, client, db_engine):
    use_sql(client, setup, "Stock")
    save(client, auth(setup[ADMIN]), "Stock", pull_enabled=False, reason="Sayım")
    save(client, auth(setup[SYSTEM_OWNER]), "BOM", method="SQL")
    job = pull(client, setup)
    run(db_engine, job)
    data = result(client, setup, job)
    assert len(data["tables"]) == 25 and data["status"] == "Bitti"
    assert table_of(data, "Stock")["status"] == "Atlandı" and table_of(data, "Stock")["reason"] == "Çekim kapalı"
    assert table_of(data, "BOM")["reason"] == "View tanımsız" and table_of(data, "Resource")["reason"] == "Yöntemi Excel"
    assert table_of(data, "Material")["status"] == "Alındı" and stg_count(db_engine, "Stock") == 0


def test_no_new_signal_is_skipped_not_an_error(setup, client, db_engine):
    pull_one(db_engine, client, setup)
    table = pull_one(db_engine, client, setup)
    assert table["status"] == "Yeni veri yok" and table["batch_id"] is None
    assert stg_count(db_engine) == 212 and len(batches(db_engine)) == 1


def test_read_anyway(setup, client, db_engine):
    pull_one(db_engine, client, setup)
    table = pull_one(db_engine, client, setup, read_anyway=["Material"])
    assert table["status"] == "Alındı" and len(batches(db_engine)) == 2


def test_read_anyway_is_per_table(setup, client, db_engine):
    use_sql(client, setup, "Stock")
    job = pull(client, setup, entities=["Material", "Stock"])
    run(db_engine, job)
    job = pull(client, setup, entities=["Material", "Stock"], read_anyway=["Stock"])
    run(db_engine, job)
    data = result(client, setup, job)
    assert table_of(data, "Material")["status"] == "Yeni veri yok" and table_of(data, "Material")["reason"] == "Son çekimden beri değişiklik yok."
    assert table_of(data, "Stock")["status"] == "Alındı"


def test_new_signal_is_read(setup, client, db_engine):
    pull_one(db_engine, client, setup)
    signal_again()
    assert pull_one(db_engine, client, setup)["status"] == "Alındı"


def test_table_signal_counts_only_for_its_table(setup, client, db_engine):
    use_sql(client, setup, "Stock")
    job = pull(client, setup, entities=["Material", "Stock"])
    run(db_engine, job)
    run_sql("INSERT INTO dbo.ERP_LoadLog (EntityName, StartedAt, FinishedAt) VALUES (N'Stock', SYSUTCDATETIME(), SYSUTCDATETIME())")
    job = pull(client, setup, entities=["Material", "Stock"])
    run(db_engine, job)
    data = result(client, setup, job)
    assert table_of(data, "Material")["status"] == "Yeni veri yok" and table_of(data, "Stock")["status"] == "Alındı"


def test_refreshing_is_not_an_error_and_keeps_old_rows(setup, client, db_engine):
    pull_one(db_engine, client, setup)
    run_sql("INSERT INTO dbo.ERP_LoadLog (EntityName, StartedAt) VALUES (N'Material', SYSUTCDATETIME())")
    table = pull_one(db_engine, client, setup, read_anyway=["Material"])  # yine de oku da güncellemeyi geçmez
    assert table["status"] == "Veri güncellemesi devam ediyor" and table["reason"] == "Veri güncellemesi devam ediyor."
    assert stg_count(db_engine) == 212 and len(batches(db_engine)) == 1
    run_sql("UPDATE dbo.ERP_LoadLog SET FinishedAt = SYSUTCDATETIME() WHERE FinishedAt IS NULL")
    assert pull_one(db_engine, client, setup)["status"] == "Alındı"


def test_refresh_starting_during_read_rejects_the_batch(setup, client, db_engine, monkeypatch):
    original = Source.read_rows

    def starts_refresh(self, view, columns):
        run_sql("INSERT INTO dbo.ERP_LoadLog (EntityName, StartedAt) VALUES (NULL, SYSUTCDATETIME())")
        return original(self, view, columns)

    monkeypatch.setattr(Source, "read_rows", starts_refresh)
    table = pull_one(db_engine, client, setup)
    assert table["status"] == "Tamamlanmadı" and table["reason"] == "Çekim sırasında veri güncellendi."
    assert stg_count(db_engine) == 0 and batches(db_engine)[-1]["Status"] == "Tamamlanmadı"


def test_missing_required_column_keeps_old_rows(setup, client, db_engine):
    pull_one(db_engine, client, setup)
    signal_again()
    original = run_sql("SELECT OBJECT_DEFINITION(OBJECT_ID('dbo.View_Material'))")[0][0]
    broken = original.replace("CREATE VIEW", "ALTER VIEW", 1).replace("t.[ITEM_CODE] AS [Code],", "t.[ITEM_CODE] AS [CodeX],")
    assert broken != original.replace("CREATE VIEW", "ALTER VIEW", 1)
    run_sql(broken)
    try:
        table = pull_one(db_engine, client, setup)
        assert table["status"] == "Hata" and "Zorunlu kolon yok: Code" in table["reason"]
        assert stg_count(db_engine) == 212 and len(batches(db_engine)) == 1
        with db_engine.connect() as c:
            assert c.execute(sa.text("SELECT LastCheckStatus FROM adm.IntegrationEntity WHERE EntityName = N'Material'")).scalar() == "Hatalı"
    finally:
        run_sql(original.replace("CREATE VIEW", "ALTER VIEW", 1))


def test_one_table_error_does_not_stop_others(setup, client, db_engine):
    use_sql(client, setup, "Stock")
    with db_engine.begin() as c:
        c.execute(sa.text("UPDATE adm.IntegrationEntity SET ViewName = N'View_Kalkti' WHERE EntityName = N'Material'"))
    job = pull(client, setup, entities=["Material", "Stock"])
    run(db_engine, job)
    data = result(client, setup, job)
    assert table_of(data, "Material")["status"] == "Hata" and "View bulunamadı" in table_of(data, "Material")["reason"]
    assert table_of(data, "Stock")["status"] == "Alındı" and data["status"] == "Bitti"


def test_transient_error_is_retried_three_times(setup, client, db_engine, monkeypatch):
    calls = []

    def fails(self, view, columns):
        calls.append(view)
        raise DBAPIError("SELECT", {}, Exception("zaman aşımı"))

    monkeypatch.setattr(Source, "read_rows", fails)
    table = pull_one(db_engine, client, setup)
    assert len(calls) == 3 and table["status"] == "Hata" and [a["attempt"] for a in table["attempts"]] == [1, 2, 3]
    assert "zaman aşımı" not in json.dumps(table)  # sürücü metni kullanıcıya gitmez
    assert {b["Status"] for b in batches(db_engine)} == {"Tamamlanmadı"} and stg_count(db_engine) == 0


def test_transient_error_recovers(setup, client, db_engine, monkeypatch):
    original = Source.read_rows
    calls = []

    def once(self, view, columns):
        calls.append(view)
        if len(calls) == 1:
            raise DBAPIError("SELECT", {}, Exception("kopma"))
        return original(self, view, columns)

    monkeypatch.setattr(Source, "read_rows", once)
    table = pull_one(db_engine, client, setup)
    assert table["status"] == "Alındı" and len(table["attempts"]) == 1 and stg_count(db_engine) == 212


def test_empty_view_is_failed(setup, client, db_engine):
    run_sql("CREATE VIEW dbo.View_StockBos AS SELECT * FROM dbo.ERP_Stock WHERE 1 = 0")
    try:
        use_sql(client, setup, "Stock", "View_StockBos")
        job = pull(client, setup, entities=["Stock"])
        run(db_engine, job)
        table = table_of(result(client, setup, job), "Stock")
        assert table["status"] == "Hatalı" and table["read"] == 0 and "satır vermedi" in table["reason"]
    finally:
        run_sql("DROP VIEW dbo.View_StockBos")


def test_crash_leaves_batch_incomplete_and_retry_is_clean(setup, client, db_engine):
    job = pull(client, setup, entities=["Material"])
    with Session(db_engine) as s:
        attempt = queue.claim_next(s, CHANNEL_PULL, JobSettings())["Attempt"]
    with db_engine.begin() as c:  # süreç okurken düşmüş gibi
        batch = c.execute(sa.text("INSERT INTO adm.ImportBatch (Method, EntityName, LoadType, ReceivedAt, Status, JobId, SourceObject) OUTPUT inserted.Id "
                                  "VALUES (N'SQL', N'Material', N'Tam', SYSUTCDATETIME(), N'Ön kontrol', :j, N'View_Material')"), {"j": job}).scalar()
        c.execute(sa.text("INSERT INTO stg.Material (ImportBatchId, Code) VALUES (:b, N'YARIM')"), {"b": batch})
    run_pull_job(job, attempt)
    with db_engine.connect() as c:
        assert c.execute(sa.text("SELECT COUNT(*) FROM stg.Material WHERE Code = N'YARIM'")).scalar() == 0
        assert c.execute(sa.text("SELECT Status FROM adm.ImportBatch WHERE Id = :b"), {"b": batch}).scalar() == "Tamamlanmadı"
    assert stg_count(db_engine) == 212


def test_dismissed_notification_stays_closed(setup, client, db_engine):
    """K-132: kapatma işte saklanır, yeniden girişte de görünür; başkası kapatamaz."""
    job = pull(client, setup, entities=["Material"])
    run(db_engine, job)
    own = auth(setup[KEY_USER])
    assert next(j for j in client.get("/api/jobs", headers=own).json()["jobs"] if j["id"] == job)["dismissed"] is False
    assert client.post(f"/api/jobs/{job}/dismiss", headers=auth(setup[ADMIN])).status_code == 403
    assert client.post(f"/api/jobs/{job}/dismiss", headers=own).status_code == 204
    assert next(j for j in client.get("/api/jobs", headers=auth(setup[KEY_USER], fresh=True)).json()["jobs"] if j["id"] == job)["dismissed"] is True
    assert client.post("/api/jobs/999999/dismiss", headers=own).status_code == 404


def test_unknown_job_is_404(setup, client):
    assert client.get("/api/pulls/999999", headers=auth(setup[KEY_USER])).status_code == 404


# --- Excel yöntemden bağımsız (K-130) ---

def xlsx(table="Material", rows=None) -> bytes:
    buffer = io.BytesIO()
    write_template(buffer, contract.entity(table), None, rows=rows or [{"LocationCode": "ORM-01", "Code": "E-1", "Name": "Ad", "BaseUom": "ADET"}])
    return buffer.getvalue()


def upload(client, user, table="Material"):
    return client.post(f"/api/imports/{table}?mode=Tam", content=xlsx(table), headers={**auth(user), "X-File-Name": "m.xlsx"})


def test_excel_upload_works_on_sql_table(setup, client, db_engine):
    r = upload(client, setup[KEY_USER])
    assert r.status_code == 200, r.text
    assert batches(db_engine)[-1]["Method"] == "Excel" and r.json()["valid"] == 1


def test_excel_upload_works_when_pull_is_off(setup, client, db_engine):
    save(client, auth(setup[ADMIN]), "Material", pull_enabled=False, reason="Sayım")
    assert upload(client, setup[KEY_USER]).status_code == 200
    table = pull_one(db_engine, client, setup)
    assert table["status"] == "Atlandı" and table["reason"] == "Çekim kapalı"  # anahtar yalnız SQL çekimini durdurur


def test_pull_switch_is_usable_on_excel_table(integration_db, people, client):  # noqa: F811
    r = save(client, auth(people[ADMIN]), "Resource", pull_enabled=False, reason="Kapalı")
    assert r.status_code == 200
    assert upload(client, people[KEY_USER], "Resource").status_code == 200


def test_method_change_leaves_open_precheck_alone(integration_db, people, client):  # noqa: F811
    r = upload(client, people[KEY_USER])
    batch = r.json()["batch_id"]
    save(client, auth(people[SYSTEM_OWNER]), "Material", method="SQL")
    assert client.get(f"/api/imports/{batch}", headers=auth(people[KEY_USER])).json()["status"] == "Ön kontrol"
    assert client.get("/api/imports/pending/Material", headers=auth(people[KEY_USER])).json()["batch_id"] == batch


def test_pull_leaves_open_precheck_alone(setup, client, db_engine):
    batch = upload(client, setup[KEY_USER]).json()["batch_id"]
    pull_one(db_engine, client, setup)
    assert client.get(f"/api/imports/{batch}", headers=auth(setup[KEY_USER])).json()["status"] == "Ön kontrol"
    with db_engine.connect() as c:
        assert c.execute(sa.text("SELECT COUNT(*) FROM stg.Material WHERE ImportBatchId = :b"), {"b": batch}).scalar() == 1


def test_sql_batch_is_not_an_open_precheck(setup, client, db_engine, monkeypatch):
    """Okunan SQL partisi Excel penceresine düşmez, yeni Excel yüklemesi onu kapatmaz."""
    seen = {}
    original = Source.signal

    def spy(self, table):
        if "pending" not in seen and batches(db_engine):
            seen["pending"] = client.get("/api/imports/pending/Material", headers=auth(setup[KEY_USER])).json()
        return original(self, table)

    monkeypatch.setattr(Source, "signal", spy)
    pull_one(db_engine, client, setup)
    assert seen["pending"] is None
    sql_batch = batches(db_engine)[0]
    assert client.get(f"/api/imports/{sql_batch['Id']}", headers=auth(setup[KEY_USER])).status_code == 404  # Excel uçları SQL partisini görmez
    upload(client, setup[KEY_USER])
    assert batches(db_engine)[0]["Status"] == "Alındı"


def test_last_load_time_covers_sql(setup, client, db_engine):
    pull_one(db_engine, client, setup)
    rows = client.post("/api/data-entities/query", json={"limit": 50}, headers=auth(setup[KEY_USER])).json()["rows"]
    assert next(x for x in rows if x["Entity"] == "Material")["LastLoadAt"]


def test_contract_change_asks_for_recheck(setup, client, db_engine):
    with db_engine.begin() as c:
        c.execute(sa.text("UPDATE adm.IntegrationEntity SET LastContractHash = N'eski' WHERE EntityName = N'Material'"))
    rows = client.post("/api/data-entities/query", json={"limit": 50}, headers=auth(setup[KEY_USER])).json()["rows"]
    assert next(x for x in rows if x["Entity"] == "Material")["Warning"] == "Yeniden denetle"
    client.post("/api/integration/test", json={}, headers=auth(setup[ADMIN]))
    rows = client.post("/api/data-entities/query", json={"limit": 50}, headers=auth(setup[KEY_USER])).json()["rows"]
    assert next(x for x in rows if x["Entity"] == "Material")["Warning"] is None


def test_channel_appears_in_job_filter(integration_db, people, client):  # noqa: F811
    columns = client.get("/api/job-queue/columns", headers=auth(people[ADMIN])).json()["columns"]
    assert "Veri çekme" in next(c for c in columns if c["field"] == "Channel")["values"]
    assert "Veri çekme" in next(c for c in columns if c["field"] == "JobType")["values"]
