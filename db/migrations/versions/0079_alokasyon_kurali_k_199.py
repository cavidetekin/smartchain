"""0079 · Alokasyon kuralı (K-199): core.MaterialAllocationRule

Yeni tablo: bir malzemenin hangi sahip (sipariş, proje, müşteri) adına ayrı izleneceği. Sistem üretir (her aktarımın sonunda ve sentetik yüklemede,
`app/allocation/rules.py`); ERP sözleşmesinde yoktur. Versiyonlu; tekillik lokasyon + malzeme + seviye + anahtar (güncel kayıtta).

Geçiş hesap yapmaz: tablo boş açılır, ilk aktarımda ya da sentetik yüklemede dolar. Veri kaybı yok. Açıklamalar geçişte sabittir (K-197).
Geri alış tabloyu, sözlük ve geçmiş satırlarını siler.

Revision ID: 0079
Revises: 0078
Create Date: 2026-11-25
"""
from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql

from dictionary import sync
from models import metadata

revision = '0079'
down_revision = '0078'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('MaterialAllocationRule',
    sa.Column('Id', sa.BigInteger(), autoincrement=False, nullable=False, comment='Kayıt kimliği'),
    sa.Column('LocationId', sa.Integer(), nullable=False, comment='Lokasyon'),
    sa.Column('MaterialId', sa.BigInteger(), nullable=False, comment='Malzeme'),
    sa.Column('AllocationLevel', sa.Unicode(length=10), nullable=False, comment='Sipariş | Proje | Müşteri'),
    sa.Column('AllocationKey', sa.Unicode(length=60), nullable=False, comment='Malzemenin adına ayrı izlendiği sahibin anahtarı; arz satırlarındaki anahtarla aynı biçimde'),
    sa.Column('Reason', sa.Unicode(length=20), nullable=False, comment='Kendi arzı var | Alt seviye yüzünden'),
    sa.Column('SourceMaterialId', sa.BigInteger(), nullable=True, comment='Kaynak malzeme (iç bağ): ayrılmış arzın durduğu alt malzemelerden koda göre ilki; kolon olarak gösterilmez'),
    sa.Column('SourceMaterials', sa.Unicode(length=70), nullable=True, comment='Sebebi alt seviye olan satırda ayrılmış arzın durduğu alt malzeme; birden çoksa koda göre ilki ve kalanların sayısı'),
    sa.Column('VersionFrom', sa.Integer(), autoincrement=False, nullable=False, comment='Kaydın geçerli olduğu ilk veri versiyonu'),
    sa.Column('VersionTo', sa.Integer(), nullable=True, comment='Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş'),
    sa.Column('ImportBatchId', sa.BigInteger(), nullable=True, comment='Kaydı getiren yükleme partisi'),
    sa.Column('BusinessKey', sa.Unicode(length=200), nullable=False, comment='İş anahtarı; kod ya da kodların birleşimi'),
    sa.Column('UpdatedAt', mssql.DATETIME2(), nullable=False, comment='Son değişiklik zamanı'),
    sa.ForeignKeyConstraint(['ImportBatchId'], ['adm.ImportBatch.Id'], name=op.f('FK_MaterialAllocationRule_ImportBatchId')),
    sa.ForeignKeyConstraint(['LocationId'], ['core.Location.Id'], name=op.f('FK_MaterialAllocationRule_LocationId')),
    sa.PrimaryKeyConstraint('Id', 'VersionFrom', name=op.f('PK_MaterialAllocationRule')),
    schema='core',
    comment='Alokasyon kuralı: bir malzemenin hangi sahip (sipariş, proje, müşteri) adına ayrı izleneceği. Sistem üretir: her aktarımın sonunda ve sentetik yüklemede taleplerden ürün ağacında aşağı yürünerek hesaplanır (K-199). ERP sözleşmesinde yoktur, elle değiştirilemez, veri kuralı yazamaz, senaryoya bağlı değildir. Model ve pegging ağaçta yeniden yürümez, bu tabloyu okur.',
    info={'field_class': 'Ana veri'}
    )
    op.create_index(op.f('IX_MaterialAllocationRule_MaterialId'), 'MaterialAllocationRule', ['MaterialId'], unique=False, schema='core')
    op.create_index(op.f('IX_MaterialAllocationRule_SourceMaterialId'), 'MaterialAllocationRule', ['SourceMaterialId'], unique=False, schema='core')
    op.create_index('UX_MaterialAllocationRule_LocationId_MaterialId_AllocationLevel_AllocationKey', 'MaterialAllocationRule', ['LocationId', 'MaterialId', 'AllocationLevel', 'AllocationKey'], unique=True, schema='core', mssql_where=sa.text('VersionTo IS NULL'))
    if not context.is_offline_mode():  # bağlantısız SQL betiğinde satırlar yazılmaz; ilk bağlantılı geçişte kurulur
        sync(op.get_bind(), metadata)


def downgrade():
    for table in ('FieldDefinition', 'FieldChange'):
        op.execute(f"DELETE FROM adm.[{table}] WHERE TableName = N'MaterialAllocationRule'")
    op.drop_index('UX_MaterialAllocationRule_LocationId_MaterialId_AllocationLevel_AllocationKey', table_name='MaterialAllocationRule', schema='core', mssql_where=sa.text('VersionTo IS NULL'))
    op.drop_index(op.f('IX_MaterialAllocationRule_SourceMaterialId'), table_name='MaterialAllocationRule', schema='core')
    op.drop_index(op.f('IX_MaterialAllocationRule_MaterialId'), table_name='MaterialAllocationRule', schema='core')
    op.drop_table('MaterialAllocationRule', schema='core')
