"""Öncelik yönetimi, 7.14a (K-195; ekran 32, fonksiyon 25): listeler ve sentetik kayıtlar, hiyerarşinin bütün dalları (sipariş → proje → müşteri → yok;
tahminde proje → müşteri → yok), girilen değerin ERP önceliğini ezmesi, aralık dışı ERP önceliği, doğrulamalar, Baz + fark (fark, boşaltma, fark kaldırma,
çakışma, Baz satırının silinmesi, izlemeyen senaryo), İşlem verisi alanları, motor arayüzü, veri kalitesi ve yetki. Smartchain_test'te; yazdığını siler,
sentetik kayıtların satırlarını değiştirmez (Baz'da yalnız girilmemiş kayıtlara yazar; sentetik değerler izleyen senaryoda fark olarak denenir)."""
import json

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app import priorities as rules
from app.api.permissions import END_USER, KEY_USER
from app.data.synthetic import dataset as d
from app.engine.data import SqlPlanningData
from app.params import resolve, scenario_tables
from app.quality import run as quality_run

from auth_helpers import auth
from test_capacity import clean, world  # noqa: F401  (fixture'lar)
from test_capacity_entries import api, audits, people  # noqa: F401

pytestmark = pytest.mark.db
CUSTOMERS, PROJECTS, ORDERS, FORECASTS = "priority-customers", "priority-projects", "priority-orders", "priority-forecasts"
PG, EFF, SRC = "PriorityGroup", "EffectivePriorityGroup", "PrioritySource"
PROBLEM = "1 ile 5 arasında tam sayı olmalı."


@pytest.fixture
def ids(db_engine, world, clean):  # noqa: F811
    """Sentetik kayıtların kimlikleri; test sonunda bu testin yazdığı öncelik satırları ve geçmişleri silinir."""
    with db_engine.connect() as c:
        mark = c.execute(sa.text("SELECT COALESCE(MAX(Id), 0) FROM param.DemandPriority")).scalar()
        one = lambda sql, **p: c.execute(sa.text(sql), p).scalar_one()  # noqa: E731
        customer = lambda code: one("SELECT Id FROM core.Customer WHERE Code = :c AND VersionTo IS NULL", c=code)  # noqa: E731
        order = lambda no: one("SELECT Id FROM core.SalesOrderLine WHERE OrderNo = :n AND VersionTo IS NULL", n=no)  # noqa: E731
        out = {"A": customer("MUS-A"), "B": customer("MUS-B"), "C": customer("MUS-C"),
               "P1": one("SELECT Id FROM core.Project WHERE Code = N'PRJ-01' AND VersionTo IS NULL"), "P2": one("SELECT Id FROM core.Project WHERE Code = N'PRJ-02' AND VersionTo IS NULL"),
               "low": order("SO-1003"), "high": order("SO-1033"), "plain_a": order("SO-1001"), "plain_b": order("SO-1014"), "prj1": order("SO-1020"), "prj2": order("SO-1030"),
               "mono": one("SELECT Id FROM param.ScenarioDefinition WHERE Name = N'Kısıtsız kapasite' AND IsSynthetic = 1")}
    yield out
    with db_engine.begin() as c:
        c.execute(sa.text("DELETE FROM param.DemandPriority WHERE Id > :m"), {"m": mark})
        c.execute(sa.text("DELETE FROM adm.FieldChange WHERE TableName = N'DemandPriority'"))


def rows(api, name: str, scenario: int, **body) -> list[dict]:  # noqa: F811
    r = api.post(f"/api/{name}/query", json={"limit": 100, "scenario_id": scenario, **body})
    assert r.status_code == 200, r.text
    return r.json()["rows"]


def row(api, name: str, scenario: int, record_id: int) -> dict:  # noqa: F811
    found = rows(api, name, scenario, filters=[{"field": "Id", "op": "in", "values": [str(record_id)]}])
    assert len(found) == 1, (name, record_id, len(found))
    return found[0]


def put(api, level: str, scenario: int, changes: list[tuple], expect: int = 200):  # noqa: F811
    r = api.put(f"/api/priorities/{level}?scenario_id={scenario}", json={"changes": [{"id": i, "field": f, "value": v} for i, f, v in changes]})
    assert r.status_code == expect, r.text
    return r.json() if expect == 200 else r.json()["error"]


def restore(api, level: str, scenario: int, record_id: int, expect: int = 200):  # noqa: F811
    r = api.post(f"/api/priorities/{level}/{record_id}/restore?scenario_id={scenario}")
    assert r.status_code == expect, r.text


def effective(api, scenario: int, order_id: int) -> tuple:  # noqa: F811
    r = row(api, ORDERS, scenario, order_id)
    return r[PG], r[EFF], r[SRC]


def stored(db_engine, scenario: int, level: str, record_id: int) -> list[tuple]:
    with db_engine.connect() as c:
        return [tuple(r) for r in c.execute(sa.text("SELECT BaseRowId, OverriddenFields, PriorityGroup FROM param.DemandPriority WHERE ScenarioDefinitionId = :s AND [Level] = :l "
                                                    "AND RecordId = :r ORDER BY Id"), {"s": scenario, "l": level, "r": record_id})]


# ------------------------------------------------------------------ listeler ve sentetik kayıtlar

def test_lists_and_synthetic_priorities(api, db_engine, world, ids):  # noqa: F811
    """Listeler ana verinin listelerinden türetilir; "Öncelik grubu" ve "ERP önceliği" ayrı kolonlar; Sipariş'te yalnız açık satırlar ve hesaplanan iki
    alan; sentetik kayıtlar (docs/11) ve "Kısıtsız kapasite" senaryosundaki fark; kayıt defteri."""
    base = world["base"]
    cols = api.get(f"/api/{CUSTOMERS}/columns").json()
    assert [c["field"] for c in cols["columns"] if c["default_visible"]] == ["Code", "Name", "Priority", PG, "Origin"] and cols["scenario_list"] is True
    labels = {c["field"]: c["label"] for c in cols["columns"]}
    assert (labels["Code"], labels["Priority"], labels[PG], labels["Origin"]) == ("Müşteri", "ERP önceliği", "Öncelik grubu", "Kaynağı")
    assert "CustomerGroup" in labels                                                                 # ana verinin öteki alanları Alanlar'dan açılır
    got = {r["Code"]: (r["Priority"], r[PG], r["Origin"]) for r in rows(api, CUSTOMERS, base)}
    assert got == {"MUS-A": (1, 1, "Baz"), "MUS-B": (2, None, None), "MUS-C": (3, 4, "Baz")}        # MUS-B'ye girilmemiş: ERP önceliği geçerli
    projects = {r["Code"]: (r["Priority"], r[PG]) for r in rows(api, PROJECTS, base)}
    assert projects == {"PRJ-01": (d.PRIORITY_BAD_VALUE, None), "PRJ-02": (2, 3)}
    assert {c["field"]: c["label"] for c in api.get(f"/api/{PROJECTS}/columns").json()["columns"]}["Code"] == "Proje"

    cols = api.get(f"/api/{ORDERS}/columns").json()
    assert [c["field"] for c in cols["columns"] if c["default_visible"]] == [
        "LocationCode", "OrderNo", "LineNo", "CustomerCode", "ProjectCode", "MaterialCode", "RequestedDate", "OpenQuantity", "Priority", PG, EFF, SRC, "Origin"]
    labels = {c["field"]: c["label"] for c in cols["columns"]}
    assert (labels[EFF], labels[SRC], labels["Priority"]) == ("Geçerli öncelik grubu", "Öncelik kaynağı", "ERP önceliği")
    with db_engine.connect() as c:
        open_lines = c.execute(sa.text("SELECT COUNT(*) FROM core.SalesOrderLine WHERE VersionTo IS NULL AND OpenQuantity > 0")).scalar()
        all_lines = c.execute(sa.text("SELECT COUNT(*) FROM core.SalesOrderLine WHERE VersionTo IS NULL")).scalar()
    r = api.post(f"/api/{ORDERS}/query", json={"limit": 1, "scenario_id": base}).json()
    assert r["total"] == open_lines <= all_lines                                                     # yalnız açık sipariş satırları
    assert effective(api, base, ids["low"]) == (5, 5, "Sipariş") and effective(api, base, ids["high"]) == (1, 1, "Sipariş")     # sipariş müşterisini ezer
    assert effective(api, base, ids["plain_a"]) == (None, 1, "Müşteri")                              # MUS-A'nın girilen değeri
    assert effective(api, base, ids["plain_b"]) == (None, 2, "Müşteri")                              # MUS-B: girilmemiş, ERP önceliği
    assert effective(api, base, ids["prj2"]) == (None, 3, "Proje")                                   # PRJ-02: girilen 3, ERP önceliği 2'yi ezer
    assert effective(api, base, ids["prj1"]) == (None, 2, "Müşteri")                                 # PRJ-01'in ERP önceliği aralık dışı: müşteriye geçer
    # "Kısıtsız kapasite": MUS-C 2 (fark); müşterisinden okuyan siparişler de değişir, siparişe girilen değer değişmez
    mono = row(api, CUSTOMERS, ids["mono"], ids["C"])
    assert (mono[PG], mono["Origin"], mono["OverriddenFields"], json.loads(mono["BaseValues"]), mono["CanRestore"]) == (
        d.PRIORITY_DIFF[1], "Senaryo farkı", ",PriorityGroup,", {"PriorityGroup": 4}, True)
    assert effective(api, ids["mono"], ids["high"]) == (1, 1, "Sipariş")
    other = next(r for r in rows(api, ORDERS, ids["mono"], filters=[{"field": "CustomerCode", "op": "in", "values": ["MUS-C"]}]) if r[PG] is None and r["ProjectCode"] is None)
    assert (other[EFF], other[SRC]) == (2, "Müşteri")
    # kartlar: müşterinin siparişleri ve tahminleri süzülür
    mine = rows(api, ORDERS, base, filters=[{"field": "CustomerCode", "op": "in", "values": ["MUS-A"]}])
    assert mine and {r["CustomerCode"] for r in mine} == {"MUS-A"}
    forecasts = rows(api, FORECASTS, base)
    assert forecasts and all(r[SRC] in ("Proje", "Müşteri", "Yok") and r[EFF] in rules.GROUPS for r in forecasts)
    assert [c["field"] for c in api.get(f"/api/{FORECASTS}/columns").json()["columns"] if c["default_visible"]][-2:] == [EFF, SRC]
    # kayıt defteri: veri tablosu (Baz + fark), ayırması bağlı; eski ölçüt sırası tablosu yok
    assert "DemandPriority" in {t.name for t in scenario_tables.TABLES if t.kind == scenario_tables.DATA and t.materialize is not None}
    assert "PriorityRule" not in scenario_tables.BY_NAME and resolve.KEYS["DemandPriority"] == (("Level", "RecordId"), "")


def test_transaction_lists_offer_the_computed_fields(api, world, ids):  # noqa: F811
    """İşlem verisi › Satış siparişi ve Tahmin: iki hesaplanan alan kapalı gelir, istenince seçili senaryoya göre hesaplanır; listenin öteki özellikleri durur."""
    base = world["base"]
    for name in ("transaction-sales-order", "transaction-forecast"):
        cols = api.get(f"/api/{name}/columns").json()
        by = {c["field"]: c for c in cols["columns"]}
        assert by[EFF]["label"] == "Geçerli öncelik grubu" and by[SRC]["label"] == "Öncelik kaynağı" and not by[EFF]["default_visible"] and not by[SRC]["default_visible"]
        assert cols["scenario_list"] is True and by["ManualState"]["default_visible"]                # manuel değer kolonu yerinde
    fields = ["OrderNo", EFF, SRC]
    three = [str(ids[k]) for k in ("low", "high", "plain_a")]
    by_no = lambda s: {r["OrderNo"]: (r[EFF], r[SRC]) for r in rows(api, "transaction-sales-order", s, fields=fields, filters=[{"field": "Id", "op": "in", "values": three}])}  # noqa: E731
    assert by_no(base) == {"SO-1003": (5, "Sipariş"), "SO-1033": (1, "Sipariş"), "SO-1001": (1, "Müşteri")}
    assert by_no(ids["mono"]) == by_no(base)                                                         # bu üçü MUS-C'den okumuyor
    plain = rows(api, "transaction-sales-order", base, filters=[{"field": "Id", "op": "in", "values": [str(ids["low"])]}])
    assert EFF not in plain[0]                                                                       # kapalı alan istenmedikçe dönmez


# ------------------------------------------------------------------ hiyerarşi

def test_hierarchy_every_branch(api, db_engine, world, ids):  # noqa: F811
    """Sipariş → proje → müşteri → yok (5); tahminde proje → müşteri → yok. Her düzeyde girilen değer ERP önceliğini ezer; aralık dışı ERP önceliği yok sayılır."""
    base = world["base"]
    order = ids["prj2"]                                                                              # MUS-B (ERP 2), PRJ-02 (girilen 3, ERP 2)
    assert effective(api, base, order) == (None, 3, "Proje")
    assert put(api, "orders", base, [(order, PG, 4)])["saved"] == 1
    assert effective(api, base, order) == (4, 4, "Sipariş")
    assert put(api, "orders", base, [(order, PG, None)])["saved"] == 1                               # boşaltınca değer kalkar: projeye döner
    assert effective(api, base, order) == (None, 3, "Proje") and stored(db_engine, base, "Sipariş", order) == []
    sql = f"SELECT z.EffectivePriorityGroup, z.PrioritySource FROM ({rules.orders_sql()}) z WHERE z.SalesOrderLineId = :o"
    forecast = f"SELECT TOP 1 z.EffectivePriorityGroup, z.PrioritySource FROM ({rules.forecasts_sql()}) z JOIN core.Forecast f ON f.Id = z.ForecastId AND f.VersionTo IS NULL WHERE @@WHERE@@"
    p = {"sid": base, "base": None}
    with Session(db_engine) as s:                                                                    # ana veride işlem içinde denenir, geri alınır
        try:
            read = lambda o: tuple(s.execute(sa.text(sql), {**p, "o": o}).one())  # noqa: E731
            s.execute(sa.text("UPDATE core.SalesOrderLine SET Priority = 2 WHERE Id = :o AND VersionTo IS NULL"), {"o": order})
            assert read(order) == (2, "Sipariş")                                                     # siparişin ERP önceliği
            s.execute(sa.text("UPDATE core.SalesOrderLine SET Priority = 0 WHERE Id = :o AND VersionTo IS NULL"), {"o": order})
            assert read(order) == (3, "Proje")                                                       # aralık dışı: yok sayılır
            s.execute(sa.text("DELETE FROM param.DemandPriority WHERE [Level] = N'Proje' AND RecordId = :r"), {"r": ids["P2"]})
            assert read(order) == (2, "Proje")                                                       # projenin ERP önceliği (girilen yokken)
            s.execute(sa.text("UPDATE core.Project SET Priority = NULL WHERE Id = :r AND VersionTo IS NULL"), {"r": ids["P2"]})
            assert read(order) == (2, "Müşteri")                                                     # müşterinin ERP önceliği
            s.execute(sa.text("UPDATE core.Customer SET Priority = 7 WHERE Id = :r AND VersionTo IS NULL"), {"r": ids["B"]})
            assert read(order) == (5, "Yok")                                                         # hiçbir düzeyde değer yok: en düşük grup
            # tahmin: kendi düzeyi yok
            first = "f.Id = (SELECT TOP 1 Id FROM core.Forecast WHERE VersionTo IS NULL ORDER BY Id)"
            one = lambda: tuple(s.execute(sa.text(forecast.replace("@@WHERE@@", first)), p).one())  # noqa: E731
            move = "UPDATE core.Forecast SET CustomerId = :c, ProjectId = :r WHERE Id = (SELECT TOP 1 Id FROM core.Forecast WHERE VersionTo IS NULL ORDER BY Id) AND VersionTo IS NULL"
            s.execute(sa.text(move), {"c": None, "r": None})
            assert one() == (5, "Yok")                                                               # müşterisi ve projesi olmayan tahmin
            s.execute(sa.text(move), {"c": ids["A"], "r": None})
            assert one() == (1, "Müşteri")                                                           # müşterinin girilen değeri
            s.execute(sa.text(move), {"c": ids["A"], "r": ids["P2"]})
            assert one() == (1, "Müşteri")                                                           # projenin değeri yok (yukarıda kaldırıldı): müşteriye geçer
            s.execute(sa.text("UPDATE core.Project SET Priority = 4 WHERE Id = :r AND VersionTo IS NULL"), {"r": ids["P2"]})
            assert one() == (4, "Proje")
        finally:
            s.rollback()
    assert effective(api, base, order) == (None, 3, "Proje")                                         # geri alındı


# ------------------------------------------------------------------ giriş ve doğrulama

def test_entry_validation_and_history(api, db_engine, world, ids, people):  # noqa: F811
    """Değer 1–5 ya da boş; yalnız Öncelik grubu düzenlenir; kayıt güncel veride olmalı; hepsi ya da hiçbiri; toplu giriş; Geçmiş ve denetim izi."""
    base = world["base"]
    for bad in (0, 6, "x", 2.5, "2,5", -1, True):
        err = put(api, "customers", base, [(ids["B"], PG, bad)], expect=422)
        assert err["details"] == [{"id": ids["B"], "field": PG, "record": "Müşteri MUS-B", "problem": PROBLEM}], (bad, err)
    err = put(api, "customers", base, [(ids["B"], "Priority", 3), (ids["B"], PG, 3), (999_999, PG, 2)], expect=422)
    assert {(x["id"], x["field"]): x["problem"] for x in err["details"]} == {(ids["B"], "Priority"): "Bu alan düzenlenemez.", (999_999, PG): "Kayıt güncel veride yok."}
    assert row(api, CUSTOMERS, base, ids["B"])[PG] is None                                           # geçerli değişiklik de kaydedilmedi
    assert api.put(f"/api/priorities/groups?scenario_id={base}", json={"changes": [{"id": 1, "field": PG, "value": 1}]}).status_code == 404
    # toplu giriş: aynı değer birkaç siparişe; metin olarak yazılan sayı kabul edilir
    assert put(api, "orders", base, [(ids["plain_a"], PG, "2"), (ids["plain_b"], PG, 2), (ids["prj1"], PG, 2)])["saved"] == 3
    assert [effective(api, base, ids[k]) for k in ("plain_a", "plain_b", "prj1")] == [(2, 2, "Sipariş")] * 3
    assert put(api, "orders", base, [(ids["plain_a"], PG, 2)])["saved"] == 0                         # aynı değer: değişiklik yok
    assert put(api, "customers", base, [(ids["B"], PG, 3)])["saved"] == 1
    got = row(api, CUSTOMERS, base, ids["B"])
    assert (got[PG], got["Origin"], got["Priority"]) == (3, "Baz", 2)                                # girilen ERP'yi ezer; ERP önceliği yerinde
    history = api.post("/api/record-history/query", json={"limit": 100, "sort": [{"field": "At", "dir": "asc"}], "filters": [
        {"field": "TableName", "op": "in", "values": ["DemandPriority"]}, {"field": "RecordKey", "op": "in", "values": [f"customers:{ids['B']}"]}]}).json()["rows"]
    assert [(h["FieldLabel"], h["OldValue"], h["NewValue"]) for h in history] == [("Öncelik grubu", None, "3")]
    assert {h["SourceText"] for h in history} == {"Öncelik yönetimi · Kapasite Planlamacı"}
    logged = audits(db_engine, people[KEY_USER], "Öncelik grubu değişti")
    assert logged and (logged[-1]["ObjectType"], logged[-1]["ObjectKey"], json.loads(logged[-1]["NewValue"])) == ("Öncelik yönetimi", "Müşteri MUS-B", {"PriorityGroup": "3"})
    put(api, "customers", base, [(ids["B"], PG, "")])                                                # boş metin: değer kalkar
    assert row(api, CUSTOMERS, base, ids["B"])[PG] is None and stored(db_engine, base, "Müşteri", ids["B"]) == []


# ------------------------------------------------------------------ Baz + fark

def test_scenario_difference_clear_and_restore(api, db_engine, world, ids):  # noqa: F811
    """İzleyen senaryo Baz'ın değerini okur; değişikliği fark satırıdır; boşaltınca fark "boş" durur (ERP önceliğine, sonra hiyerarşiye geçilir); Baz'daki
    değere dönülünce fark kalkar; "Senaryo farkını kaldır" Baz'a döndürür. Baz değişmez."""
    base, follower, c = world["base"], world["follower"], ids["C"]                                  # MUS-C: Baz'da girilen 4, ERP önceliği 3
    seen = lambda s: (lambda r: (r[PG], r["Origin"], r["CanRestore"]))(row(api, CUSTOMERS, s, c))  # noqa: E731
    order = next(r["Id"] for r in rows(api, ORDERS, base, filters=[{"field": "CustomerCode", "op": "in", "values": ["MUS-C"]}]) if r[PG] is None and r["ProjectCode"] is None)
    assert seen(follower) == (4, "Baz", False) and effective(api, follower, order) == (None, 4, "Müşteri")
    put(api, "customers", follower, [(c, PG, 2)])
    assert seen(follower) == (2, "Senaryo farkı", True) and seen(base) == (4, "Baz", False)
    [diff] = stored(db_engine, follower, "Müşteri", c)
    assert diff[1:] == (",PriorityGroup,", 2) and diff[0] is not None and effective(api, follower, order) == (None, 2, "Müşteri")
    put(api, "customers", follower, [(c, PG, None)])                                                 # Baz'ın değeri bu senaryoda kaldırıldı
    got = row(api, CUSTOMERS, follower, c)
    assert (got[PG], got["Origin"], got["OverriddenFields"], json.loads(got["BaseValues"])) == (None, "Senaryo farkı", ",PriorityGroup,", {"PriorityGroup": 4})
    assert stored(db_engine, follower, "Müşteri", c)[0][2] is None and effective(api, follower, order) == (None, 3, "Müşteri")   # ERP önceliğine düşer
    assert effective(api, base, order) == (None, 4, "Müşteri")
    put(api, "customers", follower, [(c, PG, 4)])                                                    # Baz'daki değere dönüldü: fark kalkar
    assert seen(follower) == (4, "Baz", False) and stored(db_engine, follower, "Müşteri", c) == []
    restore(api, "customers", follower, c, expect=409)                                               # fark yokken kaldırılamaz
    put(api, "customers", follower, [(c, PG, 1)])
    restore(api, "customers", follower, c)
    assert seen(follower) == (4, "Baz", False) and stored(db_engine, follower, "Müşteri", c) == []
    history = api.post("/api/record-history/query", json={"limit": 100, "sort": [{"field": "At", "dir": "asc"}], "filters": [
        {"field": "TableName", "op": "in", "values": ["DemandPriority"]}, {"field": "RecordKey", "op": "in", "values": [f"customers:{c}@{follower}"]}]}).json()["rows"]
    assert [(h["OldValue"], h["NewValue"]) for h in history] == [("4", "2"), ("2", None), (None, "4"), ("4", "1"), ("1", "4")]
    restore(api, "customers", base, c, expect=409)                                                   # Baz'da fark kavramı yok


def test_scenario_own_value_meets_base_value(api, db_engine, world, ids):  # noqa: F811
    """Kayıt başına tek satır (K-191 kuralı): önce senaryoda, sonra Baz'da girilirse senaryonun değeri geçerlidir ve fark sayılır; fark kaldırılınca Baz'a
    döner. Baz'daki değer silinince izleyen senaryonun farkı kendi değerine döner. İzlemeyen senaryo kendi kopyasını düzenler."""
    base, follower, free, b = world["base"], world["follower"], world["free"], ids["B"]              # MUS-B: Baz'da girilmemiş
    seen = lambda s: (lambda r: (r[PG], r["Origin"], r["CanRestore"]))(row(api, CUSTOMERS, s, b))  # noqa: E731
    put(api, "customers", follower, [(b, PG, 5)])
    assert seen(follower) == (5, "Senaryo", True) and seen(base) == (None, None, None)
    put(api, "customers", base, [(b, PG, 2)])                                                        # sonra Baz'da da girildi
    assert seen(follower) == (5, "Senaryo farkı", True) and seen(base) == (2, "Baz", False)
    assert len(rows(api, CUSTOMERS, follower, filters=[{"field": "Id", "op": "in", "values": [str(b)]}])) == 1   # tek satır
    put(api, "customers", follower, [(b, PG, 4)])                                                    # sonraki yazma: kendi satırı fark satırına çevrilir
    [only] = stored(db_engine, follower, "Müşteri", b)
    assert only[0] is not None and only[2] == 4
    put(api, "customers", base, [(b, PG, None)])                                                     # Baz'daki değer silindi: fark kendi değerine döner
    assert seen(base) == (None, None, None) and seen(follower) == (4, "Senaryo", True)
    assert stored(db_engine, follower, "Müşteri", b) == [(None, None, 4)]
    restore(api, "customers", follower, b)                                                           # Baz'da değer yok: boşalır
    assert seen(follower) == (None, None, None)
    # izlemeyen senaryo: Baz'ın ayrıldığı andaki değerleri kendi satırlarındadır; değişikliği Baz'a geçmez
    assert seen(free)[0] is None and row(api, CUSTOMERS, free, ids["A"])[PG] == 1
    put(api, "customers", free, [(ids["A"], PG, 3)])
    assert (row(api, CUSTOMERS, free, ids["A"])[PG], row(api, CUSTOMERS, base, ids["A"])[PG]) == (3, 1)
    put(api, "customers", free, [(ids["A"], PG, 1)])
    restore(api, "customers", free, ids["A"], expect=409)


# ------------------------------------------------------------------ motor arayüzü, veri kalitesi, yetki

def test_engine_reads_the_same_priorities(api, db_engine, world, ids):  # noqa: F811
    base = world["base"]
    put(api, "orders", base, [(ids["plain_b"], PG, 4)])
    with Session(db_engine) as s:
        version = s.execute(sa.text("SELECT MAX(Id) FROM adm.DataVersion")).scalar()
        got = SqlPlanningData(s, version, base).demand_priorities()
        assert got == rules.demand_priorities(s, base) and set(got) == {"orders", "forecasts"}
        open_lines = s.execute(sa.text("SELECT COUNT(*) FROM core.SalesOrderLine WHERE VersionTo IS NULL AND OpenQuantity > 0")).scalar()
        forecasts = s.execute(sa.text("SELECT COUNT(*) FROM core.Forecast WHERE VersionTo IS NULL")).scalar()
        with pytest.raises(ValueError):
            SqlPlanningData(s, version).demand_priorities()
    assert len(got["orders"]) == open_lines and len(got["forecasts"]) == forecasts                   # yalnız açık satırlar; bütün tahminler
    by = {o["SalesOrderLineId"]: (o["PriorityGroup"], o["Source"]) for o in got["orders"]}
    assert by[ids["plain_b"]] == (4, "Sipariş") and by[ids["low"]] == (5, "Sipariş") and by[ids["plain_a"]] == (1, "Müşteri") and by[ids["prj1"]] == (2, "Müşteri")
    listed = {r["Id"]: (r[EFF], r[SRC]) for r in rows(api, ORDERS, base, filters=[{"field": "Id", "op": "in", "values": [str(i) for i in by][:60]}])}
    assert listed and all(by[i] == v for i, v in listed.items())                                     # ekran ile motor aynı sonuç
    assert all(f["PriorityGroup"] in rules.GROUPS and f["Source"] in ("Proje", "Müşteri", "Yok") for f in got["forecasts"])


def test_out_of_range_erp_priority_is_a_normal_warning(db_engine, ids):
    """`SC.PRIORITY_RANGE` (durum 10): ERP önceliği 1–5 dışında olan proje için uyarı; önemi her zaman Normal."""
    try:
        with Session(db_engine) as s:
            quality_run.run(s, {"Project", "Customer", "SalesOrderLine"})
        with db_engine.connect() as c:
            found = [tuple(r) for r in c.execute(sa.text("SELECT EntityName, RecordLabel, RuleName, Importance FROM adm.DataQualityWarning WHERE CheckCode = N'SC.PRIORITY_RANGE'"))]
        assert found == [("Project", f"Proje: {d.PRIORITY_BAD_PROJECT}", "ERP önceliği 1–5 dışında", quality_run.NORMAL)]
    finally:
        with db_engine.begin() as c:
            c.execute(sa.text("DELETE FROM adm.DataQualityWarning WHERE CheckCode = N'SC.PRIORITY_RANGE'"))


def test_end_user_reads_but_cannot_write(api, world, ids, people):  # noqa: F811
    base = world["base"]
    end = auth(people[END_USER])
    for name in (CUSTOMERS, PROJECTS, ORDERS, FORECASTS):
        assert api.post(f"/api/{name}/query", headers=end, json={"limit": 5, "scenario_id": base}).status_code == 200
    calls = [api.put(f"/api/priorities/customers?scenario_id={base}", headers=end, json={"changes": [{"id": ids["B"], "field": PG, "value": 2}]}),
             api.post(f"/api/priorities/customers/{ids['C']}/restore?scenario_id={base}", headers=end)]
    assert [c.status_code for c in calls] == [403, 403]


def test_parse():
    assert [rules.parse(v) for v in (None, "", "  ", 1, "5", 3.0)] == [(None, None)] * 3 + [(1, None), (5, None), (3, None)]
    assert all(rules.parse(v) == (None, PROBLEM) for v in (0, 6, "abc", 2.5, True, "1.5"))
