"""Hedef satırları (K-196, 24.11.2026 kurgusu; fonksiyon 22; geliştirme 7.14b): hedef listesi kullanıcınındır. Katalog, gruplar ve eksenler;
başlangıç düzeni (ana satır yok; Tahmin ödün payı %2); kapsam (seçilmeyen eksen "tümü"; örtüşme serbest; kapsanmayan kayıt hiçbir hedefe
girmez); ekleme (listenin sonuna, aktif; başka satır değişmez), düzenleme, silme (her satır); geçişler (0075'in taşıması, 0076'nın ana satırları
çevirmesi); uçlar, denetim izi, yetki; senaryo kopyası; motor arayüzü; sentetik senaryolar ve sentetik komutun veri kalitesi işi.

Veritabanı testleri Baz'ın hedeflerini test başında başlangıç düzenine getirir, sonunda eski hâline döndürür.
"""
import functools
import importlib.util
import json
import sys
from pathlib import Path

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.main import create_app
from app.api.permissions import END_USER, KEY_USER
from app.engine import loader
from app.params import catalog as cat, objectives as obj, service as params
from app.params.service import ParamError

from auth_helpers import auth, ensure_user

ROOT = Path(__file__).resolve().parents[1]
URL = "/api/parameters/objectives"
FIRM, QUOTE, HOLD, FORECAST = cat.DEMAND_TYPES
UNMET = cat.OBJECTIVE_BY_CODE["UNMET_DEMAND"]
SAFETY = cat.OBJECTIVE_BY_CODE["SAFETY_STOCK"]
OVERTIME = cat.OBJECTIVE_BY_CODE["OVERTIME"]
SUBCONTRACT = cat.OBJECTIVE_BY_CODE["SUBCONTRACT"]


@functools.cache
def migration(name: str):
    """Geçiş modülü (sabit listeler ve dönüşüm işlevleri)."""
    path = next((ROOT / "db/migrations/versions").glob(f"{name}_*.py"))
    spec = importlib.util.spec_from_file_location(f"m{name}", path)
    assert spec is not None and spec.loader is not None
    sys.path.insert(0, str(ROOT / "db"))
    try:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(ROOT / "db"))
    return module


def start(settings=None):
    rows = obj.start_rows(settings)
    for i, r in enumerate(rows, start=1):
        r["id"] = i
    obj._describe(rows)
    return rows


# ------------------------------------------------------------------ katalog ve başlangıç düzeni

def test_catalog_groups_axes_and_removed_types():
    assert [o.code for o in cat.OBJECTIVES] == ["UNMET_DEMAND", "LATENESS", "SAFETY_STOCK", "OVERTIME", "SUBCONTRACT", "OVER_TARGET_LOAD", "ALTERNATIVE",
                                                "EARLY_BUILD", "PLAN_DEVIATION"]                       # iki tahmin türü kalktı
    axes = {o.code: [(a.label, a.values) for a in o.axes] for o in cat.OBJECTIVES}
    demand = [("Talep türü", ("Kesin sipariş", "Teklif", "Beklemedeki sipariş", "Tahmin")), ("Öncelik grubu", (1, 2, 3, 4, 5))]
    material = [("Malzeme seviyesi", ("Hammadde", "Yarı mamul", "Nihai ürün")), ("Malzeme grubu", None)]
    assert axes["UNMET_DEMAND"] == axes["LATENESS"] == demand and axes["SAFETY_STOCK"] == axes["EARLY_BUILD"] == material
    assert axes["OVERTIME"] == [("Kaynak grubu tipi", ("İşçi", "Makine", "Diğer"))]                    # Fason sunulmaz
    assert axes["OVER_TARGET_LOAD"] == [("Kaynak grubu tipi", ("İşçi", "Makine", "Fason", "Diğer"))]
    assert axes["SUBCONTRACT"] == axes["ALTERNATIVE"] == axes["PLAN_DEVIATION"] == []                  # kapsam almaz
    assert cat.OBJECTIVE_LABELS["OVERTIME"] == "Ek mesai" and cat.BY_KEY["UseOvertime"].label == "Ek mesai"
    groups = {}
    for o in cat.OBJECTIVES:
        groups.setdefault(cat.FAMILY_LABELS[o.family], []).append(o.label)
    assert groups == {"Talep": ["Karşılanmayan talep", "Gecikme"], "Malzeme": ["Güvenlik stoğunun altı", "Erken üretim ve stok"],
                      "Kaynak": ["Ek mesai", "Hedef doluluğun üstü"], "Diğer": ["Fason", "Alternatif önceliği", "Önceki plandan sapma"]}


def test_start_layout_has_no_main_rows_and_keeps_the_budget():
    rows = start()
    assert len(rows) == 24 and sum(r["seconds"] or 0 for r in rows) == 1140                             # "Kalanlar" satırı yok; toplam bütçe aynı
    active = [(r["label"], r["scope_text"], r["seconds"], r["tolerance"]) for r in rows if r["active"]]
    assert active[:4] == [("Karşılanmayan talep", "Talep türü: Kesin sipariş", 210, 0), ("Gecikme", "Talep türü: Kesin sipariş", 210, 0),
                          ("Karşılanmayan talep", "Talep türü: Tahmin", 210, 2), ("Gecikme", "Talep türü: Tahmin", 210, 2)]   # Tahmin ödün payı %2
    assert active[4:7] == [("Güvenlik stoğunun altı", f"Malzeme seviyesi: {v}", 20, 5) for v in ("Nihai ürün", "Yarı mamul", "Hammadde")]
    assert active[7:12] == [("Ek mesai", "Kaynak grubu tipi: İşçi", 20, 5), ("Ek mesai", "Kaynak grubu tipi: Makine", 20, 5), ("Ek mesai", "Kaynak grubu tipi: Diğer", 20, 5),
                            ("Fason", "", 60, 5), ("Alternatif önceliği", "", 60, 5)]
    assert len(active) == 15
    off = [(r["label"], r["scope_text"]) for r in rows if not r["active"]]
    assert off == [("Karşılanmayan talep", "Talep türü: Beklemedeki sipariş"), ("Gecikme", "Talep türü: Beklemedeki sipariş"),
                   ("Karşılanmayan talep", "Talep türü: Teklif"), ("Gecikme", "Talep türü: Teklif"),
                   *[("Hedef doluluğun üstü", f"Kaynak grubu tipi: {v}") for v in ("İşçi", "Makine", "Fason", "Diğer")], ("Önceki plandan sapma", "")]
    assert all(r["seconds"] is None and r["tolerance"] is None for r in rows if not r["active"])
    assert all(len(r["scope"]) <= 1 for r in rows)                                                       # ikinci eksen seçilmez: "tümü"
    # teklif plana alınıyorsa satırı aktif gelir ve süre üç satıra bölünür
    quoted = start({"IncludeQuotes": cat.YES})
    assert [(r["seconds"], r["tolerance"]) for r in quoted if r["code"] == "UNMET_DEMAND" and r["active"]] == [(140, 0), (140, 2), (140, 0)]   # Kesin, Tahmin, Teklif
    assert sum(r["seconds"] or 0 for r in quoted) == 1140
    assert "dimmed" not in quoted[0] and "tip" not in quoted[0]                                          # soluk yalnız kapalı satır: ayrı işaret yok


# ------------------------------------------------------------------ kapsam

def test_scope_text_and_parts():
    scope = {"DemandType": [FIRM, QUOTE], "PriorityGroup": [1, 2, 3]}
    assert obj.scope_text(UNMET, scope) == "Talep türü: Kesin sipariş, Teklif · Öncelik grubu: 1, 2, 3"
    assert obj.scope_parts(UNMET, scope) == [{"label": "Talep türü", "values": [FIRM, QUOTE]}, {"label": "Öncelik grubu", "values": [1, 2, 3]}]
    assert obj.scope_text(UNMET, {"PriorityGroup": [1]}) == "Öncelik grubu: 1"                           # seçim yapılmayan kategori yazılmaz
    assert obj.scope_text(SAFETY, {"MaterialLevel": ["Nihai ürün"], "MaterialGroup": ["Rulman"]}) == "Malzeme seviyesi: Nihai ürün · Malzeme grubu: Rulman"
    assert obj.scope_text(UNMET, {}) == "Tümü" and obj.scope_parts(UNMET, {}) == []                      # hiç seçim yok: hedefin tamamı
    assert obj.scope_text(SUBCONTRACT, {}) == ""                                                         # kapsam almayan hedef


def test_check_scope():
    for code, scope in (("SUBCONTRACT", {"DemandType": [FIRM]}), ("UNMET_DEMAND", {"MaterialLevel": ["Hammadde"]}), ("UNMET_DEMAND", {"DemandType": ["Sipariş"]}),
                        ("UNMET_DEMAND", {"PriorityGroup": [6]}), ("OVERTIME", {"ResourceType": ["Fason"]}), ("SAFETY_STOCK", {"MaterialGroup": [""]}),
                        ("UNMET_DEMAND", {"PriorityGroup": [True]}), ("UNMET_DEMAND", {"DemandType": "Tahmin"})):
        with pytest.raises(ParamError):
            obj.check_scope(cat.OBJECTIVE_BY_CODE[code], scope)
    assert obj.check_scope(UNMET, {"DemandType": [FORECAST, FIRM], "PriorityGroup": []}) == {"DemandType": [FIRM, FORECAST]}   # eksenin sırası; boş eksen yazılmaz
    assert obj.check_scope(UNMET, {}) == {} and obj.check_scope(UNMET, None) == {} and obj.check_scope(SUBCONTRACT, {}) == {}   # boş kapsam geçerli
    # bir eksende hepsini seçmek ile hiç seçmemek aynıdır: o eksen yazılmaz
    assert obj.check_scope(UNMET, {"DemandType": list(cat.DEMAND_TYPES), "PriorityGroup": [1]}) == {"PriorityGroup": [1]}
    assert obj.check_scope(UNMET, {"DemandType": list(cat.DEMAND_TYPES), "PriorityGroup": [5, 4, 3, 2, 1]}) == {}
    assert obj.check_scope(SAFETY, {"MaterialGroup": [" Rulman ", "Rulman", "Yeni"]}) == {"MaterialGroup": ["Rulman", "Yeni"]}
    assert obj.check_scope(SAFETY, {"MaterialGroup": ["Rulman", "Conta"]}, ["Conta", "Rulman"]) == {}    # açık eksende "hepsi": verideki gruplar
    assert obj.check_scope(SAFETY, {"MaterialGroup": ["Rulman"]}, ["Conta", "Rulman"]) == {"MaterialGroup": ["Rulman"]}


def test_rows_of_overlap_and_uncovered():
    """Kapsamlar örtüşebilir (kayıt birden çok satıra girer); hiçbir satırın kapsamadığı kayıt hiçbir hedefe girmez."""
    def row(i, code, scope):
        return {"id": i, "code": code, "scope": scope}
    rows = [row(1, "UNMET_DEMAND", {"DemandType": [FIRM], "PriorityGroup": [1, 2]}), row(2, "UNMET_DEMAND", {"DemandType": [FIRM]}),
            row(3, "LATENESS", {}), row(4, "UNMET_DEMAND", {"DemandType": [FIRM], "PriorityGroup": [1, 2]}), row(5, "SAFETY_STOCK", {"MaterialLevel": ["Hammadde"]}),
            row(6, "SAFETY_STOCK", {"MaterialGroup": ["Rulman"]}), row(7, "OVERTIME", {"ResourceType": ["İşçi"]}), row(8, "OVERTIME", {})]
    ids = lambda code, cls: [r["id"] for r in obj.rows_of(rows, code, cls)]   # noqa: E731
    assert ids("UNMET_DEMAND", {"DemandType": FIRM, "PriorityGroup": 1}) == [1, 2, 4]                  # örtüşen üç satır, listedeki sırayla (aynı kapsam iki kez)
    assert ids("UNMET_DEMAND", {"DemandType": FIRM, "PriorityGroup": 4}) == [2]
    assert ids("UNMET_DEMAND", {"DemandType": FORECAST, "PriorityGroup": 1}) == []                     # tanımlanmamış kapsam: hiçbir hedefe girmez
    assert ids("LATENESS", {"DemandType": FORECAST, "PriorityGroup": 5}) == [3]                        # kapsamsız satır hedefin tamamı
    assert ids("SAFETY_STOCK", {"MaterialLevel": "Hammadde", "MaterialGroup": "Rulman"}) == [5, 6]
    assert ids("SAFETY_STOCK", {"MaterialLevel": "Hammadde", "MaterialGroup": None}) == [5]             # belirsiz grup yalnız grubu "tümü" olan satıra
    assert ids("SAFETY_STOCK", {"MaterialLevel": None, "MaterialGroup": "Rulman"}) == [6]
    assert ids("SAFETY_STOCK", {"MaterialLevel": None, "MaterialGroup": None}) == []
    assert ids("OVERTIME", {"ResourceType": None}) == [8] and ids("OVERTIME", {"ResourceType": "Fason"}) == [8] and ids("OVERTIME", {"ResourceType": "İşçi"}) == [7, 8]
    assert obj.resource_type(True, False, False, False) == "İşçi" and obj.resource_type(True, True, False, False) is None
    assert obj.resource_type(False, False, False, False) is None                                         # yalnız Fırın / Kalıp ya da hiçbiri
    assert obj.demand_type(True, True) == "Teklif" and obj.demand_type(False, True) == "Beklemedeki sipariş" and obj.demand_type(False, False) == "Kesin sipariş"


# ------------------------------------------------------------------ geçişler (saf)

def test_migration_0075_start_layout_then_0076_equals_the_catalog():
    """Yeni kurulum: 0075'in sabit başlangıç listesi, 0076'nın dönüşümünden sonra `start_rows` ile aynıdır (Tahmin ödün payı %2 dahil)."""
    m75, m76 = migration("0075"), migration("0076")
    fixed = [(code, bool(main), json.loads(scope) if scope else {}, seconds, tolerance) for code, main, scope, seconds, tolerance in m75._start()]
    assert len(fixed) == 30
    after = []
    for code, main, scope, seconds, tolerance in fixed:
        if not main:
            after.append((code, scope, seconds, tolerance))
            continue
        left = m76.rest_of(code, [s for c, m, s, _, _ in fixed if c == code and not m])
        if left is None:
            after.append((code, {}, seconds, tolerance))                                                 # kapsam almayan hedef: kapsamsız kalır
        else:
            assert left == [] and seconds is None                                                        # hiçbir değeri kalmamış kapalı "Kalanlar": kaldırılır
    live = [(r["code"], r["scope"], r["seconds"], r["tolerance"]) for r in obj.start_rows()]
    assert [x for x in after if x[2] is not None] == [x for x in live if x[2] is not None]              # aktifler aynı sırada
    assert sorted(map(str, after)) == sorted(map(str, live)) and len(after) == 24


def test_migration_0076_rest_of_main_rows():
    """"Kalanlar" satırı içerdiği türleri açıkça yazar: hiçbir tanımlı satırın bütünüyle almadığı ilk eksen değerleri."""
    rest = migration("0076").rest_of
    assert rest("SUBCONTRACT", []) is None and rest("UNMET_DEMAND", []) is None                          # ayrımı yok: kapsamsız kalır
    assert rest("UNMET_DEMAND", [{"DemandType": ["Tahmin"]}]) == ["Kesin sipariş", "Teklif", "Beklemedeki sipariş"]   # 0075'in taşıdığı senaryo
    assert rest("UNMET_DEMAND", [{"DemandType": ["Kesin sipariş"], "PriorityGroup": [1, 2]}, {"DemandType": ["Tahmin"]}]) == ["Kesin sipariş", "Teklif", "Beklemedeki sipariş"]
    assert rest("UNMET_DEMAND", [{"DemandType": ["Kesin sipariş"], "PriorityGroup": [1, 2]}, {"DemandType": ["Kesin sipariş"], "PriorityGroup": [3, 4, 5]}]) == [
        "Teklif", "Beklemedeki sipariş", "Tahmin"]                                                       # ikinci eksenin tamamı alınmış
    assert rest("OVERTIME", [{"ResourceType": ["İşçi"]}]) == ["Makine", "Diğer"]
    assert rest("OVERTIME", [{"ResourceType": [v]} for v in ("İşçi", "Makine", "Diğer")]) == []          # satır kaldırılır
    assert rest("SAFETY_STOCK", [{"MaterialLevel": ["Hammadde"], "MaterialGroup": ["Rulman"]}, {"MaterialLevel": ["Nihai ürün"]}]) == ["Hammadde", "Yarı mamul"]


# ------------------------------------------------------------------ veritabanı

@pytest.fixture(scope="module")
def people(db_engine):
    with db_engine.begin() as c:
        return {KEY_USER: ensure_user(c, "pytest.obj.key", KEY_USER), END_USER: ensure_user(c, "pytest.obj.end", END_USER)}


@pytest.fixture
def base(db_engine):
    """Baz'ın kimliği; hedefleri test başında başlangıç düzenine gelir, sonunda eski hâline döner."""
    from db.models import metadata
    table = metadata.tables["param.ObjectiveDefinition"]
    with db_engine.begin() as c:
        sid = c.execute(sa.text("SELECT Id FROM param.ScenarioDefinition WHERE IsBase = 1")).scalar_one()
        saved = [dict(r) for r in c.execute(sa.select(table).where(table.c.ScenarioDefinitionId == sid)).mappings()]
        obj.insert_start(c, sid, params.read_settings(c, sid))
    yield sid
    with db_engine.begin() as c:
        c.execute(sa.delete(table).where(table.c.ScenarioDefinitionId == sid))
        if saved:
            c.execute(sa.insert(table), [{k: v for k, v in r.items() if k != "Id"} for r in saved])


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app(), raise_server_exceptions=False)


def read(client, key):
    r = client.get(URL, headers=key)
    assert r.status_code == 200, r.text
    return r.json()


def names(body, code=None):
    return [f"{r['label']} · {r['scope_text']}" if r["scope_text"] else r["label"] for r in body["rows"] if code is None or r["code"] == code]


@pytest.mark.db
def test_migration_0075_moves_existing_rows_with_least_change(db_engine):
    """0075: iki tahmin türü Tahmin satırına çevrilir; sıra, süre, ödün payı ve aktiflik değişmez (Tahmin satırları %2'yi taşır)."""
    old = (("UNMET_DEMAND", 2, 300, 0), ("UNMET_FORECAST", 3, 120, 2), ("FORECAST_LATENESS", 4, 90, 2), ("LATENESS", 1, 250, 1), ("OVER_TARGET_LOAD", None, None, None))
    with db_engine.connect() as c:
        tx = c.begin()
        try:
            sid = c.execute(sa.text("INSERT INTO param.ScenarioDefinition (Name, IsBase, IsActive, RunsNightly, FollowsBase, IsSynthetic) "
                                    "OUTPUT inserted.Id VALUES (N'pytest geçiş 0075', 0, 1, 0, 0, 0)")).scalar_one()
            for code, seq, seconds, tolerance in old:
                c.execute(sa.text("INSERT INTO param.ObjectiveDefinition (ScenarioDefinitionId, Code, Seq, TimeBudgetSeconds, TolerancePct, IsActive) "
                                  "VALUES (:s, :c, :q, :t, :p, :a)"), {"s": sid, "c": code, "q": seq, "t": seconds, "p": tolerance, "a": seq is not None})
            # 0075'in taşıma SQL'i (IsMain kolonu 0076'da kalktı: yalnız kod ve kapsam güncellemeleri denenir)
            for statement in migration("0075").moved_sql(f"ScenarioDefinitionId = {sid}").split(";"):
                if statement.strip() and "IsMain = 1 WHERE" not in statement:
                    c.execute(sa.text(statement.replace("IsMain = 0, ", "")))
            rows = obj.read_objectives(c, sid)
        finally:
            tx.rollback()
    assert [(r["label"], r["scope_text"], r["seq"], r["seconds"], r["tolerance"]) for r in rows if r["active"]] == [
        ("Gecikme", "Tümü", 1, 250, 1.0), ("Karşılanmayan talep", "Tümü", 2, 300, 0.0), ("Karşılanmayan talep", "Talep türü: Tahmin", 3, 120, 2.0),
        ("Gecikme", "Talep türü: Tahmin", 4, 90, 2.0)]


@pytest.mark.db
def test_read_rows_and_catalog(base, client, people):
    key = auth(people[KEY_USER])
    body = read(client, key)
    assert len(body["rows"]) == 24 and body["total_seconds"] == 1140
    first = body["rows"][0]
    assert (first["label"], first["group"], first["family"], first["scope"], first["scope_text"], first["description"]) == (
        "Karşılanmayan talep", "Talep", "talep", {"DemandType": ["Kesin sipariş"]}, "Talep türü: Kesin sipariş", None)
    assert first["scope_parts"] == [{"label": "Talep türü", "values": ["Kesin sipariş"]}]
    assert not {"is_main", "rest", "dimmed", "tip"} & set(first)                                         # ana satır, "Kalanlar", soluk işareti ve ipucu yok
    fason = next(r for r in body["rows"] if r["code"] == "SUBCONTRACT")
    assert (fason["scope"], fason["scope_text"], fason["scope_parts"], fason["group"]) == ({}, "", [], "Diğer")
    catalog = {k["code"]: k for k in body["catalog"]}
    assert list(catalog) == [o.code for o in cat.OBJECTIVES]                                             # bütün hedefler; kapsam almayanlarda eksen yok
    assert catalog["SUBCONTRACT"]["axes"] == [] and catalog["SUBCONTRACT"]["group"] == "Diğer" and catalog["OVERTIME"]["group"] == "Kaynak"
    groups = catalog["SAFETY_STOCK"]["axes"][1]
    assert groups["open"] and "Rulman" in groups["values"]
    assert catalog["UNMET_DEMAND"]["axes"][1]["values"] == [1, 2, 3, 4, 5]


@pytest.mark.db
def test_create_edit_delete_and_reset_over_the_api(db_engine, base, client, people):
    key = auth(people[KEY_USER])
    before = read(client, key)["rows"]
    # yeni hedef: listenin (aktiflerin) sonuna, aktif; başka satır değişmez; kapsam var olan satırla örtüşür
    new = {"code": "UNMET_DEMAND", "scope": {"PriorityGroup": [2, 1], "DemandType": ["Kesin sipariş"]}, "description": " Öncelikliler önce ", "seconds": 45, "tolerance": 1.5}
    r = client.post(URL, headers=key, json=new)
    assert r.status_code == 200, r.text
    body = r.json()
    row = next(x for x in body["rows"] if x["description"] == "Öncelikliler önce")
    assert (row["seq"], row["active"], row["seconds"], row["tolerance"], row["scope_text"]) == (16, True, 45, 1.5, "Talep türü: Kesin sipariş · Öncelik grubu: 1, 2")
    strip = lambda rows: [{k: v for k, v in x.items()} for x in rows]   # noqa: E731
    assert strip([x for x in body["rows"] if x["id"] != row["id"]]) == strip(before)                     # bölme, süre paylaştırma yok
    assert body["total_seconds"] == 1140 + 45 and len(body["rows"]) == 25
    # bir eksende hepsi seçilirse o eksen yazılmaz (verideki malzeme gruplarının tamamı da)
    every = read(client, key)["catalog"][2]["axes"][1]["values"]
    r = client.post(URL, headers=key, json={"code": "SAFETY_STOCK", "scope": {"MaterialLevel": ["Hammadde"], "MaterialGroup": every}, "seconds": 5, "tolerance": 0})
    added = r.json()["rows"][16]
    assert r.status_code == 200 and (added["scope"], added["scope_text"]) == ({"MaterialLevel": ["Hammadde"]}, "Malzeme seviyesi: Hammadde")
    assert client.delete(f"{URL}/{added['id']}", headers=key).status_code == 200
    # aynı kapsam ikinci kez ve hedefin tamamı da tanımlanabilir
    assert client.post(URL, headers=key, json={**new, "description": None}).status_code == 200
    r = client.post(URL, headers=key, json={"code": "UNMET_DEMAND", "scope": {}, "seconds": 10, "tolerance": 0})
    assert r.status_code == 200 and r.json()["rows"][17]["scope_text"] == "Tümü"
    r = client.post(URL, headers=key, json={"code": "SUBCONTRACT", "seconds": 5, "tolerance": 0})
    assert r.status_code == 200 and len(r.json()["rows"]) == 28 and names(r.json(), "SUBCONTRACT") == ["Fason", "Fason"]
    # zorunlu alanlar ve doğrulamalar: süre ve ödün payı varsayılansız (K-138)
    for bad, field in (({"code": "UNMET_DEMAND", "scope": {}, "tolerance": 0}, "seconds"), ({"code": "UNMET_DEMAND", "scope": {}, "seconds": 10}, "tolerance"),
                       ({"code": "UNMET_DEMAND", "scope": {}, "seconds": 0, "tolerance": 0}, "seconds"), ({"code": "UNMET_DEMAND", "scope": {}, "seconds": 10, "tolerance": 101}, "tolerance"),
                       ({"code": "SUBCONTRACT", "scope": {"DemandType": ["Tahmin"]}, "seconds": 10, "tolerance": 0}, "scope"),
                       ({"code": "YOK", "scope": {}, "seconds": 10, "tolerance": 0}, "code"), ({"code": "UNMET_DEMAND", "scope": {"PriorityGroup": [9]}, "seconds": 10, "tolerance": 0}, "scope.PriorityGroup"),
                       ({"code": "UNMET_DEMAND", "scope": {}, "seconds": 10, "tolerance": 0, "description": "x" * 201}, "description")):
        r = client.post(URL, headers=key, json=bad)
        assert r.status_code == 422 and r.json()["error"]["details"][0]["field"] == field, bad
    # düzenle: hedef, kapsam, açıklama, süre, ödün payı; sıra ve aktiflik değişmez
    r = client.put(f"{URL}/{row['id']}", headers=key, json={"code": "LATENESS", "scope": {"DemandType": ["Tahmin", "Teklif"]}, "description": "", "seconds": 50, "tolerance": 2})
    assert r.status_code == 200, r.text
    edited = next(x for x in r.json()["rows"] if x["id"] == row["id"])
    assert (edited["label"], edited["scope_text"], edited["description"], edited["seconds"], edited["tolerance"], edited["seq"], edited["active"]) == (
        "Gecikme", "Talep türü: Teklif, Tahmin", None, 50, 2.0, 16, True)
    assert client.put(f"{URL}/{row['id']}", headers=key, json={"code": "LATENESS", "scope": {}, "description": None}).status_code == 422   # aktif satırda süre zorunlu
    # kapalı satır düzenlenir: süre ve ödün payı yazılmaz
    closed = next(x for x in r.json()["rows"] if not x["active"] and x["code"] == "OVER_TARGET_LOAD")
    r = client.put(f"{URL}/{closed['id']}", headers=key, json={"code": "OVER_TARGET_LOAD", "scope": {"ResourceType": ["Makine", "İşçi"]}, "description": "Darboğaz", "seconds": 99, "tolerance": 9})
    assert r.status_code == 200, r.text
    again = next(x for x in r.json()["rows"] if x["id"] == closed["id"])
    assert (again["scope_text"], again["description"], again["seconds"], again["tolerance"], again["active"]) == ("Kaynak grubu tipi: İşçi, Makine", "Darboğaz", None, None, False)
    assert client.put(f"{URL}/999999999", headers=key, json=new).status_code == 422
    # sil: her satır silinir (başlangıç satırı da); kapsamı başka satıra geçmez; sıra boşluksuz kalır
    first = r.json()["rows"][0]
    r = client.delete(f"{URL}/{first['id']}", headers=key)
    assert r.status_code == 200, r.text
    body = r.json()
    assert first["id"] not in [x["id"] for x in body["rows"]] and [x["seq"] for x in body["rows"] if x["active"]] == list(range(1, 19))
    assert "Karşılanmayan talep · Talep türü: Kesin sipariş" not in names(body)
    assert client.delete(f"{URL}/999999999", headers=key).status_code == 422
    # denetim izi
    with db_engine.connect() as c:
        logged = c.execute(sa.text("SELECT TOP 12 ObjectKey, OldValue, NewValue FROM adm.AuditLog WHERE Action = N'Hedef değişikliği' AND UserId = :u ORDER BY Id DESC"),
                           {"u": people[KEY_USER]}).all()
    keys = [x.ObjectKey for x in logged]
    assert "Baz · Karşılanmayan talep · Talep türü: Kesin sipariş · Öncelik grubu: 1, 2" in keys and "Baz · Gecikme · Talep türü: Teklif, Tahmin" in keys and "Baz · Fason" in keys
    change = next(x for x in logged if x.ObjectKey == "Baz · Gecikme · Talep türü: Teklif, Tahmin")
    assert json.loads(change.OldValue)["Objective"] == "Karşılanmayan talep" and json.loads(change.NewValue)["Objective"] == "Gecikme"
    # başlangıç düzenine getir
    r = client.post(f"{URL}/reset", headers=key)
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["rows"]) == 24 and body["total_seconds"] == 1140 and all(x["description"] is None for x in body["rows"])


@pytest.mark.db
def test_list_can_be_emptied_and_saved(base, client, people):
    key = auth(people[KEY_USER])
    for row in read(client, key)["rows"]:
        assert client.delete(f"{URL}/{row['id']}", headers=key).status_code == 200                       # silinemeyen satır yok
    body = read(client, key)
    assert body["rows"] == [] and body["total_seconds"] == 0
    assert client.put(URL, headers=key, json={"rows": []}).status_code == 200                            # boş liste kaydedilir
    body = client.post(URL, headers=key, json={"code": "ALTERNATIVE", "seconds": 30, "tolerance": 5}).json()
    assert [(r["label"], r["seq"]) for r in body["rows"]] == [("Alternatif önceliği", 1)]
    only = body["rows"][0]
    r = client.put(URL, headers=key, json={"rows": [{"id": only["id"], "active": False, "seconds": None, "tolerance": None}]})
    assert r.status_code == 422 and r.json()["error"]["details"][0]["problem"] == "En az bir hedef aktif olmalı."


@pytest.mark.db
def test_save_keeps_order_time_and_labels(base, client, people):
    key = auth(people[KEY_USER])
    rows = read(client, key)["rows"]
    sent = [{"id": r["id"], "active": r["active"], "seconds": r["seconds"], "tolerance": r["tolerance"]} for r in rows]
    sent[0], sent[1] = sent[1], sent[0]                                                                  # farklı hedeflerin satırları iç içe sıralanır
    sent[0]["seconds"] = 0
    r = client.put(URL, headers=key, json={"rows": sent})
    assert r.status_code == 422 and r.json()["error"]["details"][0]["record"] == "Gecikme · Talep türü: Kesin sipariş"
    sent[0]["seconds"] = 100
    body = client.put(URL, headers=key, json={"rows": sent}).json()
    assert [(x["label"], x["seq"], x["seconds"]) for x in body["rows"][:2]] == [("Gecikme", 1, 100), ("Karşılanmayan talep", 2, 210)]
    assert body["total_seconds"] == 1030


@pytest.mark.db
def test_permissions(base, client, people):
    end = auth(people[END_USER])
    new = {"code": "OVERTIME", "scope": {"ResourceType": ["İşçi"]}, "seconds": 5, "tolerance": 0}
    assert client.get(URL, headers=end).status_code == 403
    assert client.post(URL, headers=end, json=new).status_code == 403
    assert client.put(f"{URL}/1", headers=end, json=new).status_code == 403
    assert client.post(f"{URL}/reset", headers=end).status_code == 403
    assert client.delete(f"{URL}/1", headers=end).status_code == 403


@pytest.mark.db
def test_copy_and_engine_read_the_rows(db_engine, base):
    from app.params import scenarios
    with Session(db_engine) as s:
        obj.create(s, base, "UNMET_DEMAND", {"DemandType": ["Kesin sipariş"], "PriorityGroup": [1, 2]}, "Öncelikliler", 45, 0)
        copy = scenarios.create_copy(s, "pytest hedef kopyası", base, follows_base=True)
        strip = lambda rows: [{k: v for k, v in r.items() if k != "id"} for r in rows]   # noqa: E731
        assert strip(obj.read_objectives(s, copy["Id"])) == strip(obj.read_objectives(s, base))          # ayar: tam kopya (kapsam ve açıklama dahil)
        loaded = loader.load_parameters(s, copy["Id"])
        assert [(o.seq, o.code, o.scope, o.time_budget_seconds) for o in loaded.objectives[:1]] == [(1, "UNMET_DEMAND", {"DemandType": ["Kesin sipariş"]}, 210)]
        last = loaded.objectives[-1]
        assert (last.seq, last.code, last.scope, last.time_budget_seconds, last.tolerance_pct) == (16, "UNMET_DEMAND", {"DemandType": ["Kesin sipariş"], "PriorityGroup": [1, 2]}, 45, 0.0)
        assert len(loaded.objectives) == 16 and not hasattr(last, "is_main")                             # yalnız aktif satırlar
        rows = [{"id": o.seq, "code": o.code, "scope": o.scope} for o in loaded.objectives]
        assert [r["id"] for r in obj.rows_of(rows, "UNMET_DEMAND", {"DemandType": "Kesin sipariş", "PriorityGroup": 2})] == [1, 16]   # örtüşen iki satır ayrı ayrı
        assert [r["id"] for r in obj.rows_of(rows, "UNMET_DEMAND", {"DemandType": "Kesin sipariş", "PriorityGroup": 4})] == [1]
        assert obj.rows_of(rows, "UNMET_DEMAND", {"DemandType": "Teklif", "PriorityGroup": 1}) == []      # satırı kapalı: hiçbir hedefe girmez
        s.rollback()


@pytest.mark.db
def test_synthetic_scenarios_start_layout_and_added_rows(db_engine):
    with Session(db_engine) as s:
        ids = dict(s.execute(sa.text("SELECT Name, Id FROM param.ScenarioDefinition WHERE IsSynthetic = 1")).all())
        plain = obj.read_objectives(s, ids["MILP deneme"])
        assert len(plain) == 24 and sum(r["seconds"] or 0 for r in plain) == 1140
        assert sum(r["seconds"] or 0 for r in obj.read_objectives(s, ids["Kısıtsız kapasite"])) == 570     # süre bütçesi böleni 2
        rows = obj.read_objectives(s, ids["Fazla mesaili"])
        assert len(rows) == 26
        assert [(r["label"], r["scope_text"], r["seconds"], r["description"]) for r in rows[:3]] == [
            ("Karşılanmayan talep", "Talep türü: Kesin sipariş · Öncelik grubu: 1, 2", 60, "Öncelikli siparişler önce"),
            ("Hedef doluluğun üstü", "Kaynak grubu tipi: Makine", 20, None),
            ("Karşılanmayan talep", "Talep türü: Kesin sipariş", 210, None)]                              # örtüşen satır olduğu gibi durur
        safety = [r["scope_text"] for r in rows if r["code"] == "SAFETY_STOCK"]
        at = safety.index("Malzeme seviyesi: Hammadde · Malzeme grubu: Rulman")
        assert safety[at + 1] == "Malzeme seviyesi: Hammadde"


@pytest.mark.db
def test_synthetic_cli_queues_the_quality_job(db_engine):
    """Sentetik `load` ve `reset` işinin sonunda tam kapsamlı veri kalitesi işini kuyruğa koyar (K-195 madde 12); bekleyen iş varsa birleşir."""
    from app.data.synthetic.load import queue_quality
    with db_engine.begin() as c:
        before = {r[0] for r in c.execute(sa.text("SELECT Id FROM adm.Job WHERE JobType = N'Veri kalitesi' AND Status = N'Sırada'"))}
    job = queue_quality(db_engine)
    try:
        with db_engine.connect() as c:
            row = c.execute(sa.text("SELECT JobType, Status, Payload FROM adm.Job WHERE Id = :i"), {"i": job}).one()
        assert (row.JobType, row.Status) == ("Veri kalitesi", "Sırada")
        payload = json.loads(row.Payload)
        assert payload["tables"] is None and payload["today"] is None                                    # tam kapsam
        assert queue_quality(db_engine) == job                                                           # ikinci çağrı yeni iş açmaz
    finally:
        if job not in before:
            with db_engine.begin() as c:
                c.execute(sa.text("DELETE FROM adm.Job WHERE Id = :i"), {"i": job})
