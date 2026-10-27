"""Sahte motor: fikstür döndürür (adım 0.5). Gerçek motor Aşama 10'da aynı arayüzle yerine geçer (10.8).

Sahte motora özel PlanningSetting anahtarları (docs/09-motor-arayuzu.md):
- FakeEngineStepSeconds: her adımda bekleme (sn); uzun hesap, kalp atışı ve süre bütçesi denemesi için.
- FakeEngineMode: normal | crash (Çözüm adımında süreç beklenmedik biter) | error (Model kurmada motor hatası).
"""
import copy
import json
import os
import time
from functools import lru_cache
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from .interface import STAGES, EngineError, EngineInput, PlanResult, Progress

FIXTURE = Path(__file__).parent / "fixtures" / "plan_v0.json"

# Fikstürdeki uyarı kodları; PlanWarning.WarningCode param.WarningDefinition'a bağlı. Tanımlar 7.5'te ekrandan gelir.
FIXTURE_WARNING_DEFINITIONS = {"CAP_OVERLOAD": "Kapasite", "ORDER_LATE": "Sipariş"}


@lru_cache
def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def ensure_fixture_warning_definitions(session: Session) -> None:
    """Fikstürün uyarı kodları tanımlı değilse ekler (geliştirme, test ve demo için)."""
    for code, category in FIXTURE_WARNING_DEFINITIONS.items():
        session.execute(text("IF NOT EXISTS (SELECT 1 FROM param.WarningDefinition WHERE Code = :c) "
                             "INSERT INTO param.WarningDefinition (Code, Category) VALUES (:c, :cat)"),
                        {"c": code, "cat": category})
    session.commit()


class FakeEngine:
    name = "Sahte"

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
        fx = copy.deepcopy(load_fixture())
        return PlanResult(
            engine_used=settings.get("ModelType", "LP"),
            solver=self.name,
            status=fx["status"],
            planned_orders=fx["planned_orders"],
            supply_recommendations=fx["supply_recommendations"],
            demand_fulfillment=fx["demand_fulfillment"],
            capacity_loads=fx["capacity_loads"],
            pegging=fx["pegging"],
            warnings=fx["warnings"],
            metrics=fx["metrics"],
            solver_log=fx["solver_log"],
        )


def build_engine() -> FakeEngine:
    """Kullanılan motor. Aşama 10'da gerçek motor burada devreye girer (10.8)."""
    return FakeEngine()
