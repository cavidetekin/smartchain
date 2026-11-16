"""Parametreler (ekran 06; fonksiyon 22, 23; K-175): Baz senaryonun parametreleri, hedefleri ve dönem dizisi; bağlam çubuğunun senaryosu."""
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from ..db import get_session
from ..deps import require
from ..permissions import Access
from ..services import parameters as service
from ..services.auth import CurrentUser

router = APIRouter(tags=["Parametreler"])
read22, write22 = require(22, Access.READ), require(22, Access.WRITE)
read23, write23 = require(23, Access.READ), require(23, Access.WRITE)
context_read = require(82)  # bağlam çubuğu (U-17): herkes okur; 82 Sabah özeti okuma (K-100)


class Changes(BaseModel):
    model_config = ConfigDict(extra="forbid")
    changes: dict[str, Any]


class ObjectiveRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int
    active: bool
    seconds: int | float | str | None = None
    tolerance: int | float | str | None = None


class Objectives(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rows: list[ObjectiveRow]


class BucketRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bucket_type: str | None = None
    count: int | None = None
    span_unit: str | None = None


class Buckets(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rows: list[BucketRow]
    week_start: str | None = None   # yalnız önizlemede: taslak hafta başlangıcı
    plan_start: str | None = None   # yalnız önizlemede: taslak plan başlangıcı


@router.get("/scenarios/current", summary="Bağlam çubuğundaki senaryo (7.1'de Baz)")
def current(user: CurrentUser = Depends(context_read), session: Session = Depends(get_session)) -> dict:
    return service.current_scenario(session)


@router.get("/parameters", summary="Parametreler: başlıklar, alanlar, değerler (22 okuma)")
def read(user: CurrentUser = Depends(read22), session: Session = Depends(get_session)) -> dict:
    return service.read(session)


@router.put("/parameters", summary="Parametreler: yalnız değişenler yazılır, denetim izine (22 yazma)")
def update(body: Changes, user: CurrentUser = Depends(write22), session: Session = Depends(get_session)) -> dict:
    return service.update(session, user, body.changes)


@router.get("/parameters/objectives", summary="Hedefler: sıra, süre bütçesi, ödün payı, aktiflik (22 okuma)")
def objectives(user: CurrentUser = Depends(read22), session: Session = Depends(get_session)) -> dict:
    return service.objectives(session)


@router.put("/parameters/objectives", summary="Hedefler: liste sırasıyla tamamı yazılır (22 yazma)")
def update_objectives(body: Objectives, user: CurrentUser = Depends(write22), session: Session = Depends(get_session)) -> dict:
    return service.update_objectives(session, user, [r.model_dump() for r in body.rows])


@router.get("/parameters/time-buckets/{axis}", summary="Dönem dizisi (plan | rapor), hesaplanmış başlangıç ve bitişle (23 okuma)")
def time_buckets(axis: str, user: CurrentUser = Depends(read23), session: Session = Depends(get_session)) -> dict:
    return service.time_buckets(session, axis)


@router.post("/parameters/time-buckets/{axis}/preview", summary="Kaydedilmemiş dizinin tarihleri (23 okuma)")
def preview(axis: str, body: Buckets, user: CurrentUser = Depends(read23), session: Session = Depends(get_session)) -> dict:
    return service.preview_time_buckets(session, axis, [r.model_dump() for r in body.rows], body.week_start, body.plan_start)


@router.put("/parameters/time-buckets/{axis}", summary="Dönem dizisi baştan yazılır, denetim izine (23 yazma)")
def update_time_buckets(axis: str, body: Buckets, user: CurrentUser = Depends(write23), session: Session = Depends(get_session)) -> dict:
    return service.update_time_buckets(session, user, axis, [r.model_dump() for r in body.rows])
