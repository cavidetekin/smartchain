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

## Veritabanı oturumu

- Her istek kendi oturumunu `get_session` bağımlılığından alır; oturum kapanınca bağlantı havuza döner (havuz 5 + 10).
- **Dosya ve akış yanıtı veren uç noktalarda** (dışa aktarım, indirme) oturum yanıt gönderilmeden kapanır:
  `Depends(get_session, scope="function")`. Dosya istemciye akarken bağlantı havuzdadır; yavaş ya da kopan istemci
  bağlantı tutamaz. Akış hâlinde okunan sorgu sonucu (stream_results) hata olsa da kapatılır.
- Test: arka arkaya 30 aktarım ve yarıda kopan indirmeden sonra havuzdan alınmış bağlantı sayısı başlangıçtaki gibi
  (`tests/test_export_connections.py`).

## Adresler

- Bütün uç noktalar `/api` ile başlar. Adlar İngilizce ve küçük harf (`/api/health`, ileride `/api/materials`).
- API belgesi `/api/docs` ve şeması `/api/openapi.json` yalnız geliştirmede açılır (`SMARTCHAIN_ENABLE_DOCS=true`); belge dışarıdan JavaScript yüklediği için (kapalı ağ kuralı), şema da oturumsuz okunabildiği için (2.2) kurulum paketinde kapalıdır.

## Hata cevabı

Her hata aynı biçimde döner; mesaj Türkçe ve kullanıcıya gösterilebilir:

```json
{"error": {"code": "material_not_found", "message": "Malzeme bulunamadı.", "trace_id": "445ecdbb3634", "details": []}}
```

- **İş kuralı hatası:** servis `AppError(code, message, status_code)` fırlatır.
- **Girdi hatası (422):** `code = "validation"`; `details` her hatalı alanı (`field`, `problem`) listeler.
- **Veritabanına ulaşılamıyor (503):** bağlantı kurulamaz ya da havuzda boş bağlantı kalmazsa (havuz zaman aşımı) her uç nokta `code = "database_unavailable"` döner; 500 değildir. Ön yüz bunu "Veriye ulaşılamıyor" diye gösterir.
- **Beklenmeyen hata (500):** kullanıcıya yalnız takip numarası gösterilir; ayrıntı ve yığın izi loga yazılır. Kapalı ağda destek bu numarayla verilir.

## Takip numarası ve log

- Her isteğe 12 karakterlik bir takip numarası verilir; cevapta `X-Trace-Id` başlığında ve hata gövdesinde yer alır.
- Log: konsol ve `logs/smartchain.log` (her gece döner, 30 gün saklanır). Her satırda takip numarası bulunur. Motor servisi kendi dosyasına yazar (`logs/engine.log`).

## Ayarlar

Ortam değişkenleri (`SMARTCHAIN_` önekiyle) ya da kök klasördeki `.env` dosyası (`.env.example` örnek):

| Ayar | Varsayılan |
|---|---|
| `SMARTCHAIN_DB_URL` | localhost, `Smartchain` veritabanı, Windows oturumu |
| `SMARTCHAIN_TEST_DB_URL` | boş · yalnız testler, yalnız ortam değişkeni; boşsa geliştirme bağlantısından türetilir (`Smartchain_test`, K-103) |
| `SMARTCHAIN_LOG_DIR` | `logs` |
| `SMARTCHAIN_LOG_LEVEL` | `INFO` |
| `SMARTCHAIN_ENABLE_DOCS` | `false` |
| `SMARTCHAIN_JOB_WATCH_SECONDS` | `1.0` · iş kuyruğunu izleme aralığı; `0` izlemeyi kapatır |
| `SMARTCHAIN_EXPORT_DIR` | `exports` · arka planda hazırlanan Excel dosyaları (K-93); süresi geçenleri motor servisi siler |
| `SMARTCHAIN_IMPORT_DIR` | `imports` · yüklenen Excel dosyaları (K-129); silme 5.4'te |
| `SMARTCHAIN_SESSION_COOKIE_SECURE` | `true` · oturum çerezi yalnız HTTPS'te gider (K-97). HTTPS'siz test kurulumunda ve testlerde `false`. Edge ve Chrome `http://localhost`'ta da kabul eder |
| `SMARTCHAIN_ALLOWED_ORIGINS` | boş · durum değiştiren isteklerde izin verilen `Origin`'ler, virgülle (ör. `http://localhost:5173`). Boşsa `Origin`'in host'u isteğin `Host`'u olmalı (K-97) |

## Oturum ve kimlik (K-97, K-98, fonksiyon 89)

Kullanıcı oturumdan gelir; uç noktalar kullanıcıyı parametre olarak almaz. Oturum `smartchain_session` çerezindedir (HttpOnly, SameSite=Strict, `Path=/api`, tarayıcı kapanınca biter). `/api/health` ve `POST /api/auth/login` dışındaki her uç nokta oturum ister.

| Adres | Ne |
|---|---|
| `POST /api/auth/login` | `{"user_name", "password"}` → 200 `{"user": …}` ve çerez (cevap `GET /api/auth/me` ile aynı) |
| `POST /api/auth/logout` | 204; oturum kapanır, çerez silinir, bu oturumun WebSocket'leri 4401 ile kapanır |
| `GET /api/auth/me` | `{"id", "user_name", "full_name", "role", "font_size", "permissions": {"10": "read", …}, "must_change_password", "password_change_reason", "idle_seconds_left", "session": {"idle_minutes", "warning_minutes"}, "policy": {"min_length", "require_letter_and_digit", "history_count", "lock_after", "lock_minutes"}}`. Etkinlik sayılmaz |
| `POST /api/auth/activity` | Hareketsizlik sayacını sıfırlar → `{"idle_seconds_left"}`. Arayüz yalnız kullanıcı girdisi olduysa, en çok dakikada bir çağırır |
| `POST /api/auth/password` | `{"current_password", "new_password"}` → 204 |
| `PUT /api/auth/preferences` | `{"font_size": 12, 13, 14 ya da 16}` → 204; kullanıcının yazı boyutu (U-23), denetim izine yazılmaz |

**Giriş hataları** (gövde hesabın varlığını sızdırmaz; bilinmeyen kullanıcı adı da aynı sayaçla işler, K-98):

| Durum | Kod | Mesaj ve `details` |
|---|---|---|
| Kullanıcı adı ya da şifre hatalı | 401 `login_failed` | "Kullanıcı adı ya da şifre hatalı." · `[{"remaining_attempts": 2, "lock_after": 5, "lock_minutes": 15}]` |
| Hesap kilitli | 403 `account_locked` | "Hesap kilitli. 12 dk sonra açılır; yöneticiniz de açabilir." · `[{"minutes_left": 12}]` |
| Hesap kapalı (yalnız şifre doğruysa) | 403 `account_inactive` | "Hesap kapalı. Yöneticiniz açabilir." |

**Oturum hataları:**

| Durum | Kod |
|---|---|
| Çerez yok ya da oturum kapanmış | 401 `not_authenticated` |
| Hareketsizlik sınırı geçti (oturum "Zaman aşımı" ile kapanır) | 401 `session_expired` |
| Şifre değişikliği bekliyor (ilk giriş, sıfırlama, süre doldu); yalnız `me`, `activity`, `password`, `logout` açık | 403 `password_change_required` |
| Durum değiştiren istekte izinsiz `Origin` | 403 `bad_origin` |

**Şifre değiştirme hataları:** mevcut şifre yanlışsa 401 `current_password_wrong` (kilit sayacına girmez, denetim izine "Başarısız şifre değişikliği"); politika sağlanmazsa 422 `password_policy`, `details` sağlanmayan kurallar: `[{"field": "new_password", "problem": "min_length" | "letter_and_digit" | "contains_user_name" | "history" | "same_as_current"}]`. Başarılı değişiklik kullanıcının diğer oturumlarını "Şifre değişti" ile kapatır.

**Etkinlik:** `UserSession.LastActivityAt` yalnız giriş, `activity` ve `password`'da güncellenir; liste sorguları, iş listesi, veri versiyonu ve WebSocket ping'i oturumu uzatmaz. Karşılaştırmalar veritabanı saatiyle (`SYSUTCDATETIME()`).

**Şifre** hiçbir cevapta, logda ve denetim izinde yer almaz; 422 cevabı girilen değeri geri döndürmez.

## Yetki (K-99, K-100, fonksiyon 90)

Matris kodda (`app/api/permissions.py`): 4 rol × 101 fonksiyon; grup tablosu docs/06 fonksiyon 90'da. Hücre düzeyleri `full` (tam), `owner` (hepsini okur, yalnız kendi nesnesini değiştirir), `self` (yalnız kendi kayıtları), `read` (salt okunur), `none`. `GET /api/auth/me` rolün düzeylerini `permissions`'ta verir; arayüz menüyü ve düğmeleri buna göre gösterir, güvenlik sunucudadır.

- **Her uç nokta bir fonksiyon ve erişime bağlıdır** (`deps.require(fn, access)`, `access`: `read` | `write`). Bağsız uç nokta testte yakalanır; açık olanlar yalnız `GET /api/health` ve `POST /api/auth/login`.
- **Yetkisiz istek 403 `forbidden`**; denetim izine "Yetkisiz istek" (ObjectType "Fonksiyon", ObjectKey fonksiyon numarası; NewValue rol, yöntem, adres, gereken rol):

  ```json
  {"error": {"code": "forbidden", "message": "Bu işlem için Admin yetkisi gerekir. Yetki için yöneticinize başvurun.",
             "trace_id": "…", "details": [{"function": 93, "function_name": "İş kuyruğu yönetimi", "access": "write",
                                          "required_role": "Admin"}]}}
  ```

  Gereken rol System owner ise mesajın sonu "Smartchain desteğine başvurun." olur.
- **Nesne bağlamı:** yalnız sahibi değiştirir, diğerleri salt okunur görür. Sahibi değilken değiştirme 403 (ör. `view_not_owner`: "Bu görünümü yalnız sahibi değiştirebilir."), denetim izine "Yetkisiz istek" (sebep "sahibi değil").
- **Rol değişikliği** bir sonraki istekte geçerlidir; oturum kapanmaz. Her yetkili cevapta `X-Smartchain-Role` başlığı oturumdaki rolü taşır; arayüz farklı görürse `me`'yi yeniler.
- **Tanınmayan rol** (bozuk kayıt): oturum "Kapatıldı" ile kapanır, denetim izine "Geçersiz rol", 401 `not_authenticated`.

| Uç nokta | Fonksiyon · erişim |
|---|---|
| `/api/auth/me` · `activity` · `password` · `preferences` · `logout` | 89 · yazma (herkes) |
| `GET /api/data-versions/current` | 82 · okuma (bağlam çubuğu; herkes) |
| `/api/<liste>/columns` · `query` · `groups` · `values` | listenin fonksiyonu · okuma (malzeme: 10) |
| `/api/<liste>/views…` | listenin fonksiyonu · okuma (K-99: görünüm kaydetmek okuma yetkisiyle); değiştirme ve silmede sahiplik |
| `POST /api/<liste>/export` · `GET /api/exports/{id}/file` | 86 · yazma ve listenin fonksiyonu · okuma; indirmede yalnız işi başlatan |
| `GET /api/jobs` | 48 · okuma (kendi işleri); `?scope=all` 93 · okuma (herkesin işleri) |
| `GET /api/jobs/{id}` | kendi işi 48 · okuma; başkasının işi 93 · okuma |
| `POST /api/jobs/{id}/cancel` | kendi işi 48 · yazma; başkasının işi 93 · yazma |
| `POST /api/jobs/{id}/prioritize` | 93 · yazma |
| `GET /api/system-health` · `GET /api/system-events/{id}` · ortak liste `system-events` | 94 · okuma (`detail` yalnız 96 · okuma) |
| Ortak listeler `job-queue`, `job-runs` | 93 · okuma |
| Ortak liste `transfer-history` · `GET /api/transfers/{job_id}` · `GET /api/transfers/{job_id}/excel` | 08 · okuma (K-156) |
| `GET /api/cleanup` | 09 · okuma (Admin ve Key user sonucu görür) · `GET /api/cleanup/plan` · `POST /api/cleanup` 09 · yazma (yalnız System owner; K-156) |
| `GET /api/settings/health` · `PUT /api/settings/health` | 96 · okuma · yazma |
| Ortak liste `audit-log` · `GET /api/audit-log/{id}` · `GET /api/audit-log/{id}/history` | 98 · okuma (Key user yalnız kendi kayıtları) |
| `WS /api/ws` | 48 · okuma (el sıkışmada) |
| `GET /api/users/{id}` | 88 · okuma |
| `POST /api/users` · `/api/users/{id}/…` | 88 · yazma; ek kurallar "Kullanıcılar" bölümünde |
| `GET /api/field-definitions/{tablo}/{alan}` · `GET /api/settings/login-policy` | 96 · okuma |
| `PUT /api/field-definitions/{tablo}/{alan}/label` · `PUT /api/settings/login-policy` | 96 · yazma |
| `GET /api/permissions/matrix` · `GET /api/permissions/matrix/export` | 90 · okuma (Admin ve System owner) |

## Kullanıcılar (K-101, fonksiyon 88)

Liste `users` adıyla ortak liste sözleşmesini kullanır (`/api/users/columns`, `query`, `groups`, `values`, `views…`, `export`; okuma 88). Alanlar `FullName`, `UserName`, `Role`, `Status` (hesaplı: Aktif, Pasif, Kilitli, İlk giriş bekliyor), `LastLoginAt`.

| Adres | Ne |
|---|---|
| `GET /api/users/{id}` | `{"user": {…, "status", "open_sessions"}, "actions": {"role", "name", "reset", "unlock", "close", "reopen": {"allowed", "reason", "required_role"}}, "assignable_roles": […]}`; satır menüsü bununla açılır. System owner hesabı Admin'e 404 |
| `POST /api/users` | `{"full_name", "user_name", "role"}` → 201 `{"user", "temporary_password"}` |
| `PUT /api/users/{id}/role` | `{"role"}` → `{"user"}` |
| `PUT /api/users/{id}/name` | `{"full_name"}` → `{"user"}` |
| `POST /api/users/{id}/reset-password` | → `{"user", "temporary_password"}`; oturumlar "Şifre değişti" ile kapanır, WebSocket'leri 4401 |
| `POST /api/users/{id}/unlock` | → `{"user"}` |
| `POST /api/users/{id}/close` | → `{"user"}`; oturumlar "Kapatıldı" ile kapanır, WebSocket'leri 4401 |
| `POST /api/users/{id}/reopen` | → `{"user"}`; kilit ve sayaçlar temizlenir, şifre değişmez |

- **System owner gizli:** System owner hesapları yalnız System owner'a görünür. Admin'de liste, sayılar, gruplar, değer listeleri ve Excel (arka plan işi dahil) bu satırları içermez; `/api/users/{id}` ve altındaki uçlar bilinmeyen hesapla aynı 404 `user_not_found` cevabını verir, deneme denetim izine "Yetkisiz istek" yazılır. Kullanıcı adı benzersiz olduğundan yalnız ekleme çakışması (409) adın dolu olduğunu gösterir. Liste tanımında `row_scope` (role göre satır koşulu); rol bilinmiyorsa en dar kapsam.
- Geçici şifre içeren cevaplarda `Cache-Control: no-store`; şifre yalnız commit başarılıysa döner, hiçbir yere yazılmaz.
- **Hatalar:** bilinmeyen hesap 404 `user_not_found`; biçim 422 `validation`; kullanıcı adı doluysa 409 `user_name_taken`, `details`: `[{"field": "user_name", "problem": "…", "suggestion": "burak2"}]`; koruma kuralı 409 `user_protected`, `details`: `[{"rule": "last_admin"}]` (`self`, `system_owner`, `last_admin`, `inactive`, `not_locked`, `already_active`, `already_inactive`); System owner yetkisi gereken işlem 403 `forbidden` (gereken rol System owner). Reddedilenler denetim izine "Yetkisiz istek".
- `GET /api/users/{id}`'nin `actions` alanı ile yazma uçları aynı kuraldan beslenir (`services/users.py`).
- **Denetim izi:** `UserId` işlemi yapan, `ObjectType` "Kullanıcı", `ObjectKey` hedefin kullanıcı adı; `OldValue` ve `NewValue` JSON, anahtar alan adı. Eylemler: Kullanıcı oluşturuldu, Rol değişikliği, Ad soyad değişikliği, Şifre sıfırlama, Kilit açıldı, Kullanıcı kapatıldı, Kullanıcı geri açıldı.

## Sistem ayarları ve yetki matrisi (K-100, K-104, K-105)

Veri sözlüğü listesi `field-definitions` adıyla ortak liste sözleşmesini kullanır (okuma 96). Alanlar `TableName`, `FieldName`, `DisplayLabel`, `Description` (varsayılan gizli), `FieldClass`, `ValuePriority`, `ManualOverrides`, `EditableInWorkspace`, `IsRequired`, `DefaultValue`, `IsAdditional`. Liste tanımındaki `key_fields` satırda her zaman döner.

| Adres | Ne |
|---|---|
| `GET /api/field-definitions/{tablo}/{alan}` | Alan, `label`, `standard_label`, `description`, `is_additional`, öteki alanlar, `options` (`field_class`, `value_priority` listelerinin seçenekleri), `used_in_views`, `used_in_rules`. Yoksa 404 `field_not_found` |
| `PUT /api/field-definitions/{tablo}/{alan}/label` | `{"label"}`, en çok 40 karakter; boşsa standart etiket. Aynı tabloda aynı etiket 409 `label_taken`. İz "Alan etiketi değişikliği" |
| `GET /api/settings/login-policy` | `{"values", "defaults", "limits"}` |
| `PUT /api/settings/login-policy` | Değişen anahtarlar; sınır dışı ya da uyarı süresi oturum süresinden kısa değilse 422, hiçbiri yazılmaz. İz "Ayar değişikliği", anahtar başına |
| `GET /api/permissions/matrix` | Roller, 18 grup satırı, 101 fonksiyon, istisnalar |
| `GET /api/permissions/matrix/export` | Excel: fonksiyon düzeyinde 98 satır. İz "Dışa aktarım" |

## Liste sorgusu (K-87)

Bütün tablolar (ana veri, plan, rapor) aynı sözleşmeyle okunur. Filtre, sıralama ve parça parça yükleme sunucuda yapılır (U-21); ön yüzdeki ortak tablo bileşeni (docs/12) bu sözleşmeyi kullanır. Her liste sunucuda bir liste tanımıdır (`app/api/lists/`): tablo, alanlar ve sırası, varsayılan görünür alanlar, varsayılan sıralama.

**Sürümsüz ve hesaplı liste (2.3):** liste tanımı `versioned=False` ise sürüm koşulu ve veri versiyonu aranmaz (kullanıcı listesi temiz kurulumda da açılır); Excel dosya adında versiyon yoktur, Bilgi sayfasında Kaynak "Güncel kayıtlar" yazar. `source` tablo yerine alt sorgu verir, hesaplı alanlar sıralama, filtre, gruplama ve Excel'de kolon gibi çalışır.

### Kolonlar · `GET /api/<liste>/columns`

```json
{"chunk_size": 100,
 "columns": [{"field": "MaterialLevel", "label": "Malzeme seviyesi", "type": "text", "filter": "list",
              "values": ["Hammadde", "Yarı mamul", "Nihai ürün"], "values_from_server": false, "decimals": null,
              "default_visible": true}],
 "export": {"title": "Malzeme listesi", "file_slug": "malzeme", "sync_max_rows": 10000, "max_rows": 500000,
            "file_hours": 24}}
```

- **Dışa aktarım** (`export`, K-91): kapsam penceresi listenin adını, dosya adındaki kısa adı eşikleri (`ExportSyncMaxRows`, `ExportMaxRows`) ve arka plan dosyasının saklama süresini (`ExportFileHours`) buradan okur; anlık mı arka planda mı olacağını ve sınır aşımını önceden söyler.
- **Parça büyüklüğü** (`chunk_size`): SystemSetting `ListChunkSize` (varsayılan 100, en çok 500; docs/02). Tablo bir istekte hiçbir zaman bundan fazla satır istemez; sunucu da fazlasını reddeder.

- **Etiket:** docs/02 AÇIKLAMA'sından üretilir; FieldDefinition.Label varsa onu kullanır. Ek alan (K-59) yalnız Label'ı varsa listelenir (K-88).
- **Tip** (`type`) veritabanı tipinden gelir: `text`, `integer`, `number`, `bool`, `date`, `datetime`.
- **Ondalık** (`decimals`): gösterilecek ondalık sayısı liste tanımından gelir, veritabanı ölçeğinden değil (gün ve adet gibi tam sayı anlamındaki alanlar 0). `integer` için 0; sayı dışı alanlarda `null`.
- **Ondalık birimden** (`decimals_from_unit: true`, `decimals: null`): miktar kolonları; her satırda temel birimin ondalığı (UnitOfMeasure.Decimals, K-88) kullanılır. Sorgu cevabında her satır bunu `_unit_decimals` alanında taşır (birim bilinmiyorsa 2).
- **Yüzde gösterim** (`percent: true`): değer veride oran (0,05), `decimals` yüzde değerinin ondalığı; ekran ve Excel `%5,00` gösterir (K-113). Sorgu cevabı, filtre ve koşullu biçim oranla çalışır, Excel hücresinde de oran durur.
- Liste tanımında her `number` alanı ya sabit ondalıkla ya da "ondalık birimden" işaretlenir; ikisi birden ya da hiçbiri hatadır (testte).
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

Cevap: `{"rows": [{"Id": 7, "Code": "…", …, "_unit_decimals": 3}], "offset": 0, "filtered": 120, "total": 840}`. `Id` her satırda vardır; `_unit_decimals` listenin birim alanı varsa (malzemede `BaseUom`) bulunur. `filtered` filtreli sayı, `total` filtresiz sayıdır; arayüzdeki "120 / 840" sayacı bunlardır (U-12). Sayılar JSON sayısı, tarihler ISO döner (`2026-10-27`); zamanlı alanlar veritabanında UTC tutulur ve saat dilimiyle döner (`2026-10-27T09:20:00+00:00`), tarih filtresinin gün sınırı yerel gece yarısıdır.

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
- **Sınırlar:** `limit` varsayılan ve en çok `ListChunkSize` (kolonlar cevabındaki `chunk_size`); `offset` ≥ 0.
- **Hatalar:** bilinmeyen alan, operatör, eksik değer ya da sınır dışı `limit` → 422 `validation` (`details`: `field`, `problem`); veritabanı yoksa 503 `database_unavailable`; veri versiyonu yoksa 404 `no_data_version`.
- **Versiyon:** liste güncel veri versiyonunu okur (`VersionFrom ≤ v` ve `VersionTo` boş ya da `≥ v`; motorun okuduğu koşulla aynı).

### Boş değer (U-13)

- Her filtre tipinde `{"field": …, "op": "empty"}`: değeri boş olanlar. Metinde boş metin de boş sayılır.
- Liste filtresinde `{"op": "in", "values": [...], "empty": true}`: değerlerden biri ya da boş. Yalnız boş için `values` boş bırakılabilir.
- `values` cevabında boş satırlar varsa başta `{"value": null, "count": n}` döner.

### Gruplama · `POST /api/<liste>/groups` (K-90)

İstek: `{"group_by": ["MaterialLevel", "MaterialGroup"], "fields": ["SafetyStock", …], "aggregates": {"SafetyStock": {"fn": "sum"}, "StockCoverageDays": {"fn": "wavg", "weight": "SafetyStock"}}, "filters": [...], "sort": [...]}`. `aggregates` verilmezse görünen kolonlarda (`fields`) liste tanımının varsayılanı kullanılır. Cevap:

```json
{"groups": [{"key": ["Hammadde"], "count": 80, "aggregates": {"SafetyStock": 120.0}, "mixed_units": ["SafetyStock"],
             "children": [{"key": ["Hammadde", "Çubuk"], "count": 20, "aggregates": {"SafetyStock": null}, "mixed_units": []}]}],
 "aggregates": {"SafetyStock": 120.0}, "leaf_groups": 12, "filtered": 200, "total": 200}
```

- `key` kökten o gruba kadar değerlerdir; `null` boş gruptur ("(Boş)", sırada en sonda). Grup sırası: grup alanı sıralamadaysa onun yönü, değilse artan, Türkçe.
- **Ara toplam türleri** (`fn`, yalnız sayı alanları; K-90):

  | `fn` | Arayüzde | Hesap |
  |---|---|---|
  | `sum` | Toplam | dolu değerlerin toplamı |
  | `avg` | Ortalama (boşlar hariç) | toplam / dolu değer sayısı |
  | `avg_nonzero` | Ortalama (sıfırlar hariç) | toplam / sıfırdan farklı dolu değer sayısı |
  | `wavg` | Ağırlıklı ortalama | Σ(değer × ağırlık) / Σ ağırlık; değeri ya da ağırlığı (`weight`, bir sayı alanı) boş satır girmez; Σ ağırlık 0 ise `null` |
  | `min` / `max` | En küçük / En büyük | dolu değerlerin en küçüğü / en büyüğü |
  | `count` | Sayı (dolu satır) | değeri dolu satır sayısı; birimden bağımsız |
  | `none` | Yok | hesaplanmaz |

  Üst gruplar alt gruplardan tam türetilir (ortalamalar ağırlıklı birleşir). En dıştaki `aggregates` bütün filtreli satırlarındır. Bilinmeyen alan, sayı olmayan alan, bilinmeyen tür ya da `wavg`'de eksik ve geçersiz ağırlık 422.
- `mixed_units`: birimden ondalıklı (miktar) kolonlarda (ya da ağırlık miktar alanıysa) katkı veren satırlarda birden çok birim varsa kolon burada listelenir ve değeri `null` döner; `count` bu kurala girmez (K-88, K-90). Tek birimliyse `unit_decimals` o birimin ondalığını verir (`{"SafetyStock": 0}`).
- `filtered` / `total`: "120 / 840" sayacı (U-12).
- Arayüzde ortalamalar kolonun ondalığından bir fazla ondalıkla, sayı ondalıksız yazılır.
- Yaprak grup sayısı `ListMaxGroups`'u (SystemSetting, 1.000) aşarsa 422 `too_many_groups`.
- **Performans:** gruplama sorgusu SQL Server'a paralel plan tercihini bildirir (`OPTION (USE HINT('ENABLE_PARALLEL_PLAN_PREFERENCE'))`); 50.000 satırda iki alanla gruplama ortanca ~110 ms (hedef 300 ms). Birim karışıklığı, birim gizli son grup düzeyi yapılarak bulunur; ara toplam yalnız görünen kolonlar (`fields`) için hesaplanır.
- **Grubun satırları:** `query` isteğine `"group_key": [{"field": "MaterialLevel", "value": "Hammadde"}, …]` eklenir (değer `null` ise boş); parça kuralı aynıdır (K-87).
- Kolonlar cevabında her kolon varsayılan türü taşır: `aggregate: "sum" | "avg" | … | null`.

### Görünümler (K-89)

Kullanıcı oturumdan gelir (K-97).

| Adres | Ne |
|---|---|
| `GET /api/<liste>/views` | `{"views": [...], "default_view_id": 4 \| null}`; kendi görünümleri ve başkalarının paylaşılanları. Her görünüm: `id`, `name`, `owner_user_id`, `owner_name`, `is_shared`, `is_owner`, `updated_at`, `definition`, `warnings` |
| `POST /api/<liste>/views` | Yeni görünüm: `{"name", "is_shared", "definition"}` → 201 ve görünüm |
| `PUT /api/<liste>/views/{id}` | Ad, paylaşım ya da içerik değişir; yalnız sahibi |
| `DELETE /api/<liste>/views/{id}` | Siler (varsayılan yapılmışsa o seçimler de kalkar); yalnız sahibi |
| `PUT /api/<liste>/views/default` | `{"view_id": 4}` ya da `{"view_id": null}` (Standart) |
| `PUT /api/<liste>/views/standard` | Şirket Standart'ı: `{"definition"}`; yalnız System owner ve Admin, öteki rollere 403 `view_standard_forbidden`. İz "Standart görünüm değiştirildi" (K-162) |
| `DELETE /api/<liste>/views/standard` | Ürün Standart'ına döndür: şirket Standart'ı silinir; yalnız System owner ve Admin. İz "Standart görünüm ürün hâline döndü" |

`GET /api/<liste>/views` cevabında `standard`: şirket Standart'ı (`definition`, `updated_at`, `updated_by_name`, `warnings`) ya da `null`; `can_edit_standard`. Kaydedildikten sonra listeye eklenen alan ürünün varsayılanına göre eklenir (`KnownFields`).

**İçerik** (`definition`, sürüm 1):

```json
{"v": 1, "columns": [{"field": "Code", "width": 7.5}, {"field": "Name", "width": null}], "pinned": 1,
 "sort": [{"field": "Code", "dir": "asc"}], "filters": [{"field": "UpdatedAt", "op": "relative", "value": "this_week"}],
 "group_by": ["MaterialLevel"], "aggregates": {"StockCoverageDays": {"fn": "wavg", "weight": "SafetyStock"}}}
```

- `columns` görünen alanlar, görünen sırada; `width` rem (boşsa tipin varsayılanı). `pinned` soldan sabit kolon sayısı. `aggregates` kullanıcının varsayılandan farklı seçtiği ara toplam türleri (K-90).
- Göreli tarih filtresi göreli saklanır; görünüm açıldığı günün haftasına göre çalışır.
- `rules`: koşullu biçim kuralları, sıralı (aşağıda "Koşullu biçim kuralları"). Açılırken artık olmayan alana ya da karşılaştırılan alana bakan kural atılır, `warnings`'te yazar.
- Kaydederken alanlar ve filtreler liste tanımına göre doğrulanır (422). Açılırken artık olmayan alanlar atılır, `warnings`'te yazar.
- Hatalar: sahibi değilse 403 `view_not_owner`; aynı adda görünüm varsa 409 `view_name_taken`; görünüm yoksa 404 `view_not_found`; kullanıcı yoksa 404 `user_not_found`.
- "Standart" görünüm veritabanında değildir: liste tanımındaki varsayılan alanlar ve sıralamadır, silinemez.

### Koşullu biçim kuralları (U-24, K-95, K-96)

Kural görünüm içeriğindedir (`definition.rules`, en çok 20; alan yoksa boş liste):

```json
{"id": "k1", "field": "SafetyStock", "enabled": true,
 "condition": {"op": "gt", "value": 100},
 "format": {"fill": "#f4cfc4", "color": "#7a2a14", "bold": true, "icon": "arrow_up", "icon_color": "#4f5bd5"}}
```

| Kolon tipi | Koşul operatörleri |
|---|---|
| Sayı (tam sayı dahil) | `gt`, `lt`, `between` (`min`, `max`), `eq`, `empty`, `always` |
| Tarih, tarih-zaman | `gt`, `lt`, `between` (`from`, `to`), `eq`, `relative` (`this_week`, `next_4_weeks`), `empty`, `always` |
| Metin (liste filtreli metin alanları dahil) | `equals`, `contains`, `starts_with`, `in` (`values`), `empty`, `always` |
| Evet/hayır | `in` (`values`: `true`, `false`), `empty`, `always` |

`always` ("Her zaman"): koşulsuz kolon biçimi; değer almaz, kolonun bütün hücrelerinde (boşlar dahil) tutar.

- Sayı ve tarihte `gt`, `lt`, `eq` için sabit değer (`value`) yerine aynı tipte başka bir alan verilebilir: `{"op": "lt", "field_ref": "SafetyStock"}`. Tarih ve tarih-zaman gün olarak karşılaştırılır. Boş değer: sayıda `empty_as_zero` (varsayılan `true`, "Boşları 0 say") kolon ya da karşılaştırılan alan boşsa 0 sayar; `false`'ta ve tarihte boşsa kural tutmaz. `empty_as_zero` yalnız sayı alanı karşılaştırmasında verilir.
- `format`: `fill`, `color` ve `icon_color` `#rrggbb`; `bold`; `icon` şunlardan biri: `arrow_up`, `arrow_down`, `dot`, `warning`, `check`, `cross`, `flag`, `star`. En az biri (`icon_color` hariç) dolu olmalı. `color` yoksa okunur yazı rengi zemine göre hesaplanır (K-96); `icon_color` yoksa ikonun varsayılan rengi; Excel'de ikon hücrenin yazı rengiyle yazılır.
- Metin karşılaştırması filtredeki gibi büyük/küçük harf duyarsız (Türkçe); metinde boş metin boş sayılır.
- **Sorguda:** `POST /query` gövdesine `"rules": [{"field": "SafetyStock", "condition": {...}}]` (istemci yalnız aktif ve görünen kolonların kurallarını gönderir); her satır `"_rules": [0, 2]` taşır: tutan kuralların bu listedeki sırası. Gruplu okuma (`group_key`) için de aynı.
- **Excel'e aktarım:** `POST /export` gövdesine `rules` (biçimleriyle, sıralı; pasifler ve gizli kolonlarınkiler gönderilmez). Hücreye zemin, yazı rengi, kalın ve ikon (biçim kodu öneki) yazılır; aynı özellikte üstteki kural kazanır. Bilgi sayfasında "Koşullu biçim" satırı.
- **Hatalar (422 `validation`):** bilinmeyen alan; tipe uymayan operatör ya da değer; geçersiz renk ya da ikon; biçimsiz kural; `field_ref` bilinmiyor, tipi uymuyor, kendisi ya da `value` ile birlikte verilmiş; 20'den fazla kural.

### Değerler · `POST /api/<liste>/values`

Liste filtresinin seçenekleri: `{"field": "MaterialGroup", "search": "döv", "filters": [...]}` → `[{"value": "Dövme", "count": 12}, …]`. Diğer filtreler uygulanmış hâldeki ilk 100 farklı değer, değere göre sıralı; `search` içerir araması yapar. Yalnız `filter: "list"` alanlarda çalışır.

## Dışa aktarım (K-91, fonksiyon 86)

`POST /api/<liste>/export` (kullanıcı oturumdan). İstek, ekrandaki görünüm durumu ve kapsam:

```json
{"fields": ["Code", "Name", "SafetyStock"], "widths": {"Code": 7.5}, "sort": [{"field": "Code", "dir": "asc"}],
 "filters": [...], "group_by": ["MaterialLevel"], "aggregates": {"SafetyStock": {"fn": "sum"}},
 "scope": {"rows": "filtered", "columns": "visible"}}
```

- `scope.rows`: `filtered` (ekrandaki filtrelerle) ya da `all` (filtresiz); `scope.columns`: `visible` (`fields`, ekrandaki sırayla) ya da `all` (listenin bütün alanları: önce görünenler, sonra diğerleri). Gruplama ve ara toplamlar istekteki gibi (ekrandaki gibi) her zaman yazılır; Bilgi sayfası her dosyada vardır (K-91).
- Satır sayısı `ExportSyncMaxRows` (10.000) ve altıysa **200**: dosya gövdede (`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`), adı `Content-Disposition`'da.
- Üstüyse **202** `{"job_id": 81, "file_name": "…", "rows": 142000}`: iş "Excel" kanalında (K-93, K-129). İlerleme ve bitiş WebSocket iş mesajlarıyla gelir; iş sonucu `{"file_name", "size", "rows"}`.
- `ExportMaxRows`'u (500.000) aşarsa 422 `export_too_large` ("filtreyi daraltın").
- İz: her aktarım `adm.AuditLog`'a yazılır (Action "Dışa aktarım", ObjectType liste adı, ObjectKey dosya adı, NewValue JSON: kapsam, filtreler, kolonlar, satır sayısı, boyut, süre, veri versiyonu); arka planda iz, dosya hazır olunca iş bitişiyle aynı işlemde yazılır. İz yazılamazsa dosya verilmez (anlıkta 503, arka planda iş Hata).

`GET /api/exports/{job_id}/file`: arka planda hazırlanan dosya. Yalnız işi başlatan indirir (başkası 403 `export_not_owner`); iş bitmediyse 409 `export_not_ready`; süresi (`ExportFileHours`, 24 saat) geçtiyse ya da dosya silindiyse 410 `export_expired`.

Dosya: veri sayfası (başlık dondurulur, otomatik filtre; kolon genişlikleri ekrandan; başlık ve grup satırları ekrandaki tonlarla; grup başlığında ad, satır sayısı ve ara toplamlar değer olarak) ve Bilgi sayfası. Sayılar sayı, tarihler tarih, Türkçe biçim (K-92).

## Testler

- **Sıra (commit zinciri):** `npm run build` → `SMARTCHAIN_SKIP_WEB_TESTS=1 python -m pytest` → `npm test` → `npx tsc --noEmit`. Build önce: internetsizlik testi (`tests/test_offline.py`) taze derlemeyi tarar. Zincirde pytest değişkenle çalışır: arayüz testleri pytest içinden (`tests/test_web.py`) koşmaz, yalnız `npm test` adımında koşar; aynı testler iki kez koşmaz, zincir kısalır. Değişken yokken `python -m pytest` tek başına arayüz testlerini de kapsar.
- `python -m pytest`: bütün testler, **performans testleri hariç** (`pyproject.toml`: `-m 'not perf'`). Veritabanı testleri (`db` işareti) atlanırsa (SQL Server'a bağlanılamadı, yetki yok, sentetik veri yok) koşu başarısız olur; zincir yanlışlıkla geçmiş görünmez. SQL Server olmadan bilerek çalıştırmak için `python -m pytest -m "not db"`.
- `python -m pytest -m perf`: performans testleri ayrıca çalıştırılır. Büyük veriyi bir işlem içinde üretir, ölçer ve geri alır; her ölçüm birkaç denemenin ortancasıdır (makine yükündeki tek seferlik sıçramalar sonucu bozmasın).
- Ön yüz: `cd app/web; npm run build; npm test; npx tsc --noEmit`. Test süresi sınırı 15 sn (`vite.config.ts`): dosyalar paralel çalıştığı için yük altında jsdom testleri varsayılan 5 sn'yi aşabilir; tek başına bir test 2 sn'nin altındadır. `findBy` / `waitFor` beklemesi 5 sn (`src/test/setup.ts`; varsayılan 1 sn yük altında girişten sonra ekran açılışını yakalayamıyordu, 4.4).
- **Testler ayrı veritabanında (K-103):** bütün veritabanı testleri `Smartchain_test`'te koşar. Bağlantı `SMARTCHAIN_TEST_DB_URL` ortam değişkeninden gelir; yoksa geliştirme bağlantısından türetilir (`tests/testdb.py`). Ad `_test` ile bitmiyorsa hiçbir test çalışmadan durur (çıkış kodu 2). Oturum başında veritabanı yoksa açılır, şema güncellenir, önceki koşunun artıkları silinir, sentetik veri yoksa yüklenir. Bozulursa `Smartchain_test` elle silinir, sonraki koşu yeniden kurar.
- **Zincir arayüz, API ve motor açıkken de çalışır;** pencereleri kapatmak gerekmez. Aynı anda iki test koşusu desteklenmez. Performans testleri süre ölçtüğü için pencereler kapalıyken daha sağlıklıdır; zorunlu değil, aşım makine durumuyla birlikte değerlendirilir.
- **Testler geliştirme veritabanına yıkıcı işlem yapamaz** (CLAUDE.md): ayrıca `installer/setup_db.py`'de silen, açan ya da geçiş çalıştıran işlevler test sırasında (`PYTEST_CURRENT_TEST`) adı `_test` ile bitmeyen veritabanını bağlanmadan reddeder. Kurulum ve kaldırma etkilenmez.
- Bunların hepsi geçmeden commit ve push yapılmaz (CLAUDE.md).

## Uç noktalar

| Adres | Ne | Durum |
|---|---|---|
| `GET /api/health` | Uygulama sürümü, veritabanı bağlantısı, şema sürümü (beklenen ile karşılaştırma). Sorun varsa 503 ve Türkçe açıklama. Sistem sağlığı ekranının (24) çekirdeği. | uygulandı (0.3) |
| `GET /api/jobs` | Oturumdaki kullanıcının çalışan, sıradaki ve son 24 saatte biten işleri (önce çalışan, sonra sıra); kanal sayaçları (çalışan, sırada, sınır). `?scope=all` herkesin işleri (Admin ve System owner, 93). Her işte `requested_by` ve `requested_by_name`. Bağlantı kopunca istemcinin son durumu sorguladığı yer (fonksiyon 48). | uygulandı (0.4; yetki 2.2) |
| `GET /api/jobs/{id}` | İşin durumu, ilerlemesi, sıra numarası, süresi, `is_stale` (kalp atışı eşiği aşıldı). Yoksa 404 `job_not_found`. Başkasının işi 93 ister. | uygulandı (0.4; yetki 2.2) |
| `POST /api/jobs/{id}/cancel` | Sıradaki işi iptal eder; gövde `{"reason"}`, başkasının işinde zorunlu (422 `reason_required`). Çalışan iş ve Yükleme işi 409 `job_not_cancellable`. Kendi işi herkes, başkasının işi Admin ve System owner (93); System owner'ın işine Admin dokunamaz (403). İz "İş iptali". | uygulandı (0.4; yetki 2.2; neden 2.5) |
| `POST /api/jobs/{id}/dismiss` | Kendi işinin bildirimini kapatır (`Job.DismissedAt`, K-132); kapatılan bildirim yeniden çıkmaz. Başkasının işi 403. | uygulandı (3.3) |
| `POST /api/jobs/{id}/prioritize` | Sıradaki işi kanalında öne alır. Çalışan iş ve Gece kanalı 409 `job_not_prioritizable`. İz "İş öne alma". | uygulandı (2.5) |
| `GET /api/data-versions/current` | En son veri versiyonu: Id, lokasyon kodu, oluşma zamanı, tam/kısmi, sentetik mi. Yoksa 404 `no_data_version`; veritabanına bağlanılamazsa 503 `database_unavailable`. Bağlam çubuğunun veri versiyonu (docs/12). | uygulandı (1.1) |
| `GET /api/materials/columns` · `POST /api/materials/query` · `POST /api/materials/values` | Malzeme listesi, liste sorgu sözleşmesiyle (K-87). Şimdilik tablo bileşeni denemesi (`/tablo`); malzeme ekranı 6.1'de. | uygulandı (1.3) |
| `POST /api/materials/groups` · `/api/materials/views…` | Gruplama ve ara toplam (K-90), kayıtlı görünümler (K-89) | uygulandı (1.4) |
| `POST /api/materials/export` · `GET /api/exports/{job_id}/file` | Excel'e aktarım: anlık ya da arka planda (K-91, K-93) | uygulandı (1.5) |
| `query`'de `rules` | Koşullu biçim kuralları: satır başına tutan kurallar (K-95) | uygulandı (1.6) |
| `WS /api/ws` | Anlık bildirim kanalı (fonksiyon 48). Oturumla açılır; oturum yoksa el sıkışma reddedilir (403). | uygulandı (0.4; oturum 2.1) |
| `/api/auth/login` · `logout` · `me` · `activity` · `password` | Giriş, çıkış, oturumdaki kullanıcı, etkinlik, şifre değiştirme (K-97, K-98; fonksiyon 89) | uygulandı (2.1) |
| `PUT /api/auth/preferences` | Yazı boyutu (U-23) | uygulandı (2.3) |
| `/api/users…` | Kullanıcı listesi ve yönetimi (K-101; fonksiyon 88) | uygulandı (2.3) |

İş eklemek için uç nokta yoktur: işi ilgili fonksiyon (yeniden hesap 46, yükleme…) kendi servisinden `app.jobs.queue.enqueue` ile ekler.

## İş kuyruğu (fonksiyon 47, 93)

- Durumlar: Sırada → Çalışıyor → Bitti | Hata; Sırada → İptal (K-67).
- Kanal sınırı: hesaplama 3, gece 2, Veri çekme 1, Veri işleme 4 (K-134, ölçüm aşağıda) (`adm.SystemSetting`: `JobLimitInteractive`, `JobLimitNight`, `JobLimitPull`, `JobLimitProcessing`). İş alma uygulama kilidiyle sıraya konur; sıra önce öncelik, sonra istek sırası (K-68).
- Çalışan iş kalp atışı yazar. `JobHeartbeatTimeoutSeconds` (120) boyunca gelmezse takılmış sayılır; `JobMaxAttempts` (2) dolana kadar yeniden sıraya döner, sonra Hata. Eski deneme işi artık yazamaz (her yazma deneme numarasıyla).

## Sistem sağlığı (ekran 24, K-106)

| Uç nokta | Cevap |
|---|---|
| `GET /api/system-health` | `server_time`; `cards`: `queue` (`queued`, `oldest_wait_minutes`, `threshold`, `warn`), `interactive` (`running`, `limit`), `errors` (`last_7_days`, `resolved`), `disk` (`percent`, `free_bytes`, `threshold`, `warn`, `database_bytes`, `data_versions`); `services`: `app`, `engine`, `database`, `notifications` (`status`, `heartbeat_at` ve servise göre `version`, `busy`, `ms`, `pool_in_use`, `pool_size`, `connections`) |
| Ortak liste `job-queue` | Çalışan, sırada, son 24 saatte biten; satırda her zaman `Status`, `JobType`, `Channel`, `RequestedBy`, `IsProtected`, `Summary`, `RequesterName`, `QueuePosition` |
| Ortak liste `job-runs` | Son 7 günde biten işler |
| Ortak liste `system-events` | Hatalar; `Detail` listede yok |
| `GET /api/system-events/{id}` | Olay; `detail` yalnız System owner'a dolu. Yoksa 404 `event_not_found` |
| `GET` · `PUT /api/settings/health` | `DiskWarnPercent` 1–99, `QueueWaitWarnMinutes` 1–1440, `SystemEventRetentionDays` 7–3650; Excel yükleme `ImportSyncMaxMb`, `ImportMaxMb`, `ImportMaxRows` (K-129, K-157); `RawDataRetentionDays` 1–30 ya da boş (K-156); cevap login-policy gibi `values`, `defaults`, `limits`. Yalnız değişen yazılır, iz "Ayar değişikliği" |

`GET /api/jobs`'ta `requested_by_name` System owner'ın işinde "Smartchain"tir; `summary`, `is_protected`, `cancel_reason`, `cancelled_by_name` eklendi.

`{"type": "health"}` içerik taşımaz: iş ya da olay değişti, motor açıldı ya da kapandı; yalnız 93 okuma yetkili bağlantılara gider, ekran yeniler.

## Denetim izi (ekran 26, K-108)

| Uç nokta | Cevap |
|---|---|
| Ortak liste `audit-log` | `At`, `ActorName`, `Action`, `ObjectTypeLabel`, `ObjectShown`, `OldText`, `NewText` (okunur), `OldValue`, `NewValue` (ham, varsayılan gizli). Kapsam `row_scope(role, user_id)` |
| `GET /api/audit-log/{id}` | `id`, `at`, `actor`, `action`, `object_type`, `object`, `has_object`, `changes`: `[{"field", "old", "new"}]`. Kapsam dışıysa 404 `audit_not_found`. Gerçek ad, nesne ve değerler yalnız System owner'a |
| `GET /api/audit-log/{id}/history` | Aynı nesne tipi ve anahtarın kayıtları zaman sırasıyla: `rows`, `truncated` (en çok 200; en yeniler). Kapsam ve maske listeyle aynı |

**Okunur biçim:** `app/api/audit_format.py` tek yer: `FIELD_LABELS` her anahtar, `VALUE_LABELS` kodlu değerler, `SETTING_LABELS` ayar anahtarları (Sistem ayarları formuyla aynı adlar, testle denetlenir; `ObjectShown` sorguda üretilir, süzme bu adda); kolon ve sıralama alanları listenin etiketiyle. Yeni iz anahtarı ya da kodlu değer eklenirse çevirisi de eklenir: yazma noktaları taranır (`tests/test_audit_format.py`), test sırasında yazılan her iz denetlenir (`tests/audit_guard.py`). Bilinmeyen anahtar üretimde olduğu gibi görünür, bilgi kaybolmaz.

**İz yazılamazsa:** işlem geri alınır, `SystemEvent` (bileşen "Denetim izi"), 503 `audit_failed`. Excel'de dosya verilmez (`export_trace_failed` kalktı).

## Excel yükleme (ekran 02, fonksiyon 03, K-129)

Fonksiyon 03: System owner, Admin, Key user; End user 403. Devam ve vazgeç yalnız yükleyen (403 `import_not_owner`). Dosya ham gövdeyle gelir (`python-multipart` yok), akışla diske yazılır.

| Uç nokta | Cevap |
|---|---|
| `POST /api/imports/{entity}?mode=Değişen\|Tam` · gövde xlsx, başlık `X-File-Name` (URL kodlu) | `ImportSyncMaxMb` ve altı **200** özet; üstü **202** `{batch_id, job_id}`. 404 `entity_not_found`, 413 `import_too_large`, 422 `import_bad_file`, `import_wrong_entity`, `import_missing_columns`; bunlarda parti oluşmaz (büyük dosyada son ikisi işte: parti Hatalı) |
| `POST /api/imports?mode=Değişen\|Tam&skip=Material,Customer` · gövde xlsx, başlık `X-File-Name` | Veri yükle, birden çok dosya (K-158): tablo dosyanın şablon bilgisinden, dosya açılmadan okunur; cevap tek tablolu yüklemeyle aynı, ayrıca `entity` ve `name`. Parti açmadan ret: 422 `import_unknown_template` (şablon bilgisi yok), 422 `import_old_template` (eski sürüm), 409 `import_duplicate` (`skip`'teki tabloya ikinci dosya; arayüz kabul edilen tabloları sırayla gönderir), 422 `import_bad_file` |
| `GET /api/imports/{id}` | Özet: tablo, dosya, sürüm durumu, mod, durum, okunan, geçerli, hatalı, uyarı ve bilgi, dosya düzeyi bulgular, iş |
| `GET /api/imports/pending/{entity}` | Kullanıcının bu tablodaki açık ön kontrolü ya da `null` |
| Ortak liste `import-findings` | Satır, kod, alan, değer, sorun, önem; arayüz partiyi sabit filtreyle verir |
| `POST /api/imports/{id}/continue` · isteğe bağlı `{mode}` | Parti "Alındı" ve staging'in güncel hâline işlenir (K-133); `mode` verilirse partinin modu bununla yazılır (birden çok dosyada dosya başına mod, K-158); iz "Excel yükleme" ve "Validasyon" işi aynı işlemde; 409 `import_not_pending` |
| `POST /api/imports/{id}/cancel` | Satırlar ve dosya silinir, "Vazgeçildi"; sıradaki iş iptal edilir, çalışan iş sonraki parçada durur |
| `GET /api/imports/{id}/error-report` | Hatalı satırlar, özgün değerler, sonda "Hata" kolonu; iz "Hata raporu indirme". 410 `import_file_gone` |

**Ölçüm (Malzeme, 33 alan; `python -m pytest -m perf`):** 40.000 satır (5,0 MB) API dahil ortanca 12,1 sn, hedef 15 sn; 200.000 satır (25,2 MB) işte ortanca 52,6 sn. Geliştirme dizüstüsü hibrit işlemcili: süreç verimlilik çekirdeğine düşerse eşikteki dosya 26–28 sn sürer, performans çekirdeğine bağlıyken 16–17 sn ölçüldü; sunucuda ilk kurulumda ölçülür, gerekirse `ImportSyncMaxMb` düşürülür. Bu yüzden eşik 5 MB. Dosyayı açmak metin tablosunu belleğe okur: küçük dosya tek açılışla işlenir, büyük dosya istekte açılmaz (yalnız paket denetimi); yanlış tablo ve eksik kolon büyük dosyada işte anlaşılır, parti "Hatalı" olur, nedeni özette yazar. Liste dışı değer bilgisi alan ve değer başına tektir (en çok 1000): ERP'nin kendi değerleri her satırda bilgi yazdırmaz.

**Liste ek alanı:** kolon tanımında `note` başlığın ipucudur: liste tanımının notu, yoksa alanın veri sözlüğündeki açıklaması; etiketle aynıysa ya da yoksa boş. **İş cevabı:** "Excel ön kontrol" işinde `import_batch_id` ("Sonucu aç"). **İz:** `mode` pencerede görünen adla: "Ekle / güncelle", "Tam".

## SQL çekimi ve entegrasyon tanımı (ekran 02 ve 23, fonksiyon 01 ve 91, K-130)

Excel yükleme yöntemden bağımsızdır: yöntem ne olursa olsun, çekim açık ya da kapalı, `POST /api/imports/{entity}` çalışır.

| Uç nokta | Yetki | Cevap |
|---|---|---|
| `PUT /api/integration/entities` · `{changes: [{entity, method?, view?, pull_enabled?, reason?}]}` | Admin ve üstü; `method` ve `view` System owner | Tablo içi düzenlemelerin toplu kaydı (K-132), tek işlem: biri geçersizse hiçbiri yazılmaz. 422 `integration_bad_method`, `integration_reason_required`, `integration_view_not_found`. Açık ön kontrol etkilenmez. İz "Yöntem değişikliği", "Çekim kapatma", "Çekim açma", "Entegrasyon tanımı" |
| `GET /api/integration/connection` | Admin ve üstü | Veritabanı adı, hesap, son kullanım, kart sayıları |
| `PUT /api/integration/connection` · `{database}` | System owner | Ad kuralı: harf, rakam, alt çizgi. İz "Entegrasyon tanımı" |
| `POST /api/integration/test` | Admin ve üstü | Adım adım sonuç: erişim, kimlik, sinyal tablosu, view'lar. Yalnız okur |
| `POST /api/integration/entities/{entity}/preview` | Admin ve üstü | 20 satır ve her satırın bulguları; 409 `integration_view_missing` |
| `GET /api/integration/entities/{entity}/view-versions` | Admin ve üstü | View sürümleri, en yenisi önce |
| `GET /api/pulls/plan` | Key user ve üstü | Tablo, yöntem, kaynak, durum, neden; son çekim |
| `POST /api/pulls` · `{entities, read_anyway: [tablo]}` | Key user ve üstü | **202** `{job_id}`; 409 `pull_running`; 409 `integration_not_configured`. İz "Veri çekme" |
| `GET /api/pulls/{job}` | Key user ve üstü | İş durumu; tablo, yöntem, kaynak, durum, okunan, geçerli, hatalı, parti, denemeler, hata |

**Ölçüm (Malzeme, 33 alan; `python -m pytest -m perf`):** 200.000 satırlık view işte ortanca 34,5 sn; aynı satır Excel'den 52,6 sn.

**Tablo durumları:** Alındı, Hatalı, Tamamlanmadı (partisi vardır); Yeni veri yok, Veri güncellemesi devam ediyor, Atlandı, Hata (parti yok, önceki ham veri korunur).

**Liste:** `data-entities`'e Yöntem, Çekim, uyarı (satır alanı); `integration-entities`: Yöntem, Kaynak, Alan uyumu, Son durum, Son okuma; `import-findings` SQL partilerini de gösterir.

## Validasyon ve validasyon kuralları (ekran 02 ve 27, fonksiyon 04 ve 100, K-133…K-139)

Validasyon tablonun staging'deki işlenmiş katmanına aittir (ham katmanın güncel hâli, veri kuralları uygulanmış; K-140), partiye değil. Kuyruğa yazan uç nokta yoktur: Excel'de "Devam" (`POST /api/imports/{id}/continue`) ve çekimde tablonun okunması işi kendisi ekler; elle yol "Yeniden valide et"tir.

| Uç nokta | Yetki | Cevap |
|---|---|---|
| `GET /api/validation/{entity}` | Key user ve üstü (04 okuma) | Çekmece özeti: `state` (Sırada, Kurallar çalışıyor, Valide ediliyor, Bitti, Valide edilemedi), `outcome` (Geçti, Uyarılı, Hatalı), son parti (`received_at`, `method`, `uploaded_by_name`), `current_rows`, `error_rows`, `warning_rows`, `info_rows`, `error_rate`, `threshold` (boşsa `null`), `rules` (Bulgular görünümü, K-139: `[{id, name, severity, rows, message}]`; ağırdan hafife, çoktan aza; `message` yalnız tablo düzeyi bulguda, ör. "Karşılaştırılacak veri yok"). 404 `entity_not_found` |
| `POST /api/validation/{entity}/revalidate` | Key user ve üstü (04 yazma) | **202** `{job_id}`; tablonun zinciri sıraya girer (işlenmiş katman ham veriden kurulur, kurallar baştan uygulanır; K-142). Aynı tabloda sırada ya da çalışan validasyon varsa 409 `validation_running`. Güncel verisi yoksa 409 `validation_no_data`. İz "Yeniden validasyon" |
| Ortak liste `validation-data-<entity>` | Key user ve üstü | Aynı satırlar, Kuralla değişenler ve Tüm satırlar için: Satır, kaydın alanları, "Değiştiren kural" (`RuleNames`), en sonda Sorun ve Sınıf (K-144) |
| Ortak liste `validation-records-<entity>` | Key user ve üstü | İşlenmiş katmanın bütün satırları (K-140, K-143): ilk kolonlar Sorun (satırın bulguları) ve Sınıf (en ağır; bulgusuz satırda boş), sonra Satır ve sözleşmedeki bütün alanlar (etiketli ek alanlar dahil). Yalnız süzmede kullanılan (`filter_only`, kolon listesinde yok, K-144) `HasFindings`, `HasEffects` ve `RuleIds` üç seçeneğin ve kurala göre süzmenin sabit filtresidir: Bulgulu satırlar `HasFindings = 1`, Kuralla değişenler `HasEffects = 1`, Tüm satırlar filtresiz. Gizli `RuleIds` (",12,15,") kurala göre süzmek içindir: `contains` ",12," (Bulgular'da kurala tıklayınca, K-139). Excel'e aktarımı "Hatalı kayıtları indir"dir (K-91, K-93) |
| Ortak liste `validation-rules` | Admin ve üstü yazar, Key user okur (100) | Tablo, Kural (kullanıcı dilinde ad), Koşul (`ConditionText`), Sınıf, Mesaj, Tür, Aktif; gizli Kod. Yapısal kontroller listede yoktur (K-139). Satırda `Editable` (pencerede düzenlenir) ve `IsCustomized` |
| `GET /api/validation-rules/{id}` | Key user ve üstü (100 okuma) | Kural ve koşulları (`groups: [[{field, operator, value, compare_field}]]`); `editable`, `customized` (düzenlenmiş hazır kural) |
| `GET /api/validation-rules/fields/{entity}` | Key user ve üstü (100 okuma) | Koşul editörünün alanları: ad, etiket, tip, değer listesi |
| `PUT /api/validation-rules` · `{changes: [{id?, entity, name?, severity?, message?, active?, groups?, delete?, reset?}], thresholds: [{entity, value}]}` | Admin ve üstü (100 yazma) | Toplu kayıt (K-132), tek işlem: biri geçersizse hiçbiri yazılmaz. Düzenlenebilir hazır kuralda ad, mesaj ve koşul değişir (ilk düzenlemede katalog koşulu veritabanına kopyalanır, `IsCustomized`); `reset` "İlk hâline döndür"dür (K-139). Düzenlenemeyen hazır kuralda ad, mesaj ya da koşul 422 `validation`. 422 `validation_rule_locked` (yapısal kural), `validation_rule_builtin_delete` (hazır kural silinemez), `validation_rule_bad_condition`, `validation_rule_name_taken`, `validation_threshold_range` (0–100). Cevapta değişen tablolar (`changed_entities`, "Yeniden valide et" önerisi için). İz "Validasyon kuralı", "Hata eşiği" |

**İş:** tip "Validasyon", kanal "Veri işleme" (sınır `JobLimitProcessing`), yükü `{entity, scope, trigger, batch_id, group}`; `scope` "Tablo içi" ya da "Tablolar arası"; `group` toplu çekimde çekim işinin Id'si. İş düşerse çalışma "Valide edilemedi", önceki bulgular kalır. İş cevabında `validation: {entity, name, trigger, group, scope, outcome, error_rows, warning_rows}` ve `created_at`: iş panelinin kartları (K-139) ve "Sonucu aç" (çekmece).

**Kural kataloğu:** `app/validation/catalog.py`, docs/06 fonksiyon 04 tablosuyla birebir (test); veritabanıyla çalışma anında eşitlenir (validasyon işi, kural listesi, kayıt); düzenlenmiş hazır kuralın adı, mesajı ve koşulu ezilmez (K-139).

**Ölçüm (`python -m pytest -m perf`, `tests/test_validation_perf.py`; satırların yarısı bulgulu, zor durum):** 200.000 satırlık Malzeme'nin tablo içi doğrulaması ortanca 39,4 sn (33,7–44,8). Sekiz tablo × 50.000 satır, paralel iş sayısına göre ortanca: 1 → 70,2 sn, 2 → 60,5 sn, 4 → 58,3 sn, 8 → 55,5 sn. Darboğaz SQL Server: 4'ten sonra kazanç %5 ve ölçümün kendi dağılımından küçük; `JobLimitProcessing` varsayılanı 4. Tablolar arası adım (referans, pasif ebeveyn ve bütünlük kuralları dahil 109 kural, K-146), 25 tablo × 50.000 satır, her 97. satırın kodu tanımsız: ortanca 56,5 sn (55,2–85,5; ilk koşu soğuk), 450.000 bulgu. Sunucuda ilk kurulumda yeniden ölçülür. Değerlendirme kümesel SQL'dir (`INSERT … SELECT`, kural başına); döngü kuralları Python'da, kenarlar tek sorguyla okunur. Geçiş ve kurulum eksik kuralı ekler; sınıfı ve aktifliği kullanıcıda kalır. Koşuldan SQL üretilir: alan adı sözleşmeden doğrulanır, değer parametreyle geçer.

## Veri kuralları (ekran 04, fonksiyon 16, 18, 19, K-140…K-142)

Kurallar staging'in işlenmiş katmanında çalışır (K-140); uygulama validasyon işinin ilk adımıdır (K-134), ayrı iş tipi yoktur. Kural kaydı kendiliğinden uygulanmaz; elle yol "Kuralları yeniden uygula"dır.

| Uç nokta | Yetki | Cevap |
|---|---|---|
| Ortak liste `data-rules` | Admin ve üstü yazar, Key user okur (16) | Tablo (ilk kolon), Sıra (tablo içinde satır numarası, 1'den boşluksuz; K-144), Kural, Koşul (`ConditionText`), Sonuç (`ResultText`), Seçenek, Aktif, Durum (`RunState`: Pasif, Uygulanmadı, Çalıştı, Çalışmadı; neden `LastRunMessage`, zaman `LastRunAt`; K-145), Tablo; varsayılan sıralama Tablo, Sıra |
| `GET /api/data-rules/{id}` | Key user ve üstü (16 okuma) | Kural: `entity`, `name`, `target`, `result: {kind, value, source_field, operator, operand_value, operand_field}`, `mode`, `active`, `groups: [[{field, operator, value, compare_field}]]` |
| `GET /api/data-rules/fields/{entity}` | Key user ve üstü (16 okuma) | Alanlar: ad, güncel etiket (veri sözlüğü), tip, değer listesi, `target` (hedef olabilir mi) ve olamıyorsa `reason` (anahtar alan); etiketsiz ek alan yok (K-144) |
| `PUT /api/data-rules` · `{changes: [{id?, entity, name?, target?, result?, mode?, active?, groups?, delete?}], orders: [{entity, ids}]}` | Admin ve üstü (16 yazma; sıra 18) | Toplu kayıt (K-132), tek işlem: biri geçersizse hiçbiri yazılmaz. Yeni kural tablonun sonuna eklenir; `orders` tablonun bütün kural Id'lerini yeni sırayla taşır, eksik ya da fazlaysa 409 `data_rule_order_stale`. Ad tabloda tekil (422 `data_rule_name_taken`); hedef anahtar ya da sistem alanıysa 422 `data_rule_bad_target`; sonuç tipe uymuyorsa 422 `data_rule_bad_result`; koşul geçersizse 422 `data_rule_bad_condition`. Cevap `{saved, changed_entities}`. İz "Veri kuralı" (kural başına eski ve yeni değer) ve "Kural sırası" |
| `POST /api/data-rules/apply` · `{entity?}` | Admin ve üstü (19 yazma) | **202** `{job_ids}`; `entity` doluysa o tablonun zinciri (tetik "Kural değişikliği"), boşsa kuralı olan bütün tabloların toplu yolu, tablolar arası validasyon sonda. Aynı tabloda sırada ya da çalışan validasyon varsa 409 `validation_running`. İz "Kuralları yeniden uygula" |

**Uygulama** (`app/validation/rules_step.py`): işlenmiş katman tek işlemde kurulur (`prc.<Tablo>` boşaltılır, `stg.<Tablo>`'nun güncel satırları kopyalanır, kural izi silinir); kurallar `Seq` sırasıyla, her biri kendi savepoint'inde çalışır. Koşul `conditions.where` ile SQL'e çevrilir, değerler parametreli gider; bölen `NULLIF(bölen, 0)`. Kuralın tamamını etkileyen veritabanı hatasında savepoint geri alınır, `LastRunStatus` "Çalışmadı". İş düşerse işlem geri alınır, işlenmiş katman önceki hâlinde kalır.

**Kayıtlar listesi** (`validation-records-<entity>`) işlenmiş katmanı okur; gizli `RuleEffects` alanı (`key_fields`, kolon değil) satırın kuralla değişen hücrelerini taşır: hücre başına alan, kural sırası, kural adı, ham değer (ayraç U+001F), hücreler arası U+001E; hücre izinin ipucu buradan gelir.

**Ölçüm (`python -m pytest -m perf`, `tests/test_data_rules_perf.py`):** 200.000 satırlık Malzeme'de işlenmiş katmanın kopyası ortanca 15,3 sn (dolu tabloda; ilk kopya 4,8 sn), kopya ve beş kural (sabit, alan kopyası, iki formül, koşullu bayrak) ortanca 32,2 sn (31,8–32,5). Süreyi çoğunlukla eski satırların silinmesi alır; uygulama hesabı `db_datareader` / `db_datawriter` olduğu için `TRUNCATE` kullanılmaz (K-109).

## Tam ve kısmi aktarım (ekran 02, fonksiyon 05, 06 ve 07, K-149…K-155)

Staging'in işlenmiş katmanını core'a yeni bir veri versiyonunda yazar; iş tipi "Aktarım", kanal "Veri işleme", aynı anda tek aktarım. Kural ve kimlik ayrıntısı K-153'te, kısmi aktarım K-155'te (yalnız seçilen grupların tabloları; veri versiyonu "Kısmi").

| Uç nokta | Yetki | Açıklama |
|---|---|---|
| `GET /api/transfers/plan` | Key user ve üstü (05 okuma) | Onay penceresi: tablo başına güncel satır, Hatalı, durum (Aktarılır / Eşik aşıldı / Staging'de veri yok), hata oranı ve eşik; `blocked` (başlatılamıyorsa nedeni ve tablolar) |
| `POST /api/transfers` | Key user ve üstü (05 yazma) | **202** `{job_id}`. 409 `transfer_blocked` (çekim, ön kontrol, validasyon ya da aktarım sırada ya da sürüyor; validasyonu bitmemiş tablo). İz "Tam aktarım" |
| `GET /api/transfers/partial/plan` | Key user ve üstü (06 okuma) | Kısmi aktarım penceresi (K-155): gruplar ve tabloları, tablo başına güncel satır, Hatalı, durum ve not; süren iş (`busy`), validasyonu bitmemiş tablolar (`pending`) |
| `POST /api/transfers/partial` · `{groups}` | Key user ve üstü (06 yazma) | **202** `{job_id}`. 422 `transfer_groups` (grup yok ya da bilinmiyor); 409 `transfer_blocked` (süren iş, seçilen gruplarda validasyonu bitmemiş tablo). İz "Kısmi aktarım" |
| `GET /api/transfers/{job_id}` | Key user ve üstü (08 okuma) | Veri aktarım raporu (K-156): iş durumu, tür (`transfer_type`) ve gruplar, başlatan, başlama, süre (`duration_seconds`), veri versiyonu; tablo başına yeni, değişen, kapatılan, aktarılmayan, not. Tablo satırları `DataVersionEntity`'den (iş sonucuna bağlı değil), iş `DataVersion.JobId` ile |
| `GET /api/transfers/{job_id}/excel` | Key user ve üstü (08 okuma) | Raporun Excel'i: Veri sayfasında tablo satırları, Bilgi sayfasında tür, gruplar, başlatan, başlama, süre, veri versiyonu, durum; iz "Dışa aktarım" (liste adı `transfer-report`) |
| Ortak liste `transfer-history` | Key user ve üstü (08 okuma) | Veri aktarım geçmişi (K-156): aktarım işleri, en yeni üstte; Tarih, Tür, Gruplar, Başlatan, Veri, Süre (sn), Durum, Yeni, Güncellenen, Silinen, Aktarılmayan (toplam), Hata, İş no. Versiyonu geri alınmış biten iş (sentetik sıfırlama) görünmez |

**İş:** yükü `{}` (tam) ya da `{mode: "Kısmi", groups}` (özet "Tam veri aktarımı" ya da "Kısmi veri aktarımı · Talep, Stok", K-157); ilerleme tablo adıyla ("Malzeme · 3 / 25"). İş cevabında `transfer: {data_version, tables}`; bildirimde "Tam veri aktarımı bitti · v12" (ya da "Kısmi veri aktarımı bitti · v13") ve "Sonucu aç"; iz işlem adı "Tam aktarım" / "Kısmi aktarım" kalır. İş düşerse işlem geri alınır, önceki versiyon geçerli kalır. Özet denetim kaydı (K-108): veri versiyonu ve tablo başına sayılar; kısmide gruplar.

**Ölçüm (`python -m pytest -m perf -k transfer`, `tests/test_transfer_perf.py`):** 25 tablo × 50.000 satır, her 97. satırın kodu tanımsız: ilk aktarım (hepsi yeni) ortanca 270,5 sn (241,0–283,6), ardından ikinci aktarım (hepsi değişmeyen) ortanca 220,4 sn (217,0–223,1). Kısmi aktarım (`-k partial`, K-155), Talep ve Stok grupları (6 tablo × 50.000 satır, tam aktarımın ardından, hepsi değişmeyen): ortanca 63,2 sn (62,9–79,3). Sürenin çoğu kod→Id çözümlemesi ve karşılaştırmadır; sınır 30 dk. Sunucuda ilk kurulumda yeniden ölçülür.

## Ham veri temizliği (ekran 02, fonksiyon 09, K-156)

Saklama süresini (`RawDataRetentionDays`, 1–30 gün; varsayılan yok) geçen partilerde güncel olmayan ham satırları, ön kontrol bulgularını ve yüklenen
Excel dosyalarını siler; terk edilen ön kontrol partisi "Vazgeçildi" olur. İş tipi "Temizlik", kanal "Veri işleme"; veritabanı değişiklikleri tek işlemde,
dosyalar commit'ten sonra silinir.

| Uç nokta | Yetki | Açıklama |
|---|---|---|
| `GET /api/cleanup` | 09 okuma (Key user ve üstü) | `retention_days` (boşsa `null`) ve `last` (son temizlik işi: durum, zaman, başlatan, sonuç) |
| `GET /api/cleanup/plan` | 09 yazma (System owner) | Onay penceresi: `preview` (parti, terk edilen ön kontrol, satır, dosya, boyut, tablo başına satır) ve `blocked` (süre yok ya da süren iş) |
| `POST /api/cleanup` | 09 yazma (System owner) | **202** `{job_id}`. 409 `cleanup_no_retention` ("Saklama süresi tanımlı değil; temizlik çalışmaz."), 409 `cleanup_blocked` (çekim, ön kontrol, validasyon, aktarım ya da temizlik sırada veya sürüyor). İz "Ham veri temizliği" |

**İş:** ilerleme tablo adıyla; sonuç `{retention_days, cutoff, batches, abandoned, rows, files, size, tables}`, süre boşsa `{note}`; bildirimde "Ham veri
temizliği bitti · 12 yükleme · 3.400 eski satır · 2 dosya" (K-157) ve "Sonucu aç" (Veri aktarım geçmişi çekmecesi). Özet iz: süre, parti, terk edilen, satır, dosya.
Temizlik sıradayken ya da sürerken aktarım da başlamaz.

**Ayar:** `GET` · `PUT /api/settings/health` `RawDataRetentionDays` taşır; `optional` listesinde, `null` gönderilirse ayar silinir (temizlik çalışmaz).
Öteki ayarlarda `null` 422.

**Ölçüm (`python -m pytest -m perf -k cleanup`, `tests/test_cleanup_perf.py`):** 25 tablo × 50.000 güncel olmayan satır (1.250.000 satır), partiler süreden eski: ortanca 40,3 sn (39,3–40,5); sınır 30 dk. Sunucuda ilk kurulumda yeniden ölçülür.

## Dünden bugüne (ekran 28, fonksiyon 101, K-159, K-160)

| Uç nokta | Yetki | Açıklama |
|---|---|---|
| Ortak liste `raw-compare` | 101 okuma (End user dahil) | Tablo başına: Dünkü veri, Bugünkü veri, Bugünkü yükleme, Dünkü satır, Bugünkü satır, Değişim %, Yeni gelen, Gelmeyen, Güncellenen, Durum (Hazır / Önceki veri yok / Hesaplanamadı / Veri yok) |
| Ortak liste `raw-compare-changes` | 101 okuma | Güncellenenler: Kayıt, Alan, Dünkü değer, Bugünkü değer; arayüz tabloyu sabit filtreyle verir |
| Ortak listeler `raw-compare-new-<tablo>`, `raw-compare-missing-<tablo>` | 101 okuma | Yeni gelenler ve Gelmeyenler: tablonun bütün alanları; Kayıt varsayılan gizli, Alanlar panelinden açılır (K-161) |
| `GET /api/raw-compare/summary` | 101 okuma | Ana sayfa için toplamlar: karşılaştırılan tablo, yeni gelen, gelmeyen, güncellenen, son veri zamanı |

Hesap tablo validasyon işinin başında yapılır; sonuç güncelse atlanır, düşerse `State` "Hesaplanamadı" olur ve validasyon sürer. Temizlik "dün" satırlarını silmez (K-160).

**Ölçüm (`python -m pytest -m perf -k raw_compare`, `tests/test_raw_compare_perf.py`):** 25 tablo × 50.000 satır, iki günlük hâl, satırların %10'unda bir alan değişik: 25 tablonun toplamı ortanca 29,6 sn (28,5–91,0; ilk koşu soğuk önbellekle), en yavaş tablo 5,8 sn. Hesap tablo başına validasyon işinin başındadır; tek tablo yüklemesine eklenen süre tablo başınadır. Sunucuda ilk kurulumda yeniden ölçülür.

## Zamanlanmış akışlar (ekran 23, fonksiyon 92, K-163)

| Uç nokta | Yetki | Açıklama |
|---|---|---|
| `GET /api/flows` | 92 okuma (System owner, Admin) | Akışlar: tanım, sıradaki çalışma, son çalışma (durum, adım, neden); `options`: SQL tabloları ve kısmi aktarım grupları |
| `POST /api/flows` · `PUT /api/flows/{id}` | 92 yazma (System owner) | Akış tanımı. 422 doğrulama (ad, saat SS:DD, en az bir gün, Kısmi'de en az bir grup, Seçilen'de en az bir SQL tablosu); 409 `flow_conflict` (aynı gün ve saatte başka aktif akış, adıyla). İz "Akış tanımlandı" / "Akış değiştirildi" |
| `POST /api/flows/{id}/run` | 92 yazma (System owner) | Şimdi çalıştır: çalıştırma "Bekliyor" olarak yazılır, zamanlayıcı aynı kurallarla başlatır; 409 `flow_running` (başka akış sürüyor). İz "Akış elle başlatıldı" |
| Ortak liste `flow-runs` | 92 okuma | Geçmiş: Akış, Tetik, Saati, Başlama, Bitiş, Durum, Adım, Neden, Veri; arayüz akışı sabit filtreyle verir |
| `GET /api/flows/status` | 01 okuma (Key user ve üstü) | `running` (ad, başlama) ve `alert` (son çalıştırma Durdu ya da Başlamadı ve kullanıcı kapatmadıysa: ad, durum, adım, neden, zaman); bağlam çubuğu ve ana sayfa okur |
| `POST /api/flows/runs/{id}/dismiss` | 01 okuma | Kullanıcı çipi kapatır |

Akış sürerken çekim, Excel yükleme ve devam, tam ve kısmi aktarım, ham veri temizliği, veri kuralı kaydetme ve yeniden uygulama, validasyon kuralı ve eşik kaydetme, Entegrasyon tablo ayarları 409 `flow_running` ("Zamanlanmış akış sürüyor: <ad> (başlama 02:00). Bitince yeniden deneyin."). Tam ve kısmi aktarımın plan cevabında tablo başına `failed_rules` (çalışmayan veri kuralı sayısı).

## Excel şablonu (ekran 02, fonksiyon 02, K-110)

| Uç nokta | Cevap |
|---|---|
| Ortak liste `data-entities` | `Name`, `EntityClass`, `Description`, `Version`, `FieldCount`, `RequiredCount`, `LastLoadAt` (Alındı, Doğrulandı ya da Yüklendi partinin en yeni zamanı), `CatalogOrder`, `Entity` (varsayılan gizli); `LastTransferAt` ve `LastTransferType` (tablonun yazıldığı son aktarım; yazılmadığı aktarım ve sentetik yükleme sayılmaz), `HasNewData` (son aktarımdan sonra veriye alınmış yükleme; K-158). Şablon bilgisi alanları varsayılan gizli. 25 tablo; kaynak docs/03 kataloğu, etiketli ek alanlar `FieldDefinition`'dan sayılır |
| `GET /api/templates/{entity}/info` | `entity`, `name`, `version`, `file_name`, `field_count`, `required` (etiketler). Bilinmiyorsa 404 `entity_not_found` |
| `GET /api/templates/{entity}` | xlsx; `smartchain_<kısa ad>_v<sürüm>.xlsx`. İz "Şablon indirme" aynı işlemde; yazılamazsa dosya yok, 503 `audit_failed` |

Hepsi fonksiyon 02 okuma: System owner, Admin, Key user; End user 403. Üretici `app/integration/template.py` veritabanı bilmez; etiketleri servis verir, kirli Excel (docs/11) veri setinden alır.

## WebSocket mesajları (fonksiyon 48)

API, `adm.Job`'u `UpdatedAt` ile izler ve değişen işi sahibinin bağlantılarına iter (K-69). Sıradaki işlerin sırası değişince onlara da mesaj gider. Ara durumlar izleme aralığında birleşebilir; istemci her mesajı işin son hali olarak alır.

```json
{"type": "hello", "user_id": 3}
{"type": "job", "job": {"id": 61, "job_type": "Çalışma", "channel": "Hesaplama", "status": "Çalışıyor",
 "progress": "Çözülüyor", "queue_position": null, "attempt": 1, "is_stale": false, "...": "GET /api/jobs/{id} ile aynı alanlar"}}
{"type": "pong"}
{"type": "health"}
```

İstemci `ping` metni gönderirse `pong` döner (bağlantı denetimi; oturumu uzatmaz).

Bağlantı oturumla açılır (çerez; `Origin` denetimi K-97). Oturum biterse (çıkış, zaman aşımı, şifre değişince diğer oturumlar) API soketi 4401 koduyla kapatır; arayüz yeniden bağlanmaz, oturumu denetler. Zaman aşımı API'nin iş izleyicisinde 30 sn'de bir taranır.

Geliştirme demosu: API açıkken `python scripts/job_demo.py --url ws://127.0.0.1:8000/api/ws`; demo kullanıcısı adına iş ekler, sahte işçi gibi çalıştırır ve gelen bildirimleri yazdırır. Demo kullanıcısının şifresi yoktur (arayüzden giremez); script WebSocket için oturumu veritabanında kendisi açar.
