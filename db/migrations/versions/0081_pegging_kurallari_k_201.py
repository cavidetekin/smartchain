"""0081 · Pegging kuralları (K-201): param.PeggingCriterion

Yeni tablo: senaryonun pegging sıralama ölçütleri (İhtiyaç sırası ve Arz sırası listeleri; ölçüt ve yön, sırasıyla). Parametreler › Pegging
sekmesinde düzenlenir; hesap bu ayarları Aşama 10'da okur.

Geçiş veri yazmaz: senaryoda satır yoksa başlangıç sırası geçerlidir (`app/params/pegging.py`). "Özel alokasyon" ve "Full pegging yöntemi"
`param.PlanningSetting`'dedir; satırı olmayan anahtar kataloğun başlangıç değeriyle okunur, geçiş gerekmez. Veri kaybı yok. Açıklamalar geçişte
sabittir (K-197). Geri alış tabloyu ve sözlük satırlarını siler.

Revision ID: 0081
Revises: 0080
Create Date: 2026-11-25
"""
from alembic import context, op
import sqlalchemy as sa

from dictionary import sync
from models import metadata

revision = '0081'
down_revision = '0080'
branch_labels = None
depends_on = None

TABLE = 'PeggingCriterion'
UNIQUE = 'UX_PeggingCriterion_ScenarioDefinitionId_Side_Criterion'


def upgrade():
    op.create_table(TABLE,
    sa.Column('ScenarioDefinitionId', sa.Integer(), autoincrement=False, nullable=False, comment='Senaryo'),
    sa.Column('Side', sa.Unicode(length=10), autoincrement=False, nullable=False, comment='İhtiyaç | Arz'),
    sa.Column('Seq', sa.Integer(), autoincrement=False, nullable=False, comment='Sıra'),
    sa.Column('Criterion', sa.Unicode(length=40), nullable=False, comment='Ölçütün adı (Dönem, Kesin sipariş, Stok, Arz tarihi…)'),
    sa.Column('Direction', sa.Unicode(length=20), nullable=True, comment='Artan | Azalan | İhtiyaca en yakın'),
    sa.ForeignKeyConstraint(['ScenarioDefinitionId'], ['param.ScenarioDefinition.Id'], name=op.f('FK_PeggingCriterion_ScenarioDefinitionId')),
    sa.PrimaryKeyConstraint('ScenarioDefinitionId', 'Side', 'Seq', name=op.f('PK_PeggingCriterion')),
    schema='param',
    comment='Pegging sıralama ölçütleri (K-201): senaryonun İhtiyaç sırası ve Arz sırası listeleri; her satır bir ölçüttür, sırasıyla. Ölçütler yukarıdan aşağı uygulanır. Senaryoda satır yoksa başlangıç sırası geçerlidir (`app/params/pegging.py`); ilk kayıtta listenin tamamı yazılır. Bir listede her ölçüt bir kez bulunur. Yön yalnız yönlü ölçütte doludur ("İhtiyaca en yakın" yalnız arzın Dönem ölçütünde).',
    info={'field_class': 'Parametre'}
    )
    op.create_index(UNIQUE, TABLE, ['ScenarioDefinitionId', 'Side', 'Criterion'], unique=True, schema='param')
    if not context.is_offline_mode():  # bağlantısız SQL betiğinde satırlar yazılmaz; ilk bağlantılı geçişte kurulur
        sync(op.get_bind(), metadata)


def downgrade():
    for table in ('FieldDefinition', 'FieldChange'):
        op.execute(f"DELETE FROM adm.[{table}] WHERE TableName = N'{TABLE}'")
    op.drop_index(UNIQUE, table_name=TABLE, schema='param')
    op.drop_table(TABLE, schema='param')
    if not context.is_offline_mode():
        sync(op.get_bind(), metadata)
