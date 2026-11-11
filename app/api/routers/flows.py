"""Zamanlanmış akışlar (ekran 23, fonksiyon 92; K-163). Geçmiş ortak liste ucudur (flow-runs)."""
from typing import Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from ..db import get_session
from ..deps import require
from ..permissions import Access
from ..services import flows as service
from ..services.auth import CurrentUser

router = APIRouter(tags=["Zamanlanmış akışlar"])
read = require(92, Access.READ)
write = require(92, Access.WRITE)
status_read = require(1, Access.READ)


class FlowBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(max_length=200)
    is_active: bool = True
    run_time: str
    days: list[int]
    pull_scope: Literal["Tümü", "Seçilen"]
    pull_tables: list[str] = []
    transfer_mode: Literal["Tam", "Kısmi"]
    transfer_groups: list[str] = []
    cleanup: bool = False


@router.get("/flows", summary="Akışlar, sıradaki ve son çalışma; seçenekler (SQL tabloları, gruplar)")
def list_flows(user: CurrentUser = Depends(read), session: Session = Depends(get_session)) -> dict:
    return service.list_flows(session, user)


@router.post("/flows", summary="Akış tanımla (System owner)")
def create(body: FlowBody, user: CurrentUser = Depends(write), session: Session = Depends(get_session)) -> dict:
    return service.save(session, user, body.model_dump())


@router.put("/flows/{flow_id:int}", summary="Akışı değiştir (System owner)")
def update(flow_id: int, body: FlowBody, user: CurrentUser = Depends(write), session: Session = Depends(get_session)) -> dict:
    return service.save(session, user, body.model_dump(), flow_id)


@router.post("/flows/{flow_id:int}/run", summary="Şimdi çalıştır (System owner): aynı kurallarla")
def run_now(flow_id: int, user: CurrentUser = Depends(write), session: Session = Depends(get_session)) -> dict:
    return service.run_now(session, user, flow_id)


@router.get("/flows/status", summary="Süren akış ve kapatılmamış durma / başlamama bildirimleri (bağlam çubuğu, ana sayfa)")
def status(user: CurrentUser = Depends(status_read), session: Session = Depends(get_session)) -> dict:
    return service.status(session, user)


@router.post("/flows/runs/{run_id:int}/dismiss", status_code=204, summary="Akış bildirimini kapat (kullanıcı başına)")
def dismiss(run_id: int, user: CurrentUser = Depends(status_read), session: Session = Depends(get_session)) -> Response:
    service.dismiss(session, user, run_id)
    return Response(status_code=204)
