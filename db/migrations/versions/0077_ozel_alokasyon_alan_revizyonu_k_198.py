"""0077 · Özel alokasyon alan revizyonu (K-198): ad değişir, arz satırı seviye ve anahtar taşır, proje grubu ve takip kuralı kalkar

Yapı:
- `IsCustomTracked` → `IsCustomAllocated` (yeniden adlandırma, veri korunur): Material (`stg`, `prc`, `core`); Stock, WorkOrder, PurchaseOrderLine (`core`).
- Stock, WorkOrder, PurchaseOrderLine (`core`): `AllocationLevel`, `AllocationKey` (yüklemede hesaplanır) ve ERP'den geldiği gibi `SalesOrderNo`,
  `SalesOrderLineNo`, `SalesOrderLineItemNo` (kalemsiz arz: satır no boş, `SalesOrderLineId` boş). Stok'un tekil anahtarında `SalesOrderLineId`
  yerine bu üç alan. Var olan satırlarda üç alan bağlı sipariş satırından doldurulur.
- `planning.PlannedOrder`: `ProjectId` düşer; `IsCustomAllocated`, `AllocationLevel`, `AllocationKey` eklenir (motor yazar; boş).
- Kalkanlar (veri kaybı): `ProjectGroup` tablosu (`stg`, `prc`, `core`); Project `ProjectGroupCode` / `ProjectGroupId` / `TrackingRule`;
  Customer ve SalesOrderLine `IsCustomTracked` (üç katman); Stock, WorkOrder, PurchaseOrderLine `IsCustomTracked` (`stg`, `prc`).

Veri:
- Kalkan alanları kullanan kullanıcı tanımları (veri kuralı, validasyon kuralı, kayıtlı görünüm) silinir ve geçiş çıktısında listelenir; malzemedeki
  eski adı kullananlar yeni ada çevrilir. `*.CUSTOM_NO_OWNER` ve `PRJ.REF_PROJECT_GROUP` hazır kuralları bulgularıyla silinir.
- Malzemede elle girilmiş "özel takip" değerleri silinir, alttaki (ERP ya da kural) değer geçerli olur. Arz satırlarındaki eski bayrak değerleri
  yerinde kalır; ilk aktarım ya da sentetik yükleme yeniden hesaplar (geçiş hesap yapmaz: kural uygulamadadır).
- Proje grubunun `adm` kayıtları (aktarım geçmişi, bulgular, ayarlar) ve kalkan alanların sözlük satırları silinir.

Listeler ve adlar geçişte sabittir (K-197). Geri alış yapıyı geri kurar, silinen veriyi ve tanımları getirmez.

Revision ID: 0077
Revises: 0076
Create Date: 2026-11-24
"""
from alembic import context, op
import sqlalchemy as sa
from sqlalchemy.dialects import mssql

from dictionary import sync
from models import metadata

revision = '0077'
down_revision = '0076'
branch_labels = None
depends_on = None

OLD, NEW = 'IsCustomTracked', 'IsCustomAllocated'
GROUP = 'ProjectGroup'
ARZ = ('Stock', 'WorkOrder', 'PurchaseOrderLine')
# kalkan alanlar: kural katmanındaki (prc) adlarıyla
GONE_RULE_FIELDS = {'Customer': (OLD,), 'SalesOrderLine': (OLD,), 'Stock': (OLD,), 'WorkOrder': (OLD,), 'PurchaseOrderLine': (OLD,),
                    'Project': ('ProjectGroupCode', 'TrackingRule')}
# kalkan alanlar: ana tablodaki (core) adlarıyla (sözlük, manuel değer, değer kaynağı)
GONE_CORE_FIELDS = {'Customer': (OLD,), 'SalesOrderLine': (OLD,), 'Project': ('ProjectGroupId', 'TrackingRule')}
GONE_BUILTIN = ('STK.CUSTOM_NO_OWNER', 'WO.CUSTOM_NO_OWNER', 'PO.CUSTOM_NO_OWNER', 'PRJ.REF_PROJECT_GROUP')
NEW_CORE_FIELDS = ('AllocationLevel', 'AllocationKey', 'SalesOrderNo', 'SalesOrderLineNo', 'SalesOrderLineItemNo')
# kolonu taşıyan adm tabloları (geçişin yazıldığı andaki model)
WITH_DATA_RULE = ('DataRuleEffect', 'FieldChange', 'DataRuleCondition', 'FieldValueSource')
WITH_VALIDATION_RULE = ('ValidationFinding', 'ValidationRuleCondition', 'DataQualityWarning')
WITH_ENTITY = ('DataRuleEffect', 'DemandChain', 'IntegrationViewVersion', 'RawCompareRow', 'RawCompare', 'ValidationFinding', 'DataQualityWarning',
               'ValidationRun', 'DataVersionEntity', 'IntegrationEntity')
VIEW_GONE = ("(ListName = N'transaction-project-group' OR Definition LIKE N'%ProjectGroup%' OR Definition LIKE N'%TrackingRule%' "
             "OR Definition LIKE N'%CustomerId/IsCustomTracked%' OR Definition LIKE N'%SalesOrderLineId/IsCustomTracked%' "
             "OR (ListName IN (N'master-customer', N'transaction-sales-order') AND Definition LIKE N'%\"IsCustomTracked\"%'))")


def _in(names):
    return ', '.join(f"N'{n}'" for n in names)


def _rename(schema, table, old, new):
    op.execute(f"EXEC sp_rename N'{schema}.{table}.{old}', N'{new}', N'COLUMN'")


def _gone_data_rules():
    parts = [f"r.EntityName = N'{GROUP}'"]
    for entity, fields in GONE_RULE_FIELDS.items():
        names = _in(fields)
        parts.append(f"(r.EntityName = N'{entity}' AND (r.TargetField IN ({names}) OR r.SourceField IN ({names}) OR r.OperandField IN ({names}) "
                     f"OR EXISTS (SELECT 1 FROM adm.DataRuleCondition c WHERE c.DataRuleId = r.Id AND (c.FieldName IN ({names}) OR c.CompareField IN ({names})))))")
    return "SELECT r.Id, r.EntityName, r.Name FROM adm.DataRule r WHERE " + " OR ".join(parts)


def _gone_validation_rules():
    parts = [f"r.EntityName = N'{GROUP}'", f"r.Code IN ({_in(GONE_BUILTIN)})"]
    for entity, fields in GONE_RULE_FIELDS.items():
        names = _in(fields)
        parts.append(f"(r.EntityName = N'{entity}' AND EXISTS (SELECT 1 FROM adm.ValidationRuleCondition c WHERE c.ValidationRuleId = r.Id "
                     f"AND (c.FieldName IN ({names}) OR c.CompareField IN ({names}))))")
    return "SELECT r.Id, r.EntityName, r.Name, r.Kind FROM adm.ValidationRule r WHERE " + " OR ".join(parts)


def _report():
    """Silinecek kullanıcı tanımları geçiş çıktısına yazılır (bağlantılı geçişte)."""
    conn = op.get_bind()
    rows = [f"Veri kuralı · {r.EntityName} · {r.Name}" for r in conn.execute(sa.text(_gone_data_rules()))]
    rows += [f"Validasyon kuralı · {r.EntityName} · {r.Name}" for r in conn.execute(sa.text(_gone_validation_rules())) if r.Kind == 'Kullanıcı']
    rows += [f"Kayıtlı görünüm · {r.ListName} · {r.Name}" for r in conn.execute(sa.text(f"SELECT ListName, Name FROM adm.TableView WHERE {VIEW_GONE}"))]
    rows += [f"Standart görünüm · {r.ListName}" for r in conn.execute(sa.text(f"SELECT ListName FROM adm.TableViewStandard WHERE {VIEW_GONE}"))]
    manual = conn.execute(sa.text(f"SELECT COUNT(*) FROM adm.ManualValue WHERE TableName = N'Material' AND FieldName = N'{OLD}'")).scalar()
    print("0077 · silinen kullanıcı tanımları (K-198):" + ("" if rows else " yok"))
    for row in rows:
        print("  - " + row)
    print(f"0077 · malzemede silinen manuel 'özel takip' değeri: {manual}")


def _cleanup_definitions():
    """Kalkan alanları kullanan kurallar ve görünümler silinir; malzemedeki eski ad yeni ada çevrilir. Yapı değişmeden önce çalışır."""
    if not context.is_offline_mode():
        _report()
    op.execute(f"SELECT Id INTO #gone_data_rule FROM ({_gone_data_rules()}) x")
    op.execute("UPDATE adm.ManualValue SET UnderlyingRuleId = NULL WHERE UnderlyingRuleId IN (SELECT Id FROM #gone_data_rule)")
    for table in WITH_DATA_RULE:
        op.execute(f"DELETE FROM adm.[{table}] WHERE DataRuleId IN (SELECT Id FROM #gone_data_rule)")
    op.execute("DELETE FROM adm.DataRule WHERE Id IN (SELECT Id FROM #gone_data_rule)")
    op.execute("DROP TABLE #gone_data_rule")
    op.execute(f"SELECT Id INTO #gone_validation_rule FROM ({_gone_validation_rules()}) x")
    for table in WITH_VALIDATION_RULE:
        op.execute(f"DELETE FROM adm.[{table}] WHERE ValidationRuleId IN (SELECT Id FROM #gone_validation_rule)")
    op.execute("DELETE FROM adm.ValidationRule WHERE Id IN (SELECT Id FROM #gone_validation_rule)")
    op.execute("DROP TABLE #gone_validation_rule")
    # malzemenin kuralları: alan adı ve kuralın metni
    for column in ('TargetField', 'SourceField', 'OperandField'):
        op.execute(f"UPDATE adm.DataRule SET {column} = N'{NEW}' WHERE EntityName = N'Material' AND {column} = N'{OLD}'")
    for table, key in (('DataRuleCondition', 'DataRuleId'), ('ValidationRuleCondition', 'ValidationRuleId')):
        parent = table.replace('Condition', '')
        for column in ('FieldName', 'CompareField'):
            op.execute(f"UPDATE c SET {column} = N'{NEW}' FROM adm.[{table}] c JOIN adm.[{parent}] r ON r.Id = c.{key} "
                       f"WHERE r.EntityName = N'Material' AND c.{column} = N'{OLD}'")
    op.execute("UPDATE adm.DataRule SET ConditionText = REPLACE(ConditionText, N'Özel takip', N'Özel alokasyon'), "
               "ResultText = REPLACE(ResultText, N'Özel takip', N'Özel alokasyon') WHERE EntityName = N'Material'")
    op.execute("UPDATE adm.ValidationRule SET ConditionText = REPLACE(ConditionText, N'Özel takip', N'Özel alokasyon') WHERE EntityName = N'Material'")
    op.execute(f"UPDATE adm.DataRuleEffect SET FieldName = N'{NEW}' WHERE EntityName = N'Material' AND FieldName = N'{OLD}'")
    # görünümler
    op.execute(f"DELETE FROM adm.TableViewDefault WHERE ViewId IN (SELECT Id FROM adm.TableView WHERE {VIEW_GONE})")
    op.execute(f"DELETE FROM adm.TableView WHERE {VIEW_GONE}")
    op.execute(f"DELETE FROM adm.TableViewStandard WHERE {VIEW_GONE}")
    op.execute(f"UPDATE adm.TableView SET Definition = REPLACE(Definition, N'{OLD}', N'{NEW}') WHERE Definition LIKE N'%{OLD}%'")
    op.execute(f"UPDATE adm.TableViewStandard SET Definition = REPLACE(Definition, N'{OLD}', N'{NEW}'), KnownFields = REPLACE(KnownFields, N'{OLD}', N'{NEW}') "
               f"WHERE Definition LIKE N'%{OLD}%' OR KnownFields LIKE N'%{OLD}%'")
    # malzemede elle girilmiş değer: alttaki (ERP ya da kural) değer geri yazılır, manuel değer silinir
    op.execute(f"UPDATE m SET {OLD} = CASE v.UnderlyingValue WHEN N'1' THEN 1 WHEN N'0' THEN 0 ELSE NULL END FROM core.Material m "
               f"JOIN adm.ManualValue v ON v.TableName = N'Material' AND v.FieldName = N'{OLD}' AND v.RecordKey = CAST(m.Id AS nvarchar(60)) "
               "WHERE m.VersionTo IS NULL")


def _cleanup_entity():
    """Proje grubunun adm kayıtları (tablolar düştükten sonra: aktarım kayıtlarına bağ kalmaz)."""
    batches = f"SELECT Id FROM adm.ImportBatch WHERE EntityName = N'{GROUP}'"
    for table in WITH_ENTITY:
        op.execute(f"DELETE FROM adm.[{table}] WHERE EntityName = N'{GROUP}'")
    op.execute(f"DELETE FROM adm.ImportFinding WHERE ImportBatchId IN ({batches})")
    op.execute(f"DELETE FROM adm.ImportBatch WHERE EntityName = N'{GROUP}'")


def _dictionary(forward):
    """Sözlük, manuel değer, değer kaynağı ve geçmiş satırları; `sync` silmez ve yeniden adlandırmaz."""
    old, new = (OLD, NEW) if forward else (NEW, OLD)
    for table in ('Material',) + ARZ:
        where = f"TableName = N'{table}' AND FieldName = N'{old}'"
        op.execute(f"DELETE FROM adm.ManualValue WHERE {where}")
        op.execute(f"DELETE FROM adm.FieldValueSource WHERE {where}" + (" AND Source <> N'Kural'" if table == 'Material' else ''))
        op.execute(f"DELETE FROM adm.FieldDefinition WHERE TableName = N'{table}' AND FieldName = N'{new}'")
        for target in ('FieldDefinition', 'FieldValueSource', 'FieldChange'):
            op.execute(f"UPDATE adm.[{target}] SET FieldName = N'{new}' WHERE {where}")
    if forward:
        for table in ('FieldDefinition', 'ManualValue', 'FieldValueSource'):
            op.execute(f"DELETE FROM adm.[{table}] WHERE TableName = N'{GROUP}'")
            for entity, fields in GONE_CORE_FIELDS.items():
                op.execute(f"DELETE FROM adm.[{table}] WHERE TableName = N'{entity}' AND FieldName IN ({_in(fields)})")
    else:
        for table in ('FieldDefinition', 'ManualValue', 'FieldValueSource'):
            op.execute(f"DELETE FROM adm.[{table}] WHERE TableName IN ({_in(ARZ)}) AND FieldName IN ({_in(NEW_CORE_FIELDS)})")
            op.execute(f"DELETE FROM adm.[{table}] WHERE TableName = N'PlannedOrder' AND FieldName IN ({_in((NEW,) + NEW_CORE_FIELDS[:2])})")


def _fill_order_fields(table):
    """Var olan satırların sipariş no, satır no ve alt satır no'su bağlı sipariş satırından (kaydın en son versiyonu)."""
    op.execute(f"UPDATE t SET SalesOrderNo = l.OrderNo, SalesOrderLineNo = l.[LineNo], SalesOrderLineItemNo = l.LineItemNo FROM core.[{table}] t "
               "CROSS APPLY (SELECT TOP 1 OrderNo, [LineNo], LineItemNo FROM core.SalesOrderLine s WHERE s.Id = t.SalesOrderLineId ORDER BY s.VersionFrom DESC) l "
               "WHERE t.SalesOrderLineId IS NOT NULL")


def upgrade():
    _cleanup_definitions()
    op.drop_index('UX_Stock_LocationId_MaterialId_Warehouse_LotNo_Status_ProjectId_CustomerId_SalesOrderLineId', table_name='Stock', schema='core', mssql_where=sa.text('VersionTo IS NULL'))
    op.drop_table('ProjectGroup', schema='core')
    op.drop_table('ProjectGroup', schema='prc')
    op.drop_table('ProjectGroup', schema='stg')
    op.drop_column('Customer', 'IsCustomTracked', schema='core')
    _rename('core', 'Material', 'IsCustomTracked', 'IsCustomAllocated')
    op.alter_column('Material', 'IsCustomAllocated', existing_type=sa.Boolean(), existing_nullable=True,
               comment="Malzeme özel alokasyonludur: bu malzemede sahibine (sipariş, proje ya da müşteri) ayrılmış arz yalnız sahibine gider. Yalnız ERP'den ya da veri kuralıyla gelir, elle girilmez; boşsa malzemenin arzı genel sayılır ve veri kalitesi uyarır (K-198)",
               existing_comment='Malzeme ortak havuzdan değil, belli bir talebe (proje, müşteri ya da sipariş) ayrılmış olarak takip edilir; hangi talebe ayrıldığı talep kaydından gelir',
               schema='core')
    op.drop_index(op.f('IX_Project_ProjectGroupId'), table_name='Project', schema='core')
    op.drop_column('Project', 'TrackingRule', schema='core')
    op.drop_column('Project', 'ProjectGroupId', schema='core')
    op.add_column('PurchaseOrderLine', sa.Column('SalesOrderNo', sa.Unicode(length=30), nullable=True, comment="Bağlı satış sipariş no, ERP'den geldiği gibi; satır no boşsa arz siparişin bütün kalemlerine ayrılmıştır (kalemsiz arz)"), schema='core')
    op.add_column('PurchaseOrderLine', sa.Column('SalesOrderLineNo', sa.Integer(), nullable=True, comment="Bağlı satış sipariş satır no, ERP'den geldiği gibi"), schema='core')
    op.add_column('PurchaseOrderLine', sa.Column('SalesOrderLineItemNo', sa.Integer(), nullable=True, comment="Bağlı satış sipariş alt satır no, ERP'den geldiği gibi"), schema='core')
    _rename('core', 'PurchaseOrderLine', 'IsCustomTracked', 'IsCustomAllocated')
    op.alter_column('PurchaseOrderLine', 'IsCustomAllocated', existing_type=sa.Boolean(), existing_nullable=True,
               comment='Satın alma satırı sahibine ayrılmış mı: malzeme özel alokasyonluysa ve satırda sahip (sipariş, proje ya da müşteri) varsa Evet; yüklemede hesaplanır (K-198)',
               existing_comment='Satır düzeyinde özel takip',
               schema='core')
    op.add_column('PurchaseOrderLine', sa.Column('AllocationLevel', sa.Unicode(length=10), nullable=True, comment='Sipariş | Proje | Müşteri'), schema='core')
    op.add_column('PurchaseOrderLine', sa.Column('AllocationKey', sa.Unicode(length=60), nullable=True, comment='Arzın ayrıldığı sahibin anahtarı; satırda dolu olan en detaylı sahipten: sipariş (sipariş no, satır no ve alt satır no dik çizgiyle; kalemsiz arzda yalnız sipariş no), proje kodu ya da müşteri kodu. Lokasyon anahtara girmez; malzeme özel alokasyonlu değilse boştur (K-198)'), schema='core')
    op.alter_column('PurchaseOrderLine', 'SalesOrderLineId',
               existing_type=sa.BIGINT(),
               comment='Bağlı sipariş satırı; iç bağ: sipariş no ve satır no doluysa ve satır bulunuyorsa dolar, kalemsiz arzda boştur',
               existing_comment='Bağlı sipariş satırı',
               existing_nullable=True,
               schema='core')
    op.drop_column('SalesOrderLine', 'IsCustomTracked', schema='core')
    op.add_column('Stock', sa.Column('SalesOrderNo', sa.Unicode(length=30), nullable=True, comment="Sahip sipariş no, ERP'den geldiği gibi; satır no boşsa arz siparişin bütün kalemlerine ayrılmıştır (kalemsiz arz)"), schema='core')
    op.add_column('Stock', sa.Column('SalesOrderLineNo', sa.Integer(), nullable=True, comment="Sahip sipariş satır no, ERP'den geldiği gibi"), schema='core')
    op.add_column('Stock', sa.Column('SalesOrderLineItemNo', sa.Integer(), nullable=True, comment="Sahip sipariş alt satır no, ERP'den geldiği gibi"), schema='core')
    _rename('core', 'Stock', 'IsCustomTracked', 'IsCustomAllocated')
    op.alter_column('Stock', 'IsCustomAllocated', existing_type=sa.Boolean(), existing_nullable=True,
               comment='Stok sahibine ayrılmış mı: malzeme özel alokasyonluysa ve satırda sahip (sipariş, proje ya da müşteri) varsa Evet; yüklemede hesaplanır (K-198)',
               existing_comment='Stok düzeyinde özel takip',
               schema='core')
    op.add_column('Stock', sa.Column('AllocationLevel', sa.Unicode(length=10), nullable=True, comment='Sipariş | Proje | Müşteri'), schema='core')
    op.add_column('Stock', sa.Column('AllocationKey', sa.Unicode(length=60), nullable=True, comment='Arzın ayrıldığı sahibin anahtarı; satırda dolu olan en detaylı sahipten: sipariş (sipariş no, satır no ve alt satır no dik çizgiyle; kalemsiz arzda yalnız sipariş no), proje kodu ya da müşteri kodu. Lokasyon anahtara girmez; malzeme özel alokasyonlu değilse boştur (K-198)'), schema='core')
    op.alter_column('Stock', 'CustomerId',
               existing_type=sa.BIGINT(),
               comment='Sahip müşteri; stoğun ayrıldığı müşteri',
               existing_comment='Sahip müşteri; stoğun ayrıldığı müşteri, ileride kullanılmak üzere',
               existing_nullable=True,
               schema='core')
    op.alter_column('Stock', 'SalesOrderLineId',
               existing_type=sa.BIGINT(),
               comment='Sahip sipariş satırı; iç bağ: sipariş no ve satır no doluysa ve satır bulunuyorsa dolar, kalemsiz arzda boştur',
               existing_comment='Sahip sipariş satırı; stoğun ayrıldığı sipariş satırı, ileride kullanılmak üzere',
               existing_nullable=True,
               schema='core')
    _fill_order_fields('Stock')
    op.create_index('UX_Stock_LocationId_MaterialId_Warehouse_LotNo_Status_ProjectId_CustomerId_SalesOrderNo_SalesOrderLineNo_SalesOrderLineItemNo', 'Stock', ['LocationId', 'MaterialId', 'Warehouse', 'LotNo', 'Status', 'ProjectId', 'CustomerId', 'SalesOrderNo', 'SalesOrderLineNo', 'SalesOrderLineItemNo'], unique=True, schema='core', mssql_where=sa.text('VersionTo IS NULL'))
    op.add_column('WorkOrder', sa.Column('SalesOrderNo', sa.Unicode(length=30), nullable=True, comment="Bağlı sipariş no, ERP'den geldiği gibi; satır no boşsa arz siparişin bütün kalemlerine ayrılmıştır (kalemsiz arz)"), schema='core')
    op.add_column('WorkOrder', sa.Column('SalesOrderLineNo', sa.Integer(), nullable=True, comment="Bağlı sipariş satır no, ERP'den geldiği gibi"), schema='core')
    op.add_column('WorkOrder', sa.Column('SalesOrderLineItemNo', sa.Integer(), nullable=True, comment="Bağlı sipariş alt satır no, ERP'den geldiği gibi"), schema='core')
    _rename('core', 'WorkOrder', 'IsCustomTracked', 'IsCustomAllocated')
    op.alter_column('WorkOrder', 'IsCustomAllocated', existing_type=sa.Boolean(), existing_nullable=True,
               comment='İş emri sahibine ayrılmış mı: malzeme özel alokasyonluysa ve satırda sahip (sipariş, proje ya da müşteri) varsa Evet; yüklemede hesaplanır (K-198)',
               existing_comment='İş emri düzeyinde özel takip',
               schema='core')
    op.add_column('WorkOrder', sa.Column('AllocationLevel', sa.Unicode(length=10), nullable=True, comment='Sipariş | Proje | Müşteri'), schema='core')
    op.add_column('WorkOrder', sa.Column('AllocationKey', sa.Unicode(length=60), nullable=True, comment='Arzın ayrıldığı sahibin anahtarı; satırda dolu olan en detaylı sahipten: sipariş (sipariş no, satır no ve alt satır no dik çizgiyle; kalemsiz arzda yalnız sipariş no), proje kodu ya da müşteri kodu. Lokasyon anahtara girmez; malzeme özel alokasyonlu değilse boştur (K-198)'), schema='core')
    op.alter_column('WorkOrder', 'SalesOrderLineId',
               existing_type=sa.BIGINT(),
               comment='Bağlı sipariş satırı (ayraç); iç bağ: sipariş no ve satır no doluysa ve satır bulunuyorsa dolar, kalemsiz arzda boştur',
               existing_comment='Bağlı sipariş satırı (ayraç)',
               existing_nullable=True,
               schema='core')
    op.add_column('PlannedOrder', sa.Column('IsCustomAllocated', sa.Boolean(), nullable=True, comment='Planlı sipariş bir sahibe ayrılmış mı; motor yazar (K-198)'), schema='planning')
    op.add_column('PlannedOrder', sa.Column('AllocationLevel', sa.Unicode(length=10), nullable=True, comment='Sipariş | Proje | Müşteri'), schema='planning')
    op.add_column('PlannedOrder', sa.Column('AllocationKey', sa.Unicode(length=60), nullable=True, comment='Planlı siparişin ayrıldığı sahibin anahtarı; arz satırlarındaki anahtarla aynı biçimde'), schema='planning')
    op.drop_index(op.f('IX_PlannedOrder_ProjectId'), table_name='PlannedOrder', schema='planning')
    op.drop_column('PlannedOrder', 'ProjectId', schema='planning')
    op.drop_column('Customer', 'IsCustomTracked', schema='prc')
    _rename('prc', 'Material', 'IsCustomTracked', 'IsCustomAllocated')
    op.alter_column('Material', 'IsCustomAllocated', existing_type=sa.Boolean(), existing_nullable=True,
               comment='Malzeme özel alokasyonludur: bu malzemede sahibine (sipariş, proje ya da müşteri) ayrılmış arz yalnız sahibine gider; boşsa malzemenin arzı genel sayılır ve veri kalitesi uyarır (K-198)',
               existing_comment='Malzeme ortak havuzdan değil, belli bir talebe (proje, müşteri ya da sipariş) ayrılmış olarak takip edilir; hangi talebe ayrıldığı talep kaydından gelir',
               schema='prc')
    op.drop_column('Project', 'TrackingRule', schema='prc')
    op.drop_column('Project', 'ProjectGroupCode', schema='prc')
    op.drop_column('PurchaseOrderLine', 'IsCustomTracked', schema='prc')
    op.drop_column('SalesOrderLine', 'IsCustomTracked', schema='prc')
    op.alter_column('Stock', 'CustomerCode',
               existing_type=sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'),
               comment='Sahip müşteri; stoğun ayrıldığı müşteri',
               existing_comment='Sahip müşteri; stoğun ayrıldığı müşteri, ileride kullanılmak üzere',
               existing_nullable=True,
               schema='prc')
    op.alter_column('Stock', 'SalesOrderNo',
               existing_type=sa.NVARCHAR(length=30, collation='Latin1_General_100_CI_AS_SC'),
               comment='Sahip sipariş no; stoğun ayrıldığı sipariş, satır no boşsa siparişin bütün kalemleri (kalemsiz arz)',
               existing_comment='Sahip sipariş no; stoğun ayrıldığı sipariş, ileride kullanılmak üzere',
               existing_nullable=True,
               schema='prc')
    op.alter_column('Stock', 'SalesOrderLineNo',
               existing_type=sa.INTEGER(),
               comment='Sahip sipariş satırı; stoğun ayrıldığı sipariş satırı',
               existing_comment='Sahip sipariş satırı; stoğun ayrıldığı sipariş satırı, ileride kullanılmak üzere',
               existing_nullable=True,
               schema='prc')
    op.drop_column('Stock', 'IsCustomTracked', schema='prc')
    op.drop_column('WorkOrder', 'IsCustomTracked', schema='prc')
    op.drop_column('Customer', 'IsCustomTracked', schema='stg')
    _rename('stg', 'Material', 'IsCustomTracked', 'IsCustomAllocated')
    op.alter_column('Material', 'IsCustomAllocated', existing_type=sa.Boolean(), existing_nullable=True,
               comment='Malzeme özel alokasyonludur: bu malzemede sahibine (sipariş, proje ya da müşteri) ayrılmış arz yalnız sahibine gider; boşsa malzemenin arzı genel sayılır ve veri kalitesi uyarır (K-198)',
               existing_comment='Malzeme ortak havuzdan değil, belli bir talebe (proje, müşteri ya da sipariş) ayrılmış olarak takip edilir; hangi talebe ayrıldığı talep kaydından gelir',
               schema='stg')
    op.drop_column('Project', 'TrackingRule', schema='stg')
    op.drop_column('Project', 'ProjectGroupCode', schema='stg')
    op.drop_column('PurchaseOrderLine', 'IsCustomTracked', schema='stg')
    op.drop_column('SalesOrderLine', 'IsCustomTracked', schema='stg')
    op.alter_column('Stock', 'CustomerCode',
               existing_type=sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'),
               comment='Sahip müşteri; stoğun ayrıldığı müşteri',
               existing_comment='Sahip müşteri; stoğun ayrıldığı müşteri, ileride kullanılmak üzere',
               existing_nullable=True,
               schema='stg')
    op.alter_column('Stock', 'SalesOrderNo',
               existing_type=sa.NVARCHAR(length=30, collation='Latin1_General_100_CI_AS_SC'),
               comment='Sahip sipariş no; stoğun ayrıldığı sipariş, satır no boşsa siparişin bütün kalemleri (kalemsiz arz)',
               existing_comment='Sahip sipariş no; stoğun ayrıldığı sipariş, ileride kullanılmak üzere',
               existing_nullable=True,
               schema='stg')
    op.alter_column('Stock', 'SalesOrderLineNo',
               existing_type=sa.INTEGER(),
               comment='Sahip sipariş satırı; stoğun ayrıldığı sipariş satırı',
               existing_comment='Sahip sipariş satırı; stoğun ayrıldığı sipariş satırı, ileride kullanılmak üzere',
               existing_nullable=True,
               schema='stg')
    op.drop_column('Stock', 'IsCustomTracked', schema='stg')
    op.drop_column('WorkOrder', 'IsCustomTracked', schema='stg')
    for table in ('WorkOrder', 'PurchaseOrderLine'):
        _fill_order_fields(table)
    _cleanup_entity()
    _dictionary(True)
    if not context.is_offline_mode():  # bağlantısız SQL betiğinde satırlar yazılmaz; ilk bağlantılı geçişte kurulur
        sync(op.get_bind(), metadata)


def downgrade():
    op.add_column('WorkOrder', sa.Column('IsCustomTracked', mssql.BIT(), autoincrement=False, nullable=True, comment='İş emri düzeyinde özel takip'), schema='stg')
    op.add_column('Stock', sa.Column('IsCustomTracked', mssql.BIT(), autoincrement=False, nullable=True, comment='Stok düzeyinde özel takip'), schema='stg')
    op.alter_column('Stock', 'SalesOrderLineNo',
               existing_type=sa.INTEGER(),
               comment='Sahip sipariş satırı; stoğun ayrıldığı sipariş satırı, ileride kullanılmak üzere',
               existing_comment='Sahip sipariş satırı; stoğun ayrıldığı sipariş satırı',
               existing_nullable=True,
               schema='stg')
    op.alter_column('Stock', 'SalesOrderNo',
               existing_type=sa.NVARCHAR(length=30, collation='Latin1_General_100_CI_AS_SC'),
               comment='Sahip sipariş no; stoğun ayrıldığı sipariş, ileride kullanılmak üzere',
               existing_comment='Sahip sipariş no; stoğun ayrıldığı sipariş, satır no boşsa siparişin bütün kalemleri (kalemsiz arz)',
               existing_nullable=True,
               schema='stg')
    op.alter_column('Stock', 'CustomerCode',
               existing_type=sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'),
               comment='Sahip müşteri; stoğun ayrıldığı müşteri, ileride kullanılmak üzere',
               existing_comment='Sahip müşteri; stoğun ayrıldığı müşteri',
               existing_nullable=True,
               schema='stg')
    op.add_column('SalesOrderLine', sa.Column('IsCustomTracked', mssql.BIT(), autoincrement=False, nullable=True, comment='Satır düzeyinde özel takip'), schema='stg')
    op.add_column('PurchaseOrderLine', sa.Column('IsCustomTracked', mssql.BIT(), autoincrement=False, nullable=True, comment='Satır düzeyinde özel takip'), schema='stg')
    op.add_column('Project', sa.Column('ProjectGroupCode', sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'), autoincrement=False, nullable=True, comment='Proje grubu kodu'), schema='stg')
    op.add_column('Project', sa.Column('TrackingRule', sa.NVARCHAR(length=20, collation='Latin1_General_100_CI_AS_SC'), autoincrement=False, nullable=True, comment='Proje bazında takip kuralı (grubu ezer)'), schema='stg')
    _rename('stg', 'Material', 'IsCustomAllocated', 'IsCustomTracked')
    op.alter_column('Material', 'IsCustomTracked', existing_type=sa.Boolean(), existing_nullable=True,
               comment='Malzeme ortak havuzdan değil, belli bir talebe (proje, müşteri ya da sipariş) ayrılmış olarak takip edilir; hangi talebe ayrıldığı talep kaydından gelir',
               existing_comment='Malzeme özel alokasyonludur: bu malzemede sahibine (sipariş, proje ya da müşteri) ayrılmış arz yalnız sahibine gider; boşsa malzemenin arzı genel sayılır ve veri kalitesi uyarır (K-198)',
               schema='stg')
    op.add_column('Customer', sa.Column('IsCustomTracked', mssql.BIT(), autoincrement=False, nullable=True, comment='Bu müşterinin talepleri ortak havuzdan değil, müşteriye ayrılmış olarak takip edilir'), schema='stg')
    op.add_column('WorkOrder', sa.Column('IsCustomTracked', mssql.BIT(), autoincrement=False, nullable=True, comment='İş emri düzeyinde özel takip'), schema='prc')
    op.add_column('Stock', sa.Column('IsCustomTracked', mssql.BIT(), autoincrement=False, nullable=True, comment='Stok düzeyinde özel takip'), schema='prc')
    op.alter_column('Stock', 'SalesOrderLineNo',
               existing_type=sa.INTEGER(),
               comment='Sahip sipariş satırı; stoğun ayrıldığı sipariş satırı, ileride kullanılmak üzere',
               existing_comment='Sahip sipariş satırı; stoğun ayrıldığı sipariş satırı',
               existing_nullable=True,
               schema='prc')
    op.alter_column('Stock', 'SalesOrderNo',
               existing_type=sa.NVARCHAR(length=30, collation='Latin1_General_100_CI_AS_SC'),
               comment='Sahip sipariş no; stoğun ayrıldığı sipariş, ileride kullanılmak üzere',
               existing_comment='Sahip sipariş no; stoğun ayrıldığı sipariş, satır no boşsa siparişin bütün kalemleri (kalemsiz arz)',
               existing_nullable=True,
               schema='prc')
    op.alter_column('Stock', 'CustomerCode',
               existing_type=sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'),
               comment='Sahip müşteri; stoğun ayrıldığı müşteri, ileride kullanılmak üzere',
               existing_comment='Sahip müşteri; stoğun ayrıldığı müşteri',
               existing_nullable=True,
               schema='prc')
    op.add_column('SalesOrderLine', sa.Column('IsCustomTracked', mssql.BIT(), autoincrement=False, nullable=True, comment='Satır düzeyinde özel takip'), schema='prc')
    op.add_column('PurchaseOrderLine', sa.Column('IsCustomTracked', mssql.BIT(), autoincrement=False, nullable=True, comment='Satır düzeyinde özel takip'), schema='prc')
    op.add_column('Project', sa.Column('ProjectGroupCode', sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'), autoincrement=False, nullable=True, comment='Proje grubu kodu'), schema='prc')
    op.add_column('Project', sa.Column('TrackingRule', sa.NVARCHAR(length=20, collation='Latin1_General_100_CI_AS_SC'), autoincrement=False, nullable=True, comment='Proje bazında takip kuralı (grubu ezer)'), schema='prc')
    _rename('prc', 'Material', 'IsCustomAllocated', 'IsCustomTracked')
    op.alter_column('Material', 'IsCustomTracked', existing_type=sa.Boolean(), existing_nullable=True,
               comment='Malzeme ortak havuzdan değil, belli bir talebe (proje, müşteri ya da sipariş) ayrılmış olarak takip edilir; hangi talebe ayrıldığı talep kaydından gelir',
               existing_comment='Malzeme özel alokasyonludur: bu malzemede sahibine (sipariş, proje ya da müşteri) ayrılmış arz yalnız sahibine gider; boşsa malzemenin arzı genel sayılır ve veri kalitesi uyarır (K-198)',
               schema='prc')
    op.add_column('Customer', sa.Column('IsCustomTracked', mssql.BIT(), autoincrement=False, nullable=True, comment='Bu müşterinin talepleri ortak havuzdan değil, müşteriye ayrılmış olarak takip edilir'), schema='prc')
    op.add_column('PlannedOrder', sa.Column('ProjectId', sa.BIGINT(), autoincrement=False, nullable=True, comment='Proje (sahip)'), schema='planning')
    op.create_index(op.f('IX_PlannedOrder_ProjectId'), 'PlannedOrder', ['ProjectId'], unique=False, schema='planning')
    op.drop_column('PlannedOrder', 'AllocationKey', schema='planning')
    op.drop_column('PlannedOrder', 'AllocationLevel', schema='planning')
    op.drop_column('PlannedOrder', 'IsCustomAllocated', schema='planning')
    _rename('core', 'WorkOrder', 'IsCustomAllocated', 'IsCustomTracked')
    op.alter_column('WorkOrder', 'IsCustomTracked', existing_type=sa.Boolean(), existing_nullable=True,
               comment='İş emri düzeyinde özel takip',
               existing_comment='İş emri sahibine ayrılmış mı: malzeme özel alokasyonluysa ve satırda sahip (sipariş, proje ya da müşteri) varsa Evet; yüklemede hesaplanır (K-198)',
               schema='core')
    op.alter_column('WorkOrder', 'SalesOrderLineId',
               existing_type=sa.BIGINT(),
               comment='Bağlı sipariş satırı (ayraç)',
               existing_comment='Bağlı sipariş satırı (ayraç); iç bağ: sipariş no ve satır no doluysa ve satır bulunuyorsa dolar, kalemsiz arzda boştur',
               existing_nullable=True,
               schema='core')
    op.drop_column('WorkOrder', 'AllocationKey', schema='core')
    op.drop_column('WorkOrder', 'AllocationLevel', schema='core')
    op.drop_column('WorkOrder', 'SalesOrderLineItemNo', schema='core')
    op.drop_column('WorkOrder', 'SalesOrderLineNo', schema='core')
    op.drop_column('WorkOrder', 'SalesOrderNo', schema='core')
    _rename('core', 'Stock', 'IsCustomAllocated', 'IsCustomTracked')
    op.alter_column('Stock', 'IsCustomTracked', existing_type=sa.Boolean(), existing_nullable=True,
               comment='Stok düzeyinde özel takip',
               existing_comment='Stok sahibine ayrılmış mı: malzeme özel alokasyonluysa ve satırda sahip (sipariş, proje ya da müşteri) varsa Evet; yüklemede hesaplanır (K-198)',
               schema='core')
    op.drop_index('UX_Stock_LocationId_MaterialId_Warehouse_LotNo_Status_ProjectId_CustomerId_SalesOrderNo_SalesOrderLineNo_SalesOrderLineItemNo', table_name='Stock', schema='core', mssql_where=sa.text('VersionTo IS NULL'))
    op.alter_column('Stock', 'SalesOrderLineId',
               existing_type=sa.BIGINT(),
               comment='Sahip sipariş satırı; stoğun ayrıldığı sipariş satırı, ileride kullanılmak üzere',
               existing_comment='Sahip sipariş satırı; iç bağ: sipariş no ve satır no doluysa ve satır bulunuyorsa dolar, kalemsiz arzda boştur',
               existing_nullable=True,
               schema='core')
    op.alter_column('Stock', 'CustomerId',
               existing_type=sa.BIGINT(),
               comment='Sahip müşteri; stoğun ayrıldığı müşteri, ileride kullanılmak üzere',
               existing_comment='Sahip müşteri; stoğun ayrıldığı müşteri',
               existing_nullable=True,
               schema='core')
    op.drop_column('Stock', 'AllocationKey', schema='core')
    op.drop_column('Stock', 'AllocationLevel', schema='core')
    op.drop_column('Stock', 'SalesOrderLineItemNo', schema='core')
    op.drop_column('Stock', 'SalesOrderLineNo', schema='core')
    op.drop_column('Stock', 'SalesOrderNo', schema='core')
    op.add_column('SalesOrderLine', sa.Column('IsCustomTracked', mssql.BIT(), autoincrement=False, nullable=True, comment='Satır düzeyinde özel takip'), schema='core')
    _rename('core', 'PurchaseOrderLine', 'IsCustomAllocated', 'IsCustomTracked')
    op.alter_column('PurchaseOrderLine', 'IsCustomTracked', existing_type=sa.Boolean(), existing_nullable=True,
               comment='Satır düzeyinde özel takip',
               existing_comment='Satın alma satırı sahibine ayrılmış mı: malzeme özel alokasyonluysa ve satırda sahip (sipariş, proje ya da müşteri) varsa Evet; yüklemede hesaplanır (K-198)',
               schema='core')
    op.alter_column('PurchaseOrderLine', 'SalesOrderLineId',
               existing_type=sa.BIGINT(),
               comment='Bağlı sipariş satırı',
               existing_comment='Bağlı sipariş satırı; iç bağ: sipariş no ve satır no doluysa ve satır bulunuyorsa dolar, kalemsiz arzda boştur',
               existing_nullable=True,
               schema='core')
    op.drop_column('PurchaseOrderLine', 'AllocationKey', schema='core')
    op.drop_column('PurchaseOrderLine', 'AllocationLevel', schema='core')
    op.drop_column('PurchaseOrderLine', 'SalesOrderLineItemNo', schema='core')
    op.drop_column('PurchaseOrderLine', 'SalesOrderLineNo', schema='core')
    op.drop_column('PurchaseOrderLine', 'SalesOrderNo', schema='core')
    op.add_column('Project', sa.Column('ProjectGroupId', sa.BIGINT(), autoincrement=False, nullable=True, comment='Proje grubu'), schema='core')
    op.add_column('Project', sa.Column('TrackingRule', sa.NVARCHAR(length=20, collation='Latin1_General_100_CI_AS_SC'), autoincrement=False, nullable=True, comment='Proje bazında takip kuralı (grubu ezer)'), schema='core')
    op.create_index(op.f('IX_Project_ProjectGroupId'), 'Project', ['ProjectGroupId'], unique=False, schema='core')
    _rename('core', 'Material', 'IsCustomAllocated', 'IsCustomTracked')
    op.alter_column('Material', 'IsCustomTracked', existing_type=sa.Boolean(), existing_nullable=True,
               comment='Malzeme ortak havuzdan değil, belli bir talebe (proje, müşteri ya da sipariş) ayrılmış olarak takip edilir; hangi talebe ayrıldığı talep kaydından gelir',
               existing_comment="Malzeme özel alokasyonludur: bu malzemede sahibine (sipariş, proje ya da müşteri) ayrılmış arz yalnız sahibine gider. Yalnız ERP'den ya da veri kuralıyla gelir, elle girilmez; boşsa malzemenin arzı genel sayılır ve veri kalitesi uyarır (K-198)",
               schema='core')
    op.add_column('Customer', sa.Column('IsCustomTracked', mssql.BIT(), autoincrement=False, nullable=True, comment='Bu müşterinin talepleri ortak havuzdan değil, müşteriye ayrılmış olarak takip edilir'), schema='core')
    op.create_table('ProjectGroup',
    sa.Column('StagingRowId', sa.BIGINT(), sa.Identity(always=False, start=1, increment=1), autoincrement=True, nullable=False, comment='Satır kimliği'),
    sa.Column('ImportBatchId', sa.BIGINT(), autoincrement=False, nullable=False, comment='Yükleme partisi'),
    sa.Column('ErrorText', sa.NVARCHAR(length=400, collation='Latin1_General_100_CI_AS_SC'), autoincrement=False, nullable=True, comment='Hata açıklaması'),
    sa.Column('Code', sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'), autoincrement=False, nullable=True, comment='Grup kodu'),
    sa.Column('Name', sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'), autoincrement=False, nullable=True, comment='Proje grubu adı'),
    sa.Column('TrackingRule', sa.NVARCHAR(length=20, collation='Latin1_General_100_CI_AS_SC'), autoincrement=False, nullable=True, comment='Tam izolasyon | Ortaktan beslenir | Grup içi paylaşım'),
    sa.Column('Priority', sa.INTEGER(), autoincrement=False, nullable=True, comment='Proje grubu önceliği'),
    sa.Column('IsActive', mssql.BIT(), autoincrement=False, nullable=True, comment='Aktif mi'),
    sa.Column('SourceRowNo', sa.INTEGER(), autoincrement=False, nullable=True, comment='Kaynaktaki satır no'),
    sa.Column('IsCurrent', mssql.BIT(), server_default=sa.text('((0))'), autoincrement=False, nullable=False, comment='Tablonun güncel hâlinde mi (K-133)'),
    sa.Column('SupersededAt', mssql.DATETIME2(), autoincrement=False, nullable=True, comment='Satırın güncel hâlden çıktığı zaman (UTC; K-160)'),
    sa.ForeignKeyConstraint(['ImportBatchId'], ['adm.ImportBatch.Id'], name=op.f('FK_ProjectGroup_ImportBatchId')),
    sa.PrimaryKeyConstraint('StagingRowId', name=op.f('PK_ProjectGroup')),
    schema='stg',
    comment='Proje grubu (grup içi paylaşım için).'
    )
    op.create_table('ProjectGroup',
    sa.Column('StagingRowId', sa.BIGINT(), autoincrement=False, nullable=False, comment='Ham satırın kimliği (kopyalanır)'),
    sa.Column('ImportBatchId', sa.BIGINT(), autoincrement=False, nullable=False, comment='Satırın geldiği parti'),
    sa.Column('SourceRowNo', sa.INTEGER(), autoincrement=False, nullable=True, comment='Kaynaktaki satır no'),
    sa.Column('RowStatus', sa.NVARCHAR(length=15, collation='Latin1_General_100_CI_AS_SC'), server_default=sa.text("(N'Yeni')"), autoincrement=False, nullable=False, comment='Yeni | Hatalı | Aktarıldı; Hata bulgusu varsa Hatalı, load almaz (K-134)'),
    sa.Column('Code', sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'), autoincrement=False, nullable=True, comment='Grup kodu'),
    sa.Column('Name', sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'), autoincrement=False, nullable=True, comment='Proje grubu adı'),
    sa.Column('TrackingRule', sa.NVARCHAR(length=20, collation='Latin1_General_100_CI_AS_SC'), autoincrement=False, nullable=True, comment='Tam izolasyon | Ortaktan beslenir | Grup içi paylaşım'),
    sa.Column('Priority', sa.INTEGER(), autoincrement=False, nullable=True, comment='Proje grubu önceliği'),
    sa.Column('IsActive', mssql.BIT(), autoincrement=False, nullable=True, comment='Aktif mi'),
    sa.PrimaryKeyConstraint('StagingRowId', name=op.f('PK_ProjectGroup')),
    schema='prc',
    comment='Proje grubu (grup içi paylaşım için).'
    )
    op.create_table('ProjectGroup',
    sa.Column('Id', sa.BIGINT(), autoincrement=False, nullable=False, comment='Kayıt kimliği'),
    sa.Column('Code', sa.NVARCHAR(length=50, collation='Latin1_General_100_CI_AS_SC'), autoincrement=False, nullable=False, comment='Grup kodu'),
    sa.Column('Name', sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'), autoincrement=False, nullable=True, comment='Proje grubu adı'),
    sa.Column('TrackingRule', sa.NVARCHAR(length=20, collation='Latin1_General_100_CI_AS_SC'), autoincrement=False, nullable=True, comment='Tam izolasyon | Ortaktan beslenir | Grup içi paylaşım'),
    sa.Column('VersionFrom', sa.INTEGER(), autoincrement=False, nullable=False, comment='Kaydın geçerli olduğu ilk veri versiyonu'),
    sa.Column('VersionTo', sa.INTEGER(), autoincrement=False, nullable=True, comment='Kaydın geçerli olduğu son veri versiyonu; güncel kayıtta boş'),
    sa.Column('ImportBatchId', sa.BIGINT(), autoincrement=False, nullable=True, comment='Kaydı getiren yükleme partisi'),
    sa.Column('BusinessKey', sa.NVARCHAR(length=200, collation='Latin1_General_100_CI_AS_SC'), autoincrement=False, nullable=False, comment='İş anahtarı; kod ya da kodların birleşimi'),
    sa.Column('UpdatedAt', mssql.DATETIME2(), autoincrement=False, nullable=False, comment='Son değişiklik zamanı'),
    sa.Column('Priority', sa.INTEGER(), autoincrement=False, nullable=True, comment='Proje grubu önceliği'),
    sa.Column('IsActive', mssql.BIT(), autoincrement=False, nullable=True, comment='Aktif mi'),
    sa.ForeignKeyConstraint(['ImportBatchId'], ['adm.ImportBatch.Id'], name=op.f('FK_ProjectGroup_ImportBatchId')),
    sa.PrimaryKeyConstraint('Id', 'VersionFrom', name=op.f('PK_ProjectGroup')),
    schema='core',
    comment='Proje grubu (grup içi paylaşım için).'
    )
    op.create_index('UX_Stock_LocationId_MaterialId_Warehouse_LotNo_Status_ProjectId_CustomerId_SalesOrderLineId', 'Stock', ['LocationId', 'MaterialId', 'Warehouse', 'LotNo', 'Status', 'ProjectId', 'CustomerId', 'SalesOrderLineId'],
                    unique=True, schema='core', mssql_where=sa.text('VersionTo IS NULL'))
    _dictionary(False)
    if not context.is_offline_mode():
        sync(op.get_bind(), metadata)
