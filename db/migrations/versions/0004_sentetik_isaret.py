"""0004 · Sentetik veri işareti: IsSynthetic (DataVersion, Location, ParameterSet; K-79)

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-27
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

COMMENT = "Sentetik veri (geliştirme ve demo); sentetik veri komutları yalnız bunlara dokunur (K-79)"
TABLES = [("DataVersion", "adm"), ("Location", "core"), ("ParameterSet", "param")]


def upgrade():
    for table, schema in TABLES:
        op.add_column(table, sa.Column("IsSynthetic", sa.Boolean(), nullable=True, server_default=sa.text("0"),
                                       comment=COMMENT), schema=schema)


def downgrade():
    for table, schema in reversed(TABLES):
        op.drop_column(table, "IsSynthetic", schema=schema, mssql_drop_default=True)
