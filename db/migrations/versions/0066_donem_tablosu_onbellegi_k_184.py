"""0066 · Dönem tablosu önbelleği (K-184)

Yeni şema `cache` ve iki tablo: `cache.ResourceCapacityDay` (kaynak × gün kapasite ara sonucu) ve `cache.PeriodCacheState` (önbelleğin durumu).
Önbellek veri değildir: girişlerden hesaplanır, silinirse yeniden üretilir (`python -m app.periods rebuild`). Geçiş yalnız yapıyı kurar; satır
yazmaz (önbellek ilk kullanımda kurulur). Geri alış tabloları ve şemayı kaldırır; kaybolan bir veri olmaz.

Revision ID: 0066
Revises: 0065
Create Date: 2026-11-19
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql

revision = '0066'
down_revision = '0065'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA [cache]")
    op.create_table('PeriodCacheState',
    sa.Column('CacheName', sa.Unicode(length=60), autoincrement=False, nullable=False, comment='Önbelleğin adı (ör. resource-capacity-day)'),
    sa.Column('ScenarioDefinitionId', sa.Integer(), autoincrement=False, nullable=False, comment='Senaryo'),
    sa.Column('CodeVersion', sa.Integer(), nullable=False, comment='Hesap kodunun sürümü'),
    sa.Column('DataVersionId', sa.Integer(), nullable=True, comment='Kurulduğu veri versiyonu'),
    sa.Column('DateFrom', sa.DATE(), nullable=False, comment='Tutulan ilk gün'),
    sa.Column('DateTo', sa.DATE(), nullable=False, comment='Tutulan son gün'),
    sa.Column('BuiltAt', mssql.DATETIME2(), nullable=False, comment='Son tam kurulum zamanı (UTC)'),
    sa.PrimaryKeyConstraint('CacheName', 'ScenarioDefinitionId', name=op.f('PK_PeriodCacheState')),
    schema='cache',
    comment='Önbelleğin durumu (K-184): önbellek ve senaryo başına tek satır. Satır yoksa önbellek kurulmamıştır; hesap kodunun sürümü ya da veri versiyonu farklıysa önbellek düşürülüp yeniden kurulur; gün aralığı ufkun gerisinde kaldıysa geçmiş günler temizlenir, ufuk ilerlediyse yalnız eksik günler hesaplanır.'
    )
    op.create_table('ResourceCapacityDay',
    sa.Column('ScenarioDefinitionId', sa.Integer(), autoincrement=False, nullable=False, comment='Senaryo'),
    sa.Column('ResourceId', sa.BigInteger(), autoincrement=False, nullable=False, comment='Kaynak'),
    sa.Column('Date', sa.DATE(), autoincrement=False, nullable=False, comment='Gün'),
    sa.Column('WorkingDay', sa.Numeric(precision=5, scale=2), nullable=False, comment='Çalışma günü (tam 1, yarım 0,5, çalışılmıyor 0)'),
    sa.Column('Capacity', sa.Numeric(precision=18, scale=4), nullable=False, comment='Günün toplam kapasitesi'),
    sa.Column('AvailableCapacity', sa.Numeric(precision=18, scale=4), nullable=False, comment='Kullanılabilir kapasite (toplam × verim)'),
    sa.PrimaryKeyConstraint('ScenarioDefinitionId', 'ResourceId', 'Date', name=op.f('PK_ResourceCapacityDay')),
    schema='cache',
    comment='Kaynak × gün kapasite ara sonucu (K-184): dönem tablosu "Kaynak grubu × dönem" bundan toplanır. Yalnız planlama ufkundaki günler; Baz\'ı izleyen senaryoda yalnız kendi girişi olan kaynak ve günler (gerisi Baz\'ın satırlarından okunur). 7.8\'de deneme hesabının alanlarını taşır; 7.9\'da gerçek kapasite alanlarıyla yeniden düzenlenir. Kümelenmiş anahtar senaryo, kaynak, gün: tek kaynağın yenilenmesi ve senaryonun gün aralığı okuması aynı sıradan.'
    )


def downgrade():
    op.drop_table('ResourceCapacityDay', schema='cache')
    op.drop_table('PeriodCacheState', schema='cache')
    op.execute("DROP SCHEMA [cache]")
