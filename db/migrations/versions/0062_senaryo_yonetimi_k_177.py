"""0062 · Senaryo yönetimi (K-177): Baz'ı izler, kullanıcının seçili senaryosu, denetim izinde senaryo adı

- `param.ScenarioDefinition.FollowsBase` ("Baz'ı izler"; Baz'da boş). Var olan Baz dışı senaryolar Baz'dan bağımsız kurulmuştu: Hayır yazılır.
- `adm.AppUser.ScenarioDefinitionId`: kullanıcının son seçtiği senaryo (bağ yok; okurken doğrulanır).
- `adm.AuditLog.ScenarioName`: senaryoya bağlı işlemde senaryonun adı. Var olan parametre kayıtları (nesne "Senaryo", kayıt "<ad> · …") doldurulur;
  denetim izinin değişmezliği (K-109) uygulama hesabı içindir, doldurma bu geçişle bir kez yapılır.
- 0058'in pasife çevirdiği eski sentetik setin kalıntısı ("Sentetik v0") silinir (K-165, açık onay 17.11.2026): yalnız sentetik, Baz olmayan, adı
  "Sentetik v0" olan ve plan hesabı bulunmayan kayıt ve ona bağlı satırlar. Geri alışta geri gelmez.
- Açıklamalar modelden (docs/02); veri sözlüğü eşitlenir.

Revision ID: 0062
Revises: 0061
Create Date: 2026-11-17
"""
from alembic import context, op
import sqlalchemy as sa

from dictionary import sync
from models import metadata

revision = '0062'
down_revision = '0061'
branch_labels = None
depends_on = None

SD = 'param.ScenarioDefinition'
LEFTOVER = (f"SELECT d.Id FROM {SD} d WHERE d.IsSynthetic = 1 AND ISNULL(d.IsBase, 0) = 0 AND d.Name = N'Sentetik v0' "
            "AND NOT EXISTS (SELECT 1 FROM planning.PlanRun r WHERE r.ScenarioDefinitionId = d.Id) "
            "AND NOT EXISTS (SELECT 1 FROM planning.Scenario s WHERE s.ScenarioDefinitionId = d.Id)")
CHILDREN = ('PlanningSetting', 'TimeBucketDefinition', 'ObjectiveDefinition', 'PriorityRule', 'AllocationRule', 'ResourceEfficiency', 'ResourcePeriodLimit',
            'OvertimeLimit', 'SupplierLimit')
OLD = {('param', 'ScenarioDefinition', 'IsActive'): 'Aktif; pasif senaryo seçilemez ve çalışmaz (senaryo yönetimi adımı)',
       ('param', 'ScenarioDefinition', 'RunsNightly'): 'Gece çalışsın (senaryo yönetimi adımı)',
       ('param', 'ScenarioDefinition', 'NightlyPriority'): 'Gece çalışma sırası',
       ('planning', 'Scenario', None): 'Gece üretilen senaryo; bir sonraki gece akışında silinir.'}


def _comment(schema, table, column, text):
    """MS SQL'de var olan açıklama güncellenir."""
    level2 = f", 'column', '{column}'" if column else ""
    escaped = text.replace("'", "''")
    op.execute(f"EXEC sp_updateextendedproperty 'MS_Description', N'{escaped}', 'schema', '{schema}', 'table', '{table}'{level2}")


def upgrade():
    def new(schema, table, column):
        t = metadata.tables[f"{schema}.{table}"]
        return t.c[column].comment if column else t.comment

    op.add_column('AppUser', sa.Column('ScenarioDefinitionId', sa.Integer(), nullable=True, comment=new('adm', 'AppUser', 'ScenarioDefinitionId')), schema='adm')
    op.add_column('AuditLog', sa.Column('ScenarioName', sa.Unicode(length=100), nullable=True, comment=new('adm', 'AuditLog', 'ScenarioName')), schema='adm')
    op.add_column('ScenarioDefinition', sa.Column('FollowsBase', sa.Boolean(), nullable=True, comment=new('param', 'ScenarioDefinition', 'FollowsBase')),
                  schema='param')
    for key in OLD:
        _comment(*key, new(*key))
    # eski sentetik setin kalıntısı
    for child in CHILDREN:
        op.execute(f"DELETE FROM param.[{child}] WHERE ScenarioDefinitionId IN ({LEFTOVER})")
    op.execute(f"DELETE FROM {SD} WHERE Id IN ({LEFTOVER})")
    # var olan Baz dışı senaryolar Baz'ı izlemez
    op.execute(f"UPDATE {SD} SET FollowsBase = 0 WHERE ISNULL(IsBase, 0) = 0")
    # denetim izinde senaryo adı: kayıt "<ad> · <parametre>" biçiminde yazılmıştı
    op.execute("UPDATE adm.AuditLog SET ScenarioName = LEFT(ObjectKey, CHARINDEX(N' · ', ObjectKey) - 1) "
               "WHERE ObjectType = N'Senaryo' AND ScenarioName IS NULL AND CHARINDEX(N' · ', ObjectKey) > 1")
    if not context.is_offline_mode():
        sync(op.get_bind(), metadata)


def downgrade():
    for key, text in OLD.items():
        _comment(*key, text)
    op.execute("DELETE FROM adm.FieldDefinition WHERE (TableName = N'ScenarioDefinition' AND FieldName = N'FollowsBase')")
    op.drop_column('ScenarioDefinition', 'FollowsBase', schema='param')
    op.drop_column('AuditLog', 'ScenarioName', schema='adm')
    op.drop_column('AppUser', 'ScenarioDefinitionId', schema='adm')
