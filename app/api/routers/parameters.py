"""Parametreler (ekran 06; fonksiyon 22, 23; K-175): seçili senaryonun parametreleri, hedefleri ve dönem dizisi. Senaryo `scenario_id` sorgu parametresiyle gelir (K-177)."""
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
read26, write26 = require(26, Access.READ), require(26, Access.WRITE)


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


class WarningRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str
    active: bool
    low: int | float | str | None = None
    medium: int | float | str | None = None
    high: int | float | str | None = None
    critical: int | float | str | None = None
    severity: str | None = None


class Warnings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rows: list[WarningRow]


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


@router.get("/parameters", summary="Parametreler: başlıklar, alanlar, değerler (22 okuma)")
def read(scenario_id: int | None = None, user: CurrentUser = Depends(read22), session: Session = Depends(get_session)) -> dict:
    return service.read(session, user, scenario_id)


@router.put("/parameters", summary="Parametreler: yalnız değişenler yazılır, denetim izine (22 yazma)")
def update(body: Changes, scenario_id: int | None = None, user: CurrentUser = Depends(write22), session: Session = Depends(get_session)) -> dict:
    return service.update(session, user, body.changes, scenario_id)


@router.get("/parameters/objectives", summary="Hedefler: sıra, süre bütçesi, ödün payı, aktiflik (22 okuma)")
def objectives(scenario_id: int | None = None, user: CurrentUser = Depends(read22), session: Session = Depends(get_session)) -> dict:
    return service.objectives(session, user, scenario_id)


@router.put("/parameters/objectives", summary="Hedefler: liste sırasıyla tamamı yazılır (22 yazma)")
def update_objectives(body: Objectives, scenario_id: int | None = None, user: CurrentUser = Depends(write22), session: Session = Depends(get_session)) -> dict:
    return service.update_objectives(session, user, [r.model_dump() for r in body.rows], scenario_id)


@router.get("/parameters/time-buckets/{axis}", summary="Dönem dizisi (plan | rapor), hesaplanmış başlangıç ve bitişle (23 okuma)")
def time_buckets(axis: str, scenario_id: int | None = None, user: CurrentUser = Depends(read23), session: Session = Depends(get_session)) -> dict:
    return service.time_buckets(session, user, axis, scenario_id)


@router.post("/parameters/time-buckets/{axis}/preview", summary="Kaydedilmemiş dizinin tarihleri (23 okuma)")
def preview(axis: str, body: Buckets, scenario_id: int | None = None, user: CurrentUser = Depends(read23), session: Session = Depends(get_session)) -> dict:
    return service.preview_time_buckets(session, user, axis, [r.model_dump() for r in body.rows], body.week_start, body.plan_start, scenario_id)


@router.put("/parameters/time-buckets/{axis}", summary="Dönem dizisi baştan yazılır, denetim izine (23 yazma)")
def update_time_buckets(axis: str, body: Buckets, scenario_id: int | None = None, user: CurrentUser = Depends(write23), session: Session = Depends(get_session)) -> dict:
    return service.update_time_buckets(session, user, axis, [r.model_dump() for r in body.rows], scenario_id)


@router.get("/parameters/warning-thresholds", summary="Uyarı eşikleri: kademeli eşik, önem, aktiflik (26 okuma)")
def warning_thresholds(scenario_id: int | None = None, user: CurrentUser = Depends(read26), session: Session = Depends(get_session)) -> dict:
    return service.warning_thresholds(session, user, scenario_id)


@router.put("/parameters/warning-thresholds", summary="Uyarı eşikleri: tablonun tamamı, yalnız değişen satır yazılır (26 yazma)")
def update_warning_thresholds(body: Warnings, scenario_id: int | None = None, user: CurrentUser = Depends(write26), session: Session = Depends(get_session)) -> dict:
    return service.update_warning_thresholds(session, user, [r.model_dump() for r in body.rows], scenario_id)
