"""Sahte motor (adım 0.5; K-205 ile plan fikstürü): sentetik veride plan fikstürünün planını döndürür. Gerçek motor Aşama 10'da aynı arayüzle
yerine geçer (10.8).

- Sentetik verinin veri versiyonunda (lokasyonu sentetik lokasyon) Baz senaryoda "Baz · güncel" planı, sentetik senaryoda adı uyan plan döner
  (`app/data/synthetic/plan.py`). Yazımdan sonra fikstürün uyarıları, metrikleri ve tutarlılık denetimi çalışır (`after_write`).
- Öteki durumlarda (sentetik olmayan veri, fikstürde planı olmayan senaryo, testlerin kendi veri versiyonu) boş plan döner.

Sahte motora özel PlanningSetting anahtarları (docs/09-motor-arayuzu.md):
- FakeEngineStepSeconds: her adımda bekleme (sn); uzun hesap, kalp atışı ve süre bütçesi denemesi için.
- FakeEngineMode: normal | crash (Çözüm adımında süreç beklenmedik biter) | error (Model kurmada motor hatası).
"""
import os
import time

from sqlalchemy import text
from sqlalchemy.orm import Session

from .interface import STAGES, EngineError, EngineInput, PlanResult, Progress

SOLVER_LOG = {"ModelSize": "Sahte motor: model kurulmadı", "SolveSeconds": 0, "Gap": 0, "Iterations": 0}
# Uyarı kodları param.WarningDefinition'a bağlı. Katalog geçiş 0069'da yazılır (K-190); burada yalnız eksikse eklenir (geliştirme, test ve demo).
FIXTURE_WARNING_DEFINITIONS = {"CAP_OVERLOAD": "Kapasite", "ORDER_LATE": "Talep"}


def ensure_fixture_warning_definitions(session: Session) -> None:
    """Uyarı kodları tanımlı değilse ekler (geliştirme, test ve demo için)."""
    for code, category in FIXTURE_WARNING_DEFINITIONS.items():
        session.execute(text("IF NOT EXISTS (SELECT 1 FROM param.WarningDefinition WHERE Code = :c) "
                             "INSERT INTO param.WarningDefinition (Code, Category) VALUES (:c, :cat)"),
                        {"c": code, "cat": category})
    session.commit()


def fixture_plan(session: Session | None, plan_run_id: int) -> dict | None:
    """Plan hesabına uyan fikstür planı: veri versiyonu sentetik lokasyonun versiyonuysa, Baz'da "Baz · güncel", sentetik senaryoda adı uyan plan."""
    if session is None:
        return None
    from app.data.synthetic import dataset, plan as fixture
    row = session.execute(text(
        "SELECT sd.Name, ISNULL(sd.IsBase, 0) AS IsBase FROM planning.PlanRun r JOIN adm.DataVersion v ON v.Id = r.DataVersionId AND ISNULL(v.IsSynthetic, 0) = 1 "
        "JOIN core.Location l ON l.Id = v.LocationId AND l.Code = :loc JOIN param.ScenarioDefinition sd ON sd.Id = r.ScenarioDefinitionId WHERE r.Id = :id"),
        {"id": plan_run_id, "loc": dataset.LOCATION_CODE}).first()
    if row is None:
        return None
    wanted = "Baz" if row.IsBase else row.Name
    run = session.execute(text("SELECT DataVersionId FROM planning.PlanRun WHERE Id = :id"), {"id": plan_run_id}).scalar_one()
    return next((p for p in fixture.fixture_for(fixture.data_day(session, run))["plans"] if p["scenario"] == wanted and p["night"] == 0), None)


class FakeEngine:
    name = "Sahte"

    def __init__(self):
        self.after_write = None   # yazıcının çıktılardan sonra çağırdığı adım (fikstürde uyarı, metrik, tutarlılık)

    def run(self, inp: EngineInput, progress: Progress) -> PlanResult:
        settings = inp.parameters.settings
        step = float(settings.get("FakeEngineStepSeconds", "0") or 0)
        mode = settings.get("FakeEngineMode", "normal")
        for stage in STAGES:
            progress(stage)
            if mode == "error" and stage == "Model kurma":
                raise EngineError("Model kurulamadı (sahte motor deneme hatası).")
            if mode == "crash" and stage == "Çözüm":
                os._exit(3)  # süreç çöküşü: servis işi yeniden sıraya alır (K-71)
            time.sleep(step)
        result = PlanResult(engine_used=settings.get("ModelType", "LP"), solver=self.name, solver_log=dict(SOLVER_LOG))
        session = getattr(inp.data, "session", None)
        plan = fixture_plan(session, inp.plan_run.id)
        if plan is not None:
            from app.data.synthetic import plan as fixture
            r = fixture.result_for(session, inp.plan_run.id, plan)
            result.planned_supply, result.demand_fulfillment, result.planned_overtime = r.planned_supply, r.demand_fulfillment, r.planned_overtime
            result.allocation_transfers, result.pegging = r.allocation_transfers, r.pegging
            self.after_write = fixture.after_write()
        return result


def build_engine() -> FakeEngine:
    """Kullanılan motor. Aşama 10'da gerçek motor burada devreye girer (10.8)."""
    return FakeEngine()
