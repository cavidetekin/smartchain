"""0041 · Bildirim kapatma (K-132): Job.DismissedAt; LastPullStatus 40 karakter ("Veri güncellemesi devam ediyor")

Revision ID: 0041
Revises: 0040
Create Date: 2026-11-05 18:21:57.830488
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql
from sqlalchemy.dialects import mssql

revision = '0041'
down_revision = '0040'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('IntegrationEntity', 'LastPullStatus',
               existing_type=sa.NVARCHAR(length=20, collation='Latin1_General_100_CI_AS_SC'),
               type_=sa.Unicode(length=40),
               existing_comment='Son çekim durumu',
               existing_nullable=True,
               schema='adm')
    op.add_column('Job', sa.Column('DismissedAt', mssql.DATETIME2(), nullable=True, comment='Kullanıcı bildirimi kapattı; yeniden çıkmaz (K-132)'), schema='adm')
    op.alter_column('Job', 'Result',
               existing_type=sa.NVARCHAR(collation='Latin1_General_100_CI_AS_SC'),
               comment='İşin sonucu (JSON); Veri çekme: tablo başına durum (K-130)',
               existing_comment='İşin sonucu (JSON); Veri çekme: tablo başına durum',
               existing_nullable=True,
               schema='adm')


def downgrade():
    op.execute("UPDATE adm.IntegrationEntity SET LastPullStatus = N'Yenileme sürüyor' WHERE LEN(LastPullStatus) > 20")
    op.alter_column('Job', 'Result',
               existing_type=sa.NVARCHAR(collation='Latin1_General_100_CI_AS_SC'),
               comment='İşin sonucu (JSON); Veri çekme: tablo başına durum',
               existing_comment='İşin sonucu (JSON); Veri çekme: tablo başına durum (K-130)',
               existing_nullable=True,
               schema='adm')
    op.drop_column('Job', 'DismissedAt', schema='adm')
    op.alter_column('IntegrationEntity', 'LastPullStatus',
               existing_type=sa.Unicode(length=40),
               type_=sa.NVARCHAR(length=20, collation='Latin1_General_100_CI_AS_SC'),
               existing_comment='Son çekim durumu',
               existing_nullable=True,
               schema='adm')
