"""İş kuyruğu uç noktaları (fonksiyon 47, 48, 93). İş eklemek için uç nokta yok: işi ilgili fonksiyon servisten ekler."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_session
from ..services import jobs as service

router = APIRouter(tags=["İş kuyruğu"])


@router.get("/jobs", summary="Çalışan, sıradaki ve son 24 saatte biten işler; kanal sayaçları")
def list_jobs(user_id: int | None = Query(None, description="Yalnız bu kullanıcının işleri (geçici, A-36)"),
              session: Session = Depends(get_session)) -> dict:
    return service.list_jobs(session, user_id)


@router.get("/jobs/{job_id}", summary="İşin durumu, ilerlemesi ve sıra numarası")
def get_job(job_id: int, session: Session = Depends(get_session)) -> dict:
    return service.get_job(session, job_id)


@router.post("/jobs/{job_id}/cancel", summary="Sıradaki işi iptal et")
def cancel_job(job_id: int, session: Session = Depends(get_session)) -> dict:
    return service.cancel(session, job_id)
