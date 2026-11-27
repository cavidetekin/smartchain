"""Sahte motor: fikstür döndürür (adım 0.5). Gerçek motor Aşama 10'da aynı arayüzle yerine geçer (10.8).

Sahte motora özel PlanningSetting anahtarları (docs/09-motor-arayuzu.md):
- FakeEngineStepSeconds: her adımda bekleme (sn); uzun hesap, kalp atışı ve süre bütçesi denemesi için.
- FakeEngineMode: normal | crash (Çözüm adımında süreç beklenmedik biter) | error (Model kurmada motor hatası).
"""
import copy
import json
import os
import time
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from .interface import STAGES, EngineError, EngineInput, PlanResult, Progress

FIXTURE = Path(__file__).parent / "fixtures" / "plan_v0.json"

# Fikstürdeki uyarı kodları; PlanWarning.WarningCode param.WarningDefinition'a bağlı. Katalog geçiş 0069'da yazılır (K-190); burada yalnız eksikse eklenir.
FIXTURE_WARNING_DEFINITIONS = {"CAP_OVERLOAD": "Kapasite", "ORDER_LATE": "Talep"}


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
        demands = inp.data.planned_demands() if inp.data is not None else []
        fulfillment = _fulfillment(fx["demand_fulfillment"], demands)
        written = {row["ref"] for row in fulfillment}
        for row in fx["material_transactions"]:  # karşılama satırı yazılmadıysa hareketin bağı da yoktur
            if row.get("fulfillment_ref") not in written:
                row.pop("fulfillment_ref", None)
        for row in fx["pegging"]:
            at = row.pop("root_demand", None)
            if at is not None and at < len(demands):
                row["PlannedDemandId"] = demands[at]["Id"]
        return PlanResult(
            engine_used=settings.get("ModelType", "LP"),
            solver=self.name,
            status=fx["status"],
            planned_supply=fx["planned_supply"],
            demand_fulfillment=fulfillment,
            planned_overtime=fx["planned_overtime"],
            allocation_transfers=fx["allocation_transfers"],
            material_transactions=fx["material_transactions"],
            capacity_loads=fx["capacity_loads"],
            pegging=fx["pegging"],
            warnings=fx["warnings"],
            metrics=fx["metrics"],
            solver_log=fx["solver_log"],
        )


def _fulfillment(rows: list[dict], demands: list[dict]) -> list[dict]:
    """Fikstürün karşılama satırları plan hesabının taleplerine oturtulur: `demand` plana dahil taleplerin vade sırasındaki yeri, `share` talep
    miktarının payı, `weeks_late` vade döneminden kaç hafta sonra. O sırada talep yoksa satır yazılmaz."""
    out = []
    for row in rows:
        if row["demand"] >= len(demands):
            continue
        demand = demands[row["demand"]]
        start = demand["DuePeriodStart"] or demand["DueDate"]
        if isinstance(start, str):
            start = date.fromisoformat(start)
        start += timedelta(weeks=row["weeks_late"])
        out.append({"ref": row["ref"], "PlannedDemandId": demand["Id"], "PeriodStart": start, "PeriodEnd": start + timedelta(days=6),
                    "Quantity": round(float(demand["DemandQuantity"]) * row["share"], 4), "IsTardy": row["weeks_late"] > 0})
    return out


def build_engine() -> FakeEngine:
    """Kullanılan motor. Aşama 10'da gerçek motor burada devreye girer (10.8)."""
    return FakeEngine()
