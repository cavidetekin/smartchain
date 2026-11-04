"""Sistem sağlığı listeleri (ekran 24; K-106, K-107): iş kuyruğu, son çalışmalar, hatalar. Sürümsüzdür.

System owner'ın işinde kullanıcı adı yerine "Smartchain" yazar (K-101, K-107). Satır işlemi için durum, tür, kanal ve
sahiplik görünmese de her satırda döner (key_fields).
"""
import sqlalchemy as sa

from app.jobs import events
from app.jobs.constants import CHANNELS, JOB_TYPES, STATUS_QUEUED, STATUS_RUNNING, STATUSES
from db.models import metadata

from ..permissions import SYSTEM_OWNER
from .definition import ListDefinition

JOB = metadata.tables["adm.Job"]
USER = metadata.tables["adm.AppUser"]
EVENT = metadata.tables["adm.SystemEvent"]

SUPPORT_NAME = "Smartchain"
STATUS_FIELDS = ("Status", "JobType", "Channel", "RequestedBy", "IsProtected", "Summary", "RequesterName", "QueuePosition")
LABELS = {"Id": "No", "JobType": "Tür", "Summary": "İş", "Channel": "Kanal", "RequesterName": "Kullanıcı", "Status": "Durum", "QueuePosition": "Sıra",
          "Progress": "İlerleme", "DurationSeconds": "Süre (sn)", "Attempt": "Deneme", "CreatedAt": "İstek zamanı",
          "StartedAt": "Başlangıç", "EndedAt": "Bitiş", "ErrorText": "Hata", "CancelReason": "İptal nedeni"}
VALUES = {"JobType": list(JOB_TYPES), "Channel": list(CHANNELS), "Status": list(STATUSES)}


def _text(value: str) -> sa.ColumnElement:
    return sa.literal_column(f"N'{value}'", sa.Unicode)


def _source(where: sa.ColumnElement, alias: str) -> sa.Subquery:
    position = sa.func.row_number().over(partition_by=(JOB.c.Channel, JOB.c.Status),
                                         order_by=(sa.func.isnull(JOB.c.Priority, 0).desc(), JOB.c.Id))
    return sa.select(
        JOB.c.Id, JOB.c.JobType, JOB.c.Summary, JOB.c.Channel, JOB.c.Status, JOB.c.RequestedBy, JOB.c.Progress, JOB.c.Attempt,
        JOB.c.CreatedAt, JOB.c.StartedAt, JOB.c.EndedAt, JOB.c.ErrorText, JOB.c.CancelReason,
        sa.case((USER.c.Role == SYSTEM_OWNER, _text(SUPPORT_NAME)),
                else_=sa.func.coalesce(USER.c.FullName, USER.c.UserName)).label("RequesterName"),
        sa.cast(sa.case((USER.c.Role == SYSTEM_OWNER, 1), else_=0), sa.Boolean).label("IsProtected"),
        sa.case((JOB.c.Status == STATUS_QUEUED, position)).label("QueuePosition"),
        sa.cast(sa.func.datediff(sa.text("second"), JOB.c.StartedAt, sa.func.isnull(JOB.c.EndedAt, sa.func.sysutcdatetime())),
                sa.Integer).label("DurationSeconds"),
    ).select_from(JOB.outerjoin(USER, USER.c.Id == JOB.c.RequestedBy)).where(where).subquery(alias)


def _ended_within(part: str, amount: int) -> sa.ColumnElement:
    return JOB.c.EndedAt >= sa.func.dateadd(sa.text(part), -amount, sa.func.sysutcdatetime())


JOB_QUEUE_FIELDS = ("Id", "JobType", "Summary", "Channel", "RequesterName", "Status", "QueuePosition", "Progress", "DurationSeconds", "Attempt", "CreatedAt")
JOB_QUEUE = ListDefinition(
    name="job-queue",
    table="adm.Job",
    title="İş kuyruğu",
    file_slug="is-kuyrugu",
    function=93,
    versioned=False,
    source=_source(sa.or_(JOB.c.Status.in_((STATUS_QUEUED, STATUS_RUNNING)), _ended_within("hour", 24)), "jq"),
    key_fields=STATUS_FIELDS,
    fields=JOB_QUEUE_FIELDS,
    default_visible=JOB_QUEUE_FIELDS,
    default_sort=(("Id", "desc"),),
    labels=LABELS,
    values=VALUES,
    server_values=frozenset({"RequesterName"}),
)

JOB_RUNS_FIELDS = ("Id", "JobType", "Summary", "Channel", "RequesterName", "Status", "StartedAt", "EndedAt", "DurationSeconds", "Attempt", "ErrorText", "CancelReason")
JOB_RUNS = ListDefinition(
    name="job-runs",
    table="adm.Job",
    title="Son çalışmalar",
    file_slug="son-calismalar",
    function=93,
    versioned=False,
    source=_source(_ended_within("day", 7), "jr"),
    fields=JOB_RUNS_FIELDS,
    default_visible=JOB_RUNS_FIELDS,
    default_sort=(("EndedAt", "desc"),),
    labels={**LABELS, "Status": "Sonuç"},
    values=VALUES,
    server_values=frozenset({"RequesterName"}),
)

EVENT_FIELDS = ("OccurredAt", "Component", "Message", "Resolution", "IsResolved", "JobId", "TraceId")
COMPONENTS = [events.COMPONENT_ENGINE, events.COMPONENT_APP, events.COMPONENT_QUEUE, events.COMPONENT_EXPORT, events.COMPONENT_AUDIT]
SYSTEM_EVENTS = ListDefinition(
    name="system-events",
    table="adm.SystemEvent",
    title="Sistem hataları",
    file_slug="sistem-hatalari",
    function=94,
    versioned=False,
    source=sa.select(EVENT.c.Id, *[EVENT.c[f] for f in EVENT_FIELDS]).subquery("se"),  # Detail yok: yalnız System owner görür (K-106)
    fields=EVENT_FIELDS,
    default_visible=EVENT_FIELDS,
    default_sort=(("OccurredAt", "desc"),),
    labels={"OccurredAt": "Zaman", "Component": "Bileşen", "Message": "Hata", "Resolution": "Sistem aksiyonu", "IsResolved": "Çözüldü",
            "JobId": "İş no", "TraceId": "Takip no"},
    values={"Component": COMPONENTS},
)
