"""Türetme performans hedefi (K-205 S-13): 500 bin malzeme hareketi ve 100 bin kapasite yükü satırının türetilmesi ortancada 60 sn altında.

Fikstürün "Baz · güncel" planı işlem içinde çoğaltılır (tedarik planı ve karşılama satırları kopyalanır; stok ve sipariş satırları sabit kalır), türetme
üç kez ölçülür, ortanca alınır; işlem sonunda geri alınır. Varsayılan koşuda çalışmaz: `pytest -m perf` (tam ölçüm istekle).
"""
import statistics
import time

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.data.synthetic import plan
from app.planning import derive

pytestmark = [pytest.mark.db, pytest.mark.perf]
TARGET_SECONDS = 60
MIN_TRANSACTIONS, MIN_LOADS = 500_000, 100_000


def test_derivation_at_scale(db_engine):
    with Session(db_engine) as s:
        try:
            base = s.execute(sa.text("SELECT TOP 1 r.Id FROM planning.PlanRun r JOIN param.ScenarioDefinition sd ON sd.Id = r.ScenarioDefinitionId "
                                     "WHERE r.Solver = :s AND sd.IsBase = 1 ORDER BY r.Id"), {"s": plan.SOLVER}).scalar()
            assert base, "test veritabanında plan fikstürü bekleniyor (python -m app.data.synthetic plan)"
            per_copy = s.execute(sa.text("SELECT COUNT(*) FROM planning.MaterialTransaction WHERE PlanRunId = :r"), {"r": base}).scalar()
            copies = MIN_TRANSACTIONS // per_copy + 1
            run = s.execute(sa.text("INSERT INTO planning.PlanRun (DataVersionId, ScenarioDefinitionId, Status) OUTPUT inserted.Id "
                                    "SELECT DataVersionId, ScenarioDefinitionId, N'Sırada' FROM planning.PlanRun WHERE Id = :r"), {"r": base}).scalar_one()
            cols = [c for c in sa.inspect(s.connection()).get_columns("PlannedSupply", schema="planning") if c["name"] not in ("Id", "PlanRunId")]
            names = ", ".join(f"[{c['name']}]" for c in cols)
            s.execute(sa.text(f"INSERT INTO planning.PlannedSupply (PlanRunId, {names}) SELECT :run, {names} FROM planning.PlannedSupply p "
                              f"CROSS JOIN (SELECT TOP ({copies}) 1 AS x FROM sys.all_objects) n WHERE p.PlanRunId = :r"), {"run": run, "r": base})
            cols = [c for c in sa.inspect(s.connection()).get_columns("DemandFulfillment", schema="planning") if c["name"] not in ("Id", "PlanRunId")]
            names = ", ".join(f"[{c['name']}]" for c in cols)
            s.execute(sa.text(f"INSERT INTO planning.DemandFulfillment (PlanRunId, {names}) SELECT :run, {names} FROM planning.DemandFulfillment f "
                              f"CROSS JOIN (SELECT TOP ({copies}) 1 AS x FROM sys.all_objects) n WHERE f.PlanRunId = :r"), {"run": run, "r": base})
            times = []
            for _ in range(3):
                start = time.perf_counter()
                out = derive.derive(s, run)
                times.append(time.perf_counter() - start)
            moves, loads = sum(out["MaterialTransaction"].values()), sum(out["CapacityLoad"].values())
            median = statistics.median(times)
            print(f"\n  türetme: {moves} hareket, {loads} yük · ortanca {median:.1f} sn ({', '.join(f'{t:.1f}' for t in times)})")
            assert moves >= MIN_TRANSACTIONS and loads >= MIN_LOADS
            assert median < TARGET_SECONDS
        finally:
            s.rollback()
