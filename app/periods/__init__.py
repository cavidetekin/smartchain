"""Dönem tabloları (K-184): ortak dönem listesi, önbellek ve hesap işlevleri. Liste katmanından bağımsızdır; ekran da motor da buradan okur.

Hesaplar kendi alanlarındadır (kapasite: `app/capacity/compute.py`) ve buraya kaydolur; böylece önbelleğin yönetimi (senaryo silinince düşürme,
yönetim komutu) hesabın ayrıntısını bilmez.
"""
from . import cache, periods
from .periods import Period, read as read_periods

CACHES: dict[str, cache.DayCache] = {}
VALUES: dict = {}


def register(day_cache: cache.DayCache, values) -> None:
    CACHES[day_cache.name] = day_cache
    VALUES[day_cache.name] = values


def load() -> None:
    """Hesapların kaydolması (ilk kullanımda): hesap modülleri bu paketi içe aktardığı için burada tepede içe aktarılamaz."""
    from app.capacity import compute  # noqa: F401


def values(session, name: str, scenario_id: int, date_from, date_to, masters=None) -> list[dict]:
    """Dönem değerlerinin tek hesabı (docs/09): motor plan hesabında bunu çağırır; önbellek aynı hesapla kurulur."""
    load()
    return VALUES[name](session, scenario_id, date_from, date_to, masters)


def drop_scenario(session, scenario_id: int) -> None:
    """Senaryo silindi, pasif yapıldı ya da Baz'dan ayrıldı: bütün önbelleklerdeki satırları düşer."""
    load()
    for c in CACHES.values():
        cache.drop(session, c, scenario_id)


__all__ = ["CACHES", "Period", "cache", "drop_scenario", "load", "periods", "read_periods", "register", "values"]
