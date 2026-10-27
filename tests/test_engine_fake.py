"""Sahte motor (0.5): fikstür → PlanResult, adım sırası, hata modu. Veritabanı gerekmez."""
import pytest

from app.engine.fake import FakeEngine, load_fixture
from app.engine.interface import STAGES, EngineError, EngineInput, ParameterSetData, PlanRunInfo


def make_input(**settings):
    return EngineInput(plan_run=PlanRunInfo(id=1, data_version_id=1, parameter_set_id=1),
                       parameters=ParameterSetData(id=1, name="Deneme", settings=settings),
                       data=None, time_budget_seconds=180)


def test_returns_fixture_and_reports_stages():
    stages = []
    result = FakeEngine().run(make_input(ModelType="MILP"), stages.append)
    fx = load_fixture()
    assert stages == list(STAGES)
    assert result.engine_used == "MILP" and result.solver == "Sahte" and result.status == "Bitti"
    assert len(result.planned_orders) == len(fx["planned_orders"]) == 3
    assert {p["supply_ref"] for p in result.pegging if "supply_ref" in p} <= {o["ref"] for o in result.planned_orders}
    assert result.metrics["OnTimePct"] == 50


def test_result_is_a_copy():
    a = FakeEngine().run(make_input(), lambda s: None)
    a.planned_orders.clear()
    assert len(FakeEngine().run(make_input(), lambda s: None).planned_orders) == 3


def test_error_mode_stops_at_model():
    stages = []
    with pytest.raises(EngineError, match="Model kurulamadı"):
        FakeEngine().run(make_input(FakeEngineMode="error"), stages.append)
    assert stages[-1] == "Model kurma"
