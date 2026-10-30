"""Veri versiyonu uç noktaları."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_session
from ..deps import current_user
from ..services import data_versions as service

router = APIRouter(tags=["Veri"], dependencies=[Depends(current_user)])


@router.get("/data-versions/current", summary="En son veri versiyonu (bağlam çubuğu)")
def current(session: Session = Depends(get_session)) -> dict:
    return service.current(session)
