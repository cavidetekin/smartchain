"""Model kısıtları (ekran 31, fonksiyon 103; K-189; docs/08 "Model kısıtları"). Okuma liste uçlarındandır (`model-constraints-resource-groups`);
burada yazma: hücre değişiklikleri ve senaryo farkını kaldırma. Senaryo `scenario_id` sorgu parametresiyle; kimlik kaynak grubunun kimliğidir."""
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from ..db import get_session
from ..deps import require
from ..permissions import Access
from ..services import model_constraints as service
from ..services.auth import CurrentUser

router = APIRouter(tags=["Model kısıtları"])
write103 = require(103, Access.WRITE)


class CellChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int
    field: str = Field(min_length=1, max_length=60)
    value: Any = None


class Changes(BaseModel):
    model_config = ConfigDict(extra="forbid")
    changes: list[CellChange] = Field(min_length=1, max_length=2000)


@router.put("/model-constraints/resource-groups", summary="Model kısıtları: hücre değişiklikleri (hepsi ya da hiçbiri)")
def change(body: Changes, scenario_id: int | None = None, user: CurrentUser = Depends(write103), session: Session = Depends(get_session)) -> dict:
    return service.change(session, user, scenario_id, [c.model_dump() for c in body.changes])


@router.post("/model-constraints/resource-groups/{group_id}/restore", summary="Model kısıtları: senaryo farkını kaldır")
def restore(group_id: int, scenario_id: int | None = None, user: CurrentUser = Depends(write103), session: Session = Depends(get_session)) -> dict:
    return service.restore(session, user, scenario_id, group_id)
