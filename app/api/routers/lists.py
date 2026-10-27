"""Liste uç noktaları (K-87): her liste tanımı için /<ad>/columns, /<ad>/query, /<ad>/values."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_session
from ..lists import LISTS, ListDefinition
from ..lists.request import QueryRequest, ValuesRequest
from ..services import lists as service


def list_router(defn: ListDefinition) -> APIRouter:
    router = APIRouter(prefix=f"/{defn.name}", tags=["Listeler"])

    @router.get("/columns", summary=f"{defn.table}: kolonlar (etiket, tip, filtre tipi) ve parça büyüklüğü")
    def columns(session: Session = Depends(get_session)) -> dict:
        return service.columns(session, defn)

    @router.post("/query", summary=f"{defn.table}: alanlar, sıralama, filtre, parça ve sayılar")
    def query(body: QueryRequest, session: Session = Depends(get_session)) -> dict:
        return service.query(session, defn, body)

    @router.post("/values", summary=f"{defn.table}: liste filtresinin değerleri ve sayıları")
    def values(body: ValuesRequest, session: Session = Depends(get_session)) -> list[dict]:
        return service.values(session, defn, body)

    return router


routers = [list_router(d) for d in LISTS]
