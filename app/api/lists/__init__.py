"""Liste tanımları (K-87). Her liste /api/<ad>/columns, /query, /values uç noktalarını alır."""
from .definition import ListDefinition
from .materials import MATERIALS
from .users import USERS

LISTS: tuple[ListDefinition, ...] = (MATERIALS, USERS)
