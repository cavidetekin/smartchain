"""0020 · Lokasyon bayrakları (K-111): IsFactory, IsDepot, IsSubcontractor, IsActive; Name zorunlu değil

Var olan kayıtlarda bayraklar varsayılanını alır; Type'tan doldurulmaz, ikisi arasında ürün içinde bağ yoktur. Type'a dokunulmaz.

Revision ID: 0020
Revises: 0019
Create Date: 2026-11-04
"""
from alembic import context, op
import sqlalchemy as sa

from dictionary import sync
from models import metadata


revision = '0020'
down_revision = '0019'
branch_labels = None
depends_on = None

NAME_TYPE = sa.NVARCHAR(length=100, collation='Latin1_General_100_CI_AS_SC')
FLAGS = (
    ('IsFactory', 'Tesis mi', '0'),
    ('IsDepot', 'Depo mu', '0'),
    ('IsSubcontractor', 'Fason deposu mu', '0'),
    ('IsActive', 'Aktif mi', '1'),
)


def upgrade():
    for name, comment, default in FLAGS:
        op.add_column('Location', sa.Column(name, sa.Boolean(), server_default=sa.text(default), nullable=False, comment=comment), schema='core')
        op.add_column('Location', sa.Column(name, sa.Boolean(), nullable=True, comment=comment), schema='stg')
    op.alter_column('Location', 'Name', existing_type=NAME_TYPE, nullable=True, existing_comment='Lokasyon adı', schema='core')
    # Sözlük: sync IsRequired'a dokunmaz; bu değişiklik burada yazılır.
    op.execute("UPDATE adm.FieldDefinition SET IsRequired = 0 WHERE TableName = N'Location' AND FieldName = N'Name'")
    if not context.is_offline_mode():  # bağlantısız SQL betiğinde satırlar yazılmaz; ilk bağlantılı geçişte kurulur
        sync(op.get_bind(), metadata)


def downgrade():
    op.execute("DELETE FROM adm.FieldDefinition WHERE TableName = N'Location' "
               "AND FieldName IN (N'IsFactory', N'IsDepot', N'IsSubcontractor', N'IsActive')")
    op.execute("UPDATE adm.FieldDefinition SET IsRequired = 1 WHERE TableName = N'Location' AND FieldName = N'Name'")
    op.execute("UPDATE core.Location SET Name = Code WHERE Name IS NULL")
    op.alter_column('Location', 'Name', existing_type=NAME_TYPE, nullable=False, existing_comment='Lokasyon adı', schema='core')
    for name, _, _ in reversed(FLAGS):
        op.drop_column('Location', name, schema='stg')
        op.drop_column('Location', name, schema='core', mssql_drop_default=True)
