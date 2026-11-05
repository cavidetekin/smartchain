"""0039 · Stok tutulamaz malzeme (K-113 eki, A-44): Material.IsNonStockable

ERP'de varsa oradan gelir, yoksa veri kuralıyla dolar; varsayılan yok. Var olan satırlar boş kalır, doldurulmaz.
Geri alışta kolon, değerleri ve sözlük satırı kaybolur.

Revision ID: 0039
Revises: 0038
Create Date: 2026-11-05 13:15:30.410687
"""
from alembic import context, op
import sqlalchemy as sa

from dictionary import sync
from models import metadata


revision = '0039'
down_revision = '0038'
branch_labels = None
depends_on = None

COMMENT = 'Stok tutulamaz; üretilen ya da teslim alınan miktar beklemeden tüketilir, dönem sonu stoğu sıfırdır'
SCHEMAS = ('core', 'stg')


def upgrade():
    for schema in SCHEMAS:
        op.add_column('Material', sa.Column('IsNonStockable', sa.Boolean(), nullable=True, comment=COMMENT), schema=schema)
    if not context.is_offline_mode():  # bağlantısız SQL betiğinde satırlar yazılmaz; ilk bağlantılı geçişte kurulur
        sync(op.get_bind(), metadata)


def downgrade():
    op.execute("DELETE FROM adm.FieldDefinition WHERE TableName = N'Material' AND FieldName = N'IsNonStockable'")
    for schema in SCHEMAS:
        op.drop_column('Material', 'IsNonStockable', schema=schema)
