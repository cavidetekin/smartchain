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

## Liste sorgusu (K-87)

Bütün tablolar (ana veri, plan, rapor) aynı sözleşmeyle okunur. Filtre, sıralama ve parça parça yükleme sunucuda yapılır (U-21); ön yüzdeki ortak tablo bileşeni (docs/12) bu sözleşmeyi kullanır. Her liste sunucuda bir liste tanımıdır (`app/api/lists/`): tablo, alanlar ve sırası, varsayılan görünür alanlar, varsayılan sıralama.

### Kolonlar · `GET /api/<liste>/columns`

```json
[{"field": "MaterialLevel", "label": "Malzeme seviyesi", "type": "text", "filter": "list",
  "values": ["Hammadde", "Yarı mamul", "Nihai ürün"], "values_from_server": false, "decimals": null, "default_visible": true}]
```

- **Etiket:** docs/02 AÇIKLAMA'sından üretilir; FieldDefinition.Label varsa onu kullanır. Ek alan (K-59) yalnız Label'ı varsa listelenir (K-88).
- **Tip** (`type`) veritabanı tipinden gelir: `text`, `integer`, `number` (`decimals` ile), `bool`, `date`, `datetime`.
- **Filtre tipi** (`filter`) tipten gelir: metin → `text`; değer listeli metin (K-80) ve `bool` → `list` (değerler `values`'ta; bool için Evet / Hayır = `true` / `false`); liste tanımında işaretli kodlu alanlar → `list`, değerler `values` uç noktasından (`values_from_server: true`); sayı → `number`; tarih → `date`.

### Sorgu · `POST /api/<liste>/query`

```json
{"fields": ["Code", "Name", "MaterialLevel"],
 "sort": [{"field": "MaterialLevel", "dir": "asc"}, {"field": "Code", "dir": "desc"}],
 "filters": [{"field": "Name", "op": "contains", "value": "mil"},
             {"field": "MaterialLevel", "op": "in", "values": ["Hammadde"]},
             {"field": "SafetyStock", "op": "between", "min": 10, "max": 100},
             {"field": "UpdatedAt", "op": "relative", "value": "this_week"}],
 "offset": 0, "limit": 100}
```

Cevap: `{"rows": [{"Id": 7, "Code": "…", …}], "offset": 0, "filtered": 120, "total": 840}`. `Id` her satırda vardır. `filtered` filtreli sayı, `total` filtresiz sayıdır; arayüzdeki "120 / 840" sayacı bunlardır (U-12). Sayılar JSON sayısı, tarihler ISO döner (`2026-10-27`); zamanlı alanlar veritabanında UTC tutulur ve saat dilimiyle döner (`2026-10-27T09:20:00+00:00`), tarih filtresinin gün sınırı yerel gece yarısıdır.

| Filtre tipi | `op` | Alanlar |
|---|---|---|
| Metin | `contains`, `not_contains`, `equals`, `starts_with` | `value` |
| Liste | `in` | `values` (en az bir değer) |
| Sayı | `between` (`min`, `max`; biri boş olabilir), `eq`, `gt`, `lt` | `min`/`max` ya da `value` |
| Tarih | `between` (`from`, `to`; ISO tarih, biri boş olabilir), `relative` | `value`: `this_week` (bu hafta), `next_4_weeks` (bu haftanın başından dört hafta) |

- Birden fazla filtre birlikte (VE) uygulanır. `empty` (boş değer, U-13) 1.4'te eklenir.
- **Hafta:** ISO hafta, Pazartesi başlar; "bugün" API sunucusunun yerel tarihidir (kurulum müşterinin sunucusunda, yerel saat diliminde).
- **Türkçe:** metin karşılaştırma ve sıralama `Turkish_100_CI_AS` ile; büyük/küçük harf duyarsız, "İ/i" ve "I/ı" doğru.
- **Güvenlik:** alan ve operatör liste tanımındaki beyaz listeden; değerler parametreyle gider; `LIKE` içinde `%`, `_`, `[` düz karakterdir.
- **Kararlı parçalar:** sıralamanın sonuna her zaman `Id` eklenir; parçalar örtüşmez. Sıralama verilmezse liste tanımındaki varsayılan kullanılır.
- **Sınırlar:** `limit` varsayılan 100, en çok 500; `offset` ≥ 0.
- **Hatalar:** bilinmeyen alan, operatör, eksik değer ya da sınır dışı `limit` → 422 `validation` (`details`: `field`, `problem`); veritabanı yoksa 503 `database_unavailable`; veri versiyonu yoksa 404 `no_data_version`.
- **Versiyon:** liste güncel veri versiyonunu okur (`VersionFrom ≤ v` ve `VersionTo` boş ya da `≥ v`; motorun okuduğu koşulla aynı).

### Değerler · `POST /api/<liste>/values`

Liste filtresinin seçenekleri: `{"field": "MaterialGroup", "search": "döv", "filters": [...]}` → `[{"value": "Dövme", "count": 12}, …]`. Diğer filtreler uygulanmış hâldeki ilk 100 farklı değer, değere göre sıralı; `search` içerir araması yapar. Yalnız `filter: "list"` alanlarda çalışır.

## Uç noktalar

| Adres | Ne | Durum |
|---|---|---|
| `GET /api/health` | Uygulama sürümü, veritabanı bağlantısı, şema sürümü (beklenen ile karşılaştırma). Sorun varsa 503 ve Türkçe açıklama. Sistem sağlığı ekranının (24) çekirdeği. | uygulandı (0.3) |
| `GET /api/jobs?user_id=` | Çalışan, sıradaki ve son 24 saatte biten işler (önce çalışan, sonra sıra); kanal sayaçları (çalışan, sırada, sınır). `user_id` verilirse yalnız o kullanıcının işleri (geçici, A-36). Bağlantı kopunca istemcinin son durumu sorguladığı yer (fonksiyon 48). | uygulandı (0.4) |
| `GET /api/jobs/{id}` | İşin durumu, ilerlemesi, sıra numarası, süresi, `is_stale` (kalp atışı eşiği aşıldı). Yoksa 404 `job_not_found`. | uygulandı (0.4) |
| `POST /api/jobs/{id}/cancel` | Sıradaki işi iptal eder. Çalışan iş 409 `job_not_cancellable` (durdurma motorda, fonksiyon 93). Yetki kuralı 2.2'de. | uygulandı (0.4) |
| `GET /api/data-versions/current` | En son veri versiyonu: Id, lokasyon kodu, oluşma zamanı, tam/kısmi, sentetik mi. Yoksa 404 `no_data_version`; veritabanına bağlanılamazsa 503 `database_unavailable`. Bağlam çubuğunun veri versiyonu (docs/12). | uygulandı (1.1) |
| `GET /api/materials/columns` · `POST /api/materials/query` · `POST /api/materials/values` | Malzeme listesi, liste sorgu sözleşmesiyle (K-87). Şimdilik tablo bileşeni denemesi (`/tablo`); malzeme ekranı 6.1'de. | uygulandı (1.3) |
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
