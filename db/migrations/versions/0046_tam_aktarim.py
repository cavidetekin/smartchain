"""0046 · Tam aktarım (5.2, K-151, K-152, K-153): DataVersion.LocationId ve core.Resource.Quantity boş olabilir; DataVersionEntity tablo başına sayılar ve not;
iş tipi "Yükleme" → "Aktarım" (var olan iş satırları da). Veri sözlüğü (FieldDefinition) docs'tan eşitlenir.

Geri alışta boş LocationId en küçük lokasyonla, boş paralel adet 1 ile doldurulur; iş tipi "Yükleme"ye döner.

Revision ID: 0046
Revises: 0045
Create Date: 2026-11-10 11:04:02.066404
"""
from alembic import context, op
import sqlalchemy as sa

from dictionary import sync
from models import metadata


revision = '0046'
down_revision = '0045'
branch_labels = None
depends_on = None

COUNTS = (("NewCount", "Yeni kayıt sayısı (K-151)"), ("ChangedCount", "Güncellenen kayıt sayısı"), ("ClosedCount", "Silinen (kapatılan) kayıt sayısı"),
          ("NotTransferredCount", "Aktarılmayan satır sayısı (Hatalı, zorunlu ilişkisi çevrilemeyen)"))
NOTE = "Tek satır not: eşik aşıldı, veri gelmedi, ana verisi aktarılmadı (K-151)"
JOB_NEW = "Gece senaryosu | Çalışma | Aktarım | Termin sorgusu | Dışa aktarım | Excel ön kontrol | Veri çekme | Validasyon …"
JOB_OLD = "Gece senaryosu | Çalışma | Yükleme | Termin sorgusu | Dışa aktarım | Excel ön kontrol | Veri çekme | Validasyon …"
QTY_NEW = "Paralel kaynak adedi; Smartchain ekranında girilir, aktarımda önceki versiyondan gelir"
QTY_OLD = "Paralel kaynak adedi"


def _table_comment(schema, table, text):
    text = text.replace("'", "''")
    op.execute(f"EXEC sp_updateextendedproperty 'MS_Description', N'{text}', 'schema', '{schema}', 'table', '{table}'")


def upgrade():
    op.alter_column('DataVersion', 'LocationId', existing_type=sa.INTEGER(), nullable=True,
                    comment='Lokasyon; tam aktarım bütün lokasyonları kapsar, boş (K-153)', existing_comment='Lokasyon', schema='adm')
    for name, comment in COUNTS:
        op.add_column('DataVersionEntity', sa.Column(name, sa.Integer(), nullable=True, comment=comment), schema='adm')
    op.add_column('DataVersionEntity', sa.Column('Note', sa.Unicode(length=400), nullable=True, comment=NOTE), schema='adm')
    op.alter_column('Job', 'JobType', existing_type=sa.Unicode(length=20), comment=JOB_NEW, existing_comment=JOB_OLD, existing_nullable=False, schema='adm')
    _table_comment('adm', 'Job', 'İş kuyruğu (SQL Server tablosu): gece senaryoları, çalışma hesapları, aktarımlar.')
    op.execute("UPDATE adm.Job SET JobType = N'Aktarım' WHERE JobType = N'Yükleme'")
    op.alter_column('Resource', 'Quantity', existing_type=sa.INTEGER(), nullable=True, comment=QTY_NEW, existing_comment=QTY_OLD, schema='core')
    if not context.is_offline_mode():
        sync(op.get_bind(), metadata)


def downgrade():
    op.execute("UPDATE core.Resource SET Quantity = 1 WHERE Quantity IS NULL")
    op.alter_column('Resource', 'Quantity', existing_type=sa.INTEGER(), nullable=False, comment=QTY_OLD, existing_comment=QTY_NEW, schema='core')
    op.execute("UPDATE adm.Job SET JobType = N'Yükleme' WHERE JobType = N'Aktarım'")
    _table_comment('adm', 'Job', 'İş kuyruğu (SQL Server tablosu): gece senaryoları, çalışma hesapları, yüklemeler.')
    op.alter_column('Job', 'JobType', existing_type=sa.Unicode(length=20), comment=JOB_OLD, existing_comment=JOB_NEW, existing_nullable=False, schema='adm')
    op.drop_column('DataVersionEntity', 'Note', schema='adm')
    for name, _ in reversed(COUNTS):
        op.drop_column('DataVersionEntity', name, schema='adm')
    op.execute("UPDATE adm.DataVersion SET LocationId = (SELECT MIN(Id) FROM core.Location) WHERE LocationId IS NULL")
    op.alter_column('DataVersion', 'LocationId', existing_type=sa.INTEGER(), nullable=False,
                    comment='Lokasyon', existing_comment='Lokasyon; tam aktarım bütün lokasyonları kapsar, boş (K-153)', schema='adm')
