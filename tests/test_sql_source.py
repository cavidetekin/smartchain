"""SQL kaynağı (K-130): sinyal kuralı, uyum denetimi, yalnız okuma. Veritabanısız kısım önce; gerçek view'lar SmartchainIntegration_test'te."""
from datetime import datetime
from pathlib import Path

import pytest
import sqlalchemy as sa

from app.data.synthetic.sql import ensure_database
from app.integration import contract
from app.integration.sql_source import COMPATIBLE, INCOMPATIBLE, NO_SIGNAL, READY, RUNNING, WITH_WARNINGS, Source, SourceError, compare_columns, definition_hash, read_signal, valid_database

import testdb
from integration_helpers import DATABASE, _written, base_url, integration_db, run_sql  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
T1, T2, T3, T4 = (datetime(2026, 11, 5, h) for h in (1, 2, 3, 4))


def test_signal_none():
    assert read_signal([]).state == NO_SIGNAL


def test_signal_table_row_alone():
    s = read_signal([(5, T1, T2)])
    assert (s.state, s.id) == (READY, 5)


def test_signal_latest_finished_wins_between_table_and_all():
    """Toplu satır 7, tablo satırı 9: en son biten geçerli; sıra değişse de aynı."""
    assert read_signal([(7, T1, T2), (9, T3, T4)]).id == 9
    assert read_signal([(9, T1, T4), (7, T2, T3)]).id == 9


def test_signal_running_when_latest_started_is_open():
    s = read_signal([(7, T1, T2), (9, T3, None)])
    assert (s.state, s.id) == (RUNNING, 9)


def test_signal_old_open_row_is_ignored_after_a_newer_refresh():
    """Yarım kalmış eski yenileme, sonraki yenileme bittiyse çekimi kilitlemez."""
    s = read_signal([(7, T1, None), (9, T2, T3)])
    assert (s.state, s.id) == (READY, 9)


def test_signal_without_started_at():
    assert read_signal([(3, None, T2)]).state == READY


def resource_columns(**over):
    columns = {f.name: ("nvarchar", 10) if f.kind == "text" else ("int" if f.kind == "integer" else "bit" if f.kind == "bool" else "decimal" if f.kind == "number" else "date", 0)
               for f in contract.fields("Resource")}
    columns.update(over)
    return {k: v for k, v in columns.items() if v is not None}


def test_all_columns_are_compatible():
    c = compare_columns("Resource", resource_columns())
    assert c.status == COMPATIBLE and c.matched == c.expected == len(contract.fields("Resource")) and not c.message


def test_missing_required_column_is_an_error():
    c = compare_columns("Resource", resource_columns(Code=None))
    assert c.status == INCOMPATIBLE and c.matched == c.expected - 1 and "Zorunlu kolon yok: Code" in c.errors[0]


def test_missing_optional_column_only_warns():
    c = compare_columns("Resource", resource_columns(Name=None))
    assert c.status == WITH_WARNINGS and not c.errors and "İsteğe bağlı kolon yok: Name" in c.warnings[0] and "Name" not in c.columns


def test_extra_column_warns_and_is_not_read():
    c = compare_columns("Resource", resource_columns(Fazla=("int", 0)))
    assert c.status == WITH_WARNINGS and "Tanınmayan kolon yok sayıldı: Fazla" in c.warnings[0] and "Fazla" not in c.columns


def test_unlabelled_additional_column_warns():
    c = compare_columns("Resource", resource_columns(AdditionalText1=("nvarchar", 10)))
    assert "Etiketsiz ek alan yok sayıldı: AdditionalText1" in c.warnings[0]
    assert compare_columns("Resource", resource_columns(AdditionalText1=("nvarchar", 10)), {"AdditionalText1": "Etiket"}).matched == c.expected + 1


def test_text_in_number_column_warns():
    number = next(f.name for f in contract.fields("BOM") if f.kind == "number")
    columns = {f.name: ("nvarchar", 50) for f in contract.fields("BOM")}
    c = compare_columns("BOM", columns)
    assert c.status == WITH_WARNINGS and any(number in w and "sayı" in w for w in c.warnings) and not c.errors


def test_long_text_column_warns():
    long = compare_columns("Resource", resource_columns(Code=("nvarchar", -1)))
    assert any("Kolon uzun: Code" in w for w in long.warnings)


def test_column_name_is_exact():
    c = compare_columns("Resource", resource_columns(Code=None, code=("nvarchar", 10)))
    assert c.status == INCOMPATIBLE


def test_database_name_rule():
    assert valid_database("SmartchainIntegration_test")
    assert not valid_database("x]; DROP DATABASE y") and not valid_database("a b") and not valid_database("")


def test_tests_never_read_a_real_database():
    with pytest.raises(RuntimeError, match="_test"):
        Source(sa.engine.make_url("mssql+pyodbc://@localhost/Smartchain_test?driver=ODBC+Driver+18+for+SQL+Server"), "SmartchainIntegration", 5)


def test_integration_setup_gives_read_only():
    """Kurulum servis hesaplarına yalnız okuma verir (K-130); test sırasında gerçek ada dokunmaz."""
    setup_db = testdb._setup_db()
    statements = setup_db.integration_read_statements(["SUNUCU\servis"])
    assert any("db_datareader" in s for s in statements) and not any("db_datawriter" in s or "db_owner" in s for s in statements)
    with pytest.raises(RuntimeError, match="_test"):
        setup_db.setup_integration_database("x", "y", "SmartchainIntegration", [])


def test_synthetic_refuses_real_database_in_tests():
    with pytest.raises(RuntimeError, match="_test"):
        ensure_database(sa.engine.make_url("mssql+pyodbc://@localhost/x?driver=ODBC+Driver+18+for+SQL+Server"), "SmartchainIntegration", "Latin1_General_100_CI_AS_SC")


@pytest.mark.parametrize("path", ["app/integration/sql_source.py"])
def test_source_code_never_writes(path):
    """Bekçi (A-38 madde 7): kaynak okuma kodunda yazma ve DDL yok."""
    text = (ROOT / path).read_text(encoding="utf-8").upper()
    code = "\n".join(line for line in text.splitlines() if not line.strip().startswith("#"))
    for word in ("INSERT INTO", "UPDATE DBO", "UPDATE [", "DELETE FROM", "MERGE ", "TRUNCATE", "DROP ", "CREATE ", "ALTER ", "EXEC ", "EXECUTE "):
        assert word not in code, word


def test_pull_service_uses_only_the_read_source():
    """Çekim kodu entegrasyon bağlantısını yalnız Source üzerinden kullanır; kendi bağlantısını açmaz."""
    for path in ("app/api/services/pull.py", "app/api/services/integration.py"):
        text = (ROOT / path).read_text(encoding="utf-8")
        assert "create_engine" not in text and "pyodbc" not in text and "dbo.ERP" not in text


# --- Gerçek veritabanı ---

@pytest.mark.db
def source():
    return Source(base_url(), DATABASE, 15)


@pytest.mark.db
def test_signal_from_the_database(integration_db):  # noqa: F811
    run_sql("DELETE FROM dbo.ERP_LoadLog")
    with source() as s:
        assert s.signal("Material").state == NO_SIGNAL
    run_sql("INSERT INTO dbo.ERP_LoadLog (EntityName, StartedAt, FinishedAt) VALUES (NULL, '2026-11-05 01:00', '2026-11-05 02:00')")
    run_sql("INSERT INTO dbo.ERP_LoadLog (EntityName, StartedAt, FinishedAt) VALUES (N'BOM', '2026-11-05 03:00', '2026-11-05 04:00')")
    with source() as s:
        assert s.signal("Material").id < s.signal("BOM").id  # Malzeme toplu satırı, ağaç kendi satırını okur
    run_sql("INSERT INTO dbo.ERP_LoadLog (EntityName, StartedAt) VALUES (N'BOM', '2026-11-05 05:00')")
    with source() as s:
        assert s.signal("BOM").state == RUNNING and s.signal("Material").state == READY


@pytest.mark.db
def test_missing_signal_table(integration_db):  # noqa: F811
    run_sql("EXEC sp_rename 'dbo.ERP_LoadLog', 'ERP_LoadLog_yok'")
    try:
        with source() as s, pytest.raises(SourceError, match="ERP_LoadLog"):
            s.signal("Material")
    finally:
        run_sql("EXEC sp_rename 'dbo.ERP_LoadLog_yok', 'ERP_LoadLog'")


@pytest.mark.db
def test_real_view_is_compatible_and_read(integration_db):  # noqa: F811
    with source() as s:
        check = s.check_view("Material", "View_Material", {"AdditionalText1": "Malzeme sınıfı"})
        assert check.status == COMPATIBLE, check.message
        rows = s.sample("View_Material", check.columns, 3)
    assert len(rows) == 3 and rows[0][0] == 1 and rows[0][1]["LocationCode"] and rows[0][1]["Code"] and rows[0][1]["MaterialGroup"]


@pytest.mark.db
def test_text_date_is_converted_by_the_view(integration_db):  # noqa: F811
    with source() as s:
        check = s.check_view("SalesOrderLine", "View_SalesOrderLine")
        row = s.sample("View_SalesOrderLine", check.columns, 1)[0][1]
    assert hasattr(row["RequestedDate"], "year") and check.status == COMPATIBLE, check.message


@pytest.mark.parametrize("bad", ["View_Yok", "View_Material]; DROP TABLE dbo.ERP_Material; --", "ERP_Material"])
@pytest.mark.db
def test_unknown_or_injected_view_is_rejected(integration_db, bad):  # noqa: F811
    with source() as s:
        assert not s.view_exists(bad)
        with pytest.raises(SourceError, match="View bulunamadı"):
            list(s.read_rows(bad, ["Code"]))
    with source() as s:
        assert s.conn.execute(sa.text("SELECT OBJECT_ID('dbo.ERP_Material')")).scalar() is not None


@pytest.mark.db
def test_broken_view_is_reported(integration_db):  # noqa: F811
    run_sql("CREATE TABLE dbo.ERP_Gecici (A int)")
    run_sql("CREATE VIEW dbo.View_Bozuk AS SELECT A AS Code FROM dbo.ERP_Gecici")
    run_sql("DROP TABLE dbo.ERP_Gecici")
    try:
        with source() as s, pytest.raises(SourceError, match="okunamıyor"):
            s.view_columns("View_Bozuk")
    finally:
        run_sql("DROP VIEW dbo.View_Bozuk")


@pytest.mark.db
def test_definition_and_encrypted_view(integration_db):  # noqa: F811
    run_sql("CREATE TABLE dbo.ERP_Gecici (Code nvarchar(30))")
    run_sql("CREATE VIEW dbo.View_Sifreli WITH ENCRYPTION AS SELECT Code FROM dbo.ERP_Gecici")
    try:
        with source() as s:
            assert s.definition("View_Sifreli") is None
            first = s.definition("View_Material")
            assert "ERP_Material" in first and definition_hash(first) == definition_hash(first) and definition_hash(first) != definition_hash(first + " ")
    finally:
        run_sql("DROP VIEW dbo.View_Sifreli")
        run_sql("DROP TABLE dbo.ERP_Gecici")


@pytest.mark.db
def test_duplicate_keys_counted(integration_db):  # noqa: F811
    with source() as s:
        check = s.check_view("Material", "View_Material")
        assert s.duplicate_keys("Material", "View_Material", check.columns) == 1  # H4: SAT-040
        assert s.duplicate_keys("Stock", "View_Stock", s.check_view("Stock", "View_Stock").columns) == 0
