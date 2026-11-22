"""0071 · Açıklama güncellemeleri: tedarikçi limitinde Sebep iki türde (K-191 demo), alokasyon Faz 1 dışı (K-192)

Yalnız açıklamalar (MS_Description) değişir; kolon, veri ve kısıt değişmez. `param.SupplierLimit.Reason` artık üst limitte de kullanılır;
`param.AllocationRule` Faz 1 dışıdır (tablo durur, hiçbir ekran ve motor okumaz).

Revision ID: 0071
Revises: 0070
Create Date: 2026-11-23
"""
from alembic import context, op
import sqlalchemy as sa

from dictionary import sync
from models import metadata

revision = '0071'
down_revision = '0070'
branch_labels = None
depends_on = None

OLD_REASON = 'Kapanışın sebebi (serbest metin); yalnız kapanışta'
OLD_ALLOCATION = 'Kapasite alokasyonu: talep sınıfına kaynak grubu ve dönem bazında pay (K-180).'


def _table_comment(table: str, text: str) -> None:
    """SQL Server'da var olan tablo açıklaması (MS_Description) create_table_comment ile eklenemez; güncellenir."""
    op.execute(sa.text(
        "EXEC sp_updateextendedproperty @name = N'MS_Description', @value = :v, @level0type = N'SCHEMA', "
        "@level0name = N'param', @level1type = N'TABLE', @level1name = :t").bindparams(v=text, t=table))


def upgrade():
    reason = metadata.tables['param.SupplierLimit'].c.Reason
    op.alter_column('SupplierLimit', 'Reason', existing_type=sa.Unicode(length=255), existing_nullable=True, comment=reason.comment, existing_comment=OLD_REASON,
                    schema='param')
    _table_comment('AllocationRule', metadata.tables['param.AllocationRule'].comment)
    if not context.is_offline_mode():  # bağlantısız SQL betiğinde satırlar yazılmaz; ilk bağlantılı geçişte kurulur
        sync(op.get_bind(), metadata)


def downgrade():
    reason = metadata.tables['param.SupplierLimit'].c.Reason
    op.alter_column('SupplierLimit', 'Reason', existing_type=sa.Unicode(length=255), existing_nullable=True, comment=OLD_REASON, existing_comment=reason.comment,
                    schema='param')
    _table_comment('AllocationRule', OLD_ALLOCATION)
    if not context.is_offline_mode():
        sync(op.get_bind(), metadata)
