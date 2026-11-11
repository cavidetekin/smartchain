"""Dünden bugüne (ekran 28, fonksiyon 101; K-159, K-160). Listeler ortak liste uçlarıdır; özet ana sayfa içindir (bağlantı ana sayfa adımında)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_session
from ..deps import require
from ..permissions import Access
from ..services import raw_compare as service
from ..services.auth import CurrentUser

router = APIRouter(tags=["Dünden bugüne"])
read = require(101, Access.READ)


@router.get("/raw-compare/summary", summary="Toplamlar: karşılaştırılan tablo, yeni gelen, gelmeyen, güncellenen, son veri zamanı")
def summary(user: CurrentUser = Depends(read), session: Session = Depends(get_session)) -> dict:
    return service.summary(session)
