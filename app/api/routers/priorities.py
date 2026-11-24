"""Öncelik yönetimi (ekran 32, fonksiyon 25; K-195; docs/08 "Öncelik yönetimi"). Okuma liste uçlarındandır (`priority-customers`, `priority-projects`,
`priority-orders`, `priority-forecasts`); burada yazma: hücre değişiklikleri ve senaryo farkını kaldırma. Senaryo `scenario_id` sorgu parametresiyle;
düzey adreste (`customers` · `projects` · `orders`), kimlik kaydın kimliğidir."""
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from ..db import get_session
from ..deps import require
from ..permissions import Access
from ..services import priorities as service
from ..services.auth import CurrentUser

router = APIRouter(tags=["Öncelik yönetimi"])
write25 = require(25, Access.WRITE)


class CellChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int
    field: str = Field(min_length=1, max_length=60)
    value: Any = None


class Changes(BaseModel):
    model_config = ConfigDict(extra="forbid")
    changes: list[CellChange] = Field(min_length=1, max_length=5000)


@router.put("/priorities/{level}", summary="Öncelik yönetimi: hücre değişiklikleri (hepsi ya da hiçbiri; değer 1–5 ya da boş)")
def change(level: str, body: Changes, scenario_id: int | None = None, user: CurrentUser = Depends(write25), session: Session = Depends(get_session)) -> dict:
    return service.change(session, user, scenario_id, level, [c.model_dump() for c in body.changes])


@router.post("/priorities/{level}/{record_id}/restore", summary="Öncelik yönetimi: senaryo farkını kaldır")
def restore(level: str, record_id: int, scenario_id: int | None = None, user: CurrentUser = Depends(write25), session: Session = Depends(get_session)) -> dict:
    return service.restore(session, user, scenario_id, level, record_id)
