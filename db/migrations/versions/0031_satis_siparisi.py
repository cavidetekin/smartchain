"""0031 · Satış siparişi (K-120): anahtar lokasyonlu; OpenQty → OpenQuantity; yeni miktarlar, birim ve bayraklar

Açık miktar korunur. Yeni alanlar var olan satırlarda boş kalır. stg ham veridir, değerleri çevrilmez.
Geri alışta yeni alanlar kaybolur.

Revision ID: 0031
Revises: 0030
Create Date: 2026-11-05
"""
from alembic import context, op
import sqlalchemy as sa

from dictionary import sync
from models import metadata


revision = '0031'
down_revision = '0030'
branch_labels = None
depends_on = None

SCHEMAS = ('core', 'stg')
FD = 'adm.FieldDefinition'
T = 'SalesOrderLine'
NEW = (
    ('OrderedQuantity', sa.Numeric(precision=18, scale=4), 'Satırın orijinal miktarı'),
    ('DeliveredQuantity', sa.Numeric(precision=18, scale=4), 'Teslim edilen miktar'),
    ('Uom', sa.Unicode(length=10), 'Açık, sipariş ve teslim miktarının birimi; boşsa malzemenin temel biriminde kabul edilir, doluysa birim dönüşümüyle çevrilir'),
    ('IsActive', sa.Boolean(), 'Aktif mi'),
    ('IsOnHold', sa.Boolean(), 'Kredi, teknik onay ya da müşteri talebiyle bekletilen satır'),
    ('IsCustomTracked', sa.Boolean(), 'Satır düzeyinde özel takip'),
)
OLD_CORE = 'UX_SalesOrderLine_OrderNo_LineNo_LineItemNo'
NEW_CORE = 'UX_SalesOrderLine_LocationId_OrderNo_LineNo_LineItemNo'
NEW_STG = 'UX_SalesOrderLine_LocationCode_OrderNo_LineNo_LineItemNo'
WHERE = sa.text('VersionTo IS NULL')


def upgrade():
    op.drop_index(OLD_CORE, table_name=T, schema='core', mssql_where=WHERE)
    op.drop_index(OLD_CORE, table_name=T, schema='stg')
    for schema in SCHEMAS:
        op.alter_column(T, 'OpenQty', new_column_name='OpenQuantity', schema=schema)
        for name, type_, comment in NEW:
            op.add_column(T, sa.Column(name, type_, nullable=True, comment=comment), schema=schema)
    op.create_foreign_key(op.f('FK_SalesOrderLine_Uom'), T, 'UnitOfMeasure', ['Uom'], ['Code'], source_schema='core', referent_schema='core')
    op.create_index(NEW_CORE, T, ['LocationId', 'OrderNo', 'LineNo', 'LineItemNo'], unique=True, schema='core', mssql_where=WHERE)
    op.create_index(NEW_STG, T, ['LocationCode', 'OrderNo', 'LineNo', 'LineItemNo'], unique=True, schema='stg')
    # Sözlük: elle verilen etiket yeni adda kalır.
    op.execute(f"UPDATE {FD} SET FieldName = N'OpenQuantity' WHERE TableName = N'{T}' AND FieldName = N'OpenQty'")
    if not context.is_offline_mode():  # bağlantısız SQL betiğinde satırlar yazılmaz; ilk bağlantılı geçişte kurulur
        sync(op.get_bind(), metadata)


def downgrade():
    names = ', '.join(f"N'{n}'" for n, _, _ in NEW)
    op.execute(f"DELETE FROM {FD} WHERE TableName = N'{T}' AND FieldName IN ({names})")
    op.execute(f"UPDATE {FD} SET FieldName = N'OpenQty' WHERE TableName = N'{T}' AND FieldName = N'OpenQuantity'")
    op.drop_index(NEW_STG, table_name=T, schema='stg')
    op.drop_index(NEW_CORE, table_name=T, schema='core', mssql_where=WHERE)
    op.drop_constraint(op.f('FK_SalesOrderLine_Uom'), T, schema='core', type_='foreignkey')
    for schema in SCHEMAS:
        for name, _, _ in reversed(NEW):
            op.drop_column(T, name, schema=schema)
        op.alter_column(T, 'OpenQuantity', new_column_name='OpenQty', schema=schema)
    op.create_index(OLD_CORE, T, ['OrderNo', 'LineNo', 'LineItemNo'], unique=True, schema='stg')
    op.create_index(OLD_CORE, T, ['OrderNo', 'LineNo', 'LineItemNo'], unique=True, schema='core', mssql_where=WHERE)
