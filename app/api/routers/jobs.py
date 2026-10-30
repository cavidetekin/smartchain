"""İş kuyruğu uç noktaları (fonksiyon 47, 48, 93). İş eklemek için uç nokta yok: işi ilgili fonksiyon servisten ekler."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_session
from ..deps import current_user
from ..services import jobs as service
from ..services.auth import CurrentUser

router = APIRouter(tags=["İş kuyruğu"], dependencies=[Depends(current_user)])


@router.get("/jobs", summary="Oturumdaki kullanıcının çalışan, sıradaki ve son 24 saatte biten işleri; kanal sayaçları")
def list_jobs(user: CurrentUser = Depends(current_user), session: Session = Depends(get_session)) -> dict:
    return service.list_jobs(session, user.id)


@router.get("/jobs/{job_id}", summary="İşin durumu, ilerlemesi ve sıra numarası")
def get_job(job_id: int, session: Session = Depends(get_session)) -> dict:
    return service.get_job(session, job_id)


@router.post("/jobs/{job_id}/cancel", summary="Sıradaki işi iptal et")
def cancel_job(job_id: int, session: Session = Depends(get_session)) -> dict:
    return service.cancel(session, job_id)
