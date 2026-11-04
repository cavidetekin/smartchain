"""Sistem sağlığı demosu (adım 2.5; K-106, K-107). Geliştirme aracı; kurulum paketine girmez.

Yalnız işaretli satırlara dokunur: işlerde Payload {"demo": true}, olaylarda TraceId "demo".

    python scripts/health_demo.py queue 3 --user burak      sıraya iş ekler (motor açıksa hemen çalışıp Hata olur)
    python scripts/health_demo.py stuck --user burak        kalp atışı 5 dk eski çalışan iş; deneme hakkı var
    python scripts/health_demo.py stuck --last --user burak aynısı, deneme hakkı bitmiş
    python scripts/health_demo.py error                     örnek hata olayı
    python scripts/health_demo.py old-event                 100 gün önceye tarihli olay
    python scripts/health_demo.py clean-jobs                işaretli işleri siler, olaylar kalır
    python scripts/health_demo.py clean                     işaretli işleri ve olayları siler
    python scripts/health_demo.py run-engine                motor servisi; stop-engine ile düzgün kapanır (Ctrl+C gibi)
    python scripts/health_demo.py stop-engine               run-engine'i düzgün kapatır
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.db import get_engine  # noqa: E402
from app.api.logging_setup import setup_logging  # noqa: E402
from app.api.settings import get_settings  # noqa: E402
from app.engine.service import EngineService  # noqa: E402
from app.jobs import events, queue  # noqa: E402
from app.jobs.constants import CHANNEL_INTERACTIVE, STATUS_RUNNING, TYPE_WORKSPACE  # noqa: E402
from app.jobs.settings import read_settings  # noqa: E402

MARK = {"demo": True}
TRACE = "demo"
DEMO_JOBS = "Payload = :payload"


def stop_file() -> Path:
    return Path(get_settings().log_dir) / "health_demo.stop"


def run_engine() -> None:
    """Gerçek motor servisi, pencere gerektirmeden düzgün kapanabilir: WinSW'nin Ctrl+C'si gibi aynı kapanış yolundan geçer."""
    setup_logging(get_settings(), "engine.log")
    stop_file().unlink(missing_ok=True)
    svc = EngineService()
    svc.start()
    print("Motor çalışıyor", flush=True)
    try:
        while not stop_file().exists():
            svc.poll_once()
            time.sleep(1)
    finally:
        svc.shutdown()
        stop_file().unlink(missing_ok=True)
    print("Motor düzgün kapandı", flush=True)


def user_id(session: Session, name: str) -> int:
    found = session.execute(text("SELECT Id FROM adm.AppUser WHERE UserName = :n"), {"n": name}).scalar()
    if found is None:
        sys.exit(f"Kullanıcı yok: {name}")
    return found


def add_queue(session: Session, count: int, name: str) -> None:
    user = user_id(session, name)
    ids = [queue.enqueue(session, TYPE_WORKSPACE, CHANNEL_INTERACTIVE, user, MARK, summary=f"Demo çalışması {i + 1} · yeniden hesap")
           for i in range(count)]
    print("Sıraya eklendi:", ids)


def add_stuck(session: Session, name: str, last: bool) -> None:
    attempt = read_settings(session).max_attempts if last else 1
    job = session.execute(text(
        "INSERT INTO adm.Job (JobType, Channel, Status, RequestedBy, Payload, Attempt, HeartbeatAt, CreatedAt, StartedAt, UpdatedAt) "
        "OUTPUT inserted.Id VALUES (:type, :channel, :running, :user, :payload, :attempt, DATEADD(minute, -5, SYSUTCDATETIME()), "
        "DATEADD(minute, -6, SYSUTCDATETIME()), DATEADD(minute, -6, SYSUTCDATETIME()), SYSUTCDATETIME())"),
        {"type": TYPE_WORKSPACE, "channel": CHANNEL_INTERACTIVE, "running": STATUS_RUNNING, "user": user_id(session, name),
         "payload": json.dumps(MARK), "attempt": attempt}).scalar_one()
    session.commit()
    print(f"Takılı iş #{job} (deneme {attempt}); API 15 sn içinde geri alır")


def add_error(session: Session) -> None:
    written = events.record(session, events.COMPONENT_APP, "Örnek hata · demo", "Takip numarası verildi", trace_id=TRACE, detail="ÖrnekHata")
    session.commit()
    print("Olay yazıldı" if written else "Son 60 sn içinde aynısı yazılmıştı")


def add_old_event(session: Session) -> None:
    session.execute(text(
        "INSERT INTO adm.SystemEvent (OccurredAt, Component, Message, Resolution, IsResolved, TraceId) "
        "VALUES (DATEADD(day, -100, SYSUTCDATETIME()), :c, N'100 günlük örnek olay', N'Saklama süresi doldu', 0, :t)"),
        {"c": events.COMPONENT_APP, "t": TRACE})
    session.commit()
    print("100 günlük olay yazıldı; motor açılışında ya da saatlik temizlikte silinir")


def clean(session: Session, jobs_only: bool) -> None:
    payload = {"payload": json.dumps(MARK)}
    ids = [r[0] for r in session.execute(text(f"SELECT Id FROM adm.Job WHERE {DEMO_JOBS}"), payload)]
    gone = session.execute(text(f"DELETE FROM adm.Job OUTPUT deleted.Id WHERE {DEMO_JOBS}"), payload).all()
    count = 0
    if not jobs_only:
        count = len(session.execute(text("DELETE FROM adm.SystemEvent OUTPUT deleted.Id WHERE TraceId = :t"), {"t": TRACE}).all())
        for job in ids:
            count += len(session.execute(text("DELETE FROM adm.SystemEvent OUTPUT deleted.Id WHERE JobId = :j"), {"j": job}).all())
    session.commit()
    print(f"Silinen iş {len(gone)}, olay {count}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["queue", "stuck", "error", "old-event", "clean-jobs", "clean", "run-engine", "stop-engine"])
    parser.add_argument("count", nargs="?", type=int, default=1)
    parser.add_argument("--user", default="burak")
    parser.add_argument("--last", action="store_true", help="stuck: deneme hakkı bitmiş")
    args = parser.parse_args()
    if args.command == "run-engine":
        run_engine()
        return
    if args.command == "stop-engine":
        stop_file().parent.mkdir(parents=True, exist_ok=True)
        stop_file().touch()
        print("Motora kapanması söylendi")
        return
    with Session(get_engine()) as session:
        print("Veritabanı:", session.execute(text("SELECT DB_NAME()")).scalar_one())
        if args.command == "queue":
            add_queue(session, args.count, args.user)
        elif args.command == "stuck":
            add_stuck(session, args.user, args.last)
        elif args.command == "error":
            add_error(session)
        elif args.command == "old-event":
            add_old_event(session)
        else:
            clean(session, args.command == "clean-jobs")


if __name__ == "__main__":
    main()
