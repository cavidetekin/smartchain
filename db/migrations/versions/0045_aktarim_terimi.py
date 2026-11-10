"""0045 · Terim (K-152): DataVersion ve DataVersionEntity tablo açıklamaları "aktarım" terimiyle (docs/02 → db/generate.py)

Yalnız tablo yorumu (MS_Description) değişir; şema ve veri aynı kalır.

Revision ID: 0045
Revises: 0044
Create Date: 2026-11-10 10:00:00
"""
from alembic import op


revision = '0045'
down_revision = '0044'
branch_labels = None
depends_on = None

NEW = {
    "DataVersion": "Aktarım ile oluşan dondurulmuş veri versiyonu; tam ya da kısmi (K-152).",
    "DataVersionEntity": "Aktarımda hangi tabloların aktarıldığı (kısmi aktarımda seçilen grupların tabloları).",
}
OLD = {
    "DataVersion": "Yükleme ile oluşan dondurulmuş veri versiyonu; tam ya da kısmi.",
    "DataVersionEntity": "Kısmi yüklemede hangi varlıkların yüklendiği.",
}


def _table_comment(table: str, text: str) -> None:
    text = text.replace("'", "''")
    op.execute(f"EXEC sp_updateextendedproperty 'MS_Description', N'{text}', 'schema', 'adm', 'table', '{table}'")


def upgrade() -> None:
    for table, text in NEW.items():
        _table_comment(table, text)


def downgrade() -> None:
    for table, text in OLD.items():
        _table_comment(table, text)
