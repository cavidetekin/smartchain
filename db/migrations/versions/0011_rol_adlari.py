"""0011 · Rol adları (K-99)

AppUser.Role değeri "Sistem sahibi" → "System owner"; Role, AuditLog, FieldDefinition ve SystemSetting açıklamaları yeni
rol adlarıyla. Geri almada tersi.

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql


revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def _table_comment(table: str, text: str) -> None:
    """SQL Server'da var olan tablo açıklaması (MS_Description) create_table_comment ile eklenemez; güncellenir."""
    op.execute(sa.text(
        "EXEC sp_updateextendedproperty @name = N'MS_Description', @value = :v, @level0type = N'SCHEMA', "
        "@level0name = N'adm', @level1type = N'TABLE', @level1name = :t").bindparams(v=text, t=table))


def upgrade():
    op.execute("UPDATE adm.AppUser SET Role = N'System owner' WHERE Role = N'Sistem sahibi'")
    op.alter_column('AppUser', 'Role',
               existing_type=sa.NVARCHAR(length=15, collation='Latin1_General_100_CI_AS_SC'),
               comment='System owner | Admin | Key user | End user',
               existing_comment='Sistem sahibi | Admin | Key user | End user',
               existing_nullable=False,
               schema='adm')
    _table_comment('AuditLog', 'Kim, ne zaman, neyi değiştirdi; giriş kayıtları; System owner işlemleri silinemez.')
    _table_comment('FieldDefinition', 'Veri sözlüğü: her alanın sınıfı ve değer davranışı. Yapısını System owner yönetir.')
    _table_comment('SystemSetting', "System owner'ın ayarları: çözücü, süre bütçeleri, işçi sayısı, eş zamanlı çalışma sınırı, saklama süreleri.")


def downgrade():
    op.execute("UPDATE adm.AppUser SET Role = N'Sistem sahibi' WHERE Role = N'System owner'")
    _table_comment('SystemSetting', 'Sistem sahibinin ayarları: çözücü, süre bütçeleri, işçi sayısı, eş zamanlı çalışma sınırı, saklama süreleri.')
    _table_comment('FieldDefinition', 'Veri sözlüğü: her alanın sınıfı ve değer davranışı. Yapısını sistem sahibi yönetir.')
    _table_comment('AuditLog', 'Kim, ne zaman, neyi değiştirdi; giriş kayıtları; sistem sahibi işlemleri silinemez.')
    op.alter_column('AppUser', 'Role',
               existing_type=sa.NVARCHAR(length=15, collation='Latin1_General_100_CI_AS_SC'),
               comment='Sistem sahibi | Admin | Key user | End user',
               existing_comment='System owner | Admin | Key user | End user',
               existing_nullable=False,
               schema='adm')
