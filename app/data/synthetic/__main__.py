"""Sentetik veri v0 komutları (docs/11, K-79).

  python -m app.data.synthetic load   [--date 2026-10-27] [--seed 22]   temiz hâli ana tablolara yükler (öncekini siler)
  python -m app.data.synthetic unload                                    sentetik veriyi siler
  python -m app.data.synthetic excel  [--out data/synthetic/v0/kirli]    kirli hâl: entegrasyon Excel'i + beklenen hatalar
  python -m app.data.synthetic check                                     sayılar ve bilerek konmuş durumlar
"""
import argparse
import sys
from datetime import date
from pathlib import Path

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
    p.add_argument("command", choices=["load", "unload", "excel", "check"])
    p.add_argument("--date", type=date.fromisoformat, default=None, help="üretim günü (varsayılan bugün)")
    p.add_argument("--seed", type=int, default=SEED)
    p.add_argument("--out", type=Path, default=ROOT / "data" / "synthetic" / "v0" / "kirli")
    a = p.parse_args(argv)
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

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
