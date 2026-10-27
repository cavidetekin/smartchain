"""Sonucun yazılması (K-70): tek commit, tekrar çalıştırmada çift kayıt yok, yayınlanmış plan değişmez."""
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.engine.fake import FakeEngine
from app.engine.interface import EngineInput, ParameterSetData, PlanRunInfo
from app.engine.job import run_plan_job
from app.engine.submit import submit_plan_run
from app.engine.writer import JobNoLongerOwned, PlanRunPublished, write_result
from app.jobs import queue
from app.jobs.constants import CHANNEL_INTERACTIVE, STATUS_DONE, STATUS_FAILED

pytestmark = pytest.mark.db

OUTPUT_TABLES = ["planning.PlannedOrder", "planning.SupplyRecommendation", "planning.DemandFulfillment",
                 "planning.CapacityLoad", "planning.Pegging", "planning.PlanWarning", "planning.PlanMetric",
                 "adm.SolverLog"]


def counts(session, plan_run_id):
    return {t: session.execute(text(f"SELECT COUNT(*) FROM {t} WHERE PlanRunId = :id"), {"id": plan_run_id}).scalar()
            for t in OUTPUT_TABLES}


def submit_and_claim(session, env, job_settings):
    plan_run_id, job_id = submit_plan_run(session, data_version_id=env["data_version_id"],
                                          parameter_set_id=env["parameter_set_id"], requested_by=env["user_id"])
    job = queue.claim_next(session, CHANNEL_INTERACTIVE, job_settings)
    assert job["Id"] == job_id
    return plan_run_id, job


def fake_result():
    inp = EngineInput(PlanRunInfo(1, 1, 1), ParameterSetData(1, "x", {}), None, 180)
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
    assert c == {"planning.PlannedOrder": 3, "planning.SupplyRecommendation": 1, "planning.DemandFulfillment": 2,
                 "planning.CapacityLoad": 2, "planning.Pegging": 3, "planning.PlanWarning": 2,
                 "planning.PlanMetric": 4, "adm.SolverLog": 1}
    run = run_status(db_session, plan_run_id)
    assert (run.Status, run.EngineUsed, run.Solver) == ("Bitti", "LP", "Sahte") and run.StartedAt and run.EndedAt
    j = queue.get_job(db_session, job["Id"], job_settings)
    assert j["Status"] == STATUS_DONE and j["Progress"] == "Tamamlandı"

    # Pegging'deki planlı sipariş bağları bu hesabın planlı siparişlerine gider.
    linked = db_session.execute(text(
        "SELECT p.SupplyId, o.Id FROM planning.Pegging p LEFT JOIN planning.PlannedOrder o ON o.Id = p.SupplyId "
        "AND o.PlanRunId = p.PlanRunId WHERE p.PlanRunId = :id AND p.SupplyType = N'Planlı sipariş'"),
        {"id": plan_run_id}).all()
    assert len(linked) == 2 and all(o is not None for _, o in linked)


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


def test_unknown_column_rolls_back(db_session, plan_env, job_settings):
    plan_run_id, job = submit_and_claim(db_session, plan_env, job_settings)
    result = fake_result()
    result.capacity_loads[0]["Utilisation"] = 1
    with pytest.raises(ValueError, match="bilinmeyen alan Utilisation"):
        write_result(db_session, plan_run_id, result, job["Id"], job["Attempt"])
    assert set(counts(db_session, plan_run_id).values()) == {0}
    assert queue.get_job(db_session, job["Id"], job_settings)["Status"] == "Çalışıyor"


def publish(session, env, plan_run_id):
    p = {"l": env["location_id"], "ps": env["parameter_set_id"], "dv": env["data_version_id"], "u": env["user_id"],
         "pr": plan_run_id}
    sd = session.execute(text("INSERT INTO param.ScenarioDefinition (LocationId, Name, ParameterSetId) "
                              "OUTPUT inserted.Id VALUES (:l, N'Motor testi', :ps)"), p).scalar_one()
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
