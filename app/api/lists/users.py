"""Kullanıcı listesi (adm.AppUser; ekran 22, fonksiyon 88, K-101).

Sürümsüzdür: temiz kurulumda, veri yüklenmeden de açılır. Durum saklanmaz, alt sorguda hesaplanır; böylece sıralama,
filtre, gruplama ve Excel'de kolon gibi çalışır. Şifre özeti gibi alanlar `fields` dışında olduğu için sorulamaz.
"""
import sqlalchemy as sa

from db.models import metadata

from ..permissions import SYSTEM_OWNER
from .definition import ListDefinition

USER = metadata.tables["adm.AppUser"]

ACTIVE, INACTIVE, LOCKED, FIRST_LOGIN = "Aktif", "Pasif", "Kilitli", "İlk giriş bekliyor"
STATUSES = (ACTIVE, INACTIVE, LOCKED, FIRST_LOGIN)


def _text(value: str) -> sa.ColumnElement:
    return sa.literal_column(f"N'{value}'", sa.Unicode)


# Öncelik K-101: Pasif > Kilitli > İlk giriş bekliyor > Aktif. Süresi dolan şifre (sebep "Süre doldu") Aktif sayılır.
STATUS = sa.case(
    (USER.c.IsActive == sa.false(), _text(INACTIVE)),
    (USER.c.LockedUntil > sa.func.sysutcdatetime(), _text(LOCKED)),
    (sa.and_(USER.c.MustChangePassword == sa.true(),
             sa.or_(USER.c.PasswordChangeReason.is_(None), USER.c.PasswordChangeReason.in_(["İlk giriş", "Sıfırlama"]))),
     _text(FIRST_LOGIN)),
    else_=_text(ACTIVE),
).label("Status")

SOURCE = sa.select(USER.c.Id, USER.c.FullName, USER.c.UserName, USER.c.Role, STATUS, USER.c.LastLoginAt).subquery("u")


def _visible_to(role: str | None) -> sa.ColumnElement | None:
    """System owner hesapları yalnız System owner'a görünür (K-101); rol bilinmiyorsa en dar kapsam."""
    return None if role == SYSTEM_OWNER else SOURCE.c.Role != SYSTEM_OWNER


USERS = ListDefinition(
    name="users",
    table="adm.AppUser",
    title="Kullanıcı listesi",
    file_slug="kullanici",
    function=88,  # Kullanıcı yönetimi (K-100)
    versioned=False,
    source=SOURCE,
    row_scope=_visible_to,
    fields=("FullName", "UserName", "Role", "Status", "LastLoginAt"),
    default_visible=("FullName", "UserName", "Role", "Status", "LastLoginAt"),
    default_sort=(("FullName", "asc"),),
    labels={"FullName": "Ad soyad", "UserName": "Kullanıcı adı", "Role": "Rol", "Status": "Durum", "LastLoginAt": "Son giriş"},
    # Rol değerleri sunucudan: row_scope'la süzülür, Admin'in filtresinde System owner çıkmaz.
    server_values=frozenset({"Role"}),
    values={"Status": list(STATUSES)},
)
