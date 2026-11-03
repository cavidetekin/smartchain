"""0015 · Alan açıklaması (K-104): FieldDefinition.Description; docs/02 AÇIKLAMA'dan yazılır

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-03
"""
from alembic import context, op
import sqlalchemy as sa

from dictionary import sync
from models import metadata


revision = '0015'
down_revision = '0014'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('FieldDefinition', sa.Column('Description', sa.Unicode(length=200), nullable=True,
                                               comment="Alan açıklaması; docs/02 AÇIKLAMA'dan, geçişte güncellenir, System owner değiştirmez (K-104)"),
                  schema='adm')
    if not context.is_offline_mode():  # bağlantısız SQL betiğinde satırlar yazılmaz; ilk bağlantılı geçişte kurulur
        sync(op.get_bind(), metadata)


def downgrade():
    op.drop_column('FieldDefinition', 'Description', schema='adm')
