"""Son geçişin ileri – geri – ileri denemesi (K-186): boş bir deneme veritabanında (`Smartchain_migration_test`; adı `_test` ile biter, K-103)
bütün geçişler uygulanır, son geçiş geri alınır ve yeniden uygulanır; sonunda şema modellerle aynıdır (`alembic check`). Veritabanı test sonunda
düşürülür. Ortak test veritabanına (`Smartchain_test`) dokunmaz: orada geri alış sentetik veriyi silerdi.

Geçişi her zaman "son geçiş" olarak bulur: yeni geçiş eklendiğinde aynı test onu dener.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.engine import make_url

import testdb

pytestmark = pytest.mark.db

ROOT = Path(__file__).resolve().parents[1]
NAME = "Smartchain_migration_test"


def _alembic(url: str, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "SMARTCHAIN_DB_URL": url, "PYTHONIOENCODING": "utf-8"}
    return subprocess.run([sys.executable, "-m", "alembic", "-c", "db/alembic.ini", *args], cwd=ROOT, env=env, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=900)


def _drop(url: str) -> None:
    assert testdb.is_test_name(NAME)
    master = sa.create_engine(make_url(url).set(database="master"), isolation_level="AUTOCOMMIT")
    try:
        with master.connect() as conn:
            if conn.execute(sa.text("SELECT DB_ID(:n)"), {"n": NAME}).scalar() is not None:
                conn.execute(sa.text(f"ALTER DATABASE [{NAME}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE"))
                conn.execute(sa.text(f"DROP DATABASE [{NAME}]"))
    finally:
        master.dispose()


@pytest.fixture
def scratch(db_engine):
    """Boş deneme veritabanı; test sonunda düşürülür (önceki koşudan kaldıysa baştan açılır)."""
    url = make_url(os.environ["SMARTCHAIN_DB_URL"]).set(database=NAME).render_as_string(hide_password=False)
    _drop(url)
    assert testdb.ensure_database(url, timeout=30)
    try:
        yield url
    finally:
        _drop(url)


def _tables(url: str) -> set[str]:
    engine = sa.create_engine(url)
    try:
        with engine.connect() as c:
            return {f"{s}.{t}" for s, t in c.execute(sa.text("SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE'"))}
    finally:
        engine.dispose()


def _version(url: str) -> str:
    engine = sa.create_engine(url)
    try:
        with engine.connect() as c:
            return c.execute(sa.text("SELECT version_num FROM dbo.alembic_version")).scalar_one()
    finally:
        engine.dispose()


def test_latest_migration_goes_forward_back_and_forward(scratch):
    script = ScriptDirectory.from_config(Config(str(ROOT / "db" / "alembic.ini")))
    head = script.get_current_head()
    previous = script.get_revision(head).down_revision
    assert head and isinstance(previous, str)

    up = _alembic(scratch, "upgrade", "head")
    assert up.returncode == 0, up.stdout + up.stderr
    assert _version(scratch) == head
    after_first = _tables(scratch)

    down = _alembic(scratch, "downgrade", previous)
    assert down.returncode == 0, down.stdout + down.stderr
    assert _version(scratch) == previous
    before = _tables(scratch)
    if head == "0067":   # K-185: yeni giriş tabloları geri alınınca kalkar, kalkan tablolar geri gelir
        assert {"param.WorkPattern", "param.OvertimeLimit", "param.FactoryCalendar"} <= after_first - before
        assert {"core.Calendar", "core.CalendarDay", "core.ResourceCapacityProfile", "core.ResourceDowntime", "param.ResourcePeriodLimit"} <= before - after_first

    again = _alembic(scratch, "upgrade", "head")
    assert again.returncode == 0, again.stdout + again.stderr
    assert _version(scratch) == head and _tables(scratch) == after_first

    check = _alembic(scratch, "check")   # şema modellerle aynı: yeni geçiş gerekmiyor
    assert check.returncode == 0, check.stdout + check.stderr


def test_0084_closes_manual_flags_but_keeps_used_and_deliberate_ones(scratch):
    """K-203 (geçiş 0084): 0052'den sonra "Evet" ile eklenen alanlar kapanır. Manuel değeri olan alan ve System owner'ın son olarak açtığı alan açık kalır;
    listede olmayan alana dokunulmaz. Geri alış listedeki alanları yeniden açar."""
    assert _alembic(scratch, "upgrade", "0083").returncode == 0
    engine = sa.create_engine(scratch)
    flag = "SELECT TableName + N'.' + FieldName, ManualOverrides FROM adm.FieldDefinition WHERE TableName + N'.' + FieldName IN :keys"
    keys = ("ResourceGroup.IsCritical", "ResourceGroup.IsMachine", "ResourceGroup.CapacityUnit", "ResourceGroupMember.AdditionalText1",
            "WorkPattern.DayMon", "Material.MaterialGroup")
    try:
        with engine.begin() as c:
            c.execute(sa.text("ALTER TABLE adm.ManualValue NOCHECK CONSTRAINT ALL"))    # deneme veritabanı: kullanıcı satırı kurulmaz
            c.execute(sa.text("UPDATE adm.FieldDefinition SET ManualOverrides = 1 WHERE TableName + N'.' + FieldName IN :keys").bindparams(
                sa.bindparam("keys", expanding=True)), {"keys": list(keys)})      # eski kurulumdaki hâl: yeni alanlar "Evet" eklenmişti
            c.execute(sa.text("INSERT INTO adm.ManualValue (TableName, RecordKey, FieldName, Value, UnderlyingSource, IsBaseChanged, CreatedBy, CreatedAt, UpdatedBy, UpdatedAt) "
                              "VALUES (N'ResourceGroup', N'1', N'IsCritical', N'1', N'ERP', 0, 1, SYSUTCDATETIME(), 1, SYSUTCDATETIME())"))
            for at, new in (("2026-11-01", "false"), ("2026-11-02", "true")):          # kapatıp yeniden açtı: bilerek açık
                c.execute(sa.text("INSERT INTO adm.AuditLog ([At], Action, ObjectType, ObjectKey, NewValue) VALUES (:at, N'Manuel değişikliği', N'FieldDefinition', "
                                  "N'ResourceGroup.CapacityUnit', :v)"), {"at": at, "v": '{"ManualOverrides": ' + new + "}"})
        up = _alembic(scratch, "upgrade", "0084")
        assert up.returncode == 0, up.stdout + up.stderr
        q = sa.text(flag).bindparams(sa.bindparam("keys", expanding=True))
        with engine.connect() as c:
            got = dict(c.execute(q, {"keys": list(keys)}).all())
            assert got == {"ResourceGroup.IsCritical": True, "ResourceGroup.CapacityUnit": True,              # manuel değeri var · bilerek açılmış
                           "ResourceGroup.IsMachine": False, "ResourceGroupMember.AdditionalText1": False, "WorkPattern.DayMon": False,
                           "Material.MaterialGroup": True}                                                     # listede değil: dokunulmadı
            assert c.execute(sa.text("SELECT COUNT(*) FROM adm.ManualValue")).scalar() == 1                    # değer silinmedi
        down = _alembic(scratch, "downgrade", "0083")
        assert down.returncode == 0, down.stdout + down.stderr
        with engine.connect() as c:
            assert dict(c.execute(q, {"keys": list(keys)}).all())["ResourceGroup.IsMachine"] is True
    finally:
        engine.dispose()


def test_0082_renames_the_saved_pegging_criterion(scratch):
    """K-202 (geçiş 0082): "Satın alma önerisi" ölçütü "Satın alma planı" oldu; senaryoların kayıtlı Arz sırası çevrilir (sıra ve yön korunur),
    geri alışta eski ada döner. Çevrilmeseydi eski ad tanımda bulunmadığı için atılır, kullanıcının sırası bozulurdu."""
    assert _alembic(scratch, "upgrade", "0081").returncode == 0
    engine = sa.create_engine(scratch)
    rows = "SELECT Side, Seq, Criterion, Direction FROM param.PeggingCriterion ORDER BY Side, Seq"
    try:
        with engine.begin() as c:
            sid = c.execute(sa.text("SELECT Id FROM param.ScenarioDefinition WHERE IsBase = 1")).scalar_one()
            for side, seq, name, direction in (("Arz", 1, "Satın alma önerisi", None), ("Arz", 2, "Dönem", "Azalan"), ("Arz", 3, "Stok", None),
                                               ("İhtiyaç", 1, "Tahmin", None)):
                c.execute(sa.text("INSERT INTO param.PeggingCriterion (ScenarioDefinitionId, Side, Seq, Criterion, Direction) VALUES (:s, :side, :seq, :n, :d)"),
                          {"s": sid, "side": side, "seq": seq, "n": name, "d": direction})
        up = _alembic(scratch, "upgrade", "0082")
        assert up.returncode == 0, up.stdout + up.stderr
        with engine.connect() as c:
            assert [tuple(r) for r in c.execute(sa.text(rows))] == [("Arz", 1, "Satın alma planı", None), ("Arz", 2, "Dönem", "Azalan"), ("Arz", 3, "Stok", None),
                                                                     ("İhtiyaç", 1, "Tahmin", None)]
            labels = dict(c.execute(sa.text("SELECT FieldName, StandardLabel FROM adm.FieldDefinition WHERE TableName = N'WorkOrder' AND FieldName IN (N'ProductionOrderType', N'Status')")).all())
            assert labels == {"ProductionOrderType": "Üretim siparişi tipi", "Status": "Üretim siparişi durumu"}          # görünen adlar sözlükte de yenilendi
        down = _alembic(scratch, "downgrade", "0081")
        assert down.returncode == 0, down.stdout + down.stderr
        with engine.connect() as c:
            assert [r[2] for r in c.execute(sa.text(rows))][0] == "Satın alma önerisi"
    finally:
        engine.dispose()


def test_0077_cleans_user_definitions_and_keeps_renamed_data(scratch):
    """K-198 (geçiş 0077): kalkan alanları kullanan kullanıcı tanımları silinir ve çıktıda listelenir; malzemedeki eski adı kullananlar yeni ada
    çevrilir; malzemede elle girilmiş değer silinir, alttaki değer geçerli olur; arzın sipariş alanları bağlı satırdan doldurulur."""
    up = _alembic(scratch, "upgrade", "0076")
    assert up.returncode == 0, up.stdout + up.stderr
    engine = sa.create_engine(scratch)
    now = "SYSUTCDATETIME()"
    try:
        with engine.begin() as c:
            for table in ("adm.ManualValue", "adm.TableView", "adm.TableViewStandard", "core.Material", "core.Stock", "core.SalesOrderLine"):
                c.execute(sa.text(f"ALTER TABLE {table} NOCHECK CONSTRAINT ALL"))   # deneme veritabanı: kullanıcı, birim ve parti satırı kurulmaz
            loc = c.execute(sa.text("INSERT INTO core.Location (Code, IsActive) OUTPUT inserted.Id VALUES (N'G-1', 1)")).scalar_one()
            c.execute(sa.text(f"INSERT INTO core.Material (Id, LocationId, Code, BaseUom, VersionFrom, BusinessKey, UpdatedAt, IsCustomTracked) "
                              f"VALUES (1, :l, N'G-M', N'ADET', 1, N'k', {now}, 1)"), {"l": loc})
            c.execute(sa.text(f"INSERT INTO core.SalesOrderLine (Id, LocationId, OrderNo, [LineNo], LineItemNo, CustomerId, MaterialId, OpenQuantity, RequestedDate, "
                              f"VersionFrom, BusinessKey, UpdatedAt) VALUES (7, :l, N'G-S', 10, 2, 1, 1, 1, '2026-12-01', 1, N'k', {now})"), {"l": loc})
            c.execute(sa.text(f"INSERT INTO core.Stock (Id, LocationId, MaterialId, Quantity, SalesOrderLineId, VersionFrom, BusinessKey, UpdatedAt, IsCustomTracked) "
                              f"VALUES (1, :l, 1, 5, 7, 1, N'k1', {now}, 1), (2, :l, 1, 5, NULL, 1, N'k2', {now}, 0)"), {"l": loc})
            c.execute(sa.text(f"INSERT INTO adm.ManualValue (TableName, RecordKey, FieldName, Value, UnderlyingValue, CreatedBy, CreatedAt, UpdatedBy, UpdatedAt) "
                              f"VALUES (N'Material', N'1', N'IsCustomTracked', N'1', N'0', 1, {now}, 1, {now})"))

            def rule(entity, name, target):
                return c.execute(sa.text("INSERT INTO adm.DataRule (EntityName, Name, Seq, TargetField, ResultKind, ApplyMode, IsActive, ConditionText) OUTPUT inserted.Id "
                                         "VALUES (:e, :n, 1, :t, N'Değer', N'Boşsa', 1, N'Özel takip boş')"), {"e": entity, "n": name, "t": target}).scalar_one()

            rule("Material", "malzeme kuralı", "IsCustomTracked")
            rule("Customer", "müşteri kuralı", "IsCustomTracked")
            rule("ProjectGroup", "grup kuralı", "Priority")
            by_condition = rule("Project", "proje kuralı", "Priority")
            rule("Stock", "kalan kural", "IsActive")
            c.execute(sa.text("INSERT INTO adm.DataRuleCondition (DataRuleId, GroupNo, FieldName, Operator) VALUES (:r, 1, N'TrackingRule', N'boş')"), {"r": by_condition})

            def check(entity, name, field):
                rid = c.execute(sa.text("INSERT INTO adm.ValidationRule (EntityName, Code, Name, Kind, CheckType, Severity, Message, IsActive, IsCustomized) OUTPUT inserted.Id "
                                        "VALUES (:e, :c, :n, N'Kullanıcı', N'Mantıksal', N'Uyarı', N'm', 1, 0)"), {"e": entity, "c": f"USR.{name}", "n": name}).scalar_one()
                c.execute(sa.text("INSERT INTO adm.ValidationRuleCondition (ValidationRuleId, GroupNo, FieldName, Operator) VALUES (:r, 1, :f, N'boş')"), {"r": rid, "f": field})

            check("Stock", "stok kontrolü", "IsCustomTracked")
            check("Material", "malzeme kontrolü", "IsCustomTracked")
            for list_name, name, definition in (("transaction-stock", "stok görünümü", '{"columns": ["LotNo", "IsCustomTracked"]}'),
                                                ("transaction-project", "proje görünümü", '{"columns": ["Code", "ProjectGroupCode"]}'),
                                                ("master-customer", "müşteri görünümü", '{"columns": ["Code", "IsCustomTracked"]}'),
                                                ("transaction-sales-order", "sipariş görünümü", '{"columns": ["OrderNo", "MaterialId/IsCustomTracked"]}')):
                c.execute(sa.text(f"INSERT INTO adm.TableView (ListName, OwnerUserId, Name, IsShared, Definition, CreatedAt, UpdatedAt) "
                                  f"VALUES (:l, 1, :n, 0, :d, {now}, {now})"), {"l": list_name, "n": name, "d": definition})

        up = _alembic(scratch, "upgrade", "head")
        assert up.returncode == 0, up.stdout + up.stderr
        for line in ("Veri kuralı · Customer · müşteri kuralı", "Veri kuralı · ProjectGroup · grup kuralı", "Veri kuralı · Project · proje kuralı",
                     "Validasyon kuralı · Stock · stok kontrolü", "Kayıtlı görünüm · transaction-project · proje görünümü",
                     "Kayıtlı görünüm · master-customer · müşteri görünümü", "malzemede silinen manuel 'özel takip' değeri: 1"):
            assert line in up.stdout, (line, up.stdout)
        assert "malzeme kuralı" not in up.stdout and "kalan kural" not in up.stdout and "stok görünümü" not in up.stdout
        with engine.connect() as c:
            rules = dict(c.execute(sa.text("SELECT Name, TargetField FROM adm.DataRule")).all())
            assert rules == {"malzeme kuralı": "IsCustomAllocated", "kalan kural": "IsActive"}
            assert c.execute(sa.text("SELECT ConditionText FROM adm.DataRule WHERE Name = N'malzeme kuralı'")).scalar() == "Özel alokasyon boş"
            assert c.execute(sa.text("SELECT COUNT(*) FROM adm.DataRuleCondition")).scalar() == 0
            checks = c.execute(sa.text("SELECT r.Name, x.FieldName FROM adm.ValidationRule r JOIN adm.ValidationRuleCondition x ON x.ValidationRuleId = r.Id")).all()
            assert [tuple(r) for r in checks] == [("malzeme kontrolü", "IsCustomAllocated")]
            views = dict(c.execute(sa.text("SELECT Name, Definition FROM adm.TableView")).all())
            assert views == {"stok görünümü": '{"columns": ["LotNo", "IsCustomAllocated"]}', "sipariş görünümü": '{"columns": ["OrderNo", "MaterialId/IsCustomAllocated"]}'}
            assert c.execute(sa.text("SELECT COUNT(*) FROM adm.ManualValue")).scalar() == 0
            assert c.execute(sa.text("SELECT IsCustomAllocated FROM core.Material WHERE Id = 1")).scalar() is False   # alttaki değer geri geldi
            stock = c.execute(sa.text("SELECT Id, SalesOrderNo, SalesOrderLineNo, SalesOrderLineItemNo, IsCustomAllocated FROM core.Stock ORDER BY Id")).all()
            assert [tuple(r) for r in stock] == [(1, "G-S", 10, 2, True), (2, None, None, None, False)]   # bayrak değeri yerinde; ilk aktarım yeniden hesaplar
            assert "core.ProjectGroup" not in _tables(scratch)
    finally:
        engine.dispose()


def test_migrations_do_not_read_the_live_model_or_catalog():
    """K-197: geçiş güncel modelden (`metadata.tables`) ve uygulama kodundan (`app.*`) okumaz; yazdığı değerleri sabit taşır (`db/frozen.py`).
    İstisnalar: veri sözlüğü eşitlemesi (`sync(bind, metadata)`) ve 0055'in yalnız verili veritabanında çalışan geçmiş doldurması."""
    import re
    allowed = {"0055_alan_degisikligi_k_173.py": ("from app.history.backfill import backfill",)}
    problems = []
    for path in sorted((ROOT / "db" / "migrations" / "versions").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            code = line.split("#")[0]
            if "metadata.tables" in code or re.search(r"^\s*(from|import)\s+app(\.|\s|$)", code) or re.search(r"metadata\.(sorted_tables|schema)", code):
                if code.strip() not in allowed.get(path.name, ()):
                    problems.append(f"{path.name}: {code.strip()[:100]}")
    assert not problems, problems
