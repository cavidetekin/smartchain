"""0036 · Benzetilen ürün (K-126) ve kapasite birimi (K-117): MaterialReference; stg.Resource.CapacityUnit; SAAT varsayılanı kalkar

Var olan kaynakların kapasite birimi korunur. Sözlükte varsayılan silinir; alan zorunlu kalır. stg ham veridir.
Geri alışta MaterialReference satırları kaybolur, SAAT varsayılanı geri gelir.

Revision ID: 0036
Revises: 0035
Create Date: 2026-11-05 02:35:49.520537
"""
from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql

from dictionary import sync
from models import metadata
from sqlalchemy.dialects import mssql

from dictionary import sync
from models import metadata

revision = '0036'
down_revision = '0035'
branch_labels = None
depends_on = None

FD = 'adm.FieldDefinition'
UNIT_COMMENT = 'Kapasite birimi (Saat, Adet, Ton…); rotadaki tüketim aynı birimde kabul edilir'


def upgrade():
    op.create_table('MaterialReference',
    sa.Column('Id', sa.BigInteger(), autoincrement=False, nullable=False, comment='Kayıt kimliği'),
    sa.Column('LocationId', sa.Integer(), nullable=False, comment='Lokasyon'),
    sa.Column('MaterialId', sa.BigInteger(), nullable=False, comment='Benzetilen ürün'),
    sa.Column('ReferenceMaterialId', sa.BigInteger(), nullable=False, comment='Referans ürün'),
    sa.Column('ReferenceProductionVersionId', sa.BigInteger(), nullable=True, comment='Referans ürünün versiyonu; boşsa motor seçer'),
    sa.Column('ValidFrom', sa.DATE(), nullable=True, comment='Geçerlilik başlangıcı'),
    sa.Column('ValidTo', sa.DATE(), nullable=True, comment='Geçerlilik bitişi'),
    sa.Column('TimeFactor', sa.Numeric(precision=9, scale=4), server_default=sa.text('1'), nullable=True, comment='Süre çarpanı; 1,2 = %20 daha uzun'),
    sa.Column('VersionFrom', sa.Integer(), autoincrement=False, nullable=False, comment='Kaydın geçerli olduğu ilk veri versiyonu'),
    sa.Column('VersionTo', sa.Integer(), nullable=True, comment='Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş'),
    sa.Column('ImportBatchId', sa.BigInteger(), nullable=True, comment='Kaydı getiren yükleme partisi'),
    sa.Column('BusinessKey', sa.Unicode(length=200), nullable=False, comment='İş anahtarı; kod ya da kodların birleşimi'),
    sa.Column('UpdatedAt', mssql.DATETIME2(), nullable=False, comment='Son değişiklik zamanı'),
    sa.ForeignKeyConstraint(['ImportBatchId'], ['adm.ImportBatch.Id'], name=op.f('FK_MaterialReference_ImportBatchId')),
    sa.ForeignKeyConstraint(['LocationId'], ['core.Location.Id'], name=op.f('FK_MaterialReference_LocationId')),
    sa.PrimaryKeyConstraint('Id', 'VersionFrom', name=op.f('PK_MaterialReference')),
    schema='core',
    comment='Benzetilen ürün: kendi ağacı ya da rotası olmayan ürün, başka bir ürünün verisiyle planlanır.'
    )
    op.create_index(op.f('IX_MaterialReference_MaterialId'), 'MaterialReference', ['MaterialId'], unique=False, schema='core')
    op.create_index(op.f('IX_MaterialReference_ReferenceMaterialId'), 'MaterialReference', ['ReferenceMaterialId'], unique=False, schema='core')
    op.create_index(op.f('IX_MaterialReference_ReferenceProductionVersionId'), 'MaterialReference', ['ReferenceProductionVersionId'], unique=False, schema='core')
    op.create_index('UX_MaterialReference_LocationId_MaterialId_ReferenceMaterialId_ValidFrom', 'MaterialReference', ['LocationId', 'MaterialId', 'ReferenceMaterialId', 'ValidFrom'], unique=True, schema='core', mssql_where=sa.text('VersionTo IS NULL'))
    op.create_table('MaterialReference',
    sa.Column('StagingRowId', sa.BigInteger(), autoincrement=True, nullable=False, comment='Satır kimliği'),
    sa.Column('ImportBatchId', sa.BigInteger(), nullable=False, comment='Yükleme partisi'),
    sa.Column('RowStatus', sa.Unicode(length=15), nullable=False, comment='Yeni | Hatalı | Aktarıldı'),
    sa.Column('ErrorText', sa.Unicode(length=400), nullable=True, comment='Hata açıklaması'),
    sa.Column('LocationCode', sa.Unicode(length=30), nullable=True, comment='Lokasyon kodu'),
    sa.Column('MaterialCode', sa.Unicode(length=50), nullable=True, comment='Benzetilen ürün'),
    sa.Column('ReferenceMaterialCode', sa.Unicode(length=50), nullable=True, comment='Referans ürün'),
    sa.Column('ReferenceProductionVersionCode', sa.Unicode(length=30), nullable=True, comment='Referans ürünün versiyonu; boşsa motor seçer'),
    sa.Column('ValidFrom', sa.DATE(), nullable=True, comment='Geçerlilik başlangıcı'),
    sa.Column('ValidTo', sa.DATE(), nullable=True, comment='Geçerlilik bitişi'),
    sa.Column('TimeFactor', sa.Numeric(precision=9, scale=4), nullable=True, comment='Süre çarpanı; 1,2 = %20 daha uzun'),
    sa.ForeignKeyConstraint(['ImportBatchId'], ['adm.ImportBatch.Id'], name=op.f('FK_MaterialReference_ImportBatchId')),
    sa.PrimaryKeyConstraint('StagingRowId', name=op.f('PK_MaterialReference')),
    schema='stg',
    comment='Benzetilen ürün: kendi ağacı ya da rotası olmayan ürün, başka bir ürünün verisiyle planlanır.'
    )
    op.create_index('UX_MaterialReference_LocationCode_MaterialCode_ReferenceMaterialCode_ValidFrom', 'MaterialReference', ['LocationCode', 'MaterialCode', 'ReferenceMaterialCode', 'ValidFrom'], unique=True, schema='stg')
    op.alter_column('Resource', 'CapacityUnit', existing_type=sa.Unicode(length=10), server_default=None, existing_comment=UNIT_COMMENT, existing_nullable=False, schema='core')
    op.add_column('Resource', sa.Column('CapacityUnit', sa.Unicode(length=10), nullable=True, comment=UNIT_COMMENT), schema='stg')
    # Sözlük: sync varsayılana dokunmaz; yeni tablonun satırlarını kurar.
    op.execute(f"UPDATE {FD} SET DefaultValue = NULL WHERE TableName = N'Resource' AND FieldName = N'CapacityUnit'")
    if not context.is_offline_mode():  # bağlantısız SQL betiğinde satırlar yazılmaz; ilk bağlantılı geçişte kurulur
        sync(op.get_bind(), metadata)


def downgrade():
    op.execute(f"DELETE FROM {FD} WHERE TableName = N'MaterialReference'")
    op.execute(f"UPDATE {FD} SET DefaultValue = N'SAAT' WHERE TableName = N'Resource' AND FieldName = N'CapacityUnit'")
    op.drop_column('Resource', 'CapacityUnit', schema='stg')
    op.alter_column('Resource', 'CapacityUnit', existing_type=sa.Unicode(length=10), server_default=sa.text("N'SAAT'"), existing_comment=UNIT_COMMENT, existing_nullable=False, schema='core')
    op.drop_index('UX_MaterialReference_LocationCode_MaterialCode_ReferenceMaterialCode_ValidFrom', table_name='MaterialReference', schema='stg')
    op.drop_table('MaterialReference', schema='stg')
    op.drop_index('UX_MaterialReference_LocationId_MaterialId_ReferenceMaterialId_ValidFrom', table_name='MaterialReference', schema='core', mssql_where=sa.text('VersionTo IS NULL'))
    op.drop_index(op.f('IX_MaterialReference_ReferenceProductionVersionId'), table_name='MaterialReference', schema='core')
    op.drop_index(op.f('IX_MaterialReference_ReferenceMaterialId'), table_name='MaterialReference', schema='core')
    op.drop_index(op.f('IX_MaterialReference_MaterialId'), table_name='MaterialReference', schema='core')
    op.drop_table('MaterialReference', schema='core')
