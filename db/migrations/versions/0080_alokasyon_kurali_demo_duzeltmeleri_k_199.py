"""0080 · Alokasyon kuralı: demo düzeltmeleri (K-199)

- Sebep değerleri: "Kendi arzı var" → "Kendi arzı", "Alt seviye yüzünden" → "Alt seviye arzı" (tablodaki satırlar, Geçmiş'teki eski ve yeni değerler,
  kolon açıklaması).
- `SourceMaterialId` (iç bağ) düşer: kaynak birden çok malzeme olabildiği için tek malzemeye bağlı ilişkili alan yanıltıcıydı; kaynak malzeme
  yalnız metin olarak kalır (`SourceMaterials`).
- Sipariş no'da dik çizgi kuralları (`SO/STK/WO/PO.ORDER_NO_PIPE`) bulgularıyla silinir: sipariş no nasıl gelirse öyle kabul edilir.

Veri kaybı: yalnız iç bağ kolonu (yeniden hesapta üretilen değer). Değerler ve adlar geçişte sabittir (K-197). Geri alış kolonu boş olarak geri
kurar ve değerleri eski hâline çevirir; silinen kurallar geri gelmez.

Revision ID: 0080
Revises: 0079
Create Date: 2026-11-25
"""
from alembic import context, op
import sqlalchemy as sa

from dictionary import sync
from models import metadata

revision = '0080'
down_revision = '0079'
branch_labels = None
depends_on = None

TABLE = 'MaterialAllocationRule'
REASONS = (('Kendi arzı var', 'Kendi arzı'), ('Alt seviye yüzünden', 'Alt seviye arzı'))
PIPE_RULES = ('SO.ORDER_NO_PIPE', 'STK.ORDER_NO_PIPE', 'WO.ORDER_NO_PIPE', 'PO.ORDER_NO_PIPE')


def _values(forward):
    """Sebep değerleri tabloda ve Geçmiş'te çevrilir."""
    for old, new in REASONS:
        a, b = (old, new) if forward else (new, old)
        op.execute(f"UPDATE core.[{TABLE}] SET Reason = N'{b}' WHERE Reason = N'{a}'")
        for column in ('OldValue', 'NewValue'):
            op.execute(f"UPDATE adm.FieldChange SET {column} = N'{b}' WHERE TableName = N'{TABLE}' AND FieldName = N'Reason' AND {column} = N'{a}'")


def _rules():
    """Dik çizgi kuralları ve bulguları (kural eşitlemesi de siler; geçişten sonra uygulama açılmadan da temiz olsun)."""
    codes = ', '.join(f"N'{c}'" for c in PIPE_RULES)
    ids = f"SELECT Id FROM adm.ValidationRule WHERE Code IN ({codes})"
    for table in ('ValidationFinding', 'ValidationRuleCondition', 'DataQualityWarning'):
        op.execute(f"DELETE FROM adm.[{table}] WHERE ValidationRuleId IN ({ids})")
    op.execute(f"DELETE FROM adm.ValidationRule WHERE Code IN ({codes})")


def upgrade():
    _values(True)
    _rules()
    op.alter_column('MaterialAllocationRule', 'Reason',
               existing_type=sa.Unicode(length=20),
               comment='Kendi arzı | Alt seviye arzı',
               existing_comment='Kendi arzı var | Alt seviye yüzünden',
               existing_nullable=False,
               schema='core')
    op.alter_column('MaterialAllocationRule', 'SourceMaterials',
               existing_type=sa.Unicode(length=70),
               comment='Sebebi alt seviye arzı olan satırda ayrılmış arzın durduğu alt malzeme; birden çoksa koda göre ilki ve kalanların sayısı. Metindir: kaynak birden çok malzeme olabildiği için ilişkili alanı yoktur',
               existing_comment='Sebebi alt seviye olan satırda ayrılmış arzın durduğu alt malzeme; birden çoksa koda göre ilki ve kalanların sayısı',
               existing_nullable=True,
               schema='core')
    op.drop_index(op.f('IX_MaterialAllocationRule_SourceMaterialId'), table_name='MaterialAllocationRule', schema='core')
    op.drop_column('MaterialAllocationRule', 'SourceMaterialId', schema='core')
    if not context.is_offline_mode():  # bağlantısız SQL betiğinde satırlar yazılmaz; ilk bağlantılı geçişte kurulur
        sync(op.get_bind(), metadata)


def downgrade():
    _values(False)
    op.add_column('MaterialAllocationRule', sa.Column('SourceMaterialId', sa.BIGINT(), autoincrement=False, nullable=True, comment='Kaynak malzeme (iç bağ): ayrılmış arzın durduğu alt malzemelerden koda göre ilki; kolon olarak gösterilmez'), schema='core')
    op.create_index(op.f('IX_MaterialAllocationRule_SourceMaterialId'), 'MaterialAllocationRule', ['SourceMaterialId'], unique=False, schema='core')
    op.alter_column('MaterialAllocationRule', 'SourceMaterials',
               existing_type=sa.Unicode(length=70),
               comment='Sebebi alt seviye olan satırda ayrılmış arzın durduğu alt malzeme; birden çoksa koda göre ilki ve kalanların sayısı',
               existing_comment='Sebebi alt seviye arzı olan satırda ayrılmış arzın durduğu alt malzeme; birden çoksa koda göre ilki ve kalanların sayısı. Metindir: kaynak birden çok malzeme olabildiği için ilişkili alanı yoktur',
               existing_nullable=True,
               schema='core')
    op.alter_column('MaterialAllocationRule', 'Reason',
               existing_type=sa.Unicode(length=20),
               comment='Kendi arzı var | Alt seviye yüzünden',
               existing_comment='Kendi arzı | Alt seviye arzı',
               existing_nullable=False,
               schema='core')
    if not context.is_offline_mode():
        sync(op.get_bind(), metadata)
