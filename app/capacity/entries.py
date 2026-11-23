"""Kapasite girişlerinin yazılması (K-185, 7.9b): çalışma düzeni, verimlilik, ek mesai limiti, bakım ve duruş, fabrika takvimi.

Senaryo (K-176): Baz'da ve Baz'ı izlemeyen senaryoda satır yerinde yazılır. Baz'ı izleyen senaryoda Baz satırındaki değişiklik fark satırına
yazılır: yalnız değişen alanlar `OverriddenFields`'ta durur; değer Baz'dakine dönerse alan farktan çıkar, fark kalmazsa satır silinir. Baz satırı
izleyen senaryodan silinmez: o senaryo için geçersiz yapılır (`IsValid`).

Giriş altyapısı ortaktır (K-191): "sahip" tanımı (`Owner`) parametrelidir. Kapasite girişlerinde sahip kaynak grubu ya da kaynaktır; tedarikçi
limitinde lokasyon, tedarikçi ve malzeme (`app/supplierlimits`), malzeme blokajında lokasyon ve malzeme (`app/materialholds`). Senaryo çakışması (aynı sahip ve başlangıç için hem senaryonun hem Baz'ın kaydı)
çözümleme katmanındadır (`resolve.KEYS`): senaryonun kendi satırı Baz satırını örter ve burada kendi satırı gibi yazılır; "Senaryo farkını kaldır"
onu siler.

Her işlem aynı veritabanı işleminde alan geçmişini (`adm.FieldChange`) yazar ve kapasite önbelleğinin yalnız etkilenen kaynak ve günlerini
yeniler (`triggers`). Commit ve denetim izi çağırandadır (`app/api/services/capacity.py`). Doğrulama hatası `EntryError` (alan, neden).
"""
from collections.abc import Callable
from dataclasses import dataclass, field as dataclass_field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app import history
from app.params import resolve
from app.periods import cache

from . import triggers

SOURCE = "Kapasite yönetimi"                       # adm.FieldChange.Source
DAY_TEXT = {Decimal("1"): "Tam", Decimal("0.5"): "Yarım", Decimal("0"): "—"}
DAY_WORDS = {"tam": Decimal("1"), "yarım": Decimal("0.5"), "çalışılmıyor": Decimal("0"), "—": Decimal("0"), "-": Decimal("0"), "": Decimal("0")}
DAY_VALUE_TEXT = {Decimal("0"): "Çalışılmıyor", Decimal("0.5"): "Yarım gün"}
DAY_VALUE_WORDS = {"çalışılmıyor": Decimal("0"), "yarım gün": Decimal("0.5"), "yarım": Decimal("0.5")}
DOWNTIME_TYPES = ("Planlı bakım", "Arıza", "Diğer")
DAY_LABELS = dict(zip(resolve.DAYS, ("Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz")))
OWNER = ("ResourceGroupId", "ResourceId")
LOCKED = "Seviye ve kod kayıttan sonra değişmez; kaydı silip yeniden girin."


@dataclass(frozen=True)
class Field:
    name: str
    label: str
    kind: str                 # date · number · day · day_value · choice · text
    required: bool = True
    decimals: int = 4
    max_length: int | None = None
    choices: tuple[str, ...] = ()


@dataclass(frozen=True)
class Owner:
    """Kaydın sahibi (K-191): kayıttan sonra değişmeyen alanlar ve onların kuralları."""
    fields: tuple[str, ...]                                   # sahip kolonları
    check: Callable[[Session, dict], list[dict]]              # seçimi doğrular ve değerleri düzeltir (kimlik tipi, türetilen alan); sorunlar
    label: Callable[[Session, dict], str]                     # kaydın okunur adı ("Grup TORNA", "TED-05 · SAT-003")
    key: Callable[[dict], tuple | None]                       # aynı başlangıç denetiminin anahtarı (None: denetlenmez)
    duplicate: str = "Bu kaynak ya da grup için aynı başlangıç tarihli başka bir kayıt var."
    locked: str = "Seviye ve kod kayıttan sonra değişmez; kaydı silip yeniden girin."
    locked_fields: tuple[str, ...] = ("Level", "Code")        # listede sahibi gösteren, düzenlenemeyen alanlar


@dataclass(frozen=True)
class Kind:
    key: str                  # adresteki ad
    table: str
    title: str                # denetim izinde ve mesajlarda
    fields: tuple[Field, ...]
    owner: Owner | None = None   # sahibi olan giriş (kaynak grubu ya da kaynak; tedarikçi ve malzeme); None: sahipsiz (fabrika takvimi)
    start: str = "ValidFrom"
    end: str = "ValidTo"
    end_required: bool = False
    unique_start: bool = False   # aynı sahip için aynı başlangıçlı ikinci geçerli kayıt olamaz
    fixed: dict = dataclass_field(default_factory=dict)       # türü belirleyen sabit alanlar (aynı tabloda birden çok tür: {"LimitType": "Üst limit"})
    source: str = "Kapasite yönetimi"                         # adm.FieldChange.Source
    rules: Callable[[dict], list[tuple[str, str]]] | None = None   # türün kendi kuralları: [(alan, neden)]
    checks: Callable[[Session, dict], list[tuple[str, str]]] | None = None   # veriye bakan kurallar (K-193: tür malzemenin tedarik biçimine uyar)

    def field(self, name: str) -> Field | None:
        return next((f for f in self.fields if f.name == name), None)

    def matches(self, row: dict) -> bool:
        return all(row.get(k) == v for k, v in self.fixed.items())


_VALIDITY = (Field("ValidFrom", "Başlangıç", "date"), Field("ValidTo", "Bitiş", "date", required=False))
_PERIOD = (Field("StartDate", "Başlangıç", "date"), Field("EndDate", "Bitiş", "date"))
def _resource_check(session: Session, values: dict) -> list[dict]:
    return _owner_problems(session, values)


def _resource_key(row: dict) -> tuple | None:
    level = "ResourceId" if row.get("ResourceId") is not None else "ResourceGroupId"
    return None if row.get(level) is None else (level, row[level])


RESOURCE = Owner(OWNER, _resource_check, lambda session, row: owner_label(session, row), _resource_key)   # kaynak grubu ya da kaynak
KINDS = {k.key: k for k in (
    Kind("work-patterns", "WorkPattern", "Çalışma düzeni",
         (*_VALIDITY, Field("DailyCapacity", "Günlük kapasite", "number"), *[Field(d, DAY_LABELS[d], "day") for d in resolve.DAYS]), RESOURCE, unique_start=True),
    Kind("efficiency", "ResourceEfficiency", "Verimlilik", (*_VALIDITY, Field("EfficiencyPct", "Verimlilik (%)", "number", decimals=2)), RESOURCE, unique_start=True),
    Kind("overtime-limits", "OvertimeLimit", "Ek mesai limiti", (*_VALIDITY, Field("DailyLimit", "Günlük limit", "number")), RESOURCE, unique_start=True),
    Kind("downtime", "ResourceDowntime", "Bakım ve duruş",
         (Field("DowntimeType", "Tip", "choice", choices=DOWNTIME_TYPES), Field("Reason", "Sebep", "text", required=False, max_length=255), *_PERIOD),
         RESOURCE, start="StartDate", end="EndDate", end_required=True),
    Kind("factory-calendar", "FactoryCalendar", "Fabrika takvimi",
         (*_PERIOD, Field("Name", "Ad", "text", max_length=100), Field("DayValue", "Çalışma", "day_value")),
         start="StartDate", end="EndDate", end_required=True),
)}
BY_TABLE = {k.table: k for k in KINDS.values()}


class EntryError(Exception):
    """Doğrulama hatası: problems = [{field, problem, id?, record?}]; code "validation" dışındaysa tek mesajlı iş kuralı (ör. base_row)."""

    def __init__(self, problems: list[dict] | None = None, *, code: str = "validation", message: str = "Girilen bilgiler geçersiz.", status: int = 422):
        super().__init__(message)
        self.problems, self.code, self.message, self.status = problems or [], code, message, status


class NotFound(EntryError):
    def __init__(self) -> None:
        super().__init__(code="not_found", message="Kayıt bulunamadı.", status=404)


# --- değerler: okuma ve yazım ------------------------------------------------------------------------------------------------------------

def _number(text) -> Decimal:
    if isinstance(text, bool):
        raise InvalidOperation
    if isinstance(text, (int, float, Decimal)):
        return Decimal(str(text))
    s = str(text).strip().replace(" ", "")
    if "," in s:                       # Türkçe yazım: 1.234,5
        s = s.replace(".", "").replace(",", ".")
    return Decimal(s)


def parse(f: Field, value) -> tuple[object, str | None]:
    """Ham değer (pencereden tipli, tablodan yazı) → saklanacak değer ve varsa neden."""
    empty = value is None or (isinstance(value, str) and not value.strip())
    if f.kind == "day":
        key = "" if empty else str(value).strip().lower()
        if key in DAY_WORDS:
            return DAY_WORDS[key], None
        try:
            number = _number(value)
        except (InvalidOperation, ValueError):
            number = None
        return (number, None) if number in DAY_TEXT else (None, "Tam, Yarım ya da Çalışılmıyor seçilmeli.")
    if empty:
        return None, "Boş bırakılamaz." if f.required else None
    if f.kind == "date":
        if isinstance(value, datetime):
            return value.date(), None
        if isinstance(value, date):
            return value, None
        text = str(value).strip()
        for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(text[:10], fmt).date(), None
            except ValueError:
                continue
        return None, "Tarih gg.aa.yyyy biçiminde girilmeli."
    if f.kind == "number":
        try:
            number = _number(value)
        except (InvalidOperation, ValueError):
            return None, "Sayı girilmeli."
        if number != round(number, f.decimals):
            return None, f"En çok {f.decimals} ondalık."
        return number, None
    if f.kind == "day_value":
        key = str(value).strip().lower()
        if key in DAY_VALUE_WORDS:
            return DAY_VALUE_WORDS[key], None
        try:
            number = _number(value)
        except (InvalidOperation, ValueError):
            number = None
        return (number, None) if number in DAY_VALUE_TEXT else (None, "Çalışılmıyor ya da Yarım gün seçilmeli.")
    text = str(value).strip()
    if f.kind == "choice":
        return (text, None) if text in f.choices else (None, f"Şunlardan biri olmalı: {', '.join(f.choices)}.")
    if f.max_length and len(text) > f.max_length:
        return None, f"En çok {f.max_length} karakter."
    return text, None


def show(f: Field, value) -> str | None:
    """Geçmişte ve denetim izinde okunur yazım (Türkçe biçim)."""
    if value is None:
        return None
    if f.kind == "date":
        return f"{value:%d.%m.%Y}"
    if f.kind == "day":
        return DAY_TEXT.get(Decimal(str(value)), str(value))
    if f.kind == "day_value":
        return DAY_VALUE_TEXT.get(Decimal(str(value)), str(value))
    if f.kind == "number":
        number = Decimal(str(value))
        text = f"{number:,.{f.decimals}f}".rstrip("0").rstrip(".") if number != number.to_integral() else f"{number:,.0f}"
        return text.replace(",", "X").replace(".", ",").replace("X", ".")
    return str(value)


def _same(a, b) -> bool:
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, (int, float, Decimal)) and isinstance(b, (int, float, Decimal)) and not isinstance(a, bool):
        return Decimal(str(a)) == Decimal(str(b))
    return a == b


# --- okuma -------------------------------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Scope:
    scenario_id: int
    scenario_name: str
    base_id: int | None        # izlediği Baz; Baz'da ve izlemeyen senaryoda None
    is_base: bool

    @property
    def note(self) -> str | None:
        """Geçmişteki not: izleyen senaryodaki değişiklikte senaryonun adı (FieldChange'te senaryo kolonu yok)."""
        return None if self.is_base else self.scenario_name[:100]


def scope_of(session: Session, scenario: dict) -> Scope:
    return Scope(scenario["Id"], scenario["Name"], cache.base_of(session, scenario), bool(scenario["IsBase"]))


def _rows(session: Session, kind: Kind, scope: Scope, row_id: int | None = None) -> list[dict]:
    where = " WHERE x.RowId = :rid" if row_id is not None else ""
    sql = f"SELECT x.* FROM ({resolve.sql(kind.table, valid_only=False, detail=True)}) x{where}"
    params = {"sid": scope.scenario_id, "base": scope.base_id, **({"rid": row_id} if row_id is not None else {})}
    return [r for r in (dict(r) for r in session.execute(sa.text(sql), params).mappings()) if kind.matches(r)]


def is_own(row: dict) -> bool:
    """Senaryonun kendi satırı: yerinde yazılır ve silinir. Aynı anahtarlı Baz satırını örten kendi satırı da böyledir ("Kaynağı" Senaryo farkı
    görünür ama saklanan satır senaryonundur; K-191)."""
    return row["Origin"] == resolve.OWN or row.get("ShadowId") is not None


def _get(session: Session, kind: Kind, scope: Scope, row_id: int) -> dict:
    found = _rows(session, kind, scope, row_id) if row_id > 0 else []      # negatif kimlik: ERP satırı (çalışan izni), salt okunur
    if not found:
        raise NotFound()
    return found[0]


def history_key(scope: "Scope", row: dict) -> str:
    """Geçmişin kayıt anahtarı (`adm.FieldChange.RecordKey`): satırın kimliği; izleyen senaryonun Baz satırındaki değişikliğinde
    "<kimlik>@<senaryo>" (FieldChange'te senaryo kolonu yok; fark kaldırılsa da geçmişi durur, Baz'ın geçmişine karışmaz)."""
    return str(row["RowId"]) if is_own(row) else f"{row['RowId']}@{scope.scenario_id}"


def _stored(session: Session, kind: Kind, row_id: int) -> dict:
    return dict(session.execute(sa.text(f"SELECT * FROM param.[{kind.table}] WHERE Id = :i"), {"i": row_id}).mappings().one())


def owner_label(session: Session, row: dict) -> str:
    """Kaydın okunur adı: "Grup TORNA" · "Kaynak T-01"; fabrika takviminde ad."""
    if row.get("ResourceId") is not None:
        code = session.execute(sa.text("SELECT TOP 1 Code FROM core.Resource WHERE Id = :i ORDER BY VersionFrom DESC"), {"i": row["ResourceId"]}).scalar()
        return f"Kaynak {code or row['ResourceId']}"
    if row.get("ResourceGroupId") is not None:
        code = session.execute(sa.text("SELECT TOP 1 Code FROM core.ResourceGroup WHERE Id = :i ORDER BY VersionFrom DESC"), {"i": row["ResourceGroupId"]}).scalar()
        return f"Grup {code or row['ResourceGroupId']}"
    return str(row.get("Name") or "")


def record_label(session: Session, kind: Kind, row: dict) -> str:
    start = row.get(kind.start)
    name = kind.owner.label(session, row) if kind.owner else owner_label(session, row)
    return f"{name} · {start:%d.%m.%Y}" if isinstance(start, date) else name


# --- doğrulama -----------------------------------------------------------------------------------------------------------------------------

def _problems(session: Session, kind: Kind, scope: Scope, row: dict, row_id: int | None) -> list[dict]:
    """Satırın (değişiklik uygulanmış hâlinin) kuralları; alan bazında neden."""
    out: list[dict] = []

    def bad(field: str, problem: str) -> None:
        out.append({"field": field, "problem": problem})

    start, end = row.get(kind.start), row.get(kind.end)
    if start is not None and end is not None and end < start:
        bad(kind.end, "Bitiş başlangıçtan önce olamaz.")
    if kind.table == "WorkPattern":
        if row.get("DailyCapacity") is not None and row["DailyCapacity"] <= 0:
            bad("DailyCapacity", "Sıfırdan büyük olmalı.")
        if all((row.get(d) or 0) == 0 for d in resolve.DAYS):
            bad(resolve.DAYS[0], "En az bir gün Tam ya da Yarım olmalı.")
    if kind.table == "ResourceEfficiency" and row.get("EfficiencyPct") is not None and not (0 < row["EfficiencyPct"] <= Decimal("999.99")):
        bad("EfficiencyPct", "0'dan büyük, en çok 999,99 olmalı.")
    if kind.table == "OvertimeLimit" and row.get("DailyLimit") is not None and row["DailyLimit"] < 0:
        bad("DailyLimit", "Negatif olamaz.")
    for name, problem in (kind.rules(row) if kind.rules else ()):
        bad(name, problem)
    for name, problem in (kind.checks(session, row) if kind.checks else ()):
        bad(name, problem)
    if kind.unique_start and kind.owner and start is not None and row.get("IsValid", True):
        key = kind.owner.key(row)
        for other in _rows(session, kind, scope):
            if key is not None and other["RowId"] != row_id and other["IsValid"] and kind.owner.key(other) == key and other[kind.start] == start:
                bad(kind.start, kind.owner.duplicate)
                break
    return out


def _owner_problems(session: Session, values: dict) -> list[dict]:
    group, resource = values.get("ResourceGroupId"), values.get("ResourceId")
    if (group is None) == (resource is None):
        return [{"field": "ResourceGroupId" if resource is None else "ResourceId", "problem": "Kaynak grubu ya da kaynaktan biri seçilmeli."}]
    table, key, field = ("ResourceGroup", group, "ResourceGroupId") if group is not None else ("Resource", resource, "ResourceId")
    try:
        key = int(key)
    except (TypeError, ValueError):
        return [{"field": field, "problem": "Geçersiz seçim."}]
    if session.execute(sa.text(f"SELECT 1 FROM core.[{table}] WHERE Id = :i AND VersionTo IS NULL"), {"i": key}).first() is None:
        return [{"field": field, "problem": "Güncel veride yok."}]
    values[field] = key
    return []


def warnings_of(kind: Kind, row: dict, today: date) -> list[str]:
    end = row.get(kind.end)
    return ["Bitişi geçmişte kalan kayıt."] if isinstance(end, date) and end < today else []


# --- yazma ---------------------------------------------------------------------------------------------------------------------------------

def _range(kind: Kind, row: dict) -> triggers.Range:
    return (row.get(kind.start), row.get(kind.end))


def _refresh(session: Session, kind: Kind, scope: Scope, row: dict, ranges: list[triggers.Range]) -> None:
    """Önbellekte yalnız etkilenen kaynak ve günler (K-184, K-185 F): kaydın eski ve yeni aralığı."""
    if kind.table not in resolve.CAPACITY_TABLES:      # kapasite hesabına girmeyen girişin (tedarikçi limiti) önbelleği yok
        return
    if kind.owner:
        triggers.entry_changed(session, scope.scenario_id, resource_id=row.get("ResourceId"), group_id=row.get("ResourceGroupId"), ranges=ranges)
    else:
        triggers.factory_calendar_changed(session, scope.scenario_id, ranges)


def _insert(session: Session, kind: Kind, scope: Scope, values: dict, user_id: int | None) -> int:
    names = list(values)
    sql = (f"INSERT INTO param.[{kind.table}] (ScenarioDefinitionId, {', '.join(f'[{n}]' for n in names)}, UpdatedAt, UpdatedBy) OUTPUT inserted.Id "
           f"VALUES (:sid, {', '.join(':' + n for n in names)}, SYSUTCDATETIME(), :uid)")
    return session.execute(sa.text(sql), {"sid": scope.scenario_id, "uid": user_id, **values}).scalar_one()


def _update(session: Session, kind: Kind, row_id: int, values: dict, user_id: int | None) -> None:
    sets = ", ".join(f"[{n}] = :{n}" for n in values)
    session.execute(sa.text(f"UPDATE param.[{kind.table}] SET {sets}, UpdatedAt = SYSUTCDATETIME(), UpdatedBy = :uid WHERE Id = :id"),
                    {"id": row_id, "uid": user_id, **values})


def _delete(session: Session, kind: Kind, row_id: int) -> None:
    session.execute(sa.text(f"DELETE FROM param.[{kind.table}] WHERE Id = :id"), {"id": row_id})


def _fields_of(overridden: str | None) -> list[str]:
    return [f for f in (overridden or "").split(",") if f]


def create(session: Session, kind: Kind, scope: Scope, user_id: int | None, raw: dict, today: date) -> dict:
    """Yeni kayıt (senaryonun kendi satırı). Dönen: {id, label, values (okunur), warnings}."""
    unknown = [k for k in raw if kind.field(k) is None and not (kind.owner and k in kind.owner.fields) and k not in kind.fixed]
    problems = [{"field": k, "problem": "Bilinmeyen alan."} for k in unknown]
    values: dict = dict(kind.fixed)
    if kind.owner:
        values.update({k: raw.get(k) for k in kind.owner.fields})
        problems += kind.owner.check(session, values)
    for f in kind.fields:
        value = raw.get(f.name)
        if f.name == kind.end and kind.end_required and not kind.owner and (value is None or value == ""):
            value = raw.get(kind.start)                       # fabrika takvimi: bitiş boşsa tek gün
        parsed, problem = parse(f, value)
        if problem:
            problems.append({"field": f.name, "problem": problem})
        values[f.name] = parsed
    if not problems:
        problems = _problems(session, kind, scope, {**values, "IsValid": True}, None)
    if problems:
        raise EntryError(problems)
    new_id = _insert(session, kind, scope, {"IsValid": 1, **values}, user_id)
    history.record(session, kind.table, new_id, None, None, None, kind.source, user_id, change_type=history.CREATED, note=scope.note)
    _refresh(session, kind, scope, values, [_range(kind, values)])
    return {"id": new_id, "label": record_label(session, kind, values), "values": {f.name: show(f, values[f.name]) for f in kind.fields},
            "warnings": warnings_of(kind, values, today)}


def change(session: Session, kind: Kind, scope: Scope, user_id: int | None, changes: list[dict], today: date) -> dict:
    """Hücre değişiklikleri: hepsi ya da hiçbiri. Dönen: {saved, events: [{label, old, new}], warnings}."""
    by_row: dict[int, dict] = {}
    problems: list[dict] = []
    for c in changes:
        by_row.setdefault(int(c["id"]), {})[c["field"]] = c.get("value")
    plans = []
    for row_id, fields in by_row.items():
        row = _get(session, kind, scope, row_id)
        label = record_label(session, kind, row)
        parsed: dict = {}
        for name, value in fields.items():
            f = kind.field(name)
            if f is None:
                owner = kind.owner or RESOURCE
                locked = name in owner.fields or name in owner.locked_fields or name in kind.fixed
                problems.append({"id": row_id, "field": name, "record": label, "problem": owner.locked if locked else "Bu alan düzenlenemez."})
                continue
            new, problem = parse(f, value)
            if problem:
                problems.append({"id": row_id, "field": name, "record": label, "problem": problem})
            else:
                parsed[name] = new
        delta = {n: v for n, v in parsed.items() if not _same(row[n], v)}
        after = {**row, **delta}
        taken = {p["field"] for p in problems if p.get("id") == row_id}     # okunamayan hücrenin nedeni yeter; öteki hücrelerin kuralları yine denetlenir
        problems += [{"id": row_id, "record": label, **p} for p in _problems(session, kind, scope, after, row_id) if p["field"] not in taken]
        plans.append((row_id, row, delta, after, label))
    if problems:
        raise EntryError(problems, message="Kaydedilmedi.")
    events, warnings, saved = [], [], 0
    for row_id, row, delta, after, label in plans:
        if not delta:
            continue
        _write(session, kind, scope, row, delta, user_id)
        for name, new in delta.items():
            f = kind.field(name)
            history.record(session, kind.table, history_key(scope, row), name, show(f, row[name]), show(f, new), kind.source, user_id, note=scope.note)
        _refresh(session, kind, scope, row, [_range(kind, row), _range(kind, after)])
        events.append({"label": label, "old": {n: show(kind.field(n), row[n]) for n in delta},
                       "new": {n: show(kind.field(n), v) for n, v in delta.items()}})
        warnings += [f"{label}: {w}" for w in warnings_of(kind, after, today)]
        saved += len(delta)
    return {"saved": saved, "events": events, "warnings": warnings}


def _write(session: Session, kind: Kind, scope: Scope, row: dict, delta: dict, user_id: int | None, is_valid: bool | None = None) -> int:
    """Değişikliği yazar; dönen: yazılan (saklanan) satırın kimliği. Kendi satırı yerinde; Baz satırı izleyen senaryoda fark satırına."""
    if is_own(row):
        values = {**delta, **({} if is_valid is None else {"IsValid": 1 if is_valid else 0})}
        _update(session, kind, row["RowId"], values, user_id)
        return row["RowId"]
    base = _stored(session, kind, row["RowId"])                               # Baz'daki değerler
    names = [f.name for f in kind.fields]
    overridden = set(_fields_of(row.get("OverriddenFields")))
    current = {n: row[n] for n in names}                                      # senaryonun bugünkü geçerli değerleri (önceki farklar dahil)
    current.update(delta)
    overridden |= set(delta)
    overridden = {n for n in overridden if n == "IsValid" or not _same(current[n], base[n])}   # Baz'daki değere dönen alan farktan çıkar
    valid = bool(row["IsValid"]) if is_valid is None else is_valid
    overridden = (overridden - {"IsValid"}) | ({"IsValid"} if not valid else set())
    if not overridden:
        if row["StoredId"] is not None:
            _delete(session, kind, row["StoredId"])
        return row["StoredId"] or row["RowId"]
    kept = (*(kind.owner.fields if kind.owner else ()), *kind.fixed)          # sahip ve tür fark satırında Baz'daki gibi durur
    values = {**{k: base[k] for k in kept if k in base}, **{n: (current[n] if n in overridden else base[n]) for n in names},
              "IsValid": 1 if valid else 0, "OverriddenFields": "," + ",".join(sorted(overridden)) + ","}
    if row["StoredId"] is not None:
        _update(session, kind, row["StoredId"], values, user_id)
        return row["StoredId"]
    return _insert(session, kind, scope, {**values, "BaseRowId": row["RowId"]}, user_id)


def remove(session: Session, kind: Kind, scope: Scope, user_id: int | None, row_id: int) -> dict:
    """Senaryonun kendi satırını siler. Baz'dan okunan satır izleyen senaryodan silinmez (geçersiz yapılır)."""
    row = _get(session, kind, scope, row_id)
    if not is_own(row):
        raise EntryError(code="base_row", message="Bu kayıt Baz'dan okunuyor; bu senaryoda silinemez, geçersiz yapılabilir.", status=409)
    label = record_label(session, kind, row)
    _delete(session, kind, row_id)
    history.record(session, kind.table, row_id, None, None, None, kind.source, user_id, change_type=history.CLOSED, note=scope.note)
    _refresh(session, kind, scope, row, [_range(kind, row)])
    return {"label": label, "values": {f.name: show(f, row[f.name]) for f in kind.fields}}


def set_valid(session: Session, kind: Kind, scope: Scope, user_id: int | None, row_id: int, valid: bool) -> dict:
    """İzleyen senaryoda Baz satırını o senaryo için geçersiz (ya da yeniden geçerli) yapar; kendi satırında da çalışır."""
    row = _get(session, kind, scope, row_id)
    label = record_label(session, kind, row)
    if bool(row["IsValid"]) == valid:
        return {"label": label, "changed": False}
    if valid:
        problems = _problems(session, kind, scope, {**row, "IsValid": True}, row_id)
        if problems:
            raise EntryError([{"id": row_id, "record": label, **p} for p in problems], message="Geçerli yapılamadı.")
    _write(session, kind, scope, row, {}, user_id, is_valid=valid)
    history.record(session, kind.table, history_key(scope, row), "IsValid", "Evet" if row["IsValid"] else "Hayır", "Evet" if valid else "Hayır", kind.source, user_id, note=scope.note)
    _refresh(session, kind, scope, row, [_range(kind, row)])
    return {"label": label, "changed": True}


def restore(session: Session, kind: Kind, scope: Scope, user_id: int | None, row_id: int) -> dict:
    """Senaryo farkını kaldırır: fark satırı silinir, değerler Baz'a döner. Aynı anahtarlı Baz satırını örten kendi satırında (K-191) senaryonun
    satırı silinir; Baz satırı yeniden görünür."""
    row = _get(session, kind, scope, row_id)
    if row["Origin"] != resolve.DIFF or row["StoredId"] is None:
        raise EntryError(code="no_difference", message="Bu kayıtta senaryo farkı yok.", status=409)
    label = record_label(session, kind, row)
    base = _stored(session, kind, row["ShadowId"] if row.get("ShadowId") is not None else row["RowId"])
    changed = [n for n in _fields_of(row.get("OverriddenFields")) if n != "IsValid" and kind.field(n)]
    for name in changed:
        f = kind.field(name)
        history.record(session, kind.table, history_key(scope, row), name, show(f, row[name]), show(f, base[name]), kind.source, user_id, note=scope.note)
    if not row["IsValid"] and base["IsValid"]:
        history.record(session, kind.table, history_key(scope, row), "IsValid", "Hayır", "Evet", kind.source, user_id, note=scope.note)
    _delete(session, kind, row["StoredId"])
    _refresh(session, kind, scope, row, [_range(kind, row), _range(kind, base)])
    return {"label": label, "old": {n: show(kind.field(n), row[n]) for n in changed},
            "new": {n: show(kind.field(n), base[n]) for n in changed}}
