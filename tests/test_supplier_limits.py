"""Tedarikçi limiti, 7.12 (K-191; ekran 31 ikinci sekme, fonksiyon 103): iki kayıt türü (üst limit, kapanış), doğrulamalar, çoklu malzemeli kapanış,
tablo içi değişiklik, Baz + fark ve senaryo çakışmasının beş sırası, geçerlilik aralıkları, günlük ortalama, plan dönemine çevirme, malzeme toplamı,
motor arayüzü, veri kalitesi uyarısı ve yetki. Smartchain_test'te; kendi kayıtlarını uzak gelecekte (2031) açar ve sonunda siler, sentetik kayıtlara
dokunmaz. Tarihler sabittir: test haftanın gününe ve bugünün tarihine bağlı değildir.
"""
import json
from datetime import date, timedelta
from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app import supplierlimits as rules
from app.api.permissions import END_USER, KEY_USER
from app.data.synthetic import dataset as d
from app.engine.data import SqlPlanningData
from app.params import resolve, scenario_tables
from app.quality import run as quality_run

from auth_helpers import auth
from test_capacity import clean, world  # noqa: F401  (fixture'lar)
from test_capacity_entries import api, audits, people  # noqa: F401

pytestmark = pytest.mark.db

URL = "/api/model-constraints/supplier-limits"
LIST, VALIDITY = "supplier-limits", "supplier-limits-validity"
UPPER, CLOSURE = rules.UPPER, rules.CLOSURE
Y = 2031                                                   # testin kayıtlarının yılı (sentetik kayıtların ve ufkun dışında)


def tr(day: date) -> str:
    return f"{day:%d.%m.%Y}"


@pytest.fixture
def pairs(db_engine, api, clean):  # noqa: F811
    """Sentetik limitlerde kullanılmayan tedarikçi + malzeme çiftleri: tek tedarikçili iki malzeme (aynı tedarikçi), iki tedarikçili bir malzeme ve başka
    tedarikçinin malzemesi. Test sonunda bu testin açtığı tedarikçi limiti kayıtları ve geçmişleri silinir."""
    with db_engine.connect() as c:
        mark = c.execute(sa.text("SELECT COALESCE(MAX(Id), 0) FROM param.SupplierLimit")).scalar()
        used = {(r.SupplierId, r.MaterialId) for r in c.execute(sa.text("SELECT SupplierId, MaterialId FROM param.SupplierLimit"))}
    suppliers = api.get(f"{URL}/options").json()["suppliers"]
    by_material: dict[int, list[dict]] = {}
    for s in suppliers:
        for m in s["materials"]:
            by_material.setdefault(m["id"], []).append(s)
    free = lambda s, m: (s["supplier_id"], m["id"]) not in used and not any(u[0] == s["supplier_id"] and u[1] is None for u in used)  # noqa: E731
    solo = next(s for s in suppliers if sum(1 for m in s["materials"] if len(by_material[m["id"]]) == 1 and free(s, m)) >= 2)
    m1, m2 = [m for m in solo["materials"] if len(by_material[m["id"]]) == 1 and free(solo, m)][:2]
    shared_id = next(mid for mid, owners in by_material.items() if len(owners) == 2 and all((o["supplier_id"], mid) not in used for o in owners)
                     and all(o["supplier_id"] != solo["supplier_id"] for o in owners))
    theirs = {m["id"] for m in solo["materials"]}
    foreign = next(m["id"] for s in suppliers if s["supplier_id"] != solo["supplier_id"] for m in s["materials"] if m["id"] not in theirs)   # tedarikçinin vermediği malzeme
    out = {"loc": solo["location_id"], "s": solo["supplier_id"], "code": solo["code"], "m1": m1["id"], "m1_code": m1["code"], "m2": m2["id"], "m2_code": m2["code"],
           "shared": shared_id, "shared_suppliers": [o["supplier_id"] for o in by_material[shared_id]], "other_material": foreign,
           "suppliers": suppliers}
    yield out
    with db_engine.begin() as c:
        c.execute(sa.text("DELETE FROM adm.FieldChange WHERE TableName = N'SupplierLimit' AND (TRY_CAST(RecordKey AS bigint) > :m OR RecordKey LIKE N'%@%')"), {"m": mark})
        c.execute(sa.text("DELETE FROM param.SupplierLimit WHERE Id > :m"), {"m": mark})


def rows(api, name: str, scenario: int, **body) -> list[dict]:  # noqa: F811
    r = api.post(f"/api/{name}/query", json={"limit": 100, "scenario_id": scenario, **body})
    assert r.status_code == 200, r.text
    return r.json()["rows"]


def new(api, scenario: int, expect: int = 201, **values):  # noqa: F811
    r = api.post(f"{URL}?scenario_id={scenario}", json={"values": values})
    assert r.status_code == expect, r.text
    return r.json()["ids"] if expect == 201 else {p["field"]: p["problem"] for p in r.json()["error"]["details"]}


def upper(api, scenario: int, p: dict, start: date, qty, period: str = "Ay", material: str = "m1", end: date | None = None, expect: int = 201):  # noqa: F811
    out = new(api, scenario, expect, LimitType=UPPER, LocationId=p["loc"], SupplierId=p["s"], MaterialId=p[material], ValidFrom=tr(start),
              ValidTo=tr(end) if end else None, UpperLimit=qty, LimitPeriod=period)
    return out[0] if expect == 201 else out


def closure(api, scenario: int, p: dict, start: date, end: date, material: str | None = "m1", reason: str | None = None):  # noqa: F811
    return new(api, scenario, LimitType=CLOSURE, LocationId=p["loc"], SupplierId=p["s"], MaterialId=p[material] if material else None, ValidFrom=tr(start), ValidTo=tr(end),
               Reason=reason)[0]


def edit(api, scenario: int, changes: list[tuple], expect: int = 200):  # noqa: F811
    r = api.put(f"{URL}?scenario_id={scenario}", json={"changes": [{"id": i, "field": f, "value": v} for i, f, v in changes]})
    assert r.status_code == expect, r.text
    return r.json() if expect == 200 else r.json()["error"]["details"]


def act(api, scenario: int, row_id: int, action: str | None, expect: int = 200):  # noqa: F811
    r = api.delete(f"{URL}/{row_id}?scenario_id={scenario}") if action is None else api.post(f"{URL}/{row_id}/{action}?scenario_id={scenario}")
    assert r.status_code == expect, r.text


def mine(api, scenario: int, p: dict, material: str = "m1", name: str = LIST) -> list[dict]:  # noqa: F811
    """Listede bu tedarikçi ve malzemenin test yılındaki kayıtları."""
    key = f",s{p['s']}m{p[material]},"
    return [r for r in rows(api, name, scenario, filters=[{"field": "OwnerKeys", "op": "contains", "values": [key]}]) if r["ValidFrom"] >= f"{Y}-01-01"]


def seen(api, scenario: int, p: dict) -> tuple:  # noqa: F811
    found = mine(api, scenario, p)
    assert len(found) == 1, [(r["Id"], r["Origin"]) for r in found]
    return float(found[0]["UpperLimit"]), found[0]["Origin"]


def stored(db_engine, scenario: int, p: dict) -> list[dict]:
    with db_engine.connect() as c:
        return [dict(r) for r in c.execute(sa.text("SELECT * FROM param.SupplierLimit WHERE ScenarioDefinitionId = :s AND SupplierId = :sup AND ValidFrom >= :y ORDER BY Id"),
                                           {"s": scenario, "sup": p["s"], "y": date(Y, 1, 1)}).mappings()]


# ------------------------------------------------------------------ listeler ve seçenekler

def test_lists_options_and_synthetic_records(api, db_engine, world, pairs):  # noqa: F811
    """Seçenekler yalnız aktif ve güncel malzeme tedarikçisi kayıtlarıdır; Kayıtlar listesinde iki tür birlikte, Lokasyon kendi alanı ve kodun solunda;
    İlişkili alanlar; sentetik kayıtlar (docs/11) ve "Kısıtsız kapasite" senaryosundaki fark."""
    with db_engine.connect() as c:
        active = c.execute(sa.text("SELECT COUNT(*) FROM core.MaterialSupplier WHERE VersionTo IS NULL AND COALESCE(IsActive, 1) = 1")).scalar()
        mono = c.execute(sa.text("SELECT Id FROM param.ScenarioDefinition WHERE Name = N'Kısıtsız kapasite' AND IsSynthetic = 1")).scalar_one()
    assert sum(len(s["materials"]) for s in pairs["suppliers"]) == active and all(s["location"] == d.LOCATION_CODE for s in pairs["suppliers"])
    assert api.get(f"{URL}/options").json()["periods"] == ["Gün", "Hafta", "Ay", "Çeyrek", "Yıl"]

    cols = api.get(f"/api/{LIST}/columns").json()
    assert [c["field"] for c in cols["columns"] if c["default_visible"]] == [
        "LimitType", "LocationCode", "SupplierCode", "MaterialCode", "ValidFrom", "ValidTo", "UpperLimit", "LimitPeriod", "Uom", "Reason", "Origin", "IsValid"]
    labels = {c["field"]: c["label"] for c in cols["columns"]}
    assert (labels["LimitType"], labels["LocationCode"], labels["SupplierCode"], labels["MaterialCode"], labels["UpperLimit"], labels["LimitPeriod"]) == (
        "Tür", "Lokasyon", "Tedarikçi", "Malzeme", "Limit", "Limitin dönemi")
    assert [r["label"] for r in cols["relations"]] == ["Tedarikçi", "Malzeme", "Lokasyon"] and cols["scenario_list"] is True

    base = [r for r in rows(api, LIST, world["base"]) if r["ValidFrom"] < f"{Y}-01-01"]
    by = {(r["SupplierCode"], r["MaterialCode"], r["LimitType"], r["ValidFrom"]): r for r in base}
    assert len(base) == 6 and {r["LocationCode"] for r in base} == {d.LOCATION_CODE} and {r["Origin"] for r in base} == {"Baz"}
    limit = next(r for k, r in by.items() if k[:3] == (d.LIMIT_SUPPLIER, d.LIMIT_MATERIAL, UPPER))
    assert (float(limit["UpperLimit"]), limit["LimitPeriod"]) == (float(d.LIMIT_QTY), "Ay")
    steady = sorted((r for k, r in by.items() if k[0] == d.SUPLIM_STEADY[0] and k[2] == UPPER), key=lambda r: r["ValidFrom"])
    assert [float(r["UpperLimit"]) for r in steady] == [float(d.SUPLIM_STEADY[1]), float(d.SUPLIM_STEADY[2])] and steady[0]["ValidTo"] is None
    general = next(r for k, r in by.items() if k[0] == d.SUPLIM_HOLIDAY)
    assert (general["LimitType"], general["MaterialCode"], general["UpperLimit"], general["Reason"]) == (CLOSURE, "Tümü", None, "Yıl sonu tatili")
    assert any(k[0] == d.SUPLIM_STEADY[0] and k[2] == CLOSURE and r["MaterialCode"] != "Tümü" for k, r in by.items())       # malzemeye özel kapanış
    weekly = next(r for r in rows(api, LIST, mono) if r["SupplierCode"] == d.SUPLIM_WEEKLY[0] and r["LimitType"] == UPPER)
    assert (float(weekly["UpperLimit"]), weekly["Origin"], weekly["OverriddenFields"]) == (float(d.SUPLIM_WEEKLY_DIFF), "Senaryo farkı", ",UpperLimit,")
    assert float(json.loads(weekly["BaseValues"])["UpperLimit"]) == float(d.SUPLIM_WEEKLY[1])
    related = rows(api, LIST, world["base"], fields=["SupplierCode", "SupplierId/Name", "MaterialId/Name", "LocationId/Name"])
    assert all(r["SupplierId/Name"] and r["LocationId/Name"] for r in related)
    assert "SupplierLimit" in {t.name for t in scenario_tables.TABLES if t.kind == scenario_tables.DATA and t.materialize is not None}


# ------------------------------------------------------------------ yeni kayıt ve doğrulama

def test_create_both_kinds_and_validation(api, db_engine, world, pairs, people):  # noqa: F811
    """Üst limit ve kapanış; doğrulamalar alan bazında; kapanışta birden çok malzeme (her biri ayrı kayıt; hepsi ya da hiçbiri); malzemesiz kapanış "Tümü"."""
    base, p = world["base"], pairs
    a = date(Y, 1, 1)
    first = upper(api, base, p, a, "310", "Ay")
    [row] = mine(api, base, p)
    assert (row["Id"], row["LimitType"], row["SupplierCode"], row["MaterialCode"], float(row["UpperLimit"]), row["LimitPeriod"], row["ValidTo"], row["Origin"], row["IsValid"]) == (
        first, UPPER, p["code"], p["m1_code"], 310.0, "Ay", None, "Baz", True)
    # doğrulamalar
    body = dict(LimitType=UPPER, LocationId=p["loc"], SupplierId=p["s"], MaterialId=p["m1"], ValidFrom=tr(date(Y, 2, 1)), UpperLimit=5, LimitPeriod="Ay")
    cases = [
        ({**body, "LimitType": None}, "LimitType", "Tür seçilmeli."),
        ({**body, "SupplierId": None}, "SupplierId", "Tedarikçi seçilmeli."),
        ({**body, "MaterialId": p["other_material"]}, "MaterialId", rules.NO_PAIR),                # tedarikçinin vermediği malzeme
        ({**body, "MaterialId": None}, "MaterialId", "Malzeme seçilmeli."),
        ({**body, "UpperLimit": 0}, "UpperLimit", "Sıfırdan büyük olmalı."),
        ({**body, "UpperLimit": None}, "UpperLimit", "Boş bırakılamaz."),
        ({**body, "LimitPeriod": "Dönem"}, "LimitPeriod", None),
        ({**body, "LimitPeriod": None}, "LimitPeriod", "Boş bırakılamaz."),
        ({**body, "ValidFrom": None}, "ValidFrom", "Boş bırakılamaz."),
        ({**body, "ValidTo": tr(date(Y, 1, 15))}, "ValidTo", "Bitiş başlangıçtan önce olamaz."),
        ({**body, "ValidFrom": tr(a)}, "ValidFrom", "Bu tedarikçi ve malzeme için aynı başlangıç tarihli başka bir üst limit var."),
        ({**body, "Reason": "x" * 256}, "Reason", "En çok 255 karakter."),                           # Sebep üst limitte de var (isteğe bağlı)
        (dict(LimitType=CLOSURE, LocationId=p["loc"], SupplierId=p["s"], ValidFrom=tr(a)), "ValidTo", "Boş bırakılamaz."),      # kapanışta bitiş zorunlu
        (dict(LimitType=CLOSURE, LocationId=p["loc"], SupplierId=p["s"], ValidFrom=tr(a), ValidTo=tr(a), UpperLimit=5), "UpperLimit", "Bilinmeyen alan."),
        ({**body, "MaterialIds": [p["m1"], p["m2"]]}, "MaterialId", "Birden çok malzeme yalnız kapanışta seçilir."),
    ]
    for values, field, problem in cases:
        got = new(api, base, 422, **values)
        assert field in got and (problem is None or got[field] == problem), (values, got)
    assert len(mine(api, base, p)) == 1                                                            # hiçbiri kaydedilmedi
    noted = new(api, base, **{**body, "ValidFrom": tr(date(Y, 6, 1)), "Reason": "Sözleşme"})[0]         # üst limitte isteğe bağlı sebep
    assert next(r for r in mine(api, base, p) if r["Id"] == noted)["Reason"] == "Sözleşme"
    api.delete(f"{URL}/{noted}?scenario_id={base}")
    # kapanış: iki malzeme → iki kayıt; aynı tarihlerle yeniden girilebilir (kapanışlar birleşir); malzemesiz → Tümü
    ids = new(api, base, LimitType=CLOSURE, LocationId=p["loc"], SupplierId=p["s"], MaterialIds=[p["m1"], p["m2"]], ValidFrom=tr(date(Y, 1, 10)), ValidTo=tr(date(Y, 1, 12)),
              Reason="Bakım")
    assert len(ids) == 2
    closed = {r["MaterialCode"]: r for r in rows(api, LIST, base) if r["Id"] in ids}
    assert set(closed) == {p["m1_code"], p["m2_code"]} and all((r["LimitType"], r["UpperLimit"], r["LimitPeriod"], r["Reason"]) == (CLOSURE, None, None, "Bakım") for r in closed.values())
    bad = new(api, base, 422, LimitType=CLOSURE, LocationId=p["loc"], SupplierId=p["s"], MaterialIds=[p["m2"], p["other_material"]], ValidFrom=tr(date(Y, 2, 1)), ValidTo=tr(date(Y, 2, 2)))
    assert bad == {"MaterialId": rules.NO_PAIR} and len(stored(db_engine, base, p)) == 3           # hepsi ya da hiçbiri
    general = closure(api, base, p, date(Y, 1, 12), date(Y, 1, 14), material=None, reason="Tatil")
    row = next(r for r in rows(api, LIST, base) if r["Id"] == general)
    assert (row["MaterialCode"], row["MaterialId"], row["Reason"]) == ("Tümü", None, "Tatil")
    made = audits(db_engine, people[KEY_USER], "Tedarikçi limiti eklendi")
    assert {a_["ObjectType"] for a_ in made} == {"Tedarikçi üst limiti", "Tedarikçi kapanışı"} and f"{p['code']} · Tümü · 12.01.{Y}" in {a_["ObjectKey"] for a_ in made}


def test_cells_change_by_kind_and_leave_history(api, db_engine, world, pairs, people):  # noqa: F811
    """Tablo içi değişiklik: türe uyan alanlar değişir; türe uymayan alan ve tür, tedarikçi, malzeme düzenlenemez; iki türün değişiklikleri tek istekte,
    hepsi ya da hiçbiri; Geçmiş ve denetim izi."""
    base, p = world["base"], pairs
    lim = upper(api, base, p, date(Y, 1, 1), 310)
    clo = closure(api, base, p, date(Y, 1, 10), date(Y, 1, 12))
    assert edit(api, base, [(lim, "UpperLimit", "620,5"), (lim, "LimitPeriod", "Hafta"), (lim, "ValidTo", tr(date(Y, 6, 30))), (lim, "Reason", "Sözleşme"),
                            (clo, "Reason", "Sayım"), (clo, "ValidTo", tr(date(Y, 1, 15)))])["saved"] == 6              # Sebep iki türde de düzenlenir
    got = {r["Id"]: r for r in rows(api, LIST, base) if r["Id"] in (lim, clo)}
    assert (float(got[lim]["UpperLimit"]), got[lim]["LimitPeriod"], got[lim]["ValidTo"], got[lim]["Reason"]) == (620.5, "Hafta", f"{Y}-06-30", "Sözleşme")
    assert (got[clo]["Reason"], got[clo]["ValidTo"]) == ("Sayım", f"{Y}-01-15")
    problems = edit(api, base, [(clo, "LimitPeriod", "Ay"), (clo, "UpperLimit", 5), (lim, "LimitType", CLOSURE), (lim, "UpperLimit", -1), (clo, "ValidTo", tr(date(Y, 1, 20)))], expect=422)
    assert {(x["id"], x["field"]): x["problem"] for x in problems} == {
        (clo, "LimitPeriod"): "Bu alan düzenlenemez.", (clo, "UpperLimit"): "Bu alan düzenlenemez.",
        (lim, "LimitType"): "Tür, tedarikçi ve malzeme kayıttan sonra değişmez; kaydı silip yeniden girin.", (lim, "UpperLimit"): "Sıfırdan büyük olmalı."}
    assert next(r for r in rows(api, LIST, base) if r["Id"] == clo)["ValidTo"] == f"{Y}-01-15"       # geçerli değişiklik de kaydedilmedi
    history = api.post("/api/record-history/query", json={"limit": 100, "sort": [{"field": "At", "dir": "asc"}], "filters": [
        {"field": "TableName", "op": "in", "values": ["SupplierLimit"]}, {"field": "RecordKey", "op": "in", "values": [str(lim)]}]}).json()["rows"]
    assert [(h["FieldLabel"], h["OldValue"], h["NewValue"]) for h in history if h["NewValue"] != "Kayıt oluştu"] == [
        ("Limit", "310", "620,5"), ("Limitin dönemi", "Ay", "Hafta"), ("Bitiş", None, f"30.06.{Y}"), ("Sebep", None, "Sözleşme")]
    assert {h["SourceText"] for h in history} == {"Model kısıtları · Kapasite Planlamacı"}
    act(api, base, clo, None)
    assert [r["Id"] for r in stored(db_engine, base, p)] == [lim]


# ------------------------------------------------------------------ Baz + fark: beş sıra (K-191 madde 10)

def test_a_base_first_then_scenario(api, db_engine, world, pairs):  # noqa: F811
    """(a) Önce Baz, sonra senaryo: senaryodaki değişiklik fark satırıdır; tek kayıt; Baz değişmez; senaryoda aynı başlangıçla ikinci kayıt açılamaz."""
    base, follower, p = world["base"], world["follower"], pairs
    row = upper(api, base, p, date(Y, 1, 1), 310)
    assert seen(api, follower, p) == (310.0, "Baz")
    edit(api, follower, [(row, "UpperLimit", 500)])
    assert seen(api, follower, p) == (500.0, "Senaryo farkı") and seen(api, base, p) == (310.0, "Baz")
    [diff] = stored(db_engine, follower, p)
    assert (diff["BaseRowId"], diff["OverriddenFields"], diff["LimitType"], diff["MaterialId"]) == (row, ",UpperLimit,", UPPER, p["m1"])
    assert upper(api, follower, p, date(Y, 1, 1), 5, expect=422) == {"ValidFrom": "Bu tedarikçi ve malzeme için aynı başlangıç tarihli başka bir üst limit var."}
    act(api, follower, row, "invalidate")                                                          # Baz satırı senaryoda geçersiz yapılır
    assert mine(api, follower, p)[0]["IsValid"] is False and mine(api, base, p)[0]["IsValid"] is True


def test_b_scenario_first_then_base(api, db_engine, world, pairs):  # noqa: F811
    """(b) Önce senaryo (Baz'da kayıt yokken), sonra Baz: senaryoda tek kayıt; senaryonun değeri geçerli, "Kaynağı" Senaryo farkı, Baz değeri saklı;
    Geçerlilik ve günlük hesap senaryonun değerini kullanır; sonraki değişiklik senaryonun kaydına yazılır."""
    base, follower, p = world["base"], world["follower"], pairs
    own = upper(api, follower, p, date(Y, 1, 1), 500)
    assert seen(api, follower, p) == (500.0, "Senaryo") and mine(api, base, p) == []
    upper(api, base, p, date(Y, 1, 1), 310)
    [row] = mine(api, follower, p)
    assert (float(row["UpperLimit"]), row["Origin"], row["Id"], row["StoredId"]) == (500.0, "Senaryo farkı", own, own)
    assert float(json.loads(row["BaseValues"])["UpperLimit"]) == 310.0 and ",UpperLimit," in row["OverriddenFields"]
    assert seen(api, base, p) == (310.0, "Baz")
    applied = {s: [float(r["UpperLimit"]) for r in mine(api, s, p, name=VALIDITY)] for s in (base, follower)}
    assert applied == {base: [310.0], follower: [500.0]}
    edit(api, follower, [(own, "UpperLimit", 700)])
    assert seen(api, follower, p) == (700.0, "Senaryo farkı") and [r["Id"] for r in stored(db_engine, follower, p)] == [own]
    with Session(db_engine) as s:
        day = rules.daily(s, follower, date(Y, 1, 1), date(Y, 1, 1))
        assert [r["DailyLimit"] for r in day if r["MaterialId"] == p["m1"]] == [Decimal(700) / 31]


def test_c_restore_returns_to_base(api, db_engine, world, pairs):  # noqa: F811
    """(c) "Senaryo farkını kaldır": örten kayıtta senaryonun kaydı silinir, Baz'ınki görünür; farkta fark satırı silinir; farkı olmayan satırda 409."""
    base, follower, p = world["base"], world["follower"], pairs
    own = upper(api, follower, p, date(Y, 1, 1), 500)
    theirs = upper(api, base, p, date(Y, 1, 1), 310)
    act(api, follower, own, "restore")
    assert seen(api, follower, p) == (310.0, "Baz") and stored(db_engine, follower, p) == []
    act(api, follower, theirs, "restore", expect=409)
    edit(api, follower, [(theirs, "UpperLimit", 500)])
    act(api, follower, theirs, "restore")
    assert seen(api, follower, p) == (310.0, "Baz") and stored(db_engine, follower, p) == []


def test_d_deleting_in_base(api, db_engine, world, pairs):  # noqa: F811
    """(d) Baz'da silme: örtülen Baz kaydı silinince senaryonun kaydı kendi kaydı olarak kalır ("Kaynağı" Senaryo)."""
    base, follower, p = world["base"], world["follower"], pairs
    own = upper(api, follower, p, date(Y, 1, 1), 500)
    theirs = upper(api, base, p, date(Y, 1, 1), 310)
    assert seen(api, follower, p) == (500.0, "Senaryo farkı")
    act(api, base, theirs, None)
    assert seen(api, follower, p) == (500.0, "Senaryo") and mine(api, base, p) == [] and [r["Id"] for r in stored(db_engine, follower, p)] == [own]


def test_e_scenario_not_following_base(api, db_engine, world, pairs):  # noqa: F811
    """(e) Baz'ı izlemeyen senaryo: kendi kaydı Baz'ın aynı anahtarlı kaydından etkilenmez; fark ve "Senaryo farkını kaldır" yok. Kapanışlar çakışmaz:
    izleyen senaryonun ve Baz'ın aynı tarihli kapanışları ayrı kayıtlardır (birleşen tür)."""
    base, follower, free, p = world["base"], world["follower"], world["free"], pairs
    own = upper(api, free, p, date(Y, 1, 1), 500)
    upper(api, base, p, date(Y, 1, 1), 310)
    assert seen(api, free, p) == (500.0, "Senaryo") and seen(api, base, p) == (310.0, "Baz")
    act(api, free, own, "restore", expect=409)
    mine_ = closure(api, follower, p, date(Y, 2, 1), date(Y, 2, 5), material="m2")
    theirs = closure(api, base, p, date(Y, 2, 1), date(Y, 2, 5), material="m2")
    both = {r["Id"]: r["Origin"] for r in mine(api, follower, p, material="m2")}
    assert both == {mine_: "Senaryo", theirs: "Baz"}


# ------------------------------------------------------------------ geçerlilik, günlük ortalama, plan dönemi

def test_validity_daily_average_and_period_limit(api, db_engine, world, pairs):  # noqa: F811
    """Geçerlilik aralıkları (başlangıcı ileri olan kazanır), kapanışların birleşmesi (malzemeye özel ve genel), günlük ortalama (takvim günü), plan
    dönemine çevirme (kapalı günün katkısı sıfır; limitsiz gün varsa sınırsız; tamamı kapalıysa kapalı) ve motor arayüzü."""
    base, p = world["base"], pairs
    first = upper(api, base, p, date(Y, 1, 1), 310, "Ay")                                           # Ocak: 310 / 31 = 10 / gün
    second = upper(api, base, p, date(Y, 3, 1), 620, "Ay")                                          # Mart'tan itibaren: 620 / 31 = 20 / gün
    closure(api, base, p, date(Y, 1, 10), date(Y, 1, 12), reason="Bakım")                           # malzemeye özel
    closure(api, base, p, date(Y, 1, 12), date(Y, 1, 14), material=None, reason="Tatil")            # genel: malzemeninkiyle birleşir (10–14)
    shown = sorted(((r["Status"], r["ValidFrom"], r["ValidTo"], r["UpperLimit"] and float(r["UpperLimit"]), r["DailyAverage"] and float(r["DailyAverage"]), r["SourceRowId"])
                    for r in mine(api, base, p, name=VALIDITY)), key=lambda x: (x[1], x[0]))
    assert shown == [("Üst limit", f"{Y}-01-01", f"{Y}-02-28", 310.0, 10.0, first), ("Kapalı", f"{Y}-01-10", f"{Y}-01-14", None, None, shown[1][5]),
                     ("Üst limit", f"{Y}-03-01", None, 620.0, 20.0, second)]
    everyone = [r for r in rows(api, VALIDITY, base, filters=[{"field": "OwnerKeys", "op": "contains", "values": [f",s{p['s']},"]}]) if r["ValidFrom"] >= f"{Y}-01-01"]
    assert ("Tümü", "Kapalı", f"{Y}-01-12", f"{Y}-01-14") in {(r["MaterialCode"], r["Status"], r["ValidFrom"], r["ValidTo"]) for r in everyone}   # "Tümü" satırı
    cols = api.get(f"/api/{VALIDITY}/columns").json()
    assert [c["field"] for c in cols["columns"] if c["default_visible"]] == [
        "LocationCode", "SupplierCode", "MaterialCode", "Status", "ValidFrom", "ValidTo", "UpperLimit", "LimitPeriod", "DailyAverage", "Uom"]

    with Session(db_engine) as s:
        days = [r for r in rules.daily(s, base, date(Y, 1, 1), date(Y, 3, 31)) if r["MaterialId"] == p["m1"]]
        by_day = {r["Day"]: r for r in days}
        assert (by_day[date(Y, 1, 9)]["DailyLimit"], by_day[date(Y, 1, 9)]["Closed"]) == (Decimal(10), False)
        assert [by_day[date(Y, 1, n)]["Closed"] for n in (10, 12, 14, 15)] == [True, True, True, False]
        assert by_day[date(Y, 2, 1)]["DailyLimit"] == Decimal(310) / 28 and by_day[date(Y, 3, 1)]["DailyLimit"] == Decimal(20)   # Şubat 28 gün: takvim günü
        limit = lambda a, b: rules.supplier_limit(s, base, p["loc"], p["s"], p["m1"], a, b)  # noqa: E731
        assert limit(date(Y, 1, 1), date(Y, 1, 31)) == {"Limit": Decimal(260), "Closed": False}       # 31 gün − 5 kapalı gün = 26 × 10
        assert limit(date(Y, 1, 5), date(Y, 1, 11))["Limit"] == Decimal(50)                           # kısa dönem: 5 açık gün
        assert limit(date(Y - 1, 12, 25), date(Y, 1, 7)) == {"Limit": None, "Closed": False}          # dönemde limitsiz gün var: sınırsız
        assert limit(date(Y, 1, 10), date(Y, 1, 14)) == {"Limit": Decimal(0), "Closed": True}         # tamamı kapalı
        # limiti olmayan malzeme (m2): genel kapanış kısmen kapsıyorsa açık (sınırsız), tamamını kapsıyorsa kapalı
        other = lambda a, b: rules.supplier_limit(s, base, p["loc"], p["s"], p["m2"], a, b)  # noqa: E731
        assert other(date(Y, 1, 10), date(Y, 1, 20)) == {"Limit": None, "Closed": False} and other(date(Y, 1, 12), date(Y, 1, 14)) == {"Limit": Decimal(0), "Closed": True}
        version = s.execute(sa.text("SELECT MAX(Id) FROM adm.DataVersion")).scalar()
        assert [r for r in SqlPlanningData(s, version, base).supplier_limits(date(Y, 1, 1), date(Y, 3, 31)) if r["MaterialId"] == p["m1"]] == days
        with pytest.raises(ValueError):
            SqlPlanningData(s, version).supplier_limits(date(Y, 1, 1), date(Y, 1, 2))


def test_period_days_and_material_total(api, db_engine, world, pairs):  # noqa: F811
    """Limitin döneminin gün sayısı (Gün, Hafta, Ay, Çeyrek, Yıl; takvim günü) ve malzeme düzeyi: tedarikçi sınırlarının toplamı, biri limitsizse sınırsız."""
    assert [rules.period_days(k, date(2031, 2, 10)) for k in rules.PERIODS] == [1, 7, 28, 90, 365]
    assert (rules.period_days("Ay", date(2032, 2, 1)), rules.period_days("Yıl", date(2032, 6, 1)), rules.period_days("Çeyrek", date(2031, 8, 15))) == (29, 366, 92)
    with db_engine.connect() as c:
        got = c.execute(sa.text("SELECT " + ", ".join(f"{rules.period_days_sql(f'N{chr(39)}{k}{chr(39)}', 'CAST(:d AS date)')}" for k in rules.PERIODS)), {"d": date(2032, 2, 10)}).one()
    assert tuple(got) == tuple(rules.period_days(k, date(2032, 2, 10)) for k in rules.PERIODS) == (1, 7, 29, 91, 366)   # SQL ifadesi aynı sonucu verir

    base, p = world["base"], pairs
    one, two = p["shared_suppliers"]
    a, b = date(Y, 4, 1), date(Y, 4, 30)                                                            # Nisan: 30 gün
    values = dict(LimitType=UPPER, LocationId=p["loc"], MaterialId=p["shared"], ValidFrom=tr(a), LimitPeriod="Ay")
    new(api, base, **values, SupplierId=one, UpperLimit=300)
    with Session(db_engine) as s:
        total = rules.material_limit(s, base, p["loc"], p["shared"], a, b)
        assert total["Limit"] is None and total["Suppliers"][one]["Limit"] == Decimal(300) and total["Suppliers"][two]["Limit"] is None   # öteki limitsiz: sınırsız
    new(api, base, **values, SupplierId=two, UpperLimit=150)
    new(api, base, LimitType=CLOSURE, LocationId=p["loc"], SupplierId=two, MaterialId=p["shared"], ValidFrom=tr(date(Y, 4, 1)), ValidTo=tr(date(Y, 4, 10)))
    with Session(db_engine) as s:
        total = rules.material_limit(s, base, p["loc"], p["shared"], a, b)
        assert total["Limit"] == Decimal(300) + Decimal(100)                                        # ikinci tedarikçi 10 gün kapalı: 20 × 5
        assert rules.material_limit(s, base, p["loc"], p["shared"], date(Y, 4, 1), date(Y, 4, 10))["Limit"] == Decimal(100)   # kapalı tedarikçi toplamda sıfır
    with db_engine.begin() as c:                                                                    # bu testin öteki tedarikçideki kayıtları
        c.execute(sa.text("DELETE FROM param.SupplierLimit WHERE MaterialId = :m AND ValidFrom >= :y"), {"m": p["shared"], "y": date(Y, 1, 1)})


# ------------------------------------------------------------------ veri kalitesi ve yetki

def test_closed_or_passive_pair_is_a_quality_warning(api, db_engine, world, pairs):  # noqa: F811
    """`SC.SUPLIM_ORPHAN` ve `SC.SUPLIM_PASSIVE`: limit girilmiş malzeme tedarikçisi kaydı aktarımla kapanır ya da pasifleşirse uyarı çıkar; kayıt durur."""
    base, p = world["base"], pairs
    upper(api, base, p, date(Y, 1, 1), 310)

    def warnings() -> list[tuple]:
        with Session(db_engine) as s:
            quality_run.run(s, {"MaterialSupplier"})
        with db_engine.connect() as c:
            return [tuple(r) for r in c.execute(sa.text("SELECT CheckCode, RuleName FROM adm.DataQualityWarning WHERE CheckCode LIKE N'SC.SUPLIM%'"))]

    pair = {"s": p["s"], "m": p["m1"]}
    try:
        assert warnings() == []
        with db_engine.begin() as c:
            c.execute(sa.text("UPDATE core.MaterialSupplier SET IsActive = 0 WHERE SupplierId = :s AND MaterialId = :m AND VersionTo IS NULL"), pair)
        assert warnings() == [("SC.SUPLIM_PASSIVE", "Pasif malzeme tedarikçisine girilmiş tedarikçi limiti")]
        assert upper(api, base, p, date(Y, 5, 1), 5, expect=422) == {"MaterialId": rules.NO_PAIR}       # pasif kayda yeni limit girilemez
        with db_engine.begin() as c:
            c.execute(sa.text("UPDATE core.MaterialSupplier SET IsActive = 1, VersionTo = VersionFrom WHERE SupplierId = :s AND MaterialId = :m AND VersionTo IS NULL"), pair)
        assert warnings() == [("SC.SUPLIM_ORPHAN", "Kapanan malzeme tedarikçisine girilmiş tedarikçi limiti")]
        assert len(mine(api, base, p)) == 1                                                        # kayıt durur
    finally:
        with db_engine.begin() as c:
            c.execute(sa.text("UPDATE core.MaterialSupplier SET IsActive = 1, VersionTo = NULL WHERE SupplierId = :s AND MaterialId = :m AND VersionTo = VersionFrom"), pair)
            c.execute(sa.text("DELETE FROM adm.DataQualityWarning WHERE CheckCode LIKE N'SC.SUPLIM%'"))


def test_end_user_reads_but_cannot_write(api, world, pairs, people):  # noqa: F811
    base, p = world["base"], pairs
    row = upper(api, base, p, date(Y, 1, 1), 310)
    end = auth(people[END_USER])
    for name in (LIST, VALIDITY):
        assert api.post(f"/api/{name}/query", headers=end, json={"limit": 5, "scenario_id": base}).status_code == 200
    assert api.get(f"{URL}/options", headers=end).status_code == 200
    calls = [api.post(f"{URL}?scenario_id={base}", headers=end, json={"values": {}}),
             api.put(f"{URL}?scenario_id={base}", headers=end, json={"changes": [{"id": row, "field": "UpperLimit", "value": 5}]}),
             api.delete(f"{URL}/{row}?scenario_id={base}", headers=end), api.post(f"{URL}/{row}/invalidate?scenario_id={base}", headers=end),
             api.post(f"{URL}/{row}/restore?scenario_id={base}", headers=end)]
    assert [c.status_code for c in calls] == [403] * 5


def test_registry_and_resolution():
    """Tablo çözümlemede ve kayıt defterinde; çakışma anahtarı yalnız üst limit için (kapanışlar birleşir)."""
    assert resolve.KEYS["SupplierLimit"] == (("LocationId", "SupplierId", "MaterialId", "ValidFrom"), "{a}.LimitType = N'Üst limit'")
    assert set(resolve.FIELDS["SupplierLimit"]) >= {"LimitType", "LocationId", "SupplierId", "MaterialId", "UpperLimit", "LimitPeriod", "Reason"}
    assert rules.UPPER_KIND.unique_start and not rules.CLOSURE_KIND.unique_start and rules.CLOSURE_KIND.end_required
