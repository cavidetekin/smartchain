"""Temiz hâlin ana tablolara yüklenmesi ve silinmesi (K-78 istisnası, K-79).

Tek işlem: güvenlik kilidi → önceki sentetik verinin silinmesi → yükleme. Hata olursa hiçbir şey değişmez.
Güvenlik kilidi: veritabanında sentetik olmayan (IsSynthetic ≠ 1) veri versiyonu, lokasyon ya da parametre seti
varsa hiçbir şey silinmeden durulur; sentetik set yalnız geliştirme ve demo veritabanında kullanılır.
"""
import logging

import sqlalchemy as sa
from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection, Engine

from db import models
from ..cleanup import delete_plan_data
from .dataset import FIELD_DEFINITIONS, LOCATION_CODE, SET_NAME, Dataset

log = logging.getLogger("smartchain.synthetic")

# Bağımlılık sırası (K-79). Location ve UnitOfMeasure versiyonsuz; ayrı yazılır.
LOAD_ORDER = [
    "Calendar", "CalendarDay", "Shift", "ResourceGroup", "CompetenceGroup", "Supplier", "Customer", "ProjectGroup",
    "Project", "Material", "UomConversion", "Resource", "ResourceCapacityProfile", "ResourceDowntime", "ShiftPlan",
    "Worker", "WorkerCompetence", "WorkerAbsence", "ProductionVersion", "BOM", "Routing", "MaterialSupplier",
    "SalesOrderLine", "Stock", "WorkOrder", "WorkOrderComponent", "WorkOrderOperation", "PurchaseOrderLine",
    "ProductionConfirmation",
]
PARAM_ORDER = ["PlanningSetting", "TimeBucketDefinition", "PriorityRule", "SupplierLimit"]
PARAM_CHILDREN = ["PlanningSetting", "TimeBucketDefinition", "PriorityRule", "AllocationRule", "ResourceEfficiency",
                  "ResourcePeriodLimit", "OvertimeLimit", "SupplierLimit"]


class SyntheticLockError(RuntimeError):
    """Veritabanında sentetik olmayan veri var; hiçbir şey yapılmadı."""


def _table(name: str, schema: str = "core") -> sa.Table:
    return models.metadata.tables[f"{schema}.{name}"]


def _validate(table: sa.Table, rows: list[dict]) -> list[dict]:
    """Bilinmeyen alan hata; toplu ekleme için satırlar aynı alan kümesine (eksik = NULL) tamamlanır."""
    keys = {k for r in rows for k in r}
    unknown = keys - {c.name for c in table.columns}
    if unknown:
        raise ValueError(f"{table.name}: bilinmeyen alan {', '.join(sorted(unknown))}")
    return [{k: r.get(k) for k in keys} for r in rows]


def non_synthetic(conn: Connection) -> list[str]:
    """Sentetik olmayan kayıtlar (Türkçe, kullanıcıya gösterilir)."""
    found = []
    for code, id_ in conn.execute(text("SELECT Code, Id FROM core.Location WHERE ISNULL(IsSynthetic, 0) = 0")):
        found.append(f"lokasyon {code} (Id {id_})")
    for name, id_ in conn.execute(text("SELECT Name, Id FROM param.ParameterSet WHERE ISNULL(IsSynthetic, 0) = 0")):
        found.append(f"parametre seti '{name}' (Id {id_})")
    for (id_,) in conn.execute(text("SELECT Id FROM adm.DataVersion WHERE ISNULL(IsSynthetic, 0) = 0")):
        found.append(f"veri versiyonu {id_}")
    return found


def _lock(conn: Connection, action: str) -> None:
    found = non_synthetic(conn)
    if found:
        raise SyntheticLockError(
            f"Veritabanında sentetik olmayan veri var; sentetik veri {action} ve hiçbir şey silinmedi. "
            f"Sentetik olmayanlar: {', '.join(found)}. "
            "Sentetik set yalnız geliştirme ve demo veritabanında kullanılır (K-79).")


def _delete(conn: Connection) -> list[int]:
    """Sentetik lokasyonun veri versiyonlarına bağlı her şeyi ve setin parametre setini siler."""
    loc = conn.execute(text("SELECT Id FROM core.Location WHERE Code = :c AND IsSynthetic = 1"),
                       {"c": LOCATION_CODE}).scalar()
    versions = [] if loc is None else [r[0] for r in conn.execute(
        text("SELECT Id FROM adm.DataVersion WHERE LocationId = :l AND IsSynthetic = 1"), {"l": loc})]
    if versions:
        delete_plan_data(conn, versions)
        in_versions = bindparam("v", expanding=True)
        for name in reversed(LOAD_ORDER):
            conn.execute(text(f"DELETE FROM core.[{name}] WHERE VersionFrom IN :v").bindparams(in_versions),
                         {"v": versions})
        conn.execute(text("DELETE FROM adm.DataVersionEntity WHERE DataVersionId IN :v").bindparams(in_versions),
                     {"v": versions})
    sets = [r[0] for r in conn.execute(text("SELECT Id FROM param.ParameterSet WHERE Name = :n AND IsSynthetic = 1"),
                                       {"n": SET_NAME})]
    if sets:
        in_sets = bindparam("p", expanding=True)
        for child in PARAM_CHILDREN:
            conn.execute(text(f"DELETE FROM param.[{child}] WHERE ParameterSetId IN :p").bindparams(in_sets),
                         {"p": sets})
        conn.execute(text("DELETE FROM param.ScenarioDefinition WHERE ParameterSetId IN :p").bindparams(in_sets),
                     {"p": sets})
        conn.execute(text("DELETE FROM param.ParameterSet WHERE Id IN :p").bindparams(in_sets), {"p": sets})
    if versions:
        conn.execute(text("DELETE FROM adm.DataVersion WHERE Id IN :v").bindparams(bindparam("v", expanding=True)),
                     {"v": versions})
    if loc is not None:
        conn.execute(text("DELETE FROM param.ScenarioDefinition WHERE LocationId = :l"), {"l": loc})
        conn.execute(text("DELETE FROM core.Location WHERE Id = :l"), {"l": loc})
    return versions


def unload(engine: Engine) -> list[int]:
    """Sentetik veriyi siler; silinen veri versiyonlarını döndürür."""
    with engine.begin() as conn:
        _lock(conn, "silinmedi")
        versions = _delete(conn)
    log.info("Sentetik veri silindi (veri versiyonları %s)", versions)
    return versions


def load(engine: Engine, ds: Dataset) -> dict:
    """Önceki sentetik veriyi silip temiz hâli yükler. Yeni veri versiyonu ve satır sayılarını döndürür."""
    with engine.begin() as conn:
        _lock(conn, "yüklenmedi")
        removed = _delete(conn)
        now = conn.execute(text("SELECT SYSUTCDATETIME()")).scalar_one()

        loc_row = {**ds.rows("Location")[0], "IsSynthetic": True}
        loc_row.pop("Id")
        location_id = conn.execute(sa.insert(_table("Location")).values(**loc_row)
                                   .returning(_table("Location").c.Id)).scalar_one()
        for u in ds.rows("UnitOfMeasure"):
            conn.execute(text("IF NOT EXISTS (SELECT 1 FROM core.UnitOfMeasure WHERE Code = :c) "
                              "INSERT INTO core.UnitOfMeasure (Code, Name) VALUES (:c, :n)"), {"c": u["Code"], "n": u["Name"]})
        # Ek alan etiketi (K-88): yoksa eklenir; sistem sahibinin tanımı varsa dokunulmaz.
        fd = _table("FieldDefinition", "adm")
        for d in FIELD_DEFINITIONS:
            exists = conn.execute(sa.select(fd.c.TableName).where(fd.c.TableName == d["TableName"],
                                                                  fd.c.FieldName == d["FieldName"])).first()
            if not exists:
                conn.execute(sa.insert(fd).values(**d))
        dv = _table("DataVersion", "adm")
        version = conn.execute(sa.insert(dv).values(LocationId=location_id, CreatedAt=now, LoadType="Tam",
                                                    IsPinned=False, IsSynthetic=True).returning(dv.c.Id)).scalar_one()

        counts = {"Location": 1}
        for name in LOAD_ORDER:
            table = _table(name)
            rows = []
            for r in ds.rows(name):
                row = {**r, "VersionFrom": version, "VersionTo": None, "ImportBatchId": None, "UpdatedAt": now}
                if "LocationId" in table.c:
                    row["LocationId"] = location_id
                rows.append(row)
            rows = _validate(table, rows)
            if rows:
                conn.execute(sa.insert(table), rows)
            counts[name] = len(rows)
            conn.execute(sa.insert(_table("DataVersionEntity", "adm")).values(
                DataVersionId=version, EntityName=name, ImportBatchId=None))

        ps = _table("ParameterSet", "param")
        meta = ds.params["ParameterSet"][0]
        set_id = conn.execute(sa.insert(ps).values(Name=meta["Name"], IsDefault=meta["IsDefault"], IsSynthetic=True)
                              .returning(ps.c.Id)).scalar_one()
        for name in PARAM_ORDER:
            table = _table(name, "param")
            rows = [{**{k: v for k, v in r.items() if k != "Id"}, "ParameterSetId": set_id} for r in ds.params[name]]
            rows = _validate(table, rows)
            conn.execute(sa.insert(table), rows)
            counts[f"param.{name}"] = len(rows)
    log.info("Sentetik veri yüklendi: veri versiyonu %s, lokasyon %s, parametre seti %s", version, location_id, set_id)
    return {"data_version_id": version, "location_id": location_id, "parameter_set_id": set_id,
            "removed_versions": removed, "counts": counts}
