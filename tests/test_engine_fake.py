"""Sahte motor (0.5): fikstür → PlanResult, adım sırası, hata modu. Veritabanı gerekmez."""
import pytest

from app.engine.fake import FakeEngine, load_fixture
from app.engine.interface import STAGES, EngineError, EngineInput, PlanRunInfo, ScenarioParameters


def make_input(**settings):
    return EngineInput(plan_run=PlanRunInfo(id=1, data_version_id=1, scenario_definition_id=1),
                       parameters=ScenarioParameters(id=1, name="Deneme", settings=settings),
                       data=None, time_budget_seconds=180)


def test_returns_fixture_and_reports_stages():
    stages = []
    result = FakeEngine().run(make_input(ModelType="MILP"), stages.append)
    fx = load_fixture()
    assert stages == list(STAGES)
    assert result.engine_used == "MILP" and result.solver == "Sahte" and result.status == "Bitti"
    assert len(result.planned_supply) == len(fx["planned_supply"]) == 4
    assert (len(result.planned_overtime), len(result.allocation_transfers), len(result.material_transactions), len(result.capacity_loads), len(result.pegging)) == (1, 1, 8, 2, 3)
    moves = {t["ref"] for t in result.material_transactions}
    assert {p[k] for p in result.pegging for k in ("supply_ref", "demand_ref")} <= moves                      # pegging iki harekete bağlanır
    transfers = {t["ref"] for t in result.material_transactions if t["MainMovement"] == "Transfer"}
    assert len(transfers) == 2 and not transfers & {p[k] for p in result.pegging for k in ("supply_ref", "demand_ref")}   # transfer pegging'e girmez
    general = [p for p in result.pegging if p.get("IsFromGeneral")]
    assert [next(t["MovementType"] for t in result.material_transactions if t["ref"] == p["supply_ref"]) for p in general] == ["Stok"]   # genelden: gerçek arz
    assert {r["supply_ref"] for r in result.material_transactions + result.capacity_loads if "supply_ref" in r} <= {s["ref"] for s in result.planned_supply}
    assert result.demand_fulfillment == [] and not any("fulfillment_ref" in t for t in result.material_transactions)   # talep yoksa karşılama satırı yazılmaz
    assert not any("root_demand" in p or "PlannedDemandId" in p for p in result.pegging)
    assert {(s["SupplyType"], s["Source"]) for s in result.planned_supply} == {("Üretim", "Plan"), ("Satın alma", "Plan"), ("Üretim", "Sipariş")}   # fason ayrı tür değil
    assert [s.get("IsSubcontract") for s in result.planned_supply] == [False, False, True, False]
    assert result.metrics["OnTimePct"] == 50


class _Demands:
    """Plan hesabının talep kopyası yerine: iki talep."""

    def planned_demands(self, included_only=True):
        return [{"Id": 11, "DemandQuantity": 40, "DueDate": "2026-12-03", "DuePeriodStart": "2026-11-30"},
                {"Id": 12, "DemandQuantity": 100, "DueDate": "2026-12-10", "DuePeriodStart": None}]


def test_fulfillment_rows_sit_on_the_copied_demands():
    from datetime import date
    inp = EngineInput(plan_run=PlanRunInfo(id=1, data_version_id=1, scenario_definition_id=1), parameters=ScenarioParameters(id=1, name="Deneme"),
                      data=_Demands(), time_budget_seconds=180)
    result = FakeEngine().run(inp, lambda s: None)
    rows = [(r["PlannedDemandId"], r["Quantity"], r["PeriodStart"], r["PeriodEnd"], r["IsTardy"]) for r in result.demand_fulfillment]
    assert rows == [(11, 40.0, date(2026, 11, 30), date(2026, 12, 6), False),                               # tamamı, vade döneminde
                    (12, 60.0, date(2026, 12, 10), date(2026, 12, 16), False),                               # vade dönemi boşsa vade tarihinden
                    (12, 25.0, date(2026, 12, 17), date(2026, 12, 23), True)]                                # bir hafta sonra, gecikmeli
    assert [t.get("fulfillment_ref") for t in result.material_transactions if t["MainMovement"] == "Talep"] == ["F1"]
    assert {p["PlannedDemandId"] for p in result.pegging} == {11}


def test_result_is_a_copy():
    a = FakeEngine().run(make_input(), lambda s: None)
    a.planned_supply.clear()
    assert len(FakeEngine().run(make_input(), lambda s: None).planned_supply) == 4


def test_error_mode_stops_at_model():
    stages = []
    with pytest.raises(EngineError, match="Model kurulamadı"):
        FakeEngine().run(make_input(FakeEngineMode="error"), stages.append)
    assert stages[-1] == "Model kurma"
