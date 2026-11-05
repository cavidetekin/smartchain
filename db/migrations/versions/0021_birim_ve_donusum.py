"""0021 · Birim ve birim dönüşümü (K-112): stg.UnitOfMeasure kalkar, Decimals varsayılansız; UomConversion ad alanları, açıklama ve anahtar

Revision ID: 0021
Revises: 0020
Create Date: 2026-11-04
"""
from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql

from dictionary import sync
from models import metadata


revision = '0021'
down_revision = '0020'
branch_labels = None
depends_on = None

OLD_FACTOR, NEW_FACTOR = 'Çarpan', '1 kaynak birim = çarpan × hedef birim'
DECIMALS_COMMENT = "Miktar ondalığı; ERP'den gelmez, Smartchain'de tutulur (K-88)"
NULLABLE = {'core': False, 'stg': True}


def _factor_comment(new, old):
    for schema, nullable in NULLABLE.items():
        op.alter_column('UomConversion', 'Factor', existing_type=sa.NUMERIC(precision=18, scale=6), comment=new,
                        existing_comment=old, existing_nullable=nullable, schema=schema)


def upgrade():
    op.drop_table('UnitOfMeasure', schema='stg')
    op.alter_column('UnitOfMeasure', 'Decimals', existing_type=mssql.TINYINT(), server_default=None,
                    existing_comment=DECIMALS_COMMENT, existing_nullable=True, schema='core')
    for schema in NULLABLE:
        op.add_column('UomConversion', sa.Column('FromUomName', sa.Unicode(length=50), nullable=True, comment='Kaynak birim adı'), schema=schema)
        op.add_column('UomConversion', sa.Column('ToUomName', sa.Unicode(length=50), nullable=True, comment='Hedef birim adı'), schema=schema)
    _factor_comment(NEW_FACTOR, OLD_FACTOR)
    op.create_index('UX_UomConversion_MaterialId_FromUom_ToUom', 'UomConversion', ['MaterialId', 'FromUom', 'ToUom'], unique=True, schema='core', mssql_where=sa.text('VersionTo IS NULL'))
    op.create_index('UX_UomConversion_MaterialCode_FromUom_ToUom', 'UomConversion', ['MaterialCode', 'FromUom', 'ToUom'], unique=True, schema='stg')
    # Sözlük: sync DefaultValue'ya dokunmaz; bu değişiklik burada yazılır.
    op.execute("UPDATE adm.FieldDefinition SET DefaultValue = NULL WHERE TableName = N'UnitOfMeasure' AND FieldName = N'Decimals'")
    if not context.is_offline_mode():  # bağlantısız SQL betiğinde satırlar yazılmaz; ilk bağlantılı geçişte kurulur
        sync(op.get_bind(), metadata)


def downgrade():
    op.execute("DELETE FROM adm.FieldDefinition WHERE TableName = N'UomConversion' AND FieldName IN (N'FromUomName', N'ToUomName')")
    op.execute(f"UPDATE adm.FieldDefinition SET Description = N'{OLD_FACTOR}' WHERE TableName = N'UomConversion' AND FieldName = N'Factor'")
    op.execute("UPDATE adm.FieldDefinition SET DefaultValue = N'2' WHERE TableName = N'UnitOfMeasure' AND FieldName = N'Decimals'")
    op.drop_index('UX_UomConversion_MaterialCode_FromUom_ToUom', table_name='UomConversion', schema='stg')
    op.drop_index('UX_UomConversion_MaterialId_FromUom_ToUom', table_name='UomConversion', schema='core', mssql_where=sa.text('VersionTo IS NULL'))
    _factor_comment(OLD_FACTOR, NEW_FACTOR)
    for schema in NULLABLE:
        op.drop_column('UomConversion', 'ToUomName', schema=schema)
        op.drop_column('UomConversion', 'FromUomName', schema=schema)
    op.alter_column('UnitOfMeasure', 'Decimals', existing_type=mssql.TINYINT(), server_default=sa.text('2'),
                    existing_comment=DECIMALS_COMMENT, existing_nullable=True, schema='core')
    op.create_table('UnitOfMeasure',
    sa.Column('StagingRowId', sa.BIGINT(), sa.Identity(always=False, start=1, increment=1), autoincrement=True, nullable=False, comment='Satır kimliği'),
    sa.Column('ImportBatchId', sa.BIGINT(), autoincrement=False, nullable=False, comment='Yükleme partisi'),
    sa.Column('RowStatus', sa.NVARCHAR(length=15, collation='Latin1_General_100_CI_AS_SC'), autoincrement=False, nullable=False, comment='Yeni | Hatalı | Aktarıldı'),
    sa.Column('ErrorText', sa.NVARCHAR(length=400, collation='Latin1_General_100_CI_AS_SC'), autoincrement=False, nullable=True, comment='Hata açıklaması'),
    sa.Column('Code', sa.NVARCHAR(length=10, collation='Latin1_General_100_CI_AS_SC'), autoincrement=False, nullable=True, comment='Birim kodu (AD, KG, SAAT…)'),
    sa.Column('Name', sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'), autoincrement=False, nullable=True, comment='Birim adı'),
    sa.ForeignKeyConstraint(['ImportBatchId'], ['adm.ImportBatch.Id'], name=op.f('FK_UnitOfMeasure_ImportBatchId')),
    sa.PrimaryKeyConstraint('StagingRowId', name=op.f('PK_UnitOfMeasure')),
    schema='stg',
    comment='Ölçü birimi.'
    )
