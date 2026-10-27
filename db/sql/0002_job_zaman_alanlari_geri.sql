USE Smartchain;
GO

BEGIN TRANSACTION;

-- Running downgrade 0002 -> 0001

ALTER TABLE adm.[Job] DROP COLUMN [UpdatedAt];

GO

ALTER TABLE adm.[Job] DROP COLUMN [EndedAt];

GO

ALTER TABLE adm.[Job] DROP COLUMN [StartedAt];

GO

ALTER TABLE adm.[Job] DROP COLUMN [CreatedAt];

GO

UPDATE alembic_version SET version_num='0001' WHERE alembic_version.version_num = '0002';

GO

COMMIT;

GO

