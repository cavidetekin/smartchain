"""Akış zamanı (K-163): saat (SS:DD) ve haftanın günleri (1 Pazartesi … 7 Pazar), sunucunun yerel saatiyle.

Veritabanında zamanlar UTC saklanır; yerel saat yalnız akışın saatini hesaplarken ve gösterirken kullanılır.
"""
import re
from datetime import date, datetime, time, timedelta, timezone

TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
DAY_NAMES = {1: "Pazartesi", 2: "Salı", 3: "Çarşamba", 4: "Perşembe", 5: "Cuma", 6: "Cumartesi", 7: "Pazar"}
SHORT_DAYS = {1: "Pzt", 2: "Sal", 3: "Çar", 4: "Per", 5: "Cum", 6: "Cmt", 7: "Paz"}
LOOKBACK_DAYS = 7


def valid_time(value: str) -> bool:
    return bool(TIME_RE.match(value or ""))


def parse_days(value: str | None) -> list[int]:
    """"1,2,3" → [1, 2, 3]; bozuk değerler atlanır, sıralı ve tekrarsız."""
    out = set()
    for part in (value or "").split(","):
        part = part.strip()
        if part.isdigit() and 1 <= int(part) <= 7:
            out.add(int(part))
    return sorted(out)


def format_days(days: list[int]) -> str:
    return ",".join(str(d) for d in sorted(set(days)))


def days_text(days: list[int]) -> str:
    """Arayüz ve hata metni: "Her gün", "Hafta içi", "Pzt, Çar"."""
    days = sorted(set(days))
    if days == [1, 2, 3, 4, 5, 6, 7]:
        return "Her gün"
    if days == [1, 2, 3, 4, 5]:
        return "Hafta içi"
    if days == [6, 7]:
        return "Hafta sonu"
    return ", ".join(SHORT_DAYS[d] for d in days)


def _at(day: date, run_time: str) -> datetime:
    h, m = (int(x) for x in run_time.split(":"))
    return datetime.combine(day, time(h, m))


def last_due(run_time: str, days: list[int], now_local: datetime) -> datetime | None:
    """Şimdiye kadarki son saat (yerel, saniyesiz); son bir haftada yoksa None."""
    if not valid_time(run_time) or not days:
        return None
    for back in range(LOOKBACK_DAYS + 1):
        day = now_local.date() - timedelta(days=back)
        at = _at(day, run_time)
        if day.isoweekday() in days and at <= now_local:
            return at
    return None


def next_due(run_time: str, days: list[int], now_local: datetime) -> datetime | None:
    """Şimdiden sonraki ilk saat (yerel)."""
    if not valid_time(run_time) or not days:
        return None
    for ahead in range(LOOKBACK_DAYS + 1):
        day = now_local.date() + timedelta(days=ahead)
        at = _at(day, run_time)
        if day.isoweekday() in days and at > now_local:
            return at
    return None


def local_to_utc(value: datetime) -> datetime:
    """Yerel (saf) → UTC (saf). Saf datetime'ı Python sunucunun saat dilimiyle yorumlar."""
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def utc_to_local(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc).astimezone().replace(tzinfo=None)


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def hhmm(value_utc: datetime | None) -> str:
    return utc_to_local(value_utc).strftime("%H:%M") if value_utc else ""
