"""Validasyon ve validasyon kuralları (ekran 02 ve 27, fonksiyon 04 ve 100; K-133…K-139).

Çekmece ve yeniden validasyon fonksiyon 04 (Key user ve üstü). Kurallar fonksiyon 100: System owner ve Admin yazar, Key user okur.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_session
from ..deps import require
from ..permissions import Access
from ..services import validation as service
from ..services.auth import CurrentUser

router = APIRouter(tags=["Validasyon"])
read_04 = require(4, Access.READ)
write_04 = require(4, Access.WRITE)
read_100 = require(100, Access.READ)
write_100 = require(100, Access.WRITE)


class RuleChange(BaseModel):
    id: int | None = None
    entity: str | None = None
    name: str | None = None
    severity: str | None = None
    message: str | None = None
    active: bool | None = None
    groups: list[list[dict]] | None = None
    delete: bool | None = None
    reset: bool | None = None


class Threshold(BaseModel):
    entity: str
    value: str | float | None = None


class RulesBody(BaseModel):
    changes: list[RuleChange] = []
    thresholds: list[Threshold] = []


@router.get("/validation/{entity}", summary="Validasyon çekmecesinin özeti: durum, son parti, sayılar, hata oranı ve eşik, kural bazında bulgular")
def summary(entity: str, user: CurrentUser = Depends(read_04), session: Session = Depends(get_session)) -> dict:
    return service.summary(session, entity)


@router.post("/validation/{entity}/revalidate", status_code=202, summary="Tablonun validasyon zincirini yeniden sıraya koyar")
def revalidate(entity: str, user: CurrentUser = Depends(write_04), session: Session = Depends(get_session)) -> dict:
    return service.revalidate(session, user, entity)


@router.get("/validation-rules/fields/{entity}", summary="Koşul editörünün alanları: ad, etiket, tip, değer listesi")
def fields(entity: str, user: CurrentUser = Depends(read_100), session: Session = Depends(get_session)) -> list[dict]:
    return service.fields(session, entity)


@router.get("/validation-rules/{rule_id:int}", summary="Kural ve koşulları")
def detail(rule_id: int, user: CurrentUser = Depends(read_100), session: Session = Depends(get_session)) -> dict:
    return service.rule_detail(session, rule_id)


@router.put("/validation-rules", summary="Kuralların ve hata eşiklerinin toplu kaydı (K-132)")
def save(body: RulesBody, user: CurrentUser = Depends(write_100), session: Session = Depends(get_session)) -> dict:
    return service.save_rules(session, user, [c.model_dump(exclude_unset=True) for c in body.changes], [t.model_dump() for t in body.thresholds])
