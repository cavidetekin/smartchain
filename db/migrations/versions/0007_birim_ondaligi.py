"""0007 · Birim ondalığı (K-88)

core.UnitOfMeasure'a Decimals eklenir: miktarlar ekranda birimin ondalığıyla gösterilir. ERP'den gelmez, Smartchain'de
tutulur. Mevcut birimlere önerilen değerler yazılır: ADET 0, KG 3, M 2, SAAT 2; diğerleri 2 (varsayılan).

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

SUGGESTED = {"ADET": 0, "KG": 3, "M": 2, "SAAT": 2}


def upgrade():
    op.add_column("UnitOfMeasure", sa.Column(
        "Decimals", mssql.TINYINT(), server_default=sa.text("2"), nullable=True,
        comment="Miktar ondalığı; ERP'den gelmez, Smartchain'de tutulur (K-88)"), schema="core")
    op.execute("UPDATE core.UnitOfMeasure SET Decimals = 2 WHERE Decimals IS NULL")
    for code, decimals in SUGGESTED.items():
        op.execute(f"UPDATE core.UnitOfMeasure SET Decimals = {decimals} WHERE Code = N'{code}'")


def downgrade():
    op.drop_column("UnitOfMeasure", "Decimals", schema="core", mssql_drop_default=True)
