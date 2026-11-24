"""Hedef satırları (fonksiyon 22; K-196; docs/06). Hedef türleri sabittir (katalog); **hedef listesi kullanıcınındır**: sistem kendiliğinden satır
üretmez, bölmez, kaldırmaz, süre paylaştırmaz. Her satır bir hedef ve bir kapsamdır; motor aktif satırları sırayla ayrı hedef olarak çözer.

Kapsam (`Scope`): eksen → seçilen değerler; seçim yapılmayan eksen yazılmaz ve "tümü" demektir; boş kapsam hedefin tamamıdır. Eksenler: talep
hedeflerinde talep türü ve öncelik grubu, malzeme hedeflerinde malzeme seviyesi ve malzeme grubu, kaynak hedeflerinde kaynak grubu tipi; Fason,
Alternatif önceliği ve Önceki plandan sapma kapsam almaz. Kapsamlar örtüşebilir (aynı kayıt birden çok satırın hedefine girebilir); hiçbir
satırın kapsamadığı kayıt hiçbir hedefe girmez (`rows_of`; motor aynı işlevi kullanır).

HTTP'den bağımsızdır; yazma çağıranın işlemindedir (commit çağıranda). Sorunlar `ParamError` ile.
"""
import json
from decimal import Decimal

import sqlalchemy as sa

from db.models import metadata

from . import catalog as cat
from .service import ParamError, _number, read_settings

OBJECTIVE = metadata.tables["param.ObjectiveDefinition"]
ALL = "Tümü"
STALE = "Hedef listesi değişmiş; sayfayı yenileyin."
GROUP_LENGTH = 50
DESCRIPTION_LENGTH = OBJECTIVE.c.Description.type.length
SECONDS_PROBLEM = "1 ya da daha büyük tam sayı girilmeli."
TOLERANCE_PROBLEM = "0 ile 100 arasında, en çok 2 ondalıklı sayı girilmeli."
PICK = "Listedeki değerlerden seçilmeli."


# ------------------------------------------------------------------ kapsam (saf işlevler)

def parse_scope(raw: str | None) -> dict:
    return json.loads(raw) if raw else {}


def dump_scope(scope: dict) -> str | None:
    return json.dumps(scope, ensure_ascii=False) if scope else None


def check_scope(obj: cat.Objective, scope, open_values: list | None = None) -> dict:
    """İstekle gelen kapsam → temiz kapsam: eksen sırasıyla, kapalı eksende değerler eksenin sırasıyla; seçim yapılmayan eksen yazılmaz ("tümü").
    Bir eksende hepsini seçmek ile hiç seçmemek aynıdır: o eksen yazılmaz (açık eksende "hepsi" `open_values`'tır: verideki değerler).
    Kapsam almayan hedefte kapsam olmaz; değerler eksenin değerlerinden olmalı. Boş kapsam geçerlidir (hedefin tamamı); örtüşme denetlenmez."""
    scope = scope or {}
    if not isinstance(scope, dict) or set(scope) - {a.key for a in obj.axes}:
        raise ParamError([{"field": "scope", "problem": "Kapsam bu hedefin sınıflarından seçilmeli." if obj.axes else "Bu hedef kapsam almaz."}])
    out = {}
    for axis in obj.axes:
        values = scope.get(axis.key)
        if values in (None, []):
            continue
        if not isinstance(values, list):
            raise ParamError([{"field": f"scope.{axis.key}", "problem": PICK}])
        if axis.values is not None:
            if any(isinstance(v, bool) or v not in axis.values for v in values):
                raise ParamError([{"field": f"scope.{axis.key}", "problem": PICK}])
            values = [v for v in axis.values if v in values]
            if len(values) == len(axis.values):
                continue
        else:
            values = [v.strip() if isinstance(v, str) else v for v in values]
            if any(not isinstance(v, str) or not v or len(v) > GROUP_LENGTH for v in values):
                raise ParamError([{"field": f"scope.{axis.key}", "problem": PICK}])
            values = list(dict.fromkeys(values))
            if open_values and set(values) >= set(open_values):
                continue
        out[axis.key] = values
    return out


def covers(scope: dict, classes: dict) -> bool:
    """Kapsam sınıf birleşimini içeriyor mu: seçim yapılan her eksende kaydın değeri seçilenlerden biri olmalı (belirsiz değer, None, yalnız o
    ekseni "tümü" olan kapsama girer)."""
    return all(classes.get(key) in values for key, values in scope.items())


def rows_of(rows: list[dict], code: str, classes: dict) -> list[dict]:
    """Sınıf birleşiminin (eksen → değer; None: belirsiz) hedefte girdiği satırlar, listedeki sırayla. Kapsamlar örtüşebilir: birden çok satır
    dönebilir; hiçbir satır kapsamıyorsa liste boştur (kayıt o hedefe girmez)."""
    return [r for r in rows if r["code"] == code and covers(r["scope"], classes)]


def scope_parts(obj: cat.Objective, scope: dict) -> list[dict]:
    """Kapsam yazısının parçaları: seçim yapılan eksenler, kategori adıyla ([{label, values}]); seçim yapılmayan eksen yazılmaz."""
    return [{"label": a.label, "values": list(scope[a.key])} for a in obj.axes if scope.get(a.key)]


def scope_text(obj: cat.Objective, scope: dict) -> str:
    """Düz yazı: "Talep türü: Kesin sipariş, Teklif · Öncelik grubu: 1, 2"; hiç seçim yoksa "Tümü"; kapsam almayan hedefte boş."""
    parts = scope_parts(obj, scope)
    if not parts:
        return ALL if obj.axes else ""
    return " · ".join(f"{p['label']}: {', '.join(str(v) for v in p['values'])}" for p in parts)


def label_of(row: dict) -> str:
    """Denetim izinde ve hata mesajında satırın adı: "Karşılanmayan talep · Talep türü: Kesin sipariş"; kapsam almayan hedefte yalnız hedefin adı."""
    return f"{row['label']} · {row['scope_text']}" if row["scope_text"] else row["label"]


# ------------------------------------------------------------------ başlangıç düzeni

def _in_plan(settings: dict, demand_type: str) -> bool:
    key = cat.DEMAND_SWITCH.get(demand_type)
    return key is None or settings.get(key, cat.DEFAULTS.get(key)) == cat.YES


def start_rows(settings: dict | None = None) -> list[dict]:
    """Başlangıç düzeni (K-196 madde 6): hedefler ilk eksenlerine göre ayrı satırlarda, kapsam almayan hedefler birer satır; türün süresi aktif
    gelen satırlarına eşit bölünür (toplam bütçe aynı); Tahmin satırlarının ödün payı %2. Plana alınmayan talep türünün satırı ve kurulumda
    kapalı hedefler kapalı gelir. Aktifler sırasıyla, kapalılar sonda."""
    settings = settings or {}
    per = {}
    for obj in cat.OBJECTIVES:
        if obj.axes:
            first = obj.axes[0]
            rows = [dict(code=obj.code, scope={first.key: [value]},
                         active=obj.seconds is not None and (first.key != cat.AX_DEMAND_TYPE or _in_plan(settings, value))) for value in obj.start]
        else:
            rows = [dict(code=obj.code, scope={}, active=obj.seconds is not None)]
        on = [r for r in rows if r["active"]]
        special = dict(obj.start_tolerance)   # Tahmin satırlarının ödün payı korunur (%2)
        for i, r in enumerate(on):
            r["seconds"] = obj.seconds // len(on) + (obj.seconds % len(on) if i == 0 else 0)
            value = next(iter(next(iter(r["scope"].values()), [])), None)
            r["tolerance"] = special.get(value, obj.tolerance)
        per[obj.code] = rows
    ordered = []
    for group in zip(*[per[c] for c in cat.START_INTERLEAVED]):
        ordered.extend(group)
    for obj in cat.OBJECTIVES:
        if obj.code not in cat.START_INTERLEAVED:
            ordered.extend(per[obj.code])
    return [r for r in ordered if r["active"]] + [dict(r, seconds=None, tolerance=None) for r in ordered if not r["active"]]


# ------------------------------------------------------------------ sınıflar (motor)

def demand_type(is_quote, is_on_hold) -> str:
    """Sipariş satırının talep türü: teklif işaretliyse Teklif (beklemede de işaretli olsa), değilse beklemedeyse Beklemedeki sipariş."""
    return cat.DEMAND_QUOTE if is_quote else cat.DEMAND_ON_HOLD if is_on_hold else cat.DEMAND_FIRM


def resource_type(is_employee, is_machine, is_subcontractor, is_other) -> str | None:
    """Kaynak grubunun tipi: dört bayraktan tam biri işaretliyse o; hiçbiri ya da birden çoğu işaretliyse belirsiz (None). Fırın ve Kalıp Faz 1
    dışıdır: yalnız onlar işaretliyse belirsiz."""
    on = [name for name, flag in ((cat.RES_EMPLOYEE, is_employee), (cat.RES_MACHINE, is_machine), (cat.RES_SUBCONTRACTOR, is_subcontractor),
                                  (cat.RES_OTHER, is_other)) if flag]
    return on[0] if len(on) == 1 else None


def material_groups(session) -> list[str]:
    return [r[0] for r in session.execute(sa.text(
        "SELECT DISTINCT MaterialGroup FROM core.Material WHERE VersionTo IS NULL AND MaterialGroup IS NOT NULL AND MaterialGroup <> N'' ORDER BY MaterialGroup"))]


# ------------------------------------------------------------------ okuma

def _describe(rows: list[dict]) -> None:
    """Satırın gösterilen alanları: hedefin adı ve grubu, kapsam yazısı."""
    for r in rows:
        obj = cat.OBJECTIVE_BY_CODE[r["code"]]
        r["label"], r["family"], r["group"] = obj.label, obj.family, cat.FAMILY_LABELS[obj.family]
        r["scope_parts"], r["scope_text"] = scope_parts(obj, r["scope"]), scope_text(obj, r["scope"])


def read_objectives(session, scenario_id: int) -> list[dict]:
    """Hedef satırları: aktifler sırasıyla, kapalılar sonda (katalog sırasıyla, sonra eklenme sırasıyla)."""
    order = {o.code: i for i, o in enumerate(cat.OBJECTIVES)}
    found = [dict(r) for r in session.execute(sa.select(OBJECTIVE).where(OBJECTIVE.c.ScenarioDefinitionId == scenario_id)).mappings()]
    found.sort(key=lambda r: (0, r["Seq"] or 0, r["Id"]) if r["IsActive"] else (1, order.get(r["Code"], 99), r["Id"]))
    rows = [{"id": r["Id"], "code": r["Code"], "scope": parse_scope(r["Scope"]), "description": r["Description"],
             "seq": r["Seq"] if r["IsActive"] else None, "seconds": r["TimeBudgetSeconds"] if r["IsActive"] else None,
             "tolerance": float(r["TolerancePct"]) if r["IsActive"] and r["TolerancePct"] is not None else None, "active": bool(r["IsActive"])}
            for r in found if r["Code"] in cat.OBJECTIVE_BY_CODE]
    _describe(rows)
    return rows


def catalog(session) -> list[dict]:
    """Bütün hedefler, grupları ve eksenleri (pencere): kapsam almayan hedefte eksen yok; açık eksenin değerleri verideki değerlerdir."""
    groups = None
    out = []
    for obj in cat.OBJECTIVES:
        listed = []
        for axis in obj.axes:
            if axis.values is None and groups is None:
                groups = material_groups(session)
            listed.append({"key": axis.key, "label": axis.label, "values": list(axis.values if axis.values is not None else groups), "open": axis.values is None})
        out.append({"code": obj.code, "label": obj.label, "family": obj.family, "group": cat.FAMILY_LABELS[obj.family], "axes": listed})
    return out


# ------------------------------------------------------------------ yazma

def _seconds(value, field: str, record: str | None = None) -> tuple[int | None, dict | None]:
    s = _number(value) if value not in (None, "") else None
    if s is None or s != s.to_integral_value() or s < 1:
        return None, {"field": field, "problem": SECONDS_PROBLEM, **({"record": record} if record else {})}
    return int(s), None


def _tolerance(value, field: str, record: str | None = None) -> tuple[Decimal | None, dict | None]:
    t = _number(value) if value not in (None, "") else None
    if t is None or not 0 <= t <= 100 or -t.as_tuple().exponent > 2:
        return None, {"field": field, "problem": TOLERANCE_PROBLEM, **({"record": record} if record else {})}
    return t, None


def save_objectives(session, scenario_id: int, rows: list[dict], on_change=None) -> int:
    """Hedef satırlarının tamamı gelir, listedeki sırasıyla: aktiflerin sırası 1'den boşluksuz yazılır; kapalı satırın sırası, süresi ve payı
    boşalır. Liste boş olabilir; satır varsa en az biri aktif olmalı."""
    current = {r["id"]: r for r in read_objectives(session, scenario_id)}
    problems = []
    if {r.get("id") for r in rows} != set(current) or len(rows) != len(current):
        raise ParamError([{"field": "rows", "problem": STALE}])
    seq, planned = 0, []
    for i, row in enumerate(rows, start=1):
        old = current[row["id"]]
        name = label_of(old)
        if not row.get("active"):
            planned.append((old, dict(Seq=None, TimeBudgetSeconds=None, TolerancePct=None, IsActive=False)))
            continue
        seq += 1
        s, bad_s = _seconds(row.get("seconds"), f"rows.{i}.seconds", name)
        t, bad_t = _tolerance(row.get("tolerance"), f"rows.{i}.tolerance", name)
        problems.extend(p for p in (bad_s, bad_t) if p)
        planned.append((old, dict(Seq=seq, TimeBudgetSeconds=s, TolerancePct=t, IsActive=True)))
    if rows and seq == 0:
        problems.append({"field": "rows", "problem": "En az bir hedef aktif olmalı."})
    if problems:
        raise ParamError(problems)
    changed = 0
    for old, new in planned:
        before = dict(Seq=old["seq"], TimeBudgetSeconds=old["seconds"], TolerancePct=old["tolerance"], IsActive=old["active"])
        after = {**new, "TolerancePct": float(new["TolerancePct"]) if new["TolerancePct"] is not None else None}
        if before == after:
            continue
        session.execute(sa.update(OBJECTIVE).where(OBJECTIVE.c.Id == old["id"]).values(**new))
        changed += 1
        if on_change:
            diff = [k for k in after if after[k] != before[k]]
            on_change(label_of(old), {k: before[k] for k in diff}, {k: after[k] for k in diff})
    return changed


def _objective(code) -> cat.Objective:
    obj = cat.OBJECTIVE_BY_CODE.get(code)
    if obj is None:
        raise ParamError([{"field": "code", "problem": "Listedeki hedeflerden biri seçilmeli."}])
    return obj


def _description(value) -> str | None:
    text = (value or "").strip() if isinstance(value, str) or value is None else None
    if text is None or len(text) > DESCRIPTION_LENGTH:
        raise ParamError([{"field": "description", "problem": f"En çok {DESCRIPTION_LENGTH} karakter."}])
    return text or None


def _checked(session, obj: cat.Objective, scope) -> dict:
    """Kapsamı denetler; açık eksende (malzeme grubu) seçim varsa "hepsi" için verideki değerler okunur."""
    picked = isinstance(scope, dict) and any(scope.get(a.key) for a in obj.axes if a.values is None)
    return check_scope(obj, scope, material_groups(session) if picked else None)


def _name(obj: cat.Objective, scope: dict) -> str:
    text = scope_text(obj, scope)
    return f"{obj.label} · {text}" if text else obj.label


def create(session, scenario_id: int, code, scope, description, seconds, tolerance, on_change=None) -> int:
    """"Yeni hedef tanımla": satır listenin sonuna (aktiflerin sonuna), aktif olarak eklenir. Başka satır değişmez; kapsam örtüşebilir.
    Süre bütçesi ve ödün payı zorunludur (varsayılan yok, K-138). Yeni satırın kimliği."""
    obj = _objective(code)
    clean = _checked(session, obj, scope)
    text = _description(description)
    s, bad_s = _seconds(seconds, "seconds")
    t, bad_t = _tolerance(tolerance, "tolerance")
    if bad_s or bad_t:
        raise ParamError([p for p in (bad_s, bad_t) if p])
    last = session.execute(sa.select(sa.func.coalesce(sa.func.max(OBJECTIVE.c.Seq), 0))
                           .where(OBJECTIVE.c.ScenarioDefinitionId == scenario_id, OBJECTIVE.c.IsActive == sa.true())).scalar_one()
    new_id = session.execute(sa.insert(OBJECTIVE).values(
        ScenarioDefinitionId=scenario_id, Code=obj.code, Scope=dump_scope(clean), Description=text, Seq=int(last) + 1, TimeBudgetSeconds=s,
        TolerancePct=t, IsActive=True).returning(OBJECTIVE.c.Id)).scalar_one()
    if on_change:
        on_change(_name(obj, clean), None, {"Scope": scope_text(obj, clean) or None, "Description": text, "TimeBudgetSeconds": s, "TolerancePct": float(t)})
    return int(new_id)


def update(session, scenario_id: int, row_id: int, code, scope, description, seconds=None, tolerance=None, on_change=None) -> None:
    """"Düzenle": satırın hedefi, kapsamı ve açıklaması; aktif satırda süre bütçesi ve ödün payı (zorunlu). Kapalı satırın süresi ve payı boştur,
    yazılmaz. Sıra ve aktiflik değişmez."""
    rows = read_objectives(session, scenario_id)
    row = next((r for r in rows if r["id"] == row_id), None)
    if row is None:
        raise ParamError([{"field": "id", "problem": STALE}])
    obj = _objective(code)
    clean = _checked(session, obj, scope)
    text = _description(description)
    values = dict(Code=obj.code, Scope=dump_scope(clean), Description=text)
    after = {"Objective": obj.label, "Scope": scope_text(obj, clean) or None, "Description": text}
    before = {"Objective": row["label"], "Scope": row["scope_text"] or None, "Description": row["description"]}
    if row["active"]:
        s, bad_s = _seconds(seconds, "seconds")
        t, bad_t = _tolerance(tolerance, "tolerance")
        if bad_s or bad_t:
            raise ParamError([p for p in (bad_s, bad_t) if p])
        values.update(TimeBudgetSeconds=s, TolerancePct=t)
        after.update(TimeBudgetSeconds=s, TolerancePct=float(t))
        before.update(TimeBudgetSeconds=row["seconds"], TolerancePct=row["tolerance"])
    diff = [k for k in after if after[k] != before[k]]
    if not diff:
        return
    session.execute(sa.update(OBJECTIVE).where(OBJECTIVE.c.Id == row_id).values(**values))
    if on_change:
        on_change(_name(obj, clean), {k: before[k] for k in diff}, {k: after[k] for k in diff})


def delete(session, scenario_id: int, row_id: int, on_change=None) -> None:
    """"Hedefi sil": her satır silinebilir; kapsamı başka satıra geçmez. Aktiflerin sırası yeniden 1'den boşluksuz numaralanır."""
    rows = read_objectives(session, scenario_id)
    row = next((r for r in rows if r["id"] == row_id), None)
    if row is None:
        raise ParamError([{"field": "id", "problem": STALE}])
    session.execute(sa.delete(OBJECTIVE).where(OBJECTIVE.c.Id == row_id))
    seq = 0
    for r in rows:
        if r["active"] and r["id"] != row_id:
            seq += 1
            if r["seq"] != seq:
                session.execute(sa.update(OBJECTIVE).where(OBJECTIVE.c.Id == r["id"]).values(Seq=seq))
    if on_change:
        on_change(label_of(row), {"Scope": row["scope_text"] or None, "Description": row["description"], "TimeBudgetSeconds": row["seconds"],
                                  "TolerancePct": row["tolerance"]}, None)


def insert_start(session, scenario_id: int, settings: dict | None = None) -> int:
    """Senaryonun hedeflerini başlangıç düzeniyle yazar (var olan satırlar silinir). `session`: Session ya da Connection."""
    session.execute(sa.delete(OBJECTIVE).where(OBJECTIVE.c.ScenarioDefinitionId == scenario_id))
    rows = start_rows(settings)
    seq = 0
    for r in rows:
        seq += 1 if r["active"] else 0
        session.execute(sa.insert(OBJECTIVE).values(
            ScenarioDefinitionId=scenario_id, Code=r["code"], Scope=dump_scope(r["scope"]), IsActive=r["active"], Seq=seq if r["active"] else None,
            TimeBudgetSeconds=r["seconds"], TolerancePct=Decimal(str(r["tolerance"])) if r["tolerance"] is not None else None))
    return len(rows)


def reset(session, scenario_id: int, on_change=None) -> None:
    """"Başlangıç düzenine getir": senaryonun hedef satırları başlangıç düzeniyle baştan yazılır (senaryonun Talep ayarlarına göre)."""
    before = read_objectives(session, scenario_id)
    n = insert_start(session, scenario_id, read_settings(session, scenario_id))
    if on_change:
        on_change("Hedefler", {"RowCount": len(before)}, {"Layout": "Başlangıç düzeni", "RowCount": n})
