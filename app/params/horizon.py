"""Ufuk ve dönem hesabı (fonksiyon 23, K-175). Kullanıcı tarih girmez: her satır bir parçadır (dönem tipi, kapsam, kapsam birimi); başlangıç ve
bitiş plan başlangıcından hesaplanır ve her gün kayar.

Kurallar:
- Parça öncekinin bittiği günün ertesinde başlar (ilki plan başlangıcında).
- Kapsam birimi Gün: parça kapsam kadar gün sürer. Hafta, Ay, Çeyrek ya da Yıl: içinde bulunulan hafta, ay, çeyrek ya da yıl sayıya dahildir ve
  parça o birimin takvim sınırında biter (hafta sonu, ay sonu, çeyrek sonu, yıl sonu).
- Parçanın içindeki dönemler dönem tipinin takvim sınırlarına oturur: haftalık dönem hafta başlangıcı gününde başlar, aylık dönem ay sonunda
  biter (çeyrek ve yıl da öyle). Parçanın başında ya da sonunda sınıra denk gelmeyen dönem kısa kalır ve sayılır.
"""
from dataclasses import dataclass
from datetime import date, timedelta

from .catalog import DAY, MONTH, QUARTER, RANK, WEEK, WEEKDAYS, YEAR


@dataclass(frozen=True)
class Bucket:
    start: date
    end: date
    kind: str


@dataclass(frozen=True)
class Part:
    bucket_type: str
    count: int
    span_unit: str
    start: date
    end: date
    buckets: tuple[Bucket, ...]


def week_start_index(name: str | None) -> int:
    """Hafta başlangıcı gününün sırası (Pazartesi 0)."""
    return WEEKDAYS.index(name) if name in WEEKDAYS else 0


def _month_end(d: date, months_ahead: int = 0) -> date:
    m = d.month - 1 + months_ahead + 1  # izleyen ayın sıfır tabanlı sırası
    return date(d.year + m // 12, m % 12 + 1, 1) - timedelta(days=1)


def _week_end(d: date, week_start: int) -> date:
    return d + timedelta(days=(week_start - 1 - d.weekday()) % 7)


def _period_end(d: date, kind: str, week_start: int) -> date:
    """d'yi içeren dönemin son günü."""
    if kind == DAY:
        return d
    if kind == WEEK:
        return _week_end(d, week_start)
    if kind == MONTH:
        return _month_end(d)
    if kind == QUARTER:
        return _month_end(d, 2 - (d.month - 1) % 3)
    if kind == YEAR:
        return date(d.year, 12, 31)
    raise ValueError(f"Bilinmeyen dönem tipi: {kind}")


def span_end(start: date, count: int, unit: str, week_start: int) -> date:
    """Parçanın son günü: içinde bulunulan hafta ya da ay sayıya dahil."""
    if unit == DAY:
        return start + timedelta(days=count - 1)
    if unit == WEEK:
        return _week_end(start, week_start) + timedelta(weeks=count - 1)
    if unit == MONTH:
        return _month_end(start, count - 1)
    if unit == QUARTER:
        return _month_end(start, 2 - (start.month - 1) % 3 + 3 * (count - 1))
    if unit == YEAR:
        return date(start.year + count - 1, 12, 31)
    raise ValueError(f"Bilinmeyen kapsam birimi: {unit}")


def parts(start: date, rows: list[tuple[str, int, str]], week_start: int = 0) -> list[Part]:
    """Satırlardan (dönem tipi, kapsam, kapsam birimi) parçalar ve dönemleri."""
    out, at = [], start
    for bucket_type, count, unit in rows:
        end = span_end(at, int(count), unit, week_start)
        buckets, day = [], at
        while day <= end:
            last = min(_period_end(day, bucket_type, week_start), end)
            buckets.append(Bucket(day, last, bucket_type))
            day = last + timedelta(days=1)
        out.append(Part(bucket_type, int(count), unit, at, end, tuple(buckets)))
        at = end + timedelta(days=1)
    return out


def problems(rows: list[tuple[str, int | None, str]], bucket_types: tuple[str, ...]) -> list[dict]:
    """Dizinin denetimleri; satır numarasıyla (1'den)."""
    out = []
    if not rows:
        return [{"field": "rows", "problem": "En az bir satır olmalı."}]
    previous = 0
    for i, (bucket_type, count, unit) in enumerate(rows, start=1):
        if bucket_type not in bucket_types:
            out.append({"field": f"rows.{i}.BucketType", "problem": "Listedeki değerlerden biri girilmeli."})
            continue
        if unit not in RANK:
            out.append({"field": f"rows.{i}.SpanUnit", "problem": "Listedeki değerlerden biri girilmeli."})
            continue
        if count is None or int(count) < 1:
            out.append({"field": f"rows.{i}.Count", "problem": "En az 1 olmalı."})
        # kapsam birimi dönem tipinden küçük olamaz (çeyrek ve yıl dönem tipinde kapsam birimi Ay da olabilir: ay, çeyreği ve yılı tam böler)
        if RANK[unit] < min(RANK[bucket_type], RANK[MONTH]):
            out.append({"field": f"rows.{i}.SpanUnit", "problem": "Kapsam birimi dönem tipinden küçük olamaz."})
        if RANK[bucket_type] < previous:
            out.append({"field": f"rows.{i}.BucketType", "problem": "Dönemler inceden kabaya sıralanır (Gün, Hafta, Ay, Çeyrek, Yıl)."})
        previous = max(previous, RANK[bucket_type])
    return out
