"""Model kısıtları yönetim komutu (K-189).

  python -m app.modelconstraints normalize    veriyi "senaryo + grup başına tek satır" kuralına getirir; geçerli değerler değişmez

Baz'ı izleyen senaryoda bir grubun hem senaryonun kendi satırı hem Baz satırı varsa kendi satırı fark satırına çevrilir; Baz satırı silinmiş
fark satırı senaryonun kendi satırına döner. Ekran bu durumları okurken de birleştirir; komut veriyi düzeltir. Kaç grubun düzeltildiğini yazar.
"""
import sys

from sqlalchemy.orm import Session

from app.api.db import get_engine

from . import normalize


def main(argv: list[str]) -> int:
    if argv != ["normalize"]:
        print(__doc__)
        return 2
    engine = get_engine()
    with Session(engine) as session:
        fixed = normalize(session)
        session.commit()
    print(f"{engine.url.database}: {fixed} grup düzeltildi.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
