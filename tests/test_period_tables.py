"""Dönem tablosu altyapısı (K-184, geliştirme 7.8): ortak dönem listesi, dönem tablosu listesi (deneme: kaynak grubu × dönem), sıralama,
İlk · Son dönem değeri, senaryo, önbellek ve yenileme. Sentetik v0'da (Smartchain_test); kendi yazdığını geri alır.

Sabitlenenler: dönem alanları her yerde Dönem başı'na göre sıralanır; Son dönem değeri zaman içinde toplanmaz, kayıtlar arasında toplanır;
her tetikleyicide yalnız etkilenen ana kayıt ve günler yenilenir ve önbellekteki sonuç sıfırdan hesaplananla birebir aynıdır (motorun yolu).
"""
import dataclasses
import io
from collections import defaultdict
from datetime import date, timedelta

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy.orm import Session

from app import periods as P
from app.api.lists import pivot as pivot_query
from app.api.main import create_app
from app.api.permissions import END_USER, KEY_USER
from app.params import horizon, scenarios
from app.periods import cache, capacity_demo, periods as period_list
from app.periods.__main__ import main as periods_cli

from auth_helpers import auth, ensure_user

U = "/api/period-resource-group-demo"
CACHE = capacity_demo.CACHE
PERIOD_FIELDS = ["PeriodType", "Period", "PeriodStart", "PeriodEnd", "Week", "Month", "Quarter", "Year", "PeriodDays"]
MARK = (77, 33, 66, 44)   # testin yazdığı verim satırlarının yüzdeleri (temizlik bunlara bakar)


# --- dönem listesi (veritabanısız) --------------------------------------------------------------------------------------

def test_periods_from_the_horizon_labels_and_fields():
    """Karışık ufuk (hafta + ay), kısa ilk ve son hafta; alanlar dönem başından; etiketler pivotun dönem etiketleriyle aynı."""
    parts = horizon.parts(date(2026, 12, 23), [("Hafta", 3, "Hafta"), ("Ay", 2, "Ay")])   # Çarşamba'dan: ilk hafta kısa
    found = period_list.build(parts)
    assert [(p.no, p.type, p.label, p.start, p.end, p.days) for p in found[:3]] == [
        (1, "Hafta", "H52 2026", date(2026, 12, 23), date(2026, 12, 27), 5),
        (2, "Hafta", "H53 2026", date(2026, 12, 28), date(2027, 1, 3), 7),
        (3, "Hafta", "H1 2027", date(2027, 1, 4), date(2027, 1, 10), 7)]
    assert [(p.type, p.label) for p in found[3:]] == [("Ay", "Oca 2027"), ("Ay", "Şub 2027")]
    assert found[3].start == date(2027, 1, 11) and found[3].days == 21                     # ayın kalanı: yarım ay sayılır
    second = found[1]
    assert (second.week, second.month, second.quarter, second.year) == ("H53 2026", "Ara 2026", "Ç4 2026", "2026")
    assert all(a.end + timedelta(days=1) == b.start for a, b in zip(found, found[1:]))     # dönemler kesintisiz
    # hafta kendi yılıyla, Yıl dönem başının takvim yılı: 30.12.2024 "H1 2025", yılı 2024
    assert period_list.week_of(date(2024, 12, 30)) == "H1 2025"
    assert period_list.build(horizon.parts(date(2024, 12, 30), [("Hafta", 1, "Hafta")]))[0].year == "2024"
    # hafta başlangıcı Pazar: 22.11.2026 Pazar yeni haftayı başlatır
    assert period_list.week_of(date(2026, 11, 21), week_start=6) == "H47 2026" and period_list.week_of(date(2026, 11, 22), week_start=6) == "H48 2026"
    assert [period_list.label(k, date(2026, 11, 19)) for k in ("Gün", "Hafta", "Ay", "Çeyrek", "Yıl")] == ["19.11.2026", "H47 2026", "Kas 2026", "Ç4 2026", "2026"]
    # pivotun dönem etiketi aynı işlevden
    assert pivot_query.key_label("2026-11-16", "date", "week") == period_list.week_of(date(2026, 11, 16)) == "H47 2026"
    assert pivot_query.key_label("2026-11-01", "date", "month") == "Kas 2026" and pivot_query.key_label("2026-10-01", "date", "quarter") == "Ç4 2026"
    days = __import__("json").loads(period_list.days_json(found[:2]))
    assert len(days) == 12 and days[0] == {"d": "2026-12-23", "no": 1} and days[-1] == {"d": "2027-01-03", "no": 2}


# --- veritabanı ---------------------------------------------------------------------------------------------------------

pytestmark_db = pytest.mark.db


def _clean(conn) -> None:
    conn.execute(sa.text(f"DELETE FROM param.ResourceEfficiency WHERE EfficiencyPct IN ({', '.join(map(str, MARK))})"))
    conn.execute(sa.text("DELETE FROM cache.ResourceCapacityDay"))
    conn.execute(sa.text("DELETE FROM cache.PeriodCacheState"))


@pytest.fixture(scope="module")
def world(db_engine):
    """Baz, Baz'ı izleyen ve izlemeyen birer senaryo; iki kaynak (ayrı gruplardan); temiz önbellek. Sonunda yazılanlar silinir."""
    with db_engine.begin() as c:
        _clean(c)
        users = {KEY_USER: ensure_user(c, "pytest.pt.key", KEY_USER), END_USER: ensure_user(c, "pytest.pt.end", END_USER)}
        c.execute(sa.text("UPDATE adm.AppUser SET ScenarioDefinitionId = NULL WHERE Id IN (:a, :b)"), {"a": users[KEY_USER], "b": users[END_USER]})
        base = c.execute(sa.text("SELECT Id FROM param.ScenarioDefinition WHERE IsBase = 1")).scalar()
        follower = c.execute(sa.text("SELECT TOP 1 Id FROM param.ScenarioDefinition WHERE FollowsBase = 1 AND IsActive = 1 AND ISNULL(IsBase, 0) = 0 ORDER BY Id")).scalar()
        free = c.execute(sa.text("SELECT TOP 1 Id FROM param.ScenarioDefinition WHERE FollowsBase = 0 AND IsActive = 1 AND ISNULL(IsBase, 0) = 0 ORDER BY Id")).scalar()
        rows = c.execute(sa.text(
            "SELECT m.ResourceId, g.Id, g.Code FROM core.ResourceGroupMember m JOIN core.ResourceGroup g ON g.Id = m.ResourceGroupId AND g.VersionTo IS NULL "
            "JOIN core.Resource r ON r.Id = m.ResourceId AND r.VersionTo IS NULL WHERE m.VersionTo IS NULL AND r.DailyCapacity > 0 ORDER BY g.Code, m.ResourceId")).all()
    assert base and follower and free and len(rows) > 3
    r1 = rows[0]
    r2 = next(r for r in rows if r[1] != r1[1] and r[0] != r1[0])
    yield {"users": users, "base": base, "follower": follower, "free": free, "r1": r1[0], "g1": r1[2], "r2": r2[0], "g2": r2[2]}
    with db_engine.begin() as c:
        _clean(c)


@pytest.fixture
def clean(db_engine, world):
    """Her test temiz girişle ve boş önbellekle başlar."""
    with db_engine.begin() as c:
        _clean(c)
    yield
    with db_engine.begin() as c:
        _clean(c)


@pytest.fixture(scope="module")
def api(db_engine, world):
    client = TestClient(create_app(), raise_server_exceptions=False)
    client.headers.update(auth(world["users"][KEY_USER]))
    return client


def post(api, path, **body):
    r = api.post(U + path, json=body)
    assert r.status_code == 200, r.text
    return r.json()


def all_rows(api, **body):
    out, offset = [], 0
    while True:
        r = post(api, "/query", limit=100, offset=offset, **body)
        out += r["rows"]
        offset += 100
        if offset >= r["filtered"]:
            return out


def horizon_of(db_engine, scenario_id) -> list[period_list.Period]:
    with Session(db_engine) as s:
        return P.read_periods(s, scenario_id, date.today())


def efficiency(db_engine, scenario_id, resource_id, pct, start, end) -> None:
    with db_engine.begin() as c:
        c.execute(sa.text("INSERT INTO param.ResourceEfficiency (ScenarioDefinitionId, ResourceId, ValidFrom, ValidTo, EfficiencyPct) VALUES (:s, :r, :a, :b, :p)"),
                  {"s": scenario_id, "r": resource_id, "a": start, "b": end, "p": pct})


def stored(db_engine, scenario_id) -> dict:
    """Önbellek tablosundaki satırlar (senaryonun kendi tuttukları)."""
    with db_engine.connect() as c:
        rows = c.execute(sa.text("SELECT ResourceId, [Date], WorkingDay, Capacity, AvailableCapacity FROM cache.ResourceCapacityDay WHERE ScenarioDefinitionId = :s"),
                         {"s": scenario_id}).all()
    return {(r[0], r[1]): (float(r[2]), float(r[3]), float(r[4])) for r in rows}


def same_as_scratch(db_engine, scenario_id) -> int:
    """Önbellekteki geçerli sonuç, girişlerden sıfırdan hesaplananla (motorun yolu) birebir aynı. Dönen: satır sayısı."""
    found = horizon_of(db_engine, scenario_id)
    with Session(db_engine) as s:
        key = lambda r: (r["ResourceId"], r["Date"], float(r["WorkingDay"]), float(r["Capacity"]), float(r["AvailableCapacity"]))  # noqa: E731
        cached = sorted(key(r) for r in capacity_demo.cached(s, scenario_id, found[0].start, found[-1].end))
        scratch = sorted(key(r) for r in P.values(s, CACHE.name, scenario_id, found[0].start, found[-1].end))
    assert cached == scratch
    return len(cached)


def ensure(db_engine, scenario_id) -> dict:
    found = horizon_of(db_engine, scenario_id)
    with Session(db_engine) as s:
        return cache.ensure(s, CACHE, scenario_id, found[0].start, found[-1].end)


@pytest.mark.db
def test_rows_fields_and_values(api, db_engine, world, clean):
    """Satır = kaynak grubu × senaryonun dönemi; dokuz dönem alanı aynı ad ve sırayla; değerler girişlerden elle hesapla tutar."""
    cols = api.get(U + "/columns").json()
    names = [c["field"] for c in cols["columns"]]
    at = names.index("PeriodType")
    assert names[at:at + 9] == PERIOD_FIELDS and names[:3] == ["ResourceGroupCode", "ResourceGroupName", "CapacityUnit"]
    assert [c["label"] for c in cols["columns"][at:at + 9]] == ["Dönem tipi", "Dönem", "Dönem başı", "Dönem sonu", "Hafta", "Ay", "Çeyrek", "Yıl", "Dönem takvim günü"]
    by = {c["field"]: c for c in cols["columns"]}
    assert all(by[f]["order_by"] == "PeriodStart" for f in ("PeriodType", "Period", "Week", "Month", "Quarter", "Year")) and by["PeriodStart"]["order_by"] is None
    assert cols["period_table"] is True and cols["standard_pivot"]["columns"] == [{"field": "Period"}] and cols["standard_pivot"]["values_on"] == "rows"
    assert cols["calculated_values"][0]["name"] == "Ortalama verimlilik" and cols["relations"] == [{"path": "ResourceGroupId", "label": "Kaynak grubu"}]
    assert (by["ResourceCount"]["aggregate"], by["Efficiency"]["aggregate"], by["Efficiency"]["aggregate_weight"]) == ("last", "wavg", "TotalCapacity")

    found = horizon_of(db_engine, world["base"])
    rows = all_rows(api)
    with db_engine.connect() as c:
        groups = c.execute(sa.text("SELECT Id, Code FROM core.ResourceGroup WHERE VersionTo IS NULL")).all()
        members = c.execute(sa.text("SELECT m.ResourceGroupId, r.Id, r.DailyCapacity, r.CalendarId FROM core.ResourceGroupMember m JOIN core.Resource r "
                                    "ON r.Id = m.ResourceId AND r.VersionTo IS NULL WHERE m.VersionTo IS NULL")).all()
        calendar = {(r[0], r[1]): (float(r[3] if r[3] is not None else 1) if r[2] else 0.0)
                    for r in c.execute(sa.text("SELECT CalendarId, [Date], IsWorkingDay, WorkingFraction FROM core.CalendarDay WHERE VersionTo IS NULL"))}
    assert len(rows) == len(groups) * len(found) and len({r["Id"] for r in rows}) == len(rows)     # verisi olmayan dönem de satır; kimlik tekil
    first = found[0]
    line = next(r for r in rows if r["ResourceGroupCode"] == world["g1"] and r["Period"] == first.label)
    assert [line[f] for f in PERIOD_FIELDS] == [first.type, first.label, first.start.isoformat(), first.end.isoformat(), first.week, first.month, first.quarter,
                                                first.year, first.days]
    gid = next(g[0] for g in groups if g[1] == world["g1"])
    own = [m for m in members if m[0] == gid]
    working = capacity_total = 0.0
    for _g, _rid, daily, cal in own:
        day = first.start
        while day <= first.end:
            wd = calendar.get((cal, day), 1.0 if day.weekday() < 5 else 0.0)        # takvimde olmayan gün: Pazartesi–Cuma çalışılır
            working += wd
            capacity_total += wd * float(daily or 0)
            day += timedelta(days=1)
    assert line["ResourceCount"] == len({m[1] for m in own}) and line["WorkingDays"] == pytest.approx(working)
    assert line["TotalCapacity"] == pytest.approx(capacity_total) == pytest.approx(line["AvailableCapacity"]) and line["Efficiency"] == pytest.approx(1.0)
    assert line["ResourceGroupId"] == gid and line["Id"] == gid * 1000 + 1
    # kaynağı olmayan grup: satırları var, değerleri 0, verimlilik boş
    empty = [g for g in groups if g[0] not in {m[0] for m in members}]
    for g in empty[:1]:
        row = next(r for r in rows if r["ResourceGroupCode"] == g[1])
        assert (row["ResourceCount"], row["TotalCapacity"], row["Efficiency"]) == (0, 0, None)


@pytest.mark.db
def test_period_fields_are_ordered_by_period_start_everywhere(api, db_engine, world, clean):
    found = horizon_of(db_engine, world["base"])
    labels = [p.label for p in found]
    months = list(dict.fromkeys(p.month for p in found))
    assert labels != sorted(labels) and months != sorted(months)                                       # alfabetik sıra farklı olurdu
    assert [v["value"] for v in post(api, "/values", field="Period")] == labels                        # filtre penceresi
    assert [v["value"] for v in post(api, "/values", field="Month")] == months
    assert [v["value"] for v in post(api, "/values", field="PeriodType")] == list(dict.fromkeys(p.type for p in found))
    one = [{"field": "ResourceGroupCode", "op": "in", "values": [world["g1"]]}]
    up = all_rows(api, filters=one, sort=[{"field": "Period", "dir": "asc"}], fields=["Period"])
    # Ay ve Dönem aynı sıra alanına bağlı: ilki geçerli (ay azalan); sorgu hata vermez
    down = all_rows(api, filters=one, sort=[{"field": "Month", "dir": "desc"}, {"field": "Period", "dir": "asc"}], fields=["Period", "Month"])
    assert [r["Period"] for r in up] == labels and [r["Period"] for r in down] == labels[::-1]         # tablo sıralaması
    groups = post(api, "/groups", group_by=["Month", "Period"], fields=["TotalCapacity"])
    assert [g["key"][0] for g in groups["groups"]] == months                                           # gruplama
    assert [c["key"][-1] for g in groups["groups"] for c in g["children"]] == labels
    assert "ResourceCount" not in groups["aggregate_specs"] and groups["aggregate_specs"]["TotalCapacity"] == {"fn": "sum"}   # Son dönem değeri gruplamada yok
    pv = post(api, "/pivot", rows=[{"field": "ResourceGroupCode"}], columns=[{"field": "Month"}, {"field": "Period"}],
              values=[{"id": "a", "field": "TotalCapacity", "fn": "sum"}], totals={"rows": False, "columns": False, "subtotals": True}, limit=100)
    assert [c["key"][1] for c in pv["columns"] if not c["total"]] == labels                            # pivot sütunları
    assert [c["key"][0] for c in pv["columns"] if c["total"]] == months
    pv = post(api, "/pivot", rows=[{"field": "Quarter"}, {"field": "Period"}], values=[{"id": "a", "field": "TotalCapacity", "fn": "sum"}], limit=100)
    assert [r["key"][1] for r in pv["rows"]] == labels                                                 # pivot satırları
    down = post(api, "/pivot", rows=[{"field": "Period"}], values=[{"id": "a", "field": "TotalCapacity", "fn": "sum"}], limit=100, sort={"by": "name", "dir": "desc"})
    assert [r["key"][0] for r in down["rows"]] == labels[::-1]
    chart = api.post(U + "/chart", json={"x": {"field": "Period"}, "series": [{"id": "a", "field": "TotalCapacity", "fn": "sum"}], "limit": 5})
    assert chart.status_code == 200, chart.text
    assert [v["key"] for v in chart.json()["x"]["values"]][:5] == labels[:5] and chart.json()["x"]["other"] is True   # sınırda sıradaki ilk dönemler kalır


@pytest.mark.db
def test_first_and_last_period_value(api, db_engine, world, clean):
    """Zaman içinde ilk (son) dönemin değeri, kayıtlar arasında toplanır: kaynak sayısı ay altında haftaların toplamı değildir."""
    found = horizon_of(db_engine, world["base"])
    values = [{"id": "last", "field": "ResourceCount", "fn": "last"}, {"id": "first", "field": "ResourceCount", "fn": "first"},
              {"id": "sum", "field": "ResourceCount", "fn": "sum"}, {"id": "wl", "field": "WorkingDays", "fn": "last"}, {"id": "wf", "field": "WorkingDays", "fn": "first"}]
    pv = post(api, "/pivot", rows=[{"field": "ResourceGroupCode"}], columns=[{"field": "Month"}, {"field": "Period"}], values=values,
              totals={"rows": True, "columns": True, "subtotals": True}, limit=100)
    cols = pv["columns"]
    month = found[0].month
    inside = [i for i, c in enumerate(cols) if not c["total"] and c["key"][0] == month]
    sub = next(i for i, c in enumerate(cols) if c["total"] and c["key"] == [month])
    total = next(i for i, c in enumerate(cols) if c["total"] and c["key"] == [])
    assert len(inside) > 1                                                                              # ay altında birden çok hafta
    leaves = [r for r in pv["rows"] if not r["total"]]
    for r in leaves:
        n = r["cells"][0][inside[0]]
        assert [r["cells"][0][i] for i in (*inside, sub, total)] == [n] * (len(inside) + 2)             # dört hafta ay altında 3, 12 değil
        assert r["cells"][1][sub] == n and r["cells"][2][sub] == n * len(inside)                        # Toplam ise haftaları toplar
        assert r["cells"][3][sub] == r["cells"][3][inside[-1]] and r["cells"][4][sub] == r["cells"][4][inside[0]]   # son haftanın · ilk haftanın değeri
        assert r["cells"][3][total] == r["cells"][3][[i for i, c in enumerate(cols) if not c["total"]][-1]]
    grand = pv["rows"][-1]
    assert grand["total"] and grand["key"] == []
    assert grand["cells"][0][sub] == sum(r["cells"][0][sub] for r in leaves) == grand["cells"][0][total]   # kayıtlar arasında toplanır: 3 + 2 = 5
    assert grand["cells"][3][sub] == pytest.approx(sum(r["cells"][3][sub] for r in leaves))
    # satır ekseninde de: ay toplamı satırı ve genel toplam; değere göre sıralama
    pv = post(api, "/pivot", rows=[{"field": "Month"}, {"field": "Period"}], values=values[:1], totals={"rows": True, "columns": False, "subtotals": True}, limit=100)
    with db_engine.connect() as c:
        members = c.execute(sa.text("SELECT COUNT(*) FROM (SELECT DISTINCT ResourceGroupId, ResourceId FROM core.ResourceGroupMember WHERE VersionTo IS NULL) x")).scalar()
    assert {r["cells"][0][0] for r in pv["rows"]} == {members}                                          # her dönemde, ay toplamında ve genel toplamda aynı
    by_value = post(api, "/pivot", rows=[{"field": "ResourceGroupCode"}], values=values[:1], limit=100, sort={"by": "last", "dir": "desc"})
    counts = [r["cells"][0][0] for r in by_value["rows"]]
    assert counts == sorted(counts, reverse=True)
    # hesaplanan değerin işleneni olabilir; başka listede kullanılamaz
    calc = post(api, "/pivot", rows=[{"field": "ResourceGroupCode"}], limit=100,
                values=[values[0], {"id": "c", "field": "TotalCapacity", "fn": "sum"}, {"id": "x", "kind": "calc", "a": "c", "op": "div", "b": "last"}])
    row = next(r for r in calc["rows"] if r["cells"][0][0])
    cell = row["cells"][1][0]
    assert row["cells"][2][0] == pytest.approx((cell["v"] if isinstance(cell, dict) else cell) / row["cells"][0][0])
    other = api.post("/api/materials/pivot", json={"rows": [{"field": "MaterialGroup"}], "values": [{"id": "a", "field": "SafetyStock", "fn": "last"}], "limit": 10})
    assert other.status_code == 422 and "yalnız dönem tablolarında" in other.text


@pytest.mark.db
def test_related_fields_calculated_value_and_weighted_default(api, db_engine, world, clean):
    """Ana kayıt üzerinden ilişkili alan (satır, filtre); oranlar toplamda ağırlıklı ortalama ve toplamlardan hesap aynı sonucu verir."""
    found = horizon_of(db_engine, world["base"])
    efficiency(db_engine, world["base"], world["r1"], 77, found[0].start, found[1].end)
    values = [{"id": "e", "field": "Efficiency", "fn": "wavg", "weight": "TotalCapacity"}, {"id": "avg", "field": "Efficiency", "fn": "avg"},
              {"id": "a", "field": "AvailableCapacity", "fn": "sum"}, {"id": "t", "field": "TotalCapacity", "fn": "sum"},
              {"id": "x", "kind": "calc", "a": "a", "op": "div", "b": "t", "percent": True}]
    pv = post(api, "/pivot", rows=[{"field": "ResourceGroupId/IsCritical"}, {"field": "ResourceGroupCode"}], values=values,
              totals={"rows": True, "columns": False, "subtotals": True}, limit=100, filters=[{"field": "ResourceGroupId/CapacityUnit", "op": "equals", "value": "SAAT"}])
    num = lambda c: c["v"] if isinstance(c, dict) else c  # noqa: E731
    row = next(r for r in pv["rows"] if r["key"][1:] == [world["g1"]])
    assert num(row["cells"][0][0]) < 1 and num(row["cells"][0][0]) == pytest.approx(num(row["cells"][2][0]) / num(row["cells"][3][0]))
    assert num(row["cells"][4][0]) == pytest.approx(num(row["cells"][0][0]))                             # toplamlardan = kapasiteyle ağırlıklı ortalama
    assert num(row["cells"][1][0]) != pytest.approx(num(row["cells"][0][0]))                             # dönemlerin düz ortalaması farklı
    grand = pv["rows"][-1]
    assert num(grand["cells"][0][0]) == pytest.approx(num(grand["cells"][2][0]) / num(grand["cells"][3][0]))
    assert {r["key"][0] for r in pv["rows"] if r["key"]} <= {True, False}
    rows = all_rows(api, fields=["ResourceGroupCode", "ResourceGroupId/CapacityUnit"], filters=[{"field": "ResourceGroupCode", "op": "in", "values": [world["g1"]]}])
    assert rows and {r["ResourceGroupId/CapacityUnit"] for r in rows} == {"SAAT"}


@pytest.mark.db
def test_scenario_comes_from_the_request_or_the_user(api, db_engine, world, clean):
    """Dönemler isteğin senaryosundan; verilmezse kullanıcının seçili senaryosu, o da yoksa Baz. Baz'ı izleyen senaryo yalnız farkını tutar."""
    found = horizon_of(db_engine, world["base"])
    efficiency(db_engine, world["follower"], world["r2"], 33, found[0].start, found[0].end)
    one = [{"field": "ResourceGroupCode", "op": "in", "values": [world["g2"]]}, {"field": "Period", "op": "in", "values": [found[0].label]}]
    base_row = all_rows(api, filters=one)[0]
    own_row = all_rows(api, filters=one, scenario_id=world["follower"])[0]
    assert base_row["Efficiency"] == pytest.approx(1.0) and own_row["Efficiency"] < 1 and own_row["TotalCapacity"] == pytest.approx(base_row["TotalCapacity"])
    assert own_row["AvailableCapacity"] < base_row["AvailableCapacity"]
    kept = stored(db_engine, world["follower"])
    assert kept and {k[0] for k in kept} == {world["r2"]} and len(kept) == found[0].days                 # yalnız kendi girişi olan kaynak ve günler
    assert len(stored(db_engine, world["base"])) > 50 * len(kept)
    same_as_scratch(db_engine, world["follower"])
    same_as_scratch(db_engine, world["base"])
    with db_engine.begin() as c:   # kullanıcının seçili senaryosu
        c.execute(sa.text("UPDATE adm.AppUser SET ScenarioDefinitionId = :s WHERE Id = :u"), {"s": world["follower"], "u": world["users"][KEY_USER]})
    try:
        assert all_rows(api, filters=one)[0]["Efficiency"] == pytest.approx(own_row["Efficiency"])
        assert all_rows(api, filters=one, scenario_id=world["base"])[0]["Efficiency"] == pytest.approx(1.0)
        pv = post(api, "/pivot", rows=[{"field": "ResourceGroupCode"}], values=[{"id": "e", "field": "AvailableCapacity", "fn": "sum"}], filters=one, limit=10)
        cell = pv["rows"][0]["cells"][0][0]
        assert (cell["v"] if isinstance(cell, dict) else cell) == pytest.approx(own_row["AvailableCapacity"])
    finally:
        with db_engine.begin() as c:
            c.execute(sa.text("UPDATE adm.AppUser SET ScenarioDefinitionId = NULL WHERE Id = :u"), {"u": world["users"][KEY_USER]})
    # izlemeyen senaryo kendi dönemleriyle ve tam önbellekle
    free_periods = horizon_of(db_engine, world["free"])
    labels = [r["Period"] for r in all_rows(api, scenario_id=world["free"], filters=one[:1], sort=[{"field": "PeriodStart", "dir": "asc"}], fields=["Period"])]
    assert labels == [p.label for p in free_periods]
    assert len(stored(db_engine, world["free"])) == same_as_scratch(db_engine, world["free"])
    assert api.post(U + "/query", json={"scenario_id": 999999999, "limit": 5}).status_code == 404
    end = api.post(U + "/query", json={"limit": 5}, headers=auth(world["users"][END_USER]))               # End user okur
    assert end.status_code == 200 and end.json()["rows"]


@pytest.mark.db
def test_triggers_refresh_only_what_is_affected(db_engine, world, clean):
    """Her tetikleyicide: doğru ana kayıt ve günler yenilenir, başkasına dokunulmaz; önbellek sıfırdan hesaplananla birebir aynı kalır."""
    base, follower, r1, r2 = world["base"], world["follower"], world["r1"], world["r2"]
    found = horizon_of(db_engine, base)
    start, end = found[0].start, found[-1].end
    assert ensure(db_engine, follower) == {base: "built", follower: "built"}
    assert ensure(db_engine, follower) == {base: "ready", follower: "ready"}                              # kuruluysa hiçbir şey yapılmaz
    before = stored(db_engine, base)
    assert before and stored(db_engine, follower) == {}                                                   # izleyen senaryonun kendi girişi yok: satır tutmaz
    same_as_scratch(db_engine, base)
    same_as_scratch(db_engine, follower)

    def changed(a: dict, b: dict) -> set:
        return {k for k in set(a) | set(b) if a.get(k) != b.get(k)}

    # (1) Baz'da kaynağa giriş eklendi: yalnız o kaynak, kaydın tarih aralığı; izleyen senaryo Baz'dan okuduğu için onda da geçerli
    a, b = start + timedelta(days=3), start + timedelta(days=12)
    efficiency(db_engine, base, r1, 77, a, b)
    with Session(db_engine) as s:
        done = cache.invalidate(s, CACHE, base, [r1], a, b)
        s.commit()
    after = stored(db_engine, base)
    diff = changed(before, after)
    assert diff and all(k[0] == r1 and a <= k[1] <= b for k in diff) and set(after) == set(before)
    assert all(after[k][2] == pytest.approx(after[k][1] * 0.77) for k in diff)
    assert done[base] == (b - a).days + 1 and done.get(follower) == 0                                     # izleyen senaryoda yeniden yazılan satır yok (kendi girişi yok)
    assert stored(db_engine, follower) == {}
    same_as_scratch(db_engine, base)
    same_as_scratch(db_engine, follower)

    # (2) izleyen senaryoda başka kaynağa giriş: yalnız o senaryoda, o kaynak ve günler; Baz'a dokunulmaz
    c, d = start + timedelta(days=1), start + timedelta(days=5)
    efficiency(db_engine, follower, r2, 33, c, d)
    with Session(db_engine) as s:
        cache.invalidate(s, CACHE, follower, [r2], c, d)
        s.commit()
    own = stored(db_engine, follower)
    assert set(own) == {(r2, c + timedelta(days=i)) for i in range(5)} and stored(db_engine, base) == after
    same_as_scratch(db_engine, follower)

    # (3) Baz'daki değişiklik izleyen senaryonun kendi satırı olan kaynak ve günleri de yeniler (sonuç Baz girişine de bağlı): başka giriş, aynı kaynak
    efficiency(db_engine, base, r2, 66, c, d)
    with Session(db_engine) as s:
        done = cache.invalidate(s, CACHE, base, [r2], c, d)
        s.commit()
    assert done == {base: 5, follower: 5} and stored(db_engine, follower) == own                          # izleyenin kendi girişi (%33) önceliklidir: değer aynı
    assert changed(after, stored(db_engine, base)) == {(r2, c + timedelta(days=i)) for i in range(5)} - {k for k in own if after[k][1] == 0}
    same_as_scratch(db_engine, base)
    same_as_scratch(db_engine, follower)

    # (4) kaydın tarih aralığı değişti (eski ve yeni aralık), sonra silindi: izleyen senaryonun satırları yeni aralığa taşınır, sonra kalmaz
    with db_engine.begin() as conn:
        conn.execute(sa.text("UPDATE param.ResourceEfficiency SET ValidFrom = :a, ValidTo = :b WHERE ScenarioDefinitionId = :s AND EfficiencyPct = 33"),
                     {"a": d + timedelta(days=2), "b": d + timedelta(days=3), "s": follower})
    with Session(db_engine) as s:
        cache.invalidate(s, CACHE, follower, [r2], c, d + timedelta(days=3))
        s.commit()
    assert set(stored(db_engine, follower)) == {(r2, d + timedelta(days=2)), (r2, d + timedelta(days=3))}
    same_as_scratch(db_engine, follower)
    with db_engine.begin() as conn:
        conn.execute(sa.text("DELETE FROM param.ResourceEfficiency WHERE ScenarioDefinitionId = :s AND EfficiencyPct = 33"), {"s": follower})
    with Session(db_engine) as s:
        cache.invalidate(s, CACHE, follower, [r2])                                                        # tarih verilmezse önbellekteki bütün günler
        s.commit()
    assert stored(db_engine, follower) == {}
    same_as_scratch(db_engine, follower)

    # (5) bütün kaynaklar, belirli günler (fabrika takvimi gibi): yalnız o günler yeniden yazılır; sonuç aynı kalır
    snapshot = stored(db_engine, base)
    with Session(db_engine) as s:
        done = cache.invalidate(s, CACHE, base, None, a, a)
        s.commit()
    assert done[base] == len({k[0] for k in snapshot}) and stored(db_engine, base) == snapshot
    with Session(db_engine) as s:
        assert cache.invalidate(s, CACHE, base, [], a, b) == {base: 0, follower: 0}                       # etkilenen kayıt yoksa iş yok

    # (6) planlama ufku ilerledi: geçmiş gün silinir, yalnız eksik günler hesaplanır; ötekilere dokunulmaz
    with Session(db_engine) as s:
        assert cache.ensure(s, CACHE, follower, start + timedelta(days=1), end + timedelta(days=2))[follower] in ("extended", "trimmed")
    moved = stored(db_engine, base)
    assert {k[1] for k in moved} >= {end + timedelta(days=2)} and min(k[1] for k in moved) == start       # Baz izleyen adına yalnız genişler
    assert all(moved[k] == snapshot[k] for k in snapshot)
    with Session(db_engine) as s:
        assert cache.ensure(s, CACHE, base, start + timedelta(days=1), end + timedelta(days=2))[base] == "trimmed"   # Baz'ın kendi isteği geçmiş günü siler
    assert min(k[1] for k in stored(db_engine, base)) == start + timedelta(days=1)

    # (7) hesap kodunun sürümü ya da veri versiyonu değişti: senaryonun önbelleği baştan kurulur
    with Session(db_engine) as s:
        newer = dataclasses.replace(CACHE, code_version=CACHE.code_version + 1)
        assert cache.ensure(s, newer, base, start, end)[base] == "built"
        assert cache.ensure(s, CACHE, base, start, end)[base] == "built"
        s.execute(sa.text("UPDATE cache.PeriodCacheState SET DataVersionId = -1 WHERE ScenarioDefinitionId = :s"), {"s": base})
        s.commit()
        assert cache.ensure(s, CACHE, base, start, end)[base] == "built"
        assert cache.ensure(s, CACHE, base, start, end)[base] == "ready"
    same_as_scratch(db_engine, base)


@pytest.mark.db
def test_scenario_lifecycle_and_commands(db_engine, world, clean, capsys):
    """Yeni senaryonun önbelleği ilk kullanımda kurulur; pasif yapılınca, Baz'dan ayrılınca ve silinince düşer. Yönetim komutu."""
    with Session(db_engine) as s:
        new = scenarios.create_copy(s, "pytest dönem önbelleği", world["base"], follows_base=True)
        s.commit()
        sid = new["Id"]
    try:
        found = horizon_of(db_engine, sid)
        efficiency(db_engine, sid, world["r1"], 44, found[0].start, found[0].end)
        assert ensure(db_engine, sid)[sid] == "built" and len(stored(db_engine, sid)) == found[0].days
        with Session(db_engine) as s:
            scenarios.detach(s, sid)                                    # Baz'dan ayır: artık tamamını kendisi tutar; baştan kurulur
            s.commit()
        assert stored(db_engine, sid) == {}
        assert ensure(db_engine, sid) == {sid: "built"} and len(stored(db_engine, sid)) == same_as_scratch(db_engine, sid) > 100
        with Session(db_engine) as s:
            scenarios.set_active(s, sid, False)                         # pasif senaryonun önbelleği tutulmaz
            s.commit()
        assert stored(db_engine, sid) == {}
        assert ensure(db_engine, sid) == {sid: "built"}
    finally:
        with Session(db_engine) as s:
            scenarios.delete(s, sid)
            s.commit()
    assert stored(db_engine, sid) == {}
    with db_engine.connect() as c:
        assert c.execute(sa.text("SELECT COUNT(*) FROM cache.PeriodCacheState WHERE ScenarioDefinitionId = :s"), {"s": sid}).scalar() == 0
    ensure(db_engine, world["base"])
    assert periods_cli(["status"]) == 0 and f"senaryo {world['base']}" in capsys.readouterr().out
    assert periods_cli(["drop", "--scenario", str(world["base"])]) == 0 and stored(db_engine, world["base"]) == {}
    assert periods_cli(["rebuild", "--scenario", str(world["base"])]) == 0
    out = capsys.readouterr().out
    assert "kuruldu" in out and same_as_scratch(db_engine, world["base"]) == len(stored(db_engine, world["base"]))


@pytest.mark.db
def test_excel_carries_the_scenario(api, db_engine, world, clean):
    found = horizon_of(db_engine, world["follower"])
    r = api.post(U + "/export", json={"fields": ["ResourceGroupCode", "Period", "TotalCapacity"], "scope": {"rows": "all"}, "scenario_id": world["follower"],
                                      "sort": [{"field": "ResourceGroupCode", "dir": "asc"}, {"field": "Period", "dir": "asc"}]})
    assert r.status_code == 200, r.text
    wb = load_workbook(io.BytesIO(r.content))
    info = {row[0].value: row[1].value for row in wb[wb.sheetnames[-1]].iter_rows() if row[0].value}
    with db_engine.connect() as c:
        name = c.execute(sa.text("SELECT Name FROM param.ScenarioDefinition WHERE Id = :s"), {"s": world["follower"]}).scalar()
    assert info["Senaryo"] == name
    data = [[c.value for c in row] for row in wb[wb.sheetnames[0]].iter_rows(min_row=2)]
    first = data[0][0]
    assert [row[1] for row in data if row[0] == first] == [p.label for p in found]                       # dönemler dosyada da tarih sırasıyla
    std = api.get(U + "/columns").json()["standard_pivot"]
    r = api.post(U + "/pivot/export", json={"rows": std["rows"], "columns": std["columns"], "values": std["values"], "values_on": "rows", "names": {},
                                            "totals": std["totals"], "scenario_id": world["base"]})
    assert r.status_code == 200, r.text
    wb = load_workbook(io.BytesIO(r.content))
    assert [c.value for c in wb["Pivot"][1]][2:2 + len(found)] == [p.label for p in horizon_of(db_engine, world["base"])]
    info = {row[0].value: row[1].value for row in wb["Bilgi"].iter_rows() if row[0].value}
    assert info["Senaryo"] == "Baz" and "Kaynak sayısı · Son dönem değeri" in info["Değerler"]
    counts = defaultdict(int)
    for row in wb["Pivot"].iter_rows(min_row=3):
        counts[row[1].value] += 1
    assert counts["Kaynak sayısı · Son dönem değeri"] > 1
