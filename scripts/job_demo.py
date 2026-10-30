"""İş kuyruğu ve WebSocket bildirimi demosu (adım 0.4). Geliştirme aracı; kurulum paketine girmez.

Önce API'yi başlatın:   uvicorn app.api.main:app --port 8000
Sonra:                  python scripts/job_demo.py --jobs 5

'demo' kullanıcısı adına iş ekler, sahte işçi gibi çalıştırır (sınır kadar aynı anda, ilerleme ve kalp atışı
yazarak) ve WebSocket'ten gelen bildirimleri yazdırır. Gerçek işçi motor servisinde gelecek (0.5, 0.6).
"""
import argparse
import asyncio
import json
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import websockets  # noqa: E402  (uvicorn[standard] ile gelir)
from sqlalchemy import bindparam, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.db import get_engine  # noqa: E402
from app.api.deps import COOKIE  # noqa: E402
from app.api.services.auth import open_session  # noqa: E402
from app.jobs import queue  # noqa: E402
from app.jobs.constants import ACTIVE_STATUSES, CHANNEL_INTERACTIVE, TYPE_WORKSPACE  # noqa: E402
from app.jobs.settings import read_settings  # noqa: E402

STEPS = ["Veri okunuyor", "Model kuruluyor", "Çözülüyor", "Sonuç yazılıyor"]


def demo_user(engine) -> int:
    """'demo' kullanıcısını açar; önceki demodan kalan işlerini siler."""
    with engine.begin() as conn:
        conn.execute(text("IF NOT EXISTS (SELECT 1 FROM adm.AppUser WHERE UserName = N'demo') "
                          "INSERT INTO adm.AppUser (UserName, FullName, Role, MustChangePassword) "  # şifresiz (K-98)
                          "VALUES (N'demo', N'Demo kullanıcı', N'Key user', 0)"))
        user = conn.execute(text("SELECT Id FROM adm.AppUser WHERE UserName = N'demo'")).scalar_one()
        conn.execute(text("DELETE FROM adm.Job WHERE RequestedBy = :u"), {"u": user})
        return user


def run_job(engine, job: dict, step_seconds: float) -> None:
    with Session(engine) as s:
        for step in STEPS:
            time.sleep(step_seconds)
            if not queue.heartbeat(s, job["Id"], job["Attempt"], step):
                return
        queue.finish(s, job["Id"], job["Attempt"], "Tamamlandı")


def worker(engine, ids: list[int], step_seconds: float) -> None:
    """Sahte işçi: yer açıldıkça sıradaki işi alır ve ayrı iş parçacığında çalıştırır."""
    with Session(engine) as s:
        settings = read_settings(s)
        while True:
            job = queue.claim_next(s, CHANNEL_INTERACTIVE, settings)
            if job:
                threading.Thread(target=run_job, args=(engine, job, step_seconds), daemon=True).start()
                continue
            open_jobs = s.execute(text("SELECT COUNT(*) FROM adm.Job WHERE Id IN :ids AND Status IN :active")
                                  .bindparams(bindparam("ids", expanding=True), bindparam("active", expanding=True)),
                                  {"ids": ids, "active": list(ACTIVE_STATUSES)}).scalar_one()
            s.commit()
            if open_jobs == 0:
                return
            time.sleep(0.5)


async def listen(url: str, ready: asyncio.Event, token: str) -> None:
    async with websockets.connect(url, additional_headers={"Cookie": f"{COOKIE}={token}"}) as ws:
        async for raw in ws:
            msg = json.loads(raw)
            if msg["type"] == "hello":
                ready.set()
            if msg["type"] == "job":
                j = msg["job"]
                where = f"sıra {j['queue_position']}" if j["queue_position"] else (j["progress"] or "")
                print(f"  WS  iş {j['id']:>4}  {j['status']:<10} {where}")
            else:
                print(f"  WS  {msg}")


async def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--jobs", type=int, default=5)
    p.add_argument("--step", type=float, default=1.0, help="adım süresi (sn)")
    p.add_argument("--url", default="ws://127.0.0.1:8000/api/ws")
    args = p.parse_args()

    engine = get_engine()
    user = demo_user(engine)
    ready = asyncio.Event()
    with Session(engine) as s:  # WebSocket oturumla açılır (K-97); demo kullanıcısının oturumu doğrudan açılır
        token = open_session(s, user, agent="job_demo.py")
    listener = asyncio.create_task(listen(args.url, ready, token))
    await asyncio.wait_for(ready.wait(), 10)  # bağlantı kurulmadan iş eklenmez

    with Session(engine) as s:
        ids = [queue.enqueue(s, TYPE_WORKSPACE, CHANNEL_INTERACTIVE, user, {"demo": i}) for i in range(args.jobs)]
        settings = read_settings(s)
    print(f"{len(ids)} iş eklendi (kullanıcı {user}); etkileşim sınırı {settings.limit_interactive}")

    await asyncio.to_thread(worker, engine, ids, args.step)
    await asyncio.sleep(2)  # son bildirimler gelsin
    listener.cancel()
    print("Bitti.")


if __name__ == "__main__":
    asyncio.run(main())
