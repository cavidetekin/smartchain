# Motor arayüzü

Adım 0.5'te kurulan sözleşme. Motor baştan sabit bu arayüzle çalışır: Aşama 10'a kadar sahte motor fikstür döndürür, gerçek motor (MDD 18) aynı arayüzle yerine geçer (10.8). Kod: `app/engine/`.

## Akış

1. **İstek:** Yeniden hesap (46) ya da gece akışı (40) `submit_plan_run` çağırır: PlanRun `Sırada` ve iş kaydı (`adm.Job`, Payload `{"plan_run_id": …}`) tek commit'te. Kanal: etkileşim (iş türü Çalışma) ya da gece (Gece senaryosu).
2. **Motor servisi** (üst süreç, `python -m app.engine.service`; Windows servisi 0.6'da): kanal sınırına göre işi alır (K-68) ve her işi ayrı süreçte başlatır (01-mimari · iş yalıtımı).
3. **İş süreci:** PlanRun `Çalışıyor` → girdi okunur → motor çalışır (adım geçişlerinde ilerleme yazar) → sonuç, PlanRun durumu ve işin bitişi **tek işlemde** yazılır.
4. **Bildirim:** API iş tablosunu izler, ilerleme ve sonuç WebSocket'le iş sahibine gider (K-69).

## Sözleşme (`app/engine/interface.py`)

| Parça | İçerik |
|---|---|
| `EngineInput` | `plan_run` (PlanRunInfo), `parameters` (ParameterSetData), `data` (PlanningData), `time_budget_seconds` |
| `PlanRunInfo` | Id, DataVersionId, ParameterSetId, ScenarioId, WorkspaceId |
| `ParameterSetData` | Set adı; PlanningSetting (anahtar → değer); TimeBucketDefinition dizisi; PriorityRule sırası; AllocationRule satırları |
| `PlanningData` | Salt okunur veri erişimi: `read(table, columns)` PlanRun'un veri versiyonundaki `core.*` satırlarını verir. Versiyonlu tabloda `VersionFrom ≤ v` ve `VersionTo` boş ya da `≥ v`; versiyonsuz tabloda tümü. Yalnız `core` okunur (K-58); tablo ve alan adları docs/02'ye göre doğrulanır. Sahte motor kullanmaz; gerçek motor ön hesapta (29) bununla okur. |
| `Engine.run(input, progress)` | `PlanResult` döndürür; veritabanına yazmaz. `progress(adım)` her adım geçişinde çağrılır. İş diliyle hata: `EngineError` (mesaj kullanıcıya gösterilir). |
| `PlanResult` | EngineUsed (LP \| MILP \| Kurallı \| Kısıtsız MRP), Solver, Status (Bitti \| Kısmen); tablo başına satırlar (PlannedOrder, SupplyRecommendation, DemandFulfillment, CapacityLoad, Pegging, PlanWarning) docs/02 alan adlarıyla; metrikler (PlanMetric); SolverLog. |

- Planlı siparişe `ref` verilebilir; Pegging satırı `supply_ref` ile ona bağlanır. Yazıcı SupplyType'ı `Planlı sipariş`, SupplyId'yi oluşan Id yapar.
- Id, PlanRunId ve UpdatedAt'i yazıcı doldurur; bilinmeyen alan hata verir ve hiçbir şey yazılmaz.
- Adımlar (29–39): Ön hesap · MRP patlatma · Model kurma · Çözüm · Son hesap · Uyarı ve metrik.

## Sonucun yazılması (K-70)

- Önceki çıktıları sil → yeni çıktılar → PlanMetric, SolverLog → PlanRun (Status, EngineUsed, Solver, EndedAt) → iş Bitti: **aynı session, tek commit** (01-mimari · yarım plan görünmez). İş artık bu denemenin değilse (geri alındı, sonlandırıldı) hiçbir şey yazılmaz. Commit'ten sonra süreç çökse de iş Bitti olduğu için yeniden çalışmaz.
- Silip yeniden yazma yalnız yayınlanmamış PlanRun içindir. Yayınlanmış (PlanVersion'da geçen) PlanRun'un çıktıları değişmez; ona yazmak isteyen iş Hata olur. Yeniden hesap yeni PlanRun açar.
- Hata yolu da tek işlemde: PlanRun Hata + iş Hata (mesajıyla).

## PlanRun durumu

`Sırada` (istek) → `Çalışıyor` (iş süreci başladı) → `Bitti` \| `Kısmen` (motorun sonucu) \| `Hata` (motor hatası, süre bütçesi, deneme hakkı bitti).

## Motor servisi (K-71)

- **Kalp atışı servisten:** Servis her çalışan iş için `EngineHeartbeatSeconds` (15) aralıkla kalp atışı yazar; iş süreci yaşadıkça gider, çözücü GIL'i bırakmasa da etkilenmez. İş süreci yalnız adım geçişlerinde ilerleme (Progress) yazar.
- **Süre bütçesi:** Kanal bütçesi (`EngineTimeBudgetInteractiveSeconds` 180, `EngineTimeBudgetNightSeconds` 1800) + pay (`EngineKillGraceSeconds` 60) aşılırsa servis süreci sonlandırır; iş ve PlanRun Hata. Bütçe motora da `time_budget_seconds` olarak geçer (34: çözücüye süre limiti, en iyi çözümü sakla).
- **Çöküş:** İş süreci işi bitirmeden kapanırsa servis işi hemen geri alır: deneme hakkı varsa Sırada, yoksa Hata (K-67).
- **Takılan iş:** Servis `requeue_stale`'i açılışta ve 15 sn'de bir çalıştırır; API'deki izleyici de çalıştırır. Kuyruk kilidi ikisini sıraya koyar.
- **Geri alınan iş:** Kalp atışı yazılamıyorsa (iş başka denemeye geçti) servis süreci sonlandırır.
- Log: servis `logs/engine.log`, iş süreçleri servisin konsoluna.
- **İş tipine göre yönlendirme (K-93):** servis işi tipine göre kendi sürecinde çalıştırır: "Dışa aktarım" işleri Excel dosyasını üretir (`app/api/export`), diğerleri plan hesabıdır. Kanallar ayrı sınırlıdır: Etkileşim (`JobLimitInteractive`), Gece (`JobLimitNight`), Dışa aktarım (`JobLimitExport`, 2); büyük indirmeler yeniden hesabı bekletmez. Dışa aktarımın süre bütçesi etkileşim bütçesinin on katıdır (500.000 satır sığsın).
- **Dosya temizliği:** servis `SMARTCHAIN_EXPORT_DIR`'deki süresi geçmiş (`ExportFileHours`) dosyaları açılışta ve saatte bir siler.

## Çözücü (K-35, K-76)

- **Yer:** Çözücüye özel kod yalnız `app/engine/solvers/` altındadır; motorun başka hiçbir yeri çözücü paketini (`highspy`) import etmez (bekçi testi: `tests/test_offline.py`). Adaptör arayüzü (kur / çöz / oku, fonksiyon 32) 10.5'te yazılır; yeni çözücü yeni adaptör demektir.
- **Aday:** HiGHS (`highspy` 1.15.1, MIT). LP ve MILP aynı pakette. Çözücü seçimi açık (A-16, A-31).
- **Süre:** Çözücünün zaman limiti, işin süre bütçesinden (`EngineInput.time_budget_seconds`) ön hesap ve MRP payı düşülerek verilir (fonksiyon 34-02, 10.5). HiGHS'te `time_limit` seçeneği. Servisin öldürme payı (K-71) bunun üstünde son güvencedir.
- **İş parçacığı:** `SolverThreads` sistem ayarı (2) → HiGHS'in `threads` seçeneği. HiGHS bu değeri süreç başına bir kez alır; her iş kendi sürecinde çalıştığı için (K-71) iş başına ayarlanmış olur. Öneri: (`JobLimitInteractive` + `JobLimitNight`) × `SolverThreads` ≤ sunucunun çekirdek sayısı.
- **Günlük:** Çözücü konsola yazmaz (`output_flag` kapalı); SolverLog'a yazılması 10.5'te.
- **Model ve çözüm dosyaları (K-77):** Her plan hesabı için `ProgramData\Smartchain\solver\<tarih>\PlanRun-<Id>\` klasörüne model dosyası (LP), çözüm dosyası ve çözücü logu yazılır. Değişken ve kısıt adları okunur (ör. `Uretim[MAT-001,H44]`). Yazma kipi (her zaman / yalnız hata ya da süre aşımında / kapalı) ve saklama süresi sistem ayarıdır; ayar adları 10.5'te 02-veri-modeli SystemSetting listesine eklenir. Dosyalar destek paketine (95) girer. Uygulama 10.5'te, adaptörle birlikte.
- **Paket kontrolü:** `app/engine/solvers/highs.py: smoke_test(time_limit, threads)` iki sabit modeli çözer ve bilinen sonucu doğrular:
  - LP: max 3x + 5y; x ≤ 4, 2y ≤ 12, 3x + 2y ≤ 18 → x = 2, y = 6, amaç 36, gölge fiyatlar 0, 1,5, 1.
  - MILP: aynı model, 3x + 2y ≤ 17 ve x, y tamsayı → x = 1, y = 6, amaç 33 (gevşetilmiş LP 35).

  Kurulumdan sonra `verify.ps1` (duman testi) bunu da yürütür.

## Sahte motor (`app/engine/fake.py`)

- `fixtures/plan_v0.json`'u döndürür: 3 planlı sipariş, 1 mevcut arz önerisi, 2 talep karşılama, 2 doluluk, 3 pegging, 2 uyarı, 4 metrik. Malzeme, kaynak ve sipariş Id'leri sentetik veri (0.8) gelene kadar yer tutucudur; plan fikstürü 8.0'da sentetik veriye göre yeniden hazırlanır.
- Uyarı kodları (`CAP_OVERLOAD`, `ORDER_LATE`) WarningDefinition'da yoksa geliştirme ve testte `ensure_fixture_warning_definitions` ekler; tanımlar 7.5'te ekrandan gelir.
- EngineUsed parametre setindeki `ModelType`'tır (yoksa LP), Solver `Sahte`.
- Sahte motora özel PlanningSetting anahtarları (gerçek motor okumaz):

| Anahtar | Değer | Ne |
|---|---|---|
| `FakeEngineStepSeconds` | sayı (0) | Her adımda bekleme; uzun hesap, kalp atışı ve süre bütçesi denemesi |
| `FakeEngineMode` | normal \| crash \| error | crash: Çözüm adımında süreç beklenmedik biter · error: Model kurmada motor hatası |

## Durum

| Parça | Durum |
|---|---|
| Arayüz, sahte motor, yazıcı, iş süreci, motor servisi (konsol) | uygulandı (0.5) |
| Çözücünün yeri, HiGHS paketi ve paket kontrolü | uygulandı (0.7) |
| Model ve çözüm dosyalarının klasöre yazılması (K-77) | 10.5 |
| Windows servisi olarak kurulum | 0.6 |
| İş tipine göre yönlendirme, dışa aktarım kanalı ve dosya temizliği | uygulandı (1.5) |
| Gerçek motor (29–39), sıcak çalışma belleği | Aşama 10 |

Demo: API açıkken `python scripts/engine_demo.py`; plan hesapları gönderir, servisi çalıştırır, WebSocket'ten ilerlemeyi ve sonuç satır sayılarını yazdırır.
