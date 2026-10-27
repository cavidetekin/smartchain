"""Liste sorgusu istek gövdeleri (docs/08, K-87). Yapı burada, anlam (alan, operatör, tip) query.py'de doğrulanır."""
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

MAX_LIMIT = 500


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


class QueryRequest(BaseModel):
    fields: list[str] | None = None
    sort: list[SortItem] = []
    filters: list[FilterItem] = []
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=100, ge=1, le=MAX_LIMIT)


class ValuesRequest(BaseModel):
    field: str
    search: str = ""
    filters: list[FilterItem] = []
