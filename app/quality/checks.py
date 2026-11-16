"""Smartchain'de yönetilen veriden gelen veri kalitesi kontrolleri (K-174, kaynak b). Validasyon kuralları ekranında görünmez, kapatılamaz.

6.5'te tek kontrol: kapasitesi tanımsız kaynak (K-117). Aşama 7 ekranları (kapasite yönetimi, malzeme blokajı) kendi kontrollerini buraya ekler.
"""
from collections.abc import Callable
from dataclasses import dataclass

import sqlalchemy as sa


@dataclass(frozen=True)
class SmartchainCheck:
    code: str
    table: str                # core tablosu
    title: str                # listede "Kural"
    message: str              # mesajın başı; sonuna kaydın kodu
    where: Callable[[sa.Table], sa.ColumnElement]
    fix_field: str | None = None  # Kural oluştur'un hedefi; Smartchain alanı veri kuralıyla doldurulamaz


def _active(t) -> sa.ColumnElement:
    return sa.or_(t.c.IsActive.is_(None), t.c.IsActive == sa.true())


CHECKS: tuple[SmartchainCheck, ...] = (
    SmartchainCheck("SC.RES_NO_CAPACITY", "Resource", "Kapasitesi tanımsız kaynak", "Kapasite tanımsız:",
                    lambda t: sa.and_(_active(t), t.c.IsCritical == sa.true(), t.c.DailyCapacity.is_(None))),
)
BY_CODE = {c.code: c for c in CHECKS}
