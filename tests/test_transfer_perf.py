"""Tam ve kısmi aktarım performansı (K-153, K-155): 25 tablo × 50.000 satır; ilk aktarım (hepsi yeni) ve hemen ardından ikinci aktarım (hepsi değişmeyen); kısmi aktarım (Talep, Stok).

Satırlar doğrudan ham katmana yazılır (validasyon ölçülmez), işlenmiş katman kurulur. Her ölçüm aynı işlemde yapılıp geri alınır; ortanca.
Ayrıca: pytest -m perf -k transfer (kısmi: -k partial).
"""
import statistics
import time

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.integration.contract import ENTITIES
from app.transfer import engine as transfer
from app.validation import processed

from test_validation_perf import PARALLEL_ROWS, fill
from validation_helpers import clean

pytestmark = [pytest.mark.db, pytest.mark.perf]

RUNS = 3
LIMIT_SECONDS = 1800


@pytest.fixture(scope="module")
def big(db_engine):
    clean(db_engine)
    for e in ENTITIES:
        fill(db_engine, e.table, PARALLEL_ROWS, linked=True)
    with Session(db_engine) as s:
        for e in ENTITIES:
            processed.rebuild(s, e.table)
        s.commit()
    yield db_engine
    clean(db_engine)


def test_transfer_50k(big):
    first, second, counts = [], [], {}
    for _ in range(RUNS):
        with Session(big) as s:
            start = time.perf_counter()
            r1 = transfer.run_transfer(s, None)
            first.append(time.perf_counter() - start)
            start = time.perf_counter()
            r2 = transfer.run_transfer(s, None)
            second.append(time.perf_counter() - start)
            counts = {"new": sum(t["new"] or 0 for t in r1["tables"]), "not": sum(t["not_transferred"] or 0 for t in r1["tables"]),
                      "changed2": sum(t["changed"] or 0 for t in r2["tables"]), "new2": sum(t["new"] or 0 for t in r2["tables"])}
            s.rollback()
    m1, m2 = statistics.median(first), statistics.median(second)
    print(f"\nTam aktarım, {len(ENTITIES)} tablo × {PARALLEL_ROWS:,} satır: ilk ortanca {m1:.1f} sn ({', '.join(f'{t:.1f}' for t in first)}), "
          f"ikinci ortanca {m2:.1f} sn ({', '.join(f'{t:.1f}' for t in second)}); yeni {counts['new']:,}, aktarılmayan {counts['not']:,}, "
          f"ikincide değişen {counts['changed2']:,}, yeni {counts['new2']:,}")
    assert counts["new"] > 0 and counts["changed2"] == 0 and counts["new2"] == 0
    assert m1 < LIMIT_SECONDS


def test_partial_transfer_50k(big):
    """Kısmi aktarım (K-155), Talep ve Stok grupları: önce bir tam aktarım (ölçülmez), sonra aynı oturumda kısmi aktarım üç kez; ortanca."""
    groups = ["Talep", "Stok"]
    times, counts = [], {}
    with Session(big) as s:
        transfer.run_transfer(s, None)
        for _ in range(RUNS):
            start = time.perf_counter()
            r = transfer.run_transfer(s, None, groups=groups)
            times.append(time.perf_counter() - start)
            counts = {"tables": len(r["tables"]), "changed": sum(t["changed"] or 0 for t in r["tables"]),
                      "not": sum(t["not_transferred"] or 0 for t in r["tables"])}
        s.rollback()
    m = statistics.median(times)
    print(f"\nKısmi aktarım ({', '.join(groups)}; {counts['tables']} tablo × {PARALLEL_ROWS:,} satır): ortanca {m:.1f} sn "
          f"({', '.join(f'{t:.1f}' for t in times)}); değişen {counts['changed']:,}, aktarılmayan {counts['not']:,}")
    assert counts["tables"] == 6 and counts["changed"] == 0
    assert m < LIMIT_SECONDS
