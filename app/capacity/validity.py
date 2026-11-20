"""Geçerlilik aralıkları (K-185 C, K-188; 7.9c): her kaynak grubu × kaynak için hangi aralıkta hangi kaydın uygulandığı.

Kural hesaptakiyle aynıdır (`compute.effective_sql`, `RULE_ORDER`): bir gün için önce seviye (kaynağın kaydı grubunkinden önce), sonra o seviyede
o günü kapsayanlardan başlangıcı en ileri olan (eşitlikte son girilen). Burada gün gün değil kırılma noktalarıyla uygulanır: kayıtların başlangıcı
ve bitiş + 1 günü; iki kırılma noktası arasında geçerli kayıt değişmez. Her noktada kural uygulanır, aynı kaydın ardışık parçaları birleşir.
Aralıklar kayıtların kendi tarihleriyledir (ufukla kesilmez); son aralığın bitişi kayıt süresizse boştur. Kayıt olmayan aralık satır değildir.
Günlük hesapla tutarlılığı testle sabittir (`tests/test_capacity_validity.py`).
"""
from app.params import resolve

from .compute import RULE_ORDER, members_sql

# giriş → çözümlenen tablo ve değer alanları
KINDS: dict[str, tuple[str, tuple[str, ...]]] = {
    "work-patterns": ("WorkPattern", ("DailyCapacity", *resolve.DAYS)),
    "efficiency": ("ResourceEfficiency", ("EfficiencyPct",)),
    "overtime-limits": ("OvertimeLimit", ("DailyLimit",)),
}


def intervals_sql(table: str, fields: tuple[str, ...], sid: str = ":sid", base: str = ":base") -> str:
    """SELECT metni: ResourceGroupId, ResourceId, RowId (geçerli kayıt), lvl (0 kaynak, 1 grup), RecFrom, RecTo (kaydın kendi aralığı), ValidFrom,
    ValidTo (uygulandığı aralık; süresizse boş), Origin (kaydın kaynağı: Baz · Senaryo farkı · Senaryo) ve değer alanları. Parametreler: senaryo ve
    okuduğu Baz (`resolve.sql`)."""
    fields = (*fields, "Origin")
    names = ", ".join(f"w.[{f}]" for f in fields)
    rec = resolve.sql(table, sid=sid, base=base)
    members = members_sql()
    # kaydın uygulanabildiği üyelikler: kaynağın kaydı kaynağın bütün gruplarında, grubun kaydı grubun bütün kaynaklarında
    app = (f"(SELECT m.ResourceGroupId AS G, m.ResourceId AS R, 0 AS lvl, w.RowId, w.ValidFrom, w.ValidTo, {names} FROM ({rec}) w JOIN ({members}) m ON m.ResourceId = w.ResourceId "
           f"UNION ALL SELECT m.ResourceGroupId, m.ResourceId, 1, w.RowId, w.ValidFrom, w.ValidTo, {names} FROM ({rec}) w JOIN ({members}) m ON m.ResourceGroupId = w.ResourceGroupId)")
    points = f"(SELECT a1.G, a1.R, a1.ValidFrom AS P FROM {app} a1 UNION SELECT a2.G, a2.R, DATEADD(day, 1, a2.ValidTo) FROM {app} a2 WHERE a2.ValidTo IS NOT NULL)"
    picked = ", ".join(f"a.[{f}]" for f in fields)
    # her kırılma noktasında geçerli kayıt (yoksa RowId boş: o aralıkta kayıt yok)
    effective = (f"(SELECT p.G, p.R, p.P, a.RowId, a.lvl, a.ValidFrom AS RecFrom, a.ValidTo AS RecTo, {picked}, "
                 f"ROW_NUMBER() OVER (PARTITION BY p.G, p.R, p.P ORDER BY CASE WHEN a.RowId IS NULL THEN 1 ELSE 0 END, {RULE_ORDER.format(a='a')}) AS rn "
                 f"FROM {points} p LEFT JOIN {app} a ON a.G = p.G AND a.R = p.R AND a.ValidFrom <= p.P AND (a.ValidTo IS NULL OR a.ValidTo >= p.P))")
    window = "PARTITION BY e.G, e.R ORDER BY e.P"
    segments = (f"(SELECT e.*, LEAD(e.P) OVER ({window}) AS NextP, LAG(e.RowId) OVER ({window}) AS PrevRow, ROW_NUMBER() OVER ({window}) AS n "
                f"FROM {effective} e WHERE e.rn = 1)")
    islands = ("(SELECT s.*, SUM(CASE WHEN s.n = 1 OR COALESCE(s.PrevRow, 0) <> COALESCE(s.RowId, 0) THEN 1 ELSE 0 END) "
               f"OVER (PARTITION BY s.G, s.R ORDER BY s.P ROWS UNBOUNDED PRECEDING) AS grp FROM {segments} s)")
    values = ", ".join(f"MAX(i.[{f}]) AS [{f}]" for f in fields)
    return (f"SELECT i.G AS ResourceGroupId, i.R AS ResourceId, i.RowId, i.lvl, MIN(i.RecFrom) AS RecFrom, MIN(i.RecTo) AS RecTo, MIN(i.P) AS ValidFrom, "
            f"CASE WHEN COUNT(i.NextP) < COUNT(*) THEN NULL ELSE DATEADD(day, -1, MAX(i.NextP)) END AS ValidTo, {values} "
            f"FROM {islands} i WHERE i.RowId IS NOT NULL GROUP BY i.G, i.R, i.grp, i.RowId, i.lvl")


def lost_days_sql(rows: str, sid: str = ":sid", base: str = ":base") -> str:
    """Bakım ve duruş kayıtlarının kayıp günü (K-188). SELECT metni: Id, LostDays. `rows`: kayıtları veren SELECT (Id, ResourceId, ResourceGroupId,
    StartDate, EndDate, Hours). Kayıp gün, aralıktaki çalışma günü değerlerinin toplamıdır (çalışma düzeninden; Tam 1, Yarım 0,5). Kaynak kaydında
    kaynağın (birden fazla gruptaysa en büyüğü), grup kaydında grubun kaynaklarının ortalaması. Hours: çalışan izninin günlük saati (doluysa gün, saat ÷
    günlük kapasite oranıyla sayılır; en çok 1). Fabrika takvimi düşülmez. Çalışma düzeni aralıkları bir kez kurulur ve kayıtlara küme olarak birleştirilir
    (satır başına alt sorgu yok: sorgu planı küçük kalır). Haftanın günleri sayılarak bulunur (gün tablosu gerekmez): aralıkta k. günün sayısı =
    (n + 6 − ((k − aralığın ilk gününün haftadaki yeri + 7) % 7)) ÷ 7."""
    table, fields = KINDS["work-patterns"]
    wp = intervals_sql(table, fields, sid, base)
    counted = " + ".join(f"v.[{name}] * ((x.n + 6 - (({k} - x.wd + 7) % 7)) / 7)" for k, name in enumerate(resolve.DAYS))
    share = "CASE WHEN t.Hours IS NULL OR v.DailyCapacity <= 0 OR t.Hours >= v.DailyCapacity THEN 1 ELSE t.Hours / v.DailyCapacity END"
    per_member = (f"SELECT t.Id, CASE WHEN t.ResourceId IS NULL THEN 0 ELSE 1 END AS own, v.ResourceGroupId, v.ResourceId, SUM(({counted}) * x.share) AS d "
                  f"FROM ({rows}) t JOIN ({wp}) v ON (v.ResourceId = t.ResourceId OR (t.ResourceId IS NULL AND v.ResourceGroupId = t.ResourceGroupId)) "
                  "AND v.ValidFrom <= t.EndDate AND (v.ValidTo IS NULL OR v.ValidTo >= t.StartDate) "
                  "CROSS APPLY (SELECT CASE WHEN v.ValidFrom > t.StartDate THEN v.ValidFrom ELSE t.StartDate END AS a, "
                  "CASE WHEN v.ValidTo IS NULL OR v.ValidTo > t.EndDate THEN t.EndDate ELSE v.ValidTo END AS b) r "
                  f"CROSS APPLY (SELECT DATEDIFF(day, r.a, r.b) + 1 AS n, DATEDIFF(day, CAST('19000101' AS date), r.a) % 7 AS wd, {share} AS share) x "
                  "GROUP BY t.Id, CASE WHEN t.ResourceId IS NULL THEN 0 ELSE 1 END, v.ResourceGroupId, v.ResourceId")
    return f"SELECT q.Id, CAST(CASE WHEN MAX(q.own) = 1 THEN MAX(q.d) ELSE AVG(q.d) END AS decimal(18,4)) AS LostDays FROM ({per_member}) q GROUP BY q.Id"
