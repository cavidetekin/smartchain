"""Kapasite yönetimi, 7.9b (K-185): giriş listeleri ve giriş uçları. Sentetik v0'da (Smartchain_test); kendi senaryolarını açar, yazdığını geri alır.

Sabitlenenler: listeler senaryonun çözümlenmiş satırlarını gösterir (Kaynağı: Baz · Senaryo farkı · Senaryo · ERP); yeni kayıt, hücre değişikliği,
silme, geçersiz yapma ve senaryo farkını kaldırma doğrulamalarıyla; Baz'da yerinde, izleyen senaryoda fark satırıyla (K-176); her işlem aynı
işlemde geçmişi ve denetim izini yazar, kapasite önbelleğinin yalnız etkilenen kaynak ve günlerini yeniler (önbellek = sıfırdan hesap); End user
görür, yazamaz.
"""
import json
from datetime import date, timedelta

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.api.permissions import END_USER, KEY_USER

from auth_helpers import auth, delete_users, ensure_user
from test_capacity import changed, clean, ensure, same_as_scratch, stored, world  # noqa: F401  (fixture'lar ve yardımcılar)

pytestmark = pytest.mark.db

WP, EF, OT, DT, FC = "work-patterns", "efficiency", "overtime-limits", "downtime", "factory-calendar"
LIST = {WP: "capacity-work-patterns", EF: "capacity-efficiency", OT: "capacity-overtime-limits", DT: "capacity-downtime", FC: "capacity-factory-calendar"}
TABLE = {WP: "WorkPattern", EF: "ResourceEfficiency", OT: "OvertimeLimit", DT: "ResourceDowntime", FC: "FactoryCalendar"}
WEEK = {"DayMon": "Tam", "DayTue": "Tam", "DayWed": "Tam", "DayThu": "Tam", "DayFri": "Tam", "DaySat": "Yarım", "DaySun": "Çalışılmıyor"}


def tr(day: date) -> str:
    return f"{day:%d.%m.%Y}"


@pytest.fixture(scope="module")
def people(db_engine):
    with db_engine.begin() as c:
        users = {KEY_USER: ensure_user(c, "pytest.cape.key", KEY_USER, "Kapasite Planlamacı"), END_USER: ensure_user(c, "pytest.cape.end", END_USER)}
        c.execute(sa.text("UPDATE adm.AppUser SET ScenarioDefinitionId = NULL WHERE Id IN (:a, :b)"), {"a": users[KEY_USER], "b": users[END_USER]})
    yield users
    with db_engine.begin() as c:
        c.execute(sa.text("DELETE FROM adm.FieldChange WHERE Source = N'Kapasite yönetimi' AND UserId IN (:a, :b)"), {"a": users[KEY_USER], "b": users[END_USER]})
        delete_users(c, list(users.values()))


@pytest.fixture(scope="module")
def api(db_engine, people):
    client = TestClient(create_app(), raise_server_exceptions=False)
    client.headers.update(auth(people[KEY_USER]))
    return client


def rows(api, kind_or_list: str, scenario: int, **body) -> list[dict]:
    name = LIST.get(kind_or_list, kind_or_list)
    r = api.post(f"/api/{name}/query", json={"limit": 100, "scenario_id": scenario, **body})
    assert r.status_code == 200, r.text
    return r.json()["rows"]


def one(api, kind: str, scenario: int, row_id: int) -> dict:
    found = [r for r in rows(api, kind, scenario, filters=[]) if r["Id"] == row_id]
    assert len(found) == 1, (kind, row_id, len(found))
    return found[0]


def new(api, kind: str, scenario: int, expect: int = 201, **values):
    r = api.post(f"/api/capacity/{kind}?scenario_id={scenario}", json={"values": values})
    assert r.status_code == expect, r.text
    return r.json()["id"] if expect == 201 else r.json()["error"]


def edit(api, kind: str, scenario: int, changes: list[tuple], expect: int = 200):
    r = api.put(f"/api/capacity/{kind}?scenario_id={scenario}", json={"changes": [{"id": i, "field": f, "value": v} for i, f, v in changes]})
    assert r.status_code == expect, r.text
    return r.json() if expect == 200 else r.json()["error"]


def act(api, kind: str, scenario: int, row_id: int, action: str | None, expect: int = 200):
    r = api.delete(f"/api/capacity/{kind}/{row_id}?scenario_id={scenario}") if action is None else api.post(f"/api/capacity/{kind}/{row_id}/{action}?scenario_id={scenario}")
    assert r.status_code == expect, r.text
    return r.json()


def problems(error: dict) -> dict:
    return {d["field"]: d["problem"] for d in error["details"]}


def history(api, kind: str, keys: list[str]) -> list[dict]:
    r = api.post("/api/record-history/query", json={"limit": 100, "sort": [{"field": "At", "dir": "asc"}], "filters": [
        {"field": "TableName", "op": "in", "values": [TABLE[kind]]}, {"field": "RecordKey", "op": "in", "values": keys}]})
    assert r.status_code == 200, r.text
    return r.json()["rows"]


def audits(db_engine, user_id: int, action: str) -> list[dict]:
    with db_engine.connect() as c:
        found = c.execute(sa.text("SELECT ObjectType, ObjectKey, OldValue, NewValue, ScenarioName FROM adm.AuditLog WHERE UserId = :u AND Action = :a ORDER BY Id"),
                          {"u": user_id, "a": action}).mappings().all()
    return [dict(r) for r in found]


def raw(db_engine, kind: str, scenario: int) -> list[dict]:
    with db_engine.connect() as c:
        return [dict(r) for r in c.execute(sa.text(f"SELECT * FROM param.[{TABLE[kind]}] WHERE ScenarioDefinitionId = :s ORDER BY Id"), {"s": scenario}).mappings()]


# --- listeler -------------------------------------------------------------------------------------------------------------------------------

def test_lists_show_the_resolved_rows_of_the_scenario(api, db_engine, world, clean):
    """Kaynak grubu ve Kaynak listeleri; giriş listelerinde Baz'da "Baz", izleyen senaryoda Baz'dan okunan satırlar; ERP izinleri salt okunur satır;
    kartın süzmesi (grubun kendisi ve üyeleri; yalnız kaynak)."""
    base, follower, g1, r1 = world["base"], world["follower"], world["g1"], world["r1"]
    groups = {r["Id"]: r for r in rows(api, "capacity-resource-groups", base)}
    assert groups[g1]["Code"] == "ISL3" and groups[g1]["ResourceCount"] == len([1 for g, _ in world["members"] if g == g1]) and groups[g1]["IsCritical"] is True
    resources = {r["Id"]: r for r in rows(api, "capacity-resources", base)}
    assert resources[r1]["Code"] == "M3-01" and resources[r1]["Groups"] == "ISL3"
    worker = resources[world["worker"]]
    assert set(worker["Groups"].split(", ")) >= {"CG-KAL", "CG-MON"}
    in_group = rows(api, "capacity-resources", base, filters=[{"field": "GroupKeys", "op": "contains", "value": f",{g1},"}])
    assert {r["Id"] for r in in_group} == {r for g, r in world["members"] if g == g1}

    cols = api.get("/api/capacity-work-patterns/columns").json()["columns"]
    assert [c["label"] for c in cols] == ["Seviye", "Kod", "Başlangıç", "Bitiş", "Günlük kapasite", "Birim", "Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz", "Kaynağı", "Geçerli"]
    in_base, in_follower = rows(api, WP, base), rows(api, WP, follower)
    assert in_base and {r["Origin"] for r in in_base} == {"Baz"} and {r["Origin"] for r in in_follower} == {"Baz"}
    assert [r["Id"] for r in in_base] == [r["Id"] for r in in_follower]                       # izleyen senaryo Baz'ın satırlarını aynı kimlikle okur
    isl3 = next(r for r in in_base if r["Code"] == "ISL3")
    assert (isl3["Level"], isl3["DailyCapacity"], isl3["CapacityUnit"], isl3["DayMon"], isl3["DaySun"], isl3["IsValid"]) == ("Grup", 15.0, "SAAT", "Tam", "—", True)
    assert {r["Origin"] for r in rows(api, WP, world["free"])} == {"Senaryo"}                # izlemeyen senaryo: tam kopya, kendi satırları

    downtime = rows(api, DT, base)
    leaves = [r for r in downtime if r["Origin"] == "ERP"]
    assert leaves and all(r["Id"] < 0 and r["DowntimeType"] == "Çalışan izni" and r["Level"] == "Kaynak" for r in leaves)
    assert [r for r in downtime if r["Origin"] == "Baz"]
    # kartta süzme: grup kartı grubun kendisine ve üyelerine girilmiş kayıtları; kaynak kartı yalnız kaynağınkileri gösterir
    row_id = new(api, EF, base, ResourceId=r1, ValidFrom=tr(world["start"]), EfficiencyPct=90)
    card = rows(api, EF, base, filters=[{"field": "OwnerKeys", "op": "contains", "value": f",g{g1},"}])
    assert [r["Id"] for r in card] == [row_id]
    assert [r["Id"] for r in rows(api, EF, base, filters=[{"field": "OwnerKeys", "op": "contains", "value": f",r{r1},"}])] == [row_id]
    assert rows(api, EF, base, filters=[{"field": "OwnerKeys", "op": "contains", "value": f",r{world['r2']},"}]) == []
    # çoklu seçimde kart (K-171, K-187): "herhangi biri"; seçili iki kaynağın, seçili iki grubun kayıtları
    other = new(api, EF, base, ResourceId=world["worker"], ValidFrom=tr(world["start"]), EfficiencyPct=95)
    both = rows(api, EF, base, filters=[{"field": "OwnerKeys", "op": "contains", "values": [f",r{r1},", f",r{world['worker']},"]}])
    assert {r["Id"] for r in both} == {row_id, other}
    groups_card = rows(api, EF, base, filters=[{"field": "OwnerKeys", "op": "contains", "values": [f",g{g1},", f",g{world['labor']},"]}])
    assert {r["Id"] for r in groups_card} == {row_id, other}                                  # işçi CG-MON üyesi
    several = rows(api, "capacity-resources", base, filters=[{"field": "GroupKeys", "op": "contains", "values": [f",{g1},", f",{world['quality']},"]}])
    assert {r["Id"] for r in several} >= {r1, world["worker"]} and resources[r1]["CapacityUnit"] == "SAAT"
    bad = api.post(f"/api/{LIST[EF]}/query", json={"limit": 5, "scenario_id": base, "filters": [{"field": "OwnerKeys", "op": "contains", "value": "x", "values": ["y"]}]})
    assert bad.status_code == 422


# --- yeni kayıt ve doğrulamalar -------------------------------------------------------------------------------------------------------------

def test_new_entries_of_every_kind_update_the_summary(api, db_engine, world, people, clean):
    """Beş girişin her birinden yeni kayıt; kayıt aynı işlemde önbelleğin yalnız etkilenen kaynak ve günlerini yeniler; geçmiş ve denetim izi."""
    base, g1, r1, r2 = world["base"], world["g1"], world["r1"], world["r2"]
    ensure(db_engine, world, base)
    first = stored(db_engine, base)
    a, b = world["start"] + timedelta(days=7), world["start"] + timedelta(days=13)

    wp = new(api, WP, base, ResourceId=r1, ValidFrom=tr(a), ValidTo=tr(b), DailyCapacity="16,5", **WEEK)       # tablodaki yazımla: Türkçe sayı ve gün adları
    after = stored(db_engine, base)
    moved = changed(first, after)
    assert moved and all(k[0] == r1 and a <= k[2] <= b for k in moved) and {after[k][2] for k in moved} == {16.5}   # yalnız o kaynak, o günler
    assert same_as_scratch(db_engine, world, base) == len(first)
    row = one(api, WP, base, wp)
    assert (row["Level"], row["Code"], row["ValidFrom"], row["ValidTo"], row["DailyCapacity"], row["DaySat"], row["DaySun"], row["Origin"]) == (
        "Kaynak", "M3-01", a.isoformat(), b.isoformat(), 16.5, "Yarım", "—", "Baz")

    ef = new(api, EF, base, ResourceGroupId=g1, ValidFrom=a.isoformat(), EfficiencyPct=80)                    # gruba, açık bitişli, ISO tarih
    ot = new(api, OT, base, ResourceId=r2, ValidFrom=tr(a), ValidTo=tr(b), DailyLimit=2)
    dt = new(api, DT, base, ResourceId=r2, DowntimeType="Arıza", Reason="Mil arızası", StartDate=tr(a), EndDate=tr(a + timedelta(days=1)))
    fc = new(api, FC, base, StartDate=tr(b), Name="pytest tatil", DayValue="Yarım gün")                        # bitiş boş: tek gün
    assert one(api, FC, base, fc)["EndDate"] == b.isoformat() and one(api, FC, base, fc)["DayValue"] == "Yarım gün"
    assert one(api, DT, base, dt)["DowntimeType"] == "Arıza" and one(api, OT, base, ot)["DailyLimit"] == 2.0 and one(api, EF, base, ef)["ValidTo"] is None
    assert same_as_scratch(db_engine, world, base) == len(first)                              # beş girişten sonra önbellek = sıfırdan hesap
    final = stored(db_engine, base)
    assert {k[0] for k in changed(first, final)} >= {r1, r2} and all(k[2] >= a for k in changed(first, final) if k[1] == g1)

    # geçmiş: "Kayıt oluştu", Değiştiren ve Kaynak; denetim izi senaryo kolonuyla
    [created] = history(api, WP, [str(wp)])
    assert (created["NewValue"], created["ChangedBy"], created["SourceText"]) == ("Kayıt oluştu", "Kapasite Planlamacı", "Kapasite yönetimi · Kapasite Planlamacı")
    log = audits(db_engine, people[KEY_USER], "Kapasite girişi eklendi")
    assert [(x["ObjectType"], x["ScenarioName"]) for x in log[-5:]] == [("Çalışma düzeni", "Baz"), ("Verimlilik", "Baz"), ("Ek mesai limiti", "Baz"),
                                                                       ("Bakım ve duruş", "Baz"), ("Fabrika takvimi", "Baz")]
    assert log[-5]["ObjectKey"] == f"Kaynak M3-01 · {tr(a)}" and json.loads(log[-5]["NewValue"])["DailyCapacity"] == "16,5" and json.loads(log[-5]["NewValue"])["DaySat"] == "Yarım"
    assert log[-1]["ObjectKey"].startswith("pytest tatil")
    # uyarı (engel değil): bitişi geçmişte kalan kayıt
    past = api.post(f"/api/capacity/{DT}?scenario_id={base}", json={"values": {"ResourceId": r1, "DowntimeType": "Diğer", "StartDate": "01.01.2020", "EndDate": "02.01.2020"}})
    assert past.status_code == 201 and past.json()["warnings"] == ["Bitişi geçmişte kalan kayıt."]


@pytest.mark.parametrize("kind, values, field, problem", [
    (WP, {"ValidFrom": "01.02.2027", "DailyCapacity": 8, **WEEK}, "ResourceGroupId", "Kaynak grubu ya da kaynaktan biri seçilmeli."),
    (WP, {"ResourceGroupId": "g1", "ResourceId": "r1", "ValidFrom": "01.02.2027", "DailyCapacity": 8, **WEEK}, "ResourceId", "Kaynak grubu ya da kaynaktan biri seçilmeli."),
    (WP, {"ResourceId": 999_999_999, "ValidFrom": "01.02.2027", "DailyCapacity": 8, **WEEK}, "ResourceId", "Güncel veride yok."),
    (WP, {"ResourceId": "r1", "DailyCapacity": 8, **WEEK}, "ValidFrom", "Boş bırakılamaz."),
    (WP, {"ResourceId": "r1", "ValidFrom": "2027/02/01", "DailyCapacity": 8, **WEEK}, "ValidFrom", "Tarih gg.aa.yyyy biçiminde girilmeli."),
    (WP, {"ResourceId": "r1", "ValidFrom": "10.02.2027", "ValidTo": "01.02.2027", "DailyCapacity": 8, **WEEK}, "ValidTo", "Bitiş başlangıçtan önce olamaz."),
    (WP, {"ResourceId": "r1", "ValidFrom": "01.02.2027", "DailyCapacity": 0, **WEEK}, "DailyCapacity", "Sıfırdan büyük olmalı."),
    (WP, {"ResourceId": "r1", "ValidFrom": "01.02.2027", "DailyCapacity": "sekiz", **WEEK}, "DailyCapacity", "Sayı girilmeli."),
    (WP, {"ResourceId": "r1", "ValidFrom": "01.02.2027", "DailyCapacity": 8}, "DayMon", "En az bir gün Tam ya da Yarım olmalı."),
    (WP, {"ResourceId": "r1", "ValidFrom": "01.02.2027", "DailyCapacity": 8, **WEEK, "DayMon": "Bazen"}, "DayMon", "Tam, Yarım ya da Çalışılmıyor seçilmeli."),
    (EF, {"ResourceId": "r1", "ValidFrom": "01.02.2027", "EfficiencyPct": 0}, "EfficiencyPct", "0'dan büyük, en çok 999,99 olmalı."),
    (EF, {"ResourceId": "r1", "ValidFrom": "01.02.2027", "EfficiencyPct": 1000}, "EfficiencyPct", "0'dan büyük, en çok 999,99 olmalı."),
    (EF, {"ResourceId": "r1", "ValidFrom": "01.02.2027", "EfficiencyPct": "85,123"}, "EfficiencyPct", "En çok 2 ondalık."),
    (OT, {"ResourceId": "r1", "ValidFrom": "01.02.2027", "DailyLimit": -1}, "DailyLimit", "Negatif olamaz."),
    (DT, {"ResourceId": "r1", "DowntimeType": "Tatil", "StartDate": "01.02.2027", "EndDate": "01.02.2027"}, "DowntimeType", "Şunlardan biri olmalı: Planlı bakım, Arıza, Diğer."),
    (DT, {"ResourceId": "r1", "DowntimeType": "Arıza", "StartDate": "01.02.2027"}, "EndDate", "Boş bırakılamaz."),
    (DT, {"ResourceId": "r1", "DowntimeType": "Arıza", "Reason": "x" * 256, "StartDate": "01.02.2027", "EndDate": "01.02.2027"}, "Reason", "En çok 255 karakter."),
    (FC, {"StartDate": "01.02.2027", "DayValue": "Çalışılmıyor"}, "Name", "Boş bırakılamaz."),
    (FC, {"StartDate": "01.02.2027", "Name": "Bayram", "DayValue": "Tam"}, "DayValue", "Çalışılmıyor ya da Yarım gün seçilmeli."),
    (FC, {"StartDate": "01.02.2027", "Name": "Bayram", "DayValue": "Çalışılmıyor", "ResourceId": "r1"}, "ResourceId", "Bilinmeyen alan."),
])
def test_validation_names_the_field_and_the_reason(api, db_engine, world, clean, kind, values, field, problem):
    values = {k: (world[v] if isinstance(v, str) and v in ("g1", "r1") else v) for k, v in values.items()}
    before = len(raw(db_engine, kind, world["base"]))
    error = new(api, kind, world["base"], expect=422, **values)
    assert error["code"] == "validation" and problems(error).get(field) == problem, error
    assert len(raw(db_engine, kind, world["base"])) == before                                 # reddedilen kayıt yazılmadı


def test_same_start_is_rejected_and_unknown_kind_is_not_found(api, db_engine, world, clean):
    base, r1, g1 = world["base"], world["r1"], world["g1"]
    day = tr(world["start"] + timedelta(days=30))
    first = new(api, EF, base, ResourceId=r1, ValidFrom=day, EfficiencyPct=90)
    error = new(api, EF, base, expect=422, ResourceId=r1, ValidFrom=day, EfficiencyPct=80)
    assert problems(error) == {"ValidFrom": "Bu kaynak ya da grup için aynı başlangıç tarihli başka bir kayıt var."}
    new(api, EF, base, ResourceGroupId=g1, ValidFrom=day, EfficiencyPct=80)                    # başka seviye (grup): olur
    new(api, EF, base, ResourceId=world["r2"], ValidFrom=day, EfficiencyPct=80)                # başka kaynak: olur
    act(api, EF, base, first, "invalidate")                                                    # geçersiz kayıt yeri tutmaz
    second = new(api, EF, base, ResourceId=r1, ValidFrom=day, EfficiencyPct=80)
    assert problems(api.post(f"/api/capacity/{EF}/{first}/validate?scenario_id={base}").json()["error"]) == {
        "ValidFrom": "Bu kaynak ya da grup için aynı başlangıç tarihli başka bir kayıt var."} and second
    assert api.post(f"/api/capacity/takvim?scenario_id={base}", json={"values": {}}).status_code == 404
    assert api.put(f"/api/capacity/{EF}?scenario_id={base}", json={"changes": []}).status_code == 422
    leave = next(r["Id"] for r in rows(api, DT, base) if r["Origin"] == "ERP")                 # çalışan izni (ERP) salt okunur
    assert edit(api, DT, base, [(leave, "Reason", "x")], expect=404)["code"] == "not_found" and act(api, DT, base, leave, None, expect=404)


# --- hücre değişikliği ------------------------------------------------------------------------------------------------------------------------

def test_cell_changes_are_all_or_nothing_and_leave_history(api, db_engine, world, people, clean):
    """Tablo içi düzenleme: biri reddedilirse hiçbiri kaydedilmez (hücre ve kayıt adıyla neden); geçen değişiklik geçmişe eski ve yeni değerle yazılır,
    önbellekte kaydın eski ve yeni aralığı yenilenir."""
    base, r1, g1 = world["base"], world["r1"], world["g1"]
    a, b = world["start"] + timedelta(days=7), world["start"] + timedelta(days=13)
    wp = new(api, WP, base, ResourceId=r1, ValidFrom=tr(a), ValidTo=tr(b), DailyCapacity=10, **WEEK)
    ef = new(api, EF, base, ResourceId=r1, ValidFrom=tr(a), EfficiencyPct=90)
    ensure(db_engine, world, base)
    before = stored(db_engine, base)

    error = edit(api, WP, base, [(wp, "DailyCapacity", "12,5"), (wp, "ValidTo", tr(a - timedelta(days=1))), (wp, "DayMon", "Hep")], expect=422)
    assert error["message"] == "Kaydedilmedi." and {(d["id"], d["field"]) for d in error["details"]} == {(wp, "ValidTo"), (wp, "DayMon")}
    assert {d["record"] for d in error["details"]} == {f"Kaynak M3-01 · {tr(a)}"}
    assert one(api, WP, base, wp)["DailyCapacity"] == 10.0 and stored(db_engine, base) == before          # hiçbiri yazılmadı
    locked = edit(api, WP, base, [(wp, "ResourceId", world["r2"])], expect=422)
    assert locked["details"][0]["problem"].startswith("Seviye ve kod kayıttan sonra değişmez")

    c = b + timedelta(days=3)
    done = edit(api, WP, base, [(wp, "DailyCapacity", "12,5"), (wp, "ValidTo", tr(c)), (wp, "DaySat", "—"), (wp, "DayMon", "Tam")])
    assert done["saved"] == 3                                                                 # Pzt zaten Tam: değişiklik sayılmaz
    row = one(api, WP, base, wp)
    assert (row["DailyCapacity"], row["ValidTo"], row["DaySat"]) == (12.5, c.isoformat(), "—")
    after = stored(db_engine, base)
    moved = changed(before, after)
    assert moved and all(k[0] == r1 and a <= k[2] <= c for k in moved) and max(k[2] for k in moved) > b      # eski ve yeni aralık
    assert same_as_scratch(db_engine, world, base) == len(before)

    past = history(api, WP, [str(wp)])
    assert [(h["FieldLabel"], h["OldValue"], h["NewValue"]) for h in past[1:]] == [
        ("Günlük kapasite", "10", "12,5"), ("Bitiş", tr(b), tr(c)), ("Cumartesi", "Yarım", "—")] or {h["OldValue"] for h in past[1:]} == {"10", tr(b), "Yarım"}
    assert {h["ChangedBy"] for h in past} == {"Kapasite Planlamacı"} and {h["SourceText"] for h in past} == {"Kapasite yönetimi · Kapasite Planlamacı"}
    [log] = audits(db_engine, people[KEY_USER], "Kapasite girişi değişti")[-1:]
    assert json.loads(log["OldValue"]) == {"DailyCapacity": "10", "ValidTo": tr(b), "DaySat": "Yarım"} and json.loads(log["NewValue"])["DailyCapacity"] == "12,5"
    assert edit(api, EF, base, [(ef, "EfficiencyPct", "90,00")])["saved"] == 0                 # aynı değer: değişiklik yok, geçmişe yazılmaz
    assert len(history(api, EF, [str(ef)])) == 1
    # silme: kendi satırı silinir; önbellek eski hâline döner
    act(api, WP, base, wp, None)
    act(api, EF, base, ef, None)
    assert same_as_scratch(db_engine, world, base) == len(before) and history(api, WP, [str(wp)])[-1]["NewValue"] == "Kayıt kapandı"
    assert all(v[2] == 15.0 for k, v in stored(db_engine, base).items() if k[0] == r1)        # kaynağın kendi düzeni kalktı: grubunki geçerli


# --- izleyen senaryo: fark, geçersiz yapma, farkı kaldırma ---------------------------------------------------------------------------------------

def test_follower_changes_a_base_row_through_a_difference_row(api, db_engine, world, people, clean):
    """İzleyen senaryoda Baz satırı değişince fark satırı oluşur (yalnız değişen alanlar); Baz değişmez; değer Baz'a dönünce fark kalkar;
    Baz satırı silinemez, geçersiz yapılır; "Senaryo farkını kaldır" Baz'a döndürür; Baz'daki değişiklik izleyen senaryoya akar."""
    base, follower, r1, g1 = world["base"], world["follower"], world["r1"], world["g1"]
    a, b = world["start"] + timedelta(days=7), world["start"] + timedelta(days=13)
    wp = new(api, WP, base, ResourceId=r1, ValidFrom=tr(a), ValidTo=tr(b), DailyCapacity=10, **WEEK)
    ensure(db_engine, world, follower)
    assert stored(db_engine, follower) == {} and one(api, WP, follower, wp)["Origin"] == "Baz"

    edit(api, WP, follower, [(wp, "DailyCapacity", 4)])
    seen = one(api, WP, follower, wp)
    assert (seen["Origin"], seen["DailyCapacity"], seen["ValidTo"], seen["OverriddenFields"]) == ("Senaryo farkı", 4.0, b.isoformat(), ",DailyCapacity,")
    assert json.loads(seen["BaseValues"])["DailyCapacity"] == 10.0 and seen["StoredId"] != wp     # ipucu için Baz'daki değer
    assert one(api, WP, base, wp)["DailyCapacity"] == 10.0 and one(api, WP, base, wp)["Origin"] == "Baz"
    [difference] = raw(db_engine, WP, follower)
    assert (difference["BaseRowId"], difference["OverriddenFields"], float(difference["DailyCapacity"])) == (wp, ",DailyCapacity,", 4.0)
    own = stored(db_engine, follower)
    assert own and all(k[0] == r1 and a <= k[2] <= b and v[2] == 4.0 for k, v in own.items())                # yalnız Baz'dan farklı çıkan satırlar
    same_as_scratch(db_engine, world, follower)
    # geçmiş senaryolu anahtarla; Kaynak'ta senaryonun adı; Baz'ın geçmişine karışmaz
    name = "pytest kapasite izleyen"
    assert [(h["OldValue"], h["NewValue"], h["SourceText"]) for h in history(api, WP, [f"{wp}@{follower}"])] == [("10", "4", f"Kapasite yönetimi · {name} · Kapasite Planlamacı")]
    assert len(history(api, WP, [str(wp)])) == 1
    assert audits(db_engine, people[KEY_USER], "Kapasite girişi değişti")[-1]["ScenarioName"] == name

    # Baz'daki değişiklik: değiştirilmeyen alan izleyen senaryoya akar, değiştirilen alan senaryonun değerinde kalır
    c = b + timedelta(days=2)
    edit(api, WP, base, [(wp, "ValidTo", tr(c)), (wp, "DailyCapacity", 11)])
    seen = one(api, WP, follower, wp)
    assert (seen["ValidTo"], seen["DailyCapacity"]) == (c.isoformat(), 4.0)
    assert {k[2] for k in stored(db_engine, follower)} >= {c} and same_as_scratch(db_engine, world, follower) and same_as_scratch(db_engine, world, base)

    # ikinci alan da değişir; ilki Baz'daki değere dönünce farktan çıkar; ikisi de dönünce fark satırı kalkar
    edit(api, WP, follower, [(wp, "DaySat", "Tam")])
    assert one(api, WP, follower, wp)["OverriddenFields"] == ",DailyCapacity,DaySat,"
    edit(api, WP, follower, [(wp, "DailyCapacity", 11)])
    assert one(api, WP, follower, wp)["OverriddenFields"] == ",DaySat," and len(raw(db_engine, WP, follower)) == 1
    edit(api, WP, follower, [(wp, "DaySat", "Yarım")])
    assert raw(db_engine, WP, follower) == [] and one(api, WP, follower, wp)["Origin"] == "Baz" and stored(db_engine, follower) == {}

    # Baz satırı izleyen senaryodan silinemez; geçersiz yapılır (Baz'da geçerli kalır); yeniden geçerli yapılır
    assert api.delete(f"/api/capacity/{WP}/{wp}?scenario_id={follower}").json()["error"]["code"] == "base_row"
    act(api, WP, follower, wp, "invalidate")
    seen = one(api, WP, follower, wp)
    assert (seen["IsValid"], seen["Origin"], seen["OverriddenFields"]) == (False, "Senaryo farkı", ",IsValid,") and one(api, WP, base, wp)["IsValid"] is True
    assert stored(db_engine, follower) and same_as_scratch(db_engine, world, follower)                       # o senaryoda kaynağın kendi düzeni yok sayılır
    act(api, WP, follower, wp, "validate")
    assert raw(db_engine, WP, follower) == [] and one(api, WP, follower, wp)["IsValid"] is True

    # "Senaryo farkını kaldır": değerler Baz'a döner; farkı olmayan satırda 409
    edit(api, WP, follower, [(wp, "DailyCapacity", 4), (wp, "ValidTo", tr(b))])
    act(api, WP, follower, wp, "invalidate")
    act(api, WP, follower, wp, "restore")
    seen = one(api, WP, follower, wp)
    assert (seen["Origin"], seen["DailyCapacity"], seen["ValidTo"], seen["IsValid"]) == ("Baz", 11.0, c.isoformat(), True)
    assert stored(db_engine, follower) == {} and same_as_scratch(db_engine, world, follower)
    assert api.post(f"/api/capacity/{WP}/{wp}/restore?scenario_id={follower}").json()["error"]["code"] == "no_difference"
    assert audits(db_engine, people[KEY_USER], "Senaryo farkı kaldırıldı")[-1]["ScenarioName"] == name
    assert len(history(api, WP, [f"{wp}@{follower}"])) >= 6                                  # fark kalksa da geçmişi durur

    # senaryonun kendi satırı: yalnız o senaryoda; silinir
    mine = new(api, EF, follower, ResourceId=r1, ValidFrom=tr(a), EfficiencyPct=50)
    assert one(api, EF, follower, mine)["Origin"] == "Senaryo" and all(r["Id"] != mine for r in rows(api, EF, base))
    assert stored(db_engine, follower) and same_as_scratch(db_engine, world, follower)
    act(api, EF, follower, mine, None)
    assert stored(db_engine, follower) == {}


def test_scenario_that_does_not_follow_base_edits_its_own_copy(api, db_engine, world, clean):
    """Baz'ı izlemeyen senaryo: satırlar kendi kopyasıdır; yerinde değişir ve silinir; Baz etkilenmez."""
    base, free = world["base"], world["free"]
    mine = next(r for r in rows(api, WP, free) if r["Code"] == "ISL3")
    theirs = next(r for r in rows(api, WP, base) if r["Code"] == "ISL3")
    assert mine["Id"] != theirs["Id"] and mine["Origin"] == "Senaryo"
    try:
        edit(api, WP, free, [(mine["Id"], "DailyCapacity", 14)])
        assert one(api, WP, free, mine["Id"])["DailyCapacity"] == 14.0 and one(api, WP, base, theirs["Id"])["DailyCapacity"] == 15.0
        assert raw(db_engine, WP, free)[0]["BaseRowId"] is None
    finally:
        edit(api, WP, free, [(mine["Id"], "DailyCapacity", 15)])


# --- yetki ve Geçmiş -------------------------------------------------------------------------------------------------------------------------

def test_end_user_reads_but_cannot_write(api, db_engine, world, people, clean):
    end = auth(people[END_USER])
    base, r1 = world["base"], world["r1"]
    for name in ("capacity-resource-groups", "capacity-resources", *LIST.values()):
        assert api.post(f"/api/{name}/query", headers=end, json={"limit": 5, "scenario_id": base}).status_code == 200, name
    row = new(api, EF, base, ResourceId=r1, ValidFrom=tr(world["start"]), EfficiencyPct=90)
    calls = [api.post(f"/api/capacity/{EF}?scenario_id={base}", headers=end, json={"values": {"ResourceId": r1, "ValidFrom": "01.02.2027", "EfficiencyPct": 80}}),
             api.put(f"/api/capacity/{EF}?scenario_id={base}", headers=end, json={"changes": [{"id": row, "field": "EfficiencyPct", "value": 80}]}),
             api.delete(f"/api/capacity/{EF}/{row}?scenario_id={base}", headers=end),
             api.post(f"/api/capacity/{EF}/{row}/invalidate?scenario_id={base}", headers=end),
             api.post(f"/api/capacity/{EF}/{row}/restore?scenario_id={base}", headers=end)]
    assert [r.status_code for r in calls] == [403] * 5 and one(api, EF, base, row)["EfficiencyPct"] == 90.0


def test_history_has_the_changed_by_column_everywhere(api):
    """Ortak Geçmiş listesi (Ana veri ve İşlem verisi kartlarında da): Değiştiren kolonu Kaynak'tan önce."""
    for name in ("record-history", "record-history-many"):
        labels = [c["label"] for c in api.get(f"/api/{name}/columns").json()["columns"]]
        assert labels[-2:] == ["Değiştiren", "Kaynak"], (name, labels)
