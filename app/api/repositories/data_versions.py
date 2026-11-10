"""Veri versiyonu sorguları (adm.DataVersion)."""
from sqlalchemy import text
from sqlalchemy.orm import Session


def read_current(session: Session) -> dict | None:
    """En son veri versiyonu. Tam aktarımın versiyonunda lokasyon boştur (bütün lokasyonlar, K-153)."""
    row = session.execute(text(
        "SELECT TOP 1 v.Id, v.CreatedAt, v.LoadType, v.IsSynthetic, l.Code AS LocationCode "
        "FROM adm.DataVersion v LEFT JOIN core.Location l ON l.Id = v.LocationId ORDER BY v.Id DESC")).mappings().first()
    return dict(row) if row else None
