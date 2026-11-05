"""0035 · Satın alma siparişi ve üretim gerçekleşmesi (K-125): anahtarlar; ad değişiklikleri; tip ham değer; yeni alanlar; gerçekleşme iş emri bazlı

Satın alma: sipariş no, tip, açık miktar korunur; yeni alanlar boş kalır, bayraklar doldurulmaz.
Gerçekleşme: LocationId ve MaterialId iş emrinden gelir, iş emri bulunamazsa geçiş durur; eski satırlara numara üretilir (GEC-<Id>).
StartAt ve EndAt tarihe iner, saat kaybolur. OpNo, SeqNo, ResourceId ve ActualConsumption değerleri silinir; geri alışta geri gelmez, boş döner. stg ham veridir.
Aynı anahtarlı güncel satır varsa tekil indeks geçişi durdurur; veri silinmez. Geri alışta 20 karakteri aşan tip varsa durur; veri silinmez.

Revision ID: 0035
Revises: 0034
Create Date: 2026-11-05
"""
from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql

from dictionary import sync
from models import metadata


revision = '0035'
down_revision = '0034'
branch_labels = None
depends_on = None

FD = 'adm.FieldDefinition'
SCHEMAS = ('core', 'stg')
PO, PC = 'PurchaseOrderLine', 'ProductionConfirmation'
QTY = sa.Numeric(precision=18, scale=4)
OLD_TYPE, NEW_TYPE = sa.Unicode(length=20), sa.Unicode(length=50)
TYPE_OLD = 'Satın alma talebi | Satın alma | Fason'
TYPE_NEW = "ERP'den ham sipariş tipi; veri kurallarında kullanılır, değer listesi yok"
PO_RENAMED = {'OrderNo': 'PurchaseOrderNo', 'OpenQty': 'OpenQuantity'}
PO_FIELDS = (
    ('OrderedQuantity', QTY, 'Sipariş miktarı'),
    ('ReceivedQuantity', QTY, 'Teslim alınan miktar'),
    ('Uom', sa.Unicode(length=10), 'Miktarların birimi; boşsa malzemenin temel biriminde kabul edilir, doluysa birim dönüşümüyle çevrilir'),
    ('IsPurchaseRequest', sa.Boolean(), "Satın alma talebi; OrderType'tan veri kuralıyla doldurulur"),
    ('IsPurchase', sa.Boolean(), "Satın alma siparişi; OrderType'tan veri kuralıyla doldurulur"),
    ('IsSubcontract', sa.Boolean(), "Fason siparişi; OrderType'tan veri kuralıyla doldurulur"),
    ('IsActive', sa.Boolean(), 'Aktif mi'),
    ('IsCustomTracked', sa.Boolean(), 'Satır düzeyinde özel takip'),
)
PO_CORE = (('CustomerId', sa.BigInteger(), 'Müşteri'), ('SalesOrderLineId', sa.BigInteger(), 'Bağlı sipariş satırı'))
PO_STG = (('CustomerCode', sa.Unicode(length=50), 'Müşteri'), ('SalesOrderNo', sa.Unicode(length=30), 'Bağlı sipariş no'), ('SalesOrderLineNo', sa.Integer(), 'Bağlı sipariş satırı'))
OLD_PO_UX = 'UX_PurchaseOrderLine_OrderNo_LineNo'
PO_UX_CORE, PO_UX_STG = 'UX_PurchaseOrderLine_LocationId_PurchaseOrderNo_LineNo', 'UX_PurchaseOrderLine_LocationCode_PurchaseOrderNo_LineNo'
PC_RENAMED = {'ConfirmedQty': 'ConfirmedQuantity'}
PC_DATES = {'StartAt': ('StartDate', 'Başlangıç'), 'EndAt': ('EndDate', 'Bitiş')}
PC_UX_CORE, PC_UX_STG = 'UX_ProductionConfirmation_LocationId_ConfirmationNo', 'UX_ProductionConfirmation_LocationCode_ConfirmationNo'
NUMBER = sa.Unicode(length=30)
WHERE = sa.text('VersionTo IS NULL')
DROPPED = (('OpNo', sa.Integer(), 'Operasyon no', 'Operasyon no'),
           ('SeqNo', sa.Integer(), 'Operasyon içindeki alt sıra', 'Operasyon içindeki alt sıra'),
           ('ActualConsumption', sa.Numeric(precision=18, scale=6), 'Gerçekleşen tüketim (süre)', 'Gerçekleşen tüketim'))


def upgrade():
    # Satın alma
    op.drop_index(OLD_PO_UX, table_name=PO, schema='core', mssql_where=WHERE)
    op.drop_index(OLD_PO_UX, table_name=PO, schema='stg')
    for schema in SCHEMAS:
        for old, new in PO_RENAMED.items():
            op.alter_column(PO, old, new_column_name=new, schema=schema)
        op.alter_column(PO, 'OrderType', existing_type=OLD_TYPE, type_=NEW_TYPE, comment=TYPE_NEW, existing_comment=TYPE_OLD, existing_nullable=schema == 'stg', schema=schema)
        for name, type_, comment in PO_FIELDS + (PO_CORE if schema == 'core' else PO_STG):
            op.add_column(PO, sa.Column(name, type_, nullable=True, comment=comment), schema=schema)
    op.create_foreign_key(op.f('FK_PurchaseOrderLine_Uom'), PO, 'UnitOfMeasure', ['Uom'], ['Code'], source_schema='core', referent_schema='core')
    op.create_index(op.f('IX_PurchaseOrderLine_CustomerId'), PO, ['CustomerId'], unique=False, schema='core')
    op.create_index(op.f('IX_PurchaseOrderLine_SalesOrderLineId'), PO, ['SalesOrderLineId'], unique=False, schema='core')
    op.create_index(PO_UX_CORE, PO, ['LocationId', 'PurchaseOrderNo', 'LineNo'], unique=True, schema='core', mssql_where=WHERE)
    op.create_index(PO_UX_STG, PO, ['LocationCode', 'PurchaseOrderNo', 'LineNo'], unique=True, schema='stg')

    # Üretim gerçekleşmesi
    op.add_column(PC, sa.Column('LocationId', sa.Integer(), nullable=True, comment='Lokasyon'), schema='core')
    op.add_column(PC, sa.Column('MaterialId', sa.BigInteger(), nullable=True, comment='Üretilen malzeme'), schema='core')
    op.add_column(PC, sa.Column('ConfirmationNo', NUMBER, nullable=True, comment='Teyit no'), schema='core')
    for column in ('LocationId', 'MaterialId'):
        op.execute(f"UPDATE x SET {column} = (SELECT TOP 1 w.{column} FROM core.WorkOrder w WHERE w.Id = x.WorkOrderId ORDER BY w.VersionFrom DESC) FROM core.{PC} x")
    op.execute(f"UPDATE core.{PC} SET ConfirmationNo = N'GEC-' + CAST(Id AS nvarchar(20))")
    op.alter_column(PC, 'LocationId', existing_type=sa.Integer(), nullable=False, existing_comment='Lokasyon', schema='core')
    op.alter_column(PC, 'MaterialId', existing_type=sa.BigInteger(), nullable=False, existing_comment='Üretilen malzeme', schema='core')
    op.alter_column(PC, 'ConfirmationNo', existing_type=NUMBER, nullable=False, existing_comment='Teyit no', schema='core')
    op.create_foreign_key(op.f('FK_ProductionConfirmation_LocationId'), PC, 'Location', ['LocationId'], ['Id'], source_schema='core', referent_schema='core')
    op.add_column(PC, sa.Column('LocationCode', sa.Unicode(length=30), nullable=True, comment='Lokasyon kodu'), schema='stg')
    op.add_column(PC, sa.Column('ConfirmationNo', NUMBER, nullable=True, comment='Teyit no'), schema='stg')
    op.add_column(PC, sa.Column('MaterialCode', sa.Unicode(length=50), nullable=True, comment='Üretilen malzeme'), schema='stg')
    op.drop_index(op.f('IX_ProductionConfirmation_ResourceId'), table_name=PC, schema='core')
    op.drop_column(PC, 'ResourceId', schema='core')
    op.drop_column(PC, 'ResourceCode', schema='stg')
    for schema in SCHEMAS:
        for name, *_ in DROPPED:
            op.drop_column(PC, name, schema=schema)
        for old, new in PC_RENAMED.items():
            op.alter_column(PC, old, new_column_name=new, schema=schema)
        for old, (new, comment) in PC_DATES.items():
            op.alter_column(PC, old, new_column_name=new, schema=schema)
            op.alter_column(PC, new, existing_type=mssql.DATETIME2(), type_=sa.Date(), existing_comment=comment, existing_nullable=True, schema=schema)
    op.create_index(op.f('IX_ProductionConfirmation_MaterialId'), PC, ['MaterialId'], unique=False, schema='core')
    op.create_index(PC_UX_CORE, PC, ['LocationId', 'ConfirmationNo'], unique=True, schema='core', mssql_where=WHERE)
    op.create_index(PC_UX_STG, PC, ['LocationCode', 'ConfirmationNo'], unique=True, schema='stg')

    # Sözlük: elle verilen etiket yeni adda kalır; sync silmez.
    for old, new in PO_RENAMED.items():
        op.execute(f"UPDATE {FD} SET FieldName = N'{new}' WHERE TableName = N'{PO}' AND FieldName = N'{old}'")
    for old, new in PC_RENAMED.items():
        op.execute(f"UPDATE {FD} SET FieldName = N'{new}' WHERE TableName = N'{PC}' AND FieldName = N'{old}'")
    for old, (new, _) in PC_DATES.items():
        op.execute(f"UPDATE {FD} SET FieldName = N'{new}' WHERE TableName = N'{PC}' AND FieldName = N'{old}'")
    listed = ', '.join(f"N'{n}'" for n, *_ in DROPPED)
    op.execute(f"DELETE FROM {FD} WHERE TableName = N'{PC}' AND FieldName IN ({listed}, N'ResourceId')")
    if not context.is_offline_mode():  # bağlantısız SQL betiğinde satırlar yazılmaz; ilk bağlantılı geçişte kurulur
        sync(op.get_bind(), metadata)


def downgrade():
    po_new = ', '.join(f"N'{n}'" for n, _, _ in PO_FIELDS + PO_CORE)
    op.execute(f"DELETE FROM {FD} WHERE TableName = N'{PO}' AND FieldName IN ({po_new})")
    for old, new in PO_RENAMED.items():
        op.execute(f"UPDATE {FD} SET FieldName = N'{old}' WHERE TableName = N'{PO}' AND FieldName = N'{new}'")
    op.execute(f"UPDATE {FD} SET Description = N'{TYPE_OLD}' WHERE TableName = N'{PO}' AND FieldName = N'OrderType'")
    op.execute(f"DELETE FROM {FD} WHERE TableName = N'{PC}' AND FieldName IN (N'LocationId', N'ConfirmationNo', N'MaterialId')")
    for old, new in PC_RENAMED.items():
        op.execute(f"UPDATE {FD} SET FieldName = N'{old}' WHERE TableName = N'{PC}' AND FieldName = N'{new}'")
    for old, (new, _) in PC_DATES.items():
        op.execute(f"UPDATE {FD} SET FieldName = N'{old}' WHERE TableName = N'{PC}' AND FieldName = N'{new}'")
    for name, _, comment, label in DROPPED:
        op.execute(f"INSERT INTO {FD} (TableName, FieldName, FieldClass, StandardLabel, Description) VALUES (N'{PC}', N'{name}', N'İşlem verisi', N'{label}', N'{comment}')")
    op.execute(f"INSERT INTO {FD} (TableName, FieldName, FieldClass, StandardLabel, Description) VALUES (N'{PC}', N'ResourceId', N'İşlem verisi', N'Kaynak', N'Kaynak')")

    # Üretim gerçekleşmesi
    op.drop_index(PC_UX_STG, table_name=PC, schema='stg')
    op.drop_index(PC_UX_CORE, table_name=PC, schema='core', mssql_where=WHERE)
    op.drop_index(op.f('IX_ProductionConfirmation_MaterialId'), table_name=PC, schema='core')
    op.drop_constraint(op.f('FK_ProductionConfirmation_LocationId'), PC, schema='core', type_='foreignkey')
    for schema in SCHEMAS:
        for old, (new, comment) in PC_DATES.items():
            op.alter_column(PC, new, existing_type=sa.Date(), type_=mssql.DATETIME2(), existing_comment=comment, existing_nullable=True, schema=schema)
            op.alter_column(PC, new, new_column_name=old, schema=schema)
        for old, new in PC_RENAMED.items():
            op.alter_column(PC, new, new_column_name=old, schema=schema)
        for name, type_, comment, _ in DROPPED:
            op.add_column(PC, sa.Column(name, type_, nullable=True, comment=comment), schema=schema)
    op.add_column(PC, sa.Column('ResourceId', sa.BigInteger(), nullable=True, comment='Kaynak'), schema='core')
    op.add_column(PC, sa.Column('ResourceCode', sa.Unicode(length=50), nullable=True, comment='Kaynak kodu'), schema='stg')
    op.create_index(op.f('IX_ProductionConfirmation_ResourceId'), PC, ['ResourceId'], unique=False, schema='core')
    for column in ('LocationId', 'MaterialId', 'ConfirmationNo'):
        op.drop_column(PC, column, schema='core')
    for column in ('LocationCode', 'ConfirmationNo', 'MaterialCode'):
        op.drop_column(PC, column, schema='stg')

    # Satın alma
    op.drop_index(PO_UX_STG, table_name=PO, schema='stg')
    op.drop_index(PO_UX_CORE, table_name=PO, schema='core', mssql_where=WHERE)
    op.drop_index(op.f('IX_PurchaseOrderLine_SalesOrderLineId'), table_name=PO, schema='core')
    op.drop_index(op.f('IX_PurchaseOrderLine_CustomerId'), table_name=PO, schema='core')
    op.drop_constraint(op.f('FK_PurchaseOrderLine_Uom'), PO, schema='core', type_='foreignkey')
    for schema in SCHEMAS:
        for name, _, _ in reversed(PO_FIELDS + (PO_CORE if schema == 'core' else PO_STG)):
            op.drop_column(PO, name, schema=schema)
        op.alter_column(PO, 'OrderType', existing_type=NEW_TYPE, type_=OLD_TYPE, comment=TYPE_OLD, existing_comment=TYPE_NEW, existing_nullable=schema == 'stg', schema=schema)
        for old, new in PO_RENAMED.items():
            op.alter_column(PO, new, new_column_name=old, schema=schema)
    op.create_index(OLD_PO_UX, PO, ['OrderNo', 'LineNo'], unique=True, schema='stg')
    op.create_index(OLD_PO_UX, PO, ['OrderNo', 'LineNo'], unique=True, schema='core', mssql_where=WHERE)
