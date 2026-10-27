# Smartchain

Tedarik zincirindeki orta ölçekli, sipariş odaklı üreticiler için ERP'den bağımsız üretim planlama aracı. ERP'deki siparişi, stoğu, ürün ağacını ve kaynak kapasitesini alır; kapasite ve malzeme kısıtları altında teslimi en iyileyen planı optimizasyonla (LP / MILP) hesaplar; planlamacıya karşılaştırılabilir senaryolar, düzenlenebilir bir plan ve nedenleriyle uyarılar verir.

## Çalışma kuralları

- **Tek kaynak `docs/`.** Değişiklik önce docs'ta (karar, sözleşme, prensip), sonra kodda (K-54). Docs ile kod çelişirse dur ve sor.
- **Sıra `GELISTIRME_ADIMLARI.md`.** Adımlar sırayla, ekran ekran ve fonksiyon fonksiyon ilerler. Sıradaki adım dışında iş yapma; kapsam büyütme.
- **Motor en son.** Optimizasyon, çözüm motoru ve simülasyonlar Aşama 10'da. O zamana kadar ekranlar plan fikstürüyle ve sahte motorla çalışır; motor arayüzü baştan sabittir.
- **Bitti tanımı:** prensip slaytı ve mockup okundu → API, ekran ve test yazıldı → sentetik veriyle çalışıyor → docs'ta "uygulandı" işlendi → demo yapıldı. Biri eksikse adım kapanmaz (K-55).
- **Kararlar numaralı.** Karar K-n, açık konu A-n (`docs/00-kararlar.md`). Kodda ve commit mesajında bu numaralara atıf yap.

## Mimari (özet)

- Kurulum müşterinin sunucusunda, internete kapalı ağda; uzaktan erişim yok. Kodda ve pakette internet bağımlılığı olmaz (CDN, çevrimiçi lisans, dış servis yok).
- Yalnız Windows Server. Python; API FastAPI, IIS arkasında Windows servisi. Motor ayrı Windows servisi, her iş kendi sürecinde.
- Ürüne ayrılmış ayrı MS SQL Server instance'ı. İş kuyruğu SQL Server'daki Job tablosu; ek bileşen yok.
- Modelleme katmanı çözücüden bağımsız (aday HiGHS). LLM Faz 1'de kapalı.
- Roller: sistem sahibi, admin, key user, end user (end user yalnız görüntüler ve Excel'e indirir).

## Veri

- **İki katman (K-58).** Entegrasyon tabloları (`stg.*`) ERP'nin dilidir: Id yok, ilişkiler kodla (MaterialCode, LocationCode…). Ana tablolar Id + Code taşır; motor, ekranlar ve raporlar yalnız ana tabloları okur.
- **ETL sırası:** Staging'e çekme (API, SQL arayüz tabloları, Excel) → yapısal doğrulama → veri kuralları → aktarım filtresi (A-34) → referans kontrolü ve kod→Id → değer önceliği (ERP, kural, elle, varsayılan; ERP değeri her zaman saklanır) → versiyonlu yazma (VersionFrom / VersionTo).
- **Ek alanlar (K-59):** ana veride AdditionalText1–7 ve AdditionalNumber1–3, yapı ve işlem verisinde AdditionalText1–3 ve AdditionalNumber1–2; etiketleri FieldDefinition'da.
- Tablo ve alan adları `docs/02-veri-modeli.md` ve `docs/03-entegrasyon.md` ile birebir; sözleşme alan adlarını değiştirme.
- **Şemalar (K-62):** `stg` entegrasyon, `core` ana veri ve işlem verisi, `param` parametreler, `planning` plan çıktıları, `adm` veri yönetimi ve sistem. Aynı ad iki katmanda: `stg.Material` → `core.Material`.
- **Versiyonlu tablolar (K-63):** birincil anahtar `Id + VersionFrom`; `Id` kaydın bütün versiyonlarında aynı. Versiyonlu tabloya fiziksel FK yok, bütünlüğü aktarım sağlar; tekillik yalnız güncel kayıtta (`VersionTo IS NULL`).
- **Şema docs'tan üretilir (K-64):** `db/models.py` ve `docs/07-veritabani.md` elle değiştirilmez. Sıra: docs → `python db/generate.py` → `alembic -c db/alembic.ini revision --autogenerate -m "..."` → geçişi gözden geçir.

## Arayüz

- U-1…U-23 bağlayıcıdır (`docs/04-arayuz-prensipleri.md`). Ekran ağırlıkla nötr, indigo aksiyon, durum renkleri yalnız durum için; her tablo sıralanır, filtrelenir, alanları açılıp kapanır; ana tablo ekrana sığar, kenar menü daraltılır; varsayılan yazı sıkıdır, kullanıcı dört boyuttan birini seçer.
- Yazı tipleri Instrument Sans ve JetBrains Mono, pakete gömülü. Sayı ve tarih Türkçe biçimde.

## Dil ve adlandırma

- Kod, tablo ve alan adları İngilizce; arayüz metinleri ve docs Türkçe.
- Ürün ERP bağımsızdır: kodda, arayüzde ve docs'ta ERP marka adı geçmez.
- Ekran, fonksiyon ve rapor numaraları docs'taki sade numaralardır (ör. ekran 02, fonksiyon 16); "P-KAY-03" gibi kod üretme.

## Faz 1 dışı (dokunma)

Set-up, kalıp, fırın, faz bazlı işçi tüketimi, raf ömrü kuralları (yalnız uyarı var), LLM, çoklu lokasyon, ERP'ye geri yazma, AD / SSO, bulut.

## Docs haritası

| Dosya | İçerik |
|---|---|
| `docs/00-kararlar.md` | Bütün kararlar (K-n) ve açık konular (A-n) |
| `docs/01-mimari.md` | Mimari kararlar (MDD 19) |
| `docs/02-veri-modeli.md` | Ana tablolar ve alanlar (MDD 21) |
| `docs/03-entegrasyon.md` | Entegrasyon tasarımı ve `stg.*` tabloları (MDD 26) |
| `docs/04-arayuz-prensipleri.md` | U-1…U-23 (MDD 23) |
| `docs/05-ekranlar.md` | 25 ekran ve ekran mockupları (MDD 24) |
| `docs/06-fonksiyonlar.md` | 98 fonksiyonun çalışma prensipleri ve mockupları (MDD 24) |
| `docs/07-veritabani.md` | Veritabanı haritası: şemalar ve tablolar (üretilmiş) |
| `docs/08-api.md` | API kuralları: katmanlar, adresler, hata cevabı, log, ayarlar |
| `docs/mockups/` | Mockup görselleri |

Motor (MDD 18), raporlar (25), kurulum (27) ve fazlama (28) ilgili aşamaya gelince eklenir.

## Komutlar

```
pip install -r requirements.txt
python db/generate.py                              # docs → db/models.py, docs/07-veritabani.md
alembic -c db/alembic.ini upgrade head             # veritabanını güncelle (SMARTCHAIN_DB_URL)
alembic -c db/alembic.ini upgrade head --sql       # bağlantısız: SQL betiğini yazdır
alembic -c db/alembic.ini downgrade -1             # son geçişi geri al
uvicorn app.api.main:app --reload --port 8000      # API'yi başlat (geliştirme)
python -m pytest                                   # testler
```
