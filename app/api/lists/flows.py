"""Zamanlanmış işler listesi (ekran 25 · Zamanlanmış işler sekmesi, fonksiyon 92; K-163, K-164). Sürümsüzdür.

Zaman "Hafta içi 02:00" gibi okunur (günler SQL'de çevrilir); sıradaki saat `Flow.NextRunAt` (zamanlayıcı günceller); son çalışma her işin en son
çalıştırmasıdır (durum, zaman, neden).
"""
import sqlalchemy as sa

from app.flows.runner import MODE_PARTIAL, SCOPE_ALL, STATES
from db.models import metadata

from .definition import ListDefinition

FLOW = metadata.tables["adm.Flow"]
RUN = metadata.tables["adm.FlowRun"]
SHORT = {"1": "Pzt", "2": "Sal", "3": "Çar", "4": "Per", "5": "Cum", "6": "Cmt", "7": "Paz"}


def _text(value: str) -> sa.ColumnElement:
    return sa.literal_column(f"N'{value}'", sa.Unicode)


def _days() -> sa.ColumnElement:
    """"1,2,3,4,5" → "Hafta içi"; öteki seçimler kısa adlarla ("Pzt, Çar"); schedule.days_text ile aynı."""
    named = FLOW.c.Days
    for digit, name in SHORT.items():
        named = sa.func.replace(named, digit, name)
    return sa.case((FLOW.c.Days == "1,2,3,4,5,6,7", _text("Her gün")), (FLOW.c.Days == "1,2,3,4,5", _text("Hafta içi")),
                   (FLOW.c.Days == "6,7", _text("Hafta sonu")), else_=sa.func.replace(named, ",", ", "))


def _last(column) -> sa.ColumnElement:
    """En son çalıştırmanın alanı (MS SQL'de LATERAL yok: ilişkili alt sorgu)."""
    return sa.select(column).where(RUN.c.FlowId == FLOW.c.Id).order_by(RUN.c.Id.desc()).limit(1).correlate(FLOW).scalar_subquery()


_tables = sa.literal_column("(SELECT COUNT(*) FROM OPENJSON([adm].[Flow].[PullTables]))", sa.Integer)
_groups = sa.literal_column("(SELECT STRING_AGG(g.value, N', ') FROM OPENJSON([adm].[Flow].[TransferGroups]) AS g)", sa.Unicode)

SOURCE = sa.select(
    FLOW.c.Id,
    FLOW.c.Name,
    (_days() + _text(" ") + FLOW.c.RunTime).label("Schedule"),
    sa.case((FLOW.c.PullScope == SCOPE_ALL, _text("Bütün tablolar")), else_=sa.func.concat(_tables, _text(" tablo"))).label("PullText"),
    sa.case((FLOW.c.TransferMode == MODE_PARTIAL, sa.func.concat(_text("Kısmi · "), _groups)), else_=_text("Tam")).label("TransferText"),
    FLOW.c.Cleanup,
    FLOW.c.NextRunAt,
    _last(RUN.c.State).label("LastState"),
    _last(sa.func.coalesce(RUN.c.EndedAt, RUN.c.StartedAt, RUN.c.ScheduledAt)).label("LastAt"),
    _last(RUN.c.Reason).label("LastReason"),
    FLOW.c.IsActive,
    FLOW.c.RunTime,
).select_from(FLOW).subquery("fl")

FIELDS = ("Name", "Schedule", "PullText", "TransferText", "Cleanup", "NextRunAt", "LastState", "LastAt", "LastReason", "IsActive", "RunTime", "Id")
FLOWS = ListDefinition(
    name="flows",
    table="adm.Flow",
    title="Zamanlanmış işler",
    file_slug="zamanlanmis-isler",
    function=92,
    versioned=False,
    source=SOURCE,
    key_fields=("Id", "LastState", "LastAt", "LastReason"),
    fields=FIELDS,
    default_visible=("Name", "Schedule", "PullText", "TransferText", "Cleanup", "NextRunAt", "LastState", "IsActive"),
    default_sort=(("RunTime", "asc"),),
    labels={"Name": "Zamanlanmış iş", "Schedule": "Zaman", "PullText": "Veri çekimi", "TransferText": "Veri aktarımı", "Cleanup": "Temizlik",
            "NextRunAt": "Sıradaki", "LastState": "Son çalışma", "LastAt": "Son çalışma zamanı", "LastReason": "Son çalışmanın nedeni", "IsActive": "Aktif",
            "RunTime": "Saat", "Id": "No"},
    values={"LastState": list(STATES)},
    server_values=frozenset({"Schedule", "PullText", "TransferText"}),
    notes={"NextRunAt": "Sunucunun yerel saatiyle; pasif işte boş", "LastState": "En son çalıştırmanın durumu; ipucunda neden"},
)
