"""Plan çıktı tabloları (K-202, 2. parça): tablo yapısı, hareket türlerinin tek tanımı, veri sözlüğü kaydı, talep kopyası ve karşılama özeti.

Veritabanı testi plan hesabını işlem içinde açar ve geri alır; test veritabanında iz bırakmaz.
"""
from datetime import date
from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app import priorities
from app.engine.data import SqlPlanningData
from app.params import catalog as cat, pegging, service as params
from app.periods import cache, periods
from app.planning import demand, movements
from db import dictionary
from db.models import metadata

PLAN = ("PlannedSupply", "PlannedDemand", "DemandFulfillment", "PlannedOvertime", "PlannedAllocationTransfer", "MaterialTransaction", "CapacityLoad", "Pegging")
SYSTEM = {"Id", "PlanRunId", "UpdatedAt"}


def table(name: str) -> sa.Table:
    return metadata.tables[f"planning.{name}"]


def values(name: str, column: str) -> list[str]:
    return table(name).c[column].info["values"]


def test_old_tables_are_gone_and_every_plan_table_hangs_on_the_plan_run():
    assert not {"planning.PlannedOrder", "planning.SupplyRecommendation"} & set(metadata.tables)
    for name in PLAN:
        t = table(name)
        assert not t.c.PlanRunId.nullable and t.c.PlanRunId.index and {fk.column.table.name for fk in t.c.PlanRunId.foreign_keys} == {"PlanRun"}, name
        assert {"PeriodStart", "PeriodEnd"} <= set(t.c.keys()) or name in ("PlannedDemand", "Pegging"), name           # dönem iki tarihle saklanır
        assert not any(isinstance(c.type, sa.Integer) and "Period" in c.name for c in t.columns), name                # dönem numarası saklanmaz
    assert "IsFixed" not in table("Pegging").c and "Overtime" not in table("CapacityLoad").c and "GrossCapacity" not in table("CapacityLoad").c
    assert {"SalesOrderLineId", "ForecastId", "DueDate", "DuePeriodStart"} <= set(table("PlannedDemand").c.keys())    # iki iç bağ; vade tarihi ve dönemi
    assert {"SupplyTransactionId", "DemandTransactionId", "PlannedDemandId", "ParentPeggingId"} <= set(table("Pegging").c.keys())
    # plan satırları arasındaki bağlar veritabanında korunur ve indekslidir
    links = {("DemandFulfillment", "PlannedDemandId"): "PlannedDemand", ("MaterialTransaction", "PlannedSupplyId"): "PlannedSupply",
             ("MaterialTransaction", "DemandFulfillmentId"): "DemandFulfillment", ("CapacityLoad", "PlannedSupplyId"): "PlannedSupply",
             ("Pegging", "SupplyTransactionId"): "MaterialTransaction", ("Pegging", "DemandTransactionId"): "MaterialTransaction",
             ("Pegging", "ParentPeggingId"): "Pegging", ("Pegging", "PlannedDemandId"): "PlannedDemand"}
    for (name, column), target in links.items():
        col = table(name).c[column]
        assert {fk.column.table.name for fk in col.foreign_keys} == {target} and col.index, (name, column)


def test_fason_flag_has_the_work_order_name_and_label():
    """Öneri b: fason ayrı tür değildir; ayraç `WorkOrder`'daki alanla aynı ad ve etikette."""
    flag, order = table("PlannedSupply").c.IsSubcontract, metadata.tables["core.WorkOrder"].c.IsSubcontract
    assert flag.info["label"] == order.info["label"] == "Fason"
    assert values("PlannedSupply", "SupplyType") == [movements.SUPPLY_PRODUCTION, movements.SUPPLY_PURCHASE] == ["Üretim", "Satın alma"]
    assert values("PlannedSupply", "Source") == [movements.SOURCE_PLAN, movements.SOURCE_ORDER]
    assert movements.supply_number("Üretim", 71) == "ÜP-000071" and movements.supply_number("Satın alma", 214) == "SP-000214"


def test_movement_types_have_a_single_definition():
    """docs/02'deki değer listeleri, hareket tanımı ve Pegging sekmesinin ölçütleri aynı adları taşır; talep türleri Hedefler'le aynı kaynaktan."""
    assert values("MaterialTransaction", "MainMovement") == list(movements.MAIN)
    assert values("MaterialTransaction", "MovementType") == list(movements.TYPES)
    assert values("MaterialTransaction", "Direction") == [movements.PLUS, movements.MINUS]
    for side in ("Supply", "Demand"):
        assert values("Pegging", f"{side}MainMovement") == list(movements.MAIN) and values("Pegging", f"{side}MovementType") == list(movements.TYPES)
    assert movements.MAIN[movements.MAIN_DEMAND] == cat.DEMAND_TYPES
    for name, column in (("PlannedDemand", "DemandType"), ("DemandFulfillment", "DemandType"), ("Pegging", "RootDemandType")):
        assert values(name, column) == list(cat.DEMAND_TYPES), (name, column)
    need = [c.name for c in pegging.CRITERIA[pegging.NEED] if not c.hints]
    supply = [c.name for c in pegging.CRITERIA[pegging.SUPPLY] if not c.hints]
    assert sorted(need) == sorted(movements.NEED_TYPES) and sorted(supply) == sorted(movements.SUPPLY_TYPES)
    assert movements.MAIN[movements.MAIN_TRANSFER] == ("Alokasyon transferi",) and "Fason" not in movements.TYPES


def test_plan_tables_are_in_the_dictionary():
    rows = {(f["TableName"], f["FieldName"]): f for f in dictionary.fields(metadata)}
    for name in PLAN:
        t = table(name)
        assert t.info["field_class"] == "Plan"
        listed = {field for tname, field in rows if tname == name}
        assert listed == set(t.c.keys()) - SYSTEM, name                                                                # sistem alanları sözlüğe girmez
        assert all(rows[name, f]["FieldClass"] == "Plan" and rows[name, f]["StandardLabel"] and len(rows[name, f]["StandardLabel"]) <= 40 for f in listed), name
        assert not any(rows[name, f]["ManualOverrides"] or rows[name, f]["EditableInWorkspace"] for f in listed), name     # plan çıktısına manuel değer girilmez
    assert rows["PlannedSupply", "SupplyNo"]["StandardLabel"] == "No" and rows["MaterialTransaction", "DocumentNo"]["StandardLabel"] == "No"
    assert rows["PlannedDemand", "DuePeriodStart"]["StandardLabel"] == "Vade dönemi" and rows["DemandFulfillment", "Quantity"]["StandardLabel"] == "Karşılama adedi"
    assert "Plan" in metadata.tables["adm.FieldDefinition"].c.FieldClass.info["values"]
    with_class = [t.name for t in metadata.tables.values() if t.info.get("field_class")]
    assert len(with_class) == len(set(with_class))                                                                     # sözlükte tablo adı tekildir
    assert {t.schema for t in metadata.tables.values() if t.info.get("field_class") and t.name not in PLAN} == {"core", "param"}


# ------------------------------------------------------------------ talep kopyası ve özet (veritabanı)

def _one(session: Session, sql: str, **p):
    return session.execute(sa.text(sql), p).scalar()


@pytest.mark.db
def test_demand_copy_and_summary(db_engine):
    with Session(db_engine) as s:
        try:
            base = cache.base_id(s)
            version = _one(s, "SELECT MAX(Id) FROM adm.DataVersion")
            run = _one(s, "INSERT INTO planning.PlanRun (DataVersionId, ScenarioDefinitionId, Status) OUTPUT inserted.Id VALUES (:v, :s, N'Sırada')", v=version, s=base)
            written = demand.copy(s, run)
            open_orders = _one(s, "SELECT COUNT(*) FROM core.SalesOrderLine WHERE VersionTo IS NULL AND ISNULL(IsActive, 1) = 1 AND OpenQuantity > 0")
            forecasts = _one(s, "SELECT COUNT(*) FROM core.Forecast WHERE VersionTo IS NULL AND ISNULL(IsActive, 1) = 1 AND Quantity > 0")
            assert open_orders > 0 and forecasts > 0, "test veritabanında sentetik veri bekleniyor"
            assert written == open_orders + forecasts                                                                    # açık bütün talepler; her tahmin bir satır
            rows = SqlPlanningData(s, version, base, run).planned_demands(included_only=False)
            assert len(rows) == written and {r["DemandType"] for r in rows} <= set(cat.DEMAND_TYPES)
            by_type = {t: [r for r in rows if r["DemandType"] == t] for t in cat.DEMAND_TYPES}
            assert len(by_type[cat.DEMAND_FORECAST]) == forecasts and by_type[cat.DEMAND_FIRM]
            # iki iç bağdan tam biri dolu; tahminde sipariş alanları boş
            assert all((r["SalesOrderLineId"] is None) != (r["ForecastId"] is None) for r in rows)
            assert all(r["OrderNo"] is None and r["LineNo"] is None for r in by_type[cat.DEMAND_FORECAST]) and all(r["OrderNo"] for r in by_type[cat.DEMAND_FIRM])
            # tür: teklif işaretliyse Teklif, değilse beklemedeyse Beklemedeki sipariş (Hedefler'le aynı kural)
            flags = {r.Id: (r.IsQuote, r.IsOnHold, r.OpenQuantity, r.ConfirmedDate or r.RequestedDate) for r in s.execute(sa.text(
                "SELECT Id, IsQuote, IsOnHold, OpenQuantity, ConfirmedDate, RequestedDate FROM core.SalesOrderLine WHERE VersionTo IS NULL"))}
            from app.params.objectives import demand_type
            for r in rows:
                if r["SalesOrderLineId"] is not None:
                    quote, hold, quantity, due = flags[r["SalesOrderLineId"]]
                    assert r["DemandType"] == demand_type(quote, hold) and r["DemandQuantity"] == quantity and r["DueDate"] == due
            # plana dahil: yalnız türü parametreyle kapalı talep Hayır
            settings = params.read_settings(s, base)
            closed = {t for t, key in cat.DEMAND_SWITCH.items() if settings.get(key) == cat.NO}
            assert all(r["IsIncluded"] == (r["DemandType"] not in closed) for r in rows)
            assert [r["Id"] for r in SqlPlanningData(s, version, base, run).planned_demands()] == [r["Id"] for r in rows if r["IsIncluded"]]
            # öncelik grubu: Öncelik yönetimi'nin geçerli grubu
            wanted = {o["SalesOrderLineId"]: o["PriorityGroup"] for o in priorities.demand_priorities(s, base)["orders"]}
            assert all(r["PriorityGroup"] == wanted[r["SalesOrderLineId"]] for r in rows if r["SalesOrderLineId"] in wanted)
            assert all(1 <= r["PriorityGroup"] <= 5 for r in rows)
            # vade dönemi: vadenin düştüğü plan dönemi; vade plan başlangıcından önceyse ilk dönem, ufuktan sonraysa boş
            horizon = periods.read(s, base, date.today())
            for r in rows:
                expected = next((p.start for p in horizon if r["DueDate"] <= p.end), None)
                assert r["DuePeriodStart"] == expected, (r["DueDate"], r["DuePeriodStart"])
            assert any(r["DuePeriodStart"] == horizon[0].start for r in rows) or all(r["DueDate"] >= horizon[0].start for r in rows)
            assert all(r["FulfilledQuantity"] is None for r in rows)                                                     # özet hesaptan sonra yazılır

            # özet: kırılım satırlarından
            included = [r for r in rows if r["IsIncluded"]]
            full, partial, none = included[0], included[1], included[2]
            excluded = next((r for r in rows if not r["IsIncluded"]), None)

            def fulfil(d, share, tardy, start):
                s.execute(sa.text("INSERT INTO planning.DemandFulfillment (PlanRunId, PlannedDemandId, DemandType, MaterialId, LocationId, PeriodStart, PeriodEnd, "
                                  "Quantity, IsTardy, UpdatedAt) VALUES (:run, :d, :t, :m, :l, :a, :a, :q, :tardy, SYSUTCDATETIME())"),
                          {"run": run, "d": d["Id"], "t": d["DemandType"], "m": d["MaterialId"], "l": d["LocationId"], "a": start,
                           "q": d["DemandQuantity"] * Decimal(str(share)), "tardy": tardy})

            fulfil(full, 1, 0, date(2026, 12, 7))
            fulfil(partial, 0.5, 0, date(2026, 12, 7))
            fulfil(partial, 0.25, 1, date(2026, 12, 14))
            demand.summarize(s, run)
            got = {r["Id"]: r for r in demand.rows(s, run)}
            f, p, n = got[full["Id"]], got[partial["Id"]], got[none["Id"]]
            q = partial["DemandQuantity"]
            assert (f["FulfilledQuantity"], f["OnTimeQuantity"], f["LateQuantity"], f["UnmetQuantity"], f["FulfillmentPct"]) == (full["DemandQuantity"], full["DemandQuantity"], 0, 0, 100)
            assert (p["FulfilledQuantity"], p["OnTimeQuantity"], p["LateQuantity"], p["UnmetQuantity"]) == (q * Decimal("0.75"), q * Decimal("0.5"), q * Decimal("0.25"), q * Decimal("0.25"))
            assert p["FulfillmentPct"] == 75 and p["LastFulfillmentPeriodStart"] == date(2026, 12, 14) and f["LastFulfillmentPeriodStart"] == date(2026, 12, 7)
            assert (n["FulfilledQuantity"], n["UnmetQuantity"], n["FulfillmentPct"], n["LastFulfillmentPeriodStart"]) == (0, none["DemandQuantity"], 0, None)
            if excluded is not None:                                                                                      # plana dahil olmayan talepte özet boş
                assert got[excluded["Id"]]["FulfilledQuantity"] is None and got[excluded["Id"]]["UnmetQuantity"] is None
            # kopya yeniden kurulabilir: önce çıktılar silinir
            s.execute(sa.text("DELETE FROM planning.DemandFulfillment WHERE PlanRunId = :r"), {"r": run})
            assert demand.copy(s, run) == written
        finally:
            s.rollback()
