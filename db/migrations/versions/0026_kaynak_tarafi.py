"""0026 · Kaynak tarafı (K-117): işçiler kaynak, yetkinlikler kaynak grubu; ResourceGroupAssignment ve EmployeeAbsence; Worker, CompetenceGroup, WorkerCompetence, WorkerAbsence kalkar

Veri taşınır: CompetenceGroup → ResourceGroup (aynı lokasyon ve kodda grup varsa ona bayrak konur), Worker → Resource (IsEmployee),
Resource.ResourceGroupId, Worker.ResourceGroupId ve WorkerCompetence → ResourceGroupAssignment, WorkerAbsence → EmployeeAbsence, ShiftPlan.CompetenceGroupId → ResourceGroupId.
Bitiş günü dahil tutulur: gece yarısında biten eski kayıtta EndDate bir gün öncedir. ResourceType'tan tip bayrakları doldurulur.
İşçilerin kapasite alanları boş gelir (ekranda tanımlanır); bu yüzden DailyCapacity ve CalendarId boş kalabilir.
Kodu aynı olan işçi ve kaynak varsa tekil indeks geçişi durdurur. stg ham veridir, değerleri taşınmaz.
Geri alışta veri geri taşınır; yeni bayraklar, ProductionLocation ve kalan fazla mesai kaybolur, sözlükte eski tabloların etiketi alan adı olur.

Revision ID: 0026
Revises: 0025
Create Date: 2026-11-04
"""
from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql

from dictionary import sync
from models import metadata


revision = '0026'
down_revision = '0025'
branch_labels = None
depends_on = None

SCHEMAS = ('core', 'stg')
FD = 'adm.FieldDefinition'
DROPPED = ('Worker', 'CompetenceGroup', 'WorkerCompetence', 'WorkerAbsence')
ADDITIONAL = ', '.join([f'AdditionalText{i}' for i in range(1, 8)] + [f'AdditionalNumber{i}' for i in range(1, 4)])
VERSION = 'VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt'

RAW = "ERP'den gelen ham değer; tip bayraklarla ifade edilir"
OLD_TYPE = 'Makine | İşçi | Fason | Kalıp | Fırın | Diğer'
CRITICAL = '1: planda kısıt, 0: sonsuz kapasite (sadece raporlanır)'
OLD_GROUP = 'Kaynak grubu (makine grubu, işçi kaynak grubu).'
NEW_GROUP = 'Kaynak ve yetkinlik grubu. Kapasite havuzu değil, uygun kaynaklar listesidir; kapasite yalnız kaynakta tutulur.'
FLAGS = (
    ('IsEmployee', 'Kaynak işçi mi', 'İşçi'),
    ('IsMachine', 'Kaynak makine mi', 'Makine'),
    ('IsFurnace', 'Kaynak fırın mı; Faz 1 planlamada kullanılmaz', 'Fırın'),
    ('IsMold', 'Kaynak kalıp mı; Faz 1 planlamada kullanılmaz', 'Kalıp'),
    ('IsOther', 'Diğer kaynak mı', 'Diğer'),
    ('IsSubcontractor', 'Kaynak fason mu', 'Fason'),
)
RESOURCE_NEW = (
    ('ProductionLocation', sa.Unicode(length=50), 'Lokasyonun alt tanımı (hol, hat)'),
    ('IsActive', sa.Boolean(), 'Aktif mi'),
    ('RemainingOverTimeYear', sa.Numeric(precision=9, scale=2), 'Yıllık kalan fazla mesai (saat)'),
    ('RemainingOverTimeMonth', sa.Numeric(precision=9, scale=2), 'Aylık kalan fazla mesai (saat)'),
)
GROUP_NEW = (
    ('Type', sa.Unicode(length=50), 'Grup tipi; ERP\'den gelen ham değer'),
    ('IsResourceGroup', sa.Boolean(), 'Kaynak grubu'),
    ('IsCompetenceGroup', sa.Boolean(), 'Yetkinlik grubu'),
    ('IsActive', sa.Boolean(), 'Aktif'),
)
STG_REMOVED = (
    ('ResourceGroupCode', sa.NVARCHAR(length=50), 'Kaynak grubu'),
    ('ResourceRole', sa.NVARCHAR(length=10), 'Primary | Secondary'),
    ('CapacityUnit', sa.NVARCHAR(length=10), 'Kapasite birimi (Saat, Adet, Ton…); rotadaki tüketim aynı birimde kabul edilir'),
    ('DailyCapacity', sa.Numeric(precision=18, scale=4), 'Bir adet kaynağın bir çalışma günündeki kapasitesi'),
    ('Quantity', sa.Integer(), 'Paralel kaynak adedi'),
    ('CapacitySource', sa.NVARCHAR(length=10), 'İşçi gruplarında: Vardiyadan | Doğrudan'),
    ('SubconPlanningType', sa.NVARCHAR(length=15), 'Fasonda: İş yeri | Tedarik süresi'),
    ('SubconFixedLeadTimeDays', sa.Numeric(precision=9, scale=2), 'Fasonda sabit süre (taşıma ve kuyruk)'),
    ('SubconVariableDaysPerUnit', sa.Numeric(precision=18, scale=6), 'Fasonda birim başına gün (fasoncunun hızı)'),
)
NEW_FIELDS = {
    'Resource': ('IsEmployee', 'IsMachine', 'IsFurnace', 'IsMold', 'IsOther', 'IsSubcontractor', 'ProductionLocation', 'IsActive', 'RemainingOverTimeYear', 'RemainingOverTimeMonth'),
    'ResourceGroup': ('Type', 'IsResourceGroup', 'IsCompetenceGroup', 'IsActive'),
}


def _group_comment(text):
    for schema in SCHEMAS:
        op.execute(f"EXEC sp_updateextendedproperty 'MS_Description', N'{text}', 'schema', '{schema}', 'table', 'ResourceGroup'")


def _new_tables():
    op.create_table('EmployeeAbsence',
    sa.Column('Id', sa.BigInteger(), autoincrement=False, nullable=False, comment='Kayıt kimliği'),
    sa.Column('LocationId', sa.Integer(), nullable=False, comment='Lokasyon'),
    sa.Column('ResourceId', sa.BigInteger(), nullable=False, comment='Kaynak'),
    sa.Column('AbsenceType', sa.Unicode(length=50), nullable=False, comment="ERP'den gelen ham değer (izin, rapor…)"),
    sa.Column('StartDate', sa.DATE(), nullable=False, comment='Başlangıç'),
    sa.Column('EndDate', sa.DATE(), nullable=False, comment='Bitiş günü (dahil)'),
    sa.Column('HoursPerDay', sa.Numeric(precision=9, scale=2), nullable=True, comment='Günlük devamsız saat; kısmi devamsızlık için, boşsa tam gün'),
    sa.Column('VersionFrom', sa.Integer(), autoincrement=False, nullable=False, comment='Kaydın geçerli olduğu ilk veri versiyonu'),
    sa.Column('VersionTo', sa.Integer(), nullable=True, comment='Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş'),
    sa.Column('ImportBatchId', sa.BigInteger(), nullable=True, comment='Kaydı getiren yükleme partisi'),
    sa.Column('BusinessKey', sa.Unicode(length=200), nullable=False, comment='İş anahtarı; kod ya da kodların birleşimi'),
    sa.Column('UpdatedAt', mssql.DATETIME2(), nullable=False, comment='Son değişiklik zamanı'),
    sa.ForeignKeyConstraint(['ImportBatchId'], ['adm.ImportBatch.Id'], name=op.f('FK_EmployeeAbsence_ImportBatchId')),
    sa.ForeignKeyConstraint(['LocationId'], ['core.Location.Id'], name=op.f('FK_EmployeeAbsence_LocationId')),
    sa.PrimaryKeyConstraint('Id', 'VersionFrom', name=op.f('PK_EmployeeAbsence')),
    schema='core',
    comment='Kişi bazında izin ve rapor.',
    info={'field_class': 'İşlem verisi'}
    )
    op.create_index(op.f('IX_EmployeeAbsence_ResourceId'), 'EmployeeAbsence', ['ResourceId'], unique=False, schema='core')
    op.create_index('UX_EmployeeAbsence_LocationId_ResourceId_AbsenceType_StartDate', 'EmployeeAbsence', ['LocationId', 'ResourceId', 'AbsenceType', 'StartDate'], unique=True, schema='core', mssql_where=sa.text('VersionTo IS NULL'))
    op.create_table('ResourceGroupAssignment',
    sa.Column('Id', sa.BigInteger(), autoincrement=False, nullable=False, comment='Kayıt kimliği'),
    sa.Column('LocationId', sa.Integer(), nullable=False, comment='Lokasyon'),
    sa.Column('ResourceGroupId', sa.BigInteger(), nullable=False, comment='Kaynak ya da yetkinlik grubu'),
    sa.Column('ResourceId', sa.BigInteger(), nullable=False, comment='Kaynak'),
    sa.Column('ValidFrom', sa.DATE(), nullable=True, comment='Geçerlilik başlangıcı'),
    sa.Column('ValidTo', sa.DATE(), nullable=True, comment='Geçerlilik bitişi'),
    sa.Column('VersionFrom', sa.Integer(), autoincrement=False, nullable=False, comment='Kaydın geçerli olduğu ilk veri versiyonu'),
    sa.Column('VersionTo', sa.Integer(), nullable=True, comment='Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş'),
    sa.Column('ImportBatchId', sa.BigInteger(), nullable=True, comment='Kaydı getiren yükleme partisi'),
    sa.Column('BusinessKey', sa.Unicode(length=200), nullable=False, comment='İş anahtarı; kod ya da kodların birleşimi'),
    sa.Column('UpdatedAt', mssql.DATETIME2(), nullable=False, comment='Son değişiklik zamanı'),
    sa.ForeignKeyConstraint(['ImportBatchId'], ['adm.ImportBatch.Id'], name=op.f('FK_ResourceGroupAssignment_ImportBatchId')),
    sa.ForeignKeyConstraint(['LocationId'], ['core.Location.Id'], name=op.f('FK_ResourceGroupAssignment_LocationId')),
    sa.PrimaryKeyConstraint('Id', 'VersionFrom', name=op.f('PK_ResourceGroupAssignment')),
    schema='core',
    comment='Kaynağın gruba ataması; bir kaynak birden fazla gruba atanabilir, yetkinlik matrisi bu tablodur. Geçerlilik tarihleri yalnız girdi.',
    info={'field_class': 'Ana veri'}
    )
    op.create_index(op.f('IX_ResourceGroupAssignment_ResourceGroupId'), 'ResourceGroupAssignment', ['ResourceGroupId'], unique=False, schema='core')
    op.create_index(op.f('IX_ResourceGroupAssignment_ResourceId'), 'ResourceGroupAssignment', ['ResourceId'], unique=False, schema='core')
    op.create_index('UX_ResourceGroupAssignment_LocationId_ResourceGroupId_ResourceId', 'ResourceGroupAssignment', ['LocationId', 'ResourceGroupId', 'ResourceId'], unique=True, schema='core', mssql_where=sa.text('VersionTo IS NULL'))
    op.create_table('EmployeeAbsence',
    sa.Column('StagingRowId', sa.BigInteger(), autoincrement=True, nullable=False, comment='Satır kimliği'),
    sa.Column('ImportBatchId', sa.BigInteger(), nullable=False, comment='Yükleme partisi'),
    sa.Column('RowStatus', sa.Unicode(length=15), nullable=False, comment='Yeni | Hatalı | Aktarıldı'),
    sa.Column('ErrorText', sa.Unicode(length=400), nullable=True, comment='Hata açıklaması'),
    sa.Column('LocationCode', sa.Unicode(length=30), nullable=True, comment='Lokasyon kodu'),
    sa.Column('ResourceCode', sa.Unicode(length=50), nullable=True, comment='Kaynak kodu'),
    sa.Column('AbsenceType', sa.Unicode(length=50), nullable=True, comment="ERP'den gelen ham değer (izin, rapor…)"),
    sa.Column('StartDate', sa.DATE(), nullable=True, comment='Başlangıç'),
    sa.Column('EndDate', sa.DATE(), nullable=True, comment='Bitiş günü (dahil)'),
    sa.Column('HoursPerDay', sa.Numeric(precision=9, scale=2), nullable=True, comment='Günlük devamsız saat; kısmi devamsızlık için, boşsa tam gün'),
    sa.ForeignKeyConstraint(['ImportBatchId'], ['adm.ImportBatch.Id'], name=op.f('FK_EmployeeAbsence_ImportBatchId')),
    sa.PrimaryKeyConstraint('StagingRowId', name=op.f('PK_EmployeeAbsence')),
    schema='stg',
    comment='Kişi bazında izin ve rapor.'
    )
    op.create_index('UX_EmployeeAbsence_LocationCode_ResourceCode_AbsenceType_StartDate', 'EmployeeAbsence', ['LocationCode', 'ResourceCode', 'AbsenceType', 'StartDate'], unique=True, schema='stg')
    op.create_table('ResourceGroupAssignment',
    sa.Column('StagingRowId', sa.BigInteger(), autoincrement=True, nullable=False, comment='Satır kimliği'),
    sa.Column('ImportBatchId', sa.BigInteger(), nullable=False, comment='Yükleme partisi'),
    sa.Column('RowStatus', sa.Unicode(length=15), nullable=False, comment='Yeni | Hatalı | Aktarıldı'),
    sa.Column('ErrorText', sa.Unicode(length=400), nullable=True, comment='Hata açıklaması'),
    sa.Column('LocationCode', sa.Unicode(length=30), nullable=True, comment='Lokasyon kodu'),
    sa.Column('ResourceGroupCode', sa.Unicode(length=50), nullable=True, comment='Kaynak ya da yetkinlik grubu'),
    sa.Column('ResourceCode', sa.Unicode(length=50), nullable=True, comment='Kaynak kodu'),
    sa.Column('ValidFrom', sa.DATE(), nullable=True, comment='Geçerlilik başlangıcı'),
    sa.Column('ValidTo', sa.DATE(), nullable=True, comment='Geçerlilik bitişi'),
    sa.ForeignKeyConstraint(['ImportBatchId'], ['adm.ImportBatch.Id'], name=op.f('FK_ResourceGroupAssignment_ImportBatchId')),
    sa.PrimaryKeyConstraint('StagingRowId', name=op.f('PK_ResourceGroupAssignment')),
    schema='stg',
    comment='Kaynağın gruba ataması; bir kaynak birden fazla gruba atanabilir, yetkinlik matrisi bu tablodur. Geçerlilik tarihleri yalnız girdi.'
    )
    op.create_index('UX_ResourceGroupAssignment_LocationCode_ResourceGroupCode_ResourceCode', 'ResourceGroupAssignment', ['LocationCode', 'ResourceGroupCode', 'ResourceCode'], unique=True, schema='stg')


def _old_tables():
    op.create_table('Worker',
    sa.Column('Id', sa.BIGINT(), autoincrement=False, nullable=False, comment='Kayıt kimliği'),
    sa.Column('LocationId', sa.INTEGER(), autoincrement=False, nullable=False, comment='Lokasyon'),
    sa.Column('Code', sa.NVARCHAR(length=50), autoincrement=False, nullable=False, comment='Sicil no'),
    sa.Column('Name', sa.NVARCHAR(length=150), autoincrement=False, nullable=True, comment='Ad'),
    sa.Column('ResourceGroupId', sa.BIGINT(), autoincrement=False, nullable=True, comment='Bağlı olduğu işçi kaynak grubu'),
    sa.Column('IsActive', mssql.BIT(), server_default=sa.text('((1))'), autoincrement=False, nullable=True, comment='Aktif mi'),
    sa.Column('AdditionalText1', sa.NVARCHAR(length=255), autoincrement=False, nullable=True, comment="Ek metin alanları; etiketi FieldDefinition'da"),
    sa.Column('AdditionalText2', sa.NVARCHAR(length=255), autoincrement=False, nullable=True, comment="Ek metin alanları; etiketi FieldDefinition'da"),
    sa.Column('AdditionalText3', sa.NVARCHAR(length=255), autoincrement=False, nullable=True, comment="Ek metin alanları; etiketi FieldDefinition'da"),
    sa.Column('AdditionalText4', sa.NVARCHAR(length=255), autoincrement=False, nullable=True, comment="Ek metin alanları; etiketi FieldDefinition'da"),
    sa.Column('AdditionalText5', sa.NVARCHAR(length=255), autoincrement=False, nullable=True, comment="Ek metin alanları; etiketi FieldDefinition'da"),
    sa.Column('AdditionalText6', sa.NVARCHAR(length=255), autoincrement=False, nullable=True, comment="Ek metin alanları; etiketi FieldDefinition'da"),
    sa.Column('AdditionalText7', sa.NVARCHAR(length=255), autoincrement=False, nullable=True, comment="Ek metin alanları; etiketi FieldDefinition'da"),
    sa.Column('AdditionalNumber1', sa.NUMERIC(precision=18, scale=4), autoincrement=False, nullable=True, comment="Ek sayı alanları; etiketi FieldDefinition'da"),
    sa.Column('AdditionalNumber2', sa.NUMERIC(precision=18, scale=4), autoincrement=False, nullable=True, comment="Ek sayı alanları; etiketi FieldDefinition'da"),
    sa.Column('AdditionalNumber3', sa.NUMERIC(precision=18, scale=4), autoincrement=False, nullable=True, comment="Ek sayı alanları; etiketi FieldDefinition'da"),
    sa.Column('VersionFrom', sa.INTEGER(), autoincrement=False, nullable=False, comment='Kaydın geçerli olduğu ilk veri versiyonu'),
    sa.Column('VersionTo', sa.INTEGER(), autoincrement=False, nullable=True, comment='Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş'),
    sa.Column('ImportBatchId', sa.BIGINT(), autoincrement=False, nullable=True, comment='Kaydı getiren yükleme partisi'),
    sa.Column('BusinessKey', sa.NVARCHAR(length=200), autoincrement=False, nullable=False, comment='İş anahtarı; kod ya da kodların birleşimi'),
    sa.Column('UpdatedAt', mssql.DATETIME2(), autoincrement=False, nullable=False, comment='Son değişiklik zamanı'),
    sa.ForeignKeyConstraint(['ImportBatchId'], ['adm.ImportBatch.Id'], name=op.f('FK_Worker_ImportBatchId')),
    sa.ForeignKeyConstraint(['LocationId'], ['core.Location.Id'], name=op.f('FK_Worker_LocationId')),
    sa.PrimaryKeyConstraint('Id', 'VersionFrom', name=op.f('PK_Worker')),
    schema='core',
    comment='İşçi.'
    )
    op.create_index(op.f('IX_Worker_ResourceGroupId'), 'Worker', ['ResourceGroupId'], unique=False, schema='core')
    op.create_table('WorkerCompetence',
    sa.Column('StagingRowId', sa.BIGINT(), sa.Identity(always=False, start=1, increment=1), autoincrement=True, nullable=False, comment='Satır kimliği'),
    sa.Column('ImportBatchId', sa.BIGINT(), autoincrement=False, nullable=False, comment='Yükleme partisi'),
    sa.Column('RowStatus', sa.NVARCHAR(length=15), autoincrement=False, nullable=False, comment='Yeni | Hatalı | Aktarıldı'),
    sa.Column('ErrorText', sa.NVARCHAR(length=400), autoincrement=False, nullable=True, comment='Hata açıklaması'),
    sa.Column('WorkerCode', sa.NVARCHAR(length=50), autoincrement=False, nullable=True, comment='İşçi sicil no'),
    sa.Column('CompetenceGroupCode', sa.NVARCHAR(length=50), autoincrement=False, nullable=True, comment='Yetkinlik grubu kodu'),
    sa.ForeignKeyConstraint(['ImportBatchId'], ['adm.ImportBatch.Id'], name=op.f('FK_WorkerCompetence_ImportBatchId')),
    sa.PrimaryKeyConstraint('StagingRowId', name=op.f('PK_WorkerCompetence')),
    schema='stg',
    comment='İşçi–yetkinlik grubu eşleşmesi; çoktan çoğa.'
    )
    op.create_table('WorkerAbsence',
    sa.Column('Id', sa.BIGINT(), autoincrement=False, nullable=False, comment='Kayıt kimliği'),
    sa.Column('WorkerId', sa.BIGINT(), autoincrement=False, nullable=False, comment='İşçi'),
    sa.Column('StartAt', mssql.DATETIME2(), autoincrement=False, nullable=False, comment='Başlangıç'),
    sa.Column('EndAt', mssql.DATETIME2(), autoincrement=False, nullable=False, comment='Bitiş'),
    sa.Column('AbsenceType', sa.NVARCHAR(length=10), autoincrement=False, nullable=False, comment='İzin | Rapor'),
    sa.Column('VersionFrom', sa.INTEGER(), autoincrement=False, nullable=False, comment='Kaydın geçerli olduğu ilk veri versiyonu'),
    sa.Column('VersionTo', sa.INTEGER(), autoincrement=False, nullable=True, comment='Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş'),
    sa.Column('ImportBatchId', sa.BIGINT(), autoincrement=False, nullable=True, comment='Kaydı getiren yükleme partisi'),
    sa.Column('BusinessKey', sa.NVARCHAR(length=200), autoincrement=False, nullable=False, comment='İş anahtarı; kod ya da kodların birleşimi'),
    sa.Column('UpdatedAt', mssql.DATETIME2(), autoincrement=False, nullable=False, comment='Son değişiklik zamanı'),
    sa.ForeignKeyConstraint(['ImportBatchId'], ['adm.ImportBatch.Id'], name=op.f('FK_WorkerAbsence_ImportBatchId')),
    sa.PrimaryKeyConstraint('Id', 'VersionFrom', name=op.f('PK_WorkerAbsence')),
    schema='core',
    comment='Kişi bazında izin ve rapor.'
    )
    op.create_index(op.f('IX_WorkerAbsence_WorkerId'), 'WorkerAbsence', ['WorkerId'], unique=False, schema='core')
    op.create_table('WorkerCompetence',
    sa.Column('WorkerId', sa.BIGINT(), autoincrement=False, nullable=False, comment='İşçi'),
    sa.Column('CompetenceGroupId', sa.BIGINT(), autoincrement=False, nullable=False, comment='Yetkinlik grubu'),
    sa.Column('VersionFrom', sa.INTEGER(), autoincrement=False, nullable=False, comment='Kaydın geçerli olduğu ilk veri versiyonu'),
    sa.Column('VersionTo', sa.INTEGER(), autoincrement=False, nullable=True, comment='Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş'),
    sa.Column('ImportBatchId', sa.BIGINT(), autoincrement=False, nullable=True, comment='Kaydı getiren yükleme partisi'),
    sa.Column('BusinessKey', sa.NVARCHAR(length=200), autoincrement=False, nullable=False, comment='İş anahtarı; kod ya da kodların birleşimi'),
    sa.Column('UpdatedAt', mssql.DATETIME2(), autoincrement=False, nullable=False, comment='Son değişiklik zamanı'),
    sa.ForeignKeyConstraint(['ImportBatchId'], ['adm.ImportBatch.Id'], name=op.f('FK_WorkerCompetence_ImportBatchId')),
    sa.PrimaryKeyConstraint('WorkerId', 'CompetenceGroupId', 'VersionFrom', name=op.f('PK_WorkerCompetence')),
    schema='core',
    comment='İşçi–yetkinlik grubu eşleşmesi; çoktan çoğa.'
    )
    op.create_index(op.f('IX_WorkerCompetence_WorkerId'), 'WorkerCompetence', ['WorkerId'], unique=False, schema='core')
    op.create_index(op.f('IX_WorkerCompetence_CompetenceGroupId'), 'WorkerCompetence', ['CompetenceGroupId'], unique=False, schema='core')
    op.create_table('CompetenceGroup',
    sa.Column('StagingRowId', sa.BIGINT(), sa.Identity(always=False, start=1, increment=1), autoincrement=True, nullable=False, comment='Satır kimliği'),
    sa.Column('ImportBatchId', sa.BIGINT(), autoincrement=False, nullable=False, comment='Yükleme partisi'),
    sa.Column('RowStatus', sa.NVARCHAR(length=15), autoincrement=False, nullable=False, comment='Yeni | Hatalı | Aktarıldı'),
    sa.Column('ErrorText', sa.NVARCHAR(length=400), autoincrement=False, nullable=True, comment='Hata açıklaması'),
    sa.Column('LocationCode', sa.NVARCHAR(length=30), autoincrement=False, nullable=True, comment='Lokasyon kodu'),
    sa.Column('Code', sa.NVARCHAR(length=50), autoincrement=False, nullable=True, comment='Grup kodu'),
    sa.Column('Name', sa.NVARCHAR(length=150), autoincrement=False, nullable=True, comment='Grup adı'),
    sa.ForeignKeyConstraint(['ImportBatchId'], ['adm.ImportBatch.Id'], name=op.f('FK_CompetenceGroup_ImportBatchId')),
    sa.PrimaryKeyConstraint('StagingRowId', name=op.f('PK_CompetenceGroup')),
    schema='stg',
    comment='İşçi yetkinlik grubu.'
    )
    op.create_table('Worker',
    sa.Column('StagingRowId', sa.BIGINT(), sa.Identity(always=False, start=1, increment=1), autoincrement=True, nullable=False, comment='Satır kimliği'),
    sa.Column('ImportBatchId', sa.BIGINT(), autoincrement=False, nullable=False, comment='Yükleme partisi'),
    sa.Column('RowStatus', sa.NVARCHAR(length=15), autoincrement=False, nullable=False, comment='Yeni | Hatalı | Aktarıldı'),
    sa.Column('ErrorText', sa.NVARCHAR(length=400), autoincrement=False, nullable=True, comment='Hata açıklaması'),
    sa.Column('LocationCode', sa.NVARCHAR(length=30), autoincrement=False, nullable=True, comment='Lokasyon kodu'),
    sa.Column('Code', sa.NVARCHAR(length=50), autoincrement=False, nullable=True, comment='Sicil no'),
    sa.Column('Name', sa.NVARCHAR(length=150), autoincrement=False, nullable=True, comment='Ad'),
    sa.Column('ResourceGroupCode', sa.NVARCHAR(length=50), autoincrement=False, nullable=True, comment='Bağlı olduğu işçi kaynak grubu kodu'),
    sa.Column('IsActive', mssql.BIT(), autoincrement=False, nullable=True, comment='Aktif mi'),
    sa.Column('AdditionalText1', sa.NVARCHAR(length=255), autoincrement=False, nullable=True, comment="Ek metin alanları; etiketi FieldDefinition'da"),
    sa.Column('AdditionalText2', sa.NVARCHAR(length=255), autoincrement=False, nullable=True, comment="Ek metin alanları; etiketi FieldDefinition'da"),
    sa.Column('AdditionalText3', sa.NVARCHAR(length=255), autoincrement=False, nullable=True, comment="Ek metin alanları; etiketi FieldDefinition'da"),
    sa.Column('AdditionalText4', sa.NVARCHAR(length=255), autoincrement=False, nullable=True, comment="Ek metin alanları; etiketi FieldDefinition'da"),
    sa.Column('AdditionalText5', sa.NVARCHAR(length=255), autoincrement=False, nullable=True, comment="Ek metin alanları; etiketi FieldDefinition'da"),
    sa.Column('AdditionalText6', sa.NVARCHAR(length=255), autoincrement=False, nullable=True, comment="Ek metin alanları; etiketi FieldDefinition'da"),
    sa.Column('AdditionalText7', sa.NVARCHAR(length=255), autoincrement=False, nullable=True, comment="Ek metin alanları; etiketi FieldDefinition'da"),
    sa.Column('AdditionalNumber1', sa.NUMERIC(precision=18, scale=4), autoincrement=False, nullable=True, comment="Ek sayı alanları; etiketi FieldDefinition'da"),
    sa.Column('AdditionalNumber2', sa.NUMERIC(precision=18, scale=4), autoincrement=False, nullable=True, comment="Ek sayı alanları; etiketi FieldDefinition'da"),
    sa.Column('AdditionalNumber3', sa.NUMERIC(precision=18, scale=4), autoincrement=False, nullable=True, comment="Ek sayı alanları; etiketi FieldDefinition'da"),
    sa.ForeignKeyConstraint(['ImportBatchId'], ['adm.ImportBatch.Id'], name=op.f('FK_Worker_ImportBatchId')),
    sa.PrimaryKeyConstraint('StagingRowId', name=op.f('PK_Worker')),
    schema='stg',
    comment='İşçi.'
    )
    op.create_table('CompetenceGroup',
    sa.Column('Id', sa.BIGINT(), autoincrement=False, nullable=False, comment='Kayıt kimliği'),
    sa.Column('LocationId', sa.INTEGER(), autoincrement=False, nullable=False, comment='Lokasyon'),
    sa.Column('Code', sa.NVARCHAR(length=50), autoincrement=False, nullable=False, comment='Grup kodu'),
    sa.Column('Name', sa.NVARCHAR(length=150), autoincrement=False, nullable=True, comment='Grup adı'),
    sa.Column('VersionFrom', sa.INTEGER(), autoincrement=False, nullable=False, comment='Kaydın geçerli olduğu ilk veri versiyonu'),
    sa.Column('VersionTo', sa.INTEGER(), autoincrement=False, nullable=True, comment='Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş'),
    sa.Column('ImportBatchId', sa.BIGINT(), autoincrement=False, nullable=True, comment='Kaydı getiren yükleme partisi'),
    sa.Column('BusinessKey', sa.NVARCHAR(length=200), autoincrement=False, nullable=False, comment='İş anahtarı; kod ya da kodların birleşimi'),
    sa.Column('UpdatedAt', mssql.DATETIME2(), autoincrement=False, nullable=False, comment='Son değişiklik zamanı'),
    sa.ForeignKeyConstraint(['ImportBatchId'], ['adm.ImportBatch.Id'], name=op.f('FK_CompetenceGroup_ImportBatchId')),
    sa.ForeignKeyConstraint(['LocationId'], ['core.Location.Id'], name=op.f('FK_CompetenceGroup_LocationId')),
    sa.PrimaryKeyConstraint('Id', 'VersionFrom', name=op.f('PK_CompetenceGroup')),
    schema='core',
    comment='İşçi yetkinlik grubu.'
    )
    op.create_table('WorkerAbsence',
    sa.Column('StagingRowId', sa.BIGINT(), sa.Identity(always=False, start=1, increment=1), autoincrement=True, nullable=False, comment='Satır kimliği'),
    sa.Column('ImportBatchId', sa.BIGINT(), autoincrement=False, nullable=False, comment='Yükleme partisi'),
    sa.Column('RowStatus', sa.NVARCHAR(length=15), autoincrement=False, nullable=False, comment='Yeni | Hatalı | Aktarıldı'),
    sa.Column('ErrorText', sa.NVARCHAR(length=400), autoincrement=False, nullable=True, comment='Hata açıklaması'),
    sa.Column('WorkerCode', sa.NVARCHAR(length=50), autoincrement=False, nullable=True, comment='İşçi sicil no'),
    sa.Column('StartAt', mssql.DATETIME2(), autoincrement=False, nullable=True, comment='Başlangıç'),
    sa.Column('EndAt', mssql.DATETIME2(), autoincrement=False, nullable=True, comment='Bitiş'),
    sa.Column('AbsenceType', sa.NVARCHAR(length=10), autoincrement=False, nullable=True, comment='İzin | Rapor'),
    sa.ForeignKeyConstraint(['ImportBatchId'], ['adm.ImportBatch.Id'], name=op.f('FK_WorkerAbsence_ImportBatchId')),
    sa.PrimaryKeyConstraint('StagingRowId', name=op.f('PK_WorkerAbsence')),
    schema='stg',
    comment='Kişi bazında izin ve rapor.'
    )


def upgrade():
    _new_tables()

    # --- ResourceGroup: yeni alanlar; yetkinlik grupları buraya
    op.drop_index('UX_ResourceGroup_Code', table_name='ResourceGroup', schema='core', mssql_where=sa.text('VersionTo IS NULL'))
    op.drop_index('UX_ResourceGroup_Code', table_name='ResourceGroup', schema='stg')
    for schema in SCHEMAS:
        for name, type_, comment in GROUP_NEW:
            op.add_column('ResourceGroup', sa.Column(name, type_, nullable=True, comment=comment), schema=schema)
    op.execute("UPDATE core.ResourceGroup SET IsResourceGroup = 1, IsCompetenceGroup = 0")
    op.execute("SELECT x.OldId, x.LocationId, x.Code, g.Id AS ExistingId, CAST(NULL AS bigint) AS NewId INTO #cg "
               "FROM (SELECT Id AS OldId, LocationId, Code, ROW_NUMBER() OVER (PARTITION BY Id ORDER BY VersionFrom DESC) AS n FROM core.CompetenceGroup) x "
               "OUTER APPLY (SELECT TOP 1 r.Id FROM core.ResourceGroup r WHERE r.LocationId = x.LocationId AND r.Code = x.Code) g WHERE x.n = 1")
    op.execute("UPDATE m SET NewId = m.ExistingId FROM #cg m WHERE m.ExistingId IS NOT NULL")
    op.execute("UPDATE m SET NewId = z.base + z.rn FROM #cg m JOIN (SELECT OldId, ROW_NUMBER() OVER (ORDER BY OldId) AS rn, "
               "(SELECT ISNULL(MAX(Id), 0) FROM core.ResourceGroup) AS base FROM #cg WHERE ExistingId IS NULL) z ON z.OldId = m.OldId")
    op.execute("UPDATE g SET IsCompetenceGroup = 1 FROM core.ResourceGroup g JOIN #cg m ON m.ExistingId = g.Id")
    op.execute(f"INSERT INTO core.ResourceGroup (Id, {VERSION}, LocationId, Code, Name, IsResourceGroup, IsCompetenceGroup) "
               "SELECT m.NewId, c.VersionFrom, c.VersionTo, c.ImportBatchId, c.BusinessKey, c.UpdatedAt, c.LocationId, c.Code, c.Name, 0, 1 "
               "FROM core.CompetenceGroup c JOIN #cg m ON m.OldId = c.Id WHERE m.ExistingId IS NULL")
    op.create_index('UX_ResourceGroup_LocationId_Code', 'ResourceGroup', ['LocationId', 'Code'], unique=True, schema='core', mssql_where=sa.text('VersionTo IS NULL'))
    op.create_index('UX_ResourceGroup_LocationCode_Code', 'ResourceGroup', ['LocationCode', 'Code'], unique=True, schema='stg')
    _group_comment(NEW_GROUP)

    # --- Resource: yeni alanlar, adlar, boş kalabilen kapasite alanları; işçiler buraya
    op.drop_index('UX_Resource_Code', table_name='Resource', schema='core', mssql_where=sa.text('VersionTo IS NULL'))
    op.drop_index('UX_Resource_Code', table_name='Resource', schema='stg')
    op.drop_index(op.f('IX_Resource_SupplierId'), table_name='Resource', schema='core')
    op.drop_index(op.f('IX_Resource_CalendarId'), table_name='Resource', schema='core')
    for schema in SCHEMAS:
        for name, comment, _ in FLAGS:
            op.add_column('Resource', sa.Column(name, sa.Boolean(), nullable=True, comment=comment), schema=schema)
        for name, type_, comment in RESOURCE_NEW:
            op.add_column('Resource', sa.Column(name, type_, nullable=True, comment=comment), schema=schema)
        op.alter_column('Resource', 'IsConstrained', new_column_name='IsCritical', schema=schema)
        op.alter_column('Resource', 'SupplierId' if schema == 'core' else 'SupplierCode', new_column_name='SubcontractorId' if schema == 'core' else 'SubcontractorCode', schema=schema)
        op.alter_column('Resource', 'ResourceType', existing_type=sa.NVARCHAR(length=20), comment=RAW, existing_comment=OLD_TYPE, existing_nullable=schema == 'stg', schema=schema)
    op.alter_column('Resource', 'SubcontractorCode', existing_type=sa.NVARCHAR(length=50), comment='Fasoncu', existing_comment='Fasonda fasoncu', existing_nullable=True, schema='stg')
    op.alter_column('Resource', 'ResourceType', existing_type=sa.NVARCHAR(length=20), server_default=None, nullable=True, existing_comment=RAW, schema='core')
    op.alter_column('Resource', 'IsCritical', existing_type=sa.Boolean(), server_default=None, nullable=True, existing_comment=CRITICAL, schema='core')
    op.alter_column('Resource', 'DailyCapacity', existing_type=sa.Numeric(precision=18, scale=4), nullable=True, existing_comment='Bir adet kaynağın bir çalışma günündeki kapasitesi', schema='core')
    op.alter_column('Resource', 'CalendarId', existing_type=sa.Integer(), nullable=True, existing_comment='Çalışma takvimi (Smartchain ekranında atanır)', schema='core')
    op.create_index(op.f('IX_Resource_CalendarId'), 'Resource', ['CalendarId'], unique=False, schema='core')
    op.create_index(op.f('IX_Resource_SubcontractorId'), 'Resource', ['SubcontractorId'], unique=False, schema='core')
    assignments = ', '.join(f"{name} = CASE WHEN ResourceType = N'{kind}' THEN 1 ELSE 0 END" for name, _, kind in FLAGS)
    op.execute(f"UPDATE core.Resource SET {assignments}")
    op.execute("IF EXISTS (SELECT 1 FROM core.Worker) AND NOT EXISTS (SELECT 1 FROM core.UnitOfMeasure WHERE Code = N'SAAT') "
               "INSERT INTO core.UnitOfMeasure (Code) VALUES (N'SAAT')")
    op.execute("SELECT x.OldId, x.LocationId, x.Code, base.v + ROW_NUMBER() OVER (ORDER BY x.OldId) AS NewId INTO #w "
               "FROM (SELECT Id AS OldId, LocationId, Code, ROW_NUMBER() OVER (PARTITION BY Id ORDER BY VersionFrom DESC) AS n FROM core.Worker) x "
               "CROSS JOIN (SELECT ISNULL(MAX(Id), 0) AS v FROM core.Resource) base WHERE x.n = 1")
    op.execute(f"INSERT INTO core.Resource (Id, {VERSION}, LocationId, Code, Name, ResourceType, IsEmployee, IsMachine, IsFurnace, IsMold, IsOther, IsSubcontractor, IsActive, {ADDITIONAL}) "
               f"SELECT m.NewId, w.VersionFrom, w.VersionTo, w.ImportBatchId, w.BusinessKey, w.UpdatedAt, w.LocationId, w.Code, w.Name, N'İşçi', 1, 0, 0, 0, 0, 0, w.IsActive, {ADDITIONAL} "
               "FROM core.Worker w JOIN #w m ON m.OldId = w.Id")
    op.create_index('UX_Resource_LocationId_Code', 'Resource', ['LocationId', 'Code'], unique=True, schema='core', mssql_where=sa.text('VersionTo IS NULL'))
    op.create_index('UX_Resource_LocationCode_Code', 'Resource', ['LocationCode', 'Code'], unique=True, schema='stg')

    # --- Atamalar: kaynağın grubu, işçinin grubu, işçi yetkinlikleri
    op.execute("SELECT r.LocationId, r.ResourceGroupId AS GroupId, r.Id AS ResourceId, r.VersionFrom, r.VersionTo, r.ImportBatchId, r.UpdatedAt INTO #a "
               "FROM core.Resource r WHERE r.ResourceGroupId IS NOT NULL")
    op.execute("INSERT INTO #a SELECT w.LocationId, w.ResourceGroupId, m.NewId, w.VersionFrom, w.VersionTo, w.ImportBatchId, w.UpdatedAt "
               "FROM core.Worker w JOIN #w m ON m.OldId = w.Id WHERE w.ResourceGroupId IS NOT NULL")
    op.execute("INSERT INTO #a SELECT m.LocationId, c.NewId, m.NewId, wc.VersionFrom, wc.VersionTo, wc.ImportBatchId, wc.UpdatedAt "
               "FROM core.WorkerCompetence wc JOIN #w m ON m.OldId = wc.WorkerId JOIN #cg c ON c.OldId = wc.CompetenceGroupId")
    op.execute(f"INSERT INTO core.ResourceGroupAssignment (Id, {VERSION}, LocationId, ResourceGroupId, ResourceId) "
               "SELECT DENSE_RANK() OVER (ORDER BY a.LocationId, a.GroupId, a.ResourceId), a.VersionFrom, a.VersionTo, a.ImportBatchId, "
               "LEFT(CONCAT(l.Code, N'|', g.Code, N'|', r.Code), 200), a.UpdatedAt, a.LocationId, a.GroupId, a.ResourceId "
               "FROM (SELECT *, ROW_NUMBER() OVER (PARTITION BY LocationId, GroupId, ResourceId, CASE WHEN VersionTo IS NULL THEN -1 ELSE VersionFrom END ORDER BY VersionFrom DESC) AS n FROM #a) a "
               "JOIN core.Location l ON l.Id = a.LocationId "
               "CROSS APPLY (SELECT TOP 1 x.Code FROM core.ResourceGroup x WHERE x.Id = a.GroupId ORDER BY x.VersionFrom DESC) g "
               "CROSS APPLY (SELECT TOP 1 x.Code FROM core.Resource x WHERE x.Id = a.ResourceId ORDER BY x.VersionFrom DESC) r WHERE a.n = 1")

    # --- İzinler; bitiş günü dahil
    op.execute(f"INSERT INTO core.EmployeeAbsence (Id, {VERSION}, LocationId, ResourceId, AbsenceType, StartDate, EndDate) "
               "SELECT a.Id, a.VersionFrom, a.VersionTo, a.ImportBatchId, "
               "LEFT(CONCAT(l.Code, N'|', m.Code, N'|', a.AbsenceType, N'|', CONVERT(nvarchar(10), CAST(a.StartAt AS date), 23)), 200), a.UpdatedAt, "
               "m.LocationId, m.NewId, a.AbsenceType, CAST(a.StartAt AS date), "
               "CASE WHEN CAST(a.EndAt AS time) = '00:00:00' AND a.EndAt > a.StartAt THEN DATEADD(day, -1, CAST(a.EndAt AS date)) ELSE CAST(a.EndAt AS date) END "
               "FROM core.WorkerAbsence a JOIN #w m ON m.OldId = a.WorkerId JOIN core.Location l ON l.Id = m.LocationId")

    # --- Vardiya planı yalnız grubu gösterir
    op.execute("UPDATE s SET ResourceGroupId = c.NewId FROM core.ShiftPlan s JOIN #cg c ON c.OldId = s.CompetenceGroupId WHERE s.ResourceGroupId IS NULL")
    op.drop_index(op.f('IX_ShiftPlan_CompetenceGroupId'), table_name='ShiftPlan', schema='core')
    op.drop_column('ShiftPlan', 'CompetenceGroupId', schema='core')
    op.alter_column('ShiftPlan', 'ResourceGroupId', existing_type=sa.BigInteger(), comment='Kaynak ya da yetkinlik grubu', existing_comment='İşçi kaynak grubu', existing_nullable=True, schema='core')

    # --- Kalkanlar
    op.drop_index(op.f('IX_Resource_ResourceGroupId'), table_name='Resource', schema='core')
    op.drop_column('Resource', 'ResourceGroupId', schema='core')
    op.drop_column('Resource', 'ResourceRole', schema='core', mssql_drop_default=True)
    for name, _, _ in STG_REMOVED:
        op.drop_column('Resource', name, schema='stg')
    op.execute("DROP TABLE #a")
    op.execute("DROP TABLE #w")
    op.execute("DROP TABLE #cg")
    for table in ('WorkerAbsence', 'WorkerCompetence', 'Worker', 'CompetenceGroup'):
        op.drop_table(table, schema='stg')
    op.drop_index(op.f('IX_WorkerCompetence_CompetenceGroupId'), table_name='WorkerCompetence', schema='core')
    op.drop_index(op.f('IX_WorkerCompetence_WorkerId'), table_name='WorkerCompetence', schema='core')
    op.drop_table('WorkerCompetence', schema='core')
    op.drop_index(op.f('IX_WorkerAbsence_WorkerId'), table_name='WorkerAbsence', schema='core')
    op.drop_table('WorkerAbsence', schema='core')
    op.drop_index(op.f('IX_Worker_ResourceGroupId'), table_name='Worker', schema='core')
    op.drop_table('Worker', schema='core')
    op.drop_table('CompetenceGroup', schema='core')

    # --- Sözlük: elle verilen etiket yeni adda kalır; sync silmez, IsRequired ve DefaultValue'ya dokunmaz.
    names = ', '.join(f"N'{t}'" for t in DROPPED)
    op.execute(f"DELETE FROM {FD} WHERE TableName IN ({names})")
    op.execute(f"DELETE FROM {FD} WHERE TableName = N'Resource' AND FieldName IN (N'ResourceGroupId', N'ResourceRole')")
    op.execute(f"DELETE FROM {FD} WHERE TableName = N'ShiftPlan' AND FieldName = N'CompetenceGroupId'")
    op.execute(f"UPDATE {FD} SET FieldName = N'IsCritical' WHERE TableName = N'Resource' AND FieldName = N'IsConstrained'")
    op.execute(f"UPDATE {FD} SET FieldName = N'SubcontractorId' WHERE TableName = N'Resource' AND FieldName = N'SupplierId'")
    op.execute(f"UPDATE {FD} SET IsRequired = 0 WHERE TableName = N'Resource' AND FieldName IN (N'ResourceType', N'DailyCapacity', N'CalendarId', N'IsCritical')")
    op.execute(f"UPDATE {FD} SET DefaultValue = NULL WHERE TableName = N'Resource' AND FieldName IN (N'ResourceType', N'IsCritical')")
    if not context.is_offline_mode():  # bağlantısız SQL betiğinde satırlar yazılmaz; ilk bağlantılı geçişte kurulur
        sync(op.get_bind(), metadata)


def downgrade():
    _old_tables()

    # --- Veri geri: yetkinlik grupları, işçiler, yetkinlikler, izinler
    op.execute(f"INSERT INTO core.CompetenceGroup (Id, {VERSION}, LocationId, Code, Name) "
               f"SELECT Id, {VERSION}, LocationId, Code, Name FROM core.ResourceGroup WHERE IsCompetenceGroup = 1")
    op.add_column('Resource', sa.Column('ResourceGroupId', sa.BigInteger(), nullable=True, comment='Kaynak grubu'), schema='core')
    op.execute("UPDATE r SET ResourceGroupId = (SELECT TOP 1 a.ResourceGroupId FROM core.ResourceGroupAssignment a "
               "WHERE a.ResourceId = r.Id AND EXISTS (SELECT 1 FROM core.ResourceGroup g WHERE g.Id = a.ResourceGroupId AND ISNULL(g.IsCompetenceGroup, 0) = 0) ORDER BY a.Id) FROM core.Resource r")
    op.execute(f"INSERT INTO core.Worker (Id, {VERSION}, LocationId, Code, Name, ResourceGroupId, IsActive, {ADDITIONAL}) "
               f"SELECT Id, {VERSION}, LocationId, Code, Name, ResourceGroupId, IsActive, {ADDITIONAL} FROM core.Resource WHERE IsEmployee = 1")
    op.execute(f"INSERT INTO core.WorkerCompetence (WorkerId, CompetenceGroupId, {VERSION}) "
               f"SELECT a.ResourceId, a.ResourceGroupId, a.VersionFrom, a.VersionTo, a.ImportBatchId, a.BusinessKey, a.UpdatedAt FROM core.ResourceGroupAssignment a "
               "WHERE EXISTS (SELECT 1 FROM core.ResourceGroup g WHERE g.Id = a.ResourceGroupId AND g.IsCompetenceGroup = 1) "
               "AND EXISTS (SELECT 1 FROM core.Resource r WHERE r.Id = a.ResourceId AND r.IsEmployee = 1)")
    op.execute(f"INSERT INTO core.WorkerAbsence (Id, {VERSION}, WorkerId, StartAt, EndAt, AbsenceType) "
               f"SELECT Id, {VERSION}, ResourceId, CAST(StartDate AS datetime2), DATEADD(day, 1, CAST(EndDate AS datetime2)), LEFT(AbsenceType, 10) FROM core.EmployeeAbsence")

    # --- Vardiya planı
    op.add_column('ShiftPlan', sa.Column('CompetenceGroupId', sa.BigInteger(), nullable=True, comment='Yetkinlik grubu (ya da)'), schema='core')
    op.execute("UPDATE s SET CompetenceGroupId = s.ResourceGroupId, ResourceGroupId = NULL FROM core.ShiftPlan s "
               "WHERE EXISTS (SELECT 1 FROM core.ResourceGroup g WHERE g.Id = s.ResourceGroupId AND g.IsCompetenceGroup = 1)")
    op.create_index(op.f('IX_ShiftPlan_CompetenceGroupId'), 'ShiftPlan', ['CompetenceGroupId'], unique=False, schema='core')
    op.alter_column('ShiftPlan', 'ResourceGroupId', existing_type=sa.BigInteger(), comment='İşçi kaynak grubu', existing_comment='Kaynak ya da yetkinlik grubu', existing_nullable=True, schema='core')

    # --- Yeni tablolar ve taşınan satırlar
    op.drop_index('UX_ResourceGroupAssignment_LocationCode_ResourceGroupCode_ResourceCode', table_name='ResourceGroupAssignment', schema='stg')
    op.drop_table('ResourceGroupAssignment', schema='stg')
    op.drop_index('UX_EmployeeAbsence_LocationCode_ResourceCode_AbsenceType_StartDate', table_name='EmployeeAbsence', schema='stg')
    op.drop_table('EmployeeAbsence', schema='stg')
    op.drop_index('UX_ResourceGroupAssignment_LocationId_ResourceGroupId_ResourceId', table_name='ResourceGroupAssignment', schema='core', mssql_where=sa.text('VersionTo IS NULL'))
    op.drop_index(op.f('IX_ResourceGroupAssignment_ResourceId'), table_name='ResourceGroupAssignment', schema='core')
    op.drop_index(op.f('IX_ResourceGroupAssignment_ResourceGroupId'), table_name='ResourceGroupAssignment', schema='core')
    op.drop_table('ResourceGroupAssignment', schema='core')
    op.drop_index('UX_EmployeeAbsence_LocationId_ResourceId_AbsenceType_StartDate', table_name='EmployeeAbsence', schema='core', mssql_where=sa.text('VersionTo IS NULL'))
    op.drop_index(op.f('IX_EmployeeAbsence_ResourceId'), table_name='EmployeeAbsence', schema='core')
    op.drop_table('EmployeeAbsence', schema='core')
    op.execute("DELETE FROM core.Resource WHERE IsEmployee = 1")
    op.execute("DELETE FROM core.ResourceGroup WHERE IsCompetenceGroup = 1 AND ISNULL(IsResourceGroup, 0) = 0")

    # --- Resource geri
    op.drop_index('UX_Resource_LocationCode_Code', table_name='Resource', schema='stg')
    op.drop_index('UX_Resource_LocationId_Code', table_name='Resource', schema='core', mssql_where=sa.text('VersionTo IS NULL'))
    op.drop_index(op.f('IX_Resource_SubcontractorId'), table_name='Resource', schema='core')
    op.drop_index(op.f('IX_Resource_CalendarId'), table_name='Resource', schema='core')
    op.add_column('Resource', sa.Column('ResourceRole', sa.NVARCHAR(length=10), server_default=sa.text("N'Primary'"), nullable=False, comment='Primary | Secondary'), schema='core')
    op.create_index(op.f('IX_Resource_ResourceGroupId'), 'Resource', ['ResourceGroupId'], unique=False, schema='core')
    for name, type_, comment in STG_REMOVED:
        op.add_column('Resource', sa.Column(name, type_, nullable=True, comment=comment), schema='stg')
    op.execute("UPDATE core.Resource SET ResourceType = N'Diğer' WHERE ResourceType IS NULL")
    op.execute("UPDATE core.Resource SET IsCritical = 0 WHERE IsCritical IS NULL")
    op.execute("UPDATE core.Resource SET DailyCapacity = 0 WHERE DailyCapacity IS NULL")
    op.execute("UPDATE core.Resource SET CalendarId = (SELECT MIN(Id) FROM core.Calendar) WHERE CalendarId IS NULL")
    op.alter_column('Resource', 'CalendarId', existing_type=sa.Integer(), nullable=False, existing_comment='Çalışma takvimi (Smartchain ekranında atanır)', schema='core')
    op.alter_column('Resource', 'DailyCapacity', existing_type=sa.Numeric(precision=18, scale=4), nullable=False, existing_comment='Bir adet kaynağın bir çalışma günündeki kapasitesi', schema='core')
    op.alter_column('Resource', 'IsCritical', existing_type=sa.Boolean(), server_default=sa.text('0'), nullable=False, existing_comment=CRITICAL, schema='core')
    op.alter_column('Resource', 'ResourceType', existing_type=sa.NVARCHAR(length=20), server_default=sa.text("N'Diğer'"), nullable=False, existing_comment=RAW, schema='core')
    op.alter_column('Resource', 'SubcontractorCode', existing_type=sa.NVARCHAR(length=50), comment='Fasonda fasoncu', existing_comment='Fasoncu', existing_nullable=True, schema='stg')
    for schema in SCHEMAS:
        op.alter_column('Resource', 'ResourceType', existing_type=sa.NVARCHAR(length=20), comment=OLD_TYPE, existing_comment=RAW, existing_nullable=schema == 'stg', schema=schema)
        op.alter_column('Resource', 'IsCritical', new_column_name='IsConstrained', schema=schema)
        op.alter_column('Resource', 'SubcontractorId' if schema == 'core' else 'SubcontractorCode', new_column_name='SupplierId' if schema == 'core' else 'SupplierCode', schema=schema)
        for name, _, _ in reversed(RESOURCE_NEW):
            op.drop_column('Resource', name, schema=schema)
        for name, _, _ in reversed(FLAGS):
            op.drop_column('Resource', name, schema=schema)
    op.create_index(op.f('IX_Resource_SupplierId'), 'Resource', ['SupplierId'], unique=False, schema='core')
    op.create_index(op.f('IX_Resource_CalendarId'), 'Resource', ['CalendarId'], unique=False, schema='core')
    op.create_index('UX_Resource_Code', 'Resource', ['Code'], unique=True, schema='stg')
    op.create_index('UX_Resource_Code', 'Resource', ['Code'], unique=True, schema='core', mssql_where=sa.text('VersionTo IS NULL'))

    # --- ResourceGroup geri
    op.drop_index('UX_ResourceGroup_LocationCode_Code', table_name='ResourceGroup', schema='stg')
    op.drop_index('UX_ResourceGroup_LocationId_Code', table_name='ResourceGroup', schema='core', mssql_where=sa.text('VersionTo IS NULL'))
    _group_comment(OLD_GROUP)
    for schema in SCHEMAS:
        for name, _, _ in reversed(GROUP_NEW):
            op.drop_column('ResourceGroup', name, schema=schema)
    op.create_index('UX_ResourceGroup_Code', 'ResourceGroup', ['Code'], unique=True, schema='stg')
    op.create_index('UX_ResourceGroup_Code', 'ResourceGroup', ['Code'], unique=True, schema='core', mssql_where=sa.text('VersionTo IS NULL'))

    # --- Sözlük
    for table, fields in NEW_FIELDS.items():
        names = ', '.join(f"N'{f}'" for f in fields)
        op.execute(f"DELETE FROM {FD} WHERE TableName = N'{table}' AND FieldName IN ({names})")
    op.execute(f"DELETE FROM {FD} WHERE TableName IN (N'ResourceGroupAssignment', N'EmployeeAbsence')")
    op.execute(f"UPDATE {FD} SET FieldName = N'IsConstrained', DefaultValue = N'0', IsRequired = 1 WHERE TableName = N'Resource' AND FieldName = N'IsCritical'")
    op.execute(f"UPDATE {FD} SET FieldName = N'SupplierId' WHERE TableName = N'Resource' AND FieldName = N'SubcontractorId'")
    op.execute(f"UPDATE {FD} SET IsRequired = 1 WHERE TableName = N'Resource' AND FieldName IN (N'ResourceType', N'DailyCapacity', N'CalendarId')")
    op.execute(f"UPDATE {FD} SET DefaultValue = N'Diğer' WHERE TableName = N'Resource' AND FieldName = N'ResourceType'")
    op.execute(f"INSERT INTO {FD} (TableName, FieldName, FieldClass, StandardLabel) VALUES (N'Resource', N'ResourceGroupId', N'Ana veri', N'Kaynak grubu'), "
               "(N'Resource', N'ResourceRole', N'Ana veri', N'Kaynak rolü'), (N'ShiftPlan', N'CompetenceGroupId', N'Ana veri', N'Yetkinlik grubu')")
    for table, field_class in (('Worker', 'Ana veri'), ('CompetenceGroup', 'Ana veri'), ('WorkerCompetence', 'Ana veri'), ('WorkerAbsence', 'İşlem verisi')):
        op.execute(f"INSERT INTO {FD} (TableName, FieldName, FieldClass, StandardLabel) SELECT N'{table}', COLUMN_NAME, N'{field_class}', COLUMN_NAME "
                   f"FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = 'core' AND TABLE_NAME = '{table}' "
                   "AND COLUMN_NAME NOT IN ('Id', 'VersionFrom', 'VersionTo', 'ImportBatchId', 'BusinessKey', 'UpdatedAt')")
