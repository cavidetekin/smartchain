"""Staging'in güncel hâli ve doğrulama zinciri (K-133, K-134): Tam ve Ekle / güncelle, ön kontrolde düşen satır, ilişkili tablo,
"Karşılaştırılacak veri yok", satır işareti, iş düşünce Valide edilemedi, toplu çekimin tablolar arası işi."""
import io

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.main import create_app
from app.api.permissions import KEY_USER
from app.integration import contract
from app.integration.template import write_template
from app.jobs import queue
from app.jobs.constants import CHANNEL_PROCESSING, TYPE_PULL
from app.jobs.settings import JobSettings
from app.validation import engine

from auth_helpers import auth, ensure_user
from validation_helpers import clean, run_validations

pytestmark = pytest.mark.db

USER = "pytest.zincir.key"


def xlsx(entity: str, rows) -> bytes:
    buffer = io.BytesIO()
    write_template(buffer, contract.entity(entity), None, rows=rows)
    return buffer.getvalue()


def resource(code: str, **extra) -> dict:
    return {"LocationCode": "ORM-01", "Code": code, "Name": f"Ad {code}", "IsMachine": 1, "CapacityUnit": "SAAT", "IsActive": 1, "IsCritical": 1, **extra}


def material(code: str, **extra) -> dict:
    return {"LocationCode": "ORM-01", "Code": code, "BaseUom": "ADET", "IsActive": 1, "DefaultSupplyType": "Satın alma", "IsPurchasable": 1, **extra}


@pytest.fixture
def env(db_engine):
    clean(db_engine)
    with db_engine.begin() as c:
        user = ensure_user(c, USER, KEY_USER, "Ad")
    yield TestClient(create_app(), raise_server_exceptions=False), user, db_engine
    clean(db_engine)


def load(env, entity: str, rows, mode: str = "Tam") -> int:
    client, user, _ = env
    r = client.post(f"/api/imports/{entity}?mode={mode}", content=xlsx(entity, rows), headers={**auth(user), "X-File-Name": f"{entity}.xlsx"})
    assert r.status_code == 200, r.text
    batch = r.json()["batch_id"]
    assert client.post(f"/api/imports/{batch}/continue", headers=auth(user)).status_code == 200
    return batch


def current_codes(engine, entity: str, field: str = "Code") -> dict:
    with engine.connect() as c:
        return dict(c.execute(sa.text(f"SELECT [{field}], Name FROM stg.[{entity}] WHERE IsCurrent = 1")).all())


def findings(engine, entity: str | None = None) -> list[tuple]:
    with engine.connect() as c:
        q = "SELECT f.EntityName, r.Code, f.RowKey, f.Severity, f.Message FROM adm.ValidationFinding f JOIN adm.ValidationRule r ON r.Id = f.ValidationRuleId"
        rows = c.execute(sa.text(q + (" WHERE f.EntityName = :e" if entity else "")), {"e": entity}).all()
    return sorted(tuple(r) for r in rows)


def test_full_replaces_and_changed_merges(env):
    engine = env[2]
    load(env, "Resource", [resource("A"), resource("B")])
    load(env, "Resource", [resource("B", Name="Yeni B"), resource("C")], mode="Değişen")
    assert current_codes(engine, "Resource") == {"A": "Ad A", "B": "Yeni B", "C": "Ad C"}
    load(env, "Resource", [resource("C"), resource("D")])  # Tam: A ve B silinmiş sayılır
    assert current_codes(engine, "Resource") == {"C": "Ad C", "D": "Ad D"}
    with engine.connect() as c:
        assert c.execute(sa.text("SELECT COUNT(*) FROM stg.Resource")).scalar() == 6  # eski satırlar tarihçede (K-133)


def test_full_keeps_row_whose_new_line_was_rejected(env):
    engine = env[2]
    load(env, "Resource", [resource("A"), resource("B")])
    load(env, "Resource", [resource("A"), resource("B", IsMachine="belki")])  # B ön kontrolde düşer: silinmiş sayılmaz
    assert set(current_codes(engine, "Resource")) == {"A", "B"}


def test_chain_writes_findings_marks_rows_and_counts(env):
    client, user, engine = env
    load(env, "Resource", [resource("A"), resource("B", IsEmployee=1), resource("C", CapacityUnit=None)])
    with engine.connect() as c:
        state = c.execute(sa.text("SELECT TOP 1 State FROM adm.ValidationRun WHERE EntityName = N'Resource' ORDER BY Id DESC")).scalar()
    assert state == engine_state_queued()
    assert run_validations(engine)
    found = findings(engine, "Resource")
    assert ("Resource", "RES.TYPE_FLAGS", "ORM-01 · B", "Uyarı", "Kaynağın tek bir tipi olmalı.") in found
    assert ("Resource", "STR.REQUIRED", "ORM-01 · C", "Hata", "Zorunlu alan boş.") in found  # kapasite birimi kurallardan sonra boş (K-117)
    with engine.connect() as c:
        status = dict(c.execute(sa.text("SELECT Code, RowStatus FROM stg.Resource WHERE IsCurrent = 1")).all())
    assert status == {"A": "Yeni", "B": "Yeni", "C": "Hatalı"}
    s = client.get("/api/validation/Resource", headers=auth(user)).json()
    assert (s["state"], s["outcome"], s["current_rows"], s["error_rows"], s["warning_rows"]) == ("Bitti", "Hatalı", 3, 1, 1)
    assert round(s["error_rate"], 2) == 33.33 and s["threshold"] is None and s["batch"]["method"] == "Excel"
    assert {(r["name"], r["severity"], r["rows"]) for r in s["rules"]} >= {("Zorunlu alan boş", "Hata", 1), ("Kaynak tipi tek değil", "Uyarı", 1)}
    assert "by_check_type" not in s
    rows = client.post("/api/data-entities/query", json={"fields": ["Name", "Validation"], "filters": [], "offset": 0, "limit": 50}, headers=auth(user)).json()["rows"]
    chip = next(r for r in rows if r["Entity"] == "Resource")
    assert (chip["Validation"], chip["ValidationErrors"], chip["ValidationWarnings"]) == ("Hatalı", 1, 1)


def engine_state_queued() -> str:
    return engine.QUEUED


def test_related_table_refreshes_cross_rule_on_the_other_table(env):
    """Malzeme yüklenince Stok'taki IsNonStockable kontrolü yenilenir, bulgu Stok'a yazılır (K-134)."""
    _, _, eng = env
    stock = {"LocationCode": "ORM-01", "MaterialCode": "M-1", "Warehouse": "ANA", "Quantity": 5, "IsAvailable": 1, "IsActive": 1}
    load(env, "Stock", [stock])
    run_validations(eng)
    assert [f for f in findings(eng, "Stock") if f[1] == "STK.NON_STOCKABLE"] == [
        ("Stock", "STK.NON_STOCKABLE", None, "Bilgi", "Karşılaştırılacak veri yok: Malzeme.")]
    load(env, "Material", [material("M-1", IsNonStockable=1)])
    run_validations(eng)
    hit = [f for f in findings(eng, "Stock") if f[1] == "STK.NON_STOCKABLE"]
    assert len(hit) == 1 and hit[0][3] == "Uyarı" and hit[0][2].startswith("ORM-01 · M-1")
    load(env, "Material", [material("M-1", IsNonStockable=0)], mode="Değişen")
    run_validations(eng)
    assert not [f for f in findings(eng, "Stock") if f[1] == "STK.NON_STOCKABLE"]


def test_inactive_rule_writes_nothing_and_user_rule_runs(env):
    client, user, eng = env
    load(env, "Resource", [resource("A", IsEmployee=1)])
    with Session(eng) as s:
        engine.sync_rules(s, force=True)
    with eng.begin() as c:
        c.execute(sa.text("UPDATE adm.ValidationRule SET IsActive = 0 WHERE EntityName = N'Resource' AND Code = N'RES.TYPE_FLAGS'"))
        rule = c.execute(sa.text("INSERT INTO adm.ValidationRule (EntityName, Code, Name, Kind, CheckType, Severity, Message, IsActive, IsCustomized) OUTPUT inserted.Id "
                                 "VALUES (N'Resource', N'KUL-1', N'Ad kontrolü', N'Kullanıcı', N'Mantıksal', N'Bilgi', N'Ad A ile başlıyor.', 1, 0)")).scalar_one()
        c.execute(sa.text("INSERT INTO adm.ValidationRuleCondition (ValidationRuleId, GroupNo, FieldName, Operator, Value) VALUES (:r, 1, N'Name', N'İle başlar', N'Ad A')"), {"r": rule})
    run_validations(eng)
    codes = {f[1] for f in findings(eng, "Resource")}
    assert "RES.TYPE_FLAGS" not in codes and "KUL-1" in codes


def test_failed_job_marks_run_and_keeps_old_findings(env, monkeypatch):
    client, user, eng = env
    load(env, "Resource", [resource("A", IsEmployee=1)])
    run_validations(eng)
    before = findings(eng, "Resource")
    assert client.post("/api/validation/Resource/revalidate", headers=auth(user)).status_code == 202
    assert client.post("/api/validation/Resource/revalidate", headers=auth(user)).status_code == 409  # sürüyor
    monkeypatch.setattr(engine, "run_table", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("düştü")))
    run_validations(eng)
    s = client.get("/api/validation/Resource", headers=auth(user)).json()
    assert s["state"] == engine.FAILED and findings(eng, "Resource") == before


def test_revalidate_without_data_is_refused(env):
    client, user, _ = env
    r = client.post("/api/validation/Customer/revalidate", headers=auth(user))
    assert r.status_code == 409 and r.json()["error"]["code"] == "validation_no_data"


def test_bulk_cross_job_starts_after_pull_and_all_tables(env):
    """Toplu çekim: tablo içi işler bitince ve çekim bitince tablolar arası iş bir kez sıraya girer (K-134)."""
    _, user, eng = env
    load(env, "Resource", [resource("A")])
    with Session(eng) as s:
        pull = queue.enqueue(s, TYPE_PULL, "Veri çekme", user, {"entities": []})
        job = engine.enqueue(s, "Resource", engine.SCOPE_TABLE, engine.TRIGGER_BULK, None, user, pull)
    with Session(eng) as s:
        assert engine.maybe_start_cross(s, pull) is None  # çekim sürüyor
        s.execute(sa.text("UPDATE adm.Job SET Status = N'Bitti' WHERE Id = :j"), {"j": pull})
        s.commit()
        assert engine.maybe_start_cross(s, pull) is None  # tablo işi sırada
    run_validations(eng)  # tablo işi biter, son çıkan tablolar arası işi başlatır ve o da koşar
    with eng.connect() as c:
        scopes = c.execute(sa.text("SELECT Scope, State FROM adm.ValidationRun WHERE GroupId = :g ORDER BY Id"), {"g": pull}).all()
    assert [tuple(r) for r in scopes] == [("Tablo içi", "Bitti"), ("Tablolar arası", "Bitti")]
    with Session(eng) as s:
        assert engine.maybe_start_cross(s, pull) is None  # bir kez
    assert job


def test_new_batch_drops_findings_of_rows_that_left(env):
    _, _, eng = env
    load(env, "Resource", [resource("A", IsEmployee=1)])
    run_validations(eng)
    assert findings(eng, "Resource")
    load(env, "Resource", [resource("B")])  # A güncel hâlden çıkar
    assert not [f for f in findings(eng, "Resource") if f[2] == "ORM-01 · A"]
