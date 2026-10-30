"""İstek başına oturum ve köken denetimi (K-97).

- `current_user`: oturum ister; şifre değişikliği bekleyen kullanıcıyı (ilk giriş, sıfırlama, süre doldu) geçirmez.
- `session_user`: oturum ister, şifre değişikliği bekleyeni de geçirir (yalnız /api/auth uç noktaları).
- `check_origin`: durum değiştiren isteklerde Origin izinli adreslerden biri olmalı (CSRF; SameSite=Strict'e ek).

Oturum denetimi kendi kısa veritabanı oturumunu açar ve hemen kapatır; uç noktanın oturumundan (ör. dosya akışında
scope="function") bağımsızdır. Testler bu bağımlılıkları dependency_overrides ile değiştirebilir.
"""
from urllib.parse import urlsplit

from fastapi import Depends, Request
from sqlalchemy.orm import sessionmaker

from .db import get_engine
from .errors import AppError
from .services import auth
from .services.auth import CurrentUser
from .settings import get_settings

COOKIE = "smartchain_session"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def origin_allowed(origin: str | None, host: str | None) -> bool:
    """Origin yoksa (tarayıcı dışı istemci, aynı köken GET) izinli; varsa ayardaki listede ya da Host'la aynı olmalı."""
    if not origin:
        return True
    origin = origin.strip().rstrip("/").lower()
    allowed = get_settings().origins()
    if allowed:
        return origin in allowed
    return bool(host) and urlsplit(origin).netloc == host.lower()


def check_origin(request: Request) -> None:
    if request.method not in SAFE_METHODS and not origin_allowed(request.headers.get("origin"), request.headers.get("host")):
        raise AppError("bad_origin", "İstek izin verilmeyen bir adresten geldi.", 403)


def authenticate(token: str | None) -> CurrentUser:
    try:
        engine = get_engine()
    except Exception as exc:
        raise AppError("database_unavailable", auth.DB_DOWN, 503) from exc
    with sessionmaker(bind=engine)() as session:
        return auth.authenticate(session, token)


def session_user(request: Request, _origin: None = Depends(check_origin)) -> CurrentUser:
    return authenticate(request.cookies.get(COOKIE))


def current_user(user: CurrentUser = Depends(session_user)) -> CurrentUser:
    if user.must_change_password:
        raise AppError("password_change_required", "Devam etmek için şifrenizi değiştirin.", 403)
    return user
