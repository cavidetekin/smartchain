USE Smartchain;
GO

BEGIN TRANSACTION;

-- Running downgrade 0005 -> 0004

ALTER TABLE param.[PriorityRule] ALTER COLUMN [Direction] NVARCHAR(4) NULL;

GO

ALTER TABLE stg.[PurchaseOrderLine] ALTER COLUMN [OrderType] NVARCHAR(15) NULL;

GO

ALTER TABLE core.[PurchaseOrderLine] ALTER COLUMN [OrderType] NVARCHAR(15) NOT NULL;

GO

ALTER TABLE stg.[MaterialSupplier] ALTER COLUMN [LeadTimeBasis] NVARCHAR(10) NULL;

GO

ALTER TABLE core.[MaterialSupplier] ALTER COLUMN [LeadTimeBasis] NVARCHAR(10) NULL;

GO

UPDATE alembic_version SET version_num='0004' WHERE alembic_version.version_num = '0005';

GO

COMMIT;

GO

