"""0065 · Şema açıklamalarında adım numarası yerine adımın adı (K-182)

Adımlar yeniden numaralandı (7.6 İlişkili alanlar araya girdi). Açıklama veritabanına da yazıldığı için numara açıklamadan çıkar:
"7.8'de kalkar" → "Kapasite yönetimi adımında kalkar". Yalnız açıklama metni değişir (dört kolon, iki tablo); yapı ve veri değişmez.
Geri alış eski metni döndürür.
Veri sözlüğü de eşitlenir: Kaynak grup eşleşmesi'nde ilişki alanının standart etiketi "Grup" yerine "Kaynak grubu" (ilişkili alan başlığı
"Kaynak grubu · Kritik" olsun diye; System owner'ın kendi etiketi korunur).

Revision ID: 0065
Revises: 0064
Create Date: 2026-11-19
"""
from alembic import context, op

from dictionary import sync
from models import metadata

revision = '0065'
down_revision = '0064'
branch_labels = None
depends_on = None

COLUMNS = [('core', 'Resource', c) for c in ('DailyCapacity', 'CalendarId', 'SubconFixedLeadTimeDays', 'SubconVariableDaysPerUnit')]
TABLES = [('core', 'ResourceCapacityProfile'), ('param', 'ResourcePeriodLimit')]
TEXTS = [("geçici alan (7.8''de kalkar)", "geçici alan (Kapasite yönetimi adımında kalkar)"),
         ("Geçici tablo: 7.8''de yeniden tasarlanır", "Geçici tablo: Kapasite yönetimi adımında yeniden tasarlanır")]


def _replace(schema, table, column, old, new):
    """Var olan açıklamada metni değiştirir (MS SQL: genişletilmiş özellik yerinde güncellenir)."""
    minor = f"COLUMNPROPERTY(OBJECT_ID(N'{schema}.{table}'), N'{column}', 'ColumnId')" if column else "0"
    level2 = f", 'column', N'{column}'" if column else ""
    op.execute(
        f"DECLARE @v nvarchar(4000) = (SELECT CAST(value AS nvarchar(4000)) FROM sys.extended_properties "
        f"WHERE class = 1 AND name = N'MS_Description' AND major_id = OBJECT_ID(N'{schema}.{table}') AND minor_id = {minor}); "
        f"IF @v IS NOT NULL BEGIN SET @v = REPLACE(@v, N'{old}', N'{new}'); "
        f"EXEC sp_updateextendedproperty N'MS_Description', @v, 'schema', N'{schema}', 'table', N'{table}'{level2}; END")


def _apply(forward):
    for old, new in TEXTS:
        a, b = (old, new) if forward else (new, old)
        for schema, table, column in COLUMNS:
            _replace(schema, table, column, a, b)
        for schema, table in TABLES:
            _replace(schema, table, None, a, b)


def upgrade():
    _apply(True)
    if not context.is_offline_mode():  # bağlantısız SQL betiğinde satırlar yazılmaz; ilk bağlantılı geçişte kurulur
        sync(op.get_bind(), metadata)


def downgrade():
    _apply(False)
