"""Kapasite hesabı (K-185 C, D): kaynak grubu × kaynak × gün. Tek hesap: önbellek bununla kurulur, motor doğrudan okur.

Geçerlilik (çalışma düzeni, verimlilik, ek mesai limiti): bir gün için önce seviye (kaynakta o günü kapsayan kayıt varsa kaynağın kayıtları,
yoksa grubunkiler), sonra o seviyede o günü kapsayanlardan başlangıcı en ileri olan. Grup kaydı o grubun içinde uygulanır: birden fazla gruba
üye kaynak her grupta o grubun değeriyle hesaplanır.
Duruş: fabrika takvimi (Çalışılmıyor 1, Yarım gün 0,5), bakım ve duruş (1), çalışan izni (günlük saat doluysa saat ÷ günlük kapasite, en çok 1;
boşsa 1) birleşir: en büyüğü alınır, günün çalışma değerini aşamaz (aynı gün bir kez sayılır; çalışılmayan günde 0).

Hız: senaryonun çözümlenmiş girişleri, üyelikler ve günler önce oturumun geçici tablolarına alınır (`prepare`); geçerli kayıt üyelik × gün
başına küme tabanlı bulunur (birleştirme ve sıra numarası), asıl sorgu bu tabloların anahtar üzerinden birleşimidir. Geçici tablolar yalnız
o bağlantıda yaşar.
"""
import json
from datetime import date

import sqlalchemy as sa
from sqlalchemy.orm import Session

from db.models import metadata

from app import periods
from app.params import resolve
from app.periods import cache as cache_
from app.periods.cache import DayCache, Scope

INPUTS = (("#cap_wp", "WorkPattern", ("DailyCapacity", *resolve.DAYS)), ("#cap_ef", "ResourceEfficiency", ("EfficiencyPct",)),
          ("#cap_ol", "OvertimeLimit", ("DailyLimit",)))
EFFECTIVE = {"#cap_wp": "#eff_wp", "#cap_ef": "#eff_ef", "#cap_ol": "#eff_ol"}
# Geçerlilik kuralının sıralaması (K-185 C), tek yerde: önce seviye (0 kaynak, 1 grup), sonra başlangıcı en ileri olan, eşitlikte son girilen.
# Günlük hesap ve geçerlilik aralıkları (`validity.py`) aynı sıralamayı kullanır.
RULE_ORDER = "{a}.lvl, {a}.ValidFrom DESC, {a}.RowId DESC"
TEMPS = ("#cap_m", "#cap_d", "#cap_wp", "#cap_ef", "#cap_ol", "#cap_dt", "#cap_fc", "#cap_ab", "#eff_wp", "#eff_ef", "#eff_ol", "#eff_mt", "#eff_lv")


def members_sql() -> str:
    """Güncel üyelikler (kaynak grubu, kaynak); kaynağı ve grubu güncel veride olanlar."""
    return ("SELECT DISTINCT mm.ResourceGroupId, mm.ResourceId FROM core.ResourceGroupMember mm "
            "JOIN core.Resource r ON r.Id = mm.ResourceId AND r.VersionTo IS NULL "
            "JOIN core.ResourceGroup g ON g.Id = mm.ResourceGroupId AND g.VersionTo IS NULL WHERE mm.VersionTo IS NULL")


def _literal(value) -> str:
    """Geçici tabloyu kuran deyimler parametresiz çalışır (parametreli deyimde geçici tablo deyimle birlikte düşer); değerler burada yazılır:
    yalnız tam sayı, tarih ve tam sayı listesi."""
    if value is None:
        return "NULL"
    if isinstance(value, date):
        return f"CAST('{value:%Y%m%d}' AS date)"
    return str(int(value))


def effective_sql(source: str, fields: tuple[str, ...]) -> str:
    """Geçerlilik kuralı (K-185 C), tek yerde: her üyelik ve gün için geçerli kayıt. Önce seviye (kaynağın kaydı grubunkinden önce), sonra o
    seviyede o günü kapsayanlardan başlangıcı en ileri olan (eşitlikte son girilen). Küme tabanlı: kayıtlar üyeliklere ve kapsadıkları günlere
    birleştirilir, üyelik × gün başına ilk sıradaki alınır. Geçerlilik tablosu da (7.9c) bu sonucu aralıklara çevirir."""
    names = ", ".join(f"w.[{f}]" for f in fields)
    days = "JOIN #cap_d d ON d.[Date] >= w.ValidFrom AND (w.ValidTo IS NULL OR d.[Date] <= w.ValidTo)"
    own = f"SELECT m.ResourceGroupId, m.ResourceId, d.[Date], 0 AS lvl, w.ValidFrom, w.RowId, {names} FROM {source} w JOIN #cap_m m ON m.ResourceId = w.ResourceId {days}"
    group = (f"SELECT m.ResourceGroupId, m.ResourceId, d.[Date], 1 AS lvl, w.ValidFrom, w.RowId, {names} FROM {source} w "
             f"JOIN #cap_m m ON m.ResourceGroupId = w.ResourceGroupId {days}")
    picked = ", ".join(f"q.[{f}]" for f in fields)
    return (f"SELECT q.ResourceGroupId, q.ResourceId, q.[Date], q.RowId, {picked} FROM (SELECT u.*, ROW_NUMBER() OVER (PARTITION BY u.ResourceGroupId, u.ResourceId, u.[Date] "
            f"ORDER BY {RULE_ORDER.format(a='u')}) AS rn FROM ({own} UNION ALL {group}) u) q WHERE q.rn = 1")


def prepare(session: Session, scope: Scope) -> None:
    """Hesabın girdileri oturumun geçici tablolarına: üyelikler (istenen kaynaklarla süzülmüş), günler (haftanın günü ve fabrika takvimi kaybıyla),
    senaryonun çözümlenmiş girişleri (K-176: Baz + fark), çalışan izinleri; sonra üyelik × gün başına geçerli kayıtlar ve duruşlar."""
    sid, base = _literal(scope.scenario_id), _literal(scope.base_id)
    a, b = _literal(scope.date_from), _literal(scope.date_to)

    def resolved(table: str) -> str:
        return resolve.sql(table, sid=sid, base=base)

    drops = [f"IF OBJECT_ID('tempdb..{name}') IS NOT NULL DROP TABLE {name}" for name in TEMPS]
    only = "" if scope.masters is None else f" WHERE x.ResourceId IN (SELECT CAST(value AS bigint) FROM OPENJSON(N'{json.dumps([int(i) for i in scope.masters])}'))"
    key = "(ResourceId, ResourceGroupId, [Date])"
    run = [
        f"SELECT x.ResourceGroupId, x.ResourceId INTO #cap_m FROM ({members_sql()}) x{only}",
        "CREATE UNIQUE CLUSTERED INDEX ix ON #cap_m (ResourceId, ResourceGroupId)",
        f"SELECT ResourceGroupId, ResourceId, StartDate, EndDate INTO #cap_dt FROM ({resolved('ResourceDowntime')}) x WHERE x.EndDate >= {a} AND x.StartDate <= {b}",
        f"SELECT StartDate, EndDate, DayValue INTO #cap_fc FROM ({resolved('FactoryCalendar')}) x WHERE x.EndDate >= {a} AND x.StartDate <= {b}",
        f"SELECT ab.ResourceId, ab.StartDate, ab.EndDate, ab.HoursPerDay INTO #cap_ab FROM core.EmployeeAbsence ab WHERE ab.VersionTo IS NULL "
        f"AND ab.EndDate >= {a} AND ab.StartDate <= {b}",
        # günler: haftanın günü (0 Pazartesi … 6 Pazar; DATEFIRST'ten bağımsız) ve fabrika takviminin o günkü kaybı (Çalışılmıyor 1, Yarım gün 0,5)
        f"SELECT q.[Date], DATEDIFF(day, CAST('19000101' AS date), q.[Date]) % 7 AS wd, "
        "CAST(COALESCE((SELECT MAX(1 - f.DayValue) FROM #cap_fc f WHERE q.[Date] BETWEEN f.StartDate AND f.EndDate), 0) AS decimal(18,8)) AS factory "
        f"INTO #cap_d FROM (SELECT DATEADD(day, n.i, {a}) AS [Date] FROM (SELECT TOP (DATEDIFF(day, {a}, {b}) + 1) "
        "ROW_NUMBER() OVER (ORDER BY (SELECT NULL)) - 1 AS i FROM sys.all_objects o1 CROSS JOIN sys.all_objects o2) n) q",
        "CREATE UNIQUE CLUSTERED INDEX ix ON #cap_d ([Date])",
    ]
    for temp, table, fields in INPUTS:
        names = ", ".join(fields)
        run += [f"SELECT RowId, ResourceGroupId, ResourceId, ValidFrom, ValidTo, {names} INTO {temp} FROM ({resolved(table)}) x "
                f"WHERE x.ValidFrom <= {b} AND (x.ValidTo IS NULL OR x.ValidTo >= {a})",
                f"SELECT e.* INTO {EFFECTIVE[temp]} FROM ({effective_sql(temp, fields)}) e",
                f"CREATE UNIQUE CLUSTERED INDEX ix ON {EFFECTIVE[temp]} {key}"]
    run += [
        # bakım ve duruş: kaynağa ya da grubuna girilmiş kayıtların kapsadığı üyelik × günler (birleşir: gün bir kez)
        "SELECT DISTINCT m.ResourceGroupId, m.ResourceId, d.[Date] INTO #eff_mt FROM #cap_dt t "
        "JOIN #cap_m m ON m.ResourceId = t.ResourceId OR m.ResourceGroupId = t.ResourceGroupId JOIN #cap_d d ON d.[Date] BETWEEN t.StartDate AND t.EndDate",
        f"CREATE UNIQUE CLUSTERED INDEX ix ON #eff_mt {key}",
        # çalışan izni (ERP): kaynak × gün; günlük saati boş kayıt tam gündür
        "SELECT ab.ResourceId, d.[Date], MAX(CASE WHEN ab.HoursPerDay IS NULL THEN 1 ELSE 0 END) AS full_day, MAX(ab.HoursPerDay) AS hours INTO #eff_lv "
        "FROM #cap_ab ab JOIN #cap_d d ON d.[Date] BETWEEN ab.StartDate AND ab.EndDate GROUP BY ab.ResourceId, d.[Date]",
        "CREATE UNIQUE CLUSTERED INDEX ix ON #eff_lv (ResourceId, [Date])",
    ]
    # tek seferde gönderilir (sunucuya gidiş geliş sayısı hazırlığın sabit yüküdür); SET NOCOUNT: ara satır sayıları istemciye dönmez
    session.execute(sa.text("SET NOCOUNT ON; " + "; ".join([*drops, *run]) + "; SET NOCOUNT OFF;"))


def _select() -> str:
    on = "{t}.ResourceId = m.ResourceId AND {t}.ResourceGroupId = m.ResourceGroupId AND {t}.[Date] = d.[Date]"
    day_value = "CASE d.wd " + " ".join(f"WHEN {i} THEN wp.[{name}]" for i, name in enumerate(resolve.DAYS)) + " END"
    return (
        "SELECT :sid AS ScenarioDefinitionId, m.ResourceId, m.ResourceGroupId, d.[Date], "
        "CAST(x.wd AS decimal(2,1)) AS WorkingDay, CAST(x.dt AS decimal(5,4)) AS Downtime, CAST(x.cap AS decimal(18,4)) AS DailyCapacity, "
        "CAST(x.wd * x.cap * x.eff AS decimal(18,4)) AS Capacity, CAST((x.wd - x.dt) * x.cap * x.eff AS decimal(18,4)) AS AvailableCapacity, "
        "CAST((x.wd - x.dt) * x.ol AS decimal(18,4)) AS OvertimeLimit "
        "FROM #cap_m m CROSS JOIN #cap_d d "
        f"LEFT JOIN #eff_wp wp ON {on.format(t='wp')} LEFT JOIN #eff_ef ef ON {on.format(t='ef')} LEFT JOIN #eff_ol ol ON {on.format(t='ol')} "
        f"LEFT JOIN #eff_mt mt ON {on.format(t='mt')} LEFT JOIN #eff_lv lv ON lv.ResourceId = m.ResourceId AND lv.[Date] = d.[Date] "
        f"CROSS APPLY (SELECT CAST(COALESCE({day_value}, 0) AS decimal(18,8)) AS wd, CAST(COALESCE(wp.DailyCapacity, 0) AS decimal(18,4)) AS cap) a "
        "CROSS APPLY (SELECT CAST(CASE WHEN mt.ResourceId IS NULL THEN 0 ELSE 1 END AS decimal(18,8)) AS maintenance, "
        "CAST(CASE WHEN lv.ResourceId IS NULL THEN 0 WHEN lv.full_day = 1 OR a.cap <= 0 OR lv.hours >= a.cap THEN 1 ELSE lv.hours / a.cap END AS decimal(18,8)) AS leave) l "
        # duruşlar birleşir: en büyüğü; günün çalışma değerini aşamaz
        "CROSS APPLY (SELECT CASE WHEN d.factory >= l.maintenance AND d.factory >= l.leave THEN d.factory WHEN l.maintenance >= l.leave THEN l.maintenance "
        "ELSE l.leave END AS loss) s "
        "CROSS APPLY (SELECT a.wd, a.cap, CAST(COALESCE(ef.EfficiencyPct, 100) AS decimal(18,8)) / 100 AS eff, "
        "CAST(COALESCE(ol.DailyLimit, 0) AS decimal(18,4)) AS ol, CASE WHEN s.loss > a.wd THEN a.wd ELSE s.loss END AS dt) x")


CACHE = DayCache(name="resource-capacity-day", table=metadata.tables["cache.ResourceCapacityDay"], keys=("ResourceId", "ResourceGroupId"), master="ResourceId",
                 values=("WorkingDay", "Downtime", "DailyCapacity", "Capacity", "AvailableCapacity", "OvertimeLimit"), code_version=2, select=_select,
                 prepare=prepare, has_own=lambda session, scenario_id: resolve.has_own(session, scenario_id))


def values(session: Session, scenario_id: int, date_from: date, date_to: date, masters: tuple[int, ...] | None = None) -> list[dict]:
    """Hesabın doğrudan sonucu (önbellekten okumadan): motorun yolu. Senaryonun geçerli değerleri (Baz'dan okunanlar dahil)."""
    scenario = cache_.scenario_row(session, scenario_id)
    scope = Scope(scenario_id, cache_.base_of(session, scenario), date_from, date_to, masters)
    prepare(session, scope)
    return [dict(r) for r in session.execute(sa.text(_select()), {"sid": scenario_id}).mappings()]


def cached(session: Session, scenario_id: int, date_from: date, date_to: date) -> list[dict]:
    """Önbellekteki geçerli günlük satırlar (senaryonun satırı varsa o, yoksa Baz'ınki); testte `values` ile karşılaştırılır."""
    scenario = cache_.scenario_row(session, scenario_id)
    sql = f"SELECT * FROM ({cache_.effective_sql(CACHE)}) e WHERE e.[Date] BETWEEN :dfrom AND :dto"
    rows = session.execute(sa.text(sql), {"sid": scenario_id, "base": cache_.base_of(session, scenario), "dfrom": date_from, "dto": date_to}).mappings()
    return [dict(r) for r in rows]


periods.register(CACHE, values)
