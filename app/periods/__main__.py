"""Dönem tablosu önbelleği yönetim komutları (K-184). Önbellek veri değildir; düşürmek ya da yeniden kurmak hiçbir girişi değiştirmez.

  python -m app.periods status                      önbellek, senaryo, gün aralığı ve satır sayısı
  python -m app.periods rebuild [--scenario <id>]   önbelleği düşürüp girişlerden yeniden kurar (senaryo verilmezse aktif senaryoların hepsi)
  python -m app.periods drop    [--scenario <id>]   önbelleği boşaltır; ilk kullanımda yeniden kurulur
"""
import argparse
import sys
import time
from datetime import date

import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from . import CACHES, cache, periods


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.periods", description="Dönem tablosu önbelleği (K-184)")
    parser.add_argument("command", choices=("status", "rebuild", "drop"))
    parser.add_argument("--scenario", type=int, default=None)
    args = parser.parse_args(argv)
    from app.api.db import get_engine
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    with sessionmaker(bind=get_engine())() as session:
        active = sa.func.coalesce(cache.SCENARIO.c.IsActive, sa.true()) == sa.true()
        scenarios = [args.scenario] if args.scenario is not None else [
            r[0] for r in session.execute(sa.select(cache.SCENARIO.c.Id).where(active).order_by(cache.SCENARIO.c.Id))]
        for c in CACHES.values():
            if args.command in ("drop", "rebuild"):
                rows = cache.drop(session, c, args.scenario)
                session.commit()
                print(f"{c.name}: boşaltıldı ({'senaryo ' + str(args.scenario) if args.scenario is not None else 'hepsi'}; {rows} satır)")
            if args.command == "rebuild":
                for sid in scenarios:
                    found = periods.read(session, sid, date.today())
                    if not found:
                        print(f"{c.name}: senaryo {sid} için planlama ufku tanımlı değil; atlandı")
                        continue
                    t0 = time.perf_counter()
                    cache.ensure(session, c, sid, found[0].start, found[-1].end)
                    print(f"{c.name}: senaryo {sid} kuruldu ({found[0].start:%d.%m.%Y} – {found[-1].end:%d.%m.%Y}; {time.perf_counter() - t0:.1f} sn)")
            state = cache.status(session, c)
            print(f"{c.name}: {len(state)} senaryo" if state else f"{c.name}: boş (ilk kullanımda kurulur)")
            for r in state:
                print(f"  senaryo {r['ScenarioDefinitionId']}: {r['DateFrom']:%d.%m.%Y} – {r['DateTo']:%d.%m.%Y}, {r['Rows']} satır, "
                      f"veri versiyonu {r['DataVersionId']}, hesap sürümü {r['CodeVersion']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
