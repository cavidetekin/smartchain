"""Kullanıcı yönetimi uç noktaları (fonksiyon 88, K-101). Liste uçları ortak liste yönlendiricisinden gelir (lists.USERS)."""
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy.orm import Session

from ..db import get_session
from ..deps import require
from ..permissions import Access
from ..services import users as service
from ..services.auth import CurrentUser

router = APIRouter(prefix="/users", tags=["Kullanıcılar"])
read = require(88, Access.READ)
write = require(88, Access.WRITE)

Role = Literal["System owner", "Admin", "Key user", "End user"]
FullName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]


class UserCreate(BaseModel):
    full_name: FullName
    user_name: str = Field(pattern=r"^[a-z][a-z0-9._-]{1,59}$")  # K-101
    role: Role


class RoleChange(BaseModel):
    role: Role


class NameChange(BaseModel):
    full_name: FullName


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"  # geçici şifre tarayıcı ya da vekil önbelleğinde kalmasın


@router.get("/{user_id:int}", summary="Kayıt, açık oturum sayısı, işlemlerin izni ve nedeni (satır menüsü)")
def detail(user_id: int, user: CurrentUser = Depends(read), session: Session = Depends(get_session)) -> dict:
    return service.detail(session, user, user_id)


@router.post("", status_code=201, summary="Kullanıcı ekle; geçici şifre bir kez döner")
def create(body: UserCreate, response: Response, user: CurrentUser = Depends(write),
           session: Session = Depends(get_session)) -> dict:
    _no_store(response)
    return service.create(session, user, body.full_name, body.user_name, body.role)


@router.put("/{user_id:int}/role", summary="Rol değiştir; bir sonraki istekte geçerli, oturum kapanmaz")
def change_role(user_id: int, body: RoleChange, user: CurrentUser = Depends(write),
                session: Session = Depends(get_session)) -> dict:
    return service.change_role(session, user, user_id, body.role)


@router.put("/{user_id:int}/name", summary="Ad soyad düzelt")
def change_name(user_id: int, body: NameChange, user: CurrentUser = Depends(write),
                session: Session = Depends(get_session)) -> dict:
    return service.change_name(session, user, user_id, body.full_name)


@router.post("/{user_id:int}/reset-password", summary="Şifre sıfırla; geçici şifre bir kez döner, oturumlar kapanır")
async def reset_password(user_id: int, request: Request, response: Response, user: CurrentUser = Depends(write),
                         session: Session = Depends(get_session)) -> dict:
    _no_store(response)
    out, ended = await run_in_threadpool(service.reset_password, session, user, user_id)
    await request.app.state.notifier.close_sessions(ended)
    return out


@router.post("/{user_id:int}/unlock", summary="Kilidi aç")
def unlock(user_id: int, user: CurrentUser = Depends(write), session: Session = Depends(get_session)) -> dict:
    return service.unlock(session, user, user_id)


@router.post("/{user_id:int}/close", summary="Kapat: pasif olur, oturumlar kapanır; silinmez")
async def close(user_id: int, request: Request, user: CurrentUser = Depends(write),
                session: Session = Depends(get_session)) -> dict:
    out, ended = await run_in_threadpool(service.close, session, user, user_id)
    await request.app.state.notifier.close_sessions(ended)
    return out


@router.post("/{user_id:int}/reopen", summary="Geri aç; şifre değişmez, kilit ve sayaçlar temizlenir")
def reopen(user_id: int, user: CurrentUser = Depends(write), session: Session = Depends(get_session)) -> dict:
    return service.reopen(session, user, user_id)
