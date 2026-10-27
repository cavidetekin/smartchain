USE Smartchain;
GO

BEGIN TRANSACTION;

-- Running downgrade 0004 -> 0003

declare @const_name varchar(256)
select @const_name = QUOTENAME([name]) from sys.default_constraints
where parent_object_id = object_id('param.ParameterSet')
and col_name(parent_object_id, parent_column_id) = 'IsSynthetic'
exec('alter table param.[ParameterSet] drop constraint ' + @const_name);

GO

ALTER TABLE param.[ParameterSet] DROP COLUMN [IsSynthetic];

GO

declare @const_name varchar(256)
select @const_name = QUOTENAME([name]) from sys.default_constraints
where parent_object_id = object_id('core.Location')
and col_name(parent_object_id, parent_column_id) = 'IsSynthetic'
exec('alter table core.[Location] drop constraint ' + @const_name);

GO

ALTER TABLE core.[Location] DROP COLUMN [IsSynthetic];

GO

declare @const_name varchar(256)
select @const_name = QUOTENAME([name]) from sys.default_constraints
where parent_object_id = object_id('adm.DataVersion')
and col_name(parent_object_id, parent_column_id) = 'IsSynthetic'
exec('alter table adm.[DataVersion] drop constraint ' + @const_name);

GO

ALTER TABLE adm.[DataVersion] DROP COLUMN [IsSynthetic];

GO

UPDATE alembic_version SET version_num='0003' WHERE alembic_version.version_num = '0004';

GO

COMMIT;

GO

