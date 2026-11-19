"""Deneme hesabı (7.8, K-184): kaynak × gün kapasite, bugün var olan geçici veriden. 7.9'da gerçek kapasite hesabıyla değişir.

Kural: çalışma günü kaynağın takviminden (`core.CalendarDay`: çalışılıyorsa oranı, çalışılmıyorsa 0); takvimde olmayan günde Pazartesi–Cuma
çalışılır. Toplam kapasite = çalışma günü × günlük kapasite. Kullanılabilir kapasite = toplam × verim; verim senaryonun o günü kapsayan
`param.ResourceEfficiency` satırından, yoksa (Baz'ı izliyorsa) Baz'ın satırından, o da yoksa %100.
"""
from datetime import date

import sqlalchemy as sa
from sqlalchemy.orm import Session

from db.models import metadata

from . import cache as cache_
from .cache import DayCache, Scope

_EFFICIENCY = ("OUTER APPLY (SELECT TOP 1 e.EfficiencyPct FROM param.ResourceEfficiency e WHERE e.ScenarioDefinitionId = {scenario} "
               "AND e.ResourceId = r.Id AND d.[Date] BETWEEN e.ValidFrom AND e.ValidTo ORDER BY e.ValidFrom DESC, e.Id DESC) {alias}")


def _select(own_only: bool) -> str:
    return (
        "SELECT :sid, r.Id, d.[Date], w.wd, w.wd * COALESCE(r.DailyCapacity, 0), "
        "w.wd * COALESCE(r.DailyCapacity, 0) * COALESCE(own.EfficiencyPct, bas.EfficiencyPct, 100) / 100 "
        "FROM core.Resource r "
        "CROSS JOIN (SELECT DATEADD(day, n.i, CAST(:dfrom AS date)) AS [Date] FROM (SELECT TOP (DATEDIFF(day, CAST(:dfrom AS date), CAST(:dto AS date)) + 1) "
        "ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) - 1 AS i FROM sys.all_objects a CROSS JOIN sys.all_objects b) n) d "
        "LEFT JOIN core.CalendarDay cd ON cd.CalendarId = r.CalendarId AND cd.[Date] = d.[Date] AND cd.VersionTo IS NULL "
        "CROSS APPLY (SELECT CAST(CASE WHEN cd.CalendarId IS NOT NULL THEN CASE WHEN cd.IsWorkingDay = 1 THEN COALESCE(cd.WorkingFraction, 1) ELSE 0 END "
        "WHEN DATEDIFF(day, CAST('19000101' AS date), d.[Date]) % 7 < 5 THEN 1 ELSE 0 END AS decimal(5,2)) AS wd) w "
        + _EFFICIENCY.format(scenario=":sid", alias="own") + " " + _EFFICIENCY.format(scenario=":base", alias="bas") + " "
        "WHERE r.VersionTo IS NULL AND (:ids IS NULL OR r.Id IN (SELECT CAST(value AS bigint) FROM OPENJSON(:ids)))"
        + (" AND own.EfficiencyPct IS NOT NULL" if own_only else ""))


CACHE = DayCache(name="resource-capacity-day", table=metadata.tables["cache.ResourceCapacityDay"], master="ResourceId",
                 values=("WorkingDay", "Capacity", "AvailableCapacity"), code_version=1, select=_select)


def values(session: Session, scenario_id: int, date_from: date, date_to: date, masters: tuple[int, ...] | None = None) -> list[dict]:
    """Aynı hesabın doğrudan sonucu (önbellekten okumadan): motorun kullandığı yol. Senaryonun geçerli değerleri (Baz'dan okunanlar dahil)."""
    scenario = cache_.scenario_row(session, scenario_id)
    scope = Scope(scenario_id, cache_.base_of(session, scenario), date_from, date_to, masters)
    rows = session.execute(sa.text(_select(False)), scope.params())
    return [{"ResourceId": r[1], "Date": r[2], "WorkingDay": r[3], "Capacity": r[4], "AvailableCapacity": r[5]} for r in rows]


def cached(session: Session, scenario_id: int, date_from: date, date_to: date) -> list[dict]:
    """Önbellekteki geçerli günlük satırlar (senaryonun satırı varsa o, yoksa Baz'ınki); testte `values` ile karşılaştırılır."""
    scenario = cache_.scenario_row(session, scenario_id)
    sql = f"SELECT * FROM ({cache_.effective_sql(CACHE)}) e WHERE e.[Date] BETWEEN :dfrom AND :dto"
    rows = session.execute(sa.text(sql), {"sid": scenario_id, "base": cache_.base_of(session, scenario), "dfrom": date_from, "dto": date_to}).mappings()
    return [dict(r) for r in rows]
