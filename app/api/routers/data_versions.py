"""Veri versiyonu uç noktaları."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_session
from ..services import data_versions as service

router = APIRouter(tags=["Veri"])


@router.get("/data-versions/current", summary="En son veri versiyonu (bağlam çubuğu)")
def current(session: Session = Depends(get_session)) -> dict:
    return service.current(session)
