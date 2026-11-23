"""Malzeme blokajı, 7.13 (K-193; ekran 31 üçüncü sekme, fonksiyon 99): kayıt ve doğrulamalar, türün malzemenin tedarik biçimine uyması, tablo içi
değişiklik, Baz + fark, plan dönemi hesabı (oranın altı, üstü, tam eşiği; birleşme; en düşük oran; iki tedarik biçimi; süresiz kayıt; kısa ilk dönem),
motor arayüzü, veri kalitesi uyarısı ve yetki. Smartchain_test'te; kendi kayıtlarını uzak gelecekte (2031) açar ve sonunda siler, sentetik kayıtlara
dokunmaz. Dönem hesabı sabit bir "bugün" ile yapılır (T0): test haftanın gününe ve bugünün tarihine bağlı değildir.
"""
import json
from datetime import date, timedelta
from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app import materialholds as rules
from app.api.permissions import END_USER, KEY_USER
from app.data.synthetic import dataset as d
from app.engine.data import SqlPlanningData
from app.params import resolve, scenario_tables
from app.quality import run as quality_run

from auth_helpers import auth
from test_capacity import clean, world  # noqa: F401  (fixture'lar)
from test_capacity_entries import api, audits, people  # noqa: F401

pytestmark = pytest.mark.db

URL = "/api/model-constraints/material-holds"
LIST, VALIDITY = "material-holds", "material-holds-validity"
PRODUCTION, PURCHASE, BOTH = rules.PRODUCTION, rules.PURCHASE, rules.BOTH
Y = 2031                                                   # testin kayıtlarının yılı (sentetik kayıtların ve bugünkü ufkun dışında)
T0 = date(Y, 1, 6)                                         # dönem hesabının "bugün"ü (Pazartesi): haftalık Oca–Mar, aylık Nis–Eyl
LOCKED = "Lokasyon ve malzeme kayıttan sonra değişmez; kaydı silip yeniden girin."


def tr(day: date) -> str:
    return f"{day:%d.%m.%Y}"


@pytest.fixture
def mats(db_engine, api, clean):  # noqa: F811
    """Sentetik blokajlarda kullanılmayan malzemeler: yalnız satın alınan, yalnız üretilen; ayrıca hem üretilen hem satın alınan (üç tür de girilebilir). Test
    sonunda bu testin açtığı blokaj kayıtları ve geçmişleri silinir."""
    with db_engine.connect() as c:
        mark = c.execute(sa.text("SELECT COALESCE(MAX(Id), 0) FROM param.MaterialHold")).scalar()
        used = {r[0] for r in c.execute(sa.text("SELECT DISTINCT MaterialId FROM param.MaterialHold"))}
    options = api.get(f"{URL}/options").json()["materials"]
    free = [m for m in options if m["material_id"] not in used]
    buy = next(m for m in free if m["purchasable"] is True and m["producible"] is False)
    make = next(m for m in free if m["producible"] is True and m["purchasable"] is False)
    any_ = next(m for m in options if m["producible"] is True and m["purchasable"] is True)      # sentetik: ALT-020 (kendi kayıtları 2027'de)
    out = {"loc": buy["location_id"], "buy": buy["material_id"], "buy_code": buy["code"], "make": make["material_id"], "make_code": make["code"],
           "any": any_["material_id"], "any_code": any_["code"], "options": options}
    yield out
    with db_engine.begin() as c:
        c.execute(sa.text("DELETE FROM adm.FieldChange WHERE TableName = N'MaterialHold' AND (TRY_CAST(RecordKey AS bigint) > :m OR RecordKey LIKE N'%@%')"), {"m": mark})
        c.execute(sa.text("DELETE FROM param.MaterialHold WHERE Id > :m"), {"m": mark})


def rows(api, name: str, scenario: int, **body) -> list[dict]:  # noqa: F811
    r = api.post(f"/api/{name}/query", json={"limit": 100, "scenario_id": scenario, **body})
    assert r.status_code == 200, r.text
    return r.json()["rows"]


def new(api, scenario: int, expect: int = 201, **values):  # noqa: F811
    r = api.post(f"{URL}?scenario_id={scenario}", json={"values": values})
    assert r.status_code == expect, r.text
    return r.json()["id"] if expect == 201 else {p["field"]: p["problem"] for p in r.json()["error"]["details"]}


def hold(api, scenario: int, m: dict, start: date, end: date | None, kind: str = PURCHASE, material: str = "buy", pct=50, reason: str | None = None, expect: int = 201):  # noqa: F811
    return new(api, scenario, expect, LocationId=m["loc"], MaterialId=m[material], HoldType=kind, StartDate=tr(start), EndDate=tr(end) if end else None, ClosePct=pct,
               Reason=reason)


def edit(api, scenario: int, changes: list[tuple], expect: int = 200):  # noqa: F811
    r = api.put(f"{URL}?scenario_id={scenario}", json={"changes": [{"id": i, "field": f, "value": v} for i, f, v in changes]})
    assert r.status_code == expect, r.text
    return r.json() if expect == 200 else r.json()["error"]["details"]


def act(api, scenario: int, row_id: int, action: str | None, expect: int = 200):  # noqa: F811
    r = api.delete(f"{URL}/{row_id}?scenario_id={scenario}") if action is None else api.post(f"{URL}/{row_id}/{action}?scenario_id={scenario}")
    assert r.status_code == expect, r.text


def mine(api, scenario: int, m: dict, material: str = "buy") -> list[dict]:  # noqa: F811
    """Kayıtlar listesinde bu malzemenin test yılındaki kayıtları."""
    found = rows(api, LIST, scenario, filters=[{"field": "OwnerKeys", "op": "contains", "values": [f",m{m[material]},"]}], sort=[{"field": "StartDate", "dir": "asc"}])
    return [r for r in found if r["StartDate"] >= f"{Y}-01-01"]


def periods(db_engine, scenario: int, m: dict, material: str = "buy", today: date = T0) -> dict:
    """Malzemenin dönem sonuçları: (tedarik biçimi, dönem başı) → (blokajlı gün, takvim günü, eşik, kapalı)."""
    with Session(db_engine) as s:
        found = [r for r in rules.periods(s, scenario, today) if r["MaterialId"] == m[material]]
    return {(r["Supply"], r["PeriodStart"]): (r["BlockedDays"], r["Days"], float(r["ClosePct"]), r["Closed"]) for r in found}


# ------------------------------------------------------------------ listeler ve seçenekler

def test_lists_options_and_synthetic_records(api, db_engine, world, mats):  # noqa: F811
    """Seçenekler güncel malzemelerdir, tedarik biçimiyle; Kayıtlar ve Geçerlilik listelerinin alanları; İlişkili alanlar; sentetik kayıtlar (docs/11) ve
    "Kısıtsız kapasite" senaryosundaki fark; kayıt defteri."""
    with db_engine.connect() as c:
        current = c.execute(sa.text("SELECT COUNT(*) FROM core.Material WHERE VersionTo IS NULL")).scalar()
        mono = c.execute(sa.text("SELECT Id FROM param.ScenarioDefinition WHERE Name = N'Kısıtsız kapasite' AND IsSynthetic = 1")).scalar_one()
    body = api.get(f"{URL}/options").json()
    assert len(body["materials"]) == current and body["types"] == [PRODUCTION, PURCHASE, BOTH]
    assert all(m["location"] == d.LOCATION_CODE for m in body["materials"])
    both = next(m for m in body["materials"] if m["code"] == d.HOLD_PARTIAL_MATERIAL)
    assert (both["producible"], both["purchasable"]) == (True, True)                                 # hem üretilen hem satın alınan (docs/11)
    assert [m["code"] for m in body["materials"] if m["producible"] and m["purchasable"]] == [d.HOLD_PARTIAL_MATERIAL]

    cols = api.get(f"/api/{LIST}/columns").json()
    assert [c["field"] for c in cols["columns"] if c["default_visible"]] == ["LocationCode", "MaterialCode", "HoldType", "StartDate", "EndDate", "ClosePct", "Reason", "Origin", "IsValid"]
    labels = {c["field"]: c["label"] for c in cols["columns"]}
    assert (labels["LocationCode"], labels["MaterialCode"], labels["HoldType"], labels["ClosePct"], labels["MaterialName"]) == (
        "Lokasyon", "Malzeme", "Tür", "Dönemi kapatma oranı (%)", "Malzeme adı")
    assert [r["label"] for r in cols["relations"]] == ["Malzeme", "Lokasyon"] and cols["scenario_list"] is True
    cols = api.get(f"/api/{VALIDITY}/columns").json()
    assert [c["field"] for c in cols["columns"] if c["default_visible"]] == [
        "LocationCode", "MaterialCode", "Supply", "Period", "PeriodStart", "PeriodEnd", "BlockedDays", "Ratio", "Threshold", "Status"]
    assert {c["field"]: c["label"] for c in cols["columns"]}["Threshold"] == "Eşik (%)"

    base = world["base"]
    synthetic = {(r["MaterialCode"], r["HoldType"]): r for r in rows(api, LIST, base) if r["StartDate"] < f"{Y}-01-01"}
    assert set(synthetic) == {(d.HOLD_PARTIAL_MATERIAL, PRODUCTION), (d.HOLD_PARTIAL_MATERIAL, BOTH), (d.HOLD_OPEN_MATERIAL, PURCHASE)}
    assert synthetic[(d.HOLD_OPEN_MATERIAL, PURCHASE)]["EndDate"] is None and all(float(r["ClosePct"]) == d.HOLD_PCT and r["Origin"] == "Baz" for r in synthetic.values())
    short, long = synthetic[(d.HOLD_PARTIAL_MATERIAL, PRODUCTION)], synthetic[(d.HOLD_PARTIAL_MATERIAL, BOTH)]
    days = lambda r: (date.fromisoformat(r["EndDate"]) - date.fromisoformat(r["StartDate"])).days + 1  # noqa: E731
    assert (days(short), days(long)) == (d.HOLD_SHORT_DAYS, d.HOLD_LONG_DAYS) and short["StartDate"][8:] == long["StartDate"][8:] == "01"
    off = next(r for r in rows(api, LIST, mono) if r["Id"] == long["Id"])                            # "Kısıtsız kapasite": 20 günlük blokaj geçersiz
    assert (off["IsValid"], off["Origin"], off["OverriddenFields"]) == (False, "Senaryo farkı", ",IsValid,")
    related = rows(api, LIST, base, fields=["MaterialCode", "MaterialId/Name", "LocationId/Name"])
    assert all(r["MaterialId/Name"] and r["LocationId/Name"] for r in related)
    assert "MaterialHold" in {t.name for t in scenario_tables.TABLES if t.kind == scenario_tables.DATA and t.materialize is not None}
    assert "MaterialHold" not in resolve.KEYS and "AllocationRule" not in scenario_tables.BY_NAME     # blokajlar birleşir; alokasyon tablosu kalktı


# ------------------------------------------------------------------ yeni kayıt ve doğrulama

def test_create_and_validation(api, db_engine, world, mats, people):  # noqa: F811
    """Kayıt; doğrulamalar alan bazında; tür malzemenin tedarik biçimine uyar (boş alan izin verir); aynı malzeme ve başlangıçla ikinci kayıt serbest."""
    base, m = world["base"], mats
    a = date(Y, 4, 1)
    first = hold(api, base, m, a, None, reason="Tedarikçi geçişi")
    [row] = mine(api, base, m)
    assert (row["Id"], row["LocationCode"], row["MaterialCode"], row["HoldType"], row["StartDate"], row["EndDate"], float(row["ClosePct"]), row["Reason"], row["Origin"],
            row["IsValid"]) == (first, d.LOCATION_CODE, m["buy_code"], PURCHASE, f"{Y}-04-01", None, 50.0, "Tedarikçi geçişi", "Baz", True)
    body = dict(LocationId=m["loc"], MaterialId=m["buy"], HoldType=PURCHASE, StartDate=tr(date(Y, 5, 1)), ClosePct=50)
    cases = [
        ({**body, "MaterialId": None}, "MaterialId", "Malzeme seçilmeli."),
        ({**body, "MaterialId": 999_999_999}, "MaterialId", "Güncel veride yok."),
        ({**body, "HoldType": None}, "HoldType", "Boş bırakılamaz."),
        ({**body, "HoldType": "Satış"}, "HoldType", None),                                           # satış blokajı yok
        ({**body, "HoldType": PRODUCTION}, "HoldType", rules.NOT_PRODUCED),                          # yalnız satın alınan malzeme
        ({**body, "HoldType": BOTH}, "HoldType", rules.NOT_PRODUCED),
        ({**body, "MaterialId": m["make"], "HoldType": PURCHASE}, "HoldType", rules.NOT_PURCHASED),  # yalnız üretilen malzeme
        ({**body, "MaterialId": m["make"], "HoldType": BOTH}, "HoldType", rules.NOT_PURCHASED),
        ({**body, "StartDate": None}, "StartDate", "Boş bırakılamaz."),
        ({**body, "EndDate": tr(date(Y, 4, 15))}, "EndDate", "Bitiş başlangıçtan önce olamaz."),
        ({**body, "ClosePct": None}, "ClosePct", "Boş bırakılamaz."),
        ({**body, "ClosePct": 0}, "ClosePct", "0'dan büyük, en çok 100 olmalı."),
        ({**body, "ClosePct": "100,5"}, "ClosePct", "0'dan büyük, en çok 100 olmalı."),
        ({**body, "ClosePct": "33,333"}, "ClosePct", "En çok 2 ondalık."),
        ({**body, "Reason": "x" * 256}, "Reason", "En çok 255 karakter."),
        ({**body, "SupplierId": 1}, "SupplierId", "Bilinmeyen alan."),
    ]
    for values, field, problem in cases:
        got = new(api, base, 422, **values)
        assert field in got and (problem is None or got[field] == problem), (values, got)
    assert len(mine(api, base, m)) == 1                                                            # hiçbiri kaydedilmedi
    # hem üretilen hem satın alınan malzemede üç tür de girilir; yalnız üretilende "Üretim"
    made = [hold(api, base, m, date(Y, 5, n + 1), date(Y, 5, n + 1), kind=kind, material="any") for n, kind in enumerate(rules.TYPES)]
    assert [r["HoldType"] for r in mine(api, base, m, "any")] == list(rules.TYPES) and len(made) == 3
    hold(api, base, m, a, a, kind=PRODUCTION, material="make", pct="100")
    # aynı malzeme ve başlangıçla ikinci kayıt serbest (blokajlar birleşir)
    again = hold(api, base, m, a, date(Y, 4, 3), pct="12,5")
    assert [r["Id"] for r in mine(api, base, m)] == [first, again] or [r["Id"] for r in mine(api, base, m)] == [again, first]
    logged = audits(db_engine, people[KEY_USER], "Malzeme blokajı eklendi")
    assert {a_["ObjectType"] for a_ in logged} == {"Malzeme blokajı"} and f"{m['buy_code']} · 01.04.{Y}" in {a_["ObjectKey"] for a_ in logged}
    new_value = json.loads(next(a_ for a_ in logged if a_["ObjectKey"] == f"{m['buy_code']} · 01.04.{Y}")["NewValue"])
    assert set(new_value) >= {"HoldType", "StartDate", "ClosePct"}


def test_cells_change_and_leave_history(api, db_engine, world, mats, people):  # noqa: F811
    """Tablo içi değişiklik: tür, tarihler, oran ve sebep değişir; lokasyon ve malzeme düzenlenemez; tür değişirken de tedarik biçimine uyar; hepsi ya da
    hiçbiri; Geçmiş ("Model kısıtları") ve denetim izi; silme."""
    base, m = world["base"], mats
    row = hold(api, base, m, date(Y, 4, 1), None, kind=PRODUCTION, material="any")
    assert edit(api, base, [(row, "HoldType", BOTH), (row, "EndDate", tr(date(Y, 4, 20))), (row, "ClosePct", "62,5"), (row, "Reason", "Kalıp değişimi")])["saved"] == 4
    [got] = mine(api, base, m, "any")
    assert (got["HoldType"], got["EndDate"], float(got["ClosePct"]), got["Reason"]) == (BOTH, f"{Y}-04-20", 62.5, "Kalıp değişimi")
    other = hold(api, base, m, date(Y, 4, 1), None)                                                 # yalnız satın alınan malzeme
    problems = edit(api, base, [(other, "HoldType", BOTH), (other, "MaterialCode", "X"), (row, "ClosePct", 0), (row, "LocationCode", "Y"), (row, "Reason", "geçerli değişiklik")], expect=422)
    assert {(x["id"], x["field"]): x["problem"] for x in problems} == {
        (other, "HoldType"): rules.NOT_PRODUCED, (other, "MaterialCode"): LOCKED, (row, "ClosePct"): "0'dan büyük, en çok 100 olmalı.", (row, "LocationCode"): LOCKED}
    assert mine(api, base, m, "any")[0]["Reason"] == "Kalıp değişimi"                              # geçerli değişiklik de kaydedilmedi
    history = api.post("/api/record-history/query", json={"limit": 100, "sort": [{"field": "At", "dir": "asc"}], "filters": [
        {"field": "TableName", "op": "in", "values": ["MaterialHold"]}, {"field": "RecordKey", "op": "in", "values": [str(row)]}]}).json()["rows"]
    assert sorted((h["FieldLabel"], h["OldValue"], h["NewValue"]) for h in history if h["NewValue"] != "Kayıt oluştu") == sorted([
        ("Tür", PRODUCTION, BOTH), ("Bitiş", None, f"20.04.{Y}"), ("Dönemi kapatma oranı (%)", "50", "62,5"), ("Sebep", None, "Kalıp değişimi")])
    assert {h["SourceText"] for h in history} == {"Model kısıtları · Kapasite Planlamacı"}
    changed = audits(db_engine, people[KEY_USER], "Malzeme blokajı değişti")
    assert changed and json.loads(changed[-1]["NewValue"])["ClosePct"] == "62,5"
    act(api, base, other, None)
    assert mine(api, base, m) == [] and audits(db_engine, people[KEY_USER], "Malzeme blokajı silindi")


def test_unknown_supply_flag_allows_every_type(db_engine, mats):
    """ "Bilinmiyor" (boş alan) yolu (K-193 madde 3): `IsProducible` ya da `IsPurchasable` boşsa tür reddedilmez; yalnız açıkça "Hayır" olan reddedilir.
    Alan işlem içinde boşaltılır ve geri alınır: sentetik veri değişmez."""
    m = mats
    row = lambda material, kind: {"MaterialId": m[material], "HoldType": kind}  # noqa: E731
    with Session(db_engine) as s:
        assert rules._type_fits(s, row("make", PURCHASE)) == [("HoldType", rules.NOT_PURCHASED)] and rules._type_fits(s, row("make", BOTH)) == [("HoldType", rules.NOT_PURCHASED)]
        assert rules._type_fits(s, row("buy", PRODUCTION)) == [("HoldType", rules.NOT_PRODUCED)]
        try:
            s.execute(sa.text("UPDATE core.Material SET IsPurchasable = NULL WHERE Id = :a AND VersionTo IS NULL"), {"a": m["make"]})
            s.execute(sa.text("UPDATE core.Material SET IsProducible = NULL WHERE Id = :b AND VersionTo IS NULL"), {"b": m["buy"]})
            assert [rules._type_fits(s, row(material, kind)) for material in ("make", "buy") for kind in rules.TYPES] == [[]] * 6
            listed = {o["material_id"]: o for o in rules.options(s)}
            assert (listed[m["make"]]["producible"], listed[m["make"]]["purchasable"]) == (True, None)          # seçeneklerde boş: bilinmiyor
            assert (listed[m["buy"]]["producible"], listed[m["buy"]]["purchasable"]) == (None, True)
        finally:
            s.rollback()
    with Session(db_engine) as s:                                                                    # geri alındı
        assert rules._type_fits(s, row("make", PURCHASE)) == [("HoldType", rules.NOT_PURCHASED)]


# ------------------------------------------------------------------ Baz + fark

def test_scenario_difference_invalidate_and_restore(api, db_engine, world, mats):  # noqa: F811
    """Baz'ı izleyen senaryo Baz'ın kaydını okur; değişikliği fark satırıdır; Baz kaydı senaryoda silinmez, geçersiz yapılır; "Senaryo farkını kaldır" Baz'a
    döndürür. Aynı malzeme ve başlangıçla senaryonun kendi kaydı ayrı satırdır (çakışma kuralı yok: blokajlar birleşir)."""
    base, follower, m = world["base"], world["follower"], mats
    april = date(Y, 4, 1)
    row = hold(api, base, m, april, date(Y, 4, 20))                                                 # 20 / 30 gün: Nisan kapalı
    assert [(r["Id"], r["Origin"]) for r in mine(api, follower, m)] == [(row, "Baz")]
    edit(api, follower, [(row, "EndDate", tr(date(Y, 4, 10)))])                                     # senaryoda 10 gün: açık
    [seen] = mine(api, follower, m)
    assert (seen["EndDate"], seen["Origin"], seen["OverriddenFields"]) == (f"{Y}-04-10", "Senaryo farkı", ",EndDate,")
    assert json.loads(seen["BaseValues"])["EndDate"] == f"{Y}-04-20" and mine(api, base, m)[0]["EndDate"] == f"{Y}-04-20"
    assert periods(db_engine, base, m)[(PURCHASE, april)][3] is True and periods(db_engine, follower, m)[(PURCHASE, april)][3] is False
    act(api, follower, row, None, expect=409)                                                       # Baz kaydı senaryoda silinmez
    act(api, follower, row, "invalidate")
    assert mine(api, follower, m)[0]["IsValid"] is False and periods(db_engine, follower, m) == {}  # geçersiz kayıt hesaba girmez
    assert periods(db_engine, base, m)[(PURCHASE, april)][3] is True
    act(api, follower, row, "restore")
    [back] = mine(api, follower, m)
    assert (back["EndDate"], back["Origin"], back["IsValid"]) == (f"{Y}-04-20", "Baz", True)
    own = hold(api, follower, m, april, date(Y, 4, 25))                                             # aynı başlangıçla senaryonun kendi kaydı: iki satır
    assert sorted((r["Id"], r["Origin"]) for r in mine(api, follower, m)) == sorted([(row, "Baz"), (own, "Senaryo")])
    assert periods(db_engine, follower, m)[(PURCHASE, april)][:2] == (25, 30) and [r["Id"] for r in mine(api, base, m)] == [row]
    assert mine(api, world["free"], m) == []                                                        # izlemeyen senaryo Baz'ın sonraki kayıtlarını okumaz


# ------------------------------------------------------------------ plan dönemi

def test_period_is_closed_at_or_above_the_ratio(api, db_engine, world, mats):  # noqa: F811
    """Oranın altı açık, tam eşiği ve üstü kapalı (%50; Nisan 30 gün: 14 açık, 15 ve 16 kapalı); yalnız blokajlı günü olan dönemler döner."""
    assert [rules.is_closed(n, 30, 50) for n in (14, 15, 16)] == [False, True, True] and rules.is_closed(1, 3, Decimal("33.33")) and not rules.is_closed(1, 3, Decimal("33.34"))
    base, m = world["base"], mats
    april = date(Y, 4, 1)
    row = hold(api, base, m, april, date(Y, 4, 14))
    assert periods(db_engine, base, m) == {(PURCHASE, april): (14, 30, 50.0, False)}
    for last, closed in ((15, True), (16, True), (14, False)):
        edit(api, base, [(row, "EndDate", tr(date(Y, 4, last)))])
        assert periods(db_engine, base, m) == {(PURCHASE, april): (last, 30, 50.0, closed)}
    edit(api, base, [(row, "ClosePct", "46,66")])                                                   # 14 / 30 = %46,67 ≥ %46,66
    assert periods(db_engine, base, m)[(PURCHASE, april)][3] is True
    edit(api, base, [(row, "ClosePct", 100), (row, "EndDate", tr(date(Y, 4, 29)))])
    assert periods(db_engine, base, m)[(PURCHASE, april)] == (29, 30, 100.0, False)                 # %100: ancak dönemin tamamı blokajlıysa
    edit(api, base, [(row, "EndDate", tr(date(Y, 5, 2)))])                                          # Mayıs'a taşar: 2 / 31 gün, açık
    assert periods(db_engine, base, m) == {(PURCHASE, april): (30, 30, 100.0, True), (PURCHASE, date(Y, 5, 1)): (2, 31, 100.0, False)}


def test_overlaps_merge_lowest_ratio_and_separate_supplies(api, db_engine, world, mats):  # noqa: F811
    """Üst üste binen kayıtlar birleşir (gün bir kez sayılır); oranlar farklıysa en düşüğü geçerlidir; Üretim ve Satın alma ayrı hesaplanır ("Üretim ve
    satın alma" ikisine de sayılır)."""
    base, m = world["base"], mats
    april = date(Y, 4, 1)
    hold(api, base, m, april, date(Y, 4, 10), pct=50)
    assert periods(db_engine, base, m)[(PURCHASE, april)] == (10, 30, 50.0, False)
    hold(api, base, m, date(Y, 4, 8), date(Y, 4, 14), pct=80)                                       # 8–10 iki kayıtta: 14 gün
    assert periods(db_engine, base, m)[(PURCHASE, april)] == (14, 30, 50.0, False)
    hold(api, base, m, date(Y, 4, 20), date(Y, 4, 20), pct=40)                                      # ayrık üçüncü kayıt: 15 gün, en düşük oran %40
    assert periods(db_engine, base, m)[(PURCHASE, april)] == (15, 30, 40.0, True)
    # hem üretilen hem satın alınan malzeme: Üretim 1–12 Haziran, Üretim ve satın alma 10–16 Haziran
    june = date(Y, 6, 1)
    hold(api, base, m, june, date(Y, 6, 12), kind=PRODUCTION, material="any", pct=50)
    hold(api, base, m, date(Y, 6, 10), date(Y, 6, 16), kind=BOTH, material="any", pct=20)
    assert periods(db_engine, base, m, "any") == {(PRODUCTION, june): (16, 30, 20.0, True), (PURCHASE, june): (7, 30, 20.0, True)}


def test_open_ended_short_first_period_and_engine(api, db_engine, world, mats):  # noqa: F811
    """Bitişi boş kayıt ufkun sonuna kadar sayılır; haftalık dönemde ve kısa ilk dönemde takvim günü dönemin kendi gün sayısıdır; motor arayüzü aynı
    hesabı verir."""
    base, m = world["base"], mats
    hold(api, base, m, date(Y, 3, 12), None)                                                        # Çarşamba'dan itibaren süresiz
    found = periods(db_engine, base, m)
    starts = sorted(k[1] for k in found)
    assert found[(PURCHASE, date(Y, 3, 10))] == (5, 7, 50.0, True)                                  # haftanın 5 günü: kapalı
    assert all(v[0] == v[1] and v[3] for k, v in found.items() if k[1] > date(Y, 3, 10)) and starts[-1] >= date(Y, 9, 1)   # sonraki bütün dönemler tam kapalı
    hold(api, base, m, date(Y, 1, 8), date(Y, 1, 9), kind=PRODUCTION, material="make")
    midweek = date(Y, 1, 8)                                                                         # plan Çarşamba başlarsa ilk dönem kısa (5 gün)
    short = periods(db_engine, base, m, "make", today=midweek)
    assert short == {(PRODUCTION, midweek): (2, 5, 50.0, False)}
    assert periods(db_engine, base, m, "make") == {(PRODUCTION, T0): (2, 7, 50.0, False)}
    with Session(db_engine) as s:
        version = s.execute(sa.text("SELECT MAX(Id) FROM adm.DataVersion")).scalar()
        engine = [r for r in SqlPlanningData(s, version, base).material_holds(T0) if r["MaterialId"] in (m["buy"], m["make"])]
        assert engine == [r for r in rules.periods(s, base, T0) if r["MaterialId"] in (m["buy"], m["make"])] and len(engine) == len(found) + 1
        assert set(engine[0]) == {"LocationId", "MaterialId", "Supply", "PeriodNo", "PeriodStart", "PeriodEnd", "Days", "BlockedDays", "ClosePct", "Closed"}
        with pytest.raises(ValueError):
            SqlPlanningData(s, version).material_holds(T0)


def test_validity_list_matches_the_engine(api, db_engine, world, mats):  # noqa: F811
    """Geçerlilik listesi (bugünün ufkuyla) motor arayüzüyle aynı sonucu verir: malzeme × tedarik biçimi × dönem; Durum Açık ya da Kapalı."""
    base, m = world["base"], mats
    start = date.today() + timedelta(days=45)
    hold(api, base, m, start, start + timedelta(days=75), kind=BOTH, material="any", pct=50)
    key = f",m{m['any']},"
    listed = [r for r in rows(api, VALIDITY, base, filters=[{"field": "OwnerKeys", "op": "contains", "values": [key]}], sort=[{"field": "PeriodStart", "dir": "asc"}])]
    with Session(db_engine) as s:
        engine = [r for r in rules.periods(s, base, date.today()) if r["MaterialId"] == m["any"]]
    assert len(listed) == len(engine) >= 4
    by = {(r["Supply"], r["PeriodStart"]): r for r in listed}
    for e in engine:
        row = by[(e["Supply"], e["PeriodStart"].isoformat())]
        assert (row["BlockedDays"], row["PeriodDays"], float(row["Threshold"]), row["Status"], row["MaterialCode"], row["LocationCode"]) == (
            e["BlockedDays"], e["Days"], float(e["ClosePct"]), "Kapalı" if e["Closed"] else "Açık", m["any_code"], d.LOCATION_CODE)
        assert abs(float(row["Ratio"]) - e["BlockedDays"] * 100 / e["Days"]) < 0.01 and row["SourceRowId"] is not None
    assert {r["Supply"] for r in listed} == {PRODUCTION, PURCHASE} and len({r["Id"] for r in listed}) == len(listed)
    closed = rows(api, VALIDITY, base, filters=[{"field": "OwnerKeys", "op": "contains", "values": [key]}, {"field": "Status", "op": "in", "values": ["Kapalı"]}])
    assert closed and all(r["Status"] == "Kapalı" for r in closed)


# ------------------------------------------------------------------ veri kalitesi ve yetki

def test_closed_material_is_a_quality_warning(api, db_engine, world, mats):  # noqa: F811
    """`SC.HOLD_ORPHAN`: blokaj girilmiş malzeme aktarımla kapanırsa uyarı çıkar; kayıt durur; kapanan malzemeye yeni blokaj girilemez."""
    base, m = world["base"], mats
    hold(api, base, m, date(Y, 4, 1), None)

    def warnings() -> list[tuple]:
        with Session(db_engine) as s:
            quality_run.run(s, {"Material"})
        with db_engine.connect() as c:
            return [tuple(r) for r in c.execute(sa.text("SELECT CheckCode, RuleName FROM adm.DataQualityWarning WHERE CheckCode = N'SC.HOLD_ORPHAN'"))]

    try:
        assert warnings() == []
        with db_engine.begin() as c:
            c.execute(sa.text("UPDATE core.Material SET VersionTo = VersionFrom WHERE Id = :m AND VersionTo IS NULL"), {"m": m["buy"]})
        assert warnings() == [("SC.HOLD_ORPHAN", "Kapanan malzemeye girilmiş malzeme blokajı")]
        assert hold(api, base, m, date(Y, 5, 1), None, expect=422) == {"MaterialId": "Güncel veride yok."}
        [kept] = mine(api, base, m)
        assert kept["MaterialCode"] == m["buy_code"]                                               # kayıt durur; kod son versiyondan
    finally:
        with db_engine.begin() as c:
            c.execute(sa.text("UPDATE core.Material SET VersionTo = NULL WHERE Id = :m AND VersionTo = VersionFrom"), {"m": m["buy"]})
            c.execute(sa.text("DELETE FROM adm.DataQualityWarning WHERE CheckCode = N'SC.HOLD_ORPHAN'"))


def test_end_user_reads_but_cannot_write(api, world, mats, people):  # noqa: F811
    base, m = world["base"], mats
    row = hold(api, base, m, date(Y, 4, 1), None)
    end = auth(people[END_USER])
    for name in (LIST, VALIDITY):
        assert api.post(f"/api/{name}/query", headers=end, json={"limit": 5, "scenario_id": base}).status_code == 200
    assert api.get(f"{URL}/options", headers=end).status_code == 200
    calls = [api.post(f"{URL}?scenario_id={base}", headers=end, json={"values": {}}),
             api.put(f"{URL}?scenario_id={base}", headers=end, json={"changes": [{"id": row, "field": "ClosePct", "value": 5}]}),
             api.delete(f"{URL}/{row}?scenario_id={base}", headers=end), api.post(f"{URL}/{row}/invalidate?scenario_id={base}", headers=end),
             api.post(f"{URL}/{row}/restore?scenario_id={base}", headers=end)]
    assert [c.status_code for c in calls] == [403] * 5
