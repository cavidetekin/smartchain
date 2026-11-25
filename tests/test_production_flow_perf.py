"""Üretim akışı uçlarının performans ölçümü (K-200, docs/08): yaklaşık 10.000 malzeme, 16 seviye, 30.000 ağaç satırı (alokasyon kuralı ölçümünün
ağacı) ve 2.000 yerde kullanılan bir malzeme (cıvata örneği). Ölçülen: pencerenin bir + basışında sunucuda geçen süre (servis çağrısı; ağ hariç).

Hedef: bir + basışında ortanca ≤ 200 ms (kutu, kullandıkları, kullananların ilk 20'si; çok kullanılan malzemede de). "+N malzeme" adımı (sonraki 200)
çok kullanılan malzemede ölçülür ve yazdırılır; hedefe bağlanması karar bekliyor (ölçüm 265–470 ms; docs/08). Veri bir işlem içinde üretilir, ölçülür ve
geri alınır; iz kalmaz."""
import statistics
import time

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.services import production_flow as flow

from test_allocation_rules_perf import FAMILIES, LEVELS, generate, node

pytestmark = [pytest.mark.db, pytest.mark.perf]

TARGET_MS = 200.0
WIDE = 2_000          # çok kullanılan malzemeyi kullanan üst malzeme sayısı
SAMPLES = 40


def _measure(call, args: list) -> dict:
    times = []
    for a in args:
        t0 = time.perf_counter()
        call(a)
        times.append((time.perf_counter() - t0) * 1000)
    return {"median": round(statistics.median(times), 1), "max": round(max(times), 1), "n": len(times)}


def test_production_flow_at_scale(db_engine, capsys):
    with Session(db_engine) as s:
        try:
            size = generate(s)
            bolt = node(0, LEVELS, 0)          # en alt seviyeden bir malzeme: 2.000 üst malzemenin ağacına eklenir
            s.execute(text(
                "INSERT INTO core.BOM (Id, LocationId, MaterialId, Code, ComponentMaterialId, OperationNo, SequenceNo, Quantity, VersionFrom, BusinessKey, UpdatedAt) "
                f"SELECT TOP ({WIDE}) 9500000 + ROW_NUMBER() OVER (ORDER BY pv.MaterialId), pv.LocationId, pv.MaterialId, pv.BOMCode, :c, 90, 1, 4, :v, "
                "CONCAT('PERF-BOLT-', pv.MaterialId), SYSUTCDATETIME() FROM core.ProductionVersion pv WHERE pv.LocationId = :l AND pv.MaterialId <> :c "
                "AND NOT EXISTS (SELECT 1 FROM core.BOM b WHERE b.LocationId = pv.LocationId AND b.MaterialId = pv.MaterialId AND b.Code = pv.BOMCode AND b.ComponentMaterialId = :c) "
                "ORDER BY pv.MaterialId"), {"c": bolt, "v": size["version"], "l": size["location"]})
            # farklı seviyelerden malzemeler (ilk çağrı ısınmadır, ölçüye girmez)
            sample = [node(f * 7, lv, f) for f in range(SAMPLES // 4) for lv in (0, 4, 9, LEVELS - 1)]
            flow.components(s, sample[0]), flow.parents(s, sample[1], 0, 20), flow.read(s, sample[0])
            result = {
                "kutu (GET /{id})": _measure(lambda m: flow.read(s, m), sample),
                "kullandıkları (components)": _measure(lambda m: flow.components(s, m), sample),
                "kullananlar (parents, ilk 20)": _measure(lambda m: flow.parents(s, m, 0, 20), [m for m in sample if m != node(m // 100, 0)]),
                f"çok kullanılan: {WIDE} kullanan, ilk 20": _measure(lambda _: flow.parents(s, bolt, 0, 20), list(range(10))),
                f"çok kullanılan: {WIDE} kullanan, sonraki 200": _measure(lambda o: flow.parents(s, bolt, o, 200), [20 + 200 * i for i in range(8)]),
            }
            wide = flow.parents(s, bolt, 0, 20)
            deep = flow.components(s, node(3, 5, 2))
        finally:
            s.rollback()
    with capsys.disabled():
        print(f"\nÜretim akışı · {size['materials']} malzeme, {size['bom'] + WIDE} ağaç satırı, {FAMILIES} aile × {LEVELS + 1} seviye")
        for name, r in result.items():
            print(f"  {name:<46} ortanca {r['median']:>7} ms · en uzun {r['max']:>7} ms · {r['n']} çağrı")
    assert wide["total"] >= WIDE and len(wide["items"]) == 20 and all(i["uses"] for i in wide["items"])
    assert len(deep["alternatives"]) == 1 and len(deep["alternatives"][0]["items"]) >= 3
    slow = {name: r["median"] for name, r in result.items() if r["median"] > TARGET_MS and "sonraki 200" not in name}
    assert not slow, f"hedef {TARGET_MS} ms aşıldı: {slow}"
