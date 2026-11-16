"""Geliştirme aracı (K-174): `python -m app.quality run [--gun YYYY-MM-DD]`.

Tam kapsamlı bir "Veri kalitesi" işini kuyruğa koyar; --gun verilirse tarihli kurallar o güne göre çalışır (gün dönümünü bir gün beklemeden
göstermek için). Veritabanında tarih geriye alınmaz, hiçbir şey silinmez; yalnız uyarı tabloları yazılır, bir sonraki gerçek koşu bugünle düzeltir.
Ürün işlevi değildir, arayüzde yoktur. İşi motor servisi çalıştırır (açık olmalı).
"""
import argparse
from datetime import date

from sqlalchemy.orm import Session

from . import TRIGGER_DEV, enqueue


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.quality", description="Veri kalitesi geliştirme aracı (K-174)")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="tam kapsamlı Veri kalitesi işini kuyruğa koy")
    run.add_argument("--gun", type=date.fromisoformat, default=None, help="tarihli kuralların günü (YYYY-MM-DD); verilmezse bugün")
    args = parser.parse_args(argv)
    from app.api.db import get_engine
    engine = get_engine()
    with Session(engine) as session:
        job_id = enqueue(session, None, TRIGGER_DEV, day=args.gun)
    print(f"Veri kalitesi işi kuyrukta: #{job_id} · veritabanı {engine.url.database}" + (f" · gün {args.gun.isoformat()}" if args.gun else ""))
    print("İşi motor servisi çalıştırır (python -m app.engine.service).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
