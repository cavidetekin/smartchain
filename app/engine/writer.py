"""PlanResult'u planning.* tablolarına yazar (K-70, K-202).

Plan hesabı başlarken (`prepare`) hesabın önceki çıktıları silinir ve talep kopyası (`PlannedDemand`) kurulur. Çıktılar, talep özeti, PlanRun durumu
ve iş kaydının bitişi aynı işlemde (tek commit) yazılır: yarım plan görünmez, commit'ten sonra süreç çökse de iş Bitti olduğu için yeniden
çalışmaz. Yayınlanmış PlanRun'a dokunulmaz.

Sistemin doldurdukları (motor yazmaz): tedarik planı numarası (ÜP-…, SP-…), talep karşılama kırılımındaki talep kimliği, hareketin no'su
(tedarik planı kaydından), pegging satırındaki iki tarafın ve kök talebin alanları, talebin özet alanları. Talep hareketinin no'su satış sipariş no'dur (karşılama satırından).
"""
import logging
from datetime import date

import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.jobs import queue
from app.planning import demand, movements
from db.models import (CapacityLoad, DemandFulfillment, MaterialTransaction, Pegging, PlanMetric, PlannedAllocationTransfer, PlannedDemand,
                       PlannedOvertime, PlannedSupply, PlanWarning, SolverLog)
from .interface import RUN_FAILED, RUN_RUNNING, PlanResult

log = logging.getLogger("smartchain.engine")

# PlanResult alanı → tablo ve satırdaki bağ anahtarları (anahtar → kolon, bağlanan PlanResult alanı). Yazım sırasıdır; silme sırası tersidir.
# Satıra `ref` verilebilir; başka tablonun satırı bağ anahtarıyla o satıra bağlanır (kolon, oluşan Id olur).
OUTPUTS = [
    ("planned_supply", PlannedSupply, {}),
    ("demand_fulfillment", DemandFulfillment, {}),
    ("planned_overtime", PlannedOvertime, {}),
    ("allocation_transfers", PlannedAllocationTransfer, {}),
    ("material_transactions", MaterialTransaction, {"supply_ref": ("PlannedSupplyId", "planned_supply"), "fulfillment_ref": ("DemandFulfillmentId", "demand_fulfillment")}),
    ("capacity_loads", CapacityLoad, {"supply_ref": ("PlannedSupplyId", "planned_supply")}),
    ("pegging", Pegging, {"supply_ref": ("SupplyTransactionId", "material_transactions"), "demand_ref": ("DemandTransactionId", "material_transactions"),
                          "parent_ref": ("ParentPeggingId", "pegging")}),
    ("warnings", PlanWarning, {}),
]
SYSTEM_COLUMNS = {"Id", "PlanRunId", "UpdatedAt"}
REF = "ref"


class PlanRunPublished(Exception):
    """Yayınlanmış PlanRun'un çıktıları değişmez; yeniden hesap yeni PlanRun açar (K-70)."""

    message = "Bu plan yayınlanmış; çıktıları değiştirilemez. Yeniden hesap yeni bir plan hesabı açar."


class JobNoLongerOwned(Exception):
    """İş artık bu denemenin değil (geri alındı ya da sonlandırıldı); hiçbir şey yazılmadı."""


def is_published(session: Session, plan_run_id: int) -> bool:
    return session.execute(text("SELECT CASE WHEN EXISTS (SELECT 1 FROM planning.PlanVersion "
                                "WHERE PlanRunId = :id) THEN 1 ELSE 0 END"), {"id": plan_run_id}).scalar_one() == 1


def mark_running(session: Session, plan_run_id: int) -> None:
    if is_published(session, plan_run_id):
        raise PlanRunPublished()
    session.execute(text("UPDATE planning.PlanRun SET Status = :s, StartedAt = SYSUTCDATETIME(), EndedAt = NULL, "
                         "EngineUsed = NULL, Solver = NULL WHERE Id = :id"), {"s": RUN_RUNNING, "id": plan_run_id})
    session.commit()


def prepare(session: Session, plan_run_id: int) -> int:
    """Plan hesabı başlarken: önceki çıktılar silinir, talep kopyası kurulur (tek commit). Kopyalanan talep sayısı döner."""
    try:
        if is_published(session, plan_run_id):
            raise PlanRunPublished()
        _delete_outputs(session, plan_run_id)
        count = demand.copy(session, plan_run_id)
        session.commit()
    except Exception:
        session.rollback()
        raise
    return count


def _rows(table: sa.Table, rows: list[dict], plan_run_id: int, now, drop=(REF,)) -> list[dict]:
    allowed = {c.name for c in table.columns} - SYSTEM_COLUMNS
    dates = {c.name for c in table.columns if isinstance(c.type, sa.Date)}
    out = []
    for row in rows:
        values = {k: v for k, v in row.items() if k not in drop}
        unknown = set(values) - allowed
        if unknown:
            raise ValueError(f"{table.name}: bilinmeyen alan {', '.join(sorted(unknown))}")
        for k in dates & set(values):
            if isinstance(values[k], str):
                values[k] = date.fromisoformat(values[k])
        out.append({**values, "PlanRunId": plan_run_id, "UpdatedAt": now})
    return out


def _delete_outputs(session: Session, plan_run_id: int) -> None:
    """Motorun ve sistemin yazdığı çıktılar; talep kopyası (`PlannedDemand`) kalır, onu `prepare` yeniden kurar."""
    for _, table, _ in reversed(OUTPUTS):
        session.execute(sa.delete(table).where(table.c.PlanRunId == plan_run_id))
    session.execute(sa.delete(PlanMetric).where(PlanMetric.c.PlanRunId == plan_run_id))
    session.execute(sa.delete(SolverLog).where(SolverLog.c.PlanRunId == plan_run_id))


def _numbered(rows: list[dict]) -> list[dict]:
    """Tedarik planı numarası: motorun boş bıraktığı plan kaydına türüne göre sırayla ÜP-… ya da SP-… (plan hesabı içinde sıra)."""
    seq: dict[str, int] = {}
    out = []
    for row in rows:
        if not row.get("SupplyNo") and row.get("Source") == movements.SOURCE_PLAN and row.get("SupplyType") in movements.NUMBER_PREFIX:
            seq[row["SupplyType"]] = seq.get(row["SupplyType"], 0) + 1
            row = {**row, "SupplyNo": movements.supply_number(row["SupplyType"], seq[row["SupplyType"]])}
        out.append(row)
    return out


def _with_demand(session: Session, plan_run_id: int, rows: list[dict]) -> list[dict]:
    """Kırılım satırına talebin kimlik alanları kopyalanır; motor yalnız talebi, dönemi, miktarı ve gecikmeyi yazar."""
    if not rows:
        return rows
    found = session.execute(sa.select(PlannedDemand.c.Id, *(PlannedDemand.c[f] for f in demand.IDENTITY)).where(PlannedDemand.c.PlanRunId == plan_run_id)).mappings()
    demands = {r["Id"]: {f: r[f] for f in demand.IDENTITY} for r in found}
    out = []
    for row in rows:
        if row.get("PlannedDemandId") not in demands:
            raise ValueError(f"DemandFulfillment: bu plan hesabında olmayan talep {row.get('PlannedDemandId')}")
        out.append({**row, **demands[row["PlannedDemandId"]]})
    return out


def _fill_copies(session: Session, plan_run_id: int) -> None:
    """Bağdan kopyalanan alanlar: hareketin no'su tedarik planı kaydından ya da (talep hareketinde) karşılama satırının satış sipariş no'sundan, tahminde
    boş kalır; pegging'de iki tarafın alanları hareketlerden, kök talebin alanları talepten. Transfer hareketi pegging'e bağlanamaz (yalnız bakiye içindir)."""
    p = {"run": plan_run_id}
    session.execute(text("UPDATE t SET DocumentNo = s.SupplyNo FROM planning.MaterialTransaction t JOIN planning.PlannedSupply s ON s.Id = t.PlannedSupplyId "
                         "WHERE t.PlanRunId = :run AND t.DocumentNo IS NULL"), p)
    session.execute(text("UPDATE t SET DocumentNo = f.OrderNo FROM planning.MaterialTransaction t JOIN planning.DemandFulfillment f ON f.Id = t.DemandFulfillmentId "
                         "WHERE t.PlanRunId = :run AND t.DocumentNo IS NULL"), p)
    transfers = session.execute(text(
        "SELECT COUNT(*) FROM planning.Pegging g JOIN planning.MaterialTransaction a ON a.Id = g.SupplyTransactionId "
        "JOIN planning.MaterialTransaction b ON b.Id = g.DemandTransactionId WHERE g.PlanRunId = :run AND (a.MainMovement = :m OR b.MainMovement = :m)"),
        {**p, "m": movements.MAIN_TRANSFER}).scalar()
    if transfers:
        raise ValueError("Pegging: transfer hareketi bağlanamaz; arz tarafı gerçek arzın hareketidir (Genelden = Evet)")
    sides = ", ".join(f"{side}{f} = {alias}.{f}" for side, alias in (("Supply", "a"), ("Demand", "b"))
                      for f in ("MainMovement", "MovementType", "DocumentNo", "PeriodStart", "PeriodEnd", "MovementDate", "AllocationLevel", "AllocationKey"))
    session.execute(text(f"UPDATE g SET {sides} FROM planning.Pegging g JOIN planning.MaterialTransaction a ON a.Id = g.SupplyTransactionId "
                         "JOIN planning.MaterialTransaction b ON b.Id = g.DemandTransactionId WHERE g.PlanRunId = :run"), p)
    session.execute(text("UPDATE g SET RootDemandType = d.DemandType, RootOrderNo = d.OrderNo, RootLineNo = d.[LineNo], RootLineItemNo = d.LineItemNo, "
                         "RootCustomerId = d.CustomerId, RootProjectId = d.ProjectId FROM planning.Pegging g JOIN planning.PlannedDemand d ON d.Id = g.PlannedDemandId "
                         "WHERE g.PlanRunId = :run"), p)


def _insert(session: Session, attr: str, table: sa.Table, links: dict, source: list[dict], plan_run_id: int, now, refs: dict[str, dict]) -> dict:
    """Bir tablonun satırları. `ref` verilen satır tek tek yazılır (Id'si bağlar için gerekir), ötekiler toplu. Kendi tablosuna bağlanan satır
    (pegging'in üst bağı) kendinden önce yazılmış, `ref`'li bir satıra bağlanır."""
    own: dict = {}
    bulk = []
    for src in source:
        row = dict(src)
        for key, (column, target) in links.items():
            if key not in row:
                continue
            known = own if target == attr else refs.get(target, {})
            if row[key] not in known:
                raise ValueError(f"{table.name}: bilinmeyen bağ {key} = {row[key]}")
            row[column] = known[row.pop(key)]
        if REF in src:
            values = _rows(table, [row], plan_run_id, now)[0]
            own[src[REF]] = session.execute(sa.insert(table).values(**values).returning(table.c.Id)).scalar_one()
        else:
            bulk.append(row)
    if bulk:
        session.execute(sa.insert(table), _rows(table, bulk, plan_run_id, now))
    return own


def write_result(session: Session, plan_run_id: int, result: PlanResult, job_id: int, attempt: int) -> None:
    """Önceki çıktıları sil → yaz → talep özeti → PlanRun ve iş Bitti; tek commit. İş bu denemenin değilse hiçbir şey yazılmaz."""
    try:
        if is_published(session, plan_run_id):
            raise PlanRunPublished()
        now = queue.db_now(session)
        _delete_outputs(session, plan_run_id)

        refs: dict[str, dict] = {}
        for attr, table, links in OUTPUTS:
            rows = getattr(result, attr)
            if attr == "planned_supply":
                rows = _numbered(rows)
            elif attr == "demand_fulfillment":
                rows = _with_demand(session, plan_run_id, rows)
            refs[attr] = _insert(session, attr, table, links, rows, plan_run_id, now, refs)
        _fill_copies(session, plan_run_id)
        demand.summarize(session, plan_run_id)
        if result.metrics:
            session.execute(sa.insert(PlanMetric), [{"PlanRunId": plan_run_id, "MetricCode": k, "Value": v}
                                                    for k, v in result.metrics.items()])
        if result.solver_log:
            session.execute(sa.insert(SolverLog).values(PlanRunId=plan_run_id, **result.solver_log))

        session.execute(text("UPDATE planning.PlanRun SET Status = :s, EngineUsed = :e, Solver = :sv, "
                             "EndedAt = SYSUTCDATETIME() WHERE Id = :id"),
                        {"s": result.status, "e": result.engine_used, "sv": result.solver, "id": plan_run_id})
        if not queue.finish(session, job_id, attempt, progress="Tamamlandı", commit=False):
            raise JobNoLongerOwned()
        session.commit()
    except Exception:
        session.rollback()
        raise
    log.info("PlanRun %s yazıldı (iş %s, %s tedarik planı kaydı)", plan_run_id, job_id, len(result.planned_supply))


def write_failure(session: Session, plan_run_id: int | None, job_id: int, attempt: int, message: str) -> bool:
    """PlanRun Hata + iş Hata, tek commit. İş bu denemenin değilse hiçbir şey yazılmaz (False)."""
    try:
        if plan_run_id is not None and not is_published(session, plan_run_id):
            session.execute(text("UPDATE planning.PlanRun SET Status = :s, EndedAt = SYSUTCDATETIME() WHERE Id = :id"),
                            {"s": RUN_FAILED, "id": plan_run_id})
        if not queue.fail(session, job_id, attempt, message, commit=False):
            session.rollback()
            return False
        session.commit()
    except Exception:
        session.rollback()
        raise
    log.warning("PlanRun %s hata (iş %s): %s", plan_run_id, job_id, message)
    return True
