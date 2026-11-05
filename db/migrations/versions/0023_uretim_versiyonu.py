"""0023 · Material.IsCritical (K-113); Üretim versiyonu (K-114): LocationCode ve anahtar, yeni alanlar, IsDefault kalkar

Var olan versiyonlarda LocationId malzemeden gelir. BOMCode zorunlu; var olan satırlara versiyon kodu yazılır, gerçek değer sonraki yüklemede gelir.
stg ham veridir, doldurulmaz. Geri alışta bütün versiyonlar IsDefault = 1 olur.

Revision ID: 0023
Revises: 0022
Create Date: 2026-11-04
"""
from alembic import context, op
import sqlalchemy as sa

from dictionary import sync
from models import metadata


revision = '0023'
down_revision = '0022'
branch_labels = None
depends_on = None

SCHEMAS = ('core', 'stg')
FD = 'adm.FieldDefinition'
CRITICAL = 'Kritik malzeme; malzeme kısıtı yalnız kritik malzemelere uygulanır, kritik olmayanın her zaman temin edilebildiği varsayılır'
OLD_DESC = "Üretim versiyonu: bir malzemenin ürün ağacı ve rota başlığı; rotaya RouteCode ile bağlanır. Faz 1'de varsayılan versiyon kullanılır."
NEW_DESC = 'Üretim versiyonu: bir malzemenin ürün ağacı ve rota başlığı; rotaya RouteCode, ürün ağacına BOMCode ile bağlanır. Versiyon seçimi motorun kararıdır; aynı malzeme aynı dönemde birden fazla versiyonla üretilebilir.'
OPTIONAL = (
    ('Name', sa.Unicode(length=100), 'Versiyon adı'),
    ('Type', sa.Unicode(length=50), 'Versiyonları ayrıştırmak için kurallarda kullanılır; değer listesi yok'),
    ('IsActive', sa.Boolean(), 'Aktif'),
    ('Priority', sa.Integer(), 'Versiyonlar arası tercih bilgisi; motora girdi'),
)
BOM_COMMENT = 'Versiyonun kullandığı ürün ağacı'


def _table_comment(schema, text):
    escaped = text.replace("'", "''")
    op.execute(f"EXEC sp_updateextendedproperty 'MS_Description', N'{escaped}', 'schema', '{schema}', 'table', 'ProductionVersion'")


def upgrade():
    for schema in SCHEMAS:
        op.add_column('Material', sa.Column('IsCritical', sa.Boolean(), nullable=True, comment=CRITICAL), schema=schema)
        for name, type_, comment in OPTIONAL:
            op.add_column('ProductionVersion', sa.Column(name, type_, nullable=True, comment=comment), schema=schema)
    op.add_column('ProductionVersion', sa.Column('LocationId', sa.Integer(), nullable=True, comment='Lokasyon'), schema='core')
    op.add_column('ProductionVersion', sa.Column('BOMCode', sa.Unicode(length=50), nullable=True, comment=BOM_COMMENT), schema='core')
    op.execute("UPDATE pv SET BOMCode = pv.Code, LocationId = (SELECT TOP 1 m.LocationId FROM core.Material m WHERE m.Id = pv.MaterialId ORDER BY m.VersionFrom DESC) "
               "FROM core.ProductionVersion pv")
    op.alter_column('ProductionVersion', 'LocationId', existing_type=sa.Integer(), nullable=False, existing_comment='Lokasyon', schema='core')
    op.alter_column('ProductionVersion', 'BOMCode', existing_type=sa.Unicode(length=50), nullable=False, existing_comment=BOM_COMMENT, schema='core')
    op.create_foreign_key(op.f('FK_ProductionVersion_LocationId'), 'ProductionVersion', 'Location', ['LocationId'], ['Id'], source_schema='core', referent_schema='core')
    op.add_column('ProductionVersion', sa.Column('LocationCode', sa.Unicode(length=30), nullable=True, comment='Lokasyon kodu'), schema='stg')
    op.add_column('ProductionVersion', sa.Column('BOMCode', sa.Unicode(length=50), nullable=True, comment=BOM_COMMENT), schema='stg')
    op.drop_column('ProductionVersion', 'IsDefault', schema='core', mssql_drop_default=True)
    op.drop_column('ProductionVersion', 'IsDefault', schema='stg')
    op.create_index('UX_ProductionVersion_LocationId_MaterialId_Code', 'ProductionVersion', ['LocationId', 'MaterialId', 'Code'], unique=True, schema='core', mssql_where=sa.text('VersionTo IS NULL'))
    op.create_index('UX_ProductionVersion_LocationCode_MaterialCode_Code', 'ProductionVersion', ['LocationCode', 'MaterialCode', 'Code'], unique=True, schema='stg')
    for schema in SCHEMAS:
        _table_comment(schema, NEW_DESC)
    op.execute(f"DELETE FROM {FD} WHERE TableName = N'ProductionVersion' AND FieldName = N'IsDefault'")
    if not context.is_offline_mode():  # bağlantısız SQL betiğinde satırlar yazılmaz; ilk bağlantılı geçişte kurulur
        sync(op.get_bind(), metadata)


def downgrade():
    op.execute(f"DELETE FROM {FD} WHERE TableName = N'Material' AND FieldName = N'IsCritical'")
    op.execute(f"DELETE FROM {FD} WHERE TableName = N'ProductionVersion' AND FieldName IN (N'LocationId', N'Name', N'Type', N'IsActive', N'Priority', N'BOMCode')")
    op.execute(f"INSERT INTO {FD} (TableName, FieldName, FieldClass, DefaultValue, IsRequired, StandardLabel, Description) VALUES "
               "(N'ProductionVersion', N'IsDefault', N'Ana veri', N'1', 1, N'Varsayılan versiyon', N'Varsayılan versiyon')")
    for schema in SCHEMAS:
        _table_comment(schema, OLD_DESC)
    op.drop_index('UX_ProductionVersion_LocationCode_MaterialCode_Code', table_name='ProductionVersion', schema='stg')
    op.drop_index('UX_ProductionVersion_LocationId_MaterialId_Code', table_name='ProductionVersion', schema='core', mssql_where=sa.text('VersionTo IS NULL'))
    op.add_column('ProductionVersion', sa.Column('IsDefault', sa.Boolean(), nullable=True, comment='Varsayılan versiyon'), schema='stg')
    op.add_column('ProductionVersion', sa.Column('IsDefault', sa.Boolean(), server_default=sa.text('1'), nullable=False, comment='Varsayılan versiyon'), schema='core')
    op.drop_constraint(op.f('FK_ProductionVersion_LocationId'), 'ProductionVersion', schema='core', type_='foreignkey')
    op.drop_column('ProductionVersion', 'LocationId', schema='core')
    op.drop_column('ProductionVersion', 'LocationCode', schema='stg')
    for schema in SCHEMAS:
        op.drop_column('ProductionVersion', 'BOMCode', schema=schema)
        for name, _, _ in reversed(OPTIONAL):
            op.drop_column('ProductionVersion', name, schema=schema)
        op.drop_column('Material', 'IsCritical', schema=schema)
