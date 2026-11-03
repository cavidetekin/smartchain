"""0014 · Standart etiketler (K-88, K-104): docs/02 ETİKET kolonu var olan sözlüğe yazılır

Şema değişmez; yalnız FieldDefinition.StandardLabel güncellenir, System owner'ın yazdığı Label'a dokunulmaz.

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-03
"""
from alembic import context, op

from dictionary import sync
from models import metadata


revision = '0014'
down_revision = '0013'
branch_labels = None
depends_on = None


def upgrade():
    if not context.is_offline_mode():  # bağlantısız SQL betiğinde satırlar yazılmaz; ilk bağlantılı geçişte kurulur
        sync(op.get_bind(), metadata)


def downgrade():
    pass  # StandardLabel docs'tan gelir; bir sonraki sync yerine yazar
