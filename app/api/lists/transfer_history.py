"""Veri aktarım geçmişi (ekran 02, fonksiyon 08; K-151, K-156): aktarım işleri (Tam / Kısmi), en yeni üstte. Sürümsüzdür.

Kaynak aktarım işleri (`Job`), versiyonu `DataVersion.JobId` ile, sayıları `DataVersionEntity` toplamıyla. Hatayla biten aktarımda versiyon ve
sayılar boştur. Sentetik versiyonların işi yoktur, listede görünmez; versiyonu geri alınmış biten iş (geliştirmede sentetik sıfırlama, K-79) da görünmez. System owner'ın işinde kullanıcı adı yerine "Smartchain" (K-101).
"""
import sqlalchemy as sa

from app.jobs.constants import STATUS_DONE, STATUSES, TYPE_TRANSFER
from db.models import metadata

from ..permissions import SYSTEM_OWNER
from .definition import ListDefinition
from .jobs import SUPPORT_NAME, _text

JOB = metadata.tables["adm.Job"]
USER = metadata.tables["adm.AppUser"]
VERSION = metadata.tables["adm.DataVersion"]
ENTITY = metadata.tables["adm.DataVersionEntity"]
FULL, PARTIAL = "Tam", "Kısmi"
COUNTS = ("NewCount", "ChangedCount", "ClosedCount", "NotTransferredCount")

_sums = sa.select(ENTITY.c.DataVersionId, *[sa.func.sum(ENTITY.c[c]).label(c) for c in COUNTS]).group_by(ENTITY.c.DataVersionId).subquery("dve")
_groups = sa.literal_column("(SELECT STRING_AGG(g.value, N', ') FROM OPENJSON([adm].[Job].[Payload], '$.groups') AS g)", sa.Unicode)
_partial = sa.func.json_value(JOB.c.Payload, "$.mode") == PARTIAL

SOURCE = sa.select(
    JOB.c.Id,
    sa.func.coalesce(JOB.c.StartedAt, JOB.c.CreatedAt).label("StartedAt"),
    sa.case((_partial, _text(PARTIAL)), else_=_text(FULL)).label("TransferType"),
    sa.case((_partial, _groups)).label("Groups"),
    sa.case((USER.c.Role == SYSTEM_OWNER, _text(SUPPORT_NAME)), else_=sa.func.coalesce(USER.c.FullName, USER.c.UserName)).label("RequesterName"),
    sa.cast(VERSION.c.Id, sa.Integer).label("DataVersionId"),
    sa.cast(sa.func.datediff(sa.text("second"), JOB.c.StartedAt, sa.func.isnull(JOB.c.EndedAt, sa.func.sysutcdatetime())), sa.Integer).label("DurationSeconds"),
    JOB.c.Status,
    *[sa.cast(_sums.c[c], sa.Integer).label(c) for c in COUNTS],
    JOB.c.ErrorText,
).select_from(JOB.outerjoin(USER, USER.c.Id == JOB.c.RequestedBy)
              .outerjoin(VERSION, VERSION.c.JobId == JOB.c.Id)
              .outerjoin(_sums, _sums.c.DataVersionId == VERSION.c.Id)).where(JOB.c.JobType == TYPE_TRANSFER, sa.or_(JOB.c.Status != STATUS_DONE, VERSION.c.Id.is_not(None))).subquery("th")

FIELDS = ("StartedAt", "TransferType", "Groups", "RequesterName", "DataVersionId", "DurationSeconds", "Status", *COUNTS, "ErrorText", "Id")
TRANSFER_HISTORY = ListDefinition(
    name="transfer-history",
    table="adm.Job",
    title="Veri aktarım geçmişi",
    file_slug="veri-aktarim-gecmisi",
    function=8,
    versioned=False,
    source=SOURCE,
    key_fields=("Id", "Status"),
    fields=FIELDS,
    default_visible=FIELDS[:-2],
    default_sort=(("StartedAt", "desc"),),
    labels={"StartedAt": "Tarih", "TransferType": "Tür", "Groups": "Gruplar", "RequesterName": "Başlatan", "DataVersionId": "Veri",
            "DurationSeconds": "Süre (sn)", "Status": "Durum", "NewCount": "Yeni", "ChangedCount": "Güncellenen", "ClosedCount": "Silinen",
            "NotTransferredCount": "Aktarılmayan", "ErrorText": "Hata", "Id": "İş no"},
    values={"TransferType": [FULL, PARTIAL], "Status": list(STATUSES)},
    server_values=frozenset({"RequesterName", "Groups"}),
    notes={"NotTransferredCount": "Hatalı satırlar ve validasyonda görünmeyen aktarılmayanlar; ayrıntısı raporun notunda",
           "DurationSeconds": "İşin başlamasından bitişine"},
)
