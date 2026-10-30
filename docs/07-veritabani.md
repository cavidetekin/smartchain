# Veritabanı haritası

Üretilmiş dosya: `db/generate.py`. Kaynak `docs/02-veri-modeli.md` ve `docs/03-entegrasyon.md`.

## Kurallar

- **Beş şema:** `stg` entegrasyon, `core` ana veri ve işlem verisi, `param` parametreler, `planning` plan çıktıları, `adm` veri yönetimi ve sistem.
- **Aynı ad, iki katman:** `stg.Material` ERP'den geldiği haliyle (kodlarla), `core.Material` Smartchain'in tablosu (Id ile). Aktarım `stg`'den `core`'a yapılır (K-58).
- **Versiyonlu tablolar:** `VersionFrom`, `VersionTo`, `ImportBatchId`, `BusinessKey`, `UpdatedAt` alanlarını taşır. Birincil anahtar `Id + VersionFrom`; `Id` bir kaydın bütün versiyonlarında aynıdır. Güncel kayıtta `VersionTo` boştur; tekillik (UK) yalnız güncel kayıtlarda aranır.
- **İlişkiler:** Versiyonsuz tabloya giden ilişkiler veritabanında yabancı anahtarla (FK) korunur. Versiyonlu tabloya giden ilişkilerde FK yoktur, yalnız indeks vardır; bütünlüğü aktarım adımı (kod→Id) sağlar.
- **Entegrasyon tablolarının standart alanları:** `StagingRowId`, `ImportBatchId`, `RowStatus` (Yeni, Hatalı, Aktarıldı), `ErrorText`. Bu tablolarda zorunluluk veritabanında değil, doğrulama adımında kontrol edilir.
- **Açıklamalar:** Her tablo ve alanın Türkçe açıklaması veritabanına da yazılır; SQL Server Management Studio'da tablo ve kolon özelliklerinde görünür.

## `stg` · Entegrasyon tabloları: ERP'nin dili, ilişkiler kodla (K-58) (26 tablo)

| Tablo | Açıklama | Sınıf | Versiyonlu | Alan |
|---|---|---|---|---|
| `stg.Material` | Malzeme ve planlama ana verisi. | Entegrasyon |  | 33 |
| `stg.Location` | Lokasyon (tesis, depo). Faz 1'de her lokasyon kendi içinde planlanır. | Entegrasyon |  | 19 |
| `stg.UnitOfMeasure` | Ölçü birimi. | Entegrasyon |  | 2 |
| `stg.UomConversion` | Malzeme bazında birim dönüşümü. | Entegrasyon |  | 4 |
| `stg.ProductionVersion` | Üretim versiyonu: bir malzemenin ürün ağacı ve rota başlığı; rotaya RouteCode ile bağlanır. Faz 1'de varsayılan versiyon kullanılır. | Entegrasyon |  | 12 |
| `stg.BOM` | Ürün ağacı satırı. | Entegrasyon |  | 12 |
| `stg.Routing` | Rota: her satır bir operasyon–kaynak ilişkisi; sıra önce OpNo, sonra SeqNo. Aynı operasyonun kaynakları ayrı satırda, ResourceRole ile. | Entegrasyon |  | 20 |
| `stg.Resource` | Kaynak: makine, işçi, fason, diğer. Kapasite kaynağın kendi biriminde günlük kapasite olarak tutulur. | Entegrasyon |  | 25 |
| `stg.ResourceGroup` | Kaynak grubu (makine grubu, işçi kaynak grubu). | Entegrasyon |  | 13 |
| `stg.CompetenceGroup` | İşçi yetkinlik grubu. | Entegrasyon |  | 3 |
| `stg.Worker` | İşçi. | Entegrasyon |  | 15 |
| `stg.WorkerCompetence` | İşçi–yetkinlik grubu eşleşmesi; çoktan çoğa. | Entegrasyon |  | 2 |
| `stg.WorkerAbsence` | Kişi bazında izin ve rapor. | Entegrasyon |  | 4 |
| `stg.Supplier` | Tedarikçi ve fasoncu. | Entegrasyon |  | 13 |
| `stg.MaterialSupplier` | Malzeme–tedarikçi ilişkisi; satın alma parametreleri. Satın alma her zaman sürekli; yuvarlama son hesapta. | Entegrasyon |  | 16 |
| `stg.Customer` | Müşteri. | Entegrasyon |  | 14 |
| `stg.ProjectGroup` | Proje grubu (grup içi paylaşım için). | Entegrasyon |  | 3 |
| `stg.Project` | Proje. | Entegrasyon |  | 16 |
| `stg.SalesOrderLine` | Müşteri sipariş satırı; teklifler Type = Teklif ile gelir. Vade: teyit tarihi, yoksa istek tarihi. | Entegrasyon |  | 19 |
| `stg.Forecast` | Talep tahmini (netleme ön hesapta). | Entegrasyon |  | 11 |
| `stg.Stock` | Stok; lot ve durum bazında. Sahip: proje ya da ortak. | Entegrasyon |  | 14 |
| `stg.WorkOrder` | Açık iş emri (üretim, fason, yeniden işleme). | Entegrasyon |  | 19 |
| `stg.WorkOrderComponent` | İş emrinin bileşenleri ve çekilen miktar. | Entegrasyon |  | 9 |
| `stg.WorkOrderOperation` | İş emrinin operasyonları ve kalan iş. | Entegrasyon |  | 12 |
| `stg.PurchaseOrderLine` | Açık satın alma ve fason siparişi satırı (ve talep). | Entegrasyon |  | 17 |
| `stg.ProductionConfirmation` | Üretim gerçekleşmeleri; ilk günden tutulur (verim önerisi ve ileriki fazlar). | Entegrasyon |  | 13 |

## `core` · Ana veri ve işlem verisi (33 tablo)

| Tablo | Açıklama | Sınıf | Versiyonlu | Alan |
|---|---|---|---|---|
| `core.Location` | Lokasyon (tesis, depo). Faz 1'de her lokasyon kendi içinde planlanır. | Ana veri |  | 21 |
| `core.UnitOfMeasure` | Ölçü birimi. | Ana veri |  | 3 |
| `core.UomConversion` | Malzeme bazında birim dönüşümü. | Ana veri | evet | 5 |
| `core.Calendar` | Çalışma takvimi başlığı (kaynaklara bağlanır). Smartchain'de ekrandan girilir; entegrasyondan gelmez (K-65). | Ana veri | evet | 3 |
| `core.CalendarDay` | Takvimin gün bazında çalışma durumu. Smartchain'de ekrandan girilir; entegrasyondan gelmez (K-65). | Ana veri | evet | 4 |
| `core.Resource` | Kaynak: makine, işçi, fason, diğer. Kapasite kaynağın kendi biriminde günlük kapasite olarak tutulur. | Ana veri | evet | 27 |
| `core.ResourceGroup` | Kaynak grubu (makine grubu, işçi kaynak grubu). | Ana veri | evet | 14 |
| `core.ResourceCapacityProfile` | Günlük kapasitenin dönemsel değişikliği (ör. ikinci vardiya açıldı). Birim kaynağın CapacityUnit'i; ekranda gösterilir, ayrı saklanmaz. Smartchain'de ekrandan girilir; entegrasyondan gelmez (K-65). | Ana veri | evet | 5 |
| `core.ResourceDowntime` | Bakım ve arıza takvimi; kapasiteden düşülür. Çalışmada geçici değiştirilebilir. Smartchain'de ekrandan girilir; entegrasyondan gelmez (K-65). | Ana veri | evet | 8 |
| `core.CompetenceGroup` | İşçi yetkinlik grubu. | Ana veri | evet | 4 |
| `core.Worker` | İşçi. | Ana veri | evet | 16 |
| `core.WorkerCompetence` | İşçi–yetkinlik grubu eşleşmesi; çoktan çoğa. | Ana veri | evet | 2 |
| `core.Shift` | Vardiya tanımı. Smartchain'de ekrandan girilir; entegrasyondan gelmez (K-65). | Ana veri | evet | 6 |
| `core.ShiftPlan` | Dönem bazında grup–vardiya–kişi sayısı. Çalışmada geçici değiştirilebilir. Smartchain'de ekrandan girilir; entegrasyondan gelmez (K-65). | Ana veri | evet | 7 |
| `core.WorkerAbsence` | Kişi bazında izin ve rapor. | İşlem verisi | evet | 5 |
| `core.Material` | Malzeme ve planlama ana verisi. | Ana veri | evet | 34 |
| `core.Supplier` | Tedarikçi ve fasoncu. | Ana veri | evet | 14 |
| `core.MaterialSupplier` | Malzeme–tedarikçi ilişkisi; satın alma parametreleri. Satın alma her zaman sürekli; yuvarlama son hesapta. | Ana veri | evet | 17 |
| `core.ProductionVersion` | Üretim versiyonu: bir malzemenin ürün ağacı ve rota başlığı; rotaya RouteCode ile bağlanır. Faz 1'de varsayılan versiyon kullanılır. | Ana veri | evet | 13 |
| `core.BOM` | Ürün ağacı satırı. | Ana veri | evet | 12 |
| `core.Routing` | Rota: her satır bir operasyon–kaynak ilişkisi; sıra önce OpNo, sonra SeqNo. Aynı operasyonun kaynakları ayrı satırda, ResourceRole ile. | Ana veri | evet | 21 |
| `core.ProjectGroup` | Proje grubu (grup içi paylaşım için). | Ana veri | evet | 4 |
| `core.Project` | Proje. | Ana veri | evet | 17 |
| `core.Customer` | Müşteri. | Ana veri | evet | 15 |
| `core.SalesOrderLine` | Müşteri sipariş satırı; teklifler Type = Teklif ile gelir, plana dahil olmaları senaryo parametresi. Vade: teyit tarihi, yoksa istek tarihi. | İşlem verisi | evet | 20 |
| `core.Forecast` | Talep tahmini (netleme ön hesapta). | İşlem verisi | evet | 12 |
| `core.Stock` | Stok; lot ve durum bazında. Sahip: proje ya da ortak. | İşlem verisi | evet | 15 |
| `core.WorkOrder` | Açık iş emri (üretim, fason, yeniden işleme). | İşlem verisi | evet | 19 |
| `core.WorkOrderComponent` | İş emrinin bileşenleri ve çekilen miktar. | İşlem verisi | evet | 11 |
| `core.WorkOrderOperation` | İş emrinin operasyonları ve kalan iş. | İşlem verisi | evet | 14 |
| `core.PurchaseOrderLine` | Açık satın alma ve fason siparişi satırı (ve talep). | İşlem verisi | evet | 18 |
| `core.TransferOrder` | Açık lokasyonlar arası transfer; Faz 1'de sabit hareket (gelen arz, giden talep). | İşlem verisi | evet | 13 |
| `core.ProductionConfirmation` | Üretim gerçekleşmeleri; ilk günden tutulur (verim önerisi ve ileriki fazlar). | İşlem verisi | evet | 14 |

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

## `adm` · Veri yönetimi ve sistem (SQL Server'da `sys` ayrılmış olduğu için `adm`) (19 tablo)

| Tablo | Açıklama | Sınıf | Versiyonlu | Alan |
|---|---|---|---|---|
| `adm.FieldDefinition` | Veri sözlüğü: her alanın sınıfı ve değer davranışı. Yapısını sistem sahibi yönetir. | Veri yönetimi |  | 9 |
| `adm.DataRule` | Veri kuralı: 'X = … ise Alan = …'. | Veri yönetimi |  | 11 |
| `adm.DataRuleCondition` | Kural koşulları (VE / VEYA). | Veri yönetimi |  | 6 |
| `adm.ManualValue` | Kayıt bazında elle girilen değer. | Veri yönetimi |  | 8 |
| `adm.FieldValueSource` | Geçerli değerin kaynağı ve ERP değeri (ezilse bile saklanır). | Veri yönetimi |  | 6 |
| `adm.ImportBatch` | Ham veri partisi: her yükleme parti numarası, zaman ve kaynakla. Ham veri bir hafta saklanır. | Veri yönetimi |  | 8 |
| `adm.DataVersion` | Yükleme ile oluşan dondurulmuş veri versiyonu; tam ya da kısmi. | Veri yönetimi |  | 7 |
| `adm.DataVersionEntity` | Kısmi yüklemede hangi varlıkların yüklendiği. | Veri yönetimi |  | 3 |
| `adm.AppUser` | Uygulama kullanıcısı (Faz 1'de yerel). | Sistem |  | 13 |
| `adm.UserSession` | Sunucu tarafı oturum (K-97). Tarayıcıdaki çerez rastgele bir anahtar taşır; tabloda yalnız anahtarın SHA-256 özeti durur. | Sistem |  | 9 |
| `adm.PasswordHistory` | Kullanıcının önceki şifre özetleri (K-98): yeni şifre son `PasswordHistoryCount` şifreden farklı olmalı. | Sistem |  | 4 |
| `adm.LoginThrottle` | Bilinmeyen, şifresiz ya da pasif hesap adına yapılan hatalı girişlerin sayacı (K-98). Gerçek hesaptaki sayaçla aynı davranır; giriş cevabından hesabın var olup olmadığı anlaşılmaz. | Sistem |  | 4 |
| `adm.Job` | İş kuyruğu (SQL Server tablosu): gece senaryoları, çalışma hesapları, yüklemeler. | Sistem |  | 15 |
| `adm.SolverLog` | Çözüm logu; ilk günden tutulur. | Sistem |  | 6 |
| `adm.AuditLog` | Kim, ne zaman, neyi değiştirdi; giriş kayıtları; sistem sahibi işlemleri silinemez. | Sistem |  | 8 |
| `adm.SystemSetting` | Sistem sahibinin ayarları: çözücü, süre bütçeleri, işçi sayısı, eş zamanlı çalışma sınırı, saklama süreleri. | Sistem |  | 2 |
| `adm.TableView` | Kayıtlı tablo görünümü (K-89): kolon seti ve sırası, genişlikler, sabitleme, sıralama, filtreler, gruplama. | Sistem |  | 8 |
| `adm.TableViewDefault` | Kullanıcının bir liste için varsayılan görünümü (K-89). Satır yoksa liste tanımındaki "Standart" görünüm açılır. | Sistem |  | 3 |
| `adm.License` | Çevrimdışı imzalı lisans. | Sistem |  | 4 |

