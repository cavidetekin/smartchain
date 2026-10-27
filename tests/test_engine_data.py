"""SqlPlanningData: motorun salt okunur veri erişimi, veri versiyonuna göre süzme (K-63)."""
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.engine.data import SqlPlanningData

pytestmark = pytest.mark.db

ROWS = [  # Id, Code, Name, VersionFrom, VersionTo
    (900001, "TEST-C1", "Eski ad", 1, 1),
    (900001, "TEST-C1", "Yeni ad", 2, None),
    (900002, "TEST-C2", "Sonradan gelen", 3, None),
]


@pytest.fixture
def customers(db_engine):
    with db_engine.begin() as c:
        c.execute(text("DELETE FROM core.Customer WHERE Id IN (900001, 900002)"))
        for i, code, name, vf, vt in ROWS:
            c.execute(text("INSERT INTO core.Customer (Id, Code, Name, VersionFrom, VersionTo, BusinessKey, UpdatedAt) "
                           "VALUES (:i, :c, :n, :vf, :vt, :c, SYSUTCDATETIME())"),
                      {"i": i, "c": code, "n": name, "vf": vf, "vt": vt})
    yield
    with db_engine.begin() as c:
        c.execute(text("DELETE FROM core.Customer WHERE Id IN (900001, 900002)"))


def names(db_engine, version):
    with Session(db_engine) as s:
        rows = SqlPlanningData(s, version).read("Customer", ["Id", "Name"])
    return [r["Name"] for r in rows if r["Id"] in (900001, 900002)]


def test_version_filter(db_engine, customers):
    assert names(db_engine, 1) == ["Eski ad"]
    assert names(db_engine, 2) == ["Yeni ad"]
    assert names(db_engine, 3) == ["Yeni ad", "Sonradan gelen"]


def test_unversioned_table_and_full_row(db_engine, customers):
    with Session(db_engine) as s:
        data = SqlPlanningData(s, 2)
        assert isinstance(data.read("core.Location"), list)
        row = next(r for r in data.read("Customer") if r["Id"] == 900001)
        assert row["Code"] == "TEST-C1" and row["VersionFrom"] == 2


@pytest.mark.parametrize("table, columns, problem", [
    ("adm.Job", None, "yalnız core"),
    ("Musteri", None, "Bilinmeyen tablo"),
    ("Customer", ["Id", "Unvan"], "bilinmeyen alan Unvan"),
])
def test_rejects(db_engine, table, columns, problem):
    with Session(db_engine) as s, pytest.raises(ValueError, match=problem):
        SqlPlanningData(s, 1).read(table, columns)
