"""0002 · Job zaman alanları: CreatedAt, StartedAt, EndedAt, UpdatedAt (K-67, K-69)

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    # Zorunlu alanlar önce boş kabul edilir, var olan satırlar doldurulur, sonra zorunlu yapılır.
    op.add_column('Job', sa.Column('CreatedAt', mssql.DATETIME2(), nullable=True, comment='İstek zamanı (UTC); sıra buna göre görünür'), schema='adm')
    op.add_column('Job', sa.Column('StartedAt', mssql.DATETIME2(), nullable=True, comment='Çalışmaya başlama (UTC)'), schema='adm')
    op.add_column('Job', sa.Column('EndedAt', mssql.DATETIME2(), nullable=True, comment='Bitiş, hata ya da iptal (UTC)'), schema='adm')
    op.add_column('Job', sa.Column('UpdatedAt', mssql.DATETIME2(), nullable=True, comment='Son değişiklik (UTC); API bildirim için izler (K-69)'), schema='adm')
    op.execute("UPDATE adm.Job SET CreatedAt = SYSUTCDATETIME(), UpdatedAt = SYSUTCDATETIME()")
    op.alter_column('Job', 'CreatedAt', existing_type=mssql.DATETIME2(), nullable=False, schema='adm')
    op.alter_column('Job', 'UpdatedAt', existing_type=mssql.DATETIME2(), nullable=False, schema='adm')


def downgrade():
    op.drop_column('Job', 'UpdatedAt', schema='adm')
    op.drop_column('Job', 'EndedAt', schema='adm')
    op.drop_column('Job', 'StartedAt', schema='adm')
    op.drop_column('Job', 'CreatedAt', schema='adm')
