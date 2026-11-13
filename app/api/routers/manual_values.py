"""Manuel değer (fonksiyon 12 girme, 13 kaldırma; K-170): ana veri ve işlem verisi ekranlarında hücre içinde."""
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from ..db import get_session
from ..deps import require
from ..permissions import Access
from ..services import manual_values as service
from ..services.auth import CurrentUser

router = APIRouter(tags=["Manuel değer"])


class Change(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int | str
    field: str
    value: Any = None


class SaveBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    list: str
    changes: list[Change] = Field(min_length=1, max_length=5000)


class Item(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int | str
    field: str | None = None  # boşsa kaydın bütün manuel değerleri


class RemoveBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    list: str
    items: list[Item] = Field(min_length=1, max_length=5000)


@router.post("/manual-values", summary="Manuel değerleri kaydet: yerinde güncellenir, yeni veri versiyonu açılmaz, denetim izine yazılır")
def save(body: SaveBody, user: CurrentUser = Depends(require(12, Access.WRITE)), session: Session = Depends(get_session)) -> dict:
    return service.save(session, user, body.list, [c.model_dump() for c in body.changes])


@router.post("/manual-values/remove", summary="Manuel değerleri kaldır: hücre kural ya da ERP değerine döner")
def remove(body: RemoveBody, user: CurrentUser = Depends(require(13, Access.WRITE)), session: Session = Depends(get_session)) -> dict:
    return service.remove(session, user, body.list, [i.model_dump() for i in body.items])
