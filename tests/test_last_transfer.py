"""Veri yükleme tablosunda "Son aktarım" ve "Yeni veri" (ekran 02; K-151, K-158): tablonun yazıldığı son aktarım (tablonun yazılmadığı aktarım ve
sentetik yükleme sayılmaz); son aktarımdan sonra gelen veriye alınmış yükleme "Yeni veri". Aynı oturumda yazılıp geri alınır (K-103)."""
from datetime import datetime, timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.api.lists.data_entities import SOURCE

pytestmark = pytest.mark.db
T0 = datetime(2030, 1, 1, 8, 0)


def state(s, entity="Customer") -> tuple:
    row = s.execute(sa.select(SOURCE.c.LastTransferAt, SOURCE.c.LastTransferType, SOURCE.c.HasNewData).where(SOURCE.c.Entity == entity)).one()
    return tuple(row)


def batch(s, at: datetime, status="Alındı", entity="Customer") -> None:
    s.execute(sa.text("INSERT INTO adm.ImportBatch (Method, EntityName, LoadType, ReceivedAt, Status) VALUES (N'Excel', :e, N'Tam', :at, :st)"),
              {"e": entity, "at": at, "st": status})


def version(s, at: datetime, load_type: str, new_count: int | None, synthetic=False, entity="Customer") -> None:
    vid = s.execute(sa.text("INSERT INTO adm.DataVersion (CreatedAt, LoadType, IsPinned, IsSynthetic) OUTPUT inserted.Id VALUES (:at, :lt, 0, :syn)"),
                    {"at": at, "lt": load_type, "syn": synthetic}).scalar()
    s.execute(sa.text("INSERT INTO adm.DataVersionEntity (DataVersionId, EntityName, NewCount, Note) VALUES (:v, :e, :n, :note)"),
              {"v": vid, "e": entity, "n": new_count, "note": None if new_count is not None else "Veri gelmedi; mevcut veri korunur."})


@pytest.fixture
def s(db_engine):
    with Session(db_engine) as session:
        session.execute(sa.text("DELETE FROM adm.ImportBatch WHERE EntityName = N'Customer'"))   # geri alınır
        session.execute(sa.text("DELETE dve FROM adm.DataVersionEntity dve JOIN adm.DataVersion v ON v.Id = dve.DataVersionId "
                                "WHERE dve.EntityName = N'Customer' AND ISNULL(v.IsSynthetic, 0) = 0"))
        yield session
        session.rollback()


def test_no_data_no_transfer(s):
    assert state(s) == (None, None, False)


def test_loaded_but_never_transferred_is_new_data(s):
    batch(s, T0)
    version(s, T0 + timedelta(hours=1), "Tam", None)                       # tablo yazılmadı (veri gelmedi notu): aktarım sayılmaz
    version(s, T0 + timedelta(hours=2), "Tam", 3, synthetic=True)           # sentetik yükleme aktarım değildir
    assert state(s) == (None, None, True)


def test_last_written_transfer_and_new_data_after_it(s):
    batch(s, T0)
    version(s, T0 + timedelta(hours=1), "Tam", 5)
    version(s, T0 + timedelta(hours=2), "Kısmi", 0)                          # yazıldı, değişiklik yok: yine aktarım
    version(s, T0 + timedelta(hours=3), "Tam", None)                         # eşik aşıldı: sayılmaz
    assert state(s) == (T0 + timedelta(hours=2), "Kısmi", False)
    batch(s, T0 + timedelta(hours=4), status="Ön kontrol")                   # henüz alınmadı: yeni veri değil
    assert state(s)[2] is False
    batch(s, T0 + timedelta(hours=4))
    assert state(s) == (T0 + timedelta(hours=2), "Kısmi", True)
