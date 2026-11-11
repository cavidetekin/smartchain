"""Sistem sağlığı (ekran 24, fonksiyon 94; K-106). Listeler (job-queue, job-runs, system-events) ortak liste uçlarıdır."""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from ..db import get_session
from ..deps import require
from ..permissions import Access
from ..services import health_settings, system_health
from ..services.auth import CurrentUser

router = APIRouter(tags=["Sistem sağlığı"])
health_read = require(94, Access.READ)
owner_read = require(96, Access.READ)
owner_write = require(96, Access.WRITE)


class HealthSettingsChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    DiskWarnPercent: int | None = None
    QueueWaitWarnMinutes: int | None = None
    SystemEventRetentionDays: int | None = None
    ImportSyncMaxMb: int | None = None  # K-129: Excel yükleme
    ImportMaxMb: int | None = None
    ImportMaxRows: int | None = None
    RawDataRetentionDays: int | None = None  # K-156: boş gönderilirse silinir (temizlik çalışmaz)


@router.get("/system-health", summary="Kartlar, servis durumu, eşik aşımları")
def summary(request: Request, user: CurrentUser = Depends(health_read), session: Session = Depends(get_session)) -> dict:
    return system_health.summary(session, request.app.state.started_at, request.app.state.notifier.connection_count())


@router.get("/system-events/{event_id:int}", summary="Hata detayı; teknik özet yalnız System owner'a")
def event_detail(event_id: int, user: CurrentUser = Depends(health_read), session: Session = Depends(get_session)) -> dict:
    return system_health.event_detail(session, event_id, user)


@router.get("/settings/health", summary="Sistem sağlığı eşikleri ve saklama süresi")
def settings(user: CurrentUser = Depends(owner_read), session: Session = Depends(get_session)) -> dict:
    return health_settings.read(session)


@router.put("/settings/health", summary="Sistem sağlığı eşikleri: yalnız değişenler yazılır, denetim izine")
def settings_update(body: HealthSettingsChange, user: CurrentUser = Depends(owner_write),
                    session: Session = Depends(get_session)) -> dict:
    return health_settings.update(session, user, body.model_dump(exclude_unset=True))
