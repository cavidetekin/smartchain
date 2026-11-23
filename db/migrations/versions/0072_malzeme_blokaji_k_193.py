"""0072 · Malzeme blokajı (K-193); alokasyon tablosu kalkar (K-192)

Yeni tablo `param.MaterialHold` (senaryolu, Baz + fark): malzeme için belli tarihlerde yeni tedarik planı çıkarılmaz. Veri taşınmaz.
`param.AllocationRule` düşer (Faz 1 dışı, K-192; hiçbir ekran ve motor okumuyordu): içindeki satırlar ve sözlük kayıtları silinir.
`adm.FieldChange.Source` açıklamasında "Malzeme blokajı" yerine "Model kısıtları" (ekranın adı; yalnız açıklama).

Geri alış `MaterialHold`'u ve kayıtlarını siler; `AllocationRule` boş olarak yeniden açılır.

Revision ID: 0072
Revises: 0071
Create Date: 2026-11-23
"""
from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql

from dictionary import sync
from models import metadata

revision = '0072'
down_revision = '0071'
branch_labels = None
depends_on = None

TABLE = 'MaterialHold'
GONE = 'AllocationRule'
GONE_COMMENT = 'Faz 1 dışı (K-192): kapasite alokasyonu, talep sınıfına kaynak grubu ve dönem bazında pay (K-180). Tablo durur, hiçbir ekran ve motor okumaz.'
OLD_SOURCE = 'Aktarım | Manuel değer | Manuel değer kaldırma | Kapasite yönetimi | Malzeme blokajı'
DICTIONARY = ('FieldDefinition', 'ManualValue', 'FieldValueSource')   # sözlük eşitlemesi silmez


def upgrade():
    c = metadata.tables[f'param.{TABLE}'].c
    op.create_table(TABLE,
    sa.Column('Id', sa.BigInteger(), autoincrement=True, nullable=False, comment=c.Id.comment),
    sa.Column('ScenarioDefinitionId', sa.Integer(), nullable=False, comment=c.ScenarioDefinitionId.comment),
    sa.Column('BaseRowId', sa.BigInteger(), nullable=True, comment=c.BaseRowId.comment),
    sa.Column('OverriddenFields', sa.Unicode(length=400), nullable=True, comment=c.OverriddenFields.comment),
    sa.Column('IsValid', sa.Boolean(), server_default=sa.text('1'), nullable=False, comment=c.IsValid.comment),
    sa.Column('LocationId', sa.Integer(), nullable=False, comment=c.LocationId.comment),
    sa.Column('MaterialId', sa.BigInteger(), nullable=False, comment=c.MaterialId.comment),
    sa.Column('HoldType', sa.Unicode(length=25), nullable=False, comment=c.HoldType.comment),
    sa.Column('StartDate', sa.DATE(), nullable=False, comment=c.StartDate.comment),
    sa.Column('EndDate', sa.DATE(), nullable=True, comment=c.EndDate.comment),
    sa.Column('ClosePct', sa.Numeric(precision=5, scale=2), nullable=False, comment=c.ClosePct.comment),
    sa.Column('Reason', sa.Unicode(length=255), nullable=True, comment=c.Reason.comment),
    sa.Column('UpdatedAt', mssql.DATETIME2(), nullable=False, comment=c.UpdatedAt.comment),
    sa.Column('UpdatedBy', sa.Integer(), nullable=True, comment=c.UpdatedBy.comment),
    sa.ForeignKeyConstraint(['LocationId'], ['core.Location.Id'], name=op.f('FK_MaterialHold_LocationId')),
    sa.ForeignKeyConstraint(['ScenarioDefinitionId'], ['param.ScenarioDefinition.Id'], name=op.f('FK_MaterialHold_ScenarioDefinitionId')),
    sa.PrimaryKeyConstraint('Id', name=op.f('PK_MaterialHold')),
    schema='param',
    comment=metadata.tables[f'param.{TABLE}'].comment,
    info={'field_class': 'Parametre'}
    )
    op.create_index(op.f('IX_MaterialHold_LocationId'), TABLE, ['LocationId'], unique=False, schema='param')
    op.create_index(op.f('IX_MaterialHold_MaterialId'), TABLE, ['MaterialId'], unique=False, schema='param')
    # alokasyon tablosu (K-192)
    for table in DICTIONARY:
        op.execute(f"DELETE FROM adm.[{table}] WHERE TableName = N'{GONE}'")
    op.drop_index(op.f('IX_AllocationRule_ResourceGroupId'), table_name=GONE, schema='param')
    op.drop_table(GONE, schema='param')
    source = metadata.tables['adm.FieldChange'].c.Source
    op.alter_column('FieldChange', 'Source', existing_type=sa.Unicode(length=40), existing_nullable=False, comment=source.comment, existing_comment=OLD_SOURCE,
                    schema='adm')
    if not context.is_offline_mode():  # bağlantısız SQL betiğinde satırlar yazılmaz; ilk bağlantılı geçişte kurulur
        sync(op.get_bind(), metadata)


def downgrade():
    source = metadata.tables['adm.FieldChange'].c.Source
    op.alter_column('FieldChange', 'Source', existing_type=sa.Unicode(length=40), existing_nullable=False, comment=OLD_SOURCE, existing_comment=source.comment,
                    schema='adm')
    op.create_table(GONE,
    sa.Column('Id', sa.BigInteger(), autoincrement=True, nullable=False, comment='Kayıt kimliği'),
    sa.Column('ScenarioDefinitionId', sa.Integer(), nullable=False, comment='Senaryo'),
    sa.Column('DemandClass', sa.Unicode(length=100), nullable=False, comment='Talep sınıfı tanımı (müşteri, proje, ürün grubu)'),
    sa.Column('ResourceGroupId', sa.BigInteger(), nullable=True, comment='Kaynak grubu'),
    sa.Column('ValidFrom', sa.DATE(), nullable=True, comment='Başlangıç'),
    sa.Column('ValidTo', sa.DATE(), nullable=True, comment='Bitiş'),
    sa.Column('SharePct', sa.Numeric(precision=6, scale=2), nullable=False, comment='Pay (%)'),
    sa.Column('Hardness', sa.Unicode(length=10), server_default=sa.text("N'Yumuşak'"), nullable=True, comment='Taban | Tavan | Yumuşak'),
    sa.ForeignKeyConstraint(['ScenarioDefinitionId'], ['param.ScenarioDefinition.Id'], name=op.f('FK_AllocationRule_ScenarioDefinitionId')),
    sa.PrimaryKeyConstraint('Id', name=op.f('PK_AllocationRule')),
    schema='param',
    comment=GONE_COMMENT,
    info={'field_class': 'Parametre'}
    )
    op.create_index(op.f('IX_AllocationRule_ResourceGroupId'), GONE, ['ResourceGroupId'], unique=False, schema='param')
    for table in DICTIONARY:
        op.execute(f"DELETE FROM adm.[{table}] WHERE TableName = N'{TABLE}'")
    op.drop_index(op.f('IX_MaterialHold_MaterialId'), table_name=TABLE, schema='param')
    op.drop_index(op.f('IX_MaterialHold_LocationId'), table_name=TABLE, schema='param')
    op.drop_table(TABLE, schema='param')
    if not context.is_offline_mode():
        sync(op.get_bind(), metadata)
