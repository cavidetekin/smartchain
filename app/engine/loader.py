"""Motor girdisini okur: PlanRun ve senaryonun parametreleri (docs/02 · Plan, Parametre; K-175)."""
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.params import catalog as cat, objectives as objective_rows, service as params

from .data import SqlPlanningData
from .interface import EngineInput, Objective, PlanRunInfo, ScenarioParameters, TimeBucket


class PlanRunNotFound(LookupError):
    pass


def load_plan_run(session: Session, plan_run_id: int) -> PlanRunInfo:
    row = session.execute(text(
        "SELECT Id, DataVersionId, ScenarioDefinitionId, ScenarioId, WorkspaceId FROM planning.PlanRun WHERE Id = :id"),
        {"id": plan_run_id}).first()
    if row is None:
        raise PlanRunNotFound(plan_run_id)
    return PlanRunInfo(id=row.Id, data_version_id=row.DataVersionId, scenario_definition_id=row.ScenarioDefinitionId,
                       scenario_id=row.ScenarioId, workspace_id=row.WorkspaceId)


def _buckets(session: Session, scenario_definition_id: int, axis: str) -> tuple[TimeBucket, ...]:
    return tuple(TimeBucket(i, b, c, u) for i, (b, c, u) in enumerate(params.bucket_rows(session, scenario_definition_id, axis), start=1))


def load_parameters(session: Session, scenario_definition_id: int) -> ScenarioParameters:
    p = {"id": scenario_definition_id}
    name = session.execute(text("SELECT Name FROM param.ScenarioDefinition WHERE Id = :id"), p).scalar_one()
    settings = params.all_settings(session, scenario_definition_id)
    plan = _buckets(session, scenario_definition_id, cat.AXIS_PLAN)
    report = plan if settings.get("ReportAxisSameAsPlan") != cat.NO else _buckets(session, scenario_definition_id, cat.AXIS_REPORT)
    objectives = tuple(Objective(o["seq"], o["code"], o["seconds"], o["tolerance"] or 0.0, o["scope"])
                       for o in objective_rows.read_objectives(session, scenario_definition_id) if o["active"])
    return ScenarioParameters(id=scenario_definition_id, name=name, settings=settings, time_buckets=plan, report_buckets=report,
                              objectives=objectives)


def load_input(session: Session, plan_run_id: int, time_budget_seconds: int) -> EngineInput:
    run = load_plan_run(session, plan_run_id)
    return EngineInput(plan_run=run, parameters=load_parameters(session, run.scenario_definition_id),
                       data=SqlPlanningData(session, run.data_version_id, run.scenario_definition_id), time_budget_seconds=time_budget_seconds)
