"""Veri versiyonu uç noktaları."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_session
from ..deps import require
from ..services import data_versions as service

# Bağlam çubuğu (U-17): herkes okur; 82 Sabah özeti okuma (K-100).
router = APIRouter(tags=["Veri"], dependencies=[Depends(require(82))])


@router.get("/data-versions/current", summary="En son veri versiyonu (bağlam çubuğu)")
def current(session: Session = Depends(get_session)) -> dict:
    return service.current(session)
