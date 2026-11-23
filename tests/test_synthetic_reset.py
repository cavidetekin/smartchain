"""Geliştirme veritabanının sıfırlanması (K-79, K-153): aktarımlar geri alınır, kapatılan sentetik satırlar açılır, sentetik veri yeniden yüklenir;
onay yoksa ya da koruma koşulu tutmazsa hiçbir şey değişmez. Test veritabanında (K-103)."""
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.data.synthetic.dataset import generate
from app.data.synthetic.load import ResetRefused, reset
from app.transfer import engine as transfer

from test_validation_references import put
from validation_helpers import clean

pytestmark = pytest.mark.db


def counts(engine) -> dict:
    with engine.connect() as c:
        q = lambda sql: c.execute(sa.text(sql)).scalar()  # noqa: E731
        return {"real_versions": q("SELECT COUNT(*) FROM adm.DataVersion WHERE ISNULL(IsSynthetic, 0) = 0"),
                "customers": q("SELECT COUNT(*) FROM core.Customer WHERE VersionTo IS NULL"),
                "closed": q("SELECT COUNT(*) FROM core.Customer WHERE VersionTo IS NOT NULL"),
                "rs": q("SELECT COUNT(*) FROM core.Customer WHERE Code = N'RS-1'")}


@pytest.fixture
def transferred(db_engine):
    """Yalnız Müşteri staging'de: aktarım sentetik müşterileri kapatır, RS-1'i ekler (commit)."""
    clean(db_engine)
    before = counts(db_engine)
    put(db_engine, {"Customer": [{"Code": "RS-1", "Name": "Sıfırlama", "IsActive": 1}]})
    with Session(db_engine) as s:
        transfer.run_transfer(s, None)
        s.commit()
    yield db_engine, before
    clean(db_engine)


def test_reset_removes_transfers_and_reopens_synthetic_rows(transferred):
    eng, before = transferred
    after_transfer = counts(eng)
    assert after_transfer["real_versions"] == 1 and after_transfer["rs"] == 1 and after_transfer["closed"] > 0
    seen = {}
    result = reset(eng, generate(), lambda preview: seen.update(preview) or True)
    assert seen["rows"] >= 1 and len(seen["versions"]) == 1 and result["removed_transfers"] == seen["versions"]
    assert counts(eng) == {**before, "real_versions": 0, "rs": 0, "closed": 0}


def test_reset_removes_records_bound_to_real_locations(transferred):
    """Sentetik olmayan lokasyona bağlı fabrika takvimi, tedarikçi limiti ve malzeme blokajı kayıtları lokasyonla birlikte silinir (K-194): geçiş 0073
    çok lokasyonlu veritabanında takvim kayıtlarını her lokasyona kopyalar; sıfırlama o kopyalar yüzünden durmaz. Sentetik lokasyonun kayıtları kalır."""
    eng, _ = transferred
    bound = ("FactoryCalendar", "SupplierLimit", "MaterialHold")

    def rows(conn) -> dict:
        return {t: conn.execute(sa.text(f"SELECT COUNT(*) FROM param.[{t}] x JOIN core.Location l ON l.Id = x.LocationId WHERE ISNULL(l.IsSynthetic, 0) = 0")).scalar() for t in bound}

    with eng.begin() as c:
        base = c.execute(sa.text("SELECT Id FROM param.ScenarioDefinition WHERE IsBase = 1")).scalar_one()
        kept = {t: c.execute(sa.text(f"SELECT COUNT(*) FROM param.[{t}] WHERE ScenarioDefinitionId = :b"), {"b": base}).scalar() for t in bound}
        loc = c.execute(sa.text("INSERT INTO core.Location (Code, Name, IsActive, IsSynthetic) OUTPUT inserted.Id VALUES (N'RS-LOC-1', N'Sıfırlama lokasyonu', 1, 0)")).scalar_one()
        p = {"b": base, "l": loc}
        c.execute(sa.text("INSERT INTO param.FactoryCalendar (ScenarioDefinitionId, IsValid, LocationId, StartDate, EndDate, Name, DayValue, UpdatedAt) "
                          "VALUES (:b, 1, :l, '20270101', '20270101', N'pytest kopya', 0, SYSUTCDATETIME())"), p)
        c.execute(sa.text("INSERT INTO param.SupplierLimit (ScenarioDefinitionId, IsValid, LimitType, LocationId, SupplierId, MaterialId, ValidFrom, UpperLimit, LimitPeriod, UpdatedAt) "
                          "VALUES (:b, 1, N'Üst limit', :l, 1, 1, '20270101', 5, N'Ay', SYSUTCDATETIME())"), p)
        c.execute(sa.text("INSERT INTO param.MaterialHold (ScenarioDefinitionId, IsValid, LocationId, MaterialId, HoldType, StartDate, ClosePct, UpdatedAt) "
                          "VALUES (:b, 1, :l, 1, N'Üretim', '20270101', 50, SYSUTCDATETIME())"), p)
        assert rows(c) == {t: 1 for t in bound}
    assert reset(eng, generate(), lambda preview: True) is not None                        # yabancı anahtar hatasıyla durmaz
    with eng.connect() as c:
        assert rows(c) == {t: 0 for t in bound} and c.execute(sa.text("SELECT COUNT(*) FROM core.Location WHERE Code = N'RS-LOC-1'")).scalar() == 0
        base = c.execute(sa.text("SELECT Id FROM param.ScenarioDefinition WHERE IsBase = 1")).scalar_one()
        assert {t: c.execute(sa.text(f"SELECT COUNT(*) FROM param.[{t}] WHERE ScenarioDefinitionId = :b"), {"b": base}).scalar() for t in bound} == kept   # sentetik kayıtlar yerinde


def test_reset_without_confirmation_changes_nothing(transferred):
    eng, _ = transferred
    snapshot = counts(eng)
    assert reset(eng, generate(), lambda preview: False) is None
    assert counts(eng) == snapshot
    reset(eng, generate(), lambda preview: True)  # temizlik


def test_reset_refuses_pinned_version(transferred):
    eng, _ = transferred
    with eng.begin() as c:
        c.execute(sa.text("UPDATE adm.DataVersion SET IsPinned = 1 WHERE ISNULL(IsSynthetic, 0) = 0"))
    snapshot = counts(eng)
    with pytest.raises(ResetRefused, match="sabitlenmiş"):
        reset(eng, generate(), lambda preview: True)
    assert counts(eng) == snapshot
    with eng.begin() as c:
        c.execute(sa.text("UPDATE adm.DataVersion SET IsPinned = 0 WHERE ISNULL(IsSynthetic, 0) = 0"))
    reset(eng, generate(), lambda preview: True)  # temizlik
