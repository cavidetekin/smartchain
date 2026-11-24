"""0071 · Açıklama güncellemeleri: tedarikçi limitinde Sebep iki türde (K-191 demo), alokasyon Faz 1 dışı (K-192)

Yalnız açıklamalar (MS_Description) değişir; kolon, veri ve kısıt değişmez. `param.SupplierLimit.Reason` artık üst limitte de kullanılır;
`param.AllocationRule` Faz 1 dışıdır (tablo durur, hiçbir ekran ve motor okumaz).

Revision ID: 0071
Revises: 0070
Create Date: 2026-11-23
"""
from alembic import context, op
import sqlalchemy as sa

from dictionary import sync
from models import metadata
from frozen import frozen

# Bu geçişin okuduğu tablo ve kolon açıklamaları sabittir: geçişin yazıldığı andaki modelden (commit 71a5004); güncel modelden okunmaz
# (K-197). Boş anahtar tablonun açıklamasıdır.
COMMENTS = {
    'param.SupplierLimit': {
        '': 'Tedarikçi limiti (K-191; problem 39): satın alınan malzemede tedarikçi üst limiti ve tedarikçi kapanışı; iki kayıt türü tek tabloda. Senaryoya bağlı, Baz + fark (K-176). Model kısıtları ekranından girilir.',
        'Id': 'Kayıt kimliği',
        'ScenarioDefinitionId': 'Senaryo',
        'BaseRowId': "Baz'ı izleyen senaryoda Baz'daki satırın farkıysa o satırın kimliği; senaryonun kendi satırında ve Baz'da boş",
        'OverriddenFields': 'Fark satırında senaryonun değiştirdiği alanların adları (virgüllerle çevrili); yalnız bu alanlar senaryodan, gerisi Baz satırından okunur',
        'IsValid': 'Geçersiz yapılan kayıt uygulanmaz; izleyen senaryoda Baz satırı fark satırıyla geçersiz yapılır',
        'LimitType': 'Üst limit | Kapanış',
        'LocationId': 'Lokasyon (malzeme tedarikçisi kaydının lokasyonu)',
        'SupplierId': 'Tedarikçi',
        'MaterialId': 'Malzeme; üst limitte zorunlu, kapanışta boşsa tedarikçinin bütün malzemeleri',
        'ValidFrom': 'Başlangıç',
        'ValidTo': 'Bitiş; üst limitte boşsa süresiz, kapanışta zorunlu',
        'UpperLimit': 'Üst limit (sıfırdan büyük), malzemenin temel biriminde; yalnız üst limitte',
        'LimitPeriod': 'Gün | Hafta | Ay | Çeyrek | Yıl',
        'Reason': 'Sebep (serbest metin, isteğe bağlı); üst limitte ve kapanışta',
        'UpdatedAt': 'Son değişiklik zamanı (UTC)',
        'UpdatedBy': 'Son değiştiren kullanıcı; sentetik ve geçişle gelen satırda boş',
    },
}
FROZEN = frozen(COMMENTS)

revision = '0071'
down_revision = '0070'
branch_labels = None
depends_on = None

OLD_REASON = 'Kapanışın sebebi (serbest metin); yalnız kapanışta'
OLD_ALLOCATION = 'Kapasite alokasyonu: talep sınıfına kaynak grubu ve dönem bazında pay (K-180).'
# Tablo 0072'de kalktı (K-193): açıklaması artık modelden okunamaz, burada sabittir
NEW_ALLOCATION = 'Faz 1 dışı (K-192): kapasite alokasyonu, talep sınıfına kaynak grubu ve dönem bazında pay (K-180). Tablo durur, hiçbir ekran ve motor okumaz.'


def _table_comment(table: str, text: str) -> None:
    """SQL Server'da var olan tablo açıklaması (MS_Description) create_table_comment ile eklenemez; güncellenir."""
    op.execute(sa.text(
        "EXEC sp_updateextendedproperty @name = N'MS_Description', @value = :v, @level0type = N'SCHEMA', "
        "@level0name = N'param', @level1type = N'TABLE', @level1name = :t").bindparams(v=text, t=table))


def upgrade():
    reason = FROZEN.tables['param.SupplierLimit'].c.Reason
    op.alter_column('SupplierLimit', 'Reason', existing_type=sa.Unicode(length=255), existing_nullable=True, comment=reason.comment, existing_comment=OLD_REASON,
                    schema='param')
    _table_comment('AllocationRule', NEW_ALLOCATION)
    if not context.is_offline_mode():  # bağlantısız SQL betiğinde satırlar yazılmaz; ilk bağlantılı geçişte kurulur
        sync(op.get_bind(), metadata)


def downgrade():
    reason = FROZEN.tables['param.SupplierLimit'].c.Reason
    op.alter_column('SupplierLimit', 'Reason', existing_type=sa.Unicode(length=255), existing_nullable=True, comment=OLD_REASON, existing_comment=reason.comment,
                    schema='param')
    _table_comment('AllocationRule', OLD_ALLOCATION)
    if not context.is_offline_mode():
        sync(op.get_bind(), metadata)
