"""0028 · Tedarikçi ve malzeme tedarikçisi (K-118): LocationId ve anahtar; tedarik süresi ikiye ayrılır; ad değişiklikleri; yeni alanlar

Eski LeadTimeDays sabit süreye taşınır (FixedLeadTimeDays). QuotaRatio oran olarak tutulur: core'daki yüzde değer 100'e bölünür.
Var olan satırlarda LocationId malzemeden gelir. stg ham veridir, değerleri çevrilmez.
Geri alışta değişken süre kaybolur, boş sabit süre 0 olur.

Revision ID: 0028
Revises: 0027
Create Date: 2026-11-04
"""
from alembic import context, op
import sqlalchemy as sa

from dictionary import sync
from models import metadata


revision = '0028'
down_revision = '0027'
branch_labels = None
depends_on = None

SCHEMAS = ('core', 'stg')
FD = 'adm.FieldDefinition'
T = 'MaterialSupplier'
RENAMED = {'QuotaPct': 'QuotaRatio', 'LeadTimeDays': 'FixedLeadTimeDays', 'MinOrderQty': 'MinimumOrderQuantity', 'OrderMultiple': 'OrderLotSize', 'MaxOrderQty': 'MaximumOrderQuantity'}
QUOTA_OLD, QUOTA_NEW = 'Kota (%)', 'Oran olarak kota (0,30 = %30)'
LEAD_OLD, LEAD_NEW = 'Tedarik süresi', 'Miktardan bağımsız kısım'
LOT_OLD, LOT_NEW = 'Kat', 'Sipariş miktarı bu sayının katı olur'
VARIABLE = 'Birim başına gün; miktar arttıkça uzayan kısım'
WIDE, RATIO, PERCENT = sa.Numeric(precision=10, scale=4), sa.Numeric(precision=6, scale=4), sa.Numeric(precision=6, scale=2)
LEAD = sa.Numeric(precision=9, scale=2)
LOT = sa.Numeric(precision=18, scale=4)
UNIQUE_CORE = 'UX_MaterialSupplier_LocationId_MaterialId_SupplierId'
UNIQUE_STG = 'UX_MaterialSupplier_LocationCode_MaterialCode_SupplierCode'


def _rename(pairs):
    for schema in SCHEMAS:
        for old, new in pairs:
            op.alter_column(T, old, new_column_name=new, schema=schema)


def _scale(schema, old_type, final, operator):
    op.alter_column(T, 'QuotaRatio', existing_type=old_type, type_=WIDE, existing_nullable=True, schema=schema)
    if schema == 'core':
        op.execute(f"UPDATE core.{T} SET QuotaRatio = QuotaRatio {operator} 100")
    op.alter_column(T, 'QuotaRatio', existing_type=WIDE, type_=final, existing_nullable=True, schema=schema)


def _comments(quota, quota_old, lead, lead_old, lot, lot_old):
    for schema in SCHEMAS:
        op.alter_column(T, 'QuotaRatio', existing_type=RATIO, comment=quota, existing_comment=quota_old, existing_nullable=True, schema=schema)
        op.alter_column(T, 'FixedLeadTimeDays', existing_type=LEAD, comment=lead, existing_comment=lead_old, existing_nullable=True, schema=schema)
        op.alter_column(T, 'OrderLotSize', existing_type=LOT, comment=lot, existing_comment=lot_old, existing_nullable=True, schema=schema)


def upgrade():
    for schema in SCHEMAS:
        op.add_column('Supplier', sa.Column('IsActive', sa.Boolean(), nullable=True, comment='Aktif mi'), schema=schema)
        op.add_column('Supplier', sa.Column('Country', sa.Unicode(length=100), nullable=True, comment='Ülke'), schema=schema)
        op.add_column('Supplier', sa.Column('City', sa.Unicode(length=100), nullable=True, comment='Şehir'), schema=schema)
        op.add_column(T, sa.Column('IsActive', sa.Boolean(), nullable=True, comment='Aktif mi'), schema=schema)
        op.add_column(T, sa.Column('VariableLeadTimeDays', sa.Numeric(precision=18, scale=6), nullable=True, comment=VARIABLE), schema=schema)
    op.add_column(T, sa.Column('LocationId', sa.Integer(), nullable=True, comment='Lokasyon'), schema='core')
    op.add_column(T, sa.Column('LocationCode', sa.Unicode(length=30), nullable=True, comment='Lokasyon kodu'), schema='stg')
    op.execute(f"UPDATE s SET LocationId = (SELECT TOP 1 m.LocationId FROM core.Material m WHERE m.Id = s.MaterialId ORDER BY m.VersionFrom DESC) FROM core.{T} s")
    op.alter_column(T, 'LocationId', existing_type=sa.Integer(), nullable=False, existing_comment='Lokasyon', schema='core')
    op.create_foreign_key(op.f(f'FK_{T}_LocationId'), T, 'Location', ['LocationId'], ['Id'], source_schema='core', referent_schema='core')
    _rename(RENAMED.items())
    op.alter_column(T, 'FixedLeadTimeDays', existing_type=LEAD, nullable=True, existing_comment=LEAD_OLD, schema='core')
    for schema in SCHEMAS:
        _scale(schema, PERCENT, RATIO, '/')
    _comments(QUOTA_NEW, QUOTA_OLD, LEAD_NEW, LEAD_OLD, LOT_NEW, LOT_OLD)
    op.create_index(UNIQUE_CORE, T, ['LocationId', 'MaterialId', 'SupplierId'], unique=True, schema='core', mssql_where=sa.text('VersionTo IS NULL'))
    op.create_index(UNIQUE_STG, T, ['LocationCode', 'MaterialCode', 'SupplierCode'], unique=True, schema='stg')
    # Sözlük: elle verilen etiket yeni adda kalır; sync silmez, IsRequired'a dokunmaz.
    for old, new in RENAMED.items():
        op.execute(f"UPDATE {FD} SET FieldName = N'{new}' WHERE TableName = N'{T}' AND FieldName = N'{old}'")
    op.execute(f"UPDATE {FD} SET IsRequired = 0 WHERE TableName = N'{T}' AND FieldName = N'FixedLeadTimeDays'")
    if not context.is_offline_mode():  # bağlantısız SQL betiğinde satırlar yazılmaz; ilk bağlantılı geçişte kurulur
        sync(op.get_bind(), metadata)


def downgrade():
    op.execute(f"DELETE FROM {FD} WHERE TableName = N'Supplier' AND FieldName IN (N'IsActive', N'Country', N'City')")
    op.execute(f"DELETE FROM {FD} WHERE TableName = N'{T}' AND FieldName IN (N'LocationId', N'IsActive', N'VariableLeadTimeDays')")
    for old, new in RENAMED.items():
        op.execute(f"UPDATE {FD} SET FieldName = N'{old}' WHERE TableName = N'{T}' AND FieldName = N'{new}'")
    op.execute(f"UPDATE {FD} SET StandardLabel = N'{QUOTA_OLD}', Description = N'{QUOTA_OLD}' WHERE TableName = N'{T}' AND FieldName = N'QuotaPct'")
    op.execute(f"UPDATE {FD} SET StandardLabel = N'{LEAD_OLD}', Description = N'{LEAD_OLD}', IsRequired = 1 WHERE TableName = N'{T}' AND FieldName = N'LeadTimeDays'")
    op.execute(f"UPDATE {FD} SET StandardLabel = N'Sipariş katı', Description = N'{LOT_OLD}' WHERE TableName = N'{T}' AND FieldName = N'OrderMultiple'")
    op.drop_index(UNIQUE_STG, table_name=T, schema='stg')
    op.drop_index(UNIQUE_CORE, table_name=T, schema='core', mssql_where=sa.text('VersionTo IS NULL'))
    _comments(QUOTA_OLD, QUOTA_NEW, LEAD_OLD, LEAD_NEW, LOT_OLD, LOT_NEW)
    for schema in SCHEMAS:
        _scale(schema, RATIO, PERCENT, '*')
    op.execute(f"UPDATE core.{T} SET FixedLeadTimeDays = 0 WHERE FixedLeadTimeDays IS NULL")
    op.alter_column(T, 'FixedLeadTimeDays', existing_type=LEAD, nullable=False, existing_comment=LEAD_OLD, schema='core')
    _rename([(new, old) for old, new in RENAMED.items()])
    op.drop_constraint(op.f(f'FK_{T}_LocationId'), T, schema='core', type_='foreignkey')
    op.drop_column(T, 'LocationId', schema='core')
    op.drop_column(T, 'LocationCode', schema='stg')
    for schema in SCHEMAS:
        op.drop_column(T, 'VariableLeadTimeDays', schema=schema)
        op.drop_column(T, 'IsActive', schema=schema)
        op.drop_column('Supplier', 'City', schema=schema)
        op.drop_column('Supplier', 'Country', schema=schema)
        op.drop_column('Supplier', 'IsActive', schema=schema)
