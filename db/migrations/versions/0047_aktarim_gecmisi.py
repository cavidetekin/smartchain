"""0047 · Veri aktarım geçmişi ve ham veri temizliği (5.4, K-156): DataVersion.JobId (var olan aktarımlar iş sonucundan doldurulur);
ImportBatch.RawDeletedAt; iş tipi "Temizlik". Veri sözlüğü (FieldDefinition) docs'tan eşitlenir.

Revision ID: 0047
Revises: 0046
Create Date: 2026-11-10 15:40:00
"""
from alembic import context, op
import sqlalchemy as sa

from dictionary import sync
from models import metadata


revision = '0047'
down_revision = '0046'
branch_labels = None
depends_on = None

JOB_ID = "Aktarım işi; versiyonu açan iş (`Job.Id`), veri aktarım geçmişi ve raporu buradan bağlanır"
RAW_DELETED = "Ham verinin silindiği zaman; temizlik partinin güncel olmayan satırlarını, bulgularını ve dosyasını siler (UTC)"
JOB_NEW = "Gece senaryosu | Çalışma | Aktarım | Termin sorgusu | Dışa aktarım | Excel ön kontrol | Veri çekme | Validasyon | Temizlik …"
JOB_OLD = "Gece senaryosu | Çalışma | Aktarım | Termin sorgusu | Dışa aktarım | Excel ön kontrol | Veri çekme | Validasyon …"
BATCH_NEW = ('Ham veri partisi: her yükleme parti numarası, zaman ve kaynakla. Ham veri saklama süresi kadar saklanır (`RawDataRetentionDays`; boşsa temizlik '
             'çalışmaz, K-156); parti kaydı ve sayıları silinmez. LoadType Değişen: arayüzde "Ekle / güncelle" (K-129).')
BATCH_OLD = 'Ham veri partisi: her yükleme parti numarası, zaman ve kaynakla. Ham veri bir hafta saklanır. LoadType Değişen: arayüzde "Ekle / güncelle" (K-129).'


def _table_comment(schema, table, text):
    text = text.replace("'", "''")
    op.execute(f"EXEC sp_updateextendedproperty 'MS_Description', N'{text}', 'schema', '{schema}', 'table', '{table}'")


def upgrade():
    op.add_column('DataVersion', sa.Column('JobId', sa.BigInteger(), nullable=True, comment=JOB_ID), schema='adm')
    op.execute("UPDATE dv SET JobId = j.Id FROM adm.DataVersion dv JOIN adm.Job j "
               "ON j.JobType = N'Aktarım' AND ISJSON(j.Result) = 1 AND TRY_CAST(JSON_VALUE(j.Result, '$.data_version') AS bigint) = dv.Id")
    op.add_column('ImportBatch', sa.Column('RawDeletedAt', sa.dialects.mssql.DATETIME2(), nullable=True, comment=RAW_DELETED), schema='adm')
    _table_comment('adm', 'ImportBatch', BATCH_NEW)
    op.alter_column('Job', 'JobType', existing_type=sa.Unicode(length=20), comment=JOB_NEW, existing_comment=JOB_OLD, existing_nullable=False, schema='adm')
    if not context.is_offline_mode():
        sync(op.get_bind(), metadata)


def downgrade():
    op.execute("DELETE FROM adm.Job WHERE JobType = N'Temizlik'")
    op.alter_column('Job', 'JobType', existing_type=sa.Unicode(length=20), comment=JOB_OLD, existing_comment=JOB_NEW, existing_nullable=False, schema='adm')
    _table_comment('adm', 'ImportBatch', BATCH_OLD)
    op.drop_column('ImportBatch', 'RawDeletedAt', schema='adm')
    op.drop_column('DataVersion', 'JobId', schema='adm')
