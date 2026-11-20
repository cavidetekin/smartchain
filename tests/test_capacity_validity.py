"""Kapasite yönetimi, 7.9c (K-188): geçerlilik aralıkları ve listeleri, Bakım ve duruşlar'da "Gün", aktarım tetikleyicisi, yetim kayıt uyarısı,
ufuk ucu ve motorun dönem değerleri. Sentetik v0'da (Smartchain_test); kendi senaryolarını açar, yazdığını geri alır.

Sabitlenenler: geçerlilik aralıkları kuralı uygular (önce seviye, sonra başlangıcı en ileri olan; geçici kayıt bitince öncekine dönüş: mockup
örneği) ve günlük hesapla tutarlıdır; "Gün" çalışma düzeninden; aktarım yalnız etkilenen kaynakları yeniler ve önbelleği yeni veri versiyonuna
çeker (tam kurulum yok); kapanan kaynağa girilmiş kayıt uyarıdır.
"""
from datetime import date, timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.capacity import compute, triggers, validity
from app.engine.data import SqlPlanningData
from app.params import resolve
from app.quality import run as quality_run

from test_capacity import (CACHE, KEY, _sql, calc, changed, clean, days, delete, diff, ensure, pattern, row, same_as_scratch, stored, working_days,  # noqa: F401
                           world)
from test_capacity_entries import api, people, rows  # noqa: F401  (fixture'lar)

pytestmark = pytest.mark.db

WP = "capacity-work-patterns-validity"
DAY_NUMBER = {"Tam": 1.0, "Yarım": 0.5, "—": 0.0}


def of(api, name: str, scenario: int, key: str) -> list[dict]:  # noqa: F811
    return rows(api, name, scenario, filters=[{"field": "OwnerKeys", "op": "contains", "value": key}],
                sort=[{"field": "Code", "dir": "asc"}, {"field": "ValidFrom", "dir": "asc"}])


def spans(found: list[dict], field: str = "DailyCapacity") -> list[tuple]:
    return [(r["ValidFrom"], r["ValidTo"], float(r[field])) for r in found]


def iso(day: date | None) -> str | None:
    return day.isoformat() if day else None


def intervals(db_engine, kind: str, scenario: int, base: int | None) -> list[dict]:
    table, fields = validity.KINDS[kind]
    with db_engine.connect() as c:
        return [dict(r) for r in c.execute(sa.text(validity.intervals_sql(table, fields)), {"sid": scenario, "base": base}).mappings()]


def test_validity_follows_the_rule_like_the_mockup(api, db_engine, world, clean):  # noqa: F811
    """Mockup örneği: grubun süresiz kaydı; kaynağa geçici kayıt; gruba geçici kayıt. Kaynağın kaydı grubunkinden önce gelir, bitince grubun o gün
    geçerli kaydına (başlangıcı en ileri olana), o da bitince süresiz kayda dönülür. İzleyen senaryoda geçersiz yapılan kayıt hesaba girmez."""
    base, follower, g1, r1, r2 = world["base"], world["follower"], world["g1"], world["r1"], world["r2"]
    before = of(api, WP, base, f",r{r1},")
    assert len(before) == 1 and before[0]["ValidTo"] is None and before[0]["SourceRecord"].startswith("Grup ")   # sentetik: grubun süresiz kaydı
    first, usual = date.fromisoformat(before[0]["ValidFrom"]), float(before[0]["DailyCapacity"])
    a = world["start"] + timedelta(days=20)
    b, c, e = a + timedelta(days=30), a + timedelta(days=9), a + timedelta(days=50)
    own = pattern(db_engine, base, a, b, 24, ResourceId=r1)
    pattern(db_engine, base, c, e, 20, ResourceGroupId=g1)

    got = of(api, WP, base, f",r{r1},")
    assert spans(got) == [(iso(first), iso(a - timedelta(days=1)), usual), (iso(a), iso(b), 24.0), (iso(b + timedelta(days=1)), iso(e), 20.0),
                          (iso(e + timedelta(days=1)), None, usual)]
    code = got[0]["Code"]
    group = got[0]["GroupCode"]
    assert [r["SourceRecord"] for r in got] == [f"Grup {group} · {first:%d.%m.%Y}", f"Kaynak {code} · {a:%d.%m.%Y}", f"Grup {group} · {c:%d.%m.%Y}",
                                                f"Grup {group} · {first:%d.%m.%Y}"]
    assert got[1]["SourceSpan"] == f"Kaynak {code} · {a:%d.%m.%Y} – {b:%d.%m.%Y}" and got[0]["SourceSpan"] == f"Grup {group} · {first:%d.%m.%Y}'dan itibaren"
    assert got[0]["SourceRowId"] == got[3]["SourceRowId"] != got[1]["SourceRowId"] == own and got[0]["CapacityUnit"]
    # zaman çubuğunun iki rengi ve fark işareti bu alanlardan: kaydın seviyesi ve kaynağı
    assert [r["SourceLevel"] for r in got] == ["Grup", "Kaynak", "Grup", "Grup"] and {r["SourceOrigin"] for r in got} == {"Baz"}
    assert spans(of(api, WP, base, f",r{r2},")) == [(iso(first), iso(c - timedelta(days=1)), usual), (iso(c), iso(e), 20.0), (iso(e + timedelta(days=1)), None, usual)]
    # grup kartı: grubun bütün kaynakları
    assert {r["Code"] for r in of(api, WP, base, f",g{g1},")} >= {code, of(api, WP, base, f",r{r2},")[0]["Code"]}

    # izleyen senaryo Baz'dan okur; kaynağın kaydını kendisi için geçersiz yapınca o aralık grubun kayıtlarına kalır
    assert spans(of(api, WP, follower, f",r{r1},")) == spans(got)
    changed_here = diff(db_engine, "WorkPattern", follower, own, DailyCapacity=30)       # izleyen senaryo kaydın değerini değiştirdi: senaryo farkı
    theirs = of(api, WP, follower, f",r{r1},")
    assert [(float(r["DailyCapacity"]), r["SourceOrigin"]) for r in theirs] == [(usual, "Baz"), (30.0, "Senaryo farkı"), (20.0, "Baz"), (usual, "Baz")]
    delete(db_engine, "WorkPattern", changed_here)
    diff(db_engine, "WorkPattern", follower, own, IsValid=0)
    assert spans(of(api, WP, follower, f",r{r1},")) == spans(of(api, WP, follower, f",r{r2},"))
    assert spans(of(api, WP, base, f",r{r1},")) == spans(got)

    # End user görür; yazma ucu yok (salt okunur liste)
    cols = api.get(f"/api/{WP}/columns").json()
    assert [c["field"] for c in cols["columns"]][:6] == ["LocationCode", "GroupCode", "Code", "ValidFrom", "ValidTo", "DailyCapacity"]

    # görünüm zaman çubuğunun yüksekliğini ve yakınlaştırmasını saklar (K-188); sınır dışı değer reddedilir
    definition = {"v": 1, "columns": [{"field": "Code"}, {"field": "ValidFrom"}], "above": {"height": 0.3, "zoom": 2}}
    made = api.post(f"/api/{WP}/views", json={"name": "pytest geçerlilik", "is_shared": False, "definition": definition})
    assert made.status_code == 201, made.text
    try:
        saved = next(v for v in api.get(f"/api/{WP}/views").json()["views"] if v["name"] == "pytest geçerlilik")
        assert saved["definition"]["above"] == {"height": 0.3, "zoom": 2}
        bad = api.post(f"/api/{WP}/views", json={"name": "pytest geçerlilik 2", "is_shared": False, "definition": {**definition, "above": {"height": 0.3, "zoom": 99}}})
        assert bad.status_code == 422
    finally:
        with db_engine.begin() as c:
            _sql(c, "DELETE FROM adm.TableView WHERE Name LIKE N'pytest geçerlilik%'")


def test_validity_matches_the_daily_computation(db_engine, world, clean):  # noqa: F811
    """Geçerlilik aralıkları günlük hesapla tutarlı (ayrı hesap yok): ufkun her gününde, her üyelikte günlük kapasite ve günün çalışma değeri,
    o günü kapsayan aralığın değeridir; aralık yoksa 0. Aralıklar üyelik başına örtüşmez."""
    base, g1, r1 = world["base"], world["g1"], world["r1"]
    a = world["start"] + timedelta(days=10)
    pattern(db_engine, base, a, a + timedelta(days=12), 9, ResourceId=r1, DaySat=1)
    pattern(db_engine, base, a + timedelta(days=5), a + timedelta(days=40), 11, ResourceGroupId=g1)
    pattern(db_engine, base, a + timedelta(days=5), None, 12, ResourceGroupId=g1, DayFri=0.5)      # aynı başlangıç: son girilen geçerli
    found = intervals(db_engine, "work-patterns", base, None)
    by: dict[tuple, list[dict]] = {}
    for r in found:
        by.setdefault((r["ResourceId"], r["ResourceGroupId"]), []).append(r)
    for parts in by.values():
        parts.sort(key=lambda r: r["ValidFrom"])
        for prev, nxt in zip(parts, parts[1:]):
            assert prev["ValidTo"] is not None and prev["ValidTo"] < nxt["ValidFrom"]
    daily = calc(db_engine, base, world["start"], world["end"])
    assert daily and {(g, r) for r, g, _d in daily} == world["members"] and {(g, r) for r, g in by} <= world["members"]
    checked = 0
    for (res, grp, day), v in daily.items():
        part = next((p for p in by.get((res, grp), []) if p["ValidFrom"] <= day and (p["ValidTo"] is None or p["ValidTo"] >= day)), None)
        expected = (float(part["DailyCapacity"]), float(part[resolve.DAYS[day.weekday()]])) if part else (0.0, 0.0)
        assert (v["DailyCapacity"], v["WorkingDay"]) == expected, (res, grp, day)
        checked += 1
    assert checked == len(world["members"]) * ((world["end"] - world["start"]).days + 1)
    # verimlilik ve ek mesai limiti de aynı işlevden: kayıt olmayan üyelik satır değildir
    for kind in ("efficiency", "overtime-limits"):
        for r in intervals(db_engine, kind, base, None):
            assert r["RowId"] is not None and (r["ValidTo"] is None or r["ValidTo"] >= r["ValidFrom"])


def test_lost_days_of_downtime(api, db_engine, world, clean):  # noqa: F811
    """"Gün": kaydın aralığındaki çalışma günü değerlerinin toplamı (çalışma düzeninden). Kaynak kaydı, grup kaydı (kaynakların ortalaması), süren
    çalışma düzeni değişince iki aralığın toplamı; çalışan izninde günlük saat ÷ günlük kapasite."""
    base, g1, r1 = world["base"], world["g1"], world["r1"]
    week = of(api, WP, base, f",r{r1},")[0]
    per_week = sum(DAY_NUMBER[week[d]] for d in resolve.DAYS)
    monday = world["start"] + timedelta(days=(7 - world["start"].weekday()) % 7 + 14)
    one = row(db_engine, "ResourceDowntime", base, ResourceId=r1, StartDate=monday, EndDate=monday + timedelta(days=13), DowntimeType="Planlı bakım", Reason="pytest gün")
    grp = row(db_engine, "ResourceDowntime", base, ResourceGroupId=g1, StartDate=monday + timedelta(days=2), EndDate=monday + timedelta(days=2), DowntimeType="Arıza",
              Reason="pytest gün grup")
    found = {r["Id"]: r for r in rows(api, "capacity-downtime", base, filters=[{"field": "OwnerKeys", "op": "contains", "value": f",g{g1},"}])}
    assert float(found[one]["LostDays"]) == 2 * per_week
    assert float(found[grp]["LostDays"]) == DAY_NUMBER[week[resolve.DAYS[2]]]
    # kaynağa ikinci haftadan itibaren hafta sonu da tam çalışılan düzen: ilk hafta eski düzen, ikinci hafta yedi gün
    pattern(db_engine, base, monday + timedelta(days=7), None, float(week["DailyCapacity"]), ResourceId=r1, DaySat=1, DaySun=1)
    found = {r["Id"]: r for r in rows(api, "capacity-downtime", base, filters=[{"field": "OwnerKeys", "op": "contains", "value": f",r{r1},"}])}
    assert float(found[one]["LostDays"]) == per_week + 7
    cols = {c["field"]: c for c in api.get("/api/capacity-downtime/columns").json()["columns"]}
    assert cols["LostDays"]["label"] == "Gün" and list(cols).index("LostDays") == list(cols).index("EndDate") + 1
    # çalışan izni (ERP): günlük saat kapasitenin yarısı → yarım gün
    (day,) = working_days(db_engine, world, 1, r1)
    with db_engine.begin() as c:
        _sql(c, "INSERT INTO core.EmployeeAbsence (Id, LocationId, ResourceId, AbsenceType, StartDate, EndDate, HoursPerDay, VersionFrom, BusinessKey, UpdatedAt) "
                "VALUES (9900020, :l, :r, N'İzin', :d, :d, :h, :v, :k, SYSUTCDATETIME())", l=world["location"], r=r1, d=day, h=float(week["DailyCapacity"]) / 2,
             v=world["version"], k=KEY + "-gun")
    try:
        leave = next(r for r in rows(api, "capacity-downtime", base, filters=[{"field": "OwnerKeys", "op": "contains", "value": f",r{r1},"}]) if r["Id"] == -9900020)
        assert float(leave["LostDays"]) == 0.5
    finally:
        with db_engine.begin() as c:
            _sql(c, "DELETE FROM core.EmployeeAbsence WHERE BusinessKey = :k", k=KEY + "-gun")


def _state(db_engine, scenario: int) -> dict:
    with db_engine.connect() as c:
        return dict(c.execute(sa.text("SELECT DataVersionId, BuiltAt FROM cache.PeriodCacheState WHERE CacheName = :n AND ScenarioDefinitionId = :s"),
                              {"n": CACHE.name, "s": scenario}).mappings().one())


def test_transfer_refreshes_only_what_changed(db_engine, world, clean):  # noqa: F811
    """Aktarım (K-188): yeni veri versiyonu açılır; izni değişen kaynak iznin aralığında, eşleşmesi değişen kaynak bütün günlerde yenilenir; önbellek
    yeni versiyona çekilir ve sonraki okumada baştan kurulmaz. Önbellek aktarımdan önce bayatsa dokunulmaz (ilk kullanımda baştan kurulur)."""
    base, follower, free, r1, r2, g1 = world["base"], world["follower"], world["free"], world["r1"], world["r2"], world["g1"]
    assert ensure(db_engine, world, follower)[base] == "built" and ensure(db_engine, world, free) == {free: "built"}
    first, built = stored(db_engine, base), _state(db_engine, base)
    (day,) = working_days(db_engine, world, 1, r1)
    total = (world["end"] - world["start"]).days + 1
    with db_engine.begin() as c:
        version = _sql(c, "INSERT INTO adm.DataVersion (CreatedAt, LoadType, IsPinned, IsSynthetic) OUTPUT inserted.Id VALUES (SYSUTCDATETIME(), N'Tam', 0, 0)").scalar()
        _sql(c, "INSERT INTO core.EmployeeAbsence (Id, LocationId, ResourceId, AbsenceType, StartDate, EndDate, HoursPerDay, VersionFrom, BusinessKey, UpdatedAt) "
                "VALUES (9900030, :l, :r, N'İzin', :d, :d, NULL, :v, :k, SYSUTCDATETIME())", l=world["location"], r=r1, d=day, v=version, k=KEY + "-at")
        _sql(c, "INSERT INTO core.ResourceGroupMember (Id, LocationId, ResourceGroupId, ResourceId, VersionFrom, BusinessKey, UpdatedAt) "
                "VALUES (9900031, :l, :g, :r, :v, :k, SYSUTCDATETIME())", l=world["location"], g=world["other"], r=r2, v=version, k=KEY + "-at")
    try:
        with Session(db_engine) as s:
            done = triggers.after_transfer(s, version)
            s.commit()
        assert done == {"scenarios": 3, "resources": 1, "leave": 1}
        after = stored(db_engine, base)
        assert changed(first, after) == {(r1, g1, day)} | {(r2, world["other"], x) for x in days(world["start"], world["end"])}
        assert after[(r1, g1, day)][1] == 1.0 and len(after) == len(first) + total
        now = _state(db_engine, base)
        assert now["DataVersionId"] == version and now["BuiltAt"] == built["BuiltAt"]            # baştan kurulmadı
        assert ensure(db_engine, world, follower) == {base: "ready", follower: "ready"} and ensure(db_engine, world, free) == {free: "ready"}
        for sid in (base, follower, free):
            same_as_scratch(db_engine, world, sid)

        # önbellek bayatken (aktarım dışı bir işlem versiyon açmış) aktarım dokunmaz; ilk kullanımda baştan kurulur
        with db_engine.begin() as c:
            _sql(c, "UPDATE cache.PeriodCacheState SET DataVersionId = :v WHERE CacheName = :n", v=version - 1, n=CACHE.name)
            later = _sql(c, "INSERT INTO adm.DataVersion (CreatedAt, LoadType, IsPinned, IsSynthetic) OUTPUT inserted.Id VALUES (SYSUTCDATETIME(), N'Tam', 0, 0)").scalar()
        with Session(db_engine) as s:
            assert triggers.after_transfer(s, later) == {"scenarios": 0, "resources": 0, "leave": 0}
            s.commit()
        assert ensure(db_engine, world, base) == {base: "built"}
    finally:
        with db_engine.begin() as c:
            _sql(c, "DELETE FROM core.EmployeeAbsence WHERE BusinessKey = :k", k=KEY + "-at")
            _sql(c, "DELETE FROM core.ResourceGroupMember WHERE BusinessKey = :k", k=KEY + "-at")
            _sql(c, "DELETE FROM cache.ResourceCapacityDay")
            _sql(c, "DELETE FROM cache.PeriodCacheState")
            _sql(c, "DELETE FROM adm.DataVersion WHERE Id >= :v", v=version)


def test_orphan_entry_is_a_quality_warning(db_engine, world, clean):  # noqa: F811
    """`SC.CAP_ORPHAN`: aktarımın kapattığı (güncel veride olmayan) kaynağa Baz'da girilmiş, geçerli ve bitmemiş kayıt uyarıdır; bitmiş kayıt ve izleyen
    senaryonun kaydı uyarı vermez. Kayıt silinince uyarı kalkar."""
    base, follower = world["base"], world["follower"]
    today = date.today()
    with db_engine.begin() as c:
        _sql(c, "INSERT INTO core.Resource (Id, LocationId, Code, Name, VersionFrom, VersionTo, BusinessKey, UpdatedAt) "
                "VALUES (9900040, :l, N'PYT-KAPALI', N'Kapanan kaynak', :v, :v, :k, SYSUTCDATETIME())", l=world["location"], v=world["version"], k=KEY + "-orphan")

    def warnings() -> list[dict]:
        with Session(db_engine) as s:
            quality_run.run(s, {"Resource", "ResourceGroup"})
        with db_engine.connect() as c:
            return [dict(r) for r in c.execute(sa.text("SELECT EntityName, RecordKey, RecordLabel, RuleName, Message, Importance, Source FROM adm.DataQualityWarning "
                                                       "WHERE CheckCode = N'SC.CAP_ORPHAN'")).mappings()]
    try:
        assert warnings() == []
        ended = row(db_engine, "ResourceEfficiency", base, ResourceId=9900040, ValidFrom=today - timedelta(days=30), ValidTo=today - timedelta(days=1), EfficiencyPct=90)
        row(db_engine, "ResourceEfficiency", follower, ResourceId=9900040, ValidFrom=today, ValidTo=None, EfficiencyPct=90)
        assert warnings() == []
        live = pattern(db_engine, base, today - timedelta(days=5), None, 8, ResourceId=9900040)
        (w,) = warnings()
        assert (w["EntityName"], w["RecordKey"], w["Importance"], w["Source"]) == ("Resource", "9900040", "Normal", "Smartchain")
        assert w["RuleName"] == "Kapanan kaynağa girilmiş kapasite kaydı" and w["Message"].endswith("PYT-KAPALI") and "PYT-KAPALI" in w["RecordLabel"]
        with db_engine.begin() as c:
            _sql(c, "DELETE FROM param.WorkPattern WHERE Id = :i", i=live)
        assert warnings() == [] and ended
    finally:
        with db_engine.begin() as c:
            _sql(c, "DELETE FROM adm.DataQualityWarning WHERE CheckCode = N'SC.CAP_ORPHAN'")
            _sql(c, "DELETE FROM core.Resource WHERE BusinessKey = :k", k=KEY + "-orphan")


def test_horizon_and_engine_period_values(api, db_engine, world, clean):  # noqa: F811
    """Ufuk ucu senaryonun dönemlerinin ilk ve son günü; motorun veri erişimi dönem değerlerini aynı hesaptan okur (docs/09)."""
    base, r1 = world["base"], world["r1"]
    got = api.get(f"/api/capacity/horizon?scenario_id={base}")
    assert got.status_code == 200 and got.json() == {"start": world["start"].isoformat(), "end": world["end"].isoformat()}
    a, b = world["start"], world["start"] + timedelta(days=6)
    with Session(db_engine) as s:
        version = s.execute(sa.text("SELECT MAX(Id) FROM adm.DataVersion")).scalar()
        mine = SqlPlanningData(s, version, base).period_values("resource-capacity-day", a, b)
        direct = compute.values(s, base, a, b)
        with pytest.raises(ValueError):
            SqlPlanningData(s, version).period_values("resource-capacity-day", a, b)
    key = lambda r: (r["ResourceId"], r["ResourceGroupId"], r["Date"])  # noqa: E731
    assert sorted(mine, key=key) == sorted(direct, key=key) and any(r["ResourceId"] == r1 for r in mine)


def test_edit_from_validity_reads_the_record_with_the_lists_own_fields(api, world, clean):  # noqa: F811
    """Geçerlilik › Düzenle kaydı Kayıtlar listesinden okur; istenen alanlar listenin kendi kolonlarıdır. Girişlerin alanları aynı değildir:
    Verimlilik'te "Birim" yoktur ve olmayan alan isteği reddettirir (7.9c demosunda Düzenle'nin açılmamasının nedeni)."""
    base = world["base"]
    for name in ("capacity-work-patterns", "capacity-efficiency", "capacity-overtime-limits"):
        fields = [c["field"] for c in api.get(f"/api/{name}/columns").json()["columns"]]
        got = api.post(f"/api/{name}/query", json={"limit": 100, "scenario_id": base, "fields": fields})
        assert got.status_code == 200, (name, got.text)
        assert ("CapacityUnit" in fields) == (name != "capacity-efficiency")
    bad = api.post("/api/capacity-efficiency/query", json={"limit": 100, "scenario_id": base, "fields": ["Level", "Code", "CapacityUnit"]})
    assert bad.status_code == 422 and "CapacityUnit" in bad.text
