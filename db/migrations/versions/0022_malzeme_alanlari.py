"""0022 · Malzeme alanları (K-113): anahtar LocationCode + Code; yeni alanlar; ad değişiklikleri; Ownership ve ProductionLeadTimeDays kalkar

Adı değişen kolonlarda veri korunur. ScrapRatio oran olarak tutulur: core'daki yüzde değer 100'e bölünür. Ownership IsCustomerSupplied'a çevrilir.
stg ham veridir, değerleri çevrilmez. Kayıtlı görünümler yeni adlara geçer, kaldırılan alanlar görünümden düşer.
Geri alışta ProductionLeadTimeDays boş döner, görünümlerden düşen alanlar geri gelmez.

Revision ID: 0022
Revises: 0021
Create Date: 2026-11-04
"""
import json

from alembic import context, op
import sqlalchemy as sa

from dictionary import sync
from models import metadata


revision = '0022'
down_revision = '0021'
branch_labels = None
depends_on = None

SCHEMAS = ('core', 'stg')
FD = 'adm.FieldDefinition'
COLLATION = 'Latin1_General_100_CI_AS_SC'
RENAMED = {'DefaultProcurement': 'DefaultSupplyType', 'AssemblyScrapPct': 'ScrapRatio', 'IsProjectTracked': 'IsCustomTracked'}
REMOVED = frozenset({'ProductionLeadTimeDays', 'Ownership'})

MRP = 'MRP grubu; planlama parametreleri aynı olan malzemeleri gruplar'
NEW_COLUMNS = (
    ('MaterialType', sa.Unicode(length=50), 'Malzeme tipi'),
    ('Brand', sa.Unicode(length=50), 'Marka'),
    ('PlannerCode', sa.Unicode(length=50), 'Planlamacı'),
    ('MRPGroup', sa.Unicode(length=50), MRP),
    ('IsActive', sa.Boolean(), 'Aktif'),
    ('IsSubcontractable', sa.Boolean(), 'Fasona verilebilir'),
    ('IsCustomerSupplied', sa.Boolean(), 'Müşteri temin malzemesi'),
    ('StockCoverageDays', sa.Numeric(precision=9, scale=2), 'Gün cinsinden güvenlik stoğu'),
    ('QtyPerBox', sa.Numeric(precision=18, scale=4), 'Temel birimde kutu içi miktar'),
    ('QtyPerPallet', sa.Numeric(precision=18, scale=4), 'Temel birimde palet içi miktar'),
)
CUSTOM = 'Malzeme ortak havuzdan değil, belli bir talebe (proje, müşteri ya da sipariş) ayrılmış olarak takip edilir; hangi talebe ayrıldığı talep kaydından gelir'
OLD_TRACKED = {'core': 'Proje bazlı takip; değilse her zaman ortak', 'stg': 'Proje bazlı takip edilir mi (değilse her zaman ortak)'}
OLD_OWNERSHIP = {'core': 'Sahiplik: Kendi | Müşteri (müşteri temin malzemesi)', 'stg': 'Kendi | Müşteri (müşteri temin malzemesi)'}
OLD_SCRAP, NEW_SCRAP = 'Montaj firesi (%)', 'Oran olarak fire (0,05 = %5)'
WIDE = sa.Numeric(precision=10, scale=4)   # dönüşüm sırasında hassasiyet kaybolmasın


def _rewrite_views(names, removed):
    """Kayıtlı görünüm alan adıyla saklanır; bilinmeyen alan görünümü bozar."""
    if context.is_offline_mode():
        return
    conn = op.get_bind()
    for id_, text in conn.execute(sa.text("SELECT Id, Definition FROM adm.TableView WHERE ListName = N'materials'")).all():
        d = json.loads(text)
        keep, name = (lambda f: f not in removed), (lambda f: names.get(f, f))
        d['columns'] = [{**c, 'field': name(c['field'])} for c in d.get('columns', []) if keep(c['field'])]
        d['pinned'] = min(d.get('pinned', 0), len(d['columns']))
        for key in ('sort', 'filters'):
            d[key] = [{**i, 'field': name(i['field'])} for i in d.get(key, []) if keep(i['field'])]
        d['group_by'] = [name(f) for f in d.get('group_by', []) if keep(f)]
        d['aggregates'] = {name(f): ({**s, 'weight': name(s['weight'])} if s.get('weight') else s)
                           for f, s in d.get('aggregates', {}).items() if keep(f) and keep(s.get('weight'))}
        rules = []
        for r in d.get('rules', []):
            ref = (r.get('condition') or {}).get('field_ref')
            if keep(r['field']) and keep(ref):
                condition = {**r['condition'], 'field_ref': name(ref)} if ref else r.get('condition')
                rules.append({**r, 'field': name(r['field']), 'condition': condition})
        d['rules'] = rules
        conn.execute(sa.text("UPDATE adm.TableView SET Definition = :d WHERE Id = :i"), {'d': json.dumps(d, ensure_ascii=False), 'i': id_})


def _rename(pairs):
    for schema in SCHEMAS:
        for old, new in pairs:
            op.alter_column('Material', old, new_column_name=new, schema=schema)


def _scale(column, schema, final, operator):
    op.alter_column('Material', column, existing_type=sa.Numeric(precision=6, scale=2 if final.scale == 4 else 4), type_=WIDE, existing_nullable=True, schema=schema)
    if schema == 'core':
        op.execute(f"UPDATE core.Material SET {column} = {column} {operator} 100")
    op.alter_column('Material', column, existing_type=WIDE, type_=final, existing_nullable=True, schema=schema)


def upgrade():
    op.drop_index('UX_Material_Code', table_name='Material', schema='core', mssql_where=sa.text('VersionTo IS NULL'))
    op.drop_index('UX_Material_Code', table_name='Material', schema='stg')
    for schema in SCHEMAS:
        for name, type_, comment in NEW_COLUMNS:
            op.add_column('Material', sa.Column(name, type_, nullable=True, comment=comment), schema=schema)
    op.execute("UPDATE core.Material SET IsCustomerSupplied = CASE Ownership WHEN N'Müşteri' THEN 1 WHEN N'Kendi' THEN 0 END")
    _rename(RENAMED.items())
    for schema in SCHEMAS:
        _scale('ScrapRatio', schema, sa.Numeric(precision=6, scale=4), '/')
        op.alter_column('Material', 'ScrapRatio', existing_type=sa.Numeric(precision=6, scale=4), comment=NEW_SCRAP, existing_comment=OLD_SCRAP, existing_nullable=True, schema=schema)
        op.alter_column('Material', 'IsCustomTracked', existing_type=sa.Boolean(), comment=CUSTOM, existing_comment=OLD_TRACKED[schema], existing_nullable=True, schema=schema)
    op.drop_column('Material', 'Ownership', schema='core', mssql_drop_default=True)
    op.drop_column('Material', 'Ownership', schema='stg')
    for schema in SCHEMAS:
        op.drop_column('Material', 'ProductionLeadTimeDays', schema=schema)
    op.create_index('UX_Material_LocationId_Code', 'Material', ['LocationId', 'Code'], unique=True, schema='core', mssql_where=sa.text('VersionTo IS NULL'))
    op.create_index('UX_Material_LocationCode_Code', 'Material', ['LocationCode', 'Code'], unique=True, schema='stg')
    # Sözlük: elle verilen etiket yeni adda kalır; sync silmez, yalnız ekler ve docs kolonlarını günceller.
    for old, new in RENAMED.items():
        op.execute(f"UPDATE {FD} SET FieldName = N'{new}' WHERE TableName = N'Material' AND FieldName = N'{old}'")
    op.execute(f"DELETE FROM {FD} WHERE TableName = N'Material' AND FieldName IN (N'Ownership', N'ProductionLeadTimeDays')")
    if not context.is_offline_mode():  # bağlantısız SQL betiğinde satırlar yazılmaz; ilk bağlantılı geçişte kurulur
        sync(op.get_bind(), metadata)
    _rewrite_views(RENAMED, REMOVED)


def downgrade():
    _rewrite_views({new: old for old, new in RENAMED.items()}, frozenset(name for name, _, _ in NEW_COLUMNS))
    names = ', '.join(f"N'{name}'" for name, _, _ in NEW_COLUMNS)
    op.execute(f"DELETE FROM {FD} WHERE TableName = N'Material' AND FieldName IN ({names})")
    for old, new in RENAMED.items():
        op.execute(f"UPDATE {FD} SET FieldName = N'{old}' WHERE TableName = N'Material' AND FieldName = N'{new}'")
    op.execute(f"UPDATE {FD} SET StandardLabel = N'{OLD_SCRAP}', Description = N'{OLD_SCRAP}' WHERE TableName = N'Material' AND FieldName = N'AssemblyScrapPct'")
    op.execute(f"UPDATE {FD} SET StandardLabel = N'Proje bazlı takip', Description = N'{OLD_TRACKED['core']}' WHERE TableName = N'Material' AND FieldName = N'IsProjectTracked'")
    op.execute(f"INSERT INTO {FD} (TableName, FieldName, FieldClass, DefaultValue, StandardLabel, Description) VALUES "
               f"(N'Material', N'Ownership', N'Ana veri', N'Kendi', N'Sahiplik', N'{OLD_OWNERSHIP['core']}'), "
               "(N'Material', N'ProductionLeadTimeDays', N'Ana veri', NULL, N'Üretim süresi (gün)', N'Üretim süresi (gün)')")
    op.drop_index('UX_Material_LocationCode_Code', table_name='Material', schema='stg')
    op.drop_index('UX_Material_LocationId_Code', table_name='Material', schema='core', mssql_where=sa.text('VersionTo IS NULL'))
    for schema in SCHEMAS:
        op.add_column('Material', sa.Column('ProductionLeadTimeDays', sa.Numeric(precision=9, scale=2), nullable=True, comment='Üretim süresi (gün)'), schema=schema)
    op.add_column('Material', sa.Column('Ownership', sa.NVARCHAR(length=10, collation=COLLATION), nullable=True, comment=OLD_OWNERSHIP['stg']), schema='stg')
    op.add_column('Material', sa.Column('Ownership', sa.NVARCHAR(length=10, collation=COLLATION), server_default=sa.text("N'Kendi'"), nullable=True, comment=OLD_OWNERSHIP['core']), schema='core')
    op.execute("UPDATE core.Material SET Ownership = CASE WHEN IsCustomerSupplied = 1 THEN N'Müşteri' ELSE N'Kendi' END")
    for schema in SCHEMAS:
        op.alter_column('Material', 'IsCustomTracked', existing_type=sa.Boolean(), comment=OLD_TRACKED[schema], existing_comment=CUSTOM, existing_nullable=True, schema=schema)
        op.alter_column('Material', 'ScrapRatio', existing_type=sa.Numeric(precision=6, scale=4), comment=OLD_SCRAP, existing_comment=NEW_SCRAP, existing_nullable=True, schema=schema)
        _scale('ScrapRatio', schema, sa.Numeric(precision=6, scale=2), '*')
    _rename([(new, old) for old, new in RENAMED.items()])
    for schema in SCHEMAS:
        for name, _, _ in reversed(NEW_COLUMNS):
            op.drop_column('Material', name, schema=schema)
    op.create_index('UX_Material_Code', 'Material', ['Code'], unique=True, schema='stg')
    op.create_index('UX_Material_Code', 'Material', ['Code'], unique=True, schema='core', mssql_where=sa.text('VersionTo IS NULL'))
