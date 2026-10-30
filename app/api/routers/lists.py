"""Liste uç noktaları (K-87): her liste tanımı için /<ad>/columns, /<ad>/query, /<ad>/values. Oturum ister (K-97)."""
from urllib.parse import quote

from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..db import get_session
from ..deps import current_user
from ..lists import LISTS, ListDefinition
from ..lists.request import (
    DefaultViewRequest, ExportRequest, GroupsRequest, QueryRequest, ValuesRequest, ViewCreate, ViewUpdate,
)
from ..services import export, lists as service, views
from ..services.auth import CurrentUser


def list_router(defn: ListDefinition) -> APIRouter:
    router = APIRouter(prefix=f"/{defn.name}", tags=["Listeler"], dependencies=[Depends(current_user)])

    @router.get("/columns", summary=f"{defn.table}: kolonlar (etiket, tip, filtre tipi) ve parça büyüklüğü")
    def columns(session: Session = Depends(get_session)) -> dict:
        return service.columns(session, defn)

    @router.post("/query", summary=f"{defn.table}: alanlar, sıralama, filtre, parça ve sayılar")
    def query(body: QueryRequest, session: Session = Depends(get_session)) -> dict:
        return service.query(session, defn, body)

    @router.post("/groups", summary=f"{defn.table}: gruplar, satır sayıları ve ara toplamlar (K-90)")
    def groups(body: GroupsRequest, session: Session = Depends(get_session)) -> dict:
        return service.groups(session, defn, body)

    @router.post("/values", summary=f"{defn.table}: liste filtresinin değerleri ve sayıları")
    def values(body: ValuesRequest, session: Session = Depends(get_session)) -> list[dict]:
        return service.values(session, defn, body)

    @router.post("/export", response_model=None,
                 summary=f"{defn.name}: Excel'e aktarım; anlık dosya (200) ya da arka plan işi (202) (K-91)")
    def export_list(body: ExportRequest, user: CurrentUser = Depends(current_user),
                    session: Session = Depends(get_session, scope="function")) -> Response:
        # scope="function": dosya gönderilmeden oturum kapanır, bağlantı havuza döner (docs/08 "Veritabanı oturumu").
        out = export.start(session, defn, user.id, body)
        if "job_id" in out:
            return JSONResponse(out, status_code=202)
        return Response(out["file"], media_type=export.XLSX, headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(out['file_name'])}"})

    # Kayıtlı görünümler (K-89).
    @router.get("/views", summary=f"{defn.name}: görünümler ve kullanıcının varsayılanı")
    def list_views(user: CurrentUser = Depends(current_user), session: Session = Depends(get_session)) -> dict:
        return views.list_views(session, defn, user.id)

    @router.post("/views", status_code=201, summary=f"{defn.name}: yeni görünüm")
    def create_view(body: ViewCreate, user: CurrentUser = Depends(current_user), session: Session = Depends(get_session)) -> dict:
        return views.create(session, defn, user.id, body)

    @router.put("/views/default", summary=f"{defn.name}: varsayılan görünümü seç (boşsa Standart)")
    def default_view(body: DefaultViewRequest, user: CurrentUser = Depends(current_user),
                     session: Session = Depends(get_session)) -> dict:
        return views.set_default(session, defn, user.id, body)

    @router.put("/views/{view_id}", summary=f"{defn.name}: görünümü değiştir (yalnız sahibi)")
    def update_view(view_id: int, body: ViewUpdate, user: CurrentUser = Depends(current_user),
                    session: Session = Depends(get_session)) -> dict:
        return views.update(session, defn, user.id, view_id, body)

    @router.delete("/views/{view_id}", status_code=204, summary=f"{defn.name}: görünümü sil (yalnız sahibi)")
    def delete_view(view_id: int, user: CurrentUser = Depends(current_user), session: Session = Depends(get_session)) -> Response:
        views.delete(session, defn, user.id, view_id)
        return Response(status_code=204)

    return router


routers = [list_router(d) for d in LISTS]
