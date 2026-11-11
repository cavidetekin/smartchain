"""Akış geçmişi (ekran 23, fonksiyon 92; K-163): her çalıştırma, en yeni üstte. Arayüz akışı sabit filtreyle verir (FlowId)."""
import sqlalchemy as sa

from app.flows.runner import STATES, STEPS, MANUAL, SCHEDULED
from db.models import metadata

from .definition import ListDefinition

RUN = metadata.tables["adm.FlowRun"]
USER = metadata.tables["adm.AppUser"]

SOURCE = sa.select(
    RUN.c.Id,
    RUN.c.FlowId,
    RUN.c.FlowName,
    RUN.c.TriggerType,
    RUN.c.ScheduledAt,
    RUN.c.StartedAt,
    RUN.c.EndedAt,
    RUN.c.State,
    RUN.c.Step,
    RUN.c.Reason,
    sa.cast(RUN.c.DataVersionId, sa.Integer).label("DataVersionId"),
    sa.cast(RUN.c.TransferJobId, sa.Integer).label("TransferJobId"),
    sa.func.coalesce(USER.c.FullName, USER.c.UserName).label("RequesterName"),
).select_from(RUN.outerjoin(USER, USER.c.Id == RUN.c.RequestedBy)).subquery("fr")

FIELDS = ("ScheduledAt", "FlowName", "TriggerType", "StartedAt", "EndedAt", "State", "Step", "Reason", "DataVersionId", "RequesterName", "TransferJobId", "Id", "FlowId")
FLOW_RUNS = ListDefinition(
    name="flow-runs",
    table="adm.FlowRun",
    title="Akış geçmişi",
    file_slug="akis-gecmisi",
    function=92,
    versioned=False,
    source=SOURCE,
    key_fields=("Id", "State", "TransferJobId"),
    fields=FIELDS,
    default_visible=FIELDS[:9],
    default_sort=(("Id", "desc"),),
    labels={"ScheduledAt": "Saati", "FlowName": "Akış", "TriggerType": "Tetik", "StartedAt": "Başlama", "EndedAt": "Bitiş", "State": "Durum",
            "Step": "Adım", "Reason": "Neden", "DataVersionId": "Veri", "RequesterName": "Elle başlatan", "TransferJobId": "Aktarım işi",
            "Id": "Çalıştırma", "FlowId": "Akış no"},
    values={"TriggerType": [SCHEDULED, MANUAL], "State": list(STATES), "Step": list(STEPS)},
    server_values=frozenset({"FlowName", "RequesterName"}),
    filter_only=("FlowId",),
    notes={"Step": "Durduğu ya da bittiği adım", "DataVersionId": "Akışın açtığı veri versiyonu"},
)
