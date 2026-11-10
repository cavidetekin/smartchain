"""Tam aktarım (ekran 02, fonksiyon 05 ve 07, K-149…K-153). Yetki fonksiyon 05 (Key user ve üstü)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_session
from ..deps import require
from ..permissions import Access
from ..services import transfer as service
from ..services.auth import CurrentUser

router = APIRouter(tags=["Aktarım"])
read = require(5, Access.READ)
write = require(5, Access.WRITE)


@router.get("/transfers/plan", summary="Onay penceresi: tablo başına güncel satır, Hatalı, durum; başlatılamıyorsa nedeni")
def plan(user: CurrentUser = Depends(read), session: Session = Depends(get_session)) -> dict:
    return service.plan(session)


@router.post("/transfers", status_code=202, summary="Tam aktarımı başlat; iş kuyruğuna yazılır")
def start(user: CurrentUser = Depends(write), session: Session = Depends(get_session)) -> dict:
    return service.start(session, user)


@router.get("/transfers/{job_id}", summary="Aktarımın sonucu: veri versiyonu, tablo başına yeni, değişen, kapatılan, aktarılmayan")
def result(job_id: int, user: CurrentUser = Depends(read), session: Session = Depends(get_session)) -> dict:
    return service.result(session, job_id)
