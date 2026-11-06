"""Liste tanımları (K-87). Her liste /api/<ad>/columns, /query, /values uç noktalarını alır."""
from .audit_log import AUDIT_LOG
from .data_entities import DATA_ENTITIES, INTEGRATION_ENTITIES
from .definition import ListDefinition
from .field_definitions import FIELD_DEFINITIONS
from .import_findings import IMPORT_FINDINGS
from .jobs import JOB_QUEUE, JOB_RUNS, SYSTEM_EVENTS
from .materials import MATERIALS
from .users import USERS

LISTS: tuple[ListDefinition, ...] = (INTEGRATION_ENTITIES, MATERIALS, USERS, FIELD_DEFINITIONS, JOB_QUEUE, JOB_RUNS, SYSTEM_EVENTS, AUDIT_LOG, DATA_ENTITIES, IMPORT_FINDINGS)
