"""Sonucun yazılması (K-70): tek commit, tekrar çalıştırmada çift kayıt yok, yayınlanmış plan değişmez."""
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.engine.fake import FakeEngine
from app.engine.interface import EngineInput, PlanRunInfo, ScenarioParameters
from app.engine.job import run_plan_job
from app.engine.submit import submit_plan_run
from app.engine.writer import JobNoLongerOwned, PlanRunPublished, write_result
from app.jobs import queue
from app.jobs.constants import CHANNEL_INTERACTIVE, STATUS_DONE, STATUS_FAILED

pytestmark = pytest.mark.db

OUTPUT_TABLES = ["planning.PlannedSupply", "planning.DemandFulfillment", "planning.PlannedOvertime", "planning.PlannedAllocationTransfer",
                 "planning.MaterialTransaction", "planning.CapacityLoad", "planning.Pegging", "planning.PlanWarning", "planning.PlanMetric",
                 "adm.SolverLog"]


def test_output_tables_are_listed_once():
    """Plan çıktı tabloları: yazıcının listesi ile temizliğin listesi aynı tabloları taşır (K-202); silme sırası bağlanan önce."""
    from app.data.cleanup import OUTPUT_TABLES as cleaned
    from app.engine.writer import OUTPUTS
    written = {t.name for _, t, _ in OUTPUTS}
    assert written | {"PlannedDemand", "PlanMetric"} == set(cleaned) and len(cleaned) == len(set(cleaned))
    assert {f"planning.{t}" for t in written} | {"planning.PlanMetric", "adm.SolverLog"} == set(OUTPUT_TABLES)
    order = {t: i for i, t in enumerate(cleaned)}
    assert order["Pegging"] < order["MaterialTransaction"] < order["DemandFulfillment"] < order["PlannedDemand"]
    assert order["CapacityLoad"] < order["PlannedSupply"] and order["MaterialTransaction"] < order["PlannedSupply"]


def counts(session, plan_run_id):
    return {t: session.execute(text(f"SELECT COUNT(*) FROM {t} WHERE PlanRunId = :id"), {"id": plan_run_id}).scalar()
            for t in OUTPUT_TABLES}


def submit_and_claim(session, env, job_settings):
    plan_run_id, job_id = submit_plan_run(session, data_version_id=env["data_version_id"],
                                          scenario_definition_id=env["scenario_definition_id"], requested_by=env["user_id"])
    job = queue.claim_next(session, CHANNEL_INTERACTIVE, job_settings)
    assert job["Id"] == job_id
    return plan_run_id, job


def fake_result():
    inp = EngineInput(PlanRunInfo(1, 1, 1), ScenarioParameters(1, "x", {}), None, 180)
    return FakeEngine().run(inp, lambda s: None)


def run_status(session, plan_run_id):
    return session.execute(text("SELECT Status, EngineUsed, Solver, StartedAt, EndedAt FROM planning.PlanRun "
                                "WHERE Id = :id"), {"id": plan_run_id}).first()


def test_job_writes_plan(db_session, plan_env, job_settings):
    plan_run_id, job = submit_and_claim(db_session, plan_env, job_settings)
    assert run_status(db_session, plan_run_id).Status == "Sırada"

    run_plan_job(job["Id"], job["Attempt"], 180)

    db_session.expire_all()
    c = counts(db_session, plan_run_id)
    # talep kopyası hesap başlarken kurulur; sahte motorun üç karşılama satırı ilk iki talebe oturur (talep yoksa satır yazılmaz)
    demands = db_session.execute(text("SELECT COUNT(*) FROM planning.PlannedDemand WHERE PlanRunId = :id AND IsIncluded = 1"), {"id": plan_run_id}).scalar()
    fulfilled = 3 if demands >= 2 else demands
    assert c == {"planning.PlannedSupply": 4, "planning.DemandFulfillment": fulfilled, "planning.PlannedOvertime": 1, "planning.PlannedAllocationTransfer": 1,
                 "planning.MaterialTransaction": 8, "planning.CapacityLoad": 2, "planning.Pegging": 3, "planning.PlanWarning": 2,
                 "planning.PlanMetric": 4, "adm.SolverLog": 1}
    if demands >= 2:   # kırılım satırına talebin kimliği kopyalanır; özet kırılımdan yazılır
        rows = db_session.execute(text(
            "SELECT d.DemandType, f.DemandType, d.MaterialId, f.MaterialId, d.DemandQuantity, d.FulfilledQuantity, d.OnTimeQuantity, d.LateQuantity, d.UnmetQuantity, "
            "d.FulfillmentPct, (SELECT SUM(x.Quantity) FROM planning.DemandFulfillment x WHERE x.PlannedDemandId = d.Id) "
            "FROM planning.DemandFulfillment f JOIN planning.PlannedDemand d ON d.Id = f.PlannedDemandId WHERE f.PlanRunId = :id ORDER BY f.Id"), {"id": plan_run_id}).all()
        assert all(r[0] == r[1] and r[2] == r[3] and r[5] == r[10] and r[6] + r[7] == r[5] and r[8] == r[4] - r[5] for r in rows)
        assert [float(r[9]) for r in rows] == [100.0, 85.0, 85.0]
        untouched = db_session.execute(text("SELECT COUNT(*) FROM planning.PlannedDemand WHERE PlanRunId = :id AND IsIncluded = 1 AND FulfilledQuantity = 0 "
                                            "AND UnmetQuantity = DemandQuantity"), {"id": plan_run_id}).scalar()
        assert untouched == demands - 2                                                         # karşılanmayan talep: tamamı karşılanmadı
    run = run_status(db_session, plan_run_id)
    assert (run.Status, run.EngineUsed, run.Solver) == ("Bitti", "LP", "Sahte") and run.StartedAt and run.EndedAt
    j = queue.get_job(db_session, job["Id"], job_settings)
    assert j["Status"] == STATUS_DONE and j["Progress"] == "Tamamlandı"

    p = {"id": plan_run_id}
    # tedarik planı numarası: plan kaydına sistem verir (türüne göre sıra), sipariş kaydında motorun yazdığı kalır
    supply = db_session.execute(text("SELECT SupplyNo, SupplyType, Source, IsSubcontract, IsIncluded, IsManual, IsFixed FROM planning.PlannedSupply "
                                     "WHERE PlanRunId = :id ORDER BY Id"), p).all()
    assert [tuple(r) for r in supply] == [("ÜP-000001", "Üretim", "Plan", False, True, False, False), ("SP-000001", "Satın alma", "Plan", False, True, False, False),
                                          ("ÜP-000002", "Üretim", "Plan", True, True, False, False), ("ÜS-3001", "Üretim", "Sipariş", False, True, False, False)]
    # bağlar bu hesabın satırlarına gider; hareketin no'su tedarik planı kaydından
    # talep hareketinin no'su satış sipariş no'dur (karşılama satırından); tahminde, stokta ve alokasyon transferinde boş kalır
    order_no = db_session.execute(text("SELECT TOP 1 f.OrderNo FROM planning.DemandFulfillment f WHERE f.PlanRunId = :id ORDER BY f.Id"), p).scalar()
    assert order_no or not demands
    moves = db_session.execute(text("SELECT t.MovementType, t.Direction, t.DocumentNo, s.SupplyNo FROM planning.MaterialTransaction t "
                                    "LEFT JOIN planning.PlannedSupply s ON s.Id = t.PlannedSupplyId AND s.PlanRunId = t.PlanRunId WHERE t.PlanRunId = :id ORDER BY t.Id"), p).all()
    assert [tuple(r) for r in moves] == [("Üretim planı", "+", "ÜP-000001", "ÜP-000001"), ("Üretim planı ihtiyacı", "-", "ÜP-000001", "ÜP-000001"),
                                         ("Satın alma planı", "+", "SP-000001", "SP-000001"), ("Kesin sipariş", "-", order_no, None), ("Stok", "+", None, None),
                                         ("Alokasyon transferi", "-", None, None), ("Alokasyon transferi", "+", None, None), ("Üretim siparişi", "+", "ÜS-3001", "ÜS-3001")]
    loads = db_session.execute(text("SELECT s.SupplyNo, l.CapacityUsage FROM planning.CapacityLoad l JOIN planning.PlannedSupply s ON s.Id = l.PlannedSupplyId "
                                    "WHERE l.PlanRunId = :id ORDER BY l.Id"), p).all()
    assert [(r[0], float(r[1])) for r in loads] == [("ÜP-000001", 60.0), ("ÜS-3001", 30.0)]
    # pegging: iki hareket bağı, üst bağ ve iki tarafın satıra kopyalanan alanları
    peg = db_session.execute(text(
        "SELECT g.[Level], g.SupplyMovementType, g.SupplyDocumentNo, g.DemandMovementType, g.DemandDocumentNo, g.SupplyAllocationKey, g.IsFromGeneral, "
        "CASE WHEN up.Id IS NULL THEN 0 ELSE 1 END, a.MovementType, b.MovementType, g.SupplyPeriodStart, a.PeriodStart, g.PlannedDemandId, g.RootDemandType "
        "FROM planning.Pegging g JOIN planning.MaterialTransaction a ON a.Id = g.SupplyTransactionId JOIN planning.MaterialTransaction b ON b.Id = g.DemandTransactionId "
        "LEFT JOIN planning.Pegging up ON up.Id = g.ParentPeggingId WHERE g.PlanRunId = :id ORDER BY g.Id"), p).all()
    # pegging gerçek arzı gösterir: genelden karşılanan miktarın arzı Stok hareketidir (Genelden = Evet); transfer hareketi pegging'e girmez
    assert [tuple(r[:8]) for r in peg] == [(0, "Üretim planı", "ÜP-000001", "Kesin sipariş", order_no, None, False, 0),
                                           (1, "Satın alma planı", "SP-000001", "Üretim planı ihtiyacı", "ÜP-000001", None, False, 1),
                                           (1, "Stok", None, "Üretim planı ihtiyacı", "ÜP-000001", None, True, 1)]
    assert all(r[1] == r[8] and r[3] == r[9] and r[10] == r[11] and (r[12] is None) == (demands == 0) and (r[13] is None) == (demands == 0) for r in peg)


def test_rerun_unpublished_replaces_outputs(db_session, plan_env, job_settings):
    plan_run_id, job = submit_and_claim(db_session, plan_env, job_settings)
    run_plan_job(job["Id"], job["Attempt"], 180)
    first = counts(db_session, plan_run_id)
    # Aynı PlanRun yeni bir işle tekrar hesaplanır (ör. iş geri alınıp yeniden çalıştı).
    job2_id = queue.enqueue(db_session, "Çalışma", CHANNEL_INTERACTIVE, plan_env["user_id"],
                            {"plan_run_id": plan_run_id})
    job2 = queue.claim_next(db_session, CHANNEL_INTERACTIVE, job_settings)
    assert job2["Id"] == job2_id
    run_plan_job(job2["Id"], job2["Attempt"], 180)
    db_session.expire_all()
    assert counts(db_session, plan_run_id) == first


def test_nothing_written_when_job_no_longer_owned(db_session, plan_env, job_settings):
    plan_run_id, job = submit_and_claim(db_session, plan_env, job_settings)
    with pytest.raises(JobNoLongerOwned):
        write_result(db_session, plan_run_id, fake_result(), job["Id"], job["Attempt"] + 1)
    assert set(counts(db_session, plan_run_id).values()) == {0}
    assert run_status(db_session, plan_run_id).Status == "Sırada"


def test_unknown_link_rolls_back(db_session, plan_env, job_settings):
    plan_run_id, job = submit_and_claim(db_session, plan_env, job_settings)
    result = fake_result()
    result.pegging[0]["demand_ref"] = "YOK"
    with pytest.raises(ValueError, match="bilinmeyen bağ demand_ref = YOK"):
        write_result(db_session, plan_run_id, result, job["Id"], job["Attempt"])
    result = fake_result()
    result.pegging[2]["supply_ref"] = "T7"                                                    # alokasyon transferi hareketi
    with pytest.raises(ValueError, match="transfer hareketi bağlanamaz"):
        write_result(db_session, plan_run_id, result, job["Id"], job["Attempt"])
    result = fake_result()
    result.demand_fulfillment.append({"PlannedDemandId": -1, "PeriodStart": "2026-12-07", "PeriodEnd": "2026-12-13", "Quantity": 1, "IsTardy": False})
    with pytest.raises(ValueError, match="bu plan hesabında olmayan talep"):
        write_result(db_session, plan_run_id, result, job["Id"], job["Attempt"])
    assert set(counts(db_session, plan_run_id).values()) == {0}


def test_unknown_column_rolls_back(db_session, plan_env, job_settings):
    plan_run_id, job = submit_and_claim(db_session, plan_env, job_settings)
    result = fake_result()
    result.capacity_loads[0]["Utilisation"] = 1
    with pytest.raises(ValueError, match="bilinmeyen alan Utilisation"):
        write_result(db_session, plan_run_id, result, job["Id"], job["Attempt"])
    assert set(counts(db_session, plan_run_id).values()) == {0}
    assert queue.get_job(db_session, job["Id"], job_settings)["Status"] == "Çalışıyor"


def publish(session, env, plan_run_id):
    p = {"l": env["location_id"], "dv": env["data_version_id"], "u": env["user_id"], "pr": plan_run_id}
    sd = session.execute(text("INSERT INTO param.ScenarioDefinition (LocationId, Name, IsBase, IsActive, IsSynthetic) "
                              "OUTPUT inserted.Id VALUES (:l, N'Motor testi', 0, 0, 1)"), p).scalar_one()
    sc = session.execute(text("INSERT INTO planning.Scenario (ScenarioDefinitionId, DataVersionId) "
                              "OUTPUT inserted.Id VALUES (:sd, :dv)"), {**p, "sd": sd}).scalar_one()
    ws = session.execute(text("INSERT INTO planning.Workspace (ScenarioId, OwnerUserId, Status) "
                              "OUTPUT inserted.Id VALUES (:sc, :u, N'Yayınlandı')"), {**p, "sc": sc}).scalar_one()
    session.execute(text("INSERT INTO planning.PlanVersion (LocationId, PlanRunId, WorkspaceId, PublishedBy, "
                         "PublishedAt, IsCurrent) VALUES (:l, :pr, :ws, :u, SYSUTCDATETIME(), 0)"), {**p, "ws": ws})
    session.commit()


def test_published_plan_run_is_immutable(db_session, plan_env, job_settings):
    plan_run_id, job = submit_and_claim(db_session, plan_env, job_settings)
    run_plan_job(job["Id"], job["Attempt"], 180)
    before = counts(db_session, plan_run_id)
    publish(db_session, plan_env, plan_run_id)

    job2_id = queue.enqueue(db_session, "Çalışma", CHANNEL_INTERACTIVE, plan_env["user_id"],
                            {"plan_run_id": plan_run_id})
    job2 = queue.claim_next(db_session, CHANNEL_INTERACTIVE, job_settings)
    with pytest.raises(PlanRunPublished):
        write_result(db_session, plan_run_id, fake_result(), job2["Id"], job2["Attempt"])

    run_plan_job(job2["Id"], job2["Attempt"], 180)
    db_session.expire_all()
    j = queue.get_job(db_session, job2_id, job_settings)
    assert j["Status"] == STATUS_FAILED and "yayınlanmış" in j["ErrorText"]
    assert counts(db_session, plan_run_id) == before
    assert run_status(db_session, plan_run_id).Status == "Bitti"


def test_missing_plan_run_id_fails_job(db_session, plan_env, job_settings):
    queue.enqueue(db_session, "Çalışma", CHANNEL_INTERACTIVE, plan_env["user_id"], {"başka": 1})
    job = queue.claim_next(db_session, CHANNEL_INTERACTIVE, job_settings)
    run_plan_job(job["Id"], job["Attempt"], 180)
    with Session(db_session.get_bind()) as s:
        j = queue.get_job(s, job["Id"], job_settings)
    assert j["Status"] == STATUS_FAILED and "plan_run_id" in j["ErrorText"]
