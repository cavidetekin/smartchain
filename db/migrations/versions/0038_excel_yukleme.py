"""0038 · Excel yükleme (K-129): stg tekil indeksleri kalkar; stg.SourceRowNo; ImportBatch alanları; ImportFinding; kanal adı Excel

Partiler ve ham veri korunur. Kanal adı iş satırlarında değişir; denetim izindeki eski kayıtlar değişmez.
Geri alışta ImportFinding ve yeni alanlar kaybolur; yeni durumlu partiler (Ön kontrol, Tamamlanmadı, Vazgeçildi) "Hatalı" olur.
Aynı anahtarlı stg satırı varsa geri alış durur; veri silinmez.

Revision ID: 0038
Revises: 0037
Create Date: 2026-11-05
"""
from alembic import op
import sqlalchemy as sa


revision = '0038'
down_revision = '0037'
branch_labels = None
depends_on = None

STG_UX = (
    ('BOM', 'UX_BOM_LocationCode_MaterialCode_Code_ComponentMaterialCode_OperationNo_SequenceNo', ['LocationCode', 'MaterialCode', 'Code', 'ComponentMaterialCode', 'OperationNo', 'SequenceNo']),
    ('BorrowPayback', 'UX_BorrowPayback_LocationCode_MaterialCode_LendingProjectCode_BorrowingProjectCode_BorrowDate', ['LocationCode', 'MaterialCode', 'LendingProjectCode', 'BorrowingProjectCode', 'BorrowDate']),
    ('Customer', 'UX_Customer_Code', ['Code']),
    ('EmployeeAbsence', 'UX_EmployeeAbsence_LocationCode_ResourceCode_AbsenceType_StartDate', ['LocationCode', 'ResourceCode', 'AbsenceType', 'StartDate']),
    ('Forecast', 'UX_Forecast_LocationCode_MaterialCode_CustomerCode_ProjectCode_Period_Type', ['LocationCode', 'MaterialCode', 'CustomerCode', 'ProjectCode', 'Period', 'Type']),
    ('Location', 'UX_Location_Code', ['Code']),
    ('Material', 'UX_Material_LocationCode_Code', ['LocationCode', 'Code']),
    ('MaterialReference', 'UX_MaterialReference_LocationCode_MaterialCode_ReferenceMaterialCode_ValidFrom', ['LocationCode', 'MaterialCode', 'ReferenceMaterialCode', 'ValidFrom']),
    ('MaterialSupplier', 'UX_MaterialSupplier_LocationCode_MaterialCode_SupplierCode', ['LocationCode', 'MaterialCode', 'SupplierCode']),
    ('ProductionConfirmation', 'UX_ProductionConfirmation_LocationCode_ConfirmationNo', ['LocationCode', 'ConfirmationNo']),
    ('ProductionVersion', 'UX_ProductionVersion_LocationCode_MaterialCode_Code', ['LocationCode', 'MaterialCode', 'Code']),
    ('Project', 'UX_Project_Code', ['Code']),
    ('ProjectGroup', 'UX_ProjectGroup_Code', ['Code']),
    ('PurchaseOrderLine', 'UX_PurchaseOrderLine_LocationCode_PurchaseOrderNo_LineNo', ['LocationCode', 'PurchaseOrderNo', 'LineNo']),
    ('Resource', 'UX_Resource_LocationCode_Code', ['LocationCode', 'Code']),
    ('ResourceGroup', 'UX_ResourceGroup_LocationCode_Code', ['LocationCode', 'Code']),
    ('ResourceGroupAssignment', 'UX_ResourceGroupAssignment_LocationCode_ResourceGroupCode_ResourceCode', ['LocationCode', 'ResourceGroupCode', 'ResourceCode']),
    ('Routing', 'UX_Routing_LocationCode_RouteCode_OperationNo_SequenceNo', ['LocationCode', 'RouteCode', 'OperationNo', 'SequenceNo']),
    ('SalesOrderLine', 'UX_SalesOrderLine_LocationCode_OrderNo_LineNo_LineItemNo', ['LocationCode', 'OrderNo', 'LineNo', 'LineItemNo']),
    ('Stock', 'UX_Stock_LocationCode_MaterialCode_Warehouse_LotNo_Status_ProjectCode_CustomerCode_SalesOrderNo_SalesOrderLineNo_SalesO_f3688038', ['LocationCode', 'MaterialCode', 'Warehouse', 'LotNo', 'Status', 'ProjectCode', 'CustomerCode', 'SalesOrderNo', 'SalesOrderLineNo', 'SalesOrderLineItemNo']),
    ('Supplier', 'UX_Supplier_Code', ['Code']),
    ('UomConversion', 'UX_UomConversion_MaterialCode_FromUom_ToUom', ['MaterialCode', 'FromUom', 'ToUom']),
    ('WorkOrder', 'UX_WorkOrder_LocationCode_WorkOrderNo', ['LocationCode', 'WorkOrderNo']),
    ('WorkOrderComponent', 'UX_WorkOrderComponent_LocationCode_WorkOrderNo_MaterialCode_OperationNo_SequenceNo', ['LocationCode', 'WorkOrderNo', 'MaterialCode', 'OperationNo', 'SequenceNo']),
    ('WorkOrderOperation', 'UX_WorkOrderOperation_LocationCode_WorkOrderNo_OperationNo_SequenceNo', ['LocationCode', 'WorkOrderNo', 'OperationNo', 'SequenceNo']),
)
STG_TABLES = ['BOM', 'BorrowPayback', 'Customer', 'EmployeeAbsence', 'Forecast', 'Location', 'Material', 'MaterialReference', 'MaterialSupplier', 'ProductionConfirmation', 'ProductionVersion', 'Project', 'ProjectGroup', 'PurchaseOrderLine', 'Resource', 'ResourceGroup', 'ResourceGroupAssignment', 'Routing', 'SalesOrderLine', 'Stock', 'Supplier', 'UomConversion', 'WorkOrder', 'WorkOrderComponent', 'WorkOrderOperation']
SOURCE_ROW = 'Kaynaktaki satır no'
STATUS_OLD = 'Alındı | Doğrulandı | Hatalı | Yüklendi'
STATUS_NEW = 'Ön kontrol | Alındı | Doğrulandı | Hatalı | Yüklendi | Tamamlanmadı | Vazgeçildi'
CHANNEL_OLD, CHANNEL_NEW = 'Gece | Hesaplama | Dışa aktarım', 'Gece | Hesaplama | Excel'
TYPE_OLD = 'Gece senaryosu | Çalışma | Yükleme | Termin sorgusu | Dışa aktarım …'
TYPE_NEW = 'Gece senaryosu | Çalışma | Yükleme | Termin sorgusu | Dışa aktarım | Excel ön kontrol …'
BATCH_OLD = 'Ham veri partisi: her yükleme parti numarası, zaman ve kaynakla. Ham veri bir hafta saklanır.'
BATCH_NEW = 'Ham veri partisi: her yükleme parti numarası, zaman ve kaynakla. Ham veri bir hafta saklanır. LoadType Değişen: arayüzde "Ekle / güncelle" (K-129).'
FINDING_COMMENT = 'Partinin bulguları: ön kontrol (fonksiyon 03) ve doğrulama (fonksiyon 04) aynı listeye yazar.'
BATCH_FIELDS = (
    ('UploadedBy', sa.Integer(), 'Yükleyen kullanıcı; Excel yüklemesinde dolu'),
    ('FileName', sa.Unicode(length=255), 'Yüklenen dosyanın adı'),
    ('FilePath', sa.Unicode(length=400), 'Sunucuda saklanan dosyanın yolu'),
    ('TemplateVersion', sa.Integer(), 'Dosyanın şablon sürümü'),
    ('JobId', sa.BigInteger(), 'Büyük dosyada ön kontrol işi'),
)


def _table_comment(schema, table, text):
    op.execute(f"EXEC sp_updateextendedproperty 'MS_Description', N'{text}', 'schema', '{schema}', 'table', '{table}'")


def upgrade():
    for table, name, _ in STG_UX:
        op.drop_index(name, table_name=table, schema='stg')
    for table in STG_TABLES:
        op.add_column(table, sa.Column('SourceRowNo', sa.Integer(), nullable=True, comment=SOURCE_ROW), schema='stg')
    for name, type_, comment in BATCH_FIELDS:
        op.add_column('ImportBatch', sa.Column(name, type_, nullable=True, comment=comment), schema='adm')
    op.create_foreign_key(op.f('FK_ImportBatch_UploadedBy'), 'ImportBatch', 'AppUser', ['UploadedBy'], ['Id'], source_schema='adm', referent_schema='adm')
    op.alter_column('ImportBatch', 'Status', existing_type=sa.Unicode(length=15), comment=STATUS_NEW, existing_comment=STATUS_OLD, existing_nullable=False, schema='adm')
    _table_comment('adm', 'ImportBatch', BATCH_NEW.replace("'", "''"))
    op.create_table(
        'ImportFinding',
        sa.Column('Id', sa.BigInteger(), autoincrement=True, nullable=False, comment='Kayıt kimliği'),
        sa.Column('ImportBatchId', sa.BigInteger(), nullable=False, comment='Parti'),
        sa.Column('RowNo', sa.Integer(), nullable=True, comment='Dosyadaki satır no; dosya düzeyi bulguda boş'),
        sa.Column('Severity', sa.Unicode(length=10), nullable=False, comment='Hata | Uyarı | Bilgi'),
        sa.Column('CheckCode', sa.Unicode(length=30), nullable=False, comment='Kontrolün kodu'),
        sa.Column('FieldName', sa.Unicode(length=200), nullable=True, comment='Alanın etiketi; tekrar eden anahtarda boş'),
        sa.Column('Value', sa.Unicode(length=255), nullable=True, comment='Dosyadaki değer'),
        sa.Column('Message', sa.Unicode(length=400), nullable=False, comment='Sorun'),
        sa.Column('RowKey', sa.Unicode(length=200), nullable=True, comment='Kaydın anahtarı'),
        sa.ForeignKeyConstraint(['ImportBatchId'], ['adm.ImportBatch.Id'], name=op.f('FK_ImportFinding_ImportBatchId')),
        sa.PrimaryKeyConstraint('Id', name=op.f('PK_ImportFinding')),
        schema='adm',
        comment=FINDING_COMMENT,
    )
    op.create_index(op.f('IX_ImportFinding_ImportBatchId'), 'ImportFinding', ['ImportBatchId'], unique=False, schema='adm')
    op.alter_column('Job', 'Channel', existing_type=sa.Unicode(length=15), comment=CHANNEL_NEW, existing_comment=CHANNEL_OLD, existing_nullable=False, schema='adm')
    op.alter_column('Job', 'JobType', existing_type=sa.Unicode(length=20), comment=TYPE_NEW, existing_comment=TYPE_OLD, existing_nullable=False, schema='adm')
    op.execute("UPDATE adm.Job SET Channel = N'Excel' WHERE Channel = N'Dışa aktarım'")


def downgrade():
    op.execute("UPDATE adm.Job SET Channel = N'Dışa aktarım' WHERE Channel = N'Excel'")
    op.execute("DELETE FROM adm.Job WHERE JobType = N'Excel ön kontrol'")
    op.alter_column('Job', 'JobType', existing_type=sa.Unicode(length=20), comment=TYPE_OLD, existing_comment=TYPE_NEW, existing_nullable=False, schema='adm')
    op.alter_column('Job', 'Channel', existing_type=sa.Unicode(length=15), comment=CHANNEL_OLD, existing_comment=CHANNEL_NEW, existing_nullable=False, schema='adm')
    op.drop_index(op.f('IX_ImportFinding_ImportBatchId'), table_name='ImportFinding', schema='adm')
    op.drop_table('ImportFinding', schema='adm')
    op.execute("UPDATE adm.ImportBatch SET Status = N'Hatalı' WHERE Status IN (N'Ön kontrol', N'Tamamlanmadı', N'Vazgeçildi')")
    _table_comment('adm', 'ImportBatch', BATCH_OLD)
    op.alter_column('ImportBatch', 'Status', existing_type=sa.Unicode(length=15), comment=STATUS_OLD, existing_comment=STATUS_NEW, existing_nullable=False, schema='adm')
    op.drop_constraint(op.f('FK_ImportBatch_UploadedBy'), 'ImportBatch', schema='adm', type_='foreignkey')
    for name, _, _ in reversed(BATCH_FIELDS):
        op.drop_column('ImportBatch', name, schema='adm')
    for table in STG_TABLES:
        op.drop_column(table, 'SourceRowNo', schema='stg')
    for table, name, columns in STG_UX:
        op.create_index(name, table, columns, unique=True, schema='stg')
