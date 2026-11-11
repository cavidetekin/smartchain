"""Zamanlanmış işler (ekran 25 sekmesi, fonksiyon 92; K-163, K-164). Liste ve geçmiş ortak liste uçlarıdır (flows, flow-runs)."""
from typing import Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from ..db import get_session
from ..deps import require
from ..permissions import Access
from ..services import flows as service
from ..services.auth import CurrentUser

router = APIRouter(tags=["Zamanlanmış işler"])
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


@router.get("/flows", summary="Zamanlanmış işler, sıradaki ve son çalışma; seçenekler (SQL tabloları, gruplar)")
def list_flows(user: CurrentUser = Depends(read), session: Session = Depends(get_session)) -> dict:
    return service.list_flows(session, user)


class FlowSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    FlowWaitMinutes: int | None = None
    FlowRefreshWaitMinutes: int | None = None


@router.put("/flows/settings", summary="İki bekleme süresi (System owner); yalnız değişenler, denetim izine")
def save_settings(body: FlowSettings, user: CurrentUser = Depends(write), session: Session = Depends(get_session)) -> dict:
    return service.save_settings(session, user, body.model_dump(exclude_unset=True))


@router.post("/flows", summary="Zamanlanmış iş tanımla (System owner)")
def create(body: FlowBody, user: CurrentUser = Depends(write), session: Session = Depends(get_session)) -> dict:
    return service.save(session, user, body.model_dump())


@router.put("/flows/{flow_id:int}", summary="Zamanlanmış işi değiştir (System owner)")
def update(flow_id: int, body: FlowBody, user: CurrentUser = Depends(write), session: Session = Depends(get_session)) -> dict:
    return service.save(session, user, body.model_dump(), flow_id)


@router.post("/flows/{flow_id:int}/run", summary="Şimdi çalıştır (System owner): aynı kurallarla")
def run_now(flow_id: int, user: CurrentUser = Depends(write), session: Session = Depends(get_session)) -> dict:
    return service.run_now(session, user, flow_id)


@router.get("/flows/status", summary="Süren zamanlanmış iş ve kapatılmamış durma / başlamama bildirimleri (bağlam çubuğu, ana sayfa)")
def status(user: CurrentUser = Depends(status_read), session: Session = Depends(get_session)) -> dict:
    return service.status(session, user)


@router.post("/flows/runs/{run_id:int}/dismiss", status_code=204, summary="Zamanlanmış iş bildirimini kapat (kullanıcı başına)")
def dismiss(run_id: int, user: CurrentUser = Depends(status_read), session: Session = Depends(get_session)) -> Response:
    service.dismiss(session, user, run_id)
    return Response(status_code=204)
