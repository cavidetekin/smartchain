"""0058 · Senaryo parametreleri (K-175): parametre seti kalkar, her senaryo parametrelerinin tamamını taşır; Baz senaryo; hedefler

Veri silinmez. Baz açılır (sentetik olmayan varsayılan set varsa onun satırlarıyla, yoksa katalogdaki başlangıç değerleriyle). Öteki setler kendi
adlarıyla pasif senaryoya çevrilir; var olan senaryo tanımları setlerinin satırlarının kopyasını alır, eski `IsActive` ("gece çalışsın") `RunsNightly`
olur. Sentetik setin `PriorityRule` ve `SupplierLimit` satırları Baz'a bağlanır (sentetik yükleme artık oraya yazar). `ParameterSetId` taşıyan
tablolarda kolon `ScenarioDefinitionId` olur. `TimeBucketDefinition`'a eksen (`Axis`) ve kapsam birimi (`SpanUnit`) gelir; eski satırda kapsam birimi
dönem tipidir (Çeyrek ve Yıl aya çevrilir). Yeni tablo `ObjectiveDefinition`.

Geri alınmaz: `ParameterSet` tablosu ve set–senaryo bağı kaldırıldı; geri dönüş yedekten yapılır.

Revision ID: 0058
Revises: 0057
Create Date: 2026-11-16
"""
import sys
from pathlib import Path

from alembic import context, op
import sqlalchemy as sa

from dictionary import sync
from models import metadata

revision = '0058'
down_revision = '0057'
branch_labels = None
depends_on = None

SD = 'param.ScenarioDefinition'
KEYED = ('PlanningSetting', 'TimeBucketDefinition', 'PriorityRule')          # anahtarında set olanlar
PLAIN = ('ResourceEfficiency', 'ResourcePeriodLimit', 'OvertimeLimit', 'SupplierLimit', 'AllocationRule')
COPY = {  # var olan senaryo tanımına setinden kopyalanan kolonlar
    'PlanningSetting': 'SettingKey, Value',
    'TimeBucketDefinition': 'Axis, Seq, BucketType, [Count], SpanUnit',
    'PriorityRule': 'Seq, Criterion, Direction',
    'ResourceEfficiency': 'ResourceId, ValidFrom, ValidTo, EfficiencyPct',
    'ResourcePeriodLimit': 'ResourceId, ValidFrom, ValidTo, UpperLimit',
    'OvertimeLimit': 'ShiftPlanId, MaxOvertimeHours',
    'SupplierLimit': 'SupplierId, MaterialId, ValidFrom, ValidTo, UpperLimit',
    'AllocationRule': 'DemandClass, ResourceId, ResourceGroupId, ValidFrom, ValidTo, SharePct, Hardness',
}
PRIMARY = {'PlanningSetting': ['ScenarioDefinitionId', 'SettingKey'], 'TimeBucketDefinition': ['ScenarioDefinitionId', 'Axis', 'Seq'],
           'PriorityRule': ['ScenarioDefinitionId', 'Seq']}
COMMENTED = [('param', t) for t in (*KEYED, *PLAIN, 'ScenarioDefinition', 'ObjectiveDefinition')] + [('planning', 'PlanRun')]
BASE = f"(SELECT Id FROM {SD} WHERE IsBase = 1)"


def _catalog():
    root = str(Path(__file__).resolve().parents[3])
    if root not in sys.path:
        sys.path.insert(0, root)
    from app.params import catalog
    return catalog


def _n(text: str) -> str:
    return "N'" + str(text).replace("'", "''") + "'"


def _comments():
    """Kolon ve tablo açıklamaları modelden (docs/02): yeniden adlandırılan ve yeni kolonlarda; kolon yoksa atlanır."""
    for schema, name in COMMENTED:
        table = metadata.tables.get(f"{schema}.{name}")
        if table is None:
            continue
        items = [(None, table.comment)] + [(c.name, c.comment) for c in table.columns]
        for column, comment in items:
            if not comment:
                continue
            level2 = f", 'column', '{column}'" if column else ""
            exists = (f"EXISTS (SELECT 1 FROM sys.extended_properties p WHERE p.name = 'MS_Description' AND p.major_id = OBJECT_ID('{schema}.{name}') "
                      + (f"AND p.minor_id = COLUMNPROPERTY(OBJECT_ID('{schema}.{name}'), '{column}', 'ColumnId'))" if column else "AND p.minor_id = 0)"))
            guard = f"COL_LENGTH('{schema}.{name}', '{column}') IS NOT NULL" if column else f"OBJECT_ID('{schema}.{name}') IS NOT NULL"
            args = f"'MS_Description', {_n(comment)}, 'schema', '{schema}', 'table', '{name}'{level2}"
            op.execute(f"IF {guard} BEGIN IF {exists} EXEC sp_updateextendedproperty {args} ELSE EXEC sp_addextendedproperty {args} END")


def upgrade():
    cat = _catalog()

    # 1 · Senaryo tanımı: yeni kolonlar; eski "gece çalışsın" RunsNightly olur
    op.drop_constraint('FK_ScenarioDefinition_ParameterSetId', 'ScenarioDefinition', schema='param', type_='foreignkey')
    op.alter_column('ScenarioDefinition', 'ParameterSetId', existing_type=sa.Integer(), nullable=True, schema='param')
    op.alter_column('ScenarioDefinition', 'LocationId', existing_type=sa.Integer(), nullable=True, schema='param')
    op.add_column('ScenarioDefinition', sa.Column('IsBase', sa.Boolean(), server_default=sa.text('0'), nullable=True), schema='param')
    op.add_column('ScenarioDefinition', sa.Column('RunsNightly', sa.Boolean(), server_default=sa.text('0'), nullable=True), schema='param')
    op.add_column('ScenarioDefinition', sa.Column('IsSynthetic', sa.Boolean(), server_default=sa.text('0'), nullable=True), schema='param')
    op.add_column('ScenarioDefinition', sa.Column('LegacySetId', sa.Integer(), nullable=True), schema='param')  # geçiş süresince set ↔ senaryo
    op.execute(f"UPDATE {SD} SET RunsNightly = ISNULL(IsActive, 1), IsActive = 1, IsBase = 0, IsSynthetic = 0")
    # ad tekil olacak: "Baz" adını taşıyan ve adı yinelenen tanım numarasıyla ayrışır
    op.execute(f"UPDATE d SET Name = LEFT(d.Name, 85) + N' #' + CAST(d.Id AS nvarchar(12)) FROM {SD} d "
               f"WHERE d.Name = {_n(cat.BASE_NAME)} OR EXISTS (SELECT 1 FROM {SD} o WHERE o.Name = d.Name AND o.Id < d.Id)")
    # Baz: sentetik olmayan varsayılan set varsa onun satırlarını alır
    op.execute(f"INSERT INTO {SD} (Name, IsBase, IsActive, RunsNightly, IsSynthetic, LegacySetId) "
               f"SELECT {_n(cat.BASE_NAME)}, 1, 1, 0, 0, (SELECT TOP 1 Id FROM param.ParameterSet WHERE IsDefault = 1 AND ISNULL(IsSynthetic, 0) = 0 ORDER BY Id)")
    # öteki setler pasif senaryo (veri silinmez)
    op.execute(f"INSERT INTO {SD} (Name, IsBase, IsActive, RunsNightly, IsSynthetic, LegacySetId) "
               f"SELECT CASE WHEN EXISTS (SELECT 1 FROM {SD} d WHERE d.Name = p.Name) OR EXISTS (SELECT 1 FROM param.ParameterSet o WHERE o.Name = p.Name AND o.Id < p.Id) "
               "THEN LEFT(p.Name, 80) + N' · set ' + CAST(p.Id AS nvarchar(12)) ELSE p.Name END, 0, 0, 0, ISNULL(p.IsSynthetic, 0), p.Id "
               f"FROM param.ParameterSet p WHERE NOT EXISTS (SELECT 1 FROM {SD} d WHERE d.LegacySetId = p.Id)")

    # 2 · Sete bağlı tablolar: ScenarioDefinitionId
    for name in (*KEYED, *PLAIN):
        op.drop_constraint(f'FK_{name}_ParameterSetId', name, schema='param', type_='foreignkey')
        if name in KEYED:
            op.drop_constraint(f'PK_{name}', name, schema='param', type_='primary')
        op.add_column(name, sa.Column('ScenarioDefinitionId', sa.Integer(), nullable=True), schema='param')
    op.add_column('TimeBucketDefinition', sa.Column('Axis', sa.Unicode(length=10), server_default=sa.text("N'Plan'"), nullable=False), schema='param')
    op.add_column('TimeBucketDefinition', sa.Column('SpanUnit', sa.Unicode(length=10), nullable=True), schema='param')
    op.execute("UPDATE param.TimeBucketDefinition SET SpanUnit = CASE WHEN BucketType IN (N'Çeyrek', N'Yıl') THEN N'Ay' ELSE BucketType END, "
               "[Count] = CASE BucketType WHEN N'Çeyrek' THEN [Count] * 3 WHEN N'Yıl' THEN [Count] * 12 ELSE [Count] END, "
               "BucketType = CASE WHEN BucketType IN (N'Çeyrek', N'Yıl') THEN N'Ay' ELSE BucketType END")
    for name in (*KEYED, *PLAIN):
        op.execute(f"UPDATE t SET ScenarioDefinitionId = d.Id FROM param.[{name}] t JOIN {SD} d ON d.LegacySetId = t.ParameterSetId")
        # var olan senaryo tanımı setinin satırlarının kopyasını alır
        cols = COPY[name]
        op.execute(f"INSERT INTO param.[{name}] (ParameterSetId, ScenarioDefinitionId, {cols}) "
                   f"SELECT t.ParameterSetId, d.Id, {', '.join('t.' + c.strip() for c in cols.split(','))} FROM param.[{name}] t "
                   f"JOIN {SD} own ON own.LegacySetId = t.ParameterSetId AND own.Id = t.ScenarioDefinitionId "
                   f"JOIN {SD} d ON d.ParameterSetId = t.ParameterSetId AND d.LegacySetId IS NULL")
    # eski senaryo kolonları parametre anahtarı olur (tek yer)
    for key, expr in (("ModelType", "d.ModelType"), ("ResourceConstraint", "d.ResourceConstraint"),
                      ("MaterialConstraint", "CASE WHEN d.MaterialConstraint = 0 THEN N'0' ELSE N'1' END")):
        op.execute(f"DELETE s FROM param.PlanningSetting s JOIN {SD} d ON d.Id = s.ScenarioDefinitionId "
                   f"WHERE d.ParameterSetId IS NOT NULL AND d.LegacySetId IS NULL AND s.SettingKey = N'{key}'")
        op.execute("INSERT INTO param.PlanningSetting (ParameterSetId, ScenarioDefinitionId, SettingKey, Value) "
                   f"SELECT d.ParameterSetId, d.Id, N'{key}', {expr} FROM {SD} d WHERE d.ParameterSetId IS NOT NULL AND d.LegacySetId IS NULL AND {expr} IS NOT NULL")
    # sentetik setin sıralama kuralı ve tedarikçi limiti Baz'a (Baz'da yoksa)
    for name in ('PriorityRule', 'SupplierLimit'):
        op.execute(f"UPDATE t SET ScenarioDefinitionId = {BASE} FROM param.[{name}] t JOIN {SD} d ON d.Id = t.ScenarioDefinitionId "
                   f"WHERE d.IsSynthetic = 1 AND d.LegacySetId IS NOT NULL AND NOT EXISTS (SELECT 1 FROM param.[{name}] b WHERE b.ScenarioDefinitionId = {BASE})")

    # 3 · Plan hesabı
    op.drop_constraint('FK_PlanRun_ParameterSetId', 'PlanRun', schema='planning', type_='foreignkey')
    op.add_column('PlanRun', sa.Column('ScenarioDefinitionId', sa.Integer(), nullable=True), schema='planning')
    op.execute(f"UPDATE r SET ScenarioDefinitionId = d.Id FROM planning.PlanRun r JOIN {SD} d ON d.LegacySetId = r.ParameterSetId")

    # 4 · Eski kolonlar kalkar, anahtarlar ve bağlar kurulur
    for schema, name in [('param', n) for n in (*KEYED, *PLAIN)] + [('planning', 'PlanRun')]:
        op.drop_column(name, 'ParameterSetId', schema=schema)
        op.alter_column(name, 'ScenarioDefinitionId', existing_type=sa.Integer(), nullable=False, schema=schema)
        if name in PRIMARY:
            op.create_primary_key(f'PK_{name}', name, PRIMARY[name], schema=schema)
        op.create_foreign_key(op.f(f'FK_{name}_ScenarioDefinitionId'), name, 'ScenarioDefinition', ['ScenarioDefinitionId'], ['Id'],
                              source_schema=schema, referent_schema='param')
    op.alter_column('TimeBucketDefinition', 'SpanUnit', existing_type=sa.Unicode(length=10), nullable=False, schema='param')
    op.drop_column('ScenarioDefinition', 'ParameterSetId', schema='param')
    for column in ('ModelType', 'ResourceConstraint', 'MaterialConstraint'):
        op.drop_column('ScenarioDefinition', column, schema='param', mssql_drop_default=True)
    op.drop_column('ScenarioDefinition', 'LegacySetId', schema='param')
    op.create_index('UX_ScenarioDefinition_Name', 'ScenarioDefinition', ['Name'], unique=True, schema='param')
    op.drop_table('ParameterSet', schema='param')

    # 5 · Hedefler
    op.create_table(
        'ObjectiveDefinition',
        sa.Column('Id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('ScenarioDefinitionId', sa.Integer(), nullable=False),
        sa.Column('Code', sa.Unicode(length=30), nullable=False),
        sa.Column('PriorityGroup', sa.Integer(), nullable=True),
        sa.Column('Seq', sa.Integer(), nullable=True),
        sa.Column('TimeBudgetSeconds', sa.Integer(), nullable=True),
        sa.Column('TolerancePct', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('IsActive', sa.Boolean(), server_default=sa.text('1'), nullable=True),
        sa.ForeignKeyConstraint(['ScenarioDefinitionId'], ['param.ScenarioDefinition.Id'], name=op.f('FK_ObjectiveDefinition_ScenarioDefinitionId')),
        sa.PrimaryKeyConstraint('Id', name=op.f('PK_ObjectiveDefinition')),
        schema='param',
    )
    op.create_index('UX_ObjectiveDefinition_ScenarioDefinitionId_Code_PriorityGroup', 'ObjectiveDefinition',
                    ['ScenarioDefinitionId', 'Code', 'PriorityGroup'], unique=True, schema='param')

    # 6 · Baz'ın başlangıç değerleri (katalog): eksik parametreler, hedefler, dönem dizisi
    for key, value in cat.DEFAULTS.items():
        op.execute(f"INSERT INTO param.PlanningSetting (ScenarioDefinitionId, SettingKey, Value) SELECT d.Id, N'{key}', {_n(value)} FROM {SD} d "
                   f"WHERE d.IsBase = 1 AND NOT EXISTS (SELECT 1 FROM param.PlanningSetting s WHERE s.ScenarioDefinitionId = d.Id AND s.SettingKey = N'{key}')")
    seq = 0
    for o in cat.OBJECTIVES:
        active = o.seconds is not None
        seq += 1 if active else 0
        values = f"{seq}, {o.seconds}, {o.tolerance}, 1" if active else "NULL, NULL, NULL, 0"
        op.execute("INSERT INTO param.ObjectiveDefinition (ScenarioDefinitionId, Code, PriorityGroup, Seq, TimeBudgetSeconds, TolerancePct, IsActive) "
                   f"SELECT d.Id, N'{o.code}', NULL, {values} FROM {SD} d WHERE d.IsBase = 1")
    rows = ", ".join(f"({i}, {_n(bucket)}, {count}, {_n(unit)})" for i, (bucket, count, unit) in enumerate(cat.DEFAULT_BUCKETS, start=1))
    op.execute("INSERT INTO param.TimeBucketDefinition (ScenarioDefinitionId, Axis, Seq, BucketType, [Count], SpanUnit) "
               f"SELECT d.Id, N'Plan', v.Seq, v.BucketType, v.Cnt, v.SpanUnit FROM {SD} d CROSS JOIN (VALUES {rows}) v (Seq, BucketType, Cnt, SpanUnit) "
               "WHERE d.IsBase = 1 AND NOT EXISTS (SELECT 1 FROM param.TimeBucketDefinition t WHERE t.ScenarioDefinitionId = d.Id AND t.Axis = N'Plan')")

    # 7 · Açıklamalar ve veri sözlüğü
    _comments()
    op.execute("DELETE FROM adm.FieldDefinition WHERE TableName = N'ParameterSet' OR FieldName = N'ParameterSetId' "
               "OR (TableName = N'ScenarioDefinition' AND FieldName IN (N'ModelType', N'ResourceConstraint', N'MaterialConstraint'))")
    if not context.is_offline_mode():  # bağlantısız SQL betiğinde satırlar yazılmaz; ilk bağlantılı geçişte kurulur
        sync(op.get_bind(), metadata)


def downgrade():
    raise RuntimeError("0058 geri alınmaz (K-175): parametre seti tablosu ve set–senaryo bağı kaldırıldı; geri dönüş yedekten yapılır.")
