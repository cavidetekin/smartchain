"""Kapasite önbelleğinin tetikleyicileri (K-184, K-185 F): giriş değişince yalnız etkilenen kaynak ve günler yenilenir.

Her işlev, değişikliği kaydeden işlemle aynı veritabanı işleminde çağrılır (commit çağıranındır). Baz'da yapılan değişiklik Baz'ı izleyen
senaryolarda aynı kaynak ve günleri de yeniler (`cache.invalidate`). Yeni senaryo ve Baz'dan ayırma ayrıca bağlıdır: senaryonun önbelleği
düşer, ilk kullanımda baştan kurulur (`app/params/scenarios.py`).

Çağıranlar: giriş ekranlarının kayıt işlemleri (7.9b) ve aktarım (7.9c). 7.9a'da işlevler hazırdır ve testlidir.
"""
from datetime import date
from typing import Iterable

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.periods import cache

from .compute import CACHE

Range = tuple[date | None, date | None]   # başlangıç, bitiş; bitiş boşsa süresiz (önbelleğin sonuna kadar)
SCENARIO = cache.SCENARIO


def group_members(session: Session, group_id: int) -> list[int]:
    """Grubun güncel kaynakları."""
    return [r[0] for r in session.execute(sa.text("SELECT DISTINCT ResourceId FROM core.ResourceGroupMember WHERE ResourceGroupId = :g AND VersionTo IS NULL"),
                                          {"g": group_id})]


def _span(ranges: Iterable[Range]) -> Range:
    """Kaydın eski ve yeni aralığını kapsayan tek aralık (başlangıcın en küçüğü, bitişin en büyüğü; biri süresizse süresiz)."""
    found = [r for r in ranges if r is not None]
    starts = [a for a, _ in found if a is not None]
    ends = [b for _, b in found]
    return (min(starts) if starts and len(starts) == len(found) else None, None if any(b is None for b in ends) or not ends else max(ends))


def entry_changed(session: Session, scenario_id: int, *, resource_id: int | None = None, group_id: int | None = None,
                  ranges: Iterable[Range] = ()) -> dict[int, int]:
    """Giriş kaydı (çalışma düzeni, verimlilik, ek mesai limiti, bakım ve duruş) eklendi, değişti, silindi ya da geçersiz yapıldı. Kaynağa
    girildiyse o kaynak, gruba girildiyse grubun kaynakları; `ranges`: kaydın eski ve yeni tarih aralığı (ekleme ve silmede tek aralık)."""
    resources = [resource_id] if resource_id is not None else group_members(session, group_id) if group_id is not None else []
    start, end = _span(ranges)
    return cache.invalidate(session, CACHE, scenario_id, resources, start, end)


def factory_calendar_changed(session: Session, scenario_id: int, ranges: Iterable[Range]) -> dict[int, int]:
    """Fabrika takvimi değişti: bütün kaynaklar, o günler (kaydın eski ve yeni aralığı)."""
    start, end = _span(ranges)
    return cache.invalidate(session, CACHE, scenario_id, None, start, end)


def transfer_changed(session: Session, resource_ids: Iterable[int], ranges: Iterable[Range] = ((None, None),)) -> dict[int, int]:
    """Aktarım, ERP'den gelen ve hesaba giren veriyi değiştirdi (grup eşleşmesi, çalışan izni): o kaynaklar, o günler (eşleşmede bütün günler).
    Veri senaryodan bağımsız olduğu için bütün senaryolarda: Baz (izleyenleri de yeniler) ve Baz'ı izlemeyen senaryolar. Kalan fazla mesai günlük
    hesaba girmez (dönem tablosu ERP alanını doğrudan okur): yenileme gerekmez."""
    ids = list(dict.fromkeys(int(i) for i in resource_ids))
    start, end = _span(ranges)
    out: dict[int, int] = {}
    own = sa.or_(SCENARIO.c.IsBase == sa.true(), sa.func.coalesce(SCENARIO.c.FollowsBase, sa.false()) == sa.false())
    for (sid,) in session.execute(sa.select(SCENARIO.c.Id).where(own).order_by(SCENARIO.c.IsBase.desc(), SCENARIO.c.Id)).all():
        out.update(cache.invalidate(session, CACHE, sid, ids, start, end))
    return out
