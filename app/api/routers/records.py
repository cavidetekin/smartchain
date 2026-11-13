"""Kaydın kartı (K-171, K-173): detay kartının başlığı, güncellik ve İlişkili kayıtlar. Geçmiş ortak liste ucudur (`record-history`)."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_session
from ..deps import require
from ..permissions import Access
from ..services import records as service
from ..services.auth import CurrentUser

router = APIRouter(tags=["Kayıt kartı"])


class ManyRequest(BaseModel):
    ids: list[str]


@router.post("/records/{list_name}/many", summary="Çoklu seçimde kart (K-171): seçili kayıtların İlişkili kayıtlarının birleşimi")
def read_many(list_name: str, body: ManyRequest, session: Session = Depends(get_session), user: CurrentUser = Depends(require(14, Access.READ))) -> dict:
    return service.read_many(session, user, list_name, body.ids)


@router.get("/records/{list_name}/{key}", summary="Kaydın kartı: kod ve ad, güncel veride mi, İlişkili kayıtlar (listenin okuma yetkisiyle)")
def read_record(list_name: str, key: str, session: Session = Depends(get_session), user: CurrentUser = Depends(require(14, Access.READ))) -> dict:
    return service.read(session, user, list_name, key)
