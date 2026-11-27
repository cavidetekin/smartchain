"""Pegging sıralama ölçütleri (K-201; Parametreler › Pegging): iki listenin tek tanımı, okunması ve yazılması.

İki liste: **İhtiyaç sırası** (ihtiyaçlar hangi sırayla ele alınır) ve **Arz sırası** (her ihtiyaç arzı hangi sırayla tüketir). Ölçütler yukarıdan
aşağı uygulanır; yönlü ölçütte yön seçilir. Kullanıcı yalnız sırayı ve yönü değiştirir: ölçüt eklenmez, silinmez, yinelenmez.

Talep türleri (Kesin sipariş · Teklif · Beklemedeki sipariş · Tahmin) Hedefler'le aynı kaynaktan üretilir (`catalog.DEMAND_TYPES`, K-196); ikinci
bir liste yazılmaz. Senaryoda satır yoksa başlangıç sırası geçerlidir; ilk kayıtta listenin tamamı yazılır. Tanıma sonradan eklenen ölçüt eski
senaryolarda başlangıçtaki komşusunun ardına eklenir, tanımdan kalkan atılır.

Bu ayarları bugün hiçbir hesap kullanmaz: pegging 10.6'da, model (özel alokasyon) 10.4'te okur (`ScenarioParameters.pegging`).
"""
from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.planning import movements
from db.models import metadata

from . import catalog as cat
from .service import ParamError, read_settings, save_settings

TABLE = metadata.tables["param.PeggingCriterion"]
NEED, SUPPLY = "İhtiyaç", "Arz"
SIDES = {"need": NEED, "supply": SUPPLY}       # API'deki alan adı → saklanan liste adı
METHOD = "FullPeggingMethod"
ASC, DESC, NEAREST = "Artan", "Azalan", "İhtiyaca en yakın"

# Yön seçeneğinin ipucu, ölçütün türüne göre (ekranda yer tutan açıklama yazısı yoktur)
_TIME = {ASC: "erken önce", DESC: "geç önce"}
_GROUP = {ASC: "1 önce", DESC: "5 önce"}
_NUMBER = {ASC: "küçük numara önce", DESC: "büyük numara önce"}
_NEAREST = {NEAREST: "ihtiyacın döneminden geriye, yetmezse ileriye"}


@dataclass(frozen=True)
class Criterion:
    name: str
    hints: tuple[tuple[str, str], ...] = ()    # (yön, ipucu); boşsa ölçüt yönsüzdür (ihtiyaç ya da arz türü)

    @property
    def directions(self) -> tuple[str, ...]:
        return tuple(d for d, _ in self.hints)

    @property
    def default(self) -> str | None:
        return self.hints[0][0] if self.hints else None


def _directed(name: str, *hints: dict) -> Criterion:
    return Criterion(name, tuple((d, h) for group in hints for d, h in group.items()))


# arz ve ihtiyaç türlerinin adları malzeme hareketlerinin tek tanımından (K-202, `app/planning/movements.py`)
PRODUCTION_ORDER_NEED, PRODUCTION_PLAN_NEED = movements.PRODUCTION_ORDER_NEED, movements.PRODUCTION_PLAN_NEED

# Başlangıç sırası tanımın sırasıdır (K-201 madde 4 ve 5)
CRITERIA: dict[str, tuple[Criterion, ...]] = {
    NEED: (
        _directed("Dönem", _TIME),
        *(Criterion(t) for t in cat.DEMAND_TYPES),          # talep türleri: Hedefler'le aynı kaynak
        Criterion(PRODUCTION_ORDER_NEED), Criterion(PRODUCTION_PLAN_NEED),
        _directed("Öncelik grubu", _GROUP), _directed("İhtiyaç tarihi", _TIME), _directed("Sipariş no", _NUMBER),
    ),
    SUPPLY: (
        _directed("Dönem", _TIME, _NEAREST),
        Criterion(movements.STOCK), Criterion(movements.QUALITY_STOCK), Criterion(movements.PRODUCTION_ORDER), Criterion(movements.PURCHASE_ORDER),
        _directed("Arz tarihi", _TIME),
        Criterion(movements.PRODUCTION_PLAN), Criterion(movements.PURCHASE_PLAN),
        _directed("Son kullanma tarihi", _TIME),
    ),
}
BY_NAME = {side: {c.name: c for c in items} for side, items in CRITERIA.items()}
assert all(len(BY_NAME[s]) == len(CRITERIA[s]) for s in CRITERIA), "ölçüt adı yinelendi"


def start(side: str) -> list[tuple[str, str | None]]:
    """Listenin başlangıç sırası ve yönleri."""
    return [(c.name, c.default) for c in CRITERIA[side]]


def _complete(side: str, stored: list[tuple[str, str | None]]) -> list[tuple[str, str | None]]:
    """Saklanan liste tanıma uydurulur: tanımdan kalkan atılır, geçersiz yön başlangıç yönüne döner, eksik ölçüt başlangıçtaki komşusunun ardına girer."""
    known = BY_NAME[side]
    out = [(n, d if d in known[n].directions else known[n].default) for n, d in stored if n in known]
    have = {n for n, _ in out}
    order = [c.name for c in CRITERIA[side]]
    for i, name in enumerate(order):
        if name in have:
            continue
        before = next((p for p in reversed(order[:i]) if p in have), None)     # başlangıç sırasında kendinden önceki, listede olan ilk ölçüt
        at = next(j for j, (n, _) in enumerate(out) if n == before) + 1 if before else 0
        out.insert(at, (name, known[name].default))
        have.add(name)
    return out


def read_list(session: Session, scenario_id: int, side: str) -> list[tuple[str, str | None]]:
    """Senaryonun listesi, sırasıyla: (ölçüt, yön). Satır yoksa başlangıç sırası."""
    rows = session.execute(sa.select(TABLE.c.Criterion, TABLE.c.Direction).where(TABLE.c.ScenarioDefinitionId == scenario_id, TABLE.c.Side == side)
                           .order_by(TABLE.c.Seq)).all()
    return _complete(side, [(r.Criterion, r.Direction) for r in rows]) if rows else start(side)


def read(session: Session, scenario_id: int) -> dict:
    """Ekranın okuduğu hâl: yöntem ve iki liste; her ölçütte yön seçenekleri ve ipuçları."""
    method = cat.BY_KEY[METHOD]

    def rows(side: str) -> list[dict]:
        return [{"criterion": name, "direction": direction, "directions": [{"value": d, "hint": h} for d, h in BY_NAME[side][name].hints]}
                for name, direction in read_list(session, scenario_id, side)]

    return {"method": {"key": METHOD, "label": method.label, "value": read_settings(session, scenario_id)[METHOD], "options": list(method.options)},
            **{field: rows(side) for field, side in SIDES.items()}}


def _checked(field: str, side: str, rows) -> tuple[list[tuple[str, str | None]], list[dict]]:
    """Gelen liste: tanımdaki ölçütlerin tamamı, birer kez; yön yalnız yönlü ölçütte ve seçeneklerinden biri."""
    known = BY_NAME[side]
    problems, out = [], []
    names = [str(r.get("criterion")) if isinstance(r, dict) else "" for r in rows] if isinstance(rows, list) else None
    if names is None:
        return [], [{"field": field, "problem": "Liste bekleniyor."}]
    unknown = [n for n in names if n not in known]
    repeated = sorted({n for n in names if names.count(n) > 1 and n in known})
    missing = [c.name for c in CRITERIA[side] if c.name not in names]
    if unknown:
        problems.append({"field": field, "problem": f"Bilinmeyen ölçüt: {', '.join(unknown)}."})
    if repeated:
        problems.append({"field": field, "problem": f"Ölçüt yinelenemez: {', '.join(repeated)}."})
    if missing:
        problems.append({"field": field, "problem": f"Ölçüt çıkarılamaz: {', '.join(missing)}."})
    if problems:
        return [], problems
    for row, name in zip(rows, names):
        direction = row.get("direction") or None
        allowed = known[name].directions
        if allowed and direction not in allowed:
            problems.append({"field": field, "problem": f"{name}: yön {' · '.join(allowed)} olabilir."})
        elif not allowed and direction is not None:
            problems.append({"field": field, "problem": f"{name}: bu ölçütün yönü yoktur."})
        out.append((name, direction))
    return out, problems


def text_of(rows: list[tuple[str, str | None]]) -> list[str]:
    """İzdeki okunur hâl: "Dönem (Artan)", "Stok"."""
    return [f"{name} ({direction})" if direction else name for name, direction in rows]


def save(session: Session, scenario_id: int, body: dict, on_setting=None, on_list=None) -> dict:
    """Yöntem ve iki liste tek işlemde; yalnız değişen yazılır, biri geçersizse hiçbiri yazılmaz. Dönen: değişenler.

    on_setting(anahtar, eski, yeni) ve on_list(liste adı, eski sıra, yeni sıra) değişiklikte çağrılır (iz)."""
    problems, lists = [], {}
    for field, side in SIDES.items():
        if field not in body:
            continue
        rows, found = _checked(field, side, body[field])
        problems += found
        lists[side] = rows
    if problems:
        raise ParamError(problems)
    changed: dict = {}
    if "method" in body:
        try:
            if save_settings(session, scenario_id, {METHOD: body["method"]}, on_setting):
                changed["method"] = True
        except ParamError as err:
            raise ParamError([{"field": "method", "problem": p["problem"]} for p in err.problems]) from None
    for side, rows in lists.items():
        current = read_list(session, scenario_id, side)
        if rows == current:
            continue
        session.execute(sa.delete(TABLE).where(TABLE.c.ScenarioDefinitionId == scenario_id, TABLE.c.Side == side))
        session.execute(sa.insert(TABLE), [{"ScenarioDefinitionId": scenario_id, "Side": side, "Seq": i, "Criterion": name, "Direction": direction}
                                           for i, (name, direction) in enumerate(rows, start=1)])
        changed[side] = True
        if on_list:
            on_list(side, text_of(current), text_of(rows))
    return changed
