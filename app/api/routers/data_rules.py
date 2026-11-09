"""Veri kuralları (ekran 04, fonksiyon 16, 18, 19; K-140…K-142).

Tanımlama 16, sıra ve aç / kapa 18, uygulama 19: System owner ve Admin yazar, Key user okur, End user görmez.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_session
from ..deps import require
from ..permissions import Access
from ..services import data_rules as service
from ..services.auth import CurrentUser

router = APIRouter(tags=["Veri kuralları"])
read_16 = require(16, Access.READ)
write_16 = require(16, Access.WRITE)
write_19 = require(19, Access.WRITE)


class RuleResult(BaseModel):
    kind: str | None = None
    value: str | float | int | None = None
    source_field: str | None = None
    operator: str | None = None
    operand_value: str | float | int | None = None
    operand_field: str | None = None


class RuleChange(BaseModel):
    id: int | None = None
    entity: str | None = None
    name: str | None = None
    target: str | None = None
    result: RuleResult | None = None
    mode: str | None = None
    active: bool | None = None
    groups: list[list[dict]] | None = None
    delete: bool | None = None


class RuleOrder(BaseModel):
    entity: str
    ids: list[int] = []


class RulesBody(BaseModel):
    changes: list[RuleChange] = []
    orders: list[RuleOrder] = []


class ApplyBody(BaseModel):
    entity: str | None = None


@router.get("/data-rules/fields/{entity}", summary="Kural penceresinin alanları: ad, etiket, tip, değer listesi, hedef olabilir mi")
def fields(entity: str, user: CurrentUser = Depends(read_16), session: Session = Depends(get_session)) -> list[dict]:
    return service.fields(session, entity)


@router.get("/data-rules/{rule_id:int}", summary="Veri kuralı: hedef, sonuç, seçenek, koşullar")
def detail(rule_id: int, user: CurrentUser = Depends(read_16), session: Session = Depends(get_session)) -> dict:
    return service.rule_detail(session, rule_id)


@router.put("/data-rules", summary="Veri kurallarının ve sıranın toplu kaydı (K-132)")
def save(body: RulesBody, user: CurrentUser = Depends(write_16), session: Session = Depends(get_session)) -> dict:
    return service.save_rules(session, user, [c.model_dump(exclude_unset=True) for c in body.changes], [o.model_dump() for o in body.orders])


@router.post("/data-rules/apply", status_code=202, summary="Kuralları yeniden uygula: tablonun ya da kuralı olan bütün tabloların zinciri (K-142)")
def apply(body: ApplyBody, user: CurrentUser = Depends(write_19), session: Session = Depends(get_session)) -> dict:
    return service.apply(session, user, body.entity)
