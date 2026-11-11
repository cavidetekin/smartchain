"""Zamanlanmış akışlar (fonksiyon 92, K-163): zamanlama, bekleme, teknik hata ve veri bulgusu, adımlar, kesinti ve SQL bağlantısının
kopması, durum çipi, akış kilidi (409 flow_running), yetki, zamanlayıcı satırı. Test veritabanında (K-103); SQL Server'a dokunulmaz,
bağlantı kopması taklit edilir."""
import json
from datetime import datetime, timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.api.permissions import ADMIN, END_USER, KEY_USER, SYSTEM_OWNER
from app.engine.service import EngineService
from app.engine.settings import EngineSettings
from app.engine.transfer_job import run_transfer_job
from app.flows import runner, schedule
from app.jobs import queue
from app.jobs.constants import CHANNEL_PROCESSING, TYPE_PULL, TYPE_TRANSFER, TYPE_VALIDATION
from app.jobs.settings import JobSettings
from app.validation import engine as validation_engine

from auth_helpers import auth, ensure_user
from test_validation_references import put
from validation_helpers import clean, new_client, run_validations

pytestmark = pytest.mark.db

BASE = datetime(2026, 11, 10, 2, 0)  # Salı 02:00, sunucunun yerel saati
DUE = schedule.local_to_utc(BASE)
DATA_JOBS = "(N'Veri çekme', N'Excel ön kontrol', N'Validasyon', N'Aktarım', N'Temizlik')"


# ------------------------------------------------------------------ zaman (veritabanısız)

@pytest.mark.parametrize("now, expected", [
    (datetime(2026, 11, 10, 2, 0), datetime(2026, 11, 10, 2, 0)),      # tam saatinde
    (datetime(2026, 11, 10, 1, 59), datetime(2026, 11, 6, 2, 0)),      # Salı saatinden önce → önceki Cuma (Pzt seçili değil)
    (datetime(2026, 11, 12, 9, 0), datetime(2026, 11, 10, 2, 0)),      # Perşembe → Salı
])
def test_last_due(now, expected):
    assert schedule.last_due("02:00", [2, 5], now) == expected


def test_next_due_and_texts():
    assert schedule.next_due("02:00", [2, 5], datetime(2026, 11, 10, 2, 0)) == datetime(2026, 11, 13, 2, 0)
    assert schedule.days_text([1, 2, 3, 4, 5]) == "Hafta içi" and schedule.days_text([7, 1]) == "Pzt, Paz"
    assert schedule.valid_time("23:59") and not schedule.valid_time("24:00") and not schedule.valid_time("2:00")
    assert schedule.parse_days("3,1,x,9,1") == [1, 3]


def test_same_reason_is_grouped():
    errors = [(t, {"status": "Hata", "reason": "SQL kaynağına bağlanılamadı: Yok."}) for t in ("Location", "Material", "Customer", "Stock", "BOM")]
    errors.append(("Routing", {"status": "Tamamlanmadı", "reason": None}))
    assert runner._grouped(errors) == "Lokasyon, Malzeme, Müşteri ve 2 tablo: SQL kaynağına bağlanılamadı: Yok.; Rota: Tamamlanmadı"


# ------------------------------------------------------------------ fikstürler

def _clean_flows(engine) -> None:
    with engine.begin() as c:
        c.execute(sa.text("DELETE FROM adm.FlowRunDismissal"))
        c.execute(sa.text("DELETE FROM adm.FlowRun"))
        c.execute(sa.text("DELETE FROM adm.Flow"))
        c.execute(sa.text(f"DELETE FROM adm.Job WHERE JobType IN {DATA_JOBS}"))
        c.execute(sa.text("DELETE FROM adm.SystemSetting WHERE SettingKey IN (N'FlowWaitMinutes', N'FlowRefreshWaitMinutes', N'RawDataRetentionDays')"))
        c.execute(sa.text("DELETE FROM adm.IntegrationEntity"))
        c.execute(sa.text("DELETE FROM adm.ServiceStatus WHERE ServiceName = N'Zamanlayıcı'"))


@pytest.fixture
def people(db_engine):
    with db_engine.begin() as c:
        return {SYSTEM_OWNER: ensure_user(c, "pytest.akis.owner", SYSTEM_OWNER, "Akış Owner"),
                ADMIN: ensure_user(c, "pytest.akis.admin", ADMIN, "Akış Admin"),
                KEY_USER: ensure_user(c, "pytest.akis.key", KEY_USER, "Akış Key"),
                END_USER: ensure_user(c, "pytest.akis.end", END_USER, "Akış End")}


@pytest.fixture
def env(db_engine, people):
    clean(db_engine)
    _clean_flows(db_engine)
    yield db_engine
    _clean_flows(db_engine)
    clean(db_engine)


def flow(engine, owner: int, name="Gece tam", run_time="02:00", days="1,2,3,4,5,6,7", scope="Tümü", tables=(), mode="Tam", groups=(),
         cleanup=False, updated=None, active=True) -> int:
    with engine.begin() as c:
        return c.execute(sa.insert(runner.FLOW).values(
            Name=name, IsActive=active, RunTime=run_time, Days=days, PullScope=scope, PullTables=json.dumps(list(tables)), TransferMode=mode,
            TransferGroups=json.dumps(list(groups)), Cleanup=cleanup, UpdatedAt=updated or DUE - timedelta(hours=2), UpdatedBy=owner)
            .returning(runner.FLOW.c.Id)).scalar_one()


def sql_table(engine, table: str) -> None:
    with engine.begin() as c:
        c.execute(sa.text("INSERT INTO adm.IntegrationEntity (EntityName, Method, IsPullEnabled, ViewName) VALUES (:t, N'SQL', 1, :v)"),
                  {"t": table, "v": f"vw_{table}"})


def tick(engine, now: datetime) -> None:
    with Session(engine) as s:
        runner.tick(s, now)


def runs(engine) -> list[dict]:
    with engine.connect() as c:
        return [dict(r) for r in c.execute(sa.select(runner.RUN).order_by(runner.RUN.c.Id)).mappings()]


def last(engine) -> dict:
    return runs(engine)[-1]


def job(engine, job_id: int) -> dict:
    with engine.connect() as c:
        return dict(c.execute(sa.text("SELECT * FROM adm.Job WHERE Id = :id"), {"id": job_id}).mappings().one())


def finish(engine, job_id: int, result, status="Bitti") -> None:
    with engine.begin() as c:
        c.execute(sa.text("UPDATE adm.Job SET Status = :s, Result = :r, EndedAt = SYSUTCDATETIME() WHERE Id = :id"),
                  {"s": status, "r": json.dumps(result, ensure_ascii=False), "id": job_id})


def jobs_of(engine, job_type: str) -> list[dict]:
    with engine.connect() as c:
        return [dict(r) for r in c.execute(sa.text("SELECT * FROM adm.Job WHERE JobType = :t ORDER BY Id"), {"t": job_type}).mappings()]


def pulled(entity, status, reason=None) -> dict:
    return {"entity": entity, "name": entity, "status": status, "reason": reason}


# ------------------------------------------------------------------ zamanlama

def test_due_flow_starts_and_pulls_only_sql_tables(env, people):
    sql_table(env, "Material")
    flow(env, people[SYSTEM_OWNER])
    tick(env, DUE + timedelta(seconds=10))
    r = last(env)
    assert (r["State"], r["Step"], r["TriggerType"], r["ScheduledAt"]) == ("Çalışıyor", "Veri çekme", "Zamanlanmış", DUE)
    pull = job(env, r["PullJobId"])
    assert json.loads(pull["Payload"])["entities"] == ["Material"] and pull["RequestedBy"] is None   # Excel tabloları çekilmez
    tick(env, DUE + timedelta(seconds=20))
    assert len(runs(env)) == 1                                                                         # aynı saat için ikinci çalıştırma yok


def test_service_back_within_wait_still_runs(env, people):
    """01:55'te yeniden başlayıp 02:10'da gelen sunucuda 02:00 akışı çalışır."""
    flow(env, people[SYSTEM_OWNER])
    tick(env, DUE + timedelta(minutes=10))
    assert last(env)["State"] == "Çalışıyor" and last(env)["ScheduledAt"] == DUE


def test_service_back_late_is_not_started(env, people):
    flow(env, people[SYSTEM_OWNER])
    tick(env, DUE + timedelta(minutes=61))
    r = last(env)
    assert (r["State"], r["Reason"]) == ("Başlamadı", runner.MISSED) and not jobs_of(env, TYPE_PULL)


def test_flow_saved_after_its_time_waits_for_next_day(env, people):
    flow(env, people[SYSTEM_OWNER], updated=DUE + timedelta(minutes=1))
    tick(env, DUE + timedelta(minutes=2))
    assert runs(env) == []


def test_inactive_and_other_days_do_not_run(env, people):
    flow(env, people[SYSTEM_OWNER], name="Kapalı", active=False)
    flow(env, people[SYSTEM_OWNER], name="Pazar", run_time="02:00", days="7")
    tick(env, DUE + timedelta(seconds=10))
    assert all(r["ScheduledAt"] != DUE for r in runs(env))


def test_overlap_marks_next_flow_not_started(env, people):
    flow(env, people[SYSTEM_OWNER], name="Pazar tam", run_time="01:00")
    flow(env, people[SYSTEM_OWNER], name="Hafta içi kısmi", run_time="02:00", mode="Kısmi", groups=["Stok"])
    sql_table(env, "Material")
    tick(env, DUE - timedelta(minutes=60))                       # 01:00 akışı başlar, çekim sürer
    tick(env, DUE + timedelta(seconds=5))
    first, second = runs(env)
    assert first["State"] == "Çalışıyor"
    assert (second["FlowName"], second["State"], second["Reason"]) == ("Hafta içi kısmi", "Başlamadı", "Pazar tam sürüyordu.")


# ------------------------------------------------------------------ başlangıçta bekleme

def test_waits_for_manual_job_then_starts(env, people):
    flow(env, people[SYSTEM_OWNER])
    with Session(env) as s:
        manual = queue.enqueue(s, TYPE_VALIDATION, CHANNEL_PROCESSING, people[KEY_USER], {})
    tick(env, DUE + timedelta(minutes=1))
    assert last(env)["State"] == "Bekliyor"
    finish(env, manual, {})
    tick(env, DUE + timedelta(minutes=30))
    assert last(env)["State"] == "Çalışıyor"


def test_manual_job_not_finishing_in_time(env, people):
    flow(env, people[SYSTEM_OWNER])
    with Session(env) as s:
        queue.enqueue(s, TYPE_VALIDATION, CHANNEL_PROCESSING, people[KEY_USER], {})
    tick(env, DUE + timedelta(minutes=1))
    tick(env, DUE + timedelta(minutes=61))
    r = last(env)
    assert (r["State"], r["Reason"]) == ("Başlamadı", "Validasyon 60 dakikada bitmedi.")


# ------------------------------------------------------------------ teknik hata ve veri bulgusu

def test_pull_error_stops_before_transfer(env, people):
    sql_table(env, "Material")
    sql_table(env, "Customer")
    flow(env, people[SYSTEM_OWNER])
    tick(env, DUE)
    with env.connect() as c:
        versions = c.execute(sa.text("SELECT COUNT(*) FROM adm.DataVersion")).scalar()
    finish(env, last(env)["PullJobId"], [pulled("Customer", "Alındı"), pulled("Material", "Hata", "SQL kaynağına ulaşılamadı.")])
    tick(env, DUE + timedelta(minutes=5))
    r = last(env)
    assert (r["State"], r["Step"]) == ("Durdu", "Veri çekme") and "Malzeme: SQL kaynağına ulaşılamadı." in r["Reason"]
    assert not jobs_of(env, TYPE_TRANSFER)
    with env.connect() as c:
        assert c.execute(sa.text("SELECT COUNT(*) FROM adm.DataVersion")).scalar() == versions         # kullanılan veri dünkü hâlinde


def test_failed_pull_job_is_a_technical_error(env, people):
    sql_table(env, "Material")
    flow(env, people[SYSTEM_OWNER])
    tick(env, DUE)
    finish(env, last(env)["PullJobId"], [], status="Hata")
    tick(env, DUE + timedelta(minutes=1))
    assert last(env)["State"] == "Durdu" and "Veri çekme işi tamamlanamadı" in last(env)["Reason"]


def test_no_new_data_and_findings_do_not_stop(env, people):
    sql_table(env, "Material")
    sql_table(env, "Customer")
    flow(env, people[SYSTEM_OWNER])
    tick(env, DUE)
    finish(env, last(env)["PullJobId"], [pulled("Customer", "Yeni veri yok", "Son çekimden beri değişiklik yok."), pulled("Material", "Alındı")])
    tick(env, DUE + timedelta(minutes=2))
    r = last(env)
    assert (r["State"], r["Step"]) == ("Çalışıyor", "Aktarım")
    payload = json.loads(job(env, r["TransferJobId"])["Payload"])
    assert payload["user_id"] is None and payload["flow_name"] == "Gece tam" and "mode" not in payload


def test_erp_refresh_is_retried_then_times_out(env, people):
    sql_table(env, "Material")
    sql_table(env, "Stock")
    flow(env, people[SYSTEM_OWNER])
    tick(env, DUE)
    first = last(env)["PullJobId"]
    finish(env, first, [pulled("Material", "Alındı"), pulled("Stock", "Veri güncellemesi devam ediyor")])
    tick(env, DUE + timedelta(minutes=1))
    assert last(env)["PullJobId"] == first                                         # bekleme aralığı
    tick(env, DUE + timedelta(minutes=3))
    retry = last(env)["PullJobId"]
    assert retry != first and json.loads(job(env, retry)["Payload"])["entities"] == ["Stock"]
    finish(env, retry, [pulled("Stock", "Veri güncellemesi devam ediyor")])
    tick(env, DUE + timedelta(minutes=122))
    r = last(env)
    assert (r["State"], r["Step"]) == ("Durdu", "Veri çekme") and r["Reason"] == "ERP veri güncellemesi 120 dakikada bitmedi: Stok."
    assert not jobs_of(env, TYPE_TRANSFER)


def test_erp_refresh_finishing_continues(env, people):
    sql_table(env, "Stock")
    flow(env, people[SYSTEM_OWNER])
    tick(env, DUE)
    finish(env, last(env)["PullJobId"], [pulled("Stock", "Veri güncellemesi devam ediyor")])
    tick(env, DUE + timedelta(minutes=1))
    tick(env, DUE + timedelta(minutes=3))
    finish(env, last(env)["PullJobId"], [pulled("Stock", "Alındı")])
    tick(env, DUE + timedelta(minutes=4))
    assert last(env)["Step"] == "Aktarım"


def _failed_rule(engine, entity: str) -> None:
    with engine.begin() as c:
        c.execute(sa.text("INSERT INTO adm.DataRule (EntityName, Name, Seq, TargetField, ResultKind, Value, ApplyMode, IsActive, LastRunStatus, LastRunMessage) "
                          "VALUES (:e, N'Bozuk kural', 1, N'Name', N'Değer', N'X', N'Her zaman', 1, N'Çalışmadı', N'Alan yok')"), {"e": entity})


def test_failed_data_rule_on_excel_table_stops(env, people):
    _failed_rule(env, "Customer")                       # Müşteri Excel tablosu: çekilmez ama aktarılır
    flow(env, people[SYSTEM_OWNER])
    tick(env, DUE)
    r = last(env)
    assert (r["State"], r["Step"], r["Reason"]) == ("Durdu", "Validasyon", "Çalışmayan veri kuralı var: Müşteri (1).")
    assert not jobs_of(env, TYPE_TRANSFER)


def test_partial_flow_checks_only_its_groups(env, people):
    _failed_rule(env, "Customer")                       # Stok grubunda değil
    flow(env, people[SYSTEM_OWNER], name="Öğlen stok", mode="Kısmi", groups=["Stok"])
    tick(env, DUE)
    r = last(env)
    assert r["Step"] == "Aktarım"
    payload = json.loads(job(env, r["TransferJobId"])["Payload"])
    assert (payload["mode"], payload["groups"]) == ("Kısmi", ["Stok"])
    _clean_flows(env)
    _failed_rule(env, "Stock")
    flow(env, people[SYSTEM_OWNER], name="Öğlen stok", mode="Kısmi", groups=["Stok"])
    tick(env, DUE)
    assert last(env)["State"] == "Durdu" and "Stok (1)" in last(env)["Reason"]


def test_failed_validation_run_stops(env, people):
    flow(env, people[SYSTEM_OWNER])
    tick(env, DUE)                                       # çekecek tablo yok: validasyon, sonra aktarım sırada
    _clean_flows(env)
    flow(env, people[SYSTEM_OWNER])
    sql_table(env, "Material")
    tick(env, DUE)
    with env.begin() as c:
        c.execute(sa.text("INSERT INTO adm.ValidationRun (EntityName, Scope, TriggerType, State, CreatedAt) "
                          "VALUES (N'Material', N'Tablo içi', N'Çekim', N'Valide edilemedi', SYSUTCDATETIME())"))
    finish(env, last(env)["PullJobId"], [pulled("Material", "Alındı")])
    tick(env, DUE + timedelta(minutes=1))
    assert last(env)["State"] == "Durdu" and last(env)["Reason"] == "Validasyon tamamlanamadı: Malzeme."


def test_whole_flow_with_excel_table_transfers_and_skips_cleanup(env, people):
    """Excel tablosu çekilmez, son yüklenmiş hâli aktarılır; Hatalı satır akışı durdurmaz; saklama süresi boşsa temizlik notla atlanır."""
    put(env, {"Customer": [{"Code": "AK-1", "Name": "Akış", "IsActive": 1}]})
    with Session(env) as s:
        validation_engine.enqueue(s, "Customer", validation_engine.SCOPE_TABLE, validation_engine.TRIGGER_UPLOAD)
    run_validations(env)
    flow(env, people[SYSTEM_OWNER], cleanup=True)
    tick(env, DUE)
    r = last(env)
    assert r["Step"] == "Aktarım" and json.loads(r["Detail"])["note"] == "Çekilecek SQL tablosu yok."
    with Session(env) as s:
        claimed = queue.claim_next(s, CHANNEL_PROCESSING, JobSettings(limit_processing=10))
    assert claimed["Id"] == r["TransferJobId"]
    run_transfer_job(claimed["Id"], claimed["Attempt"])
    tick(env, DUE + timedelta(minutes=5))
    r = last(env)
    version = r["DataVersionId"]
    try:
        assert (r["State"], r["Reason"]) == ("Bitti", "Ham veri temizliği atlandı: saklama süresi tanımlı değil.") and version
        customer = next(t for t in json.loads(job(env, r["TransferJobId"])["Result"])["tables"] if t["entity"] == "Customer")
        assert customer["not_transferred"] == 1                     # Excel tablosu aktarıldı; Hatalı satır veri bulgusudur, akışı durdurmaz
    finally:
        with env.begin() as c:
            c.execute(sa.text("DELETE FROM core.Customer WHERE VersionFrom = :v"), {"v": version})
            c.execute(sa.text("UPDATE core.Customer SET VersionTo = NULL WHERE VersionTo = :t"), {"t": version - 1})
            c.execute(sa.text("DELETE FROM adm.DataVersionEntity WHERE DataVersionId = :v"), {"v": version})
            c.execute(sa.text("DELETE FROM adm.DataVersion WHERE Id = :v"), {"v": version})


def test_cleanup_step_and_failed_transfer(env, people):
    with env.begin() as c:
        c.execute(sa.text("INSERT INTO adm.SystemSetting (SettingKey, Value) VALUES (N'RawDataRetentionDays', N'7')"))
    flow(env, people[SYSTEM_OWNER], cleanup=True)
    tick(env, DUE)
    finish(env, last(env)["TransferJobId"], {"data_version": 4242})
    tick(env, DUE + timedelta(minutes=1))
    r = last(env)
    assert (r["Step"], r["DataVersionId"]) == ("Temizlik", 4242) and json.loads(job(env, r["CleanupJobId"])["Payload"])["user_id"] is None
    finish(env, r["CleanupJobId"], {})
    tick(env, DUE + timedelta(minutes=2))
    assert last(env)["State"] == "Bitti"
    _clean_flows(env)
    flow(env, people[SYSTEM_OWNER])
    tick(env, DUE)
    finish(env, last(env)["TransferJobId"], {}, status="Hata")
    tick(env, DUE + timedelta(minutes=1))
    assert last(env)["State"] == "Durdu" and last(env)["Reason"].startswith("Aktarım tamamlanamadı; önceki veri versiyonu geçerli")


# ------------------------------------------------------------------ kesinti

def _service(engine) -> EngineService:
    return EngineService(engine, job_settings=JobSettings(heartbeat_timeout_seconds=120), channels=(), engine_settings=EngineSettings(heartbeat_seconds=60))


def _running_in_transfer(engine, people) -> dict:
    flow(env := engine, people[SYSTEM_OWNER], updated=schedule.utcnow())   # gerçek saatte yeniden zamanlanmasın
    with Session(env) as s:
        f = dict(s.execute(sa.select(runner.FLOW)).mappings().one())
        runner.insert_run(s, f, runner.MANUAL, schedule.utcnow())
        s.commit()
    tick(env, schedule.utcnow())
    r = last(env)
    assert r["Step"] == "Aktarım" and job(env, r["TransferJobId"])["Status"] == "Sırada"
    return r


def test_service_restart_interrupts_running_flow(env, people):
    r = _running_in_transfer(env, people)
    svc = _service(env)
    svc.start()
    try:
        after = last(env)
        assert (after["State"], after["Reason"]) == ("Durdu", runner.INTERRUPTED_RESTART)
        assert job(env, r["TransferJobId"])["Status"] == "İptal"                       # aktarım yapılmaz
    finally:
        svc.shutdown()


def test_sql_connection_drop_during_flow(env, people, monkeypatch):
    """Bağlantı adımların ortasında kopar (taklit), servis yeniden bağlanır: çalıştırma yarıda kesilir, aktarım yapılmaz, sonraki akış normal başlar."""
    svc = _service(env)
    svc.start()
    try:
        r = _running_in_transfer(env, people)
        real_tick = runner.tick

        def dropped(session, now=None):
            raise OperationalError("SELECT 1", {}, Exception("08S01 bağlantı koptu"))
        monkeypatch.setattr(runner, "tick", dropped)
        svc._last_flow_tick = 0.0
        with pytest.raises(OperationalError) as caught:
            svc.poll_once()
        svc._record_loop_error(caught.value)                                           # run_forever'ın yaptığı
        assert last(env)["State"] == "Çalışıyor"                                       # kopukken hiçbir şey yazılmadı
        monkeypatch.setattr(runner, "tick", real_tick)
        svc.poll_once()                                                                # bağlantı geri geldi
        after = last(env)
        assert (after["State"], after["Reason"]) == ("Durdu", runner.INTERRUPTED_DB)
        assert job(env, r["TransferJobId"])["Status"] == "İptal" and not svc._db_lost
        with Session(env) as s:                                                        # sonraki akış normal başlar
            f = dict(s.execute(sa.select(runner.FLOW)).mappings().one())
            runner.insert_run(s, f, runner.MANUAL, schedule.utcnow())
            s.commit()
        svc._last_flow_tick = 0.0
        svc.poll_once()
        assert last(env)["State"] == "Çalışıyor"
    finally:
        svc.shutdown()


def test_deadlock_like_errors_do_not_interrupt(env, people):
    svc = _service(env)
    from sqlalchemy.exc import IntegrityError
    svc._record_loop_error(IntegrityError("x", {}, Exception("tekil")))
    assert not svc._db_lost


# ------------------------------------------------------------------ API, yetki, kilit, çip

BODY = {"name": "Hafta içi kısmi", "run_time": "02:00", "days": [1, 2, 3, 4, 5], "pull_scope": "Seçilen", "pull_tables": ["Stock"],
        "transfer_mode": "Kısmi", "transfer_groups": ["Stok"], "cleanup": False}


def test_roles(env, people):
    client = new_client()
    h = {role: auth(uid) for role, uid in people.items()}
    r = client.post("/api/flows", headers=h[SYSTEM_OWNER], json=BODY)
    assert r.status_code == 200, r.text
    flow_id = r.json()["id"]
    assert client.get("/api/flows", headers=h[ADMIN]).status_code == 200                    # Admin salt okunur (92 istisnası)
    assert client.get("/api/flows", headers=h[ADMIN]).json()["can_edit"] is False
    assert client.post("/api/flows", headers=h[ADMIN], json={**BODY, "name": "B"}).status_code == 403
    assert client.post(f"/api/flows/{flow_id}/run", headers=h[ADMIN]).status_code == 403
    assert client.get("/api/flows", headers=h[KEY_USER]).status_code == 403
    assert client.get("/api/flow-runs/columns", headers=h[KEY_USER]).status_code == 403
    assert client.get("/api/flow-runs/columns", headers=h[ADMIN]).status_code == 200
    assert client.get("/api/flows/status", headers=h[KEY_USER]).status_code == 200          # çip Key user'a
    assert client.get("/api/flows/status", headers=h[END_USER]).status_code == 403


def test_validation_conflict_and_audit(env, people):
    client = new_client()
    h = auth(people[SYSTEM_OWNER])
    bad = client.post("/api/flows", headers=h, json={**BODY, "name": " ", "run_time": "25:00", "days": [], "pull_tables": [], "transfer_groups": []})
    assert bad.status_code == 422 and {p["field"] for p in bad.json()["error"]["details"]} == {"name", "run_time", "days", "pull_tables", "transfer_groups"}
    assert client.post("/api/flows", headers=h, json=BODY).status_code == 200
    r = client.post("/api/flows", headers=h, json={**BODY, "name": "Cuma tam", "days": [5, 6], "transfer_mode": "Tam", "transfer_groups": []})
    assert r.status_code == 409 and r.json()["error"]["message"] == "Aynı gün ve saatte başka bir akış var: Hafta içi kısmi (Cum 02:00)."
    assert client.post("/api/flows", headers=h, json={**BODY, "name": "Cuma tam", "days": [6], "transfer_mode": "Tam"}).status_code == 200
    assert client.post("/api/flows", headers=h, json={**BODY, "name": "Kapalı", "is_active": False}).status_code == 200   # pasif çakışmaz
    body = client.get("/api/flows", headers=h).json()
    saved = {f["name"]: f for f in body["flows"]}
    assert saved["Cuma tam"]["transfer_groups"] == [] and saved["Hafta içi kısmi"]["days_text"] == "Hafta içi" and saved["Hafta içi kısmi"]["next_at"]
    assert {g["name"]: g["sql_tables"] for g in body["options"]["groups"]}["Stok"] == []                               # SQL tablosu yok
    with env.connect() as c:
        row = c.execute(sa.text("SELECT TOP 1 ObjectKey, NewValue FROM adm.AuditLog WHERE Action = N'Akış tanımlandı' ORDER BY Id DESC")).one()
    assert row[0] == "Kapalı" and json.loads(row[1])["IsActive"] is False


def test_run_now_lock_and_chip(env, people):
    client = new_client()
    h = auth(people[SYSTEM_OWNER])
    key = auth(people[KEY_USER])
    flow_id = client.post("/api/flows", headers=h, json=BODY).json()["id"]
    run_id = client.post(f"/api/flows/{flow_id}/run", headers=h).json()["run_id"]
    r = last(env)
    assert (r["Id"], r["State"], r["TriggerType"], r["RequestedBy"]) == (run_id, "Bekliyor", "Elle", people[SYSTEM_OWNER])
    again = client.post(f"/api/flows/{flow_id}/run", headers=h)
    assert again.status_code == 409 and again.json()["error"]["code"] == "flow_running"
    status = client.get("/api/flows/status", headers=key).json()
    assert status["running"]["flow_name"] == "Hafta içi kısmi" and status["running"]["message"].startswith("Zamanlanmış akış sürüyor: Hafta içi kısmi (başlama ")
    locked = [
        client.post("/api/pulls", headers=h, json={}),
        client.post("/api/transfers", headers=h),
        client.post("/api/transfers/partial", headers=h, json={"groups": ["Stok"]}),
        client.post("/api/cleanup", headers=h),
        client.put("/api/data-rules", headers=h, json={"changes": [], "orders": []}),
        client.post("/api/data-rules/apply", headers=h, json={}),
        client.put("/api/validation-rules", headers=h, json={"changes": [], "thresholds": []}),
        client.put("/api/integration/entities", headers=h, json={"changes": [{"entity": "Customer", "pull_enabled": True}]}),
        client.post("/api/imports/Customer?mode=Tam", headers={**h, "X-File-Name": "x.xlsx"}, content=b"PK"),
        client.post("/api/imports?mode=Tam", headers={**h, "X-File-Name": "x.xlsx"}, content=b"PK"),
    ]
    assert [x.status_code for x in locked] == [409] * len(locked), [x.text for x in locked]
    assert {x.json()["error"]["code"] for x in locked} == {"flow_running"}
    # akış durdu: çip görünür, kapatılınca o kullanıcıda kaybolur
    with env.begin() as c:
        c.execute(sa.text("UPDATE adm.FlowRun SET State = N'Durdu', Step = N'Veri çekme', Reason = N'Veri çekilemedi', EndedAt = SYSUTCDATETIME()"))
    status = client.get("/api/flows/status", headers=key).json()
    assert status["running"] is None and [a["reason"] for a in status["alerts"]] == ["Veri çekilemedi"] and status["can_view_history"] is False
    assert client.post(f"/api/flows/runs/{run_id}/dismiss", headers=key).status_code == 204
    assert client.get("/api/flows/status", headers=key).json()["alerts"] == []
    assert len(client.get("/api/flows/status", headers=h).json()["alerts"]) == 1                   # öteki kullanıcıda durur
    # başarılı akış çipi kaldırır
    with Session(env) as s:
        f = dict(s.execute(sa.select(runner.FLOW)).mappings().one())
        runner.insert_run(s, f, runner.MANUAL, schedule.utcnow(), state=runner.DONE)
        s.commit()
    assert client.get("/api/flows/status", headers=h).json()["alerts"] == []


def test_transfer_plan_warns_failed_rules(env, people):
    _failed_rule(env, "Customer")
    client = new_client()
    body = client.get("/api/transfers/plan", headers=auth(people[KEY_USER])).json()
    assert {t["entity"]: t["failed_rules"] for t in body["tables"]}["Customer"] == 1
    partial = client.get("/api/transfers/partial/plan", headers=auth(people[KEY_USER])).json()
    assert all(t["failed_rules"] == 0 for g in partial["groups"] for t in g["tables"])


def test_settings_have_flow_waits(env, people):
    client = new_client()
    h = auth(people[SYSTEM_OWNER])
    body = client.get("/api/settings/health", headers=h).json()
    assert body["defaults"]["FlowWaitMinutes"] == 60 and body["defaults"]["FlowRefreshWaitMinutes"] == 120
    assert body["limits"]["FlowWaitMinutes"] == {"min": 5, "max": 720}
    assert client.put("/api/settings/health", headers=h, json={"FlowWaitMinutes": 4}).status_code == 422
    assert client.put("/api/settings/health", headers=h, json={"FlowWaitMinutes": 30}).json()["values"]["FlowWaitMinutes"] == 30
    flow(env, people[SYSTEM_OWNER])
    tick(env, DUE + timedelta(minutes=31))
    assert last(env)["Reason"] == runner.MISSED


def test_scheduler_row(env, people):
    client = new_client()
    h = auth(people[SYSTEM_OWNER])

    def row():
        return next(s for s in client.get("/api/system-health", headers=h).json()["services"] if s["key"] == "scheduler")
    assert row()["status"] == "Kapalı"
    with env.begin() as c:
        for name in ("Motor", "Zamanlayıcı"):
            c.execute(sa.text("DELETE FROM adm.ServiceStatus WHERE ServiceName = :n"), {"n": name})
            c.execute(sa.text("INSERT INTO adm.ServiceStatus (ServiceName, HeartbeatAt, StartedAt, AppVersion) VALUES (:n, SYSUTCDATETIME(), SYSUTCDATETIME(), N'test')"),
                      {"n": name})
    assert row()["status"] == "Çalışıyor" and row()["checked_at"]
    now_local = schedule.utc_to_local(schedule.utcnow()) - timedelta(minutes=5)   # 5 dakika önce saati gelmiş, çalıştırma yok
    flow(env, people[SYSTEM_OWNER], name="Geciken", run_time=now_local.strftime("%H:%M"), updated=schedule.utcnow() - timedelta(days=1))
    data = row()
    assert (data["status"], data["late"]) == ("Gecikti", "Geciken") and data["next"]["name"] == "Geciken"
