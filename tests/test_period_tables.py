"""Dönem tablosu altyapısı (K-184, geliştirme 7.8) ve Kaynak grubu × dönem (K-185, 7.9a): ortak dönem listesi, dönem tablosu listesi, sıralama,
İlk · Son dönem değeri, senaryo, gruplama, Excel. Sentetik v0'da (Smartchain_test); kendi yazdığını geri alır. Hesabın, çözümlemenin ve
tetikleyicilerin testleri `tests/test_capacity.py`'dedir.

Sabitlenenler: dönem alanları her yerde Dönem başı'na göre sıralanır; Son dönem değeri zaman içinde toplanmaz, kayıtlar arasında toplanır;
her tetikleyicide yalnız etkilenen ana kayıt ve günler yenilenir ve önbellekteki sonuç sıfırdan hesaplananla birebir aynıdır (motorun yolu).
"""
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
from app.params import horizon
from app.capacity import compute
from app.data.synthetic import capacity as reference
from app.data.synthetic.dataset import generate
from app.periods import cache, periods as period_list

from auth_helpers import auth, ensure_user

U = "/api/period-resource-group"
CACHE = compute.CACHE
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
        rows = {r[3]: r for r in c.execute(sa.text(
            "SELECT m.ResourceId, g.Id, g.Code, r.Code FROM core.ResourceGroupMember m JOIN core.ResourceGroup g ON g.Id = m.ResourceGroupId AND g.VersionTo IS NULL "
            "JOIN core.Resource r ON r.Id = m.ResourceId AND r.VersionTo IS NULL WHERE m.VersionTo IS NULL"))}
    assert base and follower and free
    r1, r2 = rows["M3-01"], rows["M3-03"]     # ISL3: grup düzeyinde çalışma düzeni, tek gruba üye; sentetik senaryo farklarından etkilenmez
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
        c.execute(sa.text("INSERT INTO param.ResourceEfficiency (ScenarioDefinitionId, ResourceId, ValidFrom, ValidTo, EfficiencyPct, UpdatedAt) "
                          "VALUES (:s, :r, :a, :b, :p, SYSUTCDATETIME())"),
                  {"s": scenario_id, "r": resource_id, "a": start, "b": end, "p": pct})


def stored(db_engine, scenario_id) -> dict:
    """Önbellek tablosundaki satırlar (senaryonun kendi tuttukları)."""
    with db_engine.connect() as c:
        rows = c.execute(sa.text("SELECT ResourceId, [Date], ResourceGroupId, WorkingDay, Capacity, AvailableCapacity FROM cache.ResourceCapacityDay "
                                 "WHERE ScenarioDefinitionId = :s"), {"s": scenario_id}).all()
    return {(r[0], r[1], r[2]): (float(r[3]), float(r[4]), float(r[5])) for r in rows}


def same_as_scratch(db_engine, scenario_id) -> int:
    """Önbellekteki geçerli sonuç, girişlerden sıfırdan hesaplananla (motorun yolu) birebir aynı. Dönen: satır sayısı."""
    found = horizon_of(db_engine, scenario_id)
    with Session(db_engine) as s:
        key = lambda r: (r["ResourceId"], r["ResourceGroupId"], r["Date"], *[float(r[v]) for v in CACHE.values])  # noqa: E731
        cached = sorted(key(r) for r in compute.cached(s, scenario_id, found[0].start, found[-1].end))
        scratch = sorted(key(r) for r in P.values(s, CACHE.name, scenario_id, found[0].start, found[-1].end))
    assert cached == scratch
    return len(cached)


def ensure(db_engine, scenario_id) -> dict:
    found = horizon_of(db_engine, scenario_id)
    with Session(db_engine) as s:
        return cache.ensure(s, CACHE, scenario_id, found[0].start, found[-1].end)


@pytest.mark.db
def test_rows_fields_and_values(api, db_engine, world, clean):
    """Satır = kaynak grubu × senaryonun dönemi; dokuz dönem alanı aynı ad ve sırayla; değerler girişlerden bağımsız (Python) hesapla tutar."""
    cols = api.get(U + "/columns").json()
    names = [c["field"] for c in cols["columns"]]
    at = names.index("PeriodType")
    assert names[at:at + 9] == PERIOD_FIELDS and names[:4] == ["LocationCode", "ResourceGroupCode", "ResourceGroupName", "CapacityUnit"]
    assert [c["label"] for c in cols["columns"][at:at + 9]] == ["Dönem tipi", "Dönem", "Dönem başı", "Dönem sonu", "Hafta", "Ay", "Çeyrek", "Yıl", "Dönem takvim günü"]
    assert names[at + 9:] == ["ResourceCount", "WorkingDays", "Downtime", "WorkableDays", "AvgDailyCapacity", "TotalDailyCapacity", "Efficiency", "TotalCapacity",
                              "AvailableCapacity", "OvertimeLimit", "RemainingOvertimeMonth", "RemainingOvertimeYear"]
    by = {c["field"]: c for c in cols["columns"]}
    assert all(by[f]["order_by"] == "PeriodStart" for f in ("PeriodType", "Period", "Week", "Month", "Quarter", "Year")) and by["PeriodStart"]["order_by"] is None
    assert cols["period_table"] is True and cols["standard_pivot"]["columns"] == [{"field": "Period"}] and cols["standard_pivot"]["values_on"] == "rows"
    assert [v["field"] for v in cols["standard_pivot"]["values"]] == ["TotalCapacity", "AvailableCapacity", "Downtime"]
    assert [c["name"] for c in cols["calculated_values"]] == ["Duruş oranı", "Kullanılabilirlik"] and cols["relations"] == [{"path": "ResourceGroupId", "label": "Kaynak grubu"}]
    # varsayılan hesaplamalar tek yerde (K-185 E): sayı ve ERP'nin kalan fazla mesaisi Son dönem değeri; günlük kapasiteler ortalama; verimlilik ağırlıklı
    assert {f: by[f]["aggregate"] for f in ("ResourceCount", "AvgDailyCapacity", "TotalDailyCapacity", "Efficiency", "RemainingOvertimeMonth", "TotalCapacity")} == {
        "ResourceCount": "last", "AvgDailyCapacity": "avg", "TotalDailyCapacity": "avg", "Efficiency": "wavg", "RemainingOvertimeMonth": "last", "TotalCapacity": "sum"}
    assert by["Efficiency"]["aggregate_weight"] == "TotalCapacity"

    found = horizon_of(db_engine, world["base"])
    rows = all_rows(api)
    ds = generate(date.today())
    daily = reference.daily(ds, found[0].start, found[-1].end)
    groups = {g["Id"]: g["Code"] for g in ds.rows("ResourceGroup")}
    assert len(rows) == len(groups) * len(found) and len({r["Id"] for r in rows}) == len(rows)     # verisi olmayan dönem de satır; kimlik tekil
    period_of = {}
    for p in found:
        day = p.start
        while day <= p.end:
            period_of[day] = p.label
            day += timedelta(days=1)
    want: dict = defaultdict(lambda: defaultdict(float))
    worked: dict = defaultdict(set)
    for (g, _r, day), v in daily.items():
        key = (groups[g], period_of[day])
        for f in ("WorkingDay", "Downtime", "Capacity", "AvailableCapacity", "OvertimeLimit"):
            want[key][f] += v[f]
        want[key]["Gross"] += v["WorkingDay"] * v["DailyCapacity"]
        if v["WorkingDay"] > 0:
            worked[key].add(day)
    members = defaultdict(set)
    for m in ds.rows("ResourceGroupMember"):
        members[groups[m["ResourceGroupId"]]].add(m["ResourceId"])
    checked = 0
    for r in rows:
        key = (r["ResourceGroupCode"], r["Period"])
        w = want.get(key, {})
        assert r["ResourceCount"] == len(members[r["ResourceGroupCode"]])
        assert r["WorkingDays"] == pytest.approx(w.get("WorkingDay", 0)) and r["Downtime"] == pytest.approx(w.get("Downtime", 0), abs=1e-3), key
        assert r["WorkableDays"] == pytest.approx(w.get("WorkingDay", 0) - w.get("Downtime", 0), abs=1e-3)
        assert r["TotalCapacity"] == pytest.approx(w.get("Capacity", 0), abs=0.01) and r["AvailableCapacity"] == pytest.approx(w.get("AvailableCapacity", 0), abs=0.01), key
        assert r["OvertimeLimit"] == pytest.approx(w.get("OvertimeLimit", 0), abs=0.01)
        if w.get("WorkingDay"):
            assert r["AvgDailyCapacity"] == pytest.approx(w["Gross"] / w["WorkingDay"], abs=1e-3)                 # kaynak başına, çalışma günüyle ağırlıklı
            assert r["TotalDailyCapacity"] == pytest.approx(w["Gross"] / len(worked[key]), abs=1e-3)             # grubun toplamı, çalışılan günlerin ortalaması
            assert r["Efficiency"] == pytest.approx(w["Capacity"] / w["Gross"], abs=1e-4) if w["Gross"] else r["Efficiency"] is None
            checked += 1
        else:
            assert r["AvgDailyCapacity"] is None and r["TotalDailyCapacity"] is None and r["Efficiency"] is None
    assert checked > len(found) * 5
    first = found[0]
    line = next(r for r in rows if r["ResourceGroupCode"] == world["g1"] and r["Period"] == first.label)
    assert [line[f] for f in PERIOD_FIELDS] == [first.type, first.label, first.start.isoformat(), first.end.isoformat(), first.week, first.month, first.quarter,
                                                first.year, first.days]
    # bilerek konmuş durumlar: üç tezgâh × 15 saat (ISL3) → ortalama 15, toplam 45; TASLAMA'da verimlilik %85; çalışma düzeni olmayan grup 0
    isl3 = next(r for r in rows if r["ResourceGroupCode"] == "ISL3" and r["Period"] == found[1].label)
    assert (isl3["AvgDailyCapacity"], isl3["TotalDailyCapacity"]) == (pytest.approx(15.0), pytest.approx(45.0))
    assert next(r for r in rows if r["ResourceGroupCode"] == "TASLAMA" and r["Period"] == found[1].label)["Efficiency"] == pytest.approx(0.85)
    kapla = next(r for r in rows if r["ResourceGroupCode"] == "F-KAPLA" and r["Period"] == found[1].label)
    assert (kapla["ResourceCount"], kapla["WorkingDays"], kapla["TotalCapacity"], kapla["Efficiency"]) == (1, 0, 0, None)
    # ERP'nin kalan fazla mesaisi: kaynakların toplamı, her dönemde aynı
    months = {r["RemainingOvertimeMonth"] for r in rows if r["ResourceGroupCode"] == "CG-MON"}
    assert len(months) == 1


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
    """Ana kayıt üzerinden ilişkili alan (satır, filtre); verimlilik toplamda kapasiteyle ağırlıklı; hazır oranlar toplamlardan."""
    found = horizon_of(db_engine, world["base"])
    efficiency(db_engine, world["base"], world["r1"], 77, found[0].start, found[1].end)
    values = [{"id": "e", "field": "Efficiency", "fn": "wavg", "weight": "TotalCapacity"}, {"id": "avg", "field": "Efficiency", "fn": "avg"},
              {"id": "a", "field": "AvailableCapacity", "fn": "sum"}, {"id": "t", "field": "TotalCapacity", "fn": "sum"},
              {"id": "x", "kind": "calc", "a": "a", "op": "div", "b": "t", "percent": True},
              {"id": "ad", "field": "AvgDailyCapacity", "fn": "avg"}, {"id": "td", "field": "TotalDailyCapacity", "fn": "avg"}]
    pv = post(api, "/pivot", rows=[{"field": "ResourceGroupId/IsCritical"}, {"field": "ResourceGroupCode"}], values=values,
              totals={"rows": True, "columns": False, "subtotals": True}, limit=100, filters=[{"field": "ResourceGroupId/CapacityUnit", "op": "equals", "value": "SAAT"}])
    num = lambda c: c["v"] if isinstance(c, dict) else c  # noqa: E731
    row = next(r for r in pv["rows"] if r["key"][1:] == [world["g1"]])
    one = all_rows(api, filters=[{"field": "ResourceGroupCode", "op": "in", "values": [world["g1"]]}], fields=["Efficiency", "TotalCapacity", "AvgDailyCapacity"])
    weighted = sum(r["Efficiency"] * r["TotalCapacity"] for r in one if r["Efficiency"] is not None) / sum(r["TotalCapacity"] for r in one)
    assert num(row["cells"][0][0]) < 1 and num(row["cells"][0][0]) == pytest.approx(weighted)             # kapasiteyle ağırlıklı ortalama
    plain = [r["Efficiency"] for r in one if r["Efficiency"] is not None]
    assert num(row["cells"][1][0]) == pytest.approx(sum(plain) / len(plain)) and num(row["cells"][1][0]) != pytest.approx(weighted)
    assert num(row["cells"][4][0]) == pytest.approx(num(row["cells"][2][0]) / num(row["cells"][3][0]))    # kullanılabilirlik toplamlardan
    daily = [r["AvgDailyCapacity"] for r in one if r["AvgDailyCapacity"] is not None]
    assert num(row["cells"][5][0]) == pytest.approx(sum(daily) / len(daily)) == pytest.approx(15.0)       # günlük kapasite toplanmaz: ortalama
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
    assert base_row["Efficiency"] == pytest.approx(1.0) and own_row["Efficiency"] < 1 and own_row["TotalCapacity"] < base_row["TotalCapacity"]
    assert own_row["AvailableCapacity"] < base_row["AvailableCapacity"] and own_row["WorkingDays"] == base_row["WorkingDays"]
    kept = stored(db_engine, world["follower"])
    mine = {k for k in kept if k[0] == world["r2"]}
    # izleyen senaryo yalnız Baz'dan farklı çıkan satırları tutar: bu kaynakta girişin kapsadığı çalışılan günler (çalışılmayan günde sonuç aynı)
    assert mine and all(found[0].start <= k[1] <= found[0].end and k[1].weekday() < 5 for k in mine) and len(mine) <= found[0].days
    assert len(stored(db_engine, world["base"])) > len(kept)
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
    assert len(stored(db_engine, world["free"])) == same_as_scratch(db_engine, world["free"])              # izlemeyen senaryo tamamını kendisi tutar
    assert api.post(U + "/query", json={"scenario_id": 999999999, "limit": 5}).status_code == 404
    end = api.post(U + "/query", json={"limit": 5}, headers=auth(world["users"][END_USER]))               # End user okur
    assert end.status_code == 200 and end.json()["rows"]


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
    assert info["Senaryo"] == "Baz" and "Toplam kapasite · Toplam" in info["Değerler"]
    counts = defaultdict(int)
    for row in wb["Pivot"].iter_rows(min_row=3):
        counts[row[1].value] += 1
    assert counts["Toplam kapasite · Toplam"] > 1 and counts["Duruş · Toplam"] == counts["Toplam kapasite · Toplam"]


@pytest.mark.db
def test_grouping_by_every_period_and_master_field(api, db_engine, world, clean):
    """Tablodaki gruplama (7.8 demo bulgusu): her dönem alanı ve ana kayıt alanıyla; ara toplamlar ve sıralama. Arayüzün gönderdiği gövdeyle:
    görünen bütün alanlar ve varsayılan ara toplamlar. Ağırlıklı ortalamada ağırlık verilmezse liste tanımının ağırlık alanı kullanılır."""
    found = horizon_of(db_engine, world["base"])
    efficiency(db_engine, world["base"], world["r1"], 77, found[0].start, found[1].end)
    names = [c["field"] for c in api.get(U + "/columns").json()["columns"]]
    sent = {"WorkingDays": {"fn": "sum"}, "TotalCapacity": {"fn": "sum"}, "AvailableCapacity": {"fn": "sum"}, "Efficiency": {"fn": "wavg"}}   # ağırlıksız: ilk demo gövdesi
    weight = lambda g: g["aggregates"]["TotalCapacity"]  # noqa: E731
    order = {"Month": [p.month for p in found], "Period": [p.label for p in found], "Week": [p.week for p in found], "Quarter": [p.quarter for p in found],
             "Year": [p.year for p in found], "PeriodType": [p.type for p in found]}
    totals = all_rows(api, fields=["TotalCapacity", "AvailableCapacity"])
    capacity = sum(r["TotalCapacity"] for r in totals)
    for field in ("Month", "Period", "Week", "Quarter", "Year", "PeriodType", "PeriodStart", "PeriodEnd", "PeriodDays", "ResourceGroupCode", "ResourceGroupName", "CapacityUnit"):
        out = post(api, "/groups", group_by=[field], fields=names, aggregates=sent, filters=[], sort=[])
        groups = out["groups"]
        assert groups and sum(g["count"] for g in groups) == len(totals), field
        assert out["aggregate_specs"]["Efficiency"] == {"fn": "wavg", "weight": "TotalCapacity"}
        if field in order:
            assert [g["key"][0] for g in groups] == list(dict.fromkeys(order[field])), field                 # dönem başına göre
        if field != "CapacityUnit" or len(groups) == 1:
            got = sum((g["aggregates"]["TotalCapacity"] or 0) for g in groups)
            assert got == pytest.approx(capacity), field                                                       # ara toplamlar kayıtlarla tutar
        for g in groups:
            assert (g["aggregates"]["Efficiency"] is None) == (not weight(g)), field                           # verimlilik kapasiteyle ağırlıklı: kapasite yoksa boş
    # iki düzey ve azalan sıralama; grubun satırları
    out = post(api, "/groups", group_by=["Month", "ResourceGroupCode"], fields=names, aggregates=sent, filters=[], sort=[{"field": "Month", "dir": "desc"}])
    months = list(dict.fromkeys(p.month for p in found))
    assert [g["key"][0] for g in out["groups"]] == months[::-1] and all(len(g["children"]) > 1 for g in out["groups"])
    first = out["groups"][0]
    rows = post(api, "/query", limit=100, group_key=[{"field": "Month", "value": first["key"][0]}, {"field": "ResourceGroupCode", "value": first["children"][0]["key"][-1]}])
    assert rows["filtered"] == first["children"][0]["count"] == len(rows["rows"])
    # arayüz varsayılanlarını göndermezse: sunucunun varsayılanı (Son dönem değeri gruplamada yok)
    plain = post(api, "/groups", group_by=["Month"], fields=names)
    assert set(plain["aggregate_specs"]) == {"WorkingDays", "Downtime", "WorkableDays", "AvgDailyCapacity", "TotalDailyCapacity", "Efficiency", "TotalCapacity",
                                             "AvailableCapacity", "OvertimeLimit"}                           # Son dönem değeri gruplamada yok


@pytest.mark.db
def test_label_chart_value_and_merged_period_headers_in_excel(api, db_engine, world, clean):
    """K-186: "Çalışılabilir gün"; grafik ilk açılışta Kullanılabilir kapasite; Ay › Dönem'de aylık dönemin iki başlığı Excel'de tek hücre."""
    cols = api.get(U + "/columns").json()
    assert {c["field"]: c["label"] for c in cols["columns"]}["WorkableDays"] == "Çalışılabilir gün" and cols["chart_value"] == "AvailableCapacity"
    found = horizon_of(db_engine, world["base"])
    monthly = [p.label for p in found if p.type == "Ay"]
    weekly_months = {p.month for p in found if p.type == "Hafta"}
    assert monthly and weekly_months
    body = {"rows": [{"field": "ResourceGroupCode"}], "columns": [{"field": "Month"}, {"field": "Period"}],
            "values": [{"id": "d1", "field": "TotalCapacity", "fn": "sum"}], "values_on": "rows", "scenario_id": world["base"]}
    r = api.post(U + "/pivot/export", json=body)
    assert r.status_code == 200, r.text
    ws = load_workbook(io.BytesIO(r.content))["Pivot"]
    merged = {str(m): m for m in ws.merged_cells.ranges}
    top = {ws.cell(1, c).value: c for c in range(3, ws.max_column + 1) if ws.cell(1, c).value}
    for label in monthly:                                   # aylık dönem: üstte ve altta aynı yazı → iki satır tek hücre
        column = top[label]
        letter = ws.cell(1, column).column_letter
        assert f"{letter}1:{letter}2" in merged and ws.cell(2, column).value is None
    weekly = next(m for m in weekly_months if m in top)     # haftaları olan ay: üstte ay (haftaları boyunca), altta haftalar
    assert ws.cell(2, top[weekly]).value.startswith("H") and not any(m.min_row == 1 and m.max_row == 2 and m.min_col == top[weekly] for m in merged.values())
    assert "A4:A4" not in merged and ws["A4"].value                                                  # tek değer satırı: birleşme gerekmez
