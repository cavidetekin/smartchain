"""0024 · Ürün ağacı (K-115): ağaç kendi koduyla (Code); ProductionVersionId kalkar; LocationId, MaterialId, anahtar, yeni alanlar, ad değişiklikleri

Var olan satırlarda LocationId, MaterialId ve Code bağlı oldukları versiyondan gelir (Code = BOMCode), böylece versiyon–ağaç bağı korunur.
ScrapRatio oran olarak tutulur: core'daki yüzde değer 100'e bölünür. stg ham veridir, değerleri çevrilmez.
Geri alışta her satır aynı malzeme ve BOMCode'a sahip ilk versiyona bağlanır; versiyonu olmayan ağaç satırı varsa geri alış durur.

Revision ID: 0024
Revises: 0023
Create Date: 2026-11-04
"""
from alembic import context, op
import sqlalchemy as sa

from dictionary import sync
from models import metadata


revision = '0024'
down_revision = '0023'
branch_labels = None
depends_on = None

SCHEMAS = ('core', 'stg')
FD = 'adm.FieldDefinition'
RENAMED = {'OpNo': 'OperationNo', 'ScrapPct': 'ScrapRatio', 'IsFixedQuantity': 'IsLotBasedUsage'}
OLD_SCRAP, NEW_SCRAP = 'Bileşen firesi (%)', 'Oran olarak fire (0,05 = %5)'
OLD_LOT = 'Sabit miktarlı bileşen'
NEW_LOT = 'Doluysa bileşen üretilen miktardan bağımsız, her üretim lotu için sabit kullanılır; değilse birim başına'
WIDE = sa.Numeric(precision=10, scale=4)   # dönüşüm sırasında hassasiyet kaybolmasın
RATIO, PERCENT = sa.Numeric(precision=6, scale=4), sa.Numeric(precision=6, scale=2)
OPTIONAL = (
    ('SequenceNo', sa.Integer(), 'Sıra no; aynı bileşen iki kez geçerse operasyon no ile ayrışır'),
    ('ComponentUom', sa.Unicode(length=10), 'Bileşen miktarının birimi; boşsa bileşenin temel biriminde kabul edilir, doluysa birim dönüşümüyle çevrilir'),
    ('AlternativeGroup', sa.Unicode(length=50), 'Aynı grup koduna sahip satırlar birbirinin alternatifidir'),
    ('AlternativePriority', sa.Integer(), 'Grup içindeki tercih bilgisi'),
)
UNIQUE_CORE = 'UX_BOM_LocationId_MaterialId_Code_ComponentMaterialId_OperationNo_SequenceNo'
UNIQUE_STG = 'UX_BOM_LocationCode_MaterialCode_Code_ComponentMaterialCode_OperationNo_SequenceNo'
ADDED = ('LocationId', 'MaterialId', 'Code', 'SequenceNo', 'ComponentUom', 'IsPhantom', 'AlternativeGroup', 'AlternativePriority')


def _rename(pairs):
    for schema in SCHEMAS:
        for old, new in pairs:
            op.alter_column('BOM', old, new_column_name=new, schema=schema)


def _scale(schema, old_type, final, operator):
    op.alter_column('BOM', 'ScrapRatio', existing_type=old_type, type_=WIDE, existing_nullable=True, schema=schema)
    if schema == 'core':
        op.execute(f"UPDATE core.BOM SET ScrapRatio = ScrapRatio {operator} 100")
    op.alter_column('BOM', 'ScrapRatio', existing_type=WIDE, type_=final, existing_nullable=True, schema=schema)


def _comments(scrap, old_scrap, lot, old_lot, scrap_type):
    for schema in SCHEMAS:
        op.alter_column('BOM', 'ScrapRatio', existing_type=scrap_type, comment=scrap, existing_comment=old_scrap, existing_nullable=True, schema=schema)
        op.alter_column('BOM', 'IsLotBasedUsage', existing_type=sa.Boolean(), comment=lot, existing_comment=old_lot, existing_nullable=True, schema=schema)


def upgrade():
    op.drop_index('UX_BOM_MaterialCode_ProductionVersionCode', table_name='BOM', schema='stg')
    op.add_column('BOM', sa.Column('LocationId', sa.Integer(), nullable=True, comment='Lokasyon'), schema='core')
    op.add_column('BOM', sa.Column('MaterialId', sa.BigInteger(), nullable=True, comment='Üretilen malzeme'), schema='core')
    op.add_column('BOM', sa.Column('Code', sa.Unicode(length=50), nullable=True, comment='Ürün ağacı kodu'), schema='core')
    op.execute("UPDATE b SET LocationId = p.LocationId, MaterialId = p.MaterialId, Code = p.BOMCode FROM core.BOM b "
               "CROSS APPLY (SELECT TOP 1 pv.LocationId, pv.MaterialId, pv.BOMCode FROM core.ProductionVersion pv "
               "WHERE pv.Id = b.ProductionVersionId ORDER BY pv.VersionFrom DESC) p")
    op.alter_column('BOM', 'LocationId', existing_type=sa.Integer(), nullable=False, existing_comment='Lokasyon', schema='core')
    op.alter_column('BOM', 'MaterialId', existing_type=sa.BigInteger(), nullable=False, existing_comment='Üretilen malzeme', schema='core')
    op.alter_column('BOM', 'Code', existing_type=sa.Unicode(length=50), nullable=False, existing_comment='Ürün ağacı kodu', schema='core')
    op.drop_index(op.f('IX_BOM_ProductionVersionId'), table_name='BOM', schema='core')
    op.drop_column('BOM', 'ProductionVersionId', schema='core')
    op.add_column('BOM', sa.Column('LocationCode', sa.Unicode(length=30), nullable=True, comment='Lokasyon kodu'), schema='stg')
    op.add_column('BOM', sa.Column('Code', sa.Unicode(length=50), nullable=True, comment='Ürün ağacı kodu'), schema='stg')
    op.drop_column('BOM', 'ProductionVersionCode', schema='stg')
    _rename(RENAMED.items())
    for schema in SCHEMAS:
        _scale(schema, PERCENT, RATIO, '/')
    _comments(NEW_SCRAP, OLD_SCRAP, NEW_LOT, OLD_LOT, RATIO)
    for schema in SCHEMAS:
        for name, type_, comment in OPTIONAL:
            op.add_column('BOM', sa.Column(name, type_, nullable=True, comment=comment), schema=schema)
    op.add_column('BOM', sa.Column('IsPhantom', sa.Boolean(), server_default=sa.text('0'), nullable=True, comment='Hayalet bileşen'), schema='core')
    op.add_column('BOM', sa.Column('IsPhantom', sa.Boolean(), nullable=True, comment='Hayalet bileşen'), schema='stg')
    op.execute("UPDATE core.BOM SET IsPhantom = 0")
    op.create_index(op.f('IX_BOM_MaterialId'), 'BOM', ['MaterialId'], unique=False, schema='core')
    op.create_index(UNIQUE_CORE, 'BOM', ['LocationId', 'MaterialId', 'Code', 'ComponentMaterialId', 'OperationNo', 'SequenceNo'], unique=True, schema='core', mssql_where=sa.text('VersionTo IS NULL'))
    op.create_index(UNIQUE_STG, 'BOM', ['LocationCode', 'MaterialCode', 'Code', 'ComponentMaterialCode', 'OperationNo', 'SequenceNo'], unique=True, schema='stg')
    op.create_foreign_key(op.f('FK_BOM_ComponentUom'), 'BOM', 'UnitOfMeasure', ['ComponentUom'], ['Code'], source_schema='core', referent_schema='core')
    op.create_foreign_key(op.f('FK_BOM_LocationId'), 'BOM', 'Location', ['LocationId'], ['Id'], source_schema='core', referent_schema='core')
    # Sözlük: elle verilen etiket yeni adda kalır; sync silmez, yalnız ekler ve docs kolonlarını günceller.
    for old, new in RENAMED.items():
        op.execute(f"UPDATE {FD} SET FieldName = N'{new}' WHERE TableName = N'BOM' AND FieldName = N'{old}'")
    op.execute(f"DELETE FROM {FD} WHERE TableName = N'BOM' AND FieldName = N'ProductionVersionId'")
    if not context.is_offline_mode():  # bağlantısız SQL betiğinde satırlar yazılmaz; ilk bağlantılı geçişte kurulur
        sync(op.get_bind(), metadata)


def downgrade():
    names = ', '.join(f"N'{name}'" for name in ADDED)
    op.execute(f"DELETE FROM {FD} WHERE TableName = N'BOM' AND FieldName IN ({names})")
    for old, new in RENAMED.items():
        op.execute(f"UPDATE {FD} SET FieldName = N'{old}' WHERE TableName = N'BOM' AND FieldName = N'{new}'")
    op.execute(f"UPDATE {FD} SET StandardLabel = N'{OLD_SCRAP}', Description = N'{OLD_SCRAP}' WHERE TableName = N'BOM' AND FieldName = N'ScrapPct'")
    op.execute(f"UPDATE {FD} SET StandardLabel = N'{OLD_LOT}', Description = N'{OLD_LOT}' WHERE TableName = N'BOM' AND FieldName = N'IsFixedQuantity'")
    op.execute(f"INSERT INTO {FD} (TableName, FieldName, FieldClass, IsRequired, StandardLabel, Description) VALUES "
               "(N'BOM', N'ProductionVersionId', N'Ana veri', 1, N'Üretim versiyonu', N'Üretim versiyonu')")
    op.drop_constraint(op.f('FK_BOM_LocationId'), 'BOM', schema='core', type_='foreignkey')
    op.drop_constraint(op.f('FK_BOM_ComponentUom'), 'BOM', schema='core', type_='foreignkey')
    op.drop_index(UNIQUE_STG, table_name='BOM', schema='stg')
    op.drop_index(UNIQUE_CORE, table_name='BOM', schema='core', mssql_where=sa.text('VersionTo IS NULL'))
    op.drop_index(op.f('IX_BOM_MaterialId'), table_name='BOM', schema='core')
    op.add_column('BOM', sa.Column('ProductionVersionId', sa.BigInteger(), nullable=True, comment='Üretim versiyonu'), schema='core')
    op.execute("UPDATE b SET ProductionVersionId = (SELECT TOP 1 pv.Id FROM core.ProductionVersion pv "
               "WHERE pv.MaterialId = b.MaterialId AND pv.BOMCode = b.Code ORDER BY pv.Id, pv.VersionFrom DESC) FROM core.BOM b")
    op.alter_column('BOM', 'ProductionVersionId', existing_type=sa.BigInteger(), nullable=False, existing_comment='Üretim versiyonu', schema='core')
    op.create_index(op.f('IX_BOM_ProductionVersionId'), 'BOM', ['ProductionVersionId'], unique=False, schema='core')
    op.add_column('BOM', sa.Column('ProductionVersionCode', sa.Unicode(length=30), nullable=True, comment='Üretim versiyonu kodu'), schema='stg')
    _comments(OLD_SCRAP, NEW_SCRAP, OLD_LOT, NEW_LOT, RATIO)
    for schema in SCHEMAS:
        _scale(schema, RATIO, PERCENT, '*')
    _rename([(new, old) for old, new in RENAMED.items()])
    op.drop_column('BOM', 'IsPhantom', schema='core', mssql_drop_default=True)
    op.drop_column('BOM', 'IsPhantom', schema='stg')
    for schema in SCHEMAS:
        for name, _, _ in reversed(OPTIONAL):
            op.drop_column('BOM', name, schema=schema)
    op.drop_column('BOM', 'Code', schema='stg')
    op.drop_column('BOM', 'LocationCode', schema='stg')
    op.drop_column('BOM', 'Code', schema='core')
    op.drop_column('BOM', 'MaterialId', schema='core')
    op.drop_column('BOM', 'LocationId', schema='core')
    op.create_index('UX_BOM_MaterialCode_ProductionVersionCode', 'BOM', ['MaterialCode', 'ProductionVersionCode'], unique=True, schema='stg')
