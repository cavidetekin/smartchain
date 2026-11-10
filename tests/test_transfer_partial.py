"""Kısmi aktarım (K-150, K-155): yalnız seçilen grupların tabloları yazılır; ana veri ve seçilmeyen gruplar dokunulmaz; seçilen grupta silme;
bağlı ana verisi mevcut veride olmayan satır bekler (mevcut hâli kalır); pasif ana veri mevcut veride aktifse satır aktarılır; Kısmi veri versiyonu.

Önce tam aktarım, sonra işlenmiş katmanda değişiklik ve kısmi aktarım; hepsi aynı oturumda, commit edilmez (test veritabanının sentetik core verisi
değişmez)."""
import json
import re
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.integration.contract import ENTITIES
from app.transfer import engine as transfer
from app.transfer.groups import GROUPS, UnknownGroup, group_tables

from test_transfer import SO, WO, core_rows, set_prc
from test_validation_references import put
from validation_helpers import clean

pytestmark = pytest.mark.db
ROOT = Path(__file__).resolve().parents[1]
L1 = "PL-1"


def mat(code, **extra):
    return {"LocationCode": L1, "Code": code, "Name": f"Ad {code}", "BaseUom": "ADET", "IsActive": 1, "DefaultSupplyType": "Satın alma", **extra}


def so(no, material, **extra):
    return {"LocationCode": L1, "OrderNo": no, "LineNo": 1, "LineItemNo": 0, "CustomerCode": "PC-1", "MaterialCode": material, "OpenQuantity": 5,
            "IsActive": 1, **SO, **extra}


STOCK = {"LocationCode": L1, "Warehouse": "ANA", "Uom": "ADET", "IsAvailable": 1, "IsInQuality": 0, "IsBlocked": 0, "IsCustomTracked": 0, "IsActive": 1}
DATA = {
    "Location": [{"Code": L1, "Name": "Kısmi 1", "IsFactory": 1, "IsActive": 1}],
    "Material": [mat("P-OK"), mat("P-PAS"), mat("P-LATE")],
    "Customer": [{"Code": "PC-1", "Name": "Müşteri", "IsActive": 1}],
    "SalesOrderLine": [so("PS-1", "P-OK"), so("PS-2", "P-OK"), so("PS-3", "P-LATE"), so("PS-4", "P-PAS"), so("PS-9", "P-OK")],
    "Stock": [{**STOCK, "MaterialCode": "P-OK", "Quantity": 3, "LotNo": "L1"},
              {**STOCK, "MaterialCode": "P-OK", "Quantity": 4, "LotNo": "L9", "SalesOrderNo": "PS-9", "SalesOrderLineNo": 1, "SalesOrderLineItemNo": 0}],
    "WorkOrder": [{"LocationCode": L1, "WorkOrderNo": "PW-1", "MaterialCode": "P-OK", **WO}],
}


@pytest.fixture(scope="module")
def staged(db_engine):
    clean(db_engine)
    put(db_engine, DATA)
    yield db_engine
    clean(db_engine)


@pytest.fixture
def s(staged):
    """Tam aktarım yapılmış oturum: P-LATE ve PS-9 o sırada Hatalı (mevcut veride yok)."""
    with Session(staged) as session:
        set_prc(session, "Material", "Code = N'P-LATE'", RowStatus="Hatalı")
        set_prc(session, "SalesOrderLine", "OrderNo = N'PS-9'", RowStatus="Hatalı")
        session.info["full"] = transfer.run_transfer(session, None)["data_version"]
        set_prc(session, "Material", "Code = N'P-LATE'", RowStatus="Yeni")      # gelen veride artık geçerli; kısmide aktarılmaz
        set_prc(session, "SalesOrderLine", "OrderNo = N'PS-9'", RowStatus="Yeni")
        yield session
        session.rollback()


def by_entity(result) -> dict:
    return {t["entity"]: t for t in result["tables"]}


def one(s, entity, where):
    rows = core_rows(s, entity, where)
    assert len(rows) == 1, (entity, where, rows)
    return rows[0]


def test_groups_match_docs():
    """docs/00 K-150 ile birebir; her işlem verisi tablosu tam bir grupta; Proje ve Proje grubu Talep'te (istisna)."""
    text = (ROOT / "docs" / "00-kararlar.md").read_text(encoding="utf-8")
    k150 = next(line for line in text.splitlines() if line.startswith("| K-150 |"))
    names = {e.name: e.table for e in ENTITIES}
    documented = {g: tuple(names[n.strip()] for n in tables.split(",")) for g, tables in re.findall(r"\*\*([^*]+)\*\* \(([^)]+)\)", k150)}
    assert {g: set(t) for g, t in documented.items()} == {g: set(t) for g, t in GROUPS.items()}
    tables = [t for ts in GROUPS.values() for t in ts]
    assert len(tables) == len(set(tables))
    transaction = {e.table for e in ENTITIES if e.data_class == "İşlem verisi"}
    assert set(tables) - transaction == {"Project", "ProjectGroup"} and transaction <= set(tables)
    with pytest.raises(UnknownGroup):
        group_tables(["Talep", "Yok"])


def test_partial_writes_only_selected_groups(s):
    full = s.info["full"]
    set_prc(s, "Material", "Code = N'P-OK'", Name="Yeni ad")
    set_prc(s, "SalesOrderLine", "OrderNo = N'PS-1'", OpenQuantity=7)
    set_prc(s, "Stock", "LotNo = N'L1'", Quantity=9)
    set_prc(s, "WorkOrder", "WorkOrderNo = N'PW-1'", OpenQuantity=2)
    r = transfer.run_transfer(s, None, groups=["Talep"])
    v, t = r["data_version"], by_entity(r)
    assert one(s, "SalesOrderLine", "OrderNo = N'PS-1'")["OpenQuantity"] == 7 and t["SalesOrderLine"]["changed"] >= 1
    assert one(s, "Material", "Code = N'P-OK'")["VersionFrom"] == full                       # ana veri aktarılmaz
    assert one(s, "Stock", "LotNo = N'L1'")["VersionFrom"] == full                           # seçilmeyen grup dokunulmaz
    assert one(s, "WorkOrder", "WorkOrderNo = N'PW-1'")["VersionFrom"] == full
    assert s.execute(sa.text("SELECT LoadType FROM adm.DataVersion WHERE Id = :v"), {"v": v}).scalar() == "Kısmi"
    entities = {e for e, in s.execute(sa.text("SELECT EntityName FROM adm.DataVersionEntity WHERE DataVersionId = :v"), {"v": v})}
    assert entities == set(GROUPS["Talep"]) and set(t) == set(GROUPS["Talep"])
    assert t["Forecast"]["note"] == transfer.NOTE_EMPTY


def test_partial_closes_missing_rows_in_selected_group(s):
    s.execute(sa.text("DELETE FROM prc.SalesOrderLine WHERE OrderNo = N'PS-2'"))
    s.execute(sa.text("DELETE FROM prc.Stock WHERE LotNo = N'L1'"))
    r = transfer.run_transfer(s, None, groups=["Talep"])
    assert not core_rows(s, "SalesOrderLine", "OrderNo = N'PS-2'") and by_entity(r)["SalesOrderLine"]["closed"] >= 1
    assert core_rows(s, "Stock", "LotNo = N'L1'")                                             # Stok seçilmedi: kalır


def test_waiting_row_keeps_existing_version(s):
    """P-LATE mevcut veride yok: yeni satır (PS-3) aktarılmaz; malzemesi P-LATE'e dönen PS-1'in mevcut hâli kalır."""
    full = s.info["full"]
    before = one(s, "SalesOrderLine", "OrderNo = N'PS-1'")
    set_prc(s, "SalesOrderLine", "OrderNo = N'PS-1'", MaterialCode="P-LATE", OpenQuantity=8)
    t = by_entity(transfer.run_transfer(s, None, groups=["Talep"]))
    assert not core_rows(s, "SalesOrderLine", "OrderNo = N'PS-3'")
    after = one(s, "SalesOrderLine", "OrderNo = N'PS-1'")
    assert (after["VersionFrom"], after["MaterialId"], after["OpenQuantity"]) == (full, before["MaterialId"], before["OpenQuantity"])
    assert t["SalesOrderLine"]["note"] == transfer.NOTE_WAITING.format(n=2) and t["SalesOrderLine"]["not_transferred"] == 2


def test_row_linked_to_unselected_group_waits(s):
    """PS-9 gelen veride geçerli ama Talep seçilmedi: ona bağlı stok bekler."""
    t = by_entity(transfer.run_transfer(s, None, groups=["Stok"]))
    assert not core_rows(s, "Stock", "LotNo = N'L9'") and core_rows(s, "Stock", "LotNo = N'L1'")
    assert t["Stock"]["note"] == transfer.NOTE_WAITING.format(n=1)


def test_inactive_master_in_incoming_data_still_active_in_existing(s):
    set_prc(s, "Material", "Code = N'P-PAS'", IsActive=0)
    set_prc(s, "SalesOrderLine", "OrderNo = N'PS-4'", OpenQuantity=6)
    transfer.run_transfer(s, None, groups=["Talep"])
    assert one(s, "SalesOrderLine", "OrderNo = N'PS-4'")["OpenQuantity"] == 6                # ana veri mevcut veride aktif: aktarılır
    assert core_rows(s, "Material", "Code = N'P-PAS'")
    transfer.run_transfer(s, None)                                                           # tam aktarımda ana veri ve ona bakan satır kapanır
    assert not core_rows(s, "Material", "Code = N'P-PAS'") and not core_rows(s, "SalesOrderLine", "OrderNo = N'PS-4'")


def test_full_after_partial_brings_waiting_rows(s):
    transfer.run_transfer(s, None, groups=["Talep", "Stok"])
    assert not core_rows(s, "SalesOrderLine", "OrderNo = N'PS-3'")
    transfer.run_transfer(s, None)
    assert core_rows(s, "SalesOrderLine", "OrderNo = N'PS-3'") and core_rows(s, "Stock", "LotNo = N'L9'")


# ------------------------------------------------------------------ API, yetki, iş

def test_partial_api_plan_start_and_permissions(db_engine):
    from app.api.permissions import END_USER, KEY_USER
    from auth_helpers import auth, ensure_user
    from validation_helpers import new_client

    clean(db_engine)
    put(db_engine, {"Stock": [{**STOCK, "MaterialCode": "P-OK", "Quantity": 1}]})
    with db_engine.begin() as c:
        key = ensure_user(c, "pytest.kismi.key", KEY_USER, "Ad")
        end = ensure_user(c, "pytest.kismi.end", END_USER, "Ad")
    client = new_client()
    try:
        body = client.get("/api/transfers/partial/plan", headers=auth(key)).json()
        assert [g["name"] for g in body["groups"]] == list(GROUPS) and body["busy"] is None and body["pending"] == ["Stock"]
        stok = next(g for g in body["groups"] if g["name"] == "Stok")
        assert [t["entity"] for t in stok["tables"]] == ["Stock", "BorrowPayback"] and stok["tables"][0]["status"] == "Aktarılır"
        r = client.post("/api/transfers/partial", json={"groups": ["Stok"]}, headers=auth(key))
        assert r.status_code == 409 and "Stok" in r.json()["error"]["message"]                     # validasyonu bitmemiş (yalnız seçilen)
        for groups in ([], ["Yok"]):
            r = client.post("/api/transfers/partial", json={"groups": groups}, headers=auth(key))
            assert r.status_code == 422 and r.json()["error"]["code"] == "transfer_groups"
        assert client.get("/api/transfers/partial/plan", headers=auth(end)).status_code == 403
        assert client.post("/api/transfers/partial", json={"groups": ["Talep"]}, headers=auth(end)).status_code == 403
        r = client.post("/api/transfers/partial", json={"groups": ["İzin", "Talep", "Talep"]}, headers=auth(key))   # Stok seçilmedi: engel yok
        assert r.status_code == 202
        with db_engine.connect() as c:
            job = c.execute(sa.text("SELECT Payload, Summary FROM adm.Job WHERE Id = :i"), {"i": r.json()["job_id"]}).one()
            audit_row = c.execute(sa.text("SELECT TOP 1 NewValue FROM adm.AuditLog WHERE Action = N'Kısmi aktarım' AND ObjectType = N'Job' ORDER BY Id DESC")).scalar()
        assert json.loads(job[0]) == {"user_id": key, "mode": "Kısmi", "groups": ["Talep", "İzin"]} and job[1] == "Kısmi veri aktarımı · Talep, İzin"
        assert json.loads(audit_row) == {"transfer_type": "Kısmi", "groups": "Talep, İzin"}
    finally:
        clean(db_engine)


def test_partial_job_writes_kismi_version_and_audit(db_engine):
    from app.engine.transfer_job import run_transfer_job
    from app.jobs import queue
    from app.jobs.constants import CHANNEL_PROCESSING, TYPE_TRANSFER
    from app.jobs.settings import JobSettings

    clean(db_engine)
    put(db_engine, {"Customer": [{"Code": "PJ-1", "Name": "Kısmi iş", "IsActive": 1}]})   # ana veri: kısmide aktarılmaz
    with Session(db_engine) as s:
        job_id = queue.enqueue(s, TYPE_TRANSFER, CHANNEL_PROCESSING, None, {"user_id": None, "mode": "Kısmi", "groups": ["İzin"]})
    with Session(db_engine) as s:
        job = queue.claim_next(s, CHANNEL_PROCESSING, JobSettings(limit_processing=10))
    assert job["Id"] == job_id
    run_transfer_job(job_id, job["Attempt"])
    with db_engine.connect() as c:
        status, progress, result = c.execute(sa.text("SELECT Status, Progress, Result FROM adm.Job WHERE Id = :i"), {"i": job_id}).one()
        version = json.loads(result)["data_version"]
        try:
            assert status == "Bitti" and progress == f"Kısmi veri aktarımı bitti · v{version}"
            assert c.execute(sa.text("SELECT LoadType FROM adm.DataVersion WHERE Id = :v"), {"v": version}).scalar() == "Kısmi"
            assert [e for e, in c.execute(sa.text("SELECT EntityName FROM adm.DataVersionEntity WHERE DataVersionId = :v"), {"v": version})] == ["EmployeeAbsence"]
            assert not c.execute(sa.text("SELECT COUNT(*) FROM core.Customer WHERE Code = N'PJ-1'")).scalar()
            audit_row = c.execute(sa.text("SELECT TOP 1 ObjectKey, NewValue FROM adm.AuditLog WHERE Action = N'Kısmi aktarım' AND ObjectType = N'DataVersion' "
                                          "ORDER BY Id DESC")).one()
            assert audit_row[0] == str(version) and json.loads(audit_row[1])["groups"] == "İzin"
        finally:
            c.execute(sa.text("DELETE FROM adm.DataVersionEntity WHERE DataVersionId = :v"), {"v": version})
            c.execute(sa.text("DELETE FROM adm.DataVersion WHERE Id = :v"), {"v": version})
            c.commit()
    clean(db_engine)
