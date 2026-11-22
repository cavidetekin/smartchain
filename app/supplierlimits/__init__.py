"""Tedarikçi limiti (ekran 31 ikinci sekme, fonksiyon 103; K-191): satın alınan malzemede tedarikçi üst limiti ve tedarikçi kapanışı.

İki kayıt türü tek tablodadır (`param.SupplierLimit`, `LimitType`); giriş, Baz + fark ve senaryo çakışması ortak altyapıdandır
(`app/capacity/entries.py`, `app/params/resolve.py`). Burada türlerin tanımı, sahibin (lokasyon, tedarikçi, malzeme) kuralları, geçerlilik aralıkları
ve plan dönemine çevirme vardır; liste, servis ve motor arayüzü buradan okur.

Kurallar:
- Limit yalnız tanımlı, aktif ve güncel malzeme tedarikçisi kaydına girilir. Kayıt yoksa tedarikçi o malzemede sınırsızdır.
- Üst limit: aynı tedarikçi ve malzemede o günü kapsayan kayıtlardan başlangıcı en ileri olan geçerlidir; aynı başlangıçlı ikinci kayıt reddedilir.
- Kapanışlar birleşir; malzemesi boş kapanış tedarikçinin bütün malzemelerine uygulanır. Kapalı günde limit de varsa kapanış kazanır.
- Günlük ortalama: limit ÷ limitin döneminin gün sayısı (Gün 1, Hafta 7; Ay, Çeyrek, Yıl için o takvim döneminin gerçek gün sayısı).
- Plan dönemi (`period_limit`): limitsiz ve açık gün varsa dönem sınırsız; yoksa limitli-açık günlerin günlük ortalamalarının toplamı (kapalı günün
  katkısı sıfır); bütün günler kapalıysa tedarikçi o dönemde kapalıdır. Limiti olmayan tedarikçi yalnız dönemin tamamı kapalıysa kapalıdır.
- Malzeme (`material_limit`): tedarikçi sınırlarının toplamı; birinin sınırı yoksa malzeme sınırsızdır.
"""
import calendar
from datetime import date, timedelta
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.capacity.entries import Field, Kind, Owner
from app.params import resolve
from app.periods import cache

TABLE = "SupplierLimit"
SOURCE = "Model kısıtları"                     # adm.FieldChange.Source (ekranın adı)
UPPER, CLOSURE = "Üst limit", "Kapanış"
PERIODS = ("Gün", "Hafta", "Ay", "Çeyrek", "Yıl")
ALL_MATERIALS = "Tümü"                         # malzemesi boş kapanışın yazımı
NO_PAIR = "Bu tedarikçinin bu malzeme için tanımlı kaydı yok."
NO_SUPPLIER = "Bu tedarikçinin tanımlı malzeme tedarikçisi kaydı yok."
# güncel ve aktif malzeme tedarikçisi kayıtları (limit yalnız bunlara girilir)
ACTIVE_PAIRS = "core.MaterialSupplier ms WHERE ms.VersionTo IS NULL AND COALESCE(ms.IsActive, 1) = 1"


# --- sahip: lokasyon, tedarikçi, malzeme -------------------------------------------------------------------------------------------------

def _owner_check(session: Session, values: dict) -> list[dict]:
    """Seçimi doğrular ve kimlikleri sayıya çevirir: tedarikçi (lokasyonuyla) ve varsa malzeme, güncel ve aktif malzeme tedarikçisi kaydı olmalı."""
    out: list[dict] = []
    for name, required in (("LocationId", True), ("SupplierId", True), ("MaterialId", False)):
        value = values.get(name)
        if value is None or value == "":
            values[name] = None
            if required:
                out.append({"field": "SupplierId", "problem": "Tedarikçi seçilmeli."})
            continue
        try:
            values[name] = int(value)
        except (TypeError, ValueError):
            out.append({"field": name if name != "LocationId" else "SupplierId", "problem": "Geçersiz seçim."})
    if out:
        return out[:1]
    params = {"l": values["LocationId"], "s": values["SupplierId"], "m": values["MaterialId"]}
    found = session.execute(sa.text(f"SELECT TOP 1 1 FROM {ACTIVE_PAIRS} AND ms.LocationId = :l AND ms.SupplierId = :s AND (:m IS NULL OR ms.MaterialId = :m)"), params).first()
    if found is None:
        return [{"field": "MaterialId" if values["MaterialId"] is not None else "SupplierId", "problem": NO_PAIR if values["MaterialId"] is not None else NO_SUPPLIER}]
    return []


def _code(session: Session, table: str, row_id: int | None) -> str | None:
    if row_id is None:
        return None
    return session.execute(sa.text(f"SELECT TOP 1 Code FROM core.[{table}] WHERE Id = :i ORDER BY VersionFrom DESC"), {"i": row_id}).scalar()


def _owner_label(session: Session, row: dict) -> str:
    """Kaydın okunur adı: "TED-05 · SAT-003"; bütün malzemeleri kapsayan kapanışta "TED-03 · Tümü"."""
    supplier = _code(session, "Supplier", row.get("SupplierId")) or str(row.get("SupplierId"))
    material = _code(session, "Material", row.get("MaterialId")) if row.get("MaterialId") is not None else ALL_MATERIALS
    return f"{supplier} · {material or row.get('MaterialId')}"


def _owner_key(row: dict) -> tuple | None:
    return (row.get("LocationId"), row.get("SupplierId"), row.get("MaterialId"))


SUPPLIER = Owner(("LocationId", "SupplierId", "MaterialId"), _owner_check, _owner_label, _owner_key,
                 duplicate="Bu tedarikçi ve malzeme için aynı başlangıç tarihli başka bir üst limit var.",
                 locked="Tür, tedarikçi ve malzeme kayıttan sonra değişmez; kaydı silip yeniden girin.",
                 locked_fields=("LimitType", "LocationCode", "SupplierCode", "MaterialCode"))


def _upper_rules(row: dict) -> list[tuple[str, str]]:
    out = []
    if row.get("MaterialId") is None:
        out.append(("MaterialId", "Malzeme seçilmeli."))
    if row.get("UpperLimit") is not None and row["UpperLimit"] <= 0:
        out.append(("UpperLimit", "Sıfırdan büyük olmalı."))
    return out


_START = Field("ValidFrom", "Başlangıç", "date")
_REASON = Field("Reason", "Sebep", "text", required=False, max_length=255)      # iki türde de isteğe bağlı (K-191 demo)
UPPER_KIND = Kind("upper", TABLE, "Tedarikçi üst limiti",
                  (_START, Field("ValidTo", "Bitiş", "date", required=False), Field("UpperLimit", "Limit", "number"),
                   Field("LimitPeriod", "Limitin dönemi", "choice", choices=PERIODS), _REASON),
                  SUPPLIER, unique_start=True, fixed={"LimitType": UPPER}, source=SOURCE, rules=_upper_rules)
CLOSURE_KIND = Kind("closure", TABLE, "Tedarikçi kapanışı",
                    (_START, Field("ValidTo", "Bitiş", "date"), _REASON),
                    SUPPLIER, end_required=True, fixed={"LimitType": CLOSURE}, source=SOURCE)
KINDS = {UPPER: UPPER_KIND, CLOSURE: CLOSURE_KIND}
ANY = Kind("any", TABLE, "Tedarikçi limiti", (), SUPPLIER, source=SOURCE)     # türden bağımsız okuma (satırın türünü bulmak için)


# --- seçenekler --------------------------------------------------------------------------------------------------------------------------

def options(session: Session) -> list[dict]:
    """Pencerenin seçenekleri: güncel ve aktif malzeme tedarikçisi kayıtları, tedarikçi (lokasyonuyla) ve malzemeleri."""
    found = session.execute(sa.text(
        "SELECT ms.LocationId, l.Code AS Location, ms.SupplierId, s.Code, s.Name, ms.MaterialId, m.Code AS MaterialCode, m.Name AS MaterialName, m.BaseUom "
        "FROM core.MaterialSupplier ms JOIN core.Supplier s ON s.Id = ms.SupplierId AND s.VersionTo IS NULL "
        "JOIN core.Material m ON m.Id = ms.MaterialId AND m.VersionTo IS NULL JOIN core.Location l ON l.Id = ms.LocationId "
        "WHERE ms.VersionTo IS NULL AND COALESCE(ms.IsActive, 1) = 1 ORDER BY l.Code, s.Code, m.Code")).mappings()
    out: dict[tuple, dict] = {}
    for r in found:
        key = (r["LocationId"], r["SupplierId"])
        entry = out.setdefault(key, {"location_id": r["LocationId"], "location": r["Location"], "supplier_id": r["SupplierId"], "code": r["Code"], "name": r["Name"],
                                     "materials": []})
        entry["materials"].append({"id": r["MaterialId"], "code": r["MaterialCode"], "name": r["MaterialName"], "unit": r["BaseUom"]})
    return list(out.values())


# --- geçerlilik aralıkları ---------------------------------------------------------------------------------------------------------------

def period_days(period: str, day: date) -> int:
    """Limitin döneminin o günü içeren takvim dönemindeki gün sayısı (K-191 madde 6)."""
    if period == "Gün":
        return 1
    if period == "Hafta":
        return 7
    if period == "Ay":
        return calendar.monthrange(day.year, day.month)[1]
    if period == "Çeyrek":
        first = 3 * ((day.month - 1) // 3) + 1
        return sum(calendar.monthrange(day.year, m)[1] for m in range(first, first + 3))
    if period == "Yıl":
        return 366 if calendar.isleap(day.year) else 365
    raise ValueError(period)


def period_days_sql(period: str, day: str) -> str:
    """`period_days`'in SQL karşılığı (ifade)."""
    quarter = f"DATEFROMPARTS(YEAR({day}), ((MONTH({day}) - 1) / 3) * 3 + 1, 1)"
    return (f"CASE {period} WHEN N'Gün' THEN 1 WHEN N'Hafta' THEN 7 WHEN N'Ay' THEN DAY(EOMONTH({day})) "
            f"WHEN N'Çeyrek' THEN DATEDIFF(day, {quarter}, DATEADD(month, 3, {quarter})) "
            f"WHEN N'Yıl' THEN DATEDIFF(day, DATEFROMPARTS(YEAR({day}), 1, 1), DATEFROMPARTS(YEAR({day}) + 1, 1, 1)) END")


def _records(sid: str, base: str) -> str:
    return resolve.sql(TABLE, sid=sid, base=base)      # senaryonun geçerli kayıtları (çakışmada senaryonun kaydı)


def upper_intervals_sql(sid: str = ":sid", base: str = ":base") -> str:
    """Üst limitin uygulandığı aralıklar. SELECT: LocationId, SupplierId, MaterialId, RowId (geçerli kayıt), Origin, ValidFrom, ValidTo (uygulandığı
    aralık; süresizse boş), UpperLimit, LimitPeriod. Kural kırılma noktalarında uygulanır (kayıtların başlangıcı ve bitiş + 1 günü): her noktada o günü
    kapsayan kayıtlardan başlangıcı en ileri olan (eşitlikte son girilen); aynı kaydın ardışık parçaları birleşir. Kayıt olmayan aralık satır değildir."""
    rec = f"(SELECT u.* FROM ({_records(sid, base)}) u WHERE u.LimitType = N'{UPPER}')"
    key = "{a}.LocationId = {b}.LocationId AND {a}.SupplierId = {b}.SupplierId AND {a}.MaterialId = {b}.MaterialId"
    points = (f"(SELECT a1.LocationId, a1.SupplierId, a1.MaterialId, a1.ValidFrom AS P FROM {rec} a1 "
              f"UNION SELECT a2.LocationId, a2.SupplierId, a2.MaterialId, DATEADD(day, 1, a2.ValidTo) FROM {rec} a2 WHERE a2.ValidTo IS NOT NULL)")
    effective = (f"(SELECT p.LocationId, p.SupplierId, p.MaterialId, p.P, a.RowId, a.Origin, a.UpperLimit, a.LimitPeriod, "
                 "ROW_NUMBER() OVER (PARTITION BY p.LocationId, p.SupplierId, p.MaterialId, p.P ORDER BY CASE WHEN a.RowId IS NULL THEN 1 ELSE 0 END, a.ValidFrom DESC, a.RowId DESC) AS rn "
                 f"FROM {points} p LEFT JOIN {rec} a ON {key.format(a='a', b='p')} AND a.ValidFrom <= p.P AND (a.ValidTo IS NULL OR a.ValidTo >= p.P))")
    window = "PARTITION BY e.LocationId, e.SupplierId, e.MaterialId ORDER BY e.P"
    segments = (f"(SELECT e.*, LEAD(e.P) OVER ({window}) AS NextP, LAG(e.RowId) OVER ({window}) AS PrevRow, ROW_NUMBER() OVER ({window}) AS n "
                f"FROM {effective} e WHERE e.rn = 1)")
    islands = ("(SELECT s.*, SUM(CASE WHEN s.n = 1 OR COALESCE(s.PrevRow, 0) <> COALESCE(s.RowId, 0) THEN 1 ELSE 0 END) "
               f"OVER (PARTITION BY s.LocationId, s.SupplierId, s.MaterialId ORDER BY s.P ROWS UNBOUNDED PRECEDING) AS grp FROM {segments} s)")
    return ("SELECT i.LocationId, i.SupplierId, i.MaterialId, i.RowId, MAX(i.Origin) AS Origin, MIN(i.P) AS ValidFrom, "
            "CASE WHEN COUNT(i.NextP) < COUNT(*) THEN NULL ELSE DATEADD(day, -1, MAX(i.NextP)) END AS ValidTo, MAX(i.UpperLimit) AS UpperLimit, MAX(i.LimitPeriod) AS LimitPeriod "
            f"FROM {islands} i WHERE i.RowId IS NOT NULL GROUP BY i.LocationId, i.SupplierId, i.MaterialId, i.grp, i.RowId")


def closures_sql(sid: str = ":sid", base: str = ":base", expand: bool = True) -> str:
    """Birleşmiş kapanış aralıkları. SELECT: LocationId, SupplierId, MaterialId (boş: bütün malzemeler), ValidFrom, ValidTo, RowId (aralıktaki ilk kayıt),
    Origin, Reason, Records (birleşen kayıt sayısı). expand: malzemesi boş kapanış, tedarikçinin limiti ya da kapanışı olan her malzemesine de uygulanır
    (o malzemenin kapanışlarıyla birleşir); "Tümü" satırı ayrıca kalır."""
    rec = f"({_records(sid, base)})"
    own = f"SELECT c.LocationId, c.SupplierId, c.MaterialId, c.ValidFrom AS A, c.ValidTo AS B, c.RowId, c.Origin, c.Reason FROM {rec} c WHERE c.LimitType = N'{CLOSURE}'"
    if expand:
        pairs = f"(SELECT DISTINCT p.LocationId, p.SupplierId, p.MaterialId FROM {rec} p WHERE p.MaterialId IS NOT NULL)"
        own += (f" UNION ALL SELECT g.LocationId, g.SupplierId, p.MaterialId, g.ValidFrom, g.ValidTo, g.RowId, g.Origin, g.Reason FROM {rec} g JOIN {pairs} p "
                f"ON p.LocationId = g.LocationId AND p.SupplierId = g.SupplierId WHERE g.LimitType = N'{CLOSURE}' AND g.MaterialId IS NULL")
    part = "PARTITION BY x.LocationId, x.SupplierId, COALESCE(x.MaterialId, 0)"
    marked = (f"(SELECT x.*, MAX(x.B) OVER ({part} ORDER BY x.A, x.B, x.RowId ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS PrevEnd FROM ({own}) x)")
    grouped = ("(SELECT m.*, SUM(CASE WHEN m.PrevEnd IS NULL OR m.A > DATEADD(day, 1, m.PrevEnd) THEN 1 ELSE 0 END) "
               "OVER (PARTITION BY m.LocationId, m.SupplierId, COALESCE(m.MaterialId, 0) ORDER BY m.A, m.B, m.RowId ROWS UNBOUNDED PRECEDING) AS grp "
               f"FROM {marked} m)")
    return ("SELECT q.LocationId, q.SupplierId, q.MaterialId, MIN(q.A) AS ValidFrom, MAX(q.B) AS ValidTo, MIN(q.RowId) AS RowId, MAX(q.Origin) AS Origin, "
            "MAX(q.Reason) AS Reason, COUNT(*) AS Records "
            f"FROM {grouped} q GROUP BY q.LocationId, q.SupplierId, q.MaterialId, COALESCE(q.MaterialId, 0), q.grp")


def validity_sql(sid: str = ":sid", base: str = ":base") -> str:
    """Geçerlilik listesinin satırları: üst limit aralıkları ("Üst limit") ve birleşmiş kapanışlar ("Kapalı"). SELECT: LocationId, SupplierId, MaterialId,
    Status, ValidFrom, ValidTo, UpperLimit, LimitPeriod, DailyAverage (aralığın ilk gününün günlük ortalaması), Reason, SourceRowId, SourceOrigin."""
    upper = upper_intervals_sql(sid, base)
    closed = closures_sql(sid, base)
    daily = f"CAST(u.UpperLimit / {period_days_sql('u.LimitPeriod', 'u.ValidFrom')} AS decimal(18,4))"
    return (f"SELECT u.LocationId, u.SupplierId, u.MaterialId, N'{UPPER}' AS Status, u.ValidFrom, u.ValidTo, u.UpperLimit, u.LimitPeriod, {daily} AS DailyAverage, "
            f"CAST(NULL AS nvarchar(255)) AS Reason, u.RowId AS SourceRowId, u.Origin AS SourceOrigin FROM ({upper}) u "
            f"UNION ALL SELECT c.LocationId, c.SupplierId, c.MaterialId, N'Kapalı', c.ValidFrom, c.ValidTo, NULL, NULL, NULL, c.Reason, c.RowId, c.Origin FROM ({closed}) c")


# --- plan dönemine çevirme ve motor arayüzü ----------------------------------------------------------------------------------------------

def _scope(session: Session, scenario_id: int) -> dict:
    scenario = cache.scenario_row(session, scenario_id)
    return {"sid": scenario_id, "base": cache.base_of(session, scenario)}


def daily(session: Session, scenario_id: int, date_from: date, date_to: date) -> list[dict]:
    """Gün bazında satırlar (motor arayüzü, docs/09): {LocationId, SupplierId, MaterialId, Day, DailyLimit, Closed}; yalnız üst limiti ya da kapanışı
    olan günler. Kapalı günde `Closed` doğrudur (limit de varsa `DailyLimit` yine yazılır ama kapanış kazanır). Malzemesi boş satır tedarikçinin bütün
    malzemelerini kapsayan kapanıştır; aynı kapanış, limiti ya da kapanışı olan malzemelerin satırlarına da işlenmiştir."""
    params = {**_scope(session, scenario_id), "a": date_from, "b": date_to}
    uppers = session.execute(sa.text(f"SELECT u.* FROM ({upper_intervals_sql()}) u WHERE u.ValidFrom <= :b AND (u.ValidTo IS NULL OR u.ValidTo >= :a)"), params).mappings().all()
    closed = session.execute(sa.text(f"SELECT c.* FROM ({closures_sql()}) c WHERE c.ValidFrom <= :b AND c.ValidTo >= :a"), params).mappings().all()
    out: dict[tuple, dict] = {}

    def days(start: date, end: date | None):
        day, last = max(start, date_from), min(end or date_to, date_to)
        while day <= last:
            yield day
            day += timedelta(days=1)

    for u in uppers:
        key = (u["LocationId"], u["SupplierId"], u["MaterialId"])
        for day in days(u["ValidFrom"], u["ValidTo"]):
            out[(*key, day)] = {"LocationId": key[0], "SupplierId": key[1], "MaterialId": key[2], "Day": day,
                                "DailyLimit": Decimal(u["UpperLimit"]) / period_days(u["LimitPeriod"], day), "Closed": False}
    for c in closed:
        key = (c["LocationId"], c["SupplierId"], c["MaterialId"])
        for day in days(c["ValidFrom"], c["ValidTo"]):
            row = out.setdefault((*key, day), {"LocationId": key[0], "SupplierId": key[1], "MaterialId": key[2], "Day": day, "DailyLimit": None, "Closed": True})
            row["Closed"] = True
    return sorted(out.values(), key=lambda r: (r["LocationId"], r["SupplierId"], r["MaterialId"] or 0, r["Day"]))


def period_limit(rows: list[dict], start: date, end: date) -> dict:
    """Bir tedarikçi + malzemenin plan dönemindeki sınırı. rows: o çiftin gün satırları (`daily`; malzemeye özel ve genel kapanış birlikte).
    Dönen: {"Limit": sınır (None: sınırsız), "Closed": dönemin tamamı kapalı}. Kurallar modülün başında."""
    by_day = {r["Day"]: r for r in rows}
    total, unlimited, any_open = Decimal(0), False, False
    day = start
    while day <= end:
        row = by_day.get(day)
        if not (row and row["Closed"]):
            any_open = True
            if row is None or row["DailyLimit"] is None:
                unlimited = True
            else:
                total += row["DailyLimit"]
        day += timedelta(days=1)
    if not any_open:
        return {"Limit": Decimal(0), "Closed": True}
    return {"Limit": None if unlimited else total, "Closed": False}


def _pair_rows(rows: list[dict], location_id: int, supplier_id: int, material_id: int) -> list[dict]:
    """Çiftin gün satırları: malzemenin kendi satırları; kaydı olmayan malzemede tedarikçinin genel kapanışı."""
    own = [r for r in rows if (r["LocationId"], r["SupplierId"], r["MaterialId"]) == (location_id, supplier_id, material_id)]
    return own or [r for r in rows if (r["LocationId"], r["SupplierId"], r["MaterialId"]) == (location_id, supplier_id, None)]


def supplier_limit(session: Session, scenario_id: int, location_id: int, supplier_id: int, material_id: int, start: date, end: date) -> dict:
    """Tedarikçi + malzemenin plan dönemindeki sınırı (`period_limit`)."""
    return period_limit(_pair_rows(daily(session, scenario_id, start, end), location_id, supplier_id, material_id), start, end)


def material_limit(session: Session, scenario_id: int, location_id: int, material_id: int, start: date, end: date) -> dict:
    """Malzemenin plan dönemindeki satın alma üst sınırı: güncel ve aktif tedarikçilerinin sınırlarının toplamı; birinin sınırı yoksa sınırsız (None).
    Dönen: {"Limit", "Suppliers": {tedarikçi: {"Limit", "Closed"}}}."""
    suppliers = [r[0] for r in session.execute(sa.text(f"SELECT ms.SupplierId FROM {ACTIVE_PAIRS} AND ms.LocationId = :l AND ms.MaterialId = :m ORDER BY ms.SupplierId"),
                                               {"l": location_id, "m": material_id})]
    rows = daily(session, scenario_id, start, end)
    per = {s: period_limit(_pair_rows(rows, location_id, s, material_id), start, end) for s in suppliers}
    limits = [p["Limit"] for p in per.values()]
    return {"Limit": None if (not limits or any(x is None for x in limits)) else sum(limits, Decimal(0)), "Suppliers": per}
