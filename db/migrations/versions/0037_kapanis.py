"""0037 · 3.1b kapanışı (K-127, K-128): IsQuote; ham alanlar nvarchar(50), zorunlu değil, listesiz; SalesOrderLineItemNo; RemainingQuantity; tablo açıklamaları

Var olan satırların değerleri korunur; IsQuote boş kalır, doldurulmaz. stg ham veridir.
Aynı anahtarlı stg.Stock satırı varsa tekil indeks geçişi durdurur; veri silinmez.
Geri alışta boş satış sipariş tipi Kesin olur. Boş durum ya da tip, 15 karakteri (tipte 10) aşan değer varsa geri alış durur; veri silinmez.

Revision ID: 0037
Revises: 0036
Create Date: 2026-11-05
"""
from alembic import context, op
import sqlalchemy as sa

from dictionary import sync
from models import metadata


revision = '0037'
down_revision = '0036'
branch_labels = None
depends_on = None

FD = 'adm.FieldDefinition'
SCHEMAS = ('core', 'stg')
SO, PO, WO, STOCK, COMP, PC = 'SalesOrderLine', 'PurchaseOrderLine', 'WorkOrder', 'Stock', 'WorkOrderComponent', 'ProductionConfirmation'
LONG = sa.Unicode(length=50)
TYPE_NEW = "ERP'den ham sipariş tipi; veri kurallarında kullanılır, değer listesi yok"
STATUS_NEW = "ERP'den ham sipariş durumu; veri kurallarında kullanılır, değer listesi yok"
WO_STATUS = "ERP'den ham iş emri durumu; veri kurallarında kullanılır, değer listesi yok"
SO_TYPE_OLD, SO_STATUS_OLD, PO_STATUS_OLD = 'Kesin | Teklif', 'Açık | Kapandı | İptal', 'Durum'
QUOTE = "Teklif satırı; Type'tan veri kuralıyla doldurulur"
ITEM = 'Bağlı sipariş alt satırı'
OWNER_OLD, OWNER_NEW = 'Sahip proje (boşsa ortak)', 'Sahip proje; proje, müşteri ve sipariş boşsa stok ortaktır'
STOCK_UX_OLD = 'UX_Stock_LocationCode_MaterialCode_Warehouse_LotNo_Status_ProjectCode_CustomerCode_SalesOrderNo_SalesOrderLineNo'
STOCK_UX_NEW = 'UX_Stock_LocationCode_MaterialCode_Warehouse_LotNo_Status_ProjectCode_CustomerCode_SalesOrderNo_SalesOrderLineNo_SalesO_f3688038'
STOCK_KEY = ['LocationCode', 'MaterialCode', 'Warehouse', 'LotNo', 'Status', 'ProjectCode', 'CustomerCode', 'SalesOrderNo', 'SalesOrderLineNo']
COMMENTS = (  # şema, tablo, eski, yeni
    ('core', SO, 'Müşteri sipariş satırı; teklifler Type = Teklif ile gelir, plana dahil olmaları senaryo parametresi. Vade: teyit tarihi, yoksa istek tarihi.',
     'Müşteri sipariş satırı; teklifler IsQuote ile okunur, plana dahil olmaları senaryo parametresi. Vade: teyit tarihi, yoksa istek tarihi.'),
    ('stg', SO, 'Müşteri sipariş satırı; teklifler Type = Teklif ile gelir. Vade: teyit tarihi, yoksa istek tarihi.',
     'Müşteri sipariş satırı; teklifler IsQuote ile okunur. Vade: teyit tarihi, yoksa istek tarihi.'),
) + tuple((s, STOCK, 'Stok; lot ve durum bazında. Sahip: proje ya da ortak.', 'Stok; lot ve durum bazında. Sahip: proje, müşteri, sipariş ya da ortak.') for s in SCHEMAS) \
  + tuple((s, PC, 'Üretim gerçekleşmeleri; ilk günden tutulur (verim önerisi ve ileriki fazlar).', 'Üretim gerçekleşmeleri: iş emri bazında stoğa girişler.') for s in SCHEMAS)


def _table_comment(schema, table, text):
    op.execute(f"EXEC sp_updateextendedproperty 'MS_Description', N'{text}', 'schema', '{schema}', 'table', '{table}'")


def upgrade():
    # Satış siparişi
    op.alter_column(SO, 'Type', existing_type=sa.Unicode(length=10), server_default=None, existing_comment=SO_TYPE_OLD, existing_nullable=False, schema='core')
    for schema in SCHEMAS:
        op.alter_column(SO, 'Type', existing_type=sa.Unicode(length=10), type_=LONG, nullable=True, comment=TYPE_NEW, existing_comment=SO_TYPE_OLD, schema=schema)
        op.alter_column(SO, 'Status', existing_type=sa.Unicode(length=15), type_=LONG, nullable=True, comment=STATUS_NEW, existing_comment=SO_STATUS_OLD, schema=schema)
        op.add_column(SO, sa.Column('IsQuote', sa.Boolean(), nullable=True, comment=QUOTE), schema=schema)

    # İş emri ve satın alma
    op.alter_column(WO, 'Status', existing_type=LONG, nullable=True, existing_comment=WO_STATUS, schema='core')
    op.alter_column(PO, 'OrderType', existing_type=LONG, nullable=True, existing_comment=TYPE_NEW, schema='core')
    for schema in SCHEMAS:
        op.alter_column(PO, 'Status', existing_type=sa.Unicode(length=15), type_=LONG, nullable=True, comment=STATUS_NEW, existing_comment=PO_STATUS_OLD, schema=schema)

    # Sipariş bağı (core'da SalesOrderLineId; K-120)
    for table in (WO, PO, STOCK):
        op.add_column(table, sa.Column('SalesOrderLineItemNo', sa.Integer(), nullable=True, comment=ITEM), schema='stg')
    op.drop_index(STOCK_UX_OLD, table_name=STOCK, schema='stg')
    op.create_index(STOCK_UX_NEW, STOCK, STOCK_KEY + ['SalesOrderLineItemNo'], unique=True, schema='stg')

    # Metinler ve ad
    op.alter_column(STOCK, 'ProjectId', existing_type=sa.BigInteger(), comment=OWNER_NEW, existing_comment=OWNER_OLD, existing_nullable=True, schema='core')
    op.alter_column(STOCK, 'ProjectCode', existing_type=sa.Unicode(length=50), comment=OWNER_NEW, existing_comment=OWNER_OLD, existing_nullable=True, schema='stg')
    for schema, table, _, new in COMMENTS:
        _table_comment(schema, table, new)
    op.alter_column(COMP, 'RemainingQty', new_column_name='RemainingQuantity', schema='core')

    # Sözlük: elle verilen etiket yeni adda kalır; sync IsRequired ve DefaultValue'ya dokunmaz.
    op.execute(f"UPDATE {FD} SET FieldName = N'RemainingQuantity' WHERE TableName = N'{COMP}' AND FieldName = N'RemainingQty'")
    op.execute(f"UPDATE {FD} SET DefaultValue = NULL, IsRequired = 0 WHERE TableName = N'{SO}' AND FieldName = N'Type'")
    for table, field in ((SO, 'Status'), (WO, 'Status'), (PO, 'Status'), (PO, 'OrderType')):
        op.execute(f"UPDATE {FD} SET IsRequired = 0 WHERE TableName = N'{table}' AND FieldName = N'{field}'")
    if not context.is_offline_mode():  # bağlantısız SQL betiğinde satırlar yazılmaz; ilk bağlantılı geçişte kurulur
        sync(op.get_bind(), metadata)


def downgrade():
    op.execute(f"DELETE FROM {FD} WHERE TableName = N'{SO}' AND FieldName = N'IsQuote'")
    op.execute(f"UPDATE {FD} SET FieldName = N'RemainingQty' WHERE TableName = N'{COMP}' AND FieldName = N'RemainingQuantity'")
    op.execute(f"UPDATE {FD} SET DefaultValue = N'Kesin', IsRequired = 1, Description = N'{SO_TYPE_OLD}' WHERE TableName = N'{SO}' AND FieldName = N'Type'")
    op.execute(f"UPDATE {FD} SET IsRequired = 1, Description = N'{SO_STATUS_OLD}' WHERE TableName = N'{SO}' AND FieldName = N'Status'")
    op.execute(f"UPDATE {FD} SET IsRequired = 1 WHERE TableName = N'{WO}' AND FieldName = N'Status'")
    op.execute(f"UPDATE {FD} SET IsRequired = 1, Description = N'{PO_STATUS_OLD}' WHERE TableName = N'{PO}' AND FieldName = N'Status'")
    op.execute(f"UPDATE {FD} SET IsRequired = 1 WHERE TableName = N'{PO}' AND FieldName = N'OrderType'")
    op.execute(f"UPDATE {FD} SET Description = N'{OWNER_OLD}' WHERE TableName = N'{STOCK}' AND FieldName = N'ProjectId'")

    op.alter_column(COMP, 'RemainingQuantity', new_column_name='RemainingQty', schema='core')
    for schema, table, old, _ in COMMENTS:
        _table_comment(schema, table, old)
    op.alter_column(STOCK, 'ProjectId', existing_type=sa.BigInteger(), comment=OWNER_OLD, existing_comment=OWNER_NEW, existing_nullable=True, schema='core')
    op.alter_column(STOCK, 'ProjectCode', existing_type=sa.Unicode(length=50), comment=OWNER_OLD, existing_comment=OWNER_NEW, existing_nullable=True, schema='stg')

    op.drop_index(STOCK_UX_NEW, table_name=STOCK, schema='stg')
    op.create_index(STOCK_UX_OLD, STOCK, STOCK_KEY, unique=True, schema='stg')
    for table in (WO, PO, STOCK):
        op.drop_column(table, 'SalesOrderLineItemNo', schema='stg')

    for schema, nullable in (('core', False), ('stg', True)):
        op.alter_column(PO, 'Status', existing_type=LONG, type_=sa.Unicode(length=15), nullable=nullable, comment=PO_STATUS_OLD, existing_comment=STATUS_NEW, schema=schema)
    op.alter_column(PO, 'OrderType', existing_type=LONG, nullable=False, existing_comment=TYPE_NEW, schema='core')
    op.alter_column(WO, 'Status', existing_type=LONG, nullable=False, existing_comment=WO_STATUS, schema='core')

    op.execute(f"UPDATE core.{SO} SET Type = N'Kesin' WHERE Type IS NULL")
    for schema, nullable in (('core', False), ('stg', True)):
        op.drop_column(SO, 'IsQuote', schema=schema)
        op.alter_column(SO, 'Status', existing_type=LONG, type_=sa.Unicode(length=15), nullable=nullable, comment=SO_STATUS_OLD, existing_comment=STATUS_NEW, schema=schema)
        op.alter_column(SO, 'Type', existing_type=LONG, type_=sa.Unicode(length=10), nullable=nullable, comment=SO_TYPE_OLD, existing_comment=TYPE_NEW, schema=schema)
    op.alter_column(SO, 'Type', existing_type=sa.Unicode(length=10), server_default=sa.text("N'Kesin'"), existing_comment=SO_TYPE_OLD, existing_nullable=False, schema='core')
