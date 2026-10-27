USE Smartchain;
GO

BEGIN TRANSACTION;

-- Running upgrade 0003 -> 0004

ALTER TABLE adm.[DataVersion] ADD [IsSynthetic] BIT NULL DEFAULT 0;

GO

execute sp_addextendedproperty 'MS_Description', N'Sentetik veri (geliştirme ve demo); sentetik veri komutları yalnız bunlara dokunur (K-79)', 'schema', adm, 'table', [DataVersion], 'column', [IsSynthetic];

GO

ALTER TABLE core.[Location] ADD [IsSynthetic] BIT NULL DEFAULT 0;

GO

execute sp_addextendedproperty 'MS_Description', N'Sentetik veri (geliştirme ve demo); sentetik veri komutları yalnız bunlara dokunur (K-79)', 'schema', core, 'table', [Location], 'column', [IsSynthetic];

GO

ALTER TABLE param.[ParameterSet] ADD [IsSynthetic] BIT NULL DEFAULT 0;

GO

execute sp_addextendedproperty 'MS_Description', N'Sentetik veri (geliştirme ve demo); sentetik veri komutları yalnız bunlara dokunur (K-79)', 'schema', param, 'table', [ParameterSet], 'column', [IsSynthetic];

GO

UPDATE alembic_version SET version_num='0004' WHERE alembic_version.version_num = '0003';

GO

COMMIT;

GO

