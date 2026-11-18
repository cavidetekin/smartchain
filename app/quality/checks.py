"""Smartchain'de yönetilen veriden gelen veri kalitesi kontrolleri (K-174, kaynak b). Validasyon kuralları ekranında görünmez, kapatılamaz.

6.5'te tek kontrol: kapasitesi tanımsız kaynak (K-117). Aşama 7 ekranları (kapasite yönetimi, malzeme blokajı) kendi kontrollerini buraya ekler.
"""
from collections.abc import Callable
from dataclasses import dataclass

import sqlalchemy as sa

from db.models import metadata


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


def _in_critical_group(t) -> sa.ColumnElement:
    """Kaynak en az bir aktif kritik gruba üye (K-180: kritiklik kaynak grubundadır)."""
    m = metadata.tables["core.ResourceGroupMember"].alias("sc_member")
    g = metadata.tables["core.ResourceGroup"].alias("sc_group")
    return sa.exists().where(m.c.ResourceId == t.c.Id, m.c.VersionTo.is_(None), g.c.Id == m.c.ResourceGroupId, g.c.VersionTo.is_(None),
                             _active(g), g.c.IsCritical == sa.true())


CHECKS: tuple[SmartchainCheck, ...] = (
    # Geçici: günlük kapasite 7.9'da kaynaktan kalkar; kontrol o adımda yeniden ele alınır (K-180)
    SmartchainCheck("SC.RES_NO_CAPACITY", "Resource", "Kapasitesi tanımsız kaynak", "Kapasite tanımsız:",
                    lambda t: sa.and_(_active(t), _in_critical_group(t), t.c.DailyCapacity.is_(None))),
)
BY_CODE = {c.code: c for c in CHECKS}
