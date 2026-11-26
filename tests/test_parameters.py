"""Parametreler (K-175; fonksiyon 22, 23; ekran 06): katalog ve docs, dönem hesabı (iki yazım, kısa hafta, yarım ay), Baz senaryo, okuma ve kısmi
kayıt, doğrulama, denetim izi, hedefler, dönem dizisi ve önizleme, raporlama ekseni, yetkiler, veri kalitesi ufku ve motor yükleyicisi.

Veritabanı testleri Baz'ın parametrelerini, hedeflerini ve dönem dizisini test sonunda eski hâline döndürür.
"""
import re
from datetime import date
from pathlib import Path

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.main import create_app
from app.api.permissions import END_USER, KEY_USER, SYSTEM_OWNER
from app.api.services import parameters as api_service
from app.engine import loader
from app.params import catalog as cat, horizon, objectives as objective_rows, service as params
from app.quality import chain

from auth_helpers import auth, ensure_user

ROOT = Path(__file__).resolve().parents[1]
MON = date(2026, 11, 16)  # Pazartesi


# ------------------------------------------------------------------ katalog

def test_catalog_matches_docs():
    """docs/06 fonksiyon 22'deki parametre tablosu katalogla aynı: anahtar, başlık, ad, değerler, başlangıç."""
    text = (ROOT / "docs" / "06-fonksiyonlar.md").read_text(encoding="utf-8")
    rows = {}
    for line in text.splitlines():
        m = re.match(r"^\| `(\w+)` \| (.+?) \| (.+?) \| (.+?) \| (.*?) \|$", line)
        if m and m.group(1) in cat.BY_KEY:
            rows[m.group(1)] = tuple(x.strip() for x in m.groups()[1:])
    assert set(rows) == set(cat.BY_KEY)
    where = {p.key: f"{s.title} › {sub.title}" if len(s.subs) > 1 else s.title for s in cat.SECTIONS for sub in s.subs for p in sub.params}
    shown = {cat.YES: "Evet", cat.NO: "Hayır", None: "boş"}
    for p in cat.PARAMS:
        values = "Evet · Hayır" if p.kind == cat.BOOL else " · ".join(p.options) if p.kind == cat.CHOICE else ("tam sayı" if p.kind == cat.INT else "sayı")
        default = shown.get(p.default, p.default) if p.kind == cat.BOOL or p.default is None else p.default
        assert rows[p.key] == (where[p.key], p.label, values, default), p.key


def test_catalog_defaults_are_valid():
    for p in cat.PARAMS:
        if p.default is not None:
            assert params.normalize(p, p.default) == (p.default, None), p.key
    assert [o.code for o in cat.OBJECTIVES if o.seconds is None] == ["OVER_TARGET_LOAD", "PLAN_DEVIATION"]


# ------------------------------------------------------------------ dönem hesabı

def spans(parts):
    return [(p.start, p.end, len(p.buckets)) for p in parts]


def test_weeks_spanning_months_then_months():
    """Hafta · 3 · Ay + Ay · 6 · Ay: içinde bulunulan ay + 2 ay haftalık (ay sonunda biter), sonra 6 ay aylık."""
    parts = horizon.parts(MON, [("Hafta", 3, "Ay"), ("Ay", 6, "Ay")])
    assert spans(parts) == [(MON, date(2027, 1, 31), 11), (date(2027, 2, 1), date(2027, 7, 31), 6)]
    assert all(b.start.weekday() == 0 for b in parts[0].buckets)             # haftalar Pazartesi başlar
    assert [b.end for b in parts[1].buckets][:2] == [date(2027, 2, 28), date(2027, 3, 31)]


def test_weeks_spanning_weeks_then_half_month():
    """Hafta · 12 · Hafta + Ay · 6 · Ay: 12 hafta; aylık parça ay ortasında başlar, ilk dönem yarım aydır ve sayıya dahildir."""
    parts = horizon.parts(MON, [("Hafta", 12, "Hafta"), ("Ay", 6, "Ay")])
    assert spans(parts) == [(MON, date(2027, 2, 7), 12), (date(2027, 2, 8), date(2027, 7, 31), 6)]
    first = parts[1].buckets[0]
    assert (first.start, first.end) == (date(2027, 2, 8), date(2027, 2, 28))


def test_days():
    parts = horizon.parts(MON, [("Gün", 14, "Gün")])
    assert spans(parts) == [(MON, date(2026, 11, 29), 14)]


def test_short_weeks_at_both_ends():
    """Hafta ortasında başlayan parçanın ilk haftası, ay sonunda biten parçanın son haftası kısa kalır."""
    wed = date(2026, 11, 18)
    parts = horizon.parts(wed, [("Hafta", 1, "Ay")])
    weeks = [(b.start, b.end) for b in parts[0].buckets]
    assert weeks[0] == (wed, date(2026, 11, 22)) and weeks[-1] == (date(2026, 11, 30), date(2026, 11, 30)) and len(weeks) == 3
    # içinde bulunulan hafta sayıya dahil: Çarşamba'dan 2 hafta, ikinci haftanın sonunda biter
    assert spans(horizon.parts(wed, [("Hafta", 2, "Hafta")])) == [(wed, date(2026, 11, 29), 2)]


def test_week_start_and_year_end():
    sunday = horizon.week_start_index("Pazar")
    parts = horizon.parts(MON, [("Hafta", 2, "Hafta")], sunday)
    assert spans(parts) == [(MON, date(2026, 11, 28), 2)] and parts[0].buckets[1].start.weekday() == 6
    months = horizon.parts(MON, [("Ay", 3, "Ay")])
    assert [(b.start, b.end) for b in months[0].buckets] == [(MON, date(2026, 11, 30)), (date(2026, 12, 1), date(2026, 12, 31)),
                                                             (date(2027, 1, 1), date(2027, 1, 31))]
    quarters = horizon.parts(MON, [("Çeyrek", 5, "Ay"), ("Yıl", 12, "Ay")])
    assert [(b.start, b.end) for b in quarters[0].buckets] == [(MON, date(2026, 12, 31)), (date(2027, 1, 1), date(2027, 3, 31))]
    assert [(b.start, b.end) for b in quarters[1].buckets] == [(date(2027, 4, 1), date(2027, 12, 31)), (date(2028, 1, 1), date(2028, 3, 31))]


@pytest.mark.parametrize("rows, field", [
    ([("Hafta", 3, "Gün")], "rows.1.SpanUnit"),                     # kapsam birimi dönem tipinden küçük
    ([("Ay", 1, "Hafta")], "rows.1.SpanUnit"),
    ([("Ay", 2, "Ay"), ("Hafta", 4, "Hafta")], "rows.2.BucketType"),  # kabadan inceye dönmez
    ([("Gün", 0, "Gün")], "rows.1.Count"),
    ([("Çeyrek", 4, "Hafta")], "rows.1.SpanUnit"),                   # çeyrek ve yıl dönem tipinde kapsam birimi Ay, Çeyrek ya da Yıl
    ([("Hafta", 2, "Dönem")], "rows.1.SpanUnit"),                    # bilinmeyen kapsam birimi
    ([("Yıl", 1, "Ay"), ("Çeyrek", 4, "Ay")], "rows.2.BucketType"),
    ([("Saat", 4, "Gün")], "rows.1.BucketType"),                     # bilinmeyen dönem tipi
    ([], "rows"),
])
def test_bucket_problems(rows, field):
    assert [p["field"] for p in horizon.problems(rows, cat.PLAN_BUCKETS)] == [field]


def test_span_in_quarters_and_years():
    """Kapsam birimi Çeyrek ya da Yıl: içinde bulunulan çeyrek ya da yıl sayıya dahil, parça çeyrek ya da yıl sonunda biter."""
    two_quarters = horizon.parts(MON, [("Ay", 2, "Çeyrek")])      # 2026 4. çeyrek + 2027 1. çeyrek, aylık
    assert spans(two_quarters) == [(MON, date(2027, 3, 31), 5)]
    assert [(b.start, b.end) for b in two_quarters[0].buckets][:2] == [(MON, date(2026, 11, 30)), (date(2026, 12, 1), date(2026, 12, 31))]
    year = horizon.parts(MON, [("Çeyrek", 1, "Yıl")])             # yıl sonuna kadar çeyreklik: tek (kısa) çeyrek
    assert spans(year) == [(MON, date(2026, 12, 31), 1)]
    mixed = horizon.parts(MON, [("Hafta", 1, "Çeyrek"), ("Çeyrek", 2, "Yıl"), ("Yıl", 2, "Yıl")])
    assert spans(mixed) == [(MON, date(2026, 12, 31), 7), (date(2027, 1, 1), date(2028, 12, 31), 8), (date(2029, 1, 1), date(2030, 12, 31), 2)]
    assert mixed[0].buckets[-1].end == date(2026, 12, 31) and (mixed[0].buckets[-1].end - mixed[0].buckets[-1].start).days + 1 == 4   # yıl sonunda kısa hafta
    assert horizon.problems([("Hafta", 1, "Çeyrek"), ("Ay", 2, "Çeyrek"), ("Çeyrek", 1, "Yıl"), ("Yıl", 2, "Yıl")], cat.PLAN_BUCKETS) == []
    assert horizon.problems([("Çeyrek", 4, "Ay"), ("Yıl", 12, "Ay"), ("Yıl", 4, "Çeyrek")], cat.PLAN_BUCKETS) == []     # ay ve çeyrek yılı tam böler


def test_both_axes_accept_quarter_and_year():
    assert cat.SPAN_UNITS == ("Gün", "Hafta", "Ay", "Çeyrek", "Yıl") and cat.FIX_UNITS == ("Gün", "Hafta", "Ay")
    assert cat.PLAN_BUCKETS == cat.REPORT_BUCKETS == ("Gün", "Hafta", "Ay", "Çeyrek", "Yıl")
    assert horizon.problems([("Ay", 6, "Ay"), ("Çeyrek", 6, "Ay"), ("Yıl", 24, "Ay")], cat.PLAN_BUCKETS) == []
    assert horizon.problems([("Gün", 14, "Gün"), ("Hafta", 12, "Hafta"), ("Ay", 6, "Ay")], cat.PLAN_BUCKETS) == []


# ------------------------------------------------------------------ veritabanı

TABLES = ("PlanningSetting", "ObjectiveDefinition", "TimeBucketDefinition")


@pytest.fixture(scope="module")
def people(db_engine):
    with db_engine.begin() as c:
        return {SYSTEM_OWNER: ensure_user(c, "pytest.prm.owner", SYSTEM_OWNER), KEY_USER: ensure_user(c, "pytest.prm.key", KEY_USER),
                END_USER: ensure_user(c, "pytest.prm.end", END_USER)}


@pytest.fixture
def base(db_engine, monkeypatch):
    """Baz senaryonun kimliği; test sonunda parametreleri, hedefleri ve dönem dizisi eski hâline döner. Bugün sabit (16.11.2026)."""
    monkeypatch.setattr(api_service, "today", lambda: MON)
    with db_engine.connect() as c:
        sid = c.execute(sa.text("SELECT Id FROM param.ScenarioDefinition WHERE IsBase = 1")).scalar_one()
        saved = {t: [dict(r) for r in c.execute(sa.text(f"SELECT * FROM param.[{t}] WHERE ScenarioDefinitionId = :s"), {"s": sid}).mappings()] for t in TABLES}
    with db_engine.begin() as c:   # hedefler başlangıç düzeninde (K-196): test veritabanının geçmişinden bağımsız
        objective_rows.insert_start(c, sid, params.read_settings(c, sid))
    yield sid
    from db.models import metadata
    with db_engine.begin() as c:
        for t in TABLES:
            table = metadata.tables[f"param.{t}"]
            c.execute(sa.delete(table).where(table.c.ScenarioDefinitionId == sid))
            rows = [{k: v for k, v in r.items() if k != "Id"} for r in saved[t]]
            if rows:
                c.execute(sa.insert(table), rows)


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.mark.db
def test_base_scenario_comes_with_start_values(db_engine, base, client, people):
    with db_engine.connect() as c:
        row = c.execute(sa.text("SELECT Name, IsBase, IsActive, IsSynthetic FROM param.ScenarioDefinition WHERE Id = :s"), {"s": base}).one()
        assert (row.Name, bool(row.IsBase), bool(row.IsActive), bool(row.IsSynthetic)) == ("Baz", True, True, False)
        assert c.execute(sa.text("SELECT COUNT(*) FROM param.ScenarioDefinition WHERE IsBase = 1")).scalar() == 1
        assert not c.execute(sa.text("SELECT COUNT(*) FROM adm.FieldDefinition WHERE TableName = N'ParameterSet' OR FieldName = N'ParameterSetId'")).scalar()
    key = auth(people[KEY_USER])
    body = client.get("/api/parameters", headers=key).json()
    assert body["scenario"] == {"id": base, "name": "Baz"}
    assert [s["title"] for s in body["sections"]] == ["Model", "Hedefler", "Pegging", "Talep", "Malzeme", "Kapasite", "Planlama ufku", "Plan kararlılığı", "Uyarı eşikleri"]
    labels = {p["key"]: p["label"] for s in body["sections"] for sub in s["subs"] for p in sub["params"]}
    assert labels["FixPeriod"] == "Sabit dönem"
    assert [labels[k] for k in ("IncludeFirmOrders", "IncludeQuotes", "IncludeOnHold", "IncludeForecast")] == ["Kesin sipariş", "Teklif", "Beklemedeki sipariş", "Tahmin"]
    assert [labels[k] for k in ("UseOvertime", "UseSubcontracting", "LaborConstraint")] == ["Ek mesai", "Fason", "İşçi kısıtı"]   # K-196: "Ek mesai"
    assert (labels["MaxLatenessDays"], labels["KeepLockedRecords"]) == ("En fazla gecikebilecek gün", "Sabitlenmiş kararlar korunsun")
    assert (body["values"]["SafetyStockMode"], body["values"]["OpenWorkOrders"]) == ("Esnek hedef", "Yalnız öteleme önerisi")
    fix = next(p for s in body["sections"] for sub in s["subs"] for p in sub["params"] if p["key"] == "FixPeriod")
    assert fix["unit_key"] == "FixPeriodUnit" and body["computed"] == {"fix_period_end": None}
    assert [sub["title"] for sub in body["sections"][4]["subs"]] == ["Kısıt ve stok", "Güvenlik stoğu", "Tedarik"]
    assert body["values"] == {p.key: p.default for p in cat.PARAMS}
    lot = next(p for s in body["sections"] for sub in s["subs"] for p in sub["params"] if p["key"] == "ProductionMinLot")
    assert lot["enabled_when"] == {"key": "ModelType", "value": "MILP"}
    assert client.get("/api/scenarios/current", headers=auth(people[END_USER])).json() == {"id": base, "name": "Baz", "is_base": True, "is_active": True}


@pytest.mark.db
def test_partial_save_validation_and_audit(db_engine, base, client, people):
    key = auth(people[KEY_USER])
    r = client.put("/api/parameters", headers=key, json={"changes": {"ModelType": "MILP", "ProductionMinLot": True, "SafetyStockMode": "Esnek hedef",
                                                                     "MaxLatenessDays": 5, "OptimalityGapPct": "0,5"}})
    assert r.status_code == 200, r.text
    values = r.json()["values"]
    assert (values["ModelType"], values["ProductionMinLot"], values["MaxLatenessDays"], values["OptimalityGapPct"]) == ("MILP", "1", "5", "0.5")
    with db_engine.connect() as c:
        log = c.execute(sa.text("SELECT ObjectKey, OldValue, NewValue FROM adm.AuditLog WHERE Action = N'Parametre değişikliği' AND UserId = :u ORDER BY Id DESC"),
                        {"u": people[KEY_USER]}).all()[:4]
    # yalnız değişenler yazılır ve izlenir (SafetyStockMode aynı kaldı)
    assert {k: (o, n) for k, o, n in log} == {
        "Baz · ModelType": ('{"Value": "LP"}', '{"Value": "MILP"}'), "Baz · ProductionMinLot": ('{"Value": "0"}', '{"Value": "1"}'),
        "Baz · MaxLatenessDays": ('{"Value": null}', '{"Value": "5"}'), "Baz · OptimalityGapPct": ('{"Value": "1"}', '{"Value": "0.5"}')}
    # boş bırakılabilen sayı boşaltılır
    assert client.put("/api/parameters", headers=key, json={"changes": {"MaxLatenessDays": None}}).json()["values"]["MaxLatenessDays"] is None
    # geçersiz değerde hiçbiri yazılmaz
    bad = client.put("/api/parameters", headers=key, json={"changes": {"ModelType": "LP", "OptimalityGapPct": -1, "WeekStart": "Pzt", "FixPeriod": 1.5,
                                                                       "Bilinmeyen": 1, "UseOvertime": "belki", "PlanStart": None}})
    assert bad.status_code == 422
    assert {d["field"]: d["problem"] for d in bad.json()["error"]["details"]} == {
        "OptimalityGapPct": "En az 0.", "WeekStart": "Listedeki değerlerden biri girilmeli.", "FixPeriod": "Tam sayı girilmeli.",
        "Bilinmeyen": "Bilinmeyen parametre.", "UseOvertime": "Evet ya da Hayır girilmeli.", "PlanStart": "Boş bırakılamaz."}
    assert client.get("/api/parameters", headers=key).json()["values"]["ModelType"] == "MILP"


@pytest.mark.db
def test_permissions(base, client, people):
    end, key, owner = auth(people[END_USER]), auth(people[KEY_USER]), auth(people[SYSTEM_OWNER])
    for url in ("/api/parameters", "/api/parameters/objectives", "/api/parameters/time-buckets/plan"):
        assert client.get(url, headers=end).status_code == 403, url
        assert client.get(url, headers=key).status_code == 200, url
    assert client.put("/api/parameters", headers=end, json={"changes": {"ModelType": "MILP"}}).status_code == 403
    assert client.put("/api/parameters", headers=owner, json={"changes": {"UseOvertime": True}}).status_code == 200
    assert client.get("/api/parameters/time-buckets/gece", headers=key).status_code == 422


@pytest.mark.db
def test_objectives_order_budget_and_tolerance(db_engine, base, client, people):
    key = auth(people[KEY_USER])
    body = client.get("/api/parameters/objectives", headers=key).json()
    rows = body["rows"]
    assert len(rows) == 24 and body["total_seconds"] == 1140                                              # başlangıç düzeni (K-196)
    assert [r["seq"] for r in rows] == [*range(1, 16), *[None] * 9] and not any(r["active"] for r in rows[15:])
    # Gecikme · Kesin sipariş başa alınır, Fason kapanır, Önceki plandan sapma açılır
    name = lambda r: f"{r['label']} · {r['scope_text']}" if r["scope_text"] else r["label"]   # noqa: E731
    by = {name(r): r for r in rows}
    first, closed, opened = "Gecikme · Talep türü: Kesin sipariş", "Fason", "Önceki plandan sapma"
    order = [first, *[n for n in by if n not in (first, closed, opened) and by[n]["active"]], opened, closed, *[n for n in by if n not in (first, closed, opened) and not by[n]["active"]]]
    sent = [{"id": by[n]["id"], "active": by[n]["active"], "seconds": by[n]["seconds"], "tolerance": by[n]["tolerance"]} for n in order]
    sent[0]["tolerance"] = 1.5
    sent[14].update(active=True, seconds=30, tolerance=10)
    sent[15]["active"] = False
    r = client.put("/api/parameters/objectives", headers=key, json={"rows": sent})
    assert r.status_code == 200, r.text
    after = r.json()
    assert [(name(x), x["seq"]) for x in after["rows"]][:2] == [(first, 1), ("Karşılanmayan talep · Talep türü: Kesin sipariş", 2)]
    saved = {name(x): x for x in after["rows"]}
    assert (saved[first]["tolerance"], saved[opened]["seq"], saved[opened]["seconds"]) == (1.5, 15, 30)
    assert (saved[closed]["active"], saved[closed]["seq"], saved[closed]["seconds"]) == (False, None, None)
    assert after["total_seconds"] == 1140 - 60 + 30
    with db_engine.connect() as c:
        keys = {r[0] for r in c.execute(sa.text("SELECT TOP 20 ObjectKey FROM adm.AuditLog WHERE Action = N'Hedef değişikliği' AND UserId = :u ORDER BY Id DESC"),
                                        {"u": people[KEY_USER]})}
    assert {f"Baz · {first}", f"Baz · {closed}", f"Baz · {opened}"} <= keys
    # denetimler: süre, ödün payı, en az bir aktif hedef, eksik liste
    bad = [dict(x) for x in sent]
    bad[0].update(seconds=0, tolerance=120)
    r = client.put("/api/parameters/objectives", headers=key, json={"rows": bad})
    assert r.status_code == 422 and [d["field"] for d in r.json()["error"]["details"]] == ["rows.1.seconds", "rows.1.tolerance"]
    none = [{**x, "active": False} for x in sent]
    assert client.put("/api/parameters/objectives", headers=key, json={"rows": none}).json()["error"]["details"][0]["problem"] == "En az bir hedef aktif olmalı."
    assert client.put("/api/parameters/objectives", headers=key, json={"rows": sent[:3]}).status_code == 422


@pytest.mark.db
def test_time_buckets_dates_preview_and_save(db_engine, base, client, people):
    key = auth(people[KEY_USER])
    plan = client.get("/api/parameters/time-buckets/plan", headers=key).json()
    assert [(r["bucket_type"], r["count"], r["span_unit"], r["start"], r["end"]) for r in plan["rows"]] == [
        ("Hafta", 3, "Ay", "2026-11-16", "2027-01-31"), ("Ay", 6, "Ay", "2027-02-01", "2027-07-31")]
    assert (plan["bucket_types"], plan["span_units"], plan["end"]) == (["Gün", "Hafta", "Ay", "Çeyrek", "Yıl"], ["Gün", "Hafta", "Ay", "Çeyrek", "Yıl"], "2027-07-31")
    # dönem listesi: 11 hafta + 6 ay; numara, tarih, tip, gün sayısı
    assert (len(plan["periods"]), plan["buckets"]) == (17, 17)
    assert plan["periods"][0] == {"no": 1, "start": "2026-11-16", "end": "2026-11-22", "bucket_type": "Hafta", "days": 7}
    assert plan["periods"][11] == {"no": 12, "start": "2027-02-01", "end": "2027-02-28", "bucket_type": "Ay", "days": 28}
    rows = [{"bucket_type": "Gün", "count": 14, "span_unit": "Gün"}, {"bucket_type": "Hafta", "count": 12, "span_unit": "Hafta"},
            {"bucket_type": "Ay", "count": 6, "span_unit": "Ay"}]
    pre = client.post("/api/parameters/time-buckets/plan/preview", headers=key, json={"rows": rows}).json()
    assert [(r["start"], r["end"], r["buckets"]) for r in pre["rows"]] == [
        ("2026-11-16", "2026-11-29", 14), ("2026-11-30", "2027-02-21", 12), ("2027-02-22", "2027-07-31", 6)]
    # taslağın dönem listesi: 12 haftadan sonra yarım ay (22.02–28.02, 7 gün) görünür
    assert [(p["start"], p["end"], p["days"]) for p in pre["periods"] if p["bucket_type"] == "Ay"][0] == ("2027-02-22", "2027-02-28", 7)
    short = client.post("/api/parameters/time-buckets/plan/preview", headers=key, json={"rows": [{"bucket_type": "Hafta", "count": 1, "span_unit": "Ay"}]}).json()
    assert [(p["start"], p["days"]) for p in short["periods"]] == [("2026-11-16", 7), ("2026-11-23", 7), ("2026-11-30", 1)]   # ay sonunda kısa hafta
    quarters = client.post("/api/parameters/time-buckets/plan/preview", headers=key, json={"rows": [
        {"bucket_type": "Çeyrek", "count": 5, "span_unit": "Ay"}, {"bucket_type": "Yıl", "count": 12, "span_unit": "Ay"}]}).json()
    assert [(p["start"], p["end"], p["bucket_type"]) for p in quarters["periods"]] == [
        ("2026-11-16", "2026-12-31", "Çeyrek"), ("2027-01-01", "2027-03-31", "Çeyrek"), ("2027-04-01", "2027-12-31", "Yıl"), ("2028-01-01", "2028-03-31", "Yıl")]
    by_quarter = client.post("/api/parameters/time-buckets/plan/preview", headers=key, json={"rows": [
        {"bucket_type": "Ay", "count": 2, "span_unit": "Çeyrek"}, {"bucket_type": "Çeyrek", "count": 1, "span_unit": "Yıl"}]}).json()
    assert [(r["start"], r["end"], r["buckets"]) for r in by_quarter["rows"]] == [("2026-11-16", "2027-03-31", 5), ("2027-04-01", "2027-12-31", 3)]
    # önizleme yazmaz; hafta başlangıcı taslağıyla sınırlar değişir
    assert len(client.get("/api/parameters/time-buckets/plan", headers=key).json()["rows"]) == 2
    sunday = client.post("/api/parameters/time-buckets/plan/preview", headers=key, json={"rows": rows[1:2], "week_start": "Pazar"}).json()
    assert sunday["rows"][0]["end"] == "2027-02-06"
    saved = client.put("/api/parameters/time-buckets/plan", headers=key, json={"rows": rows})
    assert saved.status_code == 200 and saved.json()["end"] == "2027-07-31" and len(saved.json()["rows"]) == 3
    with db_engine.connect() as c:
        log = c.execute(sa.text("SELECT TOP 1 ObjectKey, OldValue, NewValue FROM adm.AuditLog WHERE Action = N'Dönem dizisi değişikliği' ORDER BY Id DESC")).one()
    assert log.ObjectKey == "Baz · Plan ekseni" and "Hafta · 3 Ay + Ay · 6 Ay" in log.OldValue and "Gün · 14 Gün + Hafta · 12 Hafta + Ay · 6 Ay" in log.NewValue
    bad = client.put("/api/parameters/time-buckets/plan", headers=key, json={"rows": [{"bucket_type": "Hafta", "count": 3, "span_unit": "Gün"}]})
    assert bad.status_code == 422 and bad.json()["error"]["details"][0] == {"field": "rows.1.SpanUnit", "problem": "Kapsam birimi dönem tipinden küçük olamaz."}
    assert client.put("/api/parameters/time-buckets/plan", headers=key, json={"rows": []}).status_code == 422


@pytest.mark.db
def test_report_axis_and_plan_start(db_engine, base, client, people):
    key = auth(people[KEY_USER])
    assert client.get("/api/parameters/time-buckets/rapor", headers=key).json()["rows"] == []
    # sabit dönem: değer ve birim; sınır kapsam kuralıyla (içinde bulunulan hafta ya da ay dahil, takvim sınırında biter)
    for count, unit, end in ((10, "Gün", "2026-11-25"), (2, "Hafta", "2026-11-29"), (1, "Ay", "2026-11-30"), (2, "Ay", "2026-12-31"), (0, "Ay", None)):
        got = client.put("/api/parameters", headers=key, json={"changes": {"FixPeriod": count, "FixPeriodUnit": unit}}).json()
        assert got["computed"]["fix_period_end"] == end, (count, unit)
    assert client.put("/api/parameters", headers=key, json={"changes": {"FixPeriodUnit": "Yıl"}}).status_code == 422
    assert client.get("/api/parameters/time-buckets/rapor", headers=key).json()["bucket_types"] == ["Gün", "Hafta", "Ay", "Çeyrek", "Yıl"]
    report = [{"bucket_type": "Ay", "count": 2, "span_unit": "Ay"}, {"bucket_type": "Çeyrek", "count": 6, "span_unit": "Ay"}]
    r = client.put("/api/parameters/time-buckets/rapor", headers=key, json={"rows": report})
    assert [(x["start"], x["end"], x["buckets"]) for x in r.json()["rows"]] == [("2026-11-16", "2026-12-31", 2), ("2027-01-01", "2027-06-30", 2)]
    with Session(db_engine) as s:
        assert [p.bucket_type for p in params.read_parts(s, base, MON, cat.AXIS_REPORT)] == ["Hafta", "Ay"]   # "planla aynı" iken plan dizisi
        client.put("/api/parameters", headers=key, json={"changes": {"ReportAxisSameAsPlan": False}})
        assert [p.bucket_type for p in params.read_parts(s, base, MON, cat.AXIS_REPORT)] == ["Ay", "Çeyrek"]
        loaded = loader.load_parameters(s, base)
        assert [b.bucket_type for b in loaded.report_buckets] == ["Ay", "Çeyrek"] and [b.span_unit for b in loaded.time_buckets] == ["Ay", "Ay"]
        # plan başlangıcı veri versiyonunun tarihi: güncel veri versiyonunun yerel günü
        client.put("/api/parameters", headers=key, json={"changes": {"PlanStart": cat.PLAN_START_DATA}})
        from app.flows.schedule import utc_to_local
        at = s.execute(sa.text("SELECT TOP 1 CreatedAt FROM adm.DataVersion ORDER BY Id DESC")).scalar()
        expected = utc_to_local(at).date() if at else MON
        assert params.read_parts(s, base, MON)[0].start == expected


@pytest.mark.db
def test_quality_horizon_and_engine_read_the_base_scenario(db_engine, base):
    with Session(db_engine) as s:
        assert chain.horizon(s, MON) == (date(2026, 11, 1), date(2027, 7, 31))
        loaded = loader.load_parameters(s, base)
        assert (loaded.name, loaded.settings["ModelType"], loaded.settings["SupplierSelectionRule"]) == ("Baz", "LP", "Öncelik")
        assert [o.code for o in loaded.objectives][:2] == ["UNMET_DEMAND", "LATENESS"] and len(loaded.objectives) == 15   # aktif satırlar (K-196)
        assert sum(o.time_budget_seconds for o in loaded.objectives) == params.time_budget(s, base) == 1140
        assert [(b.bucket_type, b.count, b.span_unit) for b in loaded.time_buckets] == [("Hafta", 3, "Ay"), ("Ay", 6, "Ay")]
        assert loaded.report_buckets == loaded.time_buckets
