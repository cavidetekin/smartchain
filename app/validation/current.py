"""Staging'in güncel hâli (K-133): parti "Alındı" olduğu anda, çağıranın işleminde güncel hâle işlenir.

Tam: güncel hâlin yerine geçer; partide olmayan kayıt güncel hâlden çıkar. Ekle / güncelle: aynı anahtarlı kayıt değişir,
öteki kayıtlar kalır. Ön kontrolde düşen satırın anahtarı okunabiliyorsa (bulgudaki kayıt) o anahtarın önceki güncel
satırı kalır; Tam'da da silinmiş sayılmaz. Güncel hâlden çıkan satırların validasyon bulguları silinir.
"""
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.integration.structural import _text, key_fields
from db.models import metadata

from .sqlkit import ROW_KEY_SEPARATOR, current, same, table

FULL, CHANGED = "Tam", "Değişen"
FINDING = metadata.tables["adm.ImportFinding"]
VALIDATION = metadata.tables["adm.ValidationFinding"]
ERROR = "Hata"


def _protected(session: Session, entity: str, batch_id: int) -> list[int]:
    """Ön kontrolde düşen satırların anahtarına denk gelen güncel satırlar (Tam'da silinmiş sayılmaz)."""
    keys = key_fields(entity)
    if not keys:
        return []
    dropped = set(session.execute(sa.select(FINDING.c.RowKey).where(FINDING.c.ImportBatchId == batch_id, FINDING.c.Severity == ERROR,
                                                                    FINDING.c.RowKey.is_not(None)).distinct()).scalars())
    if not dropped:
        return []
    t = table(entity)
    out = []
    for row in session.execute(sa.select(t.c.StagingRowId, *[t.c[k] for k in keys]).where(current(t))):
        parts = [_text(v) for v in row[1:] if v not in (None, "")]
        if ROW_KEY_SEPARATOR.join(p for p in parts if p)[:200] in dropped:
            out.append(row[0])
    return out


def apply_batch(session: Session, entity: str, batch_id: int, mode: str) -> dict[str, int]:
    """Partiyi güncel hâle işler; commit çağıranındır. (çıkan, giren) satır sayısı."""
    t = table(entity)
    keys = key_fields(entity)
    if mode == FULL or not keys:
        keep = _protected(session, entity, batch_id) if mode == FULL else []
        if mode == FULL:
            stmt = sa.update(t).where(current(t), t.c.ImportBatchId != batch_id)
            if keep:
                session.execute(sa.text("CREATE TABLE #keep (Id bigint PRIMARY KEY)"))
                try:
                    for start in range(0, len(keep), 1000):
                        session.execute(sa.text("INSERT INTO #keep (Id) VALUES " + ", ".join(f"({int(i)})" for i in keep[start:start + 1000])))
                    stmt = stmt.where(sa.text("StagingRowId NOT IN (SELECT Id FROM #keep)"))
                    removed = session.execute(stmt.values(IsCurrent=False)).rowcount
                finally:
                    session.execute(sa.text("DROP TABLE #keep"))
            else:
                removed = session.execute(stmt.values(IsCurrent=False)).rowcount
        else:
            removed = 0  # anahtarsız tabloda ekle / güncelle ekler
    else:
        new = t.alias("new")
        matched = sa.exists().where(new.c.ImportBatchId == batch_id, *[same(new.c[k], t.c[k]) for k in keys])
        removed = session.execute(sa.update(t).where(current(t), t.c.ImportBatchId != batch_id, matched).values(IsCurrent=False)).rowcount
    added = session.execute(sa.update(t).where(t.c.ImportBatchId == batch_id).values(IsCurrent=True)).rowcount
    if removed:
        session.execute(sa.delete(VALIDATION).where(
            VALIDATION.c.EntityName == entity,
            VALIDATION.c.StagingRowId.in_(sa.select(t.c.StagingRowId).where(t.c.IsCurrent == sa.false()))))
    return {"removed": removed, "added": added}


def current_rows(session: Session, entity: str) -> int:
    t = table(entity)
    return session.execute(sa.select(sa.func.count()).select_from(t).where(current(t))).scalar_one()
