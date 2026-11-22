"""Tedarikçi limiti (ekran 31 ikinci sekme, fonksiyon 103; K-191; docs/08 "Tedarikçi limiti"). Okuma liste uçlarındandır (`supplier-limits`,
`supplier-limits-validity`); burada pencerenin seçenekleri ve yazma: yeni kayıt, hücre değişikliği, silme, geçersiz yapma, senaryo farkını kaldırma.
Senaryo `scenario_id` sorgu parametresiyle."""
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from ..db import get_session
from ..deps import require
from ..permissions import Access
from ..services import supplier_limits as service
from ..services.auth import CurrentUser

router = APIRouter(tags=["Model kısıtları"])
read103, write103 = require(103, Access.READ), require(103, Access.WRITE)
BASE = "/model-constraints/supplier-limits"


class NewEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    values: dict[str, Any]


class CellChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int
    field: str = Field(min_length=1, max_length=60)
    value: Any = None


class Changes(BaseModel):
    model_config = ConfigDict(extra="forbid")
    changes: list[CellChange] = Field(min_length=1, max_length=2000)


@router.get(f"{BASE}/options", summary="Tedarikçi limiti: pencerenin seçenekleri (aktif ve güncel malzeme tedarikçisi kayıtları)")
def options(user: CurrentUser = Depends(read103), session: Session = Depends(get_session)) -> dict:
    return service.options(session, user)


@router.post(BASE, status_code=201, summary="Tedarikçi limiti: yeni kayıt (üst limit ya da kapanış; kapanışta birden çok malzeme)")
def create(body: NewEntry, scenario_id: int | None = None, user: CurrentUser = Depends(write103), session: Session = Depends(get_session)) -> dict:
    return service.create(session, user, scenario_id, body.values)


@router.put(BASE, summary="Tedarikçi limiti: hücre değişiklikleri (hepsi ya da hiçbiri)")
def change(body: Changes, scenario_id: int | None = None, user: CurrentUser = Depends(write103), session: Session = Depends(get_session)) -> dict:
    return service.change(session, user, scenario_id, [c.model_dump() for c in body.changes])


@router.delete(f"{BASE}/{{row_id}}", summary="Tedarikçi limiti: senaryonun kendi satırını sil")
def remove(row_id: int, scenario_id: int | None = None, user: CurrentUser = Depends(write103), session: Session = Depends(get_session)) -> dict:
    return service.remove(session, user, scenario_id, row_id)


@router.post(f"{BASE}/{{row_id}}/invalidate", summary="Tedarikçi limiti: bu senaryoda geçersiz yap")
def invalidate(row_id: int, scenario_id: int | None = None, user: CurrentUser = Depends(write103), session: Session = Depends(get_session)) -> dict:
    return service.set_valid(session, user, scenario_id, row_id, False)


@router.post(f"{BASE}/{{row_id}}/validate", summary="Tedarikçi limiti: bu senaryoda yeniden geçerli yap")
def validate(row_id: int, scenario_id: int | None = None, user: CurrentUser = Depends(write103), session: Session = Depends(get_session)) -> dict:
    return service.set_valid(session, user, scenario_id, row_id, True)


@router.post(f"{BASE}/{{row_id}}/restore", summary="Tedarikçi limiti: senaryo farkını kaldır")
def restore(row_id: int, scenario_id: int | None = None, user: CurrentUser = Depends(write103), session: Session = Depends(get_session)) -> dict:
    return service.restore(session, user, scenario_id, row_id)
