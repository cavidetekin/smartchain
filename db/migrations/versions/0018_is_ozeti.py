"""0018 · İş özeti ve adlar (K-106, K-107): Job.Summary; kanal "Etkileşim" → "Hesaplama"; yorumlar

Revision ID: 0018
Revises: 0017
Create Date: 2026-11-03
"""
from alembic import op
import sqlalchemy as sa


revision = '0018'
down_revision = '0017'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('Job', sa.Column('Summary', sa.Unicode(length=200), nullable=True, comment='İş özeti; kuyruğa girerken iş türü yazar (K-107)'), schema='adm')
    op.alter_column('Job', 'Channel',
               existing_type=sa.NVARCHAR(length=15, collation='Latin1_General_100_CI_AS_SC'),
               comment='Gece | Hesaplama | Dışa aktarım',
               existing_comment='Gece | Etkileşim | Dışa aktarım',
               existing_nullable=False,
               schema='adm')
    op.alter_column('SystemEvent', 'Resolution',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='Sistem aksiyonu',
               existing_comment='Sistemin yaptığı',
               existing_nullable=True,
               schema='adm')
    # create_table_comment var olan yorumda hata verir (sp_addextendedproperty); güncelleme çağrısı gerekir
    op.execute("EXEC sp_updateextendedproperty 'MS_Description', N'Sistem hataları ve sistem aksiyonu (K-106). Saklama `SystemEventRetentionDays`; motor servisi eskileri siler.', 'schema', 'adm', 'table', 'SystemEvent'")
    op.execute("UPDATE adm.Job SET Channel = N'Hesaplama' WHERE Channel = N'Etkileşim'")


def downgrade():
    op.execute("UPDATE adm.Job SET Channel = N'Etkileşim' WHERE Channel = N'Hesaplama'")
    # create_table_comment var olan yorumda hata verir (sp_addextendedproperty); güncelleme çağrısı gerekir
    op.execute("EXEC sp_updateextendedproperty 'MS_Description', N'Sistem hataları ve sistemin yaptığı (K-106). Saklama `SystemEventRetentionDays`; motor servisi eskileri siler.', 'schema', 'adm', 'table', 'SystemEvent'")
    op.alter_column('SystemEvent', 'Resolution',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='Sistemin yaptığı',
               existing_comment='Sistem aksiyonu',
               existing_nullable=True,
               schema='adm')
    op.alter_column('Job', 'Channel',
               existing_type=sa.NVARCHAR(length=15, collation='Latin1_General_100_CI_AS_SC'),
               comment='Gece | Etkileşim | Dışa aktarım',
               existing_comment='Gece | Hesaplama | Dışa aktarım',
               existing_nullable=False,
               schema='adm')
    op.drop_column('Job', 'Summary', schema='adm')
