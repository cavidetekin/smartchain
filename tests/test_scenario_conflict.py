"""Senaryo çakışması (K-191 madde 10; A-47): elle müdahale edilen yerde senaryo, edilmeyen yerde Baz geçerlidir. Baz'ı izleyen senaryoda aynı sahip ve
aynı başlangıç için hem senaryonun kendi kaydı hem Baz'ın kaydı olursa tek kayıt görünür: senaryonun değeri geçerlidir, "Kaynağı" Senaryo farkı,
Baz'daki değer saklıdır; "Senaryo farkını kaldır" Baz'a döndürür. Kural çözümleme katmanında tek yerdedir (`app/params/resolve.py`, `KEYS`).

Kapasite yönetimi'nin başlangıcı tekil üç giriş türü (Çalışma düzeni, Verimlilik, Ek mesai limiti) için beş sıra ayrı ayrı: (a) önce Baz sonra
senaryo, (b) önce senaryo sonra Baz, (c) fark kaldırma, (d) Baz'da silme, (e) Baz'ı izlemeyen senaryo. Geçerlilik ve Kapasite özeti senaryonun
değerini kullanır. Tedarikçi üst limitinin aynı sıraları `tests/test_supplier_limits.py`'dedir. Smartchain_test'te; yazdığını geri alır.
"""
import json
from datetime import timedelta

import pytest
import sqlalchemy as sa

from app.params import resolve

from test_capacity import clean, world  # noqa: F401  (fixture'lar)
from test_capacity_entries import EF, LIST, OT, TABLE, WEEK, WP, act, api, edit, new, people, raw, rows, tr  # noqa: F401

pytestmark = pytest.mark.db

# tür → (değer alanı, kaydın öteki alanları, Baz değeri, senaryo değeri, senaryoda sonraki değer)
KINDS = {WP: ("DailyCapacity", WEEK, 10, 4, 6), EF: ("EfficiencyPct", {}, 90, 70, 60), OT: ("DailyLimit", {}, 2, 3, 5)}
ALL = list(KINDS)


@pytest.fixture
def at(world):  # noqa: F811
    """Sahip (kaynak) ve başlangıç günü: ufkun içinde, sentetik kayıtların başlangıcından farklı bir gün."""
    return {"r": world["r1"], "day": world["start"] + timedelta(days=45)}


def add(api, kind: str, scenario: int, at: dict, value) -> int:  # noqa: F811
    field, more, *_ = KINDS[kind]
    return new(api, kind, scenario, ResourceId=at["r"], ValidFrom=tr(at["day"]), **{field: value}, **more)


def mine(api, kind: str, scenario: int, at: dict) -> list[dict]:  # noqa: F811
    """Senaryonun listesinde bu sahip ve başlangıçtaki kayıtlar (çakışmada tek satır olmalı)."""
    return [r for r in rows(api, kind, scenario) if r["ResourceId"] == at["r"] and r["ValidFrom"] == at["day"].isoformat()]


def seen(api, kind: str, scenario: int, at: dict) -> tuple:  # noqa: F811
    found = mine(api, kind, scenario, at)
    assert len(found) == 1, (kind, [(r["Id"], r["Origin"]) for r in found])
    return float(found[0][KINDS[kind][0]]), found[0]["Origin"]


def applied(api, kind: str, scenario: int, at: dict) -> set:  # noqa: F811
    """Geçerlilik: bu kaynağa başlangıç gününde uygulanan değer (kaynak birden çok gruptaysa her grupta aynı)."""
    r = api.post(f"/api/{LIST[kind]}-validity/query", json={"limit": 100, "scenario_id": scenario,
                                                           "filters": [{"field": "OwnerKeys", "op": "contains", "values": [f",r{at['r']},"]}]})
    assert r.status_code == 200, r.text
    day = at["day"].isoformat()
    return {float(x[KINDS[kind][0]]) for x in r.json()["rows"] if x["ResourceId"] == at["r"] and x["ValidFrom"] <= day and (x["ValidTo"] is None or x["ValidTo"] >= day)}


def stored(db_engine, kind: str, scenario: int) -> list[dict]:
    return raw(db_engine, kind, scenario)


@pytest.mark.parametrize("kind", ALL)
def test_a_base_first_then_scenario(api, db_engine, world, clean, at, kind):  # noqa: F811
    """(a) Önce Baz, sonra senaryo: senaryodaki değişiklik Baz satırının farkıdır; tek kayıt; Baz değişmez; Geçerlilik senaryonun değerini uygular."""
    base, follower = world["base"], world["follower"]
    field, _, v_base, v_mine, _ = KINDS[kind]
    row = add(api, kind, base, at, v_base)
    assert seen(api, kind, follower, at) == (v_base, "Baz")
    edit(api, kind, follower, [(row, field, v_mine)])
    assert seen(api, kind, follower, at) == (v_mine, "Senaryo farkı") and seen(api, kind, base, at) == (v_base, "Baz")
    [diff] = stored(db_engine, kind, follower)
    assert (diff["BaseRowId"], diff["OverriddenFields"]) == (row, f",{field},")
    assert applied(api, kind, follower, at) == {float(v_mine)} and applied(api, kind, base, at) == {float(v_base)}
    # aynı sahip ve başlangıçla senaryoda ikinci kayıt açılamaz (Baz satırı görünür olduğu için)
    again = api.post(f"/api/capacity/{kind}?scenario_id={follower}", json={"values": {"ResourceId": at["r"], "ValidFrom": tr(at["day"]), field: v_mine, **KINDS[kind][1]}})
    assert again.status_code == 422 and again.json()["error"]["details"][0]["field"] == "ValidFrom"


@pytest.mark.parametrize("kind", ALL)
def test_b_scenario_first_then_base(api, db_engine, world, clean, at, kind):  # noqa: F811
    """(b) Önce senaryo (Baz'da kayıt yokken), sonra Baz: senaryoda tek kayıt görünür; senaryonun değeri geçerlidir, "Kaynağı" Senaryo farkı, Baz'daki
    değer saklıdır; Geçerlilik senaryonun değerini uygular (bugüne kadar Baz'ınki uygulanıyordu). Sonraki değişiklik senaryonun kaydına yazılır."""
    base, follower = world["base"], world["follower"]
    field, _, v_base, v_mine, v_next = KINDS[kind]
    own = add(api, kind, follower, at, v_mine)
    assert seen(api, kind, follower, at) == (v_mine, "Senaryo") and mine(api, kind, base, at) == []
    theirs = add(api, kind, base, at, v_base)                                    # Baz'ın denetimi yalnız Baz'a bakar: kayıt açılır
    [row] = mine(api, kind, follower, at)                                        # senaryoda tek kayıt
    assert (float(row[field]), row["Origin"], row["Id"], row["StoredId"]) == (v_mine, "Senaryo farkı", own, own)
    assert float(json.loads(row["BaseValues"])[field]) == v_base and f",{field}," in row["OverriddenFields"]
    assert seen(api, kind, base, at) == (v_base, "Baz")
    assert applied(api, kind, follower, at) == {float(v_mine)} and applied(api, kind, base, at) == {float(v_base)}
    edit(api, kind, follower, [(own, field, v_next)])                            # senaryonun kaydı yerinde değişir; yeni satır açılmaz
    assert seen(api, kind, follower, at) == (v_next, "Senaryo farkı") and seen(api, kind, base, at) == (v_base, "Baz")
    assert [r["Id"] for r in stored(db_engine, kind, follower)] == [own] and [r["Id"] for r in stored(db_engine, kind, base) if r["Id"] == theirs] == [theirs]
    assert applied(api, kind, follower, at) == {float(v_next)}
    # Baz'dan okunan satırın kuralları örten kayıtta da geçerli: senaryoda silinemez diye bir kısıt yok (senaryonun kendi kaydıdır)
    if kind == EF:                                                               # Kapasite özeti de senaryonun değerini kullanır
        with db_engine.connect() as c:
            code = c.execute(sa.text("SELECT TOP 1 g.Code FROM core.ResourceGroupMember m JOIN core.ResourceGroup g ON g.Id = m.ResourceGroupId AND g.VersionTo IS NULL "
                                     "WHERE m.ResourceId = :r AND m.VersionTo IS NULL ORDER BY g.Code"), {"r": at["r"]}).scalar_one()

        def available(scenario: int) -> float:
            found = api.post("/api/period-resource-group/query", json={
                "limit": 100, "scenario_id": scenario, "fields": ["ResourceGroupCode", "PeriodStart", "PeriodEnd", "AvailableCapacity"],
                "filters": [{"field": "ResourceGroupCode", "op": "in", "values": [code]}]})
            assert found.status_code == 200, found.text
            return sum(float(x["AvailableCapacity"] or 0) for x in found.json()["rows"] if x["PeriodEnd"] >= at["day"].isoformat())
        assert available(follower) < available(base)                            # senaryoda verimlilik %60, Baz'da %90


@pytest.mark.parametrize("kind", ALL)
def test_c_restore_returns_to_base(api, db_engine, world, clean, at, kind):  # noqa: F811
    """(c) "Senaryo farkını kaldır": örten kayıtta senaryonun kaydı silinir, Baz'ın kaydı görünür; farkta fark satırı silinir. Farkı olmayan satırda 409."""
    base, follower = world["base"], world["follower"]
    field, _, v_base, v_mine, _ = KINDS[kind]
    own = add(api, kind, follower, at, v_mine)
    theirs = add(api, kind, base, at, v_base)
    assert seen(api, kind, follower, at) == (v_mine, "Senaryo farkı")
    act(api, kind, follower, own, "restore")
    assert seen(api, kind, follower, at) == (v_base, "Baz") and stored(db_engine, kind, follower) == []
    assert applied(api, kind, follower, at) == {float(v_base)}
    assert api.post(f"/api/capacity/{kind}/{theirs}/restore?scenario_id={follower}").status_code == 409     # fark yok
    edit(api, kind, follower, [(theirs, field, v_mine)])                         # (a) sırasındaki fark da kaldırılır
    act(api, kind, follower, theirs, "restore")
    assert seen(api, kind, follower, at) == (v_base, "Baz") and stored(db_engine, kind, follower) == []


@pytest.mark.parametrize("kind", ALL)
def test_d_deleting_in_base(api, db_engine, world, clean, at, kind):  # noqa: F811
    """(d) Baz'da silme: örtülen Baz kaydı silinince senaryonun kaydı kendi kaydı olarak kalır ("Kaynağı" Senaryo); farkı olan Baz kaydı silinince
    senaryoda da görünmez."""
    base, follower = world["base"], world["follower"]
    field, _, v_base, v_mine, _ = KINDS[kind]
    own = add(api, kind, follower, at, v_mine)
    theirs = add(api, kind, base, at, v_base)
    assert seen(api, kind, follower, at) == (v_mine, "Senaryo farkı")
    act(api, kind, base, theirs, None)                                           # Baz'da sil
    assert seen(api, kind, follower, at) == (v_mine, "Senaryo") and mine(api, kind, base, at) == []
    assert [r["Id"] for r in stored(db_engine, kind, follower)] == [own] and applied(api, kind, follower, at) == {float(v_mine)}


@pytest.mark.parametrize("kind", ALL)
def test_e_scenario_not_following_base(api, db_engine, world, clean, at, kind):  # noqa: F811
    """(e) Baz'ı izlemeyen senaryo: kendi kaydı Baz'ın aynı anahtarlı kaydından etkilenmez; "Kaynağı" Senaryo, fark ve "Senaryo farkını kaldır" yok."""
    base, free = world["base"], world["free"]
    field, _, v_base, v_mine, _ = KINDS[kind]
    own = add(api, kind, free, at, v_mine)
    add(api, kind, base, at, v_base)
    assert seen(api, kind, free, at) == (v_mine, "Senaryo") and seen(api, kind, base, at) == (v_base, "Baz")
    assert api.post(f"/api/capacity/{kind}/{own}/restore?scenario_id={free}").status_code == 409
    assert applied(api, kind, free, at) == {float(v_mine)}


def test_rule_lives_in_the_resolution_layer():
    """Kural tek yerde: başlangıcı tekil tabloların anahtarı `resolve.KEYS`'te; birleşen türlerde (duruş, fabrika takvimi) çakışma kuralı yok."""
    assert set(resolve.KEYS) == {"WorkPattern", "ResourceEfficiency", "OvertimeLimit", "SupplierLimit", "DemandPriority"}
    assert all(k[-1] == "ValidFrom" for name, (k, _) in resolve.KEYS.items() if name != "DemandPriority")     # tarihli girişlerde anahtar: sahip + başlangıç
    assert resolve.KEYS["DemandPriority"][0] == ("Level", "RecordId")                                            # öncelik grubu tarihsiz: kayıt başına tek değer (K-195)
    for table in ("ResourceDowntime", "FactoryCalendar"):
        assert "ShadowId" in resolve.sql(table) and "OUTER APPLY" not in resolve.sql(table)
    assert "OUTER APPLY" in resolve.sql("WorkPattern") and "NOT EXISTS" in resolve.sql("WorkPattern")


@pytest.mark.db
def test_detaching_from_base_keeps_one_record(api, db_engine, world, clean, at):  # noqa: F811
    """Baz'dan ayırma (materialize): senaryonun kaydının örttüğü Baz kaydı kopyalanmaz; ayrıldıktan sonra da tek kayıt kalır."""
    base, follower = world["base"], world["follower"]
    add(api, EF, follower, at, 70)
    add(api, EF, base, at, 90)
    from sqlalchemy.orm import Session
    with Session(db_engine) as s:
        resolve.materializer("ResourceEfficiency")(s, follower)
        got = [dict(r) for r in s.execute(sa.text("SELECT ResourceId, ValidFrom, EfficiencyPct, BaseRowId FROM param.ResourceEfficiency WHERE ScenarioDefinitionId = :s "
                                                  "AND ResourceId = :r AND ValidFrom = :d"), {"s": follower, "r": at["r"], "d": at["day"]}).mappings()]
        s.rollback()
    assert [(float(r["EfficiencyPct"]), r["BaseRowId"]) for r in got] == [(70.0, None)]
