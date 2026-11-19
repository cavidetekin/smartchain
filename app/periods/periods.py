"""Ortak dönem listesi (K-184): senaryonun planlama ufkundaki dönemler ve dönem alanları. Etiketler tek yerden; pivot ve Excel de bunu kullanır.

Yeniden hesap yoktur: dönemler `app/params/horizon.py`'nin parçalarından düzleştirilir (Parametreler ekranındaki önizlemeyle aynı dönemler)."""
import json
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.params import catalog as cat, horizon, service as params

MONTHS = ("Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara")
# Liste tarafındaki dönem adları (grafik, pivot) → dönem tipi
KIND_OF_BUCKET = {"day": cat.DAY, "week": cat.WEEK, "month": cat.MONTH, "quarter": cat.QUARTER, "year": cat.YEAR}


def week_of(day: date, week_start: int = 0) -> str:
    """Günün haftası, haftanın kendi yılıyla ("H1 2027" 28.12.2026'da başlayabilir). Hafta, hafta başlangıcı gününden sayılır; numarası
    haftanın dördüncü gününün ISO haftasıdır (grafik ve pivottaki kural)."""
    first = day - timedelta(days=(day.weekday() - week_start) % 7)
    year, week, _ = (first + timedelta(days=3)).isocalendar()
    return f"H{week} {year}"


def month_of(day: date) -> str:
    return f"{MONTHS[day.month - 1]} {day.year}"


def quarter_of(day: date) -> str:
    return f"Ç{(day.month - 1) // 3 + 1} {day.year}"


def label(kind: str, start: date, week_start: int = 0) -> str:
    """Dönemin etiketi: gün "19.11.2026", hafta "H47 2026", ay "Kas 2026", çeyrek "Ç4 2026", yıl "2026"."""
    if kind == cat.DAY:
        return f"{start:%d.%m.%Y}"
    if kind == cat.WEEK:
        return week_of(start, week_start)
    if kind == cat.MONTH:
        return month_of(start)
    return quarter_of(start) if kind == cat.QUARTER else str(start.year)


@dataclass(frozen=True)
class Period:
    no: int        # 1'den, dönem başı sırasıyla
    type: str      # Gün · Hafta · Ay · Çeyrek · Yıl
    label: str
    start: date
    end: date
    week: str      # dönem başının haftası (yılıyla)
    month: str
    quarter: str
    year: str      # dönem başının takvim yılı
    days: int      # dönemin takvim günü sayısı


def build(parts: list[horizon.Part], week_start: int = 0) -> list[Period]:
    out: list[Period] = []
    for part in parts:
        for b in part.buckets:
            out.append(Period(no=len(out) + 1, type=b.kind, label=label(b.kind, b.start, week_start), start=b.start, end=b.end,
                              week=week_of(b.start, week_start), month=month_of(b.start), quarter=quarter_of(b.start), year=str(b.start.year),
                              days=(b.end - b.start).days + 1))
    return out


def read(session: Session, scenario_id: int, today: date) -> list[Period]:
    """Senaryonun plan eksenindeki dönemleri (K-175): plan başlangıcından, hafta başlangıcı ayarıyla."""
    settings = params.read_settings(session, scenario_id)
    return build(params.read_parts(session, scenario_id, today), horizon.week_start_index(settings.get("WeekStart")))


def to_json(periods: list[Period]) -> str:
    """Dönemler SQL'e tek parametreyle gider (OPENJSON); alan adları `PERIOD_JSON_SCHEMA` ile aynı."""
    return json.dumps([{"no": p.no, "type": p.type, "label": p.label, "start": p.start.isoformat(), "end": p.end.isoformat(), "week": p.week,
                        "month": p.month, "quarter": p.quarter, "year": p.year, "days": p.days} for p in periods], ensure_ascii=False)


PERIOD_JSON_SCHEMA = ("[no] int, [type] nvarchar(10), [label] nvarchar(20), [start] date, [end] date, [week] nvarchar(12), [month] nvarchar(12), "
                      "[quarter] nvarchar(12), [year] nvarchar(4), [days] int")


def days_json(periods: list[Period]) -> str:
    """Ufkun her günü, ait olduğu dönemin sırasıyla: günlük ara sonucu döneme toplarken eşitlikle birleştirilir."""
    out = []
    for p in periods:
        day = p.start
        while day <= p.end:
            out.append({"d": day.isoformat(), "no": p.no})
            day += timedelta(days=1)
    return json.dumps(out)


DAY_JSON_SCHEMA = "[d] date, [no] int"
