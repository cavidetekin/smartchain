"""Validasyon işinde kilitlenme (K-181): birlikte koşan işlerde SQL Server kurban seçtiği işlemi geri alır (1205); iş düşmez, baştan koşar.
Veritabanısız: yeniden deneme mantığı sahte hatayla."""
import pytest
from sqlalchemy.exc import DBAPIError, OperationalError

from app.validation import engine

DEADLOCK = ("40001", "[40001] [Microsoft][ODBC Driver 18 for SQL Server][SQL Server]Transaction (Process ID 89) was deadlocked on lock resources "
            "with another process and has been chosen as the deadlock victim. Rerun the transaction. (1205) (SQLExecDirectW)")


class FakeSession:
    def __init__(self):
        self.rollbacks = 0

    def rollback(self):
        self.rollbacks += 1


def _error(args, cls=DBAPIError):
    return cls("UPDATE prc.[Stock] SET [RowStatus]=?", (), Exception(*args))


def _work(failures: list):
    calls = []

    def work():
        calls.append(1)
        if failures:
            raise failures.pop(0)
        return "bitti"
    return work, calls


def test_deadlock_victim_is_rolled_back_and_rerun():
    session, pauses = FakeSession(), []
    work, calls = _work([_error(DEADLOCK), _error(DEADLOCK, OperationalError)])
    assert engine._with_deadlock_retry(session, work, pauses.append) == "bitti"
    assert (len(calls), session.rollbacks, len(pauses)) == (3, 2, 2) and pauses[0] < pauses[1] * 4 and all(p > 0 for p in pauses)


def test_other_errors_and_exhausted_retries_fail_the_job():
    session = FakeSession()
    work, calls = _work([_error(("42S22", "Invalid column name 'X'. (207)"))])
    with pytest.raises(DBAPIError):
        engine._with_deadlock_retry(session, work, lambda _s: None)
    assert (len(calls), session.rollbacks) == (1, 0)  # kilitlenme değil: yeniden denenmez
    work, calls = _work([_error(DEADLOCK) for _ in range(engine.DEADLOCK_RETRIES)])
    with pytest.raises(DBAPIError):
        engine._with_deadlock_retry(session, work, lambda _s: None)
    assert len(calls) == engine.DEADLOCK_RETRIES and session.rollbacks == engine.DEADLOCK_RETRIES - 1
    assert engine.is_deadlock(_error(DEADLOCK)) and not engine.is_deadlock(ValueError("x"))
