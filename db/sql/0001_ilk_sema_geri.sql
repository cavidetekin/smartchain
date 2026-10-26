USE Smartchain;
GO

BEGIN TRANSACTION;

-- Running downgrade 0001 -> 

ALTER TABLE planning.[Workspace] DROP CONSTRAINT [FK_Workspace_CurrentPlanRunId];

GO

ALTER TABLE planning.[Workspace] DROP CONSTRAINT [FK_Workspace_ScenarioId];

GO

ALTER TABLE planning.[PlanRun] DROP CONSTRAINT [FK_PlanRun_WorkspaceId];

GO

ALTER TABLE planning.[PlanRun] DROP CONSTRAINT [FK_PlanRun_ScenarioId];

GO

ALTER TABLE planning.[Scenario] DROP CONSTRAINT [FK_Scenario_PlanRunId];

GO

DROP TABLE planning.[SupplyRecommendation];

GO

DROP TABLE planning.[PlannedOrder];

GO

DROP TABLE planning.[PlanWarning];

GO

DROP TABLE planning.[PlanVersion];

GO

DROP TABLE planning.[PlanMetric];

GO

DROP TABLE planning.[Pegging];

GO

DROP TABLE planning.[DemandFulfillment];

GO

DROP TABLE planning.[CapacityLoad];

GO

DROP TABLE adm.[SolverLog];

GO

DROP TABLE planning.[WorkspaceOverride];

GO

DROP TABLE planning.[Scenario];

GO

DROP TABLE planning.[PlanRun];

GO

DROP TABLE adm.[DataVersionEntity];

GO

DROP TABLE stg.[WorkerCompetence];

GO

DROP TABLE stg.[WorkerAbsence];

GO

DROP TABLE stg.[Worker];

GO

DROP TABLE stg.[WorkOrderOperation];

GO

DROP TABLE stg.[WorkOrderComponent];

GO

DROP TABLE stg.[WorkOrder];

GO

DROP TABLE stg.[UomConversion];

GO

DROP TABLE stg.[UnitOfMeasure];

GO

DROP TABLE stg.[Supplier];

GO

DROP TABLE stg.[Stock];

GO

DROP TABLE stg.[SalesOrderLine];

GO

DROP TABLE stg.[Routing];

GO

DROP TABLE stg.[ResourceGroup];

GO

DROP TABLE stg.[Resource];

GO

DROP TABLE stg.[PurchaseOrderLine];

GO

DROP TABLE stg.[ProjectGroup];

GO

DROP TABLE stg.[Project];

GO

DROP TABLE stg.[ProductionVersion];

GO

DROP TABLE stg.[ProductionConfirmation];

GO

DROP TABLE stg.[MaterialSupplier];

GO

DROP TABLE stg.[Material];

GO

DROP TABLE stg.[Location];

GO

DROP TABLE stg.[Forecast];

GO

DROP TABLE stg.[Customer];

GO

DROP TABLE stg.[CompetenceGroup];

GO

DROP TABLE stg.[BOM];

GO

DROP TABLE planning.[Workspace];

GO

DROP TABLE param.[TimeBucketDefinition];

GO

DROP TABLE param.[SupplierLimit];

GO

DROP TABLE param.[ScenarioDefinition];

GO

DROP TABLE param.[ResourcePeriodLimit];

GO

DROP TABLE param.[ResourceEfficiency];

GO

DROP TABLE param.[PriorityRule];

GO

DROP TABLE param.[PlanningSetting];

GO

DROP TABLE param.[OvertimeLimit];

GO

DROP TABLE param.[AllocationRule];

GO

DROP TABLE core.[WorkerCompetence];

GO

DROP TABLE core.[WorkerAbsence];

GO

DROP TABLE core.[Worker];

GO

DROP TABLE core.[WorkOrderOperation];

GO

DROP TABLE core.[WorkOrderComponent];

GO

DROP TABLE core.[WorkOrder];

GO

DROP TABLE core.[UomConversion];

GO

DROP TABLE core.[TransferOrder];

GO

DROP TABLE core.[Supplier];

GO

DROP TABLE core.[Stock];

GO

DROP TABLE core.[ShiftPlan];

GO

DROP TABLE core.[Shift];

GO

DROP TABLE core.[SalesOrderLine];

GO

DROP TABLE core.[Routing];

GO

DROP TABLE core.[ResourceGroup];

GO

DROP TABLE core.[ResourceDowntime];

GO

DROP TABLE core.[ResourceCapacityProfile];

GO

DROP TABLE core.[Resource];

GO

DROP TABLE core.[PurchaseOrderLine];

GO

DROP TABLE core.[ProjectGroup];

GO

DROP TABLE core.[Project];

GO

DROP TABLE core.[ProductionVersion];

GO

DROP TABLE core.[ProductionConfirmation];

GO

DROP TABLE core.[MaterialSupplier];

GO

DROP TABLE core.[Material];

GO

DROP TABLE core.[Forecast];

GO

DROP TABLE core.[Customer];

GO

DROP TABLE core.[CompetenceGroup];

GO

DROP TABLE core.[CalendarDay];

GO

DROP TABLE core.[Calendar];

GO

DROP TABLE core.[BOM];

GO

DROP TABLE adm.[ManualValue];

GO

DROP TABLE adm.[Job];

GO

DROP TABLE adm.[FieldValueSource];

GO

DROP TABLE adm.[DataVersion];

GO

DROP TABLE adm.[DataRuleCondition];

GO

DROP TABLE adm.[AuditLog];

GO

DROP TABLE param.[WarningDefinition];

GO

DROP TABLE param.[ParameterSet];

GO

DROP TABLE core.[UnitOfMeasure];

GO

DROP TABLE core.[Location];

GO

DROP TABLE adm.[SystemSetting];

GO

DROP TABLE adm.[License];

GO

DROP TABLE adm.[ImportBatch];

GO

DROP TABLE adm.[FieldDefinition];

GO

DROP TABLE adm.[DataRule];

GO

DROP TABLE adm.[AppUser];

GO

DROP SCHEMA [adm];

GO

DROP SCHEMA [planning];

GO

DROP SCHEMA [param];

GO

DROP SCHEMA [core];

GO

DROP SCHEMA [stg];

GO

DELETE FROM alembic_version WHERE alembic_version.version_num = '0001';

GO

COMMIT;

GO

