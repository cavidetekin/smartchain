"""Motor arayüzü ve sahte motor demosu (adım 0.5). Geliştirme aracı; kurulum paketine girmez.

API'yi yeni sürümle başlatın:   uvicorn app.api.main:app --port 8000
Sonra:                          python scripts/engine_demo.py --runs 4

'demo' kullanıcısı adına plan hesapları (PlanRun + iş) gönderir, motor servisini bu süreçte çalıştırır
(her iş ayrı süreçte, kalp atışı servisten), WebSocket'ten gelen ilerlemeyi ve sonuçta planning.* satır
sayılarını yazdırır. API'ye bağlanılamazsa bildirimler olmadan devam eder.
"""
import argparse
import asyncio
import json
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import websockets  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.db import get_engine  # noqa: E402
from app.api.deps import COOKIE  # noqa: E402
from app.api.services.auth import open_session  # noqa: E402
from app.engine.fake import ensure_fixture_warning_definitions  # noqa: E402
from app.engine.service import EngineService  # noqa: E402
from app.engine.submit import submit_plan_run  # noqa: E402
from app.jobs.constants import ACTIVE_STATUSES  # noqa: E402

TABLES = ["PlannedOrder", "SupplyRecommendation", "DemandFulfillment", "CapacityLoad", "Pegging", "PlanWarning",
          "PlanMetric"]


def demo_refs(session: Session, step: float) -> dict:
    """Demo kullanıcısı, lokasyonu, veri versiyonu ve parametre seti (yoksa açılır)."""
    ensure_fixture_warning_definitions(session)
    q = lambda sql, **p: session.execute(text(sql), p)  # noqa: E731
    q("IF NOT EXISTS (SELECT 1 FROM adm.AppUser WHERE UserName = N'demo') INSERT INTO adm.AppUser "
      "(UserName, FullName, Role, MustChangePassword) VALUES (N'demo', N'Demo kullanıcı', N'Key user', 0)")  # şifresiz (K-98)
    q("IF NOT EXISTS (SELECT 1 FROM core.Location WHERE Code = N'DEMO') "
      "INSERT INTO core.Location (Code, Name, Type, IsSynthetic) VALUES (N'DEMO', N'Demo fabrikası', N'Tesis', 1)")
    user = q("SELECT Id FROM adm.AppUser WHERE UserName = N'demo'").scalar_one()
    loc = q("SELECT Id FROM core.Location WHERE Code = N'DEMO'").scalar_one()
    dv = q("SELECT TOP 1 Id FROM adm.DataVersion WHERE LocationId = :l ORDER BY Id", l=loc).scalar()
    if dv is None:
        dv = q("INSERT INTO adm.DataVersion (LocationId, CreatedAt, LoadType, IsSynthetic) OUTPUT inserted.Id "
               "VALUES (:l, SYSUTCDATETIME(), N'Tam', 1)", l=loc).scalar_one()
    ps = q("SELECT TOP 1 Id FROM param.ParameterSet WHERE Name = N'Demo · sahte motor'").scalar()
    if ps is None:
        ps = q("INSERT INTO param.ParameterSet (Name, IsSynthetic) OUTPUT inserted.Id VALUES (N'Demo · sahte motor', 1)").scalar_one()
    q("DELETE FROM param.PlanningSetting WHERE ParameterSetId = :p", p=ps)
    for k, v in {"ModelType": "LP", "FakeEngineStepSeconds": str(step), "FakeEngineMode": "normal"}.items():
        q("INSERT INTO param.PlanningSetting (ParameterSetId, SettingKey, Value) VALUES (:p, :k, :v)", p=ps, k=k, v=v)
    q("DELETE FROM adm.Job WHERE RequestedBy = :u", u=user)  # önceki demo işleri
    session.commit()
    return {"user": user, "data_version": dv, "parameter_set": ps}


def run_service(db, job_ids: list[int], stop: threading.Event) -> None:
    svc = EngineService(db)
    svc.start()
    try:
        with Session(db) as s:
            while not stop.is_set():
                svc.poll_once()
                open_jobs = s.execute(text("SELECT COUNT(*) FROM adm.Job WHERE Id IN ({}) AND Status IN (:a, :b)"
                                           .format(",".join(map(str, job_ids)))),
                                      {"a": ACTIVE_STATUSES[0], "b": ACTIVE_STATUSES[1]}).scalar_one()
                s.commit()
                if open_jobs == 0 and not svc.running:
                    return
                time.sleep(0.5)
    finally:
        svc.shutdown()


async def listen(url: str, ready: asyncio.Event, token: str) -> None:
    try:
        async with websockets.connect(url, open_timeout=5, additional_headers={"Cookie": f"{COOKIE}={token}"}) as ws:
            async for raw in ws:
                msg = json.loads(raw)
                if msg["type"] == "hello":
                    ready.set()
                    print(f"  WS  bağlandı ({url})")
                elif msg["type"] == "job":
                    j = msg["job"]
                    where = f"sıra {j['queue_position']}" if j["queue_position"] else (j["progress"] or "")
                    print(f"  WS  iş {j['id']:>4}  {j['status']:<10} {where}")
    except (OSError, websockets.exceptions.WebSocketException) as exc:
        print(f"  WS  bağlanılamadı ({exc}); bildirimler olmadan devam")
        ready.set()


async def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--runs", type=int, default=4, help="plan hesabı sayısı")
    p.add_argument("--step", type=float, default=1.0, help="sahte motorun adım süresi (sn)")
    p.add_argument("--url", default="ws://127.0.0.1:8000/api/ws")
    args = p.parse_args()

    db = get_engine()
    with Session(db) as s:
        refs = demo_refs(s, args.step)
    ready = asyncio.Event()
    with Session(db) as s:  # WebSocket oturumla açılır (K-97); demo kullanıcısının oturumu doğrudan açılır
        token = open_session(s, refs["user"], agent="engine_demo.py")
    listener = asyncio.create_task(listen(args.url, ready, token))
    await asyncio.wait_for(ready.wait(), 10)

    with Session(db) as s:
        submitted = [submit_plan_run(s, data_version_id=refs["data_version"], parameter_set_id=refs["parameter_set"],
                                     requested_by=refs["user"]) for _ in range(args.runs)]
    print(f"{len(submitted)} plan hesabı gönderildi: PlanRun {[r for r, _ in submitted]}")

    stop = threading.Event()
    await asyncio.to_thread(run_service, db, [j for _, j in submitted], stop)
    await asyncio.sleep(2)  # son bildirimler gelsin
    listener.cancel()

    with Session(db) as s:
        for run_id, job_id in submitted:
            status, engine_used, solver = s.execute(text(
                "SELECT Status, EngineUsed, Solver FROM planning.PlanRun WHERE Id = :id"), {"id": run_id}).one()
            n = {t: s.execute(text(f"SELECT COUNT(*) FROM planning.{t} WHERE PlanRunId = :id"), {"id": run_id}).scalar()
                 for t in TABLES}
            print(f"PlanRun {run_id} (iş {job_id}): {status}, {engine_used}/{solver} · "
                  + ", ".join(f"{t} {c}" for t, c in n.items()))


if __name__ == "__main__":
    asyncio.run(main())
