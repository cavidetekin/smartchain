"""0084 · Veri sözlüğünde Manuel bayrağı (K-203; K-170'e düzeltme)

K-170'e göre her alan kurulumda "Manuel: Hayır" gelir, System owner açar. Geçiş 0052 o gün var olan alanları kapattı; ama sözlüğe yeni alan ekleyen
kod (`db/dictionary.py`) yeni satırı "Evet" ile yazıyordu. 0052'den sonra eklenen alanlar bu yüzden açık geldi: ana veri ve işlem verisinde 41 alan
(0063, 0077, 0078, 0079), parametre tablolarında 95 alan. Bu geçiş yalnız bu listedeki alanları kapatır; liste sabittir (K-197).

Kapatılmayanlar (geçiş kendisi denetler):
- Alana girilmiş manuel değer varsa alan açık kalır, değer silinmez.
- Denetim izinde System owner'ın alanı son olarak açtığı kayıt varsa (bilerek açılmış) alan açık kalır.
- Listede olmayan alanlara (0052'den önce var olan, System owner'ın açtıkları) dokunulmaz.

Geri alış listedeki kapalı alanları yeniden açar (geçişten önceki hâl). Şema değişmez.

Revision ID: 0084
Revises: 0083
Create Date: 2026-11-27
"""
from alembic import op

revision = '0084'
down_revision = '0083'
branch_labels = None
depends_on = None

MANUAL_ACTION = "Manuel değişikliği"   # app/api/services/manual_values.py (denetim izindeki eylem adı)

# 0052'den sonra "Evet" ile eklenen alanlar: tablo → alanlar (ana veri, işlem verisi ve parametre; plan tabloları 0083'te zaten "Hayır")
FIELDS = {
    'DemandPriority': ('IsValid', 'Level', 'PriorityGroup', 'RecordId', 'ScenarioDefinitionId',),
    'FactoryCalendar': ('DayValue', 'EndDate', 'IsValid', 'LocationId', 'Name', 'ScenarioDefinitionId', 'StartDate',),
    'MaterialAllocationRule': ('AllocationKey', 'AllocationLevel', 'LocationId', 'MaterialId', 'Reason', 'SourceMaterials',),
    'MaterialHold': ('ClosePct', 'EndDate', 'HoldType', 'IsValid', 'LocationId', 'MaterialId', 'Reason', 'ScenarioDefinitionId', 'StartDate',),
    'ObjectiveDefinition': ('Code', 'Description', 'IsActive', 'ScenarioDefinitionId', 'Scope', 'Seq', 'TimeBudgetSeconds', 'TolerancePct',),
    'OvertimeLimit': ('DailyLimit', 'IsValid', 'ResourceGroupId', 'ResourceId', 'ScenarioDefinitionId', 'ValidFrom', 'ValidTo',),
    'PeggingCriterion': ('Criterion', 'Direction', 'ScenarioDefinitionId', 'Seq', 'Side',),
    'PlanningSetting': ('ScenarioDefinitionId',),
    'PurchaseOrderLine': ('AllocationKey', 'AllocationLevel', 'CustomerCode', 'ProjectCode', 'SalesOrderLineItemNo', 'SalesOrderLineNo', 'SalesOrderNo',),
    'ResourceDowntime': ('DowntimeType', 'EndDate', 'IsValid', 'Reason', 'ResourceGroupId', 'ResourceId', 'ScenarioDefinitionId', 'StartDate',),
    'ResourceEfficiency': ('EfficiencyPct', 'IsValid', 'ResourceGroupId', 'ResourceId', 'ScenarioDefinitionId', 'ValidFrom', 'ValidTo',),
    'ResourceGroup': ('CapacityUnit', 'IsCritical', 'IsEmployee', 'IsFurnace', 'IsMachine', 'IsMold', 'IsOther', 'IsSubcontractor', 'SubcontractorId',),
    'ResourceGroupConstraint': ('IsValid', 'ResourceGroupId', 'ScenarioDefinitionId', 'TargetUtilizationPct', 'UnconstrainedCapacityFactor',),
    'ResourceGroupMember': ('AdditionalNumber1', 'AdditionalNumber2', 'AdditionalText1', 'AdditionalText2', 'AdditionalText3',),
    'ScenarioDefinition': ('FollowsBase', 'RunsNightly',),
    'Stock': ('AllocationKey', 'AllocationLevel', 'CustomerCode', 'ProjectCode', 'SalesOrderLineItemNo', 'SalesOrderLineNo', 'SalesOrderNo',),
    'SupplierLimit': ('IsValid', 'LimitPeriod', 'LimitType', 'LocationId', 'Reason', 'ScenarioDefinitionId',),
    'TimeBucketDefinition': ('Axis', 'ScenarioDefinitionId', 'SpanUnit',),
    'WarningThreshold': ('IsActive', 'ScenarioDefinitionId', 'Severity', 'ThresholdCritical', 'ThresholdHigh', 'ThresholdLow', 'ThresholdMedium', 'WarningCode',),
    'WorkOrder': ('AllocationKey', 'AllocationLevel', 'CustomerCode', 'ProjectCode', 'SalesOrderLineItemNo', 'SalesOrderLineNo', 'SalesOrderNo',),
    'WorkPattern': ('DailyCapacity', 'DayFri', 'DayMon', 'DaySat', 'DaySun', 'DayThu', 'DayTue', 'DayWed', 'IsValid', 'ResourceGroupId', 'ResourceId', 'ScenarioDefinitionId', 'ValidFrom', 'ValidTo',),
}


def _pairs():
    return " OR ".join(f"(f.TableName = N'{t}' AND f.FieldName = N'{x}')" for t, xs in FIELDS.items() for x in xs)


def upgrade():
    # alana manuel değer girilmişse ya da System owner son olarak açmışsa dokunulmaz
    op.execute(
        "UPDATE f SET ManualOverrides = 0 FROM adm.FieldDefinition f "
        f"WHERE f.ManualOverrides = 1 AND ({_pairs()}) "
        "AND NOT EXISTS (SELECT 1 FROM adm.ManualValue m WHERE m.TableName = f.TableName AND m.FieldName = f.FieldName) "
        "AND NOT EXISTS (SELECT 1 FROM (SELECT TOP 1 a.NewValue FROM adm.AuditLog a "
        f"WHERE a.Action = N'{MANUAL_ACTION}' AND a.ObjectKey = f.TableName + N'.' + f.FieldName ORDER BY a.[At] DESC, a.Id DESC) last "
        "WHERE last.NewValue LIKE N'%true%')")


def downgrade():
    op.execute(f"UPDATE f SET ManualOverrides = 1 FROM adm.FieldDefinition f WHERE f.ManualOverrides = 0 AND ({_pairs()})")
