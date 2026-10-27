"""Liste sorgusu istek gövdeleri (docs/08, K-87). Yapı burada, anlam (alan, operatör, tip) query.py'de doğrulanır."""
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

MAX_LIMIT = 500             # ListChunkSize'ın üst sınırı (docs/02)
DEFAULT_CHUNK_SIZE = 100
DEFAULT_MAX_GROUPS = 1000  # ListMaxGroups (K-90)


class SortItem(BaseModel):
    field: str
    dir: Literal["asc", "desc"] = "asc"


class FilterItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    field: str
    op: str
    value: Any = None
    values: list[Any] | None = None
    min: float | None = None
    max: float | None = None
    from_: date | None = Field(default=None, alias="from")
    to: date | None = None
    empty: bool = False      # liste filtresinde: değerler ya da boş (U-13)


class GroupKeyItem(BaseModel):
    """Grubun satırları (K-90): alan = değer; değer null ise boş grup."""
    field: str
    value: Any = None


class QueryRequest(BaseModel):
    fields: list[str] | None = None
    sort: list[SortItem] = []
    filters: list[FilterItem] = []
    offset: int = Field(default=0, ge=0)
    limit: int | None = Field(default=None, ge=1, le=MAX_LIMIT)  # boşsa ListChunkSize
    group_key: list[GroupKeyItem] = []


class GroupsRequest(BaseModel):
    group_by: list[str] = Field(min_length=1, max_length=4)
    fields: list[str] | None = None  # ara toplam yalnız bu (görünen) kolonlar için; boşsa bütün toplanabilenler
    filters: list[FilterItem] = []
    sort: list[SortItem] = []


class ValuesRequest(BaseModel):
    field: str
    search: str = ""
    filters: list[FilterItem] = []


# --- Kayıtlı görünüm (K-89, docs/08 "Görünümler") ---------------------------------------------------------------

MIN_WIDTH_REM, MAX_WIDTH_REM = 4.0, 60.0


class ViewColumn(BaseModel):
    field: str
    width: float | None = Field(default=None, ge=MIN_WIDTH_REM, le=MAX_WIDTH_REM)  # rem; boşsa tipin varsayılanı


class ViewDefinition(BaseModel):
    """Görünüm içeriği, sürüm 1. Göreli tarih filtresi göreli saklanır (op relative), tarih değil."""
    v: Literal[1] = 1
    columns: list[ViewColumn] = Field(min_length=1)
    pinned: int = Field(default=0, ge=0)
    sort: list[SortItem] = []
    filters: list[FilterItem] = []
    group_by: list[str] = Field(default=[], max_length=4)


class ViewCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    is_shared: bool = False
    definition: ViewDefinition


class ViewUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    is_shared: bool | None = None
    definition: ViewDefinition | None = None


class DefaultViewRequest(BaseModel):
    view_id: int | None = None
