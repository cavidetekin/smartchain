"""Arka planda hazırlanan Excel dosyasının indirilmesi (K-91, K-93)."""
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..db import get_session
from ..deps import current_user
from ..services import export as service
from ..services.auth import CurrentUser

router = APIRouter(tags=["Dışa aktarım"], dependencies=[Depends(current_user)])


@router.get("/exports/{job_id}/file", summary="Arka planda hazırlanan Excel dosyası (yalnız sahibine, süresi içinde)")
def download(job_id: int, user: CurrentUser = Depends(current_user),
             session: Session = Depends(get_session, scope="function")) -> FileResponse:
    # scope="function": oturum dosya akmaya başlamadan kapanır; akış süresince bağlantı tutulmaz (docs/08).
    path, file_name = service.download(session, job_id, user.id)
    return FileResponse(path, media_type=service.XLSX, filename=file_name)
