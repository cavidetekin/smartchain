"""Alokasyon kuralı (K-199): `core.MaterialAllocationRule`'un hesabı.

Bir malzeme bir sahip (sipariş, proje, müşteri) adına ayrı izlenir ancak malzemenin kendisinde ya da alt seviyelerinde o sahibe ayrılmış açık arz
varsa. Tanım: (malzeme, anahtar) satırı vardır ⇔ o anahtara uyan bir talebin malzemesinden o anahtarlı açık arzın malzemesine inen bir yolun
üzerindedir (uçlar dahil). Arz malzemenin kendisindeyse sebep "Kendi arzı", yalnız alt seviyelerindeyse "Alt seviye arzı". Kullanacak talebi
olmayan, sahibi bulunamayan ya da kapanmış ayrılmış arz satır açmaz. Model ve pegging ağaçta yeniden yürümez; bu tabloyu okur (Aşama 10, 7.17).

Hesap veritabanında, küme SQL'iyle ve geçici tablolarla (her turda yalnız son turun satırları genişler):
1. Kenarlar: aktif üretim versiyonlarının ağaç satırları (bütün versiyonlar ve alternatifler), kendi aktif versiyonu olmayan malzemede benzetilen
   ürünün ağacı, açık üretim siparişlerinin kendi bileşenleri. Malzemenin `Id`'si lokasyona özgüdür: yürüyüş lokasyon içinde kalır.
2. Arz anahtarları: stok (miktar > 0), üretim siparişi ve satın alma satırı (açık miktar > 0); yalnız anahtarlı (özel alokasyonlu) satırlar (K-198).
3. Talep anahtarları: açık satış siparişi satırı → Sipariş / kalemli anahtar, Sipariş / kalemsiz anahtar (yalnız sipariş no), Proje, Müşteri;
   aktif tahmin → Proje, Müşteri. Yalnız arzı olan anahtarlar alınır (budama).
4. Yukarı kapanış (arzdan; talebi olan anahtarlar; arzın durduğu malzeme "kaynak" olarak taşınır): arzın üstündeki bütün malzemeler. Küçük kümedir.
5. Aşağı kapanış (talepten), yalnız yukarı kapanışın içinde: talepten arza inen yolun her malzemesi arzın üstündedir, bu yüzden yürüyüş o kümenin
   dışına çıkmaz. (Önce aşağı yürümek her sahip için bütün ağacı dolaşırdı; ölçümde 28 sn tutuyordu.)
6. Sonuç ve fark: değişmeyen satır kalır, kalkan kapanır, yeni açılır, sebebi ya da kaynağı değişen yeni versiyon açar. Kimlik anahtara bağlıdır
   (lokasyon + malzeme + seviye + anahtar): aynı kural yeniden hesapta aynı `Id`'yi korur. Hayalet malzemeye satır açılmaz.

Aktarımın sonunda (tam ve kısmi; `app.transfer.engine.run_transfer`) ve sentetik yüklemede çağrılır; her seferinde tam hesap.
"""
import time

import sqlalchemy as sa

from . import CUSTOMER, ORDER, PROJECT, SEP

TABLE = "MaterialAllocationRule"
OWN, BELOW = "Kendi arzı", "Alt seviye arzı"
MAX_LEVELS = 60          # döngü ve derinlik koruması (talep zinciriyle aynı)
TEMP = ("#ar_edge", "#ar_key", "#ar_supply", "#ar_demand", "#ar_down", "#ar_up", "#ar_rule")
ON = "ISNULL({0}.IsActive, 1) = 1"
TEXT = "COLLATE DATABASE_DEFAULT"

# Anahtar (seviye + anahtar metni) kapanışlarda tam sayı kimlikle taşınır (#ar_key): turlar metin karşılaştırmaz
CREATE = (
    "CREATE TABLE #ar_edge (P bigint NOT NULL, C bigint NOT NULL, PRIMARY KEY (P, C))",
    "CREATE INDEX IX_ar_edge_child ON #ar_edge (C, P)",
    f"CREATE TABLE #ar_key (Id int IDENTITY(1, 1) PRIMARY KEY, L nvarchar(10) {TEXT} NOT NULL, K nvarchar(60) {TEXT} NOT NULL, UNIQUE (L, K))",
    "CREATE TABLE #ar_supply (KeyId int NOT NULL, M bigint NOT NULL, PRIMARY KEY (KeyId, M))",
    "CREATE TABLE #ar_demand (KeyId int NOT NULL, M bigint NOT NULL, PRIMARY KEY (KeyId, M))",
    "CREATE TABLE #ar_down (KeyId int NOT NULL, M bigint NOT NULL, D int NOT NULL, PRIMARY KEY (KeyId, M))",
    "CREATE INDEX IX_ar_down_depth ON #ar_down (D)",
    "CREATE TABLE #ar_up (KeyId int NOT NULL, M bigint NOT NULL, S bigint NOT NULL, D int NOT NULL, PRIMARY KEY (KeyId, M, S))",
    "CREATE INDEX IX_ar_up_depth ON #ar_up (D)",
    f"CREATE TABLE #ar_rule (LocationId int NOT NULL, MaterialId bigint NOT NULL, L nvarchar(10) {TEXT} NOT NULL, K nvarchar(60) {TEXT} NOT NULL, "
    f"Reason nvarchar(20) {TEXT} NOT NULL, SourceMaterials nvarchar(70) {TEXT} NULL, Id bigint NULL, St tinyint NOT NULL DEFAULT 0, "
    "PRIMARY KEY (MaterialId, L, K))",
)

# Ürün ağacı satırı versiyonun ağacına `BOMCode` ile bağlanır (K-115); bütün aktif versiyonlar ve alternatif satırlar kenardır
BOM_OF = ("JOIN core.BOM b ON b.Code = pv.BOMCode AND b.LocationId = pv.LocationId AND b.MaterialId = pv.MaterialId AND b.VersionTo IS NULL")
EDGES = f"""
INSERT INTO #ar_edge (P, C)
SELECT x.P, x.C FROM (
    SELECT pv.MaterialId AS P, b.ComponentMaterialId AS C FROM core.ProductionVersion pv {BOM_OF}
    WHERE pv.VersionTo IS NULL AND {ON.format('pv')}
    UNION
    SELECT r.MaterialId, b.ComponentMaterialId FROM core.MaterialReference r
    JOIN core.ProductionVersion pv ON pv.VersionTo IS NULL AND {ON.format('pv')}
         AND ((r.ReferenceProductionVersionId IS NOT NULL AND pv.Id = r.ReferenceProductionVersionId)
              OR (r.ReferenceProductionVersionId IS NULL AND pv.MaterialId = r.ReferenceMaterialId))
    {BOM_OF}
    WHERE r.VersionTo IS NULL AND NOT EXISTS (SELECT 1 FROM core.ProductionVersion o WHERE o.MaterialId = r.MaterialId AND o.VersionTo IS NULL AND {ON.format('o')})
    UNION
    SELECT w.MaterialId, c.MaterialId FROM core.WorkOrder w JOIN core.WorkOrderComponent c ON c.WorkOrderId = w.Id AND c.VersionTo IS NULL
    WHERE w.VersionTo IS NULL AND w.OpenQuantity > 0
) x WHERE x.P <> x.C"""

# Açık ve anahtarlı arz (K-198): stokta miktar > 0, üretim siparişi ve satın alma satırında açık miktar > 0
OPEN_SUPPLY = f"""
    SELECT AllocationLevel AS L, AllocationKey AS K, MaterialId AS M FROM core.Stock s
    WHERE s.VersionTo IS NULL AND s.IsCustomAllocated = 1 AND s.AllocationKey IS NOT NULL AND s.Quantity > 0 AND {ON.format('s')}
    UNION
    SELECT AllocationLevel, AllocationKey, MaterialId FROM core.WorkOrder w
    WHERE w.VersionTo IS NULL AND w.IsCustomAllocated = 1 AND w.AllocationKey IS NOT NULL AND w.OpenQuantity > 0
    UNION
    SELECT AllocationLevel, AllocationKey, MaterialId FROM core.PurchaseOrderLine p
    WHERE p.VersionTo IS NULL AND p.IsCustomAllocated = 1 AND p.AllocationKey IS NOT NULL AND p.OpenQuantity > 0 AND {ON.format('p')}"""
KEYS = f"INSERT INTO #ar_key (L, K) SELECT DISTINCT x.L, x.K FROM ({OPEN_SUPPLY}) x"
SUPPLY = f"INSERT INTO #ar_supply (KeyId, M) SELECT DISTINCT k.Id, x.M FROM ({OPEN_SUPPLY}) x JOIN #ar_key k ON k.L = x.L AND k.K = x.K"

OPEN_ORDER = f"s.VersionTo IS NULL AND {ON.format('s')} AND s.OpenQuantity > 0"
FORECAST = f"f.VersionTo IS NULL AND {ON.format('f')} AND f.Quantity > 0"
# Talebin uyduğu anahtarlar; yalnız arzı olan anahtarlar alınır (#ar_key'e bağlanarak): arzı olmayan sahip hiç yürünmez
DEMAND = f"""
INSERT INTO #ar_demand (KeyId, M)
SELECT DISTINCT k.Id, x.M FROM (
    SELECT N'{ORDER}' AS L, CAST(CONCAT(s.OrderNo, N'{SEP}', s.[LineNo], N'{SEP}', ISNULL(s.LineItemNo, 0)) AS nvarchar(60)) AS K, s.MaterialId AS M
    FROM core.SalesOrderLine s WHERE {OPEN_ORDER}
    UNION ALL
    SELECT N'{ORDER}', CAST(s.OrderNo AS nvarchar(60)), s.MaterialId FROM core.SalesOrderLine s WHERE {OPEN_ORDER}
    UNION ALL
    SELECT N'{PROJECT}', CAST(p.Code AS nvarchar(60)), s.MaterialId FROM core.SalesOrderLine s JOIN core.Project p ON p.Id = s.ProjectId AND p.VersionTo IS NULL
    WHERE {OPEN_ORDER}
    UNION ALL
    SELECT N'{CUSTOMER}', CAST(c.Code AS nvarchar(60)), s.MaterialId FROM core.SalesOrderLine s JOIN core.Customer c ON c.Id = s.CustomerId AND c.VersionTo IS NULL
    WHERE {OPEN_ORDER}
    UNION ALL
    SELECT N'{PROJECT}', CAST(p.Code AS nvarchar(60)), f.MaterialId FROM core.Forecast f JOIN core.Project p ON p.Id = f.ProjectId AND p.VersionTo IS NULL
    WHERE {FORECAST}
    UNION ALL
    SELECT N'{CUSTOMER}', CAST(c.Code AS nvarchar(60)), f.MaterialId FROM core.Forecast f JOIN core.Customer c ON c.Id = f.CustomerId AND c.VersionTo IS NULL
    WHERE {FORECAST}
) x JOIN #ar_key k ON k.L = x.L AND k.K = x.K"""

# kaynak: arzın durduğu malzeme (S); kaynaksız hesapta 0 (yalnız performans karşılaştırması için)
UP_START = "INSERT INTO #ar_up (KeyId, M, S, D) SELECT s.KeyId, s.M, {source}, 0 FROM #ar_supply s WHERE EXISTS (SELECT 1 FROM #ar_demand d WHERE d.KeyId = s.KeyId)"
UP_STEP = """
INSERT INTO #ar_up (KeyId, M, S, D)
SELECT DISTINCT u.KeyId, e.P, u.S, :n FROM #ar_up u JOIN #ar_edge e ON e.C = u.M
WHERE u.D = :p AND NOT EXISTS (SELECT 1 FROM #ar_up x WHERE x.KeyId = u.KeyId AND x.M = e.P AND x.S = u.S)"""
ABOVE = "EXISTS (SELECT 1 FROM #ar_up u WHERE u.KeyId = d.KeyId AND u.M = {m})"   # arzın üstünde (ya da arzın kendisi)
DOWN_START = f"INSERT INTO #ar_down (KeyId, M, D) SELECT d.KeyId, d.M, 0 FROM #ar_demand d WHERE {ABOVE.format(m='d.M')}"
DOWN_STEP = f"""
INSERT INTO #ar_down (KeyId, M, D)
SELECT DISTINCT d.KeyId, e.C, :n FROM #ar_down d JOIN #ar_edge e ON e.P = d.M
WHERE d.D = :p AND {ABOVE.format(m='e.C')} AND NOT EXISTS (SELECT 1 FROM #ar_down x WHERE x.KeyId = d.KeyId AND x.M = e.C)"""

OWN_HERE = "EXISTS (SELECT 1 FROM #ar_supply s WHERE s.KeyId = g.KeyId AND s.M = g.M)"
BELOW_HERE = "u.KeyId = g.KeyId AND u.M = g.M AND u.S <> g.M"
RESULT_WITH = f"""
INSERT INTO #ar_rule (LocationId, MaterialId, L, K, Reason, SourceMaterials)
SELECT m.LocationId, g.M, k.L, k.K, CASE WHEN {OWN_HERE} THEN N'{OWN}' ELSE N'{BELOW}' END,
       CASE WHEN {OWN_HERE} THEN NULL WHEN n.Others > 1 THEN CONCAT(f.Code, N' +', n.Others - 1) ELSE f.Code END
FROM #ar_down g JOIN #ar_key k ON k.Id = g.KeyId
JOIN core.Material m ON m.Id = g.M AND m.VersionTo IS NULL AND ISNULL(m.IsPhantom, 0) = 0
OUTER APPLY (SELECT TOP 1 sm.Code FROM #ar_up u JOIN core.Material sm ON sm.Id = u.S AND sm.VersionTo IS NULL WHERE {BELOW_HERE} ORDER BY sm.Code) f
OUTER APPLY (SELECT COUNT(*) AS Others FROM #ar_up u WHERE {BELOW_HERE}) n"""
RESULT_WITHOUT = f"""
INSERT INTO #ar_rule (LocationId, MaterialId, L, K, Reason)
SELECT m.LocationId, g.M, k.L, k.K, CASE WHEN {OWN_HERE} THEN N'{OWN}' ELSE N'{BELOW}' END
FROM #ar_down g JOIN #ar_key k ON k.Id = g.KeyId
JOIN core.Material m ON m.Id = g.M AND m.VersionTo IS NULL AND ISNULL(m.IsPhantom, 0) = 0"""

T = f"core.[{TABLE}]"
SAME_KEY = "t.LocationId = r.LocationId AND t.MaterialId = r.MaterialId AND t.AllocationLevel = r.L AND t.AllocationKey = r.K"
CURRENT = f"SELECT 1 FROM {T} c WHERE c.Id = r.Id AND c.VersionTo IS NULL"
DIFFERS = "(c.Reason <> r.Reason OR ISNULL(c.SourceMaterials, N'') <> ISNULL(r.SourceMaterials, N''))"
GONE = f"t.VersionTo IS NULL AND NOT EXISTS (SELECT 1 FROM #ar_rule r WHERE r.Id = t.Id)"
HISTORY = "INSERT INTO adm.FieldChange (TableName, RecordKey, ChangeType, DataVersionId, At, Source, UserId{more}) "
BASE = f"N'{TABLE}', CAST({{id}} AS nvarchar(60)), :type, :v, :now, :source, :user"


def _run(conn, sql: str, **params) -> int:
    return conn.execute(sa.text(sql), params).rowcount or 0


def _drop(conn) -> None:
    for name in TEMP:
        conn.execute(sa.text(f"IF OBJECT_ID('tempdb..{name}') IS NOT NULL DROP TABLE {name}"))


def _closure(conn, start: str, step: str) -> int:
    conn.execute(sa.text(start))
    for depth in range(1, MAX_LEVELS + 1):
        if not _run(conn, step, n=depth, p=depth - 1):
            return depth - 1
    return MAX_LEVELS


def compute(conn, sources: bool = True) -> dict:
    """Kuralları `#ar_rule` geçici tablosuna hesaplar (yazmaz); aşama süreleri (sn) ve sayılar. Çağıran `_drop` ile temizler."""
    t0 = time.perf_counter()
    seconds, counts = {}, {}

    def lap(name: str) -> None:
        nonlocal t0
        seconds[name] = round(time.perf_counter() - t0, 3)
        t0 = time.perf_counter()

    _drop(conn)
    for sql in CREATE:
        conn.execute(sa.text(sql))
    counts["edges"] = _run(conn, EDGES)
    lap("edges")
    counts["keys"] = _run(conn, KEYS)
    counts["supply"] = _run(conn, SUPPLY)
    counts["demand"] = _run(conn, DEMAND)
    lap("keys")
    counts["levels_up"] = _closure(conn, UP_START.format(source="s.M" if sources else "0"), UP_STEP)
    lap("up")
    counts["levels_down"] = _closure(conn, DOWN_START, DOWN_STEP)
    lap("down")
    counts["rules"] = _run(conn, RESULT_WITH if sources else RESULT_WITHOUT)
    lap("result")
    return {"seconds": seconds, **counts}


def rebuild(conn, version: int, now, user_id: int | None = None, sources: bool = True, history: bool = True) -> dict:
    """Tam hesap ve fark; `version` veri versiyonuyla yazar. conn: oturum ya da bağlantı (çağıranın işleminde). Sayılar ve aşama süreleri döner."""
    from app import history as h

    out = compute(conn, sources)
    t0 = time.perf_counter()
    try:
        # kimlik anahtara bağlı: kural daha önce varsa (kapanmış olsa da) aynı Id; yoksa yeni Id
        _run(conn, f"UPDATE r SET Id = (SELECT TOP 1 t.Id FROM {T} t WHERE {SAME_KEY} ORDER BY t.VersionFrom DESC) FROM #ar_rule r")
        _run(conn, f"WITH n AS (SELECT Id, ROW_NUMBER() OVER (ORDER BY MaterialId, L, K) AS rn FROM #ar_rule WHERE Id IS NULL) "
                   f"UPDATE n SET Id = (SELECT ISNULL(MAX(Id), 0) FROM {T}) + rn")
        _run(conn, f"UPDATE r SET St = CASE WHEN c.Id IS NULL THEN 1 WHEN {DIFFERS} THEN 2 ELSE 0 END "
                   f"FROM #ar_rule r LEFT JOIN {T} c ON c.Id = r.Id AND c.VersionTo IS NULL")
        base = {"v": version, "now": now, "source": h.TRANSFER, "user": user_id}
        if history:
            _run(conn, HISTORY.format(more="") + f"SELECT {BASE.format(id='r.Id')} FROM #ar_rule r WHERE r.St = 1", type=h.CREATED, **base)
            for field in ("Reason", "SourceMaterials"):
                _run(conn, HISTORY.format(more=", FieldName, OldValue, NewValue") + f"SELECT {BASE.format(id='r.Id')}, N'{field}', c.{field}, r.{field} "
                           f"FROM #ar_rule r JOIN {T} c ON c.Id = r.Id AND c.VersionTo IS NULL "
                           f"WHERE r.St = 2 AND ISNULL(c.{field}, N'') <> ISNULL(r.{field}, N'')", type=h.CHANGED, **base)
            _run(conn, HISTORY.format(more="") + f"SELECT {BASE.format(id='t.Id')} FROM {T} t WHERE {GONE}", type=h.CLOSED, **base)
        # kalkan ve değişen: bu versiyonda yazılmış satır yerinde (silinir ya da güncellenir), eskisi kapanır
        out["closed"] = _run(conn, f"DELETE t FROM {T} t WHERE {GONE} AND t.VersionFrom = :v", v=version)
        out["closed"] += _run(conn, f"UPDATE t SET VersionTo = :v - 1, UpdatedAt = :now FROM {T} t WHERE {GONE}", v=version, now=now)
        _run(conn, f"UPDATE t SET Reason = r.Reason, SourceMaterials = r.SourceMaterials, UpdatedAt = :now "
                   f"FROM {T} t JOIN #ar_rule r ON r.Id = t.Id AND r.St = 2 WHERE t.VersionTo IS NULL AND t.VersionFrom = :v", v=version, now=now)
        _run(conn, f"UPDATE t SET VersionTo = :v - 1, UpdatedAt = :now FROM {T} t JOIN #ar_rule r ON r.Id = t.Id AND r.St = 2 "
                   "WHERE t.VersionTo IS NULL AND t.VersionFrom < :v", v=version, now=now)
        _run(conn, f"INSERT INTO {T} (Id, LocationId, MaterialId, AllocationLevel, AllocationKey, Reason, SourceMaterials, VersionFrom, VersionTo, "
                   "ImportBatchId, BusinessKey, UpdatedAt) "
                   "SELECT r.Id, r.LocationId, r.MaterialId, r.L, r.K, r.Reason, r.SourceMaterials, :v, NULL, NULL, "
                   f"LEFT(CONCAT(l.Code, N'{SEP}', m.Code, N'{SEP}', r.L, N'{SEP}', r.K), 200), :now "
                   "FROM #ar_rule r JOIN core.Location l ON l.Id = r.LocationId JOIN core.Material m ON m.Id = r.MaterialId AND m.VersionTo IS NULL "
                   f"WHERE r.St IN (1, 2) AND NOT EXISTS ({CURRENT})", v=version, now=now)
        row = conn.execute(sa.text("SELECT SUM(CASE WHEN St = 1 THEN 1 ELSE 0 END), SUM(CASE WHEN St = 2 THEN 1 ELSE 0 END) FROM #ar_rule")).one()
        out["new"], out["changed"] = int(row[0] or 0), int(row[1] or 0)
    finally:
        _drop(conn)
    out["seconds"]["write"] = round(time.perf_counter() - t0, 3)
    out["seconds"]["total"] = round(sum(out["seconds"].values()), 3)
    return out
