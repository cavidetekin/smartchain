"""Kapasite yönetimi, 7.9a (K-185): çözümleme katmanı (Baz + fark), geçerlilik kuralı, kapasite hesabı, önbellek ve tetikleyiciler.

Sentetik v0'da (Smartchain_test); kendi senaryolarını açar, yazdığını geri alır. Sabitlenenler:
- çözümleme: Baz satırı, alan düzeyinde fark, geçersiz yapılan satır, senaryonun kendi satırı, Baz'ı izlemeyen senaryo, kopya, Baz'dan ayırma, silme;
- geçerlilik: önce seviye (kaynak, yoksa grup), sonra başlangıcı en ileri olan; açık bitiş; geçici kayıt bitince öncekine dönüş; çok gruplu kaynak;
- hesap: veritabanındaki sonuç bağımsız Python hesabıyla (`app/data/synthetic/capacity.py`) birebir; duruşlar birleşir, gün bir kez düşer;
- her tetikleyici ayrı testte (giriş değişikliği kaynakta ve grupta, fabrika takvimi, aktarım, Baz değişikliği, yeni senaryo ve Baz'dan ayrılma):
  yalnız etkilenen kaynak ve günler yenilenir, önbellekteki sonuç sıfırdan hesaplananla (motorun yolu) birebir aynıdır.
"""
import dataclasses
from datetime import date, timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app import periods as P
from app.capacity import compute, triggers
from app.data.synthetic import capacity as reference
from app.data.synthetic import dataset as d
from app.params import resolve, scenarios
from app.periods import cache
from app.periods.__main__ import main as periods_cli

CACHE = compute.CACHE
TABLES = tuple(resolve.FIELDS)
NAME = "pytest kapasite"          # testin açtığı senaryoların ad öneki
KEY = "pytest-cap"                # testin ana veriye yazdığı satırların iş anahtarı öneki
WEEK = {name: 1 for name in resolve.DAYS}


# --- geçerlilik kuralı (veritabanısız; bağımsız Python hesabı) -----------------------------------------------------------

def test_reference_validity_rule():
    """Önce seviye, sonra başlangıcı en ileri olan; açık bitiş; geçici kayıt bitince önceki geçerli; geçersiz kayıt yok sayılır."""
    day = date(2027, 1, 4)
    rows = [
        {"Id": 1, "ResourceGroupId": 10, "ResourceId": None, "ValidFrom": day, "ValidTo": None, "V": "grup"},
        {"Id": 2, "ResourceGroupId": 10, "ResourceId": None, "ValidFrom": day + timedelta(days=20), "ValidTo": None, "V": "grup-yeni"},
        {"Id": 3, "ResourceGroupId": None, "ResourceId": 7, "ValidFrom": day + timedelta(days=5), "ValidTo": day + timedelta(days=9), "V": "kaynak-geçici"},
        {"Id": 4, "ResourceGroupId": None, "ResourceId": 7, "ValidFrom": day + timedelta(days=7), "ValidTo": day + timedelta(days=8), "V": "kaynak-içte"},
        {"Id": 5, "ResourceGroupId": None, "ResourceId": 7, "ValidFrom": day + timedelta(days=30), "ValidTo": None, "V": "geçersiz", "IsValid": False},
        {"Id": 6, "ResourceGroupId": 11, "ResourceId": None, "ValidFrom": day, "ValidTo": None, "V": "öteki grup"},
    ]

    def at(offset: int, group: int = 10, resource: int = 7):
        found = reference.effective(rows, group, resource, day + timedelta(days=offset))
        return found and found["V"]

    assert at(-1) is None                                                     # hiçbir kayıt kapsamıyor
    assert at(0) == "grup" and at(4) == "grup"                                # kaynağın kaydı yok: grubunki
    assert at(5) == "kaynak-geçici" and at(6) == "kaynak-geçici"              # kaynağın kaydı grubunkinden önce
    assert at(7) == "kaynak-içte" and at(8) == "kaynak-içte"                  # aynı seviyede başlangıcı en ileri olan
    assert at(9) == "kaynak-geçici" and at(10) == "grup"                      # geçici kayıt bitince bir önceki geçerli
    assert at(25) == "grup-yeni" and at(400) == "grup-yeni"                   # açık bitiş: süresiz
    assert at(35) == "grup-yeni"                                              # geçersiz yapılmış kayıt yok sayılır
    assert at(6, group=11) == "kaynak-geçici" and at(0, group=11) == "öteki grup"   # çok gruplu kaynak: her grupta o grubun değeri
    assert at(6, resource=8) == "grup"                                        # başka kaynak: grubun değeri


# --- veritabanı ---------------------------------------------------------------------------------------------------------

pytestmark = pytest.mark.db


def _sql(conn, q: str, **p):
    return conn.execute(sa.text(q), p)


def _purge(db_engine) -> None:
    """Önceki koşudan kalan (yarıda kesilmiş) test senaryoları ve ana veri satırları."""
    with Session(db_engine) as s:
        for (sid,) in s.execute(sa.text("SELECT Id FROM param.ScenarioDefinition WHERE Name LIKE :n"), {"n": NAME + "%"}).all():
            scenarios.delete(s, sid)
        for table in ("EmployeeAbsence", "ResourceGroupMember"):
            s.execute(sa.text(f"DELETE FROM core.[{table}] WHERE BusinessKey LIKE :k"), {"k": KEY + "%"})
        s.commit()


def _clean(conn, marks: dict) -> None:
    for table, mark in marks.items():
        _sql(conn, f"DELETE FROM param.[{table}] WHERE Id > :m", m=mark)
    for table in ("EmployeeAbsence", "ResourceGroupMember"):
        _sql(conn, f"DELETE FROM core.[{table}] WHERE BusinessKey LIKE :k", k=KEY + "%")
    _sql(conn, "DELETE FROM cache.ResourceCapacityDay")
    _sql(conn, "DELETE FROM cache.PeriodCacheState")


@pytest.fixture(scope="module")
def world(db_engine):
    """Baz; Baz'ı izleyen ve izlemeyen birer test senaryosu (sentetik senaryo farklarından bağımsız); kaynaklar. Sonunda yazılanlar silinir."""
    _purge(db_engine)
    with Session(db_engine) as s:
        base = cache.base_id(s)
        follower = scenarios.create_copy(s, NAME + " izleyen", base, follows_base=True)["Id"]
        free = scenarios.create_copy(s, NAME + " bağımsız", base, follows_base=False)["Id"]
        s.commit()
    with db_engine.begin() as c:
        marks = {t: _sql(c, f"SELECT COALESCE(MAX(Id), 0) FROM param.[{t}]").scalar() for t in TABLES}
        members = _sql(c, "SELECT g.Code, r.Code, m.ResourceGroupId, m.ResourceId, m.LocationId, m.VersionFrom FROM core.ResourceGroupMember m "
                          "JOIN core.ResourceGroup g ON g.Id = m.ResourceGroupId AND g.VersionTo IS NULL "
                          "JOIN core.Resource r ON r.Id = m.ResourceId AND r.VersionTo IS NULL WHERE m.VersionTo IS NULL").all()
        _clean(c, marks)
    by = {(g, r): (gid, rid) for g, r, gid, rid, _l, _v in members}
    groups_of: dict[int, set[int]] = {}
    for _g, _r, gid, rid, _l, _v in members:
        groups_of.setdefault(rid, set()).add(gid)
    g1, r1 = next(v for (g, r), v in by.items() if r == "M3-01")      # ISL3: çalışma düzeni grup düzeyinde, tek gruba üye
    _g, r2 = next(v for (g, r), v in by.items() if r == "M3-03")
    assert _g == g1 and groups_of[r1] == {g1} and groups_of[r2] == {g1}
    labor, quality_group = (next(gid for g, _r, gid, *_ in members if g == code) for code in (d.LABOR_GROUP, "CG-KAL"))
    worker = next(rid for rid, gs in groups_of.items() if {labor, quality_group} <= gs)                     # iki gruba üye işçi
    other = next(gid for g, _r, gid, *_ in members if g == "TASLAMA")
    with Session(db_engine) as s:
        found = P.read_periods(s, base, date.today())
    yield {"base": base, "follower": follower, "free": free, "marks": marks, "g1": g1, "r1": r1, "r2": r2, "groups_of": groups_of,
           "members": {(gid, rid) for _g, _r, gid, rid, _l, _v in members}, "labor": labor, "quality": quality_group, "worker": worker, "other": other,
           "location": members[0][4], "version": members[0][5], "start": found[0].start, "end": found[-1].end}
    with db_engine.begin() as c:
        _clean(c, marks)
    _purge(db_engine)


@pytest.fixture
def clean(db_engine, world):
    """Her test temiz girişle ve boş önbellekle başlar."""
    with db_engine.begin() as c:
        _clean(c, world["marks"])
    yield
    with db_engine.begin() as c:
        _clean(c, world["marks"])


def row(db_engine, table: str, scenario_id: int, **values) -> int:
    """Giriş tablosuna satır yazar (ekranın kayıt işlemi 7.9b'dedir); dönen: kimlik."""
    values = {"ScenarioDefinitionId": scenario_id, "IsValid": 1, **values}
    with db_engine.begin() as c:
        if table == "FactoryCalendar" and "LocationId" not in values:      # fabrika takvimi lokasyon bazlıdır (K-194): sentetik lokasyon
            values["LocationId"] = _sql(c, "SELECT Id FROM core.Location WHERE Code = :c", c=d.LOCATION_CODE).scalar_one()
    names = ", ".join(f"[{k}]" for k in values)
    with db_engine.begin() as c:
        return _sql(c, f"INSERT INTO param.[{table}] ({names}, UpdatedAt) OUTPUT inserted.Id VALUES ({', '.join(':' + k for k in values)}, SYSUTCDATETIME())",
                    **values).scalar()


def diff(db_engine, table: str, scenario_id: int, base_row: int, **changed) -> int:
    """Baz satırına fark satırı: değiştirilen alanlar `OverriddenFields`'ta; öteki alanlar Baz'dan okunur (satırda Baz'ın o anki kopyası durur)."""
    fields = resolve.FIELDS[table]
    with db_engine.begin() as c:
        source = dict(_sql(c, f"SELECT {', '.join(f'[{f}]' for f in fields)} FROM param.[{table}] WHERE Id = :i", i=base_row).mappings().one())
    is_valid = changed.pop("IsValid", 1)
    marked = [*changed, *(["IsValid"] if is_valid != 1 else [])]
    return row(db_engine, table, scenario_id, **{**source, **changed, "IsValid": is_valid, "BaseRowId": base_row, "OverriddenFields": "," + ",".join(marked) + ","})


def update(db_engine, table: str, row_id: int, **values) -> None:
    with db_engine.begin() as c:
        _sql(c, f"UPDATE param.[{table}] SET {', '.join(f'[{k}] = :{k}' for k in values)} WHERE Id = :id", id=row_id, **values)


def delete(db_engine, table: str, row_id: int) -> None:
    with db_engine.begin() as c:
        _sql(c, f"DELETE FROM param.[{table}] WHERE Id = :id", id=row_id)


def resolved(db_engine, table: str, scenario_id: int, base: int | None, ids: set[int], valid_only: bool = True) -> list[dict]:
    """Senaryonun çözümlenmiş satırlarından testin yazdıkları (RowId ile)."""
    with db_engine.connect() as c:
        rows = c.execute(sa.text(resolve.sql(table, valid_only=valid_only)), {"sid": scenario_id, "base": base}).mappings().all()
    return sorted((dict(r) for r in rows if r["RowId"] in ids), key=lambda r: r["RowId"])


def calc(db_engine, scenario_id: int, start: date, end: date, *resources: int) -> dict:
    """Hesabın doğrudan sonucu (önbelleksiz): (kaynak, grup, gün) → değerler."""
    with Session(db_engine) as s:
        rows = compute.values(s, scenario_id, start, end, tuple(resources) or None)
    return {(r["ResourceId"], r["ResourceGroupId"], r["Date"]): {v: float(r[v]) for v in CACHE.values} for r in rows}


def stored(db_engine, scenario_id: int) -> dict:
    """Önbellek tablosunda senaryonun kendi tuttuğu satırlar: (kaynak, grup, gün) → değerler."""
    with db_engine.connect() as c:
        rows = c.execute(sa.text(f"SELECT ResourceId, ResourceGroupId, [Date], {', '.join(CACHE.values)} FROM cache.ResourceCapacityDay "
                                 "WHERE ScenarioDefinitionId = :s"), {"s": scenario_id}).all()
    return {(r[0], r[1], r[2]): tuple(float(v) for v in r[3:]) for r in rows}


def state(db_engine, scenario_id: int) -> int:
    with db_engine.connect() as c:
        return c.execute(sa.text("SELECT COUNT(*) FROM cache.PeriodCacheState WHERE ScenarioDefinitionId = :s"), {"s": scenario_id}).scalar()


def changed(a: dict, b: dict) -> set:
    return {k for k in set(a) | set(b) if a.get(k) != b.get(k)}


def ensure(db_engine, world, scenario_id: int) -> dict:
    with Session(db_engine) as s:
        return cache.ensure(s, CACHE, scenario_id, world["start"], world["end"])


def same_as_scratch(db_engine, world, scenario_id: int) -> int:
    """Önbellekteki geçerli sonuç, girişlerden sıfırdan hesaplananla (motorun yolu) birebir aynı. Dönen: satır sayısı."""
    with Session(db_engine) as s:
        key = lambda r: (r["ResourceId"], r["ResourceGroupId"], r["Date"], *[float(r[v]) for v in CACHE.values])  # noqa: E731
        cached = sorted(key(r) for r in compute.cached(s, scenario_id, world["start"], world["end"]))
        scratch = sorted(key(r) for r in P.values(s, CACHE.name, scenario_id, world["start"], world["end"]))
    assert cached == scratch
    return len(cached)


def fire(db_engine, fn, *args, **kwargs) -> dict:
    """Tetikleyiciyi kendi işleminde çağırır (ekranda girişi kaydeden işlemle aynı işlemdir)."""
    with Session(db_engine) as s:
        done = fn(s, *args, **kwargs)
        s.commit()
    return done


def days(a: date, b: date) -> list[date]:
    return [a + timedelta(days=i) for i in range((b - a).days + 1)]


def working_days(db_engine, world, count: int, *resources: int) -> list[date]:
    """Verilen kaynakların hepsinde tam çalışılan ve duruşu olmayan günler (ufkun üçüncü haftasından sonra)."""
    a = world["start"] + timedelta(days=14)
    got = calc(db_engine, world["base"], a, a + timedelta(days=70), *resources)
    ok = [day for day in days(a, a + timedelta(days=70))
          if all(v["WorkingDay"] == 1 and v["Downtime"] == 0 for (r, _g, x), v in got.items() if x == day)]
    assert len(ok) >= count
    return ok[:count]


def pattern(db_engine, scenario_id: int, start: date, end: date | None, capacity: float, **more) -> int:
    return row(db_engine, "WorkPattern", scenario_id, ValidFrom=start, ValidTo=end, DailyCapacity=capacity, **{**WEEK, **more})


def efficiency(db_engine, scenario_id: int, resource_id: int, pct: float, start: date, end: date | None) -> int:
    return row(db_engine, "ResourceEfficiency", scenario_id, ResourceId=resource_id, ValidFrom=start, ValidTo=end, EfficiencyPct=pct)


# --- çözümleme katmanı (Baz + fark) ---------------------------------------------------------------------------------------

def test_resolver_base_difference_invalid_and_own_rows(db_engine, world, clean):
    """Baz satırı izleyen senaryoda görünür; fark satırı yalnız değiştirdiği alanı ezer; geçersiz yapılan satır o senaryoda yok sayılır."""
    base, follower, free, r1 = world["base"], world["follower"], world["free"], world["r1"]
    a, b = world["start"], world["start"] + timedelta(days=9)
    first = efficiency(db_engine, base, r1, 77, a, b)
    second = efficiency(db_engine, base, r1, 66, b + timedelta(days=1), None)
    ids = {first, second}

    seen = resolved(db_engine, "ResourceEfficiency", follower, base, ids)
    assert [(r["RowId"], r["StoredId"], r["Origin"], float(r["EfficiencyPct"])) for r in seen] == [(first, None, "Baz", 77.0), (second, None, "Baz", 66.0)]
    assert [r["Origin"] for r in resolved(db_engine, "ResourceEfficiency", base, None, ids)] == ["Senaryo", "Senaryo"]   # Baz'da satır kendi satırıdır
    assert resolved(db_engine, "ResourceEfficiency", free, None, ids) == []                                 # izlemeyen senaryo Baz'ı okumaz

    # alan düzeyinde fark: yalnız yüzde değişti; satırdaki eski tarih kopyası okunmaz, tarihler Baz'dan gelir
    stored_id = row(db_engine, "ResourceEfficiency", follower, ResourceId=r1, ValidFrom=a + timedelta(days=50), ValidTo=a + timedelta(days=60),
                    EfficiencyPct=33, BaseRowId=first, OverriddenFields=",EfficiencyPct,")
    one = resolved(db_engine, "ResourceEfficiency", follower, base, {first})[0]
    assert (one["RowId"], one["StoredId"], one["Origin"], float(one["EfficiencyPct"]), one["ValidFrom"], one["ValidTo"]) == (first, stored_id, "Senaryo farkı", 33.0, a, b)
    assert float(resolved(db_engine, "ResourceEfficiency", base, None, {first})[0]["EfficiencyPct"]) == 77.0   # Baz değişmedi
    # Baz'da değiştirilmeyen alan değişirse izleyen senaryoya akar; değiştirilen alan senaryonun değerinde kalır
    update(db_engine, "ResourceEfficiency", first, ValidTo=b - timedelta(days=2), EfficiencyPct=70)
    one = resolved(db_engine, "ResourceEfficiency", follower, base, {first})[0]
    assert (one["ValidTo"], float(one["EfficiencyPct"])) == (b - timedelta(days=2), 33.0)

    # geçersiz yapma: Baz satırı senaryoda yok sayılır (fark satırı IsValid alanını ezer); Baz'da geçerli kalır
    gone = row(db_engine, "ResourceEfficiency", follower, ResourceId=r1, ValidFrom=b, ValidTo=None, EfficiencyPct=66, IsValid=0, BaseRowId=second,
               OverriddenFields=",IsValid,")
    assert [r["RowId"] for r in resolved(db_engine, "ResourceEfficiency", follower, base, ids)] == [first]
    every = resolved(db_engine, "ResourceEfficiency", follower, base, ids, valid_only=False)
    assert [(r["RowId"], r["StoredId"], bool(r["IsValid"])) for r in every] == [(first, stored_id, True), (second, gone, False)]
    assert [r["RowId"] for r in resolved(db_engine, "ResourceEfficiency", base, None, ids)] == [first, second]

    # senaryonun kendi satırı (Baz'da karşılığı yok): yalnız o senaryoda
    own = efficiency(db_engine, follower, r1, 44, b + timedelta(days=30), None)
    mine = resolved(db_engine, "ResourceEfficiency", follower, base, {own})[0]
    assert (mine["RowId"], mine["StoredId"], mine["Origin"]) == (own, own, "Senaryo")
    assert resolved(db_engine, "ResourceEfficiency", base, None, {own}) == []
    with Session(db_engine) as s:
        assert resolve.has_own(s, follower) and not resolve.has_own(s, follower, ("FactoryCalendar",))


def test_copy_detach_and_delete(db_engine, world, clean):
    """Kopya senaryo farklarıyla birlikte kopyalanır; Baz'dan ayırınca Baz'ın o anki geçerli değerleri (farklarla) tam kopyalanır; silince kalmaz."""
    base, follower, r1 = world["base"], world["follower"], world["r1"]
    a = world["start"]
    kept = efficiency(db_engine, base, r1, 77, a, a + timedelta(days=4))
    changed_row = efficiency(db_engine, base, r1, 66, a + timedelta(days=5), a + timedelta(days=9))
    dropped = efficiency(db_engine, base, r1, 55, a + timedelta(days=10), None)
    diff(db_engine, "ResourceEfficiency", follower, changed_row, EfficiencyPct=33)
    diff(db_engine, "ResourceEfficiency", follower, dropped, IsValid=0)
    efficiency(db_engine, follower, r1, 44, a + timedelta(days=20), None)

    def view(scenario_id: int, base_id: int | None) -> list[tuple]:
        with db_engine.connect() as c:
            rows = c.execute(sa.text(resolve.sql("ResourceEfficiency", valid_only=False)), {"sid": scenario_id, "base": base_id}).mappings().all()
        return sorted((r["ValidFrom"], r["ValidTo"], float(r["EfficiencyPct"]), bool(r["IsValid"])) for r in rows if r["ResourceId"] == r1)

    def raw(scenario_id: int) -> list[tuple]:
        with db_engine.connect() as c:
            return [tuple(r) for r in c.execute(sa.text("SELECT BaseRowId, OverriddenFields FROM param.ResourceEfficiency WHERE ScenarioDefinitionId = :s "
                                                        "AND ResourceId = :r ORDER BY Id"), {"s": scenario_id, "r": r1})]

    before = view(follower, base)
    assert before == [(a, a + timedelta(days=4), 77.0, True), (a + timedelta(days=5), a + timedelta(days=9), 33.0, True),
                      (a + timedelta(days=10), None, 55.0, False), (a + timedelta(days=20), None, 44.0, True)]
    with Session(db_engine) as s:
        copy = scenarios.create_copy(s, NAME + " kopya", follower, follows_base=True)["Id"]
        s.commit()
    try:
        assert view(copy, base) == before                                                   # kopya: farklar ve kendi satırı kopyalandı, Baz hâlâ okunuyor
        assert raw(copy) == [(changed_row, ",EfficiencyPct,"), (dropped, ",IsValid,"), (None, None)]
        update(db_engine, "ResourceEfficiency", kept, EfficiencyPct=78)                     # Baz değişikliği izleyen kopyaya akar
        assert view(copy, base)[0][2] == 78.0
        with Session(db_engine) as s:
            scenarios.detach(s, copy)
            s.commit()
        assert all(link is None and fields is None for link, fields in raw(copy)) and len(raw(copy)) == 4   # fark satırı kalmadı: hepsi kendi satırı
        after = view(copy, None)
        assert after == [(a, a + timedelta(days=4), 78.0, True), *before[1:]]               # ayrıldığı andaki geçerli değerler; geçersiz yapılan geçersiz kalır
        update(db_engine, "ResourceEfficiency", kept, EfficiencyPct=79)                     # ayrıldıktan sonra Baz değişikliği gelmez
        assert view(copy, None) == after and view(follower, base)[0][2] == 79.0
    finally:
        with Session(db_engine) as s:
            scenarios.delete(s, copy)
            s.commit()
    with db_engine.connect() as c:
        left = [c.execute(sa.text(f"SELECT COUNT(*) FROM param.[{t}] WHERE ScenarioDefinitionId = :s"), {"s": copy}).scalar() for t in TABLES]
    assert left == [0] * len(TABLES)


def test_scenario_not_following_base_gets_full_copy(db_engine, world, clean):
    """Baz'ı izlemeden açılan senaryo Baz'ın satırlarını tam kopya olarak tutar: hesabı Baz'la aynı başlar, sonra Baz'dan etkilenmez."""
    base, free, r1, g1 = world["base"], world["free"], world["r1"], world["g1"]
    with db_engine.connect() as c:
        counts = {t: [c.execute(sa.text(f"SELECT COUNT(*) FROM param.[{t}] WHERE ScenarioDefinitionId = :s AND BaseRowId IS NULL"), {"s": s}).scalar()
                      for s in (base, free)] for t in TABLES}
        links = sum(c.execute(sa.text(f"SELECT COUNT(*) FROM param.[{t}] WHERE ScenarioDefinitionId = :s AND BaseRowId IS NOT NULL"), {"s": free}).scalar() for t in TABLES)
    assert all(a == b for a, b in counts.values()) and counts["WorkPattern"][0] > 0 and links == 0
    a, b = world["start"], world["start"] + timedelta(days=13)
    assert calc(db_engine, free, a, b) == calc(db_engine, base, a, b)
    efficiency(db_engine, base, r1, 50, a, b)                                                # Baz'daki değişiklik izlemeyen senaryoya gelmez
    total = lambda sid: sum(v["Capacity"] for v in calc(db_engine, sid, a, b, r1).values())  # noqa: E731
    assert total(base) > 0 and total(free) == pytest.approx(2 * total(base))


# --- geçerlilik kuralı ve hesap (veritabanında) -----------------------------------------------------------------------------

def test_validity_rule_in_the_computation(db_engine, world, clean):
    """Seviye, başlangıcı en ileri olan, açık bitiş, geçici kaydın bitişi, geçersiz kayıt, çok gruplu kaynak ve izleyen senaryonun farkı."""
    base, follower, r1, r2, g1 = world["base"], world["follower"], world["r1"], world["r2"], world["g1"]
    a = world["start"] + timedelta(days=21)
    lo, hi = a - timedelta(days=4), a + timedelta(days=12)
    group_value = calc(db_engine, base, lo, hi, r1)[(r1, g1, a)]["DailyCapacity"]
    assert group_value > 0

    def caps(scenario_id: int, resource_id: int) -> list[float]:
        got = calc(db_engine, scenario_id, lo, hi, resource_id)
        return [got[(resource_id, g1, day)]["DailyCapacity"] for day in days(lo, hi)]

    G = group_value
    temporary = pattern(db_engine, base, a, a + timedelta(days=6), 5, ResourceId=r1)
    assert caps(base, r1) == [G] * 4 + [5.0] * 7 + [G] * 6                                  # kaynağın kaydı grubunkinden önce; bitince grubunki geri gelir
    assert caps(base, r2) == [G] * 17                                                       # öteki kaynak grubun değerinde
    pattern(db_engine, base, a + timedelta(days=3), None, 6, ResourceId=r1)
    assert caps(base, r1) == [G] * 4 + [5.0] * 3 + [6.0] * 10                               # başlangıcı en ileri olan; açık bitiş süresiz
    pattern(db_engine, base, a - timedelta(days=2), None, 9, ResourceId=r1)
    assert caps(base, r1) == [G] * 2 + [9.0] * 2 + [5.0] * 3 + [6.0] * 10                   # erken başlayan açık kayıt sonrakileri ezmez
    pattern(db_engine, base, a + timedelta(days=5), None, 20, ResourceGroupId=g1)
    assert caps(base, r1) == [G] * 2 + [9.0] * 2 + [5.0] * 3 + [6.0] * 10                   # grubun yeni kaydı kaynağın kaydını ezmez (seviye önce)
    assert caps(base, r2) == [G] * 9 + [20.0] * 8                                           # grubun yeni kaydı öteki üyede geçerli
    row(db_engine, "WorkPattern", base, ResourceId=r1, ValidFrom=a + timedelta(days=4), ValidTo=None, DailyCapacity=99, IsValid=0, **WEEK)
    assert caps(base, r1) == [G] * 2 + [9.0] * 2 + [5.0] * 3 + [6.0] * 10                   # geçersiz kayıt yok sayılır
    # çalışma günü değeri kayıttan: bütün günler 1 girildi (hafta sonu dahil)
    got = calc(db_engine, base, a, a + timedelta(days=6), r1)
    assert {v["WorkingDay"] for v in got.values()} == {1.0}
    # izleyen senaryo: Baz'ın geçici kaydında yalnız günlük kapasiteyi değiştirir; tarihleri Baz'dan okur
    diff(db_engine, "WorkPattern", follower, temporary, DailyCapacity=4)
    assert caps(follower, r1) == [G] * 2 + [9.0] * 2 + [4.0] * 3 + [6.0] * 10 and caps(base, r1)[4] == 5.0

    # çok gruplu kaynak: her grupta o grubun değeriyle hesaplanır (çelişki veri kalitesi uyarısıdır)
    w = world["worker"]
    both = calc(db_engine, base, world["start"], world["start"], w)
    assert both[(w, world["labor"], world["start"])]["DailyCapacity"] == 7.5 and both[(w, world["quality"], world["start"])]["DailyCapacity"] == d.CONFLICT_DAILY


def test_downtime_is_merged_and_counted_once(db_engine, world, clean):
    """Fabrika takvimi, bakım ve duruş, çalışan izni birleşir: en büyüğü alınır, günün çalışma değerini aşamaz; kısmi izin saat ÷ günlük kapasite."""
    base, r1, r2, g1 = world["base"], world["r1"], world["r2"], world["g1"]
    d1, d2, d3, d4, d5, d6, d7 = working_days(db_engine, world, 7, r1, r2)
    plain = calc(db_engine, base, d1, d7, r1, r2)
    cap = plain[(r1, g1, d1)]["DailyCapacity"]

    def absence(no: int, day: date, hours) -> None:
        with db_engine.begin() as c:
            _sql(c, "INSERT INTO core.EmployeeAbsence (Id, LocationId, ResourceId, AbsenceType, StartDate, EndDate, HoursPerDay, VersionFrom, BusinessKey, UpdatedAt) "
                    "VALUES (:i, :l, :r, :t, :d, :d, :h, :v, :k, SYSUTCDATETIME())",
                 i=9_900_000 + no, l=world["location"], r=r1, t=f"İzin {no}", d=day, h=hours, v=world["version"], k=f"{KEY}-{no}")

    row(db_engine, "FactoryCalendar", base, StartDate=d1, EndDate=d1, Name="pytest yarım gün", DayValue=0.5)
    row(db_engine, "ResourceDowntime", base, ResourceId=r1, StartDate=d1, EndDate=d1, DowntimeType="Planlı bakım")        # yarım gün + bakım: 1 (1,5 değil)
    absence(1, d2, 3)                                                                                              # kısmi izin: 3 saat ÷ günlük kapasite
    absence(2, d3, None)                                                                                           # günlük saati boş: tam gün
    absence(3, d3, 2)                                                                                              # aynı gün ikinci izin: gün bir kez
    absence(4, d4, cap * 2)                                                                                        # kapasiteden uzun izin: en çok 1
    row(db_engine, "ResourceDowntime", base, ResourceGroupId=g1, StartDate=d5, EndDate=d5, DowntimeType="Planlı bakım")    # gruba girilen duruş: bütün üyeler
    half = {name: 0.5 for name in resolve.DAYS}
    pattern(db_engine, base, d6, d6, cap, ResourceId=r1, **half)                                                   # yarım çalışılan gün
    row(db_engine, "ResourceDowntime", base, ResourceId=r1, StartDate=d6, EndDate=d6, DowntimeType="Arıza")        # duruş günün değerini aşamaz
    none = {name: 0 for name in resolve.DAYS}
    pattern(db_engine, base, d7, d7, cap, ResourceId=r1, **none)                                                   # çalışılmayan gün
    row(db_engine, "FactoryCalendar", base, StartDate=d7, EndDate=d7, Name="pytest tatil", DayValue=0)

    got = calc(db_engine, base, d1, d7, r1, r2)

    def of(resource: int, day: date) -> tuple[float, float]:
        v = got[(resource, g1, day)]
        return v["WorkingDay"], v["Downtime"]

    assert of(r1, d1) == (1.0, 1.0) and of(r2, d1) == (1.0, 0.5)
    assert of(r1, d2) == (1.0, pytest.approx(3 / cap, abs=0.0001)) and of(r2, d2) == (1.0, 0.0)
    assert of(r1, d3) == (1.0, 1.0) and of(r1, d4) == (1.0, 1.0)
    assert of(r1, d5) == (1.0, 1.0) and of(r2, d5) == (1.0, 1.0)
    assert of(r1, d6) == (0.5, 0.5) and of(r1, d7) == (0.0, 0.0) and of(r2, d7) == (1.0, 1.0)
    for key, v in got.items():                                                              # kullanılabilir = (çalışma günü − duruş) × günlük kapasite × verimlilik
        before = plain[key]
        if before["WorkingDay"] == 0:                                                        # aradaki hafta sonu
            continue
        eff = before["Capacity"] / (before["WorkingDay"] * before["DailyCapacity"])
        assert v["Capacity"] == pytest.approx(v["WorkingDay"] * v["DailyCapacity"] * eff, abs=0.0002)
        assert v["AvailableCapacity"] == pytest.approx((v["WorkingDay"] - v["Downtime"]) * v["DailyCapacity"] * eff, abs=0.0002)


def test_computation_matches_the_python_reference(db_engine, world, clean):
    """Baz'ın bütün ufku: veritabanındaki hesap, sentetik girişlerden bağımsız Python hesabıyla birebir (grup × kaynak × gün)."""
    ds = d.generate(date.today())
    want = reference.daily(ds, world["start"], world["end"])
    groups = {g["Id"]: g["Code"] for g in ds.rows("ResourceGroup")}
    resources = {r["Id"]: r["Code"] for r in ds.rows("Resource")}
    with db_engine.connect() as c:
        group_codes = dict(c.execute(sa.text("SELECT Id, Code FROM core.ResourceGroup WHERE VersionTo IS NULL")).all())
        resource_codes = dict(c.execute(sa.text("SELECT Id, Code FROM core.Resource WHERE VersionTo IS NULL")).all())
    got = {(group_codes[g], resource_codes[r], day): v for (r, g, day), v in calc(db_engine, world["base"], world["start"], world["end"]).items()}
    assert len(got) == len(want) > 5_000
    bad = [(key, w, got.get(key)) for (g, r, day), w in want.items() for key in [(groups[g], resources[r], day)]
           if key not in got or any(abs(got[key][f] - w[f]) > 0.00011 for f in w)]
    assert bad == []
    assert sum(v["Downtime"] for v in got.values()) > 0 and sum(v["OvertimeLimit"] for v in got.values()) > 0   # sentetik veri bu yolları da gezer


# --- tetikleyiciler: her biri ayrı test -----------------------------------------------------------------------------------

def test_trigger_entry_changed_on_a_resource(db_engine, world, clean):
    """Kaynağa giriş eklendi, tarih aralığı değişti (eski ve yeni aralık), bitişi açıldı, silindi: yalnız o kaynak ve o günler yenilenir."""
    base, r1, g1 = world["base"], world["r1"], world["g1"]
    assert ensure(db_engine, world, base) == {base: "built"}
    first = stored(db_engine, base)
    a, b = world["start"] + timedelta(days=3), world["start"] + timedelta(days=12)

    rid = efficiency(db_engine, base, r1, 77, a, b)                                          # ekleme
    done = fire(db_engine, triggers.entry_changed, base, resource_id=r1, ranges=[(a, b)])
    after = stored(db_engine, base)
    moved = changed(first, after)
    assert done[base] == 10 and moved and all(k[0] == r1 and a <= k[2] <= b for k in moved) and set(after) == set(first)
    assert all(after[k][4] == pytest.approx(first[k][4] * 0.77, abs=0.0002) for k in moved)   # kullanılabilir kapasite %77
    same_as_scratch(db_engine, world, base)

    c, e = b + timedelta(days=2), b + timedelta(days=4)                                      # tarih aralığı değişti: eski ve yeni aralık birlikte yenilenir
    update(db_engine, "ResourceEfficiency", rid, ValidFrom=c, ValidTo=e)
    done = fire(db_engine, triggers.entry_changed, base, resource_id=r1, ranges=[(a, b), (c, e)])
    after = stored(db_engine, base)
    assert done[base] == (e - a).days + 1 and all(k[0] == r1 and c <= k[2] <= e for k in changed(first, after))
    same_as_scratch(db_engine, world, base)

    update(db_engine, "ResourceEfficiency", rid, ValidTo=None)                               # bitiş açıldı: ufkun sonuna kadar
    done = fire(db_engine, triggers.entry_changed, base, resource_id=r1, ranges=[(c, e), (c, None)])
    after = stored(db_engine, base)
    assert done[base] == (world["end"] - c).days + 1 and max(k[2] for k in changed(first, after)) > e + timedelta(days=7)
    assert all(k[0] == r1 and k[2] >= c for k in changed(first, after))
    same_as_scratch(db_engine, world, base)

    update(db_engine, "ResourceEfficiency", rid, IsValid=0)                                  # geçersiz yapıldı: silinmiş gibi
    fire(db_engine, triggers.entry_changed, base, resource_id=r1, ranges=[(c, None)])
    assert stored(db_engine, base) == first
    update(db_engine, "ResourceEfficiency", rid, IsValid=1)
    fire(db_engine, triggers.entry_changed, base, resource_id=r1, ranges=[(c, None)])
    assert stored(db_engine, base) != first
    delete(db_engine, "ResourceEfficiency", rid)                                             # silindi
    fire(db_engine, triggers.entry_changed, base, resource_id=r1, ranges=[(c, None)])
    assert stored(db_engine, base) == first and same_as_scratch(db_engine, world, base) == len(first)


def test_trigger_entry_changed_on_a_group(db_engine, world, clean):
    """Gruba giriş: grubun bütün kaynakları, yalnız kaydın günleri; başka grubun kaynaklarına dokunulmaz."""
    base, g1 = world["base"], world["g1"]
    ensure(db_engine, world, base)
    first = stored(db_engine, base)
    members = {r for g, r in world["members"] if g == g1}
    memberships = sum(len(world["groups_of"][r]) for r in members)
    a, b = world["start"] + timedelta(days=7), world["start"] + timedelta(days=13)

    rid = pattern(db_engine, base, a, b, 5, ResourceGroupId=g1)
    done = fire(db_engine, triggers.entry_changed, base, group_id=g1, ranges=[(a, b)])
    after = stored(db_engine, base)
    moved = changed(first, after)
    assert done[base] == memberships * 7 and len(members) >= 2
    assert {k[0] for k in moved} == members and all(k[1] == g1 and a <= k[2] <= b for k in moved) and set(after) == set(first)
    assert all(after[k][2] == 5.0 for k in moved)                                            # günlük kapasite kayıttan
    same_as_scratch(db_engine, world, base)

    delete(db_engine, "WorkPattern", rid)
    fire(db_engine, triggers.entry_changed, base, group_id=g1, ranges=[(a, b)])
    assert stored(db_engine, base) == first
    same_as_scratch(db_engine, world, base)
    with Session(db_engine) as s:                                                            # kaynak da grup da verilmezse iş yok
        assert triggers.entry_changed(s, base, ranges=[(a, b)]) == {base: 0, **{f: 0 for f in cache.followers(s) if state(db_engine, f)}}


def test_trigger_factory_calendar_changed(db_engine, world, clean):
    """Fabrika takvimi: kaydın lokasyonundaki bütün kaynaklar (K-194; sentetik veride tek lokasyon), yalnız o günler (kaydın eski ve yeni aralığı)."""
    base = world["base"]
    ensure(db_engine, world, base)
    first = stored(db_engine, base)
    d1, d2 = working_days(db_engine, world, 2, world["r1"], world["r2"])

    rid = row(db_engine, "FactoryCalendar", base, StartDate=d1, EndDate=d1, Name="pytest tatil", DayValue=0)
    done = fire(db_engine, triggers.factory_calendar_changed, base, world["location"], [(d1, d1)])
    after = stored(db_engine, base)
    moved = changed(first, after)
    assert done[base] == len(world["members"]) and moved and {k[2] for k in moved} == {d1} and set(after) == set(first)
    assert all(after[k][1] == after[k][0] and after[k][4] == 0 for k in after if k[2] == d1)   # o gün duruş = çalışma günü; kullanılabilir kapasite 0
    assert {k[0] for k in moved} >= {world["r1"], world["r2"]}
    same_as_scratch(db_engine, world, base)

    update(db_engine, "FactoryCalendar", rid, StartDate=d2, EndDate=d2, DayValue=0.5)        # gün taşındı: eski ve yeni gün
    done = fire(db_engine, triggers.factory_calendar_changed, base, world["location"], [(d1, d1), (d2, d2)])
    after = stored(db_engine, base)
    assert done[base] == len(world["members"]) * ((d2 - d1).days + 1) and {k[2] for k in changed(first, after)} == {d2}
    assert after[(world["r1"], world["g1"], d2)][1] == 0.5
    same_as_scratch(db_engine, world, base)


def test_trigger_transfer_changed(db_engine, world, clean):
    """Aktarım: çalışan izni (o kaynak, o günler) ve grup eşleşmesi (o kaynak, bütün günler); veri senaryodan bağımsız olduğu için Baz'da ve
    Baz'ı izlemeyen senaryoda yenilenir, izleyen senaryo Baz'dan okur."""
    base, follower, free, r1, r2, g1 = world["base"], world["follower"], world["free"], world["r1"], world["r2"], world["g1"]
    assert ensure(db_engine, world, follower) == {base: "built", follower: "built"} and ensure(db_engine, world, free) == {free: "built"}
    first, first_free = stored(db_engine, base), stored(db_engine, free)
    assert stored(db_engine, follower) == {} and first == first_free                         # izleyen satır tutmaz; izlemeyen tam kopyayla aynı sonuç
    (day,) = working_days(db_engine, world, 1, r1)

    with db_engine.begin() as c:                                                             # ERP'den izin geldi
        _sql(c, "INSERT INTO core.EmployeeAbsence (Id, LocationId, ResourceId, AbsenceType, StartDate, EndDate, HoursPerDay, VersionFrom, BusinessKey, UpdatedAt) "
                "VALUES (9900010, :l, :r, N'İzin', :d, :d, NULL, :v, :k, SYSUTCDATETIME())", l=world["location"], r=r1, d=day, v=world["version"], k=KEY + "-t")
    done = fire(db_engine, triggers.transfer_changed, [r1], [(day, day)])
    assert (done[base], done[follower], done[free]) == (1, 0, 1)
    for sid, before in ((base, first), (free, first_free)):
        after = stored(db_engine, sid)
        assert changed(before, after) == {(r1, g1, day)} and after[(r1, g1, day)][1] == 1.0
        same_as_scratch(db_engine, world, sid)
    assert stored(db_engine, follower) == {} and same_as_scratch(db_engine, world, follower) == len(first)

    with db_engine.begin() as c:                                                             # ERP'den yeni grup eşleşmesi geldi: kaynak bir gruba daha üye
        _sql(c, "INSERT INTO core.ResourceGroupMember (Id, LocationId, ResourceGroupId, ResourceId, VersionFrom, BusinessKey, UpdatedAt) "
                "VALUES (9900011, :l, :g, :r, :v, :k, SYSUTCDATETIME())", l=world["location"], g=world["other"], r=r2, v=world["version"], k=KEY + "-m")
    middle = stored(db_engine, base)
    total = (world["end"] - world["start"]).days + 1
    done = fire(db_engine, triggers.transfer_changed, [r2])
    after = stored(db_engine, base)
    assert done[base] == done[free] == 2 * total                                             # kaynağın bütün günleri, iki grubunda
    assert set(after) - set(middle) == {(r2, world["other"], x) for x in days(world["start"], world["end"])}
    assert all(after[k] == middle[k] for k in middle)                                        # ötekilere dokunulmadı
    for sid in (base, follower, free):
        same_as_scratch(db_engine, world, sid)
    with db_engine.begin() as c:                                                             # eşleşme kalktı
        _sql(c, "DELETE FROM core.ResourceGroupMember WHERE BusinessKey = :k", k=KEY + "-m")
    fire(db_engine, triggers.transfer_changed, [r2])
    assert stored(db_engine, base) == middle
    for sid in (base, follower, free):
        same_as_scratch(db_engine, world, sid)


def test_trigger_base_change_reaches_followers(db_engine, world, clean):
    """Baz'daki değişiklik Baz'ı izleyen senaryolarda aynı kaynak ve günleri de yeniler; izlemeyen senaryoya dokunulmaz."""
    base, follower, free, r1, r2, g1 = world["base"], world["follower"], world["free"], world["r1"], world["r2"], world["g1"]
    ensure(db_engine, world, follower)
    ensure(db_engine, world, free)
    first, first_free = stored(db_engine, base), stored(db_engine, free)
    a, b = world["start"] + timedelta(days=7), world["start"] + timedelta(days=13)

    # izleyen senaryonun kendi girişi yokken: Baz değişir, izleyen satır tutmadan Baz'dan okur
    efficiency(db_engine, base, r1, 77, a, b)
    done = fire(db_engine, triggers.entry_changed, base, resource_id=r1, ranges=[(a, b)])
    assert done[base] == 7 and done[follower] == 0 and free not in done
    assert stored(db_engine, follower) == {} and stored(db_engine, free) == first_free
    same_as_scratch(db_engine, world, follower)

    # izleyen senaryonun kendi girişi var (verimlilik): yalnız Baz'dan farklı çıkan satırları tutar
    efficiency(db_engine, follower, r2, 33, a, b)
    fire(db_engine, triggers.entry_changed, follower, resource_id=r2, ranges=[(a, b)])
    own = stored(db_engine, follower)
    assert own and all(k[0] == r2 and k[1] == g1 and a <= k[2] <= b for k in own)
    middle = stored(db_engine, base)
    assert all(own[k][4] == pytest.approx(middle[k][4] * 0.33, abs=0.0002) for k in own)
    same_as_scratch(db_engine, world, follower)

    # Baz'da aynı kaynağın çalışma düzeni değişti: izleyen senaryonun o kaynak ve günlerdeki satırları da yeniden hesaplanır (sonucu Baz girişine de bağlı)
    pattern(db_engine, base, a, b, 5, ResourceId=r2)
    done = fire(db_engine, triggers.entry_changed, base, resource_id=r2, ranges=[(a, b)])
    assert done[base] == 7 and done[follower] == 7 and free not in done
    after, mine = stored(db_engine, base), stored(db_engine, follower)
    assert all(k[0] == r2 and a <= k[2] <= b for k in changed(middle, after))
    assert set(mine) == {(r2, g1, x) for x in days(a, b)}                                    # bütün günler 1 girildi: her gün Baz'dan farklı
    assert all(mine[k][2] == 5.0 and mine[k][4] == pytest.approx(after[k][4] * 0.33, abs=0.0002) for k in mine)
    assert stored(db_engine, free) == first_free and first != after
    for sid in (base, follower, free):
        same_as_scratch(db_engine, world, sid)


def test_trigger_new_scenario_and_detach(db_engine, world, clean):
    """Yeni senaryonun önbelleği ilk kullanımda kurulur (kendi girişi yoksa boş); Baz'dan ayrılınca düşer ve tamamını kendisi tutacak biçimde
    baştan kurulur; sonra Baz'daki değişiklik ona ulaşmaz."""
    base, r1, g1 = world["base"], world["r1"], world["g1"]
    with Session(db_engine) as s:
        sid = scenarios.create_copy(s, NAME + " yeni", base, follows_base=True)["Id"]
        s.commit()
    try:
        assert state(db_engine, sid) == 0                                                    # yeni senaryo: önbellek yok
        assert ensure(db_engine, world, sid) == {base: "built", sid: "built"}                # ilk kullanımda kurulur
        assert stored(db_engine, sid) == {} and state(db_engine, sid) == 1                   # kendi girişi yok: Baz'ın satırlarını okur
        total = same_as_scratch(db_engine, world, sid)

        with db_engine.connect() as c:                                                       # Baz'ın grup çalışma düzeninde günlük kapasiteyi değiştirir (fark satırı)
            base_row, start, end = c.execute(sa.text("SELECT TOP 1 Id, ValidFrom, ValidTo FROM param.WorkPattern WHERE ScenarioDefinitionId = :s "
                                                     "AND ResourceGroupId = :g AND BaseRowId IS NULL ORDER BY ValidFrom"), {"s": base, "g": g1}).one()
        diff(db_engine, "WorkPattern", sid, base_row, DailyCapacity=10)
        fire(db_engine, triggers.entry_changed, sid, group_id=g1, ranges=[(start, end)])
        own = stored(db_engine, sid)
        assert own and all(k[1] == g1 for k in own) and all(v[2] == 10.0 for v in own.values())
        assert same_as_scratch(db_engine, world, sid) == total

        with Session(db_engine) as s:
            scenarios.detach(s, sid)
            s.commit()
        assert stored(db_engine, sid) == {} and state(db_engine, sid) == 0                   # Baz'dan ayrıldı: önbelleği düştü
        assert ensure(db_engine, world, sid) == {sid: "built"}                               # artık Baz kurulmaz; senaryo tamamını kendisi tutar
        assert len(stored(db_engine, sid)) == same_as_scratch(db_engine, world, sid) == total
        assert all(stored(db_engine, sid)[k][2] == 10.0 for k in own)                        # farkı tam kopyaya işlendi

        before = stored(db_engine, sid)
        efficiency(db_engine, base, r1, 50, world["start"], None)                            # ayrıldıktan sonra Baz değişikliği ulaşmaz
        done = fire(db_engine, triggers.entry_changed, base, resource_id=r1, ranges=[(world["start"], None)])
        assert sid not in done and stored(db_engine, sid) == before
        same_as_scratch(db_engine, world, sid)
    finally:
        with Session(db_engine) as s:
            scenarios.delete(s, sid)
            s.commit()
    assert stored(db_engine, sid) == {} and state(db_engine, sid) == 0                       # silinen senaryonun önbelleği kalmaz


# --- önbellek: kurulum, ufuk, sürüm; senaryonun yaşam döngüsü; yönetim komutu -----------------------------------------------

def test_cache_is_built_once_and_follows_the_horizon(db_engine, world, clean):
    """Kuruluysa hiçbir şey yapılmaz; ufuk ilerleyince geçmiş gün silinir ve yalnız eksik günler hesaplanır; hesap sürümü ya da veri versiyonu
    değişince baştan kurulur."""
    base, follower = world["base"], world["follower"]
    start, end = world["start"], world["end"]
    assert ensure(db_engine, world, follower) == {base: "built", follower: "built"}
    assert ensure(db_engine, world, follower) == {base: "ready", follower: "ready"}
    snapshot = stored(db_engine, base)

    with Session(db_engine) as s:                                                            # ufuk bir gün ilerledi, iki gün uzadı
        assert cache.ensure(s, CACHE, follower, start + timedelta(days=1), end + timedelta(days=2))[follower] in ("extended", "trimmed")
    moved = stored(db_engine, base)
    assert {k[2] for k in moved} >= {end + timedelta(days=2)} and min(k[2] for k in moved) == start   # Baz izleyen adına yalnız genişler
    assert all(moved[k] == snapshot[k] for k in snapshot)                                    # var olan günlere dokunulmadı
    with Session(db_engine) as s:                                                            # Baz'ın kendi isteği geçmiş günü siler
        assert cache.ensure(s, CACHE, base, start + timedelta(days=1), end + timedelta(days=2))[base] == "trimmed"
    assert min(k[2] for k in stored(db_engine, base)) == start + timedelta(days=1)

    with Session(db_engine) as s:
        newer = dataclasses.replace(CACHE, code_version=CACHE.code_version + 1)              # hesap kodu değişti
        assert cache.ensure(s, newer, base, start, end)[base] == "built"
        assert cache.ensure(s, CACHE, base, start, end)[base] == "built"
        s.execute(sa.text("UPDATE cache.PeriodCacheState SET DataVersionId = -1 WHERE ScenarioDefinitionId = :s"), {"s": base})   # veri versiyonu değişti
        s.commit()
        assert cache.ensure(s, CACHE, base, start, end)[base] == "built"
        assert cache.ensure(s, CACHE, base, start, end)[base] == "ready"
    assert same_as_scratch(db_engine, world, base) == len(snapshot)


def test_scenario_lifecycle_and_commands(db_engine, world, clean, capsys):
    """Pasif yapılan ve silinen senaryonun önbelleği düşer; yönetim komutu (status, drop, rebuild) girişlere dokunmaz."""
    base, r1 = world["base"], world["r1"]
    with Session(db_engine) as s:
        sid = scenarios.create_copy(s, NAME + " ömür", base, follows_base=True)["Id"]
        s.commit()
    try:
        efficiency(db_engine, sid, r1, 44, world["start"], world["start"] + timedelta(days=6))
        assert ensure(db_engine, world, sid)[sid] == "built" and 0 < len(stored(db_engine, sid)) <= 7
        with Session(db_engine) as s:
            scenarios.set_active(s, sid, False)                                              # pasif senaryonun önbelleği tutulmaz
            s.commit()
        assert stored(db_engine, sid) == {} and state(db_engine, sid) == 0
        assert ensure(db_engine, world, sid)[sid] == "built"
    finally:
        with Session(db_engine) as s:
            scenarios.delete(s, sid)
            s.commit()
    assert stored(db_engine, sid) == {} and state(db_engine, sid) == 0

    ensure(db_engine, world, base)
    with db_engine.connect() as c:
        entries = [c.execute(sa.text(f"SELECT COUNT(*) FROM param.[{t}]")).scalar() for t in TABLES]
    assert periods_cli(["status"]) == 0 and f"senaryo {base}" in capsys.readouterr().out
    assert periods_cli(["drop", "--scenario", str(base)]) == 0 and stored(db_engine, base) == {}
    assert periods_cli(["rebuild", "--scenario", str(base)]) == 0
    assert "kuruldu" in capsys.readouterr().out and same_as_scratch(db_engine, world, base) == len(stored(db_engine, base))
    with db_engine.connect() as c:
        assert entries == [c.execute(sa.text(f"SELECT COUNT(*) FROM param.[{t}]")).scalar() for t in TABLES]   # önbellek veri değildir
