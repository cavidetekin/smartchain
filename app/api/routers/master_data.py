"""Ana veri (ekran 03, fonksiyon 10) ve İşlem verisi (ekran 29, fonksiyon 102) ekranları (K-168, K-169).
Tabloların satırları ortak liste uçlarıdır (materials, master-…, transaction-…)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_session
from ..deps import require
from ..permissions import Access
from ..services import master_data as service

router = APIRouter(tags=["Ana veri ve işlem verisi"])


@router.get("/master-data/counts", summary="Ana veri sekmeleri, tabloları ve güncel veri versiyonundaki kayıt sayıları",
            dependencies=[Depends(require(10, Access.READ))])
def master_counts(session: Session = Depends(get_session)) -> dict:
    return service.counts(session, "master")


@router.get("/transaction-data/counts", summary="İşlem verisi sekmeleri, tabloları ve güncel veri versiyonundaki kayıt sayıları",
            dependencies=[Depends(require(102, Access.READ))])
def transaction_counts(session: Session = Depends(get_session)) -> dict:
    return service.counts(session, "transaction")
