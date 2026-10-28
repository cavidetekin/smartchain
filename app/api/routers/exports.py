"""Arka planda hazırlanan Excel dosyasının indirilmesi (K-91, K-93)."""
from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..db import get_session
from ..services import export as service

router = APIRouter(tags=["Dışa aktarım"])


@router.get("/exports/{job_id}/file", summary="Arka planda hazırlanan Excel dosyası (yalnız sahibine, süresi içinde)")
def download(job_id: int, user_id: int = Query(...),
             session: Session = Depends(get_session, scope="function")) -> FileResponse:
    # scope="function": oturum dosya akmaya başlamadan kapanır; akış süresince bağlantı tutulmaz (docs/08).
    path, file_name = service.download(session, job_id, user_id)
    return FileResponse(path, media_type=service.XLSX, filename=file_name)
