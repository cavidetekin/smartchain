"""Dönem tablosu önbelleği (K-184): ana kayıt × gün ara sonucu `cache` şemasında durur. Veri değildir: girişlerden hesaplanır, silinirse yeniden
üretilir. Ekran açılırken hesap yapılmaz; okuma önbellekten. Giriş değişince yalnız etkilenen ana kayıt ve günler yenilenir (`invalidate`).

Boyut kuralları: yalnız ufuktaki günler tutulur; Baz'ı izleyen senaryo yalnız kendi girişi olan ana kayıt ve günleri tutar (gerisi Baz'ın
satırlarından okunur); eski veri versiyonunun önbelleği tutulmaz; silinen ya da pasif yapılan senaryonun satırları düşer.
"""
import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Callable, Iterable

import sqlalchemy as sa
from sqlalchemy.orm import Session

from db.models import metadata

log = logging.getLogger("smartchain.periods")
STATE = metadata.tables["cache.PeriodCacheState"]
SCENARIO = metadata.tables["param.ScenarioDefinition"]
VERSION = metadata.tables["adm.DataVersion"]


@dataclass(frozen=True)
class Scope:
    """Hesabın kapsamı: senaryo, Baz (senaryo Baz'ı izliyorsa; yoksa None), gün aralığı, ana kayıtlar (None: hepsi)."""
    scenario_id: int
    base_id: int | None
    date_from: date
    date_to: date
    masters: tuple[int, ...] | None = None

    def params(self) -> dict:
        return {"sid": self.scenario_id, "base": self.base_id, "dfrom": self.date_from, "dto": self.date_to,
                "ids": None if self.masters is None else json.dumps(list(self.masters))}


@dataclass(frozen=True)
class DayCache:
    """Bir önbellek tablosu ve hesabı. `select(own_only)` günlük satırları üreten SELECT metnidir (kolonlar tablonun sırasıyla; parametreler
    `Scope.params()`): own_only doğruysa yalnız senaryonun kendi girişi olan ana kayıt ve günler (Baz'ı izleyen senaryonun tuttuğu fark)."""
    name: str
    table: sa.Table
    master: str                              # ana kayıt kolonu (ör. ResourceId)
    values: tuple[str, ...]                  # değer kolonları
    code_version: int                        # hesap değişince artırılır: önbellek düşürülüp yeniden kurulur
    select: Callable[[bool], str]

    @property
    def full_name(self) -> str:
        return f"[{self.table.schema}].[{self.table.name}]"

    @property
    def columns(self) -> str:
        return ", ".join(f"[{c}]" for c in ("ScenarioDefinitionId", self.master, "Date", *self.values))


def scenario_row(session: Session, scenario_id: int) -> dict:
    row = session.execute(sa.select(SCENARIO.c.Id, SCENARIO.c.IsBase, SCENARIO.c.FollowsBase, SCENARIO.c.IsActive)
                          .where(SCENARIO.c.Id == scenario_id)).mappings().first()
    if row is None:
        raise LookupError(f"Senaryo bulunamadı: {scenario_id}")
    return dict(row)


def base_id(session: Session) -> int | None:
    return session.execute(sa.select(SCENARIO.c.Id).where(SCENARIO.c.IsBase == sa.true())).scalar()


def base_of(session: Session, scenario: dict) -> int | None:
    """Senaryonun okuduğu Baz: Baz'ı izliyorsa Baz'ın kimliği; Baz'ın kendisinde ve izlemeyen senaryoda None."""
    if scenario["IsBase"] or not scenario["FollowsBase"]:
        return None
    return base_id(session)


def _data_version(session: Session) -> int | None:
    return session.execute(sa.select(sa.func.max(VERSION.c.Id))).scalar()


def _lock(session: Session, cache: DayCache, scenario_id: int) -> None:
    """Aynı önbelleği iki istek birlikte kurmasın: işlem boyunca uygulama kilidi (işlem bitince kendiliğinden bırakılır)."""
    session.execute(sa.text("EXEC sp_getapplock @Resource = :r, @LockMode = 'Exclusive', @LockOwner = 'Transaction', @LockTimeout = 60000"),
                    {"r": f"smartchain-period-cache:{cache.name}:{scenario_id}"})


def _state(session: Session, cache: DayCache, scenario_id: int) -> dict | None:
    row = session.execute(sa.select(STATE).where(STATE.c.CacheName == cache.name, STATE.c.ScenarioDefinitionId == scenario_id)).mappings().first()
    return dict(row) if row else None


def _delete(session: Session, cache: DayCache, scenario_id: int, date_from: date | None = None, date_to: date | None = None,
            masters: Iterable[int] | None = None) -> int:
    where, p = ["[ScenarioDefinitionId] = :sid"], {"sid": scenario_id}
    if date_from is not None:
        where.append("[Date] >= :dfrom")
        p["dfrom"] = date_from
    if date_to is not None:
        where.append("[Date] <= :dto")
        p["dto"] = date_to
    if masters is not None:
        where.append(f"[{cache.master}] IN (SELECT CAST(value AS bigint) FROM OPENJSON(:ids))")
        p["ids"] = json.dumps(list(masters))
    return session.execute(sa.text(f"DELETE FROM {cache.full_name} WHERE {' AND '.join(where)}"), p).rowcount


def _fill(session: Session, cache: DayCache, scope: Scope) -> int:
    """Kapsamın satırlarını girişlerden hesaplayıp yazar (önce silinmiş olmalı)."""
    if scope.date_from > scope.date_to:
        return 0
    sql = f"INSERT INTO {cache.full_name} ({cache.columns}) {cache.select(scope.base_id is not None)}"
    return session.execute(sa.text(sql), scope.params()).rowcount


def _save_state(session: Session, cache: DayCache, scenario_id: int, date_from: date, date_to: date, version: int | None, built: bool) -> None:
    values = {"CodeVersion": cache.code_version, "DataVersionId": version, "DateFrom": date_from, "DateTo": date_to}
    if built:
        values["BuiltAt"] = datetime.now(timezone.utc).replace(tzinfo=None)
    key = sa.and_(STATE.c.CacheName == cache.name, STATE.c.ScenarioDefinitionId == scenario_id)
    if session.execute(sa.update(STATE).where(key).values(**values)).rowcount == 0:
        values.setdefault("BuiltAt", datetime.now(timezone.utc).replace(tzinfo=None))
        session.execute(sa.insert(STATE).values(CacheName=cache.name, ScenarioDefinitionId=scenario_id, **values))


def ensure(session: Session, cache: DayCache, scenario_id: int, date_from: date, date_to: date) -> dict:
    """Okumadan önce: senaryonun (ve izliyorsa Baz'ın) önbelleği [date_from, date_to] aralığını kapsar hâle gelir. Kurulu ve güncelse hiçbir
    şey yapmaz. Dönen: senaryo → yapılan iş ("built" tam kurulum, "extended" eksik günler, "trimmed" geçmiş günler silindi, "ready")."""
    scenario = scenario_row(session, scenario_id)
    base = base_of(session, scenario)
    done: dict[int, str] = {}
    # Baz'ın satırlarını izleyen senaryolar da okur: Baz'ın aralığı izleyen adına yalnız genişler; Baz'ın kendi isteğinde sonu kısalmaz
    if base is not None:
        done[base] = _ensure_one(session, cache, base, None, date_from, date_to, keep_start=True, keep_end=True)
    done[scenario_id] = _ensure_one(session, cache, scenario_id, base, date_from, date_to, keep_end=bool(scenario["IsBase"]))
    if any(v != "ready" for v in done.values()):
        session.commit()
    return done


def _ensure_one(session: Session, cache: DayCache, scenario_id: int, base: int | None, date_from: date, date_to: date,
                keep_start: bool = False, keep_end: bool = False) -> str:
    version = _data_version(session)

    def read() -> tuple[dict | None, bool, date, date]:
        state = _state(session, cache, scenario_id)
        fresh = state is not None and state["CodeVersion"] == cache.code_version and state["DataVersionId"] == version
        start = min(date_from, state["DateFrom"]) if fresh and keep_start else date_from
        end = max(date_to, state["DateTo"]) if fresh and keep_end else date_to
        return state, fresh, start, end

    state, fresh, date_from_, date_to_ = read()
    if fresh and state["DateFrom"] == date_from_ and state["DateTo"] == date_to_:
        return "ready"
    _lock(session, cache, scenario_id)
    state, fresh, date_from, date_to = read()  # kilidi beklerken başka istek kurmuş olabilir
    if not fresh:
        _delete(session, cache, scenario_id)
        rows = _fill(session, cache, Scope(scenario_id, base, date_from, date_to))
        _save_state(session, cache, scenario_id, date_from, date_to, version, built=True)
        log.info("Dönem önbelleği kuruldu: %s, senaryo %s, %s – %s, %s satır", cache.name, scenario_id, date_from, date_to, rows)
        return "built"
    if state["DateFrom"] == date_from and state["DateTo"] == date_to:
        return "ready"
    work = "trimmed"
    # ufkun dışında kalan günler tutulmaz (geçmiş günler; ufuk kısaldıysa sondakiler)
    if state["DateFrom"] < date_from:
        _delete(session, cache, scenario_id, date_to=date_from - timedelta(days=1))
    if state["DateTo"] > date_to:
        _delete(session, cache, scenario_id, date_from=date_to + timedelta(days=1))
    # önbellekte olmayan günler hesaplanır (ufuk ilerledi ya da uzadı); ötekilere dokunulmaz
    if date_from < state["DateFrom"]:
        _fill(session, cache, Scope(scenario_id, base, date_from, min(state["DateFrom"] - timedelta(days=1), date_to)))
        work = "extended"
    if date_to > state["DateTo"]:
        _fill(session, cache, Scope(scenario_id, base, max(state["DateTo"] + timedelta(days=1), date_from), date_to))
        work = "extended"
    _save_state(session, cache, scenario_id, date_from, date_to, version, built=False)
    return work


def followers(session: Session) -> list[int]:
    """Baz'ı izleyen senaryolar (Baz'daki değişiklik bunların aynı ana kayıt ve günlerini de yeniler)."""
    return [r[0] for r in session.execute(sa.select(SCENARIO.c.Id).where(SCENARIO.c.FollowsBase == sa.true(),
                                                                         sa.func.coalesce(SCENARIO.c.IsBase, sa.false()) == sa.false()))]


def invalidate(session: Session, cache: DayCache, scenario_id: int, masters: Iterable[int] | None = None,
               date_from: date | None = None, date_to: date | None = None) -> dict[int, int]:
    """Giriş değişti: yalnız etkilenen ana kayıt ve günler silinip girişlerden yeniden hesaplanır (masters None: bütün ana kayıtlar; tarih
    None: önbellekteki bütün günler). Baz'da çağrılırsa Baz'ı izleyen senaryolarda da aynı ana kayıt ve günler yenilenir. Kurulmamış
    önbelleğe dokunulmaz (ilk kullanımda zaten girişlerden kurulur). Girişi kaydeden işlemle aynı işlemde çalışır; commit çağıranındır.
    Dönen: senaryo → yeniden yazılan satır sayısı."""
    scenario = scenario_row(session, scenario_id)
    ids = None if masters is None else tuple(dict.fromkeys(int(m) for m in masters))
    targets = [scenario_id] + (followers(session) if scenario["IsBase"] else [])
    out: dict[int, int] = {}
    for sid in targets:
        state = _state(session, cache, sid)
        if state is None or state["CodeVersion"] != cache.code_version:
            continue
        _lock(session, cache, sid)
        start = max(date_from or state["DateFrom"], state["DateFrom"])
        end = min(date_to or state["DateTo"], state["DateTo"])
        if start > end or ids == ():
            out[sid] = 0
            continue
        base = base_of(session, scenario_row(session, sid))
        _delete(session, cache, sid, start, end, ids)
        out[sid] = _fill(session, cache, Scope(sid, base, start, end, ids))
    return out


def drop(session: Session, cache: DayCache, scenario_id: int | None = None) -> int:
    """Önbelleği boşaltır (senaryo verilmezse hepsi); ilk kullanımda yeniden kurulur. Senaryo silinince, pasif yapılınca ve Baz'dan ayrılınca."""
    key = [STATE.c.CacheName == cache.name] + ([STATE.c.ScenarioDefinitionId == scenario_id] if scenario_id is not None else [])
    session.execute(sa.delete(STATE).where(*key))
    if scenario_id is None:
        return session.execute(sa.text(f"DELETE FROM {cache.full_name}")).rowcount
    return _delete(session, cache, scenario_id)


def status(session: Session, cache: DayCache) -> list[dict]:
    rows = session.execute(sa.text(
        f"SELECT s.ScenarioDefinitionId, s.CodeVersion, s.DataVersionId, s.DateFrom, s.DateTo, s.BuiltAt, "
        f"(SELECT COUNT(*) FROM {cache.full_name} c WHERE c.ScenarioDefinitionId = s.ScenarioDefinitionId) AS [Rows] "
        "FROM cache.PeriodCacheState s WHERE s.CacheName = :n ORDER BY s.ScenarioDefinitionId"), {"n": cache.name}).mappings()
    return [dict(r) for r in rows]


def effective_sql(cache: DayCache) -> str:
    """Senaryonun geçerli günlük satırları: senaryonun satırı varsa o, yoksa (Baz'ı izliyorsa) Baz'ın satırı. Parametreler: :sid, :base."""
    values = ", ".join(f"CASE WHEN s.[{cache.master}] IS NOT NULL THEN s.[{v}] ELSE b.[{v}] END AS [{v}]" for v in cache.values)
    return (f"SELECT b.[{cache.master}], b.[Date], {values} FROM {cache.full_name} b "
            f"LEFT JOIN {cache.full_name} s ON s.[ScenarioDefinitionId] = :sid AND :base IS NOT NULL AND s.[{cache.master}] = b.[{cache.master}] AND s.[Date] = b.[Date] "
            "WHERE b.[ScenarioDefinitionId] = COALESCE(:base, :sid)")
