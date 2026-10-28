"""0009 · Dışa aktarım kanalı (K-93)

adm.Job.Channel 10 → 15 karakter ("Dışa aktarım" kanalı); Channel ve JobType açıklamalarına "Dışa aktarım" eklenir.
Yalnız uzatma; veri kaybı yok.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-28
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql


revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('Job', 'JobType',
               existing_type=sa.NVARCHAR(length=20, collation='Latin1_General_100_CI_AS_SC'),
               comment='Gece senaryosu | Çalışma | Yükleme | Termin sorgusu | Dışa aktarım …',
               existing_comment='Gece senaryosu | Çalışma | Yükleme | Termin sorgusu …',
               existing_nullable=False,
               schema='adm')
    op.alter_column('Job', 'Channel',
               existing_type=sa.NVARCHAR(length=10, collation='Latin1_General_100_CI_AS_SC'),
               type_=sa.Unicode(length=15),
               comment='Gece | Etkileşim | Dışa aktarım',
               existing_comment='Gece | Etkileşim',
               existing_nullable=False,
               schema='adm')


def downgrade():
    op.alter_column('Job', 'Channel',
               existing_type=sa.Unicode(length=15),
               type_=sa.NVARCHAR(length=10, collation='Latin1_General_100_CI_AS_SC'),
               comment='Gece | Etkileşim',
               existing_comment='Gece | Etkileşim | Dışa aktarım',
               existing_nullable=False,
               schema='adm')
    op.alter_column('Job', 'JobType',
               existing_type=sa.NVARCHAR(length=20, collation='Latin1_General_100_CI_AS_SC'),
               comment='Gece senaryosu | Çalışma | Yükleme | Termin sorgusu …',
               existing_comment='Gece senaryosu | Çalışma | Yükleme | Termin sorgusu | Dışa aktarım …',
               existing_nullable=False,
               schema='adm')
