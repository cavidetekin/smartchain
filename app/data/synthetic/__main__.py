"""Sentetik veri v0 komutları (docs/11, K-79).

  python -m app.data.synthetic load   [--date 2026-10-27] [--seed 22]   temiz hâli ana tablolara yükler (öncekini siler)
  python -m app.data.synthetic unload                                    sentetik veriyi siler
  python -m app.data.synthetic excel  [--out data/synthetic/v0/kirli]    kirli hâl: entegrasyon Excel'i + beklenen hatalar
  python -m app.data.synthetic sql    [--database SmartchainIntegration] kirli hâl: entegrasyon veritabanına ham tablolar, view'lar, ERP_LoadLog (K-130)
  python -m app.data.synthetic check                                     sayılar ve bilerek konmuş durumlar
  python -m app.data.synthetic users                                     kullanıcılar: geçici şifreler (docs/11, 2.1)
"""
import argparse
import sys
from datetime import date
from pathlib import Path

from sqlalchemy import text

from .dataset import SEED, generate
from .situations import all_checks, summary

ROOT = Path(__file__).resolve().parents[3]


def _print_check(ds) -> bool:
    for k, v in summary(ds).items():
        print(f"  {k}: {v}")
    ok = True
    for c in all_checks(ds):
        ok &= c.ok
        print(f"  {'VAR ' if c.ok else 'YOK '} {c.no}. {c.name}: {c.detail}")
    return ok


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m app.data.synthetic", description="Sentetik veri seti v0 (docs/11)")
    p.add_argument("command", choices=["load", "unload", "excel", "sql", "check", "users"])
    p.add_argument("--date", type=date.fromisoformat, default=None, help="üretim günü (varsayılan bugün)")
    p.add_argument("--seed", type=int, default=SEED)
    p.add_argument("--out", type=Path, default=ROOT / "data" / "synthetic" / "v0" / "kirli")
    p.add_argument("--database", default=None, help="sql: entegrasyon veritabanı")
    a = p.parse_args(argv)
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

    if a.command == "users":
        from app.api.db import get_engine
        from .users import reset_users, write_file
        users = reset_users(get_engine())
        path = ROOT / ".local" / "gecici-sifreler.txt"
        write_file(path, users)
        print("Sentetik kullanıcılar geçici şifreye döndü; ilk girişte şifre değiştirilecek.")
        for name, role, password in users:
            print(f"  {name:<10} {role:<14} {password}")
        print(f"Şifreler ayrıca: {path} (git dışı; yalnız geliştirme)")
        return 0

    ds = generate(a.date, a.seed) if a.command != "unload" else None
    if a.command == "check":
        print(f"Sentetik v0 · tohum {ds.seed} · üretim günü {ds.generated_on:%d.%m.%Y}")
        return 0 if _print_check(ds) else 1
    if a.command == "excel":
        from .excel import write_excel
        m = write_excel(ds, a.out)
        print(f"Kirli hâl: {a.out} · {len(m['files'])} dosya, {sum(m['files'].values())} satır, "
              f"{len(m['errors'])} kasıtlı hata (beklenen-hatalar.json)")
        return 0

    from app.api.db import get_engine
    if a.command == "sql":
        from .sql import DATABASE, SyntheticSqlLock, configure_demo, write_sql
        engine = get_engine()
        with engine.connect() as c:
            collation = c.execute(text("SELECT CONVERT(nvarchar(128), DATABASEPROPERTYEX(DB_NAME(), 'Collation'))")).scalar()
        try:
            m = write_sql(ds, engine.url, a.database or DATABASE, collation)
        except SyntheticSqlLock as exc:
            print(f"DURDU: {exc}", file=sys.stderr)
            return 2
        configure_demo(engine)
        print(f"SQL kaynağı: {m['database']} · {len(m['tables'])} tablo, {sum(m['tables'].values())} satır, {len(m['errors'])} kasıtlı hata")
        print("Demo: Ürün ağacı, Rota, Stok, Satış siparişi, İş emri SQL ve view'lı; Malzeme ekranda seçilir.")
        return 0
    from .load import SyntheticLockError, load, unload
    try:
        if a.command == "unload":
            removed = unload(get_engine())
            print(f"Sentetik veri silindi (veri versiyonları: {removed or 'yok'})")
            return 0
        r = load(get_engine(), ds)
    except SyntheticLockError as exc:
        print(f"DURDU: {exc}", file=sys.stderr)
        return 2
    print(f"Sentetik v0 yüklendi: veri versiyonu {r['data_version_id']}, lokasyon {r['location_id']}, "
          f"parametre seti {r['parameter_set_id']}; {sum(r['counts'].values())} satır"
          + (f"; silinen eski versiyonlar {r['removed_versions']}" if r["removed_versions"] else ""))
    _print_check(ds)
    return 0


if __name__ == "__main__":
    sys.exit(main())
