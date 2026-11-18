"""0064 · Eşleşme tablosunun Türkçe adı "Kaynak grup eşleşmesi" (K-181)

Yalnız tablo açıklaması değişir (stg, prc, core `ResourceGroupMember`); yapı ve veri değişmez. Geri alış açıklamayı eski hâline döndürür.

Revision ID: 0064
Revises: 0063
Create Date: 2026-11-18
"""
from alembic import op

revision = '0064'
down_revision = '0063'
branch_labels = None
depends_on = None

REST = (': kaynağın gruba üyeliği. Bir kaynak birden fazla gruba üye olabilir (birden fazla yetkinliği olan işçi). Geçerlilik tarihi yoktur: '
        'yüklü eşleşme bugünden itibaren geçerlidir. Gruptaki kaynak sayısı bu tablodan bilinir (K-180).')
SCHEMAS = ('stg', 'prc', 'core')


def _table_comment(schema, table, text):
    """MS SQL'de var olan tablo açıklaması güncellenir."""
    escaped = text.replace("'", "''")
    op.execute(f"EXEC sp_updateextendedproperty 'MS_Description', N'{escaped}', 'schema', '{schema}', 'table', '{table}'")


def upgrade():
    for schema in SCHEMAS:
        _table_comment(schema, 'ResourceGroupMember', 'Kaynak grup eşleşmesi' + REST)


def downgrade():
    for schema in SCHEMAS:
        _table_comment(schema, 'ResourceGroupMember', 'Grup eşleşmesi' + REST)
