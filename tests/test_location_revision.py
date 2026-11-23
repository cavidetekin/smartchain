"""Lokasyon revizyonu (K-194): Fabrika takvimi lokasyon bazlıdır (kayıt lokasyon ister, lokasyon kilitli, liste alanı ve ilişki); iki lokasyonlu
kapasite hesabı, tetikleyici ve Kapasite özeti (bir lokasyonun takvim kaydı ötekini etkilemez); geçiş 0073'ün bağlama deyimi (tek lokasyon, çok
lokasyon, lokasyonsuz); lokasyon listesi; sentetik durma mesajı. Smartchain_test'te; ikinci lokasyonu yeni satırlarla kurar ve sonunda siler."""
import importlib.util
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.capacity import compute, triggers
from app.data.synthetic import dataset as d, load as synthetic_load
from app.params import resolve

import two_locations
from test_capacity import clean, ensure, fire, pattern, row, stored, working_days, world  # noqa: F401  (fixture'lar ve yardımcılar)
from test_capacity_entries import api, new, one, people, rows  # noqa: F401

pytestmark = pytest.mark.db
FC = "factory-calendar"
LOCKED = "Lokasyon kayıttan sonra değişmez; kaydı silip yeniden girin."


def tr(day: date) -> str:
    return f"{day:%d.%m.%Y}"


@pytest.fixture
def second(db_engine, world, clean):  # noqa: F811
    """İkinci lokasyon: birinci lokasyondakiyle aynı kodlu kaynak grubu (ISL3) ve kaynak (M3-01); gruba çalışma düzeni. Sonunda silinir."""
    two_locations.destroy(db_engine)
    built = two_locations.build(db_engine)
    pattern(db_engine, world["base"], world["start"] - timedelta(days=7), None, 8, ResourceGroupId=built["group"])
    yield built
    two_locations.destroy(db_engine)


def values(db_engine, scenario: int, a: date, b: date, *resources: int) -> dict:
    with Session(db_engine) as s:
        return {(r["ResourceId"], r["Date"]): r for r in compute.values(s, scenario, a, b, tuple(resources))}


# ------------------------------------------------------------------ giriş, liste, seçenekler

def test_factory_calendar_needs_a_location_and_keeps_it(api, db_engine, world, clean):  # noqa: F811
    """Fabrika takvimi kaydı lokasyon ister; lokasyon kayıttan sonra değişmez; listede Lokasyon ilk alan ve ilişki; fark satırı lokasyonu korur."""
    base, follower, loc = world["base"], world["follower"], world["location"]
    day = world["start"] + timedelta(days=30)
    body = dict(StartDate=tr(day), Name="pytest tatil", DayValue="Çalışılmıyor")
    for bad, problem in ((None, "Lokasyon seçilmeli."), ("", "Lokasyon seçilmeli."), (999_999, "Geçersiz lokasyon."), ("x", "Geçersiz lokasyon.")):
        details = new(api, FC, base, 422, LocationId=bad, **body)["details"]
        assert details == [{"field": "LocationId", "problem": problem}], (bad, details)
    assert new(api, FC, base, 422, **body)["details"] == [{"field": "LocationId", "problem": "Lokasyon seçilmeli."}]
    made = new(api, FC, base, LocationId=loc, **body)
    got = one(api, FC, base, made)
    assert (got["LocationCode"], got["LocationId"], got["Name"], got["EndDate"]) == (d.LOCATION_CODE, loc, "pytest tatil", day.isoformat())
    r = api.put(f"/api/capacity/{FC}?scenario_id={base}", json={"changes": [{"id": made, "field": "LocationCode", "value": "X"}, {"id": made, "field": "LocationId", "value": 5}]})
    assert r.status_code == 422 and {p["field"]: p["problem"] for p in r.json()["error"]["details"]} == {"LocationCode": LOCKED, "LocationId": LOCKED}
    cols = api.get("/api/capacity-factory-calendar/columns").json()
    assert [c["field"] for c in cols["columns"] if c["default_visible"]][:3] == ["LocationCode", "StartDate", "EndDate"]
    assert {c["field"]: c["label"] for c in cols["columns"]}["LocationCode"] == "Lokasyon" and cols["relations"] == [{"path": "LocationId", "label": "Lokasyon"}]
    related = rows(api, FC, base, fields=["Name", "LocationId/Name"])
    assert all(x["LocationId/Name"] for x in related)
    # izleyen senaryodaki fark satırı lokasyonu Baz'daki gibi taşır
    r = api.put(f"/api/capacity/{FC}?scenario_id={follower}", json={"changes": [{"id": made, "field": "Name", "value": "pytest toplu izin"}]})
    assert r.status_code == 200, r.text
    with db_engine.connect() as c:
        diff = c.execute(sa.text("SELECT LocationId, BaseRowId, OverriddenFields FROM param.FactoryCalendar WHERE ScenarioDefinitionId = :s AND BaseRowId = :b"),
                         {"s": follower, "b": made}).one()
    assert tuple(diff) == (loc, made, ",Name,") and one(api, FC, follower, made)["LocationCode"] == d.LOCATION_CODE
    assert resolve.FIELDS["FactoryCalendar"][0] == "LocationId" and "FactoryCalendar" not in resolve.KEYS
    listed = api.get("/api/capacity/locations").json()["locations"]
    assert {"id": loc, "code": d.LOCATION_CODE} in [{"id": x["id"], "code": x["code"]} for x in listed] and all(set(x) == {"id", "code", "name"} for x in listed)


# ------------------------------------------------------------------ iki lokasyon: hesap, tetikleyici, Kapasite özeti

def test_calendar_of_one_location_does_not_touch_the_other(api, db_engine, world, second):  # noqa: F811
    """Bir lokasyonun takvim kaydı yalnız kendi kaynaklarının kapasitesini düşürür; tetikleyici yalnız o lokasyonun kaynaklarını yeniler; Kapasite
    özeti (kaynak grubu × dönem) de öyle. İki lokasyonda aynı kodlu kaynak ayrı hesaplanır."""
    base = world["base"]
    here, there = world["r1"], second["resource"]                   # M3-01 (birinci lokasyon) ve aynı kodlu kaynak (ikinci lokasyon)
    d1, d2 = working_days(db_engine, world, 2, here)
    before = values(db_engine, base, d1, d2, here, there)
    assert before[(there, d1)]["WorkingDay"] == 1 and before[(there, d1)]["Downtime"] == 0 and float(before[(there, d1)]["AvailableCapacity"]) == 8.0

    def summary() -> dict:
        found = rows(api, "period-resource-group", base, filters=[{"field": "ResourceGroupCode", "op": "in", "values": ["ISL3"]}],
                     fields=["LocationCode", "ResourceGroupCode", "PeriodStart", "AvailableCapacity", "Downtime"])
        return {(x["LocationCode"], x["PeriodStart"]): (float(x["AvailableCapacity"]), float(x["Downtime"])) for x in found}

    quiet = summary()
    assert {k[0] for k in quiet} == {d.LOCATION_CODE, two_locations.CODE}                       # aynı kodlu iki grup, lokasyonla ayrışır

    # birinci lokasyonun tatili (ekrandan): yalnız birinci lokasyon
    first = new(api, FC, base, LocationId=world["location"], StartDate=tr(d1), Name="pytest tatil 1", DayValue="Çalışılmıyor")
    after = values(db_engine, base, d1, d2, here, there)
    assert after[(here, d1)]["Downtime"] == 1 and float(after[(here, d1)]["AvailableCapacity"]) == 0.0
    assert after[(there, d1)] == before[(there, d1)] and after[(here, d2)] == before[(here, d2)]
    held = summary()
    changed = {k for k in quiet if quiet[k] != held[k]}
    assert changed and {k[0] for k in changed} == {d.LOCATION_CODE}                             # Kapasite özeti: öteki lokasyon aynı
    cached = stored(db_engine, base)
    assert cached[(here, world["g1"], d1)][4] == 0 and cached[(there, second["group"], d1)][4] == 8.0   # önbellek = hesap

    # ikinci lokasyonun yarım günü: yalnız ikinci lokasyon
    new(api, FC, base, LocationId=second["location"], StartDate=tr(d2), Name="pytest yarım gün 2", DayValue="Yarım gün")
    last = values(db_engine, base, d1, d2, here, there)
    assert last[(there, d2)]["Downtime"] == 0.5 and float(last[(there, d2)]["AvailableCapacity"]) == 4.0
    assert last[(here, d2)] == before[(here, d2)] and last[(there, d1)] == before[(there, d1)]
    both = summary()
    assert {k[0] for k in held if held[k] != both[k]} == {two_locations.CODE}
    assert stored(db_engine, base)[(there, second["group"], d2)][4] == 4.0
    listed = {(x["LocationCode"], x["Name"]) for x in rows(api, FC, base) if str(x["Name"]).startswith("pytest")}
    assert listed == {(d.LOCATION_CODE, "pytest tatil 1"), (two_locations.CODE, "pytest yarım gün 2")}

    # tetikleyici: yalnız kaydın lokasyonundaki kaynaklar
    done = fire(db_engine, triggers.factory_calendar_changed, base, second["location"], [(d1, d2)])
    assert done[base] == (d2 - d1).days + 1                                                    # ikinci lokasyonda tek üyelik
    with Session(db_engine) as s:
        assert triggers.location_resources(s, second["location"]) == [there] and here in triggers.location_resources(s, world["location"])
    # birden çok lokasyonda kaydın okunur adı lokasyonla
    api.delete(f"/api/capacity/{FC}/{first}?scenario_id={base}")
    with db_engine.connect() as c:
        key = c.execute(sa.text("SELECT TOP 1 ObjectKey FROM adm.AuditLog WHERE Action = N'Kapasite kaydı silindi' ORDER BY Id DESC")).scalar()
    assert key is None or key.startswith(f"{d.LOCATION_CODE} · pytest tatil 1")


# ------------------------------------------------------------------ geçiş 0073

def _migration():
    root = Path(__file__).resolve().parents[1] / "db"
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    spec = importlib.util.spec_from_file_location("migration_0073", root / "migrations" / "versions" / "0073_fabrika_takvimi_lokasyon_k_194.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("codes, expected", [
    (("A",), {"A": 3}),                                              # tek lokasyon: hepsi ona bağlanır
    (("B", "A", "C"), {"A": 3, "B": 3, "C": 3}),                     # çok lokasyon: her lokasyona kopyalanır
    ((), {}),                                                        # lokasyon yok: kayıtlar silinir
])
def test_migration_binds_existing_calendar_rows(db_engine, codes, expected):
    """Geçiş 0073'ün bağlama deyimi geçici tablolarda: Baz satırı, senaryonun kendi satırı ve fark satırı; kopyada fark satırı yeni Baz kopyasına bağlanır."""
    sql = _migration().bind_sql("#fc", "#loc")
    with db_engine.connect() as c:
        c.execute(sa.text("CREATE TABLE #loc (Id int NOT NULL, Code nvarchar(30) NOT NULL)"))
        c.execute(sa.text("CREATE TABLE #fc (Id bigint IDENTITY(1,1) PRIMARY KEY, ScenarioDefinitionId int NOT NULL, BaseRowId bigint NULL, OverriddenFields nvarchar(400) NULL, "
                          "IsValid bit NOT NULL, LocationId int NULL, StartDate date NOT NULL, EndDate date NOT NULL, Name nvarchar(100) NOT NULL, DayValue decimal(2,1) NOT NULL, "
                          "UpdatedAt datetime2 NOT NULL, UpdatedBy int NULL)"))
        for i, code in enumerate(codes):
            c.execute(sa.text("INSERT INTO #loc VALUES (:i, :c)"), {"i": 10 + i, "c": code})
        insert = ("INSERT INTO #fc (ScenarioDefinitionId, BaseRowId, OverriddenFields, IsValid, StartDate, EndDate, Name, DayValue, UpdatedAt) "
                  "VALUES (:s, :b, :o, :v, '20270101', '20270101', :n, 0, SYSUTCDATETIME())")
        c.execute(sa.text(insert), {"s": 1, "b": None, "o": None, "v": 1, "n": "Baz"})            # Id 1: Baz satırı
        c.execute(sa.text(insert), {"s": 2, "b": None, "o": None, "v": 1, "n": "Senaryo"})        # Id 2: senaryonun kendi satırı
        c.execute(sa.text(insert), {"s": 2, "b": 1, "o": ",IsValid,", "v": 0, "n": "Baz"})        # Id 3: Baz satırının farkı (geçersiz)
        c.execute(sa.text(sql))
        found = c.execute(sa.text("SELECT f.Id, l.Code, f.ScenarioDefinitionId, f.BaseRowId, f.OverriddenFields, f.IsValid, f.Name, f.LocationId FROM #fc f "
                                  "LEFT JOIN #loc l ON l.Id = f.LocationId ORDER BY f.Id")).all()
        c.rollback()
    by_code: dict = {}
    for r in found:
        by_code.setdefault(r.Code, []).append(r)
    assert {k: len(v) for k, v in by_code.items()} == expected and all(r.LocationId is not None for r in found)
    if codes:
        assert [r.Id for r in by_code["A"]] == [1, 2, 3]                                          # var olan satırlar koda göre ilk lokasyonda
    for code, group in by_code.items():
        base = next(r for r in group if r.ScenarioDefinitionId == 1)
        own = next(r for r in group if r.ScenarioDefinitionId == 2 and r.BaseRowId is None)
        diff = next(r for r in group if r.BaseRowId is not None)
        assert (base.Name, own.Name) == ("Baz", "Senaryo") and (diff.BaseRowId, diff.OverriddenFields, diff.IsValid) == (base.Id, ",IsValid,", False)   # fark kendi lokasyonunun Baz kopyasına bağlı


# ------------------------------------------------------------------ sentetik durma mesajı

def test_synthetic_lock_message_tells_what_to_do(monkeypatch):
    monkeypatch.setattr(synthetic_load, "non_synthetic", lambda conn: ["veri versiyonu 69", "lokasyon V-LOC-1"])
    with pytest.raises(synthetic_load.SyntheticLockError) as err:
        synthetic_load._lock(None, "yüklenmedi")
    text = str(err.value)
    assert "veri versiyonu 69" in text and text.endswith("python -m app.data.synthetic reset")
