"""0025 · Rota (K-116): LocationId ve anahtar; ad değişiklikleri; kaynak ya da kaynak grubu; yeni alanlar; işçilik alanları kalkar

Var olan satırlarda LocationId kaynağın lokasyonundan gelir. İşçilik alanlarındaki değerler dönüştürülmez: yetkinlik grubu kaynak grubu değildir,
işçilik satırları yeni yüklemede ayrı kaynak satırı olarak gelir. stg ham veridir, doldurulmaz.
Geri alışta kaynağı boş satırlar (eski modelde karşılığı yok) silinir, işçilik alanları varsayılanlarıyla boş döner.

Revision ID: 0025
Revises: 0024
Create Date: 2026-11-04
"""
from alembic import context, op
import sqlalchemy as sa

from dictionary import sync
from models import metadata


revision = '0025'
down_revision = '0024'
branch_labels = None
depends_on = None

SCHEMAS = ('core', 'stg')
FD = 'adm.FieldDefinition'
COLLATION = 'Latin1_General_100_CI_AS_SC'
RENAMED = {'OpNo': 'OperationNo', 'SeqNo': 'SequenceNo', 'TransferLotQty': 'TransferQuantity'}
SUFFIX = 'Aynı operasyonun kaynakları ayrı satırda, ResourceRole ile.'
OLD_DESC = f'Rota: her satır bir operasyon–kaynak ilişkisi; sıra önce OpNo, sonra SeqNo. {SUFFIX}'
NEW_DESC = f'Rota: her satır bir operasyon–kaynak ilişkisi; sıra önce OperationNo, sonra SequenceNo. {SUFFIX}'
OPTIONAL = (
    ('IsActive', sa.Boolean(), 'Operasyon plana dahil mi'),
    ('ProductionLocation', sa.Unicode(length=50), 'Lokasyonun alt tanımı (hol, hat); ileride kısıtlar için'),
    ('WaitingTimeHours', sa.Numeric(precision=9, scale=2), 'Operasyon öncesi kuyruk beklemesi'),
    ('TransferTimeHours', sa.Numeric(precision=9, scale=2), 'Sonraki operasyona taşıma'),
    ('AlternativeGroup', sa.Unicode(length=50), 'Aynı gruptaki satırlar birbirinin alternatifidir'),
    ('AlternativePriority', sa.Integer(), 'Grup içindeki tercih bilgisi'),
)
LOT = 'Doluysa tüketim üretilen miktardan bağımsız, lot başına sabit; pratikte hazırlık süresi'
UNIQUE_CORE = 'UX_Routing_LocationId_RouteCode_OperationNo_SequenceNo'
UNIQUE_STG = 'UX_Routing_LocationCode_RouteCode_OperationNo_SequenceNo'
ADDED = ('LocationId', 'ResourceGroupId', 'IsLotBasedUsage') + tuple(name for name, _, _ in OPTIONAL)
TYPE_DESC, BASIS_DESC = 'İşçi: Yetkinlik grubu | Kaynak grubu | Yok', 'Ekip (süre × kişi) | Toplam (adam-saat)'
TIME_CORE = 'Toplam işçilik süresi; işçilik esası Toplam olduğunda kullanılır'
TIME_STG = 'Toplam işçilik (adam-saat), LaborBasis = Toplam ise'


def _table_comment(schema, text):
    op.execute(f"EXEC sp_updateextendedproperty 'MS_Description', N'{text}', 'schema', '{schema}', 'table', 'Routing'")


def _rename(pairs):
    for schema in SCHEMAS:
        for old, new in pairs:
            op.alter_column('Routing', old, new_column_name=new, schema=schema)


def upgrade():
    op.drop_index('UX_Routing_RouteCode_OpNo_SeqNo', table_name='Routing', schema='core', mssql_where=sa.text('VersionTo IS NULL'))
    op.drop_index('UX_Routing_RouteCode_OpNo_SeqNo', table_name='Routing', schema='stg')
    _rename(RENAMED.items())
    op.add_column('Routing', sa.Column('LocationId', sa.Integer(), nullable=True, comment='Lokasyon'), schema='core')
    op.execute("UPDATE r SET LocationId = (SELECT TOP 1 x.LocationId FROM core.Resource x WHERE x.Id = r.ResourceId ORDER BY x.VersionFrom DESC) FROM core.Routing r")
    op.alter_column('Routing', 'LocationId', existing_type=sa.Integer(), nullable=False, existing_comment='Lokasyon', schema='core')
    op.drop_index(op.f('IX_Routing_ResourceId'), table_name='Routing', schema='core')  # zorunluluk indeks varken değişmez
    op.alter_column('Routing', 'ResourceId', existing_type=sa.BigInteger(), nullable=True, existing_comment='Kaynak', schema='core')
    op.create_index(op.f('IX_Routing_ResourceId'), 'Routing', ['ResourceId'], unique=False, schema='core')
    op.add_column('Routing', sa.Column('ResourceGroupId', sa.BigInteger(), nullable=True, comment='Kaynak grubu'), schema='core')
    op.add_column('Routing', sa.Column('LocationCode', sa.Unicode(length=30), nullable=True, comment='Lokasyon kodu'), schema='stg')
    op.add_column('Routing', sa.Column('ResourceGroupCode', sa.Unicode(length=50), nullable=True, comment='Kaynak grubu'), schema='stg')
    for schema in SCHEMAS:
        for name, type_, comment in OPTIONAL:
            op.add_column('Routing', sa.Column(name, type_, nullable=True, comment=comment), schema=schema)
    op.add_column('Routing', sa.Column('IsLotBasedUsage', sa.Boolean(), server_default=sa.text('0'), nullable=True, comment=LOT), schema='core')
    op.add_column('Routing', sa.Column('IsLotBasedUsage', sa.Boolean(), nullable=True, comment=LOT), schema='stg')
    op.execute("UPDATE core.Routing SET IsLotBasedUsage = 0")
    for name in ('LaborType', 'LaborBasis', 'CrewSize'):
        op.drop_column('Routing', name, schema='core', mssql_drop_default=True)
        op.drop_column('Routing', name, schema='stg')
    op.drop_column('Routing', 'LaborRefId', schema='core')
    op.drop_column('Routing', 'LaborRefCode', schema='stg')
    for schema in SCHEMAS:
        op.drop_column('Routing', 'LaborTime', schema=schema)
        _table_comment(schema, NEW_DESC)
    op.create_index(op.f('IX_Routing_ResourceGroupId'), 'Routing', ['ResourceGroupId'], unique=False, schema='core')
    op.create_index(UNIQUE_CORE, 'Routing', ['LocationId', 'RouteCode', 'OperationNo', 'SequenceNo'], unique=True, schema='core', mssql_where=sa.text('VersionTo IS NULL'))
    op.create_index(UNIQUE_STG, 'Routing', ['LocationCode', 'RouteCode', 'OperationNo', 'SequenceNo'], unique=True, schema='stg')
    op.create_foreign_key(op.f('FK_Routing_LocationId'), 'Routing', 'Location', ['LocationId'], ['Id'], source_schema='core', referent_schema='core')
    # Sözlük: elle verilen etiket yeni adda kalır; sync silmez, IsRequired'a dokunmaz.
    for old, new in RENAMED.items():
        op.execute(f"UPDATE {FD} SET FieldName = N'{new}' WHERE TableName = N'Routing' AND FieldName = N'{old}'")
    op.execute(f"DELETE FROM {FD} WHERE TableName = N'Routing' AND FieldName IN (N'LaborType', N'LaborRefId', N'LaborBasis', N'CrewSize', N'LaborTime')")
    op.execute(f"UPDATE {FD} SET IsRequired = 0 WHERE TableName = N'Routing' AND FieldName = N'ResourceId'")
    if not context.is_offline_mode():  # bağlantısız SQL betiğinde satırlar yazılmaz; ilk bağlantılı geçişte kurulur
        sync(op.get_bind(), metadata)


def downgrade():
    names = ', '.join(f"N'{name}'" for name in ADDED)
    op.execute(f"DELETE FROM {FD} WHERE TableName = N'Routing' AND FieldName IN ({names})")
    for old, new in RENAMED.items():
        op.execute(f"UPDATE {FD} SET FieldName = N'{old}' WHERE TableName = N'Routing' AND FieldName = N'{new}'")
    op.execute(f"UPDATE {FD} SET StandardLabel = N'Alt sıra' WHERE TableName = N'Routing' AND FieldName = N'SeqNo'")
    op.execute(f"UPDATE {FD} SET StandardLabel = N'Transfer partisi' WHERE TableName = N'Routing' AND FieldName = N'TransferLotQty'")
    op.execute(f"UPDATE {FD} SET IsRequired = 1 WHERE TableName = N'Routing' AND FieldName = N'ResourceId'")
    op.execute(f"INSERT INTO {FD} (TableName, FieldName, FieldClass, DefaultValue, StandardLabel, Description) VALUES "
               f"(N'Routing', N'LaborType', N'Ana veri', N'Yok', N'İşçilik tipi', N'{TYPE_DESC}'), "
               "(N'Routing', N'LaborRefId', N'Ana veri', NULL, N'İlgili yetkinlik ya da kaynak grubu', N'İlgili yetkinlik ya da kaynak grubu'), "
               f"(N'Routing', N'LaborBasis', N'Ana veri', N'Ekip', N'İşçilik esası', N'{BASIS_DESC}'), "
               "(N'Routing', N'CrewSize', N'Ana veri', N'1', N'Gerekli işçi sayısı', N'Gerekli işçi sayısı'), "
               f"(N'Routing', N'LaborTime', N'Ana veri', NULL, N'Toplam işçilik (adam-saat)', N'{TIME_CORE}')")
    op.drop_constraint(op.f('FK_Routing_LocationId'), 'Routing', schema='core', type_='foreignkey')
    op.drop_index(UNIQUE_STG, table_name='Routing', schema='stg')
    op.drop_index(UNIQUE_CORE, table_name='Routing', schema='core', mssql_where=sa.text('VersionTo IS NULL'))
    op.drop_index(op.f('IX_Routing_ResourceGroupId'), table_name='Routing', schema='core')
    op.execute("DELETE FROM core.Routing WHERE ResourceId IS NULL")
    for schema in SCHEMAS:
        _table_comment(schema, OLD_DESC)
    collated = lambda n: sa.NVARCHAR(length=n, collation=COLLATION)  # noqa: E731
    op.add_column('Routing', sa.Column('LaborType', collated(15), server_default=sa.text("N'Yok'"), nullable=True, comment=TYPE_DESC), schema='core')
    op.add_column('Routing', sa.Column('LaborBasis', collated(10), server_default=sa.text("N'Ekip'"), nullable=True, comment=BASIS_DESC), schema='core')
    op.add_column('Routing', sa.Column('CrewSize', sa.Integer(), server_default=sa.text('1'), nullable=True, comment='Gerekli işçi sayısı'), schema='core')
    op.add_column('Routing', sa.Column('LaborRefId', sa.BigInteger(), nullable=True, comment='İlgili yetkinlik ya da kaynak grubu'), schema='core')
    op.add_column('Routing', sa.Column('LaborTime', sa.Numeric(precision=18, scale=6), nullable=True, comment=TIME_CORE), schema='core')
    op.add_column('Routing', sa.Column('LaborType', collated(15), nullable=True, comment=TYPE_DESC), schema='stg')
    op.add_column('Routing', sa.Column('LaborBasis', collated(10), nullable=True, comment=BASIS_DESC), schema='stg')
    op.add_column('Routing', sa.Column('CrewSize', sa.Integer(), nullable=True, comment='Gerekli işçi sayısı'), schema='stg')
    op.add_column('Routing', sa.Column('LaborRefCode', collated(50), nullable=True, comment='İlgili yetkinlik ya da kaynak grubu'), schema='stg')
    op.add_column('Routing', sa.Column('LaborTime', sa.Numeric(precision=18, scale=6), nullable=True, comment=TIME_STG), schema='stg')
    op.drop_column('Routing', 'IsLotBasedUsage', schema='core', mssql_drop_default=True)
    op.drop_column('Routing', 'IsLotBasedUsage', schema='stg')
    for schema in SCHEMAS:
        for name, _, _ in reversed(OPTIONAL):
            op.drop_column('Routing', name, schema=schema)
    op.drop_column('Routing', 'ResourceGroupCode', schema='stg')
    op.drop_column('Routing', 'LocationCode', schema='stg')
    op.drop_column('Routing', 'ResourceGroupId', schema='core')
    op.drop_index(op.f('IX_Routing_ResourceId'), table_name='Routing', schema='core')
    op.alter_column('Routing', 'ResourceId', existing_type=sa.BigInteger(), nullable=False, existing_comment='Kaynak', schema='core')
    op.create_index(op.f('IX_Routing_ResourceId'), 'Routing', ['ResourceId'], unique=False, schema='core')
    op.drop_column('Routing', 'LocationId', schema='core')
    _rename([(new, old) for old, new in RENAMED.items()])
    op.create_index('UX_Routing_RouteCode_OpNo_SeqNo', 'Routing', ['RouteCode', 'OpNo', 'SeqNo'], unique=True, schema='stg')
    op.create_index('UX_Routing_RouteCode_OpNo_SeqNo', 'Routing', ['RouteCode', 'OpNo', 'SeqNo'], unique=True, schema='core', mssql_where=sa.text('VersionTo IS NULL'))
