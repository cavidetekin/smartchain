"""Tam ve kısmi aktarım (ekran 02, fonksiyon 05, 06 ve 07, K-149…K-153, K-155) ve Veri aktarım raporu (fonksiyon 08, K-156).
Yetki: tam 05, kısmi 06, rapor 08 (Key user ve üstü)."""
from urllib.parse import quote

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_session
from ..deps import require
from ..permissions import Access
from ..services import transfer as service
from ..services.auth import CurrentUser

router = APIRouter(tags=["Aktarım"])
read = require(5, Access.READ)
write = require(5, Access.WRITE)
partial_read = require(6, Access.READ)
partial_write = require(6, Access.WRITE)
report_read = require(8, Access.READ)


class PartialRequest(BaseModel):
    groups: list[str]


@router.get("/transfers/plan", summary="Onay penceresi: tablo başına güncel satır, Hatalı, durum; başlatılamıyorsa nedeni")
def plan(user: CurrentUser = Depends(read), session: Session = Depends(get_session)) -> dict:
    return service.plan(session)


@router.post("/transfers", status_code=202, summary="Tam aktarımı başlat; iş kuyruğuna yazılır")
def start(user: CurrentUser = Depends(write), session: Session = Depends(get_session)) -> dict:
    return service.start(session, user)


@router.get("/transfers/partial/plan", summary="Kısmi aktarım penceresi: gruplar ve tabloları; süren iş; validasyonu bitmemiş tablolar")
def partial_plan(user: CurrentUser = Depends(partial_read), session: Session = Depends(get_session)) -> dict:
    return service.partial_plan(session)


@router.post("/transfers/partial", status_code=202, summary="Kısmi aktarımı başlat (seçilen gruplar); iş kuyruğuna yazılır")
def start_partial(body: PartialRequest, user: CurrentUser = Depends(partial_write), session: Session = Depends(get_session)) -> dict:
    return service.start_partial(session, user, body.groups)


@router.get("/transfers/{job_id}", summary="Veri aktarım raporu: durum, tür ve gruplar, başlatan, süre, veri versiyonu, tablo başına sayılar")
def result(job_id: int, user: CurrentUser = Depends(report_read), session: Session = Depends(get_session)) -> dict:
    return service.result(session, job_id)


@router.get("/transfers/{job_id}/excel", summary="Veri aktarım raporunun Excel'i; iz")
def report_excel(job_id: int, user: CurrentUser = Depends(report_read), session: Session = Depends(get_session, scope="function")) -> Response:
    data, name = service.report_excel(session, user, job_id)
    return Response(data, media_type=service.XLSX, headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})
