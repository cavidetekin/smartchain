"""Zamanlanmış veri akışları (K-163, geliştirme 5.6): Flow, FlowRun, FlowRunDismissal.

Revision ID: 0050
Revises: 0049
Create Date: 2026-11-11 12:46:31.304438
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql

revision = '0050'
down_revision = '0049'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('Flow',
    sa.Column('Id', sa.Integer(), autoincrement=True, nullable=False, comment='Akış kimliği'),
    sa.Column('Name', sa.Unicode(length=100), nullable=False, comment='Akışın adı'),
    sa.Column('IsActive', sa.Boolean(), server_default=sa.text('1'), nullable=False, comment='Aktif'),
    sa.Column('RunTime', sa.Unicode(length=5), nullable=False, comment='Saat (SS:DD, sunucunun yerel saati)'),
    sa.Column('Days', sa.Unicode(length=20), nullable=False, comment='Haftanın günleri; 1 Pazartesi … 7 Pazar, virgülle'),
    sa.Column('PullScope', sa.Unicode(length=10), nullable=False, comment='Tümü | Seçilen'),
    sa.Column('PullTables', sa.NVARCHAR(), nullable=True, comment='Seçilen SQL tabloları; JSON'),
    sa.Column('TransferMode', sa.Unicode(length=10), nullable=False, comment='Tam | Kısmi'),
    sa.Column('TransferGroups', sa.Unicode(length=200), nullable=True, comment='Kısmi aktarımın grupları; JSON'),
    sa.Column('Cleanup', sa.Boolean(), server_default=sa.text('0'), nullable=False, comment='Ham veri temizliği adımı'),
    sa.Column('UpdatedAt', mssql.DATETIME2(), nullable=False, comment='Son değişiklik zamanı (UTC)'),
    sa.Column('UpdatedBy', sa.Integer(), nullable=False, comment='Değiştiren'),
    sa.ForeignKeyConstraint(['UpdatedBy'], ['adm.AppUser.Id'], name=op.f('FK_Flow_UpdatedBy')),
    sa.PrimaryKeyConstraint('Id', name=op.f('PK_Flow')),
    schema='adm',
    comment='Zamanlanmış veri akışı (K-163): zaman, Veri çek kapsamı, aktarım türü, isteğe bağlı temizlik. Adımların sırası sabittir.'
    )
    op.create_index('UX_Flow_Name', 'Flow', ['Name'], unique=True, schema='adm')
    op.create_table('FlowRun',
    sa.Column('Id', sa.BigInteger(), autoincrement=True, nullable=False, comment='Çalıştırma kimliği'),
    sa.Column('FlowId', sa.Integer(), nullable=False, comment='Akış'),
    sa.Column('FlowName', sa.Unicode(length=100), nullable=False, comment='Çalıştığı andaki adı'),
    sa.Column('TriggerType', sa.Unicode(length=15), nullable=False, comment='Zamanlanmış | Elle'),
    sa.Column('ScheduledAt', mssql.DATETIME2(), nullable=False, comment='Saati (UTC)'),
    sa.Column('StartedAt', mssql.DATETIME2(), nullable=True, comment='Başlama (UTC)'),
    sa.Column('EndedAt', mssql.DATETIME2(), nullable=True, comment='Bitiş (UTC)'),
    sa.Column('State', sa.Unicode(length=15), nullable=False, comment='Bekliyor | Çalışıyor | Bitti | Durdu | Başlamadı'),
    sa.Column('Step', sa.Unicode(length=20), nullable=False, comment='Başlangıç | Veri çekme | Validasyon | Aktarım | Temizlik'),
    sa.Column('Reason', sa.Unicode(length=400), nullable=True, comment='Durma ya da başlamama nedeni; bitende not'),
    sa.Column('Detail', sa.NVARCHAR(), nullable=True, comment='Adım ayrıntısı; JSON (tablo durumları, yeniden çekim)'),
    sa.Column('PullJobId', sa.BigInteger(), nullable=True, comment='Son çekim işi'),
    sa.Column('TransferJobId', sa.BigInteger(), nullable=True, comment='Aktarım işi'),
    sa.Column('CleanupJobId', sa.BigInteger(), nullable=True, comment='Temizlik işi'),
    sa.Column('DataVersionId', sa.BigInteger(), nullable=True, comment='Açılan veri versiyonu'),
    sa.Column('RequestedBy', sa.Integer(), nullable=True, comment='Elle başlatan'),
    sa.ForeignKeyConstraint(['FlowId'], ['adm.Flow.Id'], name=op.f('FK_FlowRun_FlowId')),
    sa.ForeignKeyConstraint(['RequestedBy'], ['adm.AppUser.Id'], name=op.f('FK_FlowRun_RequestedBy')),
    sa.PrimaryKeyConstraint('Id', name=op.f('PK_FlowRun')),
    schema='adm',
    comment='Akışın her çalıştırması (K-163): zaman, adım, durum ve nedeni, işler, veri versiyonu.'
    )
    op.create_index(op.f('IX_FlowRun_FlowId'), 'FlowRun', ['FlowId'], unique=False, schema='adm')
    op.create_table('FlowRunDismissal',
    sa.Column('FlowRunId', sa.BigInteger(), autoincrement=False, nullable=False, comment='Çalıştırma'),
    sa.Column('UserId', sa.Integer(), autoincrement=False, nullable=False, comment='Kullanıcı'),
    sa.Column('DismissedAt', mssql.DATETIME2(), nullable=False, comment='Kapatma zamanı (UTC)'),
    sa.ForeignKeyConstraint(['FlowRunId'], ['adm.FlowRun.Id'], name=op.f('FK_FlowRunDismissal_FlowRunId')),
    sa.ForeignKeyConstraint(['UserId'], ['adm.AppUser.Id'], name=op.f('FK_FlowRunDismissal_UserId')),
    sa.PrimaryKeyConstraint('FlowRunId', 'UserId', name=op.f('PK_FlowRunDismissal')),
    schema='adm',
    comment='Kullanıcının kapattığı akış bildirimi (K-163); kapatılan çip o kullanıcıda yeniden görünmez.'
    )


def downgrade():
    op.drop_table('FlowRunDismissal', schema='adm')
    op.drop_index(op.f('IX_FlowRun_FlowId'), table_name='FlowRun', schema='adm')
    op.drop_table('FlowRun', schema='adm')
    op.drop_index('UX_Flow_Name', table_name='Flow', schema='adm')
    op.drop_table('Flow', schema='adm')
