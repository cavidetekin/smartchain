"""0067 · Kapasite yönetimi: giriş tabloları, önbelleğin yeni tanesi, geçici alan ve tabloların kalkması (K-185)

Yeni tablolar (param; senaryolu, Baz + fark): WorkPattern (çalışma düzeni), OvertimeLimit (ek mesai limiti), ResourceDowntime (bakım ve duruş),
FactoryCalendar (fabrika takvimi). ResourceEfficiency yeni yapıya geçer (grup ya da kaynak, bitiş isteğe bağlı, fark alanları).
Önbellek tablosu cache.ResourceCapacityDay yeni tanesiyle (kaynak grubu × kaynak × gün) yeniden kurulur.
Kalkanlar: core.Resource üzerinde DailyCapacity, CalendarId, SubconPlanningType, SubconFixedLeadTimeDays, SubconVariableDaysPerUnit;
core.Calendar, core.CalendarDay, core.ResourceCapacityProfile, core.ResourceDowntime, param.ResourcePeriodLimit.

VERİ TAŞINMAZ: eski kapasite verisi (takvim, kapasite profili, duruş, kaynaktaki günlük kapasite) silinir; yeni girişler Kapasite yönetimi
ekranından ya da sentetik veriyle gelir. Geçişten sonra sentetik veri yeniden yüklenir. Önbellek boşalır (ilk kullanımda yeniden kurulur).
Geri alış yapıyı döndürür, veriyi döndürmez: yeni giriş tablolarındaki kayıtlar da silinir.

Revision ID: 0067
Revises: 0066
Create Date: 2026-11-19
"""
from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql

from dictionary import sync
from models import metadata

revision = '0067'
down_revision = '0066'
branch_labels = None
depends_on = None

GONE_TABLES = ('Calendar', 'CalendarDay', 'ResourceCapacityProfile', 'ResourcePeriodLimit')
GONE_FIELDS = {'Resource': ('DailyCapacity', 'CalendarId', 'SubconPlanningType', 'SubconFixedLeadTimeDays', 'SubconVariableDaysPerUnit')}
REBUILT = ('ResourceDowntime', 'ResourceEfficiency')   # alanları değişti: sözlük satırları yeniden kurulur
NEW_TABLES = ('WorkPattern', 'OvertimeLimit', 'FactoryCalendar')


def _in(names) -> str:
    return ", ".join(f"N'{n}'" for n in names)


def _forget(tables, fields) -> None:
    """Kalkan tablo ve alanların alan tanımı, manuel değer ve değer kaynağı satırları (sync silmez)."""
    for table in ('FieldDefinition', 'ManualValue', 'FieldValueSource'):
        op.execute(f"DELETE FROM adm.[{table}] WHERE TableName IN ({_in(tables)})")
        for entity, names in fields.items():
            op.execute(f"DELETE FROM adm.[{table}] WHERE TableName = N'{entity}' AND FieldName IN ({_in(names)})")


def _empty_cache() -> None:
    op.execute("DELETE FROM cache.PeriodCacheState")
    op.drop_table('ResourceCapacityDay', schema='cache')


def upgrade():
    _forget((*GONE_TABLES, *REBUILT), GONE_FIELDS)
    op.create_table('FactoryCalendar',
    sa.Column('Id', sa.BigInteger(), autoincrement=True, nullable=False, comment='Kayıt kimliği'),
    sa.Column('ScenarioDefinitionId', sa.Integer(), nullable=False, comment='Senaryo'),
    sa.Column('BaseRowId', sa.BigInteger(), nullable=True, comment="Baz'ı izleyen senaryoda Baz'daki satırın farkıysa o satırın kimliği; senaryonun kendi satırında ve Baz'da boş"),
    sa.Column('OverriddenFields', sa.Unicode(length=400), nullable=True, comment='Fark satırında senaryonun değiştirdiği alanların adları (virgüllerle çevrili: ",ValidTo,DailyCapacity,"); yalnız bu alanlar senaryodan, gerisi Baz satırından okunur'),
    sa.Column('IsValid', sa.Boolean(), server_default=sa.text('1'), nullable=False, comment='Geçerli (K-176): Hayır ise kayıt bu senaryoda uygulanmaz ("Geçersiz yap")'),
    sa.Column('StartDate', sa.DATE(), nullable=False, comment='Başlangıç'),
    sa.Column('EndDate', sa.DATE(), nullable=False, comment='Bitiş (dahil)'),
    sa.Column('Name', sa.Unicode(length=100), nullable=False, comment='Ad (ör. Yılbaşı)'),
    sa.Column('DayValue', sa.Numeric(precision=2, scale=1), server_default=sa.text('0'), nullable=False, comment='O günlerde çalışılan oran: 0 Çalışılmıyor · 0,5 Yarım gün'),
    sa.Column('UpdatedAt', mssql.DATETIME2(), nullable=False, comment='Son değişiklik zamanı (UTC)'),
    sa.Column('UpdatedBy', sa.Integer(), nullable=True, comment='Son değiştiren kullanıcı; sentetik ve geçişle gelen satırda boş'),
    sa.ForeignKeyConstraint(['ScenarioDefinitionId'], ['param.ScenarioDefinition.Id'], name=op.f('FK_FactoryCalendar_ScenarioDefinitionId')),
    sa.PrimaryKeyConstraint('Id', name=op.f('PK_FactoryCalendar')),
    schema='param',
    comment='Fabrika takvimi (K-185): bütün kaynak gruplarına uygulanan toplu duruş (tatil, toplu izin, yarım gün). Tek günde başlangıç ve bitiş aynıdır.',
    info={'field_class': 'Parametre'}
    )
    op.create_table('OvertimeLimit',
    sa.Column('Id', sa.BigInteger(), autoincrement=True, nullable=False, comment='Kayıt kimliği'),
    sa.Column('ScenarioDefinitionId', sa.Integer(), nullable=False, comment='Senaryo'),
    sa.Column('BaseRowId', sa.BigInteger(), nullable=True, comment="Baz'ı izleyen senaryoda Baz'daki satırın farkıysa o satırın kimliği; senaryonun kendi satırında ve Baz'da boş"),
    sa.Column('OverriddenFields', sa.Unicode(length=400), nullable=True, comment='Fark satırında senaryonun değiştirdiği alanların adları (virgüllerle çevrili: ",ValidTo,DailyCapacity,"); yalnız bu alanlar senaryodan, gerisi Baz satırından okunur'),
    sa.Column('IsValid', sa.Boolean(), server_default=sa.text('1'), nullable=False, comment='Geçerli (K-176): Hayır ise kayıt bu senaryoda uygulanmaz ("Geçersiz yap")'),
    sa.Column('ResourceGroupId', sa.BigInteger(), nullable=True, comment='Kaynak grubu (gruba girilen kayıt); kaynak doluysa boş'),
    sa.Column('ResourceId', sa.BigInteger(), nullable=True, comment='Kaynak (kaynağa girilen kayıt); grup doluysa boş'),
    sa.Column('ValidFrom', sa.DATE(), nullable=False, comment='Başlangıç'),
    sa.Column('ValidTo', sa.DATE(), nullable=True, comment='Bitiş (dahil); boşsa süresiz'),
    sa.Column('DailyLimit', sa.Numeric(precision=18, scale=4), nullable=False, comment='Günlük ek mesai limiti, kaynak başına'),
    sa.Column('UpdatedAt', mssql.DATETIME2(), nullable=False, comment='Son değişiklik zamanı (UTC)'),
    sa.Column('UpdatedBy', sa.Integer(), nullable=True, comment='Son değiştiren kullanıcı; sentetik ve geçişle gelen satırda boş'),
    sa.ForeignKeyConstraint(['ScenarioDefinitionId'], ['param.ScenarioDefinition.Id'], name=op.f('FK_OvertimeLimit_ScenarioDefinitionId')),
    sa.PrimaryKeyConstraint('Id', name=op.f('PK_OvertimeLimit')),
    schema='param',
    comment="Ek mesai limiti (K-185): çalışılan günde kaynak başına yapılabilecek ek mesai, grubun kapasite biriminde. Giriş yoksa ek mesai yok. Her gruba girilebilir. ERP'den gelen kalan fazla mesai (kaynakta) ayrıdır, birleştirilmez.",
    info={'field_class': 'Parametre'}
    )
    op.create_index(op.f('IX_OvertimeLimit_ResourceGroupId'), 'OvertimeLimit', ['ResourceGroupId'], unique=False, schema='param')
    op.create_index(op.f('IX_OvertimeLimit_ResourceId'), 'OvertimeLimit', ['ResourceId'], unique=False, schema='param')
    op.create_table('ResourceDowntime',
    sa.Column('Id', sa.BigInteger(), autoincrement=True, nullable=False, comment='Kayıt kimliği'),
    sa.Column('ScenarioDefinitionId', sa.Integer(), nullable=False, comment='Senaryo'),
    sa.Column('BaseRowId', sa.BigInteger(), nullable=True, comment="Baz'ı izleyen senaryoda Baz'daki satırın farkıysa o satırın kimliği; senaryonun kendi satırında ve Baz'da boş"),
    sa.Column('OverriddenFields', sa.Unicode(length=400), nullable=True, comment='Fark satırında senaryonun değiştirdiği alanların adları (virgüllerle çevrili: ",ValidTo,DailyCapacity,"); yalnız bu alanlar senaryodan, gerisi Baz satırından okunur'),
    sa.Column('IsValid', sa.Boolean(), server_default=sa.text('1'), nullable=False, comment='Geçerli (K-176): Hayır ise kayıt bu senaryoda uygulanmaz ("Geçersiz yap")'),
    sa.Column('ResourceGroupId', sa.BigInteger(), nullable=True, comment='Kaynak grubu (gruba girilen kayıt); kaynak doluysa boş'),
    sa.Column('ResourceId', sa.BigInteger(), nullable=True, comment='Kaynak (kaynağa girilen kayıt); grup doluysa boş'),
    sa.Column('StartDate', sa.DATE(), nullable=False, comment='Başlangıç'),
    sa.Column('EndDate', sa.DATE(), nullable=False, comment='Bitiş (dahil)'),
    sa.Column('DowntimeType', sa.Unicode(length=20), nullable=False, comment='Planlı bakım | Arıza | Diğer'),
    sa.Column('Reason', sa.Unicode(length=255), nullable=True, comment='Sebep (serbest metin)'),
    sa.Column('UpdatedAt', mssql.DATETIME2(), nullable=False, comment='Son değişiklik zamanı (UTC)'),
    sa.Column('UpdatedBy', sa.Integer(), nullable=True, comment='Son değiştiren kullanıcı; sentetik ve geçişle gelen satırda boş'),
    sa.ForeignKeyConstraint(['ScenarioDefinitionId'], ['param.ScenarioDefinition.Id'], name=op.f('FK_ResourceDowntime_ScenarioDefinitionId')),
    sa.PrimaryKeyConstraint('Id', name=op.f('PK_ResourceDowntime')),
    schema='param',
    comment="Bakım ve duruş (K-185): kapasiteden düşülür. Gruba girilen duruş grubun bütün kaynaklarına uygulanır. Geçerlilik kuralının dışındadır: duruşlar birleşir, gün bir kez düşer. Çalışan izni ERP'den gelir (`core.EmployeeAbsence`), burada tutulmaz.",
    info={'field_class': 'Parametre'}
    )
    op.create_index(op.f('IX_ResourceDowntime_ResourceGroupId'), 'ResourceDowntime', ['ResourceGroupId'], unique=False, schema='param')
    op.create_index(op.f('IX_ResourceDowntime_ResourceId'), 'ResourceDowntime', ['ResourceId'], unique=False, schema='param')
    op.create_table('WorkPattern',
    sa.Column('Id', sa.BigInteger(), autoincrement=True, nullable=False, comment='Kayıt kimliği'),
    sa.Column('ScenarioDefinitionId', sa.Integer(), nullable=False, comment='Senaryo'),
    sa.Column('BaseRowId', sa.BigInteger(), nullable=True, comment="Baz'ı izleyen senaryoda Baz'daki satırın farkıysa o satırın kimliği; senaryonun kendi satırında ve Baz'da boş"),
    sa.Column('OverriddenFields', sa.Unicode(length=400), nullable=True, comment='Fark satırında senaryonun değiştirdiği alanların adları (virgüllerle çevrili: ",ValidTo,DailyCapacity,"); yalnız bu alanlar senaryodan, gerisi Baz satırından okunur'),
    sa.Column('IsValid', sa.Boolean(), server_default=sa.text('1'), nullable=False, comment='Geçerli (K-176): Hayır ise kayıt bu senaryoda uygulanmaz ("Geçersiz yap")'),
    sa.Column('ResourceGroupId', sa.BigInteger(), nullable=True, comment='Kaynak grubu (gruba girilen kayıt); kaynak doluysa boş'),
    sa.Column('ResourceId', sa.BigInteger(), nullable=True, comment='Kaynak (kaynağa girilen kayıt); grup doluysa boş'),
    sa.Column('ValidFrom', sa.DATE(), nullable=False, comment='Başlangıç'),
    sa.Column('ValidTo', sa.DATE(), nullable=True, comment='Bitiş (dahil); boşsa süresiz'),
    sa.Column('DailyCapacity', sa.Numeric(precision=18, scale=4), nullable=False, comment='Tam çalışma günündeki kapasite, kaynak başına, grubun kapasite biriminde; yarım günde yarısı'),
    sa.Column('DayMon', sa.Numeric(precision=2, scale=1), server_default=sa.text('1'), nullable=False, comment='Pazartesi: 1 Tam · 0,5 Yarım · 0 Çalışılmıyor'),
    sa.Column('DayTue', sa.Numeric(precision=2, scale=1), server_default=sa.text('1'), nullable=False, comment='Salı: 1 Tam · 0,5 Yarım · 0 Çalışılmıyor'),
    sa.Column('DayWed', sa.Numeric(precision=2, scale=1), server_default=sa.text('1'), nullable=False, comment='Çarşamba: 1 Tam · 0,5 Yarım · 0 Çalışılmıyor'),
    sa.Column('DayThu', sa.Numeric(precision=2, scale=1), server_default=sa.text('1'), nullable=False, comment='Perşembe: 1 Tam · 0,5 Yarım · 0 Çalışılmıyor'),
    sa.Column('DayFri', sa.Numeric(precision=2, scale=1), server_default=sa.text('1'), nullable=False, comment='Cuma: 1 Tam · 0,5 Yarım · 0 Çalışılmıyor'),
    sa.Column('DaySat', sa.Numeric(precision=2, scale=1), server_default=sa.text('0'), nullable=False, comment='Cumartesi: 1 Tam · 0,5 Yarım · 0 Çalışılmıyor'),
    sa.Column('DaySun', sa.Numeric(precision=2, scale=1), server_default=sa.text('0'), nullable=False, comment='Pazar: 1 Tam · 0,5 Yarım · 0 Çalışılmıyor'),
    sa.Column('UpdatedAt', mssql.DATETIME2(), nullable=False, comment='Son değişiklik zamanı (UTC)'),
    sa.Column('UpdatedBy', sa.Integer(), nullable=True, comment='Son değiştiren kullanıcı; sentetik ve geçişle gelen satırda boş'),
    sa.ForeignKeyConstraint(['ScenarioDefinitionId'], ['param.ScenarioDefinition.Id'], name=op.f('FK_WorkPattern_ScenarioDefinitionId')),
    sa.PrimaryKeyConstraint('Id', name=op.f('PK_WorkPattern')),
    schema='param',
    comment='Çalışma düzeni (K-185): günlük kapasite ve haftanın günleri. Çalışma günü yalnız buradan gelir. Geçerlilik: önce seviye (kaynakta o günü kapsayan kayıt varsa kaynağınkiler, yoksa grubunkiler), sonra başlangıcı en ileri olan.',
    info={'field_class': 'Parametre'}
    )
    op.create_index(op.f('IX_WorkPattern_ResourceGroupId'), 'WorkPattern', ['ResourceGroupId'], unique=False, schema='param')
    op.create_index(op.f('IX_WorkPattern_ResourceId'), 'WorkPattern', ['ResourceId'], unique=False, schema='param')
    op.drop_table('Calendar', schema='core')
    op.drop_index(op.f('IX_ResourcePeriodLimit_ResourceId'), table_name='ResourcePeriodLimit', schema='param')
    op.drop_table('ResourcePeriodLimit', schema='param')
    op.drop_index(op.f('IX_ResourceDowntime_ResourceId'), table_name='ResourceDowntime', schema='core')
    op.drop_table('ResourceDowntime', schema='core')
    op.drop_index(op.f('IX_ResourceCapacityProfile_ResourceId'), table_name='ResourceCapacityProfile', schema='core')
    op.drop_table('ResourceCapacityProfile', schema='core')
    op.drop_index(op.f('IX_CalendarDay_CalendarId'), table_name='CalendarDay', schema='core')
    op.drop_table('CalendarDay', schema='core')
    _empty_cache()
    op.create_table('ResourceCapacityDay',
    sa.Column('ScenarioDefinitionId', sa.Integer(), autoincrement=False, nullable=False, comment='Senaryo'),
    sa.Column('ResourceId', sa.BigInteger(), autoincrement=False, nullable=False, comment='Kaynak'),
    sa.Column('ResourceGroupId', sa.BigInteger(), autoincrement=False, nullable=False, comment='Kaynak grubu'),
    sa.Column('Date', sa.DATE(), autoincrement=False, nullable=False, comment='Gün'),
    sa.Column('WorkingDay', sa.Numeric(precision=2, scale=1), nullable=False, comment='Çalışma günü (Tam 1, Yarım 0,5, Çalışılmıyor 0; çalışma düzeni yoksa 0)'),
    sa.Column('Downtime', sa.Numeric(precision=5, scale=4), nullable=False, comment='Duruş (gün; çalışma gününü aşmaz)'),
    sa.Column('DailyCapacity', sa.Numeric(precision=18, scale=4), nullable=False, comment='O gün geçerli günlük kapasite (çalışma düzeni yoksa 0)'),
    sa.Column('Capacity', sa.Numeric(precision=18, scale=4), nullable=False, comment='Toplam kapasite: çalışma günü × günlük kapasite × verimlilik'),
    sa.Column('AvailableCapacity', sa.Numeric(precision=18, scale=4), nullable=False, comment='Kullanılabilir kapasite: (çalışma günü − duruş) × günlük kapasite × verimlilik'),
    sa.Column('OvertimeLimit', sa.Numeric(precision=18, scale=4), nullable=False, comment='Ek mesai limiti: (çalışma günü − duruş) × günlük limit'),
    sa.PrimaryKeyConstraint('ScenarioDefinitionId', 'ResourceId', 'ResourceGroupId', 'Date', name=op.f('PK_ResourceCapacityDay')),
    schema='cache',
    comment='Kaynak grubu × kaynak × gün kapasite ara sonucu (K-184, K-185): dönem tablosu "Kaynak grubu × dönem" bundan toplanır. Grup kaydı o grubun içinde uygulandığı için birden fazla gruba üye kaynak her grubunda ayrı satırdır. Yalnız planlama ufkundaki günler; Baz\'ı izleyen senaryoda yalnız Baz\'dan farklı çıkan satırlar (gerisi Baz\'ın satırlarından okunur). Kümelenmiş anahtar senaryo, kaynak, grup, gün: tek kaynağın yenilenmesi ve senaryonun gün aralığı okuması aynı sıradan.'
    )
    op.drop_index(op.f('IX_Resource_CalendarId'), table_name='Resource', schema='core')
    op.drop_column('Resource', 'SubconPlanningType', schema='core')
    op.drop_column('Resource', 'DailyCapacity', schema='core')
    op.drop_column('Resource', 'SubconFixedLeadTimeDays', schema='core')
    op.drop_column('Resource', 'SubconVariableDaysPerUnit', schema='core')
    op.drop_column('Resource', 'CalendarId', schema='core')
    op.drop_table('ResourceEfficiency', schema='param')
    op.create_table('ResourceEfficiency',
    sa.Column('Id', sa.BigInteger(), autoincrement=True, nullable=False, comment='Kayıt kimliği'),
    sa.Column('ScenarioDefinitionId', sa.Integer(), nullable=False, comment='Senaryo'),
    sa.Column('BaseRowId', sa.BigInteger(), nullable=True, comment="Baz'ı izleyen senaryoda Baz'daki satırın farkıysa o satırın kimliği; senaryonun kendi satırında ve Baz'da boş"),
    sa.Column('OverriddenFields', sa.Unicode(length=400), nullable=True, comment='Fark satırında senaryonun değiştirdiği alanların adları (virgüllerle çevrili: ",ValidTo,DailyCapacity,"); yalnız bu alanlar senaryodan, gerisi Baz satırından okunur'),
    sa.Column('IsValid', sa.Boolean(), server_default=sa.text('1'), nullable=False, comment='Geçerli (K-176): Hayır ise kayıt bu senaryoda uygulanmaz ("Geçersiz yap")'),
    sa.Column('ResourceGroupId', sa.BigInteger(), nullable=True, comment='Kaynak grubu (gruba girilen kayıt); kaynak doluysa boş'),
    sa.Column('ResourceId', sa.BigInteger(), nullable=True, comment='Kaynak (kaynağa girilen kayıt); grup doluysa boş'),
    sa.Column('ValidFrom', sa.DATE(), nullable=False, comment='Başlangıç'),
    sa.Column('ValidTo', sa.DATE(), nullable=True, comment='Bitiş (dahil); boşsa süresiz'),
    sa.Column('EfficiencyPct', sa.Numeric(precision=6, scale=2), server_default=sa.text('100'), nullable=False, comment='Verimlilik (%)'),
    sa.Column('UpdatedAt', mssql.DATETIME2(), nullable=False, comment='Son değişiklik zamanı (UTC)'),
    sa.Column('UpdatedBy', sa.Integer(), nullable=True, comment='Son değiştiren kullanıcı; sentetik ve geçişle gelen satırda boş'),
    sa.ForeignKeyConstraint(['ScenarioDefinitionId'], ['param.ScenarioDefinition.Id'], name=op.f('FK_ResourceEfficiency_ScenarioDefinitionId_ScenarioDefinition')),
    sa.PrimaryKeyConstraint('Id', name=op.f('PK_ResourceEfficiency')),
    schema='param',
    comment='Verimlilik (K-185): kapasite katsayısı, yüzde. Giriş yoksa %100. Geçerlilik kuralı çalışma düzenindeki gibi, kendi kayıtlarından.'
    )
    op.create_index(op.f('IX_ResourceEfficiency_ResourceGroupId'), 'ResourceEfficiency', ['ResourceGroupId'], unique=False, schema='param')
    op.create_index(op.f('IX_ResourceEfficiency_ResourceId'), 'ResourceEfficiency', ['ResourceId'], unique=False, schema='param')
    if not context.is_offline_mode():  # bağlantısız SQL betiğinde satırlar yazılmaz; ilk bağlantılı geçişte kurulur
        sync(op.get_bind(), metadata)


def downgrade():
    _forget((*NEW_TABLES, *REBUILT), {})
    op.drop_table('ResourceEfficiency', schema='param')
    op.create_table('ResourceEfficiency',
    sa.Column('Id', sa.BigInteger(), autoincrement=True, nullable=False, comment='Kayıt kimliği'),
    sa.Column('ScenarioDefinitionId', sa.Integer(), nullable=False, comment='Senaryo'),
    sa.Column('ResourceId', sa.BigInteger(), nullable=False, comment='Kaynak'),
    sa.Column('ValidFrom', sa.DATE(), nullable=False, comment='Başlangıç'),
    sa.Column('ValidTo', sa.DATE(), nullable=False, comment='Bitiş'),
    sa.Column('EfficiencyPct', sa.Numeric(precision=6, scale=2), server_default=sa.text('100'), nullable=False, comment='Verim (%)'),
    sa.ForeignKeyConstraint(['ScenarioDefinitionId'], ['param.ScenarioDefinition.Id'], name=op.f('FK_ResourceEfficiency_ScenarioDefinitionId_ScenarioDefinition')),
    sa.PrimaryKeyConstraint('Id', name=op.f('PK_ResourceEfficiency')),
    schema='param',
    comment='Kaynak ve dönem bazında verim (kapasite katsayısı); senaryoya özel.'
    )
    op.create_index(op.f('IX_ResourceEfficiency_ResourceId'), 'ResourceEfficiency', ['ResourceId'], unique=False, schema='param')
    op.add_column('Resource', sa.Column('CalendarId', sa.INTEGER(), autoincrement=False, nullable=True, comment='Çalışma takvimi (Smartchain ekranında atanır); geçici alan (Kapasite yönetimi adımında kalkar)'), schema='core')
    op.add_column('Resource', sa.Column('SubconVariableDaysPerUnit', sa.NUMERIC(precision=18, scale=6), autoincrement=False, nullable=True, comment='Fasonda birim başına gün (fasoncunun hızı); geçici alan (Kapasite yönetimi adımında kalkar)'), schema='core')
    op.add_column('Resource', sa.Column('SubconFixedLeadTimeDays', sa.NUMERIC(precision=9, scale=2), autoincrement=False, nullable=True, comment='Fasonda sabit süre (taşıma ve kuyruk); geçici alan (Kapasite yönetimi adımında kalkar)'), schema='core')
    op.add_column('Resource', sa.Column('DailyCapacity', sa.NUMERIC(precision=18, scale=4), autoincrement=False, nullable=True, comment='Kaynağın bir çalışma günündeki kapasitesi; geçici alan (Kapasite yönetimi adımında kalkar)'), schema='core')
    op.add_column('Resource', sa.Column('SubconPlanningType', sa.NVARCHAR(length=15, collation='Latin1_General_100_CI_AS_SC'), autoincrement=False, nullable=True, comment='Fasonda: İş yeri | Tedarik süresi'), schema='core')
    op.create_index(op.f('IX_Resource_CalendarId'), 'Resource', ['CalendarId'], unique=False, schema='core')
    _empty_cache()
    op.create_table('ResourceCapacityDay',
    sa.Column('ScenarioDefinitionId', sa.Integer(), autoincrement=False, nullable=False, comment='Senaryo'),
    sa.Column('ResourceId', sa.BigInteger(), autoincrement=False, nullable=False, comment='Kaynak'),
    sa.Column('Date', sa.DATE(), autoincrement=False, nullable=False, comment='Gün'),
    sa.Column('WorkingDay', sa.Numeric(precision=5, scale=2), nullable=False, comment='Çalışma günü (tam 1, yarım 0,5, çalışılmıyor 0)'),
    sa.Column('Capacity', sa.Numeric(precision=18, scale=4), nullable=False, comment='Günün toplam kapasitesi'),
    sa.Column('AvailableCapacity', sa.Numeric(precision=18, scale=4), nullable=False, comment='Kullanılabilir kapasite (toplam × verim)'),
    sa.PrimaryKeyConstraint('ScenarioDefinitionId', 'ResourceId', 'Date', name=op.f('PK_ResourceCapacityDay')),
    schema='cache',
    comment='Kaynak × gün kapasite ara sonucu (K-184).'
    )
    op.create_table('CalendarDay',
    sa.Column('CalendarId', sa.INTEGER(), autoincrement=False, nullable=False, comment='Takvim'),
    sa.Column('Date', sa.DATE(), autoincrement=False, nullable=False, comment='Gün'),
    sa.Column('IsWorkingDay', mssql.BIT(), autoincrement=False, nullable=False, comment='Çalışma günü mü'),
    sa.Column('WorkingFraction', sa.NUMERIC(precision=5, scale=4), autoincrement=False, nullable=True, comment='Günün çalışılan oranı (yarım gün 0,5)'),
    sa.Column('VersionFrom', sa.INTEGER(), autoincrement=False, nullable=False, comment='Kaydın geçerli olduğu ilk veri versiyonu'),
    sa.Column('VersionTo', sa.INTEGER(), autoincrement=False, nullable=True, comment='Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş'),
    sa.Column('ImportBatchId', sa.BIGINT(), autoincrement=False, nullable=True, comment='Kaydı getiren yükleme partisi'),
    sa.Column('BusinessKey', sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'), autoincrement=False, nullable=False, comment='İş anahtarı; kod ya da kodların birleşimi'),
    sa.Column('UpdatedAt', mssql.DATETIME2(), autoincrement=False, nullable=False, comment='Son değişiklik zamanı'),
    sa.ForeignKeyConstraint(['ImportBatchId'], ['adm.ImportBatch.Id'], name=op.f('FK_CalendarDay_ImportBatchId')),
    sa.PrimaryKeyConstraint('CalendarId', 'Date', 'VersionFrom', name=op.f('PK_CalendarDay')),
    schema='core',
    comment="Takvimin gün bazında çalışma durumu. Smartchain'de ekrandan girilir; entegrasyondan gelmez (K-65)."
    )
    op.create_index(op.f('IX_CalendarDay_CalendarId'), 'CalendarDay', ['CalendarId'], unique=False, schema='core')
    op.create_table('ResourceCapacityProfile',
    sa.Column('Id', sa.BIGINT(), autoincrement=False, nullable=False, comment='Kayıt kimliği'),
    sa.Column('ResourceId', sa.BIGINT(), autoincrement=False, nullable=False, comment='Kaynak'),
    sa.Column('ValidFrom', sa.DATE(), autoincrement=False, nullable=False, comment='Başlangıç'),
    sa.Column('ValidTo', sa.DATE(), autoincrement=False, nullable=False, comment='Bitiş'),
    sa.Column('DailyCapacity', sa.NUMERIC(precision=18, scale=4), autoincrement=False, nullable=False, comment='Bu aralıktaki günlük kapasite'),
    sa.Column('VersionFrom', sa.INTEGER(), autoincrement=False, nullable=False, comment='Kaydın geçerli olduğu ilk veri versiyonu'),
    sa.Column('VersionTo', sa.INTEGER(), autoincrement=False, nullable=True, comment='Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş'),
    sa.Column('ImportBatchId', sa.BIGINT(), autoincrement=False, nullable=True, comment='Kaydı getiren yükleme partisi'),
    sa.Column('BusinessKey', sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'), autoincrement=False, nullable=False, comment='İş anahtarı; kod ya da kodların birleşimi'),
    sa.Column('UpdatedAt', mssql.DATETIME2(), autoincrement=False, nullable=False, comment='Son değişiklik zamanı'),
    sa.ForeignKeyConstraint(['ImportBatchId'], ['adm.ImportBatch.Id'], name=op.f('FK_ResourceCapacityProfile_ImportBatchId')),
    sa.PrimaryKeyConstraint('Id', 'VersionFrom', name=op.f('PK_ResourceCapacityProfile')),
    schema='core',
    comment="Günlük kapasitenin dönemsel değişikliği. Birim kaynağın gruplarının ortak kapasite birimi; ekranda gösterilir, ayrı saklanmaz. Geçici tablo: Kapasite yönetimi adımında yeniden tasarlanır (K-180). Smartchain'de ekrandan girilir; entegrasyondan gelmez (K-65)."
    )
    op.create_index(op.f('IX_ResourceCapacityProfile_ResourceId'), 'ResourceCapacityProfile', ['ResourceId'], unique=False, schema='core')
    op.create_table('ResourceDowntime',
    sa.Column('Id', sa.BIGINT(), autoincrement=False, nullable=False, comment='Kayıt kimliği'),
    sa.Column('ResourceId', sa.BIGINT(), autoincrement=False, nullable=False, comment='Kaynak'),
    sa.Column('DowntimeType', sa.NVARCHAR(length=10, collation='Latin1_General_100_CI_AS_SC'), autoincrement=False, nullable=False, comment='Bakım | Arıza'),
    sa.Column('StartAt', mssql.DATETIME2(), autoincrement=False, nullable=False, comment='Başlangıç'),
    sa.Column('EndAt', mssql.DATETIME2(), autoincrement=False, nullable=False, comment='Bitiş'),
    sa.Column('AffectedQuantity', sa.INTEGER(), autoincrement=False, nullable=False, comment='Etkilenen kaynak adedi'),
    sa.Column('DurationDays', sa.NUMERIC(precision=9, scale=4), autoincrement=False, nullable=True, comment='Süre, gün olarak (yarım gün 0,5)'),
    sa.Column('Note', sa.NVARCHAR(length=400, collation='Latin1_General_100_CI_AS_SC'), autoincrement=False, nullable=True, comment='Açıklama'),
    sa.Column('VersionFrom', sa.INTEGER(), autoincrement=False, nullable=False, comment='Kaydın geçerli olduğu ilk veri versiyonu'),
    sa.Column('VersionTo', sa.INTEGER(), autoincrement=False, nullable=True, comment='Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş'),
    sa.Column('ImportBatchId', sa.BIGINT(), autoincrement=False, nullable=True, comment='Kaydı getiren yükleme partisi'),
    sa.Column('BusinessKey', sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'), autoincrement=False, nullable=False, comment='İş anahtarı; kod ya da kodların birleşimi'),
    sa.Column('UpdatedAt', mssql.DATETIME2(), autoincrement=False, nullable=False, comment='Son değişiklik zamanı'),
    sa.ForeignKeyConstraint(['ImportBatchId'], ['adm.ImportBatch.Id'], name=op.f('FK_ResourceDowntime_ImportBatchId')),
    sa.PrimaryKeyConstraint('Id', 'VersionFrom', name=op.f('PK_ResourceDowntime')),
    schema='core',
    comment="Bakım ve arıza takvimi; kapasiteden düşülür. Çalışmada geçici değiştirilebilir. Smartchain'de ekrandan girilir; entegrasyondan gelmez (K-65)."
    )
    op.create_index(op.f('IX_ResourceDowntime_ResourceId'), 'ResourceDowntime', ['ResourceId'], unique=False, schema='core')
    op.create_table('ResourcePeriodLimit',
    sa.Column('Id', sa.BIGINT(), sa.Identity(always=False, start=1, increment=1), autoincrement=True, nullable=False, comment='Kayıt kimliği'),
    sa.Column('ResourceId', sa.BIGINT(), autoincrement=False, nullable=False, comment='Kaynak'),
    sa.Column('ValidFrom', sa.DATE(), autoincrement=False, nullable=False, comment='Başlangıç'),
    sa.Column('ValidTo', sa.DATE(), autoincrement=False, nullable=False, comment='Bitiş'),
    sa.Column('UpperLimit', sa.NUMERIC(precision=18, scale=4), autoincrement=False, nullable=False, comment='Dönem üst limiti'),
    sa.Column('ScenarioDefinitionId', sa.INTEGER(), autoincrement=False, nullable=False, comment='Senaryo'),
    sa.ForeignKeyConstraint(['ScenarioDefinitionId'], ['param.ScenarioDefinition.Id'], name=op.f('FK_ResourcePeriodLimit_ScenarioDefinitionId')),
    sa.PrimaryKeyConstraint('Id', name=op.f('PK_ResourcePeriodLimit')),
    schema='param',
    comment='Dönem bazlı üst limit; kısıtsız kaynaklarda ve fasonda. Birim kaynağın gruplarının ortak kapasite birimi. Geçici tablo: Kapasite yönetimi adımında yeniden tasarlanır (K-180).'
    )
    op.create_index(op.f('IX_ResourcePeriodLimit_ResourceId'), 'ResourcePeriodLimit', ['ResourceId'], unique=False, schema='param')
    op.create_table('Calendar',
    sa.Column('Id', sa.INTEGER(), autoincrement=False, nullable=False, comment='Takvim kimliği'),
    sa.Column('Code', sa.NVARCHAR(length=30, collation='Latin1_General_100_CI_AS_SC'), autoincrement=False, nullable=False, comment='Takvim kodu'),
    sa.Column('Name', sa.NVARCHAR(length=100, collation='Latin1_General_100_CI_AS_SC'), autoincrement=False, nullable=True, comment='Takvim adı'),
    sa.Column('VersionFrom', sa.INTEGER(), autoincrement=False, nullable=False, comment='Kaydın geçerli olduğu ilk veri versiyonu'),
    sa.Column('VersionTo', sa.INTEGER(), autoincrement=False, nullable=True, comment='Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş'),
    sa.Column('ImportBatchId', sa.BIGINT(), autoincrement=False, nullable=True, comment='Kaydı getiren yükleme partisi'),
    sa.Column('BusinessKey', sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'), autoincrement=False, nullable=False, comment='İş anahtarı; kod ya da kodların birleşimi'),
    sa.Column('UpdatedAt', mssql.DATETIME2(), autoincrement=False, nullable=False, comment='Son değişiklik zamanı'),
    sa.ForeignKeyConstraint(['ImportBatchId'], ['adm.ImportBatch.Id'], name=op.f('FK_Calendar_ImportBatchId')),
    sa.PrimaryKeyConstraint('Id', 'VersionFrom', name=op.f('PK_Calendar')),
    schema='core',
    comment="Çalışma takvimi başlığı (kaynaklara bağlanır). Smartchain'de ekrandan girilir; entegrasyondan gelmez (K-65)."
    )
    op.drop_index(op.f('IX_WorkPattern_ResourceId'), table_name='WorkPattern', schema='param')
    op.drop_index(op.f('IX_WorkPattern_ResourceGroupId'), table_name='WorkPattern', schema='param')
    op.drop_table('WorkPattern', schema='param')
    op.drop_index(op.f('IX_ResourceDowntime_ResourceId'), table_name='ResourceDowntime', schema='param')
    op.drop_index(op.f('IX_ResourceDowntime_ResourceGroupId'), table_name='ResourceDowntime', schema='param')
    op.drop_table('ResourceDowntime', schema='param')
    op.drop_index(op.f('IX_OvertimeLimit_ResourceId'), table_name='OvertimeLimit', schema='param')
    op.drop_index(op.f('IX_OvertimeLimit_ResourceGroupId'), table_name='OvertimeLimit', schema='param')
    op.drop_table('OvertimeLimit', schema='param')
    op.drop_table('FactoryCalendar', schema='param')
    if not context.is_offline_mode():
        sync(op.get_bind(), metadata)
