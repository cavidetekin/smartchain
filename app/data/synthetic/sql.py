"""Sentetik veri: SQL çekiminin kaynağı (docs/11, K-130). Kirli hâl entegrasyon veritabanına ham tablo ve view olarak yazılır.

Malzeme, Ürün ağacı ve Satış siparişinin ham tablosu gerçekten farklı biçimdedir (başka kolon adları, join, metin tarih); öteki tablolar düzdür, yalnız test içindir.
Bu dosya entegrasyon veritabanına yazar; ürün kodu yazmaz (app/integration/sql_source.py).
"""
import os
from dataclasses import dataclass, field
from datetime import date, datetime

import sqlalchemy as sa
from sqlalchemy.dialects import mssql
from sqlalchemy.engine import URL
from sqlalchemy.pool import NullPool

from app.integration import contract
from app.integration.contract import stg_columns

from .dataset import Dataset
from .excel import labels_of, make_dirty

DATABASE = "SmartchainIntegration"
MARKER = "SyntheticMarker"
SIGNAL = "ERP_LoadLog"
DEMO_TABLES = ("BOM", "Routing", "Stock", "SalesOrderLine", "WorkOrder")  # Malzeme demoda elle seçilir
DIALECT = mssql.dialect()
ITEM_GROUPS = "ERP_ItemGroup"


class SyntheticSqlLock(RuntimeError):
    """Veritabanı bu komutun açtığı değil: sentetik olmayan veriye dokunulmaz."""


@dataclass(frozen=True)
class Shape:
    """Ham tablonun biçimi: alan → ham kolon. Yazılmayan alan aynı adla durur."""
    renames: dict[str, str] = field(default_factory=dict)
    text_dates: frozenset[str] = frozenset()  # 'yyyymmdd' metin; view tarihe çevirir


SHAPES = {
    "Material": Shape({"LocationCode": "PLANT", "Code": "ITEM_CODE", "Name": "ITEM_NAME", "BaseUom": "UOM", "MaterialType": "ITEM_TYPE", "PlannerCode": "PLANNER"}),
    "BOM": Shape({"LocationCode": "PLANT", "MaterialCode": "PARENT_ITEM", "Code": "BOM_NO", "ComponentMaterialCode": "CHILD_ITEM", "Quantity": "CHILD_QTY"}),
    "SalesOrderLine": Shape({"LocationCode": "PLANT", "OrderNo": "SO_NO", "LineNo": "SO_LINE", "CustomerCode": "CUST_NO", "MaterialCode": "ITEM_CODE", "OpenQuantity": "OPEN_QTY",
                             "RequestedDate": "REQ_DATE", "ConfirmedDate": "CONF_DATE"}, frozenset({"RequestedDate", "ConfirmedDate"})),
}


def _quoted(name: str) -> str:
    return "[" + name.replace("]", "]]") + "]"


def raw_table(table: str) -> str:
    return f"ERP_{table}"


def view_name(table: str) -> str:
    return f"View_{table}"


def _columns(table: str) -> list[tuple[str, str]]:
    """Sözleşme alanı → stg tipi; yalnız şablondaki alanlar (etiketli ek alan dahil)."""
    known = {c.name: c for c in stg_columns(table)}
    return [(f.name, known[f.name].type.compile(dialect=DIALECT)) for f in contract.fields(table, labels_of(table))]


def _view_sql(table: str, columns: list[tuple[str, str]]) -> str:
    shape = SHAPES.get(table, Shape())
    items = []
    for name, _type in columns:
        raw = f"t.{_quoted(shape.renames.get(name, name))}"
        if table == "Material" and name == "MaterialGroup":
            items.append(f"g.GROUP_NAME AS {_quoted(name)}")
        elif name in shape.text_dates:
            items.append(f"CONVERT(date, {raw}, 112) AS {_quoted(name)}")
        else:
            items.append(f"{raw} AS {_quoted(name)}" if name in shape.renames else f"{raw}")
    source = f"dbo.{raw_table(table)} t"
    if table == "Material":
        source += f" LEFT JOIN dbo.{ITEM_GROUPS} g ON g.GROUP_ID = t.GROUP_ID"
    return f"CREATE VIEW dbo.{view_name(table)} AS\nSELECT " + ",\n       ".join(items) + f"\nFROM {source}"


def ensure_database(base_url: URL, database: str, collation: str) -> None:
    """Yoksa açar; varsa yalnız _test ya da bu komutun açtığı veritabanına yazılır."""
    if "PYTEST_CURRENT_TEST" in os.environ and not database.lower().endswith("_test"):
        raise RuntimeError(f"Test sırasında veritabanının adı _test ile bitmeli; '{database}' reddedildi.")
    master = sa.create_engine(base_url.set(database="master"), isolation_level="AUTOCOMMIT", poolclass=NullPool)
    try:
        with master.connect() as c:
            if c.execute(sa.text("SELECT DB_ID(:n)"), {"n": database}).scalar() is None:
                c.execute(sa.text(f"CREATE DATABASE {_quoted(database)} COLLATE {collation}"))
                created = True
            else:
                created = False
    finally:
        master.dispose()
    db = sa.create_engine(base_url.set(database=database), poolclass=NullPool)
    try:
        with db.begin() as c:
            marked = c.execute(sa.text("SELECT OBJECT_ID(:n, 'U')"), {"n": f"dbo.{MARKER}"}).scalar() is not None
            if not created and not marked and not database.lower().endswith("_test"):
                raise SyntheticSqlLock(f"'{database}' bu komutun açtığı bir veritabanı değil; hiçbir şey yazılmadı.")
            if not marked:
                c.execute(sa.text(f"CREATE TABLE dbo.{MARKER} (Note nvarchar(60) NOT NULL)"))
                c.execute(sa.text(f"INSERT INTO dbo.{MARKER} (Note) VALUES (N'Sentetik v0')"))
    finally:
        db.dispose()


def _drop_all(c: sa.Connection) -> None:
    for name in c.execute(sa.text("SELECT name FROM sys.views WHERE schema_id = SCHEMA_ID('dbo') AND name LIKE 'View[_]%'")).scalars().all():
        c.execute(sa.text(f"DROP VIEW dbo.{_quoted(name)}"))
    for name in c.execute(sa.text("SELECT name FROM sys.tables WHERE schema_id = SCHEMA_ID('dbo') AND name LIKE 'ERP[_]%'")).scalars().all():
        c.execute(sa.text(f"DROP TABLE dbo.{_quoted(name)}"))


def _raw_value(value, text_date: bool):
    if text_date and isinstance(value, (date, datetime)):
        return value.strftime("%Y%m%d")
    return value


def _write_table(c: sa.Connection, table: str, rows: list[dict]) -> None:
    shape = SHAPES.get(table, Shape())
    columns = _columns(table)
    groups: dict[str, int] = {}
    defs, names = [], []
    for name, sql_type in columns:
        if table == "Material" and name == "MaterialGroup":
            defs.append("[GROUP_ID] int NULL")
            names.append("GROUP_ID")
            continue
        raw = shape.renames.get(name, name)
        defs.append(f"{_quoted(raw)} {'char(8)' if name in shape.text_dates else sql_type} NULL")
        names.append(raw)
    c.execute(sa.text(f"CREATE TABLE dbo.{raw_table(table)} ({', '.join(defs)})"))
    data = []
    for row in rows:
        values = []
        for name, _type in columns:
            if table == "Material" and name == "MaterialGroup":
                value = row.get(name)
                values.append(groups.setdefault(value, len(groups) + 1) if value else None)
            else:
                values.append(_raw_value(row.get(name), name in shape.text_dates))
        data.append(tuple(values))
    if table == "Material":
        c.execute(sa.text(f"CREATE TABLE dbo.{ITEM_GROUPS} (GROUP_ID int NOT NULL, GROUP_NAME nvarchar(50) NOT NULL)"))
        for name, group_id in groups.items():
            c.execute(sa.text(f"INSERT INTO dbo.{ITEM_GROUPS} (GROUP_ID, GROUP_NAME) VALUES (:i, :n)"), {"i": group_id, "n": name})
    if data:
        marks = ", ".join("?" * len(names))
        cols = ", ".join(_quoted(n) for n in names)
        c.exec_driver_sql(f"INSERT INTO dbo.{raw_table(table)} ({cols}) VALUES ({marks})", data)
    c.execute(sa.text(_view_sql(table, columns)))


def write_sql(ds: Dataset, base_url: URL, database: str = DATABASE, collation: str = "Latin1_General_100_CI_AS_SC") -> dict:
    """Ham tablolar, view'lar ve biten bir toplu sinyal; varsa yeniden açılır."""
    ensure_database(base_url, database, collation)
    stg, errors = make_dirty(ds)
    engine = sa.create_engine(base_url.set(database=database), poolclass=NullPool)
    try:
        with engine.begin() as c:
            _drop_all(c)
            c.execute(sa.text(f"CREATE TABLE dbo.{SIGNAL} (Id bigint IDENTITY(1,1) PRIMARY KEY, EntityName nvarchar(60) NULL, StartedAt datetime2 NOT NULL, FinishedAt datetime2 NULL)"))
            for table, rows in stg.items():
                _write_table(c, table, rows)
            c.execute(sa.text(f"INSERT INTO dbo.{SIGNAL} (EntityName, StartedAt, FinishedAt) VALUES (NULL, SYSUTCDATETIME(), SYSUTCDATETIME())"))
    finally:
        engine.dispose()
    return {"database": database, "tables": {t: len(r) for t, r in stg.items()}, "errors": errors}


def signal_all(base_url: URL, database: str) -> None:
    """Yeni bir toplu bitti sinyali: yenileme bitti (test ve demo)."""
    engine = sa.create_engine(base_url.set(database=database), poolclass=NullPool)
    try:
        with engine.begin() as c:
            c.execute(sa.text(f"INSERT INTO dbo.{SIGNAL} (EntityName, StartedAt, FinishedAt) VALUES (NULL, SYSUTCDATETIME(), SYSUTCDATETIME())"))
    finally:
        engine.dispose()


def configure_demo(engine: sa.Engine, tables: tuple[str, ...] = DEMO_TABLES) -> None:
    """Demo kurulumu: yöntem SQL, view atanmış. Satır varsa yalnız yöntem ve view değişir; iz yazılmaz, sentetik kurulum verisidir."""
    with engine.begin() as c:
        for table in tables:
            changed = c.execute(sa.text("UPDATE adm.IntegrationEntity SET Method = N'SQL', ViewName = :v WHERE EntityName = :t"), {"t": table, "v": view_name(table)}).rowcount
            if not changed:
                c.execute(sa.text("INSERT INTO adm.IntegrationEntity (EntityName, Method, ViewName) VALUES (:t, N'SQL', :v)"), {"t": table, "v": view_name(table)})
