"""Excel şablonu (ekran 02, fonksiyon 02, K-110)."""
from urllib.parse import quote

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from ..db import get_session
from ..deps import require
from ..permissions import Access
from ..services import templates as service
from ..services.auth import CurrentUser

router = APIRouter(tags=["Excel şablonu"])
read = require(2, Access.READ)


@router.get("/templates/{entity}/info", summary="Şablon bilgisi: sürüm, alanlar, zorunlular, kod listeleri")
def template_info(entity: str, user: CurrentUser = Depends(read), session: Session = Depends(get_session)) -> dict:
    return service.info(session, entity)


@router.get("/templates/{entity}", summary="Şablonu indir; iz bırakır")
def template_file(entity: str, user: CurrentUser = Depends(read),
                  session: Session = Depends(get_session, scope="function")) -> Response:
    data, name = service.download(session, user, entity)
    return Response(data, media_type=service.XLSX, headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})
