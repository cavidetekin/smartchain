"""0075 · Hedeflerin ayrıştırılması (K-196)

`param.ObjectiveDefinition`: hedef, ilgili olduğu şeyin sınıfına göre satırlara ayrışır. `IsMain` (hedefin ana satırı) ve `Scope` (tanımlanan
satırın kapsamı, JSON) eklenir; `PriorityGroup` ve (senaryo, kod, öncelik grubu) tekilliği kalkar (bir hedefin birden çok satırı olur).

Veri:
- **Mevcut senaryolar en az değişiklikle taşınır** (K-196 madde 7): her hedefin satırı ana satır olur; "Karşılanmayan tahmin" satırı
  "Karşılanmayan talep · Tahmin", "Tahmin gecikmesi" satırı "Gecikme · Tahmin" tanımlı satırına çevrilir. Sıra, süre, ödün payı ve aktiflik
  değişmez (senaryonun toplam süre bütçesi ve çözüm sırası aynı kalır).
- **Yeni kurulum** (veri versiyonu yok ve tek senaryo, Baz) ayrışmış başlangıç düzeniyle gelir (K-196 madde 4, 5): 30 satır; türün süresi aktif
  satırlarına eşit bölünür (toplam 1.140 sn); Tahmin satırlarının ödün payı eski başlangıç değeridir (%2). Bu liste geçişte sabittir (`app/params/objectives.py` `start_rows` ile aynı; test karşılaştırır).

Geri alış: tanımlı satırlar silinir (iki Tahmin satırı eski türlerine döner), ana satırlar kalır, sıra yeniden numaralanır; ayrıştırma kaybolur.

Revision ID: 0075
Revises: 0074
Create Date: 2026-11-23
"""
from alembic import context, op
import sqlalchemy as sa

from dictionary import sync
from models import metadata

revision = '0075'
down_revision = '0074'
branch_labels = None
depends_on = None

TABLE = 'ObjectiveDefinition'
T = f'param.{TABLE}'
INDEX = 'UX_ObjectiveDefinition_ScenarioDefinitionId_Code_PriorityGroup'
DICTIONARY = ('FieldDefinition', 'ManualValue', 'FieldValueSource')   # sözlük eşitlemesi silmez
OLD_TABLE = ('Senaryonun hedefleri (leksikografik, ağırlık yok; K-175): motor hedefleri sırayla çözer. Senaryonun süre bütçesi aktif hedeflerin '
             'sürelerinin toplamıdır.')
OLD_CODE = 'Hedefin kodu (UNMET_DEMAND, LATENESS, UNMET_FORECAST…; fonksiyon 22)'
OLD_GROUP = 'Sipariş öncelik grubu; boş = bütün siparişler (gruplar öncelik kuralları adımında)'
# Bu geçişin yazdığı açıklamalar sabittir (yazıldığı andaki modelle birebir): IsMain 0076'da modelden kalktı, Scope ve tablo açıklaması değişti.
NEW_TABLE = ('Senaryonun hedef satırları (leksikografik, ağırlık yok; K-175): motor satırları sırayla çözer. Senaryonun süre bütçesi aktif satırların '
             'sürelerinin toplamıdır. Hedef, ilgili olduğu şeyin sınıfına göre satırlara ayrışır (K-196): her hedefin bir ana satırı (IsMain) ve '
             'tanımlanan satırları (Scope) vardır; her sınıf birleşimi hedefte tam bir satırdadır.')
NEW_CODE = 'Hedefin kodu (UNMET_DEMAND, LATENESS, SAFETY_STOCK…; fonksiyon 22); bir hedefin birden çok satırı olabilir (K-196)'
IS_MAIN = ('Hedefin ana satırı ("Kalanlar"; ayrım yoksa "Tümü"): tanımlı satırların almadığı ve sınıfı belirsiz kayıtlar; hedef başına tam bir tane, '
           'silinemez (K-196)')
SCOPE = ('Tanımlanan satırın kapsamı (JSON): eksen → değerler (DemandType, PriorityGroup, MaterialLevel, MaterialGroup, ResourceType); eksen yoksa o '
         'eksen "Tümü"; ana satırda boş (K-196)')
FORECAST = {'UNMET_FORECAST': 'UNMET_DEMAND', 'FORECAST_LATENESS': 'LATENESS'}
FORECAST_SCOPE = '{"DemandType": ["Tahmin"]}'


def _scope(axis: str, value: str) -> str:
    return f'{{"{axis}": ["{value}"]}}'


# Başlangıç düzeni (yeni kurulum; Talep ayarlarının başlangıç değerleriyle: Tahmin planda, Teklif ve Beklemedeki sipariş değil).
# (kod, ana satır mı, kapsam, süre, ödün payı): süresi olan aktif, sırası listedeki sırası.
def _start() -> list[tuple]:
    d, lv, rs = 'DemandType', 'MaterialLevel', 'ResourceType'
    levels, people = ('Nihai ürün', 'Yarı mamul', 'Hammadde'), ('İşçi', 'Makine', 'Diğer')
    rows = []
    for kind, tolerance in (('Kesin sipariş', 0), ('Tahmin', 2)):   # Tahmin satırlarının ödün payı korunur (eski başlangıç değeri %2)
        rows += [(code, 0, _scope(d, kind), 210, tolerance) for code in ('UNMET_DEMAND', 'LATENESS')]
    rows += [('SAFETY_STOCK', 0, _scope(lv, v), 20, 5) for v in levels]
    rows += [('OVERTIME', 0, _scope(rs, v), 20, 5) for v in people]
    rows += [('SUBCONTRACT', 1, None, 60, 5), ('ALTERNATIVE', 1, None, 60, 5)]
    rows += [('EARLY_BUILD', 0, _scope(lv, v), 20, 5) for v in levels]
    # kapalı gelenler: plana alınmayan talep türleri, yalnız belirsiz sınıfları kapsayan ana satırlar, kurulumda kapalı hedefler
    for kind in ('Beklemedeki sipariş', 'Teklif'):
        rows += [(code, 0, _scope(d, kind), None, None) for code in ('UNMET_DEMAND', 'LATENESS')]
    rows += [(code, 1, None, None, None) for code in ('UNMET_DEMAND', 'LATENESS', 'SAFETY_STOCK', 'OVERTIME')]
    rows += [('OVER_TARGET_LOAD', 0, _scope(rs, v), None, None) for v in ('İşçi', 'Makine', 'Fason', 'Diğer')]
    rows += [('OVER_TARGET_LOAD', 1, None, None, None), ('EARLY_BUILD', 1, None, None, None), ('PLAN_DEVIATION', 1, None, None, None)]
    return rows


def _n(text: str | None) -> str:
    return 'NULL' if text is None else "N'" + text.replace("'", "''") + "'"


def _table_comment(text: str) -> None:
    """SQL Server'da var olan tablo açıklaması (MS_Description) create_table_comment ile eklenemez; güncellenir."""
    op.execute(sa.text(
        "EXEC sp_updateextendedproperty @name = N'MS_Description', @value = :v, @level0type = N'SCHEMA', "
        "@level0name = N'param', @level1type = N'TABLE', @level1name = :t").bindparams(v=text, t=TABLE))


def fresh_sql() -> str:
    """Yeni kurulum: bütün senaryoların (tek senaryo, Baz) hedefleri başlangıç düzeniyle baştan yazılır."""
    values = []
    seq = 0
    for code, main, scope, seconds, tolerance in _start():
        seq += 1 if seconds is not None else 0
        tail = f"{seq}, {seconds}, {tolerance}, 1" if seconds is not None else "NULL, NULL, NULL, 0"
        values.append(f"(N'{code}', {main}, {_n(scope)}, {tail})")
    return ("DELETE FROM param.ObjectiveDefinition; "
            "INSERT INTO param.ObjectiveDefinition (ScenarioDefinitionId, Code, IsMain, Scope, Seq, TimeBudgetSeconds, TolerancePct, IsActive) "
            "SELECT d.Id, v.Code, v.IsMain, v.Scope, v.Seq, v.Seconds, v.Tolerance, v.IsActive FROM param.ScenarioDefinition d "
            f"CROSS JOIN (VALUES {', '.join(values)}) v (Code, IsMain, Scope, Seq, Seconds, Tolerance, IsActive);")


def moved_sql(where: str = "1 = 1") -> str:
    """Mevcut senaryolar: her satır ana satır olur; iki tahmin türü talep hedeflerinin Tahmin satırına çevrilir. `where`: test için satır süzmesi."""
    return f"UPDATE param.ObjectiveDefinition SET IsMain = 1 WHERE {where}; " + " ".join(
        f"UPDATE param.ObjectiveDefinition SET Code = N'{new}', IsMain = 0, Scope = {_n(FORECAST_SCOPE)} WHERE Code = N'{old}' AND {where};"
        for old, new in FORECAST.items())


def upgrade():
    op.add_column(TABLE, sa.Column('IsMain', sa.Boolean(), server_default=sa.text('0'), nullable=False, comment=IS_MAIN), schema='param')
    op.add_column(TABLE, sa.Column('Scope', sa.Unicode(), nullable=True, comment=SCOPE), schema='param')
    op.drop_index(INDEX, table_name=TABLE, schema='param')
    for table in DICTIONARY:
        op.execute(f"DELETE FROM adm.[{table}] WHERE TableName = N'{TABLE}' AND FieldName = N'PriorityGroup'")
    op.drop_column(TABLE, 'PriorityGroup', schema='param')
    op.alter_column(TABLE, 'Code', existing_type=sa.Unicode(30), existing_nullable=False, comment=NEW_CODE, existing_comment=OLD_CODE, schema='param')
    _table_comment(NEW_TABLE)
    # veri: yeni kurulumda başlangıç düzeni, mevcut senaryolarda en az değişiklik
    op.execute("IF NOT EXISTS (SELECT 1 FROM adm.DataVersion) AND (SELECT COUNT(*) FROM param.ScenarioDefinition) = 1 "
               f"BEGIN {fresh_sql()} END ELSE BEGIN {moved_sql()} END")
    if not context.is_offline_mode():  # bağlantısız SQL betiğinde satırlar yazılmaz; ilk bağlantılı geçişte kurulur
        sync(op.get_bind(), metadata)


def downgrade():
    for old, new in FORECAST.items():
        op.execute(f"UPDATE param.ObjectiveDefinition SET Code = N'{old}', IsMain = 1 WHERE Code = N'{new}' AND IsMain = 0 AND Scope = {_n(FORECAST_SCOPE)}")
    op.execute("DELETE FROM param.ObjectiveDefinition WHERE IsMain = 0")
    op.execute("UPDATE o SET Seq = n.Seq FROM param.ObjectiveDefinition o JOIN (SELECT Id, ROW_NUMBER() OVER (PARTITION BY ScenarioDefinitionId ORDER BY Seq) AS Seq "
               "FROM param.ObjectiveDefinition WHERE IsActive = 1) n ON n.Id = o.Id")
    _table_comment(OLD_TABLE)
    op.alter_column(TABLE, 'Code', existing_type=sa.Unicode(30), existing_nullable=False, comment=OLD_CODE, existing_comment=NEW_CODE, schema='param')
    op.add_column(TABLE, sa.Column('PriorityGroup', sa.Integer(), nullable=True, comment=OLD_GROUP), schema='param')
    op.create_index(INDEX, TABLE, ['ScenarioDefinitionId', 'Code', 'PriorityGroup'], unique=True, schema='param')
    for table in DICTIONARY:
        op.execute(f"DELETE FROM adm.[{table}] WHERE TableName = N'{TABLE}' AND FieldName IN (N'IsMain', N'Scope')")
    op.drop_column(TABLE, 'Scope', schema='param')
    op.drop_column(TABLE, 'IsMain', schema='param', mssql_drop_default=True)
    if not context.is_offline_mode():
        sync(op.get_bind(), metadata)
