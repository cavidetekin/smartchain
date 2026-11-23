"""Kapasite önbelleğinin tetikleyicileri (K-184, K-185 F): giriş değişince yalnız etkilenen kaynak ve günler yenilenir.

Her işlev, değişikliği kaydeden işlemle aynı veritabanı işleminde çağrılır (commit çağıranındır). Baz'da yapılan değişiklik Baz'ı izleyen
senaryolarda aynı kaynak ve günleri de yeniler (`cache.invalidate`). Yeni senaryo ve Baz'dan ayırma ayrıca bağlıdır: senaryonun önbelleği
düşer, ilk kullanımda baştan kurulur (`app/params/scenarios.py`).

Çağıranlar: giriş ekranlarının kayıt işlemleri (7.9b) ve aktarım (7.9c: `after_transfer`, aktarımın işleminde).
"""
from datetime import date
from typing import Iterable

import logging

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.periods import cache

from .compute import CACHE

log = logging.getLogger("smartchain.capacity")
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


def location_resources(session: Session, location_id: int) -> list[int]:
    """Lokasyonun güncel kaynakları."""
    return [r[0] for r in session.execute(sa.text("SELECT Id FROM core.Resource WHERE LocationId = :l AND VersionTo IS NULL"), {"l": location_id})]


def factory_calendar_changed(session: Session, scenario_id: int, location_id: int | None, ranges: Iterable[Range]) -> dict[int, int]:
    """Fabrika takvimi değişti: kaydın lokasyonundaki kaynaklar (K-194), o günler (kaydın eski ve yeni aralığı). Lokasyon verilmezse bütün kaynaklar."""
    start, end = _span(ranges)
    resources = None if location_id is None else location_resources(session, location_id)
    return cache.invalidate(session, CACHE, scenario_id, resources, start, end)


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


def _changed_ids(session: Session, table: str, column: str, version: int) -> set[int]:
    """Bu aktarımda yeni versiyonu yazılan ya da kapatılan satırların `column` değerleri (aktarım: kapatma `VersionTo` = versiyon − 1, ekleme
    `VersionFrom` = versiyon)."""
    return {int(r[0]) for r in session.execute(sa.text(f"SELECT DISTINCT [{column}] FROM core.[{table}] WHERE (VersionFrom = :v OR VersionTo = :v - 1) AND [{column}] IS NOT NULL"),
                                               {"v": version})}


def _appeared_or_closed(session: Session, table: str, version: int) -> set[int]:
    """Bu aktarımda güncel veriye giren ya da güncel veriden çıkan kayıtlar (değişip yeni versiyonu yazılan kayıt sayılmaz: hâlâ günceldir)."""
    return {int(r[0]) for r in session.execute(sa.text(
        f"SELECT t.Id FROM core.[{table}] t WHERE t.VersionFrom = :v AND NOT EXISTS (SELECT 1 FROM core.[{table}] p WHERE p.Id = t.Id AND p.VersionTo = :v - 1) "
        f"UNION SELECT t.Id FROM core.[{table}] t WHERE t.VersionTo = :v - 1 AND NOT EXISTS (SELECT 1 FROM core.[{table}] n WHERE n.Id = t.Id AND n.VersionFrom = :v)"),
        {"v": version})}


def after_transfer(session: Session, version: int) -> dict:
    """Aktarımın sonunda, aktarımın işleminde (K-188): hesaba giren ERP verisi değişen kaynaklar yenilenir, güncel önbellekler yeni veri versiyonuna
    çekilir (tam kurulum yok). Eşleşmesi değişen, kendisi ya da grubu güncel veriye giren ya da çıkan kaynaklar bütün günlerde; çalışan izni değişen
    kaynaklar iznin eski ve yeni aralığında. Kalan fazla mesai hesaba girmez. Önbellek aktarımdan önce bayatsa dokunulmaz: ilk kullanımda baştan kurulur."""
    state = cache.STATE
    previous = session.execute(sa.text("SELECT MAX(Id) FROM adm.DataVersion WHERE Id < :v"), {"v": version}).scalar()
    fresh = [int(r[0]) for r in session.execute(sa.select(state.c.ScenarioDefinitionId).where(
        state.c.CacheName == CACHE.name, state.c.CodeVersion == CACHE.code_version, state.c.DataVersionId == previous))]
    if not fresh:
        return {"scenarios": 0, "resources": 0, "leave": 0}
    members = _changed_ids(session, "ResourceGroupMember", "ResourceId", version) | _appeared_or_closed(session, "Resource", version)
    groups = _appeared_or_closed(session, "ResourceGroup", version)
    if groups:
        members |= {int(r[0]) for r in session.execute(sa.text(
            "SELECT DISTINCT ResourceId FROM core.ResourceGroupMember WHERE ResourceGroupId IN (SELECT CAST(value AS bigint) FROM OPENJSON(:g)) "
            "AND (VersionTo IS NULL OR VersionTo = :v - 1)"), {"g": "[" + ",".join(str(g) for g in sorted(groups)) + "]", "v": version})}
    leave: dict[int, list[Range]] = {}
    for r in session.execute(sa.text("SELECT ResourceId, StartDate, EndDate FROM core.EmployeeAbsence WHERE (VersionFrom = :v OR VersionTo = :v - 1) "
                                     "AND ResourceId IS NOT NULL"), {"v": version}):
        if int(r[0]) not in members:
            leave.setdefault(int(r[0]), []).append((r[1], r[2]))
    if members:
        transfer_changed(session, sorted(members))
    if leave:
        transfer_changed(session, sorted(leave), [span for spans in leave.values() for span in spans])
    session.execute(sa.update(state).where(state.c.CacheName == CACHE.name, state.c.ScenarioDefinitionId.in_(fresh)).values(DataVersionId=version))
    log.info("Kapasite önbelleği aktarımla yenilendi: veri versiyonu %s, %s senaryo, %s kaynak (bütün günler), %s kaynak (izin aralığı)",
             version, len(fresh), len(members), len(leave))
    return {"scenarios": len(fresh), "resources": len(members), "leave": len(leave)}
