"""GET /api/health: uygulamanın ve veritabanının durumu (Sistem sağlığı ekranının çekirdeği, ekran 24)."""
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from ..db import get_session
from ..services import health as service

router = APIRouter(tags=["Sistem"])


@router.get("/health", summary="Uygulama ve veritabanı durumu")
def health(response: Response, session: Session = Depends(get_session)) -> dict:
    result = service.check(session)
    if result["status"] != "ok":
        response.status_code = 503
    return result
