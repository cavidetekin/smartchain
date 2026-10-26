USE Smartchain;
GO

BEGIN TRANSACTION;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

GO

-- Running upgrade  -> 0001

CREATE SCHEMA [stg];

GO

CREATE SCHEMA [core];

GO

CREATE SCHEMA [param];

GO

CREATE SCHEMA [planning];

GO

CREATE SCHEMA [adm];

GO

CREATE TABLE adm.[AppUser] (
    [Id] INTEGER NOT NULL IDENTITY, 
    [UserName] NVARCHAR(60) NOT NULL, 
    [FullName] NVARCHAR(150) NULL, 
    [Role] NVARCHAR(15) NOT NULL, 
    [PasswordHash] VARBINARY(256) NOT NULL, 
    [MustChangePassword] BIT NULL DEFAULT 1, 
    [FailedAttempts] INTEGER NULL DEFAULT 0, 
    [IsLocked] BIT NULL DEFAULT 0, 
    [IsActive] BIT NULL DEFAULT 1, 
    CONSTRAINT [PK_AppUser] PRIMARY KEY ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Uygulama kullanıcısı (Faz 1''de yerel).', 'schema', adm, 'table', [AppUser];

GO

execute sp_addextendedproperty 'MS_Description', N'Kullanıcı kimliği', 'schema', adm, 'table', [AppUser], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Kullanıcı adı', 'schema', adm, 'table', [AppUser], 'column', [UserName];

GO

execute sp_addextendedproperty 'MS_Description', N'Ad soyad', 'schema', adm, 'table', [AppUser], 'column', [FullName];

GO

execute sp_addextendedproperty 'MS_Description', N'Sistem sahibi | Admin | Key user | End user', 'schema', adm, 'table', [AppUser], 'column', [Role];

GO

execute sp_addextendedproperty 'MS_Description', N'Özetlenmiş şifre', 'schema', adm, 'table', [AppUser], 'column', [PasswordHash];

GO

execute sp_addextendedproperty 'MS_Description', N'İlk girişte değiştir', 'schema', adm, 'table', [AppUser], 'column', [MustChangePassword];

GO

execute sp_addextendedproperty 'MS_Description', N'Hatalı deneme', 'schema', adm, 'table', [AppUser], 'column', [FailedAttempts];

GO

execute sp_addextendedproperty 'MS_Description', N'Kilitli', 'schema', adm, 'table', [AppUser], 'column', [IsLocked];

GO

execute sp_addextendedproperty 'MS_Description', N'Aktif', 'schema', adm, 'table', [AppUser], 'column', [IsActive];

GO

CREATE UNIQUE INDEX [UX_AppUser_UserName] ON adm.[AppUser] ([UserName]);

GO

CREATE TABLE adm.[DataRule] (
    [Id] BIGINT NOT NULL IDENTITY, 
    [TableName] NVARCHAR(60) NOT NULL, 
    [FieldName] NVARCHAR(60) NOT NULL, 
    [Seq] INTEGER NOT NULL, 
    [AssignValue] NVARCHAR(200) NULL, 
    [AssignFromField] NVARCHAR(60) NULL, 
    [Owner] NVARCHAR(10) NOT NULL, 
    [IsActive] BIT NULL DEFAULT 1, 
    [ValidFrom] DATE NULL, 
    [ValidTo] DATE NULL, 
    [Description] NVARCHAR(400) NULL, 
    CONSTRAINT [PK_DataRule] PRIMARY KEY ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Veri kuralı: ''X = … ise Alan = …''.', 'schema', adm, 'table', [DataRule];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', adm, 'table', [DataRule], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Hedef tablo', 'schema', adm, 'table', [DataRule], 'column', [TableName];

GO

execute sp_addextendedproperty 'MS_Description', N'Hedef alan', 'schema', adm, 'table', [DataRule], 'column', [FieldName];

GO

execute sp_addextendedproperty 'MS_Description', N'Sıra (ilk eşleşen kazanır)', 'schema', adm, 'table', [DataRule], 'column', [Seq];

GO

execute sp_addextendedproperty 'MS_Description', N'Atanacak değer', 'schema', adm, 'table', [DataRule], 'column', [AssignValue];

GO

execute sp_addextendedproperty 'MS_Description', N'Ya da başka bir alandan', 'schema', adm, 'table', [DataRule], 'column', [AssignFromField];

GO

execute sp_addextendedproperty 'MS_Description', N'Kurulum | Kullanıcı', 'schema', adm, 'table', [DataRule], 'column', [Owner];

GO

execute sp_addextendedproperty 'MS_Description', N'Aktif', 'schema', adm, 'table', [DataRule], 'column', [IsActive];

GO

execute sp_addextendedproperty 'MS_Description', N'Geçerlilik', 'schema', adm, 'table', [DataRule], 'column', [ValidFrom];

GO

execute sp_addextendedproperty 'MS_Description', N'Geçerlilik', 'schema', adm, 'table', [DataRule], 'column', [ValidTo];

GO

execute sp_addextendedproperty 'MS_Description', N'Açıklama', 'schema', adm, 'table', [DataRule], 'column', [Description];

GO

CREATE TABLE adm.[FieldDefinition] (
    [TableName] NVARCHAR(60) NOT NULL, 
    [FieldName] NVARCHAR(60) NOT NULL, 
    [FieldClass] NVARCHAR(15) NOT NULL, 
    [EditableInWorkspace] BIT NOT NULL DEFAULT 0, 
    [ValuePriority] NVARCHAR(10) NULL DEFAULT N'ERP ezer', 
    [ManualOverrides] BIT NULL DEFAULT 1, 
    [DefaultValue] NVARCHAR(200) NULL, 
    [IsRequired] BIT NULL DEFAULT 0, 
    CONSTRAINT [PK_FieldDefinition] PRIMARY KEY ([TableName], [FieldName])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Veri sözlüğü: her alanın sınıfı ve değer davranışı. Yapısını sistem sahibi yönetir.', 'schema', adm, 'table', [FieldDefinition];

GO

execute sp_addextendedproperty 'MS_Description', N'Tablo', 'schema', adm, 'table', [FieldDefinition], 'column', [TableName];

GO

execute sp_addextendedproperty 'MS_Description', N'Alan', 'schema', adm, 'table', [FieldDefinition], 'column', [FieldName];

GO

execute sp_addextendedproperty 'MS_Description', N'Ana veri | Parametre | İşlem verisi', 'schema', adm, 'table', [FieldDefinition], 'column', [FieldClass];

GO

execute sp_addextendedproperty 'MS_Description', N'Çalışmada geçici değiştirilebilir mi', 'schema', adm, 'table', [FieldDefinition], 'column', [EditableInWorkspace];

GO

execute sp_addextendedproperty 'MS_Description', N'ERP ezer | Kural ezer', 'schema', adm, 'table', [FieldDefinition], 'column', [ValuePriority];

GO

execute sp_addextendedproperty 'MS_Description', N'Elle değer her şeyi ezer mi', 'schema', adm, 'table', [FieldDefinition], 'column', [ManualOverrides];

GO

execute sp_addextendedproperty 'MS_Description', N'Varsayılan', 'schema', adm, 'table', [FieldDefinition], 'column', [DefaultValue];

GO

execute sp_addextendedproperty 'MS_Description', N'Zorunlu mu', 'schema', adm, 'table', [FieldDefinition], 'column', [IsRequired];

GO

CREATE TABLE adm.[ImportBatch] (
    [Id] BIGINT NOT NULL IDENTITY, 
    [Method] NVARCHAR(10) NOT NULL, 
    [EntityName] NVARCHAR(60) NOT NULL, 
    [LoadType] NVARCHAR(10) NOT NULL, 
    [ReceivedAt] DATETIME2 NOT NULL, 
    [Status] NVARCHAR(15) NOT NULL, 
    [RowCount] INTEGER NULL, 
    [ErrorCount] INTEGER NULL, 
    CONSTRAINT [PK_ImportBatch] PRIMARY KEY ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Ham veri partisi: her yükleme parti numarası, zaman ve kaynakla. Ham veri bir hafta saklanır.', 'schema', adm, 'table', [ImportBatch];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', adm, 'table', [ImportBatch], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'API | Excel | SQL', 'schema', adm, 'table', [ImportBatch], 'column', [Method];

GO

execute sp_addextendedproperty 'MS_Description', N'Varlık', 'schema', adm, 'table', [ImportBatch], 'column', [EntityName];

GO

execute sp_addextendedproperty 'MS_Description', N'Tam | Değişen', 'schema', adm, 'table', [ImportBatch], 'column', [LoadType];

GO

execute sp_addextendedproperty 'MS_Description', N'Alınma zamanı', 'schema', adm, 'table', [ImportBatch], 'column', [ReceivedAt];

GO

execute sp_addextendedproperty 'MS_Description', N'Alındı | Doğrulandı | Hatalı | Yüklendi', 'schema', adm, 'table', [ImportBatch], 'column', [Status];

GO

execute sp_addextendedproperty 'MS_Description', N'Satır sayısı', 'schema', adm, 'table', [ImportBatch], 'column', [RowCount];

GO

execute sp_addextendedproperty 'MS_Description', N'Hatalı satır', 'schema', adm, 'table', [ImportBatch], 'column', [ErrorCount];

GO

CREATE TABLE adm.[License] (
    [Id] INTEGER NOT NULL IDENTITY, 
    [LicenseFile] VARBINARY(max) NOT NULL, 
    [ValidUntil] DATE NOT NULL, 
    [InstallationId] NVARCHAR(100) NOT NULL, 
    CONSTRAINT [PK_License] PRIMARY KEY ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Çevrimdışı imzalı lisans.', 'schema', adm, 'table', [License];

GO

execute sp_addextendedproperty 'MS_Description', N'Kimlik', 'schema', adm, 'table', [License], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'İmzalı lisans dosyası', 'schema', adm, 'table', [License], 'column', [LicenseFile];

GO

execute sp_addextendedproperty 'MS_Description', N'Bitiş', 'schema', adm, 'table', [License], 'column', [ValidUntil];

GO

execute sp_addextendedproperty 'MS_Description', N'Kurulum kimliği', 'schema', adm, 'table', [License], 'column', [InstallationId];

GO

CREATE TABLE adm.[SystemSetting] (
    [SettingKey] NVARCHAR(60) NOT NULL, 
    [Value] NVARCHAR(200) NOT NULL, 
    CONSTRAINT [PK_SystemSetting] PRIMARY KEY ([SettingKey])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Sistem sahibinin ayarları: çözücü, süre bütçeleri, işçi sayısı, eş zamanlı çalışma sınırı, saklama süreleri.', 'schema', adm, 'table', [SystemSetting];

GO

execute sp_addextendedproperty 'MS_Description', N'Ayar', 'schema', adm, 'table', [SystemSetting], 'column', [SettingKey];

GO

execute sp_addextendedproperty 'MS_Description', N'Değer', 'schema', adm, 'table', [SystemSetting], 'column', [Value];

GO

CREATE TABLE core.[Location] (
    [Id] INTEGER NOT NULL IDENTITY, 
    [Code] NVARCHAR(30) NOT NULL, 
    [Name] NVARCHAR(100) NOT NULL, 
    [Type] NVARCHAR(15) NOT NULL DEFAULT N'Tesis', 
    [Country] NVARCHAR(100) NULL, 
    [CountryCode] NVARCHAR(10) NULL, 
    [Region] NVARCHAR(100) NULL, 
    [RegionCode] NVARCHAR(20) NULL, 
    [City] NVARCHAR(100) NULL, 
    [CityCode] NVARCHAR(20) NULL, 
    [AdditionalText1] NVARCHAR(255) NULL, 
    [AdditionalText2] NVARCHAR(255) NULL, 
    [AdditionalText3] NVARCHAR(255) NULL, 
    [AdditionalText4] NVARCHAR(255) NULL, 
    [AdditionalText5] NVARCHAR(255) NULL, 
    [AdditionalText6] NVARCHAR(255) NULL, 
    [AdditionalText7] NVARCHAR(255) NULL, 
    [AdditionalNumber1] NUMERIC(18, 4) NULL, 
    [AdditionalNumber2] NUMERIC(18, 4) NULL, 
    [AdditionalNumber3] NUMERIC(18, 4) NULL, 
    CONSTRAINT [PK_Location] PRIMARY KEY ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Lokasyon (tesis, depo). Faz 1''de her lokasyon kendi içinde planlanır.', 'schema', core, 'table', [Location];

GO

execute sp_addextendedproperty 'MS_Description', N'Lokasyon kimliği', 'schema', core, 'table', [Location], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Lokasyon kodu', 'schema', core, 'table', [Location], 'column', [Code];

GO

execute sp_addextendedproperty 'MS_Description', N'Lokasyon adı', 'schema', core, 'table', [Location], 'column', [Name];

GO

execute sp_addextendedproperty 'MS_Description', N'Tesis | Depo | Fason deposu', 'schema', core, 'table', [Location], 'column', [Type];

GO

execute sp_addextendedproperty 'MS_Description', N'Ülke', 'schema', core, 'table', [Location], 'column', [Country];

GO

execute sp_addextendedproperty 'MS_Description', N'Ülke kodu', 'schema', core, 'table', [Location], 'column', [CountryCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Bölge', 'schema', core, 'table', [Location], 'column', [Region];

GO

execute sp_addextendedproperty 'MS_Description', N'Bölge kodu', 'schema', core, 'table', [Location], 'column', [RegionCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Şehir', 'schema', core, 'table', [Location], 'column', [City];

GO

execute sp_addextendedproperty 'MS_Description', N'Şehir kodu', 'schema', core, 'table', [Location], 'column', [CityCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Location], 'column', [AdditionalText1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Location], 'column', [AdditionalText2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Location], 'column', [AdditionalText3];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Location], 'column', [AdditionalText4];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Location], 'column', [AdditionalText5];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Location], 'column', [AdditionalText6];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Location], 'column', [AdditionalText7];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Location], 'column', [AdditionalNumber1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Location], 'column', [AdditionalNumber2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Location], 'column', [AdditionalNumber3];

GO

CREATE UNIQUE INDEX [UX_Location_Code] ON core.[Location] ([Code]);

GO

CREATE TABLE core.[UnitOfMeasure] (
    [Code] NVARCHAR(10) NOT NULL, 
    [Name] NVARCHAR(50) NULL, 
    CONSTRAINT [PK_UnitOfMeasure] PRIMARY KEY ([Code])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Ölçü birimi.', 'schema', core, 'table', [UnitOfMeasure];

GO

execute sp_addextendedproperty 'MS_Description', N'Birim kodu (AD, KG, SAAT…)', 'schema', core, 'table', [UnitOfMeasure], 'column', [Code];

GO

execute sp_addextendedproperty 'MS_Description', N'Birim adı', 'schema', core, 'table', [UnitOfMeasure], 'column', [Name];

GO

CREATE TABLE param.[ParameterSet] (
    [Id] INTEGER NOT NULL IDENTITY, 
    [Name] NVARCHAR(100) NOT NULL, 
    [IsDefault] BIT NULL DEFAULT 0, 
    CONSTRAINT [PK_ParameterSet] PRIMARY KEY ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Parametre seti; gece senaryoları farklı setlerle çalışır.', 'schema', param, 'table', [ParameterSet];

GO

execute sp_addextendedproperty 'MS_Description', N'Set kimliği', 'schema', param, 'table', [ParameterSet], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Set adı', 'schema', param, 'table', [ParameterSet], 'column', [Name];

GO

execute sp_addextendedproperty 'MS_Description', N'Varsayılan set', 'schema', param, 'table', [ParameterSet], 'column', [IsDefault];

GO

CREATE TABLE param.[WarningDefinition] (
    [Code] NVARCHAR(30) NOT NULL, 
    [Category] NVARCHAR(20) NOT NULL, 
    [Threshold] NUMERIC(18, 4) NULL, 
    [Severity] NVARCHAR(10) NULL, 
    [IsActive] BIT NULL DEFAULT 1, 
    CONSTRAINT [PK_WarningDefinition] PRIMARY KEY ([Code])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Uyarı tanımı, eşik ve önem seviyesi.', 'schema', param, 'table', [WarningDefinition];

GO

execute sp_addextendedproperty 'MS_Description', N'Uyarı kodu', 'schema', param, 'table', [WarningDefinition], 'column', [Code];

GO

execute sp_addextendedproperty 'MS_Description', N'Kapasite | Malzeme | Sipariş | Ana veri | İşlem verisi | Veri değişikliği | Plan değişikliği', 'schema', param, 'table', [WarningDefinition], 'column', [Category];

GO

execute sp_addextendedproperty 'MS_Description', N'Tolerans eşiği', 'schema', param, 'table', [WarningDefinition], 'column', [Threshold];

GO

execute sp_addextendedproperty 'MS_Description', N'Önem seviyesi', 'schema', param, 'table', [WarningDefinition], 'column', [Severity];

GO

execute sp_addextendedproperty 'MS_Description', N'Aktif', 'schema', param, 'table', [WarningDefinition], 'column', [IsActive];

GO

CREATE TABLE adm.[AuditLog] (
    [Id] BIGINT NOT NULL IDENTITY, 
    [UserId] INTEGER NULL, 
    [At] DATETIME2 NOT NULL, 
    [Action] NVARCHAR(40) NOT NULL, 
    [ObjectType] NVARCHAR(40) NULL, 
    [ObjectKey] NVARCHAR(200) NULL, 
    [OldValue] NVARCHAR(max) NULL, 
    [NewValue] NVARCHAR(max) NULL, 
    CONSTRAINT [PK_AuditLog] PRIMARY KEY ([Id]), 
    CONSTRAINT [FK_AuditLog_UserId] FOREIGN KEY([UserId]) REFERENCES adm.[AppUser] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Kim, ne zaman, neyi değiştirdi; giriş kayıtları; sistem sahibi işlemleri silinemez.', 'schema', adm, 'table', [AuditLog];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', adm, 'table', [AuditLog], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Kullanıcı', 'schema', adm, 'table', [AuditLog], 'column', [UserId];

GO

execute sp_addextendedproperty 'MS_Description', N'Zaman', 'schema', adm, 'table', [AuditLog], 'column', [At];

GO

execute sp_addextendedproperty 'MS_Description', N'İşlem', 'schema', adm, 'table', [AuditLog], 'column', [Action];

GO

execute sp_addextendedproperty 'MS_Description', N'Nesne', 'schema', adm, 'table', [AuditLog], 'column', [ObjectType];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt', 'schema', adm, 'table', [AuditLog], 'column', [ObjectKey];

GO

execute sp_addextendedproperty 'MS_Description', N'Önceki', 'schema', adm, 'table', [AuditLog], 'column', [OldValue];

GO

execute sp_addextendedproperty 'MS_Description', N'Yeni', 'schema', adm, 'table', [AuditLog], 'column', [NewValue];

GO

CREATE TABLE adm.[DataRuleCondition] (
    [Id] BIGINT NOT NULL IDENTITY, 
    [DataRuleId] BIGINT NOT NULL, 
    [GroupNo] INTEGER NULL DEFAULT 1, 
    [FieldName] NVARCHAR(60) NOT NULL, 
    [Operator] NVARCHAR(15) NOT NULL, 
    [Value] NVARCHAR(200) NULL, 
    CONSTRAINT [PK_DataRuleCondition] PRIMARY KEY ([Id]), 
    CONSTRAINT [FK_DataRuleCondition_DataRuleId] FOREIGN KEY([DataRuleId]) REFERENCES adm.[DataRule] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Kural koşulları (VE / VEYA).', 'schema', adm, 'table', [DataRuleCondition];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', adm, 'table', [DataRuleCondition], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Kural', 'schema', adm, 'table', [DataRuleCondition], 'column', [DataRuleId];

GO

execute sp_addextendedproperty 'MS_Description', N'VEYA grubu', 'schema', adm, 'table', [DataRuleCondition], 'column', [GroupNo];

GO

execute sp_addextendedproperty 'MS_Description', N'Alan', 'schema', adm, 'table', [DataRuleCondition], 'column', [FieldName];

GO

execute sp_addextendedproperty 'MS_Description', N'Eşittir | İçinde | İle başlar | İçerir | Büyüktür | Küçüktür | Boş', 'schema', adm, 'table', [DataRuleCondition], 'column', [Operator];

GO

execute sp_addextendedproperty 'MS_Description', N'Değer', 'schema', adm, 'table', [DataRuleCondition], 'column', [Value];

GO

CREATE TABLE adm.[DataVersion] (
    [Id] BIGINT NOT NULL IDENTITY, 
    [LocationId] INTEGER NOT NULL, 
    [CreatedAt] DATETIME2 NOT NULL, 
    [LoadType] NVARCHAR(10) NOT NULL, 
    [CreatedBy] INTEGER NULL, 
    [IsPinned] BIT NULL DEFAULT 0, 
    CONSTRAINT [PK_DataVersion] PRIMARY KEY ([Id]), 
    CONSTRAINT [FK_DataVersion_CreatedBy] FOREIGN KEY([CreatedBy]) REFERENCES adm.[AppUser] ([Id]), 
    CONSTRAINT [FK_DataVersion_LocationId] FOREIGN KEY([LocationId]) REFERENCES core.[Location] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Yükleme ile oluşan dondurulmuş veri versiyonu; tam ya da kısmi.', 'schema', adm, 'table', [DataVersion];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', adm, 'table', [DataVersion], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Lokasyon', 'schema', adm, 'table', [DataVersion], 'column', [LocationId];

GO

execute sp_addextendedproperty 'MS_Description', N'Oluşma zamanı', 'schema', adm, 'table', [DataVersion], 'column', [CreatedAt];

GO

execute sp_addextendedproperty 'MS_Description', N'Tam | Kısmi', 'schema', adm, 'table', [DataVersion], 'column', [LoadType];

GO

execute sp_addextendedproperty 'MS_Description', N'Kullanıcı ya da sistem kullanıcısı', 'schema', adm, 'table', [DataVersion], 'column', [CreatedBy];

GO

execute sp_addextendedproperty 'MS_Description', N'Onaylı plana bağlı; silinmez', 'schema', adm, 'table', [DataVersion], 'column', [IsPinned];

GO

CREATE TABLE adm.[FieldValueSource] (
    [TableName] NVARCHAR(60) NOT NULL, 
    [RecordId] BIGINT NOT NULL, 
    [FieldName] NVARCHAR(60) NOT NULL, 
    [Source] NVARCHAR(10) NOT NULL, 
    [DataRuleId] BIGINT NULL, 
    [ErpValue] NVARCHAR(200) NULL, 
    CONSTRAINT [PK_FieldValueSource] PRIMARY KEY ([TableName], [RecordId], [FieldName]), 
    CONSTRAINT [FK_FieldValueSource_DataRuleId] FOREIGN KEY([DataRuleId]) REFERENCES adm.[DataRule] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Geçerli değerin kaynağı ve ERP değeri (ezilse bile saklanır).', 'schema', adm, 'table', [FieldValueSource];

GO

execute sp_addextendedproperty 'MS_Description', N'Tablo', 'schema', adm, 'table', [FieldValueSource], 'column', [TableName];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt', 'schema', adm, 'table', [FieldValueSource], 'column', [RecordId];

GO

execute sp_addextendedproperty 'MS_Description', N'Alan', 'schema', adm, 'table', [FieldValueSource], 'column', [FieldName];

GO

execute sp_addextendedproperty 'MS_Description', N'ERP | Kural | Elle | Varsayılan', 'schema', adm, 'table', [FieldValueSource], 'column', [Source];

GO

execute sp_addextendedproperty 'MS_Description', N'Uygulanan kural', 'schema', adm, 'table', [FieldValueSource], 'column', [DataRuleId];

GO

execute sp_addextendedproperty 'MS_Description', N'ERP''den gelen değer', 'schema', adm, 'table', [FieldValueSource], 'column', [ErpValue];

GO

CREATE TABLE adm.[Job] (
    [Id] BIGINT NOT NULL IDENTITY, 
    [JobType] NVARCHAR(20) NOT NULL, 
    [Channel] NVARCHAR(10) NOT NULL, 
    [Priority] INTEGER NULL, 
    [Status] NVARCHAR(15) NOT NULL, 
    [RequestedBy] INTEGER NULL, 
    [Payload] NVARCHAR(max) NULL, 
    [Progress] NVARCHAR(100) NULL, 
    [HeartbeatAt] DATETIME2 NULL, 
    [Attempt] INTEGER NULL DEFAULT 0, 
    [ErrorText] NVARCHAR(max) NULL, 
    CONSTRAINT [PK_Job] PRIMARY KEY ([Id]), 
    CONSTRAINT [FK_Job_RequestedBy] FOREIGN KEY([RequestedBy]) REFERENCES adm.[AppUser] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'İş kuyruğu (SQL Server tablosu): gece senaryoları, çalışma hesapları, yüklemeler.', 'schema', adm, 'table', [Job];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', adm, 'table', [Job], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Gece senaryosu | Çalışma | Yükleme | Termin sorgusu …', 'schema', adm, 'table', [Job], 'column', [JobType];

GO

execute sp_addextendedproperty 'MS_Description', N'Gece | Etkileşim', 'schema', adm, 'table', [Job], 'column', [Channel];

GO

execute sp_addextendedproperty 'MS_Description', N'Öncelik', 'schema', adm, 'table', [Job], 'column', [Priority];

GO

execute sp_addextendedproperty 'MS_Description', N'Sırada | Çalışıyor | Bitti | Hata | İptal', 'schema', adm, 'table', [Job], 'column', [Status];

GO

execute sp_addextendedproperty 'MS_Description', N'Başlatan', 'schema', adm, 'table', [Job], 'column', [RequestedBy];

GO

execute sp_addextendedproperty 'MS_Description', N'İş parametreleri (JSON)', 'schema', adm, 'table', [Job], 'column', [Payload];

GO

execute sp_addextendedproperty 'MS_Description', N'İlerleme', 'schema', adm, 'table', [Job], 'column', [Progress];

GO

execute sp_addextendedproperty 'MS_Description', N'Son yaşam sinyali', 'schema', adm, 'table', [Job], 'column', [HeartbeatAt];

GO

execute sp_addextendedproperty 'MS_Description', N'Deneme sayısı', 'schema', adm, 'table', [Job], 'column', [Attempt];

GO

execute sp_addextendedproperty 'MS_Description', N'Hata', 'schema', adm, 'table', [Job], 'column', [ErrorText];

GO

CREATE TABLE adm.[ManualValue] (
    [Id] BIGINT NOT NULL IDENTITY, 
    [TableName] NVARCHAR(60) NOT NULL, 
    [RecordKey] NVARCHAR(200) NOT NULL, 
    [FieldName] NVARCHAR(60) NOT NULL, 
    [Value] NVARCHAR(200) NOT NULL, 
    [ValidUntil] NVARCHAR(20) NULL DEFAULT N'Süresiz', 
    [CreatedBy] INTEGER NULL, 
    [CreatedAt] DATETIME2 NULL, 
    CONSTRAINT [PK_ManualValue] PRIMARY KEY ([Id]), 
    CONSTRAINT [FK_ManualValue_CreatedBy] FOREIGN KEY([CreatedBy]) REFERENCES adm.[AppUser] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt bazında elle girilen değer.', 'schema', adm, 'table', [ManualValue];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', adm, 'table', [ManualValue], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Tablo', 'schema', adm, 'table', [ManualValue], 'column', [TableName];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın iş anahtarı', 'schema', adm, 'table', [ManualValue], 'column', [RecordKey];

GO

execute sp_addextendedproperty 'MS_Description', N'Alan', 'schema', adm, 'table', [ManualValue], 'column', [FieldName];

GO

execute sp_addextendedproperty 'MS_Description', N'Değer', 'schema', adm, 'table', [ManualValue], 'column', [Value];

GO

execute sp_addextendedproperty 'MS_Description', N'Süresiz | ERP değişene kadar | tarih', 'schema', adm, 'table', [ManualValue], 'column', [ValidUntil];

GO

execute sp_addextendedproperty 'MS_Description', N'Giren kullanıcı', 'schema', adm, 'table', [ManualValue], 'column', [CreatedBy];

GO

execute sp_addextendedproperty 'MS_Description', N'Zaman', 'schema', adm, 'table', [ManualValue], 'column', [CreatedAt];

GO

CREATE TABLE core.[BOM] (
    [Id] BIGINT NOT NULL, 
    [ProductionVersionId] BIGINT NOT NULL, 
    [ComponentMaterialId] BIGINT NOT NULL, 
    [Quantity] NUMERIC(18, 6) NOT NULL, 
    [ScrapPct] NUMERIC(6, 2) NULL DEFAULT 0, 
    [IsFixedQuantity] BIT NULL DEFAULT 0, 
    [OpNo] INTEGER NULL, 
    [AdditionalText1] NVARCHAR(255) NULL, 
    [AdditionalText2] NVARCHAR(255) NULL, 
    [AdditionalText3] NVARCHAR(255) NULL, 
    [AdditionalNumber1] NUMERIC(18, 4) NULL, 
    [AdditionalNumber2] NUMERIC(18, 4) NULL, 
    [VersionFrom] INTEGER NOT NULL, 
    [VersionTo] INTEGER NULL, 
    [ImportBatchId] BIGINT NULL, 
    [BusinessKey] NVARCHAR(200) NOT NULL, 
    [UpdatedAt] DATETIME2 NOT NULL, 
    CONSTRAINT [PK_BOM] PRIMARY KEY ([Id], [VersionFrom]), 
    CONSTRAINT [FK_BOM_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Ürün ağacı satırı.', 'schema', core, 'table', [BOM];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', core, 'table', [BOM], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Üretim versiyonu', 'schema', core, 'table', [BOM], 'column', [ProductionVersionId];

GO

execute sp_addextendedproperty 'MS_Description', N'Bileşen', 'schema', core, 'table', [BOM], 'column', [ComponentMaterialId];

GO

execute sp_addextendedproperty 'MS_Description', N'Baz miktar için bileşen miktarı', 'schema', core, 'table', [BOM], 'column', [Quantity];

GO

execute sp_addextendedproperty 'MS_Description', N'Bileşen firesi (%)', 'schema', core, 'table', [BOM], 'column', [ScrapPct];

GO

execute sp_addextendedproperty 'MS_Description', N'Sabit miktarlı bileşen', 'schema', core, 'table', [BOM], 'column', [IsFixedQuantity];

GO

execute sp_addextendedproperty 'MS_Description', N'Bağlı olduğu operasyon no (ihtiyaç tarihi için)', 'schema', core, 'table', [BOM], 'column', [OpNo];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [BOM], 'column', [AdditionalText1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [BOM], 'column', [AdditionalText2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [BOM], 'column', [AdditionalText3];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [BOM], 'column', [AdditionalNumber1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [BOM], 'column', [AdditionalNumber2];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu ilk veri versiyonu', 'schema', core, 'table', [BOM], 'column', [VersionFrom];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş', 'schema', core, 'table', [BOM], 'column', [VersionTo];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydı getiren yükleme partisi', 'schema', core, 'table', [BOM], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'İş anahtarı (kod ya da kodların birleşimi)', 'schema', core, 'table', [BOM], 'column', [BusinessKey];

GO

execute sp_addextendedproperty 'MS_Description', N'Son değişiklik zamanı', 'schema', core, 'table', [BOM], 'column', [UpdatedAt];

GO

CREATE INDEX [IX_BOM_ComponentMaterialId] ON core.[BOM] ([ComponentMaterialId]);

GO

CREATE INDEX [IX_BOM_ProductionVersionId] ON core.[BOM] ([ProductionVersionId]);

GO

CREATE TABLE core.[Calendar] (
    [Id] INTEGER NOT NULL, 
    [Code] NVARCHAR(30) NOT NULL, 
    [Name] NVARCHAR(100) NULL, 
    [VersionFrom] INTEGER NOT NULL, 
    [VersionTo] INTEGER NULL, 
    [ImportBatchId] BIGINT NULL, 
    [BusinessKey] NVARCHAR(200) NOT NULL, 
    [UpdatedAt] DATETIME2 NOT NULL, 
    CONSTRAINT [PK_Calendar] PRIMARY KEY ([Id], [VersionFrom]), 
    CONSTRAINT [FK_Calendar_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Çalışma takvimi başlığı (kaynaklara bağlanır). Smartchain''de ekrandan girilir; entegrasyondan gelmez (K-65).', 'schema', core, 'table', [Calendar];

GO

execute sp_addextendedproperty 'MS_Description', N'Takvim kimliği', 'schema', core, 'table', [Calendar], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Takvim kodu', 'schema', core, 'table', [Calendar], 'column', [Code];

GO

execute sp_addextendedproperty 'MS_Description', N'Takvim adı', 'schema', core, 'table', [Calendar], 'column', [Name];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu ilk veri versiyonu', 'schema', core, 'table', [Calendar], 'column', [VersionFrom];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş', 'schema', core, 'table', [Calendar], 'column', [VersionTo];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydı getiren yükleme partisi', 'schema', core, 'table', [Calendar], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'İş anahtarı (kod ya da kodların birleşimi)', 'schema', core, 'table', [Calendar], 'column', [BusinessKey];

GO

execute sp_addextendedproperty 'MS_Description', N'Son değişiklik zamanı', 'schema', core, 'table', [Calendar], 'column', [UpdatedAt];

GO

CREATE UNIQUE INDEX [UX_Calendar_Code] ON core.[Calendar] ([Code]) WHERE VersionTo IS NULL;

GO

CREATE TABLE core.[CalendarDay] (
    [CalendarId] INTEGER NOT NULL, 
    [Date] DATE NOT NULL, 
    [IsWorkingDay] BIT NOT NULL DEFAULT 1, 
    [WorkingFraction] NUMERIC(5, 4) NULL DEFAULT 1, 
    [VersionFrom] INTEGER NOT NULL, 
    [VersionTo] INTEGER NULL, 
    [ImportBatchId] BIGINT NULL, 
    [BusinessKey] NVARCHAR(200) NOT NULL, 
    [UpdatedAt] DATETIME2 NOT NULL, 
    CONSTRAINT [PK_CalendarDay] PRIMARY KEY ([CalendarId], [Date], [VersionFrom]), 
    CONSTRAINT [FK_CalendarDay_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Takvimin gün bazında çalışma durumu. Smartchain''de ekrandan girilir; entegrasyondan gelmez (K-65).', 'schema', core, 'table', [CalendarDay];

GO

execute sp_addextendedproperty 'MS_Description', N'Takvim', 'schema', core, 'table', [CalendarDay], 'column', [CalendarId];

GO

execute sp_addextendedproperty 'MS_Description', N'Gün', 'schema', core, 'table', [CalendarDay], 'column', [Date];

GO

execute sp_addextendedproperty 'MS_Description', N'Çalışma günü mü', 'schema', core, 'table', [CalendarDay], 'column', [IsWorkingDay];

GO

execute sp_addextendedproperty 'MS_Description', N'Günün çalışılan oranı (yarım gün 0,5)', 'schema', core, 'table', [CalendarDay], 'column', [WorkingFraction];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu ilk veri versiyonu', 'schema', core, 'table', [CalendarDay], 'column', [VersionFrom];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş', 'schema', core, 'table', [CalendarDay], 'column', [VersionTo];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydı getiren yükleme partisi', 'schema', core, 'table', [CalendarDay], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'İş anahtarı (kod ya da kodların birleşimi)', 'schema', core, 'table', [CalendarDay], 'column', [BusinessKey];

GO

execute sp_addextendedproperty 'MS_Description', N'Son değişiklik zamanı', 'schema', core, 'table', [CalendarDay], 'column', [UpdatedAt];

GO

CREATE INDEX [IX_CalendarDay_CalendarId] ON core.[CalendarDay] ([CalendarId]);

GO

CREATE TABLE core.[CompetenceGroup] (
    [Id] BIGINT NOT NULL, 
    [LocationId] INTEGER NOT NULL, 
    [Code] NVARCHAR(50) NOT NULL, 
    [Name] NVARCHAR(150) NULL, 
    [VersionFrom] INTEGER NOT NULL, 
    [VersionTo] INTEGER NULL, 
    [ImportBatchId] BIGINT NULL, 
    [BusinessKey] NVARCHAR(200) NOT NULL, 
    [UpdatedAt] DATETIME2 NOT NULL, 
    CONSTRAINT [PK_CompetenceGroup] PRIMARY KEY ([Id], [VersionFrom]), 
    CONSTRAINT [FK_CompetenceGroup_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id]), 
    CONSTRAINT [FK_CompetenceGroup_LocationId] FOREIGN KEY([LocationId]) REFERENCES core.[Location] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'İşçi yetkinlik grubu.', 'schema', core, 'table', [CompetenceGroup];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', core, 'table', [CompetenceGroup], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Lokasyon', 'schema', core, 'table', [CompetenceGroup], 'column', [LocationId];

GO

execute sp_addextendedproperty 'MS_Description', N'Grup kodu', 'schema', core, 'table', [CompetenceGroup], 'column', [Code];

GO

execute sp_addextendedproperty 'MS_Description', N'Grup adı', 'schema', core, 'table', [CompetenceGroup], 'column', [Name];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu ilk veri versiyonu', 'schema', core, 'table', [CompetenceGroup], 'column', [VersionFrom];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş', 'schema', core, 'table', [CompetenceGroup], 'column', [VersionTo];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydı getiren yükleme partisi', 'schema', core, 'table', [CompetenceGroup], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'İş anahtarı (kod ya da kodların birleşimi)', 'schema', core, 'table', [CompetenceGroup], 'column', [BusinessKey];

GO

execute sp_addextendedproperty 'MS_Description', N'Son değişiklik zamanı', 'schema', core, 'table', [CompetenceGroup], 'column', [UpdatedAt];

GO

CREATE UNIQUE INDEX [UX_CompetenceGroup_Code] ON core.[CompetenceGroup] ([Code]) WHERE VersionTo IS NULL;

GO

CREATE TABLE core.[Customer] (
    [Id] BIGINT NOT NULL, 
    [Code] NVARCHAR(50) NOT NULL, 
    [Name] NVARCHAR(200) NULL, 
    [Priority] INTEGER NULL, 
    [AllowPartialDelivery] BIT NULL DEFAULT 1, 
    [AdditionalText1] NVARCHAR(255) NULL, 
    [AdditionalText2] NVARCHAR(255) NULL, 
    [AdditionalText3] NVARCHAR(255) NULL, 
    [AdditionalText4] NVARCHAR(255) NULL, 
    [AdditionalText5] NVARCHAR(255) NULL, 
    [AdditionalText6] NVARCHAR(255) NULL, 
    [AdditionalText7] NVARCHAR(255) NULL, 
    [AdditionalNumber1] NUMERIC(18, 4) NULL, 
    [AdditionalNumber2] NUMERIC(18, 4) NULL, 
    [AdditionalNumber3] NUMERIC(18, 4) NULL, 
    [VersionFrom] INTEGER NOT NULL, 
    [VersionTo] INTEGER NULL, 
    [ImportBatchId] BIGINT NULL, 
    [BusinessKey] NVARCHAR(200) NOT NULL, 
    [UpdatedAt] DATETIME2 NOT NULL, 
    CONSTRAINT [PK_Customer] PRIMARY KEY ([Id], [VersionFrom]), 
    CONSTRAINT [FK_Customer_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Müşteri.', 'schema', core, 'table', [Customer];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', core, 'table', [Customer], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Müşteri kodu', 'schema', core, 'table', [Customer], 'column', [Code];

GO

execute sp_addextendedproperty 'MS_Description', N'Ad', 'schema', core, 'table', [Customer], 'column', [Name];

GO

execute sp_addextendedproperty 'MS_Description', N'Müşteri önceliği', 'schema', core, 'table', [Customer], 'column', [Priority];

GO

execute sp_addextendedproperty 'MS_Description', N'Kısmi teslimata izin', 'schema', core, 'table', [Customer], 'column', [AllowPartialDelivery];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Customer], 'column', [AdditionalText1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Customer], 'column', [AdditionalText2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Customer], 'column', [AdditionalText3];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Customer], 'column', [AdditionalText4];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Customer], 'column', [AdditionalText5];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Customer], 'column', [AdditionalText6];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Customer], 'column', [AdditionalText7];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Customer], 'column', [AdditionalNumber1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Customer], 'column', [AdditionalNumber2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Customer], 'column', [AdditionalNumber3];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu ilk veri versiyonu', 'schema', core, 'table', [Customer], 'column', [VersionFrom];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş', 'schema', core, 'table', [Customer], 'column', [VersionTo];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydı getiren yükleme partisi', 'schema', core, 'table', [Customer], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'İş anahtarı (kod ya da kodların birleşimi)', 'schema', core, 'table', [Customer], 'column', [BusinessKey];

GO

execute sp_addextendedproperty 'MS_Description', N'Son değişiklik zamanı', 'schema', core, 'table', [Customer], 'column', [UpdatedAt];

GO

CREATE UNIQUE INDEX [UX_Customer_Code] ON core.[Customer] ([Code]) WHERE VersionTo IS NULL;

GO

CREATE TABLE core.[Forecast] (
    [Id] BIGINT NOT NULL, 
    [LocationId] INTEGER NOT NULL, 
    [MaterialId] BIGINT NOT NULL, 
    [CustomerId] BIGINT NULL, 
    [ProjectId] BIGINT NULL, 
    [Period] DATE NOT NULL, 
    [Quantity] NUMERIC(18, 4) NOT NULL, 
    [AdditionalText1] NVARCHAR(255) NULL, 
    [AdditionalText2] NVARCHAR(255) NULL, 
    [AdditionalText3] NVARCHAR(255) NULL, 
    [AdditionalNumber1] NUMERIC(18, 4) NULL, 
    [AdditionalNumber2] NUMERIC(18, 4) NULL, 
    [VersionFrom] INTEGER NOT NULL, 
    [VersionTo] INTEGER NULL, 
    [ImportBatchId] BIGINT NULL, 
    [BusinessKey] NVARCHAR(200) NOT NULL, 
    [UpdatedAt] DATETIME2 NOT NULL, 
    CONSTRAINT [PK_Forecast] PRIMARY KEY ([Id], [VersionFrom]), 
    CONSTRAINT [FK_Forecast_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id]), 
    CONSTRAINT [FK_Forecast_LocationId] FOREIGN KEY([LocationId]) REFERENCES core.[Location] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Talep tahmini (netleme ön hesapta).', 'schema', core, 'table', [Forecast];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', core, 'table', [Forecast], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Lokasyon', 'schema', core, 'table', [Forecast], 'column', [LocationId];

GO

execute sp_addextendedproperty 'MS_Description', N'Malzeme', 'schema', core, 'table', [Forecast], 'column', [MaterialId];

GO

execute sp_addextendedproperty 'MS_Description', N'Müşteri', 'schema', core, 'table', [Forecast], 'column', [CustomerId];

GO

execute sp_addextendedproperty 'MS_Description', N'Proje', 'schema', core, 'table', [Forecast], 'column', [ProjectId];

GO

execute sp_addextendedproperty 'MS_Description', N'Dönem', 'schema', core, 'table', [Forecast], 'column', [Period];

GO

execute sp_addextendedproperty 'MS_Description', N'Miktar', 'schema', core, 'table', [Forecast], 'column', [Quantity];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Forecast], 'column', [AdditionalText1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Forecast], 'column', [AdditionalText2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Forecast], 'column', [AdditionalText3];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Forecast], 'column', [AdditionalNumber1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Forecast], 'column', [AdditionalNumber2];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu ilk veri versiyonu', 'schema', core, 'table', [Forecast], 'column', [VersionFrom];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş', 'schema', core, 'table', [Forecast], 'column', [VersionTo];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydı getiren yükleme partisi', 'schema', core, 'table', [Forecast], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'İş anahtarı (kod ya da kodların birleşimi)', 'schema', core, 'table', [Forecast], 'column', [BusinessKey];

GO

execute sp_addextendedproperty 'MS_Description', N'Son değişiklik zamanı', 'schema', core, 'table', [Forecast], 'column', [UpdatedAt];

GO

CREATE INDEX [IX_Forecast_CustomerId] ON core.[Forecast] ([CustomerId]);

GO

CREATE INDEX [IX_Forecast_MaterialId] ON core.[Forecast] ([MaterialId]);

GO

CREATE INDEX [IX_Forecast_ProjectId] ON core.[Forecast] ([ProjectId]);

GO

CREATE TABLE core.[Material] (
    [Id] BIGINT NOT NULL, 
    [LocationId] INTEGER NOT NULL, 
    [Code] NVARCHAR(50) NOT NULL, 
    [Name] NVARCHAR(200) NULL, 
    [BaseUom] NVARCHAR(10) NOT NULL, 
    [MaterialGroup] NVARCHAR(50) NULL, 
    [MaterialLevel] NVARCHAR(15) NULL, 
    [IsPurchasable] BIT NULL DEFAULT 0, 
    [IsProducible] BIT NULL DEFAULT 0, 
    [IsSellable] BIT NULL DEFAULT 0, 
    [DefaultProcurement] NVARCHAR(10) NULL, 
    [Ownership] NVARCHAR(10) NULL DEFAULT N'Kendi', 
    [IsProjectTracked] BIT NULL DEFAULT 0, 
    [IsPhantom] BIT NULL DEFAULT 0, 
    [ProductionLeadTimeDays] NUMERIC(9, 2) NULL, 
    [GoodsReceiptDays] NUMERIC(9, 2) NULL DEFAULT 0, 
    [SafetyStock] NUMERIC(18, 4) NULL DEFAULT 0, 
    [MaxStock] NUMERIC(18, 4) NULL, 
    [LotSizePolicy] NVARCHAR(15) NULL DEFAULT N'Lot-for-lot', 
    [MinLot] NUMERIC(18, 4) NULL, 
    [MaxLot] NUMERIC(18, 4) NULL, 
    [LotMultiple] NUMERIC(18, 4) NULL, 
    [AssemblyScrapPct] NUMERIC(6, 2) NULL DEFAULT 0, 
    [ShelfLifeDays] INTEGER NULL, 
    [AdditionalText1] NVARCHAR(255) NULL, 
    [AdditionalText2] NVARCHAR(255) NULL, 
    [AdditionalText3] NVARCHAR(255) NULL, 
    [AdditionalText4] NVARCHAR(255) NULL, 
    [AdditionalText5] NVARCHAR(255) NULL, 
    [AdditionalText6] NVARCHAR(255) NULL, 
    [AdditionalText7] NVARCHAR(255) NULL, 
    [AdditionalNumber1] NUMERIC(18, 4) NULL, 
    [AdditionalNumber2] NUMERIC(18, 4) NULL, 
    [AdditionalNumber3] NUMERIC(18, 4) NULL, 
    [VersionFrom] INTEGER NOT NULL, 
    [VersionTo] INTEGER NULL, 
    [ImportBatchId] BIGINT NULL, 
    [BusinessKey] NVARCHAR(200) NOT NULL, 
    [UpdatedAt] DATETIME2 NOT NULL, 
    CONSTRAINT [PK_Material] PRIMARY KEY ([Id], [VersionFrom]), 
    CONSTRAINT [FK_Material_BaseUom] FOREIGN KEY([BaseUom]) REFERENCES core.[UnitOfMeasure] ([Code]), 
    CONSTRAINT [FK_Material_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id]), 
    CONSTRAINT [FK_Material_LocationId] FOREIGN KEY([LocationId]) REFERENCES core.[Location] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Malzeme ve planlama ana verisi.', 'schema', core, 'table', [Material];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', core, 'table', [Material], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Lokasyon', 'schema', core, 'table', [Material], 'column', [LocationId];

GO

execute sp_addextendedproperty 'MS_Description', N'Malzeme kodu', 'schema', core, 'table', [Material], 'column', [Code];

GO

execute sp_addextendedproperty 'MS_Description', N'Malzeme adı', 'schema', core, 'table', [Material], 'column', [Name];

GO

execute sp_addextendedproperty 'MS_Description', N'Temel birim', 'schema', core, 'table', [Material], 'column', [BaseUom];

GO

execute sp_addextendedproperty 'MS_Description', N'Malzeme grubu', 'schema', core, 'table', [Material], 'column', [MaterialGroup];

GO

execute sp_addextendedproperty 'MS_Description', N'Hammadde | Yarı mamul | Nihai ürün', 'schema', core, 'table', [Material], 'column', [MaterialLevel];

GO

execute sp_addextendedproperty 'MS_Description', N'Satın alınabilir', 'schema', core, 'table', [Material], 'column', [IsPurchasable];

GO

execute sp_addextendedproperty 'MS_Description', N'Üretilebilir', 'schema', core, 'table', [Material], 'column', [IsProducible];

GO

execute sp_addextendedproperty 'MS_Description', N'Satılabilir', 'schema', core, 'table', [Material], 'column', [IsSellable];

GO

execute sp_addextendedproperty 'MS_Description', N'Üretim | Satın alma | Fason', 'schema', core, 'table', [Material], 'column', [DefaultProcurement];

GO

execute sp_addextendedproperty 'MS_Description', N'Kendi | Müşteri (müşteri temin malzemesi)', 'schema', core, 'table', [Material], 'column', [Ownership];

GO

execute sp_addextendedproperty 'MS_Description', N'Proje bazlı takip edilir mi (değilse her zaman ortak)', 'schema', core, 'table', [Material], 'column', [IsProjectTracked];

GO

execute sp_addextendedproperty 'MS_Description', N'Hayalet yarı mamul', 'schema', core, 'table', [Material], 'column', [IsPhantom];

GO

execute sp_addextendedproperty 'MS_Description', N'Üretim süresi (gün)', 'schema', core, 'table', [Material], 'column', [ProductionLeadTimeDays];

GO

execute sp_addextendedproperty 'MS_Description', N'Mal kabul süresi (iş günü)', 'schema', core, 'table', [Material], 'column', [GoodsReceiptDays];

GO

execute sp_addextendedproperty 'MS_Description', N'Güvenlik stoğu', 'schema', core, 'table', [Material], 'column', [SafetyStock];

GO

execute sp_addextendedproperty 'MS_Description', N'Maksimum stok', 'schema', core, 'table', [Material], 'column', [MaxStock];

GO

execute sp_addextendedproperty 'MS_Description', N'Üretimde: Lot-for-lot | Sabit | Dönemsel', 'schema', core, 'table', [Material], 'column', [LotSizePolicy];

GO

execute sp_addextendedproperty 'MS_Description', N'Üretimde minimum', 'schema', core, 'table', [Material], 'column', [MinLot];

GO

execute sp_addextendedproperty 'MS_Description', N'Üretimde maksimum', 'schema', core, 'table', [Material], 'column', [MaxLot];

GO

execute sp_addextendedproperty 'MS_Description', N'Üretimde kat', 'schema', core, 'table', [Material], 'column', [LotMultiple];

GO

execute sp_addextendedproperty 'MS_Description', N'Montaj firesi (%)', 'schema', core, 'table', [Material], 'column', [AssemblyScrapPct];

GO

execute sp_addextendedproperty 'MS_Description', N'Raf ömrü (gün); Faz 1''de yalnız uyarı', 'schema', core, 'table', [Material], 'column', [ShelfLifeDays];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Material], 'column', [AdditionalText1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Material], 'column', [AdditionalText2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Material], 'column', [AdditionalText3];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Material], 'column', [AdditionalText4];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Material], 'column', [AdditionalText5];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Material], 'column', [AdditionalText6];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Material], 'column', [AdditionalText7];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Material], 'column', [AdditionalNumber1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Material], 'column', [AdditionalNumber2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Material], 'column', [AdditionalNumber3];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu ilk veri versiyonu', 'schema', core, 'table', [Material], 'column', [VersionFrom];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş', 'schema', core, 'table', [Material], 'column', [VersionTo];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydı getiren yükleme partisi', 'schema', core, 'table', [Material], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'İş anahtarı (kod ya da kodların birleşimi)', 'schema', core, 'table', [Material], 'column', [BusinessKey];

GO

execute sp_addextendedproperty 'MS_Description', N'Son değişiklik zamanı', 'schema', core, 'table', [Material], 'column', [UpdatedAt];

GO

CREATE UNIQUE INDEX [UX_Material_Code] ON core.[Material] ([Code]) WHERE VersionTo IS NULL;

GO

CREATE TABLE core.[MaterialSupplier] (
    [Id] BIGINT NOT NULL, 
    [MaterialId] BIGINT NOT NULL, 
    [SupplierId] BIGINT NOT NULL, 
    [Priority] INTEGER NULL DEFAULT 1, 
    [QuotaPct] NUMERIC(6, 2) NULL, 
    [LeadTimeDays] NUMERIC(9, 2) NOT NULL, 
    [LeadTimeBasis] NVARCHAR(10) NULL DEFAULT N'Takvim günü', 
    [MinOrderQty] NUMERIC(18, 4) NULL, 
    [OrderMultiple] NUMERIC(18, 4) NULL, 
    [MaxOrderQty] NUMERIC(18, 4) NULL, 
    [ValidFrom] DATE NULL, 
    [ValidTo] DATE NULL, 
    [AdditionalText1] NVARCHAR(255) NULL, 
    [AdditionalText2] NVARCHAR(255) NULL, 
    [AdditionalText3] NVARCHAR(255) NULL, 
    [AdditionalNumber1] NUMERIC(18, 4) NULL, 
    [AdditionalNumber2] NUMERIC(18, 4) NULL, 
    [VersionFrom] INTEGER NOT NULL, 
    [VersionTo] INTEGER NULL, 
    [ImportBatchId] BIGINT NULL, 
    [BusinessKey] NVARCHAR(200) NOT NULL, 
    [UpdatedAt] DATETIME2 NOT NULL, 
    CONSTRAINT [PK_MaterialSupplier] PRIMARY KEY ([Id], [VersionFrom]), 
    CONSTRAINT [FK_MaterialSupplier_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Malzeme–tedarikçi ilişkisi; satın alma parametreleri. Satın alma her zaman sürekli; yuvarlama son hesapta.', 'schema', core, 'table', [MaterialSupplier];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', core, 'table', [MaterialSupplier], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Malzeme', 'schema', core, 'table', [MaterialSupplier], 'column', [MaterialId];

GO

execute sp_addextendedproperty 'MS_Description', N'Tedarikçi', 'schema', core, 'table', [MaterialSupplier], 'column', [SupplierId];

GO

execute sp_addextendedproperty 'MS_Description', N'Öncelik', 'schema', core, 'table', [MaterialSupplier], 'column', [Priority];

GO

execute sp_addextendedproperty 'MS_Description', N'Kota (%)', 'schema', core, 'table', [MaterialSupplier], 'column', [QuotaPct];

GO

execute sp_addextendedproperty 'MS_Description', N'Tedarik süresi', 'schema', core, 'table', [MaterialSupplier], 'column', [LeadTimeDays];

GO

execute sp_addextendedproperty 'MS_Description', N'Takvim günü | İş günü', 'schema', core, 'table', [MaterialSupplier], 'column', [LeadTimeBasis];

GO

execute sp_addextendedproperty 'MS_Description', N'Minimum sipariş miktarı', 'schema', core, 'table', [MaterialSupplier], 'column', [MinOrderQty];

GO

execute sp_addextendedproperty 'MS_Description', N'Kat', 'schema', core, 'table', [MaterialSupplier], 'column', [OrderMultiple];

GO

execute sp_addextendedproperty 'MS_Description', N'Maksimum', 'schema', core, 'table', [MaterialSupplier], 'column', [MaxOrderQty];

GO

execute sp_addextendedproperty 'MS_Description', N'Geçerlilik başlangıcı', 'schema', core, 'table', [MaterialSupplier], 'column', [ValidFrom];

GO

execute sp_addextendedproperty 'MS_Description', N'Geçerlilik bitişi', 'schema', core, 'table', [MaterialSupplier], 'column', [ValidTo];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [MaterialSupplier], 'column', [AdditionalText1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [MaterialSupplier], 'column', [AdditionalText2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [MaterialSupplier], 'column', [AdditionalText3];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [MaterialSupplier], 'column', [AdditionalNumber1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [MaterialSupplier], 'column', [AdditionalNumber2];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu ilk veri versiyonu', 'schema', core, 'table', [MaterialSupplier], 'column', [VersionFrom];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş', 'schema', core, 'table', [MaterialSupplier], 'column', [VersionTo];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydı getiren yükleme partisi', 'schema', core, 'table', [MaterialSupplier], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'İş anahtarı (kod ya da kodların birleşimi)', 'schema', core, 'table', [MaterialSupplier], 'column', [BusinessKey];

GO

execute sp_addextendedproperty 'MS_Description', N'Son değişiklik zamanı', 'schema', core, 'table', [MaterialSupplier], 'column', [UpdatedAt];

GO

CREATE INDEX [IX_MaterialSupplier_MaterialId] ON core.[MaterialSupplier] ([MaterialId]);

GO

CREATE INDEX [IX_MaterialSupplier_SupplierId] ON core.[MaterialSupplier] ([SupplierId]);

GO

CREATE TABLE core.[ProductionConfirmation] (
    [Id] BIGINT NOT NULL, 
    [WorkOrderId] BIGINT NOT NULL, 
    [OpNo] INTEGER NULL, 
    [SeqNo] INTEGER NULL, 
    [ResourceId] BIGINT NULL, 
    [ConfirmedQty] NUMERIC(18, 4) NOT NULL, 
    [ActualConsumption] NUMERIC(18, 6) NULL, 
    [StartAt] DATETIME2 NULL, 
    [EndAt] DATETIME2 NULL, 
    [AdditionalText1] NVARCHAR(255) NULL, 
    [AdditionalText2] NVARCHAR(255) NULL, 
    [AdditionalText3] NVARCHAR(255) NULL, 
    [AdditionalNumber1] NUMERIC(18, 4) NULL, 
    [AdditionalNumber2] NUMERIC(18, 4) NULL, 
    [VersionFrom] INTEGER NOT NULL, 
    [VersionTo] INTEGER NULL, 
    [ImportBatchId] BIGINT NULL, 
    [BusinessKey] NVARCHAR(200) NOT NULL, 
    [UpdatedAt] DATETIME2 NOT NULL, 
    CONSTRAINT [PK_ProductionConfirmation] PRIMARY KEY ([Id], [VersionFrom]), 
    CONSTRAINT [FK_ProductionConfirmation_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Üretim gerçekleşmeleri; ilk günden tutulur (verim önerisi ve ileriki fazlar).', 'schema', core, 'table', [ProductionConfirmation];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', core, 'table', [ProductionConfirmation], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'İş emri', 'schema', core, 'table', [ProductionConfirmation], 'column', [WorkOrderId];

GO

execute sp_addextendedproperty 'MS_Description', N'Operasyon no', 'schema', core, 'table', [ProductionConfirmation], 'column', [OpNo];

GO

execute sp_addextendedproperty 'MS_Description', N'Operasyon içindeki alt sıra', 'schema', core, 'table', [ProductionConfirmation], 'column', [SeqNo];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaynak', 'schema', core, 'table', [ProductionConfirmation], 'column', [ResourceId];

GO

execute sp_addextendedproperty 'MS_Description', N'Teyit miktarı', 'schema', core, 'table', [ProductionConfirmation], 'column', [ConfirmedQty];

GO

execute sp_addextendedproperty 'MS_Description', N'Gerçekleşen tüketim (süre)', 'schema', core, 'table', [ProductionConfirmation], 'column', [ActualConsumption];

GO

execute sp_addextendedproperty 'MS_Description', N'Başlangıç', 'schema', core, 'table', [ProductionConfirmation], 'column', [StartAt];

GO

execute sp_addextendedproperty 'MS_Description', N'Bitiş', 'schema', core, 'table', [ProductionConfirmation], 'column', [EndAt];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [ProductionConfirmation], 'column', [AdditionalText1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [ProductionConfirmation], 'column', [AdditionalText2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [ProductionConfirmation], 'column', [AdditionalText3];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [ProductionConfirmation], 'column', [AdditionalNumber1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [ProductionConfirmation], 'column', [AdditionalNumber2];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu ilk veri versiyonu', 'schema', core, 'table', [ProductionConfirmation], 'column', [VersionFrom];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş', 'schema', core, 'table', [ProductionConfirmation], 'column', [VersionTo];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydı getiren yükleme partisi', 'schema', core, 'table', [ProductionConfirmation], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'İş anahtarı (kod ya da kodların birleşimi)', 'schema', core, 'table', [ProductionConfirmation], 'column', [BusinessKey];

GO

execute sp_addextendedproperty 'MS_Description', N'Son değişiklik zamanı', 'schema', core, 'table', [ProductionConfirmation], 'column', [UpdatedAt];

GO

CREATE INDEX [IX_ProductionConfirmation_ResourceId] ON core.[ProductionConfirmation] ([ResourceId]);

GO

CREATE INDEX [IX_ProductionConfirmation_WorkOrderId] ON core.[ProductionConfirmation] ([WorkOrderId]);

GO

CREATE TABLE core.[ProductionVersion] (
    [Id] BIGINT NOT NULL, 
    [MaterialId] BIGINT NOT NULL, 
    [Code] NVARCHAR(30) NOT NULL, 
    [IsDefault] BIT NOT NULL DEFAULT 1, 
    [BaseQuantity] NUMERIC(18, 4) NULL DEFAULT 1, 
    [RouteCode] NVARCHAR(50) NOT NULL, 
    [ValidFrom] DATE NULL, 
    [ValidTo] DATE NULL, 
    [AdditionalText1] NVARCHAR(255) NULL, 
    [AdditionalText2] NVARCHAR(255) NULL, 
    [AdditionalText3] NVARCHAR(255) NULL, 
    [AdditionalNumber1] NUMERIC(18, 4) NULL, 
    [AdditionalNumber2] NUMERIC(18, 4) NULL, 
    [VersionFrom] INTEGER NOT NULL, 
    [VersionTo] INTEGER NULL, 
    [ImportBatchId] BIGINT NULL, 
    [BusinessKey] NVARCHAR(200) NOT NULL, 
    [UpdatedAt] DATETIME2 NOT NULL, 
    CONSTRAINT [PK_ProductionVersion] PRIMARY KEY ([Id], [VersionFrom]), 
    CONSTRAINT [FK_ProductionVersion_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Üretim versiyonu: bir malzemenin ürün ağacı ve rota başlığı; rotaya RouteCode ile bağlanır. Faz 1''de varsayılan versiyon kullanılır.', 'schema', core, 'table', [ProductionVersion];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', core, 'table', [ProductionVersion], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Üretilen malzeme', 'schema', core, 'table', [ProductionVersion], 'column', [MaterialId];

GO

execute sp_addextendedproperty 'MS_Description', N'Versiyon kodu', 'schema', core, 'table', [ProductionVersion], 'column', [Code];

GO

execute sp_addextendedproperty 'MS_Description', N'Varsayılan versiyon', 'schema', core, 'table', [ProductionVersion], 'column', [IsDefault];

GO

execute sp_addextendedproperty 'MS_Description', N'Baz miktar (rota ve ağaç bu miktar için)', 'schema', core, 'table', [ProductionVersion], 'column', [BaseQuantity];

GO

execute sp_addextendedproperty 'MS_Description', N'Rota kodu (Routing.RouteCode)', 'schema', core, 'table', [ProductionVersion], 'column', [RouteCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Geçerlilik başlangıcı', 'schema', core, 'table', [ProductionVersion], 'column', [ValidFrom];

GO

execute sp_addextendedproperty 'MS_Description', N'Geçerlilik bitişi', 'schema', core, 'table', [ProductionVersion], 'column', [ValidTo];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [ProductionVersion], 'column', [AdditionalText1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [ProductionVersion], 'column', [AdditionalText2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [ProductionVersion], 'column', [AdditionalText3];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [ProductionVersion], 'column', [AdditionalNumber1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [ProductionVersion], 'column', [AdditionalNumber2];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu ilk veri versiyonu', 'schema', core, 'table', [ProductionVersion], 'column', [VersionFrom];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş', 'schema', core, 'table', [ProductionVersion], 'column', [VersionTo];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydı getiren yükleme partisi', 'schema', core, 'table', [ProductionVersion], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'İş anahtarı (kod ya da kodların birleşimi)', 'schema', core, 'table', [ProductionVersion], 'column', [BusinessKey];

GO

execute sp_addextendedproperty 'MS_Description', N'Son değişiklik zamanı', 'schema', core, 'table', [ProductionVersion], 'column', [UpdatedAt];

GO

CREATE INDEX [IX_ProductionVersion_MaterialId] ON core.[ProductionVersion] ([MaterialId]);

GO

CREATE TABLE core.[Project] (
    [Id] BIGINT NOT NULL, 
    [Code] NVARCHAR(50) NOT NULL, 
    [Name] NVARCHAR(200) NULL, 
    [ProjectGroupId] BIGINT NULL, 
    [IsolationRule] NVARCHAR(20) NULL, 
    [Priority] INTEGER NULL, 
    [IsClosed] BIT NULL DEFAULT 0, 
    [AdditionalText1] NVARCHAR(255) NULL, 
    [AdditionalText2] NVARCHAR(255) NULL, 
    [AdditionalText3] NVARCHAR(255) NULL, 
    [AdditionalText4] NVARCHAR(255) NULL, 
    [AdditionalText5] NVARCHAR(255) NULL, 
    [AdditionalText6] NVARCHAR(255) NULL, 
    [AdditionalText7] NVARCHAR(255) NULL, 
    [AdditionalNumber1] NUMERIC(18, 4) NULL, 
    [AdditionalNumber2] NUMERIC(18, 4) NULL, 
    [AdditionalNumber3] NUMERIC(18, 4) NULL, 
    [VersionFrom] INTEGER NOT NULL, 
    [VersionTo] INTEGER NULL, 
    [ImportBatchId] BIGINT NULL, 
    [BusinessKey] NVARCHAR(200) NOT NULL, 
    [UpdatedAt] DATETIME2 NOT NULL, 
    CONSTRAINT [PK_Project] PRIMARY KEY ([Id], [VersionFrom]), 
    CONSTRAINT [FK_Project_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Proje.', 'schema', core, 'table', [Project];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', core, 'table', [Project], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Proje kodu', 'schema', core, 'table', [Project], 'column', [Code];

GO

execute sp_addextendedproperty 'MS_Description', N'Proje adı', 'schema', core, 'table', [Project], 'column', [Name];

GO

execute sp_addextendedproperty 'MS_Description', N'Proje grubu', 'schema', core, 'table', [Project], 'column', [ProjectGroupId];

GO

execute sp_addextendedproperty 'MS_Description', N'Proje bazında izolasyon (grubu ezer)', 'schema', core, 'table', [Project], 'column', [IsolationRule];

GO

execute sp_addextendedproperty 'MS_Description', N'Proje önceliği', 'schema', core, 'table', [Project], 'column', [Priority];

GO

execute sp_addextendedproperty 'MS_Description', N'Kapandı mı', 'schema', core, 'table', [Project], 'column', [IsClosed];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Project], 'column', [AdditionalText1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Project], 'column', [AdditionalText2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Project], 'column', [AdditionalText3];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Project], 'column', [AdditionalText4];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Project], 'column', [AdditionalText5];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Project], 'column', [AdditionalText6];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Project], 'column', [AdditionalText7];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Project], 'column', [AdditionalNumber1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Project], 'column', [AdditionalNumber2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Project], 'column', [AdditionalNumber3];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu ilk veri versiyonu', 'schema', core, 'table', [Project], 'column', [VersionFrom];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş', 'schema', core, 'table', [Project], 'column', [VersionTo];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydı getiren yükleme partisi', 'schema', core, 'table', [Project], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'İş anahtarı (kod ya da kodların birleşimi)', 'schema', core, 'table', [Project], 'column', [BusinessKey];

GO

execute sp_addextendedproperty 'MS_Description', N'Son değişiklik zamanı', 'schema', core, 'table', [Project], 'column', [UpdatedAt];

GO

CREATE INDEX [IX_Project_ProjectGroupId] ON core.[Project] ([ProjectGroupId]);

GO

CREATE UNIQUE INDEX [UX_Project_Code] ON core.[Project] ([Code]) WHERE VersionTo IS NULL;

GO

CREATE TABLE core.[ProjectGroup] (
    [Id] BIGINT NOT NULL, 
    [Code] NVARCHAR(50) NOT NULL, 
    [Name] NVARCHAR(200) NULL, 
    [IsolationRule] NVARCHAR(20) NULL DEFAULT N'Ortaktan beslenir', 
    [VersionFrom] INTEGER NOT NULL, 
    [VersionTo] INTEGER NULL, 
    [ImportBatchId] BIGINT NULL, 
    [BusinessKey] NVARCHAR(200) NOT NULL, 
    [UpdatedAt] DATETIME2 NOT NULL, 
    CONSTRAINT [PK_ProjectGroup] PRIMARY KEY ([Id], [VersionFrom]), 
    CONSTRAINT [FK_ProjectGroup_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Proje grubu (grup içi paylaşım için).', 'schema', core, 'table', [ProjectGroup];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', core, 'table', [ProjectGroup], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Grup kodu', 'schema', core, 'table', [ProjectGroup], 'column', [Code];

GO

execute sp_addextendedproperty 'MS_Description', N'Proje grubu adı', 'schema', core, 'table', [ProjectGroup], 'column', [Name];

GO

execute sp_addextendedproperty 'MS_Description', N'Tam izolasyon | Ortaktan beslenir | Grup içi paylaşım', 'schema', core, 'table', [ProjectGroup], 'column', [IsolationRule];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu ilk veri versiyonu', 'schema', core, 'table', [ProjectGroup], 'column', [VersionFrom];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş', 'schema', core, 'table', [ProjectGroup], 'column', [VersionTo];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydı getiren yükleme partisi', 'schema', core, 'table', [ProjectGroup], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'İş anahtarı (kod ya da kodların birleşimi)', 'schema', core, 'table', [ProjectGroup], 'column', [BusinessKey];

GO

execute sp_addextendedproperty 'MS_Description', N'Son değişiklik zamanı', 'schema', core, 'table', [ProjectGroup], 'column', [UpdatedAt];

GO

CREATE UNIQUE INDEX [UX_ProjectGroup_Code] ON core.[ProjectGroup] ([Code]) WHERE VersionTo IS NULL;

GO

CREATE TABLE core.[PurchaseOrderLine] (
    [Id] BIGINT NOT NULL, 
    [LocationId] INTEGER NOT NULL, 
    [OrderNo] NVARCHAR(30) NOT NULL, 
    [LineNo] INTEGER NOT NULL, 
    [OrderType] NVARCHAR(15) NOT NULL, 
    [SupplierId] BIGINT NULL, 
    [MaterialId] BIGINT NOT NULL, 
    [OpenQty] NUMERIC(18, 4) NOT NULL, 
    [RequestedDate] DATE NULL, 
    [ConfirmedDate] DATE NULL, 
    [ProjectId] BIGINT NULL, 
    [WorkOrderId] BIGINT NULL, 
    [Status] NVARCHAR(15) NOT NULL, 
    [AdditionalText1] NVARCHAR(255) NULL, 
    [AdditionalText2] NVARCHAR(255) NULL, 
    [AdditionalText3] NVARCHAR(255) NULL, 
    [AdditionalNumber1] NUMERIC(18, 4) NULL, 
    [AdditionalNumber2] NUMERIC(18, 4) NULL, 
    [VersionFrom] INTEGER NOT NULL, 
    [VersionTo] INTEGER NULL, 
    [ImportBatchId] BIGINT NULL, 
    [BusinessKey] NVARCHAR(200) NOT NULL, 
    [UpdatedAt] DATETIME2 NOT NULL, 
    CONSTRAINT [PK_PurchaseOrderLine] PRIMARY KEY ([Id], [VersionFrom]), 
    CONSTRAINT [FK_PurchaseOrderLine_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id]), 
    CONSTRAINT [FK_PurchaseOrderLine_LocationId] FOREIGN KEY([LocationId]) REFERENCES core.[Location] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Açık satın alma ve fason siparişi satırı (ve talep).', 'schema', core, 'table', [PurchaseOrderLine];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', core, 'table', [PurchaseOrderLine], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Lokasyon', 'schema', core, 'table', [PurchaseOrderLine], 'column', [LocationId];

GO

execute sp_addextendedproperty 'MS_Description', N'Sipariş no', 'schema', core, 'table', [PurchaseOrderLine], 'column', [OrderNo];

GO

execute sp_addextendedproperty 'MS_Description', N'Satır no', 'schema', core, 'table', [PurchaseOrderLine], 'column', [LineNo];

GO

execute sp_addextendedproperty 'MS_Description', N'Satın alma talebi | Satın alma | Fason', 'schema', core, 'table', [PurchaseOrderLine], 'column', [OrderType];

GO

execute sp_addextendedproperty 'MS_Description', N'Tedarikçi', 'schema', core, 'table', [PurchaseOrderLine], 'column', [SupplierId];

GO

execute sp_addextendedproperty 'MS_Description', N'Malzeme', 'schema', core, 'table', [PurchaseOrderLine], 'column', [MaterialId];

GO

execute sp_addextendedproperty 'MS_Description', N'Açık miktar', 'schema', core, 'table', [PurchaseOrderLine], 'column', [OpenQty];

GO

execute sp_addextendedproperty 'MS_Description', N'İstenen tarih', 'schema', core, 'table', [PurchaseOrderLine], 'column', [RequestedDate];

GO

execute sp_addextendedproperty 'MS_Description', N'Tedarikçi teyit tarihi', 'schema', core, 'table', [PurchaseOrderLine], 'column', [ConfirmedDate];

GO

execute sp_addextendedproperty 'MS_Description', N'Proje', 'schema', core, 'table', [PurchaseOrderLine], 'column', [ProjectId];

GO

execute sp_addextendedproperty 'MS_Description', N'Fasonda bağlı iş emri', 'schema', core, 'table', [PurchaseOrderLine], 'column', [WorkOrderId];

GO

execute sp_addextendedproperty 'MS_Description', N'Durum', 'schema', core, 'table', [PurchaseOrderLine], 'column', [Status];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [PurchaseOrderLine], 'column', [AdditionalText1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [PurchaseOrderLine], 'column', [AdditionalText2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [PurchaseOrderLine], 'column', [AdditionalText3];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [PurchaseOrderLine], 'column', [AdditionalNumber1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [PurchaseOrderLine], 'column', [AdditionalNumber2];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu ilk veri versiyonu', 'schema', core, 'table', [PurchaseOrderLine], 'column', [VersionFrom];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş', 'schema', core, 'table', [PurchaseOrderLine], 'column', [VersionTo];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydı getiren yükleme partisi', 'schema', core, 'table', [PurchaseOrderLine], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'İş anahtarı (kod ya da kodların birleşimi)', 'schema', core, 'table', [PurchaseOrderLine], 'column', [BusinessKey];

GO

execute sp_addextendedproperty 'MS_Description', N'Son değişiklik zamanı', 'schema', core, 'table', [PurchaseOrderLine], 'column', [UpdatedAt];

GO

CREATE INDEX [IX_PurchaseOrderLine_MaterialId] ON core.[PurchaseOrderLine] ([MaterialId]);

GO

CREATE INDEX [IX_PurchaseOrderLine_ProjectId] ON core.[PurchaseOrderLine] ([ProjectId]);

GO

CREATE INDEX [IX_PurchaseOrderLine_SupplierId] ON core.[PurchaseOrderLine] ([SupplierId]);

GO

CREATE INDEX [IX_PurchaseOrderLine_WorkOrderId] ON core.[PurchaseOrderLine] ([WorkOrderId]);

GO

CREATE UNIQUE INDEX [UX_PurchaseOrderLine_OrderNo_LineNo] ON core.[PurchaseOrderLine] ([OrderNo], [LineNo]) WHERE VersionTo IS NULL;

GO

CREATE TABLE core.[Resource] (
    [Id] BIGINT NOT NULL, 
    [LocationId] INTEGER NOT NULL, 
    [Code] NVARCHAR(50) NOT NULL, 
    [Name] NVARCHAR(150) NULL, 
    [ResourceGroupId] BIGINT NULL, 
    [ResourceType] NVARCHAR(20) NOT NULL DEFAULT N'Diğer', 
    [ResourceRole] NVARCHAR(10) NOT NULL DEFAULT N'Primary', 
    [IsConstrained] BIT NOT NULL DEFAULT 0, 
    [CapacityUnit] NVARCHAR(10) NOT NULL DEFAULT N'SAAT', 
    [DailyCapacity] NUMERIC(18, 4) NOT NULL, 
    [Quantity] INTEGER NOT NULL DEFAULT 1, 
    [CalendarId] INTEGER NOT NULL, 
    [CapacitySource] NVARCHAR(10) NULL DEFAULT N'Doğrudan', 
    [SubconPlanningType] NVARCHAR(15) NULL, 
    [SupplierId] BIGINT NULL, 
    [SubconFixedLeadTimeDays] NUMERIC(9, 2) NULL, 
    [SubconVariableDaysPerUnit] NUMERIC(18, 6) NULL, 
    [AdditionalText1] NVARCHAR(255) NULL, 
    [AdditionalText2] NVARCHAR(255) NULL, 
    [AdditionalText3] NVARCHAR(255) NULL, 
    [AdditionalText4] NVARCHAR(255) NULL, 
    [AdditionalText5] NVARCHAR(255) NULL, 
    [AdditionalText6] NVARCHAR(255) NULL, 
    [AdditionalText7] NVARCHAR(255) NULL, 
    [AdditionalNumber1] NUMERIC(18, 4) NULL, 
    [AdditionalNumber2] NUMERIC(18, 4) NULL, 
    [AdditionalNumber3] NUMERIC(18, 4) NULL, 
    [VersionFrom] INTEGER NOT NULL, 
    [VersionTo] INTEGER NULL, 
    [ImportBatchId] BIGINT NULL, 
    [BusinessKey] NVARCHAR(200) NOT NULL, 
    [UpdatedAt] DATETIME2 NOT NULL, 
    CONSTRAINT [PK_Resource] PRIMARY KEY ([Id], [VersionFrom]), 
    CONSTRAINT [FK_Resource_CapacityUnit] FOREIGN KEY([CapacityUnit]) REFERENCES core.[UnitOfMeasure] ([Code]), 
    CONSTRAINT [FK_Resource_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id]), 
    CONSTRAINT [FK_Resource_LocationId] FOREIGN KEY([LocationId]) REFERENCES core.[Location] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Kaynak: makine, işçi, fason, diğer. Kapasite kaynağın kendi biriminde günlük kapasite olarak tutulur.', 'schema', core, 'table', [Resource];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', core, 'table', [Resource], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Lokasyon', 'schema', core, 'table', [Resource], 'column', [LocationId];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaynak kodu', 'schema', core, 'table', [Resource], 'column', [Code];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaynak adı', 'schema', core, 'table', [Resource], 'column', [Name];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaynak grubu', 'schema', core, 'table', [Resource], 'column', [ResourceGroupId];

GO

execute sp_addextendedproperty 'MS_Description', N'Makine | İşçi | Fason | Kalıp | Fırın | Diğer', 'schema', core, 'table', [Resource], 'column', [ResourceType];

GO

execute sp_addextendedproperty 'MS_Description', N'Primary | Secondary', 'schema', core, 'table', [Resource], 'column', [ResourceRole];

GO

execute sp_addextendedproperty 'MS_Description', N'1: planda kısıt, 0: sonsuz kapasite (sadece raporlanır)', 'schema', core, 'table', [Resource], 'column', [IsConstrained];

GO

execute sp_addextendedproperty 'MS_Description', N'Kapasite birimi (Saat, Adet, Ton…); rotadaki tüketim aynı birimde kabul edilir', 'schema', core, 'table', [Resource], 'column', [CapacityUnit];

GO

execute sp_addextendedproperty 'MS_Description', N'Bir adet kaynağın bir çalışma günündeki kapasitesi', 'schema', core, 'table', [Resource], 'column', [DailyCapacity];

GO

execute sp_addextendedproperty 'MS_Description', N'Paralel kaynak adedi', 'schema', core, 'table', [Resource], 'column', [Quantity];

GO

execute sp_addextendedproperty 'MS_Description', N'Çalışma takvimi (Smartchain ekranında atanır)', 'schema', core, 'table', [Resource], 'column', [CalendarId];

GO

execute sp_addextendedproperty 'MS_Description', N'İşçi gruplarında: Vardiyadan | Doğrudan', 'schema', core, 'table', [Resource], 'column', [CapacitySource];

GO

execute sp_addextendedproperty 'MS_Description', N'Fasonda: İş yeri | Tedarik süresi', 'schema', core, 'table', [Resource], 'column', [SubconPlanningType];

GO

execute sp_addextendedproperty 'MS_Description', N'Fasonda fasoncu', 'schema', core, 'table', [Resource], 'column', [SupplierId];

GO

execute sp_addextendedproperty 'MS_Description', N'Fasonda sabit süre (taşıma ve kuyruk)', 'schema', core, 'table', [Resource], 'column', [SubconFixedLeadTimeDays];

GO

execute sp_addextendedproperty 'MS_Description', N'Fasonda birim başına gün (fasoncunun hızı)', 'schema', core, 'table', [Resource], 'column', [SubconVariableDaysPerUnit];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Resource], 'column', [AdditionalText1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Resource], 'column', [AdditionalText2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Resource], 'column', [AdditionalText3];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Resource], 'column', [AdditionalText4];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Resource], 'column', [AdditionalText5];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Resource], 'column', [AdditionalText6];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Resource], 'column', [AdditionalText7];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Resource], 'column', [AdditionalNumber1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Resource], 'column', [AdditionalNumber2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Resource], 'column', [AdditionalNumber3];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu ilk veri versiyonu', 'schema', core, 'table', [Resource], 'column', [VersionFrom];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş', 'schema', core, 'table', [Resource], 'column', [VersionTo];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydı getiren yükleme partisi', 'schema', core, 'table', [Resource], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'İş anahtarı (kod ya da kodların birleşimi)', 'schema', core, 'table', [Resource], 'column', [BusinessKey];

GO

execute sp_addextendedproperty 'MS_Description', N'Son değişiklik zamanı', 'schema', core, 'table', [Resource], 'column', [UpdatedAt];

GO

CREATE INDEX [IX_Resource_CalendarId] ON core.[Resource] ([CalendarId]);

GO

CREATE INDEX [IX_Resource_ResourceGroupId] ON core.[Resource] ([ResourceGroupId]);

GO

CREATE INDEX [IX_Resource_SupplierId] ON core.[Resource] ([SupplierId]);

GO

CREATE UNIQUE INDEX [UX_Resource_Code] ON core.[Resource] ([Code]) WHERE VersionTo IS NULL;

GO

CREATE TABLE core.[ResourceCapacityProfile] (
    [Id] BIGINT NOT NULL, 
    [ResourceId] BIGINT NOT NULL, 
    [ValidFrom] DATE NOT NULL, 
    [ValidTo] DATE NOT NULL, 
    [DailyCapacity] NUMERIC(18, 4) NOT NULL, 
    [VersionFrom] INTEGER NOT NULL, 
    [VersionTo] INTEGER NULL, 
    [ImportBatchId] BIGINT NULL, 
    [BusinessKey] NVARCHAR(200) NOT NULL, 
    [UpdatedAt] DATETIME2 NOT NULL, 
    CONSTRAINT [PK_ResourceCapacityProfile] PRIMARY KEY ([Id], [VersionFrom]), 
    CONSTRAINT [FK_ResourceCapacityProfile_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Günlük kapasitenin dönemsel değişikliği (ör. ikinci vardiya açıldı). Birim kaynağın CapacityUnit''i; ekranda gösterilir, ayrı saklanmaz. Smartchain''de ekrandan girilir; entegrasyondan gelmez (K-65).', 'schema', core, 'table', [ResourceCapacityProfile];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', core, 'table', [ResourceCapacityProfile], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaynak', 'schema', core, 'table', [ResourceCapacityProfile], 'column', [ResourceId];

GO

execute sp_addextendedproperty 'MS_Description', N'Başlangıç', 'schema', core, 'table', [ResourceCapacityProfile], 'column', [ValidFrom];

GO

execute sp_addextendedproperty 'MS_Description', N'Bitiş', 'schema', core, 'table', [ResourceCapacityProfile], 'column', [ValidTo];

GO

execute sp_addextendedproperty 'MS_Description', N'Bu aralıktaki günlük kapasite', 'schema', core, 'table', [ResourceCapacityProfile], 'column', [DailyCapacity];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu ilk veri versiyonu', 'schema', core, 'table', [ResourceCapacityProfile], 'column', [VersionFrom];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş', 'schema', core, 'table', [ResourceCapacityProfile], 'column', [VersionTo];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydı getiren yükleme partisi', 'schema', core, 'table', [ResourceCapacityProfile], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'İş anahtarı (kod ya da kodların birleşimi)', 'schema', core, 'table', [ResourceCapacityProfile], 'column', [BusinessKey];

GO

execute sp_addextendedproperty 'MS_Description', N'Son değişiklik zamanı', 'schema', core, 'table', [ResourceCapacityProfile], 'column', [UpdatedAt];

GO

CREATE INDEX [IX_ResourceCapacityProfile_ResourceId] ON core.[ResourceCapacityProfile] ([ResourceId]);

GO

CREATE TABLE core.[ResourceDowntime] (
    [Id] BIGINT NOT NULL, 
    [ResourceId] BIGINT NOT NULL, 
    [DowntimeType] NVARCHAR(10) NOT NULL, 
    [StartAt] DATETIME2 NOT NULL, 
    [EndAt] DATETIME2 NOT NULL, 
    [AffectedQuantity] INTEGER NOT NULL DEFAULT 1, 
    [DurationDays] NUMERIC(9, 4) NULL, 
    [Note] NVARCHAR(400) NULL, 
    [VersionFrom] INTEGER NOT NULL, 
    [VersionTo] INTEGER NULL, 
    [ImportBatchId] BIGINT NULL, 
    [BusinessKey] NVARCHAR(200) NOT NULL, 
    [UpdatedAt] DATETIME2 NOT NULL, 
    CONSTRAINT [PK_ResourceDowntime] PRIMARY KEY ([Id], [VersionFrom]), 
    CONSTRAINT [FK_ResourceDowntime_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Bakım ve arıza takvimi; kapasiteden düşülür. Çalışmada geçici değiştirilebilir. Smartchain''de ekrandan girilir; entegrasyondan gelmez (K-65).', 'schema', core, 'table', [ResourceDowntime];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', core, 'table', [ResourceDowntime], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaynak', 'schema', core, 'table', [ResourceDowntime], 'column', [ResourceId];

GO

execute sp_addextendedproperty 'MS_Description', N'Bakım | Arıza', 'schema', core, 'table', [ResourceDowntime], 'column', [DowntimeType];

GO

execute sp_addextendedproperty 'MS_Description', N'Başlangıç', 'schema', core, 'table', [ResourceDowntime], 'column', [StartAt];

GO

execute sp_addextendedproperty 'MS_Description', N'Bitiş', 'schema', core, 'table', [ResourceDowntime], 'column', [EndAt];

GO

execute sp_addextendedproperty 'MS_Description', N'Etkilenen kaynak adedi', 'schema', core, 'table', [ResourceDowntime], 'column', [AffectedQuantity];

GO

execute sp_addextendedproperty 'MS_Description', N'Süre, gün olarak (yarım gün 0,5)', 'schema', core, 'table', [ResourceDowntime], 'column', [DurationDays];

GO

execute sp_addextendedproperty 'MS_Description', N'Açıklama', 'schema', core, 'table', [ResourceDowntime], 'column', [Note];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu ilk veri versiyonu', 'schema', core, 'table', [ResourceDowntime], 'column', [VersionFrom];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş', 'schema', core, 'table', [ResourceDowntime], 'column', [VersionTo];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydı getiren yükleme partisi', 'schema', core, 'table', [ResourceDowntime], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'İş anahtarı (kod ya da kodların birleşimi)', 'schema', core, 'table', [ResourceDowntime], 'column', [BusinessKey];

GO

execute sp_addextendedproperty 'MS_Description', N'Son değişiklik zamanı', 'schema', core, 'table', [ResourceDowntime], 'column', [UpdatedAt];

GO

CREATE INDEX [IX_ResourceDowntime_ResourceId] ON core.[ResourceDowntime] ([ResourceId]);

GO

CREATE TABLE core.[ResourceGroup] (
    [Id] BIGINT NOT NULL, 
    [LocationId] INTEGER NOT NULL, 
    [Code] NVARCHAR(50) NOT NULL, 
    [Name] NVARCHAR(150) NULL, 
    [AdditionalText1] NVARCHAR(255) NULL, 
    [AdditionalText2] NVARCHAR(255) NULL, 
    [AdditionalText3] NVARCHAR(255) NULL, 
    [AdditionalText4] NVARCHAR(255) NULL, 
    [AdditionalText5] NVARCHAR(255) NULL, 
    [AdditionalText6] NVARCHAR(255) NULL, 
    [AdditionalText7] NVARCHAR(255) NULL, 
    [AdditionalNumber1] NUMERIC(18, 4) NULL, 
    [AdditionalNumber2] NUMERIC(18, 4) NULL, 
    [AdditionalNumber3] NUMERIC(18, 4) NULL, 
    [VersionFrom] INTEGER NOT NULL, 
    [VersionTo] INTEGER NULL, 
    [ImportBatchId] BIGINT NULL, 
    [BusinessKey] NVARCHAR(200) NOT NULL, 
    [UpdatedAt] DATETIME2 NOT NULL, 
    CONSTRAINT [PK_ResourceGroup] PRIMARY KEY ([Id], [VersionFrom]), 
    CONSTRAINT [FK_ResourceGroup_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id]), 
    CONSTRAINT [FK_ResourceGroup_LocationId] FOREIGN KEY([LocationId]) REFERENCES core.[Location] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Kaynak grubu (makine grubu, işçi kaynak grubu).', 'schema', core, 'table', [ResourceGroup];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', core, 'table', [ResourceGroup], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Lokasyon', 'schema', core, 'table', [ResourceGroup], 'column', [LocationId];

GO

execute sp_addextendedproperty 'MS_Description', N'Grup kodu', 'schema', core, 'table', [ResourceGroup], 'column', [Code];

GO

execute sp_addextendedproperty 'MS_Description', N'Grup adı', 'schema', core, 'table', [ResourceGroup], 'column', [Name];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [ResourceGroup], 'column', [AdditionalText1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [ResourceGroup], 'column', [AdditionalText2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [ResourceGroup], 'column', [AdditionalText3];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [ResourceGroup], 'column', [AdditionalText4];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [ResourceGroup], 'column', [AdditionalText5];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [ResourceGroup], 'column', [AdditionalText6];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [ResourceGroup], 'column', [AdditionalText7];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [ResourceGroup], 'column', [AdditionalNumber1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [ResourceGroup], 'column', [AdditionalNumber2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [ResourceGroup], 'column', [AdditionalNumber3];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu ilk veri versiyonu', 'schema', core, 'table', [ResourceGroup], 'column', [VersionFrom];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş', 'schema', core, 'table', [ResourceGroup], 'column', [VersionTo];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydı getiren yükleme partisi', 'schema', core, 'table', [ResourceGroup], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'İş anahtarı (kod ya da kodların birleşimi)', 'schema', core, 'table', [ResourceGroup], 'column', [BusinessKey];

GO

execute sp_addextendedproperty 'MS_Description', N'Son değişiklik zamanı', 'schema', core, 'table', [ResourceGroup], 'column', [UpdatedAt];

GO

CREATE UNIQUE INDEX [UX_ResourceGroup_Code] ON core.[ResourceGroup] ([Code]) WHERE VersionTo IS NULL;

GO

CREATE TABLE core.[Routing] (
    [Id] BIGINT NOT NULL, 
    [RouteCode] NVARCHAR(50) NOT NULL, 
    [OpNo] INTEGER NOT NULL, 
    [SeqNo] INTEGER NOT NULL, 
    [OperationName] NVARCHAR(150) NULL, 
    [ResourceId] BIGINT NOT NULL, 
    [ResourceRole] NVARCHAR(10) NOT NULL DEFAULT N'Primary', 
    [Consumption] NUMERIC(18, 6) NOT NULL, 
    [ResourceNumber] INTEGER NOT NULL DEFAULT 1, 
    [IsSubcontracted] BIT NULL DEFAULT 0, 
    [TransferLotQty] NUMERIC(18, 4) NULL, 
    [LaborType] NVARCHAR(15) NULL DEFAULT N'Yok', 
    [LaborRefId] BIGINT NULL, 
    [LaborBasis] NVARCHAR(10) NULL DEFAULT N'Ekip', 
    [CrewSize] INTEGER NULL DEFAULT 1, 
    [LaborTime] NUMERIC(18, 6) NULL, 
    [AdditionalText1] NVARCHAR(255) NULL, 
    [AdditionalText2] NVARCHAR(255) NULL, 
    [AdditionalText3] NVARCHAR(255) NULL, 
    [AdditionalNumber1] NUMERIC(18, 4) NULL, 
    [AdditionalNumber2] NUMERIC(18, 4) NULL, 
    [VersionFrom] INTEGER NOT NULL, 
    [VersionTo] INTEGER NULL, 
    [ImportBatchId] BIGINT NULL, 
    [BusinessKey] NVARCHAR(200) NOT NULL, 
    [UpdatedAt] DATETIME2 NOT NULL, 
    CONSTRAINT [PK_Routing] PRIMARY KEY ([Id], [VersionFrom]), 
    CONSTRAINT [FK_Routing_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Rota: her satır bir operasyon–kaynak ilişkisi; sıra önce OpNo, sonra SeqNo. Aynı operasyonun kaynakları ayrı satırda, ResourceRole ile.', 'schema', core, 'table', [Routing];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', core, 'table', [Routing], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Rota kodu', 'schema', core, 'table', [Routing], 'column', [RouteCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Operasyon no (birinci sıralama)', 'schema', core, 'table', [Routing], 'column', [OpNo];

GO

execute sp_addextendedproperty 'MS_Description', N'Operasyon içindeki alt sıra (ikinci sıralama)', 'schema', core, 'table', [Routing], 'column', [SeqNo];

GO

execute sp_addextendedproperty 'MS_Description', N'Operasyon adı', 'schema', core, 'table', [Routing], 'column', [OperationName];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaynak', 'schema', core, 'table', [Routing], 'column', [ResourceId];

GO

execute sp_addextendedproperty 'MS_Description', N'Primary | Secondary', 'schema', core, 'table', [Routing], 'column', [ResourceRole];

GO

execute sp_addextendedproperty 'MS_Description', N'Baz miktar için kaynak tüketimi (kaynağın kapasite biriminde)', 'schema', core, 'table', [Routing], 'column', [Consumption];

GO

execute sp_addextendedproperty 'MS_Description', N'Operasyonda aynı anda kullanılan kaynak adedi', 'schema', core, 'table', [Routing], 'column', [ResourceNumber];

GO

execute sp_addextendedproperty 'MS_Description', N'Fason operasyon', 'schema', core, 'table', [Routing], 'column', [IsSubcontracted];

GO

execute sp_addextendedproperty 'MS_Description', N'Transfer partisi', 'schema', core, 'table', [Routing], 'column', [TransferLotQty];

GO

execute sp_addextendedproperty 'MS_Description', N'İşçi: Yetkinlik grubu | Kaynak grubu | Yok', 'schema', core, 'table', [Routing], 'column', [LaborType];

GO

execute sp_addextendedproperty 'MS_Description', N'İlgili yetkinlik ya da kaynak grubu', 'schema', core, 'table', [Routing], 'column', [LaborRefId];

GO

execute sp_addextendedproperty 'MS_Description', N'Ekip (süre × kişi) | Toplam (adam-saat)', 'schema', core, 'table', [Routing], 'column', [LaborBasis];

GO

execute sp_addextendedproperty 'MS_Description', N'Gerekli işçi sayısı', 'schema', core, 'table', [Routing], 'column', [CrewSize];

GO

execute sp_addextendedproperty 'MS_Description', N'Toplam işçilik (adam-saat), LaborBasis = Toplam ise', 'schema', core, 'table', [Routing], 'column', [LaborTime];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Routing], 'column', [AdditionalText1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Routing], 'column', [AdditionalText2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Routing], 'column', [AdditionalText3];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Routing], 'column', [AdditionalNumber1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Routing], 'column', [AdditionalNumber2];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu ilk veri versiyonu', 'schema', core, 'table', [Routing], 'column', [VersionFrom];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş', 'schema', core, 'table', [Routing], 'column', [VersionTo];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydı getiren yükleme partisi', 'schema', core, 'table', [Routing], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'İş anahtarı (kod ya da kodların birleşimi)', 'schema', core, 'table', [Routing], 'column', [BusinessKey];

GO

execute sp_addextendedproperty 'MS_Description', N'Son değişiklik zamanı', 'schema', core, 'table', [Routing], 'column', [UpdatedAt];

GO

CREATE INDEX [IX_Routing_ResourceId] ON core.[Routing] ([ResourceId]);

GO

CREATE UNIQUE INDEX [UX_Routing_RouteCode_OpNo_SeqNo] ON core.[Routing] ([RouteCode], [OpNo], [SeqNo]) WHERE VersionTo IS NULL;

GO

CREATE TABLE core.[SalesOrderLine] (
    [Id] BIGINT NOT NULL, 
    [LocationId] INTEGER NOT NULL, 
    [OrderNo] NVARCHAR(30) NOT NULL, 
    [LineNo] INTEGER NOT NULL, 
    [LineItemNo] INTEGER NULL DEFAULT 0, 
    [Type] NVARCHAR(10) NOT NULL DEFAULT N'Kesin', 
    [CustomerId] BIGINT NOT NULL, 
    [MaterialId] BIGINT NOT NULL, 
    [ProjectId] BIGINT NULL, 
    [OpenQty] NUMERIC(18, 4) NOT NULL, 
    [RequestedDate] DATE NOT NULL, 
    [ConfirmedDate] DATE NULL, 
    [Priority] INTEGER NULL, 
    [AllowPartialDelivery] BIT NULL, 
    [Status] NVARCHAR(15) NOT NULL, 
    [AdditionalText1] NVARCHAR(255) NULL, 
    [AdditionalText2] NVARCHAR(255) NULL, 
    [AdditionalText3] NVARCHAR(255) NULL, 
    [AdditionalNumber1] NUMERIC(18, 4) NULL, 
    [AdditionalNumber2] NUMERIC(18, 4) NULL, 
    [VersionFrom] INTEGER NOT NULL, 
    [VersionTo] INTEGER NULL, 
    [ImportBatchId] BIGINT NULL, 
    [BusinessKey] NVARCHAR(200) NOT NULL, 
    [UpdatedAt] DATETIME2 NOT NULL, 
    CONSTRAINT [PK_SalesOrderLine] PRIMARY KEY ([Id], [VersionFrom]), 
    CONSTRAINT [FK_SalesOrderLine_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id]), 
    CONSTRAINT [FK_SalesOrderLine_LocationId] FOREIGN KEY([LocationId]) REFERENCES core.[Location] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Müşteri sipariş satırı; teklifler Type = Teklif ile gelir, plana dahil olmaları senaryo parametresi. Vade: teyit tarihi, yoksa istek tarihi.', 'schema', core, 'table', [SalesOrderLine];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', core, 'table', [SalesOrderLine], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Lokasyon', 'schema', core, 'table', [SalesOrderLine], 'column', [LocationId];

GO

execute sp_addextendedproperty 'MS_Description', N'Sipariş no', 'schema', core, 'table', [SalesOrderLine], 'column', [OrderNo];

GO

execute sp_addextendedproperty 'MS_Description', N'Satır no', 'schema', core, 'table', [SalesOrderLine], 'column', [LineNo];

GO

execute sp_addextendedproperty 'MS_Description', N'Alt satır no (ERP satırı kırılımlıysa)', 'schema', core, 'table', [SalesOrderLine], 'column', [LineItemNo];

GO

execute sp_addextendedproperty 'MS_Description', N'Kesin | Teklif', 'schema', core, 'table', [SalesOrderLine], 'column', [Type];

GO

execute sp_addextendedproperty 'MS_Description', N'Müşteri', 'schema', core, 'table', [SalesOrderLine], 'column', [CustomerId];

GO

execute sp_addextendedproperty 'MS_Description', N'Malzeme', 'schema', core, 'table', [SalesOrderLine], 'column', [MaterialId];

GO

execute sp_addextendedproperty 'MS_Description', N'Proje', 'schema', core, 'table', [SalesOrderLine], 'column', [ProjectId];

GO

execute sp_addextendedproperty 'MS_Description', N'Açık miktar', 'schema', core, 'table', [SalesOrderLine], 'column', [OpenQty];

GO

execute sp_addextendedproperty 'MS_Description', N'İstek tarihi', 'schema', core, 'table', [SalesOrderLine], 'column', [RequestedDate];

GO

execute sp_addextendedproperty 'MS_Description', N'Teyit tarihi', 'schema', core, 'table', [SalesOrderLine], 'column', [ConfirmedDate];

GO

execute sp_addextendedproperty 'MS_Description', N'Satır önceliği', 'schema', core, 'table', [SalesOrderLine], 'column', [Priority];

GO

execute sp_addextendedproperty 'MS_Description', N'Kısmi teslimat (müşteriyi ezer)', 'schema', core, 'table', [SalesOrderLine], 'column', [AllowPartialDelivery];

GO

execute sp_addextendedproperty 'MS_Description', N'Açık | Kapandı | İptal', 'schema', core, 'table', [SalesOrderLine], 'column', [Status];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [SalesOrderLine], 'column', [AdditionalText1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [SalesOrderLine], 'column', [AdditionalText2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [SalesOrderLine], 'column', [AdditionalText3];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [SalesOrderLine], 'column', [AdditionalNumber1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [SalesOrderLine], 'column', [AdditionalNumber2];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu ilk veri versiyonu', 'schema', core, 'table', [SalesOrderLine], 'column', [VersionFrom];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş', 'schema', core, 'table', [SalesOrderLine], 'column', [VersionTo];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydı getiren yükleme partisi', 'schema', core, 'table', [SalesOrderLine], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'İş anahtarı (kod ya da kodların birleşimi)', 'schema', core, 'table', [SalesOrderLine], 'column', [BusinessKey];

GO

execute sp_addextendedproperty 'MS_Description', N'Son değişiklik zamanı', 'schema', core, 'table', [SalesOrderLine], 'column', [UpdatedAt];

GO

CREATE INDEX [IX_SalesOrderLine_CustomerId] ON core.[SalesOrderLine] ([CustomerId]);

GO

CREATE INDEX [IX_SalesOrderLine_MaterialId] ON core.[SalesOrderLine] ([MaterialId]);

GO

CREATE INDEX [IX_SalesOrderLine_ProjectId] ON core.[SalesOrderLine] ([ProjectId]);

GO

CREATE UNIQUE INDEX [UX_SalesOrderLine_OrderNo_LineNo_LineItemNo] ON core.[SalesOrderLine] ([OrderNo], [LineNo], [LineItemNo]) WHERE VersionTo IS NULL;

GO

CREATE TABLE core.[Shift] (
    [Id] BIGINT NOT NULL, 
    [LocationId] INTEGER NOT NULL, 
    [Code] NVARCHAR(20) NOT NULL, 
    [StartTime] TIME NOT NULL, 
    [EndTime] TIME NOT NULL, 
    [BreakMinutes] INTEGER NULL DEFAULT 0, 
    [VersionFrom] INTEGER NOT NULL, 
    [VersionTo] INTEGER NULL, 
    [ImportBatchId] BIGINT NULL, 
    [BusinessKey] NVARCHAR(200) NOT NULL, 
    [UpdatedAt] DATETIME2 NOT NULL, 
    CONSTRAINT [PK_Shift] PRIMARY KEY ([Id], [VersionFrom]), 
    CONSTRAINT [FK_Shift_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id]), 
    CONSTRAINT [FK_Shift_LocationId] FOREIGN KEY([LocationId]) REFERENCES core.[Location] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Vardiya tanımı. Smartchain''de ekrandan girilir; entegrasyondan gelmez (K-65).', 'schema', core, 'table', [Shift];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', core, 'table', [Shift], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Lokasyon', 'schema', core, 'table', [Shift], 'column', [LocationId];

GO

execute sp_addextendedproperty 'MS_Description', N'Vardiya kodu', 'schema', core, 'table', [Shift], 'column', [Code];

GO

execute sp_addextendedproperty 'MS_Description', N'Başlangıç saati', 'schema', core, 'table', [Shift], 'column', [StartTime];

GO

execute sp_addextendedproperty 'MS_Description', N'Bitiş saati', 'schema', core, 'table', [Shift], 'column', [EndTime];

GO

execute sp_addextendedproperty 'MS_Description', N'Mola süresi (dk)', 'schema', core, 'table', [Shift], 'column', [BreakMinutes];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu ilk veri versiyonu', 'schema', core, 'table', [Shift], 'column', [VersionFrom];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş', 'schema', core, 'table', [Shift], 'column', [VersionTo];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydı getiren yükleme partisi', 'schema', core, 'table', [Shift], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'İş anahtarı (kod ya da kodların birleşimi)', 'schema', core, 'table', [Shift], 'column', [BusinessKey];

GO

execute sp_addextendedproperty 'MS_Description', N'Son değişiklik zamanı', 'schema', core, 'table', [Shift], 'column', [UpdatedAt];

GO

CREATE UNIQUE INDEX [UX_Shift_Code] ON core.[Shift] ([Code]) WHERE VersionTo IS NULL;

GO

CREATE TABLE core.[ShiftPlan] (
    [Id] BIGINT NOT NULL, 
    [CompetenceGroupId] BIGINT NULL, 
    [ResourceGroupId] BIGINT NULL, 
    [ShiftId] BIGINT NOT NULL, 
    [ValidFrom] DATE NOT NULL, 
    [ValidTo] DATE NOT NULL, 
    [Headcount] INTEGER NOT NULL, 
    [VersionFrom] INTEGER NOT NULL, 
    [VersionTo] INTEGER NULL, 
    [ImportBatchId] BIGINT NULL, 
    [BusinessKey] NVARCHAR(200) NOT NULL, 
    [UpdatedAt] DATETIME2 NOT NULL, 
    CONSTRAINT [PK_ShiftPlan] PRIMARY KEY ([Id], [VersionFrom]), 
    CONSTRAINT [FK_ShiftPlan_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Dönem bazında grup–vardiya–kişi sayısı. Çalışmada geçici değiştirilebilir. Smartchain''de ekrandan girilir; entegrasyondan gelmez (K-65).', 'schema', core, 'table', [ShiftPlan];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', core, 'table', [ShiftPlan], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Yetkinlik grubu (ya da)', 'schema', core, 'table', [ShiftPlan], 'column', [CompetenceGroupId];

GO

execute sp_addextendedproperty 'MS_Description', N'İşçi kaynak grubu', 'schema', core, 'table', [ShiftPlan], 'column', [ResourceGroupId];

GO

execute sp_addextendedproperty 'MS_Description', N'Vardiya', 'schema', core, 'table', [ShiftPlan], 'column', [ShiftId];

GO

execute sp_addextendedproperty 'MS_Description', N'Başlangıç', 'schema', core, 'table', [ShiftPlan], 'column', [ValidFrom];

GO

execute sp_addextendedproperty 'MS_Description', N'Bitiş', 'schema', core, 'table', [ShiftPlan], 'column', [ValidTo];

GO

execute sp_addextendedproperty 'MS_Description', N'Kişi sayısı', 'schema', core, 'table', [ShiftPlan], 'column', [Headcount];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu ilk veri versiyonu', 'schema', core, 'table', [ShiftPlan], 'column', [VersionFrom];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş', 'schema', core, 'table', [ShiftPlan], 'column', [VersionTo];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydı getiren yükleme partisi', 'schema', core, 'table', [ShiftPlan], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'İş anahtarı (kod ya da kodların birleşimi)', 'schema', core, 'table', [ShiftPlan], 'column', [BusinessKey];

GO

execute sp_addextendedproperty 'MS_Description', N'Son değişiklik zamanı', 'schema', core, 'table', [ShiftPlan], 'column', [UpdatedAt];

GO

CREATE INDEX [IX_ShiftPlan_CompetenceGroupId] ON core.[ShiftPlan] ([CompetenceGroupId]);

GO

CREATE INDEX [IX_ShiftPlan_ResourceGroupId] ON core.[ShiftPlan] ([ResourceGroupId]);

GO

CREATE INDEX [IX_ShiftPlan_ShiftId] ON core.[ShiftPlan] ([ShiftId]);

GO

CREATE TABLE core.[Stock] (
    [Id] BIGINT NOT NULL, 
    [LocationId] INTEGER NOT NULL, 
    [MaterialId] BIGINT NOT NULL, 
    [Warehouse] NVARCHAR(30) NULL, 
    [LotNo] NVARCHAR(50) NULL, 
    [StockStatus] NVARCHAR(15) NOT NULL DEFAULT N'Serbest', 
    [ProjectId] BIGINT NULL, 
    [Quantity] NUMERIC(18, 4) NOT NULL, 
    [QualityEntryDate] DATE NULL, 
    [ExpiryDate] DATE NULL, 
    [AdditionalText1] NVARCHAR(255) NULL, 
    [AdditionalText2] NVARCHAR(255) NULL, 
    [AdditionalText3] NVARCHAR(255) NULL, 
    [AdditionalNumber1] NUMERIC(18, 4) NULL, 
    [AdditionalNumber2] NUMERIC(18, 4) NULL, 
    [VersionFrom] INTEGER NOT NULL, 
    [VersionTo] INTEGER NULL, 
    [ImportBatchId] BIGINT NULL, 
    [BusinessKey] NVARCHAR(200) NOT NULL, 
    [UpdatedAt] DATETIME2 NOT NULL, 
    CONSTRAINT [PK_Stock] PRIMARY KEY ([Id], [VersionFrom]), 
    CONSTRAINT [FK_Stock_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id]), 
    CONSTRAINT [FK_Stock_LocationId] FOREIGN KEY([LocationId]) REFERENCES core.[Location] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Stok; lot ve durum bazında. Sahip: proje ya da ortak.', 'schema', core, 'table', [Stock];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', core, 'table', [Stock], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Lokasyon', 'schema', core, 'table', [Stock], 'column', [LocationId];

GO

execute sp_addextendedproperty 'MS_Description', N'Malzeme', 'schema', core, 'table', [Stock], 'column', [MaterialId];

GO

execute sp_addextendedproperty 'MS_Description', N'Depo', 'schema', core, 'table', [Stock], 'column', [Warehouse];

GO

execute sp_addextendedproperty 'MS_Description', N'Lot / seri', 'schema', core, 'table', [Stock], 'column', [LotNo];

GO

execute sp_addextendedproperty 'MS_Description', N'Serbest | Kalitede | Bloke', 'schema', core, 'table', [Stock], 'column', [StockStatus];

GO

execute sp_addextendedproperty 'MS_Description', N'Sahip proje (boşsa ortak)', 'schema', core, 'table', [Stock], 'column', [ProjectId];

GO

execute sp_addextendedproperty 'MS_Description', N'Miktar', 'schema', core, 'table', [Stock], 'column', [Quantity];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaliteye giriş tarihi', 'schema', core, 'table', [Stock], 'column', [QualityEntryDate];

GO

execute sp_addextendedproperty 'MS_Description', N'Son kullanma tarihi (raf ömrü sonraki faz)', 'schema', core, 'table', [Stock], 'column', [ExpiryDate];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Stock], 'column', [AdditionalText1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Stock], 'column', [AdditionalText2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Stock], 'column', [AdditionalText3];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Stock], 'column', [AdditionalNumber1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Stock], 'column', [AdditionalNumber2];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu ilk veri versiyonu', 'schema', core, 'table', [Stock], 'column', [VersionFrom];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş', 'schema', core, 'table', [Stock], 'column', [VersionTo];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydı getiren yükleme partisi', 'schema', core, 'table', [Stock], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'İş anahtarı (kod ya da kodların birleşimi)', 'schema', core, 'table', [Stock], 'column', [BusinessKey];

GO

execute sp_addextendedproperty 'MS_Description', N'Son değişiklik zamanı', 'schema', core, 'table', [Stock], 'column', [UpdatedAt];

GO

CREATE INDEX [IX_Stock_MaterialId] ON core.[Stock] ([MaterialId]);

GO

CREATE INDEX [IX_Stock_ProjectId] ON core.[Stock] ([ProjectId]);

GO

CREATE TABLE core.[Supplier] (
    [Id] BIGINT NOT NULL, 
    [Code] NVARCHAR(50) NOT NULL, 
    [Name] NVARCHAR(200) NULL, 
    [IsSubcontractor] BIT NULL DEFAULT 0, 
    [AdditionalText1] NVARCHAR(255) NULL, 
    [AdditionalText2] NVARCHAR(255) NULL, 
    [AdditionalText3] NVARCHAR(255) NULL, 
    [AdditionalText4] NVARCHAR(255) NULL, 
    [AdditionalText5] NVARCHAR(255) NULL, 
    [AdditionalText6] NVARCHAR(255) NULL, 
    [AdditionalText7] NVARCHAR(255) NULL, 
    [AdditionalNumber1] NUMERIC(18, 4) NULL, 
    [AdditionalNumber2] NUMERIC(18, 4) NULL, 
    [AdditionalNumber3] NUMERIC(18, 4) NULL, 
    [VersionFrom] INTEGER NOT NULL, 
    [VersionTo] INTEGER NULL, 
    [ImportBatchId] BIGINT NULL, 
    [BusinessKey] NVARCHAR(200) NOT NULL, 
    [UpdatedAt] DATETIME2 NOT NULL, 
    CONSTRAINT [PK_Supplier] PRIMARY KEY ([Id], [VersionFrom]), 
    CONSTRAINT [FK_Supplier_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Tedarikçi ve fasoncu.', 'schema', core, 'table', [Supplier];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', core, 'table', [Supplier], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Tedarikçi kodu', 'schema', core, 'table', [Supplier], 'column', [Code];

GO

execute sp_addextendedproperty 'MS_Description', N'Ad', 'schema', core, 'table', [Supplier], 'column', [Name];

GO

execute sp_addextendedproperty 'MS_Description', N'Fasoncu mu', 'schema', core, 'table', [Supplier], 'column', [IsSubcontractor];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Supplier], 'column', [AdditionalText1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Supplier], 'column', [AdditionalText2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Supplier], 'column', [AdditionalText3];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Supplier], 'column', [AdditionalText4];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Supplier], 'column', [AdditionalText5];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Supplier], 'column', [AdditionalText6];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Supplier], 'column', [AdditionalText7];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Supplier], 'column', [AdditionalNumber1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Supplier], 'column', [AdditionalNumber2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Supplier], 'column', [AdditionalNumber3];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu ilk veri versiyonu', 'schema', core, 'table', [Supplier], 'column', [VersionFrom];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş', 'schema', core, 'table', [Supplier], 'column', [VersionTo];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydı getiren yükleme partisi', 'schema', core, 'table', [Supplier], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'İş anahtarı (kod ya da kodların birleşimi)', 'schema', core, 'table', [Supplier], 'column', [BusinessKey];

GO

execute sp_addextendedproperty 'MS_Description', N'Son değişiklik zamanı', 'schema', core, 'table', [Supplier], 'column', [UpdatedAt];

GO

CREATE UNIQUE INDEX [UX_Supplier_Code] ON core.[Supplier] ([Code]) WHERE VersionTo IS NULL;

GO

CREATE TABLE core.[TransferOrder] (
    [Id] BIGINT NOT NULL, 
    [OrderNo] NVARCHAR(30) NOT NULL, 
    [FromLocationId] INTEGER NOT NULL, 
    [ToLocationId] INTEGER NOT NULL, 
    [MaterialId] BIGINT NOT NULL, 
    [OpenQty] NUMERIC(18, 4) NOT NULL, 
    [ShipDate] DATE NULL, 
    [ReceiptDate] DATE NULL, 
    [AdditionalText1] NVARCHAR(255) NULL, 
    [AdditionalText2] NVARCHAR(255) NULL, 
    [AdditionalText3] NVARCHAR(255) NULL, 
    [AdditionalNumber1] NUMERIC(18, 4) NULL, 
    [AdditionalNumber2] NUMERIC(18, 4) NULL, 
    [VersionFrom] INTEGER NOT NULL, 
    [VersionTo] INTEGER NULL, 
    [ImportBatchId] BIGINT NULL, 
    [BusinessKey] NVARCHAR(200) NOT NULL, 
    [UpdatedAt] DATETIME2 NOT NULL, 
    CONSTRAINT [PK_TransferOrder] PRIMARY KEY ([Id], [VersionFrom]), 
    CONSTRAINT [FK_TransferOrder_FromLocationId] FOREIGN KEY([FromLocationId]) REFERENCES core.[Location] ([Id]), 
    CONSTRAINT [FK_TransferOrder_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id]), 
    CONSTRAINT [FK_TransferOrder_ToLocationId] FOREIGN KEY([ToLocationId]) REFERENCES core.[Location] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Açık lokasyonlar arası transfer; Faz 1''de sabit hareket (gelen arz, giden talep).', 'schema', core, 'table', [TransferOrder];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', core, 'table', [TransferOrder], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Transfer no', 'schema', core, 'table', [TransferOrder], 'column', [OrderNo];

GO

execute sp_addextendedproperty 'MS_Description', N'Çıkış lokasyonu', 'schema', core, 'table', [TransferOrder], 'column', [FromLocationId];

GO

execute sp_addextendedproperty 'MS_Description', N'Varış lokasyonu', 'schema', core, 'table', [TransferOrder], 'column', [ToLocationId];

GO

execute sp_addextendedproperty 'MS_Description', N'Malzeme', 'schema', core, 'table', [TransferOrder], 'column', [MaterialId];

GO

execute sp_addextendedproperty 'MS_Description', N'Açık miktar', 'schema', core, 'table', [TransferOrder], 'column', [OpenQty];

GO

execute sp_addextendedproperty 'MS_Description', N'Çıkış tarihi', 'schema', core, 'table', [TransferOrder], 'column', [ShipDate];

GO

execute sp_addextendedproperty 'MS_Description', N'Varış tarihi', 'schema', core, 'table', [TransferOrder], 'column', [ReceiptDate];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [TransferOrder], 'column', [AdditionalText1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [TransferOrder], 'column', [AdditionalText2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [TransferOrder], 'column', [AdditionalText3];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [TransferOrder], 'column', [AdditionalNumber1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [TransferOrder], 'column', [AdditionalNumber2];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu ilk veri versiyonu', 'schema', core, 'table', [TransferOrder], 'column', [VersionFrom];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş', 'schema', core, 'table', [TransferOrder], 'column', [VersionTo];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydı getiren yükleme partisi', 'schema', core, 'table', [TransferOrder], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'İş anahtarı (kod ya da kodların birleşimi)', 'schema', core, 'table', [TransferOrder], 'column', [BusinessKey];

GO

execute sp_addextendedproperty 'MS_Description', N'Son değişiklik zamanı', 'schema', core, 'table', [TransferOrder], 'column', [UpdatedAt];

GO

CREATE INDEX [IX_TransferOrder_MaterialId] ON core.[TransferOrder] ([MaterialId]);

GO

CREATE UNIQUE INDEX [UX_TransferOrder_OrderNo] ON core.[TransferOrder] ([OrderNo]) WHERE VersionTo IS NULL;

GO

CREATE TABLE core.[UomConversion] (
    [Id] BIGINT NOT NULL, 
    [MaterialId] BIGINT NULL, 
    [FromUom] NVARCHAR(10) NOT NULL, 
    [ToUom] NVARCHAR(10) NOT NULL, 
    [Factor] NUMERIC(18, 6) NOT NULL, 
    [VersionFrom] INTEGER NOT NULL, 
    [VersionTo] INTEGER NULL, 
    [ImportBatchId] BIGINT NULL, 
    [BusinessKey] NVARCHAR(200) NOT NULL, 
    [UpdatedAt] DATETIME2 NOT NULL, 
    CONSTRAINT [PK_UomConversion] PRIMARY KEY ([Id], [VersionFrom]), 
    CONSTRAINT [FK_UomConversion_FromUom] FOREIGN KEY([FromUom]) REFERENCES core.[UnitOfMeasure] ([Code]), 
    CONSTRAINT [FK_UomConversion_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id]), 
    CONSTRAINT [FK_UomConversion_ToUom] FOREIGN KEY([ToUom]) REFERENCES core.[UnitOfMeasure] ([Code])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Malzeme bazında birim dönüşümü.', 'schema', core, 'table', [UomConversion];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', core, 'table', [UomConversion], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Malzeme (boşsa genel dönüşüm)', 'schema', core, 'table', [UomConversion], 'column', [MaterialId];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaynak birim', 'schema', core, 'table', [UomConversion], 'column', [FromUom];

GO

execute sp_addextendedproperty 'MS_Description', N'Hedef birim', 'schema', core, 'table', [UomConversion], 'column', [ToUom];

GO

execute sp_addextendedproperty 'MS_Description', N'Çarpan', 'schema', core, 'table', [UomConversion], 'column', [Factor];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu ilk veri versiyonu', 'schema', core, 'table', [UomConversion], 'column', [VersionFrom];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş', 'schema', core, 'table', [UomConversion], 'column', [VersionTo];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydı getiren yükleme partisi', 'schema', core, 'table', [UomConversion], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'İş anahtarı (kod ya da kodların birleşimi)', 'schema', core, 'table', [UomConversion], 'column', [BusinessKey];

GO

execute sp_addextendedproperty 'MS_Description', N'Son değişiklik zamanı', 'schema', core, 'table', [UomConversion], 'column', [UpdatedAt];

GO

CREATE INDEX [IX_UomConversion_MaterialId] ON core.[UomConversion] ([MaterialId]);

GO

CREATE TABLE core.[WorkOrder] (
    [Id] BIGINT NOT NULL, 
    [LocationId] INTEGER NOT NULL, 
    [OrderNo] NVARCHAR(30) NOT NULL, 
    [MaterialId] BIGINT NOT NULL, 
    [OrderType] NVARCHAR(15) NOT NULL DEFAULT N'Üretim', 
    [Status] NVARCHAR(15) NOT NULL, 
    [OrderQty] NUMERIC(18, 4) NOT NULL, 
    [OpenQty] NUMERIC(18, 4) NOT NULL, 
    [StartDate] DATE NULL, 
    [DueDate] DATE NOT NULL, 
    [ProjectId] BIGINT NULL, 
    [SalesOrderLineId] BIGINT NULL, 
    [ParentWorkOrderId] BIGINT NULL, 
    [LastActivityDate] DATE NULL, 
    [AdditionalText1] NVARCHAR(255) NULL, 
    [AdditionalText2] NVARCHAR(255) NULL, 
    [AdditionalText3] NVARCHAR(255) NULL, 
    [AdditionalNumber1] NUMERIC(18, 4) NULL, 
    [AdditionalNumber2] NUMERIC(18, 4) NULL, 
    [VersionFrom] INTEGER NOT NULL, 
    [VersionTo] INTEGER NULL, 
    [ImportBatchId] BIGINT NULL, 
    [BusinessKey] NVARCHAR(200) NOT NULL, 
    [UpdatedAt] DATETIME2 NOT NULL, 
    CONSTRAINT [PK_WorkOrder] PRIMARY KEY ([Id], [VersionFrom]), 
    CONSTRAINT [FK_WorkOrder_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id]), 
    CONSTRAINT [FK_WorkOrder_LocationId] FOREIGN KEY([LocationId]) REFERENCES core.[Location] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Açık iş emri (üretim, fason, yeniden işleme).', 'schema', core, 'table', [WorkOrder];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', core, 'table', [WorkOrder], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Lokasyon', 'schema', core, 'table', [WorkOrder], 'column', [LocationId];

GO

execute sp_addextendedproperty 'MS_Description', N'İş emri no', 'schema', core, 'table', [WorkOrder], 'column', [OrderNo];

GO

execute sp_addextendedproperty 'MS_Description', N'Üretilen malzeme', 'schema', core, 'table', [WorkOrder], 'column', [MaterialId];

GO

execute sp_addextendedproperty 'MS_Description', N'Üretim | Fason | Yeniden işleme', 'schema', core, 'table', [WorkOrder], 'column', [OrderType];

GO

execute sp_addextendedproperty 'MS_Description', N'Planlı | Yayınlandı | Başladı | Kısmi | Bitti', 'schema', core, 'table', [WorkOrder], 'column', [Status];

GO

execute sp_addextendedproperty 'MS_Description', N'İş emri miktarı', 'schema', core, 'table', [WorkOrder], 'column', [OrderQty];

GO

execute sp_addextendedproperty 'MS_Description', N'Açık miktar', 'schema', core, 'table', [WorkOrder], 'column', [OpenQty];

GO

execute sp_addextendedproperty 'MS_Description', N'Başlangıç', 'schema', core, 'table', [WorkOrder], 'column', [StartDate];

GO

execute sp_addextendedproperty 'MS_Description', N'Bitiş', 'schema', core, 'table', [WorkOrder], 'column', [DueDate];

GO

execute sp_addextendedproperty 'MS_Description', N'Proje (ayraç)', 'schema', core, 'table', [WorkOrder], 'column', [ProjectId];

GO

execute sp_addextendedproperty 'MS_Description', N'Bağlı sipariş satırı (ayraç)', 'schema', core, 'table', [WorkOrder], 'column', [SalesOrderLineId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yeniden işlemede orijinal iş emri', 'schema', core, 'table', [WorkOrder], 'column', [ParentWorkOrderId];

GO

execute sp_addextendedproperty 'MS_Description', N'Son hareket tarihi (eskime kontrolü)', 'schema', core, 'table', [WorkOrder], 'column', [LastActivityDate];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [WorkOrder], 'column', [AdditionalText1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [WorkOrder], 'column', [AdditionalText2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [WorkOrder], 'column', [AdditionalText3];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [WorkOrder], 'column', [AdditionalNumber1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [WorkOrder], 'column', [AdditionalNumber2];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu ilk veri versiyonu', 'schema', core, 'table', [WorkOrder], 'column', [VersionFrom];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş', 'schema', core, 'table', [WorkOrder], 'column', [VersionTo];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydı getiren yükleme partisi', 'schema', core, 'table', [WorkOrder], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'İş anahtarı (kod ya da kodların birleşimi)', 'schema', core, 'table', [WorkOrder], 'column', [BusinessKey];

GO

execute sp_addextendedproperty 'MS_Description', N'Son değişiklik zamanı', 'schema', core, 'table', [WorkOrder], 'column', [UpdatedAt];

GO

CREATE INDEX [IX_WorkOrder_MaterialId] ON core.[WorkOrder] ([MaterialId]);

GO

CREATE INDEX [IX_WorkOrder_ParentWorkOrderId] ON core.[WorkOrder] ([ParentWorkOrderId]);

GO

CREATE INDEX [IX_WorkOrder_ProjectId] ON core.[WorkOrder] ([ProjectId]);

GO

CREATE INDEX [IX_WorkOrder_SalesOrderLineId] ON core.[WorkOrder] ([SalesOrderLineId]);

GO

CREATE UNIQUE INDEX [UX_WorkOrder_OrderNo] ON core.[WorkOrder] ([OrderNo]) WHERE VersionTo IS NULL;

GO

CREATE TABLE core.[WorkOrderComponent] (
    [Id] BIGINT NOT NULL, 
    [WorkOrderId] BIGINT NOT NULL, 
    [MaterialId] BIGINT NOT NULL, 
    [RequiredQty] NUMERIC(18, 4) NOT NULL, 
    [IssuedQty] NUMERIC(18, 4) NULL DEFAULT 0, 
    [RemainingQty] NUMERIC(18, 4) NULL, 
    [AdditionalText1] NVARCHAR(255) NULL, 
    [AdditionalText2] NVARCHAR(255) NULL, 
    [AdditionalText3] NVARCHAR(255) NULL, 
    [AdditionalNumber1] NUMERIC(18, 4) NULL, 
    [AdditionalNumber2] NUMERIC(18, 4) NULL, 
    [VersionFrom] INTEGER NOT NULL, 
    [VersionTo] INTEGER NULL, 
    [ImportBatchId] BIGINT NULL, 
    [BusinessKey] NVARCHAR(200) NOT NULL, 
    [UpdatedAt] DATETIME2 NOT NULL, 
    CONSTRAINT [PK_WorkOrderComponent] PRIMARY KEY ([Id], [VersionFrom]), 
    CONSTRAINT [FK_WorkOrderComponent_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'İş emrinin bileşenleri ve çekilen miktar.', 'schema', core, 'table', [WorkOrderComponent];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', core, 'table', [WorkOrderComponent], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'İş emri', 'schema', core, 'table', [WorkOrderComponent], 'column', [WorkOrderId];

GO

execute sp_addextendedproperty 'MS_Description', N'Bileşen', 'schema', core, 'table', [WorkOrderComponent], 'column', [MaterialId];

GO

execute sp_addextendedproperty 'MS_Description', N'Gereken miktar', 'schema', core, 'table', [WorkOrderComponent], 'column', [RequiredQty];

GO

execute sp_addextendedproperty 'MS_Description', N'Çekilen miktar', 'schema', core, 'table', [WorkOrderComponent], 'column', [IssuedQty];

GO

execute sp_addextendedproperty 'MS_Description', N'Kalan ihtiyaç', 'schema', core, 'table', [WorkOrderComponent], 'column', [RemainingQty];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [WorkOrderComponent], 'column', [AdditionalText1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [WorkOrderComponent], 'column', [AdditionalText2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [WorkOrderComponent], 'column', [AdditionalText3];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [WorkOrderComponent], 'column', [AdditionalNumber1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [WorkOrderComponent], 'column', [AdditionalNumber2];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu ilk veri versiyonu', 'schema', core, 'table', [WorkOrderComponent], 'column', [VersionFrom];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş', 'schema', core, 'table', [WorkOrderComponent], 'column', [VersionTo];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydı getiren yükleme partisi', 'schema', core, 'table', [WorkOrderComponent], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'İş anahtarı (kod ya da kodların birleşimi)', 'schema', core, 'table', [WorkOrderComponent], 'column', [BusinessKey];

GO

execute sp_addextendedproperty 'MS_Description', N'Son değişiklik zamanı', 'schema', core, 'table', [WorkOrderComponent], 'column', [UpdatedAt];

GO

CREATE INDEX [IX_WorkOrderComponent_MaterialId] ON core.[WorkOrderComponent] ([MaterialId]);

GO

CREATE INDEX [IX_WorkOrderComponent_WorkOrderId] ON core.[WorkOrderComponent] ([WorkOrderId]);

GO

CREATE TABLE core.[WorkOrderOperation] (
    [Id] BIGINT NOT NULL, 
    [WorkOrderId] BIGINT NOT NULL, 
    [OpNo] INTEGER NOT NULL, 
    [SeqNo] INTEGER NOT NULL, 
    [ResourceId] BIGINT NOT NULL, 
    [PlannedConsumption] NUMERIC(18, 6) NULL, 
    [ConfirmedConsumption] NUMERIC(18, 6) NULL DEFAULT 0, 
    [RemainingConsumption] NUMERIC(18, 6) NULL, 
    [Status] NVARCHAR(15) NULL, 
    [AdditionalText1] NVARCHAR(255) NULL, 
    [AdditionalText2] NVARCHAR(255) NULL, 
    [AdditionalText3] NVARCHAR(255) NULL, 
    [AdditionalNumber1] NUMERIC(18, 4) NULL, 
    [AdditionalNumber2] NUMERIC(18, 4) NULL, 
    [VersionFrom] INTEGER NOT NULL, 
    [VersionTo] INTEGER NULL, 
    [ImportBatchId] BIGINT NULL, 
    [BusinessKey] NVARCHAR(200) NOT NULL, 
    [UpdatedAt] DATETIME2 NOT NULL, 
    CONSTRAINT [PK_WorkOrderOperation] PRIMARY KEY ([Id], [VersionFrom]), 
    CONSTRAINT [FK_WorkOrderOperation_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'İş emrinin operasyonları ve kalan iş.', 'schema', core, 'table', [WorkOrderOperation];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', core, 'table', [WorkOrderOperation], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'İş emri', 'schema', core, 'table', [WorkOrderOperation], 'column', [WorkOrderId];

GO

execute sp_addextendedproperty 'MS_Description', N'Operasyon no', 'schema', core, 'table', [WorkOrderOperation], 'column', [OpNo];

GO

execute sp_addextendedproperty 'MS_Description', N'Operasyon içindeki alt sıra', 'schema', core, 'table', [WorkOrderOperation], 'column', [SeqNo];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaynak', 'schema', core, 'table', [WorkOrderOperation], 'column', [ResourceId];

GO

execute sp_addextendedproperty 'MS_Description', N'Planlanan tüketim', 'schema', core, 'table', [WorkOrderOperation], 'column', [PlannedConsumption];

GO

execute sp_addextendedproperty 'MS_Description', N'Teyit edilen tüketim', 'schema', core, 'table', [WorkOrderOperation], 'column', [ConfirmedConsumption];

GO

execute sp_addextendedproperty 'MS_Description', N'Kalan yük', 'schema', core, 'table', [WorkOrderOperation], 'column', [RemainingConsumption];

GO

execute sp_addextendedproperty 'MS_Description', N'Açık | Bitti', 'schema', core, 'table', [WorkOrderOperation], 'column', [Status];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [WorkOrderOperation], 'column', [AdditionalText1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [WorkOrderOperation], 'column', [AdditionalText2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [WorkOrderOperation], 'column', [AdditionalText3];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [WorkOrderOperation], 'column', [AdditionalNumber1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [WorkOrderOperation], 'column', [AdditionalNumber2];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu ilk veri versiyonu', 'schema', core, 'table', [WorkOrderOperation], 'column', [VersionFrom];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş', 'schema', core, 'table', [WorkOrderOperation], 'column', [VersionTo];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydı getiren yükleme partisi', 'schema', core, 'table', [WorkOrderOperation], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'İş anahtarı (kod ya da kodların birleşimi)', 'schema', core, 'table', [WorkOrderOperation], 'column', [BusinessKey];

GO

execute sp_addextendedproperty 'MS_Description', N'Son değişiklik zamanı', 'schema', core, 'table', [WorkOrderOperation], 'column', [UpdatedAt];

GO

CREATE INDEX [IX_WorkOrderOperation_ResourceId] ON core.[WorkOrderOperation] ([ResourceId]);

GO

CREATE INDEX [IX_WorkOrderOperation_WorkOrderId] ON core.[WorkOrderOperation] ([WorkOrderId]);

GO

CREATE TABLE core.[Worker] (
    [Id] BIGINT NOT NULL, 
    [LocationId] INTEGER NOT NULL, 
    [Code] NVARCHAR(50) NOT NULL, 
    [Name] NVARCHAR(150) NULL, 
    [ResourceGroupId] BIGINT NULL, 
    [IsActive] BIT NULL DEFAULT 1, 
    [AdditionalText1] NVARCHAR(255) NULL, 
    [AdditionalText2] NVARCHAR(255) NULL, 
    [AdditionalText3] NVARCHAR(255) NULL, 
    [AdditionalText4] NVARCHAR(255) NULL, 
    [AdditionalText5] NVARCHAR(255) NULL, 
    [AdditionalText6] NVARCHAR(255) NULL, 
    [AdditionalText7] NVARCHAR(255) NULL, 
    [AdditionalNumber1] NUMERIC(18, 4) NULL, 
    [AdditionalNumber2] NUMERIC(18, 4) NULL, 
    [AdditionalNumber3] NUMERIC(18, 4) NULL, 
    [VersionFrom] INTEGER NOT NULL, 
    [VersionTo] INTEGER NULL, 
    [ImportBatchId] BIGINT NULL, 
    [BusinessKey] NVARCHAR(200) NOT NULL, 
    [UpdatedAt] DATETIME2 NOT NULL, 
    CONSTRAINT [PK_Worker] PRIMARY KEY ([Id], [VersionFrom]), 
    CONSTRAINT [FK_Worker_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id]), 
    CONSTRAINT [FK_Worker_LocationId] FOREIGN KEY([LocationId]) REFERENCES core.[Location] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'İşçi.', 'schema', core, 'table', [Worker];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', core, 'table', [Worker], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Lokasyon', 'schema', core, 'table', [Worker], 'column', [LocationId];

GO

execute sp_addextendedproperty 'MS_Description', N'Sicil no', 'schema', core, 'table', [Worker], 'column', [Code];

GO

execute sp_addextendedproperty 'MS_Description', N'Ad', 'schema', core, 'table', [Worker], 'column', [Name];

GO

execute sp_addextendedproperty 'MS_Description', N'Bağlı olduğu işçi kaynak grubu', 'schema', core, 'table', [Worker], 'column', [ResourceGroupId];

GO

execute sp_addextendedproperty 'MS_Description', N'Aktif mi', 'schema', core, 'table', [Worker], 'column', [IsActive];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Worker], 'column', [AdditionalText1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Worker], 'column', [AdditionalText2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Worker], 'column', [AdditionalText3];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Worker], 'column', [AdditionalText4];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Worker], 'column', [AdditionalText5];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Worker], 'column', [AdditionalText6];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Worker], 'column', [AdditionalText7];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Worker], 'column', [AdditionalNumber1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Worker], 'column', [AdditionalNumber2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', core, 'table', [Worker], 'column', [AdditionalNumber3];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu ilk veri versiyonu', 'schema', core, 'table', [Worker], 'column', [VersionFrom];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş', 'schema', core, 'table', [Worker], 'column', [VersionTo];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydı getiren yükleme partisi', 'schema', core, 'table', [Worker], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'İş anahtarı (kod ya da kodların birleşimi)', 'schema', core, 'table', [Worker], 'column', [BusinessKey];

GO

execute sp_addextendedproperty 'MS_Description', N'Son değişiklik zamanı', 'schema', core, 'table', [Worker], 'column', [UpdatedAt];

GO

CREATE INDEX [IX_Worker_ResourceGroupId] ON core.[Worker] ([ResourceGroupId]);

GO

CREATE UNIQUE INDEX [UX_Worker_Code] ON core.[Worker] ([Code]) WHERE VersionTo IS NULL;

GO

CREATE TABLE core.[WorkerAbsence] (
    [Id] BIGINT NOT NULL, 
    [WorkerId] BIGINT NOT NULL, 
    [StartAt] DATETIME2 NOT NULL, 
    [EndAt] DATETIME2 NOT NULL, 
    [AbsenceType] NVARCHAR(10) NOT NULL, 
    [VersionFrom] INTEGER NOT NULL, 
    [VersionTo] INTEGER NULL, 
    [ImportBatchId] BIGINT NULL, 
    [BusinessKey] NVARCHAR(200) NOT NULL, 
    [UpdatedAt] DATETIME2 NOT NULL, 
    CONSTRAINT [PK_WorkerAbsence] PRIMARY KEY ([Id], [VersionFrom]), 
    CONSTRAINT [FK_WorkerAbsence_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Kişi bazında izin ve rapor.', 'schema', core, 'table', [WorkerAbsence];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', core, 'table', [WorkerAbsence], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'İşçi', 'schema', core, 'table', [WorkerAbsence], 'column', [WorkerId];

GO

execute sp_addextendedproperty 'MS_Description', N'Başlangıç', 'schema', core, 'table', [WorkerAbsence], 'column', [StartAt];

GO

execute sp_addextendedproperty 'MS_Description', N'Bitiş', 'schema', core, 'table', [WorkerAbsence], 'column', [EndAt];

GO

execute sp_addextendedproperty 'MS_Description', N'İzin | Rapor', 'schema', core, 'table', [WorkerAbsence], 'column', [AbsenceType];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu ilk veri versiyonu', 'schema', core, 'table', [WorkerAbsence], 'column', [VersionFrom];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş', 'schema', core, 'table', [WorkerAbsence], 'column', [VersionTo];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydı getiren yükleme partisi', 'schema', core, 'table', [WorkerAbsence], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'İş anahtarı (kod ya da kodların birleşimi)', 'schema', core, 'table', [WorkerAbsence], 'column', [BusinessKey];

GO

execute sp_addextendedproperty 'MS_Description', N'Son değişiklik zamanı', 'schema', core, 'table', [WorkerAbsence], 'column', [UpdatedAt];

GO

CREATE INDEX [IX_WorkerAbsence_WorkerId] ON core.[WorkerAbsence] ([WorkerId]);

GO

CREATE TABLE core.[WorkerCompetence] (
    [WorkerId] BIGINT NOT NULL, 
    [CompetenceGroupId] BIGINT NOT NULL, 
    [VersionFrom] INTEGER NOT NULL, 
    [VersionTo] INTEGER NULL, 
    [ImportBatchId] BIGINT NULL, 
    [BusinessKey] NVARCHAR(200) NOT NULL, 
    [UpdatedAt] DATETIME2 NOT NULL, 
    CONSTRAINT [PK_WorkerCompetence] PRIMARY KEY ([WorkerId], [CompetenceGroupId], [VersionFrom]), 
    CONSTRAINT [FK_WorkerCompetence_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'İşçi–yetkinlik grubu eşleşmesi; çoktan çoğa.', 'schema', core, 'table', [WorkerCompetence];

GO

execute sp_addextendedproperty 'MS_Description', N'İşçi', 'schema', core, 'table', [WorkerCompetence], 'column', [WorkerId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yetkinlik grubu', 'schema', core, 'table', [WorkerCompetence], 'column', [CompetenceGroupId];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu ilk veri versiyonu', 'schema', core, 'table', [WorkerCompetence], 'column', [VersionFrom];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş', 'schema', core, 'table', [WorkerCompetence], 'column', [VersionTo];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydı getiren yükleme partisi', 'schema', core, 'table', [WorkerCompetence], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'İş anahtarı (kod ya da kodların birleşimi)', 'schema', core, 'table', [WorkerCompetence], 'column', [BusinessKey];

GO

execute sp_addextendedproperty 'MS_Description', N'Son değişiklik zamanı', 'schema', core, 'table', [WorkerCompetence], 'column', [UpdatedAt];

GO

CREATE INDEX [IX_WorkerCompetence_CompetenceGroupId] ON core.[WorkerCompetence] ([CompetenceGroupId]);

GO

CREATE INDEX [IX_WorkerCompetence_WorkerId] ON core.[WorkerCompetence] ([WorkerId]);

GO

CREATE TABLE param.[AllocationRule] (
    [Id] BIGINT NOT NULL IDENTITY, 
    [ParameterSetId] INTEGER NOT NULL, 
    [DemandClass] NVARCHAR(100) NOT NULL, 
    [ResourceId] BIGINT NULL, 
    [ResourceGroupId] BIGINT NULL, 
    [ValidFrom] DATE NULL, 
    [ValidTo] DATE NULL, 
    [SharePct] NUMERIC(6, 2) NOT NULL, 
    [Hardness] NVARCHAR(10) NULL DEFAULT N'Yumuşak', 
    CONSTRAINT [PK_AllocationRule] PRIMARY KEY ([Id]), 
    CONSTRAINT [FK_AllocationRule_ParameterSetId] FOREIGN KEY([ParameterSetId]) REFERENCES param.[ParameterSet] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Kapasite alokasyonu: talep sınıfına kaynak (grubu) ve dönem bazında pay.', 'schema', param, 'table', [AllocationRule];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', param, 'table', [AllocationRule], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Parametre seti', 'schema', param, 'table', [AllocationRule], 'column', [ParameterSetId];

GO

execute sp_addextendedproperty 'MS_Description', N'Talep sınıfı tanımı (müşteri, proje, ürün grubu)', 'schema', param, 'table', [AllocationRule], 'column', [DemandClass];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaynak', 'schema', param, 'table', [AllocationRule], 'column', [ResourceId];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaynak grubu', 'schema', param, 'table', [AllocationRule], 'column', [ResourceGroupId];

GO

execute sp_addextendedproperty 'MS_Description', N'Başlangıç', 'schema', param, 'table', [AllocationRule], 'column', [ValidFrom];

GO

execute sp_addextendedproperty 'MS_Description', N'Bitiş', 'schema', param, 'table', [AllocationRule], 'column', [ValidTo];

GO

execute sp_addextendedproperty 'MS_Description', N'Pay (%)', 'schema', param, 'table', [AllocationRule], 'column', [SharePct];

GO

execute sp_addextendedproperty 'MS_Description', N'Taban | Tavan | Yumuşak', 'schema', param, 'table', [AllocationRule], 'column', [Hardness];

GO

CREATE INDEX [IX_AllocationRule_ResourceGroupId] ON param.[AllocationRule] ([ResourceGroupId]);

GO

CREATE INDEX [IX_AllocationRule_ResourceId] ON param.[AllocationRule] ([ResourceId]);

GO

CREATE TABLE param.[OvertimeLimit] (
    [Id] BIGINT NOT NULL IDENTITY, 
    [ParameterSetId] INTEGER NOT NULL, 
    [ShiftPlanId] BIGINT NOT NULL, 
    [MaxOvertimeHours] NUMERIC(9, 2) NOT NULL, 
    CONSTRAINT [PK_OvertimeLimit] PRIMARY KEY ([Id]), 
    CONSTRAINT [FK_OvertimeLimit_ParameterSetId] FOREIGN KEY([ParameterSetId]) REFERENCES param.[ParameterSet] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Fazla mesai üst limiti (vardiya ve dönem bazında).', 'schema', param, 'table', [OvertimeLimit];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', param, 'table', [OvertimeLimit], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Parametre seti', 'schema', param, 'table', [OvertimeLimit], 'column', [ParameterSetId];

GO

execute sp_addextendedproperty 'MS_Description', N'Vardiya planı', 'schema', param, 'table', [OvertimeLimit], 'column', [ShiftPlanId];

GO

execute sp_addextendedproperty 'MS_Description', N'Dönem başına en fazla fazla mesai (saat)', 'schema', param, 'table', [OvertimeLimit], 'column', [MaxOvertimeHours];

GO

CREATE INDEX [IX_OvertimeLimit_ShiftPlanId] ON param.[OvertimeLimit] ([ShiftPlanId]);

GO

CREATE TABLE param.[PlanningSetting] (
    [ParameterSetId] INTEGER NOT NULL, 
    [SettingKey] NVARCHAR(60) NOT NULL, 
    [Value] NVARCHAR(200) NOT NULL, 
    CONSTRAINT [PK_PlanningSetting] PRIMARY KEY ([ParameterSetId], [SettingKey]), 
    CONSTRAINT [FK_PlanningSetting_ParameterSetId] FOREIGN KEY([ParameterSetId]) REFERENCES param.[ParameterSet] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Genel planlama parametreleri (anahtar–değer); ör. model tipi, fazla mesai dahil mi, fix dönem, toleranslar, MRP öncelik ve kısıt ayarları.', 'schema', param, 'table', [PlanningSetting];

GO

execute sp_addextendedproperty 'MS_Description', N'Parametre seti', 'schema', param, 'table', [PlanningSetting], 'column', [ParameterSetId];

GO

execute sp_addextendedproperty 'MS_Description', N'Parametre adı (ör. ModelType, UseOvertime, FixPeriodDays)', 'schema', param, 'table', [PlanningSetting], 'column', [SettingKey];

GO

execute sp_addextendedproperty 'MS_Description', N'Değer', 'schema', param, 'table', [PlanningSetting], 'column', [Value];

GO

CREATE TABLE param.[PriorityRule] (
    [ParameterSetId] INTEGER NOT NULL, 
    [Seq] INTEGER NOT NULL, 
    [Criterion] NVARCHAR(30) NOT NULL, 
    [Direction] NVARCHAR(4) NULL DEFAULT N'Artan', 
    CONSTRAINT [PK_PriorityRule] PRIMARY KEY ([ParameterSetId], [Seq]), 
    CONSTRAINT [FK_PriorityRule_ParameterSetId] FOREIGN KEY([ParameterSetId]) REFERENCES param.[ParameterSet] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Sıralama kuralı: kriterlerin sırası (bucket > müşteri > proje > satır > tarih).', 'schema', param, 'table', [PriorityRule];

GO

execute sp_addextendedproperty 'MS_Description', N'Parametre seti', 'schema', param, 'table', [PriorityRule], 'column', [ParameterSetId];

GO

execute sp_addextendedproperty 'MS_Description', N'Sıra', 'schema', param, 'table', [PriorityRule], 'column', [Seq];

GO

execute sp_addextendedproperty 'MS_Description', N'Kriter', 'schema', param, 'table', [PriorityRule], 'column', [Criterion];

GO

execute sp_addextendedproperty 'MS_Description', N'Artan | Azalan', 'schema', param, 'table', [PriorityRule], 'column', [Direction];

GO

CREATE TABLE param.[ResourceEfficiency] (
    [Id] BIGINT NOT NULL IDENTITY, 
    [ParameterSetId] INTEGER NOT NULL, 
    [ResourceId] BIGINT NOT NULL, 
    [ValidFrom] DATE NOT NULL, 
    [ValidTo] DATE NOT NULL, 
    [EfficiencyPct] NUMERIC(6, 2) NOT NULL DEFAULT 100, 
    CONSTRAINT [PK_ResourceEfficiency] PRIMARY KEY ([Id]), 
    CONSTRAINT [FK_ResourceEfficiency_ParameterSetId] FOREIGN KEY([ParameterSetId]) REFERENCES param.[ParameterSet] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Kaynak ve dönem bazında verim (kapasite katsayısı); senaryoya özel.', 'schema', param, 'table', [ResourceEfficiency];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', param, 'table', [ResourceEfficiency], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Parametre seti', 'schema', param, 'table', [ResourceEfficiency], 'column', [ParameterSetId];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaynak', 'schema', param, 'table', [ResourceEfficiency], 'column', [ResourceId];

GO

execute sp_addextendedproperty 'MS_Description', N'Başlangıç', 'schema', param, 'table', [ResourceEfficiency], 'column', [ValidFrom];

GO

execute sp_addextendedproperty 'MS_Description', N'Bitiş', 'schema', param, 'table', [ResourceEfficiency], 'column', [ValidTo];

GO

execute sp_addextendedproperty 'MS_Description', N'Verim (%)', 'schema', param, 'table', [ResourceEfficiency], 'column', [EfficiencyPct];

GO

CREATE INDEX [IX_ResourceEfficiency_ResourceId] ON param.[ResourceEfficiency] ([ResourceId]);

GO

CREATE TABLE param.[ResourcePeriodLimit] (
    [Id] BIGINT NOT NULL IDENTITY, 
    [ParameterSetId] INTEGER NOT NULL, 
    [ResourceId] BIGINT NOT NULL, 
    [ValidFrom] DATE NOT NULL, 
    [ValidTo] DATE NOT NULL, 
    [UpperLimit] NUMERIC(18, 4) NOT NULL, 
    CONSTRAINT [PK_ResourcePeriodLimit] PRIMARY KEY ([Id]), 
    CONSTRAINT [FK_ResourcePeriodLimit_ParameterSetId] FOREIGN KEY([ParameterSetId]) REFERENCES param.[ParameterSet] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Dönem bazlı üst limit; kısıtsız kaynaklarda ve fasonda. Birim kaynağın kapasite birimi.', 'schema', param, 'table', [ResourcePeriodLimit];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', param, 'table', [ResourcePeriodLimit], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Parametre seti', 'schema', param, 'table', [ResourcePeriodLimit], 'column', [ParameterSetId];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaynak', 'schema', param, 'table', [ResourcePeriodLimit], 'column', [ResourceId];

GO

execute sp_addextendedproperty 'MS_Description', N'Başlangıç', 'schema', param, 'table', [ResourcePeriodLimit], 'column', [ValidFrom];

GO

execute sp_addextendedproperty 'MS_Description', N'Bitiş', 'schema', param, 'table', [ResourcePeriodLimit], 'column', [ValidTo];

GO

execute sp_addextendedproperty 'MS_Description', N'Dönem üst limiti', 'schema', param, 'table', [ResourcePeriodLimit], 'column', [UpperLimit];

GO

CREATE INDEX [IX_ResourcePeriodLimit_ResourceId] ON param.[ResourcePeriodLimit] ([ResourceId]);

GO

CREATE TABLE param.[ScenarioDefinition] (
    [Id] INTEGER NOT NULL IDENTITY, 
    [LocationId] INTEGER NOT NULL, 
    [Name] NVARCHAR(100) NOT NULL, 
    [ParameterSetId] INTEGER NOT NULL, 
    [ResourceConstraint] NVARCHAR(15) NULL DEFAULT N'Kısıtlı', 
    [MaterialConstraint] BIT NULL DEFAULT 1, 
    [ModelType] NVARCHAR(5) NULL DEFAULT N'LP', 
    [NightlyPriority] INTEGER NULL, 
    [IsActive] BIT NULL DEFAULT 1, 
    CONSTRAINT [PK_ScenarioDefinition] PRIMARY KEY ([Id]), 
    CONSTRAINT [FK_ScenarioDefinition_LocationId] FOREIGN KEY([LocationId]) REFERENCES core.[Location] ([Id]), 
    CONSTRAINT [FK_ScenarioDefinition_ParameterSetId] FOREIGN KEY([ParameterSetId]) REFERENCES param.[ParameterSet] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Gece senaryosu tanımı: parametre seti + eksen ayarları.', 'schema', param, 'table', [ScenarioDefinition];

GO

execute sp_addextendedproperty 'MS_Description', N'Tanım kimliği', 'schema', param, 'table', [ScenarioDefinition], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Lokasyon', 'schema', param, 'table', [ScenarioDefinition], 'column', [LocationId];

GO

execute sp_addextendedproperty 'MS_Description', N'Senaryo adı', 'schema', param, 'table', [ScenarioDefinition], 'column', [Name];

GO

execute sp_addextendedproperty 'MS_Description', N'Parametre seti', 'schema', param, 'table', [ScenarioDefinition], 'column', [ParameterSetId];

GO

execute sp_addextendedproperty 'MS_Description', N'Kısıtsız | Kısıtlı | Kısmi', 'schema', param, 'table', [ScenarioDefinition], 'column', [ResourceConstraint];

GO

execute sp_addextendedproperty 'MS_Description', N'Malzeme kısıtı', 'schema', param, 'table', [ScenarioDefinition], 'column', [MaterialConstraint];

GO

execute sp_addextendedproperty 'MS_Description', N'LP | MILP', 'schema', param, 'table', [ScenarioDefinition], 'column', [ModelType];

GO

execute sp_addextendedproperty 'MS_Description', N'Gece çalışma önceliği', 'schema', param, 'table', [ScenarioDefinition], 'column', [NightlyPriority];

GO

execute sp_addextendedproperty 'MS_Description', N'Gece çalışsın mı', 'schema', param, 'table', [ScenarioDefinition], 'column', [IsActive];

GO

CREATE TABLE param.[SupplierLimit] (
    [Id] BIGINT NOT NULL IDENTITY, 
    [ParameterSetId] INTEGER NOT NULL, 
    [SupplierId] BIGINT NOT NULL, 
    [MaterialId] BIGINT NULL, 
    [ValidFrom] DATE NOT NULL, 
    [ValidTo] DATE NOT NULL, 
    [UpperLimit] NUMERIC(18, 4) NOT NULL DEFAULT 0, 
    CONSTRAINT [PK_SupplierLimit] PRIMARY KEY ([Id]), 
    CONSTRAINT [FK_SupplierLimit_ParameterSetId] FOREIGN KEY([ParameterSetId]) REFERENCES param.[ParameterSet] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Tedarikçi dönem üst limiti (problem 39): malzeme bazında maksimum miktar. Malzeme boşsa tedarikçi o dönemde kapalıdır (limit 0). Smartchain''de ekrandan girilir (K-65, K-66).', 'schema', param, 'table', [SupplierLimit];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', param, 'table', [SupplierLimit], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Parametre seti', 'schema', param, 'table', [SupplierLimit], 'column', [ParameterSetId];

GO

execute sp_addextendedproperty 'MS_Description', N'Tedarikçi', 'schema', param, 'table', [SupplierLimit], 'column', [SupplierId];

GO

execute sp_addextendedproperty 'MS_Description', N'Malzeme; boşsa tedarikçinin bütün malzemeleri (yalnız kapalı dönem)', 'schema', param, 'table', [SupplierLimit], 'column', [MaterialId];

GO

execute sp_addextendedproperty 'MS_Description', N'Başlangıç', 'schema', param, 'table', [SupplierLimit], 'column', [ValidFrom];

GO

execute sp_addextendedproperty 'MS_Description', N'Bitiş', 'schema', param, 'table', [SupplierLimit], 'column', [ValidTo];

GO

execute sp_addextendedproperty 'MS_Description', N'Dönem üst limiti, malzemenin temel biriminde; malzeme boşsa 0', 'schema', param, 'table', [SupplierLimit], 'column', [UpperLimit];

GO

CREATE INDEX [IX_SupplierLimit_MaterialId] ON param.[SupplierLimit] ([MaterialId]);

GO

CREATE INDEX [IX_SupplierLimit_SupplierId] ON param.[SupplierLimit] ([SupplierId]);

GO

CREATE TABLE param.[TimeBucketDefinition] (
    [ParameterSetId] INTEGER NOT NULL, 
    [Seq] INTEGER NOT NULL, 
    [BucketType] NVARCHAR(10) NOT NULL, 
    [Count] INTEGER NOT NULL, 
    CONSTRAINT [PK_TimeBucketDefinition] PRIMARY KEY ([ParameterSetId], [Seq]), 
    CONSTRAINT [FK_TimeBucketDefinition_ParameterSetId] FOREIGN KEY([ParameterSetId]) REFERENCES param.[ParameterSet] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Zaman yapısı: planlama ufku ve dinamik bucket dizisi.', 'schema', param, 'table', [TimeBucketDefinition];

GO

execute sp_addextendedproperty 'MS_Description', N'Parametre seti', 'schema', param, 'table', [TimeBucketDefinition], 'column', [ParameterSetId];

GO

execute sp_addextendedproperty 'MS_Description', N'Sıra', 'schema', param, 'table', [TimeBucketDefinition], 'column', [Seq];

GO

execute sp_addextendedproperty 'MS_Description', N'Gün | Hafta | Ay | Çeyrek | Yıl', 'schema', param, 'table', [TimeBucketDefinition], 'column', [BucketType];

GO

execute sp_addextendedproperty 'MS_Description', N'Bu tipten kaç bucket', 'schema', param, 'table', [TimeBucketDefinition], 'column', [Count];

GO

CREATE TABLE planning.[Workspace] (
    [Id] BIGINT NOT NULL IDENTITY, 
    [ScenarioId] BIGINT NOT NULL, 
    [OwnerUserId] INTEGER NOT NULL, 
    [Status] NVARCHAR(15) NOT NULL, 
    [CurrentPlanRunId] BIGINT NULL, 
    [LastActivityAt] DATETIME2 NULL, 
    CONSTRAINT [PK_Workspace] PRIMARY KEY ([Id]), 
    CONSTRAINT [FK_Workspace_OwnerUserId] FOREIGN KEY([OwnerUserId]) REFERENCES adm.[AppUser] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Kullanıcının bir senaryo üzerindeki çalışması; yayınlanmazsa gece silinir.', 'schema', planning, 'table', [Workspace];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', planning, 'table', [Workspace], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Senaryo', 'schema', planning, 'table', [Workspace], 'column', [ScenarioId];

GO

execute sp_addextendedproperty 'MS_Description', N'Sahibi', 'schema', planning, 'table', [Workspace], 'column', [OwnerUserId];

GO

execute sp_addextendedproperty 'MS_Description', N'Açık | Kapalı | Yayınlandı', 'schema', planning, 'table', [Workspace], 'column', [Status];

GO

execute sp_addextendedproperty 'MS_Description', N'Son hesap sonucu', 'schema', planning, 'table', [Workspace], 'column', [CurrentPlanRunId];

GO

execute sp_addextendedproperty 'MS_Description', N'Son işlem', 'schema', planning, 'table', [Workspace], 'column', [LastActivityAt];

GO

CREATE TABLE stg.[BOM] (
    [StagingRowId] BIGINT NOT NULL IDENTITY, 
    [ImportBatchId] BIGINT NOT NULL, 
    [RowStatus] NVARCHAR(15) NOT NULL, 
    [ErrorText] NVARCHAR(400) NULL, 
    [MaterialCode] NVARCHAR(50) NULL, 
    [ProductionVersionCode] NVARCHAR(30) NULL, 
    [ComponentMaterialCode] NVARCHAR(50) NULL, 
    [Quantity] NUMERIC(18, 6) NULL, 
    [ScrapPct] NUMERIC(6, 2) NULL, 
    [IsFixedQuantity] BIT NULL, 
    [OpNo] INTEGER NULL, 
    [AdditionalText1] NVARCHAR(255) NULL, 
    [AdditionalText2] NVARCHAR(255) NULL, 
    [AdditionalText3] NVARCHAR(255) NULL, 
    [AdditionalNumber1] NUMERIC(18, 4) NULL, 
    [AdditionalNumber2] NUMERIC(18, 4) NULL, 
    CONSTRAINT [PK_BOM] PRIMARY KEY ([StagingRowId]), 
    CONSTRAINT [FK_BOM_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Ürün ağacı satırı.', 'schema', stg, 'table', [BOM];

GO

execute sp_addextendedproperty 'MS_Description', N'Satır kimliği', 'schema', stg, 'table', [BOM], 'column', [StagingRowId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yükleme partisi', 'schema', stg, 'table', [BOM], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yeni | Hatalı | Aktarıldı', 'schema', stg, 'table', [BOM], 'column', [RowStatus];

GO

execute sp_addextendedproperty 'MS_Description', N'Hata açıklaması', 'schema', stg, 'table', [BOM], 'column', [ErrorText];

GO

execute sp_addextendedproperty 'MS_Description', N'Üretilen malzeme kodu', 'schema', stg, 'table', [BOM], 'column', [MaterialCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Üretim versiyonu kodu', 'schema', stg, 'table', [BOM], 'column', [ProductionVersionCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Bileşen kodu', 'schema', stg, 'table', [BOM], 'column', [ComponentMaterialCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Baz miktar için bileşen miktarı', 'schema', stg, 'table', [BOM], 'column', [Quantity];

GO

execute sp_addextendedproperty 'MS_Description', N'Bileşen firesi (%)', 'schema', stg, 'table', [BOM], 'column', [ScrapPct];

GO

execute sp_addextendedproperty 'MS_Description', N'Sabit miktarlı bileşen', 'schema', stg, 'table', [BOM], 'column', [IsFixedQuantity];

GO

execute sp_addextendedproperty 'MS_Description', N'Bağlı olduğu operasyon no (ihtiyaç tarihi için)', 'schema', stg, 'table', [BOM], 'column', [OpNo];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [BOM], 'column', [AdditionalText1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [BOM], 'column', [AdditionalText2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [BOM], 'column', [AdditionalText3];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [BOM], 'column', [AdditionalNumber1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [BOM], 'column', [AdditionalNumber2];

GO

CREATE UNIQUE INDEX [UX_BOM_MaterialCode_ProductionVersionCode] ON stg.[BOM] ([MaterialCode], [ProductionVersionCode]);

GO

CREATE TABLE stg.[CompetenceGroup] (
    [StagingRowId] BIGINT NOT NULL IDENTITY, 
    [ImportBatchId] BIGINT NOT NULL, 
    [RowStatus] NVARCHAR(15) NOT NULL, 
    [ErrorText] NVARCHAR(400) NULL, 
    [LocationCode] NVARCHAR(30) NULL, 
    [Code] NVARCHAR(50) NULL, 
    [Name] NVARCHAR(150) NULL, 
    CONSTRAINT [PK_CompetenceGroup] PRIMARY KEY ([StagingRowId]), 
    CONSTRAINT [FK_CompetenceGroup_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'İşçi yetkinlik grubu.', 'schema', stg, 'table', [CompetenceGroup];

GO

execute sp_addextendedproperty 'MS_Description', N'Satır kimliği', 'schema', stg, 'table', [CompetenceGroup], 'column', [StagingRowId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yükleme partisi', 'schema', stg, 'table', [CompetenceGroup], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yeni | Hatalı | Aktarıldı', 'schema', stg, 'table', [CompetenceGroup], 'column', [RowStatus];

GO

execute sp_addextendedproperty 'MS_Description', N'Hata açıklaması', 'schema', stg, 'table', [CompetenceGroup], 'column', [ErrorText];

GO

execute sp_addextendedproperty 'MS_Description', N'Lokasyon kodu', 'schema', stg, 'table', [CompetenceGroup], 'column', [LocationCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Grup kodu', 'schema', stg, 'table', [CompetenceGroup], 'column', [Code];

GO

execute sp_addextendedproperty 'MS_Description', N'Grup adı', 'schema', stg, 'table', [CompetenceGroup], 'column', [Name];

GO

CREATE UNIQUE INDEX [UX_CompetenceGroup_Code] ON stg.[CompetenceGroup] ([Code]);

GO

CREATE TABLE stg.[Customer] (
    [StagingRowId] BIGINT NOT NULL IDENTITY, 
    [ImportBatchId] BIGINT NOT NULL, 
    [RowStatus] NVARCHAR(15) NOT NULL, 
    [ErrorText] NVARCHAR(400) NULL, 
    [Code] NVARCHAR(50) NULL, 
    [Name] NVARCHAR(200) NULL, 
    [Priority] INTEGER NULL, 
    [AllowPartialDelivery] BIT NULL, 
    [AdditionalText1] NVARCHAR(255) NULL, 
    [AdditionalText2] NVARCHAR(255) NULL, 
    [AdditionalText3] NVARCHAR(255) NULL, 
    [AdditionalText4] NVARCHAR(255) NULL, 
    [AdditionalText5] NVARCHAR(255) NULL, 
    [AdditionalText6] NVARCHAR(255) NULL, 
    [AdditionalText7] NVARCHAR(255) NULL, 
    [AdditionalNumber1] NUMERIC(18, 4) NULL, 
    [AdditionalNumber2] NUMERIC(18, 4) NULL, 
    [AdditionalNumber3] NUMERIC(18, 4) NULL, 
    CONSTRAINT [PK_Customer] PRIMARY KEY ([StagingRowId]), 
    CONSTRAINT [FK_Customer_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Müşteri.', 'schema', stg, 'table', [Customer];

GO

execute sp_addextendedproperty 'MS_Description', N'Satır kimliği', 'schema', stg, 'table', [Customer], 'column', [StagingRowId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yükleme partisi', 'schema', stg, 'table', [Customer], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yeni | Hatalı | Aktarıldı', 'schema', stg, 'table', [Customer], 'column', [RowStatus];

GO

execute sp_addextendedproperty 'MS_Description', N'Hata açıklaması', 'schema', stg, 'table', [Customer], 'column', [ErrorText];

GO

execute sp_addextendedproperty 'MS_Description', N'Müşteri kodu', 'schema', stg, 'table', [Customer], 'column', [Code];

GO

execute sp_addextendedproperty 'MS_Description', N'Ad', 'schema', stg, 'table', [Customer], 'column', [Name];

GO

execute sp_addextendedproperty 'MS_Description', N'Müşteri önceliği', 'schema', stg, 'table', [Customer], 'column', [Priority];

GO

execute sp_addextendedproperty 'MS_Description', N'Kısmi teslimata izin', 'schema', stg, 'table', [Customer], 'column', [AllowPartialDelivery];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Customer], 'column', [AdditionalText1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Customer], 'column', [AdditionalText2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Customer], 'column', [AdditionalText3];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Customer], 'column', [AdditionalText4];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Customer], 'column', [AdditionalText5];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Customer], 'column', [AdditionalText6];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Customer], 'column', [AdditionalText7];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Customer], 'column', [AdditionalNumber1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Customer], 'column', [AdditionalNumber2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Customer], 'column', [AdditionalNumber3];

GO

CREATE UNIQUE INDEX [UX_Customer_Code] ON stg.[Customer] ([Code]);

GO

CREATE TABLE stg.[Forecast] (
    [StagingRowId] BIGINT NOT NULL IDENTITY, 
    [ImportBatchId] BIGINT NOT NULL, 
    [RowStatus] NVARCHAR(15) NOT NULL, 
    [ErrorText] NVARCHAR(400) NULL, 
    [LocationCode] NVARCHAR(30) NULL, 
    [MaterialCode] NVARCHAR(50) NULL, 
    [CustomerCode] NVARCHAR(50) NULL, 
    [ProjectCode] NVARCHAR(50) NULL, 
    [Period] DATE NULL, 
    [Quantity] NUMERIC(18, 4) NULL, 
    [AdditionalText1] NVARCHAR(255) NULL, 
    [AdditionalText2] NVARCHAR(255) NULL, 
    [AdditionalText3] NVARCHAR(255) NULL, 
    [AdditionalNumber1] NUMERIC(18, 4) NULL, 
    [AdditionalNumber2] NUMERIC(18, 4) NULL, 
    CONSTRAINT [PK_Forecast] PRIMARY KEY ([StagingRowId]), 
    CONSTRAINT [FK_Forecast_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Talep tahmini (netleme ön hesapta).', 'schema', stg, 'table', [Forecast];

GO

execute sp_addextendedproperty 'MS_Description', N'Satır kimliği', 'schema', stg, 'table', [Forecast], 'column', [StagingRowId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yükleme partisi', 'schema', stg, 'table', [Forecast], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yeni | Hatalı | Aktarıldı', 'schema', stg, 'table', [Forecast], 'column', [RowStatus];

GO

execute sp_addextendedproperty 'MS_Description', N'Hata açıklaması', 'schema', stg, 'table', [Forecast], 'column', [ErrorText];

GO

execute sp_addextendedproperty 'MS_Description', N'Lokasyon kodu', 'schema', stg, 'table', [Forecast], 'column', [LocationCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Malzeme', 'schema', stg, 'table', [Forecast], 'column', [MaterialCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Müşteri kodu', 'schema', stg, 'table', [Forecast], 'column', [CustomerCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Proje', 'schema', stg, 'table', [Forecast], 'column', [ProjectCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Dönem', 'schema', stg, 'table', [Forecast], 'column', [Period];

GO

execute sp_addextendedproperty 'MS_Description', N'Miktar', 'schema', stg, 'table', [Forecast], 'column', [Quantity];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Forecast], 'column', [AdditionalText1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Forecast], 'column', [AdditionalText2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Forecast], 'column', [AdditionalText3];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Forecast], 'column', [AdditionalNumber1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Forecast], 'column', [AdditionalNumber2];

GO

CREATE TABLE stg.[Location] (
    [StagingRowId] BIGINT NOT NULL IDENTITY, 
    [ImportBatchId] BIGINT NOT NULL, 
    [RowStatus] NVARCHAR(15) NOT NULL, 
    [ErrorText] NVARCHAR(400) NULL, 
    [Code] NVARCHAR(30) NULL, 
    [Name] NVARCHAR(100) NULL, 
    [Type] NVARCHAR(15) NULL, 
    [Country] NVARCHAR(100) NULL, 
    [CountryCode] NVARCHAR(10) NULL, 
    [Region] NVARCHAR(100) NULL, 
    [RegionCode] NVARCHAR(20) NULL, 
    [City] NVARCHAR(100) NULL, 
    [CityCode] NVARCHAR(20) NULL, 
    [AdditionalText1] NVARCHAR(255) NULL, 
    [AdditionalText2] NVARCHAR(255) NULL, 
    [AdditionalText3] NVARCHAR(255) NULL, 
    [AdditionalText4] NVARCHAR(255) NULL, 
    [AdditionalText5] NVARCHAR(255) NULL, 
    [AdditionalText6] NVARCHAR(255) NULL, 
    [AdditionalText7] NVARCHAR(255) NULL, 
    [AdditionalNumber1] NUMERIC(18, 4) NULL, 
    [AdditionalNumber2] NUMERIC(18, 4) NULL, 
    [AdditionalNumber3] NUMERIC(18, 4) NULL, 
    CONSTRAINT [PK_Location] PRIMARY KEY ([StagingRowId]), 
    CONSTRAINT [FK_Location_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Lokasyon (tesis, depo). Faz 1''de her lokasyon kendi içinde planlanır.', 'schema', stg, 'table', [Location];

GO

execute sp_addextendedproperty 'MS_Description', N'Satır kimliği', 'schema', stg, 'table', [Location], 'column', [StagingRowId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yükleme partisi', 'schema', stg, 'table', [Location], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yeni | Hatalı | Aktarıldı', 'schema', stg, 'table', [Location], 'column', [RowStatus];

GO

execute sp_addextendedproperty 'MS_Description', N'Hata açıklaması', 'schema', stg, 'table', [Location], 'column', [ErrorText];

GO

execute sp_addextendedproperty 'MS_Description', N'Lokasyon kodu', 'schema', stg, 'table', [Location], 'column', [Code];

GO

execute sp_addextendedproperty 'MS_Description', N'Lokasyon adı', 'schema', stg, 'table', [Location], 'column', [Name];

GO

execute sp_addextendedproperty 'MS_Description', N'Tesis | Depo | Fason deposu', 'schema', stg, 'table', [Location], 'column', [Type];

GO

execute sp_addextendedproperty 'MS_Description', N'Ülke', 'schema', stg, 'table', [Location], 'column', [Country];

GO

execute sp_addextendedproperty 'MS_Description', N'Ülke kodu', 'schema', stg, 'table', [Location], 'column', [CountryCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Bölge', 'schema', stg, 'table', [Location], 'column', [Region];

GO

execute sp_addextendedproperty 'MS_Description', N'Bölge kodu', 'schema', stg, 'table', [Location], 'column', [RegionCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Şehir', 'schema', stg, 'table', [Location], 'column', [City];

GO

execute sp_addextendedproperty 'MS_Description', N'Şehir kodu', 'schema', stg, 'table', [Location], 'column', [CityCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Location], 'column', [AdditionalText1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Location], 'column', [AdditionalText2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Location], 'column', [AdditionalText3];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Location], 'column', [AdditionalText4];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Location], 'column', [AdditionalText5];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Location], 'column', [AdditionalText6];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Location], 'column', [AdditionalText7];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Location], 'column', [AdditionalNumber1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Location], 'column', [AdditionalNumber2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Location], 'column', [AdditionalNumber3];

GO

CREATE UNIQUE INDEX [UX_Location_Code] ON stg.[Location] ([Code]);

GO

CREATE TABLE stg.[Material] (
    [StagingRowId] BIGINT NOT NULL IDENTITY, 
    [ImportBatchId] BIGINT NOT NULL, 
    [RowStatus] NVARCHAR(15) NOT NULL, 
    [ErrorText] NVARCHAR(400) NULL, 
    [LocationCode] NVARCHAR(30) NULL, 
    [Code] NVARCHAR(50) NULL, 
    [Name] NVARCHAR(200) NULL, 
    [BaseUom] NVARCHAR(10) NULL, 
    [MaterialGroup] NVARCHAR(50) NULL, 
    [MaterialLevel] NVARCHAR(15) NULL, 
    [IsPurchasable] BIT NULL, 
    [IsProducible] BIT NULL, 
    [IsSellable] BIT NULL, 
    [DefaultProcurement] NVARCHAR(10) NULL, 
    [Ownership] NVARCHAR(10) NULL, 
    [IsProjectTracked] BIT NULL, 
    [IsPhantom] BIT NULL, 
    [ProductionLeadTimeDays] NUMERIC(9, 2) NULL, 
    [GoodsReceiptDays] NUMERIC(9, 2) NULL, 
    [SafetyStock] NUMERIC(18, 4) NULL, 
    [MaxStock] NUMERIC(18, 4) NULL, 
    [LotSizePolicy] NVARCHAR(15) NULL, 
    [MinLot] NUMERIC(18, 4) NULL, 
    [MaxLot] NUMERIC(18, 4) NULL, 
    [LotMultiple] NUMERIC(18, 4) NULL, 
    [AssemblyScrapPct] NUMERIC(6, 2) NULL, 
    [ShelfLifeDays] INTEGER NULL, 
    [AdditionalText1] NVARCHAR(255) NULL, 
    [AdditionalText2] NVARCHAR(255) NULL, 
    [AdditionalText3] NVARCHAR(255) NULL, 
    [AdditionalText4] NVARCHAR(255) NULL, 
    [AdditionalText5] NVARCHAR(255) NULL, 
    [AdditionalText6] NVARCHAR(255) NULL, 
    [AdditionalText7] NVARCHAR(255) NULL, 
    [AdditionalNumber1] NUMERIC(18, 4) NULL, 
    [AdditionalNumber2] NUMERIC(18, 4) NULL, 
    [AdditionalNumber3] NUMERIC(18, 4) NULL, 
    CONSTRAINT [PK_Material] PRIMARY KEY ([StagingRowId]), 
    CONSTRAINT [FK_Material_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Malzeme ve planlama ana verisi.', 'schema', stg, 'table', [Material];

GO

execute sp_addextendedproperty 'MS_Description', N'Satır kimliği', 'schema', stg, 'table', [Material], 'column', [StagingRowId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yükleme partisi', 'schema', stg, 'table', [Material], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yeni | Hatalı | Aktarıldı', 'schema', stg, 'table', [Material], 'column', [RowStatus];

GO

execute sp_addextendedproperty 'MS_Description', N'Hata açıklaması', 'schema', stg, 'table', [Material], 'column', [ErrorText];

GO

execute sp_addextendedproperty 'MS_Description', N'Lokasyon kodu', 'schema', stg, 'table', [Material], 'column', [LocationCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Malzeme kodu', 'schema', stg, 'table', [Material], 'column', [Code];

GO

execute sp_addextendedproperty 'MS_Description', N'Malzeme adı', 'schema', stg, 'table', [Material], 'column', [Name];

GO

execute sp_addextendedproperty 'MS_Description', N'Temel birim', 'schema', stg, 'table', [Material], 'column', [BaseUom];

GO

execute sp_addextendedproperty 'MS_Description', N'Malzeme grubu', 'schema', stg, 'table', [Material], 'column', [MaterialGroup];

GO

execute sp_addextendedproperty 'MS_Description', N'Hammadde | Yarı mamul | Nihai ürün', 'schema', stg, 'table', [Material], 'column', [MaterialLevel];

GO

execute sp_addextendedproperty 'MS_Description', N'Satın alınabilir', 'schema', stg, 'table', [Material], 'column', [IsPurchasable];

GO

execute sp_addextendedproperty 'MS_Description', N'Üretilebilir', 'schema', stg, 'table', [Material], 'column', [IsProducible];

GO

execute sp_addextendedproperty 'MS_Description', N'Satılabilir', 'schema', stg, 'table', [Material], 'column', [IsSellable];

GO

execute sp_addextendedproperty 'MS_Description', N'Üretim | Satın alma | Fason', 'schema', stg, 'table', [Material], 'column', [DefaultProcurement];

GO

execute sp_addextendedproperty 'MS_Description', N'Kendi | Müşteri (müşteri temin malzemesi)', 'schema', stg, 'table', [Material], 'column', [Ownership];

GO

execute sp_addextendedproperty 'MS_Description', N'Proje bazlı takip edilir mi (değilse her zaman ortak)', 'schema', stg, 'table', [Material], 'column', [IsProjectTracked];

GO

execute sp_addextendedproperty 'MS_Description', N'Hayalet yarı mamul', 'schema', stg, 'table', [Material], 'column', [IsPhantom];

GO

execute sp_addextendedproperty 'MS_Description', N'Üretim süresi (gün)', 'schema', stg, 'table', [Material], 'column', [ProductionLeadTimeDays];

GO

execute sp_addextendedproperty 'MS_Description', N'Mal kabul süresi (iş günü)', 'schema', stg, 'table', [Material], 'column', [GoodsReceiptDays];

GO

execute sp_addextendedproperty 'MS_Description', N'Güvenlik stoğu', 'schema', stg, 'table', [Material], 'column', [SafetyStock];

GO

execute sp_addextendedproperty 'MS_Description', N'Maksimum stok', 'schema', stg, 'table', [Material], 'column', [MaxStock];

GO

execute sp_addextendedproperty 'MS_Description', N'Üretimde: Lot-for-lot | Sabit | Dönemsel', 'schema', stg, 'table', [Material], 'column', [LotSizePolicy];

GO

execute sp_addextendedproperty 'MS_Description', N'Üretimde minimum', 'schema', stg, 'table', [Material], 'column', [MinLot];

GO

execute sp_addextendedproperty 'MS_Description', N'Üretimde maksimum', 'schema', stg, 'table', [Material], 'column', [MaxLot];

GO

execute sp_addextendedproperty 'MS_Description', N'Üretimde kat', 'schema', stg, 'table', [Material], 'column', [LotMultiple];

GO

execute sp_addextendedproperty 'MS_Description', N'Montaj firesi (%)', 'schema', stg, 'table', [Material], 'column', [AssemblyScrapPct];

GO

execute sp_addextendedproperty 'MS_Description', N'Raf ömrü (gün); Faz 1''de yalnız uyarı', 'schema', stg, 'table', [Material], 'column', [ShelfLifeDays];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Material], 'column', [AdditionalText1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Material], 'column', [AdditionalText2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Material], 'column', [AdditionalText3];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Material], 'column', [AdditionalText4];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Material], 'column', [AdditionalText5];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Material], 'column', [AdditionalText6];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Material], 'column', [AdditionalText7];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Material], 'column', [AdditionalNumber1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Material], 'column', [AdditionalNumber2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Material], 'column', [AdditionalNumber3];

GO

CREATE UNIQUE INDEX [UX_Material_Code] ON stg.[Material] ([Code]);

GO

CREATE TABLE stg.[MaterialSupplier] (
    [StagingRowId] BIGINT NOT NULL IDENTITY, 
    [ImportBatchId] BIGINT NOT NULL, 
    [RowStatus] NVARCHAR(15) NOT NULL, 
    [ErrorText] NVARCHAR(400) NULL, 
    [MaterialCode] NVARCHAR(50) NULL, 
    [SupplierCode] NVARCHAR(50) NULL, 
    [Priority] INTEGER NULL, 
    [QuotaPct] NUMERIC(6, 2) NULL, 
    [LeadTimeDays] NUMERIC(9, 2) NULL, 
    [LeadTimeBasis] NVARCHAR(10) NULL, 
    [MinOrderQty] NUMERIC(18, 4) NULL, 
    [OrderMultiple] NUMERIC(18, 4) NULL, 
    [MaxOrderQty] NUMERIC(18, 4) NULL, 
    [ValidFrom] DATE NULL, 
    [ValidTo] DATE NULL, 
    [AdditionalText1] NVARCHAR(255) NULL, 
    [AdditionalText2] NVARCHAR(255) NULL, 
    [AdditionalText3] NVARCHAR(255) NULL, 
    [AdditionalNumber1] NUMERIC(18, 4) NULL, 
    [AdditionalNumber2] NUMERIC(18, 4) NULL, 
    CONSTRAINT [PK_MaterialSupplier] PRIMARY KEY ([StagingRowId]), 
    CONSTRAINT [FK_MaterialSupplier_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Malzeme–tedarikçi ilişkisi; satın alma parametreleri. Satın alma her zaman sürekli; yuvarlama son hesapta.', 'schema', stg, 'table', [MaterialSupplier];

GO

execute sp_addextendedproperty 'MS_Description', N'Satır kimliği', 'schema', stg, 'table', [MaterialSupplier], 'column', [StagingRowId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yükleme partisi', 'schema', stg, 'table', [MaterialSupplier], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yeni | Hatalı | Aktarıldı', 'schema', stg, 'table', [MaterialSupplier], 'column', [RowStatus];

GO

execute sp_addextendedproperty 'MS_Description', N'Hata açıklaması', 'schema', stg, 'table', [MaterialSupplier], 'column', [ErrorText];

GO

execute sp_addextendedproperty 'MS_Description', N'Malzeme', 'schema', stg, 'table', [MaterialSupplier], 'column', [MaterialCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Tedarikçi', 'schema', stg, 'table', [MaterialSupplier], 'column', [SupplierCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Öncelik', 'schema', stg, 'table', [MaterialSupplier], 'column', [Priority];

GO

execute sp_addextendedproperty 'MS_Description', N'Kota (%)', 'schema', stg, 'table', [MaterialSupplier], 'column', [QuotaPct];

GO

execute sp_addextendedproperty 'MS_Description', N'Tedarik süresi', 'schema', stg, 'table', [MaterialSupplier], 'column', [LeadTimeDays];

GO

execute sp_addextendedproperty 'MS_Description', N'Takvim günü | İş günü', 'schema', stg, 'table', [MaterialSupplier], 'column', [LeadTimeBasis];

GO

execute sp_addextendedproperty 'MS_Description', N'Minimum sipariş miktarı', 'schema', stg, 'table', [MaterialSupplier], 'column', [MinOrderQty];

GO

execute sp_addextendedproperty 'MS_Description', N'Kat', 'schema', stg, 'table', [MaterialSupplier], 'column', [OrderMultiple];

GO

execute sp_addextendedproperty 'MS_Description', N'Maksimum', 'schema', stg, 'table', [MaterialSupplier], 'column', [MaxOrderQty];

GO

execute sp_addextendedproperty 'MS_Description', N'Geçerlilik başlangıcı', 'schema', stg, 'table', [MaterialSupplier], 'column', [ValidFrom];

GO

execute sp_addextendedproperty 'MS_Description', N'Geçerlilik bitişi', 'schema', stg, 'table', [MaterialSupplier], 'column', [ValidTo];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [MaterialSupplier], 'column', [AdditionalText1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [MaterialSupplier], 'column', [AdditionalText2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [MaterialSupplier], 'column', [AdditionalText3];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [MaterialSupplier], 'column', [AdditionalNumber1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [MaterialSupplier], 'column', [AdditionalNumber2];

GO

CREATE TABLE stg.[ProductionConfirmation] (
    [StagingRowId] BIGINT NOT NULL IDENTITY, 
    [ImportBatchId] BIGINT NOT NULL, 
    [RowStatus] NVARCHAR(15) NOT NULL, 
    [ErrorText] NVARCHAR(400) NULL, 
    [WorkOrderNo] NVARCHAR(30) NULL, 
    [OpNo] INTEGER NULL, 
    [SeqNo] INTEGER NULL, 
    [ResourceCode] NVARCHAR(50) NULL, 
    [ConfirmedQty] NUMERIC(18, 4) NULL, 
    [ActualConsumption] NUMERIC(18, 6) NULL, 
    [StartAt] DATETIME2 NULL, 
    [EndAt] DATETIME2 NULL, 
    [AdditionalText1] NVARCHAR(255) NULL, 
    [AdditionalText2] NVARCHAR(255) NULL, 
    [AdditionalText3] NVARCHAR(255) NULL, 
    [AdditionalNumber1] NUMERIC(18, 4) NULL, 
    [AdditionalNumber2] NUMERIC(18, 4) NULL, 
    CONSTRAINT [PK_ProductionConfirmation] PRIMARY KEY ([StagingRowId]), 
    CONSTRAINT [FK_ProductionConfirmation_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Üretim gerçekleşmeleri; ilk günden tutulur (verim önerisi ve ileriki fazlar).', 'schema', stg, 'table', [ProductionConfirmation];

GO

execute sp_addextendedproperty 'MS_Description', N'Satır kimliği', 'schema', stg, 'table', [ProductionConfirmation], 'column', [StagingRowId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yükleme partisi', 'schema', stg, 'table', [ProductionConfirmation], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yeni | Hatalı | Aktarıldı', 'schema', stg, 'table', [ProductionConfirmation], 'column', [RowStatus];

GO

execute sp_addextendedproperty 'MS_Description', N'Hata açıklaması', 'schema', stg, 'table', [ProductionConfirmation], 'column', [ErrorText];

GO

execute sp_addextendedproperty 'MS_Description', N'İş emri', 'schema', stg, 'table', [ProductionConfirmation], 'column', [WorkOrderNo];

GO

execute sp_addextendedproperty 'MS_Description', N'Operasyon no', 'schema', stg, 'table', [ProductionConfirmation], 'column', [OpNo];

GO

execute sp_addextendedproperty 'MS_Description', N'Operasyon içindeki alt sıra', 'schema', stg, 'table', [ProductionConfirmation], 'column', [SeqNo];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaynak kodu', 'schema', stg, 'table', [ProductionConfirmation], 'column', [ResourceCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Teyit miktarı', 'schema', stg, 'table', [ProductionConfirmation], 'column', [ConfirmedQty];

GO

execute sp_addextendedproperty 'MS_Description', N'Gerçekleşen tüketim (süre)', 'schema', stg, 'table', [ProductionConfirmation], 'column', [ActualConsumption];

GO

execute sp_addextendedproperty 'MS_Description', N'Başlangıç', 'schema', stg, 'table', [ProductionConfirmation], 'column', [StartAt];

GO

execute sp_addextendedproperty 'MS_Description', N'Bitiş', 'schema', stg, 'table', [ProductionConfirmation], 'column', [EndAt];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [ProductionConfirmation], 'column', [AdditionalText1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [ProductionConfirmation], 'column', [AdditionalText2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [ProductionConfirmation], 'column', [AdditionalText3];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [ProductionConfirmation], 'column', [AdditionalNumber1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [ProductionConfirmation], 'column', [AdditionalNumber2];

GO

CREATE TABLE stg.[ProductionVersion] (
    [StagingRowId] BIGINT NOT NULL IDENTITY, 
    [ImportBatchId] BIGINT NOT NULL, 
    [RowStatus] NVARCHAR(15) NOT NULL, 
    [ErrorText] NVARCHAR(400) NULL, 
    [MaterialCode] NVARCHAR(50) NULL, 
    [Code] NVARCHAR(30) NULL, 
    [IsDefault] BIT NULL, 
    [BaseQuantity] NUMERIC(18, 4) NULL, 
    [RouteCode] NVARCHAR(50) NULL, 
    [ValidFrom] DATE NULL, 
    [ValidTo] DATE NULL, 
    [AdditionalText1] NVARCHAR(255) NULL, 
    [AdditionalText2] NVARCHAR(255) NULL, 
    [AdditionalText3] NVARCHAR(255) NULL, 
    [AdditionalNumber1] NUMERIC(18, 4) NULL, 
    [AdditionalNumber2] NUMERIC(18, 4) NULL, 
    CONSTRAINT [PK_ProductionVersion] PRIMARY KEY ([StagingRowId]), 
    CONSTRAINT [FK_ProductionVersion_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Üretim versiyonu: bir malzemenin ürün ağacı ve rota başlığı; rotaya RouteCode ile bağlanır. Faz 1''de varsayılan versiyon kullanılır.', 'schema', stg, 'table', [ProductionVersion];

GO

execute sp_addextendedproperty 'MS_Description', N'Satır kimliği', 'schema', stg, 'table', [ProductionVersion], 'column', [StagingRowId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yükleme partisi', 'schema', stg, 'table', [ProductionVersion], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yeni | Hatalı | Aktarıldı', 'schema', stg, 'table', [ProductionVersion], 'column', [RowStatus];

GO

execute sp_addextendedproperty 'MS_Description', N'Hata açıklaması', 'schema', stg, 'table', [ProductionVersion], 'column', [ErrorText];

GO

execute sp_addextendedproperty 'MS_Description', N'Üretilen malzeme', 'schema', stg, 'table', [ProductionVersion], 'column', [MaterialCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Versiyon kodu', 'schema', stg, 'table', [ProductionVersion], 'column', [Code];

GO

execute sp_addextendedproperty 'MS_Description', N'Varsayılan versiyon', 'schema', stg, 'table', [ProductionVersion], 'column', [IsDefault];

GO

execute sp_addextendedproperty 'MS_Description', N'Baz miktar (rota ve ağaç bu miktar için)', 'schema', stg, 'table', [ProductionVersion], 'column', [BaseQuantity];

GO

execute sp_addextendedproperty 'MS_Description', N'Rota kodu (Routing.RouteCode)', 'schema', stg, 'table', [ProductionVersion], 'column', [RouteCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Geçerlilik başlangıcı', 'schema', stg, 'table', [ProductionVersion], 'column', [ValidFrom];

GO

execute sp_addextendedproperty 'MS_Description', N'Geçerlilik bitişi', 'schema', stg, 'table', [ProductionVersion], 'column', [ValidTo];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [ProductionVersion], 'column', [AdditionalText1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [ProductionVersion], 'column', [AdditionalText2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [ProductionVersion], 'column', [AdditionalText3];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [ProductionVersion], 'column', [AdditionalNumber1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [ProductionVersion], 'column', [AdditionalNumber2];

GO

CREATE TABLE stg.[Project] (
    [StagingRowId] BIGINT NOT NULL IDENTITY, 
    [ImportBatchId] BIGINT NOT NULL, 
    [RowStatus] NVARCHAR(15) NOT NULL, 
    [ErrorText] NVARCHAR(400) NULL, 
    [Code] NVARCHAR(50) NULL, 
    [Name] NVARCHAR(200) NULL, 
    [ProjectGroupCode] NVARCHAR(50) NULL, 
    [IsolationRule] NVARCHAR(20) NULL, 
    [Priority] INTEGER NULL, 
    [IsClosed] BIT NULL, 
    [AdditionalText1] NVARCHAR(255) NULL, 
    [AdditionalText2] NVARCHAR(255) NULL, 
    [AdditionalText3] NVARCHAR(255) NULL, 
    [AdditionalText4] NVARCHAR(255) NULL, 
    [AdditionalText5] NVARCHAR(255) NULL, 
    [AdditionalText6] NVARCHAR(255) NULL, 
    [AdditionalText7] NVARCHAR(255) NULL, 
    [AdditionalNumber1] NUMERIC(18, 4) NULL, 
    [AdditionalNumber2] NUMERIC(18, 4) NULL, 
    [AdditionalNumber3] NUMERIC(18, 4) NULL, 
    CONSTRAINT [PK_Project] PRIMARY KEY ([StagingRowId]), 
    CONSTRAINT [FK_Project_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Proje.', 'schema', stg, 'table', [Project];

GO

execute sp_addextendedproperty 'MS_Description', N'Satır kimliği', 'schema', stg, 'table', [Project], 'column', [StagingRowId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yükleme partisi', 'schema', stg, 'table', [Project], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yeni | Hatalı | Aktarıldı', 'schema', stg, 'table', [Project], 'column', [RowStatus];

GO

execute sp_addextendedproperty 'MS_Description', N'Hata açıklaması', 'schema', stg, 'table', [Project], 'column', [ErrorText];

GO

execute sp_addextendedproperty 'MS_Description', N'Proje kodu', 'schema', stg, 'table', [Project], 'column', [Code];

GO

execute sp_addextendedproperty 'MS_Description', N'Proje adı', 'schema', stg, 'table', [Project], 'column', [Name];

GO

execute sp_addextendedproperty 'MS_Description', N'Proje grubu kodu', 'schema', stg, 'table', [Project], 'column', [ProjectGroupCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Proje bazında izolasyon (grubu ezer)', 'schema', stg, 'table', [Project], 'column', [IsolationRule];

GO

execute sp_addextendedproperty 'MS_Description', N'Proje önceliği', 'schema', stg, 'table', [Project], 'column', [Priority];

GO

execute sp_addextendedproperty 'MS_Description', N'Kapandı mı', 'schema', stg, 'table', [Project], 'column', [IsClosed];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Project], 'column', [AdditionalText1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Project], 'column', [AdditionalText2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Project], 'column', [AdditionalText3];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Project], 'column', [AdditionalText4];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Project], 'column', [AdditionalText5];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Project], 'column', [AdditionalText6];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Project], 'column', [AdditionalText7];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Project], 'column', [AdditionalNumber1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Project], 'column', [AdditionalNumber2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Project], 'column', [AdditionalNumber3];

GO

CREATE UNIQUE INDEX [UX_Project_Code] ON stg.[Project] ([Code]);

GO

CREATE TABLE stg.[ProjectGroup] (
    [StagingRowId] BIGINT NOT NULL IDENTITY, 
    [ImportBatchId] BIGINT NOT NULL, 
    [RowStatus] NVARCHAR(15) NOT NULL, 
    [ErrorText] NVARCHAR(400) NULL, 
    [Code] NVARCHAR(50) NULL, 
    [Name] NVARCHAR(200) NULL, 
    [IsolationRule] NVARCHAR(20) NULL, 
    CONSTRAINT [PK_ProjectGroup] PRIMARY KEY ([StagingRowId]), 
    CONSTRAINT [FK_ProjectGroup_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Proje grubu (grup içi paylaşım için).', 'schema', stg, 'table', [ProjectGroup];

GO

execute sp_addextendedproperty 'MS_Description', N'Satır kimliği', 'schema', stg, 'table', [ProjectGroup], 'column', [StagingRowId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yükleme partisi', 'schema', stg, 'table', [ProjectGroup], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yeni | Hatalı | Aktarıldı', 'schema', stg, 'table', [ProjectGroup], 'column', [RowStatus];

GO

execute sp_addextendedproperty 'MS_Description', N'Hata açıklaması', 'schema', stg, 'table', [ProjectGroup], 'column', [ErrorText];

GO

execute sp_addextendedproperty 'MS_Description', N'Grup kodu', 'schema', stg, 'table', [ProjectGroup], 'column', [Code];

GO

execute sp_addextendedproperty 'MS_Description', N'Proje grubu adı', 'schema', stg, 'table', [ProjectGroup], 'column', [Name];

GO

execute sp_addextendedproperty 'MS_Description', N'Tam izolasyon | Ortaktan beslenir | Grup içi paylaşım', 'schema', stg, 'table', [ProjectGroup], 'column', [IsolationRule];

GO

CREATE UNIQUE INDEX [UX_ProjectGroup_Code] ON stg.[ProjectGroup] ([Code]);

GO

CREATE TABLE stg.[PurchaseOrderLine] (
    [StagingRowId] BIGINT NOT NULL IDENTITY, 
    [ImportBatchId] BIGINT NOT NULL, 
    [RowStatus] NVARCHAR(15) NOT NULL, 
    [ErrorText] NVARCHAR(400) NULL, 
    [LocationCode] NVARCHAR(30) NULL, 
    [OrderNo] NVARCHAR(30) NULL, 
    [LineNo] INTEGER NULL, 
    [OrderType] NVARCHAR(15) NULL, 
    [SupplierCode] NVARCHAR(50) NULL, 
    [MaterialCode] NVARCHAR(50) NULL, 
    [OpenQty] NUMERIC(18, 4) NULL, 
    [RequestedDate] DATE NULL, 
    [ConfirmedDate] DATE NULL, 
    [ProjectCode] NVARCHAR(50) NULL, 
    [WorkOrderNo] NVARCHAR(30) NULL, 
    [Status] NVARCHAR(15) NULL, 
    [AdditionalText1] NVARCHAR(255) NULL, 
    [AdditionalText2] NVARCHAR(255) NULL, 
    [AdditionalText3] NVARCHAR(255) NULL, 
    [AdditionalNumber1] NUMERIC(18, 4) NULL, 
    [AdditionalNumber2] NUMERIC(18, 4) NULL, 
    CONSTRAINT [PK_PurchaseOrderLine] PRIMARY KEY ([StagingRowId]), 
    CONSTRAINT [FK_PurchaseOrderLine_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Açık satın alma ve fason siparişi satırı (ve talep).', 'schema', stg, 'table', [PurchaseOrderLine];

GO

execute sp_addextendedproperty 'MS_Description', N'Satır kimliği', 'schema', stg, 'table', [PurchaseOrderLine], 'column', [StagingRowId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yükleme partisi', 'schema', stg, 'table', [PurchaseOrderLine], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yeni | Hatalı | Aktarıldı', 'schema', stg, 'table', [PurchaseOrderLine], 'column', [RowStatus];

GO

execute sp_addextendedproperty 'MS_Description', N'Hata açıklaması', 'schema', stg, 'table', [PurchaseOrderLine], 'column', [ErrorText];

GO

execute sp_addextendedproperty 'MS_Description', N'Lokasyon kodu', 'schema', stg, 'table', [PurchaseOrderLine], 'column', [LocationCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Sipariş no', 'schema', stg, 'table', [PurchaseOrderLine], 'column', [OrderNo];

GO

execute sp_addextendedproperty 'MS_Description', N'Satır no', 'schema', stg, 'table', [PurchaseOrderLine], 'column', [LineNo];

GO

execute sp_addextendedproperty 'MS_Description', N'Satın alma talebi | Satın alma | Fason', 'schema', stg, 'table', [PurchaseOrderLine], 'column', [OrderType];

GO

execute sp_addextendedproperty 'MS_Description', N'Tedarikçi', 'schema', stg, 'table', [PurchaseOrderLine], 'column', [SupplierCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Malzeme', 'schema', stg, 'table', [PurchaseOrderLine], 'column', [MaterialCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Açık miktar', 'schema', stg, 'table', [PurchaseOrderLine], 'column', [OpenQty];

GO

execute sp_addextendedproperty 'MS_Description', N'İstenen tarih', 'schema', stg, 'table', [PurchaseOrderLine], 'column', [RequestedDate];

GO

execute sp_addextendedproperty 'MS_Description', N'Tedarikçi teyit tarihi', 'schema', stg, 'table', [PurchaseOrderLine], 'column', [ConfirmedDate];

GO

execute sp_addextendedproperty 'MS_Description', N'Proje', 'schema', stg, 'table', [PurchaseOrderLine], 'column', [ProjectCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Fasonda bağlı iş emri', 'schema', stg, 'table', [PurchaseOrderLine], 'column', [WorkOrderNo];

GO

execute sp_addextendedproperty 'MS_Description', N'Durum', 'schema', stg, 'table', [PurchaseOrderLine], 'column', [Status];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [PurchaseOrderLine], 'column', [AdditionalText1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [PurchaseOrderLine], 'column', [AdditionalText2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [PurchaseOrderLine], 'column', [AdditionalText3];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [PurchaseOrderLine], 'column', [AdditionalNumber1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [PurchaseOrderLine], 'column', [AdditionalNumber2];

GO

CREATE UNIQUE INDEX [UX_PurchaseOrderLine_OrderNo_LineNo] ON stg.[PurchaseOrderLine] ([OrderNo], [LineNo]);

GO

CREATE TABLE stg.[Resource] (
    [StagingRowId] BIGINT NOT NULL IDENTITY, 
    [ImportBatchId] BIGINT NOT NULL, 
    [RowStatus] NVARCHAR(15) NOT NULL, 
    [ErrorText] NVARCHAR(400) NULL, 
    [LocationCode] NVARCHAR(30) NULL, 
    [Code] NVARCHAR(50) NULL, 
    [Name] NVARCHAR(150) NULL, 
    [ResourceGroupCode] NVARCHAR(50) NULL, 
    [ResourceType] NVARCHAR(20) NULL, 
    [ResourceRole] NVARCHAR(10) NULL, 
    [IsConstrained] BIT NULL, 
    [CapacityUnit] NVARCHAR(10) NULL, 
    [DailyCapacity] NUMERIC(18, 4) NULL, 
    [Quantity] INTEGER NULL, 
    [CapacitySource] NVARCHAR(10) NULL, 
    [SubconPlanningType] NVARCHAR(15) NULL, 
    [SupplierCode] NVARCHAR(50) NULL, 
    [SubconFixedLeadTimeDays] NUMERIC(9, 2) NULL, 
    [SubconVariableDaysPerUnit] NUMERIC(18, 6) NULL, 
    [AdditionalText1] NVARCHAR(255) NULL, 
    [AdditionalText2] NVARCHAR(255) NULL, 
    [AdditionalText3] NVARCHAR(255) NULL, 
    [AdditionalText4] NVARCHAR(255) NULL, 
    [AdditionalText5] NVARCHAR(255) NULL, 
    [AdditionalText6] NVARCHAR(255) NULL, 
    [AdditionalText7] NVARCHAR(255) NULL, 
    [AdditionalNumber1] NUMERIC(18, 4) NULL, 
    [AdditionalNumber2] NUMERIC(18, 4) NULL, 
    [AdditionalNumber3] NUMERIC(18, 4) NULL, 
    CONSTRAINT [PK_Resource] PRIMARY KEY ([StagingRowId]), 
    CONSTRAINT [FK_Resource_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Kaynak: makine, işçi, fason, diğer. Kapasite kaynağın kendi biriminde günlük kapasite olarak tutulur.', 'schema', stg, 'table', [Resource];

GO

execute sp_addextendedproperty 'MS_Description', N'Satır kimliği', 'schema', stg, 'table', [Resource], 'column', [StagingRowId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yükleme partisi', 'schema', stg, 'table', [Resource], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yeni | Hatalı | Aktarıldı', 'schema', stg, 'table', [Resource], 'column', [RowStatus];

GO

execute sp_addextendedproperty 'MS_Description', N'Hata açıklaması', 'schema', stg, 'table', [Resource], 'column', [ErrorText];

GO

execute sp_addextendedproperty 'MS_Description', N'Lokasyon kodu', 'schema', stg, 'table', [Resource], 'column', [LocationCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaynak kodu', 'schema', stg, 'table', [Resource], 'column', [Code];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaynak adı', 'schema', stg, 'table', [Resource], 'column', [Name];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaynak grubu', 'schema', stg, 'table', [Resource], 'column', [ResourceGroupCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Makine | İşçi | Fason | Kalıp | Fırın | Diğer', 'schema', stg, 'table', [Resource], 'column', [ResourceType];

GO

execute sp_addextendedproperty 'MS_Description', N'Primary | Secondary', 'schema', stg, 'table', [Resource], 'column', [ResourceRole];

GO

execute sp_addextendedproperty 'MS_Description', N'1: planda kısıt, 0: sonsuz kapasite (sadece raporlanır)', 'schema', stg, 'table', [Resource], 'column', [IsConstrained];

GO

execute sp_addextendedproperty 'MS_Description', N'Kapasite birimi (Saat, Adet, Ton…); rotadaki tüketim aynı birimde kabul edilir', 'schema', stg, 'table', [Resource], 'column', [CapacityUnit];

GO

execute sp_addextendedproperty 'MS_Description', N'Bir adet kaynağın bir çalışma günündeki kapasitesi', 'schema', stg, 'table', [Resource], 'column', [DailyCapacity];

GO

execute sp_addextendedproperty 'MS_Description', N'Paralel kaynak adedi', 'schema', stg, 'table', [Resource], 'column', [Quantity];

GO

execute sp_addextendedproperty 'MS_Description', N'İşçi gruplarında: Vardiyadan | Doğrudan', 'schema', stg, 'table', [Resource], 'column', [CapacitySource];

GO

execute sp_addextendedproperty 'MS_Description', N'Fasonda: İş yeri | Tedarik süresi', 'schema', stg, 'table', [Resource], 'column', [SubconPlanningType];

GO

execute sp_addextendedproperty 'MS_Description', N'Fasonda fasoncu', 'schema', stg, 'table', [Resource], 'column', [SupplierCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Fasonda sabit süre (taşıma ve kuyruk)', 'schema', stg, 'table', [Resource], 'column', [SubconFixedLeadTimeDays];

GO

execute sp_addextendedproperty 'MS_Description', N'Fasonda birim başına gün (fasoncunun hızı)', 'schema', stg, 'table', [Resource], 'column', [SubconVariableDaysPerUnit];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Resource], 'column', [AdditionalText1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Resource], 'column', [AdditionalText2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Resource], 'column', [AdditionalText3];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Resource], 'column', [AdditionalText4];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Resource], 'column', [AdditionalText5];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Resource], 'column', [AdditionalText6];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Resource], 'column', [AdditionalText7];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Resource], 'column', [AdditionalNumber1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Resource], 'column', [AdditionalNumber2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Resource], 'column', [AdditionalNumber3];

GO

CREATE UNIQUE INDEX [UX_Resource_Code] ON stg.[Resource] ([Code]);

GO

CREATE TABLE stg.[ResourceGroup] (
    [StagingRowId] BIGINT NOT NULL IDENTITY, 
    [ImportBatchId] BIGINT NOT NULL, 
    [RowStatus] NVARCHAR(15) NOT NULL, 
    [ErrorText] NVARCHAR(400) NULL, 
    [LocationCode] NVARCHAR(30) NULL, 
    [Code] NVARCHAR(50) NULL, 
    [Name] NVARCHAR(150) NULL, 
    [AdditionalText1] NVARCHAR(255) NULL, 
    [AdditionalText2] NVARCHAR(255) NULL, 
    [AdditionalText3] NVARCHAR(255) NULL, 
    [AdditionalText4] NVARCHAR(255) NULL, 
    [AdditionalText5] NVARCHAR(255) NULL, 
    [AdditionalText6] NVARCHAR(255) NULL, 
    [AdditionalText7] NVARCHAR(255) NULL, 
    [AdditionalNumber1] NUMERIC(18, 4) NULL, 
    [AdditionalNumber2] NUMERIC(18, 4) NULL, 
    [AdditionalNumber3] NUMERIC(18, 4) NULL, 
    CONSTRAINT [PK_ResourceGroup] PRIMARY KEY ([StagingRowId]), 
    CONSTRAINT [FK_ResourceGroup_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Kaynak grubu (makine grubu, işçi kaynak grubu).', 'schema', stg, 'table', [ResourceGroup];

GO

execute sp_addextendedproperty 'MS_Description', N'Satır kimliği', 'schema', stg, 'table', [ResourceGroup], 'column', [StagingRowId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yükleme partisi', 'schema', stg, 'table', [ResourceGroup], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yeni | Hatalı | Aktarıldı', 'schema', stg, 'table', [ResourceGroup], 'column', [RowStatus];

GO

execute sp_addextendedproperty 'MS_Description', N'Hata açıklaması', 'schema', stg, 'table', [ResourceGroup], 'column', [ErrorText];

GO

execute sp_addextendedproperty 'MS_Description', N'Lokasyon kodu', 'schema', stg, 'table', [ResourceGroup], 'column', [LocationCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Grup kodu', 'schema', stg, 'table', [ResourceGroup], 'column', [Code];

GO

execute sp_addextendedproperty 'MS_Description', N'Grup adı', 'schema', stg, 'table', [ResourceGroup], 'column', [Name];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [ResourceGroup], 'column', [AdditionalText1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [ResourceGroup], 'column', [AdditionalText2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [ResourceGroup], 'column', [AdditionalText3];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [ResourceGroup], 'column', [AdditionalText4];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [ResourceGroup], 'column', [AdditionalText5];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [ResourceGroup], 'column', [AdditionalText6];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [ResourceGroup], 'column', [AdditionalText7];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [ResourceGroup], 'column', [AdditionalNumber1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [ResourceGroup], 'column', [AdditionalNumber2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [ResourceGroup], 'column', [AdditionalNumber3];

GO

CREATE UNIQUE INDEX [UX_ResourceGroup_Code] ON stg.[ResourceGroup] ([Code]);

GO

CREATE TABLE stg.[Routing] (
    [StagingRowId] BIGINT NOT NULL IDENTITY, 
    [ImportBatchId] BIGINT NOT NULL, 
    [RowStatus] NVARCHAR(15) NOT NULL, 
    [ErrorText] NVARCHAR(400) NULL, 
    [RouteCode] NVARCHAR(50) NULL, 
    [OpNo] INTEGER NULL, 
    [SeqNo] INTEGER NULL, 
    [OperationName] NVARCHAR(150) NULL, 
    [ResourceCode] NVARCHAR(50) NULL, 
    [ResourceRole] NVARCHAR(10) NULL, 
    [Consumption] NUMERIC(18, 6) NULL, 
    [ResourceNumber] INTEGER NULL, 
    [IsSubcontracted] BIT NULL, 
    [TransferLotQty] NUMERIC(18, 4) NULL, 
    [LaborType] NVARCHAR(15) NULL, 
    [LaborRefCode] NVARCHAR(50) NULL, 
    [LaborBasis] NVARCHAR(10) NULL, 
    [CrewSize] INTEGER NULL, 
    [LaborTime] NUMERIC(18, 6) NULL, 
    [AdditionalText1] NVARCHAR(255) NULL, 
    [AdditionalText2] NVARCHAR(255) NULL, 
    [AdditionalText3] NVARCHAR(255) NULL, 
    [AdditionalNumber1] NUMERIC(18, 4) NULL, 
    [AdditionalNumber2] NUMERIC(18, 4) NULL, 
    CONSTRAINT [PK_Routing] PRIMARY KEY ([StagingRowId]), 
    CONSTRAINT [FK_Routing_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Rota: her satır bir operasyon–kaynak ilişkisi; sıra önce OpNo, sonra SeqNo. Aynı operasyonun kaynakları ayrı satırda, ResourceRole ile.', 'schema', stg, 'table', [Routing];

GO

execute sp_addextendedproperty 'MS_Description', N'Satır kimliği', 'schema', stg, 'table', [Routing], 'column', [StagingRowId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yükleme partisi', 'schema', stg, 'table', [Routing], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yeni | Hatalı | Aktarıldı', 'schema', stg, 'table', [Routing], 'column', [RowStatus];

GO

execute sp_addextendedproperty 'MS_Description', N'Hata açıklaması', 'schema', stg, 'table', [Routing], 'column', [ErrorText];

GO

execute sp_addextendedproperty 'MS_Description', N'Rota kodu', 'schema', stg, 'table', [Routing], 'column', [RouteCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Operasyon no (birinci sıralama)', 'schema', stg, 'table', [Routing], 'column', [OpNo];

GO

execute sp_addextendedproperty 'MS_Description', N'Operasyon içindeki alt sıra (ikinci sıralama)', 'schema', stg, 'table', [Routing], 'column', [SeqNo];

GO

execute sp_addextendedproperty 'MS_Description', N'Operasyon adı', 'schema', stg, 'table', [Routing], 'column', [OperationName];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaynak kodu', 'schema', stg, 'table', [Routing], 'column', [ResourceCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Primary | Secondary', 'schema', stg, 'table', [Routing], 'column', [ResourceRole];

GO

execute sp_addextendedproperty 'MS_Description', N'Baz miktar için kaynak tüketimi (kaynağın kapasite biriminde)', 'schema', stg, 'table', [Routing], 'column', [Consumption];

GO

execute sp_addextendedproperty 'MS_Description', N'Operasyonda aynı anda kullanılan kaynak adedi', 'schema', stg, 'table', [Routing], 'column', [ResourceNumber];

GO

execute sp_addextendedproperty 'MS_Description', N'Fason operasyon', 'schema', stg, 'table', [Routing], 'column', [IsSubcontracted];

GO

execute sp_addextendedproperty 'MS_Description', N'Transfer partisi', 'schema', stg, 'table', [Routing], 'column', [TransferLotQty];

GO

execute sp_addextendedproperty 'MS_Description', N'İşçi: Yetkinlik grubu | Kaynak grubu | Yok', 'schema', stg, 'table', [Routing], 'column', [LaborType];

GO

execute sp_addextendedproperty 'MS_Description', N'İlgili yetkinlik ya da kaynak grubu', 'schema', stg, 'table', [Routing], 'column', [LaborRefCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Ekip (süre × kişi) | Toplam (adam-saat)', 'schema', stg, 'table', [Routing], 'column', [LaborBasis];

GO

execute sp_addextendedproperty 'MS_Description', N'Gerekli işçi sayısı', 'schema', stg, 'table', [Routing], 'column', [CrewSize];

GO

execute sp_addextendedproperty 'MS_Description', N'Toplam işçilik (adam-saat), LaborBasis = Toplam ise', 'schema', stg, 'table', [Routing], 'column', [LaborTime];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Routing], 'column', [AdditionalText1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Routing], 'column', [AdditionalText2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Routing], 'column', [AdditionalText3];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Routing], 'column', [AdditionalNumber1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Routing], 'column', [AdditionalNumber2];

GO

CREATE UNIQUE INDEX [UX_Routing_RouteCode_OpNo_SeqNo] ON stg.[Routing] ([RouteCode], [OpNo], [SeqNo]);

GO

CREATE TABLE stg.[SalesOrderLine] (
    [StagingRowId] BIGINT NOT NULL IDENTITY, 
    [ImportBatchId] BIGINT NOT NULL, 
    [RowStatus] NVARCHAR(15) NOT NULL, 
    [ErrorText] NVARCHAR(400) NULL, 
    [LocationCode] NVARCHAR(30) NULL, 
    [OrderNo] NVARCHAR(30) NULL, 
    [LineNo] INTEGER NULL, 
    [LineItemNo] INTEGER NULL, 
    [Type] NVARCHAR(10) NULL, 
    [CustomerCode] NVARCHAR(50) NULL, 
    [MaterialCode] NVARCHAR(50) NULL, 
    [ProjectCode] NVARCHAR(50) NULL, 
    [OpenQty] NUMERIC(18, 4) NULL, 
    [RequestedDate] DATE NULL, 
    [ConfirmedDate] DATE NULL, 
    [Priority] INTEGER NULL, 
    [AllowPartialDelivery] BIT NULL, 
    [Status] NVARCHAR(15) NULL, 
    [AdditionalText1] NVARCHAR(255) NULL, 
    [AdditionalText2] NVARCHAR(255) NULL, 
    [AdditionalText3] NVARCHAR(255) NULL, 
    [AdditionalNumber1] NUMERIC(18, 4) NULL, 
    [AdditionalNumber2] NUMERIC(18, 4) NULL, 
    CONSTRAINT [PK_SalesOrderLine] PRIMARY KEY ([StagingRowId]), 
    CONSTRAINT [FK_SalesOrderLine_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Müşteri sipariş satırı; teklifler Type = Teklif ile gelir. Vade: teyit tarihi, yoksa istek tarihi.', 'schema', stg, 'table', [SalesOrderLine];

GO

execute sp_addextendedproperty 'MS_Description', N'Satır kimliği', 'schema', stg, 'table', [SalesOrderLine], 'column', [StagingRowId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yükleme partisi', 'schema', stg, 'table', [SalesOrderLine], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yeni | Hatalı | Aktarıldı', 'schema', stg, 'table', [SalesOrderLine], 'column', [RowStatus];

GO

execute sp_addextendedproperty 'MS_Description', N'Hata açıklaması', 'schema', stg, 'table', [SalesOrderLine], 'column', [ErrorText];

GO

execute sp_addextendedproperty 'MS_Description', N'Lokasyon kodu', 'schema', stg, 'table', [SalesOrderLine], 'column', [LocationCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Sipariş no', 'schema', stg, 'table', [SalesOrderLine], 'column', [OrderNo];

GO

execute sp_addextendedproperty 'MS_Description', N'Satır no', 'schema', stg, 'table', [SalesOrderLine], 'column', [LineNo];

GO

execute sp_addextendedproperty 'MS_Description', N'Alt satır no (ERP satırı kırılımlıysa)', 'schema', stg, 'table', [SalesOrderLine], 'column', [LineItemNo];

GO

execute sp_addextendedproperty 'MS_Description', N'Kesin | Teklif', 'schema', stg, 'table', [SalesOrderLine], 'column', [Type];

GO

execute sp_addextendedproperty 'MS_Description', N'Müşteri kodu', 'schema', stg, 'table', [SalesOrderLine], 'column', [CustomerCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Malzeme', 'schema', stg, 'table', [SalesOrderLine], 'column', [MaterialCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Proje', 'schema', stg, 'table', [SalesOrderLine], 'column', [ProjectCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Açık miktar', 'schema', stg, 'table', [SalesOrderLine], 'column', [OpenQty];

GO

execute sp_addextendedproperty 'MS_Description', N'İstek tarihi', 'schema', stg, 'table', [SalesOrderLine], 'column', [RequestedDate];

GO

execute sp_addextendedproperty 'MS_Description', N'Teyit tarihi', 'schema', stg, 'table', [SalesOrderLine], 'column', [ConfirmedDate];

GO

execute sp_addextendedproperty 'MS_Description', N'Satır önceliği', 'schema', stg, 'table', [SalesOrderLine], 'column', [Priority];

GO

execute sp_addextendedproperty 'MS_Description', N'Kısmi teslimat (müşteriyi ezer)', 'schema', stg, 'table', [SalesOrderLine], 'column', [AllowPartialDelivery];

GO

execute sp_addextendedproperty 'MS_Description', N'Açık | Kapandı | İptal', 'schema', stg, 'table', [SalesOrderLine], 'column', [Status];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [SalesOrderLine], 'column', [AdditionalText1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [SalesOrderLine], 'column', [AdditionalText2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [SalesOrderLine], 'column', [AdditionalText3];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [SalesOrderLine], 'column', [AdditionalNumber1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [SalesOrderLine], 'column', [AdditionalNumber2];

GO

CREATE UNIQUE INDEX [UX_SalesOrderLine_OrderNo_LineNo_LineItemNo] ON stg.[SalesOrderLine] ([OrderNo], [LineNo], [LineItemNo]);

GO

CREATE TABLE stg.[Stock] (
    [StagingRowId] BIGINT NOT NULL IDENTITY, 
    [ImportBatchId] BIGINT NOT NULL, 
    [RowStatus] NVARCHAR(15) NOT NULL, 
    [ErrorText] NVARCHAR(400) NULL, 
    [LocationCode] NVARCHAR(30) NULL, 
    [MaterialCode] NVARCHAR(50) NULL, 
    [Warehouse] NVARCHAR(30) NULL, 
    [LotNo] NVARCHAR(50) NULL, 
    [StockStatus] NVARCHAR(15) NULL, 
    [ProjectCode] NVARCHAR(50) NULL, 
    [Quantity] NUMERIC(18, 4) NULL, 
    [QualityEntryDate] DATE NULL, 
    [ExpiryDate] DATE NULL, 
    [AdditionalText1] NVARCHAR(255) NULL, 
    [AdditionalText2] NVARCHAR(255) NULL, 
    [AdditionalText3] NVARCHAR(255) NULL, 
    [AdditionalNumber1] NUMERIC(18, 4) NULL, 
    [AdditionalNumber2] NUMERIC(18, 4) NULL, 
    CONSTRAINT [PK_Stock] PRIMARY KEY ([StagingRowId]), 
    CONSTRAINT [FK_Stock_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Stok; lot ve durum bazında. Sahip: proje ya da ortak.', 'schema', stg, 'table', [Stock];

GO

execute sp_addextendedproperty 'MS_Description', N'Satır kimliği', 'schema', stg, 'table', [Stock], 'column', [StagingRowId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yükleme partisi', 'schema', stg, 'table', [Stock], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yeni | Hatalı | Aktarıldı', 'schema', stg, 'table', [Stock], 'column', [RowStatus];

GO

execute sp_addextendedproperty 'MS_Description', N'Hata açıklaması', 'schema', stg, 'table', [Stock], 'column', [ErrorText];

GO

execute sp_addextendedproperty 'MS_Description', N'Lokasyon kodu', 'schema', stg, 'table', [Stock], 'column', [LocationCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Malzeme', 'schema', stg, 'table', [Stock], 'column', [MaterialCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Depo', 'schema', stg, 'table', [Stock], 'column', [Warehouse];

GO

execute sp_addextendedproperty 'MS_Description', N'Lot / seri', 'schema', stg, 'table', [Stock], 'column', [LotNo];

GO

execute sp_addextendedproperty 'MS_Description', N'Serbest | Kalitede | Bloke', 'schema', stg, 'table', [Stock], 'column', [StockStatus];

GO

execute sp_addextendedproperty 'MS_Description', N'Sahip proje (boşsa ortak)', 'schema', stg, 'table', [Stock], 'column', [ProjectCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Miktar', 'schema', stg, 'table', [Stock], 'column', [Quantity];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaliteye giriş tarihi', 'schema', stg, 'table', [Stock], 'column', [QualityEntryDate];

GO

execute sp_addextendedproperty 'MS_Description', N'Son kullanma tarihi (raf ömrü sonraki faz)', 'schema', stg, 'table', [Stock], 'column', [ExpiryDate];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Stock], 'column', [AdditionalText1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Stock], 'column', [AdditionalText2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Stock], 'column', [AdditionalText3];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Stock], 'column', [AdditionalNumber1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Stock], 'column', [AdditionalNumber2];

GO

CREATE TABLE stg.[Supplier] (
    [StagingRowId] BIGINT NOT NULL IDENTITY, 
    [ImportBatchId] BIGINT NOT NULL, 
    [RowStatus] NVARCHAR(15) NOT NULL, 
    [ErrorText] NVARCHAR(400) NULL, 
    [Code] NVARCHAR(50) NULL, 
    [Name] NVARCHAR(200) NULL, 
    [IsSubcontractor] BIT NULL, 
    [AdditionalText1] NVARCHAR(255) NULL, 
    [AdditionalText2] NVARCHAR(255) NULL, 
    [AdditionalText3] NVARCHAR(255) NULL, 
    [AdditionalText4] NVARCHAR(255) NULL, 
    [AdditionalText5] NVARCHAR(255) NULL, 
    [AdditionalText6] NVARCHAR(255) NULL, 
    [AdditionalText7] NVARCHAR(255) NULL, 
    [AdditionalNumber1] NUMERIC(18, 4) NULL, 
    [AdditionalNumber2] NUMERIC(18, 4) NULL, 
    [AdditionalNumber3] NUMERIC(18, 4) NULL, 
    CONSTRAINT [PK_Supplier] PRIMARY KEY ([StagingRowId]), 
    CONSTRAINT [FK_Supplier_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Tedarikçi ve fasoncu.', 'schema', stg, 'table', [Supplier];

GO

execute sp_addextendedproperty 'MS_Description', N'Satır kimliği', 'schema', stg, 'table', [Supplier], 'column', [StagingRowId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yükleme partisi', 'schema', stg, 'table', [Supplier], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yeni | Hatalı | Aktarıldı', 'schema', stg, 'table', [Supplier], 'column', [RowStatus];

GO

execute sp_addextendedproperty 'MS_Description', N'Hata açıklaması', 'schema', stg, 'table', [Supplier], 'column', [ErrorText];

GO

execute sp_addextendedproperty 'MS_Description', N'Tedarikçi kodu', 'schema', stg, 'table', [Supplier], 'column', [Code];

GO

execute sp_addextendedproperty 'MS_Description', N'Ad', 'schema', stg, 'table', [Supplier], 'column', [Name];

GO

execute sp_addextendedproperty 'MS_Description', N'Fasoncu mu', 'schema', stg, 'table', [Supplier], 'column', [IsSubcontractor];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Supplier], 'column', [AdditionalText1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Supplier], 'column', [AdditionalText2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Supplier], 'column', [AdditionalText3];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Supplier], 'column', [AdditionalText4];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Supplier], 'column', [AdditionalText5];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Supplier], 'column', [AdditionalText6];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Supplier], 'column', [AdditionalText7];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Supplier], 'column', [AdditionalNumber1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Supplier], 'column', [AdditionalNumber2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Supplier], 'column', [AdditionalNumber3];

GO

CREATE UNIQUE INDEX [UX_Supplier_Code] ON stg.[Supplier] ([Code]);

GO

CREATE TABLE stg.[UnitOfMeasure] (
    [StagingRowId] BIGINT NOT NULL IDENTITY, 
    [ImportBatchId] BIGINT NOT NULL, 
    [RowStatus] NVARCHAR(15) NOT NULL, 
    [ErrorText] NVARCHAR(400) NULL, 
    [Code] NVARCHAR(10) NULL, 
    [Name] NVARCHAR(50) NULL, 
    CONSTRAINT [PK_UnitOfMeasure] PRIMARY KEY ([StagingRowId]), 
    CONSTRAINT [FK_UnitOfMeasure_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Ölçü birimi.', 'schema', stg, 'table', [UnitOfMeasure];

GO

execute sp_addextendedproperty 'MS_Description', N'Satır kimliği', 'schema', stg, 'table', [UnitOfMeasure], 'column', [StagingRowId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yükleme partisi', 'schema', stg, 'table', [UnitOfMeasure], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yeni | Hatalı | Aktarıldı', 'schema', stg, 'table', [UnitOfMeasure], 'column', [RowStatus];

GO

execute sp_addextendedproperty 'MS_Description', N'Hata açıklaması', 'schema', stg, 'table', [UnitOfMeasure], 'column', [ErrorText];

GO

execute sp_addextendedproperty 'MS_Description', N'Birim kodu (AD, KG, SAAT…)', 'schema', stg, 'table', [UnitOfMeasure], 'column', [Code];

GO

execute sp_addextendedproperty 'MS_Description', N'Birim adı', 'schema', stg, 'table', [UnitOfMeasure], 'column', [Name];

GO

CREATE TABLE stg.[UomConversion] (
    [StagingRowId] BIGINT NOT NULL IDENTITY, 
    [ImportBatchId] BIGINT NOT NULL, 
    [RowStatus] NVARCHAR(15) NOT NULL, 
    [ErrorText] NVARCHAR(400) NULL, 
    [MaterialCode] NVARCHAR(50) NULL, 
    [FromUom] NVARCHAR(10) NULL, 
    [ToUom] NVARCHAR(10) NULL, 
    [Factor] NUMERIC(18, 6) NULL, 
    CONSTRAINT [PK_UomConversion] PRIMARY KEY ([StagingRowId]), 
    CONSTRAINT [FK_UomConversion_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Malzeme bazında birim dönüşümü.', 'schema', stg, 'table', [UomConversion];

GO

execute sp_addextendedproperty 'MS_Description', N'Satır kimliği', 'schema', stg, 'table', [UomConversion], 'column', [StagingRowId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yükleme partisi', 'schema', stg, 'table', [UomConversion], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yeni | Hatalı | Aktarıldı', 'schema', stg, 'table', [UomConversion], 'column', [RowStatus];

GO

execute sp_addextendedproperty 'MS_Description', N'Hata açıklaması', 'schema', stg, 'table', [UomConversion], 'column', [ErrorText];

GO

execute sp_addextendedproperty 'MS_Description', N'Malzeme (boşsa genel dönüşüm)', 'schema', stg, 'table', [UomConversion], 'column', [MaterialCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaynak birim', 'schema', stg, 'table', [UomConversion], 'column', [FromUom];

GO

execute sp_addextendedproperty 'MS_Description', N'Hedef birim', 'schema', stg, 'table', [UomConversion], 'column', [ToUom];

GO

execute sp_addextendedproperty 'MS_Description', N'Çarpan', 'schema', stg, 'table', [UomConversion], 'column', [Factor];

GO

CREATE TABLE stg.[WorkOrder] (
    [StagingRowId] BIGINT NOT NULL IDENTITY, 
    [ImportBatchId] BIGINT NOT NULL, 
    [RowStatus] NVARCHAR(15) NOT NULL, 
    [ErrorText] NVARCHAR(400) NULL, 
    [LocationCode] NVARCHAR(30) NULL, 
    [OrderNo] NVARCHAR(30) NULL, 
    [MaterialCode] NVARCHAR(50) NULL, 
    [OrderType] NVARCHAR(15) NULL, 
    [Status] NVARCHAR(15) NULL, 
    [OrderQty] NUMERIC(18, 4) NULL, 
    [OpenQty] NUMERIC(18, 4) NULL, 
    [StartDate] DATE NULL, 
    [DueDate] DATE NULL, 
    [ProjectCode] NVARCHAR(50) NULL, 
    [SalesOrderNo] NVARCHAR(30) NULL, 
    [SalesOrderLineNo] INTEGER NULL, 
    [ParentWorkOrderNo] NVARCHAR(30) NULL, 
    [LastActivityDate] DATE NULL, 
    [AdditionalText1] NVARCHAR(255) NULL, 
    [AdditionalText2] NVARCHAR(255) NULL, 
    [AdditionalText3] NVARCHAR(255) NULL, 
    [AdditionalNumber1] NUMERIC(18, 4) NULL, 
    [AdditionalNumber2] NUMERIC(18, 4) NULL, 
    CONSTRAINT [PK_WorkOrder] PRIMARY KEY ([StagingRowId]), 
    CONSTRAINT [FK_WorkOrder_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Açık iş emri (üretim, fason, yeniden işleme).', 'schema', stg, 'table', [WorkOrder];

GO

execute sp_addextendedproperty 'MS_Description', N'Satır kimliği', 'schema', stg, 'table', [WorkOrder], 'column', [StagingRowId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yükleme partisi', 'schema', stg, 'table', [WorkOrder], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yeni | Hatalı | Aktarıldı', 'schema', stg, 'table', [WorkOrder], 'column', [RowStatus];

GO

execute sp_addextendedproperty 'MS_Description', N'Hata açıklaması', 'schema', stg, 'table', [WorkOrder], 'column', [ErrorText];

GO

execute sp_addextendedproperty 'MS_Description', N'Lokasyon kodu', 'schema', stg, 'table', [WorkOrder], 'column', [LocationCode];

GO

execute sp_addextendedproperty 'MS_Description', N'İş emri no', 'schema', stg, 'table', [WorkOrder], 'column', [OrderNo];

GO

execute sp_addextendedproperty 'MS_Description', N'Üretilen malzeme', 'schema', stg, 'table', [WorkOrder], 'column', [MaterialCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Üretim | Fason | Yeniden işleme', 'schema', stg, 'table', [WorkOrder], 'column', [OrderType];

GO

execute sp_addextendedproperty 'MS_Description', N'Planlı | Yayınlandı | Başladı | Kısmi | Bitti', 'schema', stg, 'table', [WorkOrder], 'column', [Status];

GO

execute sp_addextendedproperty 'MS_Description', N'İş emri miktarı', 'schema', stg, 'table', [WorkOrder], 'column', [OrderQty];

GO

execute sp_addextendedproperty 'MS_Description', N'Açık miktar', 'schema', stg, 'table', [WorkOrder], 'column', [OpenQty];

GO

execute sp_addextendedproperty 'MS_Description', N'Başlangıç', 'schema', stg, 'table', [WorkOrder], 'column', [StartDate];

GO

execute sp_addextendedproperty 'MS_Description', N'Bitiş', 'schema', stg, 'table', [WorkOrder], 'column', [DueDate];

GO

execute sp_addextendedproperty 'MS_Description', N'Proje (ayraç)', 'schema', stg, 'table', [WorkOrder], 'column', [ProjectCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Bağlı sipariş no (ayraç)', 'schema', stg, 'table', [WorkOrder], 'column', [SalesOrderNo];

GO

execute sp_addextendedproperty 'MS_Description', N'Bağlı sipariş satır no', 'schema', stg, 'table', [WorkOrder], 'column', [SalesOrderLineNo];

GO

execute sp_addextendedproperty 'MS_Description', N'Yeniden işlemede orijinal iş emri', 'schema', stg, 'table', [WorkOrder], 'column', [ParentWorkOrderNo];

GO

execute sp_addextendedproperty 'MS_Description', N'Son hareket tarihi (eskime kontrolü)', 'schema', stg, 'table', [WorkOrder], 'column', [LastActivityDate];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [WorkOrder], 'column', [AdditionalText1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [WorkOrder], 'column', [AdditionalText2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [WorkOrder], 'column', [AdditionalText3];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [WorkOrder], 'column', [AdditionalNumber1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [WorkOrder], 'column', [AdditionalNumber2];

GO

CREATE UNIQUE INDEX [UX_WorkOrder_OrderNo] ON stg.[WorkOrder] ([OrderNo]);

GO

CREATE TABLE stg.[WorkOrderComponent] (
    [StagingRowId] BIGINT NOT NULL IDENTITY, 
    [ImportBatchId] BIGINT NOT NULL, 
    [RowStatus] NVARCHAR(15) NOT NULL, 
    [ErrorText] NVARCHAR(400) NULL, 
    [WorkOrderNo] NVARCHAR(30) NULL, 
    [MaterialCode] NVARCHAR(50) NULL, 
    [RequiredQty] NUMERIC(18, 4) NULL, 
    [IssuedQty] NUMERIC(18, 4) NULL, 
    [AdditionalText1] NVARCHAR(255) NULL, 
    [AdditionalText2] NVARCHAR(255) NULL, 
    [AdditionalText3] NVARCHAR(255) NULL, 
    [AdditionalNumber1] NUMERIC(18, 4) NULL, 
    [AdditionalNumber2] NUMERIC(18, 4) NULL, 
    CONSTRAINT [PK_WorkOrderComponent] PRIMARY KEY ([StagingRowId]), 
    CONSTRAINT [FK_WorkOrderComponent_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'İş emrinin bileşenleri ve çekilen miktar.', 'schema', stg, 'table', [WorkOrderComponent];

GO

execute sp_addextendedproperty 'MS_Description', N'Satır kimliği', 'schema', stg, 'table', [WorkOrderComponent], 'column', [StagingRowId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yükleme partisi', 'schema', stg, 'table', [WorkOrderComponent], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yeni | Hatalı | Aktarıldı', 'schema', stg, 'table', [WorkOrderComponent], 'column', [RowStatus];

GO

execute sp_addextendedproperty 'MS_Description', N'Hata açıklaması', 'schema', stg, 'table', [WorkOrderComponent], 'column', [ErrorText];

GO

execute sp_addextendedproperty 'MS_Description', N'İş emri', 'schema', stg, 'table', [WorkOrderComponent], 'column', [WorkOrderNo];

GO

execute sp_addextendedproperty 'MS_Description', N'Bileşen', 'schema', stg, 'table', [WorkOrderComponent], 'column', [MaterialCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Gereken miktar', 'schema', stg, 'table', [WorkOrderComponent], 'column', [RequiredQty];

GO

execute sp_addextendedproperty 'MS_Description', N'Çekilen miktar', 'schema', stg, 'table', [WorkOrderComponent], 'column', [IssuedQty];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [WorkOrderComponent], 'column', [AdditionalText1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [WorkOrderComponent], 'column', [AdditionalText2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [WorkOrderComponent], 'column', [AdditionalText3];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [WorkOrderComponent], 'column', [AdditionalNumber1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [WorkOrderComponent], 'column', [AdditionalNumber2];

GO

CREATE TABLE stg.[WorkOrderOperation] (
    [StagingRowId] BIGINT NOT NULL IDENTITY, 
    [ImportBatchId] BIGINT NOT NULL, 
    [RowStatus] NVARCHAR(15) NOT NULL, 
    [ErrorText] NVARCHAR(400) NULL, 
    [WorkOrderNo] NVARCHAR(30) NULL, 
    [OpNo] INTEGER NULL, 
    [SeqNo] INTEGER NULL, 
    [ResourceCode] NVARCHAR(50) NULL, 
    [PlannedConsumption] NUMERIC(18, 6) NULL, 
    [ConfirmedConsumption] NUMERIC(18, 6) NULL, 
    [Status] NVARCHAR(15) NULL, 
    [AdditionalText1] NVARCHAR(255) NULL, 
    [AdditionalText2] NVARCHAR(255) NULL, 
    [AdditionalText3] NVARCHAR(255) NULL, 
    [AdditionalNumber1] NUMERIC(18, 4) NULL, 
    [AdditionalNumber2] NUMERIC(18, 4) NULL, 
    CONSTRAINT [PK_WorkOrderOperation] PRIMARY KEY ([StagingRowId]), 
    CONSTRAINT [FK_WorkOrderOperation_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'İş emrinin operasyonları ve kalan iş.', 'schema', stg, 'table', [WorkOrderOperation];

GO

execute sp_addextendedproperty 'MS_Description', N'Satır kimliği', 'schema', stg, 'table', [WorkOrderOperation], 'column', [StagingRowId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yükleme partisi', 'schema', stg, 'table', [WorkOrderOperation], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yeni | Hatalı | Aktarıldı', 'schema', stg, 'table', [WorkOrderOperation], 'column', [RowStatus];

GO

execute sp_addextendedproperty 'MS_Description', N'Hata açıklaması', 'schema', stg, 'table', [WorkOrderOperation], 'column', [ErrorText];

GO

execute sp_addextendedproperty 'MS_Description', N'İş emri', 'schema', stg, 'table', [WorkOrderOperation], 'column', [WorkOrderNo];

GO

execute sp_addextendedproperty 'MS_Description', N'Operasyon no', 'schema', stg, 'table', [WorkOrderOperation], 'column', [OpNo];

GO

execute sp_addextendedproperty 'MS_Description', N'Operasyon içindeki alt sıra', 'schema', stg, 'table', [WorkOrderOperation], 'column', [SeqNo];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaynak kodu', 'schema', stg, 'table', [WorkOrderOperation], 'column', [ResourceCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Planlanan tüketim', 'schema', stg, 'table', [WorkOrderOperation], 'column', [PlannedConsumption];

GO

execute sp_addextendedproperty 'MS_Description', N'Teyit edilen tüketim', 'schema', stg, 'table', [WorkOrderOperation], 'column', [ConfirmedConsumption];

GO

execute sp_addextendedproperty 'MS_Description', N'Açık | Bitti', 'schema', stg, 'table', [WorkOrderOperation], 'column', [Status];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [WorkOrderOperation], 'column', [AdditionalText1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [WorkOrderOperation], 'column', [AdditionalText2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [WorkOrderOperation], 'column', [AdditionalText3];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [WorkOrderOperation], 'column', [AdditionalNumber1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [WorkOrderOperation], 'column', [AdditionalNumber2];

GO

CREATE TABLE stg.[Worker] (
    [StagingRowId] BIGINT NOT NULL IDENTITY, 
    [ImportBatchId] BIGINT NOT NULL, 
    [RowStatus] NVARCHAR(15) NOT NULL, 
    [ErrorText] NVARCHAR(400) NULL, 
    [LocationCode] NVARCHAR(30) NULL, 
    [Code] NVARCHAR(50) NULL, 
    [Name] NVARCHAR(150) NULL, 
    [ResourceGroupCode] NVARCHAR(50) NULL, 
    [IsActive] BIT NULL, 
    [AdditionalText1] NVARCHAR(255) NULL, 
    [AdditionalText2] NVARCHAR(255) NULL, 
    [AdditionalText3] NVARCHAR(255) NULL, 
    [AdditionalText4] NVARCHAR(255) NULL, 
    [AdditionalText5] NVARCHAR(255) NULL, 
    [AdditionalText6] NVARCHAR(255) NULL, 
    [AdditionalText7] NVARCHAR(255) NULL, 
    [AdditionalNumber1] NUMERIC(18, 4) NULL, 
    [AdditionalNumber2] NUMERIC(18, 4) NULL, 
    [AdditionalNumber3] NUMERIC(18, 4) NULL, 
    CONSTRAINT [PK_Worker] PRIMARY KEY ([StagingRowId]), 
    CONSTRAINT [FK_Worker_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'İşçi.', 'schema', stg, 'table', [Worker];

GO

execute sp_addextendedproperty 'MS_Description', N'Satır kimliği', 'schema', stg, 'table', [Worker], 'column', [StagingRowId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yükleme partisi', 'schema', stg, 'table', [Worker], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yeni | Hatalı | Aktarıldı', 'schema', stg, 'table', [Worker], 'column', [RowStatus];

GO

execute sp_addextendedproperty 'MS_Description', N'Hata açıklaması', 'schema', stg, 'table', [Worker], 'column', [ErrorText];

GO

execute sp_addextendedproperty 'MS_Description', N'Lokasyon kodu', 'schema', stg, 'table', [Worker], 'column', [LocationCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Sicil no', 'schema', stg, 'table', [Worker], 'column', [Code];

GO

execute sp_addextendedproperty 'MS_Description', N'Ad', 'schema', stg, 'table', [Worker], 'column', [Name];

GO

execute sp_addextendedproperty 'MS_Description', N'Bağlı olduğu işçi kaynak grubu kodu', 'schema', stg, 'table', [Worker], 'column', [ResourceGroupCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Aktif mi', 'schema', stg, 'table', [Worker], 'column', [IsActive];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Worker], 'column', [AdditionalText1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Worker], 'column', [AdditionalText2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Worker], 'column', [AdditionalText3];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Worker], 'column', [AdditionalText4];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Worker], 'column', [AdditionalText5];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Worker], 'column', [AdditionalText6];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek metin alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Worker], 'column', [AdditionalText7];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Worker], 'column', [AdditionalNumber1];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Worker], 'column', [AdditionalNumber2];

GO

execute sp_addextendedproperty 'MS_Description', N'Ek sayı alanları; etiketi FieldDefinition''da', 'schema', stg, 'table', [Worker], 'column', [AdditionalNumber3];

GO

CREATE UNIQUE INDEX [UX_Worker_Code] ON stg.[Worker] ([Code]);

GO

CREATE TABLE stg.[WorkerAbsence] (
    [StagingRowId] BIGINT NOT NULL IDENTITY, 
    [ImportBatchId] BIGINT NOT NULL, 
    [RowStatus] NVARCHAR(15) NOT NULL, 
    [ErrorText] NVARCHAR(400) NULL, 
    [WorkerCode] NVARCHAR(50) NULL, 
    [StartAt] DATETIME2 NULL, 
    [EndAt] DATETIME2 NULL, 
    [AbsenceType] NVARCHAR(10) NULL, 
    CONSTRAINT [PK_WorkerAbsence] PRIMARY KEY ([StagingRowId]), 
    CONSTRAINT [FK_WorkerAbsence_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Kişi bazında izin ve rapor.', 'schema', stg, 'table', [WorkerAbsence];

GO

execute sp_addextendedproperty 'MS_Description', N'Satır kimliği', 'schema', stg, 'table', [WorkerAbsence], 'column', [StagingRowId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yükleme partisi', 'schema', stg, 'table', [WorkerAbsence], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yeni | Hatalı | Aktarıldı', 'schema', stg, 'table', [WorkerAbsence], 'column', [RowStatus];

GO

execute sp_addextendedproperty 'MS_Description', N'Hata açıklaması', 'schema', stg, 'table', [WorkerAbsence], 'column', [ErrorText];

GO

execute sp_addextendedproperty 'MS_Description', N'İşçi sicil no', 'schema', stg, 'table', [WorkerAbsence], 'column', [WorkerCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Başlangıç', 'schema', stg, 'table', [WorkerAbsence], 'column', [StartAt];

GO

execute sp_addextendedproperty 'MS_Description', N'Bitiş', 'schema', stg, 'table', [WorkerAbsence], 'column', [EndAt];

GO

execute sp_addextendedproperty 'MS_Description', N'İzin | Rapor', 'schema', stg, 'table', [WorkerAbsence], 'column', [AbsenceType];

GO

CREATE TABLE stg.[WorkerCompetence] (
    [StagingRowId] BIGINT NOT NULL IDENTITY, 
    [ImportBatchId] BIGINT NOT NULL, 
    [RowStatus] NVARCHAR(15) NOT NULL, 
    [ErrorText] NVARCHAR(400) NULL, 
    [WorkerCode] NVARCHAR(50) NULL, 
    [CompetenceGroupCode] NVARCHAR(50) NULL, 
    CONSTRAINT [PK_WorkerCompetence] PRIMARY KEY ([StagingRowId]), 
    CONSTRAINT [FK_WorkerCompetence_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'İşçi–yetkinlik grubu eşleşmesi; çoktan çoğa.', 'schema', stg, 'table', [WorkerCompetence];

GO

execute sp_addextendedproperty 'MS_Description', N'Satır kimliği', 'schema', stg, 'table', [WorkerCompetence], 'column', [StagingRowId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yükleme partisi', 'schema', stg, 'table', [WorkerCompetence], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yeni | Hatalı | Aktarıldı', 'schema', stg, 'table', [WorkerCompetence], 'column', [RowStatus];

GO

execute sp_addextendedproperty 'MS_Description', N'Hata açıklaması', 'schema', stg, 'table', [WorkerCompetence], 'column', [ErrorText];

GO

execute sp_addextendedproperty 'MS_Description', N'İşçi sicil no', 'schema', stg, 'table', [WorkerCompetence], 'column', [WorkerCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Yetkinlik grubu kodu', 'schema', stg, 'table', [WorkerCompetence], 'column', [CompetenceGroupCode];

GO

CREATE UNIQUE INDEX [UX_WorkerCompetence_WorkerCode_CompetenceGroupCode] ON stg.[WorkerCompetence] ([WorkerCode], [CompetenceGroupCode]);

GO

CREATE TABLE adm.[DataVersionEntity] (
    [DataVersionId] BIGINT NOT NULL, 
    [EntityName] NVARCHAR(60) NOT NULL, 
    [ImportBatchId] BIGINT NULL, 
    CONSTRAINT [PK_DataVersionEntity] PRIMARY KEY ([DataVersionId], [EntityName]), 
    CONSTRAINT [FK_DataVersionEntity_DataVersionId] FOREIGN KEY([DataVersionId]) REFERENCES adm.[DataVersion] ([Id]), 
    CONSTRAINT [FK_DataVersionEntity_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Kısmi yüklemede hangi varlıkların yüklendiği.', 'schema', adm, 'table', [DataVersionEntity];

GO

execute sp_addextendedproperty 'MS_Description', N'Veri versiyonu', 'schema', adm, 'table', [DataVersionEntity], 'column', [DataVersionId];

GO

execute sp_addextendedproperty 'MS_Description', N'Varlık', 'schema', adm, 'table', [DataVersionEntity], 'column', [EntityName];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaynak parti', 'schema', adm, 'table', [DataVersionEntity], 'column', [ImportBatchId];

GO

CREATE TABLE planning.[PlanRun] (
    [Id] BIGINT NOT NULL IDENTITY, 
    [ScenarioId] BIGINT NULL, 
    [WorkspaceId] BIGINT NULL, 
    [DataVersionId] BIGINT NOT NULL, 
    [ParameterSetId] INTEGER NOT NULL, 
    [EngineUsed] NVARCHAR(20) NULL, 
    [Solver] NVARCHAR(20) NULL, 
    [StartedAt] DATETIME2 NULL, 
    [EndedAt] DATETIME2 NULL, 
    [Status] NVARCHAR(15) NULL, 
    CONSTRAINT [PK_PlanRun] PRIMARY KEY ([Id]), 
    CONSTRAINT [FK_PlanRun_DataVersionId] FOREIGN KEY([DataVersionId]) REFERENCES adm.[DataVersion] ([Id]), 
    CONSTRAINT [FK_PlanRun_ParameterSetId] FOREIGN KEY([ParameterSetId]) REFERENCES param.[ParameterSet] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Bir plan hesabı (senaryo ya da çalışma); bütün plan çıktıları buna bağlı.', 'schema', planning, 'table', [PlanRun];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', planning, 'table', [PlanRun], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Senaryo', 'schema', planning, 'table', [PlanRun], 'column', [ScenarioId];

GO

execute sp_addextendedproperty 'MS_Description', N'Çalışma', 'schema', planning, 'table', [PlanRun], 'column', [WorkspaceId];

GO

execute sp_addextendedproperty 'MS_Description', N'Veri versiyonu', 'schema', planning, 'table', [PlanRun], 'column', [DataVersionId];

GO

execute sp_addextendedproperty 'MS_Description', N'Parametre seti', 'schema', planning, 'table', [PlanRun], 'column', [ParameterSetId];

GO

execute sp_addextendedproperty 'MS_Description', N'LP | MILP | Kurallı | Kısıtsız MRP', 'schema', planning, 'table', [PlanRun], 'column', [EngineUsed];

GO

execute sp_addextendedproperty 'MS_Description', N'Çözücü', 'schema', planning, 'table', [PlanRun], 'column', [Solver];

GO

execute sp_addextendedproperty 'MS_Description', N'Başlangıç', 'schema', planning, 'table', [PlanRun], 'column', [StartedAt];

GO

execute sp_addextendedproperty 'MS_Description', N'Bitiş', 'schema', planning, 'table', [PlanRun], 'column', [EndedAt];

GO

execute sp_addextendedproperty 'MS_Description', N'Sırada | Çalışıyor | Bitti | Kısmen | Hata', 'schema', planning, 'table', [PlanRun], 'column', [Status];

GO

CREATE TABLE planning.[Scenario] (
    [Id] BIGINT NOT NULL IDENTITY, 
    [ScenarioDefinitionId] INTEGER NOT NULL, 
    [DataVersionId] BIGINT NOT NULL, 
    [PlanRunId] BIGINT NULL, 
    [CreatedAt] DATETIME2 NULL, 
    [Status] NVARCHAR(15) NULL, 
    CONSTRAINT [PK_Scenario] PRIMARY KEY ([Id]), 
    CONSTRAINT [FK_Scenario_DataVersionId] FOREIGN KEY([DataVersionId]) REFERENCES adm.[DataVersion] ([Id]), 
    CONSTRAINT [FK_Scenario_ScenarioDefinitionId] FOREIGN KEY([ScenarioDefinitionId]) REFERENCES param.[ScenarioDefinition] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Gece üretilen senaryo; bir sonraki gece akışında silinir.', 'schema', planning, 'table', [Scenario];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', planning, 'table', [Scenario], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Tanım', 'schema', planning, 'table', [Scenario], 'column', [ScenarioDefinitionId];

GO

execute sp_addextendedproperty 'MS_Description', N'Veri versiyonu', 'schema', planning, 'table', [Scenario], 'column', [DataVersionId];

GO

execute sp_addextendedproperty 'MS_Description', N'Üreten plan çalışması', 'schema', planning, 'table', [Scenario], 'column', [PlanRunId];

GO

execute sp_addextendedproperty 'MS_Description', N'Oluşma', 'schema', planning, 'table', [Scenario], 'column', [CreatedAt];

GO

execute sp_addextendedproperty 'MS_Description', N'Bitti | Kısmen | Hata', 'schema', planning, 'table', [Scenario], 'column', [Status];

GO

CREATE TABLE planning.[WorkspaceOverride] (
    [Id] BIGINT NOT NULL IDENTITY, 
    [WorkspaceId] BIGINT NOT NULL, 
    [TableName] NVARCHAR(60) NOT NULL, 
    [RecordKey] NVARCHAR(200) NOT NULL, 
    [FieldName] NVARCHAR(60) NOT NULL, 
    [Value] NVARCHAR(200) NOT NULL, 
    [ChangedAt] DATETIME2 NULL, 
    CONSTRAINT [PK_WorkspaceOverride] PRIMARY KEY ([Id]), 
    CONSTRAINT [FK_WorkspaceOverride_WorkspaceId] FOREIGN KEY([WorkspaceId]) REFERENCES planning.[Workspace] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Çalışmadaki geçici değişiklikler: parametreler ve çalışmada değiştirilebilir ana veri alanları.', 'schema', planning, 'table', [WorkspaceOverride];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', planning, 'table', [WorkspaceOverride], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Çalışma', 'schema', planning, 'table', [WorkspaceOverride], 'column', [WorkspaceId];

GO

execute sp_addextendedproperty 'MS_Description', N'Tablo', 'schema', planning, 'table', [WorkspaceOverride], 'column', [TableName];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt', 'schema', planning, 'table', [WorkspaceOverride], 'column', [RecordKey];

GO

execute sp_addextendedproperty 'MS_Description', N'Alan', 'schema', planning, 'table', [WorkspaceOverride], 'column', [FieldName];

GO

execute sp_addextendedproperty 'MS_Description', N'Geçici değer', 'schema', planning, 'table', [WorkspaceOverride], 'column', [Value];

GO

execute sp_addextendedproperty 'MS_Description', N'Zaman', 'schema', planning, 'table', [WorkspaceOverride], 'column', [ChangedAt];

GO

CREATE TABLE adm.[SolverLog] (
    [Id] BIGINT NOT NULL IDENTITY, 
    [PlanRunId] BIGINT NOT NULL, 
    [ModelSize] NVARCHAR(200) NULL, 
    [SolveSeconds] NUMERIC(9, 2) NULL, 
    [Gap] NUMERIC(9, 6) NULL, 
    [Iterations] INTEGER NULL, 
    CONSTRAINT [PK_SolverLog] PRIMARY KEY ([Id]), 
    CONSTRAINT [FK_SolverLog_PlanRunId] FOREIGN KEY([PlanRunId]) REFERENCES planning.[PlanRun] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Çözüm logu; ilk günden tutulur.', 'schema', adm, 'table', [SolverLog];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', adm, 'table', [SolverLog], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Plan hesabı', 'schema', adm, 'table', [SolverLog], 'column', [PlanRunId];

GO

execute sp_addextendedproperty 'MS_Description', N'Değişken, kısıt, malzeme, kaynak, dönem sayıları', 'schema', adm, 'table', [SolverLog], 'column', [ModelSize];

GO

execute sp_addextendedproperty 'MS_Description', N'Süre', 'schema', adm, 'table', [SolverLog], 'column', [SolveSeconds];

GO

execute sp_addextendedproperty 'MS_Description', N'Optimallik farkı', 'schema', adm, 'table', [SolverLog], 'column', [Gap];

GO

execute sp_addextendedproperty 'MS_Description', N'LNS turu', 'schema', adm, 'table', [SolverLog], 'column', [Iterations];

GO

CREATE TABLE planning.[CapacityLoad] (
    [Id] BIGINT NOT NULL, 
    [PlanRunId] BIGINT NOT NULL, 
    [ResourceId] BIGINT NOT NULL, 
    [BucketStart] DATE NOT NULL, 
    [GrossCapacity] NUMERIC(18, 4) NULL, 
    [DowntimeLoss] NUMERIC(18, 4) NULL, 
    [NetCapacity] NUMERIC(18, 4) NULL, 
    [Load] NUMERIC(18, 4) NULL, 
    [Overtime] NUMERIC(18, 4) NULL, 
    [VersionFrom] INTEGER NOT NULL, 
    [VersionTo] INTEGER NULL, 
    [ImportBatchId] BIGINT NULL, 
    [BusinessKey] NVARCHAR(200) NOT NULL, 
    [UpdatedAt] DATETIME2 NOT NULL, 
    CONSTRAINT [PK_CapacityLoad] PRIMARY KEY ([Id], [VersionFrom]), 
    CONSTRAINT [FK_CapacityLoad_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id]), 
    CONSTRAINT [FK_CapacityLoad_PlanRunId] FOREIGN KEY([PlanRunId]) REFERENCES planning.[PlanRun] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Kaynak ve dönem bazında kapasite ve kapasite yükü.', 'schema', planning, 'table', [CapacityLoad];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', planning, 'table', [CapacityLoad], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Plan hesabı', 'schema', planning, 'table', [CapacityLoad], 'column', [PlanRunId];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaynak', 'schema', planning, 'table', [CapacityLoad], 'column', [ResourceId];

GO

execute sp_addextendedproperty 'MS_Description', N'Dönem', 'schema', planning, 'table', [CapacityLoad], 'column', [BucketStart];

GO

execute sp_addextendedproperty 'MS_Description', N'Brüt kapasite', 'schema', planning, 'table', [CapacityLoad], 'column', [GrossCapacity];

GO

execute sp_addextendedproperty 'MS_Description', N'Duruş kaybı', 'schema', planning, 'table', [CapacityLoad], 'column', [DowntimeLoss];

GO

execute sp_addextendedproperty 'MS_Description', N'Kalan kapasite (verim sonrası)', 'schema', planning, 'table', [CapacityLoad], 'column', [NetCapacity];

GO

execute sp_addextendedproperty 'MS_Description', N'Kapasite yükü', 'schema', planning, 'table', [CapacityLoad], 'column', [Load];

GO

execute sp_addextendedproperty 'MS_Description', N'Fazla mesai', 'schema', planning, 'table', [CapacityLoad], 'column', [Overtime];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu ilk veri versiyonu', 'schema', planning, 'table', [CapacityLoad], 'column', [VersionFrom];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş', 'schema', planning, 'table', [CapacityLoad], 'column', [VersionTo];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydı getiren yükleme partisi', 'schema', planning, 'table', [CapacityLoad], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'İş anahtarı (kod ya da kodların birleşimi)', 'schema', planning, 'table', [CapacityLoad], 'column', [BusinessKey];

GO

execute sp_addextendedproperty 'MS_Description', N'Son değişiklik zamanı', 'schema', planning, 'table', [CapacityLoad], 'column', [UpdatedAt];

GO

CREATE INDEX [IX_CapacityLoad_ResourceId] ON planning.[CapacityLoad] ([ResourceId]);

GO

CREATE TABLE planning.[DemandFulfillment] (
    [Id] BIGINT NOT NULL, 
    [PlanRunId] BIGINT NOT NULL, 
    [DemandType] NVARCHAR(15) NOT NULL, 
    [DemandId] BIGINT NOT NULL, 
    [DueDate] DATE NULL, 
    [PlannedDate] DATE NULL, 
    [ShortQty] NUMERIC(18, 4) NULL, 
    [DelayDays] INTEGER NULL, 
    [VersionFrom] INTEGER NOT NULL, 
    [VersionTo] INTEGER NULL, 
    [ImportBatchId] BIGINT NULL, 
    [BusinessKey] NVARCHAR(200) NOT NULL, 
    [UpdatedAt] DATETIME2 NOT NULL, 
    CONSTRAINT [PK_DemandFulfillment] PRIMARY KEY ([Id], [VersionFrom]), 
    CONSTRAINT [FK_DemandFulfillment_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id]), 
    CONSTRAINT [FK_DemandFulfillment_PlanRunId] FOREIGN KEY([PlanRunId]) REFERENCES planning.[PlanRun] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Talebin planlanan karşılanması ve gecikmesi.', 'schema', planning, 'table', [DemandFulfillment];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', planning, 'table', [DemandFulfillment], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Plan hesabı', 'schema', planning, 'table', [DemandFulfillment], 'column', [PlanRunId];

GO

execute sp_addextendedproperty 'MS_Description', N'Sipariş | Tahmin | Teklif | Güvenlik stoğu', 'schema', planning, 'table', [DemandFulfillment], 'column', [DemandType];

GO

execute sp_addextendedproperty 'MS_Description', N'Talep kaydı', 'schema', planning, 'table', [DemandFulfillment], 'column', [DemandId];

GO

execute sp_addextendedproperty 'MS_Description', N'Vade', 'schema', planning, 'table', [DemandFulfillment], 'column', [DueDate];

GO

execute sp_addextendedproperty 'MS_Description', N'Planlanan karşılama', 'schema', planning, 'table', [DemandFulfillment], 'column', [PlannedDate];

GO

execute sp_addextendedproperty 'MS_Description', N'Karşılanamayan miktar', 'schema', planning, 'table', [DemandFulfillment], 'column', [ShortQty];

GO

execute sp_addextendedproperty 'MS_Description', N'Gecikme (gün)', 'schema', planning, 'table', [DemandFulfillment], 'column', [DelayDays];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu ilk veri versiyonu', 'schema', planning, 'table', [DemandFulfillment], 'column', [VersionFrom];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş', 'schema', planning, 'table', [DemandFulfillment], 'column', [VersionTo];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydı getiren yükleme partisi', 'schema', planning, 'table', [DemandFulfillment], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'İş anahtarı (kod ya da kodların birleşimi)', 'schema', planning, 'table', [DemandFulfillment], 'column', [BusinessKey];

GO

execute sp_addextendedproperty 'MS_Description', N'Son değişiklik zamanı', 'schema', planning, 'table', [DemandFulfillment], 'column', [UpdatedAt];

GO

CREATE TABLE planning.[Pegging] (
    [Id] BIGINT NOT NULL, 
    [PlanRunId] BIGINT NOT NULL, 
    [SupplyType] NVARCHAR(15) NOT NULL, 
    [SupplyId] BIGINT NOT NULL, 
    [DemandType] NVARCHAR(15) NOT NULL, 
    [DemandId] BIGINT NOT NULL, 
    [RootDemandId] BIGINT NULL, 
    [Quantity] NUMERIC(18, 4) NOT NULL, 
    [IsFixed] BIT NULL DEFAULT 0, 
    [VersionFrom] INTEGER NOT NULL, 
    [VersionTo] INTEGER NULL, 
    [ImportBatchId] BIGINT NULL, 
    [BusinessKey] NVARCHAR(200) NOT NULL, 
    [UpdatedAt] DATETIME2 NOT NULL, 
    CONSTRAINT [PK_Pegging] PRIMARY KEY ([Id], [VersionFrom]), 
    CONSTRAINT [FK_Pegging_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id]), 
    CONSTRAINT [FK_Pegging_PlanRunId] FOREIGN KEY([PlanRunId]) REFERENCES planning.[PlanRun] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Arz–talep bağı (full pegging).', 'schema', planning, 'table', [Pegging];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', planning, 'table', [Pegging], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Plan hesabı', 'schema', planning, 'table', [Pegging], 'column', [PlanRunId];

GO

execute sp_addextendedproperty 'MS_Description', N'Stok | İş emri | Satın alma | Planlı sipariş …', 'schema', planning, 'table', [Pegging], 'column', [SupplyType];

GO

execute sp_addextendedproperty 'MS_Description', N'Arz', 'schema', planning, 'table', [Pegging], 'column', [SupplyId];

GO

execute sp_addextendedproperty 'MS_Description', N'Sipariş | Bağımlı talep …', 'schema', planning, 'table', [Pegging], 'column', [DemandType];

GO

execute sp_addextendedproperty 'MS_Description', N'Talep', 'schema', planning, 'table', [Pegging], 'column', [DemandId];

GO

execute sp_addextendedproperty 'MS_Description', N'Kök talep', 'schema', planning, 'table', [Pegging], 'column', [RootDemandId];

GO

execute sp_addextendedproperty 'MS_Description', N'Miktar', 'schema', planning, 'table', [Pegging], 'column', [Quantity];

GO

execute sp_addextendedproperty 'MS_Description', N'Sabit ya da manuel bağ', 'schema', planning, 'table', [Pegging], 'column', [IsFixed];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu ilk veri versiyonu', 'schema', planning, 'table', [Pegging], 'column', [VersionFrom];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş', 'schema', planning, 'table', [Pegging], 'column', [VersionTo];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydı getiren yükleme partisi', 'schema', planning, 'table', [Pegging], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'İş anahtarı (kod ya da kodların birleşimi)', 'schema', planning, 'table', [Pegging], 'column', [BusinessKey];

GO

execute sp_addextendedproperty 'MS_Description', N'Son değişiklik zamanı', 'schema', planning, 'table', [Pegging], 'column', [UpdatedAt];

GO

CREATE TABLE planning.[PlanMetric] (
    [PlanRunId] BIGINT NOT NULL, 
    [MetricCode] NVARCHAR(40) NOT NULL, 
    [Value] NUMERIC(18, 4) NOT NULL, 
    CONSTRAINT [PK_PlanMetric] PRIMARY KEY ([PlanRunId], [MetricCode]), 
    CONSTRAINT [FK_PlanMetric_PlanRunId] FOREIGN KEY([PlanRunId]) REFERENCES planning.[PlanRun] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Senaryo karşılaştırma metrikleri; senaryo silinse de özet kısa süre kalır.', 'schema', planning, 'table', [PlanMetric];

GO

execute sp_addextendedproperty 'MS_Description', N'Plan hesabı', 'schema', planning, 'table', [PlanMetric], 'column', [PlanRunId];

GO

execute sp_addextendedproperty 'MS_Description', N'Metrik', 'schema', planning, 'table', [PlanMetric], 'column', [MetricCode];

GO

execute sp_addextendedproperty 'MS_Description', N'Değer', 'schema', planning, 'table', [PlanMetric], 'column', [Value];

GO

CREATE TABLE planning.[PlanVersion] (
    [Id] BIGINT NOT NULL IDENTITY, 
    [LocationId] INTEGER NOT NULL, 
    [PlanRunId] BIGINT NOT NULL, 
    [WorkspaceId] BIGINT NOT NULL, 
    [PublishedBy] INTEGER NOT NULL, 
    [PublishedAt] DATETIME2 NOT NULL, 
    [IsCurrent] BIT NOT NULL, 
    CONSTRAINT [PK_PlanVersion] PRIMARY KEY ([Id]), 
    CONSTRAINT [FK_PlanVersion_LocationId] FOREIGN KEY([LocationId]) REFERENCES core.[Location] ([Id]), 
    CONSTRAINT [FK_PlanVersion_PlanRunId] FOREIGN KEY([PlanRunId]) REFERENCES planning.[PlanRun] ([Id]), 
    CONSTRAINT [FK_PlanVersion_PublishedBy] FOREIGN KEY([PublishedBy]) REFERENCES adm.[AppUser] ([Id]), 
    CONSTRAINT [FK_PlanVersion_WorkspaceId] FOREIGN KEY([WorkspaceId]) REFERENCES planning.[Workspace] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Onaylı plan versiyonu; hep saklanır. Aynı anda tek geçerli.', 'schema', planning, 'table', [PlanVersion];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', planning, 'table', [PlanVersion], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Lokasyon', 'schema', planning, 'table', [PlanVersion], 'column', [LocationId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yayınlanan plan hesabı', 'schema', planning, 'table', [PlanVersion], 'column', [PlanRunId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yayınlanan çalışma', 'schema', planning, 'table', [PlanVersion], 'column', [WorkspaceId];

GO

execute sp_addextendedproperty 'MS_Description', N'Yayınlayan', 'schema', planning, 'table', [PlanVersion], 'column', [PublishedBy];

GO

execute sp_addextendedproperty 'MS_Description', N'Yayın zamanı', 'schema', planning, 'table', [PlanVersion], 'column', [PublishedAt];

GO

execute sp_addextendedproperty 'MS_Description', N'Geçerli onaylı plan', 'schema', planning, 'table', [PlanVersion], 'column', [IsCurrent];

GO

CREATE TABLE planning.[PlanWarning] (
    [Id] BIGINT NOT NULL, 
    [PlanRunId] BIGINT NOT NULL, 
    [WarningCode] NVARCHAR(30) NOT NULL, 
    [ObjectType] NVARCHAR(20) NULL, 
    [ObjectId] BIGINT NULL, 
    [Value] NUMERIC(18, 4) NULL, 
    [Message] NVARCHAR(400) NULL, 
    [VersionFrom] INTEGER NOT NULL, 
    [VersionTo] INTEGER NULL, 
    [ImportBatchId] BIGINT NULL, 
    [BusinessKey] NVARCHAR(200) NOT NULL, 
    [UpdatedAt] DATETIME2 NOT NULL, 
    CONSTRAINT [PK_PlanWarning] PRIMARY KEY ([Id], [VersionFrom]), 
    CONSTRAINT [FK_PlanWarning_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id]), 
    CONSTRAINT [FK_PlanWarning_PlanRunId] FOREIGN KEY([PlanRunId]) REFERENCES planning.[PlanRun] ([Id]), 
    CONSTRAINT [FK_PlanWarning_WarningCode] FOREIGN KEY([WarningCode]) REFERENCES param.[WarningDefinition] ([Code])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Plan hesabının ürettiği uyarılar.', 'schema', planning, 'table', [PlanWarning];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', planning, 'table', [PlanWarning], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Plan hesabı', 'schema', planning, 'table', [PlanWarning], 'column', [PlanRunId];

GO

execute sp_addextendedproperty 'MS_Description', N'Uyarı tanımı', 'schema', planning, 'table', [PlanWarning], 'column', [WarningCode];

GO

execute sp_addextendedproperty 'MS_Description', N'İlgili nesne tipi', 'schema', planning, 'table', [PlanWarning], 'column', [ObjectType];

GO

execute sp_addextendedproperty 'MS_Description', N'İlgili nesne', 'schema', planning, 'table', [PlanWarning], 'column', [ObjectId];

GO

execute sp_addextendedproperty 'MS_Description', N'Ölçülen değer', 'schema', planning, 'table', [PlanWarning], 'column', [Value];

GO

execute sp_addextendedproperty 'MS_Description', N'Mesaj (şablon tabanlı açıklama)', 'schema', planning, 'table', [PlanWarning], 'column', [Message];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu ilk veri versiyonu', 'schema', planning, 'table', [PlanWarning], 'column', [VersionFrom];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş', 'schema', planning, 'table', [PlanWarning], 'column', [VersionTo];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydı getiren yükleme partisi', 'schema', planning, 'table', [PlanWarning], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'İş anahtarı (kod ya da kodların birleşimi)', 'schema', planning, 'table', [PlanWarning], 'column', [BusinessKey];

GO

execute sp_addextendedproperty 'MS_Description', N'Son değişiklik zamanı', 'schema', planning, 'table', [PlanWarning], 'column', [UpdatedAt];

GO

CREATE TABLE planning.[PlannedOrder] (
    [Id] BIGINT NOT NULL, 
    [PlanRunId] BIGINT NOT NULL, 
    [MaterialId] BIGINT NOT NULL, 
    [OrderType] NVARCHAR(15) NOT NULL, 
    [SupplierId] BIGINT NULL, 
    [ProjectId] BIGINT NULL, 
    [Quantity] NUMERIC(18, 4) NOT NULL, 
    [RoundedQty] NUMERIC(18, 4) NULL, 
    [StartDate] DATE NULL, 
    [DueDate] DATE NOT NULL, 
    [BucketStart] DATE NULL, 
    [VersionFrom] INTEGER NOT NULL, 
    [VersionTo] INTEGER NULL, 
    [ImportBatchId] BIGINT NULL, 
    [BusinessKey] NVARCHAR(200) NOT NULL, 
    [UpdatedAt] DATETIME2 NOT NULL, 
    CONSTRAINT [PK_PlannedOrder] PRIMARY KEY ([Id], [VersionFrom]), 
    CONSTRAINT [FK_PlannedOrder_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id]), 
    CONSTRAINT [FK_PlannedOrder_PlanRunId] FOREIGN KEY([PlanRunId]) REFERENCES planning.[PlanRun] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Planlı sipariş: üretim, satın alma ya da fason önerisi. Satın alma sürekli hesaplanır, yuvarlanmış miktar ayrıca.', 'schema', planning, 'table', [PlannedOrder];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', planning, 'table', [PlannedOrder], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Plan hesabı', 'schema', planning, 'table', [PlannedOrder], 'column', [PlanRunId];

GO

execute sp_addextendedproperty 'MS_Description', N'Malzeme', 'schema', planning, 'table', [PlannedOrder], 'column', [MaterialId];

GO

execute sp_addextendedproperty 'MS_Description', N'Üretim | Satın alma | Fason', 'schema', planning, 'table', [PlannedOrder], 'column', [OrderType];

GO

execute sp_addextendedproperty 'MS_Description', N'Tedarikçi', 'schema', planning, 'table', [PlannedOrder], 'column', [SupplierId];

GO

execute sp_addextendedproperty 'MS_Description', N'Proje (sahip)', 'schema', planning, 'table', [PlannedOrder], 'column', [ProjectId];

GO

execute sp_addextendedproperty 'MS_Description', N'Motorun miktarı (sürekli)', 'schema', planning, 'table', [PlannedOrder], 'column', [Quantity];

GO

execute sp_addextendedproperty 'MS_Description', N'Yuvarlanmış miktar (son hesap)', 'schema', planning, 'table', [PlannedOrder], 'column', [RoundedQty];

GO

execute sp_addextendedproperty 'MS_Description', N'Başlangıç', 'schema', planning, 'table', [PlannedOrder], 'column', [StartDate];

GO

execute sp_addextendedproperty 'MS_Description', N'Bitiş', 'schema', planning, 'table', [PlannedOrder], 'column', [DueDate];

GO

execute sp_addextendedproperty 'MS_Description', N'Dönem', 'schema', planning, 'table', [PlannedOrder], 'column', [BucketStart];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu ilk veri versiyonu', 'schema', planning, 'table', [PlannedOrder], 'column', [VersionFrom];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş', 'schema', planning, 'table', [PlannedOrder], 'column', [VersionTo];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydı getiren yükleme partisi', 'schema', planning, 'table', [PlannedOrder], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'İş anahtarı (kod ya da kodların birleşimi)', 'schema', planning, 'table', [PlannedOrder], 'column', [BusinessKey];

GO

execute sp_addextendedproperty 'MS_Description', N'Son değişiklik zamanı', 'schema', planning, 'table', [PlannedOrder], 'column', [UpdatedAt];

GO

CREATE INDEX [IX_PlannedOrder_MaterialId] ON planning.[PlannedOrder] ([MaterialId]);

GO

CREATE INDEX [IX_PlannedOrder_ProjectId] ON planning.[PlannedOrder] ([ProjectId]);

GO

CREATE INDEX [IX_PlannedOrder_SupplierId] ON planning.[PlannedOrder] ([SupplierId]);

GO

CREATE TABLE planning.[SupplyRecommendation] (
    [Id] BIGINT NOT NULL, 
    [PlanRunId] BIGINT NOT NULL, 
    [SupplyType] NVARCHAR(15) NOT NULL, 
    [SupplyId] BIGINT NOT NULL, 
    [Action] NVARCHAR(15) NOT NULL, 
    [CurrentDate] DATE NULL, 
    [ProposedDate] DATE NULL, 
    [ProposedQty] NUMERIC(18, 4) NULL, 
    [VersionFrom] INTEGER NOT NULL, 
    [VersionTo] INTEGER NULL, 
    [ImportBatchId] BIGINT NULL, 
    [BusinessKey] NVARCHAR(200) NOT NULL, 
    [UpdatedAt] DATETIME2 NOT NULL, 
    CONSTRAINT [PK_SupplyRecommendation] PRIMARY KEY ([Id], [VersionFrom]), 
    CONSTRAINT [FK_SupplyRecommendation_ImportBatchId] FOREIGN KEY([ImportBatchId]) REFERENCES adm.[ImportBatch] ([Id]), 
    CONSTRAINT [FK_SupplyRecommendation_PlanRunId] FOREIGN KEY([PlanRunId]) REFERENCES planning.[PlanRun] ([Id])
);

GO

execute sp_addextendedproperty 'MS_Description', N'Mevcut arz için öneri: öne çek, ertele, iptal, azalt, hızlandır.', 'schema', planning, 'table', [SupplyRecommendation];

GO

execute sp_addextendedproperty 'MS_Description', N'Kayıt kimliği', 'schema', planning, 'table', [SupplyRecommendation], 'column', [Id];

GO

execute sp_addextendedproperty 'MS_Description', N'Plan hesabı', 'schema', planning, 'table', [SupplyRecommendation], 'column', [PlanRunId];

GO

execute sp_addextendedproperty 'MS_Description', N'İş emri | Satın alma | Fason | Transfer', 'schema', planning, 'table', [SupplyRecommendation], 'column', [SupplyType];

GO

execute sp_addextendedproperty 'MS_Description', N'Arz kaydı', 'schema', planning, 'table', [SupplyRecommendation], 'column', [SupplyId];

GO

execute sp_addextendedproperty 'MS_Description', N'Öne çek | Ertele | İptal | Azalt | Hızlandır', 'schema', planning, 'table', [SupplyRecommendation], 'column', [Action];

GO

execute sp_addextendedproperty 'MS_Description', N'Mevcut tarih', 'schema', planning, 'table', [SupplyRecommendation], 'column', [CurrentDate];

GO

execute sp_addextendedproperty 'MS_Description', N'Önerilen tarih', 'schema', planning, 'table', [SupplyRecommendation], 'column', [ProposedDate];

GO

execute sp_addextendedproperty 'MS_Description', N'Önerilen miktar', 'schema', planning, 'table', [SupplyRecommendation], 'column', [ProposedQty];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu ilk veri versiyonu', 'schema', planning, 'table', [SupplyRecommendation], 'column', [VersionFrom];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş', 'schema', planning, 'table', [SupplyRecommendation], 'column', [VersionTo];

GO

execute sp_addextendedproperty 'MS_Description', N'Kaydı getiren yükleme partisi', 'schema', planning, 'table', [SupplyRecommendation], 'column', [ImportBatchId];

GO

execute sp_addextendedproperty 'MS_Description', N'İş anahtarı (kod ya da kodların birleşimi)', 'schema', planning, 'table', [SupplyRecommendation], 'column', [BusinessKey];

GO

execute sp_addextendedproperty 'MS_Description', N'Son değişiklik zamanı', 'schema', planning, 'table', [SupplyRecommendation], 'column', [UpdatedAt];

GO

ALTER TABLE planning.[Workspace] ADD CONSTRAINT [FK_Workspace_CurrentPlanRunId] FOREIGN KEY([CurrentPlanRunId]) REFERENCES planning.[PlanRun] ([Id]);

GO

ALTER TABLE planning.[Workspace] ADD CONSTRAINT [FK_Workspace_ScenarioId] FOREIGN KEY([ScenarioId]) REFERENCES planning.[Scenario] ([Id]);

GO

ALTER TABLE planning.[PlanRun] ADD CONSTRAINT [FK_PlanRun_WorkspaceId] FOREIGN KEY([WorkspaceId]) REFERENCES planning.[Workspace] ([Id]);

GO

ALTER TABLE planning.[PlanRun] ADD CONSTRAINT [FK_PlanRun_ScenarioId] FOREIGN KEY([ScenarioId]) REFERENCES planning.[Scenario] ([Id]);

GO

ALTER TABLE planning.[Scenario] ADD CONSTRAINT [FK_Scenario_PlanRunId] FOREIGN KEY([PlanRunId]) REFERENCES planning.[PlanRun] ([Id]);

GO

INSERT INTO alembic_version (version_num) OUTPUT inserted.version_num VALUES ('0001');

GO

COMMIT;

GO

