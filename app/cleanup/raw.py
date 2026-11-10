"""Ham veri temizliği (fonksiyon 09; K-129, K-133, K-156).

Yaşı saklama süresini (`RawDataRetentionDays`, gün) geçen partilerde: güncel olmayan ham satırlar (`IsCurrent = 0`), ön kontrol bulguları ve
yüklenen Excel dosyası silinir; terk edilen "Ön kontrol" partisi "Vazgeçildi" olur; parti kaydı ve sayıları kalır, `RawDeletedAt` yazılır.
Staging'in güncel hâli, işlenmiş katman, validasyon bulguları, veri versiyonları ve özet kayıtlar silinmez. Süre boşsa temizlik çalışmaz.

Veritabanı değişiklikleri tek işlemde; dosyalar işlem commit edildikten sonra silinir (işlem düşerse dosyaya dokunulmaz).
"""
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.integration.contract import ENTITIES
from app.validation import engine as validation
from db.models import metadata

log = logging.getLogger("smartchain.cleanup")

SETTING_KEY = "RawDataRetentionDays"
LIMITS = (1, 30)
PRECHECK, ABANDONED = "Ön kontrol", "Vazgeçildi"
BATCH = metadata.tables["adm.ImportBatch"]
FINDING = metadata.tables["adm.ImportFinding"]
SETTING = metadata.tables["adm.SystemSetting"]


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def retention_days(session: Session) -> int | None:
    """Saklama süresi; satır yoksa, bozuksa ya da sınır dışıysa None (temizlik çalışmaz, K-138)."""
    raw = session.execute(sa.select(SETTING.c.Value).where(SETTING.c.SettingKey == SETTING_KEY)).scalar()
    try:
        days = int(raw) if raw is not None else None
    except (TypeError, ValueError):
        log.warning("SystemSetting %s geçersiz (%r); temizlik çalışmaz", SETTING_KEY, raw)
        return None
    if days is not None and not LIMITS[0] <= days <= LIMITS[1]:
        log.warning("SystemSetting %s sınır dışı (%s); temizlik çalışmaz", SETTING_KEY, days)
        return None
    return days


def _old_batches(cutoff: datetime) -> sa.Select:
    return sa.select(BATCH.c.Id).where(BATCH.c.ReceivedAt < cutoff, BATCH.c.RawDeletedAt.is_(None))


def _stale_rows(entity: str, cutoff: datetime):
    t = metadata.tables[f"stg.{entity}"]
    return t, sa.and_(t.c.IsCurrent == sa.false(), t.c.ImportBatchId.in_(_old_batches(cutoff).where(BATCH.c.EntityName == entity)))


def _files(session: Session, cutoff: datetime) -> list[tuple[int, Path]]:
    rows = session.execute(sa.select(BATCH.c.Id, BATCH.c.FilePath).where(BATCH.c.Id.in_(_old_batches(cutoff)), BATCH.c.FilePath.is_not(None))).all()
    return [(int(i), Path(p)) for i, p in rows]


def _size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


@dataclass
class Summary:
    retention_days: int
    cutoff: datetime
    batches: int = 0
    abandoned: int = 0
    rows: int = 0
    files: int = 0
    size: int = 0
    tables: list[dict] = field(default_factory=list)   # tablo başına silinen (silinecek) satır; satırı olmayan yazılmaz

    def as_dict(self) -> dict:
        return {"retention_days": self.retention_days, "cutoff": self.cutoff.isoformat(), "batches": self.batches, "abandoned": self.abandoned,
                "rows": self.rows, "files": self.files, "size": self.size, "tables": self.tables}


def _base(session: Session, days: int, now: datetime) -> Summary:
    cutoff = now - timedelta(days=days)
    s = Summary(days, cutoff)
    row = session.execute(sa.select(sa.func.count(), sa.func.sum(sa.case((BATCH.c.Status == PRECHECK, 1), else_=0)))
                          .where(BATCH.c.Id.in_(_old_batches(cutoff)))).one()
    s.batches, s.abandoned = int(row[0] or 0), int(row[1] or 0)
    return s


def preview(session: Session, days: int, now: datetime | None = None) -> dict:
    """Silinecek parti, satır ve dosya sayısı (onay penceresi); hiçbir şey değişmez."""
    s = _base(session, days, now or utcnow())
    for e in ENTITIES:
        t, cond = _stale_rows(e.table, s.cutoff)
        n = int(session.execute(sa.select(sa.func.count()).select_from(t).where(cond)).scalar() or 0)
        if n:
            s.tables.append({"entity": e.table, "name": e.name, "rows": n})
            s.rows += n
    files = [p for _, p in _files(session, s.cutoff)]
    s.files = sum(1 for p in files if p.exists())
    s.size = sum(_size(p) for p in files)
    return s.as_dict()


def run(session: Session, days: int, progress: Callable[[str], None] | None = None, now: datetime | None = None) -> tuple[Summary, list[Path]]:
    """Veritabanı tarafı; commit çağıranındır. Dönen dosyalar commit'ten sonra delete_files ile silinir."""
    now = now or utcnow()
    validation._applock(session, "transfer")             # aktarımla çakışmaz; tablo kilitleri validasyon ve çekimle
    for e in ENTITIES:
        validation._applock(session, f"validation:table:{e.table}")
    s = _base(session, days, now)
    for i, e in enumerate(ENTITIES, 1):
        if progress:
            progress(f"{e.name} · {i} / {len(ENTITIES)}")
        t, cond = _stale_rows(e.table, s.cutoff)
        n = session.execute(sa.delete(t).where(cond)).rowcount or 0
        if n:
            s.tables.append({"entity": e.table, "name": e.name, "rows": n})
            s.rows += n
    old = _old_batches(s.cutoff)
    session.execute(sa.delete(FINDING).where(FINDING.c.ImportBatchId.in_(old)))
    files = _files(session, s.cutoff)
    session.execute(sa.update(BATCH).where(BATCH.c.Id.in_(old), BATCH.c.Status == PRECHECK).values(Status=ABANDONED))
    session.execute(sa.update(BATCH).where(BATCH.c.Id.in_(old)).values(FilePath=None, RawDeletedAt=now))
    return s, [p for _, p in files]


def delete_files(summary: Summary, paths: list[Path]) -> None:
    """İşlem commit edildikten sonra; silinemeyen dosya loglanır, sayılmaz."""
    for p in paths:
        size = _size(p)
        try:
            if p.exists():
                p.unlink()
                summary.files += 1
                summary.size += size
        except OSError:
            log.warning("Dosya silinemedi: %s", p, exc_info=True)
