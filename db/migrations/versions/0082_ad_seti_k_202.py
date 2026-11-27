"""0082 · Ad seti (K-202, 1. parça)

- "İş emri" → "Üretim siparişi": tablo ve kolon açıklamaları (görünen adlar buradan türer; veri sözlüğü eşitlenir). Tablo ve kolon adları değişmez.
- "Satın alma önerisi" → "Satın alma planı": pegging ölçütünün adı değişti; senaryoların kayıtlı Arz sırası (`param.PeggingCriterion`) çevrilir.
  Çevrilmezse eski ad tanımda bulunmadığı için atılır ve kullanıcının sırası sessizce bozulur.

Veri kaybı yok. Değerler ve açıklamalar geçişte sabittir (K-197). Denetim izindeki eski kayıtlar eski adla kalır. Geri alış adları ve
açıklamaları eski hâline çevirir.

Revision ID: 0082
Revises: 0081
Create Date: 2026-11-26
"""
from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql  # noqa: F401

from dictionary import sync
from models import metadata

revision = '0082'
down_revision = '0081'
branch_labels = None
depends_on = None

N_OLD, N_NEW = 'Satın alma önerisi', 'Satın alma planı'


def _criteria(forward):
    """Kayıtlı pegging sıralarında ölçütün adı (Arz sırası)."""
    a, b = (N_OLD, N_NEW) if forward else (N_NEW, N_OLD)
    op.execute(f"UPDATE param.PeggingCriterion SET Criterion = N'{b}' WHERE Side = N'Arz' AND Criterion = N'{a}'")


def _table_comment(schema, table, text):
    """SQL Server'da var olan tablo açıklaması (MS_Description) create_table_comment ile eklenemez; güncellenir."""
    op.execute(sa.text("EXEC sp_updateextendedproperty @name = N'MS_Description', @value = :v, @level0type = N'SCHEMA', @level0name = :s, "
                       "@level1type = N'TABLE', @level1name = :t").bindparams(v=text, s=schema, t=table))


def upgrade():
    _criteria(True)
    op.alter_column('ProductionConfirmation', 'WorkOrderId',
               existing_type=sa.BIGINT(),
               comment='Üretim siparişi',
               existing_comment='İş emri',
               existing_nullable=False,
               schema='core')
    _table_comment('core', 'ProductionConfirmation', 'Üretim gerçekleşmeleri: üretim siparişi bazında stoğa girişler.')
    op.alter_column('PurchaseOrderLine', 'WorkOrderId',
               existing_type=sa.BIGINT(),
               comment='Fasonda bağlı üretim siparişi',
               existing_comment='Fasonda bağlı iş emri',
               existing_nullable=True,
               schema='core')
    _table_comment('core', 'ResourceGroup', "Kaynak grubu: planlama birimi (K-180). Rota ve üretim siparişi operasyonu grubu gösterir; plan ve yük grup düzeyindedir. Tip, kritiklik, kapasite birimi ve fasoncu gruptadır. Gruptaki kaynak sayısı `ResourceGroupMember`'dan bilinir, ayrıca girilmez.")
    op.alter_column('WorkOrder', 'WorkOrderNo',
               existing_type=sa.Unicode(length=30),
               comment='Üretim siparişi no',
               existing_comment='İş emri no',
               existing_nullable=False,
               schema='core')
    op.alter_column('WorkOrder', 'ProductionVersionId',
               existing_type=sa.BIGINT(),
               comment='Üretim versiyonu; üretim siparişinin kendi bileşen ve operasyon satırları geldiyse motor onları kullanır, gelmediyse bu versiyonun ağacına ve rotasına gider',
               existing_comment='Üretim versiyonu; iş emrinin kendi bileşen ve operasyon satırları geldiyse motor onları kullanır, gelmediyse bu versiyonun ağacına ve rotasına gider',
               existing_nullable=True,
               schema='core')
    op.alter_column('WorkOrder', 'ProductionOrderType',
               existing_type=sa.Unicode(length=50),
               comment="ERP'den ham üretim siparişi tipi; veri kurallarında kullanılır, değer listesi yok",
               existing_comment="ERP'den ham iş emri tipi; veri kurallarında kullanılır, değer listesi yok",
               existing_nullable=True,
               schema='core')
    op.alter_column('WorkOrder', 'Status',
               existing_type=sa.Unicode(length=50),
               comment="ERP'den ham üretim siparişi durumu; veri kurallarında kullanılır, değer listesi yok",
               existing_comment="ERP'den ham iş emri durumu; veri kurallarında kullanılır, değer listesi yok",
               existing_nullable=True,
               schema='core')
    op.alter_column('WorkOrder', 'Priority',
               existing_type=sa.INTEGER(),
               comment='Üretim siparişi önceliği',
               existing_comment='İş emri önceliği',
               existing_nullable=True,
               schema='core')
    op.alter_column('WorkOrder', 'OrderedQuantity',
               existing_type=sa.NUMERIC(precision=18, scale=4),
               comment='Üretim siparişi miktarı',
               existing_comment='İş emri miktarı',
               existing_nullable=False,
               schema='core')
    op.alter_column('WorkOrder', 'ProjectCode',
               existing_type=sa.Unicode(length=50),
               comment="Üretim siparişinin ayrıldığı proje, ERP'den geldiği gibi; proje bulunamasa da kapansa da yazıldığı gibi kalır",
               existing_comment="İş emrinin ayrıldığı proje, ERP'den geldiği gibi; proje bulunamasa da kapansa da yazıldığı gibi kalır",
               existing_nullable=True,
               schema='core')
    op.alter_column('WorkOrder', 'CustomerCode',
               existing_type=sa.Unicode(length=50),
               comment="Üretim siparişinin ayrıldığı müşteri, ERP'den geldiği gibi; müşteri bulunamasa da kapansa da yazıldığı gibi kalır",
               existing_comment="İş emrinin ayrıldığı müşteri, ERP'den geldiği gibi; müşteri bulunamasa da kapansa da yazıldığı gibi kalır",
               existing_nullable=True,
               schema='core')
    op.alter_column('WorkOrder', 'SalesOrderNo',
               existing_type=sa.Unicode(length=30),
               comment="Üretim siparişinin ayrıldığı sipariş, ERP'den geldiği gibi; satırı boşsa arz siparişin bütün kalemlerine ayrılmıştır (kalemsiz arz)",
               existing_comment="İş emrinin ayrıldığı sipariş, ERP'den geldiği gibi; satırı boşsa arz siparişin bütün kalemlerine ayrılmıştır (kalemsiz arz)",
               existing_nullable=True,
               schema='core')
    op.alter_column('WorkOrder', 'ParentWorkOrderId',
               existing_type=sa.BIGINT(),
               comment='Yeniden işlemede orijinal üretim siparişi',
               existing_comment='Yeniden işlemede orijinal iş emri',
               existing_nullable=True,
               schema='core')
    op.alter_column('WorkOrder', 'IsFixed',
               existing_type=mssql.BIT(),
               comment='Motor bu üretim siparişinin tarihini ve miktarını değiştirmez',
               existing_comment='Motor bu iş emrinin tarihini ve miktarını değiştirmez',
               existing_nullable=True,
               schema='core')
    op.alter_column('WorkOrder', 'IsReleased',
               existing_type=mssql.BIT(),
               comment="Üretim siparişi yayınlandı; Status'tan veri kuralıyla doldurulur",
               existing_comment="İş emri yayınlandı; Status'tan veri kuralıyla doldurulur",
               existing_nullable=True,
               schema='core')
    op.alter_column('WorkOrder', 'IsStarted',
               existing_type=mssql.BIT(),
               comment="Üretim siparişi başladı; Status'tan veri kuralıyla doldurulur",
               existing_comment="İş emri başladı; Status'tan veri kuralıyla doldurulur",
               existing_nullable=True,
               schema='core')
    op.alter_column('WorkOrder', 'IsProduction',
               existing_type=mssql.BIT(),
               comment="Üretim siparişi; ProductionOrderType'tan veri kuralıyla doldurulur",
               existing_comment="Üretim iş emri; ProductionOrderType'tan veri kuralıyla doldurulur",
               existing_nullable=True,
               schema='core')
    op.alter_column('WorkOrder', 'IsSubcontract',
               existing_type=mssql.BIT(),
               comment="Fason üretim siparişi; ProductionOrderType'tan veri kuralıyla doldurulur",
               existing_comment="Fason iş emri; ProductionOrderType'tan veri kuralıyla doldurulur",
               existing_nullable=True,
               schema='core')
    op.alter_column('WorkOrder', 'IsRework',
               existing_type=mssql.BIT(),
               comment="Yeniden işleme üretim siparişi; ProductionOrderType'tan veri kuralıyla doldurulur",
               existing_comment="Yeniden işleme iş emri; ProductionOrderType'tan veri kuralıyla doldurulur",
               existing_nullable=True,
               schema='core')
    op.alter_column('WorkOrder', 'IsOnHold',
               existing_type=mssql.BIT(),
               comment='Bekletilen üretim siparişi',
               existing_comment='Bekletilen iş emri',
               existing_nullable=True,
               schema='core')
    op.alter_column('WorkOrder', 'IsCustomAllocated',
               existing_type=mssql.BIT(),
               comment='Üretim siparişi sahibine ayrılmış mı: malzeme özel alokasyonluysa ve satırda sahip (sipariş, proje ya da müşteri) varsa Evet; yüklemede hesaplanır (K-198)',
               existing_comment='İş emri sahibine ayrılmış mı: malzeme özel alokasyonluysa ve satırda sahip (sipariş, proje ya da müşteri) varsa Evet; yüklemede hesaplanır (K-198)',
               existing_nullable=True,
               schema='core')
    _table_comment('core', 'WorkOrder', 'Açık üretim siparişi (üretim, fason, yeniden işleme).')
    op.alter_column('WorkOrderComponent', 'WorkOrderId',
               existing_type=sa.BIGINT(),
               comment='Üretim siparişi',
               existing_comment='İş emri',
               existing_nullable=False,
               schema='core')
    _table_comment('core', 'WorkOrderComponent', 'Üretim siparişinin bileşenleri ve çekilen miktar.')
    op.alter_column('WorkOrderOperation', 'WorkOrderId',
               existing_type=sa.BIGINT(),
               comment='Üretim siparişi',
               existing_comment='İş emri',
               existing_nullable=False,
               schema='core')
    _table_comment('core', 'WorkOrderOperation', 'Üretim siparişinin operasyonları ve kalan iş.')
    op.alter_column('Pegging', 'SupplyType',
               existing_type=sa.Unicode(length=15),
               comment='Stok | Üretim siparişi | Satın alma | Planlı sipariş …',
               existing_comment='Stok | İş emri | Satın alma | Planlı sipariş …',
               existing_nullable=False,
               schema='planning')
    op.alter_column('SupplyRecommendation', 'SupplyType',
               existing_type=sa.Unicode(length=15),
               comment='Üretim siparişi | Satın alma | Fason | Transfer',
               existing_comment='İş emri | Satın alma | Fason | Transfer',
               existing_nullable=False,
               schema='planning')
    op.alter_column('ProductionConfirmation', 'WorkOrderNo',
               existing_type=sa.Unicode(length=30),
               comment='Üretim siparişi',
               existing_comment='İş emri',
               existing_nullable=True,
               schema='prc')
    _table_comment('prc', 'ProductionConfirmation', 'Üretim gerçekleşmeleri: üretim siparişi bazında stoğa girişler.')
    op.alter_column('PurchaseOrderLine', 'WorkOrderNo',
               existing_type=sa.Unicode(length=30),
               comment='Fasonda bağlı üretim siparişi',
               existing_comment='Fasonda bağlı iş emri',
               existing_nullable=True,
               schema='prc')
    _table_comment('prc', 'ResourceGroup', "Kaynak grubu: planlama birimi (K-180). Rota ve üretim siparişi operasyonu grubu gösterir; plan ve yük grup düzeyindedir. Tip, kritiklik, kapasite birimi ve fasoncu gruptadır. Gruptaki kaynak sayısı `ResourceGroupMember`'dan bilinir, ayrıca girilmez.")
    op.alter_column('WorkOrder', 'WorkOrderNo',
               existing_type=sa.Unicode(length=30),
               comment='Üretim siparişi no',
               existing_comment='İş emri no',
               existing_nullable=True,
               schema='prc')
    op.alter_column('WorkOrder', 'ProductionVersionCode',
               existing_type=sa.Unicode(length=30),
               comment='Üretim versiyonu; üretim siparişinin kendi bileşen ve operasyon satırları geldiyse motor onları kullanır, gelmediyse bu versiyonun ağacına ve rotasına gider',
               existing_comment='Üretim versiyonu; iş emrinin kendi bileşen ve operasyon satırları geldiyse motor onları kullanır, gelmediyse bu versiyonun ağacına ve rotasına gider',
               existing_nullable=True,
               schema='prc')
    op.alter_column('WorkOrder', 'ProductionOrderType',
               existing_type=sa.Unicode(length=50),
               comment="ERP'den ham üretim siparişi tipi; veri kurallarında kullanılır, değer listesi yok",
               existing_comment="ERP'den ham iş emri tipi; veri kurallarında kullanılır, değer listesi yok",
               existing_nullable=True,
               schema='prc')
    op.alter_column('WorkOrder', 'Status',
               existing_type=sa.Unicode(length=50),
               comment="ERP'den ham üretim siparişi durumu; veri kurallarında kullanılır, değer listesi yok",
               existing_comment="ERP'den ham iş emri durumu; veri kurallarında kullanılır, değer listesi yok",
               existing_nullable=True,
               schema='prc')
    op.alter_column('WorkOrder', 'Priority',
               existing_type=sa.INTEGER(),
               comment='Üretim siparişi önceliği',
               existing_comment='İş emri önceliği',
               existing_nullable=True,
               schema='prc')
    op.alter_column('WorkOrder', 'OrderedQuantity',
               existing_type=sa.NUMERIC(precision=18, scale=4),
               comment='Üretim siparişi miktarı',
               existing_comment='İş emri miktarı',
               existing_nullable=True,
               schema='prc')
    op.alter_column('WorkOrder', 'ParentWorkOrderNo',
               existing_type=sa.Unicode(length=30),
               comment='Orijinal üretim siparişi',
               existing_comment='Yeniden işlemede orijinal iş emri',
               existing_nullable=True,
               schema='prc')
    op.alter_column('WorkOrder', 'IsFixed',
               existing_type=mssql.BIT(),
               comment='Motor bu üretim siparişinin tarihini ve miktarını değiştirmez',
               existing_comment='Motor bu iş emrinin tarihini ve miktarını değiştirmez',
               existing_nullable=True,
               schema='prc')
    op.alter_column('WorkOrder', 'IsReleased',
               existing_type=mssql.BIT(),
               comment="Üretim siparişi yayınlandı; Status'tan veri kuralıyla doldurulur",
               existing_comment="İş emri yayınlandı; Status'tan veri kuralıyla doldurulur",
               existing_nullable=True,
               schema='prc')
    op.alter_column('WorkOrder', 'IsStarted',
               existing_type=mssql.BIT(),
               comment="Üretim siparişi başladı; Status'tan veri kuralıyla doldurulur",
               existing_comment="İş emri başladı; Status'tan veri kuralıyla doldurulur",
               existing_nullable=True,
               schema='prc')
    op.alter_column('WorkOrder', 'IsProduction',
               existing_type=mssql.BIT(),
               comment="Üretim siparişi; ProductionOrderType'tan veri kuralıyla doldurulur",
               existing_comment="Üretim iş emri; ProductionOrderType'tan veri kuralıyla doldurulur",
               existing_nullable=True,
               schema='prc')
    op.alter_column('WorkOrder', 'IsSubcontract',
               existing_type=mssql.BIT(),
               comment="Fason üretim siparişi; ProductionOrderType'tan veri kuralıyla doldurulur",
               existing_comment="Fason iş emri; ProductionOrderType'tan veri kuralıyla doldurulur",
               existing_nullable=True,
               schema='prc')
    op.alter_column('WorkOrder', 'IsRework',
               existing_type=mssql.BIT(),
               comment="Yeniden işleme üretim siparişi; ProductionOrderType'tan veri kuralıyla doldurulur",
               existing_comment="Yeniden işleme iş emri; ProductionOrderType'tan veri kuralıyla doldurulur",
               existing_nullable=True,
               schema='prc')
    op.alter_column('WorkOrder', 'IsOnHold',
               existing_type=mssql.BIT(),
               comment='Bekletilen üretim siparişi',
               existing_comment='Bekletilen iş emri',
               existing_nullable=True,
               schema='prc')
    _table_comment('prc', 'WorkOrder', 'Açık üretim siparişi (üretim, fason, yeniden işleme).')
    op.alter_column('WorkOrderComponent', 'WorkOrderNo',
               existing_type=sa.Unicode(length=30),
               comment='Üretim siparişi',
               existing_comment='İş emri',
               existing_nullable=True,
               schema='prc')
    _table_comment('prc', 'WorkOrderComponent', 'Üretim siparişinin bileşenleri ve çekilen miktar.')
    op.alter_column('WorkOrderOperation', 'WorkOrderNo',
               existing_type=sa.Unicode(length=30),
               comment='Üretim siparişi',
               existing_comment='İş emri',
               existing_nullable=True,
               schema='prc')
    _table_comment('prc', 'WorkOrderOperation', 'Üretim siparişinin operasyonları ve kalan iş.')
    op.alter_column('ProductionConfirmation', 'WorkOrderNo',
               existing_type=sa.Unicode(length=30),
               comment='Üretim siparişi',
               existing_comment='İş emri',
               existing_nullable=True,
               schema='stg')
    _table_comment('stg', 'ProductionConfirmation', 'Üretim gerçekleşmeleri: üretim siparişi bazında stoğa girişler.')
    op.alter_column('PurchaseOrderLine', 'WorkOrderNo',
               existing_type=sa.Unicode(length=30),
               comment='Fasonda bağlı üretim siparişi',
               existing_comment='Fasonda bağlı iş emri',
               existing_nullable=True,
               schema='stg')
    _table_comment('stg', 'ResourceGroup', "Kaynak grubu: planlama birimi (K-180). Rota ve üretim siparişi operasyonu grubu gösterir; plan ve yük grup düzeyindedir. Tip, kritiklik, kapasite birimi ve fasoncu gruptadır. Gruptaki kaynak sayısı `ResourceGroupMember`'dan bilinir, ayrıca girilmez.")
    op.alter_column('WorkOrder', 'WorkOrderNo',
               existing_type=sa.Unicode(length=30),
               comment='Üretim siparişi no',
               existing_comment='İş emri no',
               existing_nullable=True,
               schema='stg')
    op.alter_column('WorkOrder', 'ProductionVersionCode',
               existing_type=sa.Unicode(length=30),
               comment='Üretim versiyonu; üretim siparişinin kendi bileşen ve operasyon satırları geldiyse motor onları kullanır, gelmediyse bu versiyonun ağacına ve rotasına gider',
               existing_comment='Üretim versiyonu; iş emrinin kendi bileşen ve operasyon satırları geldiyse motor onları kullanır, gelmediyse bu versiyonun ağacına ve rotasına gider',
               existing_nullable=True,
               schema='stg')
    op.alter_column('WorkOrder', 'ProductionOrderType',
               existing_type=sa.Unicode(length=50),
               comment="ERP'den ham üretim siparişi tipi; veri kurallarında kullanılır, değer listesi yok",
               existing_comment="ERP'den ham iş emri tipi; veri kurallarında kullanılır, değer listesi yok",
               existing_nullable=True,
               schema='stg')
    op.alter_column('WorkOrder', 'Status',
               existing_type=sa.Unicode(length=50),
               comment="ERP'den ham üretim siparişi durumu; veri kurallarında kullanılır, değer listesi yok",
               existing_comment="ERP'den ham iş emri durumu; veri kurallarında kullanılır, değer listesi yok",
               existing_nullable=True,
               schema='stg')
    op.alter_column('WorkOrder', 'Priority',
               existing_type=sa.INTEGER(),
               comment='Üretim siparişi önceliği',
               existing_comment='İş emri önceliği',
               existing_nullable=True,
               schema='stg')
    op.alter_column('WorkOrder', 'OrderedQuantity',
               existing_type=sa.NUMERIC(precision=18, scale=4),
               comment='Üretim siparişi miktarı',
               existing_comment='İş emri miktarı',
               existing_nullable=True,
               schema='stg')
    op.alter_column('WorkOrder', 'ParentWorkOrderNo',
               existing_type=sa.Unicode(length=30),
               comment='Orijinal üretim siparişi',
               existing_comment='Yeniden işlemede orijinal iş emri',
               existing_nullable=True,
               schema='stg')
    op.alter_column('WorkOrder', 'IsFixed',
               existing_type=mssql.BIT(),
               comment='Motor bu üretim siparişinin tarihini ve miktarını değiştirmez',
               existing_comment='Motor bu iş emrinin tarihini ve miktarını değiştirmez',
               existing_nullable=True,
               schema='stg')
    op.alter_column('WorkOrder', 'IsReleased',
               existing_type=mssql.BIT(),
               comment="Üretim siparişi yayınlandı; Status'tan veri kuralıyla doldurulur",
               existing_comment="İş emri yayınlandı; Status'tan veri kuralıyla doldurulur",
               existing_nullable=True,
               schema='stg')
    op.alter_column('WorkOrder', 'IsStarted',
               existing_type=mssql.BIT(),
               comment="Üretim siparişi başladı; Status'tan veri kuralıyla doldurulur",
               existing_comment="İş emri başladı; Status'tan veri kuralıyla doldurulur",
               existing_nullable=True,
               schema='stg')
    op.alter_column('WorkOrder', 'IsProduction',
               existing_type=mssql.BIT(),
               comment="Üretim siparişi; ProductionOrderType'tan veri kuralıyla doldurulur",
               existing_comment="Üretim iş emri; ProductionOrderType'tan veri kuralıyla doldurulur",
               existing_nullable=True,
               schema='stg')
    op.alter_column('WorkOrder', 'IsSubcontract',
               existing_type=mssql.BIT(),
               comment="Fason üretim siparişi; ProductionOrderType'tan veri kuralıyla doldurulur",
               existing_comment="Fason iş emri; ProductionOrderType'tan veri kuralıyla doldurulur",
               existing_nullable=True,
               schema='stg')
    op.alter_column('WorkOrder', 'IsRework',
               existing_type=mssql.BIT(),
               comment="Yeniden işleme üretim siparişi; ProductionOrderType'tan veri kuralıyla doldurulur",
               existing_comment="Yeniden işleme iş emri; ProductionOrderType'tan veri kuralıyla doldurulur",
               existing_nullable=True,
               schema='stg')
    op.alter_column('WorkOrder', 'IsOnHold',
               existing_type=mssql.BIT(),
               comment='Bekletilen üretim siparişi',
               existing_comment='Bekletilen iş emri',
               existing_nullable=True,
               schema='stg')
    _table_comment('stg', 'WorkOrder', 'Açık üretim siparişi (üretim, fason, yeniden işleme).')
    op.alter_column('WorkOrderComponent', 'WorkOrderNo',
               existing_type=sa.Unicode(length=30),
               comment='Üretim siparişi',
               existing_comment='İş emri',
               existing_nullable=True,
               schema='stg')
    _table_comment('stg', 'WorkOrderComponent', 'Üretim siparişinin bileşenleri ve çekilen miktar.')
    op.alter_column('WorkOrderOperation', 'WorkOrderNo',
               existing_type=sa.Unicode(length=30),
               comment='Üretim siparişi',
               existing_comment='İş emri',
               existing_nullable=True,
               schema='stg')
    _table_comment('stg', 'WorkOrderOperation', 'Üretim siparişinin operasyonları ve kalan iş.')
    if not context.is_offline_mode():  # bağlantısız SQL betiğinde satırlar yazılmaz; ilk bağlantılı geçişte kurulur
        sync(op.get_bind(), metadata)


def downgrade():
    _criteria(False)
    _table_comment('stg', 'WorkOrderOperation', 'İş emrinin operasyonları ve kalan iş.')
    op.alter_column('WorkOrderOperation', 'WorkOrderNo',
               existing_type=sa.Unicode(length=30),
               comment='İş emri',
               existing_comment='Üretim siparişi',
               existing_nullable=True,
               schema='stg')
    _table_comment('stg', 'WorkOrderComponent', 'İş emrinin bileşenleri ve çekilen miktar.')
    op.alter_column('WorkOrderComponent', 'WorkOrderNo',
               existing_type=sa.Unicode(length=30),
               comment='İş emri',
               existing_comment='Üretim siparişi',
               existing_nullable=True,
               schema='stg')
    _table_comment('stg', 'WorkOrder', 'Açık iş emri (üretim, fason, yeniden işleme).')
    op.alter_column('WorkOrder', 'IsOnHold',
               existing_type=mssql.BIT(),
               comment='Bekletilen iş emri',
               existing_comment='Bekletilen üretim siparişi',
               existing_nullable=True,
               schema='stg')
    op.alter_column('WorkOrder', 'IsRework',
               existing_type=mssql.BIT(),
               comment="Yeniden işleme iş emri; ProductionOrderType'tan veri kuralıyla doldurulur",
               existing_comment="Yeniden işleme üretim siparişi; ProductionOrderType'tan veri kuralıyla doldurulur",
               existing_nullable=True,
               schema='stg')
    op.alter_column('WorkOrder', 'IsSubcontract',
               existing_type=mssql.BIT(),
               comment="Fason iş emri; ProductionOrderType'tan veri kuralıyla doldurulur",
               existing_comment="Fason üretim siparişi; ProductionOrderType'tan veri kuralıyla doldurulur",
               existing_nullable=True,
               schema='stg')
    op.alter_column('WorkOrder', 'IsProduction',
               existing_type=mssql.BIT(),
               comment="Üretim iş emri; ProductionOrderType'tan veri kuralıyla doldurulur",
               existing_comment="Üretim siparişi; ProductionOrderType'tan veri kuralıyla doldurulur",
               existing_nullable=True,
               schema='stg')
    op.alter_column('WorkOrder', 'IsStarted',
               existing_type=mssql.BIT(),
               comment="İş emri başladı; Status'tan veri kuralıyla doldurulur",
               existing_comment="Üretim siparişi başladı; Status'tan veri kuralıyla doldurulur",
               existing_nullable=True,
               schema='stg')
    op.alter_column('WorkOrder', 'IsReleased',
               existing_type=mssql.BIT(),
               comment="İş emri yayınlandı; Status'tan veri kuralıyla doldurulur",
               existing_comment="Üretim siparişi yayınlandı; Status'tan veri kuralıyla doldurulur",
               existing_nullable=True,
               schema='stg')
    op.alter_column('WorkOrder', 'IsFixed',
               existing_type=mssql.BIT(),
               comment='Motor bu iş emrinin tarihini ve miktarını değiştirmez',
               existing_comment='Motor bu üretim siparişinin tarihini ve miktarını değiştirmez',
               existing_nullable=True,
               schema='stg')
    op.alter_column('WorkOrder', 'ParentWorkOrderNo',
               existing_type=sa.Unicode(length=30),
               comment='Yeniden işlemede orijinal iş emri',
               existing_comment='Orijinal üretim siparişi',
               existing_nullable=True,
               schema='stg')
    op.alter_column('WorkOrder', 'OrderedQuantity',
               existing_type=sa.NUMERIC(precision=18, scale=4),
               comment='İş emri miktarı',
               existing_comment='Üretim siparişi miktarı',
               existing_nullable=True,
               schema='stg')
    op.alter_column('WorkOrder', 'Priority',
               existing_type=sa.INTEGER(),
               comment='İş emri önceliği',
               existing_comment='Üretim siparişi önceliği',
               existing_nullable=True,
               schema='stg')
    op.alter_column('WorkOrder', 'Status',
               existing_type=sa.Unicode(length=50),
               comment="ERP'den ham iş emri durumu; veri kurallarında kullanılır, değer listesi yok",
               existing_comment="ERP'den ham üretim siparişi durumu; veri kurallarında kullanılır, değer listesi yok",
               existing_nullable=True,
               schema='stg')
    op.alter_column('WorkOrder', 'ProductionOrderType',
               existing_type=sa.Unicode(length=50),
               comment="ERP'den ham iş emri tipi; veri kurallarında kullanılır, değer listesi yok",
               existing_comment="ERP'den ham üretim siparişi tipi; veri kurallarında kullanılır, değer listesi yok",
               existing_nullable=True,
               schema='stg')
    op.alter_column('WorkOrder', 'ProductionVersionCode',
               existing_type=sa.Unicode(length=30),
               comment='Üretim versiyonu; iş emrinin kendi bileşen ve operasyon satırları geldiyse motor onları kullanır, gelmediyse bu versiyonun ağacına ve rotasına gider',
               existing_comment='Üretim versiyonu; üretim siparişinin kendi bileşen ve operasyon satırları geldiyse motor onları kullanır, gelmediyse bu versiyonun ağacına ve rotasına gider',
               existing_nullable=True,
               schema='stg')
    op.alter_column('WorkOrder', 'WorkOrderNo',
               existing_type=sa.Unicode(length=30),
               comment='İş emri no',
               existing_comment='Üretim siparişi no',
               existing_nullable=True,
               schema='stg')
    _table_comment('stg', 'ResourceGroup', "Kaynak grubu: planlama birimi (K-180). Rota ve iş emri operasyonu grubu gösterir; plan ve yük grup düzeyindedir. Tip, kritiklik, kapasite birimi ve fasoncu gruptadır. Gruptaki kaynak sayısı `ResourceGroupMember`'dan bilinir, ayrıca girilmez.")
    op.alter_column('PurchaseOrderLine', 'WorkOrderNo',
               existing_type=sa.Unicode(length=30),
               comment='Fasonda bağlı iş emri',
               existing_comment='Fasonda bağlı üretim siparişi',
               existing_nullable=True,
               schema='stg')
    _table_comment('stg', 'ProductionConfirmation', 'Üretim gerçekleşmeleri: iş emri bazında stoğa girişler.')
    op.alter_column('ProductionConfirmation', 'WorkOrderNo',
               existing_type=sa.Unicode(length=30),
               comment='İş emri',
               existing_comment='Üretim siparişi',
               existing_nullable=True,
               schema='stg')
    _table_comment('prc', 'WorkOrderOperation', 'İş emrinin operasyonları ve kalan iş.')
    op.alter_column('WorkOrderOperation', 'WorkOrderNo',
               existing_type=sa.Unicode(length=30),
               comment='İş emri',
               existing_comment='Üretim siparişi',
               existing_nullable=True,
               schema='prc')
    _table_comment('prc', 'WorkOrderComponent', 'İş emrinin bileşenleri ve çekilen miktar.')
    op.alter_column('WorkOrderComponent', 'WorkOrderNo',
               existing_type=sa.Unicode(length=30),
               comment='İş emri',
               existing_comment='Üretim siparişi',
               existing_nullable=True,
               schema='prc')
    _table_comment('prc', 'WorkOrder', 'Açık iş emri (üretim, fason, yeniden işleme).')
    op.alter_column('WorkOrder', 'IsOnHold',
               existing_type=mssql.BIT(),
               comment='Bekletilen iş emri',
               existing_comment='Bekletilen üretim siparişi',
               existing_nullable=True,
               schema='prc')
    op.alter_column('WorkOrder', 'IsRework',
               existing_type=mssql.BIT(),
               comment="Yeniden işleme iş emri; ProductionOrderType'tan veri kuralıyla doldurulur",
               existing_comment="Yeniden işleme üretim siparişi; ProductionOrderType'tan veri kuralıyla doldurulur",
               existing_nullable=True,
               schema='prc')
    op.alter_column('WorkOrder', 'IsSubcontract',
               existing_type=mssql.BIT(),
               comment="Fason iş emri; ProductionOrderType'tan veri kuralıyla doldurulur",
               existing_comment="Fason üretim siparişi; ProductionOrderType'tan veri kuralıyla doldurulur",
               existing_nullable=True,
               schema='prc')
    op.alter_column('WorkOrder', 'IsProduction',
               existing_type=mssql.BIT(),
               comment="Üretim iş emri; ProductionOrderType'tan veri kuralıyla doldurulur",
               existing_comment="Üretim siparişi; ProductionOrderType'tan veri kuralıyla doldurulur",
               existing_nullable=True,
               schema='prc')
    op.alter_column('WorkOrder', 'IsStarted',
               existing_type=mssql.BIT(),
               comment="İş emri başladı; Status'tan veri kuralıyla doldurulur",
               existing_comment="Üretim siparişi başladı; Status'tan veri kuralıyla doldurulur",
               existing_nullable=True,
               schema='prc')
    op.alter_column('WorkOrder', 'IsReleased',
               existing_type=mssql.BIT(),
               comment="İş emri yayınlandı; Status'tan veri kuralıyla doldurulur",
               existing_comment="Üretim siparişi yayınlandı; Status'tan veri kuralıyla doldurulur",
               existing_nullable=True,
               schema='prc')
    op.alter_column('WorkOrder', 'IsFixed',
               existing_type=mssql.BIT(),
               comment='Motor bu iş emrinin tarihini ve miktarını değiştirmez',
               existing_comment='Motor bu üretim siparişinin tarihini ve miktarını değiştirmez',
               existing_nullable=True,
               schema='prc')
    op.alter_column('WorkOrder', 'ParentWorkOrderNo',
               existing_type=sa.Unicode(length=30),
               comment='Yeniden işlemede orijinal iş emri',
               existing_comment='Orijinal üretim siparişi',
               existing_nullable=True,
               schema='prc')
    op.alter_column('WorkOrder', 'OrderedQuantity',
               existing_type=sa.NUMERIC(precision=18, scale=4),
               comment='İş emri miktarı',
               existing_comment='Üretim siparişi miktarı',
               existing_nullable=True,
               schema='prc')
    op.alter_column('WorkOrder', 'Priority',
               existing_type=sa.INTEGER(),
               comment='İş emri önceliği',
               existing_comment='Üretim siparişi önceliği',
               existing_nullable=True,
               schema='prc')
    op.alter_column('WorkOrder', 'Status',
               existing_type=sa.Unicode(length=50),
               comment="ERP'den ham iş emri durumu; veri kurallarında kullanılır, değer listesi yok",
               existing_comment="ERP'den ham üretim siparişi durumu; veri kurallarında kullanılır, değer listesi yok",
               existing_nullable=True,
               schema='prc')
    op.alter_column('WorkOrder', 'ProductionOrderType',
               existing_type=sa.Unicode(length=50),
               comment="ERP'den ham iş emri tipi; veri kurallarında kullanılır, değer listesi yok",
               existing_comment="ERP'den ham üretim siparişi tipi; veri kurallarında kullanılır, değer listesi yok",
               existing_nullable=True,
               schema='prc')
    op.alter_column('WorkOrder', 'ProductionVersionCode',
               existing_type=sa.Unicode(length=30),
               comment='Üretim versiyonu; iş emrinin kendi bileşen ve operasyon satırları geldiyse motor onları kullanır, gelmediyse bu versiyonun ağacına ve rotasına gider',
               existing_comment='Üretim versiyonu; üretim siparişinin kendi bileşen ve operasyon satırları geldiyse motor onları kullanır, gelmediyse bu versiyonun ağacına ve rotasına gider',
               existing_nullable=True,
               schema='prc')
    op.alter_column('WorkOrder', 'WorkOrderNo',
               existing_type=sa.Unicode(length=30),
               comment='İş emri no',
               existing_comment='Üretim siparişi no',
               existing_nullable=True,
               schema='prc')
    _table_comment('prc', 'ResourceGroup', "Kaynak grubu: planlama birimi (K-180). Rota ve iş emri operasyonu grubu gösterir; plan ve yük grup düzeyindedir. Tip, kritiklik, kapasite birimi ve fasoncu gruptadır. Gruptaki kaynak sayısı `ResourceGroupMember`'dan bilinir, ayrıca girilmez.")
    op.alter_column('PurchaseOrderLine', 'WorkOrderNo',
               existing_type=sa.Unicode(length=30),
               comment='Fasonda bağlı iş emri',
               existing_comment='Fasonda bağlı üretim siparişi',
               existing_nullable=True,
               schema='prc')
    _table_comment('prc', 'ProductionConfirmation', 'Üretim gerçekleşmeleri: iş emri bazında stoğa girişler.')
    op.alter_column('ProductionConfirmation', 'WorkOrderNo',
               existing_type=sa.Unicode(length=30),
               comment='İş emri',
               existing_comment='Üretim siparişi',
               existing_nullable=True,
               schema='prc')
    op.alter_column('SupplyRecommendation', 'SupplyType',
               existing_type=sa.Unicode(length=15),
               comment='İş emri | Satın alma | Fason | Transfer',
               existing_comment='Üretim siparişi | Satın alma | Fason | Transfer',
               existing_nullable=False,
               schema='planning')
    op.alter_column('Pegging', 'SupplyType',
               existing_type=sa.Unicode(length=15),
               comment='Stok | İş emri | Satın alma | Planlı sipariş …',
               existing_comment='Stok | Üretim siparişi | Satın alma | Planlı sipariş …',
               existing_nullable=False,
               schema='planning')
    _table_comment('core', 'WorkOrderOperation', 'İş emrinin operasyonları ve kalan iş.')
    op.alter_column('WorkOrderOperation', 'WorkOrderId',
               existing_type=sa.BIGINT(),
               comment='İş emri',
               existing_comment='Üretim siparişi',
               existing_nullable=False,
               schema='core')
    _table_comment('core', 'WorkOrderComponent', 'İş emrinin bileşenleri ve çekilen miktar.')
    op.alter_column('WorkOrderComponent', 'WorkOrderId',
               existing_type=sa.BIGINT(),
               comment='İş emri',
               existing_comment='Üretim siparişi',
               existing_nullable=False,
               schema='core')
    _table_comment('core', 'WorkOrder', 'Açık iş emri (üretim, fason, yeniden işleme).')
    op.alter_column('WorkOrder', 'IsCustomAllocated',
               existing_type=mssql.BIT(),
               comment='İş emri sahibine ayrılmış mı: malzeme özel alokasyonluysa ve satırda sahip (sipariş, proje ya da müşteri) varsa Evet; yüklemede hesaplanır (K-198)',
               existing_comment='Üretim siparişi sahibine ayrılmış mı: malzeme özel alokasyonluysa ve satırda sahip (sipariş, proje ya da müşteri) varsa Evet; yüklemede hesaplanır (K-198)',
               existing_nullable=True,
               schema='core')
    op.alter_column('WorkOrder', 'IsOnHold',
               existing_type=mssql.BIT(),
               comment='Bekletilen iş emri',
               existing_comment='Bekletilen üretim siparişi',
               existing_nullable=True,
               schema='core')
    op.alter_column('WorkOrder', 'IsRework',
               existing_type=mssql.BIT(),
               comment="Yeniden işleme iş emri; ProductionOrderType'tan veri kuralıyla doldurulur",
               existing_comment="Yeniden işleme üretim siparişi; ProductionOrderType'tan veri kuralıyla doldurulur",
               existing_nullable=True,
               schema='core')
    op.alter_column('WorkOrder', 'IsSubcontract',
               existing_type=mssql.BIT(),
               comment="Fason iş emri; ProductionOrderType'tan veri kuralıyla doldurulur",
               existing_comment="Fason üretim siparişi; ProductionOrderType'tan veri kuralıyla doldurulur",
               existing_nullable=True,
               schema='core')
    op.alter_column('WorkOrder', 'IsProduction',
               existing_type=mssql.BIT(),
               comment="Üretim iş emri; ProductionOrderType'tan veri kuralıyla doldurulur",
               existing_comment="Üretim siparişi; ProductionOrderType'tan veri kuralıyla doldurulur",
               existing_nullable=True,
               schema='core')
    op.alter_column('WorkOrder', 'IsStarted',
               existing_type=mssql.BIT(),
               comment="İş emri başladı; Status'tan veri kuralıyla doldurulur",
               existing_comment="Üretim siparişi başladı; Status'tan veri kuralıyla doldurulur",
               existing_nullable=True,
               schema='core')
    op.alter_column('WorkOrder', 'IsReleased',
               existing_type=mssql.BIT(),
               comment="İş emri yayınlandı; Status'tan veri kuralıyla doldurulur",
               existing_comment="Üretim siparişi yayınlandı; Status'tan veri kuralıyla doldurulur",
               existing_nullable=True,
               schema='core')
    op.alter_column('WorkOrder', 'IsFixed',
               existing_type=mssql.BIT(),
               comment='Motor bu iş emrinin tarihini ve miktarını değiştirmez',
               existing_comment='Motor bu üretim siparişinin tarihini ve miktarını değiştirmez',
               existing_nullable=True,
               schema='core')
    op.alter_column('WorkOrder', 'ParentWorkOrderId',
               existing_type=sa.BIGINT(),
               comment='Yeniden işlemede orijinal iş emri',
               existing_comment='Yeniden işlemede orijinal üretim siparişi',
               existing_nullable=True,
               schema='core')
    op.alter_column('WorkOrder', 'SalesOrderNo',
               existing_type=sa.Unicode(length=30),
               comment="İş emrinin ayrıldığı sipariş, ERP'den geldiği gibi; satırı boşsa arz siparişin bütün kalemlerine ayrılmıştır (kalemsiz arz)",
               existing_comment="Üretim siparişinin ayrıldığı sipariş, ERP'den geldiği gibi; satırı boşsa arz siparişin bütün kalemlerine ayrılmıştır (kalemsiz arz)",
               existing_nullable=True,
               schema='core')
    op.alter_column('WorkOrder', 'CustomerCode',
               existing_type=sa.Unicode(length=50),
               comment="İş emrinin ayrıldığı müşteri, ERP'den geldiği gibi; müşteri bulunamasa da kapansa da yazıldığı gibi kalır",
               existing_comment="Üretim siparişinin ayrıldığı müşteri, ERP'den geldiği gibi; müşteri bulunamasa da kapansa da yazıldığı gibi kalır",
               existing_nullable=True,
               schema='core')
    op.alter_column('WorkOrder', 'ProjectCode',
               existing_type=sa.Unicode(length=50),
               comment="İş emrinin ayrıldığı proje, ERP'den geldiği gibi; proje bulunamasa da kapansa da yazıldığı gibi kalır",
               existing_comment="Üretim siparişinin ayrıldığı proje, ERP'den geldiği gibi; proje bulunamasa da kapansa da yazıldığı gibi kalır",
               existing_nullable=True,
               schema='core')
    op.alter_column('WorkOrder', 'OrderedQuantity',
               existing_type=sa.NUMERIC(precision=18, scale=4),
               comment='İş emri miktarı',
               existing_comment='Üretim siparişi miktarı',
               existing_nullable=False,
               schema='core')
    op.alter_column('WorkOrder', 'Priority',
               existing_type=sa.INTEGER(),
               comment='İş emri önceliği',
               existing_comment='Üretim siparişi önceliği',
               existing_nullable=True,
               schema='core')
    op.alter_column('WorkOrder', 'Status',
               existing_type=sa.Unicode(length=50),
               comment="ERP'den ham iş emri durumu; veri kurallarında kullanılır, değer listesi yok",
               existing_comment="ERP'den ham üretim siparişi durumu; veri kurallarında kullanılır, değer listesi yok",
               existing_nullable=True,
               schema='core')
    op.alter_column('WorkOrder', 'ProductionOrderType',
               existing_type=sa.Unicode(length=50),
               comment="ERP'den ham iş emri tipi; veri kurallarında kullanılır, değer listesi yok",
               existing_comment="ERP'den ham üretim siparişi tipi; veri kurallarında kullanılır, değer listesi yok",
               existing_nullable=True,
               schema='core')
    op.alter_column('WorkOrder', 'ProductionVersionId',
               existing_type=sa.BIGINT(),
               comment='Üretim versiyonu; iş emrinin kendi bileşen ve operasyon satırları geldiyse motor onları kullanır, gelmediyse bu versiyonun ağacına ve rotasına gider',
               existing_comment='Üretim versiyonu; üretim siparişinin kendi bileşen ve operasyon satırları geldiyse motor onları kullanır, gelmediyse bu versiyonun ağacına ve rotasına gider',
               existing_nullable=True,
               schema='core')
    op.alter_column('WorkOrder', 'WorkOrderNo',
               existing_type=sa.Unicode(length=30),
               comment='İş emri no',
               existing_comment='Üretim siparişi no',
               existing_nullable=False,
               schema='core')
    _table_comment('core', 'ResourceGroup', "Kaynak grubu: planlama birimi (K-180). Rota ve iş emri operasyonu grubu gösterir; plan ve yük grup düzeyindedir. Tip, kritiklik, kapasite birimi ve fasoncu gruptadır. Gruptaki kaynak sayısı `ResourceGroupMember`'dan bilinir, ayrıca girilmez.")
    op.alter_column('PurchaseOrderLine', 'WorkOrderId',
               existing_type=sa.BIGINT(),
               comment='Fasonda bağlı iş emri',
               existing_comment='Fasonda bağlı üretim siparişi',
               existing_nullable=True,
               schema='core')
    _table_comment('core', 'ProductionConfirmation', 'Üretim gerçekleşmeleri: iş emri bazında stoğa girişler.')
    op.alter_column('ProductionConfirmation', 'WorkOrderId',
               existing_type=sa.BIGINT(),
               comment='İş emri',
               existing_comment='Üretim siparişi',
               existing_nullable=False,
               schema='core')
    if not context.is_offline_mode():
        sync(op.get_bind(), metadata)
