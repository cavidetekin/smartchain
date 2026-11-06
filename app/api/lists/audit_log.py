"""Denetim izi listesi (adm.AuditLog; ekran 26, fonksiyon 98, K-108). Sürümsüzdür.

System owner kayıtlarında kimlik gizlidir (K-101): kullanıcı "Smartchain", nesnesi System owner hesabıysa "Smartchain hesabı" ve
değerler boş. Liste ve Excel herkes için böyledir; ham alanlar (Raw*, RealActor) `fields` dışında olduğu için sorulamaz, yalnız
detay servisi okur. Key user yalnız kendi kayıtlarını görür (row_scope).
"""
import sqlalchemy as sa

from db.models import metadata

from ..audit_format import SETTING_LABELS, readable
from ..permissions import ADMIN, SYSTEM_OWNER
from .definition import ListDefinition

AUDIT = metadata.tables["adm.AuditLog"]
USER = metadata.tables["adm.AppUser"]

SUPPORT_NAME = "Smartchain"
SUPPORT_ACCOUNT = "Smartchain hesabı"
SYSTEM_NAME = "Sistem"
EXPORT_ACTION = "Dışa aktarım"
EXPORT_TYPE = "Dışa aktarım"
SETTING_TYPE = "SystemSetting"
OBJECT_TYPE_LABELS = {"Fonksiyon": "Yetki", "FieldDefinition": "Veri sözlüğü", SETTING_TYPE: "Ayar", "Job": "İş", "TableView": "Görünüm", "Template": "Şablon", "IntegrationEntity": "Entegrasyon", "ImportBatch": "Excel yükleme", "ValidationRule": "Validasyon kuralı"}


def _text(value: str) -> sa.ColumnElement:
    return sa.literal_column("N'" + value.replace("'", "''") + "'", sa.Unicode)


_is_owner = USER.c.Role == SYSTEM_OWNER
_about_owner = sa.and_(AUDIT.c.ObjectType == "Kullanıcı",
                       AUDIT.c.ObjectKey.in_(sa.select(USER.c.UserName).where(_is_owner).scalar_subquery()))
_type_whens = [(AUDIT.c.Action == EXPORT_ACTION, _text(EXPORT_TYPE))] + [
    (AUDIT.c.ObjectType == raw, _text(label)) for raw, label in OBJECT_TYPE_LABELS.items()]
_setting_name = sa.case({key: _text(label) for key, label in SETTING_LABELS.items()}, value=AUDIT.c.ObjectKey, else_=AUDIT.c.ObjectKey)
_masked = lambda col: sa.case((_about_owner, sa.null()), else_=col)  # noqa: E731

SOURCE = sa.select(
    AUDIT.c.Id, AUDIT.c.At, AUDIT.c.Action, AUDIT.c.UserId,
    sa.case((AUDIT.c.UserId.is_(None), _text(SYSTEM_NAME)), (_is_owner, _text(SUPPORT_NAME)),
            else_=sa.func.coalesce(USER.c.FullName, USER.c.UserName)).label("ActorName"),
    sa.case(*_type_whens, else_=AUDIT.c.ObjectType).label("ObjectTypeLabel"),
    sa.case((_about_owner, _text(SUPPORT_ACCOUNT)), (AUDIT.c.ObjectType == SETTING_TYPE, _setting_name), else_=AUDIT.c.ObjectKey).label("ObjectShown"),
    _masked(AUDIT.c.OldValue).label("OldText"),
    _masked(AUDIT.c.NewValue).label("NewText"),
    _masked(AUDIT.c.OldValue).label("OldValue"),
    _masked(AUDIT.c.NewValue).label("NewValue"),
    # Yalnız detay servisi okur
    AUDIT.c.ObjectType.label("RawType"), AUDIT.c.ObjectKey.label("RawKey"),
    AUDIT.c.OldValue.label("RawOld"), AUDIT.c.NewValue.label("RawNew"),
    sa.func.coalesce(USER.c.FullName, USER.c.UserName).label("RealActor"),
).select_from(AUDIT.outerjoin(USER, USER.c.Id == AUDIT.c.UserId)).subquery("al")

FIELDS = ("At", "ActorName", "Action", "ObjectTypeLabel", "ObjectShown", "OldText", "NewText", "OldValue", "NewValue")


def visible_to(role: str | None, user_id: int | None = None) -> sa.ColumnElement | None:
    """Admin ve System owner tümü; Key user yalnız kendi kayıtları (fonksiyon 98 "kendi"); bilinmiyorsa hiçbiri."""
    if role in (SYSTEM_OWNER, ADMIN):
        return None
    return SOURCE.c.UserId == user_id if user_id is not None else sa.false()


AUDIT_LOG = ListDefinition(
    name="audit-log",
    table="adm.AuditLog",
    title="Denetim izi",
    file_slug="denetim-izi",
    function=98,
    versioned=False,
    source=SOURCE,
    row_scope=visible_to,
    fields=FIELDS,
    default_visible=tuple(f for f in FIELDS if f not in ("OldValue", "NewValue")),
    default_sort=(("At", "desc"),),
    labels={"At": "Zaman", "ActorName": "Kullanıcı", "Action": "İşlem", "ObjectTypeLabel": "Nesne tipi", "ObjectShown": "Nesne",
            "OldText": "Eski değer", "NewText": "Yeni değer", "OldValue": "Eski değer (ham)", "NewValue": "Yeni değer (ham)"},
    server_values=frozenset({"ActorName", "Action", "ObjectTypeLabel"}),
    value_format={"OldText": readable, "NewText": readable},
)
