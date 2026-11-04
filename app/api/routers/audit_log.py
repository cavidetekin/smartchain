"""Denetim izi (ekran 26, fonksiyon 98; K-108). Liste (audit-log) ortak liste uçlarıdır; kayıtlar yalnız okunur."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_session
from ..deps import require
from ..permissions import Access
from ..services import audit_log as service
from ..services.auth import CurrentUser

router = APIRouter(prefix="/audit-log", tags=["Denetim izi"])
read = require(98, Access.READ)


@router.get("/{audit_id:int}", summary="Kayıt: alan, eski ve yeni değer; gerçek değerler yalnız System owner'a")
def detail(audit_id: int, user: CurrentUser = Depends(read), session: Session = Depends(get_session)) -> dict:
    return service.detail(session, audit_id, user)


@router.get("/{audit_id:int}/history", summary="Aynı nesnenin kayıtları zaman sırasıyla (en çok 200)")
def history(audit_id: int, user: CurrentUser = Depends(read), session: Session = Depends(get_session)) -> dict:
    return service.history(session, audit_id, user)
