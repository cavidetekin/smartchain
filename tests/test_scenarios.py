"""Senaryo yönetimi (K-176, K-177; fonksiyon 27, 28; ekran 07): kayıt defteri, kopyalayarak yeni senaryo, Baz korumaları, yeniden adlandırma,
pasif / aktif, Baz'dan ayır, silme (plan versiyonlarıyla; yayınlanmış plan engeli), "Gece çalışsın" ve gece sırası, seçili senaryo ve hatırlama,
senaryo başına parametreler, işlem bazında yetkiler, denetim izinde ve iş listesinde Senaryo kolonu, liste.

Testler kendi senaryolarını "pytest · " önekiyle açar ve siler; Baz'ın gece ayarı ve kullanıcıların seçimi eski hâline döner.
"""
import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.main import create_app
from app.api.permissions import ADMIN, END_USER, KEY_USER, SYSTEM_OWNER
from app.engine.submit import submit_plan_run
from app.params import scenario_tables as registry, scenarios, service as params

from auth_helpers import auth, ensure_user

pytestmark = pytest.mark.db
PREFIX = "pytest · "


def _clean(engine):
    with Session(engine) as s:
        ids = [r[0] for r in s.execute(sa.text("SELECT Id FROM param.ScenarioDefinition WHERE Name LIKE :p"), {"p": PREFIX + "%"})]
        for sid in ids:
            from app.data.cleanup import delete_scenario_plans
            s.execute(sa.text("DELETE v FROM planning.PlanVersion v JOIN planning.PlanRun r ON r.Id = v.PlanRunId WHERE r.ScenarioDefinitionId = :s"), {"s": sid})
            delete_scenario_plans(s.connection(), sid)
            registry.delete_rows(s, sid)
            s.execute(sa.text("UPDATE adm.AppUser SET ScenarioDefinitionId = NULL WHERE ScenarioDefinitionId = :s"), {"s": sid})
            s.execute(sa.text("DELETE FROM param.ScenarioDefinition WHERE Id = :s"), {"s": sid})
        s.execute(sa.text("DELETE FROM adm.Job WHERE JobType IN (N'Çalışma', N'Gece senaryosu')"))
        s.commit()


@pytest.fixture(scope="module")
def people(db_engine):
    with db_engine.begin() as c:
        return {SYSTEM_OWNER: ensure_user(c, "pytest.sc.owner", SYSTEM_OWNER), ADMIN: ensure_user(c, "pytest.sc.admin", ADMIN),
                KEY_USER: ensure_user(c, "pytest.sc.key", KEY_USER), END_USER: ensure_user(c, "pytest.sc.end", END_USER)}


@pytest.fixture
def base(db_engine, people):
    """Baz'ın kimliği; test sonunda testin senaryoları silinir, Baz'ın gece ayarı ve kullanıcı seçimleri eski hâline döner."""
    _clean(db_engine)
    with db_engine.connect() as c:
        row = c.execute(sa.text("SELECT Id, RunsNightly, NightlyPriority FROM param.ScenarioDefinition WHERE IsBase = 1")).one()
        others = c.execute(sa.text("SELECT Id, RunsNightly, NightlyPriority FROM param.ScenarioDefinition WHERE ISNULL(IsBase, 0) = 0")).all()
    yield row.Id
    _clean(db_engine)
    with db_engine.begin() as c:
        for r in (row, *others):
            c.execute(sa.text("UPDATE param.ScenarioDefinition SET RunsNightly = :n, NightlyPriority = :p WHERE Id = :i"),
                      {"n": r.RunsNightly, "p": r.NightlyPriority, "i": r.Id})
        c.execute(sa.text("UPDATE adm.AppUser SET ScenarioDefinitionId = NULL WHERE Id IN :ids").bindparams(sa.bindparam("ids", expanding=True)),
                  {"ids": list(people.values())})


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app(), raise_server_exceptions=False)


def new(client, who, name, source, follows=True):
    r = client.post("/api/scenarios", headers=who, json={"name": PREFIX + name, "source_id": source, "follows_base": follows})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def rows_of(engine, table, sid):
    with engine.connect() as c:
        return c.execute(sa.text(f"SELECT COUNT(*) FROM param.[{table}] WHERE ScenarioDefinitionId = :s"), {"s": sid}).scalar()


# ------------------------------------------------------------------ kayıt defteri

def test_registry_covers_every_scenario_table():
    """Modelde senaryo kimliği taşıyan her param tablosu kayıt defterinde; türü Ayar ya da Veri, Veri tablosunun ayırma işlevi bağlı."""
    assert registry.model_tables() == set(registry.BY_NAME)
    assert {t.name for t in registry.TABLES if t.kind == registry.SETTING} == {
        "PlanningSetting", "ObjectiveDefinition", "TimeBucketDefinition", "WarningThreshold"}
    assert all(t.materialize is not None for t in registry.TABLES if t.kind == registry.DATA)


# ------------------------------------------------------------------ kopya, Baz, ad

def test_copy_brings_all_settings_and_follows_rules(db_engine, base, client, people):
    admin = auth(people[ADMIN])
    client.put(f"/api/parameters?scenario_id={base}", headers=admin, json={"changes": {"UseOvertime": False}})
    a = new(client, admin, "Fazla mesaili", base)
    for table in ("PlanningSetting", "ObjectiveDefinition", "TimeBucketDefinition"):
        assert rows_of(db_engine, table, a) == rows_of(db_engine, table, base), table
    assert rows_of(db_engine, "SupplierLimit", a) == 0 and rows_of(db_engine, "SupplierLimit", base) >= 1   # Baz'ın veri satırları kopyalanmaz
    with db_engine.connect() as c:
        row = c.execute(sa.text("SELECT IsBase, IsActive, RunsNightly, NightlyPriority, FollowsBase, IsSynthetic FROM param.ScenarioDefinition WHERE Id = :s"), {"s": a}).one()
    assert tuple(row) == (False, True, False, None, True, False)                       # aktif, gece çalışmaz, sırasız, Baz'ı izler
    # parametreler senaryo başına ayrıdır: kopyadaki değişiklik Baz'a geçmez
    r = client.put(f"/api/parameters?scenario_id={a}", headers=admin, json={"changes": {"UseOvertime": True, "ModelType": "MILP"}})
    assert r.json()["scenario"]["id"] == a and r.json()["values"]["UseOvertime"] == "1"
    assert client.get(f"/api/parameters?scenario_id={base}", headers=admin).json()["values"]["UseOvertime"] == "0"
    # kopyanın kopyası: parametreler ve Baz'ı izler seçimi gelir; veri satırları kaynağın kendi satırlarıdır
    with db_engine.begin() as c:
        c.execute(sa.text("INSERT INTO param.SupplierLimit (ScenarioDefinitionId, IsValid, LimitType, LocationId, SupplierId, MaterialId, ValidFrom, ValidTo, UpperLimit, "
                          "LimitPeriod, UpdatedAt) SELECT :a, 1, LimitType, LocationId, SupplierId, MaterialId, DATEADD(year, 5, ValidFrom), DATEADD(year, 5, ValidTo), 7, "
                          "LimitPeriod, SYSUTCDATETIME() FROM param.SupplierLimit WHERE ScenarioDefinitionId = :b AND LimitType = N'Üst limit'"), {"a": a, "b": base})
    b = new(client, admin, "Fazla mesaili · MILP", a, follows=False)
    got = client.get(f"/api/parameters?scenario_id={b}", headers=admin).json()["values"]
    assert (got["UseOvertime"], got["ModelType"]) == ("1", "MILP") and rows_of(db_engine, "SupplierLimit", b) == rows_of(db_engine, "SupplierLimit", a) + rows_of(db_engine, "SupplierLimit", base)   # izlemeyen kopya: Baz'ın değerleri tam kopyalanır (K-191), kaynağın kendi satırları da gelir
    # ad: zorunlu, tekil, en çok 100
    for name, problem in (("", "Senaryo adı boş olamaz."), (PREFIX + "Fazla mesaili", "Bu adla bir senaryo var."), ("x" * 101, "En çok 100 karakter.")):
        bad = client.post("/api/scenarios", headers=admin, json={"name": name, "source_id": base, "follows_base": True})
        assert bad.status_code == 422 and bad.json()["error"]["details"][0] == {"field": "name", "problem": problem}, name
    assert client.post("/api/scenarios", headers=admin, json={"name": PREFIX + "x", "source_id": 999999999}).status_code == 404


def test_base_is_protected_and_rename(db_engine, base, client, people):
    admin = auth(people[ADMIN])
    assert client.put(f"/api/scenarios/{base}", headers=admin, json={"name": "Temel"}).json()["error"]["code"] == "base_scenario"
    assert client.post(f"/api/scenarios/{base}/deactivate", headers=admin).status_code == 422
    assert client.delete(f"/api/scenarios/{base}", headers=admin).status_code == 422
    assert client.post(f"/api/scenarios/{base}/detach", headers=admin).json()["error"]["code"] == "not_following"
    info = client.get(f"/api/scenarios/{base}/delete-info", headers=admin).json()
    assert info["deletable"] is False and "Baz" in info["reason"]
    a = new(client, admin, "Ad", base)
    r = client.put(f"/api/scenarios/{a}", headers=admin, json={"name": PREFIX + "Yeni ad"})
    assert r.status_code == 200 and r.json()["name"] == PREFIX + "Yeni ad"
    assert client.put(f"/api/scenarios/{a}", headers=admin, json={"name": "Baz"}).status_code == 422       # tekil
    with db_engine.connect() as c:
        log = c.execute(sa.text("SELECT TOP 1 Action, ScenarioName, OldValue, NewValue FROM adm.AuditLog WHERE UserId = :u ORDER BY Id DESC"), {"u": people[ADMIN]}).one()
    assert (log.Action, log.ScenarioName) == ("Senaryo adı değişti", PREFIX + "Yeni ad") and PREFIX + "Ad" in log.OldValue


# ------------------------------------------------------------------ pasif, ayır, sil

def test_passive_scenario_leaves_the_list_but_keeps_parameters(db_engine, base, client, people):
    admin, key = auth(people[ADMIN]), auth(people[KEY_USER])
    a = new(client, admin, "Pasif", base)
    client.put("/api/scenarios/nightly", headers=key, json={"rows": [{"id": a, "runs_nightly": True}]})
    assert client.put("/api/scenarios/current", headers=key, json={"id": a}).json()["id"] == a
    assert client.get("/api/scenarios/current", headers=key).json()["id"] == a                             # hatırlanır
    assert client.post(f"/api/scenarios/{a}/deactivate", headers=admin).json()["is_active"] is False
    names = [s["name"] for s in client.get("/api/scenarios/options", headers=key).json()["scenarios"]]
    assert names[0] == "Baz" and PREFIX + "Pasif" not in names
    assert client.get("/api/scenarios/current", headers=key).json()["id"] == base                          # hatırlanan pasifse Baz
    with db_engine.connect() as c:
        assert tuple(c.execute(sa.text("SELECT RunsNightly, NightlyPriority FROM param.ScenarioDefinition WHERE Id = :s"), {"s": a}).one()) == (False, None)
    # pasif senaryonun parametreleri açılır ve düzenlenir (Senaryolar ekranından); bağlam adı gösterilir
    assert client.get(f"/api/scenarios/current?scenario_id={a}", headers=key).json() == {"id": a, "name": PREFIX + "Pasif", "is_base": False, "is_active": False}
    assert client.put(f"/api/parameters?scenario_id={a}", headers=key, json={"changes": {"UseSubcontracting": True}}).json()["values"]["UseSubcontracting"] == "1"
    # pasif senaryo gece çalıştırılamaz; aktif yapılınca listeye döner
    bad = client.put("/api/scenarios/nightly", headers=key, json={"rows": [{"id": a, "runs_nightly": True}]})
    assert bad.status_code == 422 and "Pasif senaryo gece çalışmaz" in bad.json()["error"]["message"]
    assert client.post(f"/api/scenarios/{a}/activate", headers=admin).json()["is_active"] is True
    assert PREFIX + "Pasif" in [s["name"] for s in client.get("/api/scenarios/options", headers=key).json()["scenarios"]]


def test_detach_is_one_way_and_calls_the_registry(db_engine, base, client, people, monkeypatch):
    admin = auth(people[ADMIN])
    called = []
    monkeypatch.setattr(registry, "TABLES", tuple(
        registry.ScenarioTable(t.name, t.kind, (lambda s, sid, n=t.name: called.append((n, sid))) if t.kind == registry.DATA else None) for t in registry.TABLES))
    a = new(client, admin, "İzleyen", base)
    assert called == []                                                                                    # Baz'ı izleyen kopyada veri kopyalanmaz
    assert client.post(f"/api/scenarios/{a}/detach", headers=admin).status_code == 200
    assert sorted(called) == sorted((t.name, a) for t in registry.TABLES if t.kind == registry.DATA)       # 7.5'te bağlanacak işlevler
    with db_engine.connect() as c:
        assert c.execute(sa.text("SELECT FollowsBase FROM param.ScenarioDefinition WHERE Id = :s"), {"s": a}).scalar() is False
    assert client.post(f"/api/scenarios/{a}/detach", headers=admin).json()["error"]["code"] == "not_following"   # yeniden bağlama da ikinci ayırma da yok
    called.clear()
    b = new(client, admin, "Bağımsız", base, follows=False)                                                # Baz'ı izlemeden açılan senaryoda da çağrılır
    assert sorted(called) == sorted((t.name, b) for t in registry.TABLES if t.kind == registry.DATA)


def test_delete_removes_parameters_and_plan_versions(db_engine, base, client, people):
    admin = auth(people[ADMIN])
    a = new(client, admin, "Silinecek", base)
    with Session(db_engine) as s:
        dv = s.execute(sa.text("SELECT TOP 1 Id FROM adm.DataVersion ORDER BY Id DESC")).scalar_one()
        run_id, job_id = submit_plan_run(s, data_version_id=dv, scenario_definition_id=a, requested_by=people[SYSTEM_OWNER])
        s.commit()
    # iş listesinde ve panelde Senaryo: plan hesabı işinde dolu
    job = client.post("/api/job-queue/query", headers=auth(people[SYSTEM_OWNER]), json={"fields": ["Id", "ScenarioName"], "filters": [
        {"field": "ScenarioName", "op": "in", "values": [PREFIX + "Silinecek"]}]}).json()["rows"]
    assert [j["Id"] for j in job] == [job_id]
    assert next(j for j in client.get("/api/jobs", headers=auth(people[SYSTEM_OWNER])).json()["jobs"] if j["id"] == job_id)["scenario_name"] == PREFIX + "Silinecek"
    info = client.get(f"/api/scenarios/{a}/delete-info", headers=admin).json()
    assert info == {"name": PREFIX + "Silinecek", "plan_versions": 1, "deletable": True, "reason": None}
    # listede son çalışma senaryonun kendi plan hesabıdır: plan hesabı olmayan senaryoda boş
    b = new(client, admin, "Plansız", base)
    rows = client.post("/api/scenarios/query", headers=admin, json={"fields": ["Name", "LastRunAt"], "sort": [], "filters": [], "offset": 0, "limit": 100}).json()["rows"]
    status = {r["Id"]: r["LastRunStatus"] for r in rows}
    assert status[a] == "Sırada" and status[b] is None
    assert client.delete(f"/api/scenarios/{b}", headers=admin).status_code == 200
    # yayınlanmış planı olan senaryo silinemez
    with db_engine.begin() as c:
        loc = c.execute(sa.text("SELECT TOP 1 Id FROM core.Location ORDER BY Id")).scalar_one()
        sc = c.execute(sa.text("INSERT INTO planning.Scenario (ScenarioDefinitionId, DataVersionId) OUTPUT inserted.Id VALUES (:a, :dv)"), {"a": a, "dv": dv}).scalar_one()
        ws = c.execute(sa.text("INSERT INTO planning.Workspace (ScenarioId, OwnerUserId, Status) OUTPUT inserted.Id VALUES (:sc, :u, N'Yayınlandı')"),
                       {"sc": sc, "u": people[ADMIN]}).scalar_one()
        c.execute(sa.text("INSERT INTO planning.PlanVersion (LocationId, PlanRunId, WorkspaceId, PublishedBy, PublishedAt, IsCurrent) "
                          "VALUES (:l, :r, :ws, :u, SYSUTCDATETIME(), 0)"), {"l": loc, "r": run_id, "ws": ws, "u": people[ADMIN]})
    blocked = client.delete(f"/api/scenarios/{a}", headers=admin)
    assert blocked.status_code == 422 and blocked.json()["error"]["code"] == "scenario_published"
    assert client.get(f"/api/scenarios/{a}/delete-info", headers=admin).json()["deletable"] is False
    with db_engine.begin() as c:
        c.execute(sa.text("DELETE FROM planning.PlanVersion WHERE PlanRunId = :r"), {"r": run_id})
    client.put("/api/scenarios/current", headers=admin, json={"id": a})
    gone = client.delete(f"/api/scenarios/{a}", headers=admin)
    assert gone.status_code == 200 and gone.json() == {"deleted": PREFIX + "Silinecek", "plan_versions": 1}
    with db_engine.connect() as c:
        assert c.execute(sa.text("SELECT COUNT(*) FROM param.ScenarioDefinition WHERE Id = :s"), {"s": a}).scalar() == 0
        assert c.execute(sa.text("SELECT COUNT(*) FROM planning.PlanRun WHERE Id = :r"), {"r": run_id}).scalar() == 0
        assert c.execute(sa.text("SELECT COUNT(*) FROM planning.Scenario WHERE Id = :s"), {"s": sc}).scalar() == 0
        log = c.execute(sa.text("SELECT TOP 1 Action, ScenarioName FROM adm.AuditLog WHERE UserId = :u ORDER BY Id DESC"), {"u": people[ADMIN]}).one()
    assert all(rows_of(db_engine, t.name, a) == 0 for t in registry.TABLES)
    assert tuple(log) == ("Senaryo silindi", PREFIX + "Silinecek")                                          # senaryo silinse de iz adıyla okunur
    assert client.get("/api/scenarios/current", headers=admin).json()["id"] == base                        # seçmiş kullanıcı Baz'a düşer
    assert client.get(f"/api/parameters?scenario_id={a}", headers=admin).status_code == 404


# ------------------------------------------------------------------ gece

def test_nightly_switch_and_order(db_engine, base, client, people):
    admin, key = auth(people[ADMIN]), auth(people[KEY_USER])
    a, b, c_ = new(client, admin, "Gece A", base), new(client, admin, "Gece B", base), new(client, admin, "Gece C", base)
    r = client.put("/api/scenarios/nightly", headers=key, json={"rows": [
        {"id": b, "runs_nightly": True}, {"id": base, "runs_nightly": True}, {"id": a, "runs_nightly": True}, {"id": c_, "runs_nightly": False}]})
    assert r.status_code == 200, r.text
    with Session(db_engine) as s:
        mine = [(x["id"], x["priority"]) for x in scenarios.nightly_scenarios(s) if x["id"] in (a, b, c_, base)]
    assert [i for i, _ in mine] == [b, base, a] and [p for _, p in mine] == sorted(p for _, p in mine)     # liste sırası gece sırasıdır
    assert mine[0][1] == 1                                                                                 # 1'den başlar
    # Baz da kapatılabilir; kapanan senaryonun sırası boşalır, ötekiler boşluksuz kalır
    client.put("/api/scenarios/nightly", headers=key, json={"rows": [{"id": base, "runs_nightly": False}]})
    with db_engine.connect() as c:
        got = {r.Id: (bool(r.RunsNightly), r.NightlyPriority) for r in c.execute(sa.text(
            "SELECT Id, RunsNightly, NightlyPriority FROM param.ScenarioDefinition WHERE Id IN (:a, :b, :c, :base)"), {"a": a, "b": b, "c": c_, "base": base})}
        log = c.execute(sa.text("SELECT TOP 1 Action, ScenarioName FROM adm.AuditLog WHERE UserId = :u ORDER BY Id DESC"), {"u": people[KEY_USER]}).one()
    assert got[base] == (False, None) and got[c_] == (False, None) and got[b][1] == 1 and got[a][1] == 2
    assert log.Action == "Gece ayarı değişti"
    # liste: kolonlar, gece çalışanlar sırasıyla önce
    listed = client.post("/api/scenarios/query", headers=key, json={"filters": [{"field": "Name", "op": "starts_with", "value": PREFIX}]}).json()["rows"]
    assert [x["Name"] for x in listed] == [PREFIX + "Gece B", PREFIX + "Gece A", PREFIX + "Gece C"]
    first = listed[0]
    assert (first["NightlyPriority"], first["ModelType"], first["FollowsBase"], first["RunsNightly"], first["BudgetSeconds"], first["ActiveLabel"]) == (
        1, "LP", "Evet", True, 1140, "Evet")
    base_row = client.post("/api/scenarios/query", headers=key, json={"filters": [{"field": "Name", "op": "equals", "value": "Baz"}]}).json()["rows"][0]
    assert base_row["IsBase"] is True and base_row["FollowsBase"] is None
    cols = [c["label"] for c in client.get("/api/scenarios/columns", headers=key).json()["columns"] if c["default_visible"]]
    assert cols == ["Gece sırası", "Senaryo", "Model", "Baz'ı izler", "Gece çalışsın", "Süre bütçesi (sn)", "Son çalışma", "Aktif"]


# ------------------------------------------------------------------ yetki

def test_permissions_by_operation(base, client, people):
    owner, admin, key, end = auth(people[SYSTEM_OWNER]), auth(people[ADMIN]), auth(people[KEY_USER]), auth(people[END_USER])
    a = new(client, owner, "Yetki", base)
    # yönetim işlemleri Admin ve üstü; Key user 403
    for method, url, body in (("post", "/api/scenarios", {"name": PREFIX + "K", "source_id": base}), ("put", f"/api/scenarios/{a}", {"name": PREFIX + "K"}),
                              ("post", f"/api/scenarios/{a}/deactivate", None), ("post", f"/api/scenarios/{a}/activate", None),
                              ("post", f"/api/scenarios/{a}/detach", None), ("get", f"/api/scenarios/{a}/delete-info", None),
                              ("delete", f"/api/scenarios/{a}", None)):
        r = getattr(client, method)(url, headers=key, **({"json": body} if body is not None else {}))
        assert r.status_code == 403 and "Admin" in r.json()["error"]["message"], url
        assert getattr(client, method)(url, headers=end, **({"json": body} if body is not None else {})).status_code == 403, url
    # Key user: listeyi görür, parametreleri ve gece ayarını düzenler
    assert client.post("/api/scenarios/query", headers=key, json={}).status_code == 200
    assert client.put("/api/scenarios/nightly", headers=key, json={"rows": [{"id": a, "runs_nightly": True}]}).status_code == 200
    assert client.put(f"/api/parameters?scenario_id={a}", headers=key, json={"changes": {"UseOvertime": True}}).status_code == 200
    # End user: geçiş yapar; Senaryolar ekranının ve parametrelerin uçları kapalı
    assert [s["name"] for s in client.get("/api/scenarios/options", headers=end).json()["scenarios"]][0] == "Baz"
    assert client.put("/api/scenarios/current", headers=end, json={"id": a}).json()["id"] == a
    assert client.get("/api/scenarios/current", headers=end).json()["name"] == PREFIX + "Yetki"
    for method, url in (("post", "/api/scenarios/query"), ("put", "/api/scenarios/nightly")):
        assert getattr(client, method)(url, headers=end, json={"rows": []} if "nightly" in url else {}).status_code == 403
    assert client.get(f"/api/parameters?scenario_id={a}", headers=end).status_code == 403
    assert client.put("/api/scenarios/current", headers=end, json={"id": 999999999}).status_code == 404
    assert client.delete(f"/api/scenarios/{a}", headers=admin).status_code == 200


def test_audit_list_has_scenario_column(base, client, people):
    admin = auth(people[ADMIN])
    a = new(client, admin, "İz", base)
    client.put(f"/api/parameters?scenario_id={a}", headers=admin, json={"changes": {"UseOvertime": True}})
    cols = {c["field"]: c["label"] for c in client.get("/api/audit-log/columns", headers=admin).json()["columns"]}
    assert cols["ScenarioName"] == "Senaryo"
    rows = client.post("/api/audit-log/query", headers=admin, json={"fields": ["Action", "ScenarioName"], "filters": [
        {"field": "ScenarioName", "op": "in", "values": [PREFIX + "İz"]}]}).json()["rows"]
    assert {r["Action"] for r in rows} == {"Senaryo oluşturuldu", "Parametre değişikliği"}
    # veri yönetimi işlemlerinde boş
    other = client.post("/api/audit-log/query", headers=admin, json={"fields": ["Action", "ScenarioName"], "filters": [
        {"field": "Action", "op": "in", "values": ["Giriş"]}]}).json()["rows"]
    assert all(r["ScenarioName"] is None for r in other)


def test_synthetic_scenarios_follow_the_definition(db_engine, base):
    """Sentetik senaryolar (docs/11): Baz'dan kopya, parametre farkı, gece ayarı; sentetik işaretli. Geri alınır."""
    from app.data.synthetic import dataset as d
    from app.data.synthetic.load import _scenarios
    with db_engine.connect() as conn:
        tx = conn.begin()
        try:
            with Session(bind=conn) as s:  # önceki sentetik yüklemenin senaryoları (yükleme de önce bunları siler)
                for sid in s.execute(sa.text("SELECT Id FROM param.ScenarioDefinition WHERE IsSynthetic = 1 AND IsBase = 0")).scalars().all():
                    scenarios.delete(s, sid)
            assert _scenarios(conn, base) == 3
            got = {r.Name: r for r in conn.execute(sa.text(
                "SELECT Id, Name, FollowsBase, RunsNightly, NightlyPriority, IsSynthetic FROM param.ScenarioDefinition WHERE IsSynthetic = 1"))}
            assert set(got) == {s[0] for s in d.SCENARIOS}
            assert (got["Fazla mesaili"].NightlyPriority, got["Kısıtsız kapasite"].NightlyPriority, bool(got["MILP deneme"].RunsNightly)) == (2, 3, False)
            assert got["MILP deneme"].FollowsBase is False
            assert params.read_settings(conn, got["Fazla mesaili"].Id)["UseOvertime"] == "1"
            assert params.read_settings(conn, got["Kısıtsız kapasite"].Id)["ResourceConstraint"] == "Kısıtsız"
            assert params.read_settings(conn, got["MILP deneme"].Id)["ModelType"] == "MILP"
            assert params.time_budget(conn, got["Kısıtsız kapasite"].Id) == params.time_budget(conn, base) // 2
        finally:
            tx.rollback()
