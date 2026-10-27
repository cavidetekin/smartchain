USE Smartchain;
GO

BEGIN TRANSACTION;

-- Running upgrade 0004 -> 0005

ALTER TABLE core.[MaterialSupplier] ALTER COLUMN [LeadTimeBasis] NVARCHAR(15) NULL;

GO

ALTER TABLE stg.[MaterialSupplier] ALTER COLUMN [LeadTimeBasis] NVARCHAR(15) NULL;

GO

ALTER TABLE core.[PurchaseOrderLine] ALTER COLUMN [OrderType] NVARCHAR(20) NOT NULL;

GO

ALTER TABLE stg.[PurchaseOrderLine] ALTER COLUMN [OrderType] NVARCHAR(20) NULL;

GO

ALTER TABLE param.[PriorityRule] ALTER COLUMN [Direction] NVARCHAR(10) NULL;

GO

UPDATE alembic_version SET version_num='0005' WHERE alembic_version.version_num = '0004';

GO

COMMIT;

GO

