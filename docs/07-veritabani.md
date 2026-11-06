# Veritabanı haritası

Üretilmiş dosya: `db/generate.py`. Kaynak `docs/02-veri-modeli.md` ve `docs/03-entegrasyon.md`.

## Kurallar

- **Beş şema:** `stg` entegrasyon, `core` ana veri ve işlem verisi, `param` parametreler, `planning` plan çıktıları, `adm` veri yönetimi ve sistem.
- **Aynı ad, iki katman:** `stg.Material` ERP'den geldiği haliyle (kodlarla), `core.Material` Smartchain'in tablosu (Id ile). Aktarım `stg`'den `core`'a yapılır (K-58).
- **Versiyonlu tablolar:** `VersionFrom`, `VersionTo`, `ImportBatchId`, `BusinessKey`, `UpdatedAt` alanlarını taşır. Birincil anahtar `Id + VersionFrom`; `Id` bir kaydın bütün versiyonlarında aynıdır. Güncel kayıtta `VersionTo` boştur; tekillik (UK) yalnız güncel kayıtlarda aranır.
- **İlişkiler:** Versiyonsuz tabloya giden ilişkiler veritabanında yabancı anahtarla (FK) korunur. Versiyonlu tabloya giden ilişkilerde FK yoktur, yalnız indeks vardır; bütünlüğü aktarım adımı (kod→Id) sağlar.
- **Entegrasyon tablolarının standart alanları:** `StagingRowId`, `ImportBatchId`, `RowStatus` (Yeni, Hatalı, Aktarıldı), `ErrorText`, `SourceRowNo`. Bu tablolarda zorunluluk veritabanında değil, doğrulama adımında kontrol edilir.
- **Açıklamalar:** Her tablo ve alanın Türkçe açıklaması veritabanına da yazılır; SQL Server Management Studio'da tablo ve kolon özelliklerinde görünür.

## `stg` · Entegrasyon tabloları: ERP'nin dili, ilişkiler kodla (K-58) (25 tablo)

| Tablo | Açıklama | Sınıf | Versiyonlu | Alan |
|---|---|---|---|---|
| `stg.Material` | Malzeme ve planlama ana verisi. | Entegrasyon |  | 43 |
| `stg.Location` | Lokasyon (tesis, depo). Faz 1'de her lokasyon kendi içinde planlanır. | Entegrasyon |  | 23 |
| `stg.UomConversion` | Malzeme bazında birim dönüşümü. | Entegrasyon |  | 6 |
| `stg.ProductionVersion` | Üretim versiyonu: bir malzemenin ürün ağacı ve rota başlığı; rotaya RouteCode, ürün ağacına BOMCode ile bağlanır. Versiyon seçimi motorun kararıdır; aynı malzeme aynı dönemde birden fazla versiyonla üretilebilir. | Entegrasyon |  | 17 |
| `stg.BOM` | Ürün ağacı satırı. | Entegrasyon |  | 18 |
| `stg.Routing` | Rota: her satır bir operasyon–kaynak ilişkisi; sıra önce OperationNo, sonra SequenceNo. Aynı operasyonun kaynakları ayrı satırda, ResourceRole ile. | Entegrasyon |  | 24 |
| `stg.MaterialReference` | Benzetilen ürün: kendi ağacı ya da rotası olmayan ürün, başka bir ürünün verisiyle planlanır. | Entegrasyon |  | 7 |
| `stg.Resource` | Kaynak: makine, işçi, fason, diğer. Kapasite kaynağın kendi biriminde günlük kapasite olarak tutulur. | Entegrasyon |  | 27 |
| `stg.ResourceGroup` | Kaynak ve yetkinlik grubu. Kapasite havuzu değil, uygun kaynaklar listesidir; kapasite yalnız kaynakta tutulur. | Entegrasyon |  | 17 |
| `stg.ResourceGroupAssignment` | Kaynağın gruba ataması; bir kaynak birden fazla gruba atanabilir, yetkinlik matrisi bu tablodur. Geçerlilik tarihleri yalnız girdi. | Entegrasyon |  | 5 |
| `stg.EmployeeAbsence` | Kişi bazında izin ve rapor. | Entegrasyon |  | 6 |
| `stg.Supplier` | Tedarikçi ve fasoncu. | Entegrasyon |  | 16 |
| `stg.MaterialSupplier` | Malzeme–tedarikçi ilişkisi; satın alma parametreleri. Satın alma her zaman sürekli; yuvarlama son hesapta. | Entegrasyon |  | 19 |
| `stg.Customer` | Müşteri. | Entegrasyon |  | 20 |
| `stg.ProjectGroup` | Proje grubu (grup içi paylaşım için). | Entegrasyon |  | 5 |
| `stg.Project` | Proje. | Entegrasyon |  | 16 |
| `stg.SalesOrderLine` | Müşteri sipariş satırı; teklifler IsQuote ile okunur. Vade: teyit tarihi, yoksa istek tarihi. | Entegrasyon |  | 26 |
| `stg.Forecast` | Talep tahmini (netleme ön hesapta). | Entegrasyon |  | 15 |
| `stg.BorrowPayback` | Projeler arası ödünç ve geri ödeme kaydı: devreye almada açık olan ve ERP'de doğrudan yapılan ödünçlerin motora bildirilmesi; onaylanan öneriler de buraya yazılır. | Entegrasyon |  | 8 |
| `stg.Stock` | Stok; lot ve durum bazında. Sahip: proje, müşteri, sipariş ya da ortak. | Entegrasyon |  | 25 |
| `stg.WorkOrder` | Açık iş emri (üretim, fason, yeniden işleme). | Entegrasyon |  | 34 |
| `stg.WorkOrderComponent` | İş emrinin bileşenleri ve çekilen miktar. | Entegrasyon |  | 17 |
| `stg.WorkOrderOperation` | İş emrinin operasyonları ve kalan iş. | Entegrasyon |  | 25 |
| `stg.PurchaseOrderLine` | Açık satın alma ve fason siparişi satırı (ve talep). | Entegrasyon |  | 29 |
| `stg.ProductionConfirmation` | Üretim gerçekleşmeleri: iş emri bazında stoğa girişler. | Entegrasyon |  | 12 |

## `core` · Ana veri ve işlem verisi (33 tablo)

| Tablo | Açıklama | Sınıf | Versiyonlu | Alan |
|---|---|---|---|---|
| `core.Location` | Lokasyon (tesis, depo). Faz 1'de her lokasyon kendi içinde planlanır. | Ana veri |  | 25 |
| `core.UnitOfMeasure` | Ölçü birimi. | Ana veri |  | 3 |
| `core.UomConversion` | Malzeme bazında birim dönüşümü. | Ana veri | evet | 7 |
| `core.Calendar` | Çalışma takvimi başlığı (kaynaklara bağlanır). Smartchain'de ekrandan girilir; entegrasyondan gelmez (K-65). | Ana veri | evet | 3 |
| `core.CalendarDay` | Takvimin gün bazında çalışma durumu. Smartchain'de ekrandan girilir; entegrasyondan gelmez (K-65). | Ana veri | evet | 4 |
| `core.Resource` | Kaynak: makine, işçi, fason, diğer. Kapasite kaynağın kendi biriminde günlük kapasite olarak tutulur. | Ana veri | evet | 35 |
| `core.ResourceGroup` | Kaynak ve yetkinlik grubu. Kapasite havuzu değil, uygun kaynaklar listesidir; kapasite yalnız kaynakta tutulur. | Ana veri | evet | 18 |
| `core.ResourceCapacityProfile` | Günlük kapasitenin dönemsel değişikliği (ör. ikinci vardiya açıldı). Birim kaynağın CapacityUnit'i; ekranda gösterilir, ayrı saklanmaz. Smartchain'de ekrandan girilir; entegrasyondan gelmez (K-65). | Ana veri | evet | 5 |
| `core.ResourceDowntime` | Bakım ve arıza takvimi; kapasiteden düşülür. Çalışmada geçici değiştirilebilir. Smartchain'de ekrandan girilir; entegrasyondan gelmez (K-65). | Ana veri | evet | 8 |
| `core.ResourceGroupAssignment` | Kaynağın gruba ataması; bir kaynak birden fazla gruba atanabilir, yetkinlik matrisi bu tablodur. Geçerlilik tarihleri yalnız girdi. | Ana veri | evet | 6 |
| `core.Shift` | Vardiya tanımı. Smartchain'de ekrandan girilir; entegrasyondan gelmez (K-65). | Ana veri | evet | 6 |
| `core.ShiftPlan` | Dönem bazında grup–vardiya–kişi sayısı. Çalışmada geçici değiştirilebilir. Smartchain'de ekrandan girilir; entegrasyondan gelmez (K-65). | Ana veri | evet | 6 |
| `core.EmployeeAbsence` | Kişi bazında izin ve rapor. | İşlem verisi | evet | 7 |
| `core.Material` | Malzeme ve planlama ana verisi. | Ana veri | evet | 44 |
| `core.Supplier` | Tedarikçi ve fasoncu. | Ana veri | evet | 17 |
| `core.MaterialSupplier` | Malzeme–tedarikçi ilişkisi; satın alma parametreleri. Satın alma her zaman sürekli; yuvarlama son hesapta. | Ana veri | evet | 20 |
| `core.ProductionVersion` | Üretim versiyonu: bir malzemenin ürün ağacı ve rota başlığı; rotaya RouteCode, ürün ağacına BOMCode ile bağlanır. Versiyon seçimi motorun kararıdır; aynı malzeme aynı dönemde birden fazla versiyonla üretilebilir. | Ana veri | evet | 18 |
| `core.BOM` | Ürün ağacı satırı. | Ana veri | evet | 19 |
| `core.Routing` | Rota: her satır bir operasyon–kaynak ilişkisi; sıra önce OperationNo, sonra SequenceNo. Aynı operasyonun kaynakları ayrı satırda, ResourceRole ile. | Ana veri | evet | 25 |
| `core.MaterialReference` | Benzetilen ürün: kendi ağacı ya da rotası olmayan ürün, başka bir ürünün verisiyle planlanır. | Ana veri | evet | 8 |
| `core.ProjectGroup` | Proje grubu (grup içi paylaşım için). | Ana veri | evet | 6 |
| `core.Project` | Proje. | Ana veri | evet | 17 |
| `core.Customer` | Müşteri. | Ana veri | evet | 21 |
| `core.SalesOrderLine` | Müşteri sipariş satırı; teklifler IsQuote ile okunur, plana dahil olmaları senaryo parametresi. Vade: teyit tarihi, yoksa istek tarihi. | İşlem verisi | evet | 27 |
| `core.Forecast` | Talep tahmini (netleme ön hesapta). | İşlem verisi | evet | 16 |
| `core.BorrowPayback` | Projeler arası ödünç ve geri ödeme kaydı: devreye almada açık olan ve ERP'de doğrudan yapılan ödünçlerin motora bildirilmesi; onaylanan öneriler de buraya yazılır. | İşlem verisi | evet | 9 |
| `core.Stock` | Stok; lot ve durum bazında. Sahip: proje, müşteri, sipariş ya da ortak. | İşlem verisi | evet | 24 |
| `core.WorkOrder` | Açık iş emri (üretim, fason, yeniden işleme). | İşlem verisi | evet | 33 |
| `core.WorkOrderComponent` | İş emrinin bileşenleri ve çekilen miktar. | İşlem verisi | evet | 19 |
| `core.WorkOrderOperation` | İş emrinin operasyonları ve kalan iş. | İşlem verisi | evet | 27 |
| `core.PurchaseOrderLine` | Açık satın alma ve fason siparişi satırı (ve talep). | İşlem verisi | evet | 28 |
| `core.TransferOrder` | Açık lokasyonlar arası transfer; Faz 1'de sabit hareket (gelen arz, giden talep). | İşlem verisi | evet | 13 |
| `core.ProductionConfirmation` | Üretim gerçekleşmeleri: iş emri bazında stoğa girişler. | İşlem verisi | evet | 13 |

## `param` · Planlama parametreleri ve senaryo tanımları (11 tablo)

| Tablo | Açıklama | Sınıf | Versiyonlu | Alan |
|---|---|---|---|---|
| `param.ResourceEfficiency` | Kaynak ve dönem bazında verim (kapasite katsayısı); senaryoya özel. | Parametre |  | 6 |
| `param.ResourcePeriodLimit` | Dönem bazlı üst limit; kısıtsız kaynaklarda ve fasonda. Birim kaynağın kapasite birimi. | Parametre |  | 6 |
| `param.OvertimeLimit` | Fazla mesai üst limiti (vardiya ve dönem bazında). | Parametre |  | 4 |
| `param.SupplierLimit` | Tedarikçi dönem üst limiti (problem 39): malzeme bazında maksimum miktar. Malzeme boşsa tedarikçi o dönemde kapalıdır (limit 0). Smartchain'de ekrandan girilir (K-65, K-66). | Parametre |  | 7 |
| `param.ParameterSet` | Parametre seti; gece senaryoları farklı setlerle çalışır. | Parametre |  | 4 |
| `param.PlanningSetting` | Genel planlama parametreleri (anahtar–değer); ör. model tipi, fazla mesai dahil mi, fix dönem, toleranslar, MRP öncelik ve kısıt ayarları. | Parametre |  | 3 |
| `param.TimeBucketDefinition` | Zaman yapısı: planlama ufku ve dinamik bucket dizisi. | Parametre |  | 4 |
| `param.PriorityRule` | Sıralama kuralı: kriterlerin sırası (bucket > müşteri > proje > satır > tarih). | Parametre |  | 4 |
| `param.AllocationRule` | Kapasite alokasyonu: talep sınıfına kaynak (grubu) ve dönem bazında pay. | Parametre |  | 9 |
| `param.WarningDefinition` | Uyarı tanımı, eşik ve önem seviyesi. | Parametre |  | 5 |
| `param.ScenarioDefinition` | Gece senaryosu tanımı: parametre seti + eksen ayarları. | Parametre |  | 9 |

## `planning` · Senaryo, çalışma ve plan çıktıları (12 tablo)

| Tablo | Açıklama | Sınıf | Versiyonlu | Alan |
|---|---|---|---|---|
| `planning.Scenario` | Gece üretilen senaryo; bir sonraki gece akışında silinir. | Plan |  | 6 |
| `planning.Workspace` | Kullanıcının bir senaryo üzerindeki çalışması; yayınlanmazsa gece silinir. | Plan |  | 6 |
| `planning.WorkspaceOverride` | Çalışmadaki geçici değişiklikler: parametreler ve çalışmada değiştirilebilir ana veri alanları. | Plan |  | 7 |
| `planning.PlanRun` | Bir plan hesabı (senaryo ya da çalışma); bütün plan çıktıları buna bağlı. | Plan |  | 10 |
| `planning.PlanVersion` | Onaylı plan versiyonu; hep saklanır. Aynı anda tek geçerli. | Plan |  | 7 |
| `planning.PlannedOrder` | Planlı sipariş: üretim, satın alma ya da fason önerisi. Satın alma sürekli hesaplanır, yuvarlanmış miktar ayrıca. | Plan |  | 12 |
| `planning.SupplyRecommendation` | Mevcut arz için öneri: öne çek, ertele, iptal, azalt, hızlandır. | Plan |  | 9 |
| `planning.DemandFulfillment` | Talebin planlanan karşılanması ve gecikmesi. | Plan |  | 9 |
| `planning.CapacityLoad` | Kaynak ve dönem bazında kapasite ve kapasite yükü. | Plan |  | 10 |
| `planning.Pegging` | Arz–talep bağı (full pegging). | Plan |  | 10 |
| `planning.PlanWarning` | Plan hesabının ürettiği uyarılar. | Plan |  | 8 |
| `planning.PlanMetric` | Senaryo karşılaştırma metrikleri; senaryo silinse de özet kısa süre kalır. | Plan |  | 3 |

## `adm` · Veri yönetimi ve sistem (SQL Server'da `sys` ayrılmış olduğu için `adm`) (28 tablo)

| Tablo | Açıklama | Sınıf | Versiyonlu | Alan |
|---|---|---|---|---|
| `adm.FieldDefinition` | Veri sözlüğü: her alanın sınıfı ve değer davranışı. Yapısını System owner yönetir. | Veri yönetimi |  | 11 |
| `adm.DataRule` | Veri kuralı: 'X = … ise Alan = …'. | Veri yönetimi |  | 11 |
| `adm.DataRuleCondition` | Kural koşulları: aynı GroupNo'daki koşullar VE, gruplar arası VEYA (K-136); koşul editörü validasyon kurallarıyla ortaktır. | Veri yönetimi |  | 7 |
| `adm.ManualValue` | Kayıt bazında elle girilen değer. | Veri yönetimi |  | 8 |
| `adm.FieldValueSource` | Geçerli değerin kaynağı ve ERP değeri (ezilse bile saklanır). | Veri yönetimi |  | 6 |
| `adm.ImportBatch` | Ham veri partisi: her yükleme parti numarası, zaman ve kaynakla. Ham veri bir hafta saklanır. LoadType Değişen: arayüzde "Ekle / güncelle" (K-129). | Veri yönetimi |  | 15 |
| `adm.ImportFinding` | Partinin ön kontrol bulguları (fonksiyon 03). Validasyon (fonksiyon 04) partiye değil staging'in güncel hâline aittir, bulguları `ValidationFinding`'dedir (K-134). | Veri yönetimi |  | 9 |
| `adm.IntegrationEntity` | Tablo başına çekim ayarı (K-130). Satır yoksa ya da yöntem boşsa tablo Excel sayılır, çekim açıktır. | Veri yönetimi |  | 19 |
| `adm.IntegrationViewVersion` | View'ın sürüm geçmişi (K-130): tanım değişince yeni sürüm. Smartchain view oluşturmaz, yalnız okur ve saklar. | Veri yönetimi |  | 8 |
| `adm.ValidationRule` | Validasyon kuralı (K-136, ekran 27). Yapısal kontroller ve hazır kurallar koddaki katalogdan kurulur (geçişte eksik olan eklenir; sınıfı ve aktifliği kullanıcıda kalır); kullanıcı kuralı ekrandan eklenir. | Veri yönetimi |  | 13 |
| `adm.ValidationRuleCondition` | Kullanıcı kuralının ve düzenlenmiş hazır kuralın koşulları (K-136, K-139): aynı GroupNo'daki koşullar VE, gruplar arası VEYA. Operatörler `DataRuleCondition` ile aynıdır. | Veri yönetimi |  | 7 |
| `adm.ValidationRun` | Tablo başına validasyon çalışması (K-134): çipin durumu son çalışmadan, sonucu bulgulardan okunur. | Veri yönetimi |  | 16 |
| `adm.ValidationFinding` | Staging'in güncel hâlinin validasyon bulguları (K-134). Bir kural yeniden çalışınca o kuralın o tablodaki bulguları yenilenir; güncel hâlden çıkan satırın bulguları silinir. Ön kontrol bulguları `ImportFinding`'dedir. | Veri yönetimi |  | 10 |
| `adm.DataVersion` | Yükleme ile oluşan dondurulmuş veri versiyonu; tam ya da kısmi. | Veri yönetimi |  | 7 |
| `adm.DataVersionEntity` | Kısmi yüklemede hangi varlıkların yüklendiği. | Veri yönetimi |  | 3 |
| `adm.AppUser` | Uygulama kullanıcısı (Faz 1'de yerel). | Sistem |  | 14 |
| `adm.UserSession` | Sunucu tarafı oturum (K-97). Tarayıcıdaki çerez rastgele bir anahtar taşır; tabloda yalnız anahtarın SHA-256 özeti durur. | Sistem |  | 9 |
| `adm.PasswordHistory` | Kullanıcının önceki şifre özetleri (K-98): yeni şifre son `PasswordHistoryCount` şifreden farklı olmalı. | Sistem |  | 4 |
| `adm.LoginThrottle` | Bilinmeyen, şifresiz ya da pasif hesap adına yapılan hatalı girişlerin sayacı (K-98). Gerçek hesaptaki sayaçla aynı davranır; giriş cevabından hesabın var olup olmadığı anlaşılmaz. | Sistem |  | 4 |
| `adm.Job` | İş kuyruğu (SQL Server tablosu): gece senaryoları, çalışma hesapları, yüklemeler. | Sistem |  | 20 |
| `adm.SolverLog` | Çözüm logu; ilk günden tutulur. | Sistem |  | 6 |
| `adm.SystemEvent` | Sistem hataları ve sistem aksiyonu (K-106). Saklama `SystemEventRetentionDays`; motor servisi eskileri siler. | Sistem |  | 9 |
| `adm.ServiceStatus` | Motor servisinin kalp atışı (K-106). Durum saklanmaz, okurken hesaplanır. | Sistem |  | 5 |
| `adm.AuditLog` | Kim, ne zaman, neyi değiştirdi; giriş kayıtları; kayıtlar silinemez (K-109). | Sistem |  | 8 |
| `adm.SystemSetting` | System owner'ın ayarları: çözücü, süre bütçeleri, işçi sayısı, eş zamanlı çalışma sınırı, saklama süreleri. | Sistem |  | 2 |
| `adm.TableView` | Kayıtlı tablo görünümü (K-89): kolon seti ve sırası, genişlikler, sabitleme, sıralama, filtreler, gruplama. | Sistem |  | 8 |
| `adm.TableViewDefault` | Kullanıcının bir liste için varsayılan görünümü (K-89). Satır yoksa liste tanımındaki "Standart" görünüm açılır. | Sistem |  | 3 |
| `adm.License` | Çevrimdışı imzalı lisans. | Sistem |  | 4 |

