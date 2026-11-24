"""0061 · Öncelik grubu açıklaması (K-176): yalnız açıklama

Aşama 7 yeniden numaralandı; `param.ObjectiveDefinition.PriorityGroup` açıklamasından adım numarası çıktı (yeniden numaralamada geçiş gerekmesin).
Kolonun açıklaması ve veri sözlüğü satırı modelden (docs/02) güncellenir; veri değişmez.

Revision ID: 0061
Revises: 0060
Create Date: 2026-11-16
"""
from alembic import context, op

from dictionary import sync
from models import metadata

revision = '0061'
down_revision = '0060'
branch_labels = None
depends_on = None

OLD = "Sipariş öncelik grubu; boş = bütün siparişler (gruplar 7.4'te)"
# Bu geçişin yazdığı açıklama sabittir: kolon K-196'da (geçiş 0075) modelden kalktı.
NEW = "Sipariş öncelik grubu; boş = bütün siparişler (gruplar öncelik kuralları adımında)"


def _set(comment: str) -> None:
    text = comment.replace("'", "''")
    # Kolonun açıklaması yoksa eklenir, varsa güncellenir: kolon K-196'da modelden kalktığı için sıfırdan kurulumda 0058 ona açıklama yazmaz
    # (0058 açıklamaları güncel modelden okur); sonuç iki yolda da aynıdır.
    where = "'schema', 'param', 'table', 'ObjectiveDefinition', 'column', 'PriorityGroup'"
    op.execute(f"IF EXISTS (SELECT 1 FROM sys.fn_listextendedproperty('MS_Description', {where})) "
               f"EXEC sp_updateextendedproperty 'MS_Description', N'{text}', {where} "
               f"ELSE EXEC sp_addextendedproperty 'MS_Description', N'{text}', {where}")


def upgrade():
    _set(NEW)
    if not context.is_offline_mode():
        sync(op.get_bind(), metadata)


def downgrade():
    _set(OLD)
