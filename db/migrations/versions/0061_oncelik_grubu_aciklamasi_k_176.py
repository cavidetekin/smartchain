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


def _set(comment: str) -> None:
    text = comment.replace("'", "''")
    op.execute(f"EXEC sp_updateextendedproperty 'MS_Description', N'{text}', 'schema', 'param', 'table', 'ObjectiveDefinition', 'column', 'PriorityGroup'")


def upgrade():
    _set(metadata.tables['param.ObjectiveDefinition'].c.PriorityGroup.comment)
    if not context.is_offline_mode():
        sync(op.get_bind(), metadata)


def downgrade():
    _set(OLD)
