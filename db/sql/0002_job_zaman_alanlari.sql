USE Smartchain;
GO

BEGIN TRANSACTION;

-- Running upgrade 0001 -> 0002

ALTER TABLE adm.[Job] ADD [CreatedAt] DATETIME2 NULL;

GO

execute sp_addextendedproperty 'MS_Description', N'İstek zamanı (UTC); sıra buna göre görünür', 'schema', adm, 'table', [Job], 'column', [CreatedAt];

GO

ALTER TABLE adm.[Job] ADD [StartedAt] DATETIME2 NULL;

GO

execute sp_addextendedproperty 'MS_Description', N'Çalışmaya başlama (UTC)', 'schema', adm, 'table', [Job], 'column', [StartedAt];

GO

ALTER TABLE adm.[Job] ADD [EndedAt] DATETIME2 NULL;

GO

execute sp_addextendedproperty 'MS_Description', N'Bitiş, hata ya da iptal (UTC)', 'schema', adm, 'table', [Job], 'column', [EndedAt];

GO

ALTER TABLE adm.[Job] ADD [UpdatedAt] DATETIME2 NULL;

GO

execute sp_addextendedproperty 'MS_Description', N'Son değişiklik (UTC); API bildirim için izler (K-69)', 'schema', adm, 'table', [Job], 'column', [UpdatedAt];

GO

UPDATE adm.Job SET CreatedAt = SYSUTCDATETIME(), UpdatedAt = SYSUTCDATETIME();

GO

ALTER TABLE adm.[Job] ALTER COLUMN [CreatedAt] DATETIME2 NOT NULL;

GO

ALTER TABLE adm.[Job] ALTER COLUMN [UpdatedAt] DATETIME2 NOT NULL;

GO

UPDATE alembic_version SET version_num='0002' WHERE alembic_version.version_num = '0001';

GO

COMMIT;

GO

