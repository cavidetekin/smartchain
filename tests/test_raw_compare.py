"""Dünden bugüne (fonksiyon 101; K-133, K-156, K-159, K-160): tablonun iki hâlinin karşılaştırması, yükleme modları, gün sınırı, temizliğin "dün" koruması, geçişin doldurması, API.

Hesap testleri tek oturumda yazılıp geri alınır; API ve zincir testleri commit eder, sonunda temizler. Test veritabanında (K-103)."""
import importlib.util
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.api.permissions import ADMIN, END_USER, KEY_USER, SYSTEM_OWNER
from app.cleanup import raw as cleanup
from app.compare import raw as compare
from app.integration import contract
from app.validation import current, engine as validation
from db.models import metadata

from auth_helpers import auth, ensure_user
from validation_helpers import clean, new_client, run_validations

pytestmark = pytest.mark.db

DAY1, DAY2, DAY5 = datetime(2030, 1, 10, 9, 0), datetime(2030, 1, 11, 9, 0), datetime(2030, 1, 15, 9, 0)
FULL, CHANGED_MODE = "Tam", "Değişen"
BATCH = metadata.tables["adm.ImportBatch"]
STG = metadata.tables["stg.Customer"]


def load(s, rows: list[dict], mode: str, at: datetime, entity_table=STG) -> int:
    """Parti açar, satırları yazar, güncel hâle işler (zamanı verilen anda)."""
    entity = entity_table.name
    batch = s.execute(sa.insert(BATCH).values(Method="Excel", EntityName=entity, LoadType=mode, ReceivedAt=at, Status="Alındı").returning(BATCH.c.Id)).scalar_one()
    names = {k for r in rows for k in r}
    s.execute(sa.insert(entity_table), [{"ImportBatchId": batch, "SourceRowNo": i + 2, "IsCurrent": False, **dict.fromkeys(names), **r} for i, r in enumerate(rows)])
    current.apply_batch(s, entity, batch, mode, now=at)
    return batch


def customer(code: str, name: str = "Ad", **extra) -> dict:
    return {"Code": code, "Name": name, "IsActive": True, **extra}


def summary(s, entity="Customer") -> dict:
    return dict(s.execute(sa.select(compare.SUMMARY).where(compare.SUMMARY.c.EntityName == entity)).mappings().one())


def details(s, kind: str, entity="Customer") -> list[tuple]:
    r = compare.ROW
    return [tuple(x) for x in s.execute(sa.select(r.c.RowKey, r.c.FieldLabel, r.c.OldValue, r.c.NewValue).where(r.c.EntityName == entity, r.c.Kind == kind).order_by(r.c.RowKey, r.c.FieldLabel))]


@pytest.fixture
def s(db_engine):
    clean(db_engine)
    with Session(db_engine) as session:
        yield session
        session.rollback()
    clean(db_engine)


def counts(row: dict) -> tuple:
    return row["YesterdayRows"], row["TodayRows"], row["NewCount"], row["MissingCount"], row["ChangedCount"]


def test_new_column_is_not_part_of_the_contract():
    assert "SupersededAt" not in [f.name for f in contract.fields("Customer")] and "SupersededAt" not in [c.name for c in contract.stg_columns("Customer")]


def test_no_previous_data(s):
    load(s, [customer("A"), customer("B")], FULL, DAY1)
    compare.compute(s, "Customer")
    row = summary(s)
    assert (row["State"], row["YesterdayAt"], row["TodayRows"], row["NewCount"], row["TodayLoad"]) == (compare.NO_PREVIOUS, None, 2, None, "Tam")
    assert not details(s, compare.NEW)


def test_full_load_new_missing_changed(s):
    load(s, [customer("A", "Ali"), customer("B"), customer("C")], FULL, DAY1)
    load(s, [customer("A", "Veli"), customer("B"), customer("D")], FULL, DAY2)
    compare.compute(s, "Customer")
    row = summary(s)
    assert (row["State"], row["YesterdayAt"], row["TodayAt"], row["TodayLoad"]) == (compare.READY, DAY1, DAY2, "Tam") and counts(row) == (3, 3, 1, 1, 1)
    assert details(s, compare.NEW) == [("D", None, None, None)] and details(s, compare.MISSING) == [("C", None, None, None)]
    assert details(s, compare.CHANGED) == [("A", "Müşteri adı", "Ali", "Veli")]


def test_changed_mode_never_produces_missing(s):
    """Ekle / güncelle: dosyada olmayan kayıtlar güncel hâlde kalır; satır sayısı dosyanın değil tablonun hâlidir."""
    load(s, [customer(c) for c in "ABCD"], FULL, DAY1)
    load(s, [customer("A", "Yeni ad"), customer("E")], CHANGED_MODE, DAY2)
    compare.compute(s, "Customer")
    row = summary(s)
    assert counts(row) == (4, 5, 1, 0, 1) and row["TodayLoad"] == "Ekle / güncelle"
    assert details(s, compare.NEW)[0][0] == "E" and not details(s, compare.MISSING)


def test_same_day_loads_keep_yesterday_and_are_mixed(s):
    load(s, [customer("A"), customer("B")], FULL, DAY1)
    load(s, [customer("A")], FULL, DAY2)                                     # B gelmedi
    load(s, [customer("B"), customer("C")], CHANGED_MODE, DAY2 + timedelta(hours=3))  # B aynı gün geri geldi
    compare.compute(s, "Customer")
    row = summary(s)
    assert row["YesterdayAt"] == DAY1 and row["TodayAt"] == DAY2 + timedelta(hours=3) and row["TodayLoad"] == "Karma"
    assert counts(row) == (2, 3, 1, 0, 0) and details(s, compare.NEW)[0][0] == "C"


def test_gap_days_use_latest_earlier_day(s):
    load(s, [customer("A")], FULL, DAY1)
    load(s, [customer("A"), customer("B")], FULL, DAY5)
    compare.compute(s, "Customer")
    assert summary(s)["YesterdayAt"] == DAY1 and summary(s)["NewCount"] == 1


def test_day_boundary_is_local_midnight(s):
    start = compare.day_start_utc(DAY2)
    load(s, [customer("A")], FULL, start - timedelta(minutes=30))
    load(s, [customer("A"), customer("B")], FULL, start + timedelta(minutes=30))
    compare.compute(s, "Customer")
    assert summary(s)["YesterdayAt"] == start - timedelta(minutes=30) and summary(s)["NewCount"] == 1
    assert (compare.day_start_utc(start) == start) and compare.day_start_utc(start - timedelta(seconds=1)) == start - timedelta(days=1)


def test_value_comparison_rules(s):
    """Boşlar eşit, boşla dolu farklı, aynı değer değişiklik değil, büyük/küçük harf değişiklik; sayı ve bayrak okunur metinle."""
    load(s, [customer("A", "Ad", City=None, Priority=None), customer("B", "ad", City="Ankara", Priority=5, AllowPartialDelivery=True), customer("C", City=None)], FULL, DAY1)
    load(s, [customer("A", "Ad", City="İzmir", Priority=7), customer("B", "AD", City=None, Priority=5, AllowPartialDelivery=False), customer("C", City=None)], FULL, DAY2)
    compare.compute(s, "Customer")
    got = details(s, compare.CHANGED)
    label = {c.name: l for c, l in compare._compared(s, "Customer", ["Code"])}
    assert ("A", label["City"], None, "İzmir") in got and ("A", label["Priority"], None, "7") in got
    assert ("B", label["Name"], "ad", "AD") in got and ("B", label["City"], "Ankara", None) in got and ("B", label["AllowPartialDelivery"], "Evet", "Hayır") in got
    assert summary(s)["ChangedCount"] == 2 and not [g for g in got if g[0] == "C"]


def test_unlabelled_additional_fields_are_not_compared(s):
    load(s, [customer("A", AdditionalText1="x", AdditionalText2="x")], FULL, DAY1)
    load(s, [customer("A", AdditionalText1="y", AdditionalText2="y")], FULL, DAY2)
    fd = metadata.tables["adm.FieldDefinition"]
    s.execute(sa.update(fd).where(fd.c.TableName == "Customer", fd.c.FieldName == "AdditionalText1").values(Label="Bölge kodu"))
    s.execute(sa.update(fd).where(fd.c.TableName == "Customer", fd.c.FieldName == "AdditionalText2").values(Label=None))
    compare.compute(s, "Customer")
    assert details(s, compare.CHANGED) == [("A", "Bölge kodu", "x", "y")]


def test_row_dropped_in_precheck_is_not_missing(s):
    """Tam yüklemede ön kontrolde düşen satırın eski hâli güncel kalır (K-133): gelmeyen sayılmaz."""
    load(s, [customer("A"), customer("B")], FULL, DAY1)
    batch = s.execute(sa.insert(BATCH).values(Method="Excel", EntityName="Customer", LoadType=FULL, ReceivedAt=DAY2, Status="Alındı").returning(BATCH.c.Id)).scalar_one()
    s.execute(sa.insert(STG), [{"ImportBatchId": batch, "SourceRowNo": 2, "IsCurrent": False, **customer("A")}])
    s.execute(sa.insert(metadata.tables["adm.ImportFinding"]).values(ImportBatchId=batch, RowNo=3, Severity="Hata", CheckCode="T", Message="Hatalı", RowKey="B"))
    current.apply_batch(s, "Customer", batch, FULL, now=DAY2)
    compare.compute(s, "Customer")
    assert summary(s)["MissingCount"] == 0 and summary(s)["TodayRows"] == 2


def test_rules_do_not_affect_comparison(s):
    """Karşılaştırma ham katmandan: işlenmiş katmandaki değer karışmaz."""
    load(s, [customer("A", "Ham")], FULL, DAY1)
    batch = load(s, [customer("A", "Ham")], FULL, DAY2)
    row = s.execute(sa.select(STG.c.StagingRowId).where(STG.c.ImportBatchId == batch)).scalar_one()
    prc = metadata.tables["prc.Customer"]
    s.execute(sa.insert(prc).values(StagingRowId=row, ImportBatchId=batch, SourceRowNo=2, Code="A", Name="Kuralla değişti", IsActive=True))
    compare.compute(s, "Customer")
    assert summary(s)["ChangedCount"] == 0


def test_refresh_skips_when_current_and_records_failure(s, monkeypatch):
    load(s, [customer("A")], FULL, DAY1)
    load(s, [customer("A")], FULL, DAY2)
    calls = []
    original = compare.compute
    monkeypatch.setattr(compare, "compute", lambda session, entity: calls.append(entity) or original(session, entity))
    compare.refresh(s, "Customer")
    compare.refresh(s, "Customer")
    assert calls == ["Customer"]

    def boom(session, entity):
        raise RuntimeError("deneme")
    load(s, [customer("A"), customer("B")], FULL, DAY5)
    monkeypatch.setattr(compare, "compute", boom)
    compare.refresh(s, "Customer")
    assert summary(s)["State"] == compare.FAILED
    monkeypatch.setattr(compare, "compute", original)
    compare.refresh(s, "Customer")                                            # düşen hesap sonraki işte yeniden denenir
    assert summary(s)["State"] == compare.READY


def rows_of(s) -> list[str]:
    return sorted(s.execute(sa.select(STG.c.Code, STG.c.Name)).all(), key=str)


def test_cleanup_keeps_yesterday_until_next_day(s):
    """Dün anından sonra güncel hâlden çıkan satır süresi dolsa da silinmez; yeni gün gelince bir sonraki temizlikte silinir; RawDeletedAt satır silmeyi durdurmaz."""
    now = DAY5 + timedelta(days=30)
    load(s, [customer("A", "bir"), customer("B", "bir")], FULL, DAY1)
    load(s, [customer("B", "iki")], FULL, DAY2)                              # A ve eski B gün 2'de çıktı; dün anı gün 1
    assert cleanup.preview(s, 7, now=now)["rows"] == 0
    summary_first, _ = cleanup.run(s, 7, now=now)
    assert summary_first.rows == 0 and len(rows_of(s)) == 3                   # "dün" korunuyor; partiler işaretlendi
    load(s, [customer("B", "üç")], FULL, DAY5)                                # dün anı gün 2'ye ilerledi: gün 2'de çıkanlar artık "dün" değil
    assert cleanup.preview(s, 7, now=now)["rows"] == 2
    cleanup.run(s, 7, now=now)
    assert [r[1] for r in rows_of(s)] == ["iki", "üç"]                        # gün 5'te çıkan "iki" dün hâlinde; "üç" güncel


def test_cleanup_protects_one_state_not_intraday_rows(s):
    """Korunan veri yalnız "dün" hâlidir: aynı gün gelip yine aynı gün çıkan ara satır korunmaz."""
    now = DAY5 + timedelta(days=30)
    load(s, [customer("A", "dün")], FULL, DAY1)
    load(s, [customer("A", "ara")], FULL, DAY2)
    load(s, [customer("A", "son")], FULL, DAY2 + timedelta(hours=2))
    assert cleanup.preview(s, 7, now=now)["rows"] == 1
    cleanup.run(s, 7, now=now)
    assert [r[1] for r in rows_of(s)] == ["dün", "son"]


def test_cleanup_deletes_abandoned_rows_regardless_of_yesterday(s):
    now = DAY5 + timedelta(days=30)
    load(s, [customer("A")], FULL, DAY1)
    load(s, [customer("A")], FULL, DAY2)
    pending = s.execute(sa.insert(BATCH).values(Method="Excel", EntityName="Customer", LoadType=FULL, ReceivedAt=DAY1, Status="Ön kontrol").returning(BATCH.c.Id)).scalar_one()
    s.execute(sa.insert(STG), [{"ImportBatchId": pending, "SourceRowNo": 2, "IsCurrent": False, **customer("X")}])
    cleanup.run(s, 7, now=now)
    assert "X" not in [r[0] for r in rows_of(s)]


def test_migration_backfill(s):
    path = Path(__file__).resolve().parents[1] / "db" / "migrations" / "versions" / "0048_dunden_bugune.py"
    spec = importlib.util.spec_from_file_location("m0048", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.op = SimpleNamespace(execute=lambda sql: s.execute(sa.text(sql)))
    def batch(at, mode, status="Alındı"):
        return s.execute(sa.insert(BATCH).values(Method="SQL", EntityName="Customer", LoadType=mode, ReceivedAt=at, Status=status).returning(BATCH.c.Id)).scalar_one()
    b1, b2, b3 = batch(DAY1, FULL), batch(DAY2, CHANGED_MODE), batch(DAY5, FULL)
    pending = batch(DAY5 + timedelta(hours=1), FULL, "Ön kontrol")
    rows = [(b1, "A", False), (b1, "B", False), (b2, "B", False), (b3, "B", True), (pending, "Z", False)]
    s.execute(sa.insert(STG), [{"ImportBatchId": b, "SourceRowNo": i + 2, "IsCurrent": c, **customer(code)} for i, (b, code, c) in enumerate(rows)])
    module._backfill()
    at = lambda b: s.execute(sa.select(BATCH.c.AppliedAt).where(BATCH.c.Id == b)).scalar()  # noqa: E731
    assert (at(b1), at(b2), at(b3), at(pending)) == (DAY1, DAY2, DAY5, None)
    got = {(b, c): v for b, c, v in s.execute(sa.select(STG.c.ImportBatchId, STG.c.Code, STG.c.SupersededAt))}
    assert got[(b1, "A")] == DAY5 and got[(b1, "B")] == DAY2 and got[(b2, "B")] == DAY5    # Ekle / güncelle yalnız aynı anahtarı çıkarır
    assert got[(b3, "B")] is None and got[(pending, "Z")] is None


def test_chain_computes_and_api_serves(db_engine):
    clean(db_engine)
    with db_engine.begin() as c:
        people = {r: ensure_user(c, f"pytest.dunden.{r.replace(' ', '-').lower()}", r, f"Ad {r}") for r in (SYSTEM_OWNER, ADMIN, KEY_USER, END_USER)}
    try:
        with Session(db_engine) as s:
            load(s, [customer("RC-1", "Ali"), customer("RC-2"), customer("RC-3")], FULL, DAY1)
            load(s, [customer("RC-1", "Veli"), customer("RC-2"), customer("RC-4")], FULL, DAY2)
            validation.enqueue(s, "Customer", validation.SCOPE_TABLE, validation.TRIGGER_UPLOAD)
        run_validations(db_engine)
        client = new_client()
        for role, user in people.items():
            r = client.post("/api/raw-compare/query", headers=auth(user), json={"fields": ["Name", "NewCount", "MissingCount", "ChangedCount", "ChangePct", "State", "TodayLoad"], "limit": 50})
            assert r.status_code == 200, (role, r.text)
        rows = {x["Entity"]: x for x in r.json()["rows"]}
        assert len(rows) == 25
        assert (rows["Customer"]["NewCount"], rows["Customer"]["MissingCount"], rows["Customer"]["ChangedCount"], rows["Customer"]["State"]) == (1, 1, 1, compare.READY)
        assert rows["Material"]["State"] == "Veri yok"
        h = auth(people[END_USER])
        new = client.post("/api/raw-compare-new-Customer/query", headers=h, json={"fields": ["RowKey", "Code", "Name"], "limit": 10}).json()["rows"]
        assert [x["Code"] for x in new] == ["RC-4"]
        missing = client.post("/api/raw-compare-missing-Customer/query", headers=h, json={"fields": ["RowKey", "Name"], "limit": 10}).json()["rows"]
        assert [x["RowKey"] for x in missing] == ["RC-3"]
        body = {"fields": ["RowKey", "FieldLabel", "OldValue", "NewValue"], "limit": 10, "filters": [{"field": "EntityName", "op": "equals", "value": "Customer"}]}
        changes = client.post("/api/raw-compare-changes/query", headers=h, json=body).json()["rows"]
        assert [(x["RowKey"], x["OldValue"], x["NewValue"]) for x in changes] == [("RC-1", "Ali", "Veli")]
        body["filters"] = [{"field": "EntityName", "op": "equals", "value": "Material"}]
        assert client.post("/api/raw-compare-changes/query", headers=h, json=body).json()["rows"] == []
        s_body = client.get("/api/raw-compare/summary", headers=h).json()
        assert (s_body["tables"], s_body["new"], s_body["missing"], s_body["changed"]) == (1, 1, 1, 1)
    finally:
        clean(db_engine)
        with db_engine.begin() as c:
            c.execute(sa.text("DELETE FROM adm.Job WHERE JobType = N'Validasyon'"))
