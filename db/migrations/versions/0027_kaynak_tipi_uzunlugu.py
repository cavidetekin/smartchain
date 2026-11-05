"""0027 · Resource.ResourceType nvarchar(50) (K-117); EmployeeAbsence.EndDate açıklaması "Bitiş günü dahil"

Geri alışta 20 karakterden uzun ResourceType varsa geçiş durur.

Revision ID: 0027
Revises: 0026
Create Date: 2026-11-04
"""
from alembic import context, op
import sqlalchemy as sa

from dictionary import sync
from models import metadata


revision = '0027'
down_revision = '0026'
branch_labels = None
depends_on = None

SCHEMAS = ('core', 'stg')
RAW = "ERP'den gelen ham değer; tip bayraklarla ifade edilir"
OLD_END, NEW_END = 'Bitiş günü (dahil)', 'Bitiş günü dahil'


def _end_comment(new, old):
    for schema, nullable in (('core', False), ('stg', True)):
        op.alter_column('EmployeeAbsence', 'EndDate', existing_type=sa.DATE(), comment=new, existing_comment=old, existing_nullable=nullable, schema=schema)


def upgrade():
    for schema in SCHEMAS:
        op.alter_column('Resource', 'ResourceType', existing_type=sa.Unicode(length=20), type_=sa.Unicode(length=50), existing_comment=RAW, existing_nullable=True, schema=schema)
    _end_comment(NEW_END, OLD_END)
    if not context.is_offline_mode():  # bağlantısız SQL betiğinde satırlar yazılmaz; ilk bağlantılı geçişte kurulur
        sync(op.get_bind(), metadata)


def downgrade():
    _end_comment(OLD_END, NEW_END)
    op.execute(f"UPDATE adm.FieldDefinition SET Description = N'{OLD_END}' WHERE TableName = N'EmployeeAbsence' AND FieldName = N'EndDate'")
    for schema in SCHEMAS:
        op.alter_column('Resource', 'ResourceType', existing_type=sa.Unicode(length=50), type_=sa.Unicode(length=20), existing_comment=RAW, existing_nullable=True, schema=schema)
