"""Yetki kararları (fonksiyon 90; K-100): matris denetimi, nesne bağlamı ve ret kaydı.

Yetkisiz istek 403 ile reddedilir ve denetim izine "Yetkisiz istek" yazılır (olağan dışı deneme). Ret kaydı kendi kısa
veritabanı oturumunda yazılır; isteğin oturumu geri alınsa da iz kalır. Yazılamazsa ret yine verilir (loga düşer).
"""
import logging

from sqlalchemy.orm import sessionmaker

from .. import permissions as perm
from ..db import get_engine
from ..errors import AppError
from ..permissions import Access
from ..repositories import audit
from .auth import CurrentUser

log = logging.getLogger("smartchain.authz")

DENIED = "Yetkisiz istek"
INVALID_ROLE = "Geçersiz rol"
OBJECT = "Fonksiyon"


def record_denial(user: CurrentUser, fn: int, access: Access, details: dict) -> None:
    try:
        with sessionmaker(bind=get_engine())() as session:
            audit.write_audit(session, DENIED, user.id, OBJECT, str(fn),
                              {"role": user.role, "function": fn, "function_name": perm.FUNCTIONS[fn].name,
                               "access": access.value, **details})
            session.commit()
    except Exception as exc:  # iz yazılamasa da ret verilir
        log.warning("Ret denetim izine yazılamadı: %s", exc)


def forbidden(user: CurrentUser, fn: int, access: Access, details: dict | None = None) -> AppError:
    """403 forbidden: gereken rol ve kimden isteneceği (docs/08 "Yetki"); ret denetim izine yazılır."""
    record_denial(user, fn, access, details or {})
    return AppError("forbidden", perm.forbidden_message(fn, access), 403, [{
        "function": fn, "function_name": perm.FUNCTIONS[fn].name, "access": access.value,
        "required_role": perm.required_role(fn, access)}])


def ensure(user: CurrentUser, fn: int, access: Access, own: bool = True, details: dict | None = None) -> None:
    """Matris denetimi; own=False: başkasının nesnesi ya da kaydı (sahibi ve kendi düzeyleri yetmez)."""
    if not perm.allows(user.role, fn, access, own=own):
        raise forbidden(user, fn, access, details)


def ensure_owner(user: CurrentUser, owner_id: int | None, fn: int, code: str, what: str,
                 details: dict | None = None) -> None:
    """Nesne bağlamı: yalnız sahibi değiştirir, diğerleri salt okunur görür (K-100)."""
    if owner_id == user.id:
        return
    record_denial(user, fn, Access.WRITE, {"reason": "sahibi değil", **(details or {})})
    raise AppError(code, f"{what} yalnız sahibi değiştirebilir; sizin için salt okunur.", 403)
