"""Veri kuralları performansı (K-140, K-141): 200.000 satırlık Malzeme'de işlenmiş katmanın kurulması ve beş kural. Ortanca ölçüm.

Satırlar doğrudan ham katmana, güncel hâlde yazılır. Kurallar: sabit (Yalnız boşsa), alan kopyası, sayı formülü, bölen alan
(bazı satırlarda sıfır) ve koşullu bayrak. Ayrıca: pytest -m perf.
"""
import statistics
import time

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.validation import processed, rules_step
from app.validation.engine import utcnow

from test_validation_perf import fill
from validation_helpers import clean

pytestmark = [pytest.mark.db, pytest.mark.perf]

ROWS = 200_000
RUNS = 3
LIMIT_SECONDS = 120
RULES = [
    ("Minimum lot", "MinLot", "Değer", dict(Value="1"), "Yalnız boşsa", None),
    ("Kutu kopya", "QtyPerPallet", "Alan", dict(SourceField="QtyPerBox"), "Her zaman", None),
    ("Güvenlik", "SafetyStock", "Formül", dict(SourceField="MaxStock", FormulaOperator="×", OperandValue="0.5"), "Her zaman", None),
    ("Bölüm", "AdditionalNumber1", "Formül", dict(SourceField="MaxLot", FormulaOperator="÷", OperandField="LotMultiple"), "Her zaman", None),
    ("Kritik", "IsCritical", "Değer", dict(Value="1"), "Her zaman", ("IsPurchasable", "=", "1")),
]


@pytest.fixture(scope="module")
def big(db_engine):
    clean(db_engine)
    fill(db_engine, "Material", ROWS)
    with db_engine.begin() as c:
        c.execute(sa.text("UPDATE stg.Material SET LotMultiple = 0 WHERE StagingRowId % 50 = 0"))  # bölen sıfır: hücre değişmez
        for seq, (name, target, kind, extra, mode, cond) in enumerate(RULES, 1):
            rid = c.execute(sa.insert(rules_step.RULE).values(EntityName="Material", Name=name, Seq=seq, TargetField=target, ResultKind=kind, ApplyMode=mode,
                                                              IsActive=True, UpdatedAt=utcnow(), **extra).returning(rules_step.RULE.c.Id)).scalar_one()
            if cond:
                c.execute(sa.insert(rules_step.CONDITION).values(DataRuleId=rid, GroupNo=1, FieldName=cond[0], Operator=cond[1], Value=cond[2]))
    yield db_engine
    clean(db_engine)


def test_rebuild_and_five_rules_200k(big):
    copy_times, total_times = [], []
    for _ in range(RUNS):
        with Session(big) as s:
            start = time.perf_counter()
            processed.rebuild(s, "Material")
            s.commit()
            copy_times.append(time.perf_counter() - start)
        with Session(big) as s:
            start = time.perf_counter()
            ran = rules_step.run(s, "Material")
            total_times.append(time.perf_counter() - start)
    copy, total = statistics.median(copy_times), statistics.median(total_times)
    print(f"\nMalzeme {ROWS:,} satır: işlenmiş katman kopyası ortanca {copy:.1f} sn ({', '.join(f'{t:.1f}' for t in copy_times)}); "
          f"kopya + 5 kural ortanca {total:.1f} sn ({', '.join(f'{t:.1f}' for t in total_times)})")
    assert ran == len(RULES)
    with big.connect() as c:
        assert c.execute(sa.text("SELECT COUNT(*) FROM prc.Material")).scalar() == ROWS
        assert c.execute(sa.text("SELECT COUNT(*) FROM prc.Material WHERE LotMultiple = 0 AND AdditionalNumber1 IS NOT NULL")).scalar() == 0
    assert total < LIMIT_SECONDS
