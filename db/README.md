# db

Veritabanı şeması ve geçişler. Şema docs'tan üretilir (K-64); `models.py` elle değiştirilmez.

| Dosya | Ne |
|---|---|
| `generate.py` | docs/02 ve docs/03'ü okur, `models.py` ve `docs/07-veritabani.md` yazar |
| `models.py` | Üretilmiş SQLAlchemy tanımı (97 tablo, 5 şema) |
| `alembic.ini`, `migrations/` | Geçişler; `versions/0001_ilk_sema.py` ilk şema |
| `sql/` | Geçişlerin SQL karşılığı (bilgi amaçlı; SSMS'te de çalıştırılabilir) |

## Geliştirme bilgisayarında kurulum (Windows)

1. **SQL Server 2025 Developer** kur (ücretsiz, tam sürüm; indirme sayfasında "Developer" kutusu, deneme sürümü değil). Kurulum tipi Basic. Kurulumda varsayılan instance (`MSSQLSERVER`) yeterli. Yönetim için **SQL Server Management Studio (SSMS)** kur.
2. **ODBC Driver 18 for SQL Server** kur (Python'un SQL Server'a bağlanması için).
3. **Python 3.12** kur; repo klasöründe: `pip install -r requirements.txt`
4. SSMS'te veritabanını aç:
   ```sql
   CREATE DATABASE Smartchain COLLATE Latin1_General_100_CI_AS_SC;
   ```
   Türkçe karakterler nvarchar alanlarda sorunsuz saklanır. Türkçe sıralama gereken sorgularda `COLLATE Turkish_100_CI_AS` kullanılır.
5. Bağlantı varsayılan olarak `localhost` üzerindeki `Smartchain` veritabanına Windows oturumunla gider. Farklıysa `SMARTCHAIN_DB_URL` ortam değişkenini ayarla, örnek:
   `mssql+pyodbc://@localhost/Smartchain?driver=ODBC+Driver+18+for+SQL+Server&trusted_connection=yes&TrustServerCertificate=yes`
6. Şemayı kur: `alembic -c db/alembic.ini upgrade head`
7. Kontrol (SSMS): 5 şema (`stg`, `core`, `param`, `planning`, `adm`), 97 tablo ve `dbo.alembic_version`. Tablo ve kolon özelliklerinde Türkçe açıklamalar görünür.
8. Geri alma testi: `alembic -c db/alembic.ini downgrade base`, ardından yeniden `upgrade head`.

## Değişiklik akışı

docs'ta tabloyu ya da alanı değiştir → `python db/generate.py` → `alembic -c db/alembic.ini revision --autogenerate -m "kısa açıklama"` → oluşan geçişi gözden geçir → `upgrade head`.
