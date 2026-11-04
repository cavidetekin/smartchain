"""0019 · Denetim izi (K-108): AuditLog.At ve ObjectKey indeksi; SystemEvent bileşeni

Revision ID: 0019
Revises: 0018
Create Date: 2026-11-04
"""
from alembic import op
import sqlalchemy as sa


revision = '0019'
down_revision = '0018'
branch_labels = None
depends_on = None


def _table_comment(text):
    op.execute(f"EXEC sp_updateextendedproperty 'MS_Description', N'{text}', 'schema', 'adm', 'table', 'AuditLog'")


def upgrade():
    op.create_index(op.f('IX_AuditLog_At'), 'AuditLog', ['At'], unique=False, schema='adm')
    op.create_index(op.f('IX_AuditLog_ObjectKey'), 'AuditLog', ['ObjectKey'], unique=False, schema='adm')
    op.alter_column('SystemEvent', 'Component',
               existing_type=sa.NVARCHAR(length=20, collation='Latin1_General_100_CI_AS_SC'),
               comment='Motor | Uygulama | İş kuyruğu | Dışa aktarım | Denetim izi',
               existing_comment='Motor | Uygulama | İş kuyruğu | Dışa aktarım',
               existing_nullable=False,
               schema='adm')
    _table_comment('Kim, ne zaman, neyi değiştirdi; giriş kayıtları; kayıtlar silinemez (K-109).')


def downgrade():
    _table_comment('Kim, ne zaman, neyi değiştirdi; giriş kayıtları; System owner işlemleri silinemez.')
    op.alter_column('SystemEvent', 'Component',
               existing_type=sa.NVARCHAR(length=20, collation='Latin1_General_100_CI_AS_SC'),
               comment='Motor | Uygulama | İş kuyruğu | Dışa aktarım',
               existing_comment='Motor | Uygulama | İş kuyruğu | Dışa aktarım | Denetim izi',
               existing_nullable=False,
               schema='adm')
    op.drop_index(op.f('IX_AuditLog_ObjectKey'), table_name='AuditLog', schema='adm')
    op.drop_index(op.f('IX_AuditLog_At'), table_name='AuditLog', schema='adm')
