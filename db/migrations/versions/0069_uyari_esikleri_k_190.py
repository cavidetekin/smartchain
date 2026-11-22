"""0069 · Uyarı eşikleri (K-190): uyarı kataloğu ve senaryoya bağlı kademeli eşikler

`param.WarningDefinition` sistem kataloğu olur: `Threshold`, `Severity` ve `IsActive` kalkar (hiçbir ekran yazmıyordu); katalogdaki 17 uyarı yazılır,
var olan kodların kategorisi güncellenir. Yeni tablo `param.WarningThreshold` (senaryo + uyarı başına bir satır; dört önem için ayrı eşik, eşiksiz
uyarıda önem, aktiflik). Var olan her senaryoya başlangıç değerleri yazılır (eşikler ayardır: senaryolar tam kopya taşır). Değerler bu dosyada
sabittir (katalog sonradan değişse de geçiş aynı sonucu verir).

Geri alış `WarningThreshold`'u ve içindeki eşikleri siler; `WarningDefinition`'ın üç kolonu boş olarak geri gelir, katalog satırları kalır.

Revision ID: 0069
Revises: 0068
Create Date: 2026-11-22
"""
from alembic import context, op
import sqlalchemy as sa

from dictionary import sync
from models import metadata

revision = '0069'
down_revision = '0068'
branch_labels = None
depends_on = None

TABLE = 'WarningThreshold'
# kod, kategori, Düşük, Orta, Yüksek, Kritik, önem (eşiksiz uyarıda)
SEED = (
    ('ORDER_LATE', 'Talep', 5, 10, 15, 20, None),
    ('OTIF_RATE', 'Talep', 95, 90, 85, 80, None),
    ('FILL_RATE', 'Talep', 98, 95, 90, 80, None),
    ('ORDER_UNMET', 'Talep', None, None, None, None, 'Kritik'),
    ('FORECAST_UNMET', 'Talep', None, None, None, None, 'Orta'),
    ('MAT_SHORTAGE', 'Malzeme', 60, 30, 14, 7, None),
    ('MAT_BELOW_SAFETY', 'Malzeme', 100, 75, 50, 25, None),
    ('MAT_EXCESS', 'Malzeme', 100, 125, 150, None, None),
    ('PURCHASE_LATE', 'Malzeme', 1, 7, 14, 30, None),
    ('SHELF_LIFE', 'Malzeme', 90, 60, 30, 7, None),
    ('CAP_OVERLOAD', 'Kapasite', None, 100, 110, 125, None),
    ('CAP_OVER_TARGET', 'Kapasite', 100, 110, None, None, None),
    ('CAP_LOW_LOAD', 'Kapasite', 40, 20, None, None, None),
    ('OVERTIME_USE', 'Kapasite', 50, 80, 100, None, None),
    ('PLAN_TIME_LIMIT', 'Plan kalitesi', None, None, None, None, 'Orta'),
    ('PLAN_RELAXED', 'Plan kalitesi', None, None, None, None, 'Yüksek'),
    ('PLAN_FALLBACK', 'Plan kalitesi', None, None, None, None, 'Yüksek'),
)


def _n(value) -> str:
    return 'NULL' if value is None else (f"N'{value}'" if isinstance(value, str) else str(value))


def _table_comment(table: str, text: str) -> None:
    """SQL Server'da var olan tablo açıklaması (MS_Description) create_table_comment ile eklenemez; güncellenir."""
    op.execute(sa.text(
        "EXEC sp_updateextendedproperty @name = N'MS_Description', @value = :v, @level0type = N'SCHEMA', "
        "@level0name = N'param', @level1type = N'TABLE', @level1name = :t").bindparams(v=text, t=table))


def upgrade():
    for column in ('Threshold', 'Severity', 'IsActive'):   # varsayılan kısıtı yalnız IsActive'de var
        op.drop_column('WarningDefinition', column, schema='param', mssql_drop_default=column == 'IsActive')
    for code, category, *_ in SEED:
        op.execute(f"UPDATE param.WarningDefinition SET Category = N'{category}' WHERE Code = N'{code}'")
        op.execute(f"INSERT INTO param.WarningDefinition (Code, Category) SELECT N'{code}', N'{category}' "
                   f"WHERE NOT EXISTS (SELECT 1 FROM param.WarningDefinition WHERE Code = N'{code}')")
    op.create_table(TABLE,
    sa.Column('Id', sa.BigInteger(), autoincrement=True, nullable=False, comment='Kayıt kimliği'),
    sa.Column('ScenarioDefinitionId', sa.Integer(), nullable=False, comment='Senaryo'),
    sa.Column('WarningCode', sa.Unicode(length=30), nullable=False, comment='Uyarı kodu (ORDER_LATE, CAP_OVERLOAD…; fonksiyon 26)'),
    sa.Column('ThresholdLow', sa.Numeric(precision=18, scale=4), nullable=True, comment='Düşük önemin eşiği; boşsa kademe kullanılmaz'),
    sa.Column('ThresholdMedium', sa.Numeric(precision=18, scale=4), nullable=True, comment='Orta önemin eşiği; boşsa kademe kullanılmaz'),
    sa.Column('ThresholdHigh', sa.Numeric(precision=18, scale=4), nullable=True, comment='Yüksek önemin eşiği; boşsa kademe kullanılmaz'),
    sa.Column('ThresholdCritical', sa.Numeric(precision=18, scale=4), nullable=True, comment='Kritik önemin eşiği; boşsa kademe kullanılmaz'),
    sa.Column('Severity', sa.Unicode(length=10), nullable=True, comment='Düşük | Orta | Yüksek | Kritik'),
    sa.Column('IsActive', sa.Boolean(), server_default=sa.text('1'), nullable=True, comment='Kapalı uyarı üretilmez; değerleri durur'),
    sa.ForeignKeyConstraint(['ScenarioDefinitionId'], ['param.ScenarioDefinition.Id'], name=op.f('FK_WarningThreshold_ScenarioDefinitionId')),
    sa.ForeignKeyConstraint(['WarningCode'], ['param.WarningDefinition.Code'], name=op.f('FK_WarningThreshold_WarningCode')),
    sa.PrimaryKeyConstraint('Id', name=op.f('PK_WarningThreshold')),
    schema='param',
    comment=metadata.tables[f'param.{TABLE}'].comment,
    info={'field_class': 'Parametre'}
    )
    op.create_index('UX_WarningThreshold_ScenarioDefinitionId_WarningCode', TABLE, ['ScenarioDefinitionId', 'WarningCode'], unique=True, schema='param')
    rows = ", ".join(f"({_n(code)}, {_n(low)}, {_n(medium)}, {_n(high)}, {_n(critical)}, {_n(severity)})" for code, _, low, medium, high, critical, severity in SEED)
    op.execute(f"INSERT INTO param.{TABLE} (ScenarioDefinitionId, WarningCode, ThresholdLow, ThresholdMedium, ThresholdHigh, ThresholdCritical, Severity, IsActive) "
               f"SELECT d.Id, v.Code, v.L, v.M, v.H, v.C, v.S, 1 FROM param.ScenarioDefinition d CROSS JOIN (VALUES {rows}) v (Code, L, M, H, C, S)")
    op.alter_column('WarningDefinition', 'Category', existing_type=sa.Unicode(length=20), existing_nullable=False, schema='param',
                    comment='Talep | Malzeme | Kapasite | Plan kalitesi',
                    existing_comment='Kapasite | Malzeme | Sipariş | Ana veri | İşlem verisi | Veri değişikliği | Plan değişikliği')
    _table_comment('WarningDefinition', metadata.tables['param.WarningDefinition'].comment)
    for table in ('FieldDefinition', 'ManualValue', 'FieldValueSource'):   # kalkan kolonların sözlük satırları (eşitleme silmez)
        op.execute(f"DELETE FROM adm.[{table}] WHERE TableName = N'WarningDefinition' AND FieldName IN (N'Threshold', N'Severity', N'IsActive')")
    if not context.is_offline_mode():  # bağlantısız SQL betiğinde satırlar yazılmaz; ilk bağlantılı geçişte kurulur
        sync(op.get_bind(), metadata)


def downgrade():
    for table in ('FieldDefinition', 'ManualValue', 'FieldValueSource'):   # sözlük eşitlemesi silmez
        op.execute(f"DELETE FROM adm.[{table}] WHERE TableName = N'{TABLE}'")
    op.drop_index('UX_WarningThreshold_ScenarioDefinitionId_WarningCode', table_name=TABLE, schema='param')
    op.drop_table(TABLE, schema='param')
    op.alter_column('WarningDefinition', 'Category', existing_type=sa.Unicode(length=20), existing_nullable=False, schema='param',
                    comment='Kapasite | Malzeme | Sipariş | Ana veri | İşlem verisi | Veri değişikliği | Plan değişikliği',
                    existing_comment='Talep | Malzeme | Kapasite | Plan kalitesi')
    _table_comment('WarningDefinition', 'Uyarı tanımı, eşik ve önem seviyesi.')
    op.add_column('WarningDefinition', sa.Column('Threshold', sa.Numeric(precision=18, scale=4), nullable=True, comment='Tolerans eşiği'), schema='param')
    op.add_column('WarningDefinition', sa.Column('Severity', sa.Unicode(length=10), nullable=True, comment='Önem seviyesi'), schema='param')
    op.add_column('WarningDefinition', sa.Column('IsActive', sa.Boolean(), server_default=sa.text('1'), nullable=True, comment='Aktif'), schema='param')
    if not context.is_offline_mode():
        sync(op.get_bind(), metadata)
