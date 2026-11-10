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
