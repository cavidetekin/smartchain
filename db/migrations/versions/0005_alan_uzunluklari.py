"""0005 · Değer listesine sığmayan alanlar uzatıldı (K-80)

MaterialSupplier.LeadTimeBasis 10 → 15 ('Takvim günü'), PurchaseOrderLine.OrderType 15 → 20 ('Satın alma talebi'),
ana ve entegrasyon tablosunda; PriorityRule.Direction 4 → 10 ('Artan', 'Azalan'). Yalnız uzatma; veri kaybı yok.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-27
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

# (tablo, şema, alan, eski uzunluk, yeni uzunluk, boş olabilir mi)
CHANGES = [
    ("MaterialSupplier", "core", "LeadTimeBasis", 10, 15, True),
    ("MaterialSupplier", "stg", "LeadTimeBasis", 10, 15, True),
    ("PurchaseOrderLine", "core", "OrderType", 15, 20, False),
    ("PurchaseOrderLine", "stg", "OrderType", 15, 20, True),
    ("PriorityRule", "param", "Direction", 4, 10, True),
]


def upgrade():
    for table, schema, column, old, new, nullable in CHANGES:
        op.alter_column(table, column, schema=schema, type_=sa.Unicode(new), existing_type=sa.Unicode(old),
                        existing_nullable=nullable)


def downgrade():
    # Geri adım: uzun değer varsa kısaltma veri kaybettirir; SQL Server bu durumda hata verir, veri korunur.
    for table, schema, column, old, new, nullable in reversed(CHANGES):
        op.alter_column(table, column, schema=schema, type_=sa.Unicode(old), existing_type=sa.Unicode(new),
                        existing_nullable=nullable)
