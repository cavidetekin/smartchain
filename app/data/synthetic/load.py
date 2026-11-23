"""Temiz hâlin ana tablolara yüklenmesi ve silinmesi (K-78 istisnası, K-79).

Tek işlem: güvenlik kilidi → önceki sentetik verinin silinmesi → yükleme. Hata olursa hiçbir şey değişmez.
Güvenlik kilidi: veritabanında sentetik olmayan (IsSynthetic ≠ 1) veri versiyonu, lokasyon ya da parametre seti
varsa hiçbir şey silinmeden durulur; sentetik set yalnız geliştirme ve demo veritabanında kullanılır.

Sıfırlama (`reset`, K-153): geliştirme ya da demo veritabanında yapılan aktarımları geri alıp temiz sentetik hâle döner. Yalnız sentetik
veriyle kurulmuş veritabanında (sentetik veri versiyonu var), onaylı plana bağlı versiyon ve sentetik olmayan parametre seti yokken çalışır;
komut satırı silinecekleri gösterip veritabanı adının yazılmasını ister. Staging'e dokunmaz.
"""
import logging

import sqlalchemy as sa
from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection, Engine

from db import models
from ..cleanup import delete_plan_data
from .dataset import FIELD_DEFINITIONS, LOCATION_CODE, SCENARIOS, SET_NAME, Dataset

log = logging.getLogger("smartchain.synthetic")

# Bağımlılık sırası (K-79). Location ve UnitOfMeasure versiyonsuz; ayrı yazılır.
LOAD_ORDER = [
    "ResourceGroup", "Supplier", "Customer", "ProjectGroup",
    "Project", "Material", "UomConversion", "Resource",
    "ResourceGroupMember", "EmployeeAbsence", "ProductionVersion", "BOM", "Routing", "MaterialSupplier", "MaterialReference",
    "SalesOrderLine", "Forecast", "Stock", "BorrowPayback", "WorkOrder", "WorkOrderComponent", "WorkOrderOperation", "PurchaseOrderLine",
    "ProductionConfirmation",
]
CAPACITY_TABLES = ["WorkPattern", "ResourceEfficiency", "OvertimeLimit", "ResourceDowntime", "FactoryCalendar"]  # kapasite girişleri (K-185)
MODEL_TABLES = ["ResourceGroupConstraint"]  # model kısıtları (K-189)
PARAM_ORDER = ["PriorityRule", "SupplierLimit", "MaterialHold", *CAPACITY_TABLES, *MODEL_TABLES]  # Baz senaryoya bağlanır; Baz'ın parametrelerine dokunulmaz (K-175)
PARAM_CHILDREN = ["PlanningSetting", "TimeBucketDefinition", "ObjectiveDefinition", "PriorityRule", "WarningThreshold", "SupplierLimit", "MaterialHold", *CAPACITY_TABLES,
                  *MODEL_TABLES]
LOCATION_BOUND = ("FactoryCalendar", "SupplierLimit", "MaterialHold")   # lokasyon taşıyan param tabloları
NO_BASE = "Baz senaryo yok; önce veritabanını güncelleyin (alembic -c db/alembic.ini upgrade head)."


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
    for name, id_ in conn.execute(text("SELECT Name, Id FROM param.ScenarioDefinition WHERE ISNULL(IsSynthetic, 0) = 0 AND ISNULL(IsBase, 0) = 0")):
        found.append(f"senaryo '{name}' (Id {id_})")
    for (id_,) in conn.execute(text("SELECT Id FROM adm.DataVersion WHERE ISNULL(IsSynthetic, 0) = 0")):
        found.append(f"veri versiyonu {id_}")
    return found


def _lock(conn: Connection, action: str) -> None:
    found = non_synthetic(conn)
    if found:
        raise SyntheticLockError(
            f"Veritabanında sentetik olmayan veri var; sentetik veri {action} ve hiçbir şey silinmedi. "
            f"Sentetik olmayanlar: {', '.join(found)}. "
            "Sentetik set yalnız geliştirme ve demo veritabanında kullanılır (K-79). "
            "Aktarımları geri alıp temiz sentetik hâle dönmek için: python -m app.data.synthetic reset")


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
    # Baz'a bağlanan sentetik satırlar; Baz'ın parametreleri kalır
    for child in PARAM_ORDER:
        conn.execute(text(f"DELETE FROM param.[{child}] WHERE ScenarioDefinitionId IN (SELECT Id FROM param.ScenarioDefinition WHERE IsBase = 1)"))
    # sentetik senaryolar (K-177) ve 0058 öncesinin pasif kalan sentetik seti
    sets = [r[0] for r in conn.execute(text("SELECT Id FROM param.ScenarioDefinition WHERE IsSynthetic = 1 AND ISNULL(IsBase, 0) = 0"))]
    if sets:
        in_sets = bindparam("p", expanding=True)
        for child in PARAM_CHILDREN:
            conn.execute(text(f"DELETE FROM param.[{child}] WHERE ScenarioDefinitionId IN :p").bindparams(in_sets),
                         {"p": sets})
        conn.execute(text("UPDATE adm.AppUser SET ScenarioDefinitionId = NULL WHERE ScenarioDefinitionId IN :p").bindparams(in_sets), {"p": sets})
        conn.execute(text("DELETE FROM param.ScenarioDefinition WHERE Id IN :p").bindparams(in_sets), {"p": sets})
    if versions:
        conn.execute(text("DELETE FROM adm.DataVersion WHERE Id IN :v").bindparams(bindparam("v", expanding=True)),
                     {"v": versions})
    if loc is not None:
        conn.execute(text("UPDATE param.ScenarioDefinition SET LocationId = NULL WHERE LocationId = :l AND IsBase = 1"), {"l": loc})
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
        return _load(conn, ds)


class ResetRefused(RuntimeError):
    """Sıfırlama bu veritabanında yapılamaz; hiçbir şey değişmedi."""


def _versioned() -> list[sa.Table]:
    return [t for t in models.metadata.sorted_tables if t.schema == "core" and "VersionFrom" in t.c]


def reset_preview(conn: Connection) -> dict:
    """Sıfırlamanın sileceği ve açacağı (sayılar); sıfırlama yapılamıyorsa neden."""
    synthetic = [r[0] for r in conn.execute(text("SELECT Id FROM adm.DataVersion WHERE IsSynthetic = 1"))]
    transfers = [r[0] for r in conn.execute(text("SELECT Id FROM adm.DataVersion WHERE ISNULL(IsSynthetic, 0) = 0"))]
    refuse = None
    if not synthetic:
        refuse = "Bu veritabanında sentetik veri yok; sıfırlama yalnız sentetik veriyle kurulmuş geliştirme ve demo veritabanında çalışır."
    elif conn.execute(text("SELECT COUNT(*) FROM adm.DataVersion WHERE IsPinned = 1 AND ISNULL(IsSynthetic, 0) = 0")).scalar():
        refuse = "Onaylı plana bağlı (sabitlenmiş) veri versiyonu var; sıfırlanmaz."
    elif conn.execute(text("SELECT COUNT(*) FROM param.ScenarioDefinition WHERE ISNULL(IsSynthetic, 0) = 0 AND ISNULL(IsBase, 0) = 0")).scalar():
        refuse = "Baz dışında sentetik olmayan senaryo var; sıfırlanmaz."
    rows = 0
    if transfers:
        param = bindparam("v", expanding=True)
        for t in _versioned():
            rows += conn.execute(text(f"SELECT COUNT(*) FROM core.[{t.name}] WHERE VersionFrom IN :v").bindparams(param), {"v": transfers}).scalar()
    locations = conn.execute(text("SELECT COUNT(*) FROM core.Location WHERE ISNULL(IsSynthetic, 0) = 0")).scalar()
    return {"database": conn.execute(text("SELECT DB_NAME()")).scalar(), "versions": transfers, "rows": rows, "locations": locations, "refuse": refuse}


def _remove_transfers(conn: Connection, versions: list[int]) -> None:
    """Aktarımların yazdıklarını siler, kapattığı sentetik satırları açar (sentetik yükleme satır kapatmaz)."""
    if versions:
        delete_plan_data(conn, versions)
        param = bindparam("v", expanding=True)
        for t in reversed(_versioned()):
            conn.execute(text(f"DELETE FROM core.[{t.name}] WHERE VersionFrom IN :v").bindparams(param), {"v": versions})
        for t in _versioned():
            conn.execute(text(f"UPDATE core.[{t.name}] SET VersionTo = NULL WHERE VersionTo IS NOT NULL"))
        conn.execute(text("DELETE FROM adm.DataVersionEntity WHERE DataVersionId IN :v").bindparams(param), {"v": versions})
        conn.execute(text("DELETE FROM adm.DataVersion WHERE Id IN :v").bindparams(param), {"v": versions})
    conn.execute(text("DELETE FROM adm.FieldValueSource WHERE Source = N'Kural'"))
    # lokasyona bağlı Smartchain kayıtları (K-191, K-193, K-194: tedarikçi limiti, malzeme blokajı, fabrika takvimi) lokasyonla birlikte silinir;
    # 0073 çok lokasyonlu veritabanında fabrika takvimini her lokasyona kopyalar, o kopyalar da burada gider
    for name in LOCATION_BOUND:
        conn.execute(text(f"DELETE FROM param.[{name}] WHERE LocationId IN (SELECT Id FROM core.Location WHERE ISNULL(IsSynthetic, 0) = 0)"))
    conn.execute(text("DELETE FROM core.Location WHERE ISNULL(IsSynthetic, 0) = 0"))


def reset(engine: Engine, ds: Dataset, confirm) -> dict | None:
    """Aktarımları geri alıp temiz sentetik hâli yükler (tek işlem). confirm(preview) True dönmezse hiçbir şey yapılmaz."""
    with engine.begin() as conn:
        preview = reset_preview(conn)
        if preview["refuse"]:
            raise ResetRefused(preview["refuse"])
        if not confirm(preview):
            return None
        _remove_transfers(conn, preview["versions"])
        _lock(conn, "yüklenmedi")
        result = _load(conn, ds)
    log.info("Geliştirme veritabanı sıfırlandı: aktarım versiyonları %s silindi", preview["versions"])
    return {**result, "removed_transfers": preview["versions"], "removed_rows": preview["rows"]}


def _scenarios(conn: Connection, base_id: int) -> int:
    """Sentetik senaryolar (docs/11, K-177): Baz'dan kopyalanır, parametre farkları yazılır; Baz gece 1. sırada çalışır. Baz'ın parametrelerine
    dokunulmaz."""
    from app.params import scenarios, service as params
    conn.execute(text("UPDATE param.ScenarioDefinition SET RunsNightly = 1, NightlyPriority = 1 WHERE Id = :b"), {"b": base_id})
    priority = 1
    for name, follows, nightly, changes, divide in SCENARIOS:
        row = scenarios.create_copy(conn, name, base_id, follows, synthetic=True)
        params.save_settings(conn, row["Id"], changes)
        if divide > 1:
            conn.execute(text("UPDATE param.ObjectiveDefinition SET TimeBudgetSeconds = TimeBudgetSeconds / :n WHERE ScenarioDefinitionId = :s "
                              "AND TimeBudgetSeconds IS NOT NULL"), {"n": divide, "s": row["Id"]})
        if nightly:
            priority += 1
            conn.execute(text("UPDATE param.ScenarioDefinition SET RunsNightly = 1, NightlyPriority = :p WHERE Id = :s"), {"p": priority, "s": row["Id"]})
    return len(SCENARIOS)


def _scenario_differences(conn: Connection, ds: Dataset, base_id: int, now) -> None:
    """Baz'ı izleyen senaryoların kapasite farkları (docs/11, K-185): fark satırı (alan düzeyinde), geçersiz yapılmış Baz satırı ve senaryonun
    kendi satırı. Baz'ı izlemeyen senaryo kopyalanırken Baz'ın satırlarını tam alır (`materialize`)."""
    def scenario(name: str) -> int:
        return conn.execute(text("SELECT Id FROM param.ScenarioDefinition WHERE Name = :n AND IsSynthetic = 1"), {"n": name}).scalar_one()

    def group(code: str) -> int:
        return next(g["Id"] for g in ds.rows("ResourceGroup") if g["Code"] == code)

    def resource(code: str) -> int:
        return next(r["Id"] for r in ds.rows("Resource") if r["Code"] == code)

    overtime, mono = scenario("Fazla mesaili"), scenario("Kısıtsız kapasite")
    # Fazla mesaili: montajcıların ek mesai limiti 2 → 4 (Baz satırının farkı: yalnız DailyLimit); montaj hattına senaryonun kendi limiti
    conn.execute(text(
        "INSERT INTO param.OvertimeLimit (ScenarioDefinitionId, BaseRowId, OverriddenFields, IsValid, ResourceGroupId, ResourceId, ValidFrom, ValidTo, DailyLimit, UpdatedAt) "
        "SELECT :s, b.Id, N',DailyLimit,', b.IsValid, b.ResourceGroupId, b.ResourceId, b.ValidFrom, b.ValidTo, 4, :now FROM param.OvertimeLimit b "
        "WHERE b.ScenarioDefinitionId = :base AND b.ResourceGroupId = :g"), {"s": overtime, "base": base_id, "g": group("CG-MON"), "now": now})
    conn.execute(text(
        "INSERT INTO param.OvertimeLimit (ScenarioDefinitionId, IsValid, ResourceGroupId, ValidFrom, DailyLimit, UpdatedAt) VALUES (:s, 1, :g, :a, 3, :now)"),
        {"s": overtime, "g": group("MONTAJ"), "a": ds.start, "now": now})
    # Kısıtsız kapasite: T-02'nin planlı bakımı bu senaryoda geçersiz (Baz satırı silinmez; "Geçersiz yap")
    conn.execute(text(
        "INSERT INTO param.ResourceDowntime (ScenarioDefinitionId, BaseRowId, OverriddenFields, IsValid, ResourceGroupId, ResourceId, StartDate, EndDate, DowntimeType, "
        "Reason, UpdatedAt) SELECT :s, b.Id, N',IsValid,', 0, b.ResourceGroupId, b.ResourceId, b.StartDate, b.EndDate, b.DowntimeType, b.Reason, :now "
        "FROM param.ResourceDowntime b WHERE b.ScenarioDefinitionId = :base AND b.ResourceId = :r"), {"s": mono, "base": base_id, "r": resource("T-02"), "now": now})
    # Kısıtsız kapasite (K-189): bir grupta çarpan farkı (Baz satırının farkı: yalnız çarpan) ve Baz'da değeri olmayan bir grupta senaryonun kendi çarpanı
    from .dataset import MODEL_CONSTRAINT_DIFF, MODEL_CONSTRAINT_OWN
    conn.execute(text(
        "INSERT INTO param.ResourceGroupConstraint (ScenarioDefinitionId, BaseRowId, OverriddenFields, IsValid, ResourceGroupId, UnconstrainedCapacityFactor, "
        "TargetUtilizationPct, UpdatedAt) SELECT :s, b.Id, N',UnconstrainedCapacityFactor,', 1, b.ResourceGroupId, :f, b.TargetUtilizationPct, :now "
        "FROM param.ResourceGroupConstraint b WHERE b.ScenarioDefinitionId = :base AND b.ResourceGroupId = :g"),
        {"s": mono, "base": base_id, "g": group(MODEL_CONSTRAINT_DIFF[0]), "f": MODEL_CONSTRAINT_DIFF[1], "now": now})
    conn.execute(text(
        "INSERT INTO param.ResourceGroupConstraint (ScenarioDefinitionId, IsValid, ResourceGroupId, UnconstrainedCapacityFactor, UpdatedAt) VALUES (:s, 1, :g, :f, :now)"),
        {"s": mono, "g": group(MODEL_CONSTRAINT_OWN[0]), "f": MODEL_CONSTRAINT_OWN[1], "now": now})
    # Kısıtsız kapasite (K-190): uyarı eşikleri senaryoya göre farklı (ayar, tam kopya): Aşırı yük eşikleri yukarıda, Düşük doluluk kapalı
    from .dataset import WARNING_THRESHOLD_CHANGE, WARNING_THRESHOLD_OFF
    code, (low, medium, high, critical) = WARNING_THRESHOLD_CHANGE
    conn.execute(text("UPDATE param.WarningThreshold SET ThresholdLow = :l, ThresholdMedium = :m, ThresholdHigh = :h, ThresholdCritical = :c "
                      "WHERE ScenarioDefinitionId = :s AND WarningCode = :w"), {"s": mono, "w": code, "l": low, "m": medium, "h": high, "c": critical})
    conn.execute(text("UPDATE param.WarningThreshold SET IsActive = 0 WHERE ScenarioDefinitionId = :s AND WarningCode = :w"), {"s": mono, "w": WARNING_THRESHOLD_OFF})
    # Kısıtsız kapasite (K-191): haftalık tedarikçi limiti bu senaryoda daha yüksek (Baz satırının farkı: yalnız limit)
    from .dataset import SUPLIM_UPPER, SUPLIM_WEEKLY, SUPLIM_WEEKLY_DIFF, supplier_material
    weekly = supplier_material(ds, SUPLIM_WEEKLY[0])
    conn.execute(text(
        "INSERT INTO param.SupplierLimit (ScenarioDefinitionId, BaseRowId, OverriddenFields, IsValid, LimitType, LocationId, SupplierId, MaterialId, ValidFrom, ValidTo, "
        "UpperLimit, LimitPeriod, Reason, UpdatedAt) SELECT :s, b.Id, N',UpperLimit,', b.IsValid, b.LimitType, b.LocationId, b.SupplierId, b.MaterialId, b.ValidFrom, "
        "b.ValidTo, :q, b.LimitPeriod, b.Reason, :now FROM param.SupplierLimit b WHERE b.ScenarioDefinitionId = :base AND b.LimitType = :t AND b.MaterialId = :m "
        "AND b.LimitPeriod = N'Hafta'"), {"s": mono, "base": base_id, "t": SUPLIM_UPPER, "m": weekly["Id"], "q": SUPLIM_WEEKLY_DIFF, "now": now})
    # Kısıtsız kapasite (K-193): 20 günlük malzeme blokajı bu senaryoda geçersiz (Baz satırı silinmez; "Geçersiz yap")
    from .dataset import HOLD_BOTH
    conn.execute(text(
        "INSERT INTO param.MaterialHold (ScenarioDefinitionId, BaseRowId, OverriddenFields, IsValid, LocationId, MaterialId, HoldType, StartDate, EndDate, ClosePct, Reason, "
        "UpdatedAt) SELECT :s, b.Id, N',IsValid,', 0, b.LocationId, b.MaterialId, b.HoldType, b.StartDate, b.EndDate, b.ClosePct, b.Reason, :now "
        "FROM param.MaterialHold b WHERE b.ScenarioDefinitionId = :base AND b.HoldType = :t"), {"s": mono, "base": base_id, "t": HOLD_BOTH, "now": now})


def _drop_period_cache(conn: Connection) -> None:
    """Önbellek veri değildir (K-184): sentetik veri değişince boşaltılır, ilk kullanımda yeniden kurulur."""
    conn.execute(text("DELETE FROM cache.ResourceCapacityDay"))
    conn.execute(text("DELETE FROM cache.PeriodCacheState"))


def _load(conn: Connection, ds: Dataset) -> dict:
    """Yüklemenin gövdesi: önceki sentetik veriyi siler, temiz hâli yazar (çağıranın işleminde)."""
    removed = _delete(conn)
    now = conn.execute(text("SELECT SYSUTCDATETIME()")).scalar_one()

    loc_row = {**ds.rows("Location")[0], "IsSynthetic": True}
    loc_row.pop("Id")
    location_id = conn.execute(sa.insert(_table("Location")).values(**loc_row)
                               .returning(_table("Location").c.Id)).scalar_one()
    for u in ds.rows("UnitOfMeasure"):
        conn.execute(text("IF NOT EXISTS (SELECT 1 FROM core.UnitOfMeasure WHERE Code = :c) "
                          "INSERT INTO core.UnitOfMeasure (Code, Name, Decimals) VALUES (:c, :n, :d)"),
                     {"c": u["Code"], "n": u["Name"], "d": u["Decimals"]})
    # Ek alan etiketi (K-88, K-104): satır yoksa eklenir, etiket boşsa yazılır; System owner'ın etiketi korunur.
    fd = _table("FieldDefinition", "adm")
    for d in FIELD_DEFINITIONS:
        exists = conn.execute(sa.select(fd.c.Label).where(fd.c.TableName == d["TableName"],
                                                          fd.c.FieldName == d["FieldName"])).first()
        if not exists:
            conn.execute(sa.insert(fd).values(**d))
        elif not exists[0]:
            conn.execute(sa.update(fd).where(fd.c.TableName == d["TableName"], fd.c.FieldName == d["FieldName"])
                         .values(Label=d["Label"]))
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

    set_id = conn.execute(text("SELECT Id FROM param.ScenarioDefinition WHERE IsBase = 1")).scalar()
    if set_id is None:
        raise SyntheticLockError(NO_BASE)
    for name in PARAM_ORDER:
        table = _table(name, "param")
        stamp = {"UpdatedAt": now} if "UpdatedAt" in table.c else {}
        place = {"LocationId": location_id} if "LocationId" in table.c else {}      # tedarikçi limiti lokasyon taşır (K-191)
        rows = [{**{k: v for k, v in r.items() if k != "Id"}, "ScenarioDefinitionId": set_id, **stamp, **place} for r in ds.params.get(name, [])]
        rows = _validate(table, rows)
        if rows:
            conn.execute(sa.insert(table), rows)
        counts[f"param.{name}"] = len(rows)
    counts["param.ScenarioDefinition"] = _scenarios(conn, set_id)
    _scenario_differences(conn, ds, set_id, now)
    _drop_period_cache(conn)
    log.info("Sentetik veri yüklendi: veri versiyonu %s, lokasyon %s, senaryo %s (Baz)", version, location_id, set_id)
    return {"data_version_id": version, "location_id": location_id, "scenario_definition_id": set_id,
            "removed_versions": removed, "counts": counts}
