"""Excel yükleme (ekran 02, fonksiyon 03, K-129). Dosya ham gövdeyle gelir, akışla diske yazılır; python-multipart gerekmez."""
from urllib.parse import quote, unquote

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..db import get_session
from ..deps import require
from ..permissions import Access
from ..services import imports as service
from ..services.auth import CurrentUser

router = APIRouter(tags=["Excel yükleme"])
read = require(3, Access.READ)
write = require(3, Access.WRITE)
MB = 1024 * 1024


@router.post("/imports/{entity}", summary="Excel dosyasını yükle, ön kontrol; küçük dosya sonucu döner, büyük dosya iş olur")
async def upload(entity: str, request: Request, mode: str = Query(service.MODE_CHANGED), user: CurrentUser = Depends(write),
                 session: Session = Depends(get_session, scope="function")) -> JSONResponse:
    settings = await run_in_threadpool(service.limits, session, entity, mode)
    max_bytes = settings["ImportMaxMb"] * MB
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > max_bytes:
        raise service.too_large(settings["ImportMaxMb"])
    temp = service.temp_path()
    size = 0
    try:
        with temp.open("wb") as out:
            async for chunk in request.stream():
                size += len(chunk)
                if size > max_bytes:
                    raise service.too_large(settings["ImportMaxMb"])
                out.write(chunk)
        name = unquote(request.headers.get("x-file-name", "")) or f"{entity}.xlsx"
        body, status = await run_in_threadpool(service.start, session, user, entity, mode, name, temp)
    finally:
        temp.unlink(missing_ok=True)
    return JSONResponse(body, status_code=status)


@router.get("/imports/pending/{entity}", summary="Kullanıcının bu tablodaki açık ön kontrolü")
def pending(entity: str, user: CurrentUser = Depends(read), session: Session = Depends(get_session)) -> dict | None:
    return service.pending(session, user, entity)


@router.get("/imports/{batch_id}", summary="Yüklemenin özeti")
def summary(batch_id: int, user: CurrentUser = Depends(read), session: Session = Depends(get_session)) -> dict:
    return service.summary(session, batch_id)


@router.post("/imports/{batch_id}/continue", summary="Geçerli satırlarla devam: parti Alındı; iz")
def continue_batch(batch_id: int, user: CurrentUser = Depends(write), session: Session = Depends(get_session)) -> dict:
    return service.continue_batch(session, user, batch_id)


@router.post("/imports/{batch_id}/cancel", summary="Vazgeç: satırlar ve dosya silinir")
def cancel(batch_id: int, user: CurrentUser = Depends(write), session: Session = Depends(get_session)) -> dict:
    return service.cancel(session, user, batch_id)


@router.get("/imports/{batch_id}/error-report", summary="Hata raporu: hatalı satırlar ve Hata kolonu; iz")
def error_report(batch_id: int, user: CurrentUser = Depends(read), session: Session = Depends(get_session, scope="function")) -> Response:
    data, name = service.error_report(session, user, batch_id)
    return Response(data, media_type=service.XLSX, headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})
