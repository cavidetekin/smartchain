"""Kapasite yönetimi girişleri (ekran 30, fonksiyon 24; K-185, 7.9b; docs/08 "Kapasite yönetimi"). Okuma liste uçlarındandır (`capacity-*`);
burada yazma: yeni kayıt, hücre değişikliği, silme, geçersiz yapma, senaryo farkını kaldırma. Senaryo `scenario_id` sorgu parametresiyle."""
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from ..db import get_session
from ..deps import require
from ..permissions import Access
from ..services import capacity as service
from ..services.auth import CurrentUser

router = APIRouter(tags=["Kapasite yönetimi"])
write24 = require(24, Access.WRITE)
read24 = require(24, Access.READ)


@router.get("/capacity/locations", summary="Lokasyonlar (Fabrika takvimi penceresi; K-194)")
def locations(user: CurrentUser = Depends(read24), session: Session = Depends(get_session)) -> dict:
    return service.locations(session, user)


@router.get("/capacity/horizon", summary="Senaryonun planlama ufku (Geçerlilik zaman çubuğu)")
def horizon(scenario_id: int | None = None, user: CurrentUser = Depends(read24), session: Session = Depends(get_session)) -> dict:
    return service.horizon(session, user, scenario_id)


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


@router.post("/capacity/{kind}", status_code=201, summary="Kapasite girişi: yeni kayıt")
def create(kind: str, body: NewEntry, scenario_id: int | None = None, user: CurrentUser = Depends(write24), session: Session = Depends(get_session)) -> dict:
    return service.create(session, user, kind, scenario_id, body.values)


@router.put("/capacity/{kind}", summary="Kapasite girişi: hücre değişiklikleri (hepsi ya da hiçbiri)")
def change(kind: str, body: Changes, scenario_id: int | None = None, user: CurrentUser = Depends(write24), session: Session = Depends(get_session)) -> dict:
    return service.change(session, user, kind, scenario_id, [c.model_dump() for c in body.changes])


@router.delete("/capacity/{kind}/{row_id}", summary="Kapasite girişi: senaryonun kendi satırını sil")
def remove(kind: str, row_id: int, scenario_id: int | None = None, user: CurrentUser = Depends(write24), session: Session = Depends(get_session)) -> dict:
    return service.remove(session, user, kind, scenario_id, row_id)


@router.post("/capacity/{kind}/{row_id}/invalidate", summary="Kapasite girişi: bu senaryoda geçersiz yap")
def invalidate(kind: str, row_id: int, scenario_id: int | None = None, user: CurrentUser = Depends(write24), session: Session = Depends(get_session)) -> dict:
    return service.set_valid(session, user, kind, scenario_id, row_id, False)


@router.post("/capacity/{kind}/{row_id}/validate", summary="Kapasite girişi: bu senaryoda yeniden geçerli yap")
def validate(kind: str, row_id: int, scenario_id: int | None = None, user: CurrentUser = Depends(write24), session: Session = Depends(get_session)) -> dict:
    return service.set_valid(session, user, kind, scenario_id, row_id, True)


@router.post("/capacity/{kind}/{row_id}/restore", summary="Kapasite girişi: senaryo farkını kaldır")
def restore(kind: str, row_id: int, scenario_id: int | None = None, user: CurrentUser = Depends(write24), session: Session = Depends(get_session)) -> dict:
    return service.restore(session, user, kind, scenario_id, row_id)
