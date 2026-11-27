"""0086 · Plan uyarısına dönem ve kayıt bağı (K-206)

`planning.PlanWarning`'e dönem (`PeriodStart`, `PeriodEnd`) ve ilgili kayda bağlar (`ResourceGroupId`, `MaterialId`, `PlannedDemandId`,
`PlannedSupplyId`) eklenir; hepsi boş olabilir. Var olan uyarı satırlarında boş kalır (fikstür planı yeniden yüklenince dolar). Veri kaybı yok.

Revision ID: 0086
Revises: 0085
Create Date: 2026-11-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql


revision = '0086'
down_revision = '0085'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('PlanWarning', sa.Column('PeriodStart', sa.DATE(), nullable=True, comment='Uyarının döneminin ilk günü (dönemli uyarıda; K-206)'), schema='planning')
    op.add_column('PlanWarning', sa.Column('PeriodEnd', sa.DATE(), nullable=True, comment='Uyarının döneminin son günü'), schema='planning')
    op.add_column('PlanWarning', sa.Column('ResourceGroupId', sa.BigInteger(), nullable=True, comment='İlgili kaynak grubu (kapasite uyarıları)'), schema='planning')
    op.add_column('PlanWarning', sa.Column('MaterialId', sa.BigInteger(), nullable=True, comment='İlgili malzeme'), schema='planning')
    op.add_column('PlanWarning', sa.Column('PlannedDemandId', sa.BigInteger(), nullable=True, comment='İlgili talep (talep uyarıları)'), schema='planning')
    op.add_column('PlanWarning', sa.Column('PlannedSupplyId', sa.BigInteger(), nullable=True, comment='İlgili tedarik planı kaydı (malzeme uyarıları)'), schema='planning')
    op.create_index(op.f('IX_PlanWarning_MaterialId'), 'PlanWarning', ['MaterialId'], unique=False, schema='planning')
    op.create_index(op.f('IX_PlanWarning_PlannedDemandId'), 'PlanWarning', ['PlannedDemandId'], unique=False, schema='planning')
    op.create_index(op.f('IX_PlanWarning_PlannedSupplyId'), 'PlanWarning', ['PlannedSupplyId'], unique=False, schema='planning')
    op.create_index(op.f('IX_PlanWarning_ResourceGroupId'), 'PlanWarning', ['ResourceGroupId'], unique=False, schema='planning')
    op.create_foreign_key(op.f('FK_PlanWarning_PlannedSupplyId'), 'PlanWarning', 'PlannedSupply', ['PlannedSupplyId'], ['Id'], source_schema='planning', referent_schema='planning')
    op.create_foreign_key(op.f('FK_PlanWarning_PlannedDemandId'), 'PlanWarning', 'PlannedDemand', ['PlannedDemandId'], ['Id'], source_schema='planning', referent_schema='planning')


def downgrade():
    op.drop_constraint(op.f('FK_PlanWarning_PlannedDemandId'), 'PlanWarning', schema='planning', type_='foreignkey')
    op.drop_constraint(op.f('FK_PlanWarning_PlannedSupplyId'), 'PlanWarning', schema='planning', type_='foreignkey')
    op.drop_index(op.f('IX_PlanWarning_ResourceGroupId'), table_name='PlanWarning', schema='planning')
    op.drop_index(op.f('IX_PlanWarning_PlannedSupplyId'), table_name='PlanWarning', schema='planning')
    op.drop_index(op.f('IX_PlanWarning_PlannedDemandId'), table_name='PlanWarning', schema='planning')
    op.drop_index(op.f('IX_PlanWarning_MaterialId'), table_name='PlanWarning', schema='planning')
    op.drop_column('PlanWarning', 'PlannedSupplyId', schema='planning')
    op.drop_column('PlanWarning', 'PlannedDemandId', schema='planning')
    op.drop_column('PlanWarning', 'MaterialId', schema='planning')
    op.drop_column('PlanWarning', 'ResourceGroupId', schema='planning')
    op.drop_column('PlanWarning', 'PeriodEnd', schema='planning')
    op.drop_column('PlanWarning', 'PeriodStart', schema='planning')
