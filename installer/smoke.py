"""Kurulum sonrası duman testi (verify.ps1 çağırır; docs/10-kurulum.md · Kontrol).

IIS üzerinden sağlık ve WebSocket, motor servisiyle bir deneme plan hesabı, çözücü (HiGHS) paket kontrolü.
Deneme verisi açılır ve silinir.
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
    """WebSocket IIS üzerinden: oturumsuz el sıkışma reddedilir (403); geçici bir test kullanıcısının oturumuyla
    hello ve pong gelir (K-97). Test kullanıcısının şifresi yoktur (arayüzden giremez); sonunda silinir."""
    import websockets
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    from app.api.db import get_engine
    from app.api.deps import COOKIE
    from app.api.services.auth import open_session

    url = base_url.replace("http", "ws", 1) + "/api/ws"

    async def rejected():
        try:
            async with websockets.connect(url, open_timeout=10):
                pass
        except websockets.exceptions.InvalidStatus as exc:
            return exc.response.status_code
        return None

    async def hello(token: str):
        async with websockets.connect(url, open_timeout=10, additional_headers={"Cookie": f"{COOKIE}={token}"}) as ws:
            first = json.loads(await asyncio.wait_for(ws.recv(), 10))
            await ws.send("ping")
            second = json.loads(await asyncio.wait_for(ws.recv(), 10))
        return first, second

    status = asyncio.run(rejected())
    if status != 403:
        raise AssertionError(f"Oturumsuz WebSocket reddedilmedi (durum {status})")
    with Session(get_engine()) as s:
        s.execute(text("IF NOT EXISTS (SELECT 1 FROM adm.AppUser WHERE UserName = N'kurulum.testi') "
                       "INSERT INTO adm.AppUser (UserName, FullName, Role, IsActive, MustChangePassword) "
                       "VALUES (N'kurulum.testi', N'Kurulum testi', N'End user', 1, 0)"))
        user = s.execute(text("SELECT Id FROM adm.AppUser WHERE UserName = N'kurulum.testi'")).scalar_one()
        token = open_session(s, user, agent="smoke.py")
    try:
        first, second = asyncio.run(hello(token))
    finally:
        with Session(get_engine()) as s:
            s.execute(text("DELETE FROM adm.UserSession WHERE UserId = :u"), {"u": user})
            s.execute(text("DELETE FROM adm.AppUser WHERE Id = :u"), {"u": user})
            s.commit()
    if first.get("type") != "hello" or second.get("type") != "pong":
        raise AssertionError(f"WebSocket beklenmeyen yanıt: {first} {second}")
    return "oturumsuz 403; oturumla hello ve pong geldi (IIS üzerinden)"


def check_engine(timeout: int) -> str:
    from sqlalchemy import text
    from sqlalchemy.orm import Session

    from app.api.db import get_engine
    from app.engine.fake import ensure_fixture_warning_definitions
    from app.engine.submit import submit_plan_run

    db = get_engine()
    with Session(db) as s:
        ensure_fixture_warning_definitions(s)
        loc = s.execute(text("INSERT INTO core.Location (Code, Name, Type, IsSynthetic) OUTPUT inserted.Id "
                             "VALUES (:c, N'Kurulum testi', N'Tesis', 1)"), {"c": TEST_LOCATION}).scalar_one()
        dv = s.execute(text("INSERT INTO adm.DataVersion (LocationId, CreatedAt, LoadType, IsSynthetic) OUTPUT inserted.Id "
                            "VALUES (:l, SYSUTCDATETIME(), N'Tam', 1)"), {"l": loc}).scalar_one()
        ps = s.execute(text("INSERT INTO param.ParameterSet (Name, IsSynthetic) OUTPUT inserted.Id "
                            "VALUES (N'Kurulum testi', 1)")).scalar_one()
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


def check_solver() -> str:
    from app.engine.solvers.highs import smoke_test
    r = smoke_test(time_limit=10.0, threads=1)
    return (f"{r['solver']} {r['version']}: LP optimal, amaç {r['lp']['objective']:g} · "
            f"MILP optimal, amaç {r['milp']['objective']:g}")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", default="http://localhost")
    p.add_argument("--engine-timeout", type=int, default=120)
    p.add_argument("--skip-engine", action="store_true")
    p.add_argument("--solver-only", action="store_true", help="yalnız çözücü paket kontrolü (IIS ve veritabanı gerekmez)")
    a = p.parse_args()
    sys.path.insert(0, str(Path.cwd()))
    checks = [("Çözücü (HiGHS)", check_solver)]
    if not a.solver_only:
        checks += [("Sağlık (IIS)", lambda: check_health(a.base_url)),
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
