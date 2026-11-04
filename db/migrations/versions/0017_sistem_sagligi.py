"""0017 · Sistem sağlığı (K-106, K-107): SystemEvent, ServiceStatus; Job.CancelReason, Job.CancelledBy

Revision ID: 0017
Revises: 0016
Create Date: 2026-11-03
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql


revision = '0017'
down_revision = '0016'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('ServiceStatus',
    sa.Column('ServiceName', sa.Unicode(length=20), autoincrement=False, nullable=False, comment='Servis'),
    sa.Column('HeartbeatAt', mssql.DATETIME2(), nullable=False, comment='Son kalp atışı (UTC)'),
    sa.Column('StartedAt', mssql.DATETIME2(), nullable=False, comment='Açılış (UTC)'),
    sa.Column('StoppedAt', mssql.DATETIME2(), nullable=True, comment='Düzgün kapanış (UTC); çalışırken boş'),
    sa.Column('AppVersion', sa.Unicode(length=20), nullable=True, comment='Sürüm'),
    sa.PrimaryKeyConstraint('ServiceName', name=op.f('PK_ServiceStatus')),
    schema='adm',
    comment='Motor servisinin kalp atışı (K-106). Durum saklanmaz, okurken hesaplanır.'
    )
    op.create_table('SystemEvent',
    sa.Column('Id', sa.BigInteger(), autoincrement=True, nullable=False, comment='Kayıt kimliği'),
    sa.Column('OccurredAt', mssql.DATETIME2(), nullable=False, comment='Zaman (UTC)'),
    sa.Column('Component', sa.Unicode(length=20), nullable=False, comment='Motor | Uygulama | İş kuyruğu | Dışa aktarım'),
    sa.Column('Message', sa.Unicode(length=500), nullable=False, comment='Hata'),
    sa.Column('Resolution', sa.Unicode(length=200), nullable=True, comment='Sistemin yaptığı'),
    sa.Column('IsResolved', sa.Boolean(), server_default=sa.text('0'), nullable=False, comment='Sistem kendisi çözdü mü'),
    sa.Column('JobId', sa.BigInteger(), nullable=True, comment='İlgili iş; olay işten uzun yaşayabilir, bağ tutulmaz'),
    sa.Column('TraceId', sa.Unicode(length=12), nullable=True, comment='Takip numarası'),
    sa.Column('Detail', sa.Unicode(length=1000), nullable=True, comment='Teknik özet; yalnız System owner görür, yığın izi yazılmaz'),
    sa.PrimaryKeyConstraint('Id', name=op.f('PK_SystemEvent')),
    schema='adm',
    comment='Sistem hataları ve sistemin yaptığı (K-106). Saklama `SystemEventRetentionDays`; motor servisi eskileri siler.'
    )
    op.add_column('Job', sa.Column('CancelReason', sa.Unicode(length=200), nullable=True, comment='İptal nedeni; başkasının işinde zorunlu (K-107)'), schema='adm')
    op.add_column('Job', sa.Column('CancelledBy', sa.Integer(), nullable=True, comment='İptal eden'), schema='adm')
    op.create_foreign_key(op.f('FK_Job_CancelledBy'), 'Job', 'AppUser', ['CancelledBy'], ['Id'], source_schema='adm', referent_schema='adm')


def downgrade():
    op.drop_constraint(op.f('FK_Job_CancelledBy'), 'Job', schema='adm', type_='foreignkey')
    op.drop_column('Job', 'CancelledBy', schema='adm')
    op.drop_column('Job', 'CancelReason', schema='adm')
    op.drop_table('SystemEvent', schema='adm')
    op.drop_table('ServiceStatus', schema='adm')
