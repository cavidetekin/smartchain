# Motor arayüzü

Adım 0.5'te kurulan sözleşme. Motor baştan sabit bu arayüzle çalışır: Aşama 10'a kadar sahte motor fikstür döndürür, gerçek motor (MDD 18) aynı arayüzle yerine geçer (10.8). Kod: `app/engine/`.

## Akış

1. **İstek:** Yeniden hesap (46) ya da gece akışı (40) `submit_plan_run` çağırır: PlanRun `Sırada` ve iş kaydı (`adm.Job`, Payload `{"plan_run_id": …}`) tek commit'te. Kanal: hesaplama (iş türü Çalışma) ya da gece (Gece senaryosu).
2. **Motor servisi** (üst süreç, `python -m app.engine.service`; Windows servisi 0.6'da): kanal sınırına göre işi alır (K-68) ve her işi ayrı süreçte başlatır (01-mimari · iş yalıtımı).
3. **İş süreci:** PlanRun `Çalışıyor` → girdi okunur → motor çalışır (adım geçişlerinde ilerleme yazar) → sonuç, PlanRun durumu ve işin bitişi **tek işlemde** yazılır.
4. **Bildirim:** API iş tablosunu izler, ilerleme ve sonuç WebSocket'le iş sahibine gider (K-69).

## Sözleşme (`app/engine/interface.py`)

| Parça | İçerik |
|---|---|
| `EngineInput` | `plan_run` (PlanRunInfo), `parameters` (ScenarioParameters), `data` (PlanningData), `time_budget_seconds` |
| `PlanRunInfo` | Id, DataVersionId, ScenarioDefinitionId (hesabın parametrelerini taşıyan senaryo tanımı, K-175), ScenarioId, WorkspaceId |
| `ScenarioParameters` | Senaryonun parametrelerinin tamamı (K-175; 7.1'de `ParameterSetData`'nın yerini aldı): senaryo adı; `settings` (PlanningSetting anahtar → değer, katalogdaki başlangıç değerleriyle tamamlanmış; docs/06 fonksiyon 22); `time_buckets` (plan ekseni: dönem tipi, kapsam, kapsam birimi; takvim kuralları fonksiyon 23, hesap `app/params/horizon.py`); `report_buckets` (raporlama ekseni; planla aynıysa plan dizisi); `objectives` (aktif hedefler sırasıyla: kod, öncelik grubu, süre bütçesi, ödün payı); PriorityRule sırası |
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
- **İş tipine göre yönlendirme (K-93):** servis işi tipine göre kendi sürecinde çalıştırır: "Dışa aktarım" işleri Excel dosyasını üretir (`app/api/export`), diğerleri plan hesabıdır. Kanallar ayrı sınırlıdır: Hesaplama (`JobLimitInteractive`), Gece (`JobLimitNight`), Dışa aktarım (`JobLimitExport`, 2); büyük indirmeler yeniden hesabı bekletmez. Dışa aktarımın süre bütçesi etkileşim bütçesinin on katıdır (500.000 satır sığsın). "Excel ön kontrol" işleri yüklenen dosyayı kontrol edip ham veriye yazar (K-129).
- **Veri çekme (K-130):** "Veri çekme" tipi ve kanalı (sınır `JobLimitPull` 1, süre bütçesi gece kanalıyla aynı). Elle ve gece çekim bu kanalı kullanır. Süreç `app/engine/pull_job.py`, gövde `app/api/services/pull.py`. Sonuç iş kaydına yazılır; süreç düşerse parti Tamamlanmadı olur, yeniden denemede tablo baştan okunur.
- **Validasyon (K-134, K-139):** "Validasyon" tipi, "Veri işleme" kanalı (sınır `JobLimitProcessing` 4; ölçüm docs/08). Rules (işlenmiş katman ham veriden kurulur, tablonun veri kuralları sırayla çalışır; K-140, K-141), tablo içi ve tablolar arası validasyon bu kanalda; yük `{entity, scope, trigger, batch_id}`. Tetikler: Yükleme, Çekim, Toplu çekim, Yeniden valide et, İlişkili tablo, Kural değişikliği ("Kuralları yeniden uygula", K-142). Toplu çekimde tablolar arası iş, tablo içi işlerin hepsi bitince sıraya girer. Süreç `app/engine/validation_job.py`, gövde `app/api/services/validation.py`. İş düşerse çalışma "Valide edilemedi", önceki bulgular kalır.
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

## Kaynak modeli notları (7.5, K-180)

- Planlama birimi kaynak grubudur: rota ve iş emri operasyonu kaynak grubunu ve gruptan aynı anda kullanılan kaynak adedini verir; kaynak alanı yoktur. Plan ve yük grup düzeyindedir (`CapacityLoad.ResourceGroupId`).
- Kapasite kaynak grubu × kaynak × gün hesaplanır, grupta toplanır (K-185; `app/capacity/compute.py`); gruptaki kaynak sayısı `ResourceGroupMember`'dan bilinir. Birden fazla gruba üye kaynak her grupta o grubun değeriyle hesaplanır.
- Motor yalnız kritik grupları kısıtlar (K-185); kritik olmayan grup (`ResourceGroup.IsCritical` = Hayır) sonsuz kapasiteli sayılır ve yalnız raporlanır (kapasitesi yine hesaplanır, Kapasite özeti'nde görünür).
- Birden fazla gruba üye kaynağın (ortak üye, ör. iki yetkinliği olan işçi) kapasitesini yalnız kritik grupların yükü kullanır.
- Kaynağı olmayan kritik grubun kapasitesi sıfırdır; doğrulama ve veri kalitesi uyarır (`RG.NO_RESOURCE`).
- Tip bilgisi grubun bayraklarından okunur (`IsEmployee`, `IsMachine`, `IsSubcontractor`…); kaynaktaki ham tip yalnız bilgidir. Vardiya kavramı yoktur.

## Dönem değerleri (7.8, K-184)

Kapasite gibi dönem bazındaki değerlerin tek bir hesabı vardır. Kapasitede: `app.periods.values(session, "resource-capacity-day", senaryo, gün aralığı)` → kaynak grubu × kaynak × gün satırları (`WorkingDay`, `Downtime`, `DailyCapacity`, `Capacity`, `AvailableCapacity`, `OvertimeLimit`; senaryonun Baz'dan okuduğu girişler dahil). Ekran bu işlevle kurulan önbellekten okur; motor plan hesabında aynı işlevi doğrudan çağırır (önbellekten okumaz). İkisinin birebir aynı sonucu verdiği testle sabittir (`tests/test_capacity.py`). Motorun veri erişimi (7.9c, K-188): `PlanningData.period_values(name, date_from, date_to)` planın senaryosu için bu işlevi çağırır (`SqlPlanningData`; ad `"resource-capacity-day"`). Girişler senaryoludur ve versiyonlanmaz: hesap güncel girişleri ve güncel üyelikleri okur (planın veri versiyonu eskiyse de). Sahte motor kullanmaz.

## Model kısıtları (7.10, K-189)

`PlanningData.model_constraints()` planın senaryosunda geçerli değerleri verir (`SqlPlanningData`): `[{ResourceGroupId, UnconstrainedCapacityFactor, TargetUtilizationPct}]`; yalnız kritik ve güncel kaynak grupları, en az bir değeri dolu olanlar. Kritik olmayan (ya da kritik olmaktan çıkmış) grubun saklı değeri dönmez. Senaryonun Baz'dan okuduğu değerler dahildir. Sahte motor kullanmaz.

Motorun uygulayacağı kural (Aşama 10):
- Kaynak kısıtı (`ResourceConstraint`) = Kısıtsız ve çarpan dolu → grubun dönem üst sınırı = dönemin kullanılabilir kapasitesi × çarpan. Çarpan boşsa sınır yok.
- Kaynak kısıtı = Kısıtlı → çarpan kullanılmaz; kesin sınır kullanılabilir kapasitedir (ve açıksa ek mesai).
- Kaynak kısıtı = Kısmi → tanımı ve davranışı açık (A-46); çarpan bugün yalnız Kısıtsız'da uygulanır.
- Hedef doluluk dolu ve "Hedef doluluğun üstü" hedefi (`OVER_TARGET_LOAD`) açık → dönem yükünün (kullanılabilir kapasite × hedef %) üstünde kalan kısmı bu hedefte cezalandırılır. Hedef kapalıysa değer kullanılmaz.
- Kritik olmayan grup için hiçbir koşulda kısıt yazılmaz.

## Eşit öncelikte paylaşım (K-192)

Aynı öncelik grubundaki talepler arasında kaynak ya da malzeme yetmediğinde istek tarihi erken olan önce karşılanır. Ayarı yoktur. Alokasyon (talep sınıfına kaynak grubu ve dönem bazında kapasite payı) Faz 1 dışıdır; tablosu 7.13'te kaldırıldı (K-193).

## Tedarikçi limiti (7.12, K-191)

`PlanningData.supplier_limits(date_from, date_to)` planın senaryosunda gün bazında satır verir (`SqlPlanningData`, `app/supplierlimits`): `[{LocationId, SupplierId, MaterialId, Day, DailyLimit, Closed}]`; yalnız üst limiti ya da kapanışı olan günler. `DailyLimit` o günün günlük ortalamasıdır (limit ÷ limitin döneminin gün sayısı: Gün 1, Hafta 7; Ay, Çeyrek, Yıl için o takvim döneminin gerçek gün sayısı); limiti olmayan kapalı günde boştur. Aynı modülün `period_limit` ve `material_limit` işlevleri dönem ve malzeme düzeyini aynı kuralla hesaplar. Motorun uygulayacağı kural (Aşama 10):
- Tedarikçi + malzeme, plan dönemi: dönemin günleri limitli-açık, kapalı ya da limitsiz-açıktır. Limitsiz ve açık gün varsa dönem sınırsızdır. Yoksa sınır, limitli-açık günlerin günlük ortalamalarının toplamıdır (kapalı günün katkısı sıfır; kapalı günde limit de varsa kapanış kazanır). Bütün günler kapalıysa tedarikçi o dönemde o malzemede kapalıdır (sınır 0).
- Malzeme: tedarikçilerinin (aktif ve güncel malzeme tedarikçisi kayıtları) sınırlarının toplamı; birinin sınırı yoksa malzeme o dönemde sınırsızdır.
- Açık satın alma siparişleri limite sayılır: teslim tarihi o döneme düşen açık siparişler sınırdan düşer; plan yalnız kalanı önerebilir (limit 400, açık sipariş 150 ise en çok 250).
- Kaydı olmayan tedarikçi + malzeme sınırsızdır. Fason kapasitesi bu tabloda değildir.

Bu adımda motor kuralı uygulanmaz; giriş, saklama, geçerlilik hesabı ve arayüz vardır.

## Malzeme blokajı (7.13, K-193)

`PlanningData.material_holds()` planın senaryosunda plan dönemi bazında satır verir (`SqlPlanningData`, `app/materialholds`): `[{LocationId, MaterialId, Supply, PeriodNo, PeriodStart, PeriodEnd, Days, BlockedDays, ClosePct, Closed}]`; `Supply` "Üretim" ya da "Satın alma"; yalnız blokajlı günü olan dönemler (ekrandaki Geçerlilik tablosuyla aynı hesap). `Closed`: blokajlı gün ÷ dönemin takvim günü ≥ dönemi kapatma oranı (döneme dokunan kayıtların en düşüğü). Motorun uygulayacağı kural (Aşama 10):
- Kapalı dönemde o malzeme için o tedarik biçiminde yeni öneri üretilmez (Üretim: planlı üretim; Satın alma: satın alma önerisi). Açık kalan dönemde blokaj uygulanmaz.
- Açık iş emirleri ve açık satın alma siparişleri etkilenmez; gelecek arz sayılır. Eldeki stok kullanılır.
- Ürün ağacı için ek kural yoktur: blokajlı bileşenin stoğu bitince üst ürün kendiliğinden üretilemez. Satış blokajı yoktur.

Bu adımda motor kuralı uygulanmaz; giriş, saklama, dönem hesabı ve arayüz vardır.

## Uyarı eşikleri (7.11, K-190)

`PlanningData.warning_thresholds()` planın senaryosundaki aktif uyarıları verir (`SqlPlanningData`): `[{Code, Category, Unit, Direction, Low, Medium, High, Critical, Severity}]`. Kapalı uyarı dönmez. Motorun ve plan ekranlarının uygulayacağı kural (Aşama 8 ve 10):
- Eşikli uyarı: değer bir kademenin eşiğini geçiyorsa (yön `above`: değer > eşik; `below`: değer < eşik; eşik dahil değil) uyarı çıkar; önemi tuttuğu en yüksek kademedir. Boş kademe atlanır. Nesne başına tek uyarı.
- Eşiksiz uyarı: durum oluşunca `Severity` önemiyle çıkar.
- Uyarı kodları `param.WarningDefinition` kataloğundadır (geçiş 0069 yazar); `PlanWarning.WarningCode` ona bağlıdır.

Bu adımda uyarı üretilmez; yalnız arayüz ve saklama vardır.

## Sahte motor (`app/engine/fake.py`)

- `fixtures/plan_v0.json`'u döndürür: 3 planlı sipariş, 1 mevcut arz önerisi, 2 talep karşılama, 2 doluluk, 3 pegging, 2 uyarı, 4 metrik. Malzeme, kaynak ve sipariş Id'leri sentetik veri (0.8) gelene kadar yer tutucudur; plan fikstürü 8.0'da sentetik veriye göre yeniden hazırlanır.
- Uyarı kodları (`CAP_OVERLOAD`, `ORDER_LATE`) `param.WarningDefinition` kataloğundadır (7.11, K-190; geçiş 0069); eksikse geliştirme ve testte `ensure_fixture_warning_definitions` ekler.
- EngineUsed senaryonun `ModelType` parametresidir (yoksa LP), Solver `Sahte`.
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
| Veri çekme işi ve kanalı (K-130) | uygulandı (3.3) |
| Validasyon işi ve "Veri işleme" kanalı (K-134, K-139) | uygulandı (3.4) |
| Rules adımı: işlenmiş katman ve veri kuralları, tetik "Kural değişikliği", çok tablolu uygulamada grup (ilk işin Id'si, tablolar arası sonda) (K-140…K-142) | uygulandı (4.1) |
| Gerçek motor (29–39), aktif hesaplama belleği | Aşama 10 |

Demo: API açıkken `python scripts/engine_demo.py`; plan hesapları gönderir, servisi çalıştırır, WebSocket'ten ilerlemeyi ve sonuç satır sayılarını yazdırır.

## Fabrika takvimi lokasyon bazlı (K-194)

`PlanningData.period_values('resource-capacity-day', …)` hesabında fabrika takvimi kaydı yalnız kendi lokasyonundaki kaynaklara uygulanır (kaynağın lokasyonu): bir lokasyonun tatili öteki lokasyonun kapasitesini düşürmez. Motorun okuduğu satırların biçimi değişmedi.
