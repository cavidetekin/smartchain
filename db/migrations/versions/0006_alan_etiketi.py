"""0006 · Alan etiketi (K-88)

adm.FieldDefinition'a Label eklenir (ekranda görünen etiket; ek alan yalnız Label'ı varsa listede görünür).
Açıklamalar (K-64) güncellenir: Material'da etiket ön ekleri (MaterialLevel, DefaultProcurement, Ownership,
LotSizePolicy, IsProjectTracked) ve bütün versiyonlu tablolarda BusinessKey. Veri değişmez.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('FieldDefinition', sa.Column('Label', sa.Unicode(length=100), nullable=True, comment='Ekranda görünen etiket; standart alanın etiketini ezer, ek alanda boşsa alan gösterilmez (K-88)'), schema='adm')
    op.alter_column('BOM', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_nullable=False,
               schema='core')
    op.alter_column('Calendar', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_nullable=False,
               schema='core')
    op.alter_column('CalendarDay', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_nullable=False,
               schema='core')
    op.alter_column('CompetenceGroup', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_nullable=False,
               schema='core')
    op.alter_column('Customer', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_nullable=False,
               schema='core')
    op.alter_column('Forecast', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_nullable=False,
               schema='core')
    op.alter_column('Material', 'MaterialLevel',
               existing_type=sa.NVARCHAR(length=15, collation='Latin1_General_100_CI_AS_SC'),
               comment='Malzeme seviyesi: Hammadde | Yarı mamul | Nihai ürün',
               existing_comment='Hammadde | Yarı mamul | Nihai ürün',
               existing_nullable=True,
               schema='core')
    op.alter_column('Material', 'DefaultProcurement',
               existing_type=sa.NVARCHAR(length=10, collation='Latin1_General_100_CI_AS_SC'),
               comment='Tedarik türü: Üretim | Satın alma | Fason',
               existing_comment='Üretim | Satın alma | Fason',
               existing_nullable=True,
               schema='core')
    op.alter_column('Material', 'Ownership',
               existing_type=sa.NVARCHAR(length=10, collation='Latin1_General_100_CI_AS_SC'),
               comment='Sahiplik: Kendi | Müşteri (müşteri temin malzemesi)',
               existing_comment='Kendi | Müşteri (müşteri temin malzemesi)',
               existing_nullable=True,
               existing_server_default=sa.text("(N'Kendi')"),
               schema='core')
    op.alter_column('Material', 'IsProjectTracked',
               existing_type=mssql.BIT(),
               comment='Proje bazlı takip; değilse her zaman ortak',
               existing_comment='Proje bazlı takip edilir mi (değilse her zaman ortak)',
               existing_nullable=True,
               existing_server_default=sa.text('((0))'),
               schema='core')
    op.alter_column('Material', 'LotSizePolicy',
               existing_type=sa.NVARCHAR(length=15, collation='Latin1_General_100_CI_AS_SC'),
               comment='Lot politikası (üretimde): Lot-for-lot | Sabit | Dönemsel',
               existing_comment='Üretimde: Lot-for-lot | Sabit | Dönemsel',
               existing_nullable=True,
               existing_server_default=sa.text("(N'Lot-for-lot')"),
               schema='core')
    op.alter_column('Material', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_nullable=False,
               schema='core')
    op.alter_column('MaterialSupplier', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_nullable=False,
               schema='core')
    op.alter_column('ProductionConfirmation', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_nullable=False,
               schema='core')
    op.alter_column('ProductionVersion', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_nullable=False,
               schema='core')
    op.alter_column('Project', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_nullable=False,
               schema='core')
    op.alter_column('ProjectGroup', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_nullable=False,
               schema='core')
    op.alter_column('PurchaseOrderLine', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_nullable=False,
               schema='core')
    op.alter_column('Resource', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_nullable=False,
               schema='core')
    op.alter_column('ResourceCapacityProfile', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_nullable=False,
               schema='core')
    op.alter_column('ResourceDowntime', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_nullable=False,
               schema='core')
    op.alter_column('ResourceGroup', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_nullable=False,
               schema='core')
    op.alter_column('Routing', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_nullable=False,
               schema='core')
    op.alter_column('SalesOrderLine', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_nullable=False,
               schema='core')
    op.alter_column('Shift', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_nullable=False,
               schema='core')
    op.alter_column('ShiftPlan', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_nullable=False,
               schema='core')
    op.alter_column('Stock', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_nullable=False,
               schema='core')
    op.alter_column('Supplier', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_nullable=False,
               schema='core')
    op.alter_column('TransferOrder', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_nullable=False,
               schema='core')
    op.alter_column('UomConversion', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_nullable=False,
               schema='core')
    op.alter_column('WorkOrder', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_nullable=False,
               schema='core')
    op.alter_column('WorkOrderComponent', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_nullable=False,
               schema='core')
    op.alter_column('WorkOrderOperation', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_nullable=False,
               schema='core')
    op.alter_column('Worker', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_nullable=False,
               schema='core')
    op.alter_column('WorkerAbsence', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_nullable=False,
               schema='core')
    op.alter_column('WorkerCompetence', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_nullable=False,
               schema='core')


def downgrade():
    op.alter_column('WorkerCompetence', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_nullable=False,
               schema='core')
    op.alter_column('WorkerAbsence', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_nullable=False,
               schema='core')
    op.alter_column('Worker', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_nullable=False,
               schema='core')
    op.alter_column('WorkOrderOperation', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_nullable=False,
               schema='core')
    op.alter_column('WorkOrderComponent', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_nullable=False,
               schema='core')
    op.alter_column('WorkOrder', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_nullable=False,
               schema='core')
    op.alter_column('UomConversion', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_nullable=False,
               schema='core')
    op.alter_column('TransferOrder', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_nullable=False,
               schema='core')
    op.alter_column('Supplier', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_nullable=False,
               schema='core')
    op.alter_column('Stock', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_nullable=False,
               schema='core')
    op.alter_column('ShiftPlan', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_nullable=False,
               schema='core')
    op.alter_column('Shift', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_nullable=False,
               schema='core')
    op.alter_column('SalesOrderLine', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_nullable=False,
               schema='core')
    op.alter_column('Routing', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_nullable=False,
               schema='core')
    op.alter_column('ResourceGroup', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_nullable=False,
               schema='core')
    op.alter_column('ResourceDowntime', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_nullable=False,
               schema='core')
    op.alter_column('ResourceCapacityProfile', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_nullable=False,
               schema='core')
    op.alter_column('Resource', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_nullable=False,
               schema='core')
    op.alter_column('PurchaseOrderLine', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_nullable=False,
               schema='core')
    op.alter_column('ProjectGroup', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_nullable=False,
               schema='core')
    op.alter_column('Project', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_nullable=False,
               schema='core')
    op.alter_column('ProductionVersion', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_nullable=False,
               schema='core')
    op.alter_column('ProductionConfirmation', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_nullable=False,
               schema='core')
    op.alter_column('MaterialSupplier', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_nullable=False,
               schema='core')
    op.alter_column('Material', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_nullable=False,
               schema='core')
    op.alter_column('Material', 'LotSizePolicy',
               existing_type=sa.NVARCHAR(length=15, collation='Latin1_General_100_CI_AS_SC'),
               comment='Üretimde: Lot-for-lot | Sabit | Dönemsel',
               existing_comment='Lot politikası (üretimde): Lot-for-lot | Sabit | Dönemsel',
               existing_nullable=True,
               existing_server_default=sa.text("(N'Lot-for-lot')"),
               schema='core')
    op.alter_column('Material', 'IsProjectTracked',
               existing_type=mssql.BIT(),
               comment='Proje bazlı takip edilir mi (değilse her zaman ortak)',
               existing_comment='Proje bazlı takip; değilse her zaman ortak',
               existing_nullable=True,
               existing_server_default=sa.text('((0))'),
               schema='core')
    op.alter_column('Material', 'Ownership',
               existing_type=sa.NVARCHAR(length=10, collation='Latin1_General_100_CI_AS_SC'),
               comment='Kendi | Müşteri (müşteri temin malzemesi)',
               existing_comment='Sahiplik: Kendi | Müşteri (müşteri temin malzemesi)',
               existing_nullable=True,
               existing_server_default=sa.text("(N'Kendi')"),
               schema='core')
    op.alter_column('Material', 'DefaultProcurement',
               existing_type=sa.NVARCHAR(length=10, collation='Latin1_General_100_CI_AS_SC'),
               comment='Üretim | Satın alma | Fason',
               existing_comment='Tedarik türü: Üretim | Satın alma | Fason',
               existing_nullable=True,
               schema='core')
    op.alter_column('Material', 'MaterialLevel',
               existing_type=sa.NVARCHAR(length=15, collation='Latin1_General_100_CI_AS_SC'),
               comment='Hammadde | Yarı mamul | Nihai ürün',
               existing_comment='Malzeme seviyesi: Hammadde | Yarı mamul | Nihai ürün',
               existing_nullable=True,
               schema='core')
    op.alter_column('Forecast', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_nullable=False,
               schema='core')
    op.alter_column('Customer', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_nullable=False,
               schema='core')
    op.alter_column('CompetenceGroup', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_nullable=False,
               schema='core')
    op.alter_column('CalendarDay', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_nullable=False,
               schema='core')
    op.alter_column('Calendar', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_nullable=False,
               schema='core')
    op.alter_column('BOM', 'BusinessKey',
               existing_type=sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'),
               comment='İş anahtarı (kod ya da kodların birleşimi)',
               existing_comment='İş anahtarı; kod ya da kodların birleşimi',
               existing_nullable=False,
               schema='core')
    op.drop_column('FieldDefinition', 'Label', schema='adm')
