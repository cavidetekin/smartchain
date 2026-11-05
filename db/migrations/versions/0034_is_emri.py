"""0034 · İş emri, bileşen, operasyon (K-124): anahtarlar; ad değişiklikleri; tip ve durum ham değer; yeni alanlar

İş emri no, tip, durum ve miktarlar korunur; bileşen ve operasyonda LocationId iş emrinden gelir, iş emri bulunamazsa geçiş durur.
Yeni alanlar var olan satırlarda boş kalır; docs'ta varsayılanı olanlar (fire, lot bazlı, hayalet, fason, rol, kaynak adedi) varsayılanını alır; bayraklar doldurulmaz. stg ham veridir.
Aynı anahtarlı güncel satır varsa tekil indeks geçişi durdurur; veri silinmez.
Geri alışta yeni alanlar kaybolur, boş tip Üretim olur. 15 karakteri aşan tip ya da durum, kaynağı boş operasyon varsa geri alış durur; veri silinmez.

Revision ID: 0034
Revises: 0033
Create Date: 2026-11-05
"""
from alembic import context, op
import sqlalchemy as sa

from dictionary import sync
from models import metadata


revision = '0034'
down_revision = '0033'
branch_labels = None
depends_on = None

FD = 'adm.FieldDefinition'
SCHEMAS = ('core', 'stg')
WO, COMP, OPER = 'WorkOrder', 'WorkOrderComponent', 'WorkOrderOperation'
RENAMED = {
    WO: {'OrderNo': 'WorkOrderNo', 'OrderQty': 'OrderedQuantity', 'OpenQty': 'OpenQuantity'},
    COMP: {'RequiredQty': 'RequiredQuantity', 'IssuedQty': 'IssuedQuantity'},
    OPER: {'OpNo': 'OperationNo', 'SeqNo': 'SequenceNo'},
}
SHORT, LONG = sa.Unicode(length=15), sa.Unicode(length=50)
QTY, TIME = sa.Numeric(precision=18, scale=4), sa.Numeric(precision=9, scale=2)
WO_STATUS_OLD, WO_STATUS_NEW = 'Planlı | Yayınlandı | Başladı | Kısmi | Bitti', "ERP'den ham iş emri durumu; veri kurallarında kullanılır, değer listesi yok"
OP_STATUS_OLD, OP_STATUS_NEW = 'Açık | Bitti', "ERP'den ham operasyon durumu; veri kurallarında kullanılır, değer listesi yok"
TYPE_OLD, TYPE_NEW = 'Üretim | Fason | Yeniden işleme', "ERP'den ham iş emri tipi; veri kurallarında kullanılır, değer listesi yok"
PV = 'Üretim versiyonu; iş emrinin kendi bileşen ve operasyon satırları geldiyse motor onları kullanır, gelmediyse bu versiyonun ağacına ve rotasına gider'
WO_FIELDS = (
    ('Priority', sa.Integer(), 'İş emri önceliği'),
    ('CompletedQuantity', QTY, 'Tamamlanan miktar'),
    ('ScrapQuantity', QTY, 'Hurda miktarı'),
    ('Uom', sa.Unicode(length=10), 'Miktarların birimi; boşsa malzemenin temel biriminde kabul edilir, doluysa birim dönüşümüyle çevrilir'),
    ('IsFixed', sa.Boolean(), 'Motor bu iş emrinin tarihini ve miktarını değiştirmez'),
    ('IsReleased', sa.Boolean(), "İş emri yayınlandı; Status'tan veri kuralıyla doldurulur"),
    ('IsStarted', sa.Boolean(), "İş emri başladı; Status'tan veri kuralıyla doldurulur"),
    ('IsProduction', sa.Boolean(), "Üretim iş emri; ProductionOrderType'tan veri kuralıyla doldurulur"),
    ('IsSubcontract', sa.Boolean(), "Fason iş emri; ProductionOrderType'tan veri kuralıyla doldurulur"),
    ('IsRework', sa.Boolean(), "Yeniden işleme iş emri; ProductionOrderType'tan veri kuralıyla doldurulur"),
    ('IsOnHold', sa.Boolean(), 'Bekletilen iş emri'),
    ('IsCustomTracked', sa.Boolean(), 'İş emri düzeyinde özel takip'),
)
COMP_PLAIN = (
    ('OperationNo', sa.Integer(), 'Bağlı olduğu operasyon no (ihtiyaç tarihi için)'),
    ('SequenceNo', sa.Integer(), 'Sıra no; aynı bileşen iki kez geçerse operasyon no ile ayrışır'),
    ('UnitUsage', sa.Numeric(precision=18, scale=6), 'Üretilen bir birim için bileşen miktarı'),
    ('Uom', sa.Unicode(length=10), 'Bileşen miktarlarının birimi; boşsa bileşenin temel biriminde kabul edilir, doluysa birim dönüşümüyle çevrilir'),
)
COMP_ZERO = (  # core'da varsayılan 0
    ('ScrapRatio', sa.Numeric(precision=6, scale=4), 'Oran olarak fire (0,05 = %5)'),
    ('IsLotBasedUsage', sa.Boolean(), 'Doluysa bileşen üretilen miktardan bağımsız, her üretim lotu için sabit kullanılır; değilse birim başına'),
    ('IsPhantom', sa.Boolean(), 'Hayalet bileşen'),
)
ROLE = 'Primary | Secondary'
NUMBER = 'Operasyonda aynı anda kullanılan kaynak adedi'
OP_PLAIN = (
    ('OperationName', sa.Unicode(length=150), 'Operasyon adı'),
    ('IsCompleted', sa.Boolean(), "Operasyon tamamlandı; Status'tan veri kuralıyla doldurulur"),
    ('IsActive', sa.Boolean(), 'Operasyon plana dahil mi'),
    ('ProductionLocation', sa.Unicode(length=50), 'Lokasyonun alt tanımı (hol, hat); ileride kısıtlar için'),
    ('TransferQuantity', QTY, 'Transfer partisi'),
    ('WaitingTimeHours', TIME, 'Operasyon öncesi kuyruk beklemesi'),
    ('TransferTimeHours', TIME, 'Sonraki operasyona taşıma'),
)
OP_ZERO = (  # core'da varsayılan 0
    ('IsLotBasedUsage', sa.Boolean(), 'Doluysa tüketim üretilen miktardan bağımsız, lot başına sabit; pratikte hazırlık süresi'),
    ('IsSubcontracted', sa.Boolean(), 'Fason operasyon'),
)
OP_DEFAULT = (('ResourceRole', sa.Unicode(length=10), ROLE, "N'Primary'"), ('ResourceNumber', sa.Integer(), NUMBER, '1'))
WHERE = sa.text('VersionTo IS NULL')
OLD_UX = 'UX_WorkOrder_OrderNo'
WO_UX_CORE, WO_UX_STG = 'UX_WorkOrder_LocationId_WorkOrderNo', 'UX_WorkOrder_LocationCode_WorkOrderNo'
COMP_UX_CORE = 'UX_WorkOrderComponent_LocationId_WorkOrderId_MaterialId_OperationNo_SequenceNo'
COMP_UX_STG = 'UX_WorkOrderComponent_LocationCode_WorkOrderNo_MaterialCode_OperationNo_SequenceNo'
OP_UX_CORE = 'UX_WorkOrderOperation_LocationId_WorkOrderId_OperationNo_SequenceNo'
OP_UX_STG = 'UX_WorkOrderOperation_LocationCode_WorkOrderNo_OperationNo_SequenceNo'


def _add(table, fields, schema):
    for name, type_, comment in fields:
        op.add_column(table, sa.Column(name, type_, nullable=True, comment=comment), schema=schema)


def _add_location(table):
    op.add_column(table, sa.Column('LocationId', sa.Integer(), nullable=True, comment='Lokasyon'), schema='core')
    op.execute(f"UPDATE x SET LocationId = (SELECT TOP 1 w.LocationId FROM core.{WO} w WHERE w.Id = x.WorkOrderId ORDER BY w.VersionFrom DESC) FROM core.{table} x")
    op.alter_column(table, 'LocationId', existing_type=sa.Integer(), nullable=False, existing_comment='Lokasyon', schema='core')
    op.create_foreign_key(op.f(f'FK_{table}_LocationId'), table, 'Location', ['LocationId'], ['Id'], source_schema='core', referent_schema='core')
    op.add_column(table, sa.Column('LocationCode', sa.Unicode(length=30), nullable=True, comment='Lokasyon kodu'), schema='stg')


def _add_zero(table, fields):
    for name, type_, comment in fields:
        op.add_column(table, sa.Column(name, type_, server_default=sa.text('0'), nullable=True, comment=comment), schema='core')
        op.execute(f"UPDATE core.{table} SET {name} = 0")
        op.add_column(table, sa.Column(name, type_, nullable=True, comment=comment), schema='stg')


def upgrade():
    op.drop_index(OLD_UX, table_name=WO, schema='core', mssql_where=WHERE)
    op.drop_index(OLD_UX, table_name=WO, schema='stg')
    for table, pairs in RENAMED.items():
        for schema in SCHEMAS:
            for old, new in pairs.items():
                op.alter_column(table, old, new_column_name=new, schema=schema)

    # İş emri
    op.alter_column(WO, 'OrderType', existing_type=SHORT, server_default=None, existing_comment=TYPE_OLD, existing_nullable=False, schema='core')
    for schema in SCHEMAS:
        op.alter_column(WO, 'OrderType', new_column_name='ProductionOrderType', schema=schema)
        op.alter_column(WO, 'ProductionOrderType', existing_type=SHORT, type_=LONG, nullable=True, comment=TYPE_NEW, existing_comment=TYPE_OLD, schema=schema)
        op.alter_column(WO, 'Status', existing_type=SHORT, type_=LONG, comment=WO_STATUS_NEW, existing_comment=WO_STATUS_OLD, existing_nullable=schema == 'stg', schema=schema)
        _add(WO, WO_FIELDS, schema)
    op.add_column(WO, sa.Column('ProductionVersionId', sa.BigInteger(), nullable=True, comment=PV), schema='core')
    op.add_column(WO, sa.Column('CustomerId', sa.BigInteger(), nullable=True, comment='Müşteri'), schema='core')
    op.add_column(WO, sa.Column('ProductionVersionCode', sa.Unicode(length=30), nullable=True, comment=PV), schema='stg')
    op.add_column(WO, sa.Column('CustomerCode', sa.Unicode(length=50), nullable=True, comment='Müşteri'), schema='stg')
    op.create_foreign_key(op.f('FK_WorkOrder_Uom'), WO, 'UnitOfMeasure', ['Uom'], ['Code'], source_schema='core', referent_schema='core')
    op.create_index(op.f('IX_WorkOrder_ProductionVersionId'), WO, ['ProductionVersionId'], unique=False, schema='core')
    op.create_index(op.f('IX_WorkOrder_CustomerId'), WO, ['CustomerId'], unique=False, schema='core')
    op.create_index(WO_UX_CORE, WO, ['LocationId', 'WorkOrderNo'], unique=True, schema='core', mssql_where=WHERE)
    op.create_index(WO_UX_STG, WO, ['LocationCode', 'WorkOrderNo'], unique=True, schema='stg')

    # Bileşen
    _add_location(COMP)
    for schema in SCHEMAS:
        _add(COMP, COMP_PLAIN, schema)
    _add_zero(COMP, COMP_ZERO)
    op.create_foreign_key(op.f('FK_WorkOrderComponent_Uom'), COMP, 'UnitOfMeasure', ['Uom'], ['Code'], source_schema='core', referent_schema='core')
    op.create_index(COMP_UX_CORE, COMP, ['LocationId', 'WorkOrderId', 'MaterialId', 'OperationNo', 'SequenceNo'], unique=True, schema='core', mssql_where=WHERE)
    op.create_index(COMP_UX_STG, COMP, ['LocationCode', 'WorkOrderNo', 'MaterialCode', 'OperationNo', 'SequenceNo'], unique=True, schema='stg')

    # Operasyon
    _add_location(OPER)
    op.drop_index(op.f('IX_WorkOrderOperation_ResourceId'), table_name=OPER, schema='core')  # zorunluluk indeks varken değişmez
    op.alter_column(OPER, 'ResourceId', existing_type=sa.BigInteger(), nullable=True, existing_comment='Kaynak', schema='core')
    op.create_index(op.f('IX_WorkOrderOperation_ResourceId'), OPER, ['ResourceId'], unique=False, schema='core')
    op.add_column(OPER, sa.Column('ResourceGroupId', sa.BigInteger(), nullable=True, comment='Kaynak grubu'), schema='core')
    op.add_column(OPER, sa.Column('ResourceGroupCode', sa.Unicode(length=50), nullable=True, comment='Kaynak grubu'), schema='stg')
    for name, type_, comment, default in OP_DEFAULT:
        op.add_column(OPER, sa.Column(name, type_, server_default=sa.text(default), nullable=False, comment=comment), schema='core')
        op.add_column(OPER, sa.Column(name, type_, nullable=True, comment=comment), schema='stg')
    for schema in SCHEMAS:
        op.alter_column(OPER, 'Status', existing_type=SHORT, type_=LONG, comment=OP_STATUS_NEW, existing_comment=OP_STATUS_OLD, existing_nullable=True, schema=schema)
        _add(OPER, OP_PLAIN, schema)
    _add_zero(OPER, OP_ZERO)
    op.create_index(op.f('IX_WorkOrderOperation_ResourceGroupId'), OPER, ['ResourceGroupId'], unique=False, schema='core')
    op.create_index(OP_UX_CORE, OPER, ['LocationId', 'WorkOrderId', 'OperationNo', 'SequenceNo'], unique=True, schema='core', mssql_where=WHERE)
    op.create_index(OP_UX_STG, OPER, ['LocationCode', 'WorkOrderNo', 'OperationNo', 'SequenceNo'], unique=True, schema='stg')

    # Sözlük: elle verilen etiket yeni adda kalır; sync silmez, IsRequired ve DefaultValue'ya dokunmaz.
    for table, pairs in RENAMED.items():
        for old, new in pairs.items():
            op.execute(f"UPDATE {FD} SET FieldName = N'{new}' WHERE TableName = N'{table}' AND FieldName = N'{old}'")
    op.execute(f"UPDATE {FD} SET FieldName = N'ProductionOrderType', DefaultValue = NULL, IsRequired = 0 WHERE TableName = N'{WO}' AND FieldName = N'OrderType'")
    op.execute(f"UPDATE {FD} SET IsRequired = 0 WHERE TableName = N'{OPER}' AND FieldName = N'ResourceId'")
    if not context.is_offline_mode():  # bağlantısız SQL betiğinde satırlar yazılmaz; ilk bağlantılı geçişte kurulur
        sync(op.get_bind(), metadata)


def downgrade():
    wo_new = [n for n, _, _ in WO_FIELDS] + ['ProductionVersionId', 'CustomerId']
    comp_new = [n for n, _, _ in COMP_PLAIN + COMP_ZERO] + ['LocationId']
    op_new = [n for n, _, _ in OP_PLAIN + OP_ZERO] + [n for n, *_ in OP_DEFAULT] + ['LocationId', 'ResourceGroupId']
    for table, names in ((WO, wo_new), (COMP, comp_new), (OPER, op_new)):
        listed = ', '.join(f"N'{n}'" for n in names)
        op.execute(f"DELETE FROM {FD} WHERE TableName = N'{table}' AND FieldName IN ({listed})")
    for table, pairs in RENAMED.items():
        for old, new in pairs.items():
            op.execute(f"UPDATE {FD} SET FieldName = N'{old}' WHERE TableName = N'{table}' AND FieldName = N'{new}'")
    op.execute(f"UPDATE {FD} SET FieldName = N'OrderType', DefaultValue = N'Üretim', IsRequired = 1, Description = N'{TYPE_OLD}' WHERE TableName = N'{WO}' AND FieldName = N'ProductionOrderType'")
    op.execute(f"UPDATE {FD} SET Description = N'{WO_STATUS_OLD}' WHERE TableName = N'{WO}' AND FieldName = N'Status'")
    op.execute(f"UPDATE {FD} SET Description = N'{OP_STATUS_OLD}' WHERE TableName = N'{OPER}' AND FieldName = N'Status'")
    op.execute(f"UPDATE {FD} SET IsRequired = 1 WHERE TableName = N'{OPER}' AND FieldName = N'ResourceId'")
    op.execute(f"UPDATE {FD} SET StandardLabel = N'Operasyon içindeki alt sıra' WHERE TableName = N'{OPER}' AND FieldName = N'SeqNo'")

    # Operasyon
    op.drop_index(OP_UX_STG, table_name=OPER, schema='stg')
    op.drop_index(OP_UX_CORE, table_name=OPER, schema='core', mssql_where=WHERE)
    op.drop_index(op.f('IX_WorkOrderOperation_ResourceGroupId'), table_name=OPER, schema='core')
    op.drop_index(op.f('IX_WorkOrderOperation_ResourceId'), table_name=OPER, schema='core')
    op.alter_column(OPER, 'ResourceId', existing_type=sa.BigInteger(), nullable=False, existing_comment='Kaynak', schema='core')
    op.create_index(op.f('IX_WorkOrderOperation_ResourceId'), OPER, ['ResourceId'], unique=False, schema='core')
    op.drop_constraint(op.f('FK_WorkOrderOperation_LocationId'), OPER, schema='core', type_='foreignkey')
    for name, _, _ in OP_ZERO:
        op.drop_column(OPER, name, schema='core', mssql_drop_default=True)
        op.drop_column(OPER, name, schema='stg')
    for name, *_ in OP_DEFAULT:
        op.drop_column(OPER, name, schema='core', mssql_drop_default=True)
        op.drop_column(OPER, name, schema='stg')
    for schema in SCHEMAS:
        for name, _, _ in reversed(OP_PLAIN):
            op.drop_column(OPER, name, schema=schema)
        op.alter_column(OPER, 'Status', existing_type=LONG, type_=SHORT, comment=OP_STATUS_OLD, existing_comment=OP_STATUS_NEW, existing_nullable=True, schema=schema)
    op.drop_column(OPER, 'ResourceGroupId', schema='core')
    op.drop_column(OPER, 'ResourceGroupCode', schema='stg')
    op.drop_column(OPER, 'LocationId', schema='core')
    op.drop_column(OPER, 'LocationCode', schema='stg')

    # Bileşen
    op.drop_index(COMP_UX_STG, table_name=COMP, schema='stg')
    op.drop_index(COMP_UX_CORE, table_name=COMP, schema='core', mssql_where=WHERE)
    op.drop_constraint(op.f('FK_WorkOrderComponent_Uom'), COMP, schema='core', type_='foreignkey')
    op.drop_constraint(op.f('FK_WorkOrderComponent_LocationId'), COMP, schema='core', type_='foreignkey')
    for name, _, _ in COMP_ZERO:
        op.drop_column(COMP, name, schema='core', mssql_drop_default=True)
        op.drop_column(COMP, name, schema='stg')
    for schema in SCHEMAS:
        for name, _, _ in reversed(COMP_PLAIN):
            op.drop_column(COMP, name, schema=schema)
    op.drop_column(COMP, 'LocationId', schema='core')
    op.drop_column(COMP, 'LocationCode', schema='stg')

    # İş emri
    op.drop_index(WO_UX_STG, table_name=WO, schema='stg')
    op.drop_index(WO_UX_CORE, table_name=WO, schema='core', mssql_where=WHERE)
    op.drop_index(op.f('IX_WorkOrder_CustomerId'), table_name=WO, schema='core')
    op.drop_index(op.f('IX_WorkOrder_ProductionVersionId'), table_name=WO, schema='core')
    op.drop_constraint(op.f('FK_WorkOrder_Uom'), WO, schema='core', type_='foreignkey')
    op.drop_column(WO, 'ProductionVersionId', schema='core')
    op.drop_column(WO, 'CustomerId', schema='core')
    op.drop_column(WO, 'ProductionVersionCode', schema='stg')
    op.drop_column(WO, 'CustomerCode', schema='stg')
    op.execute(f"UPDATE core.{WO} SET ProductionOrderType = N'Üretim' WHERE ProductionOrderType IS NULL")
    for schema, nullable in (('core', False), ('stg', True)):
        for name, _, _ in reversed(WO_FIELDS):
            op.drop_column(WO, name, schema=schema)
        op.alter_column(WO, 'Status', existing_type=LONG, type_=SHORT, comment=WO_STATUS_OLD, existing_comment=WO_STATUS_NEW, existing_nullable=nullable, schema=schema)
        op.alter_column(WO, 'ProductionOrderType', existing_type=LONG, type_=SHORT, nullable=nullable, comment=TYPE_OLD, existing_comment=TYPE_NEW, schema=schema)
        op.alter_column(WO, 'ProductionOrderType', new_column_name='OrderType', schema=schema)
    op.alter_column(WO, 'OrderType', existing_type=SHORT, server_default=sa.text("N'Üretim'"), existing_comment=TYPE_OLD, existing_nullable=False, schema='core')

    for table, pairs in RENAMED.items():
        for schema in SCHEMAS:
            for old, new in pairs.items():
                op.alter_column(table, new, new_column_name=old, schema=schema)
    op.create_index(OLD_UX, WO, ['OrderNo'], unique=True, schema='stg')
    op.create_index(OLD_UX, WO, ['OrderNo'], unique=True, schema='core', mssql_where=WHERE)
