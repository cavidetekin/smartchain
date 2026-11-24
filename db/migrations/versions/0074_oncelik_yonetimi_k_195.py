"""0074 · Öncelik yönetimi (K-195); ölçüt sırası tablosu kalkar

Yeni tablo `param.DemandPriority` (senaryolu, Baz + fark): müşteri, proje ya da sipariş satırı için girilen 1–5 öncelik grubu. Veri taşınmaz.
`param.PriorityRule` düşer (eski "öncelik kuralları" tasarımı geçersiz; hiçbir ekran okumuyordu): satırları ve sözlük kayıtları silinir.
Müşteri, proje ve sipariş satırındaki `Priority` alanlarının açıklaması "ERP önceliği" olur (`core`, `prc`, `stg` değişmez: yalnız `core` açıklaması).

Geri alış `DemandPriority`'yi ve kayıtlarını siler; `PriorityRule` boş olarak yeniden açılır.

Revision ID: 0074
Revises: 0073
Create Date: 2026-11-23
"""
from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql

from dictionary import sync
from models import metadata

revision = '0074'
down_revision = '0073'
branch_labels = None
depends_on = None

TABLE = 'DemandPriority'
GONE = 'PriorityRule'
DICTIONARY = ('FieldDefinition', 'ManualValue', 'FieldValueSource')   # sözlük eşitlemesi silmez
OLD_PRIORITY = {'Project': 'Proje önceliği', 'Customer': 'Müşteri önceliği', 'SalesOrderLine': 'Satır önceliği'}


def _priority_comments(to_new: bool) -> None:
    for table, old in OLD_PRIORITY.items():
        new = metadata.tables[f'core.{table}'].c.Priority.comment
        op.alter_column(table, 'Priority', existing_type=sa.Integer(), existing_nullable=True, comment=new if to_new else old,
                        existing_comment=old if to_new else new, schema='core')


def upgrade():
    c = metadata.tables[f'param.{TABLE}'].c
    op.create_table(TABLE,
    sa.Column('Id', sa.BigInteger(), autoincrement=True, nullable=False, comment=c.Id.comment),
    sa.Column('ScenarioDefinitionId', sa.Integer(), nullable=False, comment=c.ScenarioDefinitionId.comment),
    sa.Column('BaseRowId', sa.BigInteger(), nullable=True, comment=c.BaseRowId.comment),
    sa.Column('OverriddenFields', sa.Unicode(length=400), nullable=True, comment=c.OverriddenFields.comment),
    sa.Column('IsValid', sa.Boolean(), server_default=sa.text('1'), nullable=False, comment=c.IsValid.comment),
    sa.Column('Level', sa.Unicode(length=10), nullable=False, comment=c.Level.comment),
    sa.Column('RecordId', sa.BigInteger(), nullable=False, comment=c.RecordId.comment),
    sa.Column('PriorityGroup', sa.Integer(), nullable=True, comment=c.PriorityGroup.comment),
    sa.Column('UpdatedAt', mssql.DATETIME2(), nullable=False, comment=c.UpdatedAt.comment),
    sa.Column('UpdatedBy', sa.Integer(), nullable=True, comment=c.UpdatedBy.comment),
    sa.ForeignKeyConstraint(['ScenarioDefinitionId'], ['param.ScenarioDefinition.Id'], name=op.f('FK_DemandPriority_ScenarioDefinitionId')),
    sa.PrimaryKeyConstraint('Id', name=op.f('PK_DemandPriority')),
    schema='param',
    comment=metadata.tables[f'param.{TABLE}'].comment,
    info={'field_class': 'Parametre'}
    )
    op.create_index(op.f('IX_DemandPriority_Level'), TABLE, ['Level'], unique=False, schema='param')
    op.create_index(op.f('IX_DemandPriority_RecordId'), TABLE, ['RecordId'], unique=False, schema='param')
    # ölçüt sırası tablosu (eski tasarım)
    for table in DICTIONARY:
        op.execute(f"DELETE FROM adm.[{table}] WHERE TableName = N'{GONE}'")
    op.drop_table(GONE, schema='param')
    _priority_comments(True)
    if not context.is_offline_mode():  # bağlantısız SQL betiğinde satırlar yazılmaz; ilk bağlantılı geçişte kurulur
        sync(op.get_bind(), metadata)


def downgrade():
    _priority_comments(False)
    op.create_table(GONE,
    sa.Column('ScenarioDefinitionId', sa.Integer(), autoincrement=False, nullable=False, comment='Senaryo'),
    sa.Column('Seq', sa.Integer(), autoincrement=False, nullable=False, comment='Sıra'),
    sa.Column('Criterion', sa.Unicode(length=30), nullable=False, comment='Kriter'),
    sa.Column('Direction', sa.Unicode(length=10), server_default=sa.text("N'Artan'"), nullable=True, comment='Artan | Azalan'),
    sa.ForeignKeyConstraint(['ScenarioDefinitionId'], ['param.ScenarioDefinition.Id'], name=op.f('FK_PriorityRule_ScenarioDefinitionId')),
    sa.PrimaryKeyConstraint('ScenarioDefinitionId', 'Seq', name=op.f('PK_PriorityRule')),
    schema='param',
    comment='Sıralama kuralı: kriterlerin sırası (bucket > müşteri > proje > satır > tarih).',
    info={'field_class': 'Parametre'}
    )
    for table in DICTIONARY:
        op.execute(f"DELETE FROM adm.[{table}] WHERE TableName = N'{TABLE}'")
    op.drop_index(op.f('IX_DemandPriority_RecordId'), table_name=TABLE, schema='param')
    op.drop_index(op.f('IX_DemandPriority_Level'), table_name=TABLE, schema='param')
    op.drop_table(TABLE, schema='param')
    if not context.is_offline_mode():
        sync(op.get_bind(), metadata)
