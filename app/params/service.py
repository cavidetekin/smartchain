"""Senaryo parametrelerinin okunması ve yazılması (fonksiyon 22, 23; K-175). HTTP'den bağımsızdır: API servisi, motor yükleyicisi ve veri kalitesi
buradan okur. Yazma çağıranın işlemindedir (commit çağıranda); sorunlar `ParamError` ile, alan bazında.
"""
from datetime import date
from decimal import Decimal, InvalidOperation

import sqlalchemy as sa
from sqlalchemy.orm import Session

from db.models import metadata

from . import catalog as cat, horizon

SCENARIO = metadata.tables["param.ScenarioDefinition"]
SETTING = metadata.tables["param.PlanningSetting"]
BUCKET = metadata.tables["param.TimeBucketDefinition"]
OBJECTIVE = metadata.tables["param.ObjectiveDefinition"]
WARNING = metadata.tables["param.WarningThreshold"]


class ParamError(Exception):
    """Geçersiz değer: `problems` alan bazında ({"field", "problem"})."""

    def __init__(self, problems: list[dict]):
        super().__init__("Girilen bilgiler geçersiz.")
        self.problems = problems


# ------------------------------------------------------------------ senaryo

def base_scenario(session: Session) -> tuple[int, str] | None:
    """Baz senaryo (kimlik, ad); geçiş 0058 açar."""
    row = session.execute(sa.select(SCENARIO.c.Id, SCENARIO.c.Name).where(SCENARIO.c.IsBase == sa.true()).order_by(SCENARIO.c.Id).limit(1)).first()
    return (row.Id, row.Name) if row else None


# ------------------------------------------------------------------ parametreler

def read_settings(session: Session, scenario_id: int) -> dict[str, str | None]:
    """Kataloğun bütün anahtarları; satırı olmayan anahtar başlangıç değeriyle (boş bırakılabilen sayı None)."""
    stored = {k: v for k, v in session.execute(sa.select(SETTING.c.SettingKey, SETTING.c.Value).where(SETTING.c.ScenarioDefinitionId == scenario_id))}
    return {p.key: stored.get(p.key, p.default) for p in cat.PARAMS}


def all_settings(session: Session, scenario_id: int) -> dict[str, str]:
    """Motorun okuduğu hâl: katalog değerleri ve katalog dışı anahtarlar (ör. sahte motorun ayarları)."""
    stored = {k: v for k, v in session.execute(sa.select(SETTING.c.SettingKey, SETTING.c.Value).where(SETTING.c.ScenarioDefinitionId == scenario_id))}
    return {**{k: v for k, v in cat.DEFAULTS.items()}, **stored}


def _number(text: str) -> Decimal | None:
    try:
        value = Decimal(str(text).replace(",", "."))
    except (InvalidOperation, ValueError):
        return None
    return value if value.is_finite() else None


def normalize(param: cat.Param, value) -> tuple[str | None, str | None]:
    """Değer → saklanan metin; (değer, sorun)."""
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return (None, None) if param.nullable else (None, "Boş bırakılamaz.")
    if param.kind == cat.BOOL:
        if isinstance(value, bool) or value in (0, 1):
            return (cat.YES if value else cat.NO), None
        if str(value) in (cat.YES, cat.NO):
            return str(value), None
        return None, "Evet ya da Hayır girilmeli."
    if param.kind == cat.CHOICE:
        return (str(value), None) if str(value) in param.options else (None, "Listedeki değerlerden biri girilmeli.")
    number = _number(value)
    if number is None:
        return None, "Tam sayı girilmeli." if param.kind == cat.INT else "Sayı girilmeli."
    if param.kind == cat.INT and number != number.to_integral_value():
        return None, "Tam sayı girilmeli."
    if param.minimum is not None and number < Decimal(str(param.minimum)):
        return None, f"En az {param.minimum:g}."
    if param.maximum is not None and number > Decimal(str(param.maximum)):
        return None, f"En çok {param.maximum:g}."
    if param.kind == cat.NUMBER and -number.as_tuple().exponent > 4:
        return None, "En çok 4 ondalık."
    text = format(number.normalize(), "f") if number != 0 else "0"
    return text, None


def save_settings(session: Session, scenario_id: int, changes: dict, on_change=None) -> dict[str, tuple[str | None, str | None]]:
    """Yalnız değişen anahtarlar yazılır; biri geçersizse hiçbiri yazılmaz. Dönen: anahtar → (eski, yeni). on_change her değişiklikte çağrılır (iz)."""
    current = read_settings(session, scenario_id)
    problems, values = [], {}
    for key, raw in changes.items():
        param = cat.BY_KEY.get(key)
        if param is None:
            problems.append({"field": key, "problem": "Bilinmeyen parametre."})
            continue
        value, problem = normalize(param, raw)
        if problem:
            problems.append({"field": key, "problem": problem})
        else:
            values[key] = value
    if problems:
        raise ParamError(problems)
    changed = {}
    for key, value in values.items():
        if value == current[key]:
            continue
        session.execute(sa.delete(SETTING).where(SETTING.c.ScenarioDefinitionId == scenario_id, SETTING.c.SettingKey == key))
        if value is not None:
            session.execute(sa.insert(SETTING).values(ScenarioDefinitionId=scenario_id, SettingKey=key, Value=value))
        changed[key] = (current[key], value)
        if on_change:
            on_change(key, current[key], value)
    return changed


# ------------------------------------------------------------------ hedefler

def read_objectives(session: Session, scenario_id: int) -> list[dict]:
    """Hedefler: aktifler sırasıyla, kapalılar sonda (katalog sırasıyla)."""
    order = {o.code: i for i, o in enumerate(cat.OBJECTIVES)}
    rows = [dict(r) for r in session.execute(sa.select(OBJECTIVE).where(OBJECTIVE.c.ScenarioDefinitionId == scenario_id)).mappings()]
    rows.sort(key=lambda r: (0, r["Seq"] or 0) if r["IsActive"] else (1, order.get(r["Code"], 99), r["PriorityGroup"] or 0))
    return [{"id": r["Id"], "code": r["Code"], "priority_group": r["PriorityGroup"], "label": objective_label(r["Code"], r["PriorityGroup"]),
             "seq": r["Seq"] if r["IsActive"] else None, "seconds": r["TimeBudgetSeconds"] if r["IsActive"] else None,
             "tolerance": float(r["TolerancePct"]) if r["IsActive"] and r["TolerancePct"] is not None else None, "active": bool(r["IsActive"])}
            for r in rows]


def objective_label(code: str, group: int | None) -> str:
    label = cat.OBJECTIVE_LABELS.get(code, code)
    return f"{label} · Öncelik {group}" if group is not None else label


def save_objectives(session: Session, scenario_id: int, rows: list[dict], on_change=None) -> int:
    """Hedeflerin tamamı gelir, listedeki sırasıyla: aktiflerin sırası 1'den boşluksuz yazılır; kapalı hedefin sırası, süresi ve payı boşalır."""
    current = {r["id"]: r for r in read_objectives(session, scenario_id)}
    problems = []
    if {r.get("id") for r in rows} != set(current) or len(rows) != len(current):
        raise ParamError([{"field": "rows", "problem": "Hedef listesi değişmiş; sayfayı yenileyin."}])
    seq, planned = 0, []
    for i, row in enumerate(rows, start=1):
        old = current[row["id"]]
        active = bool(row.get("active"))
        if not active:
            planned.append((old, dict(Seq=None, TimeBudgetSeconds=None, TolerancePct=None, IsActive=False)))
            continue
        seq += 1
        seconds, tolerance = row.get("seconds"), row.get("tolerance")
        s = _number(seconds) if seconds not in (None, "") else None
        t = _number(tolerance) if tolerance not in (None, "") else None
        if s is None or s != s.to_integral_value() or s < 1:
            problems.append({"field": f"rows.{i}.seconds", "problem": "1 ya da daha büyük tam sayı girilmeli.", "record": old["label"]})
        if t is None or not 0 <= t <= 100 or -t.as_tuple().exponent > 2:
            problems.append({"field": f"rows.{i}.tolerance", "problem": "0 ile 100 arasında, en çok 2 ondalıklı sayı girilmeli.", "record": old["label"]})
        planned.append((old, dict(Seq=seq, TimeBudgetSeconds=int(s) if s is not None else None, TolerancePct=t, IsActive=True)))
    if seq == 0:
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
            on_change(old["label"], {k: before[k] for k in diff}, {k: after[k] for k in diff})
    return changed


def time_budget(session: Session, scenario_id: int) -> int:
    """Senaryonun süre bütçesi (sn): aktif hedeflerin sürelerinin toplamı."""
    return int(session.execute(sa.select(sa.func.coalesce(sa.func.sum(OBJECTIVE.c.TimeBudgetSeconds), 0))
                               .where(OBJECTIVE.c.ScenarioDefinitionId == scenario_id, OBJECTIVE.c.IsActive == sa.true())).scalar_one())


# ------------------------------------------------------------------ zaman

def bucket_rows(session: Session, scenario_id: int, axis: str = cat.AXIS_PLAN) -> list[tuple[str, int, str]]:
    return [(r.BucketType, int(r.Count), r.SpanUnit) for r in session.execute(
        sa.select(BUCKET.c.BucketType, BUCKET.c.Count, BUCKET.c.SpanUnit)
        .where(BUCKET.c.ScenarioDefinitionId == scenario_id, BUCKET.c.Axis == axis).order_by(BUCKET.c.Seq))]


def plan_start(session: Session, settings: dict, today: date) -> date:
    """Plan başlangıcı: bugün ya da güncel veri versiyonunun (yerel) tarihi; veri yoksa bugün."""
    if settings.get("PlanStart") != cat.PLAN_START_DATA:
        return today
    from app.flows.schedule import utc_to_local
    version = metadata.tables["adm.DataVersion"]
    at = session.execute(sa.select(version.c.CreatedAt).order_by(version.c.Id.desc()).limit(1)).scalar()
    return utc_to_local(at).date() if at else today


def read_parts(session: Session, scenario_id: int, today: date, axis: str = cat.AXIS_PLAN) -> list[horizon.Part]:
    """Eksenin parçaları, hesaplanmış tarihleriyle. Raporlama ekseni "planla aynı" ise plan dizisi."""
    settings = read_settings(session, scenario_id)
    if axis == cat.AXIS_REPORT and settings.get("ReportAxisSameAsPlan") != cat.NO:
        axis = cat.AXIS_PLAN
    rows = bucket_rows(session, scenario_id, axis)
    return horizon.parts(plan_start(session, settings, today), rows, horizon.week_start_index(settings.get("WeekStart")))


def preview_parts(session: Session, scenario_id: int, today: date, rows: list[tuple[str, int, str]], week_start: str | None = None,
                  plan_start_mode: str | None = None) -> list[horizon.Part]:
    """Kaydedilmemiş dizinin hesabı (ekrandaki taslak; hafta başlangıcı ve plan başlangıcı taslağı verilebilir)."""
    settings = read_settings(session, scenario_id)
    if plan_start_mode:
        settings["PlanStart"] = plan_start_mode
    return horizon.parts(plan_start(session, settings, today), rows, horizon.week_start_index(week_start or settings.get("WeekStart")))


def save_buckets(session: Session, scenario_id: int, axis: str, rows: list[tuple[str, int | None, str]], on_change=None) -> bool:
    """Eksenin dizisi baştan yazılır; değişmediyse dokunulmaz."""
    kinds = cat.PLAN_BUCKETS if axis == cat.AXIS_PLAN else cat.REPORT_BUCKETS
    found = horizon.problems(rows, kinds)
    if found:
        raise ParamError(found)
    new = [(b, int(c), u) for b, c, u in rows]
    old = bucket_rows(session, scenario_id, axis)
    if new == old:
        return False
    session.execute(sa.delete(BUCKET).where(BUCKET.c.ScenarioDefinitionId == scenario_id, BUCKET.c.Axis == axis))
    for i, (bucket_type, count, unit) in enumerate(new, start=1):
        session.execute(sa.insert(BUCKET).values(ScenarioDefinitionId=scenario_id, Axis=axis, Seq=i, BucketType=bucket_type, Count=count, SpanUnit=unit))
    if on_change:
        on_change(axis, describe(old), describe(new))
    return True


def fix_period_end(session: Session, scenario_id: int, today: date) -> date | None:
    """Sabit dönemin son günü: plan başlangıcından, dönem dizisindeki kapsam kuralıyla (içinde bulunulan hafta ya da ay dahil, takvim sınırında
    biter). Sabit dönem 0 ise None."""
    settings = read_settings(session, scenario_id)
    count = int(settings.get("FixPeriod") or 0)
    if count < 1:
        return None
    return horizon.span_end(plan_start(session, settings, today), count, settings.get("FixPeriodUnit") or cat.DAY,
                            horizon.week_start_index(settings.get("WeekStart")))


def describe(rows: list[tuple[str, int, str]]) -> str:
    """Dizinin okunur hâli (denetim izi): "Hafta · 3 Ay + Ay · 6 Ay"."""
    return " + ".join(f"{b} · {c} {u}" for b, c, u in rows) or "—"


def horizon_end(session: Session, today: date) -> date | None:
    """Baz senaryonun planlama ufkunun son günü; Baz ya da dizisi yoksa None."""
    base = base_scenario(session)
    if base is None:
        return None
    found = read_parts(session, base[0], today)
    return found[-1].end if found else None


# --- Uyarı eşikleri (fonksiyon 26; K-190) ---------------------------------------------------------------------------------------------------

def _plain(value) -> float | None:
    return float(value) if value is not None else None


def ensure_warning_thresholds(session: Session, scenario_id: int) -> int:
    """Senaryoda eksik uyarı satırlarını katalogdaki başlangıç değerleriyle ekler (geçiş her senaryoya yazar; kataloğa sonradan eklenen uyarı ve
    kopyalanmadan açılmış senaryo için). Dönen: eklenen satır sayısı."""
    have = set(session.execute(sa.select(WARNING.c.WarningCode).where(WARNING.c.ScenarioDefinitionId == scenario_id)).scalars())
    missing = [w for w in cat.WARNINGS if w.code not in have]
    for w in missing:
        session.execute(sa.insert(WARNING).values(ScenarioDefinitionId=scenario_id, WarningCode=w.code, Severity=w.severity, IsActive=True,
                                                  **{cat.TIER_COLUMNS[t]: v for t, v in zip(cat.TIERS, w.defaults)}))
    return len(missing)


def read_warning_thresholds(session: Session, scenario_id: int) -> list[dict]:
    """Senaryonun uyarı eşikleri, katalog sırasıyla (kategori, uyarı)."""
    ensure_warning_thresholds(session, scenario_id)
    stored = {r["WarningCode"]: r for r in session.execute(sa.select(WARNING).where(WARNING.c.ScenarioDefinitionId == scenario_id)).mappings()}
    out = []
    for w in cat.WARNINGS:
        r = stored[w.code]
        out.append({"code": w.code, "label": w.label, "category": w.category, "unit": w.unit, "direction": w.direction,
                    **{t: (_plain(r[cat.TIER_COLUMNS[t]]) if w.has_threshold else None) for t in cat.TIERS},
                    "severity": None if w.has_threshold else r["Severity"], "active": bool(r["IsActive"])})
    return out


def _threshold(w: cat.Warning, value) -> tuple[Decimal | None, str | None]:
    """Hücreye yazılan eşik: boş → kademe kullanılmaz; gün tam sayı, yüzde en çok iki ondalık; 0 ya da büyük."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None, None
    number = _number(str(value).strip().replace("%", "").replace(" ", ""))
    if number is None:
        return None, "Sayı girilmeli."
    if number < 0:
        return None, "0 ya da daha büyük olmalı."
    if number >= Decimal(10) ** 9:
        return None, "Çok büyük."
    if w.unit == cat.UNIT_DAY and number != number.to_integral_value():
        return None, "Tam sayı girilmeli."
    if w.unit == cat.UNIT_PCT and -number.normalize().as_tuple().exponent > 2:
        return None, "En çok 2 ondalıklı sayı girilmeli."
    return number, None


def save_warning_thresholds(session: Session, scenario_id: int, rows: list[dict], on_change=None) -> int:
    """Tablonun tamamı gelir (katalogdaki her uyarı bir kez): hepsi ya da hiçbiri; yalnız değişen satır yazılır. Dolu kademeler yöne göre kesin
    sıralıdır (aşınca: Düşük < Orta < Yüksek < Kritik; altında tersi; boş kademe atlanır). Kapatılan uyarının değerleri durur."""
    current = {r["code"]: r for r in read_warning_thresholds(session, scenario_id)}
    if [r.get("code") for r in rows] != list(current):
        raise ParamError([{"field": "rows", "problem": "Uyarı listesi değişmiş; sayfayı yenileyin."}])
    problems, planned = [], []
    for i, row in enumerate(rows, start=1):
        w = cat.WARNING_BY_CODE[row["code"]]
        active = bool(row.get("active"))
        new = {"active": active, "severity": None, **{t: None for t in cat.TIERS}}

        def problem(field: str, text: str) -> None:
            problems.append({"field": f"rows.{i}.{field}", "problem": text, "record": w.label})

        if not w.has_threshold:
            if any(row.get(t) not in (None, "") for t in cat.TIERS):
                problem("severity", "Bu uyarının eşiği yok; yalnız önemi seçilir.")
            if row.get("severity") not in cat.SEVERITIES:
                problem("severity", "Önem seçilmeli.")
            new["severity"] = row.get("severity")
        else:
            if row.get("severity") not in (None, ""):
                problem("severity", "Eşikli uyarıda önem kademelerle belirlenir.")
            previous = None                                   # (önem, değer): bir önceki dolu kademe
            for tier, severity in zip(cat.TIERS, cat.SEVERITIES):
                value, text = _threshold(w, row.get(tier))
                if text:
                    problem(tier, text)
                    continue
                new[tier] = value
                if value is None:
                    continue
                if previous is not None and not (value > previous[1] if w.direction == cat.ABOVE else value < previous[1]):
                    problem(tier, f"{severity} eşiği {previous[0]} eşiğinden {'büyük' if w.direction == cat.ABOVE else 'küçük'} olmalı.")
                previous = (severity, value)
            if active and previous is None and not any(p["field"].startswith(f"rows.{i}.") for p in problems):
                problem("active", "Aktif uyarıda en az bir kademe dolu olmalı.")
        planned.append((w, new))
    if problems:
        raise ParamError(problems)
    changed = 0
    for w, new in planned:
        old = current[w.code]
        before = {"IsActive": old["active"], "Severity": old["severity"], **{cat.TIER_COLUMNS[t]: old[t] for t in cat.TIERS}}
        after = {"IsActive": new["active"], "Severity": new["severity"], **{cat.TIER_COLUMNS[t]: _plain(new[t]) for t in cat.TIERS}}
        diff = [k for k in after if after[k] != before[k]]
        if not diff:
            continue
        values = {k: (new[t] if (t := next((t for t, c in cat.TIER_COLUMNS.items() if c == k), None)) else after[k]) for k in diff}
        session.execute(sa.update(WARNING).where(WARNING.c.ScenarioDefinitionId == scenario_id, WARNING.c.WarningCode == w.code).values(**values))
        changed += 1
        if on_change:
            on_change(w.label, {k: before[k] for k in diff}, {k: after[k] for k in diff})
    return changed


def warning_thresholds(session: Session, scenario_id: int) -> list[dict]:
    """Motorun ve plan ekranlarının okuduğu eşikler (docs/09): senaryonun aktif uyarıları. Eşikli uyarıda dolu kademeler, eşiksiz uyarıda önem."""
    return [{"Code": r["code"], "Category": r["category"], "Unit": r["unit"], "Direction": r["direction"], "Low": r["low"], "Medium": r["medium"],
             "High": r["high"], "Critical": r["critical"], "Severity": r["severity"]}
            for r in read_warning_thresholds(session, scenario_id) if r["active"]]
