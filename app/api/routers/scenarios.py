"""Senaryolar (ekran 07; fonksiyon 27, 28; K-177). Liste ortak liste ucudur (`scenarios`). Yönetim işlemleri fonksiyon 27 yazma yetkisine ek
olarak serviste Admin ve üstüne sınırlıdır; seçili senaryo ve geçiş herkese açıktır (82 okuma)."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from ..db import get_session
from ..deps import require
from ..permissions import Access
from ..services import scenarios as service
from ..services.auth import CurrentUser

router = APIRouter(prefix="/scenarios", tags=["Senaryolar"])
context = require(82)  # bağlam çubuğu (U-17): herkes okur ve kendi seçimini yazar; 82 Sabah özeti okuma (K-100)
manage = require(27, Access.WRITE)
nightly = require(28, Access.WRITE)


class Selection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int


class NewScenario(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    source_id: int
    follows_base: bool = True


class Name(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None


class NightlyRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int
    runs_nightly: bool


class Nightly(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rows: list[NightlyRow]


@router.get("/options", summary="Bağlam çubuğunun listesi: aktif senaryolar")
def options(user: CurrentUser = Depends(context), session: Session = Depends(get_session)) -> dict:
    return service.options(session)


@router.get("/current", summary="Kullanıcının senaryosu: verilen, yoksa hatırlanan, o da geçersizse Baz")
def current(scenario_id: int | None = None, user: CurrentUser = Depends(context), session: Session = Depends(get_session)) -> dict:
    return service.current(session, user, scenario_id)


@router.put("/current", summary="Senaryo seçimi; kullanıcı bazında hatırlanır")
def select(body: Selection, user: CurrentUser = Depends(context), session: Session = Depends(get_session)) -> dict:
    return service.select(session, user, body.id)


@router.put("/nightly", summary='"Gece çalışsın" ve gece sırası, toplu (28 yazma)')
def save_nightly(body: Nightly, user: CurrentUser = Depends(nightly), session: Session = Depends(get_session)) -> dict:
    return service.save_nightly(session, user, [r.model_dump() for r in body.rows])


@router.post("", summary="Yeni senaryo: var olan senaryodan kopya (Admin ve üstü)")
def create(body: NewScenario, user: CurrentUser = Depends(manage), session: Session = Depends(get_session)) -> dict:
    return service.create(session, user, body.name, body.source_id, body.follows_base)


@router.put("/{scenario_id}", summary="Yeniden adlandır (Admin ve üstü)")
def rename(scenario_id: int, body: Name, user: CurrentUser = Depends(manage), session: Session = Depends(get_session)) -> dict:
    return service.rename(session, user, scenario_id, body.name)


@router.post("/{scenario_id}/deactivate", summary="Pasif yap (Admin ve üstü)")
def deactivate(scenario_id: int, user: CurrentUser = Depends(manage), session: Session = Depends(get_session)) -> dict:
    return service.set_active(session, user, scenario_id, False)


@router.post("/{scenario_id}/activate", summary="Aktif yap (Admin ve üstü)")
def activate(scenario_id: int, user: CurrentUser = Depends(manage), session: Session = Depends(get_session)) -> dict:
    return service.set_active(session, user, scenario_id, True)


@router.post("/{scenario_id}/detach", summary="Baz'dan ayır: geri alınamaz (Admin ve üstü)")
def detach(scenario_id: int, user: CurrentUser = Depends(manage), session: Session = Depends(get_session)) -> dict:
    return service.detach(session, user, scenario_id)


@router.get("/{scenario_id}/delete-info", summary="Silme onayının bilgisi: silinecek plan versiyonu sayısı (Admin ve üstü)")
def delete_info(scenario_id: int, user: CurrentUser = Depends(manage), session: Session = Depends(get_session)) -> dict:
    return service.delete_info(session, user, scenario_id)


@router.delete("/{scenario_id}", summary="Sil: parametreleri ve plan versiyonlarıyla (Admin ve üstü)")
def delete(scenario_id: int, user: CurrentUser = Depends(manage), session: Session = Depends(get_session)) -> dict:
    return service.delete(session, user, scenario_id)
