"""0029 · Müşteri, proje grubu, proje (K-119): yeni alanlar; IsolationRule → TrackingRule; IsClosed → IsActive (değer ters çevrilir); BorrowPayback

Adı değişen kolonlarda veri korunur. stg ham veridir, değerleri çevrilmez. Geri alışta yeni alanlar ve BorrowPayback kayıtları kaybolur.

Revision ID: 0029
Revises: 0028
Create Date: 2026-11-05
"""
from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql

from dictionary import sync
from models import metadata


revision = '0029'
down_revision = '0028'
branch_labels = None
depends_on = None

SCHEMAS = ('core', 'stg')
FD = 'adm.FieldDefinition'
TRACKED = 'Bu müşterinin talepleri ortak havuzdan değil, müşteriye ayrılmış olarak takip edilir'
CUSTOMER_NEW = (
    ('CustomerGroup', sa.Unicode(length=50), 'Müşteri grubu'),
    ('IsActive', sa.Boolean(), 'Aktif mi'),
    ('Country', sa.Unicode(length=100), 'Ülke'),
    ('Region', sa.Unicode(length=100), 'Bölge'),
    ('City', sa.Unicode(length=100), 'Şehir'),
    ('IsCustomTracked', sa.Boolean(), TRACKED),
)
GROUP_NEW = (
    ('Priority', sa.Integer(), 'Proje grubu önceliği'),
    ('IsActive', sa.Boolean(), 'Aktif mi'),
)
OLD_RULE, NEW_RULE = 'Proje bazında izolasyon (grubu ezer)', 'Proje bazında takip kuralı (grubu ezer)'
OLD_ACTIVE, NEW_ACTIVE = 'Kapandı mı', 'Aktif mi'
RULE_TYPE = sa.Unicode(length=20)


def _invert():
    op.execute("UPDATE core.Project SET {0} = CASE WHEN {0} = 1 THEN 0 WHEN {0} = 0 THEN 1 END".format('IsActive'))


def _new_table():
    op.create_table('BorrowPayback',
    sa.Column('Id', sa.BigInteger(), autoincrement=False, nullable=False, comment='Kayıt kimliği'),
    sa.Column('LocationId', sa.Integer(), nullable=False, comment='Lokasyon'),
    sa.Column('MaterialId', sa.BigInteger(), nullable=False, comment='Malzeme'),
    sa.Column('LendingProjectId', sa.BigInteger(), nullable=False, comment='Ödünç veren proje'),
    sa.Column('BorrowingProjectId', sa.BigInteger(), nullable=False, comment='Ödünç alan proje'),
    sa.Column('BorrowedQuantity', sa.Numeric(precision=18, scale=4), nullable=False, comment='Ödünç miktarı'),
    sa.Column('PaidBackQuantity', sa.Numeric(precision=18, scale=4), nullable=True, comment='Geri ödenen miktar'),
    sa.Column('BorrowDate', sa.DATE(), nullable=False, comment='Ödünç tarihi'),
    sa.Column('PaybackDueDate', sa.DATE(), nullable=True, comment='Geri ödeme tarihi'),
    sa.Column('VersionFrom', sa.Integer(), autoincrement=False, nullable=False, comment='Kaydın geçerli olduğu ilk veri versiyonu'),
    sa.Column('VersionTo', sa.Integer(), nullable=True, comment='Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş'),
    sa.Column('ImportBatchId', sa.BigInteger(), nullable=True, comment='Kaydı getiren yükleme partisi'),
    sa.Column('BusinessKey', sa.Unicode(length=200), nullable=False, comment='İş anahtarı; kod ya da kodların birleşimi'),
    sa.Column('UpdatedAt', mssql.DATETIME2(), nullable=False, comment='Son değişiklik zamanı'),
    sa.ForeignKeyConstraint(['ImportBatchId'], ['adm.ImportBatch.Id'], name=op.f('FK_BorrowPayback_ImportBatchId')),
    sa.ForeignKeyConstraint(['LocationId'], ['core.Location.Id'], name=op.f('FK_BorrowPayback_LocationId')),
    sa.PrimaryKeyConstraint('Id', 'VersionFrom', name=op.f('PK_BorrowPayback')),
    schema='core',
    comment="Projeler arası ödünç ve geri ödeme kaydı: devreye almada açık olan ve ERP'de doğrudan yapılan ödünçlerin motora bildirilmesi; onaylanan öneriler de buraya yazılır.",
    info={'field_class': 'İşlem verisi'}
    )
    op.create_index(op.f('IX_BorrowPayback_BorrowingProjectId'), 'BorrowPayback', ['BorrowingProjectId'], unique=False, schema='core')
    op.create_index(op.f('IX_BorrowPayback_LendingProjectId'), 'BorrowPayback', ['LendingProjectId'], unique=False, schema='core')
    op.create_index(op.f('IX_BorrowPayback_MaterialId'), 'BorrowPayback', ['MaterialId'], unique=False, schema='core')
    op.create_index('UX_BorrowPayback_LocationId_MaterialId_LendingProjectId_BorrowingProjectId_BorrowDate', 'BorrowPayback', ['LocationId', 'MaterialId', 'LendingProjectId', 'BorrowingProjectId', 'BorrowDate'], unique=True, schema='core', mssql_where=sa.text('VersionTo IS NULL'))
    op.create_table('BorrowPayback',
    sa.Column('StagingRowId', sa.BigInteger(), autoincrement=True, nullable=False, comment='Satır kimliği'),
    sa.Column('ImportBatchId', sa.BigInteger(), nullable=False, comment='Yükleme partisi'),
    sa.Column('RowStatus', sa.Unicode(length=15), nullable=False, comment='Yeni | Hatalı | Aktarıldı'),
    sa.Column('ErrorText', sa.Unicode(length=400), nullable=True, comment='Hata açıklaması'),
    sa.Column('LocationCode', sa.Unicode(length=30), nullable=True, comment='Lokasyon kodu'),
    sa.Column('MaterialCode', sa.Unicode(length=50), nullable=True, comment='Malzeme'),
    sa.Column('LendingProjectCode', sa.Unicode(length=50), nullable=True, comment='Ödünç veren proje'),
    sa.Column('BorrowingProjectCode', sa.Unicode(length=50), nullable=True, comment='Ödünç alan proje'),
    sa.Column('BorrowedQuantity', sa.Numeric(precision=18, scale=4), nullable=True, comment='Ödünç miktarı'),
    sa.Column('PaidBackQuantity', sa.Numeric(precision=18, scale=4), nullable=True, comment='Geri ödenen miktar'),
    sa.Column('BorrowDate', sa.DATE(), nullable=True, comment='Ödünç tarihi'),
    sa.Column('PaybackDueDate', sa.DATE(), nullable=True, comment='Geri ödeme tarihi'),
    sa.ForeignKeyConstraint(['ImportBatchId'], ['adm.ImportBatch.Id'], name=op.f('FK_BorrowPayback_ImportBatchId')),
    sa.PrimaryKeyConstraint('StagingRowId', name=op.f('PK_BorrowPayback')),
    schema='stg',
    comment="Projeler arası ödünç ve geri ödeme kaydı: devreye almada açık olan ve ERP'de doğrudan yapılan ödünçlerin motora bildirilmesi; onaylanan öneriler de buraya yazılır."
    )
    op.create_index('UX_BorrowPayback_LocationCode_MaterialCode_LendingProjectCode_BorrowingProjectCode_BorrowDate', 'BorrowPayback', ['LocationCode', 'MaterialCode', 'LendingProjectCode', 'BorrowingProjectCode', 'BorrowDate'], unique=True, schema='stg')


def upgrade():
    _new_table()
    for schema in SCHEMAS:
        for name, type_, comment in CUSTOMER_NEW:
            op.add_column('Customer', sa.Column(name, type_, nullable=True, comment=comment), schema=schema)
        for name, type_, comment in GROUP_NEW:
            op.add_column('ProjectGroup', sa.Column(name, type_, nullable=True, comment=comment), schema=schema)
        op.alter_column('ProjectGroup', 'IsolationRule', new_column_name='TrackingRule', schema=schema)
        op.alter_column('Project', 'IsolationRule', new_column_name='TrackingRule', schema=schema)
        op.alter_column('Project', 'IsClosed', new_column_name='IsActive', schema=schema)
        op.alter_column('Project', 'TrackingRule', existing_type=RULE_TYPE, comment=NEW_RULE, existing_comment=OLD_RULE, existing_nullable=True, schema=schema)
        op.alter_column('Project', 'IsActive', existing_type=sa.Boolean(), comment=NEW_ACTIVE, existing_comment=OLD_ACTIVE, existing_nullable=True, schema=schema)
    # IsClosed = 0 varsayılanı "kapalı değil" demekti; aynı anlam IsActive = 1.
    op.alter_column('Project', 'IsActive', existing_type=sa.Boolean(), server_default=None, existing_comment=NEW_ACTIVE, existing_nullable=True, schema='core')
    _invert()
    op.alter_column('Project', 'IsActive', existing_type=sa.Boolean(), server_default=sa.text('1'), existing_comment=NEW_ACTIVE, existing_nullable=True, schema='core')
    # Sözlük: elle verilen etiket yeni adda kalır; sync silmez, DefaultValue'ya dokunmaz.
    for table in ('ProjectGroup', 'Project'):
        op.execute(f"UPDATE {FD} SET FieldName = N'TrackingRule' WHERE TableName = N'{table}' AND FieldName = N'IsolationRule'")
    op.execute(f"UPDATE {FD} SET FieldName = N'IsActive', DefaultValue = N'1' WHERE TableName = N'Project' AND FieldName = N'IsClosed'")
    if not context.is_offline_mode():  # bağlantısız SQL betiğinde satırlar yazılmaz; ilk bağlantılı geçişte kurulur
        sync(op.get_bind(), metadata)


def downgrade():
    names = ', '.join(f"N'{n}'" for n, _, _ in CUSTOMER_NEW)
    op.execute(f"DELETE FROM {FD} WHERE TableName = N'BorrowPayback'")
    op.execute(f"DELETE FROM {FD} WHERE TableName = N'Customer' AND FieldName IN ({names})")
    op.execute(f"DELETE FROM {FD} WHERE TableName = N'ProjectGroup' AND FieldName IN (N'Priority', N'IsActive')")
    for table in ('ProjectGroup', 'Project'):
        op.execute(f"UPDATE {FD} SET FieldName = N'IsolationRule', StandardLabel = N'İzolasyon kuralı' WHERE TableName = N'{table}' AND FieldName = N'TrackingRule'")
    op.execute(f"UPDATE {FD} SET Description = N'{OLD_RULE}' WHERE TableName = N'Project' AND FieldName = N'IsolationRule'")
    op.execute(f"UPDATE {FD} SET FieldName = N'IsClosed', DefaultValue = N'0', StandardLabel = N'{OLD_ACTIVE}', Description = N'{OLD_ACTIVE}' WHERE TableName = N'Project' AND FieldName = N'IsActive'")
    op.alter_column('Project', 'IsActive', existing_type=sa.Boolean(), server_default=None, existing_comment=NEW_ACTIVE, existing_nullable=True, schema='core')
    _invert()
    op.alter_column('Project', 'IsActive', existing_type=sa.Boolean(), server_default=sa.text('0'), existing_comment=NEW_ACTIVE, existing_nullable=True, schema='core')
    for schema in SCHEMAS:
        op.alter_column('Project', 'IsActive', existing_type=sa.Boolean(), comment=OLD_ACTIVE, existing_comment=NEW_ACTIVE, existing_nullable=True, schema=schema)
        op.alter_column('Project', 'TrackingRule', existing_type=RULE_TYPE, comment=OLD_RULE, existing_comment=NEW_RULE, existing_nullable=True, schema=schema)
        op.alter_column('Project', 'IsActive', new_column_name='IsClosed', schema=schema)
        op.alter_column('Project', 'TrackingRule', new_column_name='IsolationRule', schema=schema)
        op.alter_column('ProjectGroup', 'TrackingRule', new_column_name='IsolationRule', schema=schema)
        for name, _, _ in reversed(GROUP_NEW):
            op.drop_column('ProjectGroup', name, schema=schema)
        for name, _, _ in reversed(CUSTOMER_NEW):
            op.drop_column('Customer', name, schema=schema)
    op.drop_index('UX_BorrowPayback_LocationCode_MaterialCode_LendingProjectCode_BorrowingProjectCode_BorrowDate', table_name='BorrowPayback', schema='stg')
    op.drop_table('BorrowPayback', schema='stg')
    op.drop_index('UX_BorrowPayback_LocationId_MaterialId_LendingProjectId_BorrowingProjectId_BorrowDate', table_name='BorrowPayback', schema='core', mssql_where=sa.text('VersionTo IS NULL'))
    op.drop_index(op.f('IX_BorrowPayback_MaterialId'), table_name='BorrowPayback', schema='core')
    op.drop_index(op.f('IX_BorrowPayback_LendingProjectId'), table_name='BorrowPayback', schema='core')
    op.drop_index(op.f('IX_BorrowPayback_BorrowingProjectId'), table_name='BorrowPayback', schema='core')
    op.drop_table('BorrowPayback', schema='core')
