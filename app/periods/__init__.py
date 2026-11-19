"""Dönem tabloları (K-184): ortak dönem listesi, önbellek ve hesap işlevleri. Liste katmanından bağımsızdır; ekran da motor da buradan okur."""
from . import cache, capacity_demo, periods
from .periods import Period, read as read_periods

CACHES = {capacity_demo.CACHE.name: capacity_demo.CACHE}
VALUES = {capacity_demo.CACHE.name: capacity_demo.values}


def values(session, name: str, scenario_id: int, date_from, date_to, masters=None) -> list[dict]:
    """Dönem değerlerinin tek hesabı (docs/09): motor plan hesabında bunu çağırır; önbellek aynı hesapla kurulur."""
    return VALUES[name](session, scenario_id, date_from, date_to, masters)


def drop_scenario(session, scenario_id: int) -> None:
    """Senaryo silindi, pasif yapıldı ya da Baz'dan ayrıldı: bütün önbelleklerdeki satırları düşer."""
    for c in CACHES.values():
        cache.drop(session, c, scenario_id)


__all__ = ["CACHES", "Period", "cache", "capacity_demo", "drop_scenario", "periods", "read_periods", "values"]
