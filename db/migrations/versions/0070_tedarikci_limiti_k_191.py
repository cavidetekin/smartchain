"""0070 · Tedarikçi limiti (K-191): iki kayıt türü (üst limit, kapanış), limitin dönemi, lokasyon, Baz + fark

`param.SupplierLimit` yeniden biçimlenir: `LimitType` (Üst limit | Kapanış), `LocationId`, `LimitPeriod`, `Reason` ve Baz + fark yapısının kolonları
(`BaseRowId`, `OverriddenFields`, `IsValid`, `UpdatedAt`, `UpdatedBy`); `ValidTo` ve `UpperLimit` boş olabilir. Var olan satırlar korunur: malzemesi
dolu ve limiti sıfırdan büyük satır "Üst limit · Ay" olur (eski tek kullanım aylık limitti); malzemesi boş ya da limiti sıfır satır "Kapanış" olur
(limiti boşalır). Lokasyon, tedarikçinin malzeme tedarikçisi kaydından alınır (yoksa tek lokasyon); lokasyonu bulunamayan satır silinir.

Geri alış yeni kolonları düşürür: tür, dönem, sebep ve senaryo farkları kaybolur; süresiz üst limitin bitişi başlangıcına eşitlenir.

Revision ID: 0070
Revises: 0069
Create Date: 2026-11-23
"""
from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql

from dictionary import sync
from models import metadata

revision = '0070'
down_revision = '0069'
branch_labels = None
depends_on = None

TABLE = 'SupplierLimit'
T = f'param.{TABLE}'
OLD_COMMENT = ("Tedarikçi dönem üst limiti (problem 39): malzeme bazında maksimum miktar. Malzeme boşsa tedarikçi o dönemde kapalıdır (limit 0). "
               "Smartchain'de ekrandan girilir (K-65, K-66).")


def _table_comment(text: str) -> None:
    """SQL Server'da var olan tablo açıklaması (MS_Description) create_table_comment ile eklenemez; güncellenir."""
    op.execute(sa.text(
        "EXEC sp_updateextendedproperty @name = N'MS_Description', @value = :v, @level0type = N'SCHEMA', "
        "@level0name = N'param', @level1type = N'TABLE', @level1name = :t").bindparams(v=text, t=TABLE))


def _drop_default(column: str) -> None:
    op.execute(f"DECLARE @c nvarchar(256); SELECT @c = QUOTENAME(d.name) FROM sys.default_constraints d "
               f"WHERE d.parent_object_id = OBJECT_ID(N'{T}') AND COL_NAME(d.parent_object_id, d.parent_column_id) = N'{column}'; "
               f"IF @c IS NOT NULL EXEC(N'ALTER TABLE {T} DROP CONSTRAINT ' + @c)")


def upgrade():
    c = metadata.tables[T].c
    for name in ('BaseRowId', 'OverriddenFields', 'LimitType', 'LocationId', 'LimitPeriod', 'Reason', 'UpdatedAt', 'UpdatedBy'):
        op.add_column(TABLE, sa.Column(name, c[name].type, nullable=True, comment=c[name].comment), schema='param')   # zorunlular doldurulduktan sonra sıkılaşır
    op.add_column(TABLE, sa.Column('IsValid', sa.Boolean(), server_default=sa.text('1'), nullable=False, comment=c.IsValid.comment), schema='param')
    _drop_default('UpperLimit')
    op.alter_column(TABLE, 'UpperLimit', existing_type=sa.NUMERIC(precision=18, scale=4), nullable=True, comment=c.UpperLimit.comment,
                    existing_comment='Dönem üst limiti, malzemenin temel biriminde; malzeme boşsa 0', schema='param')
    op.alter_column(TABLE, 'ValidTo', existing_type=sa.DATE(), nullable=True, comment=c.ValidTo.comment, existing_comment='Bitiş', schema='param')
    op.alter_column(TABLE, 'MaterialId', existing_type=sa.BIGINT(), existing_nullable=True, comment=c.MaterialId.comment,
                    existing_comment='Malzeme; boşsa tedarikçinin bütün malzemeleri (yalnız kapalı dönem)', schema='param')
    # var olan satırlar
    op.execute(f"UPDATE {T} SET LimitType = CASE WHEN MaterialId IS NULL OR COALESCE(UpperLimit, 0) <= 0 THEN N'Kapanış' ELSE N'Üst limit' END, UpdatedAt = SYSUTCDATETIME()")
    op.execute(f"UPDATE {T} SET LimitPeriod = N'Ay' WHERE LimitType = N'Üst limit'")
    op.execute(f"UPDATE {T} SET UpperLimit = NULL WHERE LimitType = N'Kapanış'")
    op.execute(f"UPDATE s SET LocationId = COALESCE("
               f"(SELECT TOP 1 ms.LocationId FROM core.MaterialSupplier ms WHERE ms.SupplierId = s.SupplierId AND (s.MaterialId IS NULL OR ms.MaterialId = s.MaterialId) "
               f"ORDER BY CASE WHEN ms.VersionTo IS NULL THEN 0 ELSE 1 END, ms.VersionFrom DESC), "
               f"(SELECT CASE WHEN COUNT(*) = 1 THEN MIN(l.Id) END FROM core.Location l)) FROM {T} s")
    op.execute(f"DELETE FROM {T} WHERE LocationId IS NULL")
    for name in ('LimitType', 'LocationId', 'UpdatedAt'):
        op.alter_column(TABLE, name, existing_type=c[name].type, nullable=False, existing_comment=c[name].comment, schema='param')
    op.create_index(op.f('IX_SupplierLimit_LocationId'), TABLE, ['LocationId'], unique=False, schema='param')
    op.create_foreign_key(op.f('FK_SupplierLimit_LocationId'), TABLE, 'Location', ['LocationId'], ['Id'], source_schema='param', referent_schema='core')
    _table_comment(metadata.tables[T].comment)
    if not context.is_offline_mode():  # bağlantısız SQL betiğinde satırlar yazılmaz; ilk bağlantılı geçişte kurulur
        sync(op.get_bind(), metadata)


def downgrade():
    c = metadata.tables[T].c
    for table in ('FieldDefinition', 'ManualValue', 'FieldValueSource'):   # sözlük eşitlemesi silmez
        op.execute(f"DELETE FROM adm.[{table}] WHERE TableName = N'{TABLE}' AND FieldName IN (N'BaseRowId', N'OverriddenFields', N'IsValid', N'LimitType', N'LocationId', "
                   "N'LimitPeriod', N'Reason', N'UpdatedAt', N'UpdatedBy')")
    op.execute(f"DELETE FROM {T} WHERE BaseRowId IS NOT NULL OR IsValid = 0")          # senaryo farkları eski yapıda tutulamaz
    op.execute(f"UPDATE {T} SET ValidTo = COALESCE(ValidTo, ValidFrom), UpperLimit = COALESCE(UpperLimit, 0)")
    _table_comment(OLD_COMMENT)
    op.drop_constraint(op.f('FK_SupplierLimit_LocationId'), TABLE, schema='param', type_='foreignkey')
    op.drop_index(op.f('IX_SupplierLimit_LocationId'), table_name=TABLE, schema='param')
    op.alter_column(TABLE, 'UpperLimit', existing_type=sa.NUMERIC(precision=18, scale=4), server_default=sa.text('0'), nullable=False,
                    comment='Dönem üst limiti, malzemenin temel biriminde; malzeme boşsa 0', existing_comment=c.UpperLimit.comment, schema='param')
    op.alter_column(TABLE, 'ValidTo', existing_type=sa.DATE(), nullable=False, comment='Bitiş', existing_comment=c.ValidTo.comment, schema='param')
    op.alter_column(TABLE, 'MaterialId', existing_type=sa.BIGINT(), existing_nullable=True,
                    comment='Malzeme; boşsa tedarikçinin bütün malzemeleri (yalnız kapalı dönem)', existing_comment=c.MaterialId.comment, schema='param')
    for name in ('UpdatedBy', 'UpdatedAt', 'Reason', 'LimitPeriod', 'LocationId', 'LimitType', 'OverriddenFields', 'BaseRowId'):
        op.drop_column(TABLE, name, schema='param')
    op.drop_column(TABLE, 'IsValid', schema='param', mssql_drop_default=True)
    if not context.is_offline_mode():
        sync(op.get_bind(), metadata)
