"""0003 · Plan çıktı tabloları versiyonsuz: Id IDENTITY, versiyon alanları kalkar (K-70)

PlannedOrder, SupplyRecommendation, DemandFulfillment, CapacityLoad, Pegging, PlanWarning.
SQL Server var olan kolona IDENTITY ekleyemediği için tablolar düşürülüp yeniden kurulur;
tablolar henüz boştur (motor 0.5'te geliyor). Doluysa geçiş durur, veri kaybolmaz.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

TABLES = ["PlannedOrder", "SupplyRecommendation", "DemandFulfillment", "CapacityLoad", "Pegging", "PlanWarning"]


def _require_empty():
    for t in TABLES:
        op.execute(f"IF EXISTS (SELECT 1 FROM planning.[{t}]) "
                   f"THROW 50000, N'planning.{t} boş değil; 0003 geçişi veri silmez.', 1")


def upgrade():
    _require_empty()
    op.drop_table('PlanWarning', schema='planning')
    op.drop_table('Pegging', schema='planning')
    op.drop_table('CapacityLoad', schema='planning')
    op.drop_table('DemandFulfillment', schema='planning')
    op.drop_table('SupplyRecommendation', schema='planning')
    op.drop_table('PlannedOrder', schema='planning')
    op.create_table('PlannedOrder',
    sa.Column('Id', sa.BigInteger(), autoincrement=True, nullable=False, comment='Kayıt kimliği'),
    sa.Column('PlanRunId', sa.BigInteger(), nullable=False, comment='Plan hesabı'),
    sa.Column('MaterialId', sa.BigInteger(), nullable=False, comment='Malzeme'),
    sa.Column('OrderType', sa.Unicode(length=15), nullable=False, comment='Üretim | Satın alma | Fason'),
    sa.Column('SupplierId', sa.BigInteger(), nullable=True, comment='Tedarikçi'),
    sa.Column('ProjectId', sa.BigInteger(), nullable=True, comment='Proje (sahip)'),
    sa.Column('Quantity', sa.Numeric(precision=18, scale=4), nullable=False, comment='Motorun miktarı (sürekli)'),
    sa.Column('RoundedQty', sa.Numeric(precision=18, scale=4), nullable=True, comment='Yuvarlanmış miktar (son hesap)'),
    sa.Column('StartDate', sa.DATE(), nullable=True, comment='Başlangıç'),
    sa.Column('DueDate', sa.DATE(), nullable=False, comment='Bitiş'),
    sa.Column('BucketStart', sa.DATE(), nullable=True, comment='Dönem'),
    sa.Column('UpdatedAt', mssql.DATETIME2(), nullable=False, comment='Yazılma zamanı (UTC)'),
    sa.ForeignKeyConstraint(['PlanRunId'], ['planning.PlanRun.Id'], name=op.f('FK_PlannedOrder_PlanRunId')),
    sa.PrimaryKeyConstraint('Id', name=op.f('PK_PlannedOrder')),
    schema='planning',
    comment='Planlı sipariş: üretim, satın alma ya da fason önerisi. Satın alma sürekli hesaplanır, yuvarlanmış miktar ayrıca.'
    )
    op.create_index(op.f('IX_PlannedOrder_MaterialId'), 'PlannedOrder', ['MaterialId'], unique=False, schema='planning')
    op.create_index(op.f('IX_PlannedOrder_ProjectId'), 'PlannedOrder', ['ProjectId'], unique=False, schema='planning')
    op.create_index(op.f('IX_PlannedOrder_SupplierId'), 'PlannedOrder', ['SupplierId'], unique=False, schema='planning')
    op.create_table('SupplyRecommendation',
    sa.Column('Id', sa.BigInteger(), autoincrement=True, nullable=False, comment='Kayıt kimliği'),
    sa.Column('PlanRunId', sa.BigInteger(), nullable=False, comment='Plan hesabı'),
    sa.Column('SupplyType', sa.Unicode(length=15), nullable=False, comment='İş emri | Satın alma | Fason | Transfer'),
    sa.Column('SupplyId', sa.BigInteger(), nullable=False, comment='Arz kaydı'),
    sa.Column('Action', sa.Unicode(length=15), nullable=False, comment='Öne çek | Ertele | İptal | Azalt | Hızlandır'),
    sa.Column('CurrentDate', sa.DATE(), nullable=True, comment='Mevcut tarih'),
    sa.Column('ProposedDate', sa.DATE(), nullable=True, comment='Önerilen tarih'),
    sa.Column('ProposedQty', sa.Numeric(precision=18, scale=4), nullable=True, comment='Önerilen miktar'),
    sa.Column('UpdatedAt', mssql.DATETIME2(), nullable=False, comment='Yazılma zamanı (UTC)'),
    sa.ForeignKeyConstraint(['PlanRunId'], ['planning.PlanRun.Id'], name=op.f('FK_SupplyRecommendation_PlanRunId')),
    sa.PrimaryKeyConstraint('Id', name=op.f('PK_SupplyRecommendation')),
    schema='planning',
    comment='Mevcut arz için öneri: öne çek, ertele, iptal, azalt, hızlandır.'
    )
    op.create_table('DemandFulfillment',
    sa.Column('Id', sa.BigInteger(), autoincrement=True, nullable=False, comment='Kayıt kimliği'),
    sa.Column('PlanRunId', sa.BigInteger(), nullable=False, comment='Plan hesabı'),
    sa.Column('DemandType', sa.Unicode(length=15), nullable=False, comment='Sipariş | Tahmin | Teklif | Güvenlik stoğu'),
    sa.Column('DemandId', sa.BigInteger(), nullable=False, comment='Talep kaydı'),
    sa.Column('DueDate', sa.DATE(), nullable=True, comment='Vade'),
    sa.Column('PlannedDate', sa.DATE(), nullable=True, comment='Planlanan karşılama'),
    sa.Column('ShortQty', sa.Numeric(precision=18, scale=4), nullable=True, comment='Karşılanamayan miktar'),
    sa.Column('DelayDays', sa.Integer(), nullable=True, comment='Gecikme (gün)'),
    sa.Column('UpdatedAt', mssql.DATETIME2(), nullable=False, comment='Yazılma zamanı (UTC)'),
    sa.ForeignKeyConstraint(['PlanRunId'], ['planning.PlanRun.Id'], name=op.f('FK_DemandFulfillment_PlanRunId')),
    sa.PrimaryKeyConstraint('Id', name=op.f('PK_DemandFulfillment')),
    schema='planning',
    comment='Talebin planlanan karşılanması ve gecikmesi.'
    )
    op.create_table('CapacityLoad',
    sa.Column('Id', sa.BigInteger(), autoincrement=True, nullable=False, comment='Kayıt kimliği'),
    sa.Column('PlanRunId', sa.BigInteger(), nullable=False, comment='Plan hesabı'),
    sa.Column('ResourceId', sa.BigInteger(), nullable=False, comment='Kaynak'),
    sa.Column('BucketStart', sa.DATE(), nullable=False, comment='Dönem'),
    sa.Column('GrossCapacity', sa.Numeric(precision=18, scale=4), nullable=True, comment='Brüt kapasite'),
    sa.Column('DowntimeLoss', sa.Numeric(precision=18, scale=4), nullable=True, comment='Duruş kaybı'),
    sa.Column('NetCapacity', sa.Numeric(precision=18, scale=4), nullable=True, comment='Kalan kapasite (verim sonrası)'),
    sa.Column('Load', sa.Numeric(precision=18, scale=4), nullable=True, comment='Kapasite yükü'),
    sa.Column('Overtime', sa.Numeric(precision=18, scale=4), nullable=True, comment='Fazla mesai'),
    sa.Column('UpdatedAt', mssql.DATETIME2(), nullable=False, comment='Yazılma zamanı (UTC)'),
    sa.ForeignKeyConstraint(['PlanRunId'], ['planning.PlanRun.Id'], name=op.f('FK_CapacityLoad_PlanRunId')),
    sa.PrimaryKeyConstraint('Id', name=op.f('PK_CapacityLoad')),
    schema='planning',
    comment='Kaynak ve dönem bazında kapasite ve kapasite yükü.'
    )
    op.create_index(op.f('IX_CapacityLoad_ResourceId'), 'CapacityLoad', ['ResourceId'], unique=False, schema='planning')
    op.create_table('Pegging',
    sa.Column('Id', sa.BigInteger(), autoincrement=True, nullable=False, comment='Kayıt kimliği'),
    sa.Column('PlanRunId', sa.BigInteger(), nullable=False, comment='Plan hesabı'),
    sa.Column('SupplyType', sa.Unicode(length=15), nullable=False, comment='Stok | İş emri | Satın alma | Planlı sipariş …'),
    sa.Column('SupplyId', sa.BigInteger(), nullable=False, comment='Arz'),
    sa.Column('DemandType', sa.Unicode(length=15), nullable=False, comment='Sipariş | Bağımlı talep …'),
    sa.Column('DemandId', sa.BigInteger(), nullable=False, comment='Talep'),
    sa.Column('RootDemandId', sa.BigInteger(), nullable=True, comment='Kök talep'),
    sa.Column('Quantity', sa.Numeric(precision=18, scale=4), nullable=False, comment='Miktar'),
    sa.Column('IsFixed', sa.Boolean(), server_default=sa.text('0'), nullable=True, comment='Sabit ya da manuel bağ'),
    sa.Column('UpdatedAt', mssql.DATETIME2(), nullable=False, comment='Yazılma zamanı (UTC)'),
    sa.ForeignKeyConstraint(['PlanRunId'], ['planning.PlanRun.Id'], name=op.f('FK_Pegging_PlanRunId')),
    sa.PrimaryKeyConstraint('Id', name=op.f('PK_Pegging')),
    schema='planning',
    comment='Arz–talep bağı (full pegging).'
    )
    op.create_table('PlanWarning',
    sa.Column('Id', sa.BigInteger(), autoincrement=True, nullable=False, comment='Kayıt kimliği'),
    sa.Column('PlanRunId', sa.BigInteger(), nullable=False, comment='Plan hesabı'),
    sa.Column('WarningCode', sa.Unicode(length=30), nullable=False, comment='Uyarı tanımı'),
    sa.Column('ObjectType', sa.Unicode(length=20), nullable=True, comment='İlgili nesne tipi'),
    sa.Column('ObjectId', sa.BigInteger(), nullable=True, comment='İlgili nesne'),
    sa.Column('Value', sa.Numeric(precision=18, scale=4), nullable=True, comment='Ölçülen değer'),
    sa.Column('Message', sa.Unicode(length=400), nullable=True, comment='Mesaj (şablon tabanlı açıklama)'),
    sa.Column('UpdatedAt', mssql.DATETIME2(), nullable=False, comment='Yazılma zamanı (UTC)'),
    sa.ForeignKeyConstraint(['PlanRunId'], ['planning.PlanRun.Id'], name=op.f('FK_PlanWarning_PlanRunId')),
    sa.ForeignKeyConstraint(['WarningCode'], ['param.WarningDefinition.Code'], name=op.f('FK_PlanWarning_WarningCode')),
    sa.PrimaryKeyConstraint('Id', name=op.f('PK_PlanWarning')),
    schema='planning',
    comment='Plan hesabının ürettiği uyarılar.'
    )


def downgrade():
    _require_empty()
    op.drop_table('PlanWarning', schema='planning')
    op.drop_table('Pegging', schema='planning')
    op.drop_table('CapacityLoad', schema='planning')
    op.drop_table('DemandFulfillment', schema='planning')
    op.drop_table('SupplyRecommendation', schema='planning')
    op.drop_table('PlannedOrder', schema='planning')
    op.create_table('PlannedOrder',
    sa.Column('Id', sa.BigInteger(), autoincrement=False, nullable=False, comment='Kayıt kimliği'),
    sa.Column('PlanRunId', sa.BigInteger(), nullable=False, comment='Plan hesabı'),
    sa.Column('MaterialId', sa.BigInteger(), nullable=False, comment='Malzeme'),
    sa.Column('OrderType', sa.Unicode(length=15), nullable=False, comment='Üretim | Satın alma | Fason'),
    sa.Column('SupplierId', sa.BigInteger(), nullable=True, comment='Tedarikçi'),
    sa.Column('ProjectId', sa.BigInteger(), nullable=True, comment='Proje (sahip)'),
    sa.Column('Quantity', sa.Numeric(precision=18, scale=4), nullable=False, comment='Motorun miktarı (sürekli)'),
    sa.Column('RoundedQty', sa.Numeric(precision=18, scale=4), nullable=True, comment='Yuvarlanmış miktar (son hesap)'),
    sa.Column('StartDate', sa.DATE(), nullable=True, comment='Başlangıç'),
    sa.Column('DueDate', sa.DATE(), nullable=False, comment='Bitiş'),
    sa.Column('BucketStart', sa.DATE(), nullable=True, comment='Dönem'),
    sa.Column('VersionFrom', sa.Integer(), autoincrement=False, nullable=False, comment='Kaydın geçerli olduğu ilk veri versiyonu'),
    sa.Column('VersionTo', sa.Integer(), nullable=True, comment='Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş'),
    sa.Column('ImportBatchId', sa.BigInteger(), nullable=True, comment='Kaydı getiren yükleme partisi'),
    sa.Column('BusinessKey', sa.Unicode(length=200), nullable=False, comment='İş anahtarı (kod ya da kodların birleşimi)'),
    sa.Column('UpdatedAt', mssql.DATETIME2(), nullable=False, comment='Son değişiklik zamanı'),
    sa.ForeignKeyConstraint(['ImportBatchId'], ['adm.ImportBatch.Id'], name=op.f('FK_PlannedOrder_ImportBatchId')),
    sa.ForeignKeyConstraint(['PlanRunId'], ['planning.PlanRun.Id'], name=op.f('FK_PlannedOrder_PlanRunId')),
    sa.PrimaryKeyConstraint('Id', 'VersionFrom', name=op.f('PK_PlannedOrder')),
    schema='planning',
    comment='Planlı sipariş: üretim, satın alma ya da fason önerisi. Satın alma sürekli hesaplanır, yuvarlanmış miktar ayrıca.'
    )
    op.create_index(op.f('IX_PlannedOrder_MaterialId'), 'PlannedOrder', ['MaterialId'], unique=False, schema='planning')
    op.create_index(op.f('IX_PlannedOrder_ProjectId'), 'PlannedOrder', ['ProjectId'], unique=False, schema='planning')
    op.create_index(op.f('IX_PlannedOrder_SupplierId'), 'PlannedOrder', ['SupplierId'], unique=False, schema='planning')
    op.create_table('SupplyRecommendation',
    sa.Column('Id', sa.BigInteger(), autoincrement=False, nullable=False, comment='Kayıt kimliği'),
    sa.Column('PlanRunId', sa.BigInteger(), nullable=False, comment='Plan hesabı'),
    sa.Column('SupplyType', sa.Unicode(length=15), nullable=False, comment='İş emri | Satın alma | Fason | Transfer'),
    sa.Column('SupplyId', sa.BigInteger(), nullable=False, comment='Arz kaydı'),
    sa.Column('Action', sa.Unicode(length=15), nullable=False, comment='Öne çek | Ertele | İptal | Azalt | Hızlandır'),
    sa.Column('CurrentDate', sa.DATE(), nullable=True, comment='Mevcut tarih'),
    sa.Column('ProposedDate', sa.DATE(), nullable=True, comment='Önerilen tarih'),
    sa.Column('ProposedQty', sa.Numeric(precision=18, scale=4), nullable=True, comment='Önerilen miktar'),
    sa.Column('VersionFrom', sa.Integer(), autoincrement=False, nullable=False, comment='Kaydın geçerli olduğu ilk veri versiyonu'),
    sa.Column('VersionTo', sa.Integer(), nullable=True, comment='Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş'),
    sa.Column('ImportBatchId', sa.BigInteger(), nullable=True, comment='Kaydı getiren yükleme partisi'),
    sa.Column('BusinessKey', sa.Unicode(length=200), nullable=False, comment='İş anahtarı (kod ya da kodların birleşimi)'),
    sa.Column('UpdatedAt', mssql.DATETIME2(), nullable=False, comment='Son değişiklik zamanı'),
    sa.ForeignKeyConstraint(['ImportBatchId'], ['adm.ImportBatch.Id'], name=op.f('FK_SupplyRecommendation_ImportBatchId')),
    sa.ForeignKeyConstraint(['PlanRunId'], ['planning.PlanRun.Id'], name=op.f('FK_SupplyRecommendation_PlanRunId')),
    sa.PrimaryKeyConstraint('Id', 'VersionFrom', name=op.f('PK_SupplyRecommendation')),
    schema='planning',
    comment='Mevcut arz için öneri: öne çek, ertele, iptal, azalt, hızlandır.'
    )
    op.create_table('DemandFulfillment',
    sa.Column('Id', sa.BigInteger(), autoincrement=False, nullable=False, comment='Kayıt kimliği'),
    sa.Column('PlanRunId', sa.BigInteger(), nullable=False, comment='Plan hesabı'),
    sa.Column('DemandType', sa.Unicode(length=15), nullable=False, comment='Sipariş | Tahmin | Teklif | Güvenlik stoğu'),
    sa.Column('DemandId', sa.BigInteger(), nullable=False, comment='Talep kaydı'),
    sa.Column('DueDate', sa.DATE(), nullable=True, comment='Vade'),
    sa.Column('PlannedDate', sa.DATE(), nullable=True, comment='Planlanan karşılama'),
    sa.Column('ShortQty', sa.Numeric(precision=18, scale=4), nullable=True, comment='Karşılanamayan miktar'),
    sa.Column('DelayDays', sa.Integer(), nullable=True, comment='Gecikme (gün)'),
    sa.Column('VersionFrom', sa.Integer(), autoincrement=False, nullable=False, comment='Kaydın geçerli olduğu ilk veri versiyonu'),
    sa.Column('VersionTo', sa.Integer(), nullable=True, comment='Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş'),
    sa.Column('ImportBatchId', sa.BigInteger(), nullable=True, comment='Kaydı getiren yükleme partisi'),
    sa.Column('BusinessKey', sa.Unicode(length=200), nullable=False, comment='İş anahtarı (kod ya da kodların birleşimi)'),
    sa.Column('UpdatedAt', mssql.DATETIME2(), nullable=False, comment='Son değişiklik zamanı'),
    sa.ForeignKeyConstraint(['ImportBatchId'], ['adm.ImportBatch.Id'], name=op.f('FK_DemandFulfillment_ImportBatchId')),
    sa.ForeignKeyConstraint(['PlanRunId'], ['planning.PlanRun.Id'], name=op.f('FK_DemandFulfillment_PlanRunId')),
    sa.PrimaryKeyConstraint('Id', 'VersionFrom', name=op.f('PK_DemandFulfillment')),
    schema='planning',
    comment='Talebin planlanan karşılanması ve gecikmesi.'
    )
    op.create_table('CapacityLoad',
    sa.Column('Id', sa.BigInteger(), autoincrement=False, nullable=False, comment='Kayıt kimliği'),
    sa.Column('PlanRunId', sa.BigInteger(), nullable=False, comment='Plan hesabı'),
    sa.Column('ResourceId', sa.BigInteger(), nullable=False, comment='Kaynak'),
    sa.Column('BucketStart', sa.DATE(), nullable=False, comment='Dönem'),
    sa.Column('GrossCapacity', sa.Numeric(precision=18, scale=4), nullable=True, comment='Brüt kapasite'),
    sa.Column('DowntimeLoss', sa.Numeric(precision=18, scale=4), nullable=True, comment='Duruş kaybı'),
    sa.Column('NetCapacity', sa.Numeric(precision=18, scale=4), nullable=True, comment='Kalan kapasite (verim sonrası)'),
    sa.Column('Load', sa.Numeric(precision=18, scale=4), nullable=True, comment='Kapasite yükü'),
    sa.Column('Overtime', sa.Numeric(precision=18, scale=4), nullable=True, comment='Fazla mesai'),
    sa.Column('VersionFrom', sa.Integer(), autoincrement=False, nullable=False, comment='Kaydın geçerli olduğu ilk veri versiyonu'),
    sa.Column('VersionTo', sa.Integer(), nullable=True, comment='Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş'),
    sa.Column('ImportBatchId', sa.BigInteger(), nullable=True, comment='Kaydı getiren yükleme partisi'),
    sa.Column('BusinessKey', sa.Unicode(length=200), nullable=False, comment='İş anahtarı (kod ya da kodların birleşimi)'),
    sa.Column('UpdatedAt', mssql.DATETIME2(), nullable=False, comment='Son değişiklik zamanı'),
    sa.ForeignKeyConstraint(['ImportBatchId'], ['adm.ImportBatch.Id'], name=op.f('FK_CapacityLoad_ImportBatchId')),
    sa.ForeignKeyConstraint(['PlanRunId'], ['planning.PlanRun.Id'], name=op.f('FK_CapacityLoad_PlanRunId')),
    sa.PrimaryKeyConstraint('Id', 'VersionFrom', name=op.f('PK_CapacityLoad')),
    schema='planning',
    comment='Kaynak ve dönem bazında kapasite ve kapasite yükü.'
    )
    op.create_index(op.f('IX_CapacityLoad_ResourceId'), 'CapacityLoad', ['ResourceId'], unique=False, schema='planning')
    op.create_table('Pegging',
    sa.Column('Id', sa.BigInteger(), autoincrement=False, nullable=False, comment='Kayıt kimliği'),
    sa.Column('PlanRunId', sa.BigInteger(), nullable=False, comment='Plan hesabı'),
    sa.Column('SupplyType', sa.Unicode(length=15), nullable=False, comment='Stok | İş emri | Satın alma | Planlı sipariş …'),
    sa.Column('SupplyId', sa.BigInteger(), nullable=False, comment='Arz'),
    sa.Column('DemandType', sa.Unicode(length=15), nullable=False, comment='Sipariş | Bağımlı talep …'),
    sa.Column('DemandId', sa.BigInteger(), nullable=False, comment='Talep'),
    sa.Column('RootDemandId', sa.BigInteger(), nullable=True, comment='Kök talep'),
    sa.Column('Quantity', sa.Numeric(precision=18, scale=4), nullable=False, comment='Miktar'),
    sa.Column('IsFixed', sa.Boolean(), server_default=sa.text('0'), nullable=True, comment='Sabit ya da manuel bağ'),
    sa.Column('VersionFrom', sa.Integer(), autoincrement=False, nullable=False, comment='Kaydın geçerli olduğu ilk veri versiyonu'),
    sa.Column('VersionTo', sa.Integer(), nullable=True, comment='Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş'),
    sa.Column('ImportBatchId', sa.BigInteger(), nullable=True, comment='Kaydı getiren yükleme partisi'),
    sa.Column('BusinessKey', sa.Unicode(length=200), nullable=False, comment='İş anahtarı (kod ya da kodların birleşimi)'),
    sa.Column('UpdatedAt', mssql.DATETIME2(), nullable=False, comment='Son değişiklik zamanı'),
    sa.ForeignKeyConstraint(['ImportBatchId'], ['adm.ImportBatch.Id'], name=op.f('FK_Pegging_ImportBatchId')),
    sa.ForeignKeyConstraint(['PlanRunId'], ['planning.PlanRun.Id'], name=op.f('FK_Pegging_PlanRunId')),
    sa.PrimaryKeyConstraint('Id', 'VersionFrom', name=op.f('PK_Pegging')),
    schema='planning',
    comment='Arz–talep bağı (full pegging).'
    )
    op.create_table('PlanWarning',
    sa.Column('Id', sa.BigInteger(), autoincrement=False, nullable=False, comment='Kayıt kimliği'),
    sa.Column('PlanRunId', sa.BigInteger(), nullable=False, comment='Plan hesabı'),
    sa.Column('WarningCode', sa.Unicode(length=30), nullable=False, comment='Uyarı tanımı'),
    sa.Column('ObjectType', sa.Unicode(length=20), nullable=True, comment='İlgili nesne tipi'),
    sa.Column('ObjectId', sa.BigInteger(), nullable=True, comment='İlgili nesne'),
    sa.Column('Value', sa.Numeric(precision=18, scale=4), nullable=True, comment='Ölçülen değer'),
    sa.Column('Message', sa.Unicode(length=400), nullable=True, comment='Mesaj (şablon tabanlı açıklama)'),
    sa.Column('VersionFrom', sa.Integer(), autoincrement=False, nullable=False, comment='Kaydın geçerli olduğu ilk veri versiyonu'),
    sa.Column('VersionTo', sa.Integer(), nullable=True, comment='Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş'),
    sa.Column('ImportBatchId', sa.BigInteger(), nullable=True, comment='Kaydı getiren yükleme partisi'),
    sa.Column('BusinessKey', sa.Unicode(length=200), nullable=False, comment='İş anahtarı (kod ya da kodların birleşimi)'),
    sa.Column('UpdatedAt', mssql.DATETIME2(), nullable=False, comment='Son değişiklik zamanı'),
    sa.ForeignKeyConstraint(['ImportBatchId'], ['adm.ImportBatch.Id'], name=op.f('FK_PlanWarning_ImportBatchId')),
    sa.ForeignKeyConstraint(['PlanRunId'], ['planning.PlanRun.Id'], name=op.f('FK_PlanWarning_PlanRunId')),
    sa.ForeignKeyConstraint(['WarningCode'], ['param.WarningDefinition.Code'], name=op.f('FK_PlanWarning_WarningCode')),
    sa.PrimaryKeyConstraint('Id', 'VersionFrom', name=op.f('PK_PlanWarning')),
    schema='planning',
    comment='Plan hesabının ürettiği uyarılar.'
    )
