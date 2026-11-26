"""Pegging kuralları: parametreler (K-201; Parametreler › Pegging, fonksiyon 22): ölçütlerin tek tanımı (talep türleri Hedefler'le aynı kaynaktan),
başlangıç sırası, saklama ve doğrulama, senaryo kopyası, denetim izi, yetkiler, "Özel alokasyon"un yeri ve motor yükleyicisi.

Veritabanı testleri Baz'ın pegging satırlarını ve iki ayarını test sonunda eski hâline döndürür; senaryo kopyası işlem içinde açılır ve geri alınır."""
import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.main import create_app
from app.api.permissions import ADMIN, END_USER, KEY_USER, SYSTEM_OWNER
from app.engine import loader
from app.params import catalog as cat, pegging, scenario_tables, scenarios

from auth_helpers import auth, delete_users, ensure_user

NEED_START = [("Dönem", "Artan"), ("Kesin sipariş", None), ("Teklif", None), ("Beklemedeki sipariş", None), ("Tahmin", None), ("Üretim siparişi ihtiyacı", None),
              ("Üretim planı ihtiyacı", None), ("Öncelik grubu", "Artan"), ("İhtiyaç tarihi", "Artan"), ("Sipariş no", "Artan")]
SUPPLY_START = [("Dönem", "Artan"), ("Stok", None), ("Kalitedeki stok", None), ("Üretim siparişi", None), ("Satın alma siparişi", None), ("Arz tarihi", "Artan"),
                ("Üretim planı", None), ("Satın alma önerisi", None), ("Son kullanma tarihi", "Artan")]
KEYS = ("FullPeggingMethod", "CustomAllocation")


def body(rows):
    return [{"criterion": n, "direction": d} for n, d in rows]


def moved(rows, name, to):
    out = [r for r in rows if r[0] != name]
    out.insert(to, next(r for r in rows if r[0] == name))
    return out


# ------------------------------------------------------------------ tanım

def test_start_order_is_the_decided_order():
    assert pegging.start(pegging.NEED) == NEED_START and pegging.start(pegging.SUPPLY) == SUPPLY_START


def test_demand_types_come_from_the_same_source_as_objectives():
    """Talep türleri senkron (K-201 madde 7): pegging listesi ve Hedefler aynı kaynaktan (`DEMAND_TYPES`), aynı sırada; ikinci liste yok."""
    names = [c.name for c in pegging.CRITERIA[pegging.NEED]]
    first = names.index(cat.DEMAND_TYPES[0])
    assert tuple(names[first:first + len(cat.DEMAND_TYPES)]) == cat.DEMAND_TYPES == ("Kesin sipariş", "Teklif", "Beklemedeki sipariş", "Tahmin")
    assert not any(pegging.BY_NAME[pegging.NEED][t].hints for t in cat.DEMAND_TYPES)            # türler yönsüz
    assert set(cat.DEMAND_SWITCH) <= set(cat.DEMAND_TYPES)                                       # Talep sekmesindeki anahtarlar da aynı türlerden
    # Hedefler'in kataloğundaki talep türü ekseni aynı değerleri verir
    axes = [tuple(a.values) for o in cat.OBJECTIVES for a in o.axes if a.key == cat.AX_DEMAND_TYPE]
    assert axes and all(a == cat.DEMAND_TYPES for a in axes)


def test_directions_and_hints():
    need, supply = pegging.BY_NAME[pegging.NEED], pegging.BY_NAME[pegging.SUPPLY]
    assert need["Dönem"].hints == (("Artan", "erken önce"), ("Azalan", "geç önce"))
    assert supply["Dönem"].hints == (("Artan", "erken önce"), ("Azalan", "geç önce"), ("İhtiyaca en yakın", "ihtiyacın döneminden geriye, yetmezse ileriye"))
    assert need["Öncelik grubu"].hints == (("Artan", "1 önce"), ("Azalan", "5 önce"))
    assert need["Sipariş no"].hints == (("Artan", "küçük numara önce"), ("Azalan", "büyük numara önce"))
    assert need["İhtiyaç tarihi"].hints == supply["Arz tarihi"].hints == supply["Son kullanma tarihi"].hints == need["Dönem"].hints
    assert "Talep termini" not in need and "Talep termini" not in supply                          # ölçüt değil (madde 9)
    directed = {s: [c.name for c in items if c.hints] for s, items in pegging.CRITERIA.items()}
    assert directed == {pegging.NEED: ["Dönem", "Öncelik grubu", "İhtiyaç tarihi", "Sipariş no"], pegging.SUPPLY: ["Dönem", "Arz tarihi", "Son kullanma tarihi"]}
    assert all(len(c.name) <= 40 for items in pegging.CRITERIA.values() for c in items) and all(len(d) <= 20 for d in (pegging.ASC, pegging.DESC, pegging.NEAREST))


def test_later_changes_to_the_definition_keep_old_lists_usable():
    """Tanıma sonradan eklenen ölçüt başlangıçtaki komşusunun ardına girer; tanımdan kalkan atılır; geçersiz yön başlangıç yönüne döner."""
    old = [("Sipariş no", "Azalan"), ("Tahmin", None), ("Kalkan ölçüt", None), ("Dönem", "Yok"), ("Kesin sipariş", None)]
    got = pegging._complete(pegging.NEED, old)
    assert [n for n, _ in got] == ["Sipariş no", "Tahmin", "Üretim siparişi ihtiyacı", "Üretim planı ihtiyacı", "Öncelik grubu", "İhtiyaç tarihi", "Dönem",
                                   "Kesin sipariş", "Teklif", "Beklemedeki sipariş"]
    assert dict(got)["Sipariş no"] == "Azalan" and dict(got)["Dönem"] == "Artan" and "Kalkan ölçüt" not in dict(got)
    assert pegging._complete(pegging.SUPPLY, SUPPLY_START) == SUPPLY_START
    assert pegging._complete(pegging.SUPPLY, [("Stok", None)])[:2] == [("Dönem", "Artan"), ("Stok", None)]     # öncesinde komşusu yoksa başa


def test_custom_allocation_is_a_model_parameter_and_method_is_under_pegging():
    where = {p.key: (s.title, sub.title) for s in cat.SECTIONS for sub in s.subs for p in sub.params}
    assert where["CustomAllocation"] == ("Model", "Çözüm") and where["FullPeggingMethod"] == ("Pegging", "Pegging")
    solution = next(sub for s in cat.SECTIONS if s.key == "model" for sub in s.subs if sub.key == "cozum")
    assert [p.key for p in solution.params] == ["CustomAllocation", "OptimalityGapPct", "MrpWarmStart"]
    assert [sub.title for s in cat.SECTIONS if s.key == "model" for sub in s.subs] == ["Model tipi", "Çözüm"]          # yeni alt başlık açılmadı
    assert (cat.BY_KEY["CustomAllocation"].options, cat.DEFAULTS["CustomAllocation"]) == (("Dikkate al", "Dikkate alma"), "Dikkate al")
    assert (cat.BY_KEY["FullPeggingMethod"].options, cat.DEFAULTS["FullPeggingMethod"]) == (("FIFO", "Talep termini"), "FIFO")
    assert [s.title for s in cat.SECTIONS] == ["Model", "Hedefler", "Pegging", "Talep", "Malzeme", "Kapasite", "Planlama ufku", "Plan kararlılığı", "Uyarı eşikleri"]
    assert scenario_tables.BY_NAME["PeggingCriterion"].kind == scenario_tables.SETTING and scenario_tables.model_tables() == set(scenario_tables.BY_NAME)


# ------------------------------------------------------------------ saklama ve uçlar

@pytest.fixture(scope="module")
def people(db_engine):
    with db_engine.begin() as c:
        ids = {role: ensure_user(c, f"pytest.peg.{role.split()[0].lower()}", role) for role in (SYSTEM_OWNER, ADMIN, KEY_USER, END_USER)}
    yield ids
    with db_engine.begin() as c:
        delete_users(c, list(ids.values()))


@pytest.fixture
def base(db_engine):
    """Baz senaryo; pegging satırları ve iki ayarı test sonunda eski hâline döner. Test boş listeyle (başlangıç sırası) başlar."""
    with db_engine.connect() as c:
        sid = c.execute(sa.text("SELECT Id FROM param.ScenarioDefinition WHERE IsBase = 1")).scalar_one()
        rows = [dict(r) for r in c.execute(sa.text("SELECT * FROM param.PeggingCriterion WHERE ScenarioDefinitionId = :s"), {"s": sid}).mappings()]
        settings = [dict(r) for r in c.execute(sa.text("SELECT * FROM param.PlanningSetting WHERE ScenarioDefinitionId = :s AND SettingKey IN :k").bindparams(
            sa.bindparam("k", expanding=True)), {"s": sid, "k": list(KEYS)}).mappings()]

    def clear(c):
        c.execute(sa.text("DELETE FROM param.PeggingCriterion WHERE ScenarioDefinitionId = :s"), {"s": sid})
        c.execute(sa.text("DELETE FROM param.PlanningSetting WHERE ScenarioDefinitionId = :s AND SettingKey IN :k").bindparams(sa.bindparam("k", expanding=True)),
                  {"s": sid, "k": list(KEYS)})

    with db_engine.begin() as c:
        clear(c)
    yield sid
    with db_engine.begin() as c:
        clear(c)
        if rows:
            c.execute(sa.insert(pegging.TABLE), rows)
        if settings:
            c.execute(sa.insert(sa.table("PlanningSetting", sa.column("ScenarioDefinitionId"), sa.column("SettingKey"), sa.column("Value"), schema="param")), settings)


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app(), raise_server_exceptions=False)


def lists(response):
    data = response.json()
    return [(r["criterion"], r["direction"]) for r in data["need"]], [(r["criterion"], r["direction"]) for r in data["supply"]]


@pytest.mark.db
def test_without_rows_the_start_order_is_read(db_engine, base, client, people):
    r = client.get("/api/parameters/pegging", headers=auth(people[KEY_USER]))
    assert r.status_code == 200, r.text
    assert lists(r) == (NEED_START, SUPPLY_START)
    data = r.json()
    assert data["method"] == {"key": "FullPeggingMethod", "label": "Full pegging yöntemi", "value": "FIFO", "options": ["FIFO", "Talep termini"]}
    assert data["supply"][0]["directions"] == [{"value": "Artan", "hint": "erken önce"}, {"value": "Azalan", "hint": "geç önce"},
                                               {"value": "İhtiyaca en yakın", "hint": "ihtiyacın döneminden geriye, yetmezse ileriye"}]
    assert data["need"][1] == {"criterion": "Kesin sipariş", "direction": None, "directions": []}
    assert set(data) == {"method", "need", "supply"}                                             # "Başlangıç düzenine getir" yok: is_default alanı da yok
    with db_engine.connect() as c:
        assert c.execute(sa.text("SELECT COUNT(*) FROM param.PeggingCriterion WHERE ScenarioDefinitionId = :s"), {"s": base}).scalar() == 0   # okumak yazmaz
    assert client.post("/api/parameters/pegging/need/reset", headers=auth(people[KEY_USER])).status_code in (404, 405)


@pytest.mark.db
def test_save_order_direction_and_method_in_one_request_with_audit(db_engine, base, client, people):
    key = auth(people[KEY_USER])
    need = moved(NEED_START, "Tahmin", 1)
    supply = [(n, "İhtiyaca en yakın" if n == "Dönem" else d) for n, d in SUPPLY_START]
    r = client.put("/api/parameters/pegging", headers=key, json={"method": "Talep termini", "need": body(need), "supply": body(supply)})
    assert r.status_code == 200, r.text
    assert lists(r) == (need, supply) and r.json()["method"]["value"] == "Talep termini"
    assert lists(client.get("/api/parameters/pegging", headers=key)) == (need, supply)
    with db_engine.connect() as c:
        stored = c.execute(sa.text("SELECT Side, Seq, Criterion, Direction FROM param.PeggingCriterion WHERE ScenarioDefinitionId = :s ORDER BY Side, Seq"), {"s": base}).all()
        log = c.execute(sa.text("SELECT Action, ObjectKey, OldValue, NewValue FROM adm.AuditLog WHERE UserId = :u ORDER BY Id DESC"), {"u": people[KEY_USER]}).all()[:3]
    assert [tuple(x) for x in stored] == [("Arz", i, n, d) for i, (n, d) in enumerate(supply, 1)] + [("İhtiyaç", i, n, d) for i, (n, d) in enumerate(need, 1)]
    found = {(a, k): (o, n) for a, k, o, n in log}
    assert set(found) == {("Parametre değişikliği", "Baz · FullPeggingMethod"), ("Pegging sırası değişikliği", "Baz · İhtiyaç sırası"),
                          ("Pegging sırası değişikliği", "Baz · Arz sırası")}
    assert found["Parametre değişikliği", "Baz · FullPeggingMethod"] == ('{"Value": "FIFO"}', '{"Value": "Talep termini"}')
    old, new = found["Pegging sırası değişikliği", "Baz · Arz sırası"]
    assert '"Dönem (Artan)"' in old and '"Dönem (İhtiyaca en yakın)"' in new and '"Stok"' in new
    # aynı içerik yeniden kaydedilirse yazılmaz, ize düşmez; yalnız verilen alan değişir
    with db_engine.connect() as c:
        before = c.execute(sa.text("SELECT COUNT(*) FROM adm.AuditLog WHERE UserId = :u"), {"u": people[KEY_USER]}).scalar()
    assert client.put("/api/parameters/pegging", headers=key, json={"method": "Talep termini", "need": body(need), "supply": body(supply)}).status_code == 200
    only = client.put("/api/parameters/pegging", headers=key, json={"need": body(NEED_START)})
    assert lists(only) == (NEED_START, supply) and only.json()["method"]["value"] == "Talep termini"
    with db_engine.connect() as c:
        assert c.execute(sa.text("SELECT COUNT(*) FROM adm.AuditLog WHERE UserId = :u"), {"u": people[KEY_USER]}).scalar() == before + 1
    # genel parametre ucu da yöntemi ve Özel alokasyon'u taşır
    values = client.get("/api/parameters", headers=key).json()["values"]
    assert (values["FullPeggingMethod"], values["CustomAllocation"]) == ("Talep termini", "Dikkate al")
    assert client.put("/api/parameters", headers=key, json={"changes": {"CustomAllocation": "Dikkate alma"}}).json()["values"]["CustomAllocation"] == "Dikkate alma"


@pytest.mark.db
@pytest.mark.parametrize("change, field, problem", [
    (lambda n, s: {"need": body(n[:-1])}, "need", "Ölçüt çıkarılamaz: Sipariş no."),
    (lambda n, s: {"need": body(n[:-1] + [n[0]])}, "need", "Ölçüt yinelenemez: Dönem."),
    (lambda n, s: {"supply": body(s + [("Raf", None)])}, "supply", "Bilinmeyen ölçüt: Raf."),
    (lambda n, s: {"need": body([(x, "İhtiyaca en yakın" if x == "Dönem" else d) for x, d in n])}, "need", "Dönem: yön Artan · Azalan olabilir."),
    (lambda n, s: {"need": body([(x, None if x == "Dönem" else d) for x, d in n])}, "need", "Dönem: yön Artan · Azalan olabilir."),
    (lambda n, s: {"supply": body([(x, "Artan" if x == "Stok" else d) for x, d in s])}, "supply", "Stok: bu ölçütün yönü yoktur."),
    (lambda n, s: {"method": "LIFO"}, "method", "Listedeki değerlerden biri girilmeli."),
])
def test_only_order_and_direction_can_change(db_engine, base, client, people, change, field, problem):
    key = auth(people[KEY_USER])
    good = moved(SUPPLY_START, "Stok", 0)
    r = client.put("/api/parameters/pegging", headers=key, json={"supply": body(good), **change(NEED_START, good)} if field != "supply" else change(NEED_START, SUPPLY_START))
    assert r.status_code == 422, r.text
    assert {"field": field, "problem": problem} in r.json()["error"]["details"]
    assert lists(client.get("/api/parameters/pegging", headers=key)) == (NEED_START, SUPPLY_START)        # biri geçersizse hiçbiri yazılmaz
    assert client.put("/api/parameters/pegging", headers=key, json={"need": body(NEED_START), "fazla": 1}).status_code == 422


@pytest.mark.db
def test_roles(base, client, people):
    for role in (SYSTEM_OWNER, ADMIN, KEY_USER):
        who = auth(people[role])
        assert client.get("/api/parameters/pegging", headers=who).status_code == 200, role
        assert client.put("/api/parameters/pegging", headers=who, json={"method": "FIFO"}).status_code == 200, role
    end = auth(people[END_USER])                                                                 # End user Parametreler'i görmez (mevcut kural)
    assert client.get("/api/parameters/pegging", headers=end).status_code == 403
    assert client.put("/api/parameters/pegging", headers=end, json={"method": "FIFO"}).status_code == 403
    assert client.get("/api/parameters/pegging").status_code == 401


@pytest.mark.db
def test_scenario_copy_is_a_full_copy_and_engine_reads_the_lists(db_engine, base):
    """Senaryo kopyasında listeler tam kopyalanır ("Baz'ı izler" açıkken de); sonra bağımsızdır. Motor yükleyicisi iki listeyi ve iki ayarı verir."""
    need = moved(NEED_START, "Sipariş no", 0)
    with Session(db_engine) as s:
        try:
            pegging.save(s, base, {"method": "Talep termini", "need": body(need)})
            copy = scenarios.create_copy(s, "pytest pegging kopya", base, follows_base=True)["Id"]
            assert pegging.read_list(s, copy, pegging.NEED) == need and pegging.read_list(s, copy, pegging.SUPPLY) == SUPPLY_START
            # Baz'daki sonraki değişiklik kopyaya yansımaz; kopyadaki değişiklik Baz'a yansımaz
            pegging.save(s, base, {"need": body(NEED_START), "supply": body(moved(SUPPLY_START, "Stok", 0))})
            pegging.save(s, copy, {"supply": body([(n, "Azalan" if n == "Arz tarihi" else d) for n, d in SUPPLY_START])})
            assert pegging.read_list(s, copy, pegging.NEED) == need
            assert dict(pegging.read_list(s, copy, pegging.SUPPLY))["Arz tarihi"] == "Azalan" and pegging.read_list(s, base, pegging.SUPPLY)[0] == ("Stok", None)
            got = loader.load_parameters(s, copy)
            assert got.pegging.need == tuple(need) and dict(got.pegging.supply)["Arz tarihi"] == "Azalan"
            assert (got.settings["FullPeggingMethod"], got.settings["CustomAllocation"]) == ("Talep termini", "Dikkate al")
            fresh = scenarios.create_copy(s, "pytest pegging kopya 2", copy, follows_base=False)["Id"]
            assert loader.load_parameters(s, fresh).pegging == got.pegging
        finally:
            s.rollback()
    with Session(db_engine) as s:                                                                # satırı olmayan senaryo: başlangıç sırası
        got = loader.load_parameters(s, base)
        assert got.pegging.need == tuple(NEED_START) and got.pegging.supply == tuple(SUPPLY_START)
