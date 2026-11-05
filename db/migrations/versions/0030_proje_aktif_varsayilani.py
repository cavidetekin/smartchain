"""0030 · Project.IsActive varsayılanı kalkar (K-119); boşsa veri kuralıyla doldurulur, mevcut değerler olduğu gibi kalır

Revision ID: 0030
Revises: 0029
Create Date: 2026-11-05
"""
from alembic import op
import sqlalchemy as sa


revision = '0030'
down_revision = '0029'
branch_labels = None
depends_on = None

FD = 'adm.FieldDefinition'


def upgrade():
    op.alter_column('Project', 'IsActive', existing_type=sa.Boolean(), server_default=None, existing_comment='Aktif mi', existing_nullable=True, schema='core')
    op.execute(f"UPDATE {FD} SET DefaultValue = NULL WHERE TableName = N'Project' AND FieldName = N'IsActive'")


def downgrade():
    op.execute(f"UPDATE {FD} SET DefaultValue = N'1' WHERE TableName = N'Project' AND FieldName = N'IsActive'")
    op.alter_column('Project', 'IsActive', existing_type=sa.Boolean(), server_default=sa.text('1'), existing_comment='Aktif mi', existing_nullable=True, schema='core')
