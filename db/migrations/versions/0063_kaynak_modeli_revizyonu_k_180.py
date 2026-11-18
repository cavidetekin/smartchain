"""0063 · Kaynak modeli revizyonu (K-180): planlama birimi kaynak grubu

Yalnız yapıyı değiştirir; var olan veri yeni modele TAŞINMAZ (K-180 madde 12). Ürün kurulu değil; geliştirme veritabanında geçişten sonra
sentetik sıfırlama çalıştırılır (`python -m app.data.synthetic reset`).

- Rota ve iş emri operasyonu: `ResourceId` / `ResourceCode` kalkar; `ResourceGroupId` zorunlu olur.
- Kaynak: tip bayrakları, `IsCritical`, `CapacityUnit`, fasoncu, `CapacitySource` ve `Quantity` kalkar (ham `ResourceType` kalır).
- Kaynak grubu: tip bayrakları, `IsCritical`, `CapacityUnit` (zorunlu), fasoncu gelir; `IsResourceGroup`, `IsCompetenceGroup` kalkar.
- `ResourceGroupAssignment` → `ResourceGroupMember` (yeni tablo; tarihsiz, ek alanlı). `Shift`, `ShiftPlan`, `OvertimeLimit` kalkar.
- `CapacityLoad` kaynak grubu düzeyinde; `AllocationRule.ResourceId` kalkar.
- SİLİNEN SATIRLAR (yeni zorunlu alanları sağlayamadıkları için): `core.ResourceGroup` (hepsi; kapasite birimi zorunlu), `core.Routing` ve
  `core.WorkOrderOperation`'da kaynak grubu boş satırlar, `planning.CapacityLoad` (hepsi; kaynak grubu zorunlu). Kalkan tabloların satırları da gider.
- `adm` temizliği: varlık adı `ResourceGroupAssignment` olan kayıtlar `ResourceGroupMember` olur; kalkan alanların alan tanımı, manuel değer ve değer
  kaynağı satırları silinir; kalkan ya da taşınan alanı kullanan kullanıcı kuralları (veri kuralı, doğrulama kuralı) bulgularıyla silinir.
- Geri alış yapıyı geri getirir, veriyi getirmez: kalkan tablolar ve alanlar boş döner; eski zorunlu alanları sağlayamayan `core.Resource`,
  `core.ResourceGroup` ve `planning.CapacityLoad` satırları silinir. Geri alıştan sonra da sentetik yükleme gerekir (K-165: yalnız kullanıcının terminalinde).
- Açıklamalar modelden (docs/02, docs/03); veri sözlüğü eşitlenir.

Revision ID: 0063
Revises: 0062
Create Date: 2026-11-18
"""
from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql

from dictionary import sync
from models import metadata

revision = '0063'
down_revision = '0062'
branch_labels = None
depends_on = None

FD = 'adm.FieldDefinition'
OLD_ENTITY, NEW_ENTITY = 'ResourceGroupAssignment', 'ResourceGroupMember'
GONE_TABLES = ('Shift', 'ShiftPlan', 'OvertimeLimit')
# Kalkan ya da taşınan alanlar: sözleşmedeki (stg) ve ana tablodaki (core) adlarıyla
MOVED = ('IsEmployee', 'IsMachine', 'IsFurnace', 'IsMold', 'IsOther', 'IsSubcontractor', 'IsCritical', 'CapacityUnit')
GONE_FIELDS = {
    'Resource': MOVED + ('SubcontractorCode', 'SubcontractorId', 'CapacitySource', 'Quantity'),
    'ResourceGroup': ('IsResourceGroup', 'IsCompetenceGroup'),
    NEW_ENTITY: ('ValidFrom', 'ValidTo'),
    'Routing': ('ResourceCode', 'ResourceId'),
    'WorkOrderOperation': ('ResourceCode', 'ResourceId'),
    'AllocationRule': ('ResourceId',),
    'CapacityLoad': ('ResourceId',),
}


def _table_comment(schema, table, text):
    """MS SQL'de var olan tablo açıklaması güncellenir."""
    escaped = text.replace("'", "''")
    op.execute(f"EXEC sp_updateextendedproperty 'MS_Description', N'{escaped}', 'schema', '{schema}', 'table', '{table}'")


def _in(values):
    return ', '.join(f"N'{v}'" for v in values)


def _adm_with(column):
    """Bu kolonu taşıyan adm tabloları (modelden)."""
    return [t.name for t in metadata.sorted_tables if t.schema == 'adm' and column in t.c]


def _rename_entity(old, new):
    op.execute(f"DELETE FROM {FD} WHERE TableName = N'{new}'")  # yeni adla satır varsa (geri alıp yeniden geçişte) çakışmasın; sync yeniden kurar
    for column in ('EntityName', 'TableName'):
        for table in _adm_with(column):
            op.execute(f"UPDATE adm.[{table}] SET {column} = N'{new}' WHERE {column} = N'{old}'")


def _delete_user_rules():
    """Kalkan ya da taşınan alanı kullanan kullanıcı kuralları bulgularıyla silinir (K-180 madde 12)."""
    for entity, fields in GONE_FIELDS.items():
        names = _in(fields)
        rules = (f"SELECT r.Id FROM adm.DataRule r WHERE r.EntityName = N'{entity}' AND (r.TargetField IN ({names}) OR r.SourceField IN ({names}) "
                 f"OR r.OperandField IN ({names}) OR EXISTS (SELECT 1 FROM adm.DataRuleCondition c WHERE c.DataRuleId = r.Id "
                 f"AND (c.FieldName IN ({names}) OR c.CompareField IN ({names}))))")
        op.execute(f"SELECT Id INTO #gone_data_rule FROM ({rules}) x")
        op.execute("UPDATE adm.ManualValue SET UnderlyingRuleId = NULL WHERE UnderlyingRuleId IN (SELECT Id FROM #gone_data_rule)")
        for table in _adm_with('DataRuleId'):
            op.execute(f"DELETE FROM adm.[{table}] WHERE DataRuleId IN (SELECT Id FROM #gone_data_rule)")
        op.execute("DELETE FROM adm.DataRule WHERE Id IN (SELECT Id FROM #gone_data_rule)")
        op.execute("DROP TABLE #gone_data_rule")
        rules = (f"SELECT r.Id FROM adm.ValidationRule r WHERE r.EntityName = N'{entity}' AND r.Kind = N'Kullanıcı' "
                 f"AND EXISTS (SELECT 1 FROM adm.ValidationRuleCondition c WHERE c.ValidationRuleId = r.Id "
                 f"AND (c.FieldName IN ({names}) OR c.CompareField IN ({names})))")
        op.execute(f"SELECT Id INTO #gone_validation_rule FROM ({rules}) x")
        for table in _adm_with('ValidationRuleId'):
            op.execute(f"DELETE FROM adm.[{table}] WHERE ValidationRuleId IN (SELECT Id FROM #gone_validation_rule)")
        op.execute("DELETE FROM adm.ValidationRule WHERE Id IN (SELECT Id FROM #gone_validation_rule)")
        op.execute("DROP TABLE #gone_validation_rule")


def _clean_dictionary():
    """Kalkan tabloların ve alanların alan tanımı, manuel değer ve değer kaynağı satırları; sync silmez."""
    for table in ('FieldDefinition', 'ManualValue', 'FieldValueSource'):
        op.execute(f"DELETE FROM adm.[{table}] WHERE TableName IN ({_in(GONE_TABLES)})")
        for entity, fields in GONE_FIELDS.items():
            op.execute(f"DELETE FROM adm.[{table}] WHERE TableName = N'{entity}' AND FieldName IN ({_in(fields)})")



def upgrade():
    # Veri taşınmaz: yeni zorunlu alanları sağlayamayan satırlar silinir (başlığa bakın); sonra sentetik sıfırlama.
    op.execute("DELETE FROM core.ResourceGroup")
    op.execute("DELETE FROM core.Routing WHERE ResourceGroupId IS NULL")
    op.execute("DELETE FROM core.WorkOrderOperation WHERE ResourceGroupId IS NULL")
    op.execute("DELETE FROM planning.CapacityLoad")
    # zorunlu yapılacak kolonun dizini önce kalkar (SQL Server dizinli kolonu değiştirmez), sonda yeniden kurulur
    op.drop_index(op.f('IX_Routing_ResourceGroupId'), table_name='Routing', schema='core')
    op.drop_index(op.f('IX_WorkOrderOperation_ResourceGroupId'), table_name='WorkOrderOperation', schema='core')
    op.create_table('ResourceGroupMember',
    sa.Column('StagingRowId', sa.BigInteger(), autoincrement=False, nullable=False, comment='Ham satırın kimliği (kopyalanır)'),
    sa.Column('ImportBatchId', sa.BigInteger(), nullable=False, comment='Satırın geldiği parti'),
    sa.Column('SourceRowNo', sa.Integer(), nullable=True, comment='Kaynaktaki satır no'),
    sa.Column('RowStatus', sa.Unicode(length=15), server_default=sa.text("N'Yeni'"), nullable=False, comment='Yeni | Hatalı | Aktarıldı; Hata bulgusu varsa Hatalı, load almaz (K-134)'),
    sa.Column('LocationCode', sa.Unicode(length=30), nullable=True, comment='Lokasyon kodu'),
    sa.Column('ResourceGroupCode', sa.Unicode(length=50), nullable=True, comment='Kaynak grubu'),
    sa.Column('ResourceCode', sa.Unicode(length=50), nullable=True, comment='Kaynak kodu'),
    sa.Column('AdditionalText1', sa.Unicode(length=255), nullable=True, comment="Ek metin alanları; etiketi FieldDefinition'da"),
    sa.Column('AdditionalText2', sa.Unicode(length=255), nullable=True, comment="Ek metin alanları; etiketi FieldDefinition'da"),
    sa.Column('AdditionalText3', sa.Unicode(length=255), nullable=True, comment="Ek metin alanları; etiketi FieldDefinition'da"),
    sa.Column('AdditionalNumber1', sa.Numeric(precision=18, scale=4), nullable=True, comment="Ek sayı alanları; etiketi FieldDefinition'da"),
    sa.Column('AdditionalNumber2', sa.Numeric(precision=18, scale=4), nullable=True, comment="Ek sayı alanları; etiketi FieldDefinition'da"),
    sa.PrimaryKeyConstraint('StagingRowId', name=op.f('PK_ResourceGroupMember')),
    schema='prc',
    comment='Grup eşleşmesi: kaynağın gruba üyeliği. Bir kaynak birden fazla gruba üye olabilir (birden fazla yetkinliği olan işçi). Geçerlilik tarihi yoktur: yüklü eşleşme bugünden itibaren geçerlidir. Gruptaki kaynak sayısı bu tablodan bilinir (K-180).'
    )
    op.create_index('UX_ResourceGroupMember_Key', 'ResourceGroupMember', ['LocationCode', 'ResourceGroupCode', 'ResourceCode'], unique=True, schema='prc')
    op.create_table('ResourceGroupMember',
    sa.Column('Id', sa.BigInteger(), autoincrement=False, nullable=False, comment='Kayıt kimliği'),
    sa.Column('LocationId', sa.Integer(), nullable=False, comment='Lokasyon'),
    sa.Column('ResourceGroupId', sa.BigInteger(), nullable=False, comment='Kaynak grubu'),
    sa.Column('ResourceId', sa.BigInteger(), nullable=False, comment='Kaynak'),
    sa.Column('AdditionalText1', sa.Unicode(length=255), nullable=True, comment="Ek metin alanları; etiketi FieldDefinition'da"),
    sa.Column('AdditionalText2', sa.Unicode(length=255), nullable=True, comment="Ek metin alanları; etiketi FieldDefinition'da"),
    sa.Column('AdditionalText3', sa.Unicode(length=255), nullable=True, comment="Ek metin alanları; etiketi FieldDefinition'da"),
    sa.Column('AdditionalNumber1', sa.Numeric(precision=18, scale=4), nullable=True, comment="Ek sayı alanları; etiketi FieldDefinition'da"),
    sa.Column('AdditionalNumber2', sa.Numeric(precision=18, scale=4), nullable=True, comment="Ek sayı alanları; etiketi FieldDefinition'da"),
    sa.Column('VersionFrom', sa.Integer(), autoincrement=False, nullable=False, comment='Kaydın geçerli olduğu ilk veri versiyonu'),
    sa.Column('VersionTo', sa.Integer(), nullable=True, comment='Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş'),
    sa.Column('ImportBatchId', sa.BigInteger(), nullable=True, comment='Kaydı getiren yükleme partisi'),
    sa.Column('BusinessKey', sa.Unicode(length=200), nullable=False, comment='İş anahtarı; kod ya da kodların birleşimi'),
    sa.Column('UpdatedAt', mssql.DATETIME2(), nullable=False, comment='Son değişiklik zamanı'),
    sa.ForeignKeyConstraint(['ImportBatchId'], ['adm.ImportBatch.Id'], name=op.f('FK_ResourceGroupMember_ImportBatchId')),
    sa.ForeignKeyConstraint(['LocationId'], ['core.Location.Id'], name=op.f('FK_ResourceGroupMember_LocationId')),
    sa.PrimaryKeyConstraint('Id', 'VersionFrom', name=op.f('PK_ResourceGroupMember')),
    schema='core',
    comment='Grup eşleşmesi: kaynağın gruba üyeliği. Bir kaynak birden fazla gruba üye olabilir (birden fazla yetkinliği olan işçi). Geçerlilik tarihi yoktur: yüklü eşleşme bugünden itibaren geçerlidir. Gruptaki kaynak sayısı bu tablodan bilinir (K-180).',
    info={'field_class': 'Ana veri'}
    )
    op.create_index(op.f('IX_ResourceGroupMember_ResourceGroupId'), 'ResourceGroupMember', ['ResourceGroupId'], unique=False, schema='core')
    op.create_index(op.f('IX_ResourceGroupMember_ResourceId'), 'ResourceGroupMember', ['ResourceId'], unique=False, schema='core')
    op.create_index('UX_ResourceGroupMember_LocationId_ResourceGroupId_ResourceId', 'ResourceGroupMember', ['LocationId', 'ResourceGroupId', 'ResourceId'], unique=True, schema='core', mssql_where=sa.text('VersionTo IS NULL'))
    op.create_table('ResourceGroupMember',
    sa.Column('StagingRowId', sa.BigInteger(), autoincrement=True, nullable=False, comment='Satır kimliği'),
    sa.Column('ImportBatchId', sa.BigInteger(), nullable=False, comment='Yükleme partisi'),
    sa.Column('ErrorText', sa.Unicode(length=400), nullable=True, comment='Hata açıklaması'),
    sa.Column('SourceRowNo', sa.Integer(), nullable=True, comment='Kaynaktaki satır no'),
    sa.Column('IsCurrent', sa.Boolean(), server_default=sa.text('0'), nullable=False, comment='Tablonun güncel hâlinde mi (K-133)'),
    sa.Column('SupersededAt', mssql.DATETIME2(), nullable=True, comment='Satırın güncel hâlden çıktığı zaman (UTC; K-160)'),
    sa.Column('LocationCode', sa.Unicode(length=30), nullable=True, comment='Lokasyon kodu'),
    sa.Column('ResourceGroupCode', sa.Unicode(length=50), nullable=True, comment='Kaynak grubu'),
    sa.Column('ResourceCode', sa.Unicode(length=50), nullable=True, comment='Kaynak kodu'),
    sa.Column('AdditionalText1', sa.Unicode(length=255), nullable=True, comment="Ek metin alanları; etiketi FieldDefinition'da"),
    sa.Column('AdditionalText2', sa.Unicode(length=255), nullable=True, comment="Ek metin alanları; etiketi FieldDefinition'da"),
    sa.Column('AdditionalText3', sa.Unicode(length=255), nullable=True, comment="Ek metin alanları; etiketi FieldDefinition'da"),
    sa.Column('AdditionalNumber1', sa.Numeric(precision=18, scale=4), nullable=True, comment="Ek sayı alanları; etiketi FieldDefinition'da"),
    sa.Column('AdditionalNumber2', sa.Numeric(precision=18, scale=4), nullable=True, comment="Ek sayı alanları; etiketi FieldDefinition'da"),
    sa.ForeignKeyConstraint(['ImportBatchId'], ['adm.ImportBatch.Id'], name=op.f('FK_ResourceGroupMember_ImportBatchId')),
    sa.PrimaryKeyConstraint('StagingRowId', name=op.f('PK_ResourceGroupMember')),
    schema='stg',
    comment='Grup eşleşmesi: kaynağın gruba üyeliği. Bir kaynak birden fazla gruba üye olabilir (birden fazla yetkinliği olan işçi). Geçerlilik tarihi yoktur: yüklü eşleşme bugünden itibaren geçerlidir. Gruptaki kaynak sayısı bu tablodan bilinir (K-180).'
    )
    op.create_index('UX_ResourceGroupMember_Current', 'ResourceGroupMember', ['LocationCode', 'ResourceGroupCode', 'ResourceCode'], unique=True, schema='stg', mssql_where=sa.text('IsCurrent = 1'))
    op.drop_table('ResourceGroupAssignment', schema='prc')
    op.drop_index(op.f('IX_ResourceGroupAssignment_ResourceGroupId'), table_name='ResourceGroupAssignment', schema='core')
    op.drop_index(op.f('IX_ResourceGroupAssignment_ResourceId'), table_name='ResourceGroupAssignment', schema='core')
    op.drop_table('ResourceGroupAssignment', schema='core')
    op.drop_table('ResourceGroupAssignment', schema='stg')
    op.drop_index(op.f('IX_OvertimeLimit_ShiftPlanId'), table_name='OvertimeLimit', schema='param')
    op.drop_table('OvertimeLimit', schema='param')
    op.drop_index(op.f('IX_ShiftPlan_ResourceGroupId'), table_name='ShiftPlan', schema='core')
    op.drop_index(op.f('IX_ShiftPlan_ShiftId'), table_name='ShiftPlan', schema='core')
    op.drop_table('ShiftPlan', schema='core')
    op.drop_table('Shift', schema='core')
    op.alter_column('Resource', 'ResourceType',
               existing_type=sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'),
               comment="ERP'den gelen ham değer; yalnız bilgi (raporlama ve filtre), planlama grubun bayraklarına bakar",
               existing_comment="ERP'den gelen ham değer; tip bayraklarla ifade edilir",
               existing_nullable=True,
               schema='core')
    op.alter_column('Resource', 'DailyCapacity',
               existing_type=sa.NUMERIC(precision=18, scale=4),
               comment="Kaynağın bir çalışma günündeki kapasitesi; geçici alan (7.8'de kalkar)",
               existing_comment='Bir adet kaynağın bir çalışma günündeki kapasitesi',
               existing_nullable=True,
               schema='core')
    op.alter_column('Resource', 'CalendarId',
               existing_type=sa.INTEGER(),
               comment="Çalışma takvimi (Smartchain ekranında atanır); geçici alan (7.8'de kalkar)",
               existing_comment='Çalışma takvimi (Smartchain ekranında atanır)',
               existing_nullable=True,
               schema='core')
    op.alter_column('Resource', 'SubconFixedLeadTimeDays',
               existing_type=sa.NUMERIC(precision=9, scale=2),
               comment="Fasonda sabit süre (taşıma ve kuyruk); geçici alan (7.8'de kalkar)",
               existing_comment='Fasonda sabit süre (taşıma ve kuyruk)',
               existing_nullable=True,
               schema='core')
    op.alter_column('Resource', 'SubconVariableDaysPerUnit',
               existing_type=sa.NUMERIC(precision=18, scale=6),
               comment="Fasonda birim başına gün (fasoncunun hızı); geçici alan (7.8'de kalkar)",
               existing_comment='Fasonda birim başına gün (fasoncunun hızı)',
               existing_nullable=True,
               schema='core')
    op.drop_index(op.f('IX_Resource_SubcontractorId'), table_name='Resource', schema='core')
    op.drop_constraint(op.f('FK_Resource_CapacityUnit'), 'Resource', schema='core', type_='foreignkey')
    _table_comment('core', 'Resource', 'Kaynak: tek bir makine, işçi ya da fason iş yeri. Planlama birimi kaynak değil kaynak grubudur (K-180): tip bayrakları, kritiklik, kapasite birimi ve fasoncu gruptadır; kaynak gruplarına `ResourceGroupMember` ile bağlanır.')
    op.drop_column('Resource', 'CapacityUnit', schema='core')
    op.drop_column('Resource', 'IsFurnace', schema='core')
    op.drop_column('Resource', 'Quantity', schema='core')
    op.drop_column('Resource', 'IsMold', schema='core')
    op.drop_column('Resource', 'CapacitySource', schema='core')
    op.drop_column('Resource', 'IsCritical', schema='core')
    op.drop_column('Resource', 'IsOther', schema='core')
    op.drop_column('Resource', 'IsMachine', schema='core')
    op.drop_column('Resource', 'SubcontractorId', schema='core')
    op.drop_column('Resource', 'IsEmployee', schema='core')
    op.drop_column('Resource', 'IsSubcontractor', schema='core')
    _table_comment('core', 'ResourceCapacityProfile', "Günlük kapasitenin dönemsel değişikliği. Birim kaynağın gruplarının ortak kapasite birimi; ekranda gösterilir, ayrı saklanmaz. Geçici tablo: 7.8'de yeniden tasarlanır (K-180). Smartchain'de ekrandan girilir; entegrasyondan gelmez (K-65).")
    op.add_column('ResourceGroup', sa.Column('IsEmployee', sa.Boolean(), nullable=True, comment='İşçi grubu mu (yetkinlik grubu)'), schema='core')
    op.add_column('ResourceGroup', sa.Column('IsMachine', sa.Boolean(), nullable=True, comment='Makine grubu mu'), schema='core')
    op.add_column('ResourceGroup', sa.Column('IsFurnace', sa.Boolean(), nullable=True, comment='Fırın grubu mu; Faz 1 planlamada kullanılmaz'), schema='core')
    op.add_column('ResourceGroup', sa.Column('IsMold', sa.Boolean(), nullable=True, comment='Kalıp grubu mu; Faz 1 planlamada kullanılmaz'), schema='core')
    op.add_column('ResourceGroup', sa.Column('IsOther', sa.Boolean(), nullable=True, comment='Diğer kaynak grubu mu'), schema='core')
    op.add_column('ResourceGroup', sa.Column('IsSubcontractor', sa.Boolean(), nullable=True, comment='Fason grubu mu'), schema='core')
    op.add_column('ResourceGroup', sa.Column('IsCritical', sa.Boolean(), nullable=True, comment='1: planda kısıt, 0: sonsuz kapasite (sadece raporlanır)'), schema='core')
    op.add_column('ResourceGroup', sa.Column('CapacityUnit', sa.Unicode(length=10), nullable=False, comment='Kapasite birimi (Saat, Adet, Ton…); rotadaki tüketim aynı birimde kabul edilir'), schema='core')
    op.add_column('ResourceGroup', sa.Column('SubcontractorId', sa.BigInteger(), nullable=True, comment='Fason grubunda fasoncu'), schema='core')
    op.alter_column('ResourceGroup', 'Type',
               existing_type=sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'),
               comment="ERP'den gelen ham değer; tip bayraklarla ifade edilir",
               existing_comment="Grup tipi; ERP'den gelen ham değer",
               existing_nullable=True,
               schema='core')
    op.alter_column('ResourceGroup', 'IsActive',
               existing_type=mssql.BIT(),
               comment='Aktif mi',
               existing_comment='Aktif',
               existing_nullable=True,
               schema='core')
    op.create_index(op.f('IX_ResourceGroup_SubcontractorId'), 'ResourceGroup', ['SubcontractorId'], unique=False, schema='core')
    op.create_foreign_key(op.f('FK_ResourceGroup_CapacityUnit'), 'ResourceGroup', 'UnitOfMeasure', ['CapacityUnit'], ['Code'], source_schema='core', referent_schema='core')
    _table_comment('core', 'ResourceGroup', "Kaynak grubu: planlama birimi (K-180). Rota ve iş emri operasyonu grubu gösterir; plan ve yük grup düzeyindedir. Tip, kritiklik, kapasite birimi ve fasoncu gruptadır. Gruptaki kaynak sayısı `ResourceGroupMember`'dan bilinir, ayrıca girilmez.")
    op.drop_column('ResourceGroup', 'IsCompetenceGroup', schema='core')
    op.drop_column('ResourceGroup', 'IsResourceGroup', schema='core')
    op.alter_column('Routing', 'ResourceGroupId',
               existing_type=sa.BIGINT(),
               nullable=False,
               existing_comment='Kaynak grubu',
               schema='core')
    op.alter_column('Routing', 'Consumption',
               existing_type=sa.NUMERIC(precision=18, scale=6),
               comment='Baz miktar için kaynak tüketimi (kaynak grubunun kapasite biriminde)',
               existing_comment='Baz miktar için kaynak tüketimi (kaynağın kapasite biriminde)',
               existing_nullable=False,
               schema='core')
    op.alter_column('Routing', 'ResourceNumber',
               existing_type=sa.INTEGER(),
               comment='Operasyonda gruptan aynı anda kullanılan kaynak adedi',
               existing_comment='Operasyonda aynı anda kullanılan kaynak adedi',
               existing_nullable=False,
               schema='core')
    op.drop_index(op.f('IX_Routing_ResourceId'), table_name='Routing', schema='core')
    _table_comment('core', 'Routing', 'Rota: her satır bir operasyon–kaynak grubu ilişkisi; sıra önce OperationNo, sonra SequenceNo. Aynı operasyonun kaynak grupları ayrı satırda, ResourceRole ile.')
    op.drop_column('Routing', 'ResourceId', schema='core')
    op.alter_column('WorkOrderOperation', 'ResourceGroupId',
               existing_type=sa.BIGINT(),
               nullable=False,
               existing_comment='Kaynak grubu',
               schema='core')
    op.drop_index(op.f('IX_WorkOrderOperation_ResourceId'), table_name='WorkOrderOperation', schema='core')
    op.drop_column('WorkOrderOperation', 'ResourceId', schema='core')
    op.drop_index(op.f('IX_AllocationRule_ResourceId'), table_name='AllocationRule', schema='param')
    _table_comment('param', 'AllocationRule', 'Kapasite alokasyonu: talep sınıfına kaynak grubu ve dönem bazında pay (K-180).')
    op.drop_column('AllocationRule', 'ResourceId', schema='param')
    _table_comment('param', 'ResourcePeriodLimit', "Dönem bazlı üst limit; kısıtsız kaynaklarda ve fasonda. Birim kaynağın gruplarının ortak kapasite birimi. Geçici tablo: 7.8'de yeniden tasarlanır (K-180).")
    op.add_column('CapacityLoad', sa.Column('ResourceGroupId', sa.BigInteger(), nullable=False, comment='Kaynak grubu'), schema='planning')
    op.drop_index(op.f('IX_CapacityLoad_ResourceId'), table_name='CapacityLoad', schema='planning')
    op.create_index(op.f('IX_CapacityLoad_ResourceGroupId'), 'CapacityLoad', ['ResourceGroupId'], unique=False, schema='planning')
    _table_comment('planning', 'CapacityLoad', 'Kaynak grubu ve dönem bazında kapasite ve kapasite yükü (plan ve yük grup düzeyindedir, K-180).')
    op.drop_column('CapacityLoad', 'ResourceId', schema='planning')
    op.alter_column('Resource', 'ResourceType',
               existing_type=sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'),
               comment="ERP'den gelen ham değer; yalnız bilgi (raporlama ve filtre), planlama grubun bayraklarına bakar",
               existing_comment="ERP'den gelen ham değer; tip bayraklarla ifade edilir",
               existing_nullable=True,
               schema='prc')
    _table_comment('prc', 'Resource', 'Kaynak: tek bir makine, işçi ya da fason iş yeri. Planlama birimi kaynak değil kaynak grubudur (K-180): tip bayrakları, kritiklik, kapasite birimi ve fasoncu gruptadır; kaynak gruplarına `ResourceGroupMember` ile bağlanır.')
    op.drop_column('Resource', 'CapacityUnit', schema='prc')
    op.drop_column('Resource', 'IsFurnace', schema='prc')
    op.drop_column('Resource', 'SubcontractorCode', schema='prc')
    op.drop_column('Resource', 'IsMold', schema='prc')
    op.drop_column('Resource', 'IsCritical', schema='prc')
    op.drop_column('Resource', 'IsOther', schema='prc')
    op.drop_column('Resource', 'IsMachine', schema='prc')
    op.drop_column('Resource', 'IsEmployee', schema='prc')
    op.drop_column('Resource', 'IsSubcontractor', schema='prc')
    op.add_column('ResourceGroup', sa.Column('IsEmployee', sa.Boolean(), nullable=True, comment='İşçi grubu mu (yetkinlik grubu)'), schema='prc')
    op.add_column('ResourceGroup', sa.Column('IsMachine', sa.Boolean(), nullable=True, comment='Makine grubu mu'), schema='prc')
    op.add_column('ResourceGroup', sa.Column('IsFurnace', sa.Boolean(), nullable=True, comment='Fırın grubu mu; Faz 1 planlamada kullanılmaz'), schema='prc')
    op.add_column('ResourceGroup', sa.Column('IsMold', sa.Boolean(), nullable=True, comment='Kalıp grubu mu; Faz 1 planlamada kullanılmaz'), schema='prc')
    op.add_column('ResourceGroup', sa.Column('IsOther', sa.Boolean(), nullable=True, comment='Diğer kaynak grubu mu'), schema='prc')
    op.add_column('ResourceGroup', sa.Column('IsSubcontractor', sa.Boolean(), nullable=True, comment='Fason grubu mu'), schema='prc')
    op.add_column('ResourceGroup', sa.Column('IsCritical', sa.Boolean(), nullable=True, comment='1: planda kısıt, 0: sonsuz kapasite (sadece raporlanır)'), schema='prc')
    op.add_column('ResourceGroup', sa.Column('CapacityUnit', sa.Unicode(length=10), nullable=True, comment='Kapasite birimi (Saat, Adet, Ton…); rotadaki tüketim aynı birimde kabul edilir'), schema='prc')
    op.add_column('ResourceGroup', sa.Column('SubcontractorCode', sa.Unicode(length=50), nullable=True, comment='Fasoncu'), schema='prc')
    op.alter_column('ResourceGroup', 'Type',
               existing_type=sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'),
               comment="ERP'den gelen ham değer; tip bayraklarla ifade edilir",
               existing_comment="Grup tipi; ERP'den gelen ham değer",
               existing_nullable=True,
               schema='prc')
    op.alter_column('ResourceGroup', 'IsActive',
               existing_type=mssql.BIT(),
               comment='Aktif mi',
               existing_comment='Aktif',
               existing_nullable=True,
               schema='prc')
    _table_comment('prc', 'ResourceGroup', "Kaynak grubu: planlama birimi (K-180). Rota ve iş emri operasyonu grubu gösterir; plan ve yük grup düzeyindedir. Tip, kritiklik, kapasite birimi ve fasoncu gruptadır. Gruptaki kaynak sayısı `ResourceGroupMember`'dan bilinir, ayrıca girilmez.")
    op.drop_column('ResourceGroup', 'IsCompetenceGroup', schema='prc')
    op.drop_column('ResourceGroup', 'IsResourceGroup', schema='prc')
    op.alter_column('Routing', 'Consumption',
               existing_type=sa.NUMERIC(precision=18, scale=6),
               comment='Baz miktar için kaynak tüketimi (kaynak grubunun kapasite biriminde)',
               existing_comment='Baz miktar için kaynak tüketimi (kaynağın kapasite biriminde)',
               existing_nullable=True,
               schema='prc')
    op.alter_column('Routing', 'ResourceNumber',
               existing_type=sa.INTEGER(),
               comment='Operasyonda gruptan aynı anda kullanılan kaynak adedi',
               existing_comment='Operasyonda aynı anda kullanılan kaynak adedi',
               existing_nullable=True,
               schema='prc')
    _table_comment('prc', 'Routing', 'Rota: her satır bir operasyon–kaynak grubu ilişkisi; sıra önce OperationNo, sonra SequenceNo. Aynı operasyonun kaynak grupları ayrı satırda, ResourceRole ile.')
    op.drop_column('Routing', 'ResourceCode', schema='prc')
    op.drop_column('WorkOrderOperation', 'ResourceCode', schema='prc')
    op.alter_column('Resource', 'ResourceType',
               existing_type=sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'),
               comment="ERP'den gelen ham değer; yalnız bilgi (raporlama ve filtre), planlama grubun bayraklarına bakar",
               existing_comment="ERP'den gelen ham değer; tip bayraklarla ifade edilir",
               existing_nullable=True,
               schema='stg')
    _table_comment('stg', 'Resource', 'Kaynak: tek bir makine, işçi ya da fason iş yeri. Planlama birimi kaynak değil kaynak grubudur (K-180): tip bayrakları, kritiklik, kapasite birimi ve fasoncu gruptadır; kaynak gruplarına `ResourceGroupMember` ile bağlanır.')
    op.drop_column('Resource', 'CapacityUnit', schema='stg')
    op.drop_column('Resource', 'IsFurnace', schema='stg')
    op.drop_column('Resource', 'SubcontractorCode', schema='stg')
    op.drop_column('Resource', 'IsMold', schema='stg')
    op.drop_column('Resource', 'IsCritical', schema='stg')
    op.drop_column('Resource', 'IsOther', schema='stg')
    op.drop_column('Resource', 'IsMachine', schema='stg')
    op.drop_column('Resource', 'IsEmployee', schema='stg')
    op.drop_column('Resource', 'IsSubcontractor', schema='stg')
    op.add_column('ResourceGroup', sa.Column('IsEmployee', sa.Boolean(), nullable=True, comment='İşçi grubu mu (yetkinlik grubu)'), schema='stg')
    op.add_column('ResourceGroup', sa.Column('IsMachine', sa.Boolean(), nullable=True, comment='Makine grubu mu'), schema='stg')
    op.add_column('ResourceGroup', sa.Column('IsFurnace', sa.Boolean(), nullable=True, comment='Fırın grubu mu; Faz 1 planlamada kullanılmaz'), schema='stg')
    op.add_column('ResourceGroup', sa.Column('IsMold', sa.Boolean(), nullable=True, comment='Kalıp grubu mu; Faz 1 planlamada kullanılmaz'), schema='stg')
    op.add_column('ResourceGroup', sa.Column('IsOther', sa.Boolean(), nullable=True, comment='Diğer kaynak grubu mu'), schema='stg')
    op.add_column('ResourceGroup', sa.Column('IsSubcontractor', sa.Boolean(), nullable=True, comment='Fason grubu mu'), schema='stg')
    op.add_column('ResourceGroup', sa.Column('IsCritical', sa.Boolean(), nullable=True, comment='1: planda kısıt, 0: sonsuz kapasite (sadece raporlanır)'), schema='stg')
    op.add_column('ResourceGroup', sa.Column('CapacityUnit', sa.Unicode(length=10), nullable=True, comment='Kapasite birimi (Saat, Adet, Ton…); rotadaki tüketim aynı birimde kabul edilir'), schema='stg')
    op.add_column('ResourceGroup', sa.Column('SubcontractorCode', sa.Unicode(length=50), nullable=True, comment='Fasoncu'), schema='stg')
    op.alter_column('ResourceGroup', 'Type',
               existing_type=sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'),
               comment="ERP'den gelen ham değer; tip bayraklarla ifade edilir",
               existing_comment="Grup tipi; ERP'den gelen ham değer",
               existing_nullable=True,
               schema='stg')
    op.alter_column('ResourceGroup', 'IsActive',
               existing_type=mssql.BIT(),
               comment='Aktif mi',
               existing_comment='Aktif',
               existing_nullable=True,
               schema='stg')
    _table_comment('stg', 'ResourceGroup', "Kaynak grubu: planlama birimi (K-180). Rota ve iş emri operasyonu grubu gösterir; plan ve yük grup düzeyindedir. Tip, kritiklik, kapasite birimi ve fasoncu gruptadır. Gruptaki kaynak sayısı `ResourceGroupMember`'dan bilinir, ayrıca girilmez.")
    op.drop_column('ResourceGroup', 'IsCompetenceGroup', schema='stg')
    op.drop_column('ResourceGroup', 'IsResourceGroup', schema='stg')
    op.alter_column('Routing', 'Consumption',
               existing_type=sa.NUMERIC(precision=18, scale=6),
               comment='Baz miktar için kaynak tüketimi (kaynak grubunun kapasite biriminde)',
               existing_comment='Baz miktar için kaynak tüketimi (kaynağın kapasite biriminde)',
               existing_nullable=True,
               schema='stg')
    op.alter_column('Routing', 'ResourceNumber',
               existing_type=sa.INTEGER(),
               comment='Operasyonda gruptan aynı anda kullanılan kaynak adedi',
               existing_comment='Operasyonda aynı anda kullanılan kaynak adedi',
               existing_nullable=True,
               schema='stg')
    _table_comment('stg', 'Routing', 'Rota: her satır bir operasyon–kaynak grubu ilişkisi; sıra önce OperationNo, sonra SequenceNo. Aynı operasyonun kaynak grupları ayrı satırda, ResourceRole ile.')
    op.drop_column('Routing', 'ResourceCode', schema='stg')
    op.drop_column('WorkOrderOperation', 'ResourceCode', schema='stg')
    op.create_index(op.f('IX_Routing_ResourceGroupId'), 'Routing', ['ResourceGroupId'], unique=False, schema='core')
    op.create_index(op.f('IX_WorkOrderOperation_ResourceGroupId'), 'WorkOrderOperation', ['ResourceGroupId'], unique=False, schema='core')

    # --- adm: varlık adı, kullanıcı kuralları, sözlük
    _rename_entity(OLD_ENTITY, NEW_ENTITY)
    _delete_user_rules()
    _clean_dictionary()
    if not context.is_offline_mode():  # bağlantısız SQL betiğinde satırlar yazılmaz; ilk bağlantılı geçişte kurulur
        sync(op.get_bind(), metadata)
    # sync var olan satırın zorunluluğuna dokunmaz: rota ve iş emri operasyonunda kaynak grubu artık zorunlu
    op.execute(f"UPDATE {FD} SET IsRequired = 1 WHERE TableName IN (N'Routing', N'WorkOrderOperation') AND FieldName = N'ResourceGroupId'")


def downgrade():
    # Veri geri gelmez: eski zorunlu alanları sağlayamayan satırlar silinir (başlığa bakın).
    op.execute("DELETE FROM core.Resource")
    op.execute("DELETE FROM core.ResourceGroup")
    op.execute("DELETE FROM planning.CapacityLoad")
    _rename_entity(NEW_ENTITY, OLD_ENTITY)
    # geri alışta artık olmayan alanların sözlük satırları (sync silmez)
    op.execute(f"DELETE FROM {FD} WHERE TableName = N'{OLD_ENTITY}' AND FieldName LIKE N'Additional%'")
    op.execute(f"DELETE FROM {FD} WHERE TableName = N'ResourceGroup' AND FieldName IN ({_in(MOVED + ('SubcontractorId',))})")
    op.execute(f"DELETE FROM {FD} WHERE TableName = N'CapacityLoad' AND FieldName = N'ResourceGroupId'")
    op.drop_index(op.f('IX_Routing_ResourceGroupId'), table_name='Routing', schema='core')
    op.drop_index(op.f('IX_WorkOrderOperation_ResourceGroupId'), table_name='WorkOrderOperation', schema='core')
    op.add_column('WorkOrderOperation', sa.Column('ResourceCode', sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'), autoincrement=False, nullable=True, comment='Kaynak kodu'), schema='stg')
    op.add_column('Routing', sa.Column('ResourceCode', sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'), autoincrement=False, nullable=True, comment='Kaynak kodu'), schema='stg')
    _table_comment('stg', 'Routing', 'Rota: her satır bir operasyon–kaynak ilişkisi; sıra önce OperationNo, sonra SequenceNo. Aynı operasyonun kaynakları ayrı satırda, ResourceRole ile.')
    op.alter_column('Routing', 'ResourceNumber',
               existing_type=sa.INTEGER(),
               comment='Operasyonda aynı anda kullanılan kaynak adedi',
               existing_comment='Operasyonda gruptan aynı anda kullanılan kaynak adedi',
               existing_nullable=True,
               schema='stg')
    op.alter_column('Routing', 'Consumption',
               existing_type=sa.NUMERIC(precision=18, scale=6),
               comment='Baz miktar için kaynak tüketimi (kaynağın kapasite biriminde)',
               existing_comment='Baz miktar için kaynak tüketimi (kaynak grubunun kapasite biriminde)',
               existing_nullable=True,
               schema='stg')
    op.add_column('ResourceGroup', sa.Column('IsResourceGroup', mssql.BIT(), autoincrement=False, nullable=True, comment='Kaynak grubu'), schema='stg')
    op.add_column('ResourceGroup', sa.Column('IsCompetenceGroup', mssql.BIT(), autoincrement=False, nullable=True, comment='Yetkinlik grubu'), schema='stg')
    _table_comment('stg', 'ResourceGroup', 'Kaynak ve yetkinlik grubu. Kapasite havuzu değil, uygun kaynaklar listesidir; kapasite yalnız kaynakta tutulur.')
    op.alter_column('ResourceGroup', 'IsActive',
               existing_type=mssql.BIT(),
               comment='Aktif',
               existing_comment='Aktif mi',
               existing_nullable=True,
               schema='stg')
    op.alter_column('ResourceGroup', 'Type',
               existing_type=sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'),
               comment="Grup tipi; ERP'den gelen ham değer",
               existing_comment="ERP'den gelen ham değer; tip bayraklarla ifade edilir",
               existing_nullable=True,
               schema='stg')
    op.drop_column('ResourceGroup', 'SubcontractorCode', schema='stg')
    op.drop_column('ResourceGroup', 'CapacityUnit', schema='stg')
    op.drop_column('ResourceGroup', 'IsCritical', schema='stg')
    op.drop_column('ResourceGroup', 'IsSubcontractor', schema='stg')
    op.drop_column('ResourceGroup', 'IsOther', schema='stg')
    op.drop_column('ResourceGroup', 'IsMold', schema='stg')
    op.drop_column('ResourceGroup', 'IsFurnace', schema='stg')
    op.drop_column('ResourceGroup', 'IsMachine', schema='stg')
    op.drop_column('ResourceGroup', 'IsEmployee', schema='stg')
    op.add_column('Resource', sa.Column('IsSubcontractor', mssql.BIT(), autoincrement=False, nullable=True, comment='Kaynak fason mu'), schema='stg')
    op.add_column('Resource', sa.Column('IsEmployee', mssql.BIT(), autoincrement=False, nullable=True, comment='Kaynak işçi mi'), schema='stg')
    op.add_column('Resource', sa.Column('IsMachine', mssql.BIT(), autoincrement=False, nullable=True, comment='Kaynak makine mi'), schema='stg')
    op.add_column('Resource', sa.Column('IsOther', mssql.BIT(), autoincrement=False, nullable=True, comment='Diğer kaynak mı'), schema='stg')
    op.add_column('Resource', sa.Column('IsCritical', mssql.BIT(), autoincrement=False, nullable=True, comment='1: planda kısıt, 0: sonsuz kapasite (sadece raporlanır)'), schema='stg')
    op.add_column('Resource', sa.Column('IsMold', mssql.BIT(), autoincrement=False, nullable=True, comment='Kaynak kalıp mı; Faz 1 planlamada kullanılmaz'), schema='stg')
    op.add_column('Resource', sa.Column('SubcontractorCode', sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'), autoincrement=False, nullable=True, comment='Fasoncu'), schema='stg')
    op.add_column('Resource', sa.Column('IsFurnace', mssql.BIT(), autoincrement=False, nullable=True, comment='Kaynak fırın mı; Faz 1 planlamada kullanılmaz'), schema='stg')
    op.add_column('Resource', sa.Column('CapacityUnit', sa.NVARCHAR(length=10, collation='Latin1_General_100_CI_AS_SC'), autoincrement=False, nullable=True, comment='Kapasite birimi (Saat, Adet, Ton…); rotadaki tüketim aynı birimde kabul edilir'), schema='stg')
    _table_comment('stg', 'Resource', 'Kaynak: makine, işçi, fason, diğer. Kapasite kaynağın kendi biriminde günlük kapasite olarak tutulur.')
    op.alter_column('Resource', 'ResourceType',
               existing_type=sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'),
               comment="ERP'den gelen ham değer; tip bayraklarla ifade edilir",
               existing_comment="ERP'den gelen ham değer; yalnız bilgi (raporlama ve filtre), planlama grubun bayraklarına bakar",
               existing_nullable=True,
               schema='stg')
    op.add_column('WorkOrderOperation', sa.Column('ResourceCode', sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'), autoincrement=False, nullable=True, comment='Kaynak kodu'), schema='prc')
    op.add_column('Routing', sa.Column('ResourceCode', sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'), autoincrement=False, nullable=True, comment='Kaynak kodu'), schema='prc')
    _table_comment('prc', 'Routing', 'Rota: her satır bir operasyon–kaynak ilişkisi; sıra önce OperationNo, sonra SequenceNo. Aynı operasyonun kaynakları ayrı satırda, ResourceRole ile.')
    op.alter_column('Routing', 'ResourceNumber',
               existing_type=sa.INTEGER(),
               comment='Operasyonda aynı anda kullanılan kaynak adedi',
               existing_comment='Operasyonda gruptan aynı anda kullanılan kaynak adedi',
               existing_nullable=True,
               schema='prc')
    op.alter_column('Routing', 'Consumption',
               existing_type=sa.NUMERIC(precision=18, scale=6),
               comment='Baz miktar için kaynak tüketimi (kaynağın kapasite biriminde)',
               existing_comment='Baz miktar için kaynak tüketimi (kaynak grubunun kapasite biriminde)',
               existing_nullable=True,
               schema='prc')
    op.add_column('ResourceGroup', sa.Column('IsResourceGroup', mssql.BIT(), autoincrement=False, nullable=True, comment='Kaynak grubu'), schema='prc')
    op.add_column('ResourceGroup', sa.Column('IsCompetenceGroup', mssql.BIT(), autoincrement=False, nullable=True, comment='Yetkinlik grubu'), schema='prc')
    _table_comment('prc', 'ResourceGroup', 'Kaynak ve yetkinlik grubu. Kapasite havuzu değil, uygun kaynaklar listesidir; kapasite yalnız kaynakta tutulur.')
    op.alter_column('ResourceGroup', 'IsActive',
               existing_type=mssql.BIT(),
               comment='Aktif',
               existing_comment='Aktif mi',
               existing_nullable=True,
               schema='prc')
    op.alter_column('ResourceGroup', 'Type',
               existing_type=sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'),
               comment="Grup tipi; ERP'den gelen ham değer",
               existing_comment="ERP'den gelen ham değer; tip bayraklarla ifade edilir",
               existing_nullable=True,
               schema='prc')
    op.drop_column('ResourceGroup', 'SubcontractorCode', schema='prc')
    op.drop_column('ResourceGroup', 'CapacityUnit', schema='prc')
    op.drop_column('ResourceGroup', 'IsCritical', schema='prc')
    op.drop_column('ResourceGroup', 'IsSubcontractor', schema='prc')
    op.drop_column('ResourceGroup', 'IsOther', schema='prc')
    op.drop_column('ResourceGroup', 'IsMold', schema='prc')
    op.drop_column('ResourceGroup', 'IsFurnace', schema='prc')
    op.drop_column('ResourceGroup', 'IsMachine', schema='prc')
    op.drop_column('ResourceGroup', 'IsEmployee', schema='prc')
    op.add_column('Resource', sa.Column('IsSubcontractor', mssql.BIT(), autoincrement=False, nullable=True, comment='Kaynak fason mu'), schema='prc')
    op.add_column('Resource', sa.Column('IsEmployee', mssql.BIT(), autoincrement=False, nullable=True, comment='Kaynak işçi mi'), schema='prc')
    op.add_column('Resource', sa.Column('IsMachine', mssql.BIT(), autoincrement=False, nullable=True, comment='Kaynak makine mi'), schema='prc')
    op.add_column('Resource', sa.Column('IsOther', mssql.BIT(), autoincrement=False, nullable=True, comment='Diğer kaynak mı'), schema='prc')
    op.add_column('Resource', sa.Column('IsCritical', mssql.BIT(), autoincrement=False, nullable=True, comment='1: planda kısıt, 0: sonsuz kapasite (sadece raporlanır)'), schema='prc')
    op.add_column('Resource', sa.Column('IsMold', mssql.BIT(), autoincrement=False, nullable=True, comment='Kaynak kalıp mı; Faz 1 planlamada kullanılmaz'), schema='prc')
    op.add_column('Resource', sa.Column('SubcontractorCode', sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'), autoincrement=False, nullable=True, comment='Fasoncu'), schema='prc')
    op.add_column('Resource', sa.Column('IsFurnace', mssql.BIT(), autoincrement=False, nullable=True, comment='Kaynak fırın mı; Faz 1 planlamada kullanılmaz'), schema='prc')
    op.add_column('Resource', sa.Column('CapacityUnit', sa.NVARCHAR(length=10, collation='Latin1_General_100_CI_AS_SC'), autoincrement=False, nullable=True, comment='Kapasite birimi (Saat, Adet, Ton…); rotadaki tüketim aynı birimde kabul edilir'), schema='prc')
    _table_comment('prc', 'Resource', 'Kaynak: makine, işçi, fason, diğer. Kapasite kaynağın kendi biriminde günlük kapasite olarak tutulur.')
    op.alter_column('Resource', 'ResourceType',
               existing_type=sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'),
               comment="ERP'den gelen ham değer; tip bayraklarla ifade edilir",
               existing_comment="ERP'den gelen ham değer; yalnız bilgi (raporlama ve filtre), planlama grubun bayraklarına bakar",
               existing_nullable=True,
               schema='prc')
    op.add_column('CapacityLoad', sa.Column('ResourceId', sa.BIGINT(), autoincrement=False, nullable=False, comment='Kaynak'), schema='planning')
    _table_comment('planning', 'CapacityLoad', 'Kaynak ve dönem bazında kapasite ve kapasite yükü.')
    op.drop_index(op.f('IX_CapacityLoad_ResourceGroupId'), table_name='CapacityLoad', schema='planning')
    op.create_index(op.f('IX_CapacityLoad_ResourceId'), 'CapacityLoad', ['ResourceId'], unique=False, schema='planning')
    op.drop_column('CapacityLoad', 'ResourceGroupId', schema='planning')
    _table_comment('param', 'ResourcePeriodLimit', 'Dönem bazlı üst limit; kısıtsız kaynaklarda ve fasonda. Birim kaynağın kapasite birimi.')
    op.add_column('AllocationRule', sa.Column('ResourceId', sa.BIGINT(), autoincrement=False, nullable=True, comment='Kaynak'), schema='param')
    _table_comment('param', 'AllocationRule', 'Kapasite alokasyonu: talep sınıfına kaynak (grubu) ve dönem bazında pay.')
    op.create_index(op.f('IX_AllocationRule_ResourceId'), 'AllocationRule', ['ResourceId'], unique=False, schema='param')
    op.add_column('WorkOrderOperation', sa.Column('ResourceId', sa.BIGINT(), autoincrement=False, nullable=True, comment='Kaynak'), schema='core')
    op.create_index(op.f('IX_WorkOrderOperation_ResourceId'), 'WorkOrderOperation', ['ResourceId'], unique=False, schema='core')
    op.alter_column('WorkOrderOperation', 'ResourceGroupId',
               existing_type=sa.BIGINT(),
               nullable=True,
               existing_comment='Kaynak grubu',
               schema='core')
    op.add_column('Routing', sa.Column('ResourceId', sa.BIGINT(), autoincrement=False, nullable=True, comment='Kaynak'), schema='core')
    _table_comment('core', 'Routing', 'Rota: her satır bir operasyon–kaynak ilişkisi; sıra önce OperationNo, sonra SequenceNo. Aynı operasyonun kaynakları ayrı satırda, ResourceRole ile.')
    op.create_index(op.f('IX_Routing_ResourceId'), 'Routing', ['ResourceId'], unique=False, schema='core')
    op.alter_column('Routing', 'ResourceNumber',
               existing_type=sa.INTEGER(),
               comment='Operasyonda aynı anda kullanılan kaynak adedi',
               existing_comment='Operasyonda gruptan aynı anda kullanılan kaynak adedi',
               existing_nullable=False,
               schema='core')
    op.alter_column('Routing', 'Consumption',
               existing_type=sa.NUMERIC(precision=18, scale=6),
               comment='Baz miktar için kaynak tüketimi (kaynağın kapasite biriminde)',
               existing_comment='Baz miktar için kaynak tüketimi (kaynak grubunun kapasite biriminde)',
               existing_nullable=False,
               schema='core')
    op.alter_column('Routing', 'ResourceGroupId',
               existing_type=sa.BIGINT(),
               nullable=True,
               existing_comment='Kaynak grubu',
               schema='core')
    op.add_column('ResourceGroup', sa.Column('IsResourceGroup', mssql.BIT(), autoincrement=False, nullable=True, comment='Kaynak grubu'), schema='core')
    op.add_column('ResourceGroup', sa.Column('IsCompetenceGroup', mssql.BIT(), autoincrement=False, nullable=True, comment='Yetkinlik grubu'), schema='core')
    _table_comment('core', 'ResourceGroup', 'Kaynak ve yetkinlik grubu. Kapasite havuzu değil, uygun kaynaklar listesidir; kapasite yalnız kaynakta tutulur.')
    op.drop_constraint(op.f('FK_ResourceGroup_CapacityUnit'), 'ResourceGroup', schema='core', type_='foreignkey')
    op.drop_index(op.f('IX_ResourceGroup_SubcontractorId'), table_name='ResourceGroup', schema='core')
    op.alter_column('ResourceGroup', 'IsActive',
               existing_type=mssql.BIT(),
               comment='Aktif',
               existing_comment='Aktif mi',
               existing_nullable=True,
               schema='core')
    op.alter_column('ResourceGroup', 'Type',
               existing_type=sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'),
               comment="Grup tipi; ERP'den gelen ham değer",
               existing_comment="ERP'den gelen ham değer; tip bayraklarla ifade edilir",
               existing_nullable=True,
               schema='core')
    op.drop_column('ResourceGroup', 'SubcontractorId', schema='core')
    op.drop_column('ResourceGroup', 'CapacityUnit', schema='core')
    op.drop_column('ResourceGroup', 'IsCritical', schema='core')
    op.drop_column('ResourceGroup', 'IsSubcontractor', schema='core')
    op.drop_column('ResourceGroup', 'IsOther', schema='core')
    op.drop_column('ResourceGroup', 'IsMold', schema='core')
    op.drop_column('ResourceGroup', 'IsFurnace', schema='core')
    op.drop_column('ResourceGroup', 'IsMachine', schema='core')
    op.drop_column('ResourceGroup', 'IsEmployee', schema='core')
    _table_comment('core', 'ResourceCapacityProfile', "Günlük kapasitenin dönemsel değişikliği (ör. ikinci vardiya açıldı). Birim kaynağın CapacityUnit'i; ekranda gösterilir, ayrı saklanmaz. Smartchain'de ekrandan girilir; entegrasyondan gelmez (K-65).")
    op.add_column('Resource', sa.Column('IsSubcontractor', mssql.BIT(), autoincrement=False, nullable=True, comment='Kaynak fason mu'), schema='core')
    op.add_column('Resource', sa.Column('IsEmployee', mssql.BIT(), autoincrement=False, nullable=True, comment='Kaynak işçi mi'), schema='core')
    op.add_column('Resource', sa.Column('SubcontractorId', sa.BIGINT(), autoincrement=False, nullable=True, comment='Fasonda fasoncu'), schema='core')
    op.add_column('Resource', sa.Column('IsMachine', mssql.BIT(), autoincrement=False, nullable=True, comment='Kaynak makine mi'), schema='core')
    op.add_column('Resource', sa.Column('IsOther', mssql.BIT(), autoincrement=False, nullable=True, comment='Diğer kaynak mı'), schema='core')
    op.add_column('Resource', sa.Column('IsCritical', mssql.BIT(), autoincrement=False, nullable=True, comment='1: planda kısıt, 0: sonsuz kapasite (sadece raporlanır)'), schema='core')
    op.add_column('Resource', sa.Column('CapacitySource', sa.NVARCHAR(length=10, collation='Latin1_General_100_CI_AS_SC'), autoincrement=False, nullable=True, comment='İşçi gruplarında: Vardiyadan | Doğrudan'), schema='core')
    op.add_column('Resource', sa.Column('IsMold', mssql.BIT(), autoincrement=False, nullable=True, comment='Kaynak kalıp mı; Faz 1 planlamada kullanılmaz'), schema='core')
    op.add_column('Resource', sa.Column('Quantity', sa.INTEGER(), autoincrement=False, nullable=True, comment='Paralel kaynak adedi; Smartchain ekranında girilir, aktarımda önceki versiyondan gelir'), schema='core')
    op.add_column('Resource', sa.Column('IsFurnace', mssql.BIT(), autoincrement=False, nullable=True, comment='Kaynak fırın mı; Faz 1 planlamada kullanılmaz'), schema='core')
    op.add_column('Resource', sa.Column('CapacityUnit', sa.NVARCHAR(length=10, collation='Latin1_General_100_CI_AS_SC'), autoincrement=False, nullable=False, comment='Kapasite birimi (Saat, Adet, Ton…); rotadaki tüketim aynı birimde kabul edilir'), schema='core')
    _table_comment('core', 'Resource', 'Kaynak: makine, işçi, fason, diğer. Kapasite kaynağın kendi biriminde günlük kapasite olarak tutulur.')
    op.create_foreign_key(op.f('FK_Resource_CapacityUnit'), 'Resource', 'UnitOfMeasure', ['CapacityUnit'], ['Code'], source_schema='core', referent_schema='core')
    op.create_index(op.f('IX_Resource_SubcontractorId'), 'Resource', ['SubcontractorId'], unique=False, schema='core')
    op.alter_column('Resource', 'SubconVariableDaysPerUnit',
               existing_type=sa.NUMERIC(precision=18, scale=6),
               comment='Fasonda birim başına gün (fasoncunun hızı)',
               existing_comment="Fasonda birim başına gün (fasoncunun hızı); geçici alan (7.8'de kalkar)",
               existing_nullable=True,
               schema='core')
    op.alter_column('Resource', 'SubconFixedLeadTimeDays',
               existing_type=sa.NUMERIC(precision=9, scale=2),
               comment='Fasonda sabit süre (taşıma ve kuyruk)',
               existing_comment="Fasonda sabit süre (taşıma ve kuyruk); geçici alan (7.8'de kalkar)",
               existing_nullable=True,
               schema='core')
    op.alter_column('Resource', 'CalendarId',
               existing_type=sa.INTEGER(),
               comment='Çalışma takvimi (Smartchain ekranında atanır)',
               existing_comment="Çalışma takvimi (Smartchain ekranında atanır); geçici alan (7.8'de kalkar)",
               existing_nullable=True,
               schema='core')
    op.alter_column('Resource', 'DailyCapacity',
               existing_type=sa.NUMERIC(precision=18, scale=4),
               comment='Bir adet kaynağın bir çalışma günündeki kapasitesi',
               existing_comment="Kaynağın bir çalışma günündeki kapasitesi; geçici alan (7.8'de kalkar)",
               existing_nullable=True,
               schema='core')
    op.alter_column('Resource', 'ResourceType',
               existing_type=sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'),
               comment="ERP'den gelen ham değer; tip bayraklarla ifade edilir",
               existing_comment="ERP'den gelen ham değer; yalnız bilgi (raporlama ve filtre), planlama grubun bayraklarına bakar",
               existing_nullable=True,
               schema='core')
    op.create_table('Shift',
    sa.Column('Id', sa.BIGINT(), autoincrement=False, nullable=False, comment='Kayıt kimliği'),
    sa.Column('LocationId', sa.INTEGER(), autoincrement=False, nullable=False, comment='Lokasyon'),
    sa.Column('Code', sa.NVARCHAR(length=20, collation='Latin1_General_100_CI_AS_SC'), autoincrement=False, nullable=False, comment='Vardiya kodu'),
    sa.Column('StartTime', mssql.TIME(), autoincrement=False, nullable=False, comment='Başlangıç saati'),
    sa.Column('EndTime', mssql.TIME(), autoincrement=False, nullable=False, comment='Bitiş saati'),
    sa.Column('BreakMinutes', sa.INTEGER(), autoincrement=False, nullable=True, comment='Mola süresi (dk)'),
    sa.Column('VersionFrom', sa.INTEGER(), autoincrement=False, nullable=False, comment='Kaydın geçerli olduğu ilk veri versiyonu'),
    sa.Column('VersionTo', sa.INTEGER(), autoincrement=False, nullable=True, comment='Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş'),
    sa.Column('ImportBatchId', sa.BIGINT(), autoincrement=False, nullable=True, comment='Kaydı getiren yükleme partisi'),
    sa.Column('BusinessKey', sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'), autoincrement=False, nullable=False, comment='İş anahtarı; kod ya da kodların birleşimi'),
    sa.Column('UpdatedAt', mssql.DATETIME2(), autoincrement=False, nullable=False, comment='Son değişiklik zamanı'),
    sa.ForeignKeyConstraint(['ImportBatchId'], ['adm.ImportBatch.Id'], name=op.f('FK_Shift_ImportBatchId')),
    sa.ForeignKeyConstraint(['LocationId'], ['core.Location.Id'], name=op.f('FK_Shift_LocationId')),
    sa.PrimaryKeyConstraint('Id', 'VersionFrom', name=op.f('PK_Shift')),
    schema='core',
    comment="Vardiya tanımı. Smartchain'de ekrandan girilir; entegrasyondan gelmez (K-65)."
    )
    op.create_table('ShiftPlan',
    sa.Column('Id', sa.BIGINT(), autoincrement=False, nullable=False, comment='Kayıt kimliği'),
    sa.Column('ResourceGroupId', sa.BIGINT(), autoincrement=False, nullable=True, comment='Kaynak ya da yetkinlik grubu'),
    sa.Column('ShiftId', sa.BIGINT(), autoincrement=False, nullable=False, comment='Vardiya'),
    sa.Column('ValidFrom', sa.DATE(), autoincrement=False, nullable=False, comment='Başlangıç'),
    sa.Column('ValidTo', sa.DATE(), autoincrement=False, nullable=False, comment='Bitiş'),
    sa.Column('Headcount', sa.INTEGER(), autoincrement=False, nullable=False, comment='Kişi sayısı'),
    sa.Column('VersionFrom', sa.INTEGER(), autoincrement=False, nullable=False, comment='Kaydın geçerli olduğu ilk veri versiyonu'),
    sa.Column('VersionTo', sa.INTEGER(), autoincrement=False, nullable=True, comment='Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş'),
    sa.Column('ImportBatchId', sa.BIGINT(), autoincrement=False, nullable=True, comment='Kaydı getiren yükleme partisi'),
    sa.Column('BusinessKey', sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'), autoincrement=False, nullable=False, comment='İş anahtarı; kod ya da kodların birleşimi'),
    sa.Column('UpdatedAt', mssql.DATETIME2(), autoincrement=False, nullable=False, comment='Son değişiklik zamanı'),
    sa.ForeignKeyConstraint(['ImportBatchId'], ['adm.ImportBatch.Id'], name=op.f('FK_ShiftPlan_ImportBatchId')),
    sa.PrimaryKeyConstraint('Id', 'VersionFrom', name=op.f('PK_ShiftPlan')),
    schema='core',
    comment="Dönem bazında grup–vardiya–kişi sayısı. Çalışmada geçici değiştirilebilir. Smartchain'de ekrandan girilir; entegrasyondan gelmez (K-65)."
    )
    op.create_index(op.f('IX_ShiftPlan_ShiftId'), 'ShiftPlan', ['ShiftId'], unique=False, schema='core')
    op.create_index(op.f('IX_ShiftPlan_ResourceGroupId'), 'ShiftPlan', ['ResourceGroupId'], unique=False, schema='core')
    op.create_table('OvertimeLimit',
    sa.Column('Id', sa.BIGINT(), sa.Identity(always=False, start=1, increment=1), autoincrement=True, nullable=False, comment='Kayıt kimliği'),
    sa.Column('ShiftPlanId', sa.BIGINT(), autoincrement=False, nullable=False, comment='Vardiya planı'),
    sa.Column('MaxOvertimeHours', sa.NUMERIC(precision=9, scale=2), autoincrement=False, nullable=False, comment='Dönem başına en fazla fazla mesai (saat)'),
    sa.Column('ScenarioDefinitionId', sa.INTEGER(), autoincrement=False, nullable=False, comment='Senaryo'),
    sa.ForeignKeyConstraint(['ScenarioDefinitionId'], ['param.ScenarioDefinition.Id'], name=op.f('FK_OvertimeLimit_ScenarioDefinitionId')),
    sa.PrimaryKeyConstraint('Id', name=op.f('PK_OvertimeLimit')),
    schema='param',
    comment='Fazla mesai üst limiti (vardiya ve dönem bazında).'
    )
    op.create_index(op.f('IX_OvertimeLimit_ShiftPlanId'), 'OvertimeLimit', ['ShiftPlanId'], unique=False, schema='param')
    op.create_table('ResourceGroupAssignment',
    sa.Column('StagingRowId', sa.BIGINT(), sa.Identity(always=False, start=1, increment=1), autoincrement=True, nullable=False, comment='Satır kimliği'),
    sa.Column('ImportBatchId', sa.BIGINT(), autoincrement=False, nullable=False, comment='Yükleme partisi'),
    sa.Column('ErrorText', sa.NVARCHAR(length=400, collation='Latin1_General_100_CI_AS_SC'), autoincrement=False, nullable=True, comment='Hata açıklaması'),
    sa.Column('LocationCode', sa.NVARCHAR(length=30, collation='Latin1_General_100_CI_AS_SC'), autoincrement=False, nullable=True, comment='Lokasyon kodu'),
    sa.Column('ResourceGroupCode', sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'), autoincrement=False, nullable=True, comment='Kaynak ya da yetkinlik grubu'),
    sa.Column('ResourceCode', sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'), autoincrement=False, nullable=True, comment='Kaynak kodu'),
    sa.Column('ValidFrom', sa.DATE(), autoincrement=False, nullable=True, comment='Geçerlilik başlangıcı'),
    sa.Column('ValidTo', sa.DATE(), autoincrement=False, nullable=True, comment='Geçerlilik bitişi'),
    sa.Column('SourceRowNo', sa.INTEGER(), autoincrement=False, nullable=True, comment='Kaynaktaki satır no'),
    sa.Column('IsCurrent', mssql.BIT(), server_default=sa.text('((0))'), autoincrement=False, nullable=False, comment='Tablonun güncel hâlinde mi (K-133)'),
    sa.Column('SupersededAt', mssql.DATETIME2(), autoincrement=False, nullable=True, comment='Satırın güncel hâlden çıktığı zaman (UTC; K-160)'),
    sa.ForeignKeyConstraint(['ImportBatchId'], ['adm.ImportBatch.Id'], name=op.f('FK_ResourceGroupAssignment_ImportBatchId')),
    sa.PrimaryKeyConstraint('StagingRowId', name=op.f('PK_ResourceGroupAssignment')),
    schema='stg',
    comment='Kaynağın gruba ataması; bir kaynak birden fazla gruba atanabilir, yetkinlik matrisi bu tablodur. Geçerlilik tarihleri yalnız girdi.'
    )
    op.create_table('ResourceGroupAssignment',
    sa.Column('Id', sa.BIGINT(), autoincrement=False, nullable=False, comment='Kayıt kimliği'),
    sa.Column('LocationId', sa.INTEGER(), autoincrement=False, nullable=False, comment='Lokasyon'),
    sa.Column('ResourceGroupId', sa.BIGINT(), autoincrement=False, nullable=False, comment='Kaynak ya da yetkinlik grubu'),
    sa.Column('ResourceId', sa.BIGINT(), autoincrement=False, nullable=False, comment='Kaynak'),
    sa.Column('ValidFrom', sa.DATE(), autoincrement=False, nullable=True, comment='Geçerlilik başlangıcı'),
    sa.Column('ValidTo', sa.DATE(), autoincrement=False, nullable=True, comment='Geçerlilik bitişi'),
    sa.Column('VersionFrom', sa.INTEGER(), autoincrement=False, nullable=False, comment='Kaydın geçerli olduğu ilk veri versiyonu'),
    sa.Column('VersionTo', sa.INTEGER(), autoincrement=False, nullable=True, comment='Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş'),
    sa.Column('ImportBatchId', sa.BIGINT(), autoincrement=False, nullable=True, comment='Kaydı getiren yükleme partisi'),
    sa.Column('BusinessKey', sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'), autoincrement=False, nullable=False, comment='İş anahtarı; kod ya da kodların birleşimi'),
    sa.Column('UpdatedAt', mssql.DATETIME2(), autoincrement=False, nullable=False, comment='Son değişiklik zamanı'),
    sa.ForeignKeyConstraint(['ImportBatchId'], ['adm.ImportBatch.Id'], name=op.f('FK_ResourceGroupAssignment_ImportBatchId')),
    sa.ForeignKeyConstraint(['LocationId'], ['core.Location.Id'], name=op.f('FK_ResourceGroupAssignment_LocationId')),
    sa.PrimaryKeyConstraint('Id', 'VersionFrom', name=op.f('PK_ResourceGroupAssignment')),
    schema='core',
    comment='Kaynağın gruba ataması; bir kaynak birden fazla gruba atanabilir, yetkinlik matrisi bu tablodur. Geçerlilik tarihleri yalnız girdi.'
    )
    op.create_index(op.f('IX_ResourceGroupAssignment_ResourceId'), 'ResourceGroupAssignment', ['ResourceId'], unique=False, schema='core')
    op.create_index(op.f('IX_ResourceGroupAssignment_ResourceGroupId'), 'ResourceGroupAssignment', ['ResourceGroupId'], unique=False, schema='core')
    op.create_table('ResourceGroupAssignment',
    sa.Column('StagingRowId', sa.BIGINT(), autoincrement=False, nullable=False, comment='Ham satırın kimliği (kopyalanır)'),
    sa.Column('ImportBatchId', sa.BIGINT(), autoincrement=False, nullable=False, comment='Satırın geldiği parti'),
    sa.Column('SourceRowNo', sa.INTEGER(), autoincrement=False, nullable=True, comment='Kaynaktaki satır no'),
    sa.Column('RowStatus', sa.NVARCHAR(length=15, collation='Latin1_General_100_CI_AS_SC'), server_default=sa.text("(N'Yeni')"), autoincrement=False, nullable=False, comment='Yeni | Hatalı | Aktarıldı; Hata bulgusu varsa Hatalı, load almaz (K-134)'),
    sa.Column('LocationCode', sa.NVARCHAR(length=30, collation='Latin1_General_100_CI_AS_SC'), autoincrement=False, nullable=True, comment='Lokasyon kodu'),
    sa.Column('ResourceGroupCode', sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'), autoincrement=False, nullable=True, comment='Kaynak ya da yetkinlik grubu'),
    sa.Column('ResourceCode', sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'), autoincrement=False, nullable=True, comment='Kaynak kodu'),
    sa.Column('ValidFrom', sa.DATE(), autoincrement=False, nullable=True, comment='Geçerlilik başlangıcı'),
    sa.Column('ValidTo', sa.DATE(), autoincrement=False, nullable=True, comment='Geçerlilik bitişi'),
    sa.PrimaryKeyConstraint('StagingRowId', name=op.f('PK_ResourceGroupAssignment')),
    schema='prc',
    comment='Kaynağın gruba ataması; bir kaynak birden fazla gruba atanabilir, yetkinlik matrisi bu tablodur. Geçerlilik tarihleri yalnız girdi.'
    )
    op.drop_index('UX_ResourceGroupMember_Current', table_name='ResourceGroupMember', schema='stg', mssql_where=sa.text('IsCurrent = 1'))
    op.drop_table('ResourceGroupMember', schema='stg')
    op.drop_index('UX_ResourceGroupMember_LocationId_ResourceGroupId_ResourceId', table_name='ResourceGroupMember', schema='core', mssql_where=sa.text('VersionTo IS NULL'))
    op.drop_index(op.f('IX_ResourceGroupMember_ResourceId'), table_name='ResourceGroupMember', schema='core')
    op.drop_index(op.f('IX_ResourceGroupMember_ResourceGroupId'), table_name='ResourceGroupMember', schema='core')
    op.drop_table('ResourceGroupMember', schema='core')
    op.drop_index('UX_ResourceGroupMember_Key', table_name='ResourceGroupMember', schema='prc')
    op.drop_table('ResourceGroupMember', schema='prc')
    op.create_index(op.f('IX_Routing_ResourceGroupId'), 'Routing', ['ResourceGroupId'], unique=False, schema='core')
    op.create_index(op.f('IX_WorkOrderOperation_ResourceGroupId'), 'WorkOrderOperation', ['ResourceGroupId'], unique=False, schema='core')
    if not context.is_offline_mode():
        sync(op.get_bind(), metadata)  # geri gelen alanların sözlük satırları; kalkanlarınki kalır (sync silmez)
    op.execute(f"UPDATE {FD} SET IsRequired = 0 WHERE TableName IN (N'Routing', N'WorkOrderOperation') AND FieldName = N'ResourceGroupId'")
