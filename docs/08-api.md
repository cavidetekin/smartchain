# API kuralları

Uygulama iskeletinin (adım 0.3) kuralları. Yeni her uç nokta bunlara uyar.

## Katmanlar

| Katman | Klasör | Görev |
|---|---|---|
| Uç nokta | `app/api/routers/` | HTTP isteğini karşılar, girdiyi doğrular, servisi çağırır. İş kuralı içermez. |
| Servis | `app/api/services/` | İş kuralları. Veritabanına doğrudan değil, repository üzerinden erişir. |
| Repository | `app/api/repositories/` | Veritabanı sorguları. Yalnız `core`, `param`, `planning`, `adm` okunur ve yazılır; `stg` yalnız ETL'de (K-58). |

## Adresler

- Bütün uç noktalar `/api` ile başlar. Adlar İngilizce ve küçük harf (`/api/health`, ileride `/api/materials`).
- API belgesi `/api/docs` yalnız geliştirmede açılır (`SMARTCHAIN_ENABLE_DOCS=true`); dışarıdan JavaScript yüklediği için kurulum paketinde kapalıdır (kapalı ağ kuralı).

## Hata cevabı

Her hata aynı biçimde döner; mesaj Türkçe ve kullanıcıya gösterilebilir:

```json
{"error": {"code": "material_not_found", "message": "Malzeme bulunamadı.", "trace_id": "445ecdbb3634", "details": []}}
```

- **İş kuralı hatası:** servis `AppError(code, message, status_code)` fırlatır.
- **Girdi hatası (422):** `code = "validation"`; `details` her hatalı alanı (`field`, `problem`) listeler.
- **Beklenmeyen hata (500):** kullanıcıya yalnız takip numarası gösterilir; ayrıntı ve yığın izi loga yazılır. Kapalı ağda destek bu numarayla verilir.

## Takip numarası ve log

- Her isteğe 12 karakterlik bir takip numarası verilir; cevapta `X-Trace-Id` başlığında ve hata gövdesinde yer alır.
- Log: konsol ve `logs/smartchain.log` (her gece döner, 30 gün saklanır). Her satırda takip numarası bulunur.

## Ayarlar

Ortam değişkenleri (`SMARTCHAIN_` önekiyle) ya da kök klasördeki `.env` dosyası (`.env.example` örnek):

| Ayar | Varsayılan |
|---|---|
| `SMARTCHAIN_DB_URL` | localhost, `Smartchain` veritabanı, Windows oturumu |
| `SMARTCHAIN_LOG_DIR` | `logs` |
| `SMARTCHAIN_LOG_LEVEL` | `INFO` |
| `SMARTCHAIN_ENABLE_DOCS` | `false` |

## Uç noktalar

| Adres | Ne | Durum |
|---|---|---|
| `GET /api/health` | Uygulama sürümü, veritabanı bağlantısı, şema sürümü (beklenen ile karşılaştırma). Sorun varsa 503 ve Türkçe açıklama. Sistem sağlığı ekranının (24) çekirdeği. | uygulandı (0.3) |
