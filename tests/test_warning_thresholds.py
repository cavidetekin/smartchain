"""Uyarı eşikleri, 7.11 (K-190; fonksiyon 26; Parametreler ekranı): katalog, başlangıç değerleri, kademeli eşiklerin okunması ve yazılması, doğrulamalar
(sayı, birim, yöne göre kademe sırası, aktif ve boş), eşiksiz uyarıda önem, kapalı uyarının değerleri, denetim izi, senaryolar (tam kopya; Baz'dan
akmaz), motor arayüzü ve yetki. Smartchain_test'te; kendi senaryolarını açar ve siler, Baz'ın ve sentetik senaryoların eşiklerine dokunmaz.
"""
import re
from pathlib import Path

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.main import create_app
from app.api.permissions import END_USER, KEY_USER
from app.data.synthetic import dataset as d
from app.engine.data import SqlPlanningData
from app.params import catalog as cat, scenario_tables, scenarios, service as params

from auth_helpers import auth, ensure_user

ROOT = Path(__file__).resolve().parents[1]
URL = "/api/parameters/warning-thresholds"
NAME = "pytest uyarı"
DEFAULTS = {w.code: (*[None if v is None else float(v) for v in w.defaults], w.severity) for w in cat.WARNINGS}


# ------------------------------------------------------------------ katalog (veritabanısız)

def test_catalog_matches_the_decision_and_the_migration():
    """17 uyarı, dört kategori; kodlar ve adlar K-190'da; geçiş 0069'un başlangıç değerleri katalogla aynı; eşikli uyarının başlangıç kademeleri yöne
    göre sıralı."""
    assert [(c, sum(1 for w in cat.WARNINGS if w.category == c)) for c in cat.WARNING_CATEGORIES] == [("Talep", 5), ("Malzeme", 5), ("Kapasite", 4), ("Plan kalitesi", 3)]
    assert [w.code for w in cat.WARNINGS if not w.has_threshold] == ["ORDER_UNMET", "FORECAST_UNMET", "PLAN_TIME_LIMIT", "PLAN_RELAXED", "PLAN_FALLBACK"]
    decision = next(line for line in (ROOT / "docs" / "00-kararlar.md").read_text(encoding="utf-8").splitlines() if line.startswith("| K-190 |"))
    for w in cat.WARNINGS:
        assert f"`{w.code}`" in decision and w.label in decision, w.code
        filled = [v for v in w.defaults if v is not None]
        assert filled == sorted(filled, reverse=w.direction == cat.BELOW) and len(set(filled)) == len(filled), w.code
    text = (ROOT / "db" / "migrations" / "versions" / "0069_uyari_esikleri_k_190.py").read_text(encoding="utf-8")
    seed = {m.group(1): m.group(2) for m in re.finditer(r"^    \('(\w+)', (.+)\),$", text, flags=re.M)}
    shown = lambda v: "None" if v is None else (f"'{v}'" if isinstance(v, str) else str(v))  # noqa: E731
    assert seed == {w.code: ", ".join([f"'{w.category}'", *[shown(v) for v in w.defaults], shown(w.severity)]) for w in cat.WARNINGS}
    last = cat.SECTIONS[-1]                                           # ekranda sekizinci başlık; alt başlıkları kategorilerdir
    assert last.title == "Uyarı eşikleri" and [(sub.title, sub.table) for sub in last.subs] == [(c, "warnings") for c in cat.WARNING_CATEGORIES]


# ------------------------------------------------------------------ veritabanı

@pytest.fixture(scope="module")
def people(db_engine):
    with db_engine.begin() as c:
        return {KEY_USER: ensure_user(c, "pytest.wrn.key", KEY_USER), END_USER: ensure_user(c, "pytest.wrn.end", END_USER)}


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app(), raise_server_exceptions=False)


def _purge(db_engine) -> None:
    with Session(db_engine) as s:
        for (sid,) in s.execute(sa.text("SELECT Id FROM param.ScenarioDefinition WHERE Name LIKE :n"), {"n": NAME + "%"}).all():
            scenarios.delete(s, sid)
        s.commit()


@pytest.fixture
def world(db_engine):
    """Baz'dan kopyalanmış test senaryosu, eşikleri başlangıç değerlerinde (Baz'ın o anki eşiklerinden bağımsız). Sonunda silinir."""
    _purge(db_engine)
    with Session(db_engine) as s:
        base = s.execute(sa.text("SELECT Id FROM param.ScenarioDefinition WHERE IsBase = 1")).scalar_one()
        sid = scenarios.create_copy(s, NAME, base, follows_base=True)["Id"]
        s.execute(sa.text("DELETE FROM param.WarningThreshold WHERE ScenarioDefinitionId = :s"), {"s": sid})
        assert params.ensure_warning_thresholds(s, sid) == len(cat.WARNINGS)       # eksik satırlar katalogdaki başlangıç değerleriyle gelir
        s.commit()
    yield {"base": base, "sid": sid}
    _purge(db_engine)


def get(client, people, sid: int, role: str = KEY_USER) -> dict:
    r = client.get(f"{URL}?scenario_id={sid}", headers=auth(people[role]))
    assert r.status_code == 200, r.text
    return r.json()


def put(client, people, sid: int, changes: dict[str, dict], expect: int = 200):
    """Tablonun tamamını gönderir; changes: kod → değişen alanlar."""
    rows = [{"code": r["code"], "active": r["active"], "severity": r["severity"], **{t: r[t] for t in cat.TIERS}, **changes.get(r["code"], {})} for r in get(client, people, sid)["rows"]]
    r = client.put(f"{URL}?scenario_id={sid}", headers=auth(people[KEY_USER]), json={"rows": rows})
    assert r.status_code == expect, r.text
    return r.json() if expect == 200 else {p["field"]: p["problem"] for p in r.json()["error"]["details"]}


def values(body: dict) -> dict[str, tuple]:
    return {r["code"]: (r["low"], r["medium"], r["high"], r["critical"], r["severity"]) for r in body["rows"]}


def at(code: str, field: str) -> str:
    return f"rows.{[w.code for w in cat.WARNINGS].index(code) + 1}.{field}"


@pytest.mark.db
def test_every_scenario_has_every_warning_with_start_values(db_engine, client, people, world):
    """Katalog sırasıyla 17 satır; başlangıç değerleri; alanlar; her senaryoda her uyarı bir satır; katalogdaki her kod WarningDefinition'da; eşik,
    önem ve aktiflik artık tanımda değil."""
    body = get(client, people, world["sid"])
    assert [r["code"] for r in body["rows"]] == [w.code for w in cat.WARNINGS]
    assert body["categories"] == ["Talep", "Malzeme", "Kapasite", "Plan kalitesi"] and body["severities"] == ["Düşük", "Orta", "Yüksek", "Kritik"]
    assert values(body) == DEFAULTS and all(r["active"] for r in body["rows"])
    late, unmet = body["rows"][0], body["rows"][3]
    assert late == {"code": "ORDER_LATE", "label": "Gecikme", "category": "Talep", "unit": "gün", "direction": "above", "low": 5.0, "medium": 10.0, "high": 15.0,
                    "critical": 20.0, "severity": None, "active": True}
    assert (unmet["label"], unmet["unit"], unmet["direction"], unmet["severity"]) == ("Karşılanmayan sipariş", None, None, "Kritik")
    assert {r["code"]: r["direction"] for r in body["rows"] if r["unit"]} == {
        "ORDER_LATE": "above", "OTIF_RATE": "below", "FILL_RATE": "below", "MAT_SHORTAGE": "below", "MAT_BELOW_SAFETY": "below", "MAT_EXCESS": "above",
        "PURCHASE_LATE": "above", "SHELF_LIFE": "below", "CAP_OVERLOAD": "above", "CAP_OVER_TARGET": "above", "CAP_LOW_LOAD": "below", "OVERTIME_USE": "above"}
    with db_engine.connect() as c:
        counts = c.execute(sa.text("SELECT s.Name, COUNT(w.Id), COUNT(DISTINCT w.WarningCode) FROM param.ScenarioDefinition s LEFT JOIN param.WarningThreshold w "
                                   "ON w.ScenarioDefinitionId = s.Id GROUP BY s.Name")).all()
        assert counts and all((n, k) == (len(cat.WARNINGS), len(cat.WARNINGS)) for _, n, k in counts), counts   # geçiş her senaryoya yazar
        defined = dict(c.execute(sa.text("SELECT Code, Category FROM param.WarningDefinition")).all())
        assert {w.code: w.category for w in cat.WARNINGS}.items() <= defined.items()
        columns = set(c.execute(sa.text("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = 'param' AND TABLE_NAME = 'WarningDefinition'")).scalars())
        assert columns == {"Code", "Category"}


@pytest.mark.db
def test_tiers_are_written_cleared_and_kept_when_switched_off(db_engine, client, people, world):
    """Kademeli eşik yazılır, kademe boşaltılır, yüzde iki ondalık alır; eşiksiz uyarıda önem değişir; kapatılan uyarının değerleri durur; yalnız değişen
    satır yazılır ve denetim izine düşer."""
    sid = world["sid"]
    body = put(client, people, sid, {"ORDER_LATE": {"medium": 12, "critical": None}, "OTIF_RATE": {"low": "97,25"}, "FORECAST_UNMET": {"severity": "Yüksek"},
                                     "CAP_LOW_LOAD": {"active": False}})
    assert body["saved"] == 4
    got = values(body)
    assert got["ORDER_LATE"] == (5.0, 12.0, 15.0, None, None) and got["OTIF_RATE"] == (97.25, 90.0, 85.0, 80.0, None) and got["FORECAST_UNMET"][4] == "Yüksek"
    off = next(r for r in body["rows"] if r["code"] == "CAP_LOW_LOAD")
    assert (off["active"], off["low"], off["medium"]) == (False, 40.0, 20.0)                                 # kapatılan uyarının değerleri durur
    assert {c: v for c, v in got.items() if c not in ("ORDER_LATE", "OTIF_RATE", "FORECAST_UNMET")} == {c: v for c, v in DEFAULTS.items() if c not in ("ORDER_LATE", "OTIF_RATE", "FORECAST_UNMET")}
    assert put(client, people, sid, {})["saved"] == 0                                                        # değişiklik yok
    assert put(client, people, sid, {"CAP_LOW_LOAD": {"active": True}})["saved"] == 1                         # yeniden açılınca eşikler yerinde
    assert values(get(client, people, sid))["CAP_LOW_LOAD"] == (40.0, 20.0, None, None, None)
    # kapalı uyarıda kademelerin hepsi boş olabilir; eşik "%95" yazımıyla da kabul edilir
    assert put(client, people, sid, {"CAP_LOW_LOAD": {"active": False, "low": None, "medium": None}, "FILL_RATE": {"low": "%99"}})["saved"] == 2
    with db_engine.connect() as c:
        log = c.execute(sa.text("SELECT ObjectKey, OldValue, NewValue, ScenarioName FROM adm.AuditLog WHERE Action = N'Uyarı eşiği değişikliği' AND UserId = :u AND ObjectKey LIKE :k "
                                "ORDER BY Id"), {"u": people[KEY_USER], "k": NAME + " · %"}).all()
    first = {k.split(" · ")[1]: (o, n) for k, o, n, _ in log[:4]}
    assert first == {"Gecikme": ('{"ThresholdMedium": 10.0, "ThresholdCritical": 20.0}', '{"ThresholdMedium": 12.0, "ThresholdCritical": null}'),
                     "OTIF oranı": ('{"ThresholdLow": 95.0}', '{"ThresholdLow": 97.25}'),
                     "Karşılanmayan tahmin": ('{"Severity": "Orta"}', '{"Severity": "Yüksek"}'), "Düşük doluluk": ('{"IsActive": true}', '{"IsActive": false}')}
    assert {s for *_, s in log} == {NAME} and len(log) == 7
    with db_engine.begin() as c:
        c.execute(sa.text("DELETE FROM adm.AuditLog WHERE Action = N'Uyarı eşiği değişikliği' AND UserId = :u"), {"u": people[KEY_USER]})


@pytest.mark.db
def test_validation_names_the_cell_and_saves_nothing(client, people, world):
    """Doğrulamalar hücre başına; biri bile varsa hiçbiri kaydedilmez. Kademe sırası yöne göre kesin (eşit de olmaz); boş kademe atlanır."""
    sid = world["sid"]
    problems = put(client, people, sid, expect=422, changes={
        "ORDER_LATE": {"high": 8},                                  # aşınca: Yüksek, Orta'dan (10) büyük olmalı
        "OTIF_RATE": {"medium": 96},                                # altında: Orta, Düşük'ten (95) küçük olmalı
        "FILL_RATE": {"medium": None, "high": 98},                  # boş kademe atlanır: Yüksek, Düşük'e (98) eşit olamaz
        "MAT_SHORTAGE": {"low": "7,5"},                             # gün tam sayı
        "MAT_BELOW_SAFETY": {"low": "99,125"},                      # yüzde en çok iki ondalık
        "MAT_EXCESS": {"low": -1},
        "PURCHASE_LATE": {"low": "abc"},
        "CAP_OVER_TARGET": {"low": None, "medium": None},           # aktif ve hiç kademe yok
        "CAP_LOW_LOAD": {"severity": "Kritik"},                     # eşikli uyarıya önem
        "ORDER_UNMET": {"severity": None},                          # eşiksiz uyarıda önem zorunlu
        "FORECAST_UNMET": {"low": 5},                               # eşiksiz uyarıya eşik
        "PLAN_RELAXED": {"severity": "Çok yüksek"},
        "OVERTIME_USE": {"medium": 120, "high": 100},               # düzeltilebilir sorun: Yüksek, Orta'dan büyük olmalı
    })
    assert problems == {
        at("ORDER_LATE", "high"): "Yüksek eşiği Orta eşiğinden büyük olmalı.", at("OTIF_RATE", "medium"): "Orta eşiği Düşük eşiğinden küçük olmalı.",
        at("FILL_RATE", "high"): "Yüksek eşiği Düşük eşiğinden küçük olmalı.", at("MAT_SHORTAGE", "low"): "Tam sayı girilmeli.",
        at("MAT_BELOW_SAFETY", "low"): "En çok 2 ondalıklı sayı girilmeli.", at("MAT_EXCESS", "low"): "0 ya da daha büyük olmalı.",
        at("PURCHASE_LATE", "low"): "Sayı girilmeli.", at("CAP_OVER_TARGET", "active"): "Aktif uyarıda en az bir kademe dolu olmalı.",
        at("CAP_LOW_LOAD", "severity"): "Eşikli uyarıda önem kademelerle belirlenir.", at("ORDER_UNMET", "severity"): "Önem seçilmeli.",
        at("FORECAST_UNMET", "severity"): "Bu uyarının eşiği yok; yalnız önemi seçilir.", at("PLAN_RELAXED", "severity"): "Önem seçilmeli.",
        at("OVERTIME_USE", "high"): "Yüksek eşiği Orta eşiğinden büyük olmalı."}
    assert values(get(client, people, sid)) == DEFAULTS                                                       # hiçbiri kaydedilmedi
    # eşit eşik iki yönde de reddedilir; sınırlar: 0 olur
    assert put(client, people, sid, {"ORDER_LATE": {"medium": 5}}, expect=422) == {at("ORDER_LATE", "medium"): "Orta eşiği Düşük eşiğinden büyük olmalı."}
    assert put(client, people, sid, {"MAT_SHORTAGE": {"critical": 0}, "CAP_LOW_LOAD": {"medium": 0}})["saved"] == 2
    # liste eksik ya da sırası farklıysa reddedilir
    rows = [{"code": r["code"], "active": r["active"], "severity": r["severity"], **{t: r[t] for t in cat.TIERS}} for r in get(client, people, sid)["rows"]]
    r = client.put(f"{URL}?scenario_id={sid}", headers=auth(people[KEY_USER]), json={"rows": rows[1:]})
    assert r.status_code == 422 and r.json()["error"]["details"][0]["problem"] == "Uyarı listesi değişmiş; sayfayı yenileyin."


@pytest.mark.db
def test_thresholds_are_settings_copied_with_the_scenario_and_not_following_base(db_engine, client, people, world):
    """Eşikler ayardır (tam kopya, K-177): kopyalanan senaryo kaynağının eşiklerini alır; sonrası bağımsızdır (Baz'ı izleyen senaryoda da kaynaktaki
    değişiklik akmaz); senaryo silinince satırları silinir; tablo kayıt defterinde Ayar türündedir."""
    sid = world["sid"]
    entry = next(t for t in scenario_tables.TABLES if t.name == "WarningThreshold")
    assert entry.kind == scenario_tables.SETTING and scenario_tables.model_tables() == {t.name for t in scenario_tables.TABLES}
    put(client, people, sid, {"ORDER_LATE": {"low": 3}, "PLAN_FALLBACK": {"severity": "Kritik"}, "SHELF_LIFE": {"active": False}})
    with Session(db_engine) as s:
        copy = scenarios.create_copy(s, NAME + " kopya", sid, follows_base=True)["Id"]
        s.commit()
    mine = get(client, people, copy)
    assert values(mine)["ORDER_LATE"][0] == 3.0 and values(mine)["PLAN_FALLBACK"][4] == "Kritik" and not next(r for r in mine["rows"] if r["code"] == "SHELF_LIFE")["active"]
    put(client, people, sid, {"ORDER_LATE": {"low": 4}})                                                      # kaynaktaki değişiklik kopyaya akmaz
    put(client, people, copy, {"OTIF_RATE": {"low": 99}})                                                     # kopyadaki değişiklik kaynağı etkilemez
    assert values(get(client, people, copy))["ORDER_LATE"][0] == 3.0 and values(get(client, people, sid))["OTIF_RATE"][0] == 95.0
    assert values(get(client, people, world["base"]))["ORDER_LATE"] == values(get(client, people, world["base"]))["ORDER_LATE"]   # Baz okunur (değişmedi)
    with Session(db_engine) as s:
        scenarios.delete(s, copy)
        s.commit()
    with db_engine.connect() as c:
        assert c.execute(sa.text("SELECT COUNT(*) FROM param.WarningThreshold WHERE ScenarioDefinitionId = :s"), {"s": copy}).scalar() == 0


@pytest.mark.db
def test_engine_reads_active_warnings_and_synthetic_scenario_differs(db_engine, client, people, world):
    """Motor arayüzü (docs/09): senaryonun aktif uyarıları, kademeleri ve önemiyle; kapalı uyarı dönmez. Sentetik "Kısıtsız kapasite" senaryosunda
    Aşırı yük eşikleri farklı ve Düşük doluluk kapalıdır (docs/11)."""
    sid = world["sid"]
    put(client, people, sid, {"CAP_LOW_LOAD": {"active": False}, "ORDER_LATE": {"low": None}})
    with Session(db_engine) as s:
        version = s.execute(sa.text("SELECT MAX(Id) FROM adm.DataVersion")).scalar()
        got = {w["Code"]: w for w in SqlPlanningData(s, version, sid).warning_thresholds()}
        with pytest.raises(ValueError):
            SqlPlanningData(s, version).warning_thresholds()
        mono = s.execute(sa.text("SELECT Id FROM param.ScenarioDefinition WHERE Name = N'Kısıtsız kapasite' AND IsSynthetic = 1")).scalar_one()
    assert set(got) == {w.code for w in cat.WARNINGS} - {"CAP_LOW_LOAD"}
    assert got["ORDER_LATE"] == {"Code": "ORDER_LATE", "Category": "Talep", "Unit": "gün", "Direction": "above", "Low": None, "Medium": 10.0, "High": 15.0, "Critical": 20.0,
                                 "Severity": None}
    assert (got["ORDER_UNMET"]["Severity"], got["ORDER_UNMET"]["Unit"], got["ORDER_UNMET"]["Low"]) == ("Kritik", None, None)
    synthetic = get(client, people, mono)
    code, tiers = d.WARNING_THRESHOLD_CHANGE
    assert values(synthetic)[code][:4] == tuple(None if v is None else float(v) for v in tiers) == (None, 110.0, 125.0, 150.0)
    assert [r["code"] for r in synthetic["rows"] if not r["active"]] == [d.WARNING_THRESHOLD_OFF] == ["CAP_LOW_LOAD"]


@pytest.mark.db
def test_permissions(client, people, world):
    """Fonksiyon 26: Key user okur ve yazar; End user'ın yetkisi yok (Parametreler'le aynı); oturumsuz 401."""
    sid = world["sid"]
    end = auth(people[END_USER])
    assert client.get(f"{URL}?scenario_id={sid}", headers=end).status_code == 403
    assert client.put(f"{URL}?scenario_id={sid}", headers=end, json={"rows": []}).status_code == 403
    assert client.get(URL).status_code == 401
    assert client.put(f"{URL}?scenario_id={sid}", headers=auth(people[KEY_USER]), json={"rows": [{"code": "ORDER_LATE", "active": True, "extra": 1}]}).status_code == 422
