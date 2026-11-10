"""Ham veri temizliği (ekran 02, fonksiyon 09; K-156). Başlatma yalnız System owner (09 yazma); sonucu Admin ve Key user de görür (09 okuma)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_session
from ..deps import require
from ..permissions import Access
from ..services import cleanup as service
from ..services.auth import CurrentUser

router = APIRouter(tags=["Ham veri temizliği"])
read = require(9, Access.READ)
write = require(9, Access.WRITE)


@router.get("/cleanup", summary="Saklama süresi ve son temizliğin sonucu")
def state(user: CurrentUser = Depends(read), session: Session = Depends(get_session)) -> dict:
    return service.state(session)


@router.get("/cleanup/plan", summary="Onay penceresi: silinecek parti, satır ve dosya; başlatılamıyorsa nedeni")
def plan(user: CurrentUser = Depends(write), session: Session = Depends(get_session)) -> dict:
    return service.plan(session)


@router.post("/cleanup", status_code=202, summary="Ham veri temizliğini başlat; iş kuyruğuna yazılır")
def start(user: CurrentUser = Depends(write), session: Session = Depends(get_session)) -> dict:
    return service.start(session, user)
