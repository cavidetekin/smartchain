USE Smartchain;
GO

BEGIN TRANSACTION;

-- Running downgrade 0003 -> 0002

IF EXISTS (SELECT 1 FROM planning.[PlannedOrder]) THROW 50000, N'planning.PlannedOrder boş değil; 0003 geçişi veri silmez.', 1;

GO

IF EXISTS (SELECT 1 FROM planning.[SupplyRecommendation]) THROW 50000, N'planning.SupplyRecommendation boş değil; 0003 geçişi veri silmez.', 1;

GO

IF EXISTS (SELECT 1 FROM planning.[DemandFulfillment]) THROW 50000, N'planning.DemandFulfillment boş değil; 0003 geçişi veri silmez.', 1;

GO

IF EXISTS (SELECT 1 FROM planning.[CapacityLoad]) THROW 50000, N'planning.CapacityLoad boş değil; 0003 geçişi veri silmez.', 1;

GO

IF EXISTS (SELECT 1 FROM planning.[Pegging]) THROW 50000, N'planning.Pegging boş değil; 0003 geçişi veri silmez.', 1;

GO

IF EXISTS (SELECT 1 FROM planning.[PlanWarning]) THROW 50000, N'planning.PlanWarning boş değil; 0003 geçişi veri silmez.', 1;

GO

DROP TABLE planning.[PlanWarning];

GO

DROP TABLE planning.[Pegging];

GO

DROP TABLE planning.[CapacityLoad];

GO

DROP TABLE planning.[DemandFulfillment];

GO

DROP TABLE planning.[SupplyRecommendation];

GO

DROP TABLE planning.[PlannedOrder];

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

UPDATE alembic_version SET version_num='0002' WHERE alembic_version.version_num = '0003';

GO

COMMIT;

GO

