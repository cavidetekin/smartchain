"""Model kısıtları, 7.10 (K-189): kaynak grubunun kısıtsız kapasite çarpanı ve hedef doluluğu; Kapasite yönetimi listelerinde ana verinin bütün
alanları, ilişkili alanlar ve Lokasyon alanı. Sentetik v0'da (Smartchain_test); kendi senaryolarını açar, yazdığını geri alır (sentetik değerlere
dokunmaz).

Sabitlenenler: liste her senaryoda her güncel kaynak grubunu tek satır verir; değer hücreye yazılır, boşaltılınca kalkar; doğrulamalar (çarpan
en az 1, hedef 0'dan büyük ve en çok 100); değer kritik olmayan gruba da girilir, motor yalnız kritik ve güncel grupları okur; Baz + fark
(K-176) beş sırada: (a) önce Baz sonra senaryo, (b) önce senaryo sonra Baz, (c) fark kaldırma, (d) Baz'da silme, (e) Baz'ı izlemeyen senaryo;
eski çift kayıtların birleşmesi; Geçmiş kaynak grubu kimliğiyle; End user görür, yazamaz.
"""
import json

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app import modelconstraints as rules
from app.api.permissions import END_USER, KEY_USER
from app.data.synthetic import dataset as d
from app.engine.data import SqlPlanningData

from auth_helpers import auth
from test_capacity import _sql, clean, world  # noqa: F401  (fixture'lar)
from test_capacity_entries import api, people  # noqa: F401

pytestmark = pytest.mark.db

LIST = "model-constraints-resource-groups"
URL = "/api/model-constraints/resource-groups"
F, T = rules.FACTOR, rules.TARGET
OTHER = d.BOTTLENECK_GROUP   # Baz'a değer yazılan ikinci grup: sentetik veride hiçbir senaryoda değeri yok (sentetik satırlar değişmesin)


@pytest.fixture
def groups(db_engine, clean):  # noqa: F811
    """Kaynak grupları koda göre; test sonunda bu testin Geçmiş satırları silinir."""
    with db_engine.connect() as c:
        found = {r.Code: {"id": r.Id, "critical": bool(r.IsCritical)} for r in c.execute(sa.text("SELECT Id, Code, IsCritical FROM core.ResourceGroup WHERE VersionTo IS NULL"))}
    yield found
    with db_engine.begin() as c:
        _sql(c, "DELETE FROM adm.FieldChange WHERE Source = N'Model kısıtları'")


def rows(api, scenario: int, **body) -> dict[str, dict]:  # noqa: F811
    r = api.post(f"/api/{LIST}/query", json={"limit": 100, "scenario_id": scenario, **body})
    assert r.status_code == 200, r.text
    found = r.json()["rows"]
    assert len({x["Code"] for x in found}) == len(found), "her senaryoda her grup tek satır"
    return {x["Code"]: x for x in found}


def seen(api, scenario: int, code: str) -> tuple:  # noqa: F811
    r = rows(api, scenario)[code]
    return r[F], r[T], r["Origin"]


def put(api, scenario: int, changes: list[tuple], expect: int = 200):  # noqa: F811
    r = api.put(f"{URL}?scenario_id={scenario}", json={"changes": [{"id": i, "field": f, "value": v} for i, f, v in changes]})
    assert r.status_code == expect, r.text
    return r.json() if expect == 200 else r.json()["error"]


def restore(api, scenario: int, group: int) -> int:  # noqa: F811
    return api.post(f"{URL}/{group}/restore?scenario_id={scenario}").status_code


def stored(db_engine, scenario: int, group: int) -> list[dict]:
    with db_engine.connect() as c:
        return [dict(r) for r in c.execute(sa.text(f"SELECT * FROM param.{rules.TABLE} WHERE ScenarioDefinitionId = :s AND ResourceGroupId = :g ORDER BY Id"),
                                           {"s": scenario, "g": group}).mappings()]


def history(api, keys: list[str]) -> list[dict]:  # noqa: F811
    r = api.post("/api/record-history/query", json={"limit": 100, "sort": [{"field": "At", "dir": "asc"}], "filters": [
        {"field": "TableName", "op": "in", "values": [rules.TABLE]}, {"field": "RecordKey", "op": "in", "values": keys}]})
    assert r.status_code == 200, r.text
    return r.json()["rows"]


def engine_values(db_engine, scenario: int) -> dict[int, tuple]:
    with Session(db_engine) as s:
        version = s.execute(sa.text("SELECT MAX(Id) FROM adm.DataVersion")).scalar()
        return {x["ResourceGroupId"]: (x[F] and float(x[F]), x[T] and float(x[T])) for x in SqlPlanningData(s, version, scenario).model_constraints()}


def test_parse_and_show():
    """Veritabanısız: boş kaldırır; virgül ve yüzde işareti kabul edilir; sınırlar; yazım."""
    assert rules.parse(F, "") == (None, None) and rules.parse(T, None) == (None, None)
    assert rules.parse(F, "1,5")[0] == 1.5 and rules.parse(F, 1)[0] == 1 and rules.parse(F, "0,99")[1] == "En az 1 olmalı."
    assert rules.parse(T, "%85")[0] == 85 and rules.parse(T, "100")[0] == 100
    assert [rules.parse(T, v)[1] for v in ("0", "100,01", "-5")] == ["0'dan büyük, en çok 100 olmalı."] * 3
    assert rules.parse(F, "abc")[1] == "Sayı olmalı." and rules.parse(F, "1,234")[0] == rules.parse(F, "1,23")[0]
    assert (rules.show(F, 1.5), rules.show(T, 85), rules.show(T, "87.50"), rules.show(F, None)) == ("1,50", "%85", "%87,5", None)


def test_list_has_one_row_per_group_and_reads_the_scenario(api, db_engine, world, groups):  # noqa: F811
    """Her güncel kaynak grubu bir satır (kaydı olmayan dahil); sentetik değerler; "Kaynağı"; izleyen senaryo Baz'dan okur; Standart alanlar (Lokasyon
    başta), ana verinin öteki alanları kapalı ve İlişkili alanlar (Lokasyon)."""
    base, follower = world["base"], world["follower"]
    got = rows(api, base)
    assert set(got) == set(groups) and all(got[c]["Id"] == groups[c]["id"] for c in groups)
    for code, factor, target in d.MODEL_CONSTRAINTS:
        assert (got[code][F], got[code][T], got[code]["Origin"], got[code]["CanRestore"]) == (factor, target, "Baz", False)
    assert (got["KALITE"][F], got["KALITE"][T], got["KALITE"]["Origin"]) == (None, None, None)          # kaydı yok: satır var, değer ve "Kaynağı" boş
    assert not groups[d.FASON_NO_CAPACITY]["critical"] and got[d.FASON_NO_CAPACITY]["IsCritical"] is False
    assert {c: (r[F], r[T], r["Origin"]) for c, r in rows(api, follower).items()} == {c: (r[F], r[T], r["Origin"]) for c, r in got.items()}

    cols = api.get(f"/api/{LIST}/columns").json()
    shown = [c["field"] for c in cols["columns"] if c["default_visible"]]
    assert shown == ["LocationCode", "Code", "Name", "IsCritical", "CapacityUnit", F, T, "Origin"] and cols["scenario_list"] is True
    labels = {c["field"]: c["label"] for c in cols["columns"]}
    assert (labels["LocationCode"], labels["Code"], labels["Name"], labels[F], labels[T], labels["Origin"]) == (
        "Lokasyon", "Kaynak grubu", "Ad", "Kısıtsız kapasite çarpanı", "Hedef doluluk (%)", "Kaynağı")
    assert {"IsMachine", "IsActive"} <= set(labels)                                                           # ana verinin öteki alanları Alanlar'da
    assert [r["label"] for r in cols["relations"]] == ["Lokasyon", "Fasoncu"]
    related = api.post(f"/api/{LIST}/query", json={"limit": 100, "scenario_id": base, "fields": ["Code", F, "LocationCode", "LocationId/Name"]})
    assert related.status_code == 200 and {r["LocationCode"] for r in related.json()["rows"]} == {d.LOCATION_CODE} and all(r["LocationId/Name"] for r in related.json()["rows"])


def test_values_are_written_in_the_cell_and_validated(api, db_engine, world, groups, people):  # noqa: F811
    """Baz: değer yazılır, değişir, boşaltılınca kalkar (iki değer de boşsa satır silinir); doğrulamalar hücre başına; hepsi ya da hiçbiri; Geçmiş
    kaynak grubu kimliğiyle ve "Değiştiren"le; denetim izi."""
    base, g = world["base"], groups["KALITE"]["id"]
    assert put(api, base, [(g, F, "1,5"), (g, T, 80)]) == {"saved": 2}
    (row,) = stored(db_engine, base, g)
    assert (float(row[F]), float(row[T]), row["BaseRowId"], row["UpdatedBy"]) == (1.5, 80.0, None, people[KEY_USER])
    assert seen(api, base, "KALITE") == (1.5, 80.0, "Baz")
    assert put(api, base, [(g, F, 2)]) == {"saved": 1} and stored(db_engine, base, g)[0]["Id"] == row["Id"]          # yerinde güncellenir
    assert put(api, base, [(g, F, 2)]) == {"saved": 0}                                                             # aynı değer: değişiklik yok

    # doğrulamalar: hiçbiri kaydedilmez
    other = groups["TASLAMA"]["id"]
    err = put(api, base, [(g, F, "0,8"), (g, T, 120), (other, T, 50), (other, F, "x")], expect=422)
    assert {(p["id"], p["field"]): p["problem"] for p in err["details"]} == {
        (g, F): "En az 1 olmalı.", (g, T): "0'dan büyük, en çok 100 olmalı.", (other, F): "Sayı olmalı."}
    assert stored(db_engine, base, other) == [] and float(stored(db_engine, base, g)[0][T]) == 80.0
    assert put(api, base, [(999999, F, 2)], expect=422)["details"][0]["problem"] == "Kaynak grubu güncel veride yok."
    assert put(api, base, [(g, "Code", "X")], expect=422)["details"][0]["problem"] == "Bu alan düzenlenemez."

    # boşaltma: tek değer kalır; ikisi de boşalınca satır silinir
    assert put(api, base, [(g, T, None)]) == {"saved": 1} and stored(db_engine, base, g)[0][T] is None
    assert put(api, base, [(g, F, "")]) == {"saved": 1} and stored(db_engine, base, g) == []
    assert rows(api, base)["KALITE"]["Origin"] is None
    assert put(api, base, [(g, T, "%75")]) == {"saved": 1} and stored(db_engine, base, g)[0]["Id"] != row["Id"]      # yeniden yazılınca yeni satır

    # Geçmiş kaynak grubu kimliğiyle: satır silinip yeniden yazılsa da kopmaz
    assert [(h["FieldLabel"], h["OldValue"], h["NewValue"], h["ChangedBy"]) for h in history(api, [str(g)])] == [
        ("Kısıtsız kapasite çarpanı", None, "1,50", "Kapasite Planlamacı"), ("Hedef doluluk (%)", None, "%80", "Kapasite Planlamacı"),
        ("Kısıtsız kapasite çarpanı", "1,50", "2,00", "Kapasite Planlamacı"), ("Hedef doluluk (%)", "%80", None, "Kapasite Planlamacı"),
        ("Kısıtsız kapasite çarpanı", "2,00", None, "Kapasite Planlamacı"), ("Hedef doluluk (%)", None, "%75", "Kapasite Planlamacı")]
    assert {h["SourceText"] for h in history(api, [str(g)])} == {"Model kısıtları · Kapasite Planlamacı"}
    with db_engine.connect() as c:
        audits = c.execute(sa.text("SELECT Action, ObjectType, ObjectKey, ScenarioName FROM adm.AuditLog WHERE UserId = :u AND Action = N'Model kısıtı değişti' ORDER BY Id"),
                           {"u": people[KEY_USER]}).all()
    assert audits and {(a.ObjectType, a.ObjectKey) for a in audits} == {("Model kısıtları", "Kaynak grubu KALITE")}


def test_non_critical_group_accepts_values_but_engine_reads_only_critical(api, db_engine, world, groups):  # noqa: F811
    """Giriş kısıtlanmaz (K-189 demo): kritik olmayan gruba da değer girilir ve saklanır; motor yalnız kritik ve güncel grupların değerini okur.
    Grup kritik olmaktan çıkınca değeri durur, motora gitmez; yeniden kritik olunca uygulanır."""
    base, follower, g, fason = world["base"], world["follower"], groups["KALITE"]["id"], groups[d.FASON_NO_CAPACITY]["id"]
    assert put(api, base, [(fason, F, 2), (fason, T, 70)]) == {"saved": 2}
    assert seen(api, base, d.FASON_NO_CAPACITY) == (2.0, 70.0, "Baz") and seen(api, follower, d.FASON_NO_CAPACITY) == (2.0, 70.0, "Baz")
    put(api, base, [(g, F, "1,5")])
    put(api, follower, [(g, F, 3)])
    mine = engine_values(db_engine, base)
    assert mine[g] == (1.5, None) and engine_values(db_engine, follower)[g] == (3.0, None) and fason not in mine      # kritik olmayan motora gitmez
    assert {groups[c]["id"]: (f, t) for c, f, t in d.MODEL_CONSTRAINTS}.items() <= mine.items()
    assert all(groups[c]["critical"] for c in groups if groups[c]["id"] in mine)
    with Session(db_engine) as s, pytest.raises(ValueError):
        SqlPlanningData(s, 1).model_constraints()

    with db_engine.begin() as c:                                                                             # grup kritik olmaktan çıktı (ERP'den)
        _sql(c, "UPDATE core.ResourceGroup SET IsCritical = 0 WHERE Id = :g AND VersionTo IS NULL", g=g)
    try:
        assert g not in engine_values(db_engine, base) and g not in engine_values(db_engine, follower)
        assert put(api, base, [(g, F, 2)]) == {"saved": 1} and seen(api, base, "KALITE")[0] == 2.0              # değer yine girilir, saklanır
        assert g not in engine_values(db_engine, base)
    finally:
        with db_engine.begin() as c:
            _sql(c, "UPDATE core.ResourceGroup SET IsCritical = 1 WHERE Id = :g AND VersionTo IS NULL", g=g)
    assert engine_values(db_engine, base)[g] == (2.0, None)                                                   # yeniden kritik: saklı değer uygulanır
    put(api, base, [(fason, F, None), (fason, T, None)])


# --- Baz + fark: beş sıra (K-189 demo bulguları 2, 3, 4) -------------------------------------------------------------------------------------

def test_a_base_first_then_scenario(api, db_engine, world, groups):  # noqa: F811
    """(a) Önce Baz, sonra izleyen senaryo: senaryodaki değişiklik fark satırıdır (yalnız değişen alan); senaryoda yeni değer görünür, "Kaynağı"
    Senaryo farkı, Baz değeri saklı; Baz değişmez; Baz'daki öteki alan akar; Baz'daki değere dönünce fark kalkar; boşaltma da farktır."""
    base, follower, g = world["base"], world["follower"], groups["KALITE"]["id"]
    put(api, base, [(g, F, "1,5"), (g, T, 80)])
    base_row = stored(db_engine, base, g)[0]["Id"]

    assert put(api, follower, [(g, F, 2)]) == {"saved": 1}
    (diff,) = stored(db_engine, follower, g)
    assert (diff["BaseRowId"], diff["OverriddenFields"], float(diff[F])) == (base_row, f",{F},", 2.0)
    theirs = rows(api, follower)["KALITE"]
    assert (theirs[F], theirs[T], theirs["Origin"], theirs["OverriddenFields"], theirs["CanRestore"]) == (2.0, 80.0, "Senaryo farkı", f",{F},", True)
    assert json.loads(theirs["BaseValues"]) == {F: 1.5, T: 80} and seen(api, base, "KALITE") == (1.5, 80.0, "Baz")   # Baz değişmedi
    put(api, base, [(g, T, 70)])                                                                             # Baz'daki öteki alan izleyene akar
    assert seen(api, follower, "KALITE") == (2.0, 70.0, "Senaryo farkı")
    put(api, base, [(g, F, 2)])                                                                              # Baz senaryonun değerine geldi: fark kalmadı
    assert seen(api, follower, "KALITE") == (2.0, 70.0, "Baz") and rows(api, follower)["KALITE"]["CanRestore"] is False
    put(api, base, [(g, F, "1,5")])                                                                          # Baz yine ayrıldı: senaryonun değeri durur
    assert seen(api, follower, "KALITE") == (2.0, 70.0, "Senaryo farkı")
    assert put(api, follower, [(g, F, "1,5")]) == {"saved": 1} and stored(db_engine, follower, g) == []       # Baz'daki değere dönüş: fark satırı kalkar
    assert seen(api, follower, "KALITE") == (1.5, 70.0, "Baz")
    assert put(api, follower, [(g, T, None)]) == {"saved": 1}                                                 # boşaltma da farktır
    assert seen(api, follower, "KALITE") == (1.5, None, "Senaryo farkı") and seen(api, base, "KALITE") == (1.5, 70.0, "Baz")
    # Geçmiş: izleyen senaryodaki değişiklik kendi anahtarında, senaryo adıyla; Baz'ın geçmişine karışmaz
    theirs_history = history(api, [f"{g}@{follower}"])
    assert [(h["OldValue"], h["NewValue"]) for h in theirs_history] == [("1,50", "2,00"), ("2,00", "1,50"), ("%70", None)]
    assert all("pytest kapasite izleyen" in h["SourceText"] for h in theirs_history)


def test_b_scenario_first_then_base(api, db_engine, world, groups):  # noqa: F811
    """(b) Önce izleyen senaryo (Baz'da değer yokken), sonra Baz: senaryoda grup tek satır kalır; senaryonun değeri geçerlidir, "Kaynağı" Senaryo
    farkı, ipucunda Baz değeri. Veride senaryonun kendi satırı Baz satırının fark satırına çevrilir. Sonraki değişiklik de doğru çalışır."""
    base, follower, g = world["base"], world["follower"], groups["KALITE"]["id"]
    assert put(api, follower, [(g, F, "1,25")]) == {"saved": 1}
    (own,) = stored(db_engine, follower, g)
    assert own["BaseRowId"] is None and seen(api, follower, "KALITE") == (1.25, None, "Senaryo") and seen(api, base, "KALITE") == (None, None, None)
    assert rows(api, follower)["KALITE"]["CanRestore"] is True                                               # Baz'da değer yok: kaldırınca boşalır

    assert put(api, base, [(g, F, "1,5"), (g, T, 80)]) == {"saved": 2}                                        # sonra Baz'a değer girildi
    theirs = rows(api, follower)["KALITE"]                                                                   # tek satır (rows() bunu da doğrular)
    assert (theirs[F], theirs[T], theirs["Origin"]) == (1.25, None, "Senaryo farkı")                          # senaryonun değeri geçerli (iki alan da senaryodan)
    assert json.loads(theirs["BaseValues"]) == {F: 1.5, T: 80} and theirs["OverriddenFields"] == f",{F},{T}," and theirs["CanRestore"] is True
    (merged,) = stored(db_engine, follower, g)                                                               # veride de tek satır: fark satırına çevrildi
    assert merged["BaseRowId"] == stored(db_engine, base, g)[0]["Id"] and merged["OverriddenFields"] == f",{F},{T},"

    assert put(api, follower, [(g, F, 3)]) == {"saved": 1}                                                    # senaryoda değiştirmek artık doğru satıra yazar
    assert seen(api, follower, "KALITE") == (3.0, None, "Senaryo farkı") and seen(api, base, "KALITE") == (1.5, 80.0, "Baz")
    assert len(stored(db_engine, follower, g)) == 1


def test_b_legacy_double_rows_are_merged_on_read_and_in_data(api, db_engine, world, groups):  # noqa: F811
    """Eski çift kayıt (7.10'un ilk demosundaki veri): senaryoda grubun hem kendi satırı hem Baz satırı. Okuma tek satır verir (senaryonun değeri,
    Senaryo farkı); `normalize` ve her yazma veriyi fark satırına çevirir; aynı değerse kendi satırı silinir."""
    base, follower, g, other = world["base"], world["follower"], groups["KALITE"]["id"], groups[OTHER]["id"]
    with db_engine.begin() as c:                                                                             # birleştirme olmadan yazılmış hâli elle kur
        for scenario, group, factor in ((follower, g, 1.25), (base, g, 1.5), (follower, other, 1.75), (base, other, 1.75)):
            _sql(c, f"INSERT INTO param.{rules.TABLE} (ScenarioDefinitionId, IsValid, ResourceGroupId, {F}, UpdatedAt) VALUES (:s, 1, :g, :f, SYSUTCDATETIME())",
                 s=scenario, g=group, f=factor)
    assert seen(api, follower, "KALITE") == (1.25, None, "Senaryo farkı") and seen(api, follower, OTHER) == (1.75, None, "Baz")   # ekranda tek satır
    assert engine_values(db_engine, follower)[g] == (1.25, None)
    with Session(db_engine) as s:
        fixed = rules.normalize(s)
        s.commit()
    assert fixed == 2
    (diff,) = stored(db_engine, follower, g)
    assert diff["BaseRowId"] == stored(db_engine, base, g)[0]["Id"] and diff["OverriddenFields"] == f",{F}," and float(diff[F]) == 1.25
    assert stored(db_engine, follower, other) == []                                                          # Baz'la aynı değer: senaryonun satırı gereksiz
    assert seen(api, follower, "KALITE") == (1.25, None, "Senaryo farkı") and seen(api, follower, OTHER) == (1.75, None, "Baz")
    with Session(db_engine) as s:
        assert rules.normalize(s) == 0                                                                       # ikinci çalıştırma bir şey değiştirmez


def test_c_restore_returns_to_base(api, db_engine, world, groups):  # noqa: F811
    """(c) "Senaryo farkını kaldır": Baz'ı izleyen senaryoda değeri senaryodan gelen her satırda çalışır; değer Baz'a döner, Baz'da değer yoksa
    boşalır. Farkı olmayan satırda, Baz'da ve Baz'ı izlemeyen senaryoda 409."""
    base, follower, free, g, own = world["base"], world["follower"], world["free"], groups["KALITE"]["id"], groups[OTHER]["id"]
    put(api, base, [(g, F, "1,5"), (g, T, 80)])
    put(api, follower, [(g, T, 60)])
    assert restore(api, follower, g) == 200 and stored(db_engine, follower, g) == [] and seen(api, follower, "KALITE") == (1.5, 80.0, "Baz")
    assert restore(api, follower, g) == 409                                                                  # fark yok

    put(api, follower, [(own, F, "1,25")])                                                                   # Baz'da değeri olmayan grup: senaryonun kendi değeri
    assert restore(api, follower, own) == 200 and stored(db_engine, follower, own) == [] and seen(api, follower, OTHER) == (None, None, None)

    put(api, follower, [(own, F, "1,25")])                                                                   # (b) sırasından sonra da çalışır: Baz'ın değerine döner
    put(api, base, [(own, F, 2)])
    assert seen(api, follower, OTHER) == (1.25, None, "Senaryo farkı")
    assert restore(api, follower, own) == 200 and seen(api, follower, OTHER) == (2.0, None, "Baz") and stored(db_engine, follower, own) == []

    assert restore(api, base, g) == 409                                                                      # Baz'da fark kavramı yok
    put(api, free, [(g, F, 3)])
    assert restore(api, free, g) == 409 and seen(api, free, "KALITE")[0] == 3.0                               # Baz'ı izlemeyen senaryoda da
    assert [(h["OldValue"], h["NewValue"]) for h in history(api, [f"{g}@{follower}"])] == [("%80", "%60"), ("%60", "%80")]


def test_d_deleting_in_base(api, db_engine, world, groups):  # noqa: F811
    """(d) Baz'da silme (iki değer de boşalır): farkı olmayan izleyen senaryoda değer kalkar; farkı olan senaryoda fark senaryonun kendi satırına
    döner (yalnız değiştirdiği alan; Baz'dan okuduğu alan boşalır). Baz'a yeniden değer girilince yine fark olur."""
    base, follower, g, other = world["base"], world["follower"], groups["KALITE"]["id"], groups[OTHER]["id"]
    put(api, base, [(g, F, "1,5"), (g, T, 80), (other, F, 2)])
    put(api, follower, [(g, F, 3)])                                                                          # g: fark (çarpan); hedef Baz'dan
    assert seen(api, follower, "KALITE") == (3.0, 80.0, "Senaryo farkı") and seen(api, follower, OTHER) == (2.0, None, "Baz")

    assert put(api, base, [(g, F, None), (g, T, None), (other, F, None)]) == {"saved": 3}                     # Baz'da ikisi de silindi
    assert stored(db_engine, base, g) == [] and stored(db_engine, base, other) == []
    assert seen(api, follower, OTHER) == (None, None, None)                                              # farkı yoktu: değer kalktı
    assert seen(api, follower, "KALITE") == (3.0, None, "Senaryo")                                           # farkı vardı: senaryonun kendi değeri; hedef boşaldı
    (mine,) = stored(db_engine, follower, g)
    assert (mine["BaseRowId"], mine["OverriddenFields"], float(mine[F]), mine[T]) == (None, None, 3.0, None)
    assert engine_values(db_engine, follower)[g] == (3.0, None) and g not in engine_values(db_engine, base)

    put(api, base, [(g, F, "1,5")])                                                                          # Baz'a yeniden değer: senaryonunki yine fark
    assert seen(api, follower, "KALITE") == (3.0, None, "Senaryo farkı") and len(stored(db_engine, follower, g)) == 1


def test_e_scenario_not_following_base(api, db_engine, world, groups):  # noqa: F811
    """(e) Baz'ı izlemeyen senaryo: açılırken Baz'ın değerlerini tam kopyayla alır (kendi satırları); sonrası bağımsızdır: Baz'daki değişiklik
    akmaz, senaryodaki değişiklik Baz'ı etkilemez; "Kaynağı" Senaryo; fark ve "Senaryo farkını kaldır" yok."""
    from app.params import scenario_tables, scenarios
    base, free, g = world["base"], world["free"], groups["KALITE"]["id"]
    assert "ResourceGroupConstraint" in {t.name for t in scenario_tables.TABLES if t.kind == scenario_tables.DATA}
    mine = rows(api, free)
    for code, factor, target in d.MODEL_CONSTRAINTS:                                                         # tam kopya: kendi satırları
        assert (mine[code][F], mine[code][T], mine[code]["Origin"], mine[code]["CanRestore"]) == (factor, target, "Senaryo", False)
    with db_engine.connect() as c:
        assert c.execute(sa.text(f"SELECT COUNT(*) FROM param.{rules.TABLE} WHERE ScenarioDefinitionId = :s AND BaseRowId IS NOT NULL"), {"s": free}).scalar() == 0

    put(api, base, [(g, F, "1,5")])
    assert seen(api, free, "KALITE") == (None, None, None)                                                   # Baz'daki değişiklik akmaz
    put(api, free, [(g, F, 4), (groups["TORNA"]["id"], T, 50)])
    assert seen(api, free, "KALITE") == (4.0, None, "Senaryo") and seen(api, free, "TORNA")[1:] == (50.0, "Senaryo")
    assert seen(api, base, "KALITE") == (1.5, None, "Baz") and seen(api, base, "TORNA")[2] == "Baz"            # Baz etkilenmez
    assert seen(api, base, "TORNA")[1] == next(t for c, _, t in d.MODEL_CONSTRAINTS if c == "TORNA")
    (row,) = stored(db_engine, free, g)
    assert row["BaseRowId"] is None and row["OverriddenFields"] is None
    put(api, base, [(g, F, None)])
    assert seen(api, free, "KALITE") == (4.0, None, "Senaryo")                                               # Baz'da silme de etkilemez

    with Session(db_engine) as s:                                                                            # kopyalama ve silme: kayıt defteri
        copy = scenarios.create_copy(s, "pytest kapasite model kopya", world["follower"], follows_base=True)["Id"]
        s.commit()
        scenarios.delete(s, copy)
        s.commit()
    with db_engine.connect() as c:
        assert c.execute(sa.text(f"SELECT COUNT(*) FROM param.{rules.TABLE} WHERE ScenarioDefinitionId = :s"), {"s": copy}).scalar() == 0


def test_end_user_reads_but_cannot_write(api, world, groups, people):  # noqa: F811
    end = auth(people[END_USER])
    assert api.post(f"/api/{LIST}/query", json={"limit": 100, "scenario_id": world["base"]}, headers=end).status_code == 200
    g = groups["KALITE"]["id"]
    assert api.put(f"{URL}?scenario_id={world['base']}", json={"changes": [{"id": g, "field": F, "value": 2}]}, headers=end).status_code == 403
    assert api.post(f"{URL}/{g}/restore?scenario_id={world['follower']}", headers=end).status_code == 403


def test_capacity_lists_offer_master_fields_related_fields_and_location(api, world):  # noqa: F811
    """Kapasite yönetimi (K-189): Kaynak grubu ve Kaynak listeleri ana verinin bütün alanlarını sunar ve İlişkili alanlar çalışır. Lokasyon, kaynağın ya
    da grubun kodunu gösteren her listede listenin kendi alanıdır: Standart'ta açık, kodun solunda; fabrika takviminde yok."""
    base = world["base"]

    def columns(name: str) -> dict:
        r = api.get(f"/api/{name}/columns")
        assert r.status_code == 200, r.text
        return r.json()

    def shown(name: str) -> list[str]:
        return [c["field"] for c in columns(name)["columns"] if c["default_visible"]]

    def master_fields(name: str) -> set[str]:
        return {c["field"] for c in columns(name)["columns"]} - {"ManualState"}

    groups_ = columns("capacity-resource-groups")
    assert shown("capacity-resource-groups") == ["LocationCode", "Code", "Name", "Type", "IsCritical", "CapacityUnit", "ResourceCount"]
    assert {c["field"] for c in groups_["columns"]} == master_fields("master-resource-group") | {"ResourceCount"}
    assert {"IsEmployee", "IsMachine", "IsSubcontractor", "IsActive", "SubcontractorCode"} <= {c["field"] for c in groups_["columns"]}
    assert [r["label"] for r in groups_["relations"]] == ["Lokasyon", "Fasoncu"]
    got = api.post("/api/capacity-resource-groups/query", json={"limit": 100, "fields": ["Code", "ResourceCount", "LocationCode", "IsMachine", "LocationId/Name"]})
    assert got.status_code == 200, got.text
    isl3 = next(r for r in got.json()["rows"] if r["Code"] == "ISL3")
    assert (isl3["ResourceCount"], isl3["LocationCode"], isl3["IsMachine"]) == (3, d.LOCATION_CODE, True) and isl3["LocationId/Name"]

    resources = columns("capacity-resources")
    assert shown("capacity-resources") == ["LocationCode", "Code", "Name", "Groups", "ProductionLocation", "IsActive", "RemainingOvertimeMonth", "RemainingOvertimeYear"]
    extra = {"Groups", "RemainingOvertimeMonth", "RemainingOvertimeYear"}
    assert {c["field"] for c in resources["columns"]} == (master_fields("master-resource") - {"RemainingOverTimeMonth", "RemainingOverTimeYear"}) | extra
    assert [r["label"] for r in resources["relations"]] == ["Lokasyon"]
    got = api.post("/api/capacity-resources/query", json={"limit": 100, "fields": ["Code", "Groups", "ResourceType", "LocationCode", "LocationId/Name"],
                                                          "filters": [{"field": "Code", "op": "equals", "value": "M3-01"}]})
    assert got.status_code == 200 and [(r["Groups"], r["LocationCode"], bool(r["LocationId/Name"])) for r in got.json()["rows"]] == [("ISL3", d.LOCATION_CODE, True)]

    # giriş ve geçerlilik listeleri: Lokasyon listenin kendi alanı (kodun solunda); satır grup, kaynak ve lokasyon kimliğini taşır (üçü de birinci seviye ilişki)
    entries = ("capacity-work-patterns", "capacity-efficiency", "capacity-overtime-limits", "capacity-downtime")
    validity = ("capacity-work-patterns-validity", "capacity-efficiency-validity", "capacity-overtime-limits-validity")
    for name in (*entries, *validity):
        cols = columns(name)
        head = shown(name)
        assert "LocationCode" in head and head.index("LocationCode") < head.index("Code"), (name, head)
        assert next(c["label"] for c in cols["columns"] if c["field"] == "LocationCode") == "Lokasyon"
        assert [r["label"] for r in cols["relations"]] == ["Kaynak grubu", "Kaynak", "Lokasyon"], name
        got = api.post(f"/api/{name}/query", json={"limit": 100, "scenario_id": base, "fields": ["LocationCode", "Code", "ResourceGroupId/IsCritical", "ResourceId/Name", "LocationId/Name"]})
        assert got.status_code == 200, (name, got.text)
        found = got.json()["rows"]
        assert found and {r["LocationCode"] for r in found} == {d.LOCATION_CODE} and all(r["LocationId/Name"] for r in found), name   # grup ve kaynak kaydında dolu
    by_level = api.post("/api/capacity-work-patterns/query", json={"limit": 100, "scenario_id": base,
                                                                   "fields": ["Level", "Code", "ResourceGroupId/Code", "ResourceId/Code"]}).json()["rows"]
    assert all((r["ResourceGroupId/Code"], r["ResourceId/Code"]) == ((r["Code"], None) if r["Level"] == "Grup" else (None, r["Code"])) for r in by_level)
    leave = api.post("/api/capacity-downtime/query", json={"limit": 100, "scenario_id": base, "filters": [{"field": "Origin", "op": "in", "values": ["ERP"]}]}).json()["rows"]
    assert leave and {r["LocationCode"] for r in leave} == {d.LOCATION_CODE}                                 # çalışan izni (ERP) satırında da
    calendar = columns("capacity-factory-calendar")
    assert calendar["relations"] == [{"path": "LocationId", "label": "Lokasyon"}] and calendar["columns"][0]["field"] == "LocationCode"   # lokasyon bazlı (K-194)

    # Kapasite özeti: Lokasyon listenin alanı (tablo görünümünde kodun solunda); Standart pivotun satır alanı değil
    summary = columns("period-resource-group")
    head = shown("period-resource-group")
    assert head[0] == "LocationCode" and "LocationCode" not in json.dumps(summary["standard_pivot"]), head
    got = api.post("/api/period-resource-group/query", json={"limit": 5, "scenario_id": base, "fields": ["LocationCode", "ResourceGroupCode"]})
    assert got.status_code == 200 and {r["LocationCode"] for r in got.json()["rows"]} == {d.LOCATION_CODE}
