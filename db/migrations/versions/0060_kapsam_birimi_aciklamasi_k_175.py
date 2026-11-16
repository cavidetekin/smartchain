"""0060 · Kapsam biriminde Çeyrek ve Yıl (K-175, 7.1 demo 2 bulgusu): yalnız açıklama

`param.TimeBucketDefinition.SpanUnit` değerleri Gün | Hafta | Ay | Çeyrek | Yıl oldu; kolon tipi aynı (nvarchar(10)). Kolonun ve tablonun
açıklaması ve veri sözlüğü satırı modelden (docs/02) güncellenir; veri değişmez.

Revision ID: 0060
Revises: 0059
Create Date: 2026-11-16
"""
from alembic import context, op

from dictionary import sync
from models import metadata

revision = '0060'
down_revision = '0059'
branch_labels = None
depends_on = None

OLD_COLUMN = 'Gün | Hafta | Ay'
OLD_TABLE = ('Zaman yapısı: senaryonun ufuk ve dönem dizisi. Kullanıcı tarih girmez; her satır bir parçadır: dönem tipi (dönemlerin büyüklüğü) ve kapsam '
             '(parçanın ne kadar sürdüğü). Başlangıç ve bitiş plan başlangıcına göre hesaplanır (fonksiyon 23, K-175). Raporlama ekseni ayrı diziyse '
             '`Axis` = Rapor satırları. Dönem tipinde Çeyrek ve Yıl yalnız raporlama ekseninde; kapsam birimi dönem tipinden küçük olamaz.')


def _set(table_comment: str, column_comment: str) -> None:
    """MS SQL'de var olan açıklama güncellenir (create_table_comment eklemeye çalışır)."""
    t, c = table_comment.replace("'", "''"), column_comment.replace("'", "''")
    op.execute(f"EXEC sp_updateextendedproperty 'MS_Description', N'{t}', 'schema', 'param', 'table', 'TimeBucketDefinition'")
    op.execute(f"EXEC sp_updateextendedproperty 'MS_Description', N'{c}', 'schema', 'param', 'table', 'TimeBucketDefinition', 'column', 'SpanUnit'")


def upgrade():
    table = metadata.tables['param.TimeBucketDefinition']
    _set(table.comment, table.c.SpanUnit.comment)
    if not context.is_offline_mode():  # veri sözlüğündeki açıklama ve değerler de modelden
        sync(op.get_bind(), metadata)


def downgrade():
    _set(OLD_TABLE, OLD_COLUMN)
