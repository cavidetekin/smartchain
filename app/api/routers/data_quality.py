"""Veri kalitesi (ekran 05, fonksiyon 20, 21; K-174). Uyarı ve talep zinciri listeleri ortak liste uçlarıdır (`data-quality-warnings`,
`data-quality-demand-chain`)."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_session
from ..deps import require
from ..permissions import Access
from ..services import data_quality as service
from ..services.auth import CurrentUser

router = APIRouter(prefix="/data-quality", tags=["Veri kalitesi"])


class IgnoreBody(BaseModel):
    ids: list[int | str]
    reason: str | None = None


class IdsBody(BaseModel):
    ids: list[int | str]


@router.post("/ignore", summary="Yok say: gerekçe zorunlu, seçilen bütün uyarılara (21 yazma)")
def ignore(body: IgnoreBody, session: Session = Depends(get_session), user: CurrentUser = Depends(require(21, Access.WRITE))) -> dict:
    return service.ignore(session, user, body.ids, body.reason)


@router.post("/unignore", summary="Yok saymayı kaldır (21 yazma)")
def unignore(body: IdsBody, session: Session = Depends(get_session), user: CurrentUser = Depends(require(21, Access.WRITE))) -> dict:
    return service.unignore(session, user, body.ids)


@router.post("/{warning_id}/demand-chain", summary="Kartın Talep zinciri: hesaplar ve önbelleğe yazar; en çok 1.000 yol (20 okuma)")
def demand_chain(warning_id: int, session: Session = Depends(get_session), user: CurrentUser = Depends(require(20, Access.READ))) -> dict:
    return service.demand_chain(session, user, warning_id)


@router.get("/summary", summary="Ana sayfa özeti: yüksek önemde uyarı ve yeni sayısı (20 okuma)")
def summary(session: Session = Depends(get_session), user: CurrentUser = Depends(require(20, Access.READ))) -> dict:
    return service.summary(session, user)
