"""Zamanlanmış iş geçmişi (ekran 25 · Zamanlanmış işler sekmesi, fonksiyon 92; K-163, K-164): her çalıştırma, en yeni üstte. Arayüz zamanlanmış işi sabit filtreyle verir (FlowId)."""
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
    sa.case((USER.c.Id.is_(None), RUN.c.TriggerType), else_=RUN.c.TriggerType + sa.literal_column("N' · '", sa.Unicode) + sa.func.coalesce(USER.c.UserName, "")).label("TriggerText"),
).select_from(RUN.outerjoin(USER, USER.c.Id == RUN.c.RequestedBy)).subquery("fr")

FIELDS = ("StartedAt", "EndedAt", "TriggerText", "State", "Step", "Reason", "DataVersionId", "ScheduledAt", "FlowName", "TriggerType", "RequesterName", "TransferJobId", "Id", "FlowId")
FLOW_RUNS = ListDefinition(
    name="flow-runs",
    table="adm.FlowRun",
    title="Zamanlanmış iş geçmişi",
    file_slug="zamanlanmis-is-gecmisi",
    function=92,
    versioned=False,
    source=SOURCE,
    key_fields=("Id", "State", "TransferJobId"),
    fields=FIELDS,
    default_visible=FIELDS[:7],
    default_sort=(("Id", "desc"),),
    labels={"ScheduledAt": "Saati", "FlowName": "Zamanlanmış iş", "TriggerType": "Tetik türü", "TriggerText": "Tetik", "StartedAt": "Başlama", "EndedAt": "Bitiş", "State": "Durum",
            "Step": "Adım", "Reason": "Neden", "DataVersionId": "Veri", "RequesterName": "Elle başlatan", "TransferJobId": "Aktarım işi",
            "Id": "Çalıştırma", "FlowId": "Zamanlanmış iş no"},
    values={"TriggerType": [SCHEDULED, MANUAL], "State": list(STATES), "Step": list(STEPS)},
    server_values=frozenset({"FlowName", "RequesterName", "TriggerText"}),
    filter_only=("FlowId",),
    notes={"TriggerText": "Elle başlatılanda başlatanın kullanıcı adı", "Step": "Durduğu ya da bittiği adım", "DataVersionId": "Zamanlanmış işin açtığı veri versiyonu"},
)
