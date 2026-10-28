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
- API belgesi `/api/docs` yalnız geliştirmede açılır (`SMARTCHAIN_ENABLE_DOCS=true`); dışarıdan JavaScript yüklediği için kurulum paketinde kapalıdır (kapalı ağ kuralı).

## Hata cevabı

Her hata aynı biçimde döner; mesaj Türkçe ve kullanıcıya gösterilebilir:

```json
{"error": {"code": "material_not_found", "message": "Malzeme bulunamadı.", "trace_id": "445ecdbb3634", "details": []}}
```

- **İş kuralı hatası:** servis `AppError(code, message, status_code)` fırlatır.
- **Girdi hatası (422):** `code = "validation"`; `details` her hatalı alanı (`field`, `problem`) listeler.
- **Veritabanına ulaşılamıyor (503):** bağlantı kurulamaz ya da havuzda boş bağlantı kalmazsa (havuz zaman aşımı) her uç nokta `code = "database_unavailable"` döner; 500 değildir. Ön yüz bunu "Veritabanına ulaşılamıyor" diye gösterir.
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
| `SMARTCHAIN_EXPORT_DIR` | `exports` · arka planda hazırlanan Excel dosyaları (K-93); süresi geçenleri motor servisi siler |

## Liste sorgusu (K-87)

Bütün tablolar (ana veri, plan, rapor) aynı sözleşmeyle okunur. Filtre, sıralama ve parça parça yükleme sunucuda yapılır (U-21); ön yüzdeki ortak tablo bileşeni (docs/12) bu sözleşmeyi kullanır. Her liste sunucuda bir liste tanımıdır (`app/api/lists/`): tablo, alanlar ve sırası, varsayılan görünür alanlar, varsayılan sıralama.

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

İstek: `{"group_by": ["MaterialLevel", "MaterialGroup"], "fields": ["SafetyStock", …], "aggregates": {"SafetyStock": {"fn": "sum"}, "ProductionLeadTimeDays": {"fn": "wavg", "weight": "SafetyStock"}}, "filters": [...], "sort": [...]}`. `aggregates` verilmezse görünen kolonlarda (`fields`) liste tanımının varsayılanı kullanılır. Cevap:

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

Kullanıcı şimdilik `user_id` sorgu parametresiyle gelir (A-36).

| Adres | Ne |
|---|---|
| `GET /api/<liste>/views?user_id=` | `{"views": [...], "default_view_id": 4 \| null}`; kendi görünümleri ve başkalarının paylaşılanları. Her görünüm: `id`, `name`, `owner_user_id`, `owner_name`, `is_shared`, `is_owner`, `updated_at`, `definition`, `warnings` |
| `POST /api/<liste>/views?user_id=` | Yeni görünüm: `{"name", "is_shared", "definition"}` → 201 ve görünüm |
| `PUT /api/<liste>/views/{id}?user_id=` | Ad, paylaşım ya da içerik değişir; yalnız sahibi |
| `DELETE /api/<liste>/views/{id}?user_id=` | Siler (varsayılan yapılmışsa o seçimler de kalkar); yalnız sahibi |
| `PUT /api/<liste>/views/default?user_id=` | `{"view_id": 4}` ya da `{"view_id": null}` (Standart) |

**İçerik** (`definition`, sürüm 1):

```json
{"v": 1, "columns": [{"field": "Code", "width": 7.5}, {"field": "Name", "width": null}], "pinned": 1,
 "sort": [{"field": "Code", "dir": "asc"}], "filters": [{"field": "UpdatedAt", "op": "relative", "value": "this_week"}],
 "group_by": ["MaterialLevel"], "aggregates": {"ProductionLeadTimeDays": {"fn": "wavg", "weight": "SafetyStock"}}}
```

- `columns` görünen alanlar, görünen sırada; `width` rem (boşsa tipin varsayılanı). `pinned` soldan sabit kolon sayısı. `aggregates` kullanıcının varsayılandan farklı seçtiği ara toplam türleri (K-90).
- Göreli tarih filtresi göreli saklanır; görünüm açıldığı günün haftasına göre çalışır.
- Kaydederken alanlar ve filtreler liste tanımına göre doğrulanır (422). Açılırken artık olmayan alanlar atılır, `warnings`'te yazar.
- Hatalar: sahibi değilse 403 `view_not_owner`; aynı adda görünüm varsa 409 `view_name_taken`; görünüm yoksa 404 `view_not_found`; kullanıcı yoksa 404 `user_not_found`.
- "Standart" görünüm veritabanında değildir: liste tanımındaki varsayılan alanlar ve sıralamadır, silinemez.

### Değerler · `POST /api/<liste>/values`

Liste filtresinin seçenekleri: `{"field": "MaterialGroup", "search": "döv", "filters": [...]}` → `[{"value": "Dövme", "count": 12}, …]`. Diğer filtreler uygulanmış hâldeki ilk 100 farklı değer, değere göre sıralı; `search` içerir araması yapar. Yalnız `filter: "list"` alanlarda çalışır.

## Dışa aktarım (K-91, fonksiyon 86)

`POST /api/<liste>/export?user_id=` (kullanıcı A-36 gereği şimdilik parametreyle). İstek, ekrandaki görünüm durumu ve kapsam:

```json
{"fields": ["Code", "Name", "SafetyStock"], "widths": {"Code": 7.5}, "sort": [{"field": "Code", "dir": "asc"}],
 "filters": [...], "group_by": ["MaterialLevel"], "aggregates": {"SafetyStock": {"fn": "sum"}},
 "scope": {"rows": "filtered", "columns": "visible"}}
```

- `scope.rows`: `filtered` (ekrandaki filtrelerle) ya da `all` (filtresiz); `scope.columns`: `visible` (`fields`, ekrandaki sırayla) ya da `all` (listenin bütün alanları: önce görünenler, sonra diğerleri). Gruplama ve ara toplamlar istekteki gibi (ekrandaki gibi) her zaman yazılır; Bilgi sayfası her dosyada vardır (K-91).
- Satır sayısı `ExportSyncMaxRows` (10.000) ve altıysa **200**: dosya gövdede (`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`), adı `Content-Disposition`'da.
- Üstüyse **202** `{"job_id": 81, "file_name": "…", "rows": 142000}`: iş "Dışa aktarım" kanalında (K-93). İlerleme ve bitiş WebSocket iş mesajlarıyla gelir; iş sonucu `{"file_name", "size", "rows"}`.
- `ExportMaxRows`'u (500.000) aşarsa 422 `export_too_large` ("filtreyi daraltın").
- İz: her aktarım `adm.AuditLog`'a yazılır (Action "Dışa aktarım", ObjectType liste adı, ObjectKey dosya adı, NewValue JSON: kapsam, filtreler, kolonlar, satır sayısı, boyut, süre, veri versiyonu); arka planda iz, dosya hazır olunca iş bitişiyle aynı işlemde yazılır. İz yazılamazsa dosya verilmez (anlıkta 503, arka planda iş Hata).

`GET /api/exports/{job_id}/file?user_id=`: arka planda hazırlanan dosya. Yalnız işi başlatan indirir (başkası 403 `export_not_owner`); iş bitmediyse 409 `export_not_ready`; süresi (`ExportFileHours`, 24 saat) geçtiyse ya da dosya silindiyse 410 `export_expired`.

Dosya: veri sayfası (başlık dondurulur, otomatik filtre; kolon genişlikleri ekrandan; başlık ve grup satırları ekrandaki tonlarla; grup başlığında ad, satır sayısı ve ara toplamlar değer olarak) ve Bilgi sayfası. Sayılar sayı, tarihler tarih, Türkçe biçim (K-92).

## Testler

- `python -m pytest`: bütün testler, **performans testleri hariç** (`pyproject.toml`: `-m 'not perf'`). Veritabanı testleri (`db` işareti) yerel SQL Server'a bağlanamazsa atlanır.
- `python -m pytest -m perf`: performans testleri ayrıca çalıştırılır. Büyük veriyi bir işlem içinde üretir, ölçer ve geri alır; her ölçüm birkaç denemenin ortancasıdır (makine yükündeki tek seferlik sıçramalar sonucu bozmasın).
- Ön yüz: `cd app/web; npm test; npx tsc --noEmit; npm run build`. Test süresi sınırı 15 sn (`vite.config.ts`): dosyalar paralel çalıştığı için yük altında jsdom testleri varsayılan 5 sn'yi aşabilir; tek başına bir test 2 sn'nin altındadır.
- Bunların hepsi geçmeden commit ve push yapılmaz (CLAUDE.md).

## Uç noktalar

| Adres | Ne | Durum |
|---|---|---|
| `GET /api/health` | Uygulama sürümü, veritabanı bağlantısı, şema sürümü (beklenen ile karşılaştırma). Sorun varsa 503 ve Türkçe açıklama. Sistem sağlığı ekranının (24) çekirdeği. | uygulandı (0.3) |
| `GET /api/jobs?user_id=` | Çalışan, sıradaki ve son 24 saatte biten işler (önce çalışan, sonra sıra); kanal sayaçları (çalışan, sırada, sınır). `user_id` verilirse yalnız o kullanıcının işleri (geçici, A-36). Bağlantı kopunca istemcinin son durumu sorguladığı yer (fonksiyon 48). | uygulandı (0.4) |
| `GET /api/jobs/{id}` | İşin durumu, ilerlemesi, sıra numarası, süresi, `is_stale` (kalp atışı eşiği aşıldı). Yoksa 404 `job_not_found`. | uygulandı (0.4) |
| `POST /api/jobs/{id}/cancel` | Sıradaki işi iptal eder. Çalışan iş 409 `job_not_cancellable` (durdurma motorda, fonksiyon 93). Yetki kuralı 2.2'de. | uygulandı (0.4) |
| `GET /api/data-versions/current` | En son veri versiyonu: Id, lokasyon kodu, oluşma zamanı, tam/kısmi, sentetik mi. Yoksa 404 `no_data_version`; veritabanına bağlanılamazsa 503 `database_unavailable`. Bağlam çubuğunun veri versiyonu (docs/12). | uygulandı (1.1) |
| `GET /api/materials/columns` · `POST /api/materials/query` · `POST /api/materials/values` | Malzeme listesi, liste sorgu sözleşmesiyle (K-87). Şimdilik tablo bileşeni denemesi (`/tablo`); malzeme ekranı 6.1'de. | uygulandı (1.3) |
| `POST /api/materials/groups` · `/api/materials/views…` | Gruplama ve ara toplam (K-90), kayıtlı görünümler (K-89) | uygulandı (1.4) |
| `POST /api/materials/export` · `GET /api/exports/{job_id}/file` | Excel'e aktarım: anlık ya da arka planda (K-91, K-93) | uygulandı (1.5) |
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
