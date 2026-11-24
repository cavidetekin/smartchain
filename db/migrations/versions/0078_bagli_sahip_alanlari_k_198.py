"""0078 · Arzın sahip alanları: tek ad takımı ve ERP'den gelen ham kodlar (K-198, demo kararları)

- Stock, WorkOrder, PurchaseOrderLine (`core`): `ProjectCode` ve `CustomerCode` (ERP'den geldiği gibi; sahip sistemde bulunmasa da kapansa da yazıldığı
  gibi kalır, özel alokasyon anahtarı bunlardan kurulur). Var olan satırlarda iç bağdan (`ProjectId`, `CustomerId`) doldurulur.
- Stok'un tekil anahtarı iç bağlar yerine ham alanlarda (`ProjectCode`, `CustomerCode`, sipariş üçlüsü); indeksin adı `UX_Stock_Key` (uzun ad 128
  karakter sınırını aşıyor).
- Etiket ve açıklamalar: üç tabloda "Bağlı proje · Bağlı müşteri · Bağlı sipariş no · Bağlı sipariş satırı · Bağlı sipariş alt satırı"; iç bağlar
  (`ProjectId`, `CustomerId`, `SalesOrderLineId`) sistem alanıdır, veri sözlüğünden çıkar.
- Bu alanlara girilmiş manuel değerler silinir (ilişki alanıdır).

Veri kaybı yok. Açıklamalar geçişte sabittir (K-197). Geri alış iki kolonu düşürür, eski indeksi geri kurar.

Revision ID: 0078
Revises: 0077
Create Date: 2026-11-25
"""
from alembic import context, op
import sqlalchemy as sa

from dictionary import sync
from models import metadata

revision = '0078'
down_revision = '0077'
branch_labels = None
depends_on = None

ARZ = ('Stock', 'WorkOrder', 'PurchaseOrderLine')
LINKS = ('ProjectId', 'CustomerId', 'SalesOrderLineId')
RAW = ('ProjectCode', 'CustomerCode', 'SalesOrderNo', 'SalesOrderLineNo', 'SalesOrderLineItemNo')


def _in(names):
    return ', '.join(f"N'{n}'" for n in names)


def _table_comment(schema, text):
    """SQL Server'da var olan tablo açıklaması (MS_Description) create_table_comment ile eklenemez; güncellenir."""
    op.execute(sa.text("EXEC sp_updateextendedproperty @name = N'MS_Description', @value = :v, @level0type = N'SCHEMA', @level0name = :s, "
                       "@level1type = N'TABLE', @level1name = N'Stock'").bindparams(v=text, s=schema))


def _fill_codes(table):
    """Var olan satırların ham proje ve müşteri kodu iç bağdan (kaydın en son versiyonu)."""
    for column, target, key in (('ProjectCode', 'Project', 'ProjectId'), ('CustomerCode', 'Customer', 'CustomerId')):
        op.execute(f"UPDATE t SET {column} = x.Code FROM core.[{table}] t CROSS APPLY (SELECT TOP 1 Code FROM core.[{target}] p WHERE p.Id = t.{key} "
                   f"ORDER BY p.VersionFrom DESC) x WHERE t.{key} IS NOT NULL")


def upgrade():
    op.drop_index('UX_Stock_LocationId_MaterialId_Warehouse_LotNo_Status_ProjectId_CustomerId_SalesOrderNo_SalesOrderLineNo_SalesOrderLineItemNo', table_name='Stock', schema='core', mssql_where=sa.text('VersionTo IS NULL'))
    op.add_column('PurchaseOrderLine', sa.Column('ProjectCode', sa.Unicode(length=50), nullable=True, comment="Satın alma satırının ayrıldığı proje, ERP'den geldiği gibi; proje bulunamasa da kapansa da yazıldığı gibi kalır"), schema='core')
    op.add_column('PurchaseOrderLine', sa.Column('CustomerCode', sa.Unicode(length=50), nullable=True, comment="Satın alma satırının ayrıldığı müşteri, ERP'den geldiği gibi; müşteri bulunamasa da kapansa da yazıldığı gibi kalır"), schema='core')
    op.alter_column('PurchaseOrderLine', 'ProjectId',
               existing_type=sa.BIGINT(),
               comment='Bağlı proje (iç bağ): proje kodu sistemde bulunuyorsa dolar; kolon olarak gösterilmez',
               existing_comment='Proje',
               existing_nullable=True,
               schema='core')
    op.alter_column('PurchaseOrderLine', 'CustomerId',
               existing_type=sa.BIGINT(),
               comment='Bağlı müşteri (iç bağ): müşteri kodu sistemde bulunuyorsa dolar; kolon olarak gösterilmez',
               existing_comment='Müşteri',
               existing_nullable=True,
               schema='core')
    op.alter_column('PurchaseOrderLine', 'SalesOrderLineId',
               existing_type=sa.BIGINT(),
               comment='Bağlı sipariş (iç bağ): sipariş no ve satırı doluysa ve satır bulunuyorsa dolar, kalemsiz arzda boştur; kolon olarak gösterilmez',
               existing_comment='Bağlı sipariş satırı; iç bağ: sipariş no ve satır no doluysa ve satır bulunuyorsa dolar, kalemsiz arzda boştur',
               existing_nullable=True,
               schema='core')
    op.alter_column('PurchaseOrderLine', 'SalesOrderNo',
               existing_type=sa.NVARCHAR(length=30, collation='Latin1_General_100_CI_AS_SC'),
               comment="Satın alma satırının ayrıldığı sipariş, ERP'den geldiği gibi; satırı boşsa arz siparişin bütün kalemlerine ayrılmıştır (kalemsiz arz)",
               existing_comment="Bağlı satış sipariş no, ERP'den geldiği gibi; satır no boşsa arz siparişin bütün kalemlerine ayrılmıştır (kalemsiz arz)",
               existing_nullable=True,
               schema='core')
    op.alter_column('PurchaseOrderLine', 'SalesOrderLineNo',
               existing_type=sa.INTEGER(),
               comment="Bağlı siparişin satır no'su, ERP'den geldiği gibi",
               existing_comment="Bağlı satış sipariş satır no, ERP'den geldiği gibi",
               existing_nullable=True,
               schema='core')
    op.alter_column('PurchaseOrderLine', 'SalesOrderLineItemNo',
               existing_type=sa.INTEGER(),
               comment="Bağlı siparişin alt satır no'su, ERP'den geldiği gibi",
               existing_comment="Bağlı satış sipariş alt satır no, ERP'den geldiği gibi",
               existing_nullable=True,
               schema='core')
    op.alter_column('PurchaseOrderLine', 'AllocationKey',
               existing_type=sa.NVARCHAR(length=60, collation='Latin1_General_100_CI_AS_SC'),
               comment="Arzın ayrıldığı sahibin anahtarı; satırda ERP'nin yazdığı en detaylı sahipten: sipariş (sipariş no, satır ve alt satır dik çizgiyle; kalemsiz arzda yalnız sipariş no), proje kodu ya da müşteri kodu. Sahip sistemde bulunmasa da kapansa da anahtar kalır; lokasyon anahtara girmez; malzeme özel alokasyonlu değilse boştur (K-198)",
               existing_comment='Arzın ayrıldığı sahibin anahtarı; satırda dolu olan en detaylı sahipten: sipariş (sipariş no, satır no ve alt satır no dik çizgiyle; kalemsiz arzda yalnız sipariş no), proje kodu ya da müşteri kodu. Lokasyon anahtara girmez; malzeme özel alokasyonlu değilse boştur (K-198)',
               existing_nullable=True,
               schema='core')
    op.add_column('Stock', sa.Column('ProjectCode', sa.Unicode(length=50), nullable=True, comment="Stoğun ayrıldığı proje, ERP'den geldiği gibi; proje bulunamasa da kapansa da yazıldığı gibi kalır"), schema='core')
    op.add_column('Stock', sa.Column('CustomerCode', sa.Unicode(length=50), nullable=True, comment="Stoğun ayrıldığı müşteri, ERP'den geldiği gibi; müşteri bulunamasa da kapansa da yazıldığı gibi kalır"), schema='core')
    op.alter_column('Stock', 'ProjectId',
               existing_type=sa.BIGINT(),
               comment='Bağlı proje (iç bağ): proje kodu sistemde bulunuyorsa dolar; kolon olarak gösterilmez',
               existing_comment='Sahip proje; proje, müşteri ve sipariş boşsa stok ortaktır',
               existing_nullable=True,
               schema='core')
    op.alter_column('Stock', 'CustomerId',
               existing_type=sa.BIGINT(),
               comment='Bağlı müşteri (iç bağ): müşteri kodu sistemde bulunuyorsa dolar; kolon olarak gösterilmez',
               existing_comment='Sahip müşteri; stoğun ayrıldığı müşteri',
               existing_nullable=True,
               schema='core')
    op.alter_column('Stock', 'SalesOrderLineId',
               existing_type=sa.BIGINT(),
               comment='Bağlı sipariş (iç bağ): sipariş no ve satırı doluysa ve satır bulunuyorsa dolar, kalemsiz arzda boştur; kolon olarak gösterilmez',
               existing_comment='Sahip sipariş satırı; iç bağ: sipariş no ve satır no doluysa ve satır bulunuyorsa dolar, kalemsiz arzda boştur',
               existing_nullable=True,
               schema='core')
    op.alter_column('Stock', 'SalesOrderNo',
               existing_type=sa.NVARCHAR(length=30, collation='Latin1_General_100_CI_AS_SC'),
               comment="Stoğun ayrıldığı sipariş, ERP'den geldiği gibi; satırı boşsa arz siparişin bütün kalemlerine ayrılmıştır (kalemsiz arz)",
               existing_comment="Sahip sipariş no, ERP'den geldiği gibi; satır no boşsa arz siparişin bütün kalemlerine ayrılmıştır (kalemsiz arz)",
               existing_nullable=True,
               schema='core')
    op.alter_column('Stock', 'SalesOrderLineNo',
               existing_type=sa.INTEGER(),
               comment="Bağlı siparişin satır no'su, ERP'den geldiği gibi",
               existing_comment="Sahip sipariş satır no, ERP'den geldiği gibi",
               existing_nullable=True,
               schema='core')
    op.alter_column('Stock', 'SalesOrderLineItemNo',
               existing_type=sa.INTEGER(),
               comment="Bağlı siparişin alt satır no'su, ERP'den geldiği gibi",
               existing_comment="Sahip sipariş alt satır no, ERP'den geldiği gibi",
               existing_nullable=True,
               schema='core')
    op.alter_column('Stock', 'AllocationKey',
               existing_type=sa.NVARCHAR(length=60, collation='Latin1_General_100_CI_AS_SC'),
               comment="Arzın ayrıldığı sahibin anahtarı; satırda ERP'nin yazdığı en detaylı sahipten: sipariş (sipariş no, satır ve alt satır dik çizgiyle; kalemsiz arzda yalnız sipariş no), proje kodu ya da müşteri kodu. Sahip sistemde bulunmasa da kapansa da anahtar kalır; lokasyon anahtara girmez; malzeme özel alokasyonlu değilse boştur (K-198)",
               existing_comment='Arzın ayrıldığı sahibin anahtarı; satırda dolu olan en detaylı sahipten: sipariş (sipariş no, satır no ve alt satır no dik çizgiyle; kalemsiz arzda yalnız sipariş no), proje kodu ya da müşteri kodu. Lokasyon anahtara girmez; malzeme özel alokasyonlu değilse boştur (K-198)',
               existing_nullable=True,
               schema='core')
    _fill_codes('Stock')
    op.create_index('UX_Stock_Key', 'Stock', ['LocationId', 'MaterialId', 'Warehouse', 'LotNo', 'Status', 'ProjectCode', 'CustomerCode', 'SalesOrderNo', 'SalesOrderLineNo', 'SalesOrderLineItemNo'], unique=True, schema='core', mssql_where=sa.text('VersionTo IS NULL'))
    _table_comment('core', 'Stok; lot ve durum bazında. Bağlı proje, müşteri ya da sipariş doluysa stok ona ayrılmıştır; boşsa geneldir.')
    op.add_column('WorkOrder', sa.Column('ProjectCode', sa.Unicode(length=50), nullable=True, comment="İş emrinin ayrıldığı proje, ERP'den geldiği gibi; proje bulunamasa da kapansa da yazıldığı gibi kalır"), schema='core')
    op.add_column('WorkOrder', sa.Column('CustomerCode', sa.Unicode(length=50), nullable=True, comment="İş emrinin ayrıldığı müşteri, ERP'den geldiği gibi; müşteri bulunamasa da kapansa da yazıldığı gibi kalır"), schema='core')
    op.alter_column('WorkOrder', 'ProjectId',
               existing_type=sa.BIGINT(),
               comment='Bağlı proje (iç bağ): proje kodu sistemde bulunuyorsa dolar; kolon olarak gösterilmez',
               existing_comment='Proje (ayraç)',
               existing_nullable=True,
               schema='core')
    op.alter_column('WorkOrder', 'CustomerId',
               existing_type=sa.BIGINT(),
               comment='Bağlı müşteri (iç bağ): müşteri kodu sistemde bulunuyorsa dolar; kolon olarak gösterilmez',
               existing_comment='Müşteri',
               existing_nullable=True,
               schema='core')
    op.alter_column('WorkOrder', 'SalesOrderLineId',
               existing_type=sa.BIGINT(),
               comment='Bağlı sipariş (iç bağ): sipariş no ve satırı doluysa ve satır bulunuyorsa dolar, kalemsiz arzda boştur; kolon olarak gösterilmez',
               existing_comment='Bağlı sipariş satırı (ayraç); iç bağ: sipariş no ve satır no doluysa ve satır bulunuyorsa dolar, kalemsiz arzda boştur',
               existing_nullable=True,
               schema='core')
    op.alter_column('WorkOrder', 'SalesOrderNo',
               existing_type=sa.NVARCHAR(length=30, collation='Latin1_General_100_CI_AS_SC'),
               comment="İş emrinin ayrıldığı sipariş, ERP'den geldiği gibi; satırı boşsa arz siparişin bütün kalemlerine ayrılmıştır (kalemsiz arz)",
               existing_comment="Bağlı sipariş no, ERP'den geldiği gibi; satır no boşsa arz siparişin bütün kalemlerine ayrılmıştır (kalemsiz arz)",
               existing_nullable=True,
               schema='core')
    op.alter_column('WorkOrder', 'SalesOrderLineNo',
               existing_type=sa.INTEGER(),
               comment="Bağlı siparişin satır no'su, ERP'den geldiği gibi",
               existing_comment="Bağlı sipariş satır no, ERP'den geldiği gibi",
               existing_nullable=True,
               schema='core')
    op.alter_column('WorkOrder', 'SalesOrderLineItemNo',
               existing_type=sa.INTEGER(),
               comment="Bağlı siparişin alt satır no'su, ERP'den geldiği gibi",
               existing_comment="Bağlı sipariş alt satır no, ERP'den geldiği gibi",
               existing_nullable=True,
               schema='core')
    op.alter_column('WorkOrder', 'AllocationKey',
               existing_type=sa.NVARCHAR(length=60, collation='Latin1_General_100_CI_AS_SC'),
               comment="Arzın ayrıldığı sahibin anahtarı; satırda ERP'nin yazdığı en detaylı sahipten: sipariş (sipariş no, satır ve alt satır dik çizgiyle; kalemsiz arzda yalnız sipariş no), proje kodu ya da müşteri kodu. Sahip sistemde bulunmasa da kapansa da anahtar kalır; lokasyon anahtara girmez; malzeme özel alokasyonlu değilse boştur (K-198)",
               existing_comment='Arzın ayrıldığı sahibin anahtarı; satırda dolu olan en detaylı sahipten: sipariş (sipariş no, satır no ve alt satır no dik çizgiyle; kalemsiz arzda yalnız sipariş no), proje kodu ya da müşteri kodu. Lokasyon anahtara girmez; malzeme özel alokasyonlu değilse boştur (K-198)',
               existing_nullable=True,
               schema='core')
    op.alter_column('PurchaseOrderLine', 'ProjectCode',
               existing_type=sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'),
               comment='Bağlı proje; satın alma satırının ayrıldığı proje',
               existing_comment='Proje',
               existing_nullable=True,
               schema='prc')
    op.alter_column('PurchaseOrderLine', 'CustomerCode',
               existing_type=sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'),
               comment='Bağlı müşteri; satın alma satırının ayrıldığı müşteri',
               existing_comment='Müşteri',
               existing_nullable=True,
               schema='prc')
    op.alter_column('PurchaseOrderLine', 'SalesOrderNo',
               existing_type=sa.NVARCHAR(length=30, collation='Latin1_General_100_CI_AS_SC'),
               comment='Bağlı sipariş no; satın alma satırının ayrıldığı sipariş, satırı boşsa siparişin bütün kalemleri (kalemsiz arz)',
               existing_comment='Bağlı sipariş no',
               existing_nullable=True,
               schema='prc')
    op.alter_column('Stock', 'ProjectCode',
               existing_type=sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'),
               comment='Bağlı proje; stoğun ayrıldığı proje',
               existing_comment='Sahip proje; proje, müşteri ve sipariş boşsa stok ortaktır',
               existing_nullable=True,
               schema='prc')
    op.alter_column('Stock', 'CustomerCode',
               existing_type=sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'),
               comment='Bağlı müşteri; stoğun ayrıldığı müşteri',
               existing_comment='Sahip müşteri; stoğun ayrıldığı müşteri',
               existing_nullable=True,
               schema='prc')
    op.alter_column('Stock', 'SalesOrderNo',
               existing_type=sa.NVARCHAR(length=30, collation='Latin1_General_100_CI_AS_SC'),
               comment='Bağlı sipariş no; stoğun ayrıldığı sipariş, satırı boşsa siparişin bütün kalemleri (kalemsiz arz)',
               existing_comment='Sahip sipariş no; stoğun ayrıldığı sipariş, satır no boşsa siparişin bütün kalemleri (kalemsiz arz)',
               existing_nullable=True,
               schema='prc')
    op.alter_column('Stock', 'SalesOrderLineNo',
               existing_type=sa.INTEGER(),
               comment='Bağlı sipariş satırı',
               existing_comment='Sahip sipariş satırı; stoğun ayrıldığı sipariş satırı',
               existing_nullable=True,
               schema='prc')
    _table_comment('prc', 'Stok; lot ve durum bazında. Bağlı proje, müşteri ya da sipariş doluysa stok ona ayrılmıştır; boşsa geneldir.')
    op.alter_column('WorkOrder', 'ProjectCode',
               existing_type=sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'),
               comment='Bağlı proje; i̇ş emrinin ayrıldığı proje',
               existing_comment='Proje (ayraç)',
               existing_nullable=True,
               schema='prc')
    op.alter_column('WorkOrder', 'CustomerCode',
               existing_type=sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'),
               comment='Bağlı müşteri; i̇ş emrinin ayrıldığı müşteri',
               existing_comment='Müşteri',
               existing_nullable=True,
               schema='prc')
    op.alter_column('WorkOrder', 'SalesOrderNo',
               existing_type=sa.NVARCHAR(length=30, collation='Latin1_General_100_CI_AS_SC'),
               comment='Bağlı sipariş no; i̇ş emrinin ayrıldığı sipariş, satırı boşsa siparişin bütün kalemleri (kalemsiz arz)',
               existing_comment='Bağlı sipariş no (ayraç)',
               existing_nullable=True,
               schema='prc')
    op.alter_column('WorkOrder', 'SalesOrderLineNo',
               existing_type=sa.INTEGER(),
               comment='Bağlı sipariş satırı',
               existing_comment='Bağlı sipariş satır no',
               existing_nullable=True,
               schema='prc')
    op.alter_column('PurchaseOrderLine', 'ProjectCode',
               existing_type=sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'),
               comment='Bağlı proje; satın alma satırının ayrıldığı proje',
               existing_comment='Proje',
               existing_nullable=True,
               schema='stg')
    op.alter_column('PurchaseOrderLine', 'CustomerCode',
               existing_type=sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'),
               comment='Bağlı müşteri; satın alma satırının ayrıldığı müşteri',
               existing_comment='Müşteri',
               existing_nullable=True,
               schema='stg')
    op.alter_column('PurchaseOrderLine', 'SalesOrderNo',
               existing_type=sa.NVARCHAR(length=30, collation='Latin1_General_100_CI_AS_SC'),
               comment='Bağlı sipariş no; satın alma satırının ayrıldığı sipariş, satırı boşsa siparişin bütün kalemleri (kalemsiz arz)',
               existing_comment='Bağlı sipariş no',
               existing_nullable=True,
               schema='stg')
    op.alter_column('Stock', 'ProjectCode',
               existing_type=sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'),
               comment='Bağlı proje; stoğun ayrıldığı proje',
               existing_comment='Sahip proje; proje, müşteri ve sipariş boşsa stok ortaktır',
               existing_nullable=True,
               schema='stg')
    op.alter_column('Stock', 'CustomerCode',
               existing_type=sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'),
               comment='Bağlı müşteri; stoğun ayrıldığı müşteri',
               existing_comment='Sahip müşteri; stoğun ayrıldığı müşteri',
               existing_nullable=True,
               schema='stg')
    op.alter_column('Stock', 'SalesOrderNo',
               existing_type=sa.NVARCHAR(length=30, collation='Latin1_General_100_CI_AS_SC'),
               comment='Bağlı sipariş no; stoğun ayrıldığı sipariş, satırı boşsa siparişin bütün kalemleri (kalemsiz arz)',
               existing_comment='Sahip sipariş no; stoğun ayrıldığı sipariş, satır no boşsa siparişin bütün kalemleri (kalemsiz arz)',
               existing_nullable=True,
               schema='stg')
    op.alter_column('Stock', 'SalesOrderLineNo',
               existing_type=sa.INTEGER(),
               comment='Bağlı sipariş satırı',
               existing_comment='Sahip sipariş satırı; stoğun ayrıldığı sipariş satırı',
               existing_nullable=True,
               schema='stg')
    _table_comment('stg', 'Stok; lot ve durum bazında. Bağlı proje, müşteri ya da sipariş doluysa stok ona ayrılmıştır; boşsa geneldir.')
    op.alter_column('WorkOrder', 'ProjectCode',
               existing_type=sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'),
               comment='Bağlı proje; i̇ş emrinin ayrıldığı proje',
               existing_comment='Proje (ayraç)',
               existing_nullable=True,
               schema='stg')
    op.alter_column('WorkOrder', 'CustomerCode',
               existing_type=sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'),
               comment='Bağlı müşteri; i̇ş emrinin ayrıldığı müşteri',
               existing_comment='Müşteri',
               existing_nullable=True,
               schema='stg')
    op.alter_column('WorkOrder', 'SalesOrderNo',
               existing_type=sa.NVARCHAR(length=30, collation='Latin1_General_100_CI_AS_SC'),
               comment='Bağlı sipariş no; i̇ş emrinin ayrıldığı sipariş, satırı boşsa siparişin bütün kalemleri (kalemsiz arz)',
               existing_comment='Bağlı sipariş no (ayraç)',
               existing_nullable=True,
               schema='stg')
    op.alter_column('WorkOrder', 'SalesOrderLineNo',
               existing_type=sa.INTEGER(),
               comment='Bağlı sipariş satırı',
               existing_comment='Bağlı sipariş satır no',
               existing_nullable=True,
               schema='stg')
    for table in ('WorkOrder', 'PurchaseOrderLine'):
        _fill_codes(table)
    for table in ARZ:   # iç bağlar sistem alanıdır: sözlükten çıkar (sync silmez)
        for name in ('FieldDefinition', 'ManualValue', 'FieldValueSource'):
            op.execute(f"DELETE FROM adm.[{name}] WHERE TableName = N'{table}' AND FieldName IN ({_in(LINKS)})")
    for table in ARZ:   # ham sahip alanları ilişki sayılır: manuel değer girilemez
        op.execute(f"DELETE FROM adm.ManualValue WHERE TableName = N'{table}' AND FieldName IN ({_in(RAW)})")
    if not context.is_offline_mode():  # bağlantısız SQL betiğinde satırlar yazılmaz; ilk bağlantılı geçişte kurulur
        sync(op.get_bind(), metadata)


def downgrade():
    op.alter_column('WorkOrder', 'SalesOrderLineNo',
               existing_type=sa.INTEGER(),
               comment='Bağlı sipariş satır no',
               existing_comment='Bağlı sipariş satırı',
               existing_nullable=True,
               schema='stg')
    op.alter_column('WorkOrder', 'SalesOrderNo',
               existing_type=sa.NVARCHAR(length=30, collation='Latin1_General_100_CI_AS_SC'),
               comment='Bağlı sipariş no (ayraç)',
               existing_comment='Bağlı sipariş no; i̇ş emrinin ayrıldığı sipariş, satırı boşsa siparişin bütün kalemleri (kalemsiz arz)',
               existing_nullable=True,
               schema='stg')
    op.alter_column('WorkOrder', 'CustomerCode',
               existing_type=sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'),
               comment='Müşteri',
               existing_comment='Bağlı müşteri; i̇ş emrinin ayrıldığı müşteri',
               existing_nullable=True,
               schema='stg')
    op.alter_column('WorkOrder', 'ProjectCode',
               existing_type=sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'),
               comment='Proje (ayraç)',
               existing_comment='Bağlı proje; i̇ş emrinin ayrıldığı proje',
               existing_nullable=True,
               schema='stg')
    _table_comment('stg', 'Stok; lot ve durum bazında. Sahip: proje, müşteri, sipariş ya da ortak.')
    op.alter_column('Stock', 'SalesOrderLineNo',
               existing_type=sa.INTEGER(),
               comment='Sahip sipariş satırı; stoğun ayrıldığı sipariş satırı',
               existing_comment='Bağlı sipariş satırı',
               existing_nullable=True,
               schema='stg')
    op.alter_column('Stock', 'SalesOrderNo',
               existing_type=sa.NVARCHAR(length=30, collation='Latin1_General_100_CI_AS_SC'),
               comment='Sahip sipariş no; stoğun ayrıldığı sipariş, satır no boşsa siparişin bütün kalemleri (kalemsiz arz)',
               existing_comment='Bağlı sipariş no; stoğun ayrıldığı sipariş, satırı boşsa siparişin bütün kalemleri (kalemsiz arz)',
               existing_nullable=True,
               schema='stg')
    op.alter_column('Stock', 'CustomerCode',
               existing_type=sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'),
               comment='Sahip müşteri; stoğun ayrıldığı müşteri',
               existing_comment='Bağlı müşteri; stoğun ayrıldığı müşteri',
               existing_nullable=True,
               schema='stg')
    op.alter_column('Stock', 'ProjectCode',
               existing_type=sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'),
               comment='Sahip proje; proje, müşteri ve sipariş boşsa stok ortaktır',
               existing_comment='Bağlı proje; stoğun ayrıldığı proje',
               existing_nullable=True,
               schema='stg')
    op.alter_column('PurchaseOrderLine', 'SalesOrderNo',
               existing_type=sa.NVARCHAR(length=30, collation='Latin1_General_100_CI_AS_SC'),
               comment='Bağlı sipariş no',
               existing_comment='Bağlı sipariş no; satın alma satırının ayrıldığı sipariş, satırı boşsa siparişin bütün kalemleri (kalemsiz arz)',
               existing_nullable=True,
               schema='stg')
    op.alter_column('PurchaseOrderLine', 'CustomerCode',
               existing_type=sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'),
               comment='Müşteri',
               existing_comment='Bağlı müşteri; satın alma satırının ayrıldığı müşteri',
               existing_nullable=True,
               schema='stg')
    op.alter_column('PurchaseOrderLine', 'ProjectCode',
               existing_type=sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'),
               comment='Proje',
               existing_comment='Bağlı proje; satın alma satırının ayrıldığı proje',
               existing_nullable=True,
               schema='stg')
    op.alter_column('WorkOrder', 'SalesOrderLineNo',
               existing_type=sa.INTEGER(),
               comment='Bağlı sipariş satır no',
               existing_comment='Bağlı sipariş satırı',
               existing_nullable=True,
               schema='prc')
    op.alter_column('WorkOrder', 'SalesOrderNo',
               existing_type=sa.NVARCHAR(length=30, collation='Latin1_General_100_CI_AS_SC'),
               comment='Bağlı sipariş no (ayraç)',
               existing_comment='Bağlı sipariş no; i̇ş emrinin ayrıldığı sipariş, satırı boşsa siparişin bütün kalemleri (kalemsiz arz)',
               existing_nullable=True,
               schema='prc')
    op.alter_column('WorkOrder', 'CustomerCode',
               existing_type=sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'),
               comment='Müşteri',
               existing_comment='Bağlı müşteri; i̇ş emrinin ayrıldığı müşteri',
               existing_nullable=True,
               schema='prc')
    op.alter_column('WorkOrder', 'ProjectCode',
               existing_type=sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'),
               comment='Proje (ayraç)',
               existing_comment='Bağlı proje; i̇ş emrinin ayrıldığı proje',
               existing_nullable=True,
               schema='prc')
    _table_comment('prc', 'Stok; lot ve durum bazında. Sahip: proje, müşteri, sipariş ya da ortak.')
    op.alter_column('Stock', 'SalesOrderLineNo',
               existing_type=sa.INTEGER(),
               comment='Sahip sipariş satırı; stoğun ayrıldığı sipariş satırı',
               existing_comment='Bağlı sipariş satırı',
               existing_nullable=True,
               schema='prc')
    op.alter_column('Stock', 'SalesOrderNo',
               existing_type=sa.NVARCHAR(length=30, collation='Latin1_General_100_CI_AS_SC'),
               comment='Sahip sipariş no; stoğun ayrıldığı sipariş, satır no boşsa siparişin bütün kalemleri (kalemsiz arz)',
               existing_comment='Bağlı sipariş no; stoğun ayrıldığı sipariş, satırı boşsa siparişin bütün kalemleri (kalemsiz arz)',
               existing_nullable=True,
               schema='prc')
    op.alter_column('Stock', 'CustomerCode',
               existing_type=sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'),
               comment='Sahip müşteri; stoğun ayrıldığı müşteri',
               existing_comment='Bağlı müşteri; stoğun ayrıldığı müşteri',
               existing_nullable=True,
               schema='prc')
    op.alter_column('Stock', 'ProjectCode',
               existing_type=sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'),
               comment='Sahip proje; proje, müşteri ve sipariş boşsa stok ortaktır',
               existing_comment='Bağlı proje; stoğun ayrıldığı proje',
               existing_nullable=True,
               schema='prc')
    op.alter_column('PurchaseOrderLine', 'SalesOrderNo',
               existing_type=sa.NVARCHAR(length=30, collation='Latin1_General_100_CI_AS_SC'),
               comment='Bağlı sipariş no',
               existing_comment='Bağlı sipariş no; satın alma satırının ayrıldığı sipariş, satırı boşsa siparişin bütün kalemleri (kalemsiz arz)',
               existing_nullable=True,
               schema='prc')
    op.alter_column('PurchaseOrderLine', 'CustomerCode',
               existing_type=sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'),
               comment='Müşteri',
               existing_comment='Bağlı müşteri; satın alma satırının ayrıldığı müşteri',
               existing_nullable=True,
               schema='prc')
    op.alter_column('PurchaseOrderLine', 'ProjectCode',
               existing_type=sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'),
               comment='Proje',
               existing_comment='Bağlı proje; satın alma satırının ayrıldığı proje',
               existing_nullable=True,
               schema='prc')
    op.alter_column('WorkOrder', 'AllocationKey',
               existing_type=sa.NVARCHAR(length=60, collation='Latin1_General_100_CI_AS_SC'),
               comment='Arzın ayrıldığı sahibin anahtarı; satırda dolu olan en detaylı sahipten: sipariş (sipariş no, satır no ve alt satır no dik çizgiyle; kalemsiz arzda yalnız sipariş no), proje kodu ya da müşteri kodu. Lokasyon anahtara girmez; malzeme özel alokasyonlu değilse boştur (K-198)',
               existing_comment="Arzın ayrıldığı sahibin anahtarı; satırda ERP'nin yazdığı en detaylı sahipten: sipariş (sipariş no, satır ve alt satır dik çizgiyle; kalemsiz arzda yalnız sipariş no), proje kodu ya da müşteri kodu. Sahip sistemde bulunmasa da kapansa da anahtar kalır; lokasyon anahtara girmez; malzeme özel alokasyonlu değilse boştur (K-198)",
               existing_nullable=True,
               schema='core')
    op.alter_column('WorkOrder', 'SalesOrderLineItemNo',
               existing_type=sa.INTEGER(),
               comment="Bağlı sipariş alt satır no, ERP'den geldiği gibi",
               existing_comment="Bağlı siparişin alt satır no'su, ERP'den geldiği gibi",
               existing_nullable=True,
               schema='core')
    op.alter_column('WorkOrder', 'SalesOrderLineNo',
               existing_type=sa.INTEGER(),
               comment="Bağlı sipariş satır no, ERP'den geldiği gibi",
               existing_comment="Bağlı siparişin satır no'su, ERP'den geldiği gibi",
               existing_nullable=True,
               schema='core')
    op.alter_column('WorkOrder', 'SalesOrderNo',
               existing_type=sa.NVARCHAR(length=30, collation='Latin1_General_100_CI_AS_SC'),
               comment="Bağlı sipariş no, ERP'den geldiği gibi; satır no boşsa arz siparişin bütün kalemlerine ayrılmıştır (kalemsiz arz)",
               existing_comment="İş emrinin ayrıldığı sipariş, ERP'den geldiği gibi; satırı boşsa arz siparişin bütün kalemlerine ayrılmıştır (kalemsiz arz)",
               existing_nullable=True,
               schema='core')
    op.alter_column('WorkOrder', 'SalesOrderLineId',
               existing_type=sa.BIGINT(),
               comment='Bağlı sipariş satırı (ayraç); iç bağ: sipariş no ve satır no doluysa ve satır bulunuyorsa dolar, kalemsiz arzda boştur',
               existing_comment='Bağlı sipariş (iç bağ): sipariş no ve satırı doluysa ve satır bulunuyorsa dolar, kalemsiz arzda boştur; kolon olarak gösterilmez',
               existing_nullable=True,
               schema='core')
    op.alter_column('WorkOrder', 'CustomerId',
               existing_type=sa.BIGINT(),
               comment='Müşteri',
               existing_comment='Bağlı müşteri (iç bağ): müşteri kodu sistemde bulunuyorsa dolar; kolon olarak gösterilmez',
               existing_nullable=True,
               schema='core')
    op.alter_column('WorkOrder', 'ProjectId',
               existing_type=sa.BIGINT(),
               comment='Proje (ayraç)',
               existing_comment='Bağlı proje (iç bağ): proje kodu sistemde bulunuyorsa dolar; kolon olarak gösterilmez',
               existing_nullable=True,
               schema='core')
    op.drop_column('WorkOrder', 'CustomerCode', schema='core')
    op.drop_column('WorkOrder', 'ProjectCode', schema='core')
    _table_comment('core', 'Stok; lot ve durum bazında. Sahip: proje, müşteri, sipariş ya da ortak.')
    op.drop_index('UX_Stock_Key', table_name='Stock', schema='core', mssql_where=sa.text('VersionTo IS NULL'))
    op.alter_column('Stock', 'AllocationKey',
               existing_type=sa.NVARCHAR(length=60, collation='Latin1_General_100_CI_AS_SC'),
               comment='Arzın ayrıldığı sahibin anahtarı; satırda dolu olan en detaylı sahipten: sipariş (sipariş no, satır no ve alt satır no dik çizgiyle; kalemsiz arzda yalnız sipariş no), proje kodu ya da müşteri kodu. Lokasyon anahtara girmez; malzeme özel alokasyonlu değilse boştur (K-198)',
               existing_comment="Arzın ayrıldığı sahibin anahtarı; satırda ERP'nin yazdığı en detaylı sahipten: sipariş (sipariş no, satır ve alt satır dik çizgiyle; kalemsiz arzda yalnız sipariş no), proje kodu ya da müşteri kodu. Sahip sistemde bulunmasa da kapansa da anahtar kalır; lokasyon anahtara girmez; malzeme özel alokasyonlu değilse boştur (K-198)",
               existing_nullable=True,
               schema='core')
    op.alter_column('Stock', 'SalesOrderLineItemNo',
               existing_type=sa.INTEGER(),
               comment="Sahip sipariş alt satır no, ERP'den geldiği gibi",
               existing_comment="Bağlı siparişin alt satır no'su, ERP'den geldiği gibi",
               existing_nullable=True,
               schema='core')
    op.alter_column('Stock', 'SalesOrderLineNo',
               existing_type=sa.INTEGER(),
               comment="Sahip sipariş satır no, ERP'den geldiği gibi",
               existing_comment="Bağlı siparişin satır no'su, ERP'den geldiği gibi",
               existing_nullable=True,
               schema='core')
    op.alter_column('Stock', 'SalesOrderNo',
               existing_type=sa.NVARCHAR(length=30, collation='Latin1_General_100_CI_AS_SC'),
               comment="Sahip sipariş no, ERP'den geldiği gibi; satır no boşsa arz siparişin bütün kalemlerine ayrılmıştır (kalemsiz arz)",
               existing_comment="Stoğun ayrıldığı sipariş, ERP'den geldiği gibi; satırı boşsa arz siparişin bütün kalemlerine ayrılmıştır (kalemsiz arz)",
               existing_nullable=True,
               schema='core')
    op.alter_column('Stock', 'SalesOrderLineId',
               existing_type=sa.BIGINT(),
               comment='Sahip sipariş satırı; iç bağ: sipariş no ve satır no doluysa ve satır bulunuyorsa dolar, kalemsiz arzda boştur',
               existing_comment='Bağlı sipariş (iç bağ): sipariş no ve satırı doluysa ve satır bulunuyorsa dolar, kalemsiz arzda boştur; kolon olarak gösterilmez',
               existing_nullable=True,
               schema='core')
    op.alter_column('Stock', 'CustomerId',
               existing_type=sa.BIGINT(),
               comment='Sahip müşteri; stoğun ayrıldığı müşteri',
               existing_comment='Bağlı müşteri (iç bağ): müşteri kodu sistemde bulunuyorsa dolar; kolon olarak gösterilmez',
               existing_nullable=True,
               schema='core')
    op.alter_column('Stock', 'ProjectId',
               existing_type=sa.BIGINT(),
               comment='Sahip proje; proje, müşteri ve sipariş boşsa stok ortaktır',
               existing_comment='Bağlı proje (iç bağ): proje kodu sistemde bulunuyorsa dolar; kolon olarak gösterilmez',
               existing_nullable=True,
               schema='core')
    op.drop_column('Stock', 'CustomerCode', schema='core')
    op.drop_column('Stock', 'ProjectCode', schema='core')
    op.alter_column('PurchaseOrderLine', 'AllocationKey',
               existing_type=sa.NVARCHAR(length=60, collation='Latin1_General_100_CI_AS_SC'),
               comment='Arzın ayrıldığı sahibin anahtarı; satırda dolu olan en detaylı sahipten: sipariş (sipariş no, satır no ve alt satır no dik çizgiyle; kalemsiz arzda yalnız sipariş no), proje kodu ya da müşteri kodu. Lokasyon anahtara girmez; malzeme özel alokasyonlu değilse boştur (K-198)',
               existing_comment="Arzın ayrıldığı sahibin anahtarı; satırda ERP'nin yazdığı en detaylı sahipten: sipariş (sipariş no, satır ve alt satır dik çizgiyle; kalemsiz arzda yalnız sipariş no), proje kodu ya da müşteri kodu. Sahip sistemde bulunmasa da kapansa da anahtar kalır; lokasyon anahtara girmez; malzeme özel alokasyonlu değilse boştur (K-198)",
               existing_nullable=True,
               schema='core')
    op.alter_column('PurchaseOrderLine', 'SalesOrderLineItemNo',
               existing_type=sa.INTEGER(),
               comment="Bağlı satış sipariş alt satır no, ERP'den geldiği gibi",
               existing_comment="Bağlı siparişin alt satır no'su, ERP'den geldiği gibi",
               existing_nullable=True,
               schema='core')
    op.alter_column('PurchaseOrderLine', 'SalesOrderLineNo',
               existing_type=sa.INTEGER(),
               comment="Bağlı satış sipariş satır no, ERP'den geldiği gibi",
               existing_comment="Bağlı siparişin satır no'su, ERP'den geldiği gibi",
               existing_nullable=True,
               schema='core')
    op.alter_column('PurchaseOrderLine', 'SalesOrderNo',
               existing_type=sa.NVARCHAR(length=30, collation='Latin1_General_100_CI_AS_SC'),
               comment="Bağlı satış sipariş no, ERP'den geldiği gibi; satır no boşsa arz siparişin bütün kalemlerine ayrılmıştır (kalemsiz arz)",
               existing_comment="Satın alma satırının ayrıldığı sipariş, ERP'den geldiği gibi; satırı boşsa arz siparişin bütün kalemlerine ayrılmıştır (kalemsiz arz)",
               existing_nullable=True,
               schema='core')
    op.alter_column('PurchaseOrderLine', 'SalesOrderLineId',
               existing_type=sa.BIGINT(),
               comment='Bağlı sipariş satırı; iç bağ: sipariş no ve satır no doluysa ve satır bulunuyorsa dolar, kalemsiz arzda boştur',
               existing_comment='Bağlı sipariş (iç bağ): sipariş no ve satırı doluysa ve satır bulunuyorsa dolar, kalemsiz arzda boştur; kolon olarak gösterilmez',
               existing_nullable=True,
               schema='core')
    op.alter_column('PurchaseOrderLine', 'CustomerId',
               existing_type=sa.BIGINT(),
               comment='Müşteri',
               existing_comment='Bağlı müşteri (iç bağ): müşteri kodu sistemde bulunuyorsa dolar; kolon olarak gösterilmez',
               existing_nullable=True,
               schema='core')
    op.alter_column('PurchaseOrderLine', 'ProjectId',
               existing_type=sa.BIGINT(),
               comment='Proje',
               existing_comment='Bağlı proje (iç bağ): proje kodu sistemde bulunuyorsa dolar; kolon olarak gösterilmez',
               existing_nullable=True,
               schema='core')
    op.drop_column('PurchaseOrderLine', 'CustomerCode', schema='core')
    op.drop_column('PurchaseOrderLine', 'ProjectCode', schema='core')
    op.create_index('UX_Stock_LocationId_MaterialId_Warehouse_LotNo_Status_ProjectId_CustomerId_SalesOrderNo_SalesOrderLineNo_SalesOrderLineItemNo', 'Stock', ['LocationId', 'MaterialId', 'Warehouse', 'LotNo', 'Status', 'ProjectId', 'CustomerId', 'SalesOrderNo', 'SalesOrderLineNo', 'SalesOrderLineItemNo'],
                    unique=True, schema='core', mssql_where=sa.text('VersionTo IS NULL'))
    for table in ARZ:
        op.execute(f"DELETE FROM adm.FieldDefinition WHERE TableName = N'{table}' AND FieldName IN (N'ProjectCode', N'CustomerCode')")
    if not context.is_offline_mode():
        sync(op.get_bind(), metadata)
