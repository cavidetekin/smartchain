"""Motor girdisini okur: PlanRun ve parametre seti (docs/02 · Plan, Parametre)."""
from sqlalchemy import text
from sqlalchemy.orm import Session

from .data import SqlPlanningData
from .interface import EngineInput, ParameterSetData, PlanRunInfo, PriorityRule, TimeBucket


class PlanRunNotFound(LookupError):
    pass


def load_plan_run(session: Session, plan_run_id: int) -> PlanRunInfo:
    row = session.execute(text(
        "SELECT Id, DataVersionId, ParameterSetId, ScenarioId, WorkspaceId FROM planning.PlanRun WHERE Id = :id"),
        {"id": plan_run_id}).first()
    if row is None:
        raise PlanRunNotFound(plan_run_id)
    return PlanRunInfo(id=row.Id, data_version_id=row.DataVersionId, parameter_set_id=row.ParameterSetId,
                       scenario_id=row.ScenarioId, workspace_id=row.WorkspaceId)


def load_parameters(session: Session, parameter_set_id: int) -> ParameterSetData:
    p = {"id": parameter_set_id}
    name = session.execute(text("SELECT Name FROM param.ParameterSet WHERE Id = :id"), p).scalar_one()
    settings = dict(session.execute(text(
        "SELECT SettingKey, Value FROM param.PlanningSetting WHERE ParameterSetId = :id"), p).all())
    buckets = tuple(TimeBucket(r.Seq, r.BucketType, r.Count) for r in session.execute(text(
        "SELECT Seq, BucketType, [Count] FROM param.TimeBucketDefinition WHERE ParameterSetId = :id ORDER BY Seq"), p))
    rules = tuple(PriorityRule(r.Seq, r.Criterion, r.Direction or "Artan") for r in session.execute(text(
        "SELECT Seq, Criterion, Direction FROM param.PriorityRule WHERE ParameterSetId = :id ORDER BY Seq"), p))
    allocation = tuple(dict(r) for r in session.execute(text(
        "SELECT * FROM param.AllocationRule WHERE ParameterSetId = :id ORDER BY Id"), p).mappings())
    return ParameterSetData(id=parameter_set_id, name=name, settings=settings, time_buckets=buckets,
                            priority_rules=rules, allocation_rules=allocation)


def load_input(session: Session, plan_run_id: int, time_budget_seconds: int) -> EngineInput:
    run = load_plan_run(session, plan_run_id)
    return EngineInput(plan_run=run, parameters=load_parameters(session, run.parameter_set_id),
                       data=SqlPlanningData(session, run.data_version_id), time_budget_seconds=time_budget_seconds)
