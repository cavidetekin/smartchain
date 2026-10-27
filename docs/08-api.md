# API kuralları

Uygulama iskeletinin (adım 0.3) ve iş kuyruğunun (adım 0.4) kuralları. Yeni her uç nokta bunlara uyar.

## Katmanlar

| Katman | Klasör | Görev |
|---|---|---|
| Uç nokta | `app/api/routers/` | HTTP isteğini karşılar, girdiyi doğrular, servisi çağırır. İş kuralı içermez. |
| Servis | `app/api/services/` | İş kuralları. Veritabanına doğrudan değil, repository üzerinden erişir. |
| Repository | `app/api/repositories/` | Veritabanı sorguları. Yalnız `core`, `param`, `planning`, `adm` okunur ve yazılır; `stg` yalnız ETL'de (K-58). |
| İş kuyruğu | `app/jobs/` | `adm.Job` sorguları; API ile motor servisinin ortak kütüphanesi. İş kuyruğu servisi repository yerine bunu kullanır. |
| Motor | `app/engine/` | Motor arayüzü, sahte motor, motor servisi (`docs/09-motor-arayuzu.md`). API motoru çağırmaz; plan hesabını `submit_plan_run` ile kuyruğa koyar. |

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
- Log: konsol ve `logs/smartchain.log` (her gece döner, 30 gün saklanır). Her satırda takip numarası bulunur. Motor servisi kendi dosyasına yazar (`logs/engine.log`).

## Ayarlar

Ortam değişkenleri (`SMARTCHAIN_` önekiyle) ya da kök klasördeki `.env` dosyası (`.env.example` örnek):

| Ayar | Varsayılan |
|---|---|
| `SMARTCHAIN_DB_URL` | localhost, `Smartchain` veritabanı, Windows oturumu |
| `SMARTCHAIN_LOG_DIR` | `logs` |
| `SMARTCHAIN_LOG_LEVEL` | `INFO` |
| `SMARTCHAIN_ENABLE_DOCS` | `false` |
| `SMARTCHAIN_JOB_WATCH_SECONDS` | `1.0` · iş kuyruğunu izleme aralığı; `0` izlemeyi kapatır |

## Uç noktalar

| Adres | Ne | Durum |
|---|---|---|
| `GET /api/health` | Uygulama sürümü, veritabanı bağlantısı, şema sürümü (beklenen ile karşılaştırma). Sorun varsa 503 ve Türkçe açıklama. Sistem sağlığı ekranının (24) çekirdeği. | uygulandı (0.3) |
| `GET /api/jobs?user_id=` | Çalışan, sıradaki ve son 24 saatte biten işler (önce çalışan, sonra sıra); kanal sayaçları (çalışan, sırada, sınır). `user_id` verilirse yalnız o kullanıcının işleri (geçici, A-36). Bağlantı kopunca istemcinin son durumu sorguladığı yer (fonksiyon 48). | uygulandı (0.4) |
| `GET /api/jobs/{id}` | İşin durumu, ilerlemesi, sıra numarası, süresi, `is_stale` (kalp atışı eşiği aşıldı). Yoksa 404 `job_not_found`. | uygulandı (0.4) |
| `POST /api/jobs/{id}/cancel` | Sıradaki işi iptal eder. Çalışan iş 409 `job_not_cancellable` (durdurma motorda, fonksiyon 93). Yetki kuralı 2.2'de. | uygulandı (0.4) |
| `GET /api/data-versions/current` | En son veri versiyonu: Id, lokasyon kodu, oluşma zamanı, tam/kısmi, sentetik mi. Yoksa 404 `no_data_version`. Bağlam çubuğunun veri versiyonu (docs/12). | uygulandı (1.1) |
| `WS /api/ws?user_id=` | Anlık bildirim kanalı (fonksiyon 48). Kullanıcı şimdilik parametreyle (A-36). | uygulandı (0.4) |

İş eklemek için uç nokta yoktur: işi ilgili fonksiyon (yeniden hesap 46, yükleme…) kendi servisinden `app.jobs.queue.enqueue` ile ekler.

## İş kuyruğu (fonksiyon 47, 93)

- Durumlar: Sırada → Çalışıyor → Bitti | Hata; Sırada → İptal (K-67).
- Kanal sınırı: etkileşim 3, gece 2 (`adm.SystemSetting`: `JobLimitInteractive`, `JobLimitNight`). İş alma uygulama kilidiyle sıraya konur; sıra önce öncelik, sonra istek sırası (K-68).
- Çalışan iş kalp atışı yazar. `JobHeartbeatTimeoutSeconds` (120) boyunca gelmezse takılmış sayılır; `JobMaxAttempts` (2) dolana kadar yeniden sıraya döner, sonra Hata. Eski deneme işi artık yazamaz (her yazma deneme numarasıyla).

## WebSocket mesajları (fonksiyon 48)

API, `adm.Job`'u `UpdatedAt` ile izler ve değişen işi sahibinin bağlantılarına iter (K-69). Sıradaki işlerin sırası değişince onlara da mesaj gider. Ara durumlar izleme aralığında birleşebilir; istemci her mesajı işin son hali olarak alır.

```json
{"type": "hello", "user_id": 3}
{"type": "job", "job": {"id": 61, "job_type": "Çalışma", "channel": "Etkileşim", "status": "Çalışıyor",
 "progress": "Çözülüyor", "queue_position": null, "attempt": 1, "is_stale": false, "...": "GET /api/jobs/{id} ile aynı alanlar"}}
{"type": "pong"}
```

İstemci `ping` metni gönderirse `pong` döner (bağlantı denetimi).

Geliştirme demosu: API açıkken `python scripts/job_demo.py --url ws://127.0.0.1:8000/api/ws`; demo kullanıcısı adına iş ekler, sahte işçi gibi çalıştırır ve gelen bildirimleri yazdırır.
