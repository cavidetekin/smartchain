"""Zamanlanmış işin sıradaki saati (K-164): Flow.NextRunAt; tablo ve alan açıklamalarında "akış" yerine "zamanlanmış iş".

Revision ID: 0051
Revises: 0050
Create Date: 2026-11-11 15:01:28.760555
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql

revision = '0051'
down_revision = '0050'
branch_labels = None
depends_on = None


def _table_comment(schema, table, text):
    """MS SQL'de var olan tablo açıklaması güncellenir (create_table_comment eklemeye çalışır)."""
    text = text.replace("'", "''")
    op.execute(f"EXEC sp_updateextendedproperty 'MS_Description', N'{text}', 'schema', '{schema}', 'table', '{table}'")


def upgrade():
    op.add_column('Flow', sa.Column('NextRunAt', mssql.DATETIME2(), nullable=True, comment='Sıradaki saat (UTC); kaydederken ve zamanlayıcının her turunda hesaplanır, pasifte boş (K-164)'), schema='adm')
    op.alter_column('Flow', 'Id',
               existing_type=sa.INTEGER(),
               comment='Zamanlanmış iş kimliği',
               existing_comment='Akış kimliği',
               existing_nullable=False,
               autoincrement=True,
               existing_server_default=sa.Identity(always=False, start=1, increment=1),
               schema='adm')
    op.alter_column('Flow', 'Name',
               existing_type=sa.NVARCHAR(length=100, collation='Latin1_General_100_CI_AS_SC'),
               comment='Zamanlanmış işin adı',
               existing_comment='Akışın adı',
               existing_nullable=False,
               schema='adm')
    _table_comment('adm', 'Flow', 'Zamanlanmış iş (K-163, K-164): zaman, Veri çek kapsamı, aktarım türü, isteğe bağlı temizlik. Adımların sırası sabittir.')
    op.alter_column('FlowRun', 'FlowId',
               existing_type=sa.INTEGER(),
               comment='Zamanlanmış iş',
               existing_comment='Akış',
               existing_nullable=False,
               schema='adm')
    _table_comment('adm', 'FlowRun', 'Zamanlanmış işin her çalıştırması (K-163): zaman, adım, durum ve nedeni, işler, veri versiyonu.')
    _table_comment('adm', 'FlowRunDismissal', 'Kullanıcının kapattığı zamanlanmış iş bildirimi (K-163); kapatılan çip o kullanıcıda yeniden görünmez.')


def downgrade():
    _table_comment('adm', 'FlowRunDismissal', 'Kullanıcının kapattığı akış bildirimi (K-163); kapatılan çip o kullanıcıda yeniden görünmez.')
    _table_comment('adm', 'FlowRun', 'Akışın her çalıştırması (K-163): zaman, adım, durum ve nedeni, işler, veri versiyonu.')
    op.alter_column('FlowRun', 'FlowId',
               existing_type=sa.INTEGER(),
               comment='Akış',
               existing_comment='Zamanlanmış iş',
               existing_nullable=False,
               schema='adm')
    _table_comment('adm', 'Flow', 'Zamanlanmış veri akışı (K-163): zaman, Veri çek kapsamı, aktarım türü, isteğe bağlı temizlik. Adımların sırası sabittir.')
    op.alter_column('Flow', 'Name',
               existing_type=sa.NVARCHAR(length=100, collation='Latin1_General_100_CI_AS_SC'),
               comment='Akışın adı',
               existing_comment='Zamanlanmış işin adı',
               existing_nullable=False,
               schema='adm')
    op.alter_column('Flow', 'Id',
               existing_type=sa.INTEGER(),
               comment='Akış kimliği',
               existing_comment='Zamanlanmış iş kimliği',
               existing_nullable=False,
               autoincrement=True,
               existing_server_default=sa.Identity(always=False, start=1, increment=1),
               schema='adm')
    op.drop_column('Flow', 'NextRunAt', schema='adm')
