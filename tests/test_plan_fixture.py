"""Plan fikstürü (K-205, geliştirme 8.0): dosyanın güncelliği, üç plan ve 12 durum, alokasyon kuralının bellekteki karşılığı, yükleme ve tutarlılık.

Yükleme testi işlem içinde çalışır ve geri alınır: test veritabanındaki fikstür planlarına dokunmaz.
"""
from datetime import date

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.data.synthetic import dataset as d, plan
from app.planning import checks, metrics, movements as mv

NAMES = ["Baz · güncel", "Baz · önceki gece", "Fazla mesaili"]


@pytest.fixture(scope="module")
def fx():
    return plan.read()


def test_file_is_current(fx):
    """Dosya, kendi üretim günü için betiğin çıktısıyla aynı. Düşerse: python -m app.data.synthetic plan --regenerate (sentetik veri ya da kural değişti)."""
    assert fx == plan.generate(date.fromisoformat(fx["generated_on"]))


def test_three_plans_and_twelve_situations(fx):
    plans = {p["name"]: p for p in fx["plans"]}
    assert list(plans) == NAMES and [p["scenario"] for p in fx["plans"]] == ["Baz", "Baz", "Fazla mesaili"] and [p["night"] for p in fx["plans"]] == [0, -1, 0]
    b = plans["Baz · güncel"]
    supply = b["supply"]
    late = [f for f in b["fulfillment"] if f["demand"][1].split("|")[1] == d.LATE_ORDER]
    assert len(late) == 2 and late[1]["week"] == late[0]["week"] + 1                                               # 1 kısmen geç
    assert not [f for f in b["fulfillment"] if f"|{d.IMPOSSIBLE_ORDER}|" in f["demand"][1]]                        # 2 karşılanmayan
    assert [o for o in b["overtime"] if o["group"] == d.BOTTLENECK_GROUP]                                          # 3 darboğazda ek mesai
    assert b["transfers"] and [g for g in b["pegging"] if g["IsFromGeneral"]]                                      # 4 genelden transfer
    assert all("transfer" not in g["supply"] and "transfer" not in g["demand"] for g in b["pegging"])              #   transfer pegging'e girmez
    assert [s for s in supply if s["IsSubcontract"] and s["Source"] == "Plan" and s["supplier"] and s["lead_days"]]  # 6 fason
    assert [s["week"] for s in supply if s["work_order"] == "WO-5012"] == [s["week"] for s in supply if s["work_order"] == "WO-5012"][:1] + \
        [[s["week"] for s in supply if s["work_order"] == "WO-5012"][0] + 1]                                       # 7 iki haftaya bölünmüş
    assert [s["material"] for s in supply if s["IsFixed"]] == ["ALT-001"] and [s["material"] for s in supply if s["IsManual"]] == ["ALT-002"]   # 8
    manual = next(s for s in supply if s["IsManual"])
    assert manual["Quantity"] != manual["ProposedQuantity"] and manual["week"] != manual["proposed_week"]
    assert {s["version"] for s in supply if s["material"] == d.ALTERNATIVE_PARENT} == {"V2"}                       # 9 alternatif versiyon
    assert [s for s in supply if s["SupplyType"] == "Satın alma" and s["RoundedQuantity"] > s["Quantity"]]         # 10 yuvarlanmış
    assert [s for s in supply if s["material"] == d.LATE_MATERIAL and s["lead_days"] == d.LATE_LEAD_DAYS]          # 11 geçmiş sipariş tarihi (yüklemede)
    assert not [f for f in b["fulfillment"] if "|SO-1041|" in f["demand"][1] or "|SO-1042|" in f["demand"][1]]     # 12 teklif karşılanmaz
    # önceki gece: aynı talepler, birkaç kayıt farklı; Fazla mesaili: daha çok ek mesai, daha az gecikme
    prev, more = plans["Baz · önceki gece"], plans["Fazla mesaili"]
    assert [f["demand"] for f in prev["fulfillment"]] == [f["demand"] for f in b["fulfillment"]] and prev["supply"] != supply
    assert not [s for s in prev["supply"] if s["IsManual"]]
    assert sum(o["Overtime"] for o in more["overtime"]) > sum(o["Overtime"] for o in b["overtime"])
    assert sum(1 for f in more["fulfillment"] if f["week"] > 0 and len([x for x in more["fulfillment"] if x["demand"] == f["demand"]]) > 1) < \
        sum(1 for f in b["fulfillment"] if len([x for x in b["fulfillment"] if x["demand"] == f["demand"]]) > 1)


@pytest.mark.db
def test_allocation_rules_match_the_database(db_engine):
    """Bellekteki alokasyon kuralı (fikstür netlemesinin anahtarı) veritabanındaki `MaterialAllocationRule` ile aynı (K-199)."""
    with Session(db_engine) as s:
        version = plan.synthetic_version(s)
        ds = d.generate(plan.data_day(s, version))
        codes = {m["Id"]: m["Code"] for m in ds.rows("Material")}
        mine = {(codes[m], lvl, k) for m, lvl, k in plan.allocation_rules(plan._World(ds))}
        db = {tuple(r) for r in s.execute(sa.text("SELECT m.Code, r.AllocationLevel, r.AllocationKey FROM core.MaterialAllocationRule r JOIN core.Material m "
                                                  "ON m.Id = r.MaterialId AND m.VersionTo IS NULL WHERE r.VersionTo IS NULL"))}
    assert mine == db and mine


@pytest.mark.db
def test_load_writes_three_consistent_plans(db_engine):
    with Session(db_engine) as s:
        try:
            out = plan.load_plans(s)
            assert [o["plan"] for o in out] == NAMES
            for o in out:
                assert checks.problems(s, o["plan_run"]) == [], o["plan"]
                assert o["PlannedSupply"] > 100 and o["MaterialTransaction"] > o["PlannedSupply"] and o["Pegging"] > 0 and o["CapacityLoad"] > 0
            base, prev, more = (o["plan_run"] for o in out)
            q = lambda sql, r=base, **p: s.execute(sa.text(sql), {"r": r, **p}).all()  # noqa: E731
            # gece sonucu ve plan hesabı
            assert q("SELECT r.EngineUsed, r.Solver, r.Status, sc.Status, CASE WHEN sc.PlanRunId = r.Id THEN 1 END FROM planning.PlanRun r "
                     "JOIN planning.Scenario sc ON sc.Id = r.ScenarioId WHERE r.Id = :r") == [(plan.ENGINE, plan.SOLVER, "Bitti", "Bitti", 1)]
            # 1 · 2 · 12: talep
            late = q("SELECT f.IsTardy, f.Quantity FROM planning.DemandFulfillment f WHERE f.PlanRunId = :r AND f.OrderNo = :o ORDER BY f.PeriodStart", o=d.LATE_ORDER)
            assert [t for t, _ in late] == [False, True]
            assert q("SELECT FulfilledQuantity, UnmetQuantity - DemandQuantity FROM planning.PlannedDemand WHERE PlanRunId = :r AND OrderNo = :o", o=d.IMPOSSIBLE_ORDER) == [(0, 0)]
            assert {r[0] for r in q("SELECT DemandType FROM planning.PlannedDemand WHERE PlanRunId = :r AND IsIncluded = 0")} == {"Teklif"}
            # 3: darboğazda ek mesai ve aşım; uyarılar
            codes = {r[0] for r in q("SELECT DISTINCT WarningCode FROM planning.PlanWarning WHERE PlanRunId = :r")}
            assert {"ORDER_LATE", "ORDER_UNMET", "CAP_OVERLOAD", "OVERTIME_USE", "PURCHASE_LATE", "MAT_EXCESS"} <= codes
            # uyarılar dönemini ve ilgili kaydı kendi alanlarında taşır (K-206)
            assert q("SELECT COUNT(*) FROM planning.PlanWarning WHERE PlanRunId = :r AND (PeriodStart IS NULL OR PeriodEnd IS NULL OR "
                     "(WarningCode IN (N'CAP_OVERLOAD', N'OVERTIME_USE') AND ResourceGroupId IS NULL) OR "
                     "(WarningCode IN (N'ORDER_LATE', N'ORDER_UNMET', N'FORECAST_UNMET') AND PlannedDemandId IS NULL) OR "
                     "(WarningCode IN (N'PURCHASE_LATE', N'MAT_EXCESS') AND (PlannedSupplyId IS NULL OR MaterialId IS NULL)))") == [(0,)]
            assert q("SELECT COUNT(*) FROM planning.PlanWarning w JOIN core.ResourceGroup g ON g.Id = w.ResourceGroupId AND g.VersionTo IS NULL "
                     "WHERE w.PlanRunId = :r AND w.WarningCode = N'CAP_OVERLOAD' AND g.Code = :g", g=d.BOTTLENECK_GROUP)[0][0] > 0
            assert q("SELECT COUNT(*) FROM planning.PlannedOvertime o JOIN core.ResourceGroup g ON g.Id = o.ResourceGroupId AND g.VersionTo IS NULL "
                     "WHERE o.PlanRunId = :r AND g.Code = :g", g=d.BOTTLENECK_GROUP)[0][0] > 0
            # 4: transfer ve Genelden pegging'i (arz gerçek genel arz)
            general = q("SELECT g.SupplyMovementType, g.SupplyAllocationKey, g.DemandAllocationKey FROM planning.Pegging g WHERE g.PlanRunId = :r AND g.IsFromGeneral = 1")
            assert general and all(t != mv.ALLOCATION_TRANSFER and a is None and k for t, a, k in general)
            # 5: sahibi kapanmış arz bağlanmaz
            assert q("SELECT COUNT(*) FROM planning.MaterialTransaction t WHERE t.PlanRunId = :r AND t.AllocationKey = :c AND EXISTS "
                     "(SELECT 1 FROM planning.Pegging g WHERE g.SupplyTransactionId = t.Id)", c=d.MISSING_CUSTOMER) == [(0,)]
            # 6 · 7 · 8 · 9: tedarik planı
            assert q("SELECT COUNT(*) FROM planning.PlannedSupply WHERE PlanRunId = :r AND IsSubcontract = 1 AND Source = N'Plan' AND SupplierId IS NOT NULL "
                     "AND OrderDate IS NOT NULL")[0][0] > 0
            assert len(q("SELECT DISTINCT PeriodStart FROM planning.PlannedSupply WHERE PlanRunId = :r AND SupplyNo = N'WO-5012'")) == 2
            assert q("SELECT SUM(CAST(IsFixed AS int)), SUM(CAST(IsManual AS int)) FROM planning.PlannedSupply WHERE PlanRunId = :r") == [(1, 1)]
            assert q("SELECT COUNT(*) FROM planning.PlannedSupply s JOIN core.ProductionVersion pv ON pv.Id = s.ProductionVersionId AND pv.VersionTo IS NULL "
                     "WHERE s.PlanRunId = :r AND pv.Code = N'V2' AND s.BOMCode = :b", b=d.ALTERNATIVE_BOM)[0][0] > 0
            assert q("SELECT COUNT(*) FROM planning.PlannedSupply WHERE PlanRunId = :r AND SupplyNo LIKE N'ÜP-%'")[0][0] > 0 and \
                q("SELECT COUNT(*) FROM planning.PlannedSupply WHERE PlanRunId = :r AND SupplyNo LIKE N'SP-%'")[0][0] > 0
            # metrikler: katalog tam; Fazla mesaili daha çok ek mesai, daha az geciken satır
            m = {r: dict(s.execute(sa.text("SELECT MetricCode, Value FROM planning.PlanMetric WHERE PlanRunId = :r"), {"r": r}).all()) for r in (base, prev, more)}
            assert set(m[base]) == set(metrics.BY_CODE)
            assert m[more]["OvertimeHours"] > m[base]["OvertimeHours"] and m[more]["LateLines"] < m[base]["LateLines"]
            # özet (demo komutu) bütün bölümleri yazar ve denetimler geçer
            text = plan.summary(s)
            assert all(f"{i} · " in text for i in range(1, 13)) and text.count("geçti") == 3
        finally:
            s.rollback()


@pytest.mark.db
def test_broken_plan_is_refused(db_engine):
    """Tutarlılık denetimi düşerse yükleme hiçbir şey bırakmaz (fikstürde bir talep fazla karşılanmış)."""
    import copy
    fx = copy.deepcopy(plan.read())
    with Session(db_engine) as s:
        try:
            on = plan.data_day(s, plan.synthetic_version(s))
            fx = copy.deepcopy(plan.fixture_for(on))
            fx["plans"] = fx["plans"][:1]
            fx["plans"][0]["fulfillment"][0]["Quantity"] *= 3
            with pytest.raises(plan.PlanFixtureError, match="Tutarlılık"):
                plan.load_plans(s, fixture=fx, on=on)
        finally:
            s.rollback()


# --- ufuk ön koşulu (K-209) ------------------------------------------------------------------------------------------------------------------

SHORT = "UPDATE param.TimeBucketDefinition SET Count = 1 WHERE Axis = N'Plan' AND BucketType = N'Hafta' AND ScenarioDefinitionId = :b"


def _base(c) -> int:
    return c.execute(sa.text("SELECT Id FROM param.ScenarioDefinition WHERE IsBase = 1")).scalar_one()


def test_horizon_covering_the_fixture_weeks_passes_short_one_is_refused(db_engine):
    """Haftalık kısım fikstürün 13 haftasını kapsıyorsa geçer; "Hafta · 1 ay" kapsamaz: plan yüklemesi hiçbir şey silmeden durur, mesaj ne
    yapılacağını yazar (geliştirme veritabanındaki hata, 27.11.2026)."""
    with Session(db_engine) as s:
        try:
            base, on = _base(s), plan.data_day(s, plan.synthetic_version(s))
            assert plan.horizon_problem(s, base, on) is None
            runs = plan.fixture_runs(s)
            s.execute(sa.text(SHORT), {"b": base})
            problem = plan.horizon_problem(s, base, on)
            assert problem and "haftalık dönemde değil" in problem
            with pytest.raises(plan.PlanFixtureError, match="Parametreler › Ufuk: haftalık kısım en az 13 hafta") as exc:
                plan.load_plans(s, on=on)
            assert "Hiçbir şey silinmedi" in str(exc.value) and plan.fixture_runs(s) == runs   # önceki fikstür planları yerinde
        finally:
            s.rollback()


@pytest.mark.parametrize("rows, problem", [
    ([("Hafta", 1, "Ay"), ("Ay", 5, "Ay")], '2. hafta (30.11.2026) haftalık dönemde değil ("H49 2026": 30.11.2026 – 30.11.2026)'),   # geliştirmedeki hata
    ([("Hafta", 3, "Ay"), ("Ay", 6, "Ay")], '11. hafta (01.02.2027) haftalık dönemde değil ("Şub 2027": 01.02.2027 – 28.02.2027)'),  # varsayılan, ay sonunda
    ([("Hafta", 4, "Ay"), ("Ay", 6, "Ay")], None),
    ([("Hafta", 13, "Hafta"), ("Ay", 6, "Ay")], None),
    ([("Hafta", 12, "Hafta"), ("Ay", 6, "Ay")], '13. hafta (15.02.2027) haftalık dönemde değil ("Şub 2027": 15.02.2027 – 28.02.2027)'),
])
def test_horizon_rule_on_fixed_periods(monkeypatch, rows, problem):
    """Kural (K-209), 27.11.2026 Cuma plan başlangıcında: fikstürün 13 haftasının her biri tam bir haftalık dönemde; ay sonunda kesilen kısa hafta
    ("Hafta" tipinde ama tek gün) ve aylık dönem kapsamaz. Veritabanısız (dönemler sabit)."""
    from app.params import horizon
    from app.periods import periods as period_list
    start = date(2026, 11, 27)
    monkeypatch.setattr(period_list, "read", lambda session, scenario_id, today: period_list.build(horizon.parts(start, rows)))
    assert plan.horizon_problem(None, 1, start) == problem


def test_load_and_reset_refuse_before_deleting_anything(db_engine):
    """load ve reset ufuk ön koşulunu silmeden önce denetler: reset onay sormaz, veri versiyonu ve planlar değişmez. Ufuk testte geçici kısaltılır,
    sonda geri yazılır (Smartchain_test)."""
    from app.data.synthetic import load as loader
    ds = d.generate(date.today())
    with db_engine.begin() as c:
        base = _base(c)
        saved = c.execute(sa.text("SELECT Count FROM param.TimeBucketDefinition WHERE Axis = N'Plan' AND BucketType = N'Hafta' AND ScenarioDefinitionId = :b"),
                          {"b": base}).scalar_one()
        c.execute(sa.text(SHORT), {"b": base})
    try:
        state = lambda: db_engine.connect().execute(sa.text(  # noqa: E731
            "SELECT (SELECT MAX(Id) FROM adm.DataVersion), (SELECT COUNT(*) FROM planning.PlanRun), (SELECT COUNT(*) FROM core.Material)")).one()
        before, asked = state(), []
        with pytest.raises(plan.PlanFixtureError, match="haftalık kısım en az 13 hafta"):
            loader.reset(db_engine, ds, lambda preview: asked.append(preview) or False)
        assert asked == []                                                         # onaydan önce durdu
        with pytest.raises(plan.PlanFixtureError, match="haftalık kısım en az 13 hafta"):
            loader.load(db_engine, ds)
        assert state() == before
    finally:
        with db_engine.begin() as c:
            c.execute(sa.text("UPDATE param.TimeBucketDefinition SET Count = :n WHERE Axis = N'Plan' AND BucketType = N'Hafta' AND ScenarioDefinitionId = :b"),
                      {"n": saved, "b": base})
