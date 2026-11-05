"""0033 · Stok (K-123): StockStatus → Status (ham değer, liste ve varsayılan yok); anahtar; bayraklar, sahip müşteri ve sipariş, kabul tarihi, birim

Stok durumu korunur, var olan satırlarda yeni alanlar boş kalır; bayraklar burada doldurulmaz. stg ham veridir, değerleri çevrilmez.
Aynı anahtarlı güncel satır varsa tekil indeks geçişi durdurur; veri silinmez.
Geri alışta yeni alanlar kaybolur, boş durum Serbest olur. 15 karakteri aşan durum varsa geri alış durur; veri silinmez.

Revision ID: 0033
Revises: 0032
Create Date: 2026-11-05
"""
from alembic import context, op
import sqlalchemy as sa

from dictionary import sync
from models import metadata


revision = '0033'
down_revision = '0032'
branch_labels = None
depends_on = None

FD = 'adm.FieldDefinition'
T = 'Stock'
OLD = 'StockStatus'
NAME = 'Status'
OLD_TYPE = sa.Unicode(length=15)
NEW_TYPE = sa.Unicode(length=50)
OLD_COMMENT = 'Serbest | Kalitede | Bloke'
NEW_COMMENT = "ERP'den ham stok durumu; veri kurallarında kullanılır, değer listesi yok"
UOM = ('Uom', sa.Unicode(length=10), 'Miktarın birimi; boşsa malzemenin temel biriminde kabul edilir, doluysa birim dönüşümüyle çevrilir')
REST = (
    UOM,
    ('ExpectedAcceptanceDate', sa.Date(), 'Kalitedeki stoğun kullanılabilir hâle gelmesi beklenen tarih'),
    ('IsAvailable', sa.Boolean(), 'Stok planda kullanılabilir; Status ve depoya göre veri kuralıyla doldurulur'),
    ('IsInQuality', sa.Boolean(), 'Stok planda kalitede sayılır; Status ve depoya göre veri kuralıyla doldurulur'),
    ('IsBlocked', sa.Boolean(), 'Stok planda bloke sayılır; Status ve depoya göre veri kuralıyla doldurulur'),
    ('IsActive', sa.Boolean(), 'Aktif mi'),
    ('IsCustomTracked', sa.Boolean(), 'Stok düzeyinde özel takip'),
)
NEW_CORE = (
    ('CustomerId', sa.BigInteger(), 'Sahip müşteri; stoğun ayrıldığı müşteri, ileride kullanılmak üzere'),
    ('SalesOrderLineId', sa.BigInteger(), 'Sahip sipariş satırı; stoğun ayrıldığı sipariş satırı, ileride kullanılmak üzere'),
) + REST
NEW_STG = (
    ('CustomerCode', sa.Unicode(length=50), 'Sahip müşteri; stoğun ayrıldığı müşteri, ileride kullanılmak üzere'),
    ('SalesOrderNo', sa.Unicode(length=30), 'Sahip sipariş no; stoğun ayrıldığı sipariş, ileride kullanılmak üzere'),
    ('SalesOrderLineNo', sa.Integer(), 'Sahip sipariş satırı; stoğun ayrıldığı sipariş satırı, ileride kullanılmak üzere'),
) + REST
UX_CORE = 'UX_Stock_LocationId_MaterialId_Warehouse_LotNo_Status_ProjectId_CustomerId_SalesOrderLineId'
UX_STG = 'UX_Stock_LocationCode_MaterialCode_Warehouse_LotNo_Status_ProjectCode_CustomerCode_SalesOrderNo_SalesOrderLineNo'
WHERE = sa.text('VersionTo IS NULL')


def upgrade():
    op.alter_column(T, OLD, existing_type=OLD_TYPE, server_default=None, existing_comment=OLD_COMMENT, existing_nullable=False, schema='core')
    for schema, new in (('core', NEW_CORE), ('stg', NEW_STG)):
        op.alter_column(T, OLD, new_column_name=NAME, schema=schema)
        op.alter_column(T, NAME, existing_type=OLD_TYPE, type_=NEW_TYPE, nullable=True, comment=NEW_COMMENT, existing_comment=OLD_COMMENT, schema=schema)
        for name, type_, comment in new:
            op.add_column(T, sa.Column(name, type_, nullable=True, comment=comment), schema=schema)
    op.create_foreign_key(op.f('FK_Stock_Uom'), T, 'UnitOfMeasure', ['Uom'], ['Code'], source_schema='core', referent_schema='core')
    op.create_index(op.f('IX_Stock_CustomerId'), T, ['CustomerId'], unique=False, schema='core')
    op.create_index(op.f('IX_Stock_SalesOrderLineId'), T, ['SalesOrderLineId'], unique=False, schema='core')
    op.create_index(UX_CORE, T, ['LocationId', 'MaterialId', 'Warehouse', 'LotNo', 'Status', 'ProjectId', 'CustomerId', 'SalesOrderLineId'], unique=True, schema='core', mssql_where=WHERE)
    op.create_index(UX_STG, T, ['LocationCode', 'MaterialCode', 'Warehouse', 'LotNo', 'Status', 'ProjectCode', 'CustomerCode', 'SalesOrderNo', 'SalesOrderLineNo'], unique=True, schema='stg')
    # Sözlük: elle verilen etiket yeni adda kalır; varsayılan ve zorunluluk kalkar.
    op.execute(f"UPDATE {FD} SET FieldName = N'{NAME}', DefaultValue = NULL, IsRequired = 0 WHERE TableName = N'{T}' AND FieldName = N'{OLD}'")
    if not context.is_offline_mode():  # bağlantısız SQL betiğinde satırlar yazılmaz; ilk bağlantılı geçişte kurulur
        sync(op.get_bind(), metadata)


def downgrade():
    names = ', '.join(f"N'{n}'" for n, _, _ in NEW_CORE)
    op.execute(f"DELETE FROM {FD} WHERE TableName = N'{T}' AND FieldName IN ({names})")
    op.execute(f"UPDATE {FD} SET FieldName = N'{OLD}', DefaultValue = N'Serbest', IsRequired = 1, Description = N'{OLD_COMMENT}' WHERE TableName = N'{T}' AND FieldName = N'{NAME}'")
    op.drop_index(UX_STG, table_name=T, schema='stg')
    op.drop_index(UX_CORE, table_name=T, schema='core', mssql_where=WHERE)
    op.drop_index(op.f('IX_Stock_SalesOrderLineId'), table_name=T, schema='core')
    op.drop_index(op.f('IX_Stock_CustomerId'), table_name=T, schema='core')
    op.drop_constraint(op.f('FK_Stock_Uom'), T, schema='core', type_='foreignkey')
    op.execute(f"UPDATE core.{T} SET {NAME} = N'Serbest' WHERE {NAME} IS NULL")
    for schema, new, nullable in (('core', NEW_CORE, False), ('stg', NEW_STG, True)):
        for name, _, _ in reversed(new):
            op.drop_column(T, name, schema=schema)
        op.alter_column(T, NAME, existing_type=NEW_TYPE, type_=OLD_TYPE, nullable=nullable, comment=OLD_COMMENT, existing_comment=NEW_COMMENT, schema=schema)
        op.alter_column(T, NAME, new_column_name=OLD, schema=schema)
    op.alter_column(T, OLD, existing_type=OLD_TYPE, server_default=sa.text("N'Serbest'"), existing_comment=OLD_COMMENT, existing_nullable=False, schema='core')
