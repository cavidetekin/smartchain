"""0016 · Sadeleşen alan açıklamaları (K-104): dört alanın yorumu ve sözlükteki Description

Revision ID: 0016
Revises: 0015
Create Date: 2026-11-03
"""
from alembic import context, op
import sqlalchemy as sa

from dictionary import sync
from models import metadata


revision = '0016'
down_revision = '0015'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('Material', 'ShelfLifeDays',
               existing_type=sa.INTEGER(),
               comment='Raf ömrü; şimdilik yalnız uyarı için kullanılır',
               existing_comment="Raf ömrü (gün); Faz 1'de yalnız uyarı",
               existing_nullable=True,
               schema='core')
    op.alter_column('ProductionVersion', 'RouteCode',
               existing_type=sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'),
               comment='Rota kodu',
               existing_comment='Rota kodu (Routing.RouteCode)',
               existing_nullable=False,
               schema='core')
    op.alter_column('Routing', 'LaborTime',
               existing_type=sa.NUMERIC(precision=18, scale=6),
               comment='Toplam işçilik süresi; işçilik esası Toplam olduğunda kullanılır',
               existing_comment='Toplam işçilik (adam-saat), LaborBasis = Toplam ise',
               existing_nullable=True,
               schema='core')
    op.alter_column('PlanningSetting', 'SettingKey',
               existing_type=sa.NVARCHAR(length=60, collation='Latin1_General_100_CI_AS_SC'),
               comment='Parametre adı',
               existing_comment='Parametre adı (ör. ModelType, UseOvertime, FixPeriodDays)',
               existing_nullable=False,
               autoincrement=False,
               schema='param')
    if not context.is_offline_mode():  # bağlantısız SQL betiğinde satırlar yazılmaz; ilk bağlantılı geçişte kurulur
        sync(op.get_bind(), metadata)


def downgrade():
    op.alter_column('PlanningSetting', 'SettingKey',
               existing_type=sa.NVARCHAR(length=60, collation='Latin1_General_100_CI_AS_SC'),
               comment='Parametre adı (ör. ModelType, UseOvertime, FixPeriodDays)',
               existing_comment='Parametre adı',
               existing_nullable=False,
               autoincrement=False,
               schema='param')
    op.alter_column('Routing', 'LaborTime',
               existing_type=sa.NUMERIC(precision=18, scale=6),
               comment='Toplam işçilik (adam-saat), LaborBasis = Toplam ise',
               existing_comment='Toplam işçilik süresi; işçilik esası Toplam olduğunda kullanılır',
               existing_nullable=True,
               schema='core')
    op.alter_column('ProductionVersion', 'RouteCode',
               existing_type=sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'),
               comment='Rota kodu (Routing.RouteCode)',
               existing_comment='Rota kodu',
               existing_nullable=False,
               schema='core')
    op.alter_column('Material', 'ShelfLifeDays',
               existing_type=sa.INTEGER(),
               comment="Raf ömrü (gün); Faz 1'de yalnız uyarı",
               existing_comment='Raf ömrü; şimdilik yalnız uyarı için kullanılır',
               existing_nullable=True,
               schema='core')
