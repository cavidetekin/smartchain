"""0013 · Veri sözlüğü (K-104): FieldDefinition.StandardLabel; core ve param alanları sözlüğe kurulur

Satırlar docs/02'den üretilen modelden gelir (db/dictionary.py). Geri almada etiketi olmayan satırlar silinir.

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-03
"""
from alembic import context, op
import sqlalchemy as sa

from dictionary import sync
from models import metadata


revision = '0013'
down_revision = '0012'
branch_labels = None
depends_on = None

LABEL_OLD = "Ekranda görünen etiket; standart alanın etiketini ezer, ek alanda boşsa alan gösterilmez (K-88)"
LABEL_NEW = LABEL_OLD + "; en çok 40 karakter girilir"


def upgrade():
    op.add_column('FieldDefinition', sa.Column('StandardLabel', sa.Unicode(length=100), nullable=True, comment="docs'tan gelen etiket; kurulumda yazılır, System owner değiştirmez (K-104)"), schema='adm')
    op.alter_column('FieldDefinition', 'Label', existing_type=sa.Unicode(length=100), existing_nullable=True,
                    comment=LABEL_NEW, existing_comment=LABEL_OLD, schema='adm')
    if not context.is_offline_mode():  # bağlantısız SQL betiğinde satırlar yazılmaz; ilk bağlantılı geçişte kurulur
        sync(op.get_bind(), metadata)


def downgrade():
    op.execute("DELETE FROM adm.FieldDefinition WHERE Label IS NULL")
    op.alter_column('FieldDefinition', 'Label', existing_type=sa.Unicode(length=100), existing_nullable=True,
                    comment=LABEL_OLD, existing_comment=LABEL_NEW, schema='adm')
    op.drop_column('FieldDefinition', 'StandardLabel', schema='adm')
