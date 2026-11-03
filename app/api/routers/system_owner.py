"""Sistem ayarları (ekran 25, fonksiyon 96; K-104, K-105) ve yetki matrisi (fonksiyon 90, K-100)."""
from urllib.parse import quote

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from .. import permissions
from ..db import get_session
from ..deps import require
from ..permissions import Access
from ..services import field_definitions, login_policy, permission_matrix
from ..services.auth import CurrentUser

router = APIRouter(tags=["System owner"])
owner_read = require(96, Access.READ)
owner_write = require(96, Access.WRITE)
matrix_read = require(90, Access.READ)  # Admin salt okunur görür (K-100)


class LabelChange(BaseModel):
    label: str = Field(max_length=40)  # K-88; boş: standart etiket


class LoginPolicyChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    PasswordMinLength: int | None = None
    PasswordRequireLetterAndDigit: bool | None = None
    PasswordHistoryCount: int | None = None
    PasswordMaxAgeDays: int | None = None
    LoginMaxFailedAttempts: int | None = None
    LoginLockMinutes: int | None = None
    SessionIdleMinutes: int | None = None
    SessionWarningMinutes: int | None = None


@router.get("/field-definitions/{table}/{field}", summary="Veri sözlüğü: alan ve kayıtlı görünümlerde kullanımı")
def field_detail(table: str, field: str, user: CurrentUser = Depends(owner_read), session: Session = Depends(get_session)) -> dict:
    return field_definitions.detail(session, table, field)


@router.put("/field-definitions/{table}/{field}/label", summary="Alan etiketi; boşsa standart etiket, ek alan listeden kalkar")
def field_label(table: str, field: str, body: LabelChange, user: CurrentUser = Depends(owner_write),
                session: Session = Depends(get_session)) -> dict:
    return field_definitions.set_label(session, user, table, field, body.label)


@router.get("/settings/login-policy", summary="Şifre ve oturum ayarları: değerler, varsayılanlar, sınırlar")
def policy(user: CurrentUser = Depends(owner_read), session: Session = Depends(get_session)) -> dict:
    return login_policy.read(session)


@router.put("/settings/login-policy", summary="Şifre ve oturum ayarları: yalnız değişenler yazılır, denetim izine")
def policy_update(body: LoginPolicyChange, user: CurrentUser = Depends(owner_write),
                  session: Session = Depends(get_session)) -> dict:
    changes = {k: int(v) for k, v in body.model_dump(exclude_none=True).items()}
    return login_policy.update(session, user, changes)


@router.get("/permissions/matrix", summary="Yetki matrisi: gruplar, fonksiyonlar, istisnalar")
def matrix(user: CurrentUser = Depends(matrix_read)) -> dict:
    return permissions.matrix()


@router.get("/permissions/matrix/export", summary="Yetki matrisi Excel'i: fonksiyon düzeyinde")
def matrix_export(user: CurrentUser = Depends(matrix_read),
                  session: Session = Depends(get_session, scope="function")) -> Response:
    data, name = permission_matrix.export(session, user)
    return Response(data, media_type=permission_matrix.XLSX,
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})
