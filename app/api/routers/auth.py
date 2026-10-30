"""Giriş ve oturum uç noktaları (fonksiyon 89; K-97, K-98)."""
from fastapi import APIRouter, Depends, Request, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..db import get_session
from ..deps import COOKIE, check_origin, session_user
from ..security import MAX_PASSWORD
from ..services import auth as service
from ..services.auth import CurrentUser
from ..settings import get_settings

router = APIRouter(prefix="/auth", tags=["Oturum"], dependencies=[Depends(check_origin)])


class LoginRequest(BaseModel):
    user_name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=1, max_length=MAX_PASSWORD)


class PasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=MAX_PASSWORD)
    new_password: str = Field(min_length=1, max_length=MAX_PASSWORD)


def _client(request: Request) -> tuple[str | None, str | None]:
    host = request.client.host if request.client else None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded and host in ("127.0.0.1", "::1"):  # IIS ters vekilinin arkasında gerçek istemci
        host = forwarded.split(",")[0].strip()
    return host, request.headers.get("user-agent")


@router.post("/login", summary="Kullanıcı adı ve şifreyle giriş; oturum çerezi")
def login(body: LoginRequest, request: Request, response: Response,
          session: Session = Depends(get_session)) -> dict:
    address, agent = _client(request)
    token, user = service.login(session, body.user_name, body.password, address, agent)
    response.set_cookie(COOKIE, token, httponly=True, samesite="strict", path="/api",
                        secure=get_settings().session_cookie_secure)
    return service.me(session, user)


@router.post("/logout", status_code=204, summary="Çıkış: oturum kapanır, WebSocket'leri 4401 ile kapanır")
async def logout(request: Request, user: CurrentUser = Depends(session_user),
                 session: Session = Depends(get_session)) -> Response:
    await run_in_threadpool(service.logout, session, user)
    await request.app.state.notifier.close_sessions([user.session_id])
    response = Response(status_code=204)
    response.delete_cookie(COOKIE, path="/api", httponly=True, samesite="strict", secure=get_settings().session_cookie_secure)
    return response


@router.get("/me", summary="Oturumdaki kullanıcı, kalan süre ve şifre politikası (etkinlik sayılmaz)")
def me(user: CurrentUser = Depends(session_user), session: Session = Depends(get_session)) -> dict:
    return service.me(session, user)


@router.post("/activity", summary="Kullanıcı etkinliği: hareketsizlik sayacı sıfırlanır")
def activity(user: CurrentUser = Depends(session_user), session: Session = Depends(get_session)) -> dict:
    return service.activity(session, user)


@router.post("/password", status_code=204, summary="Şifre değiştir; kullanıcının diğer oturumları kapanır")
async def password(body: PasswordRequest, request: Request, user: CurrentUser = Depends(session_user),
                   session: Session = Depends(get_session)) -> Response:
    ended = await run_in_threadpool(service.change_password, session, user, body.current_password, body.new_password)
    await request.app.state.notifier.close_sessions(ended)
    return Response(status_code=204)
