"""0085 · Plan fikstürü (K-205): iki plan tablosunun açıklaması

Malzeme hareketleri ve kapasite yükleri artık türetilir (`app/planning/derive.py`); tablo açıklamalarındaki "türetme 8.0'da" ifadesi güncellenir.
Veri ve şema değişmez.

Revision ID: 0085
Revises: 0084
Create Date: 2026-11-27
"""
from alembic import op
import sqlalchemy as sa

revision = '0085'
down_revision = '0084'
branch_labels = None
depends_on = None


def _table_comment(schema, table, text):
    """SQL Server'da var olan tablo açıklaması (MS_Description) güncellenir."""
    op.execute(sa.text("EXEC sp_updateextendedproperty @name = N'MS_Description', @value = :v, @level0type = N'SCHEMA', @level0name = :s, "
                       "@level1type = N'TABLE', @level1name = :t").bindparams(v=text, s=schema, t=table))


def upgrade():
    _table_comment('planning', 'MaterialTransaction', "Malzeme hareketleri (K-202): planın bütün + ve − hareketleri tek tabloda; karar tablolarından ve ERP'den gelen arzdan türetilir, elle değişmez. Türetme `app/planning/derive.py`'dedir (K-205; motor ve fikstür ortak, yazıcı karar satırlarından sonra çağırır). Ana hareket → Hareket türü: Stok (Stok · Kalitedeki stok) · Satın alma (Satın alma siparişi · Satın alma planı) · Üretim (Üretim siparişi · Üretim planı) · Talep (Kesin sipariş · Teklif · Beklemedeki sipariş · Tahmin) · Üretim ihtiyacı (Üretim siparişi ihtiyacı · Üretim planı ihtiyacı) · Transfer (Alokasyon transferi; iki satır: genelden −, özele +). Tek tanım `app/planning/movements.py`. No: Üretim planı ve Satın alma planı: tedarik planı no · Üretim siparişi ve Satın alma siparişi: sipariş no · Kesin sipariş, Teklif, Beklemedeki sipariş: satış sipariş no · Üretim ihtiyacı: ihtiyacı doğuran üretimin no'su · Stok, Tahmin, Alokasyon transferi: boş.")
    _table_comment('planning', 'CapacityLoad', "Kapasite yükleri (K-202): tedarik planı kaydı × kaynak grubu × dönem bazında yük; yalnız yükler (plan ve yük grup düzeyindedir, K-180). Sistem rotadan hesaplar (türetme `app/planning/derive.py`, K-205); rotada aynı gruba düşen operasyonlar toplanır. Kapasite (toplam, duruş, kullanılabilir) saklanmaz, kapasite hesabından okunur (K-184); ek mesai `PlannedOvertime`'dadır.")


def downgrade():
    _table_comment('planning', 'MaterialTransaction', "Malzeme hareketleri (K-202): planın bütün + ve − hareketleri tek tabloda; karar tablolarından ve ERP'den gelen arzdan türetilir, elle değişmez. Türetme 8.0'da yazılır; o güne kadar satırları sahte motorun örneği verir. Ana hareket → Hareket türü: Stok (Stok · Kalitedeki stok) · Satın alma (Satın alma siparişi · Satın alma planı) · Üretim (Üretim siparişi · Üretim planı) · Talep (Kesin sipariş · Teklif · Beklemedeki sipariş · Tahmin) · Üretim ihtiyacı (Üretim siparişi ihtiyacı · Üretim planı ihtiyacı) · Transfer (Alokasyon transferi; iki satır: genelden −, özele +). Tek tanım `app/planning/movements.py`. No: Üretim planı ve Satın alma planı: tedarik planı no · Üretim siparişi ve Satın alma siparişi: sipariş no · Kesin sipariş, Teklif, Beklemedeki sipariş: satış sipariş no · Üretim ihtiyacı: ihtiyacı doğuran üretimin no'su · Stok, Tahmin, Alokasyon transferi: boş.")
    _table_comment('planning', 'CapacityLoad', "Kapasite yükleri (K-202): tedarik planı kaydı × kaynak grubu × dönem bazında yük; yalnız yükler (plan ve yük grup düzeyindedir, K-180). Sistem rotadan hesaplar (türetme 8.0'da; o güne kadar satırları sahte motorun örneği verir); rotada aynı gruba düşen operasyonlar toplanır. Kapasite (toplam, duruş, kullanılabilir) saklanmaz, kapasite hesabından okunur (K-184); ek mesai `PlannedOvertime`'dadır.")
