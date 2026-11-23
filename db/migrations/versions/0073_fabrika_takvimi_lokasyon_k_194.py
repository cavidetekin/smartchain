"""0073 · Fabrika takvimi lokasyon bazlı (K-194)

`param.FactoryCalendar.LocationId` (zorunlu, FK `core.Location`): kayıt yalnız o lokasyonun kaynak gruplarına ve kaynaklarına uygulanır.

Var olan kayıtlar (`bind_sql`):
- Veride tek lokasyon varsa hepsi ona bağlanır.
- Birden çok lokasyon varsa kayıt, bugüne kadar bütün kaynaklara uygulandığı için, her lokasyona kopyalanır: var olan satır koda göre ilk lokasyona
  bağlanır; öteki lokasyonlar için Baz ve senaryonun kendi satırları kopyalanır, fark satırları (`BaseRowId`) yeni Baz kopyasına bağlanarak kopyalanır.
  Alan geçmişi ilk lokasyonun satırında kalır. Kaç kaydın hangi lokasyonlara kopyalandığı geçiş çıktısına yazılır.
- Hiç lokasyon yokken duran kayıt (uygulanacağı lokasyon yok) silinir; çıktıya yazılır.

Kapasite önbelleği burada boşaltılmaz: hesabın sürümü arttığı için (`app/capacity/compute.py`) ilk kullanımda kendiliğinden yeniden kurulur.
Geri alış kolonu düşürür; çok lokasyonda açılmış kopyalar durur (aynı tarihli kayıtlar birleşerek uygulanır).

Revision ID: 0073
Revises: 0072
Create Date: 2026-11-23
"""
from alembic import context, op
import sqlalchemy as sa

from dictionary import sync
from models import metadata

revision = '0073'
down_revision = '0072'
branch_labels = None
depends_on = None

TABLE = 'FactoryCalendar'
T = f'param.{TABLE}'
OLD_COMMENT = 'Fabrika takvimi (K-185): bütün kaynak gruplarına uygulanan toplu duruş (tatil, toplu izin, yarım gün). Tek günde başlangıç ve bitiş aynıdır.'
COPIED = 'ScenarioDefinitionId, IsValid, StartDate, EndDate, Name, DayValue, UpdatedAt, UpdatedBy'


def bind_sql(table: str = T, locations: str = 'core.Location') -> str:
    """Var olan kayıtları lokasyona bağlayan T-SQL (tek toplu iş). Tablo adları parametrelidir: test aynı deyimi geçici tablolarda dener.
    Sonucu PRINT ile de yazar (bağlantısız SQL betiğinde çıktı budur)."""
    s = ', '.join(f's.{c}' for c in COPIED.split(', '))
    d = ', '.join(f'd.{c}' for c in COPIED.split(', '))
    return f"""
DECLARE @first int = (SELECT TOP 1 Id FROM {locations} ORDER BY Code, Id);
DECLARE @locations int = (SELECT COUNT(*) FROM {locations});
DECLARE @rows int = (SELECT COUNT(*) FROM {table});
IF @locations = 0
BEGIN
    DELETE FROM {table};
    IF @rows > 0 PRINT N'0073: lokasyon yok; ' + CAST(@rows AS nvarchar(20)) + N' fabrika takvimi kaydı silindi (uygulanacağı lokasyon yok).';
END
ELSE
BEGIN
    UPDATE {table} SET LocationId = @first;
    IF @locations > 1 AND @rows > 0
    BEGIN
        CREATE TABLE #fc_map (OldId bigint NOT NULL, NewId bigint NOT NULL, LocationId int NOT NULL);
        MERGE {table} AS t
        USING (SELECT f.Id AS OldId, l.Id AS Loc, f.ScenarioDefinitionId, f.IsValid, f.StartDate, f.EndDate, f.Name, f.DayValue, f.UpdatedAt, f.UpdatedBy
               FROM {table} f CROSS JOIN {locations} l WHERE l.Id <> @first AND f.BaseRowId IS NULL) s ON 1 = 0
        WHEN NOT MATCHED THEN INSERT (LocationId, {COPIED}) VALUES (s.Loc, {s})
        OUTPUT s.OldId, inserted.Id, s.Loc INTO #fc_map (OldId, NewId, LocationId);
        INSERT INTO {table} (LocationId, BaseRowId, OverriddenFields, {COPIED})
        SELECT m.LocationId, m.NewId, d.OverriddenFields, {d} FROM {table} d JOIN #fc_map m ON m.OldId = d.BaseRowId WHERE d.LocationId = @first;
        DROP TABLE #fc_map;
        PRINT N'0073: ' + CAST(@rows AS nvarchar(20)) + N' fabrika takvimi kaydı ' + CAST(@locations AS nvarchar(20)) + N' lokasyona kopyalandı.';
    END
END
"""


def _report(bind) -> None:
    """Bağlantılı geçişte sonucu çıktıya yazar: kaç kayıt, hangi lokasyonlara."""
    codes = [r[0] for r in bind.execute(sa.text('SELECT Code FROM core.Location ORDER BY Code, Id'))]
    rows = bind.execute(sa.text(f'SELECT COUNT(*) FROM {T}')).scalar()
    return codes, rows


def _table_comment(text: str) -> None:
    """SQL Server'da var olan tablo açıklaması (MS_Description) create_table_comment ile eklenemez; güncellenir."""
    op.execute(sa.text(
        "EXEC sp_updateextendedproperty @name = N'MS_Description', @value = :v, @level0type = N'SCHEMA', "
        "@level0name = N'param', @level1type = N'TABLE', @level1name = :t").bindparams(v=text, t=TABLE))


def upgrade():
    c = metadata.tables[T].c
    op.add_column(TABLE, sa.Column('LocationId', sa.Integer(), nullable=True, comment=c.LocationId.comment), schema='param')   # doldurulduktan sonra zorunlu
    online = not context.is_offline_mode()
    before = _report(op.get_bind()) if online else None
    op.execute(bind_sql())
    if online:
        codes, rows = before
        after = _report(op.get_bind())[1]
        if not codes and rows:
            print(f"0073: lokasyon yok; {rows} fabrika takvimi kaydı silindi (uygulanacağı lokasyon yok).")
        elif len(codes) > 1 and rows:
            print(f"0073: {rows} fabrika takvimi kaydı {len(codes)} lokasyona kopyalandı ({', '.join(codes)}); var olan satırlar {codes[0]} lokasyonunda, "
                  f"{after - rows} kopya öteki lokasyonlarda. Gerekmeyen kopyaları Kapasite yönetimi › Fabrika takvimi'nden silin.")
        elif rows:
            print(f"0073: {rows} fabrika takvimi kaydı {codes[0]} lokasyonuna bağlandı.")
    op.alter_column(TABLE, 'LocationId', existing_type=sa.Integer(), nullable=False, existing_comment=c.LocationId.comment, schema='param')
    op.create_index(op.f('IX_FactoryCalendar_LocationId'), TABLE, ['LocationId'], unique=False, schema='param')
    op.create_foreign_key(op.f('FK_FactoryCalendar_LocationId'), TABLE, 'Location', ['LocationId'], ['Id'], source_schema='param', referent_schema='core')
    _table_comment(metadata.tables[T].comment)
    if online:  # bağlantısız SQL betiğinde satırlar yazılmaz; ilk bağlantılı geçişte kurulur
        sync(op.get_bind(), metadata)


def downgrade():
    for table in ('FieldDefinition', 'ManualValue', 'FieldValueSource'):   # sözlük eşitlemesi silmez
        op.execute(f"DELETE FROM adm.[{table}] WHERE TableName = N'{TABLE}' AND FieldName = N'LocationId'")
    _table_comment(OLD_COMMENT)
    op.drop_constraint(op.f('FK_FactoryCalendar_LocationId'), TABLE, schema='param', type_='foreignkey')
    op.drop_index(op.f('IX_FactoryCalendar_LocationId'), table_name=TABLE, schema='param')
    op.drop_column(TABLE, 'LocationId', schema='param')
    if not context.is_offline_mode():
        sync(op.get_bind(), metadata)
