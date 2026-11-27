"""Testlerin veritabanı (K-103): bütün veritabanı testleri adı _test ile biten ayrı veritabanında koşar.

Bağlantı SMARTCHAIN_TEST_DB_URL'den gelir; yoksa geliştirme bağlantısından türetilir (aynı sunucu, ad + _test).
Oturum başında veritabanı yoksa açılır, şemaya getirilir, önceki koşunun artıkları silinir, sentetik veri yoksa yüklenir.
conftest.py bunu uygulamayı import etmeden önce çağırır; bu yüzden burada üst düzeyde uygulama import edilmez.
"""
import importlib.util
from contextlib import contextmanager
import os
from collections.abc import Mapping
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import ArgumentError

ROOT = Path(__file__).resolve().parents[1]
OVERRIDE = "SMARTCHAIN_TEST_DB_URL"
SUFFIX = "_test"
# Ad yanlışsa uygulama buna bağlanır: koşu zaten başlamaz, geliştirme bağlantısına düşülmez.
NOWHERE = "mssql+pyodbc://@127.0.0.1,1/Reddedildi_test?driver=ODBC+Driver+18+for+SQL+Server&trusted_connection=yes"
SYNTHETIC_MATERIALS = 202  # 6.5'te ALT-099 ve MAM-011 (K-174)


class WrongTestDatabase(Exception):
    """Test veritabanının adı _test ile bitmiyor ya da adı çıkarılamıyor."""


def _name(url: str) -> str | None:
    try:
        return make_url(url).database
    except ArgumentError:
        return None


def is_test_name(name: str | None) -> bool:
    return bool(name) and name.lower().endswith(SUFFIX)


def _wrong(name: str) -> WrongTestDatabase:
    return WrongTestDatabase(f"Testler durdu: veritabanı adı {SUFFIX} ile bitmeli, '{name}' reddedildi. "
                             f"{OVERRIDE} ile test veritabanını verin (K-103).")


def resolve(dev_url: str, environ: Mapping[str, str] = os.environ) -> str:
    """Test bağlantısı: önce SMARTCHAIN_TEST_DB_URL, yoksa geliştirme bağlantısından türetilir."""
    explicit = environ.get(OVERRIDE)
    if explicit:
        name = _name(explicit)
        if not is_test_name(name):
            raise _wrong(name or explicit.split("?")[0])
        return explicit
    name = _name(dev_url)
    if not name:
        raise WrongTestDatabase(f"Testler durdu: geliştirme bağlantısından veritabanı adı çıkarılamadı. {OVERRIDE} verin (K-103).")
    if is_test_name(name):
        return dev_url
    return make_url(dev_url).set(database=f"{name}{SUFFIX}").render_as_string(hide_password=False)


def _setup_db():
    spec = importlib.util.spec_from_file_location("setup_db_for_tests", ROOT / "installer" / "setup_db.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ensure_database(url: str, timeout: int) -> bool:
    """Veritabanı yoksa ürünün collation'ıyla açar. Açtıysa True."""
    setup_db = _setup_db()
    name = make_url(url).database
    setup_db.refuse_in_tests(name)
    master = sa.create_engine(make_url(url).set(database="master"), isolation_level="AUTOCOMMIT", connect_args={"timeout": timeout})
    try:
        with master.connect() as conn:
            if conn.execute(sa.text("SELECT DB_ID(:n)"), {"n": name}).scalar() is not None:
                return False
            conn.execute(sa.text(f"CREATE DATABASE {setup_db.quote_name(name)} COLLATE {setup_db.COLLATION}"))
            return True
    finally:
        master.dispose()


def verify_connected(engine: Engine) -> str:
    """Bağlanılan veritabanı gerçekten test veritabanı mı (ayar ne derse desin)."""
    with engine.connect() as conn:
        name = conn.execute(sa.text("SELECT DB_NAME()")).scalar_one()
    if not is_test_name(name):
        raise _wrong(name)
    return name


def upgrade_schema() -> None:
    """alembic upgrade head; bağlantı SMARTCHAIN_DB_URL'den (conftest koyar). Güncelse işlem yapmaz."""
    from alembic import command
    from alembic.config import Config
    command.upgrade(Config(str(ROOT / "db" / "alembic.ini")), "head")


RUN_LOCK = "smartchain:pytest-run"


class TestRunBusy(RuntimeError):
    """Aynı test veritabanında başka bir pytest koşusu sürüyor."""

    __test__ = False


BUSY = ("Testler durdu: bu test veritabanında başka bir test koşusu sürüyor. Oturum başlangıcı deneme hesaplarını ve artıkları sildiği için iki koşu "
        "birbirinin verisini bozar (401 ve eksik satır hataları); önceki koşu bitince yeniden deneyin.")


def acquire_run_lock(engine: Engine):
    """Test veritabanında aynı anda tek pytest koşusu: oturum boyu tutulan uygulama kilidi. Kilit alındıysa bağlantıyı (koşu bitene kadar açık
    tutulur), başka koşu sürüyorsa None döndürür."""
    conn = engine.connect()
    got = conn.exec_driver_sql(
        f"DECLARE @r int; EXEC @r = sp_getapplock @Resource = N'{RUN_LOCK}', @LockMode = N'Exclusive', @LockOwner = N'Session', @LockTimeout = 0; SELECT @r").scalar()
    conn.commit()
    if got is None or got < 0:
        conn.close()
        return None
    return conn


def undo_transfer(conn, version: int) -> None:
    """Commit edilen test aktarımını geri alır: o versiyonun yazdığı satırlar silinir, kapattığı satırlar açılır. Bütün versiyonlu ana tablolarda:
    aktarım, yazmadığı arz tablolarında da özel alokasyonu yeniden hesaplayıp yeni versiyon açabilir (K-198; ör. sentetik müşteri kapanınca)."""
    from db.models import metadata
    for t in metadata.sorted_tables:
        if t.schema == "core" and "VersionFrom" in t.c:
            conn.execute(sa.text(f"DELETE FROM core.[{t.name}] WHERE VersionFrom = :v"), {"v": version})
            conn.execute(sa.text(f"UPDATE core.[{t.name}] SET VersionTo = NULL WHERE VersionTo = :t"), {"t": version - 1})
    conn.execute(sa.text("DELETE FROM adm.FieldChange WHERE DataVersionId = :v"), {"v": version})
    conn.execute(sa.text("DELETE FROM adm.DataVersionEntity WHERE DataVersionId = :v"), {"v": version})
    conn.execute(sa.text("DELETE FROM adm.DataVersion WHERE Id = :v"), {"v": version})


def clear_leftovers(engine: Engine) -> None:
    """Yarıda kesilen koşunun artıkları: işler, ayarlar, motor testi satırları, deneme hesapları."""
    from app.data.cleanup import delete_plan_data
    from auth_helpers import delete_users
    with engine.begin() as c:
        versions = [r[0] for r in c.execute(sa.text(
            "SELECT Id FROM adm.DataVersion WHERE LocationId IN (SELECT Id FROM core.Location WHERE Code = N'TEST-ENG')"))]
        if versions:
            delete_plan_data(c, versions)
        c.execute(sa.text("DELETE s FROM param.PlanningSetting s JOIN param.ScenarioDefinition p ON p.Id = s.ScenarioDefinitionId "
                          "WHERE p.Name LIKE N'Motor testi%'"))
        c.execute(sa.text("DELETE FROM param.ScenarioDefinition WHERE Name LIKE N'Motor testi%'"))
        for version in versions:
            c.execute(sa.text("DELETE FROM adm.DataVersion WHERE Id = :v"), {"v": version})
        c.execute(sa.text("DELETE FROM core.Location WHERE Code = N'TEST-ENG'"))
        c.execute(sa.text("DELETE FROM adm.Job"))
        c.execute(sa.text("DELETE FROM adm.DemandChainPath"))  # veri kalitesi (K-174)
        c.execute(sa.text("DELETE FROM adm.DataQualityWarning"))
        c.execute(sa.text("DELETE FROM adm.DemandChain"))
        c.execute(sa.text("DELETE FROM adm.ValidationFinding"))  # doğrulama (K-134): kural tanımları kalır, kullanıcı kuralları ve eşikler silinir
        c.execute(sa.text("DELETE FROM adm.ValidationRun"))
        c.execute(sa.text("DELETE FROM adm.ValidationRuleCondition"))
        c.execute(sa.text("DELETE FROM adm.ValidationRule WHERE Kind = N'Kullanıcı'"))
        c.execute(sa.text("UPDATE adm.ValidationRule SET IsActive = 1"))
        c.execute(sa.text("DELETE FROM adm.IntegrationViewVersion"))
        c.execute(sa.text("DELETE FROM adm.IntegrationEntity"))
        c.execute(sa.text("DELETE FROM adm.SystemEvent"))
        c.execute(sa.text("DELETE FROM adm.SystemSetting"))
        c.execute(sa.text("UPDATE adm.FieldDefinition SET Label = NULL WHERE Label LIKE N'pytest%'"))
        delete_users(c, [r[0] for r in c.execute(sa.text(
            "SELECT Id FROM adm.AppUser WHERE UserName LIKE N'pytest.%' OR UserName LIKE N'test.job.%'"))])


def _has_model_constraints(engine: Engine) -> bool:
    """Sentetik set model kısıtlarını taşıyor mu (7.10, K-189): eski setle kurulmuş test veritabanı yeniden yüklenir."""
    from app.data.synthetic.dataset import MODEL_CONSTRAINTS
    with engine.connect() as conn:
        found = conn.execute(sa.text("SELECT COUNT(*) FROM param.ResourceGroupConstraint c JOIN param.ScenarioDefinition s ON s.Id = c.ScenarioDefinitionId "
                                     "WHERE s.IsBase = 1")).scalar()
    return found >= len(MODEL_CONSTRAINTS)


def _has_warning_thresholds(engine: Engine) -> bool:
    """Sentetik set uyarı eşiği farkını taşıyor mu (7.11, K-190): eski setle kurulmuş test veritabanı yeniden yüklenir."""
    from app.data.synthetic.dataset import WARNING_THRESHOLD_OFF
    with engine.connect() as conn:
        return bool(conn.execute(sa.text("SELECT COUNT(*) FROM param.WarningThreshold w JOIN param.ScenarioDefinition s ON s.Id = w.ScenarioDefinitionId "
                                         "WHERE s.IsSynthetic = 1 AND w.WarningCode = :c AND w.IsActive = 0"), {"c": WARNING_THRESHOLD_OFF}).scalar())


def _has_supplier_limits(engine: Engine) -> bool:
    """Sentetik set tedarikçi limiti örneklerini taşıyor mu (7.12, K-191): eski setle kurulmuş test veritabanı yeniden yüklenir."""
    with engine.connect() as conn:
        return conn.execute(sa.text("SELECT COUNT(*) FROM param.SupplierLimit l JOIN param.ScenarioDefinition s ON s.Id = l.ScenarioDefinitionId "
                                    "WHERE s.IsBase = 1 AND l.LimitType = N'Kapanış'")).scalar() >= 2


def _has_material_holds(engine: Engine) -> bool:
    """Sentetik set malzeme blokajı örneklerini taşıyor mu (7.13, K-193): eski setle kurulmuş test veritabanı yeniden yüklenir."""
    with engine.connect() as conn:
        holds = conn.execute(sa.text("SELECT COUNT(*) FROM param.MaterialHold h JOIN param.ScenarioDefinition s ON s.Id = h.ScenarioDefinitionId "
                                     "WHERE s.IsBase = 1")).scalar()
        # hem üretilen hem satın alınan malzeme (docs/11): bu olmadan kurulmuş set eskidir
        both = conn.execute(sa.text("SELECT COUNT(*) FROM core.Material WHERE VersionTo IS NULL AND IsProducible = 1 AND IsPurchasable = 1")).scalar()
    return holds >= 3 and both >= 1


def _has_priorities(engine: Engine) -> bool:
    """Sentetik set öncelik gruplarını taşıyor mu (7.14a, K-195): eski setle kurulmuş test veritabanı yeniden yüklenir."""
    with engine.connect() as conn:
        return conn.execute(sa.text("SELECT COUNT(*) FROM param.DemandPriority p JOIN param.ScenarioDefinition s ON s.Id = p.ScenarioDefinitionId WHERE s.IsBase = 1")).scalar() >= 5


def _has_objective_rows(engine: Engine) -> bool:
    """Sentetik senaryolar güncel hedef satırlarını taşıyor mu (7.14b, K-196; açıklamalı örnek satır): eski setle kurulmuş test veritabanı yeniden yüklenir."""
    with engine.connect() as conn:
        return conn.execute(sa.text("SELECT COUNT(*) FROM param.ObjectiveDefinition o JOIN param.ScenarioDefinition s ON s.Id = o.ScenarioDefinitionId "
                                    "WHERE s.IsSynthetic = 1 AND s.Name = N'Fazla mesaili' AND o.Description IS NOT NULL")).scalar() >= 1


def _has_allocation(engine: Engine) -> bool:
    """Sentetik set özel alokasyon örneklerini taşıyor mu (K-198; olmayan siparişe bağlı satın alma satırı, durum 12): eski setle kurulmuş test veritabanı yeniden yüklenir."""
    with engine.connect() as conn:
        return conn.execute(sa.text("SELECT COUNT(*) FROM core.PurchaseOrderLine WHERE VersionTo IS NULL AND AllocationKey = N'SO-9999' "
                                    "AND SalesOrderLineId IS NULL AND CustomerCode IS NULL")).scalar() >= 1 and conn.execute(sa.text(
            # alokasyon kuralı (K-199, durum 13): alternatif ağaçtaki arzdan gelen kural
            "SELECT COUNT(*) FROM core.MaterialAllocationRule WHERE VersionTo IS NULL AND SourceMaterials = N'SAT-001' AND Reason = N'Alt seviye arzı'")).scalar() >= 1


FIXTURE_WEEK_MONTHS = 4   # plan fikstürünün 13 haftası her gün haftalık dönemde kalsın (K-209): "Hafta · 4 ay"


def ensure_fixture_horizon(engine: Engine) -> int:
    """Test veritabanında Baz'ın ve sentetik senaryoların plan ekseninin haftalık kısmı en az 4 ay (K-209): varsayılan "Hafta · 3 ay" ayın son
    günlerinde fikstürün 13 haftasını kapsamaz, plan yüklemesi ön koşulda durur. Yalnız test veritabanı; kurulum başlangıç değeri değişmez (K-175).
    Kurulum varsayılanını sınayan testler (test_parameters) kendi süreleri boyunca varsayılanı yazar. Değişen satır sayısı."""
    with engine.begin() as conn:
        return conn.execute(sa.text(
            "UPDATE b SET [Count] = :n FROM param.TimeBucketDefinition b JOIN param.ScenarioDefinition d ON d.Id = b.ScenarioDefinitionId "
            "WHERE (d.IsBase = 1 OR d.IsSynthetic = 1) AND b.Axis = N'Plan' AND b.BucketType = N'Hafta' AND b.SpanUnit = N'Ay' AND b.[Count] < :n"),
            {"n": FIXTURE_WEEK_MONTHS}).rowcount


@contextmanager
def default_plan_horizon(engine: Engine):
    """Kurulum başlangıç değerine bağlı testler için (ör. dönem hesabı "haftalık Oca–Mar, aylık Nis–Eyl"): Baz ve sentetik senaryoların plan
    ekseninin haftalık kısmı test süresince "Hafta · 3 ay"; sonunda fikstürün 4 ayına döner (K-209)."""
    with engine.begin() as conn:
        conn.execute(sa.text(
            "UPDATE b SET [Count] = 3 FROM param.TimeBucketDefinition b JOIN param.ScenarioDefinition d ON d.Id = b.ScenarioDefinitionId "
            "WHERE (d.IsBase = 1 OR d.IsSynthetic = 1) AND b.Axis = N'Plan' AND b.BucketType = N'Hafta' AND b.SpanUnit = N'Ay'"))
    try:
        yield
    finally:
        ensure_fixture_horizon(engine)


def ensure_synthetic(engine: Engine) -> bool:
    """Sentetik veri yoksa yükler (docs/11); varsa dokunmaz. Yüklediyse True."""
    with engine.connect() as conn:
        row = conn.execute(sa.text(
            "SELECT TOP 1 v.IsSynthetic, (SELECT COUNT(*) FROM core.Material m WHERE m.VersionFrom <= v.Id "
            "AND (m.VersionTo IS NULL OR m.VersionTo >= v.Id)) FROM adm.DataVersion v ORDER BY v.Id DESC")).first()
    if (row and row[0] and row[1] == SYNTHETIC_MATERIALS and _has_model_constraints(engine) and _has_warning_thresholds(engine) and _has_supplier_limits(engine)
            and _has_material_holds(engine) and _has_priorities(engine) and _has_objective_rows(engine) and _has_allocation(engine)):
        return False
    from app.data.synthetic.dataset import generate
    from app.data.synthetic.load import load
    load(engine, generate())
    return True
