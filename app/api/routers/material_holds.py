"""Malzeme blokajı (ekran 31 üçüncü sekme, fonksiyon 99; K-193; docs/08 "Malzeme blokajı"). Okuma liste uçlarındandır (`material-holds`,
`material-holds-validity`); burada pencerenin seçenekleri ve yazma: yeni kayıt, hücre değişikliği, silme, geçersiz yapma, senaryo farkını kaldırma.
Senaryo `scenario_id` sorgu parametresiyle."""
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from ..db import get_session
from ..deps import require
from ..permissions import Access
from ..services import material_holds as service
from ..services.auth import CurrentUser

router = APIRouter(tags=["Model kısıtları"])
read99, write99 = require(99, Access.READ), require(99, Access.WRITE)
BASE = "/model-constraints/material-holds"


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


@router.get(f"{BASE}/options", summary="Malzeme blokajı: pencerenin seçenekleri (güncel malzemeler, tedarik biçimiyle)")
def options(user: CurrentUser = Depends(read99), session: Session = Depends(get_session)) -> dict:
    return service.options(session, user)


@router.post(BASE, status_code=201, summary="Malzeme blokajı: yeni kayıt")
def create(body: NewEntry, scenario_id: int | None = None, user: CurrentUser = Depends(write99), session: Session = Depends(get_session)) -> dict:
    return service.create(session, user, scenario_id, body.values)


@router.put(BASE, summary="Malzeme blokajı: hücre değişiklikleri (hepsi ya da hiçbiri)")
def change(body: Changes, scenario_id: int | None = None, user: CurrentUser = Depends(write99), session: Session = Depends(get_session)) -> dict:
    return service.change(session, user, scenario_id, [c.model_dump() for c in body.changes])


@router.delete(f"{BASE}/{{row_id}}", summary="Malzeme blokajı: senaryonun kendi satırını sil")
def remove(row_id: int, scenario_id: int | None = None, user: CurrentUser = Depends(write99), session: Session = Depends(get_session)) -> dict:
    return service.remove(session, user, scenario_id, row_id)


@router.post(f"{BASE}/{{row_id}}/invalidate", summary="Malzeme blokajı: bu senaryoda geçersiz yap")
def invalidate(row_id: int, scenario_id: int | None = None, user: CurrentUser = Depends(write99), session: Session = Depends(get_session)) -> dict:
    return service.set_valid(session, user, scenario_id, row_id, False)


@router.post(f"{BASE}/{{row_id}}/validate", summary="Malzeme blokajı: bu senaryoda yeniden geçerli yap")
def validate(row_id: int, scenario_id: int | None = None, user: CurrentUser = Depends(write99), session: Session = Depends(get_session)) -> dict:
    return service.set_valid(session, user, scenario_id, row_id, True)


@router.post(f"{BASE}/{{row_id}}/restore", summary="Malzeme blokajı: senaryo farkını kaldır")
def restore(row_id: int, scenario_id: int | None = None, user: CurrentUser = Depends(write99), session: Session = Depends(get_session)) -> dict:
    return service.restore(session, user, scenario_id, row_id)
