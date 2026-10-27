"""Kurulum sonrası duman testi (verify.ps1 çağırır; docs/10-kurulum.md · Kontrol).

IIS üzerinden sağlık ve WebSocket, motor servisiyle bir deneme plan hesabı. Deneme verisi açılır ve silinir.
Ayarlar SMARTCHAIN_CONFIG'ten okunur; paketteki Python ile, kurulum klasöründen çalıştırılır.
"""
import argparse
import asyncio
import json
import sys
import time
import urllib.request
from pathlib import Path

TEST_LOCATION = "KURULUM-TESTI"


def check_health(base_url: str) -> str:
    try:
        with urllib.request.urlopen(f"{base_url}/api/health", timeout=10) as r:
            body = json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = json.loads(e.read())
    if body.get("status") != "ok":
        raise AssertionError(f"Sağlık: {body.get('database', {}).get('message')}")
    return f"sürüm {body['app_version']}, şema {body['database']['schema_version']}"


def check_websocket(base_url: str) -> str:
    import websockets

    async def run():
        url = base_url.replace("http", "ws", 1) + "/api/ws?user_id=0"
        async with websockets.connect(url, open_timeout=10) as ws:
            hello = json.loads(await asyncio.wait_for(ws.recv(), 10))
            await ws.send("ping")
            pong = json.loads(await asyncio.wait_for(ws.recv(), 10))
        if hello.get("type") != "hello" or pong.get("type") != "pong":
            raise AssertionError(f"WebSocket beklenmeyen yanıt: {hello} {pong}")
    asyncio.run(run())
    return "hello ve pong geldi (IIS üzerinden)"


def check_engine(timeout: int) -> str:
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    from app.api.db import get_engine
    from app.engine.fake import ensure_fixture_warning_definitions
    from app.engine.submit import submit_plan_run

    db = get_engine()
    with Session(db) as s:
        ensure_fixture_warning_definitions(s)
        loc = s.execute(text("INSERT INTO core.Location (Code, Name, Type) OUTPUT inserted.Id "
                             "VALUES (:c, N'Kurulum testi', N'Tesis')"), {"c": TEST_LOCATION}).scalar_one()
        dv = s.execute(text("INSERT INTO adm.DataVersion (LocationId, CreatedAt, LoadType) OUTPUT inserted.Id "
                            "VALUES (:l, SYSUTCDATETIME(), N'Tam')"), {"l": loc}).scalar_one()
        ps = s.execute(text("INSERT INTO param.ParameterSet (Name) OUTPUT inserted.Id VALUES (N'Kurulum testi')")
                       ).scalar_one()
        s.commit()
        run_id = job_id = None
        try:
            run_id, job_id = submit_plan_run(s, data_version_id=dv, parameter_set_id=ps)
            deadline = time.monotonic() + timeout
            status = None
            while time.monotonic() < deadline:
                status = s.execute(text("SELECT Status FROM planning.PlanRun WHERE Id = :id"), {"id": run_id}).scalar()
                s.commit()
                if status in ("Bitti", "Kısmen", "Hata"):
                    break
                time.sleep(1)
            orders = s.execute(text("SELECT COUNT(*) FROM planning.PlannedOrder WHERE PlanRunId = :id"),
                               {"id": run_id}).scalar()
            if status != "Bitti" or not orders:
                error = s.execute(text("SELECT ErrorText FROM adm.Job WHERE Id = :id"), {"id": job_id}).scalar()
                raise AssertionError(f"Plan hesabı bitmedi: {status} {error or ''}")
            return f"PlanRun {run_id} Bitti, {orders} planlı sipariş"
        finally:
            s.rollback()
            p = {"r": run_id, "j": job_id, "dv": dv, "ps": ps, "l": loc}
            if run_id:
                for t in ("PlanWarning", "Pegging", "CapacityLoad", "DemandFulfillment", "SupplyRecommendation",
                          "PlannedOrder", "PlanMetric"):
                    s.execute(text(f"DELETE FROM planning.{t} WHERE PlanRunId = :r"), p)
                s.execute(text("DELETE FROM adm.SolverLog WHERE PlanRunId = :r"), p)
                s.execute(text("DELETE FROM planning.PlanRun WHERE Id = :r"), p)
            if job_id:
                s.execute(text("DELETE FROM adm.Job WHERE Id = :j"), p)
            s.execute(text("DELETE FROM param.ParameterSet WHERE Id = :ps"), p)
            s.execute(text("DELETE FROM adm.DataVersion WHERE Id = :dv"), p)
            s.execute(text("DELETE FROM core.Location WHERE Id = :l"), p)
            s.commit()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", default="http://localhost")
    p.add_argument("--engine-timeout", type=int, default=120)
    p.add_argument("--skip-engine", action="store_true")
    a = p.parse_args()
    sys.path.insert(0, str(Path.cwd()))
    checks = [("Sağlık (IIS)", lambda: check_health(a.base_url)),
              ("WebSocket (IIS)", lambda: check_websocket(a.base_url))]
    if not a.skip_engine:
        checks.append(("Motor: deneme plan hesabı", lambda: check_engine(a.engine_timeout)))
    failed = 0
    for name, fn in checks:
        try:
            print(f"GEÇTİ  {name}: {fn()}")
        except Exception as exc:  # her kontrol ayrı raporlanır
            failed += 1
            print(f"KALDI  {name}: {exc}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
