"""Sonucun yazılması (K-70, K-205): tek commit, tekrar çalıştırmada çift kayıt yok, yayınlanmış plan değişmez; sahte motor sentetik Baz'da fikstür planını
yazar (türetme, pegging eşlemesi, uyarı, metrik, tutarlılık denetimi); bilinmeyen alan ve eşleşmeyen hareket anahtarı hiçbir şey yazdırmaz."""
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.data.cleanup import OUTPUT_TABLES as CLEANED, delete_runs
from app.data.synthetic import dataset as d
from app.engine.fake import FakeEngine
from app.engine.interface import EngineInput, PlanResult, PlanRunInfo, ScenarioParameters
from app.engine.job import run_plan_job
from app.engine.submit import submit_plan_run
from app.engine.writer import OUTPUTS, JobNoLongerOwned, PlanRunPublished, write_result
from app.jobs import queue
from app.jobs.constants import CHANNEL_INTERACTIVE, STATUS_DONE, STATUS_FAILED
from app.periods import cache
from app.planning import checks

pytestmark = pytest.mark.db

OUTPUT_TABLES = ["planning.PlannedSupply", "planning.DemandFulfillment", "planning.PlannedOvertime", "planning.PlannedAllocationTransfer",
                 "planning.MaterialTransaction", "planning.CapacityLoad", "planning.Pegging", "planning.PlanWarning", "planning.PlanMetric",
                 "adm.SolverLog"]


def test_output_tables_are_listed_once():
    """Plan çıktı tabloları: yazıcının listesi ile temizliğin listesi aynı tabloları taşır (K-202); silme sırası bağlanan önce."""
    written = {t.name for _, t in OUTPUTS}
    assert written | {"PlannedDemand", "PlanMetric"} == set(CLEANED) and len(CLEANED) == len(set(CLEANED))
    assert {f"planning.{t}" for t in written} | {"planning.PlanMetric", "adm.SolverLog"} == set(OUTPUT_TABLES)
    order = {t: i for i, t in enumerate(CLEANED)}
    assert order["Pegging"] < order["MaterialTransaction"] < order["DemandFulfillment"] < order["PlannedDemand"]
    assert order["CapacityLoad"] < order["PlannedSupply"] and order["MaterialTransaction"] < order["PlannedSupply"]
    assert [a for a, _ in OUTPUTS if a is None] == [None, None]                       # hareket ve yük motor sonucunda değil, türetilir (K-205)


def counts(session, plan_run_id):
    return {t: session.execute(text(f"SELECT COUNT(*) FROM {t} WHERE PlanRunId = :id"), {"id": plan_run_id}).scalar()
            for t in OUTPUT_TABLES}


def claim(session, job_id, job_settings):
    job = queue.claim_next(session, CHANNEL_INTERACTIVE, job_settings)
    assert job["Id"] == job_id
    return job


def submit_and_claim(session, env, job_settings):
    """Motor testlerinin kendi veri versiyonu ve senaryosu: sahte motor boş plan döner."""
    plan_run_id, job_id = submit_plan_run(session, data_version_id=env["data_version_id"],
                                          scenario_definition_id=env["scenario_definition_id"], requested_by=env["user_id"])
    return plan_run_id, claim(session, job_id, job_settings)


@pytest.fixture
def baz(db_session, plan_env, job_settings):
    """Sentetik verinin veri versiyonunda Baz senaryo: sahte motor fikstürün "Baz · güncel" planını yazar. Test sonunda plan hesabı silinir."""
    version = db_session.execute(text("SELECT MAX(v.Id) FROM adm.DataVersion v JOIN core.Location l ON l.Id = v.LocationId AND l.Code = :c "
                                      "WHERE v.IsSynthetic = 1"), {"c": d.LOCATION_CODE}).scalar()
    assert version, "test veritabanında sentetik veri bekleniyor"
    runs = []

    def submit():
        plan_run_id, job_id = submit_plan_run(db_session, data_version_id=version, scenario_definition_id=cache.base_id(db_session), requested_by=plan_env["user_id"])
        runs.append(plan_run_id)
        return plan_run_id, claim(db_session, job_id, job_settings)
    yield submit
    db_session.rollback()
    with db_session.get_bind().begin() as c:
        delete_runs(c, runs)


def fake_result():
    inp = EngineInput(PlanRunInfo(1, 1, 1), ScenarioParameters(1, "x", {}), None, 180)
    return FakeEngine().run(inp, lambda s: None)


def run_status(session, plan_run_id):
    return session.execute(text("SELECT Status, EngineUsed, Solver, StartedAt, EndedAt FROM planning.PlanRun "
                                "WHERE Id = :id"), {"id": plan_run_id}).first()


def test_job_writes_fixture_plan(db_session, baz, job_settings):
    plan_run_id, job = baz()
    assert run_status(db_session, plan_run_id).Status == "Sırada"
    run_plan_job(job["Id"], job["Attempt"], 180)
    db_session.expire_all()
    c = counts(db_session, plan_run_id)
    assert all(c[t] > 0 for t in OUTPUT_TABLES), c
    run = run_status(db_session, plan_run_id)
    assert (run.Status, run.EngineUsed, run.Solver) == ("Bitti", "LP", "Sahte") and run.StartedAt and run.EndedAt
    j = queue.get_job(db_session, job["Id"], job_settings)
    assert j["Status"] == STATUS_DONE and j["Progress"] == "Tamamlandı"
    assert checks.problems(db_session, plan_run_id) == []
    # tedarik planı numarası: plan kaydına sistem verir (türüne göre sıra), sipariş kaydında sipariş no
    nos = [r[0] for r in db_session.execute(text("SELECT SupplyNo FROM planning.PlannedSupply WHERE PlanRunId = :id AND Source = N'Plan' AND SupplyType = N'Üretim' "
                                                 "ORDER BY Id"), {"id": plan_run_id})]
    assert nos[:3] == ["ÜP-000001", "ÜP-000002", "ÜP-000003"]
    assert db_session.execute(text("SELECT COUNT(*) FROM planning.PlannedSupply WHERE PlanRunId = :id AND Source = N'Sipariş' AND SupplyNo NOT LIKE N'WO-%'"),
                              {"id": plan_run_id}).scalar() == 0
    # pegging'in iki tarafı ve kök talebi kopyalandı
    assert db_session.execute(text("SELECT COUNT(*) FROM planning.Pegging WHERE PlanRunId = :id AND (SupplyMovementType IS NULL OR DemandMovementType IS NULL)"),
                              {"id": plan_run_id}).scalar() == 0


def test_rerun_unpublished_replaces_outputs(db_session, baz, job_settings):
    plan_run_id, job = baz()
    run_plan_job(job["Id"], job["Attempt"], 180)
    first = counts(db_session, plan_run_id)
    job2 = claim(db_session, queue.enqueue(db_session, "Çalışma", CHANNEL_INTERACTIVE, None, {"plan_run_id": plan_run_id}), job_settings)
    run_plan_job(job2["Id"], job2["Attempt"], 180)
    db_session.expire_all()
    assert counts(db_session, plan_run_id) == first


def test_engine_on_other_data_returns_an_empty_plan(db_session, plan_env, job_settings):
    """Sentetik olmayan veride ya da fikstürde planı olmayan senaryoda sahte motor boş plan döner; talep kopyası yine kurulur."""
    plan_run_id, job = submit_and_claim(db_session, plan_env, job_settings)
    run_plan_job(job["Id"], job["Attempt"], 180)
    db_session.expire_all()
    assert run_status(db_session, plan_run_id).Status == "Bitti"
    c = counts(db_session, plan_run_id)
    assert c["planning.PlannedSupply"] == 0 and c["adm.SolverLog"] == 1


def test_nothing_written_when_job_no_longer_owned(db_session, plan_env, job_settings):
    plan_run_id, job = submit_and_claim(db_session, plan_env, job_settings)
    with pytest.raises(JobNoLongerOwned):
        write_result(db_session, plan_run_id, fake_result(), job["Id"], job["Attempt"] + 1)
    assert set(counts(db_session, plan_run_id).values()) == {0}
    assert run_status(db_session, plan_run_id).Status == "Sırada"


def material(session, code):
    return session.execute(text("SELECT Id FROM core.Material WHERE Code = :c AND VersionTo IS NULL"), {"c": code}).scalar_one()


def test_unknown_column_and_link_roll_back(db_session, plan_env, job_settings):
    plan_run_id, job = submit_and_claim(db_session, plan_env, job_settings)
    row = {"ref": "S1", "SupplyType": "Satın alma", "Source": "Plan", "MaterialId": material(db_session, "SAT-007"), "LocationId": plan_env["location_id"],
           "PeriodStart": "2026-12-07", "PeriodEnd": "2026-12-13", "Quantity": 5, "RoundedQuantity": 50}
    with pytest.raises(ValueError, match="bilinmeyen alan Utilisation"):
        write_result(db_session, plan_run_id, PlanResult("LP", planned_supply=[{**row, "Utilisation": 1}]), job["Id"], job["Attempt"])
    bad = {"supply": {"MovementType": "Satın alma planı", "supply_ref": "S1"}, "demand": {"MovementType": "Kesin sipariş", "fulfillment_ref": "YOK"}, "Quantity": 1}
    with pytest.raises(ValueError, match="hareket anahtarı 0 harekete uyuyor"):
        write_result(db_session, plan_run_id, PlanResult("LP", planned_supply=[row], pegging=[bad]), job["Id"], job["Attempt"])
    transfer = {"supply": {"MovementType": "Alokasyon transferi"}, "demand": bad["demand"], "Quantity": 1}
    with pytest.raises(ValueError, match="kaynak kaydı yok"):                         # transfer hareketi pegging'e bağlanamaz (kaynak kaydı yok)
        write_result(db_session, plan_run_id, PlanResult("LP", planned_supply=[row], pegging=[transfer]), job["Id"], job["Attempt"])
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
