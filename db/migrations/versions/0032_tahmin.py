"""0032 · Tahmin (K-122): anahtar; Type, Uom, DeliveryPoint, IsActive

Var olan satırlarda yeni alanlar boş kalır. stg ham veridir. Aynı anahtarlı güncel satır varsa tekil indeks geçişi durdurur; veri silinmez.
Geri alışta yeni alanlar kaybolur.

Revision ID: 0032
Revises: 0031
Create Date: 2026-11-05
"""
from alembic import context, op
import sqlalchemy as sa

from dictionary import sync
from models import metadata


revision = '0032'
down_revision = '0031'
branch_labels = None
depends_on = None

SCHEMAS = ('core', 'stg')
T = 'Forecast'
NEW = (
    ('Type', sa.Unicode(length=50), "Hangisinin plana gireceği veri kuralıyla seçilir; ERP'den ham değer, değer listesi yok"),
    ('Uom', sa.Unicode(length=10), 'Miktarın birimi; boşsa malzemenin temel biriminde kabul edilir, doluysa birim dönüşümüyle çevrilir'),
    ('DeliveryPoint', sa.Unicode(length=10), 'Miktarın dönemin başında mı sonunda mı hazır olması gerektiği: Başı | Sonu'),
    ('IsActive', sa.Boolean(), 'Aktif mi'),
)
UX_CORE = 'UX_Forecast_LocationId_MaterialId_CustomerId_ProjectId_Period_Type'
UX_STG = 'UX_Forecast_LocationCode_MaterialCode_CustomerCode_ProjectCode_Period_Type'
WHERE = sa.text('VersionTo IS NULL')


def upgrade():
    for schema in SCHEMAS:
        for name, type_, comment in NEW:
            op.add_column(T, sa.Column(name, type_, nullable=True, comment=comment), schema=schema)
    op.create_foreign_key(op.f('FK_Forecast_Uom'), T, 'UnitOfMeasure', ['Uom'], ['Code'], source_schema='core', referent_schema='core')
    op.create_index(UX_CORE, T, ['LocationId', 'MaterialId', 'CustomerId', 'ProjectId', 'Period', 'Type'], unique=True, schema='core', mssql_where=WHERE)
    op.create_index(UX_STG, T, ['LocationCode', 'MaterialCode', 'CustomerCode', 'ProjectCode', 'Period', 'Type'], unique=True, schema='stg')
    if not context.is_offline_mode():  # bağlantısız SQL betiğinde satırlar yazılmaz; ilk bağlantılı geçişte kurulur
        sync(op.get_bind(), metadata)


def downgrade():
    names = ', '.join(f"N'{n}'" for n, _, _ in NEW)
    op.execute(f"DELETE FROM adm.FieldDefinition WHERE TableName = N'{T}' AND FieldName IN ({names})")
    op.drop_index(UX_STG, table_name=T, schema='stg')
    op.drop_index(UX_CORE, table_name=T, schema='core', mssql_where=WHERE)
    op.drop_constraint(op.f('FK_Forecast_Uom'), T, schema='core', type_='foreignkey')
    for schema in SCHEMAS:
        for name, _, _ in reversed(NEW):
            op.drop_column(T, name, schema=schema)
