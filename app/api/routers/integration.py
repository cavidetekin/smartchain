"""Entegrasyon tanımı ve veri çekme (ekran 02 ve 23, fonksiyon 01 ve 91, K-130).

Yöntem, veritabanı ve view adı yalnız System owner: matriste fonksiyon 96 (Sistem ayarları) bu role açıktır; toplu kayıtta alan bazında denetlenir. Çekim anahtarı, test ve önizleme fonksiyon 91 (Admin ve üstü).
Çekim başlatma fonksiyon 01 (Key user ve üstü).
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_session
from ..deps import require
from ..permissions import Access
from ..services import integration as service, pull as pull_service
from ..services.auth import CurrentUser

router = APIRouter(tags=["Entegrasyon"])
owner = require(96, Access.WRITE)
admin_read = require(91, Access.READ)
admin_write = require(91, Access.WRITE)
pull_read = require(1, Access.READ)
pull_write = require(1, Access.WRITE)


class EntityChange(BaseModel):
    entity: str
    method: str | None = None
    view: str | None = None
    pull_enabled: bool | None = None
    reason: str | None = None


class ChangesBody(BaseModel):
    changes: list[EntityChange]


class ConnectionBody(BaseModel):
    database: str = ""


class StartBody(BaseModel):
    entities: list[str] | None = None
    read_anyway: list[str] = []


@router.put("/integration/entities", summary="Tablo içi düzenlemelerin toplu kaydı; yöntem ve view yalnız System owner")
def save_entities(body: ChangesBody, user: CurrentUser = Depends(admin_write), session: Session = Depends(get_session)) -> dict:
    return service.save_entities(session, user, [c.model_dump(exclude_unset=True) for c in body.changes])


@router.get("/integration/connection", summary="Entegrasyon veritabanı, hesap, kartlar")
def read_connection(user: CurrentUser = Depends(admin_read), session: Session = Depends(get_session)) -> dict:
    return service.read_connection(session)


@router.put("/integration/connection", summary="Entegrasyon veritabanının adı")
def write_connection(body: ConnectionBody, user: CurrentUser = Depends(owner), session: Session = Depends(get_session)) -> dict:
    return service.write_connection(session, user, body.database)


@router.post("/integration/test", summary="Bağlantıyı test et: erişim, kimlik, sinyal, view'lar; yalnız okur")
def test_connection(user: CurrentUser = Depends(admin_write), session: Session = Depends(get_session)) -> dict:
    return service.test_connection(session)


@router.post("/integration/entities/{entity}/preview", summary="20 satır önizleme; hiçbir şey yazılmaz")
def preview(entity: str, user: CurrentUser = Depends(admin_write), session: Session = Depends(get_session)) -> dict:
    return service.preview(session, entity)


@router.get("/integration/entities/{entity}/view-versions", summary="View sürümleri, en yenisi önce")
def view_versions(entity: str, user: CurrentUser = Depends(admin_read), session: Session = Depends(get_session)) -> list[dict]:
    return service.view_versions(session, entity)


@router.get("/pulls/plan", summary="Onay penceresi: tablo, yöntem, kaynak, durum")
def plan(user: CurrentUser = Depends(pull_read), session: Session = Depends(get_session)) -> dict:
    return pull_service.plan(session)


@router.post("/pulls", status_code=202, summary="Çekimi başlat; iş kuyruğuna yazılır")
def start(body: StartBody, user: CurrentUser = Depends(pull_write), session: Session = Depends(get_session)) -> dict:
    return pull_service.start(session, user, body.entities, body.read_anyway)


@router.get("/pulls/{job_id}", summary="Çekimin sonucu: tablo başına durum")
def result(job_id: int, user: CurrentUser = Depends(pull_read), session: Session = Depends(get_session)) -> dict:
    return pull_service.result(session, job_id)
