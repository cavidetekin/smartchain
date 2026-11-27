"""Plan çıktılarının tutarlılık denetimleri (K-205): fikstür yüklenirken, testlerde ve ileride motor çıktısında aynı işlev çağrılır (Aşama 10).

`problems(session, plan_run_id)` boş liste dönerse plan tutarlıdır. Denetimler:
- Bakiye: malzeme × lokasyon × alokasyon anahtarı için dönem dönem birikimli bakiye hiçbir dönemde eksiye düşmez (transfer genelden özele taşır).
- Talep: talep başına karşılama toplamı ≤ talep miktarı; plana dahil talepte özet alanları kırılımla aynı; her karşılama satırının bir − Talep hareketi var.
- Arz: plana dahil tedarik planı kaydı başına bir + hareketi, miktarı Miktar (satın almada Yuvarlanmış miktar).
- Yük: Kapasite kullanımı = Üretim adedi × Birim kullanım; ek mesai ≤ ek mesai limiti; aşım olan her grup × dönemde CAP_OVERLOAD uyarısı.
- Pegging: iki taraf aynı malzeme ve lokasyon; hareket başına bağlanan toplam ≤ hareket miktarı; transfer hareketi yok; Genelden = Evet ise arzın
  anahtarı boş, ihtiyacınki dolu; üst bağın seviyesi bir eksik; kök talep alanları talepten.
- Uyarı: geç kalan siparişin ORDER_LATE, karşılanmayan siparişin ORDER_UNMET, karşılanmayan tahminin FORECAST_UNMET uyarısı var; uyarılar dönemle ve ilgili kayıtla (K-206) eşlenir, mesaj metniyle değil.
"""
from collections import defaultdict
from datetime import date

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.params import catalog as cat

from . import capacity_view, movements as mv

TOL = 0.001
ORDER_TYPES = tuple(t for t in cat.DEMAND_TYPES if t != cat.DEMAND_FORECAST)


def _rows(session: Session, sql: str, run: int) -> list:
    return session.execute(sa.text(sql), {"run": run}).all()


def problems(session: Session, plan_run_id: int, today: date | None = None, limit: int = 20) -> list[dict]:
    out: list[dict] = []

    def add(check: str, detail: str) -> None:
        if sum(1 for p in out if p["check"] == check) < limit:
            out.append({"check": check, "detail": detail})

    run = plan_run_id
    # bakiye
    balance: dict[tuple, float] = defaultdict(float)
    for m, loc, key, start, signed in _rows(session, "SELECT MaterialId, LocationId, AllocationKey, PeriodStart, "
                                            f"SUM(CASE WHEN Direction = N'{mv.PLUS}' THEN Quantity ELSE -Quantity END) FROM planning.MaterialTransaction "
                                            "WHERE PlanRunId = :run GROUP BY MaterialId, LocationId, AllocationKey, PeriodStart "
                                            "ORDER BY MaterialId, LocationId, AllocationKey, PeriodStart", run):
        k = (m, loc, key)
        balance[k] += float(signed)
        if balance[k] < -TOL:
            add("Bakiye", f"malzeme {m}, anahtar {key or 'genel'}, {start}: bakiye {balance[k]:.3f}")

    # talep
    for d, q, f, t, late, unmet, included, s in _rows(session, """
            SELECT d.Id, d.DemandQuantity, d.FulfilledQuantity, d.OnTimeQuantity, d.LateQuantity, d.UnmetQuantity, d.IsIncluded, x.s
            FROM planning.PlannedDemand d OUTER APPLY (SELECT SUM(f.Quantity) AS s FROM planning.DemandFulfillment f WHERE f.PlannedDemandId = d.Id) x
            WHERE d.PlanRunId = :run""", run):
        s = float(s or 0)
        if s > float(q) + TOL:
            add("Talep", f"talep {d}: karşılama {s} > talep {q}")
        if included and (abs(float(f or 0) - s) > TOL or abs(float(t or 0) + float(late or 0) - s) > TOL or abs(float(unmet or 0) - max(0.0, float(q) - s)) > TOL):
            add("Talep özeti", f"talep {d}: özet alanları kırılımla uyuşmuyor")
        if not included and s > TOL:
            add("Talep", f"talep {d}: plana dahil değil ama karşılanmış")
    for (fid,) in _rows(session, "SELECT f.Id FROM planning.DemandFulfillment f WHERE f.PlanRunId = :run AND NOT EXISTS (SELECT 1 FROM planning.MaterialTransaction t "
                        "WHERE t.DemandFulfillmentId = f.Id AND t.Direction = N'-' AND ABS(t.Quantity - f.Quantity) < 0.001)", run):
        add("Talep hareketi", f"karşılama {fid}: − Talep hareketi yok")

    # arz
    for sid, no in _rows(session, f"""
            SELECT s.Id, s.SupplyNo FROM planning.PlannedSupply s WHERE s.PlanRunId = :run AND s.IsIncluded = 1 AND s.Quantity > 0 AND
            (SELECT COUNT(*) FROM planning.MaterialTransaction t WHERE t.PlannedSupplyId = s.Id AND t.Direction = N'{mv.PLUS}'
             AND ABS(t.Quantity - CASE WHEN s.SupplyType = N'{mv.SUPPLY_PURCHASE}' THEN COALESCE(s.RoundedQuantity, s.Quantity) ELSE s.Quantity END) < 0.001) <> 1""", run):
        add("Arz", f"tedarik planı {no}: + hareketi yok ya da miktarı farklı")

    # yük ve ek mesai
    for (lid,) in _rows(session, "SELECT Id FROM planning.CapacityLoad WHERE PlanRunId = :run AND ABS(CapacityUsage - ProductionQuantity * ISNULL(UnitUsage, 0)) > 0.01", run):
        add("Yük", f"yük satırı {lid}: Kapasite kullanımı ≠ Üretim adedi × Birim kullanım")
    overloaded = set()
    for g in capacity_view.group_periods(session, run, today):
        if g["Overtime"] > g["OvertimeLimit"] + TOL:
            add("Ek mesai", f"{g['Code']} {g['PeriodStart']}: ek mesai {g['Overtime']:.2f} > limit {g['OvertimeLimit']:.2f}")
        if g["Overload"] > capacity_view.EPS:
            overloaded.add((g["ResourceGroupId"], g["PeriodStart"]))
    # CAP_OVERLOAD uyarısı kaynak grubunu ve dönemini kendi alanlarında taşır (K-206)
    warned = {(g, s) for g, s in _rows(session, "SELECT ResourceGroupId, PeriodStart FROM planning.PlanWarning WHERE PlanRunId = :run "
                                                "AND WarningCode = N'CAP_OVERLOAD'", run)}
    for gid, start in sorted(overloaded - warned):
        add("Uyarı", f"kaynak grubu {gid} {start}: aşım var, CAP_OVERLOAD uyarısı yok")

    # pegging
    for gid, why in _rows(session, f"""
            SELECT g.Id, CASE
                WHEN a.MaterialId <> g.MaterialId OR b.MaterialId <> g.MaterialId OR a.LocationId <> b.LocationId THEN N'malzeme ya da lokasyon farklı'
                WHEN a.Direction <> N'{mv.PLUS}' OR b.Direction <> N'{mv.MINUS}' THEN N'yön yanlış'
                WHEN a.MainMovement = N'{mv.MAIN_TRANSFER}' OR b.MainMovement = N'{mv.MAIN_TRANSFER}' THEN N'transfer hareketi bağlanmış'
                WHEN g.IsFromGeneral = 1 AND (a.AllocationKey IS NOT NULL OR b.AllocationKey IS NULL) THEN N'Genelden: arz genel, ihtiyaç anahtarlı olmalı'
                WHEN g.ParentPeggingId IS NOT NULL AND (u.[Level] IS NULL OR g.[Level] <> u.[Level] + 1) THEN N'seviye üst bağla uyuşmuyor'
                WHEN g.PlannedDemandId IS NOT NULL AND (ISNULL(g.RootDemandType, N'') <> d.DemandType OR ISNULL(g.RootOrderNo, N'') <> ISNULL(d.OrderNo, N''))
                    THEN N'kök talep alanları farklı'
                END
            FROM planning.Pegging g JOIN planning.MaterialTransaction a ON a.Id = g.SupplyTransactionId JOIN planning.MaterialTransaction b ON b.Id = g.DemandTransactionId
            LEFT JOIN planning.Pegging u ON u.Id = g.ParentPeggingId LEFT JOIN planning.PlannedDemand d ON d.Id = g.PlannedDemandId
            WHERE g.PlanRunId = :run""", run):
        if why:
            add("Pegging", f"pegging {gid}: {why}")
    for tid, side, total, qty in _rows(session, """
            SELECT x.TransactionId, x.Side, SUM(x.Quantity), MAX(t.Quantity) FROM (
                SELECT SupplyTransactionId AS TransactionId, N'arz' AS Side, Quantity FROM planning.Pegging WHERE PlanRunId = :run
                UNION ALL SELECT DemandTransactionId, N'ihtiyaç', Quantity FROM planning.Pegging WHERE PlanRunId = :run) x
            JOIN planning.MaterialTransaction t ON t.Id = x.TransactionId GROUP BY x.TransactionId, x.Side""", run):
        if float(total) > float(qty) + TOL:
            add("Pegging miktarı", f"hareket {tid} ({side}): bağlanan {float(total):.3f} > miktar {float(qty):.3f}")

    # uyarı
    codes = {(code, did) for code, did in _rows(session, "SELECT WarningCode, PlannedDemandId FROM planning.PlanWarning WHERE PlanRunId = :run", run)}
    order_types = ", ".join(f"N'{t}'" for t in ORDER_TYPES)
    for code, oid, what in _rows(session, f"""
            SELECT N'ORDER_LATE', Id, OrderNo FROM planning.PlannedDemand WHERE PlanRunId = :run AND LateQuantity > 0.001 AND DemandType IN ({order_types})
            UNION ALL SELECT N'ORDER_UNMET', Id, OrderNo FROM planning.PlannedDemand WHERE PlanRunId = :run AND UnmetQuantity > 0.001
                AND DemandType IN ({order_types})
            UNION ALL SELECT N'FORECAST_UNMET', Id, NULL FROM planning.PlannedDemand WHERE PlanRunId = :run AND UnmetQuantity > 0.001
                AND DemandType = N'{cat.DEMAND_FORECAST}'""", run):
        if (code, oid) not in codes:
            add("Uyarı", f"{what or oid}: {code} uyarısı yok")
    return out
