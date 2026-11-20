"""0068 · Model kısıtları: kaynak grubunun kısıtsız kapasite çarpanı ve hedef doluluğu (K-189)

Yeni tablo param.ResourceGroupConstraint (senaryolu, Baz + fark; kaynak grubu başına tarihsiz iki değer). Başka tablo değişmez; veri taşınmaz.
Geri alış tabloyu ve içindeki kayıtları siler.

Revision ID: 0068
Revises: 0067
Create Date: 2026-11-20
"""
from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql

from dictionary import sync
from models import metadata

revision = '0068'
down_revision = '0067'
branch_labels = None
depends_on = None

TABLE = 'ResourceGroupConstraint'


def upgrade():
    op.create_table(TABLE,
    sa.Column('Id', sa.BigInteger(), autoincrement=True, nullable=False, comment='Kayıt kimliği'),
    sa.Column('ScenarioDefinitionId', sa.Integer(), nullable=False, comment='Senaryo'),
    sa.Column('BaseRowId', sa.BigInteger(), nullable=True, comment="Baz'ı izleyen senaryoda Baz'daki satırın farkıysa o satırın kimliği; senaryonun kendi satırında ve Baz'da boş"),
    sa.Column('OverriddenFields', sa.Unicode(length=400), nullable=True, comment='Fark satırında senaryonun değiştirdiği alanların adları (virgüllerle çevrili: ",TargetUtilizationPct,"); yalnız bu alanlar senaryodan, gerisi Baz satırından okunur'),
    sa.Column('IsValid', sa.Boolean(), server_default=sa.text('1'), nullable=False, comment='Ortak yapı gereği durur; bu tabloda her zaman Evet (değer boşaltılarak kaldırılır)'),
    sa.Column('ResourceGroupId', sa.BigInteger(), nullable=False, comment='Kaynak grubu'),
    sa.Column('UnconstrainedCapacityFactor', sa.Numeric(precision=9, scale=4), nullable=True, comment='Kısıtsız kapasite çarpanı (en az 1); boşsa sınır yok'),
    sa.Column('TargetUtilizationPct', sa.Numeric(precision=6, scale=2), nullable=True, comment="Hedef doluluk, yüzde (0'dan büyük, en çok 100); boşsa hedef yok"),
    sa.Column('UpdatedAt', mssql.DATETIME2(), nullable=False, comment='Son değişiklik zamanı (UTC)'),
    sa.Column('UpdatedBy', sa.Integer(), nullable=True, comment='Son değiştiren kullanıcı; sentetik ve geçişle gelen satırda boş'),
    sa.ForeignKeyConstraint(['ScenarioDefinitionId'], ['param.ScenarioDefinition.Id'], name=op.f('FK_ResourceGroupConstraint_ScenarioDefinitionId')),
    sa.PrimaryKeyConstraint('Id', name=op.f('PK_ResourceGroupConstraint')),
    schema='param',
    comment=metadata.tables[f'param.{TABLE}'].comment,
    info={'field_class': 'Parametre'}
    )
    op.create_index(op.f('IX_ResourceGroupConstraint_ResourceGroupId'), TABLE, ['ResourceGroupId'], unique=False, schema='param')
    if not context.is_offline_mode():  # bağlantısız SQL betiğinde satırlar yazılmaz; ilk bağlantılı geçişte kurulur
        sync(op.get_bind(), metadata)


def downgrade():
    for table in ('FieldDefinition', 'ManualValue', 'FieldValueSource'):   # sözlük eşitlemesi silmez
        op.execute(f"DELETE FROM adm.[{table}] WHERE TableName = N'{TABLE}'")
    op.drop_index(op.f('IX_ResourceGroupConstraint_ResourceGroupId'), table_name=TABLE, schema='param')
    op.drop_table(TABLE, schema='param')
    if not context.is_offline_mode():
        sync(op.get_bind(), metadata)
