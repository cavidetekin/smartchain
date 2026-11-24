"""Öncelik yönetimi (K-195; ekran 32, fonksiyon 25): müşteri, proje ve sipariş satırı için girilen 1–5 öncelik grubu ve talebin geçerli öncelik grubu.

Giriş `param.DemandPriority`'dedir (`Level`, `RecordId`, `PriorityGroup`); senaryo bazlı, Baz + fark (K-176). Kayıt bağımsız bir satır değil,
müşterinin (projenin, sipariş satırının) tek değeridir: **her senaryoda her kayıt tek satırdır** (`resolved_sql`; Model kısıtları'ndaki kalıp).

- Baz'da ve Baz'ı izlemeyen senaryoda değer senaryonun kendi satırındadır; boşaltılınca satır silinir.
- Baz'ı izleyen senaryoda: Baz'da değeri olan kayıtta değişiklik fark satırına yazılır. Değer boşaltılırsa fark "boş" olarak durur (o kayıt bu
  senaryoda girilmemiş sayılır); Baz'daki değere dönülürse fark kalkar. Baz'da değeri olmayan kayıtta senaryonun kendi satırına yazılır.
- Kaydın hem senaryonun kendi satırı hem Baz satırı varsa (önce senaryoda, sonra Baz'da girildiyse) senaryonun değeri geçerlidir ve fark sayılır
  (K-191 kuralı); sonraki yazmada kendi satırı fark satırına çevrilir.
- Baz satırı silinince izleyen senaryoların o satıra bağlı farkları kendi satırına döner (boş farklar silinir).

Geçerli öncelik (tek hesap; ekran, İşlem verisi listeleri ve motor aynı ifadeyi kullanır; önbellek yok):
- Düzey değeri = girilen öncelik grubu, yoksa 1–5 aralığındaki ERP önceliği (`Priority`); aralık dışı ERP önceliği yok sayılır.
- Sipariş satırı: siparişin → projesinin → müşterisinin düzey değeri; hiçbiri yoksa 5. Kaynağı: Sipariş · Proje · Müşteri · Yok.
- Tahmin: projesinin → müşterisinin; hiçbiri yoksa 5. Proje grubu hiyerarşiye girmez.

Her değişiklik aynı veritabanı işleminde alan geçmişini yazar (`adm.FieldChange`; kayıt anahtarı "<düzey>:<kimlik>", Baz dışındaki senaryoda
"<düzey>:<kimlik>@<senaryo>"). Commit ve denetim izi çağırandadır.
"""
from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app import history
from app.periods import cache

TABLE = "DemandPriority"
SOURCE = "Öncelik yönetimi"                        # adm.FieldChange.Source
FIELD = "PriorityGroup"
LABEL = "Öncelik grubu"
CUSTOMER, PROJECT, ORDER = "Müşteri", "Proje", "Sipariş"
NONE = "Yok"                                       # öncelik kaynağı: hiçbir düzeyde değer yok
LOWEST = 5
GROUPS = (1, 2, 3, 4, 5)
PROBLEM = "1 ile 5 arasında tam sayı olmalı."
BASE, DIFF, OWN = "Baz", "Senaryo farkı", "Senaryo"   # "Kaynağı" (app/params/resolve.py ile aynı adlar)


@dataclass(frozen=True)
class Level:
    name: str            # Müşteri · Proje · Sipariş (tablodaki değer)
    key: str             # adresteki ad ve geçmiş anahtarının öneki
    table: str           # core tablosu
    code: str            # kaydın okunur adı (SQL ifadesi; takma ad x)


LEVELS = {l.key: l for l in (
    Level(CUSTOMER, "customers", "Customer", "x.Code"),
    Level(PROJECT, "projects", "Project", "x.Code"),
    Level(ORDER, "orders", "SalesOrderLine", "x.OrderNo + N' / ' + CAST(x.[LineNo] AS nvarchar(20))"),
)}


class PriorityError(Exception):
    """Doğrulama hatası: problems = [{id, field, record, problem}]; code "validation" dışındaysa tek mesajlı iş kuralı."""

    def __init__(self, problems: list[dict] | None = None, *, code: str = "validation", message: str = "Kaydedilmedi.", status: int = 422):
        super().__init__(message)
        self.problems, self.code, self.message, self.status = problems or [], code, message, status


@dataclass(frozen=True)
class Scope:
    scenario_id: int
    scenario_name: str
    base_id: int | None        # izlediği Baz; Baz'da ve izlemeyen senaryoda None
    is_base: bool

    @property
    def note(self) -> str | None:
        return None if self.is_base else self.scenario_name[:100]

    def history_key(self, level: Level, record_id: int) -> str:
        return f"{level.key}:{record_id}" if self.is_base else f"{level.key}:{record_id}@{self.scenario_id}"


def scope_of(session: Session, scenario: dict) -> Scope:
    return Scope(scenario["Id"], scenario["Name"], cache.base_of(session, scenario), bool(scenario["IsBase"]))


# --- çözümleme: senaryo + kayıt başına tek satır -----------------------------------------------------------------------------------------

def resolved_sql(sid: str = ":sid", base: str = ":base") -> str:
    """Senaryonun girilmiş öncelik grupları, kayıt başına tek satır (SELECT metni). Parametreler: senaryo ve okuduğu Baz (Baz'da ve izlemeyen
    senaryoda NULL). Kolonlar: Level, RecordId, BaseId (Baz satırı), OwnId (senaryonun kendi satırı), DiffId (fark satırı), PriorityGroup (boş
    olabilir: izleyen senaryoda kaldırılmış Baz değeri), BasePriorityGroup, Origin (Baz · Senaryo farkı · Senaryo), OverriddenFields, BaseValues
    (JSON; yalnız farkta), CanRestore (izleyen senaryoda değer senaryodan geliyor: "Senaryo farkını kaldır").

    Öncelik: senaryonun kendi satırı > fark satırı > Baz. Aynı kayıtta birden fazla satır kalmışsa en son yazılan alınır."""
    t = f"param.[{TABLE}]"
    latest = "ROW_NUMBER() OVER (PARTITION BY x.[Level], x.RecordId ORDER BY x.Id DESC) AS rn"
    b = f"(SELECT x.*, {latest} FROM {t} x WHERE x.ScenarioDefinitionId = {base} AND x.BaseRowId IS NULL)"
    o = f"(SELECT x.*, {latest} FROM {t} x WHERE x.ScenarioDefinitionId = {sid} AND x.BaseRowId IS NULL)"
    d = f"(SELECT x.*, ROW_NUMBER() OVER (PARTITION BY x.BaseRowId ORDER BY x.Id DESC) AS rn FROM {t} x WHERE x.ScenarioDefinitionId = {sid} AND x.BaseRowId IS NOT NULL)"
    inner = ("SELECT COALESCE(b.[Level], o.[Level]) AS [Level], COALESCE(b.RecordId, o.RecordId) AS RecordId, b.Id AS BaseId, o.Id AS OwnId, d.Id AS DiffId, "
             f"CASE WHEN o.Id IS NOT NULL THEN o.[{FIELD}] WHEN d.Id IS NOT NULL THEN d.[{FIELD}] ELSE b.[{FIELD}] END AS [{FIELD}], b.[{FIELD}] AS [Base{FIELD}] "
             f"FROM (SELECT * FROM {b} b0 WHERE b0.rn = 1) b FULL JOIN (SELECT * FROM {o} o0 WHERE o0.rn = 1) o ON o.[Level] = b.[Level] AND o.RecordId = b.RecordId "
             f"LEFT JOIN (SELECT * FROM {d} d0 WHERE d0.rn = 1) d ON d.BaseRowId = b.Id")
    differs = f"((r.[{FIELD}] IS NULL AND r.[Base{FIELD}] IS NOT NULL) OR (r.[{FIELD}] IS NOT NULL AND r.[Base{FIELD}] IS NULL) OR r.[{FIELD}] <> r.[Base{FIELD}])"
    return (f"SELECT r.*, CASE WHEN r.BaseId IS NULL THEN N'{OWN}' WHEN {differs} THEN N'{DIFF}' ELSE N'{BASE}' END AS Origin, "
            f"CASE WHEN r.BaseId IS NOT NULL AND {differs} THEN N',{FIELD},' END AS OverriddenFields, "
            f"CASE WHEN r.BaseId IS NOT NULL AND {differs} THEN N'{{\"{FIELD}\":' + COALESCE(CAST(r.[Base{FIELD}] AS nvarchar(10)), N'null') + N'}}' END AS BaseValues, "
            f"CAST(CASE WHEN {base} IS NOT NULL AND (r.BaseId IS NULL OR {differs}) THEN 1 ELSE 0 END AS bit) AS CanRestore "
            f"FROM ({inner}) r")


def _resolved(session: Session, scope: Scope, level: Level, record_id: int | None = None) -> dict[int, dict]:
    where = " AND q.RecordId = :r" if record_id is not None else ""
    params = {"sid": scope.scenario_id, "base": scope.base_id, "l": level.name, **({"r": record_id} if record_id is not None else {})}
    found = session.execute(sa.text(f"SELECT q.* FROM ({resolved_sql()}) q WHERE q.[Level] = :l{where}"), params).mappings()
    return {int(r["RecordId"]): dict(r) for r in found}


# --- geçerli öncelik: hiyerarşi ---------------------------------------------------------------------------------------------------------

def _entered(level: str, sid: str, base: str) -> str:
    return f"(SELECT q.RecordId, q.[{FIELD}] FROM ({resolved_sql(sid, base)}) q WHERE q.[Level] = N'{level}' AND q.[{FIELD}] IS NOT NULL)"


def _erp(alias: str) -> str:
    """ERP önceliği yalnız 1–5 aralığındaysa kullanılır (K-195)."""
    return f"CASE WHEN {alias}.Priority BETWEEN 1 AND {LOWEST} THEN {alias}.Priority END"


def _levels(sid: str, base: str, own: bool) -> str:
    """Sipariş (ya da tahmin) satırı `s` için düzey değerleri: proje ve müşterinin girilen değeri, yoksa ERP önceliği."""
    joins = (f"LEFT JOIN core.Project pr ON pr.Id = s.ProjectId AND pr.VersionTo IS NULL LEFT JOIN {_entered(PROJECT, sid, base)} pp ON pp.RecordId = s.ProjectId "
             f"LEFT JOIN core.Customer cu ON cu.Id = s.CustomerId AND cu.VersionTo IS NULL LEFT JOIN {_entered(CUSTOMER, sid, base)} pc ON pc.RecordId = s.CustomerId ")
    values = f"COALESCE(pp.[{FIELD}], {_erp('pr')}) AS proj, COALESCE(pc.[{FIELD}], {_erp('cu')}) AS cust"
    if own:
        joins = f"LEFT JOIN {_entered(ORDER, sid, base)} po ON po.RecordId = s.Id " + joins
        values = f"COALESCE(po.[{FIELD}], {_erp('s')}) AS own, " + values
    return f"{joins}CROSS APPLY (SELECT {values}) v"


def orders_sql(sid: str = ":sid", base: str = ":base") -> str:
    """Güncel sipariş satırlarının önceliği. SELECT: SalesOrderLineId, PriorityGroup (satıra girilen; boş olabilir), EffectivePriorityGroup,
    PrioritySource (Sipariş · Proje · Müşteri · Yok)."""
    return (f"SELECT s.Id AS SalesOrderLineId, po.[{FIELD}] AS [{FIELD}], COALESCE(v.own, v.proj, v.cust, {LOWEST}) AS EffectivePriorityGroup, "
            f"CASE WHEN v.own IS NOT NULL THEN N'{ORDER}' WHEN v.proj IS NOT NULL THEN N'{PROJECT}' WHEN v.cust IS NOT NULL THEN N'{CUSTOMER}' ELSE N'{NONE}' END AS PrioritySource "
            f"FROM core.SalesOrderLine s {_levels(sid, base, own=True)} WHERE s.VersionTo IS NULL")


def forecasts_sql(sid: str = ":sid", base: str = ":base") -> str:
    """Güncel tahmin satırlarının önceliği (kendi düzeyi yok). SELECT: ForecastId, EffectivePriorityGroup, PrioritySource (Proje · Müşteri · Yok)."""
    return (f"SELECT s.Id AS ForecastId, COALESCE(v.proj, v.cust, {LOWEST}) AS EffectivePriorityGroup, "
            f"CASE WHEN v.proj IS NOT NULL THEN N'{PROJECT}' WHEN v.cust IS NOT NULL THEN N'{CUSTOMER}' ELSE N'{NONE}' END AS PrioritySource "
            f"FROM core.Forecast s {_levels(sid, base, own=False)} WHERE s.VersionTo IS NULL")


def demand_priorities(session: Session, scenario_id: int) -> dict:
    """Motor arayüzü (docs/09): {orders: [{SalesOrderLineId, PriorityGroup, Source}], forecasts: [{ForecastId, PriorityGroup, Source}]}; sipariş
    satırında yalnız açık satırlar (açık miktarı sıfırdan büyük). Ekrandaki "Geçerli öncelik grubu" ve "Öncelik kaynağı" ile aynı hesap."""
    scenario = cache.scenario_row(session, scenario_id)
    params = {"sid": scenario_id, "base": cache.base_of(session, scenario)}
    orders = session.execute(sa.text(f"SELECT z.SalesOrderLineId, z.EffectivePriorityGroup, z.PrioritySource FROM ({orders_sql()}) z "
                                     "JOIN core.SalesOrderLine o ON o.Id = z.SalesOrderLineId AND o.VersionTo IS NULL AND o.OpenQuantity > 0 ORDER BY z.SalesOrderLineId"), params).all()
    forecasts = session.execute(sa.text(f"SELECT z.ForecastId, z.EffectivePriorityGroup, z.PrioritySource FROM ({forecasts_sql()}) z ORDER BY z.ForecastId"), params).all()
    return {"orders": [{"SalesOrderLineId": int(r[0]), "PriorityGroup": int(r[1]), "Source": r[2]} for r in orders],
            "forecasts": [{"ForecastId": int(r[0]), "PriorityGroup": int(r[1]), "Source": r[2]} for r in forecasts]}


# --- değer: okuma ve yazım ---------------------------------------------------------------------------------------------------------------

def parse(value) -> tuple[int | None, str | None]:
    """Hücreye yazılan değer: boş → kaldır; 1–5 arası tam sayı."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None, None
    if isinstance(value, bool):
        return None, PROBLEM
    try:
        text = str(value).strip()
        number = int(text) if not isinstance(value, float) else (int(value) if value == int(value) else None)
    except (TypeError, ValueError):
        return None, PROBLEM
    return (number, None) if number in GROUPS else (None, PROBLEM)


def show(value) -> str | None:
    return None if value is None else str(int(value))


def _records(session: Session, level: Level, ids: list[int]) -> dict[int, str]:
    """Güncel kayıtlar: kimlik → okunur ad (müşteri ve proje kodu; sipariş "SO-1001 / 1")."""
    if not ids:
        return {}
    found = session.execute(sa.text(f"SELECT x.Id, {level.code} FROM core.[{level.table}] x WHERE x.VersionTo IS NULL AND x.Id IN (SELECT CAST(value AS bigint) FROM OPENJSON(:ids))"),
                            {"ids": "[" + ",".join(str(int(i)) for i in ids) + "]"})
    return {int(r[0]): str(r[1]) for r in found}


# --- yazma -------------------------------------------------------------------------------------------------------------------------------

def _insert(session: Session, scenario_id: int, values: dict, user_id: int | None) -> int:
    names = list(values)
    sql = (f"INSERT INTO param.[{TABLE}] (ScenarioDefinitionId, {', '.join(f'[{n}]' for n in names)}, UpdatedAt, UpdatedBy) OUTPUT inserted.Id "
           f"VALUES (:sid, {', '.join(':' + n for n in names)}, SYSUTCDATETIME(), :uid)")
    return session.execute(sa.text(sql), {"sid": scenario_id, "uid": user_id, **values}).scalar_one()


def _update(session: Session, row_id: int, values: dict, user_id: int | None) -> None:
    sets = ", ".join(f"[{n}] = :{n}" for n in values)
    session.execute(sa.text(f"UPDATE param.[{TABLE}] SET {sets}, UpdatedAt = SYSUTCDATETIME(), UpdatedBy = :uid WHERE Id = :id"), {"id": row_id, "uid": user_id, **values})


def _clear(session: Session, scenario_id: int, level: Level, record_id: int, keep: int | None = None) -> None:
    """Senaryoda kaydın satırlarını (kendi ve fark) siler; `keep` kalır. Baz satırı siliniyorsa izleyen senaryoların ona bağlı farkları önce kendi
    satırına döner (boş fark silinir): fark, Baz satırı olmadan anlamsızdır."""
    doomed = [int(r[0]) for r in session.execute(sa.text(
        f"SELECT Id FROM param.[{TABLE}] WHERE ScenarioDefinitionId = :s AND [Level] = :l AND RecordId = :r AND BaseRowId IS NULL AND (:k IS NULL OR Id <> :k)"),
        {"s": scenario_id, "l": level.name, "r": record_id, "k": keep})]
    for row_id in doomed:
        session.execute(sa.text(f"DELETE FROM param.[{TABLE}] WHERE BaseRowId = :b AND [{FIELD}] IS NULL"), {"b": row_id})
        session.execute(sa.text(f"UPDATE param.[{TABLE}] SET BaseRowId = NULL, OverriddenFields = NULL WHERE BaseRowId = :b"), {"b": row_id})
    session.execute(sa.text(f"DELETE FROM param.[{TABLE}] WHERE ScenarioDefinitionId = :s AND [Level] = :l AND RecordId = :r AND (:k IS NULL OR Id <> :k)"),
                    {"s": scenario_id, "l": level.name, "r": record_id, "k": keep})


def _store(session: Session, scope: Scope, level: Level, record_id: int, row: dict | None, value: int | None, user_id: int | None) -> None:
    """Kaydın senaryodaki değerini yazar: kayıt başına tek satır kalır. row: kaydın çözümlenmiş satırı (yoksa None)."""
    base_id = row["BaseId"] if row and scope.base_id is not None else None
    key = {"Level": level.name, "RecordId": record_id}
    if base_id is None:                                                       # senaryonun kendi satırı
        keep = row["OwnId"] if row else None
        if value is None:
            _clear(session, scope.scenario_id, level, record_id)
        elif keep is not None:
            _update(session, keep, {FIELD: value, "BaseRowId": None, "OverriddenFields": None}, user_id)
            _clear(session, scope.scenario_id, level, record_id, keep)
        else:
            _clear(session, scope.scenario_id, level, record_id)
            _insert(session, scope.scenario_id, {**key, FIELD: value}, user_id)
        return
    if value == row[f"Base{FIELD}"]:                                          # Baz'daki değere dönüldü: fark kalkar
        _clear(session, scope.scenario_id, level, record_id)
        return
    values = {**key, FIELD: value, "IsValid": 1, "BaseRowId": base_id, "OverriddenFields": f",{FIELD},"}   # value boş olabilir: Baz değeri bu senaryoda kaldırıldı
    keep = row["DiffId"] or row["OwnId"]                                     # kendi satırı varsa o satır fark satırına çevrilir
    if keep is not None:
        _update(session, keep, values, user_id)
        _clear(session, scope.scenario_id, level, record_id, keep)
    else:
        _insert(session, scope.scenario_id, values, user_id)


def change(session: Session, scope: Scope, level: Level, user_id: int | None, changes: list[dict]) -> dict:
    """Hücre değişiklikleri (kimlik: müşteri, proje ya da sipariş satırı): hepsi ya da hiçbiri. Dönen: {saved, events: [{label, old, new}]}."""
    wanted: dict[int, object] = {}
    problems: list[dict] = []
    for c in changes:
        record_id = int(c["id"])
        if c["field"] != FIELD:
            problems.append({"id": record_id, "field": c["field"], "record": str(record_id), "problem": "Bu alan düzenlenemez."})
            continue
        wanted[record_id] = c.get("value")
    names = _records(session, level, list(wanted))
    rows = _resolved(session, scope, level)
    plans = []
    for record_id, raw in wanted.items():
        label = f"{level.name} {names[record_id]}" if record_id in names else str(record_id)
        if record_id not in names:
            problems.append({"id": record_id, "field": FIELD, "record": label, "problem": "Kayıt güncel veride yok."})
            continue
        value, problem = parse(raw)
        if problem:
            problems.append({"id": record_id, "field": FIELD, "record": label, "problem": problem})
            continue
        row = rows.get(record_id)
        plans.append((record_id, label, row, row[FIELD] if row else None, value))
    for p in problems:
        if p["record"].isdigit() and int(p["record"]) in names:
            p["record"] = f"{level.name} {names[int(p['record'])]}"
    if problems:
        raise PriorityError(problems)
    events, saved = [], 0
    for record_id, label, row, before, value in plans:
        if before == value:
            continue
        _store(session, scope, level, record_id, row, value, user_id)
        history.record(session, TABLE, scope.history_key(level, record_id), FIELD, show(before), show(value), SOURCE, user_id, note=scope.note)
        events.append({"label": label, "old": {FIELD: show(before)}, "new": {FIELD: show(value)}})
        saved += 1
    return {"saved": saved, "events": events}


def restore(session: Session, scope: Scope, level: Level, user_id: int | None, record_id: int) -> dict:
    """Senaryonun değerini kaldırır (Baz'ı izleyen senaryoda): kaydın fark satırı ve kendi satırı silinir; değer Baz'a döner, Baz'da yoksa boşalır."""
    row = _resolved(session, scope, level, record_id).get(record_id)
    if scope.base_id is None or row is None or not row["CanRestore"]:
        raise PriorityError(code="no_difference", message="Bu kayıtta senaryo farkı yok.", status=409)
    name = _records(session, level, [record_id]).get(record_id)
    label = f"{level.name} {name}" if name else str(record_id)
    history.record(session, TABLE, scope.history_key(level, record_id), FIELD, show(row[FIELD]), show(row[f"Base{FIELD}"]), SOURCE, user_id, note=scope.note)
    _clear(session, scope.scenario_id, level, record_id)
    return {"label": label, "old": {FIELD: show(row[FIELD])}, "new": {FIELD: show(row[f"Base{FIELD}"])}}
