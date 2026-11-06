"""İş kuyruğu uç noktaları (fonksiyon 47, 48, 93). İş eklemek için uç nokta yok: işi ilgili fonksiyon servisten ekler.

Yetki (K-100): kendi işini görmek ve iptal etmek 48 (End user dahil, kendi işleri); herkesin işini görmek ve başkasının
işini iptal etmek 93 (Admin ve System owner).
"""
from typing import Literal

from fastapi import APIRouter, Body, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_session
from ..deps import require
from ..permissions import Access
from ..services import jobs as service
from ..services.auth import CurrentUser

router = APIRouter(tags=["İş kuyruğu"])
read_own = require(48, Access.READ)
write_own = require(48, Access.WRITE)
manage = require(93, Access.WRITE)


class CancelRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=200)  # başkasının işinde zorunlu (K-107)


@router.get("/jobs", summary="Çalışan, sıradaki ve son 24 saatte biten işler (kendi ya da herkesin); kanal sayaçları")
def list_jobs(scope: Literal["own", "all"] = Query("own", description="all: herkesin işleri (93; Admin ve üstü)"),
              user: CurrentUser = Depends(read_own), session: Session = Depends(get_session)) -> dict:
    return service.list_jobs(session, user, scope)


@router.get("/jobs/{job_id}", summary="İşin durumu, ilerlemesi ve sıra numarası")
def get_job(job_id: int, user: CurrentUser = Depends(read_own), session: Session = Depends(get_session)) -> dict:
    return service.get_job(session, job_id, user)


@router.post("/jobs/{job_id}/cancel", summary="Sıradaki işi iptal et (kendi işi; başkasının işi 93, neden zorunlu)")
def cancel_job(job_id: int, body: CancelRequest = Body(default=CancelRequest()), user: CurrentUser = Depends(write_own),
               session: Session = Depends(get_session)) -> dict:
    return service.cancel(session, job_id, user, body.reason)


@router.post("/jobs/{job_id}/dismiss", status_code=204, summary="Kendi işinin bildirimini kapat; yeniden çıkmaz")
def dismiss_job(job_id: int, user: CurrentUser = Depends(write_own), session: Session = Depends(get_session)) -> None:
    service.dismiss(session, job_id, user)


@router.post("/jobs/{job_id}/prioritize", summary="Sıradaki işi kanalında öne al (93); Gece kanalında yok")
def prioritize_job(job_id: int, user: CurrentUser = Depends(manage), session: Session = Depends(get_session)) -> dict:
    return service.prioritize(session, job_id, user)
