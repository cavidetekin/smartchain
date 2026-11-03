"""Veri versiyonu: bağlam çubuğunun gösterdiği güncel versiyon (docs/12, U-17)."""
from datetime import timezone

from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from ..errors import DB_UNAVAILABLE, AppError
from ..repositories import data_versions as repo




def current(session: Session | None) -> dict:
    if session is None:
        raise AppError("database_unavailable", DB_UNAVAILABLE, 503)
    try:
        row = repo.read_current(session)
    except DBAPIError as exc:  # bağlantı kurulamadı ya da koptu: bağlam çubuğu "Veritabanına ulaşılamıyor" der
        raise AppError("database_unavailable", DB_UNAVAILABLE, 503) from exc
    if row is None:
        raise AppError("no_data_version", "Henüz veri yüklenmedi.", 404)
    return {
        "id": row["Id"],
        "location_code": row["LocationCode"],
        "created_at": row["CreatedAt"].replace(tzinfo=timezone.utc).isoformat(timespec="seconds"),
        "load_type": row["LoadType"],
        "is_synthetic": bool(row["IsSynthetic"]),
    }
