"""Üretim akışı (K-200; ekran 03, fonksiyon 10): malzemenin kullananları ve kullandıkları, seviye seviye. Yalnız görüntüleme."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_session
from ..deps import require
from ..permissions import Access
from ..services import production_flow as service
from ..services.auth import CurrentUser

router = APIRouter(tags=["Üretim akışı"], dependencies=[Depends(require(10, Access.READ))])


@router.get("/production-flow/{material_id}", summary="Seçili malzemenin kutusu: kod, ad, seviye, lokasyon; kullananı ve alt malzemesi var mı")
def read(material_id: int, session: Session = Depends(get_session)) -> dict:
    return service.read(session, material_id)


@router.get("/production-flow/{material_id}/components", summary="Malzemenin kullandıkları: ürün ağacı alternatifleri ve bileşenleri (bir seviye)")
def components(material_id: int, session: Session = Depends(get_session)) -> dict:
    return service.components(session, material_id)


@router.post("/production-flow/{material_id}/export-log", summary="Çizimin PNG olarak indirilmesinin izi ve dosya adı (görsel tarayıcıda üretilir)")
def export_log(material_id: int, session: Session = Depends(get_session), user: CurrentUser = Depends(require(10, Access.READ))) -> dict:
    return service.export_log(session, user.id, material_id)


@router.get("/production-flow/{material_id}/parents", summary="Malzemeyi kullananlar (bir seviye), koda göre sıralı ve sayfalı")
def parents(material_id: int, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=200), session: Session = Depends(get_session)) -> dict:
    return service.parents(session, material_id, offset, limit)
