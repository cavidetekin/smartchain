"""Model kısıtları (K-189; ekran 31, fonksiyon 103): kaynak grubunun kısıtsız kapasite çarpanı ve hedef doluluğu.

Kaynak grubu başına, tarihsiz iki değer; senaryo bazlı, Baz + fark (K-176). Kapasite girişlerinden farkı: kayıt bağımsız bir satır değil, grubun
tek değeridir. Bu yüzden çözümleme kimliğe göre değil gruba göre yapılır (`resolved_sql`): **her senaryoda her grup tek satırdır.**

- Baz'da ve Baz'ı izlemeyen senaryoda değer senaryonun kendi satırındadır.
- Baz'ı izleyen senaryoda: Baz'da değeri olan grupta değişiklik fark satırına yazılır (yalnız değişen alan `OverriddenFields`'ta); Baz'da değeri
  olmayan grupta senaryonun kendi satırına. Grubun hem senaryonun kendi satırı hem Baz satırı varsa (önce senaryoda, sonra Baz'da girildiyse)
  senaryonun değeri geçerlidir ve fark sayılır; veri de buna çevrilir (`normalize`: kendi satırı Baz satırının fark satırı olur).
- Baz satırı silinince (iki değeri de boşalınca) izleyen senaryonun farkı kendi satırına döner (yalnız değiştirdiği alanlarla).
- İki değeri de boş kalan kendi satırı silinir; Baz'daki değere dönen fark kalkar.

Değer bütün gruplara girilebilir; motor yalnız kritik ve güncel grupların değerini okur (`constraints`, `PlanningData.model_constraints`, docs/09).

Her değişiklik aynı veritabanı işleminde alan geçmişini yazar (`adm.FieldChange`; kayıt anahtarı kaynak grubunun kimliği, Baz dışındaki
senaryoda "<kimlik>@<senaryo>": kayıt silinip yeniden yazılsa da geçmiş kopmaz). Commit ve denetim izi çağırandadır.
"""
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app import history
from app.periods import cache

TABLE = "ResourceGroupConstraint"
SOURCE = "Model kısıtları"                         # adm.FieldChange.Source
FACTOR, TARGET = "UnconstrainedCapacityFactor", "TargetUtilizationPct"
FIELDS = (FACTOR, TARGET)
LABELS = {FACTOR: "Kısıtsız kapasite çarpanı", TARGET: "Hedef doluluk (%)"}
DECIMALS = {FACTOR: 2, TARGET: 2}
PROBLEMS = {FACTOR: "En az 1 olmalı.", TARGET: "0'dan büyük, en çok 100 olmalı."}
BASE, DIFF, OWN = "Baz", "Senaryo farkı", "Senaryo"   # "Kaynağı" (app/params/resolve.py ile aynı adlar)


class ConstraintError(Exception):
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
        """Geçmişteki not: Baz dışındaki senaryoda senaryonun adı (FieldChange'te senaryo kolonu yok)."""
        return None if self.is_base else self.scenario_name[:100]

    def history_key(self, group_id: int) -> str:
        return str(group_id) if self.is_base else f"{group_id}@{self.scenario_id}"


def scope_of(session: Session, scenario: dict) -> Scope:
    return Scope(scenario["Id"], scenario["Name"], cache.base_of(session, scenario), bool(scenario["IsBase"]))


# --- çözümleme: senaryo + grup başına tek satır ------------------------------------------------------------------------------------------

def _differs(a: str, b: str) -> str:
    return f"(({a} IS NULL AND {b} IS NOT NULL) OR ({a} IS NOT NULL AND {b} IS NULL) OR {a} <> {b})"


def resolved_sql(sid: str = ":sid", base: str = ":base") -> str:
    """Senaryonun geçerli değerleri, kaynak grubu başına tek satır (SELECT metni). Parametreler: senaryo ve okuduğu Baz (Baz'da ve izlemeyen
    senaryoda NULL). Kolonlar: ResourceGroupId, BaseId (Baz satırı), OwnId (senaryonun kendi satırı), DiffId (fark satırı), iki değer, Baz'daki
    iki değer (`Base…`), Origin (Baz · Senaryo farkı · Senaryo), OverriddenFields (Baz'dan farklı alanlar), BaseValues (JSON; yalnız farkta),
    CanRestore (Baz'ı izleyen senaryoda değer senaryodan geliyor: "Senaryo farkını kaldır").

    Öncelik: senaryonun kendi satırı > fark satırının değiştirdiği alan > Baz. Aynı grupta birden fazla satır kalmışsa en son yazılan alınır."""
    t = f"param.[{TABLE}]"
    latest = "ROW_NUMBER() OVER (PARTITION BY x.ResourceGroupId ORDER BY x.Id DESC) AS rn"
    b = f"(SELECT x.*, {latest} FROM {t} x WHERE x.ScenarioDefinitionId = {base} AND x.BaseRowId IS NULL)"
    o = f"(SELECT x.*, {latest} FROM {t} x WHERE x.ScenarioDefinitionId = {sid} AND x.BaseRowId IS NULL)"
    d = f"(SELECT x.*, ROW_NUMBER() OVER (PARTITION BY x.BaseRowId ORDER BY x.Id DESC) AS rn FROM {t} x WHERE x.ScenarioDefinitionId = {sid} AND x.BaseRowId IS NOT NULL)"

    def value(f: str) -> str:
        return f"CASE WHEN o.Id IS NOT NULL THEN o.[{f}] WHEN d.Id IS NOT NULL AND d.OverriddenFields LIKE N'%,{f},%' THEN d.[{f}] ELSE b.[{f}] END"
    inner = (f"SELECT COALESCE(b.ResourceGroupId, o.ResourceGroupId) AS ResourceGroupId, b.Id AS BaseId, o.Id AS OwnId, d.Id AS DiffId, "
             f"{', '.join(f'{value(f)} AS [{f}]' for f in FIELDS)}, {', '.join(f'b.[{f}] AS [Base{f}]' for f in FIELDS)} "
             f"FROM (SELECT * FROM {b} b0 WHERE b0.rn = 1) b FULL JOIN (SELECT * FROM {o} o0 WHERE o0.rn = 1) o ON o.ResourceGroupId = b.ResourceGroupId "
             f"LEFT JOIN (SELECT * FROM {d} d0 WHERE d0.rn = 1) d ON d.BaseRowId = b.Id")
    changed = {f: _differs(f"r.[{f}]", f"r.[Base{f}]") for f in FIELDS}
    any_changed = " OR ".join(changed.values())
    fields = " + ".join(f"CASE WHEN {changed[f]} THEN N'{f},' ELSE N'' END" for f in FIELDS)
    json = " + N',' + ".join(f"N'\"{f}\":' + COALESCE(CAST(CAST(r.[Base{f}] AS float) AS nvarchar(40)), N'null')" for f in FIELDS)
    return (f"SELECT r.*, CASE WHEN r.BaseId IS NULL THEN N'{OWN}' WHEN {any_changed} THEN N'{DIFF}' ELSE N'{BASE}' END AS Origin, "
            f"CASE WHEN r.BaseId IS NOT NULL AND ({any_changed}) THEN N',' + {fields} END AS OverriddenFields, "
            f"CASE WHEN r.BaseId IS NOT NULL AND ({any_changed}) THEN N'{{' + {json} + N'}}' END AS BaseValues, "
            f"CAST(CASE WHEN {base} IS NOT NULL AND (r.BaseId IS NULL OR ({any_changed})) THEN 1 ELSE 0 END AS bit) AS CanRestore "
            f"FROM ({inner}) r")


def _resolved(session: Session, scope: Scope, group_id: int | None = None) -> dict[int, dict]:
    where = " WHERE q.ResourceGroupId = :g" if group_id is not None else ""
    params = {"sid": scope.scenario_id, "base": scope.base_id, **({"g": group_id} if group_id is not None else {})}
    return {int(r["ResourceGroupId"]): dict(r) for r in session.execute(sa.text(f"SELECT q.* FROM ({resolved_sql()}) q{where}"), params).mappings()}


# --- değerler: okuma ve yazım ------------------------------------------------------------------------------------------------------------

def parse(field: str, value) -> tuple[Decimal | None, str | None]:
    """Hücreye yazılan değer: boş → kaldır; sayı (ondalık virgül ya da nokta, yüzde işareti kabul edilir), iki ondalığa yuvarlanır."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None, None
    try:
        text = str(value).strip().replace("%", "").replace(" ", "")
        if "," in text:
            text = text.replace(".", "").replace(",", ".")
        number = Decimal(text)
    except (InvalidOperation, ValueError):
        return None, "Sayı olmalı."
    if not number.is_finite():
        return None, "Sayı olmalı."
    number = number.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if field == FACTOR and number < 1:
        return None, PROBLEMS[FACTOR]
    if field == TARGET and not (Decimal(0) < number <= Decimal(100)):
        return None, PROBLEMS[TARGET]
    if field == FACTOR and number >= Decimal(100000):
        return None, "Çok büyük."
    return number, None


def show(field: str, value) -> str | None:
    """Geçmiş ve denetim izindeki yazım: çarpan "1,50"; hedef doluluk "%85" (gereksiz ondalık yazılmaz)."""
    if value is None:
        return None
    number = Decimal(str(value))
    if field == TARGET:
        text = f"{number.normalize():f}" if number != number.to_integral() else str(int(number))
        return "%" + text.replace(".", ",")
    return f"{number:.2f}".replace(".", ",")


def _same(a, b) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return Decimal(str(a)) == Decimal(str(b))


def _groups(session: Session, ids: list[int]) -> dict[int, dict]:
    """Güncel kaynak grupları: kod."""
    if not ids:
        return {}
    found = session.execute(sa.text("SELECT Id, Code FROM core.ResourceGroup WHERE VersionTo IS NULL AND Id IN (SELECT CAST(value AS bigint) FROM OPENJSON(:ids))"),
                            {"ids": "[" + ",".join(str(int(i)) for i in ids) + "]"}).mappings()
    return {int(r["Id"]): dict(r) for r in found}


# --- yazma -------------------------------------------------------------------------------------------------------------------------------

def _insert(session: Session, scenario_id: int, values: dict, user_id: int | None) -> int:
    names = list(values)
    sql = (f"INSERT INTO param.[{TABLE}] (ScenarioDefinitionId, {', '.join(f'[{n}]' for n in names)}, UpdatedAt, UpdatedBy) OUTPUT inserted.Id "
           f"VALUES (:sid, {', '.join(':' + n for n in names)}, SYSUTCDATETIME(), :uid)")
    return session.execute(sa.text(sql), {"sid": scenario_id, "uid": user_id, **values}).scalar_one()


def _update(session: Session, row_id: int, values: dict, user_id: int | None) -> None:
    sets = ", ".join(f"[{n}] = :{n}" for n in values)
    session.execute(sa.text(f"UPDATE param.[{TABLE}] SET {sets}, UpdatedAt = SYSUTCDATETIME(), UpdatedBy = :uid WHERE Id = :id"), {"id": row_id, "uid": user_id, **values})


def _delete(session: Session, *row_ids: int | None) -> None:
    for row_id in row_ids:
        if row_id is not None:
            session.execute(sa.text(f"DELETE FROM param.[{TABLE}] WHERE Id = :id"), {"id": row_id})


def _clear_group(session: Session, scenario_id: int, group_id: int, keep: int | None = None) -> None:
    """Senaryoda grubun satırlarını (kendi ve fark; eskiden kalmış çift kayıtlar dahil) siler; `keep` kalır."""
    session.execute(sa.text(f"DELETE FROM param.[{TABLE}] WHERE ScenarioDefinitionId = :s AND ResourceGroupId = :g AND (:k IS NULL OR Id <> :k)"),
                    {"s": scenario_id, "g": group_id, "k": keep})


def _store(session: Session, scenario_id: int, follows: bool, group_id: int, row: dict | None, after: dict, user_id: int | None) -> None:
    """Grubun senaryodaki değerini yazar: grup başına tek satır kalır. row: grubun çözümlenmiş satırı (yoksa None); after: iki alanın yeni değeri.
    follows: senaryo Baz'ı izliyor (Baz satırı varsa değer fark olarak tutulur)."""
    base_id = row["BaseId"] if row and follows else None
    if base_id is None:                                                       # senaryonun kendi satırı
        keep = row["OwnId"] if row else None
        if all(after[f] is None for f in FIELDS):
            _clear_group(session, scenario_id, group_id)
        elif keep is not None:
            _update(session, keep, {**after, "BaseRowId": None, "OverriddenFields": None}, user_id)
            _clear_group(session, scenario_id, group_id, keep)
        else:
            _clear_group(session, scenario_id, group_id)
            _insert(session, scenario_id, {"ResourceGroupId": group_id, **after}, user_id)
        return
    overridden = [f for f in FIELDS if not _same(after[f], row[f"Base{f}"])]   # Baz'daki değere dönen alan farktan çıkar
    if not overridden:
        _clear_group(session, scenario_id, group_id)
        return
    values = {"ResourceGroupId": group_id, **{f: after[f] for f in FIELDS}, "IsValid": 1, "BaseRowId": base_id, "OverriddenFields": "," + ",".join(overridden) + ","}
    keep = row["DiffId"] or row["OwnId"]                                     # kendi satırı varsa o satır fark satırına çevrilir
    if keep is not None:
        _update(session, keep, values, user_id)
        _clear_group(session, scenario_id, group_id, keep)
    else:
        _insert(session, scenario_id, values, user_id)


def _followers(session: Session) -> list[int]:
    return [int(r[0]) for r in session.execute(sa.text("SELECT Id FROM param.ScenarioDefinition WHERE FollowsBase = 1 AND COALESCE(IsBase, 0) = 0"))]


def normalize(session: Session, scenario_ids: list[int] | None = None) -> int:
    """Veriyi "senaryo + grup başına tek satır" kuralına getirir (K-189); geçerli değerler değişmez. Baz'ı izleyen senaryolarda: grubun hem kendi
    satırı hem Baz satırı varsa kendi satırı Baz satırının farkına çevrilir (fark kalmıyorsa silinir); Baz satırı silinmiş fark satırı senaryonun
    kendi satırına döner (yalnız değiştirdiği alanlarla; hepsi boşsa silinir); aynı grupta kalmış eski çift satırlar teke iner. Baz'da ve
    izlemeyen senaryolarda çift satırlar teke iner. Dönen: düzeltilen grup sayısı. scenario_ids: None ise bütün senaryolar."""
    base = cache.base_id(session)
    followers = set(_followers(session))
    wanted = scenario_ids if scenario_ids is not None else [int(r[0]) for r in session.execute(sa.text("SELECT Id FROM param.ScenarioDefinition"))]
    fixed = 0
    for sid in wanted:
        follows = sid in followers and base is not None
        # Baz satırı silinmiş fark satırları: senaryonun kendi satırına döner
        orphans = session.execute(sa.text(
            f"SELECT d.* FROM param.[{TABLE}] d WHERE d.ScenarioDefinitionId = :s AND d.BaseRowId IS NOT NULL "
            f"AND NOT EXISTS (SELECT 1 FROM param.[{TABLE}] b WHERE b.Id = d.BaseRowId AND b.ScenarioDefinitionId = :b AND b.BaseRowId IS NULL)"),
            {"s": sid, "b": base if follows else -1}).mappings().all()
        for d in orphans:
            mine = {f: (d[f] if f",{f}," in (d["OverriddenFields"] or "") else None) for f in FIELDS}
            if all(v is None for v in mine.values()):
                _delete(session, d["Id"])
            else:
                _update(session, d["Id"], {**mine, "BaseRowId": None, "OverriddenFields": None}, d["UpdatedBy"])
            fixed += 1
        scope = Scope(sid, "", base if follows else None, sid == base)
        counts = {int(r[0]): int(r[1]) for r in session.execute(sa.text(
            f"SELECT ResourceGroupId, COUNT(*) FROM param.[{TABLE}] WHERE ScenarioDefinitionId = :s GROUP BY ResourceGroupId"), {"s": sid})}
        for group_id, row in _resolved(session, scope).items():
            double = counts.get(group_id, 0) > 1
            mixed = follows and row["BaseId"] is not None and row["OwnId"] is not None      # kendi satırı + Baz satırı: fark satırına çevrilir
            if not (double or mixed):
                continue
            stored = session.execute(sa.text(f"SELECT TOP 1 UpdatedBy FROM param.[{TABLE}] WHERE Id = :i"), {"i": row["OwnId"] or row["DiffId"]}).scalar()
            _store(session, sid, follows, group_id, row, {f: row[f] for f in FIELDS}, stored)
            fixed += 1
    return fixed


def change(session: Session, scope: Scope, user_id: int | None, changes: list[dict]) -> dict:
    """Hücre değişiklikleri (kimlik: kaynak grubu): hepsi ya da hiçbiri. Dönen: {saved, events: [{label, old, new}]}."""
    normalize(session, [scope.scenario_id])                                  # eskiden kalmış çift kayıtlar önce birleşir
    by_group: dict[int, dict] = {}
    for c in changes:
        by_group.setdefault(int(c["id"]), {})[c["field"]] = c.get("value")
    groups = _groups(session, list(by_group))
    rows = _resolved(session, scope)
    problems: list[dict] = []
    plans = []
    for group_id, fields in by_group.items():
        group = groups.get(group_id)
        label = f"Kaynak grubu {group['Code']}" if group else str(group_id)
        if group is None:
            problems += [{"id": group_id, "field": name, "record": label, "problem": "Kaynak grubu güncel veride yok."} for name in fields]
            continue
        row = rows.get(group_id)
        before = {f: (row[f] if row else None) for f in FIELDS}
        after = dict(before)
        for name, value in fields.items():
            if name not in FIELDS:
                problems.append({"id": group_id, "field": name, "record": label, "problem": "Bu alan düzenlenemez."})
                continue
            new, problem = parse(name, value)
            if problem:
                problems.append({"id": group_id, "field": name, "record": label, "problem": problem})
            else:
                after[name] = new
        plans.append((group_id, label, row, before, after))
    if problems:
        raise ConstraintError(problems)
    events, saved = [], 0
    follows = scope.base_id is not None
    for group_id, label, row, before, after in plans:
        delta = [f for f in FIELDS if not _same(before[f], after[f])]
        if not delta:
            continue
        _store(session, scope.scenario_id, follows, group_id, row, after, user_id)
        for name in delta:
            history.record(session, TABLE, scope.history_key(group_id), name, show(name, before[name]), show(name, after[name]), SOURCE, user_id, note=scope.note)
        events.append({"label": label, "old": {n: show(n, before[n]) for n in delta}, "new": {n: show(n, after[n]) for n in delta}})
        saved += len(delta)
    if scope.is_base and saved:
        # Baz'a değer girildi ya da Baz'dan silindi: izleyen senaryoların o gruptaki kendi satırları farka çevrilir, Baz'ı kalmayan farklar kendi satırına döner
        normalize(session, _followers(session))
    return {"saved": saved, "events": events}


def restore(session: Session, scope: Scope, user_id: int | None, group_id: int) -> dict:
    """Senaryonun değerini kaldırır (Baz'ı izleyen senaryoda): grubun fark satırı ve kendi satırı silinir; değerler Baz'a döner, Baz'da değer yoksa boşalır."""
    normalize(session, [scope.scenario_id])
    row = _resolved(session, scope, group_id).get(group_id)
    if scope.base_id is None or row is None or not row["CanRestore"]:
        raise ConstraintError(code="no_difference", message="Bu kayıtta senaryo farkı yok.", status=409)
    group = _groups(session, [group_id]).get(group_id)
    label = f"Kaynak grubu {group['Code']}" if group else str(group_id)
    changed = [f for f in FIELDS if not _same(row[f], row[f"Base{f}"])]
    for name in changed:
        history.record(session, TABLE, scope.history_key(group_id), name, show(name, row[name]), show(name, row[f"Base{name}"]), SOURCE, user_id, note=scope.note)
    _clear_group(session, scope.scenario_id, group_id)
    return {"label": label, "old": {n: show(n, row[n]) for n in changed}, "new": {n: show(n, row[f"Base{n}"]) for n in changed}}


def constraints(session: Session, scenario_id: int) -> list[dict]:
    """Motorun okuduğu değerler (docs/09): senaryoda geçerli, en az bir değeri dolu, kritik ve güncel kaynak grupları. Kritik olmayan grubun saklı
    değeri dönmez."""
    scenario = cache.scenario_row(session, scenario_id)
    sql = (f"SELECT x.ResourceGroupId, x.[{FACTOR}], x.[{TARGET}] FROM ({resolved_sql()}) x "
           "JOIN core.ResourceGroup g ON g.Id = x.ResourceGroupId AND g.VersionTo IS NULL AND g.IsCritical = 1 "
           f"WHERE x.[{FACTOR}] IS NOT NULL OR x.[{TARGET}] IS NOT NULL ORDER BY x.ResourceGroupId")
    found = session.execute(sa.text(sql), {"sid": scenario_id, "base": cache.base_of(session, scenario)}).mappings()
    return [{"ResourceGroupId": int(r["ResourceGroupId"]), FACTOR: r[FACTOR], TARGET: r[TARGET]} for r in found]
