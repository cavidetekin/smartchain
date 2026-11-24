"""0076 · Hedef listesi kullanıcınındır (K-196, 24.11.2026 kurgusu): ana satır kalkar, Açıklama gelir

`param.ObjectiveDefinition`: `IsMain` düşer (ana satır ve "Kalanlar" kavramı yok; silinemeyen satır yok), `Description` (kullanıcının açıklaması)
eklenir. Kapsam (`Scope`) artık örtüşebilir; seçim yapılmayan eksen "tümü"dür, boş kapsam hedefin tamamıdır.

Veri (ana satırlar normal satıra dönüşür; sıra, süre, ödün payı ve aktiflik korunur):
- ayrımı olmayan hedefin ana satırı (hedefin başka satırı yok ya da hedef kapsam almaz): kapsamsız kalır ("Tümü");
- "Kalanlar" satırı (hedefin tanımlı satırları var): içerdiği ilk eksen değerlerini açıkça yazar (ör. Talep türü: Kesin sipariş, Teklif,
  Beklemedeki sipariş). İçerdiği değer, hiçbir tanımlı satırın bütünüyle almadığı değerdir (0075 günündeki "Kalanlar (…)" yazısıyla aynı);
- hiçbir değeri kalmamış "Kalanlar" satırı (başlangıç düzenindeki kapalı satırlar; yalnız sınıfı belirsiz kayıtları kapsıyordu) kaldırılır;
  aktifse sıra yeniden numaralanır.
Dönüşüm bağlantılı çalışır (satırların kapsamı okunur). Bağlantısız SQL betiğinde (`--sql`) kapsam okunamaz: hedefin başka satırı olan ana
satırlar kaldırılır (yeni kurulumun başlangıç düzeni için doğrudur; veri taşıyan kurulum bağlantılı geçişle yükseltilir).

Eksenler ve değerleri geçişte sabittir (katalog sonradan değişebilir).

Geri alış: `Description` düşer, `IsMain` geri gelir; kapsamsız satırlardan hedef başına ilki ana satır olur, ana satırı olmayan hedefe kapalı bir
ana satır eklenir. Açıklamalar kaybolur.

Revision ID: 0076
Revises: 0075
Create Date: 2026-11-24
"""
import json

from alembic import context, op
import sqlalchemy as sa

from dictionary import sync
from models import metadata

revision = '0076'
down_revision = '0075'
branch_labels = None
depends_on = None

TABLE = 'ObjectiveDefinition'
DICTIONARY = ('FieldDefinition', 'ManualValue', 'FieldValueSource')   # sözlük eşitlemesi silmez
# açıklamalar sabit (bu geçişin yazdığı ve geri alışta döndüğü metinler)
TABLE_0075 = ('Senaryonun hedef satırları (leksikografik, ağırlık yok; K-175): motor satırları sırayla çözer. Senaryonun süre bütçesi aktif satırların '
              'sürelerinin toplamıdır. Hedef, ilgili olduğu şeyin sınıfına göre satırlara ayrışır (K-196): her hedefin bir ana satırı (IsMain) ve '
              'tanımlanan satırları (Scope) vardır; her sınıf birleşimi hedefte tam bir satırdadır.')
TABLE_0076 = ('Senaryonun hedef satırları (leksikografik, ağırlık yok; K-175): motor satırları sırayla çözer. Senaryonun süre bütçesi aktif satırların '
              'sürelerinin toplamıdır. Hedef listesi kullanıcınındır (K-196): her satır bir hedef ve bir kapsamdır (Scope); kapsamlar örtüşebilir, '
              'hiçbir satırın kapsamadığı kayıt hiçbir hedefe girmez.')
SCOPE_0075 = ('Tanımlanan satırın kapsamı (JSON): eksen → değerler (DemandType, PriorityGroup, MaterialLevel, MaterialGroup, ResourceType); eksen yoksa o '
              'eksen "Tümü"; ana satırda boş (K-196)')
SCOPE_0076 = ('Satırın kapsamı (JSON): eksen → seçilen değerler (DemandType, PriorityGroup, MaterialLevel, MaterialGroup, ResourceType); seçim '
              'yapılmayan eksen yazılmaz ve "tümü" demektir; boş = hedefin tamamı (K-196)')
IS_MAIN = ('Hedefin ana satırı ("Kalanlar"; ayrım yoksa "Tümü"): tanımlı satırların almadığı ve sınıfı belirsiz kayıtlar; hedef başına tam bir tane, '
           'silinemez (K-196)')
DESCRIPTION = 'Kullanıcının satıra yazdığı açıklama; serbest metin (K-196)'
# hedef → (ilk eksen, değerleri, ikinci eksen, ikinci eksenin değerleri; None: açık eksen ya da eksen yok)
DEMAND = ('DemandType', ('Kesin sipariş', 'Teklif', 'Beklemedeki sipariş', 'Tahmin'), 'PriorityGroup', (1, 2, 3, 4, 5))
MATERIAL = ('MaterialLevel', ('Hammadde', 'Yarı mamul', 'Nihai ürün'), 'MaterialGroup', None)
AXES = {'UNMET_DEMAND': DEMAND, 'LATENESS': DEMAND, 'SAFETY_STOCK': MATERIAL, 'EARLY_BUILD': MATERIAL,
        'OVERTIME': ('ResourceType', ('İşçi', 'Makine', 'Diğer'), None, None),
        'OVER_TARGET_LOAD': ('ResourceType', ('İşçi', 'Makine', 'Fason', 'Diğer'), None, None)}
RENUMBER = ("UPDATE o SET Seq = n.Seq FROM param.ObjectiveDefinition o JOIN (SELECT Id, ROW_NUMBER() OVER (PARTITION BY ScenarioDefinitionId ORDER BY Seq, Id) "
            "AS Seq FROM param.ObjectiveDefinition WHERE IsActive = 1) n ON n.Id = o.Id")


def _table_comment(text: str) -> None:
    """SQL Server'da var olan tablo açıklaması (MS_Description) create_table_comment ile eklenemez; güncellenir."""
    op.execute(sa.text(
        "EXEC sp_updateextendedproperty @name = N'MS_Description', @value = :v, @level0type = N'SCHEMA', "
        "@level0name = N'param', @level1type = N'TABLE', @level1name = :t").bindparams(v=text, t=TABLE))


def rest_of(code: str, scopes: list[dict]) -> list | None:
    """Ana satırın yeni kapsamı için kalan ilk eksen değerleri. None: hedef kapsam almaz ya da tanımlı satırı yok (satır kapsamsız kalır);
    []: hiçbir değer kalmamış (satır kaldırılır). Değer, tanımlı bir satır onu ikinci eksenin tamamıyla almışsa alınmış sayılır."""
    if code not in AXES or not scopes:
        return None
    first, values, second, second_values = AXES[code]
    left = []
    for value in values:
        taking = [s for s in scopes if s.get(first) is None or value in s[first]]
        whole = any(second is None or s.get(second) is None for s in taking)
        if not whole and second_values is not None:
            whole = {v for s in taking for v in (s.get(second) or ())} >= set(second_values)
        if not whole:
            left.append(value)
    return left


def convert(bind) -> None:
    """Ana satırları normal satıra çevirir (bağlantılı)."""
    rows = bind.execute(sa.text("SELECT Id, ScenarioDefinitionId, Code, IsMain, Scope FROM param.ObjectiveDefinition")).all()
    defined = {}
    for r in rows:
        if not r.IsMain:
            defined.setdefault((r.ScenarioDefinitionId, r.Code), []).append(json.loads(r.Scope) if r.Scope else {})
    gone = False
    for r in rows:
        if not r.IsMain:
            continue
        left = rest_of(r.Code, defined.get((r.ScenarioDefinitionId, r.Code), []))
        if left is None:
            bind.execute(sa.text("UPDATE param.ObjectiveDefinition SET Scope = NULL WHERE Id = :i"), {"i": r.Id})
        elif left:
            scope = json.dumps({AXES[r.Code][0]: left}, ensure_ascii=False)
            bind.execute(sa.text("UPDATE param.ObjectiveDefinition SET Scope = CAST(:s AS nvarchar(max)) WHERE Id = :i"), {"s": scope, "i": r.Id})
        else:
            bind.execute(sa.text("DELETE FROM param.ObjectiveDefinition WHERE Id = :i"), {"i": r.Id})
            gone = True
    if gone:
        bind.execute(sa.text(RENUMBER))


def upgrade():
    op.add_column(TABLE, sa.Column('Description', sa.Unicode(length=200), nullable=True, comment=DESCRIPTION), schema='param')
    if context.is_offline_mode():   # kapsam okunamaz: hedefin başka satırı olan ana satırlar kaldırılır (yeni kurulum)
        op.execute("DELETE m FROM param.ObjectiveDefinition m WHERE m.IsMain = 1 AND EXISTS (SELECT 1 FROM param.ObjectiveDefinition d "
                   "WHERE d.ScenarioDefinitionId = m.ScenarioDefinitionId AND d.Code = m.Code AND d.IsMain = 0)")
        op.execute(RENUMBER)
    else:
        convert(op.get_bind())
    for table in DICTIONARY:
        op.execute(f"DELETE FROM adm.[{table}] WHERE TableName = N'{TABLE}' AND FieldName = N'IsMain'")
    op.drop_column(TABLE, 'IsMain', schema='param', mssql_drop_default=True)
    op.alter_column(TABLE, 'Scope', existing_type=sa.Unicode(), existing_nullable=True, comment=SCOPE_0076, existing_comment=SCOPE_0075, schema='param')
    _table_comment(TABLE_0076)
    if not context.is_offline_mode():  # bağlantısız SQL betiğinde satırlar yazılmaz; ilk bağlantılı geçişte kurulur
        sync(op.get_bind(), metadata)


def downgrade():
    _table_comment(TABLE_0075)
    op.alter_column(TABLE, 'Scope', existing_type=sa.Unicode(), existing_nullable=True, comment=SCOPE_0075, existing_comment=SCOPE_0076, schema='param')
    op.add_column(TABLE, sa.Column('IsMain', sa.Boolean(), server_default=sa.text('0'), nullable=False, comment=IS_MAIN), schema='param')
    # kapsamsız satırlardan hedef başına ilki ana satır; ana satırı olmayan hedefe kapalı ana satır
    op.execute("UPDATE o SET IsMain = 1 FROM param.ObjectiveDefinition o WHERE o.Scope IS NULL AND o.Id = (SELECT MIN(x.Id) FROM param.ObjectiveDefinition x "
               "WHERE x.ScenarioDefinitionId = o.ScenarioDefinitionId AND x.Code = o.Code AND x.Scope IS NULL)")
    op.execute("INSERT INTO param.ObjectiveDefinition (ScenarioDefinitionId, Code, IsMain, IsActive) SELECT DISTINCT o.ScenarioDefinitionId, o.Code, 1, 0 "
               "FROM param.ObjectiveDefinition o WHERE NOT EXISTS (SELECT 1 FROM param.ObjectiveDefinition m WHERE m.ScenarioDefinitionId = o.ScenarioDefinitionId "
               "AND m.Code = o.Code AND m.IsMain = 1)")
    for table in DICTIONARY:
        op.execute(f"DELETE FROM adm.[{table}] WHERE TableName = N'{TABLE}' AND FieldName = N'Description'")
    op.drop_column(TABLE, 'Description', schema='param')
    if not context.is_offline_mode():
        sync(op.get_bind(), metadata)
