"""Sahte motor (0.5; K-205): adım sırası, hata modu; veri erişimi olmadan boş plan. Fikstür planının seçimi ve yazımı `test_engine_writer.py`'de."""
import pytest

from app.engine.fake import FakeEngine
from app.engine.interface import STAGES, EngineError, EngineInput, PlanResult, PlanRunInfo, ScenarioParameters


def make_input(**settings):
    return EngineInput(plan_run=PlanRunInfo(id=1, data_version_id=1, scenario_definition_id=1),
                       parameters=ScenarioParameters(id=1, name="Deneme", settings=settings),
                       data=None, time_budget_seconds=180)


def test_reports_stages_and_returns_an_empty_plan_without_data():
    stages = []
    engine = FakeEngine()
    result = engine.run(make_input(ModelType="MILP"), stages.append)
    assert stages == list(STAGES)
    assert (result.engine_used, result.solver, result.status) == ("MILP", "Sahte", "Bitti")
    assert not (result.planned_supply or result.demand_fulfillment or result.pegging or result.warnings or result.metrics)
    assert result.solver_log["ModelSize"].startswith("Sahte motor") and engine.after_write is None


def test_result_has_no_derived_tables():
    """Malzeme hareketleri ve kapasite yükleri motor sonucunda değildir; yazıcı türetir (K-205)."""
    fields = set(PlanResult.__dataclass_fields__)
    assert not {"material_transactions", "capacity_loads"} & fields
    assert {"planned_supply", "demand_fulfillment", "planned_overtime", "allocation_transfers", "pegging"} <= fields


def test_error_mode_stops_at_model():
    stages = []
    with pytest.raises(EngineError, match="Model kurulamadı"):
        FakeEngine().run(make_input(FakeEngineMode="error"), stages.append)
    assert stages[-1] == "Model kurma"
