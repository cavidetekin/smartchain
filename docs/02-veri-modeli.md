# Veri modeli (MDD adım 21)

Kaynak: Master Design Document (MDD) 26.10.2026. Bu dosya desteden üretilmiştir; değişiklik önce burada yapılır, deste dilim sonlarında buradan güncellenir (K-54).

### 21. Veri modeli
<sub>tamamlandı</sub>

- **Ne yapılacak:** Varlıklar ve ilişkileri, her tablonun alanları; her alanın tipi, ana kaynağı, sınıfı, çalışmada değiştirilebilir olup olmadığı, zorunluluğu ve varsayılanı. ERP'den bağımsız veri sözleşmesinin temeli. Çıktı: veri modeli, alan sözlüğü ve UML (Excel ve diyagramlar)
  - Bu adımın slaytları
  - 4 İlkeler ve genel görünüm
  - 6 Tablo listesi
  - 5 Ortak
  - 14 Kaynak
  - 10 Malzeme
  - 3 Talep
  - 7 Arz ve stok
  - 6 Parametre
  - 9 Veri yönetimi
  - 13 Plan
  - 6 Sistem
- **Kararlar**
  - K-38  Tablo ve alan adları İngilizce, açıklamalar Türkçe; ERP'den bağımsız tek veri sözleşmesi.
  - K-39  Veri sınıfları: ana veri, işlem verisi, parametre; her alanın sınıfı ve değer önceliği veri sözlüğünde.
  - K-40  Veri versiyonları kayıt bazında (VersionFrom, VersionTo); kısmi yüklemede veri kopyalanmaz.
  - K-41  Çalışmadaki geçici değişiklikler tek tabloda; plan çıktıları plan hesabına bağlı.
  - K-58  İki katman: entegrasyon tabloları (stg.*) kodla, ana tablolar Id ile; ERP verisi ana tablolara aktarımla geçer.
  - K-59  Ek alanlar: ana veride 10 (7 metin + 3 sayı), yapı ve işlem verisinde 5 (3 metin + 2 sayı); etiketi FieldDefinition'da.
  - K-60  Teklif ayrı tablo değil: SalesOrderLine.Type = Kesin | Teklif; kazanma olasılığı tutulmaz.
  - K-61  Rota satırı operasyon–kaynak: RouteCode + OpNo + SeqNo + ResourceCode; sıra önce OpNo, sonra SeqNo.
- **Açık konular**
  - A-17  Alanların tablo tablo birlikte gözden geçirilmesi.
  - A-18  Faz 1 dışı konuların (set-up, kalıp, fırın, raf ömrü) tabloları sonraki fazda.

### Veri modelinin ilkeleri
<sub>21. Veri modeli · İlkeler</sub>

- **ERP'den bağımsız:** Tek veri sözleşmesi; API, Excel ve SQL arayüz tabloları aynı entegrasyon tablolarına (stg.*) iner.
- **Adlandırma:** Tablo ve alan adları İngilizce (Resource.ResourceType), açıklamalar Türkçe. Veritabanı MS SQL Server.
- **Lokasyon:** Lokasyon bütün ana ve işlem verisi tablolarında baştan var; Faz 1'de her lokasyon kendi içinde planlanır.
- **Veri sınıfları:** Ana veri genel ve bütün senaryolarda aynı; parametre Smartchain'de, parametre setine bağlı ve senaryoya özel olabilir; işlem verisi ERP'den gelen hareketler.
- **Değer kaynağı:** Her alanın değeri ERP, kural, elle ya da varsayılandan gelir; öncelik veri sözlüğünde (FieldDefinition) alan bazında tanımlıdır. ERP değeri ezilse bile saklanır.
- **Veri versiyonları:** Versiyonlu tablolarda her kayıt hangi veri versiyonundan hangisine kadar geçerli olduğunu taşır (VersionFrom, VersionTo). Kısmi yüklemede sadece değişen kayıtlar yazılır; veri kopyalanmaz.
- **Çalışmalar:** Çalışmadaki geçici değişiklikler tek bir tabloda tutulur (WorkspaceOverride); ana veri değişmez.
- **Plan çıktıları:** Bütün plan çıktıları bir plan hesabına (PlanRun) bağlıdır; onaylı plan yayınlanan hesabı gösterir.
- **Proje:** Stok, iş emri, satın alma ve siparişte sahip alanı (ProjectId); envanter proje sayısıyla çoğaltılmaz.
- **İki katman:** Entegrasyon tabloları kodla (MaterialCode), ana tablolar Id ile; ERP verisi ana tablolara aktarımla geçer.
- **Ek alanlar:** Ana veride 10 (7 metin + 3 sayı), yapı ve işlem verisinde 5 (3 metin + 2 sayı); etiketi FieldDefinition'da.

### Entegrasyon tabloları ve ana tablolar
<sub>21. Veri modeli · İki katman ve ek alanlar</sub>

- ENTEGRASYON TABLOSU
- **stg.Material:** ERP'nin dili: Id yok, ilişkiler kodla. API, SQL arayüzü ve Excel aynı yapıya iner.
  - MaterialCode, LocationCode
  - Name, BaseUom, MaterialGroup …
  - AdditionalText1–7, AdditionalNumber1–3
  - ImportBatchId, RowStatus, ErrorText
- ANA TABLO
- **Material:** Motor, ekranlar ve raporlar yalnız ana tabloları okur; ERP verisi buraya doğrudan yazılmaz.
  - Id, Code, LocationId
  - Name, BaseUom, MaterialGroup …
  - AdditionalText1–7, AdditionalNumber1–3
  - VersionFrom, VersionTo

#### AKTARIM

- **1 · Doğrulama Tip, zorunlu alan, tekrar eden anahtar**
- **Kod → Id eşleme Bilinmeyen kod: satır Hatalı, ana tabloya geçmez:** 2
- **3 · Veri kuralları Eksik alanlar kural ya da elle değerle tamamlanır**
- **4 · Versiyonlu yazma Değişen kayıtlar yeni veri versiyonuyla**
- **Ek alanlar**
  - Ana veri · 10 alan
  - AdditionalText1–7 ve AdditionalNumber1–3. Location, Resource, ResourceGroup, Material, Supplier, Customer, Project, Worker.
  - Yapı ve işlem verisi · 5 alan
  - AdditionalText1–3 ve AdditionalNumber1–2. ProductionVersion, BOM, Routing, MaterialSupplier, SalesOrderLine, Forecast, Stock, iş emri tabloları, PurchaseOrderLine, TransferOrder, ProductionConfirmation.
  - Kullanım
  - Etiket ve görünürlük FieldDefinition'da (ör. AdditionalText3 = 'Malzeme sınıfı'): Label'ı olmayan ek alan listede görünmez (K-88). Ekranda sıralanır ve filtrelenir (U-6–U-8); veri kurallarında koşul olarak kullanılabilir.

### Alanların ana kaynağı
<sub>21. Veri modeli · Alan kaynakları</sub>

| KAYNAK | ANLAMI | ÖRNEK ALAN |
|---|---|---|
| ERP | Entegrasyondan gelir (API, Excel, SQL arayüz tabloları). | Material.Code, SalesOrderLine.OpenQty |
| ERP, yoksa kural | ERP'de varsa oradan; yoksa veri kuralıyla doldurulur. | Resource.ResourceType, Resource.DailyCapacity |
| Kural ya da elle | ERP'de genelde yok; veri kuralıyla ya da ana veri ekranında elle. | Resource.IsConstrained, Routing.CrewSize |
| Smartchain (parametre) | Smartchain'de tanımlanan planlama parametresi; parametre setine bağlı. | ResourceEfficiency.EfficiencyPct, AllocationRule.SharePct |
| Kullanıcı | Kullanıcının ekrandan girdiği tanım. | DataRule, ScenarioDefinition |
| Sistem | Sistemin ürettiği ya da sistem sahibinin yönettiği değer. | Id alanları, PlanRun, Job |
| Ön hesap | Ön hesapta türetilen değer. | WorkOrderComponent.RemainingQty, ResourceDowntime.DurationDays |
| Motor | Planlama motorunun çıktısı. | PlannedOrder, CapacityLoad, Pegging |

### Alan grupları ve veri akışı
<sub>21. Veri modeli · Genel görünüm</sub>

- **Veri yönetimi  9 tablo:** ImportBatch · Staging · DataRule · FieldDefinition · ManualValue · DataVersion
- **Kaynak  13 tablo:** Resource · Worker · ShiftPlan · ResourceDowntime
- **Malzeme  8 tablo:** Material · MaterialSupplier · BOM · Routing · Project
- **Parametre  6 tablo:** ParameterSet · PlanningSetting · PriorityRule · AllocationRule
- yükleme
- **Talep  3 tablo:** Customer · SalesOrderLine · Forecast
- **Arz ve stok  7 tablo:** Stock · WorkOrder · PurchaseOrderLine · TransferOrder
- **Plan  13 tablo:** ScenarioDefinition · Scenario · Workspace · PlanRun · PlanVersion · PlannedOrder · CapacityLoad · Pegging · PlanWarning
- versiyon
- **Sistem  6 tablo:** AppUser · Job · SolverLog · AuditLog · SystemSetting · License
- **Ortak  5 tablo:** Location · UnitOfMeasure · Calendar
- Akış: ERP verisi entegrasyon tablolarına (stg.*) iner, veri kurallarıyla tamamlanır ve yüklemeyle veri versiyonu olur. Senaryolar bir veri versiyonu ve bir parametre setiyle çalışır; çıktılar plan hesabına bağlanır, onaylı plan ERP'ye döner.

### Tablo listesi
<sub>21. Veri modeli · Tablo listesi · 1/6</sub>

#### ORTAK

- **Location:** Lokasyon (tesis, depo)
- **UnitOfMeasure:** Ölçü birimi
- **UomConversion:** Malzeme bazında birim dönüşümü
- **Calendar:** Çalışma takvimi başlığı (kaynaklara bağlanır)
- **CalendarDay:** Takvimin gün bazında çalışma durumu

#### TALEP

- **Customer:** Müşteri
- **SalesOrderLine:** Müşteri sipariş satırı
- **Forecast:** Talep tahmini (netleme ön hesapta)

### Tablo listesi
<sub>21. Veri modeli · Tablo listesi · 2/6</sub>

#### KAYNAK

- **Resource:** Kaynak: makine, işçi, fason, diğer
- **ResourceGroup:** Kaynak grubu (makine grubu, işçi kaynak grubu)
- **ResourceCapacityProfile:** Günlük kapasitenin dönemsel değişikliği (ör
- **ResourceDowntime:** Bakım ve arıza takvimi
- **ResourceEfficiency:** Kaynak ve dönem bazında verim (kapasite katsayısı)
- **ResourcePeriodLimit:** Dönem bazlı üst limit
- **CompetenceGroup:** İşçi yetkinlik grubu
- **Worker:** İşçi
- **WorkerCompetence:** İşçi–yetkinlik grubu eşleşmesi
- **Shift:** Vardiya tanımı
- **ShiftPlan:** Dönem bazında grup–vardiya–kişi sayısı
- **WorkerAbsence:** Kişi bazında izin ve rapor
- **OvertimeLimit:** Fazla mesai üst limiti (vardiya ve dönem bazında)

### Tablo listesi
<sub>21. Veri modeli · Tablo listesi · 3/6</sub>

#### MALZEME

- **Material:** Malzeme ve planlama ana verisi
- **Supplier:** Tedarikçi ve fasoncu
- **MaterialSupplier:** Malzeme–tedarikçi ilişkisi
- **SupplierLimit:** Tedarikçi dönem üst limiti; malzeme boşsa kapalı dönem
- **ProductionVersion:** Üretim versiyonu: bir malzemenin ürün ağacı ve rota başlığı
- Ürün ağacı satırı
- Rota satırı: operasyon–kaynak
- Proje grubu (grup içi paylaşım için)
- Proje

#### SISTEM

- **AppUser:** Uygulama kullanıcısı (Faz 1'de yerel)
- **Job:** İş kuyruğu (SQL Server tablosu): gece senaryoları, çalışma hesapları, yüklemeler
- **SolverLog:** Çözüm logu
- **AuditLog:** Kim, ne zaman, neyi değiştirdi
- **SystemSetting:** Sistem sahibinin ayarları: çözücü, süre bütçeleri, işçi sayısı, eş zamanlı çalışma sınırı, saklama süreleri
- **License:** Çevrimdışı imzalı lisans

#### BOM

- Routing
- ProjectGroup
- Project

### Tablo listesi
<sub>21. Veri modeli · Tablo listesi · 4/6</sub>

#### ARZ VE STOK

- **Stock:** Stok
- **WorkOrder:** Açık iş emri (üretim, fason, yeniden işleme)
- **WorkOrderComponent:** İş emrinin bileşenleri ve çekilen miktar
- **WorkOrderOperation:** İş emrinin operasyonları ve kalan iş
- **PurchaseOrderLine:** Açık satın alma ve fason siparişi satırı (ve talep)
- **TransferOrder:** Açık lokasyonlar arası transfer
- **ProductionConfirmation:** Üretim gerçekleşmeleri

#### PARAMETRE

- **ParameterSet:** Parametre seti
- **PlanningSetting:** Genel planlama parametreleri (anahtar–değer)
- **TimeBucketDefinition:** Zaman yapısı: planlama ufku ve dinamik bucket dizisi
- **PriorityRule:** Sıralama kuralı: kriterlerin sırası (bucket > müşteri > proje > satır > tarih)
- **AllocationRule:** Kapasite alokasyonu: talep sınıfına kaynak (grubu) ve dönem bazında pay
- **WarningDefinition:** Uyarı tanımı, eşik ve önem seviyesi

### Tablo listesi
<sub>21. Veri modeli · Tablo listesi · 5/6</sub>

#### VERI YÖNETIMI

- **FieldDefinition:** Veri sözlüğü: her alanın sınıfı ve değer davranışı
- **DataRule:** Veri kuralı: 'X = … ise Alan = …'
- **DataRuleCondition:** Kural koşulları (VE / VEYA)
- **ManualValue:** Kayıt bazında elle girilen değer
- **FieldValueSource:** Geçerli değerin kaynağı ve ERP değeri (ezilse bile saklanır)
- **ImportBatch:** Ham veri partisi: her yükleme parti numarası, zaman ve kaynakla
- **stg.*:** Entegrasyon tabloları: her varlık için bir tane (stg.Material…); ilişkiler kodla
- **DataVersion:** Yükleme ile oluşan dondurulmuş veri versiyonu
- **DataVersionEntity:** Kısmi yüklemede hangi varlıkların yüklendiği

### Tablo listesi
<sub>21. Veri modeli · Tablo listesi · 6/6</sub>

#### PLAN

- **ScenarioDefinition:** Gece senaryosu tanımı: parametre seti + eksen ayarları
- **Scenario:** Gece üretilen senaryo
- **Workspace:** Kullanıcının bir senaryo üzerindeki çalışması
- **WorkspaceOverride:** Çalışmadaki geçici değişiklikler: parametreler ve çalışmada değiştirilebilir ana veri alanları
- **PlanRun:** Bir plan hesabı (senaryo ya da çalışma)
- **PlanVersion:** Onaylı plan versiyonu
- **PlannedOrder:** Planlı sipariş: üretim, satın alma ya da fason önerisi
- **SupplyRecommendation:** Mevcut arz için öneri: öne çek, ertele, iptal, azalt, hızlandır
- **DemandFulfillment:** Talebin planlanan karşılanması ve gecikmesi
- **CapacityLoad:** Kaynak ve dönem bazında kapasite ve kapasite yükü
- **Pegging:** Arz–talep bağı (full pegging)
- **PlanWarning:** Plan hesabının ürettiği uyarılar
- **PlanMetric:** Senaryo karşılaştırma metrikleri

### Location
<sub>21. Veri modeli · Ortak</sub>

- Ana veri · versiyonsuz · Faz 1
- Lokasyon (tesis, depo). Faz 1'de her lokasyon kendi içinde planlanır.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | int | PK | Lokasyon kimliği | Sistem | H | E |  |
| Code | nvarchar(30) | UK | Lokasyon kodu | ERP | H | E |  |
| Name | nvarchar(100) |  | Lokasyon adı | ERP | H | E |  |
| Type | nvarchar(15) |  | Tesis \| Depo \| Fason deposu | ERP, yoksa kural | H | E | Tesis |
| Country | nvarchar(100) |  | Ülke | ERP | H | H |  |
| CountryCode | nvarchar(10) |  | Ülke kodu | ERP | H | H |  |
| Region | nvarchar(100) |  | Bölge | ERP | H | H |  |
| RegionCode | nvarchar(20) |  | Bölge kodu | ERP | H | H |  |
| City | nvarchar(100) |  | Şehir | ERP | H | H |  |
| CityCode | nvarchar(20) |  | Şehir kodu | ERP | H | H |  |
| AdditionalText1–7 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da | ERP | H | H |  |
| AdditionalNumber1–3 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da | ERP | H | H |  |
| IsSynthetic | bit |  | Sentetik veri (geliştirme ve demo); sentetik veri komutları yalnız bunlara dokunur (K-79) | Sistem | H | H | 0 |

### UnitOfMeasure
<sub>21. Veri modeli · Ortak</sub>

- Ana veri · versiyonsuz · Faz 1
- Ölçü birimi.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Code | nvarchar(10) | PK | Birim kodu (AD, KG, SAAT…) | ERP | H | E |  |
| Name | nvarchar(50) |  | Birim adı | ERP | H | H |  |
| Decimals | tinyint |  | Miktar ondalığı; ERP'den gelmez, Smartchain'de tutulur (K-88) | Smartchain (parametre) | H | H | 2 |

- **Decimals:** bu birimdeki miktarlar ekranda bu kadar ondalıkla gösterilir (K-88). ERP aktarımı ezmez. Önerilen değerler: ADET 0, KG 3, M 2, SAAT 2; bilinmeyen birim 2 (varsayılan). Birim ilk geldiğinde öneri uygulanır, sonra Smartchain'de değiştirilir.

### UomConversion
<sub>21. Veri modeli · Ortak</sub>

- Ana veri · versiyonlu · Faz 1
- Malzeme bazında birim dönüşümü.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| MaterialId | bigint | FK | Malzeme (boşsa genel dönüşüm) | ERP | H | H |  |
| FromUom | nvarchar(10) | FK | Kaynak birim | ERP | H | E |  |
| ToUom | nvarchar(10) | FK | Hedef birim | ERP | H | E |  |
| Factor | decimal(18,6) |  | Çarpan | ERP | H | E |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |

### Calendar
<sub>21. Veri modeli · Ortak</sub>

- Ana veri · versiyonlu · Faz 1
- Çalışma takvimi başlığı (kaynaklara bağlanır). Smartchain'de ekrandan girilir; entegrasyondan gelmez (K-65).

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | int | PK | Takvim kimliği | Sistem | H | E |  |
| Code | nvarchar(30) | UK | Takvim kodu | Kural ya da elle | H | E |  |
| Name | nvarchar(100) |  | Takvim adı | Kural ya da elle | H | H |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |

### CalendarDay
<sub>21. Veri modeli · Ortak</sub>

- Ana veri · versiyonlu · Faz 1
- Takvimin gün bazında çalışma durumu. Smartchain'de ekrandan girilir; entegrasyondan gelmez (K-65).

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| CalendarId | int | PK,FK | Takvim | Kural ya da elle | H | E |  |
| Date | date | PK | Gün | Kural ya da elle | H | E |  |
| IsWorkingDay | bit |  | Çalışma günü mü | Kural ya da elle | H | E | 1 |
| WorkingFraction | decimal(5,4) |  | Günün çalışılan oranı (yarım gün 0,5) | Kural ya da elle | H | H | 1 |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |

### Resource
<sub>21. Veri modeli · Kaynak · 1/2</sub>

- Ana veri · versiyonlu · Faz 1
- Kaynak: makine, işçi, fason, diğer. Kapasite kaynağın kendi biriminde günlük kapasite olarak tutulur.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| LocationId | int | FK | Lokasyon | ERP | H | E |  |
| Code | nvarchar(50) | UK | Kaynak kodu | ERP | H | E |  |
| Name | nvarchar(150) |  | Kaynak adı | ERP | H | H |  |
| ResourceGroupId | bigint | FK | Kaynak grubu | ERP, yoksa kural | H | H |  |
| ResourceType | nvarchar(20) |  | Makine \| İşçi \| Fason \| Kalıp \| Fırın \| Diğer | ERP, yoksa kural | H | E | Diğer |
| ResourceRole | nvarchar(10) |  | Primary \| Secondary | Kural ya da elle | H | E | Primary |
| IsConstrained | bit |  | 1: planda kısıt, 0: sonsuz kapasite (sadece raporlanır) | Kural ya da elle | H | E | 0 |
| CapacityUnit | nvarchar(10) | FK | Kapasite birimi (Saat, Adet, Ton…); rotadaki tüketim aynı birimde kabul edilir | ERP, yoksa kural | H | E | SAAT |
| DailyCapacity | decimal(18,4) |  | Bir adet kaynağın bir çalışma günündeki kapasitesi | ERP, yoksa kural | H | E |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |

### Resource
<sub>21. Veri modeli · Kaynak · 2/2</sub>

- Ana veri · versiyonlu · Faz 1
- Kaynak: makine, işçi, fason, diğer. Kapasite kaynağın kendi biriminde günlük kapasite olarak tutulur.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Quantity | int |  | Paralel kaynak adedi | ERP, yoksa kural | H | E | 1 |
| CalendarId | int | FK | Çalışma takvimi (Smartchain ekranında atanır) | Kural ya da elle | H | E |  |
| CapacitySource | nvarchar(10) |  | İşçi gruplarında: Vardiyadan \| Doğrudan | Kural ya da elle | H | H | Doğrudan |
| SubconPlanningType | nvarchar(15) |  | Fasonda: İş yeri \| Tedarik süresi | Kural ya da elle | H | H |  |
| SupplierId | bigint | FK | Fasonda fasoncu | ERP | H | H |  |
| SubconFixedLeadTimeDays | decimal(9,2) |  | Fasonda sabit süre (taşıma ve kuyruk) | Kural ya da elle | H | H |  |
| SubconVariableDaysPerUnit | decimal(18,6) |  | Fasonda birim başına gün (fasoncunun hızı) | Kural ya da elle | H | H |  |
| AdditionalText1–7 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da | ERP | H | H |  |
| AdditionalNumber1–3 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da | ERP | H | H |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |

### ResourceGroup
<sub>21. Veri modeli · Kaynak</sub>

- Ana veri · versiyonlu · Faz 1
- Kaynak grubu (makine grubu, işçi kaynak grubu).

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| LocationId | int | FK | Lokasyon | ERP | H | E |  |
| Code | nvarchar(50) | UK | Grup kodu | ERP | H | E |  |
| Name | nvarchar(150) |  | Grup adı | ERP | H | H |  |
| AdditionalText1–7 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da | ERP | H | H |  |
| AdditionalNumber1–3 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da | ERP | H | H |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |

### ResourceCapacityProfile
<sub>21. Veri modeli · Kaynak</sub>

- Ana veri · versiyonlu · Faz 1
- Günlük kapasitenin dönemsel değişikliği (ör. ikinci vardiya açıldı). Birim kaynağın CapacityUnit'i; ekranda gösterilir, ayrı saklanmaz. Smartchain'de ekrandan girilir; entegrasyondan gelmez (K-65).

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| ResourceId | bigint | FK | Kaynak | Kural ya da elle | H | E |  |
| ValidFrom | date |  | Başlangıç | Kural ya da elle | H | E |  |
| ValidTo | date |  | Bitiş | Kural ya da elle | H | E |  |
| DailyCapacity | decimal(18,4) |  | Bu aralıktaki günlük kapasite | Kural ya da elle | E | E |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |

### ResourceDowntime
<sub>21. Veri modeli · Kaynak</sub>

- Ana veri · versiyonlu · Faz 1
- Bakım ve arıza takvimi; kapasiteden düşülür. Çalışmada geçici değiştirilebilir. Smartchain'de ekrandan girilir; entegrasyondan gelmez (K-65).

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| ResourceId | bigint | FK | Kaynak | Kural ya da elle | H | E |  |
| DowntimeType | nvarchar(10) |  | Bakım \| Arıza | Kural ya da elle | H | E |  |
| StartAt | datetime2 |  | Başlangıç | Kural ya da elle | E | E |  |
| EndAt | datetime2 |  | Bitiş | Kural ya da elle | E | E |  |
| AffectedQuantity | int |  | Etkilenen kaynak adedi | Kural ya da elle | E | E | 1 |
| DurationDays | decimal(9,4) |  | Süre, gün olarak (yarım gün 0,5) | Ön hesap | H | H |  |
| Note | nvarchar(400) |  | Açıklama | Kullanıcı | H | H |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |

### ResourceEfficiency
<sub>21. Veri modeli · Kaynak</sub>

- Parametre · versiyonsuz · Faz 1
- Kaynak ve dönem bazında verim (kapasite katsayısı); senaryoya özel.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| ParameterSetId | int | FK | Parametre seti | Smartchain (parametre) | H | E |  |
| ResourceId | bigint | FK | Kaynak | Smartchain (parametre) | H | E |  |
| ValidFrom | date |  | Başlangıç | Smartchain (parametre) | H | E |  |
| ValidTo | date |  | Bitiş | Smartchain (parametre) | H | E |  |
| EfficiencyPct | decimal(6,2) |  | Verim (%) | Smartchain (parametre) | E | E | 100 |

### ResourcePeriodLimit
<sub>21. Veri modeli · Kaynak</sub>

- Parametre · versiyonsuz · Faz 1
- Dönem bazlı üst limit; kısıtsız kaynaklarda ve fasonda. Birim kaynağın kapasite birimi.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| ParameterSetId | int | FK | Parametre seti | Smartchain (parametre) | H | E |  |
| ResourceId | bigint | FK | Kaynak | Smartchain (parametre) | H | E |  |
| ValidFrom | date |  | Başlangıç | Smartchain (parametre) | H | E |  |
| ValidTo | date |  | Bitiş | Smartchain (parametre) | H | E |  |
| UpperLimit | decimal(18,4) |  | Dönem üst limiti | Smartchain (parametre) | E | E |  |

### CompetenceGroup
<sub>21. Veri modeli · Kaynak</sub>

- Ana veri · versiyonlu · Faz 1
- İşçi yetkinlik grubu.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| LocationId | int | FK | Lokasyon | ERP | H | E |  |
| Code | nvarchar(50) | UK | Grup kodu | ERP | H | E |  |
| Name | nvarchar(150) |  | Grup adı | ERP | H | H |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |

### Worker
<sub>21. Veri modeli · Kaynak</sub>

- Ana veri · versiyonlu · Faz 1
- İşçi.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| LocationId | int | FK | Lokasyon | ERP | H | E |  |
| Code | nvarchar(50) | UK | Sicil no | ERP | H | E |  |
| Name | nvarchar(150) |  | Ad | ERP | H | H |  |
| ResourceGroupId | bigint | FK | Bağlı olduğu işçi kaynak grubu | ERP, yoksa kural | H | H |  |
| IsActive | bit |  | Aktif mi | ERP | H | H | 1 |
| AdditionalText1–7 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da | ERP | H | H |  |
| AdditionalNumber1–3 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da | ERP | H | H |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |

### WorkerCompetence
<sub>21. Veri modeli · Kaynak</sub>

- Ana veri · versiyonlu · Faz 1
- İşçi–yetkinlik grubu eşleşmesi; çoktan çoğa.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| WorkerId | bigint | PK,FK | İşçi | ERP | H | E |  |
| CompetenceGroupId | bigint | PK,FK | Yetkinlik grubu | ERP | H | E |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |

### Shift
<sub>21. Veri modeli · Kaynak</sub>

- Ana veri · versiyonlu · Faz 1
- Vardiya tanımı. Smartchain'de ekrandan girilir; entegrasyondan gelmez (K-65).

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| LocationId | int | FK | Lokasyon | Kural ya da elle | H | E |  |
| Code | nvarchar(20) | UK | Vardiya kodu | Kural ya da elle | H | E |  |
| StartTime | time |  | Başlangıç saati | Kural ya da elle | H | E |  |
| EndTime | time |  | Bitiş saati | Kural ya da elle | H | E |  |
| BreakMinutes | int |  | Mola süresi (dk) | Kural ya da elle | H | H | 0 |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |

### ShiftPlan
<sub>21. Veri modeli · Kaynak</sub>

- Ana veri · versiyonlu · Faz 1
- Dönem bazında grup–vardiya–kişi sayısı. Çalışmada geçici değiştirilebilir. Smartchain'de ekrandan girilir; entegrasyondan gelmez (K-65).

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| CompetenceGroupId | bigint | FK | Yetkinlik grubu (ya da) | Kural ya da elle | H | H |  |
| ResourceGroupId | bigint | FK | İşçi kaynak grubu | Kural ya da elle | H | H |  |
| ShiftId | bigint | FK | Vardiya | Kural ya da elle | H | E |  |
| ValidFrom | date |  | Başlangıç | Kural ya da elle | H | E |  |
| ValidTo | date |  | Bitiş | Kural ya da elle | H | E |  |
| Headcount | int |  | Kişi sayısı | Kural ya da elle | E | E |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |

### WorkerAbsence
<sub>21. Veri modeli · Kaynak</sub>

- İşlem verisi · versiyonlu · Faz 1
- Kişi bazında izin ve rapor.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| WorkerId | bigint | FK | İşçi | ERP | H | E |  |
| StartAt | datetime2 |  | Başlangıç | ERP | H | E |  |
| EndAt | datetime2 |  | Bitiş | ERP | H | E |  |
| AbsenceType | nvarchar(10) |  | İzin \| Rapor | ERP | H | E |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |

### OvertimeLimit
<sub>21. Veri modeli · Kaynak</sub>

- Parametre · versiyonsuz · Faz 1
- Fazla mesai üst limiti (vardiya ve dönem bazında).

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| ParameterSetId | int | FK | Parametre seti | Smartchain (parametre) | H | E |  |
| ShiftPlanId | bigint | FK | Vardiya planı | Smartchain (parametre) | H | E |  |
| MaxOvertimeHours | decimal(9,2) |  | Dönem başına en fazla fazla mesai (saat) | Smartchain (parametre) | E | E |  |

### Material
<sub>21. Veri modeli · Malzeme · 1/2</sub>

- Ana veri · versiyonlu · Faz 1
- Malzeme ve planlama ana verisi.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| LocationId | int | FK | Lokasyon | ERP | H | E |  |
| Code | nvarchar(50) | UK | Malzeme kodu | ERP | H | E |  |
| Name | nvarchar(200) |  | Malzeme adı | ERP | H | H |  |
| BaseUom | nvarchar(10) | FK | Temel birim | ERP | H | E |  |
| MaterialGroup | nvarchar(50) |  | Malzeme grubu | ERP | H | H |  |
| MaterialLevel | nvarchar(15) |  | Malzeme seviyesi: Hammadde \| Yarı mamul \| Nihai ürün | ERP, yoksa kural | H | H |  |
| IsPurchasable | bit |  | Satın alınabilir | ERP, yoksa kural | H | H | 0 |
| IsProducible | bit |  | Üretilebilir | ERP, yoksa kural | H | H | 0 |
| IsSellable | bit |  | Satılabilir | ERP, yoksa kural | H | H | 0 |
| DefaultProcurement | nvarchar(10) |  | Tedarik türü: Üretim \| Satın alma \| Fason | ERP, yoksa kural | H | H |  |
| Ownership | nvarchar(10) |  | Sahiplik: Kendi \| Müşteri (müşteri temin malzemesi) | Kural ya da elle | H | H | Kendi |

### Material
<sub>21. Veri modeli · Malzeme · 2/2</sub>

- Ana veri · versiyonlu · Faz 1
- Malzeme ve planlama ana verisi.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| IsProjectTracked | bit |  | Proje bazlı takip; değilse her zaman ortak | Kural ya da elle | H | H | 0 |
| IsPhantom | bit |  | Hayalet yarı mamul | ERP | H | H | 0 |
| ProductionLeadTimeDays | decimal(9,2) |  | Üretim süresi (gün) | ERP, yoksa kural | H | H |  |
| GoodsReceiptDays | decimal(9,2) |  | Mal kabul süresi (iş günü) | ERP, yoksa kural | H | H | 0 |
| SafetyStock | decimal(18,4) |  | Güvenlik stoğu | ERP | H | H | 0 |
| MaxStock | decimal(18,4) |  | Maksimum stok | ERP | H | H |  |
| LotSizePolicy | nvarchar(15) |  | Lot politikası (üretimde): Lot-for-lot \| Sabit \| Dönemsel | ERP, yoksa kural | H | H | Lot-for-lot |
| MinLot | decimal(18,4) |  | Üretimde minimum | ERP | H | H |  |
| MaxLot | decimal(18,4) |  | Üretimde maksimum | ERP | H | H |  |
| LotMultiple | decimal(18,4) |  | Üretimde kat | ERP | H | H |  |
| AssemblyScrapPct | decimal(6,2) |  | Montaj firesi (%) | ERP | H | H | 0 |
| ShelfLifeDays | int |  | Raf ömrü (gün); Faz 1'de yalnız uyarı | ERP | H | H |  |
| AdditionalText1–7 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da | ERP | H | H |  |
| AdditionalNumber1–3 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da | ERP | H | H |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |

### Supplier
<sub>21. Veri modeli · Malzeme</sub>

- Ana veri · versiyonlu · Faz 1
- Tedarikçi ve fasoncu.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| Code | nvarchar(50) | UK | Tedarikçi kodu | ERP | H | E |  |
| Name | nvarchar(200) |  | Ad | ERP | H | H |  |
| IsSubcontractor | bit |  | Fasoncu mu | ERP, yoksa kural | H | H | 0 |
| AdditionalText1–7 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da | ERP | H | H |  |
| AdditionalNumber1–3 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da | ERP | H | H |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |

### MaterialSupplier
<sub>21. Veri modeli · Malzeme</sub>

- Ana veri · versiyonlu · Faz 1
- Malzeme–tedarikçi ilişkisi; satın alma parametreleri. Satın alma her zaman sürekli; yuvarlama son hesapta.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| MaterialId | bigint | FK | Malzeme | ERP | H | E |  |
| SupplierId | bigint | FK | Tedarikçi | ERP | H | E |  |
| Priority | int |  | Öncelik | ERP, yoksa kural | H | H | 1 |
| QuotaPct | decimal(6,2) |  | Kota (%) | ERP, yoksa kural | H | H |  |
| LeadTimeDays | decimal(9,2) |  | Tedarik süresi | ERP | H | E |  |
| LeadTimeBasis | nvarchar(15) |  | Takvim günü \| İş günü | Kural ya da elle | H | H | Takvim günü |
| MinOrderQty | decimal(18,4) |  | Minimum sipariş miktarı | ERP | H | H |  |
| OrderMultiple | decimal(18,4) |  | Kat | ERP | H | H |  |
| MaxOrderQty | decimal(18,4) |  | Maksimum | ERP | H | H |  |
| ValidFrom | date |  | Geçerlilik başlangıcı | ERP | H | H |  |
| ValidTo | date |  | Geçerlilik bitişi | ERP | H | H |  |
| AdditionalText1–3 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da | ERP | H | H |  |
| AdditionalNumber1–2 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da | ERP | H | H |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |

### SupplierLimit
<sub>21. Veri modeli · Malzeme</sub>

- Parametre · versiyonsuz · Faz 1
- Tedarikçi dönem üst limiti (problem 39): malzeme bazında maksimum miktar. Malzeme boşsa tedarikçi o dönemde kapalıdır (limit 0). Smartchain'de ekrandan girilir (K-65, K-66).

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| ParameterSetId | int | FK | Parametre seti | Smartchain (parametre) | H | E |  |
| SupplierId | bigint | FK | Tedarikçi | Smartchain (parametre) | H | E |  |
| MaterialId | bigint | FK | Malzeme; boşsa tedarikçinin bütün malzemeleri (yalnız kapalı dönem) | Smartchain (parametre) | H | H |  |
| ValidFrom | date |  | Başlangıç | Smartchain (parametre) | H | E |  |
| ValidTo | date |  | Bitiş | Smartchain (parametre) | H | E |  |
| UpperLimit | decimal(18,4) |  | Dönem üst limiti, malzemenin temel biriminde; malzeme boşsa 0 | Smartchain (parametre) | E | E | 0 |

### ProductionVersion
<sub>21. Veri modeli · Malzeme</sub>

- Ana veri · versiyonlu · Faz 1
- Üretim versiyonu: bir malzemenin ürün ağacı ve rota başlığı; rotaya RouteCode ile bağlanır. Faz 1'de varsayılan versiyon kullanılır.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| MaterialId | bigint | FK | Üretilen malzeme | ERP | H | E |  |
| Code | nvarchar(30) |  | Versiyon kodu | ERP | H | E |  |
| IsDefault | bit |  | Varsayılan versiyon | ERP, yoksa kural | H | E | 1 |
| BaseQuantity | decimal(18,4) |  | Baz miktar (rota ve ağaç bu miktar için) | ERP | H | H | 1 |
| RouteCode | nvarchar(50) |  | Rota kodu (Routing.RouteCode) | ERP | H | E |  |
| ValidFrom | date |  | Geçerlilik başlangıcı | ERP | H | H |  |
| ValidTo | date |  | Geçerlilik bitişi | ERP | H | H |  |
| AdditionalText1–3 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da | ERP | H | H |  |
| AdditionalNumber1–2 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da | ERP | H | H |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |

### BOM
<sub>21. Veri modeli · Malzeme</sub>

- Ana veri · versiyonlu · Faz 1
- Ürün ağacı satırı.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| ProductionVersionId | bigint | FK | Üretim versiyonu | ERP | H | E |  |
| ComponentMaterialId | bigint | FK | Bileşen | ERP | H | E |  |
| Quantity | decimal(18,6) |  | Baz miktar için bileşen miktarı | ERP | H | E |  |
| ScrapPct | decimal(6,2) |  | Bileşen firesi (%) | ERP | H | H | 0 |
| IsFixedQuantity | bit |  | Sabit miktarlı bileşen | ERP | H | H | 0 |
| OpNo | int |  | Bağlı olduğu operasyon no (ihtiyaç tarihi için) | ERP | H | H |  |
| AdditionalText1–3 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da | ERP | H | H |  |
| AdditionalNumber1–2 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da | ERP | H | H |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |

### Routing
<sub>21. Veri modeli · Malzeme · 1/2</sub>

- Ana veri · versiyonlu · Faz 1
- Rota: her satır bir operasyon–kaynak ilişkisi; sıra önce OpNo, sonra SeqNo. Aynı operasyonun kaynakları ayrı satırda, ResourceRole ile.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| RouteCode | nvarchar(50) | UK | Rota kodu | ERP | H | E |  |
| OpNo | int | UK | Operasyon no (birinci sıralama) | ERP | H | E |  |
| SeqNo | int | UK | Operasyon içindeki alt sıra (ikinci sıralama) | ERP | H | E |  |
| OperationName | nvarchar(150) |  | Operasyon adı | ERP | H | H |  |
| ResourceId | bigint | FK | Kaynak | ERP | H | E |  |
| ResourceRole | nvarchar(10) |  | Primary \| Secondary | ERP, yoksa kural | H | E | Primary |
| Consumption | decimal(18,6) |  | Baz miktar için kaynak tüketimi (kaynağın kapasite biriminde) | ERP | H | E |  |
| ResourceNumber | int |  | Operasyonda aynı anda kullanılan kaynak adedi | ERP, yoksa kural | H | E | 1 |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |

### Routing
<sub>21. Veri modeli · Malzeme · 2/2</sub>

- Ana veri · versiyonlu · Faz 1
- Rota: her satır bir operasyon–kaynak ilişkisi; sıra önce OpNo, sonra SeqNo. Aynı operasyonun kaynakları ayrı satırda, ResourceRole ile.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| IsSubcontracted | bit |  | Fason operasyon | ERP | H | H | 0 |
| TransferLotQty | decimal(18,4) |  | Transfer partisi | ERP | H | H |  |
| LaborType | nvarchar(15) |  | İşçi: Yetkinlik grubu \| Kaynak grubu \| Yok | Kural ya da elle | H | H | Yok |
| LaborRefId | bigint |  | İlgili yetkinlik ya da kaynak grubu | Kural ya da elle | H | H |  |
| LaborBasis | nvarchar(10) |  | Ekip (süre × kişi) \| Toplam (adam-saat) | Kural ya da elle | H | H | Ekip |
| CrewSize | int |  | Gerekli işçi sayısı | Kural ya da elle | H | H | 1 |
| LaborTime | decimal(18,6) |  | Toplam işçilik (adam-saat), LaborBasis = Toplam ise | Kural ya da elle | H | H |  |
| AdditionalText1–3 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da | ERP | H | H |  |
| AdditionalNumber1–2 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da | ERP | H | H |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |

### ProjectGroup
<sub>21. Veri modeli · Malzeme</sub>

- Ana veri · versiyonlu · Faz 1
- Proje grubu (grup içi paylaşım için).

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| Code | nvarchar(50) | UK | Grup kodu | Kural ya da elle | H | E |  |
| Name | nvarchar(200) |  | Proje grubu adı | Kural ya da elle | H | H |  |
| IsolationRule | nvarchar(20) |  | Tam izolasyon \| Ortaktan beslenir \| Grup içi paylaşım | Kural ya da elle | H | H | Ortaktan beslenir |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |

### Project
<sub>21. Veri modeli · Malzeme</sub>

- Ana veri · versiyonlu · Faz 1
- Proje.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| Code | nvarchar(50) | UK | Proje kodu | ERP | H | E |  |
| Name | nvarchar(200) |  | Proje adı | ERP | H | H |  |
| ProjectGroupId | bigint | FK | Proje grubu | Kural ya da elle | H | H |  |
| IsolationRule | nvarchar(20) |  | Proje bazında izolasyon (grubu ezer) | Kural ya da elle | H | H |  |
| Priority | int |  | Proje önceliği | Kural ya da elle | H | H |  |
| IsClosed | bit |  | Kapandı mı | ERP | H | H | 0 |
| AdditionalText1–7 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da | ERP | H | H |  |
| AdditionalNumber1–3 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da | ERP | H | H |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |

### Customer
<sub>21. Veri modeli · Talep</sub>

- Ana veri · versiyonlu · Faz 1
- Müşteri.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| Code | nvarchar(50) | UK | Müşteri kodu | ERP | H | E |  |
| Name | nvarchar(200) |  | Ad | ERP | H | H |  |
| Priority | int |  | Müşteri önceliği | Kural ya da elle | H | H |  |
| AllowPartialDelivery | bit |  | Kısmi teslimata izin | ERP, yoksa kural | H | H | 1 |
| AdditionalText1–7 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da | ERP | H | H |  |
| AdditionalNumber1–3 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da | ERP | H | H |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |

### SalesOrderLine
<sub>21. Veri modeli · Talep</sub>

- İşlem verisi · versiyonlu · Faz 1
- Müşteri sipariş satırı; teklifler Type = Teklif ile gelir, plana dahil olmaları senaryo parametresi. Vade: teyit tarihi, yoksa istek tarihi.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| LocationId | int | FK | Lokasyon | ERP | H | E |  |
| OrderNo | nvarchar(30) | UK | Sipariş no | ERP | H | E |  |
| LineNo | int | UK | Satır no | ERP | H | E |  |
| LineItemNo | int | UK | Alt satır no (ERP satırı kırılımlıysa) | ERP | H | H | 0 |
| Type | nvarchar(10) |  | Kesin \| Teklif | ERP, yoksa kural | H | E | Kesin |
| CustomerId | bigint | FK | Müşteri | ERP | H | E |  |
| MaterialId | bigint | FK | Malzeme | ERP | H | E |  |
| ProjectId | bigint | FK | Proje | ERP | H | H |  |
| OpenQty | decimal(18,4) |  | Açık miktar | ERP | H | E |  |
| RequestedDate | date |  | İstek tarihi | ERP | H | E |  |
| ConfirmedDate | date |  | Teyit tarihi | ERP | H | H |  |
| Priority | int |  | Satır önceliği | Kural ya da elle | H | H |  |
| AllowPartialDelivery | bit |  | Kısmi teslimat (müşteriyi ezer) | ERP | H | H |  |
| Status | nvarchar(15) |  | Açık \| Kapandı \| İptal | ERP | H | E |  |
| AdditionalText1–3 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da | ERP | H | H |  |
| AdditionalNumber1–2 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da | ERP | H | H |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |

### Forecast
<sub>21. Veri modeli · Talep</sub>

- İşlem verisi · versiyonlu · Faz 1
- Talep tahmini (netleme ön hesapta).

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| LocationId | int | FK | Lokasyon | ERP | H | E |  |
| MaterialId | bigint | FK | Malzeme | ERP | H | E |  |
| CustomerId | bigint | FK | Müşteri | ERP | H | H |  |
| ProjectId | bigint | FK | Proje | ERP | H | H |  |
| Period | date |  | Dönem | ERP | H | E |  |
| Quantity | decimal(18,4) |  | Miktar | ERP | H | E |  |
| AdditionalText1–3 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da | ERP | H | H |  |
| AdditionalNumber1–2 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da | ERP | H | H |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |

### Stock
<sub>21. Veri modeli · Arz ve stok</sub>

- İşlem verisi · versiyonlu · Faz 1
- Stok; lot ve durum bazında. Sahip: proje ya da ortak.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| LocationId | int | FK | Lokasyon | ERP | H | E |  |
| MaterialId | bigint | FK | Malzeme | ERP | H | E |  |
| Warehouse | nvarchar(30) |  | Depo | ERP | H | H |  |
| LotNo | nvarchar(50) |  | Lot / seri | ERP | H | H |  |
| StockStatus | nvarchar(15) |  | Serbest \| Kalitede \| Bloke | ERP | H | E | Serbest |
| ProjectId | bigint | FK | Sahip proje (boşsa ortak) | ERP | H | H |  |
| Quantity | decimal(18,4) |  | Miktar | ERP | H | E |  |
| QualityEntryDate | date |  | Kaliteye giriş tarihi | ERP | H | H |  |
| ExpiryDate | date |  | Son kullanma tarihi (raf ömrü sonraki faz) | ERP | H | H |  |
| AdditionalText1–3 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da | ERP | H | H |  |
| AdditionalNumber1–2 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da | ERP | H | H |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |

### WorkOrder
<sub>21. Veri modeli · Arz ve stok</sub>

- İşlem verisi · versiyonlu · Faz 1
- Açık iş emri (üretim, fason, yeniden işleme).

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| LocationId | int | FK | Lokasyon | ERP | H | E |  |
| OrderNo | nvarchar(30) | UK | İş emri no | ERP | H | E |  |
| MaterialId | bigint | FK | Üretilen malzeme | ERP | H | E |  |
| OrderType | nvarchar(15) |  | Üretim \| Fason \| Yeniden işleme | ERP, yoksa kural | H | E | Üretim |
| Status | nvarchar(15) |  | Planlı \| Yayınlandı \| Başladı \| Kısmi \| Bitti | ERP | H | E |  |
| OrderQty | decimal(18,4) |  | İş emri miktarı | ERP | H | E |  |
| OpenQty | decimal(18,4) |  | Açık miktar | ERP | H | E |  |
| StartDate | date |  | Başlangıç | ERP | H | H |  |
| DueDate | date |  | Bitiş | ERP | H | E |  |
| ProjectId | bigint | FK | Proje (ayraç) | ERP | H | H |  |
| SalesOrderLineId | bigint | FK | Bağlı sipariş satırı (ayraç) | ERP | H | H |  |
| ParentWorkOrderId | bigint | FK | Yeniden işlemede orijinal iş emri | Kural ya da elle | H | H |  |
| LastActivityDate | date |  | Son hareket tarihi (eskime kontrolü) | ERP | H | H |  |
| AdditionalText1–3 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da | ERP | H | H |  |
| AdditionalNumber1–2 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da | ERP | H | H |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |

### WorkOrderComponent
<sub>21. Veri modeli · Arz ve stok</sub>

- İşlem verisi · versiyonlu · Faz 1
- İş emrinin bileşenleri ve çekilen miktar.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| WorkOrderId | bigint | FK | İş emri | ERP | H | E |  |
| MaterialId | bigint | FK | Bileşen | ERP | H | E |  |
| RequiredQty | decimal(18,4) |  | Gereken miktar | ERP | H | E |  |
| IssuedQty | decimal(18,4) |  | Çekilen miktar | ERP | H | H | 0 |
| RemainingQty | decimal(18,4) |  | Kalan ihtiyaç | Ön hesap | H | H |  |
| AdditionalText1–3 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da | ERP | H | H |  |
| AdditionalNumber1–2 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da | ERP | H | H |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |

### WorkOrderOperation
<sub>21. Veri modeli · Arz ve stok</sub>

- İşlem verisi · versiyonlu · Faz 1
- İş emrinin operasyonları ve kalan iş.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| WorkOrderId | bigint | FK | İş emri | ERP | H | E |  |
| OpNo | int |  | Operasyon no | ERP | H | E |  |
| SeqNo | int |  | Operasyon içindeki alt sıra | ERP | H | E |  |
| ResourceId | bigint | FK | Kaynak | ERP | H | E |  |
| PlannedConsumption | decimal(18,6) |  | Planlanan tüketim | ERP | H | H |  |
| ConfirmedConsumption | decimal(18,6) |  | Teyit edilen tüketim | ERP | H | H | 0 |
| RemainingConsumption | decimal(18,6) |  | Kalan yük | Ön hesap | H | H |  |
| Status | nvarchar(15) |  | Açık \| Bitti | ERP | H | H |  |
| AdditionalText1–3 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da | ERP | H | H |  |
| AdditionalNumber1–2 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da | ERP | H | H |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |

### PurchaseOrderLine
<sub>21. Veri modeli · Arz ve stok</sub>

- İşlem verisi · versiyonlu · Faz 1
- Açık satın alma ve fason siparişi satırı (ve talep).

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| LocationId | int | FK | Lokasyon | ERP | H | E |  |
| OrderNo | nvarchar(30) | UK | Sipariş no | ERP | H | E |  |
| LineNo | int | UK | Satır no | ERP | H | E |  |
| OrderType | nvarchar(20) |  | Satın alma talebi \| Satın alma \| Fason | ERP | H | E |  |
| SupplierId | bigint | FK | Tedarikçi | ERP | H | H |  |
| MaterialId | bigint | FK | Malzeme | ERP | H | E |  |
| OpenQty | decimal(18,4) |  | Açık miktar | ERP | H | E |  |
| RequestedDate | date |  | İstenen tarih | ERP | H | H |  |
| ConfirmedDate | date |  | Tedarikçi teyit tarihi | ERP | H | H |  |
| ProjectId | bigint | FK | Proje | ERP | H | H |  |
| WorkOrderId | bigint | FK | Fasonda bağlı iş emri | ERP | H | H |  |
| Status | nvarchar(15) |  | Durum | ERP | H | E |  |
| AdditionalText1–3 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da | ERP | H | H |  |
| AdditionalNumber1–2 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da | ERP | H | H |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |

### TransferOrder
<sub>21. Veri modeli · Arz ve stok</sub>

- İşlem verisi · versiyonlu · Faz 1
- Açık lokasyonlar arası transfer; Faz 1'de sabit hareket (gelen arz, giden talep).

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| OrderNo | nvarchar(30) | UK | Transfer no | ERP | H | E |  |
| FromLocationId | int | FK | Çıkış lokasyonu | ERP | H | E |  |
| ToLocationId | int | FK | Varış lokasyonu | ERP | H | E |  |
| MaterialId | bigint | FK | Malzeme | ERP | H | E |  |
| OpenQty | decimal(18,4) |  | Açık miktar | ERP | H | E |  |
| ShipDate | date |  | Çıkış tarihi | ERP | H | H |  |
| ReceiptDate | date |  | Varış tarihi | ERP | H | H |  |
| AdditionalText1–3 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da | ERP | H | H |  |
| AdditionalNumber1–2 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da | ERP | H | H |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |

### ProductionConfirmation
<sub>21. Veri modeli · Arz ve stok</sub>

- İşlem verisi · versiyonlu · Faz 1
- Üretim gerçekleşmeleri; ilk günden tutulur (verim önerisi ve ileriki fazlar).

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| WorkOrderId | bigint | FK | İş emri | ERP | H | E |  |
| OpNo | int |  | Operasyon no | ERP | H | H |  |
| SeqNo | int |  | Operasyon içindeki alt sıra | ERP | H | H |  |
| ResourceId | bigint | FK | Kaynak | ERP | H | H |  |
| ConfirmedQty | decimal(18,4) |  | Teyit miktarı | ERP | H | E |  |
| ActualConsumption | decimal(18,6) |  | Gerçekleşen tüketim (süre) | ERP | H | H |  |
| StartAt | datetime2 |  | Başlangıç | ERP | H | H |  |
| EndAt | datetime2 |  | Bitiş | ERP | H | H |  |
| AdditionalText1–3 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da | ERP | H | H |  |
| AdditionalNumber1–2 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da | ERP | H | H |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |

### ParameterSet
<sub>21. Veri modeli · Parametre</sub>

- Parametre · versiyonsuz · Faz 1
- Parametre seti; gece senaryoları farklı setlerle çalışır.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | int | PK | Set kimliği | Sistem | H | E |  |
| Name | nvarchar(100) |  | Set adı | Kullanıcı | H | E |  |
| IsDefault | bit |  | Varsayılan set | Kullanıcı | H | H | 0 |
| IsSynthetic | bit |  | Sentetik veri (geliştirme ve demo); sentetik veri komutları yalnız bunlara dokunur (K-79) | Sistem | H | H | 0 |

### PlanningSetting
<sub>21. Veri modeli · Parametre</sub>

- Parametre · versiyonsuz · Faz 1
- Genel planlama parametreleri (anahtar–değer); ör. model tipi, fazla mesai dahil mi, fix dönem, toleranslar, MRP öncelik ve kısıt ayarları.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| ParameterSetId | int | PK,FK | Parametre seti | Smartchain (parametre) | H | E |  |
| SettingKey | nvarchar(60) | PK | Parametre adı (ör. ModelType, UseOvertime, FixPeriodDays) | Smartchain (parametre) | H | E |  |
| Value | nvarchar(200) |  | Değer | Smartchain (parametre) | E | E |  |

### TimeBucketDefinition
<sub>21. Veri modeli · Parametre</sub>

- Parametre · versiyonsuz · Faz 1
- Zaman yapısı: planlama ufku ve dinamik bucket dizisi.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| ParameterSetId | int | PK,FK | Parametre seti | Smartchain (parametre) | H | E |  |
| Seq | int | PK | Sıra | Smartchain (parametre) | H | E |  |
| BucketType | nvarchar(10) |  | Gün \| Hafta \| Ay \| Çeyrek \| Yıl | Smartchain (parametre) | H | E |  |
| Count | int |  | Bu tipten kaç bucket | Smartchain (parametre) | H | E |  |

### PriorityRule
<sub>21. Veri modeli · Parametre</sub>

- Parametre · versiyonsuz · Faz 1
- Sıralama kuralı: kriterlerin sırası (bucket > müşteri > proje > satır > tarih).

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| ParameterSetId | int | PK,FK | Parametre seti | Smartchain (parametre) | H | E |  |
| Seq | int | PK | Sıra | Smartchain (parametre) | H | E |  |
| Criterion | nvarchar(30) |  | Kriter | Smartchain (parametre) | E | E |  |
| Direction | nvarchar(10) |  | Artan \| Azalan | Smartchain (parametre) | H | H | Artan |

### AllocationRule
<sub>21. Veri modeli · Parametre</sub>

- Parametre · versiyonsuz · Faz 1
- Kapasite alokasyonu: talep sınıfına kaynak (grubu) ve dönem bazında pay.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| ParameterSetId | int | FK | Parametre seti | Smartchain (parametre) | H | E |  |
| DemandClass | nvarchar(100) |  | Talep sınıfı tanımı (müşteri, proje, ürün grubu) | Smartchain (parametre) | H | E |  |
| ResourceId | bigint | FK | Kaynak | Smartchain (parametre) | H | H |  |
| ResourceGroupId | bigint | FK | Kaynak grubu | Smartchain (parametre) | H | H |  |
| ValidFrom | date |  | Başlangıç | Smartchain (parametre) | H | H |  |
| ValidTo | date |  | Bitiş | Smartchain (parametre) | H | H |  |
| SharePct | decimal(6,2) |  | Pay (%) | Smartchain (parametre) | E | E |  |
| Hardness | nvarchar(10) |  | Taban \| Tavan \| Yumuşak | Smartchain (parametre) | H | H | Yumuşak |

### WarningDefinition
<sub>21. Veri modeli · Parametre</sub>

- Parametre · versiyonsuz · Faz 1
- Uyarı tanımı, eşik ve önem seviyesi.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Code | nvarchar(30) | PK | Uyarı kodu | Sistem | H | E |  |
| Category | nvarchar(20) |  | Kapasite \| Malzeme \| Sipariş \| Ana veri \| İşlem verisi \| Veri değişikliği \| Plan değişikliği | Sistem | H | E |  |
| Threshold | decimal(18,4) |  | Tolerans eşiği | Smartchain (parametre) | H | H |  |
| Severity | nvarchar(10) |  | Önem seviyesi | Smartchain (parametre) | H | H |  |
| IsActive | bit |  | Aktif | Smartchain (parametre) | H | H | 1 |

### FieldDefinition
<sub>21. Veri modeli · Veri yönetimi</sub>

- Veri yönetimi · versiyonsuz · Faz 1
- Veri sözlüğü: her alanın sınıfı ve değer davranışı. Yapısını sistem sahibi yönetir.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| TableName | nvarchar(60) | PK | Tablo | Sistem | H | E |  |
| FieldName | nvarchar(60) | PK | Alan | Sistem | H | E |  |
| FieldClass | nvarchar(15) |  | Ana veri \| Parametre \| İşlem verisi | Sistem | H | E |  |
| EditableInWorkspace | bit |  | Çalışmada geçici değiştirilebilir mi | Sistem | H | E | 0 |
| ValuePriority | nvarchar(10) |  | ERP ezer \| Kural ezer | Sistem | H | H | ERP ezer |
| ManualOverrides | bit |  | Elle değer her şeyi ezer mi | Sistem | H | H | 1 |
| DefaultValue | nvarchar(200) |  | Varsayılan | Sistem | H | H |  |
| IsRequired | bit |  | Zorunlu mu | Sistem | H | H | 0 |
| Label | nvarchar(100) |  | Ekranda görünen etiket; standart alanın etiketini ezer, ek alanda boşsa alan gösterilmez (K-88) | Sistem | H | H |  |

### DataRule
<sub>21. Veri modeli · Veri yönetimi</sub>

- Veri yönetimi · versiyonsuz · Faz 1
- Veri kuralı: 'X = … ise Alan = …'.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| TableName | nvarchar(60) |  | Hedef tablo | Kullanıcı | H | E |  |
| FieldName | nvarchar(60) |  | Hedef alan | Kullanıcı | H | E |  |
| Seq | int |  | Sıra (ilk eşleşen kazanır) | Kullanıcı | H | E |  |
| AssignValue | nvarchar(200) |  | Atanacak değer | Kullanıcı | H | H |  |
| AssignFromField | nvarchar(60) |  | Ya da başka bir alandan | Kullanıcı | H | H |  |
| Owner | nvarchar(10) |  | Kurulum \| Kullanıcı | Sistem | H | E |  |
| IsActive | bit |  | Aktif | Kullanıcı | H | H | 1 |
| ValidFrom | date |  | Geçerlilik | Kullanıcı | H | H |  |
| ValidTo | date |  | Geçerlilik | Kullanıcı | H | H |  |
| Description | nvarchar(400) |  | Açıklama | Kullanıcı | H | H |  |

### DataRuleCondition
<sub>21. Veri modeli · Veri yönetimi</sub>

- Veri yönetimi · versiyonsuz · Faz 1
- Kural koşulları (VE / VEYA).

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| DataRuleId | bigint | FK | Kural | Kullanıcı | H | E |  |
| GroupNo | int |  | VEYA grubu | Kullanıcı | H | H | 1 |
| FieldName | nvarchar(60) |  | Alan | Kullanıcı | H | E |  |
| Operator | nvarchar(15) |  | Eşittir \| İçinde \| İle başlar \| İçerir \| Büyüktür \| Küçüktür \| Boş | Kullanıcı | H | E |  |
| Value | nvarchar(200) |  | Değer | Kullanıcı | H | H |  |

### ManualValue
<sub>21. Veri modeli · Veri yönetimi</sub>

- Veri yönetimi · versiyonsuz · Faz 1
- Kayıt bazında elle girilen değer.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| TableName | nvarchar(60) |  | Tablo | Kullanıcı | H | E |  |
| RecordKey | nvarchar(200) |  | Kaydın iş anahtarı | Kullanıcı | H | E |  |
| FieldName | nvarchar(60) |  | Alan | Kullanıcı | H | E |  |
| Value | nvarchar(200) |  | Değer | Kullanıcı | H | E |  |
| ValidUntil | nvarchar(20) |  | Süresiz \| ERP değişene kadar \| tarih | Kullanıcı | H | H | Süresiz |
| CreatedBy | int | FK | Giren kullanıcı | Sistem | H | H |  |
| CreatedAt | datetime2 |  | Zaman | Sistem | H | H |  |

### FieldValueSource
<sub>21. Veri modeli · Veri yönetimi</sub>

- Veri yönetimi · versiyonsuz · Faz 1
- Geçerli değerin kaynağı ve ERP değeri (ezilse bile saklanır).

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| TableName | nvarchar(60) | PK | Tablo | Sistem | H | E |  |
| RecordId | bigint | PK | Kayıt | Sistem | H | E |  |
| FieldName | nvarchar(60) | PK | Alan | Sistem | H | E |  |
| Source | nvarchar(10) |  | ERP \| Kural \| Elle \| Varsayılan | Sistem | H | E |  |
| DataRuleId | bigint | FK | Uygulanan kural | Sistem | H | H |  |
| ErpValue | nvarchar(200) |  | ERP'den gelen değer | Sistem | H | H |  |

### ImportBatch
<sub>21. Veri modeli · Veri yönetimi</sub>

- Veri yönetimi · versiyonsuz · Faz 1
- Ham veri partisi: her yükleme parti numarası, zaman ve kaynakla. Ham veri bir hafta saklanır.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| Method | nvarchar(10) |  | API \| Excel \| SQL | Sistem | H | E |  |
| EntityName | nvarchar(60) |  | Varlık | Sistem | H | E |  |
| LoadType | nvarchar(10) |  | Tam \| Değişen | Sistem | H | E |  |
| ReceivedAt | datetime2 |  | Alınma zamanı | Sistem | H | E |  |
| Status | nvarchar(15) |  | Alındı \| Doğrulandı \| Hatalı \| Yüklendi | Sistem | H | E |  |
| RowCount | int |  | Satır sayısı | Sistem | H | H |  |
| ErrorCount | int |  | Hatalı satır | Sistem | H | H |  |

### stg.*
<sub>21. Veri modeli · Veri yönetimi</sub>

- Entegrasyon · versiyonsuz · Faz 1
- Entegrasyon tabloları: her varlık için bir tane (stg.Material…). ERP'nin dili: Id yok, ilişkiler kodla. API, SQL ve Excel buraya iner.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| StagingRowId | bigint | PK | Satır kimliği | Sistem | H | E |  |
| ImportBatchId | bigint | FK | Yükleme partisi | Sistem | H | E |  |
| RowStatus | nvarchar(15) |  | Yeni \| Hatalı \| Aktarıldı | Sistem | H | E | Yeni |
| ErrorText | nvarchar(400) |  | Hata açıklaması (ör. bilinmeyen MaterialCode) | Sistem | H | H |  |
| …Code | nvarchar(50) | REF | İlişkiler kodla (LocationCode, MaterialCode…); aktarımda Id'ye eşlenir | ERP | H | E |  |
| … |  |  | Varlığın sözleşme alanları ve ek alanları (26. adım) | ERP | H |  |  |

### DataVersion
<sub>21. Veri modeli · Veri yönetimi</sub>

- Veri yönetimi · versiyonsuz · Faz 1
- Yükleme ile oluşan dondurulmuş veri versiyonu; tam ya da kısmi.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| LocationId | int | FK | Lokasyon | ERP | H | E |  |
| CreatedAt | datetime2 |  | Oluşma zamanı | Sistem | H | E |  |
| LoadType | nvarchar(10) |  | Tam \| Kısmi | Sistem | H | E |  |
| CreatedBy | int | FK | Kullanıcı ya da sistem kullanıcısı | Sistem | H | H |  |
| IsPinned | bit |  | Onaylı plana bağlı; silinmez | Sistem | H | H | 0 |
| IsSynthetic | bit |  | Sentetik veri (geliştirme ve demo); sentetik veri komutları yalnız bunlara dokunur (K-79) | Sistem | H | H | 0 |

### DataVersionEntity
<sub>21. Veri modeli · Veri yönetimi</sub>

- Veri yönetimi · versiyonsuz · Faz 1
- Kısmi yüklemede hangi varlıkların yüklendiği.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| DataVersionId | bigint | PK,FK | Veri versiyonu | Sistem | H | E |  |
| EntityName | nvarchar(60) | PK | Varlık | Sistem | H | E |  |
| ImportBatchId | bigint | FK | Kaynak parti | Sistem | H | H |  |

### ScenarioDefinition
<sub>21. Veri modeli · Plan</sub>

- Parametre · versiyonsuz · Faz 1
- Gece senaryosu tanımı: parametre seti + eksen ayarları.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | int | PK | Tanım kimliği | Sistem | H | E |  |
| LocationId | int | FK | Lokasyon | ERP | H | E |  |
| Name | nvarchar(100) |  | Senaryo adı | Kullanıcı | H | E |  |
| ParameterSetId | int | FK | Parametre seti | Kullanıcı | H | E |  |
| ResourceConstraint | nvarchar(15) |  | Kısıtsız \| Kısıtlı \| Kısmi | Kullanıcı | H | H | Kısıtlı |
| MaterialConstraint | bit |  | Malzeme kısıtı | Kullanıcı | H | H | 1 |
| ModelType | nvarchar(5) |  | LP \| MILP | Kullanıcı | H | H | LP |
| NightlyPriority | int |  | Gece çalışma önceliği | Kullanıcı | H | H |  |
| IsActive | bit |  | Gece çalışsın mı | Kullanıcı | H | H | 1 |

### Scenario
<sub>21. Veri modeli · Plan</sub>

- Plan · versiyonsuz · Faz 1
- Gece üretilen senaryo; bir sonraki gece akışında silinir.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| ScenarioDefinitionId | int | FK | Tanım | Sistem | H | E |  |
| DataVersionId | bigint | FK | Veri versiyonu | Sistem | H | E |  |
| PlanRunId | bigint | FK | Üreten plan çalışması | Sistem | H | H |  |
| CreatedAt | datetime2 |  | Oluşma | Sistem | H | H |  |
| Status | nvarchar(15) |  | Bitti \| Kısmen \| Hata | Sistem | H | H |  |

### Workspace
<sub>21. Veri modeli · Plan</sub>

- Plan · versiyonsuz · Faz 1
- Kullanıcının bir senaryo üzerindeki çalışması; yayınlanmazsa gece silinir.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| ScenarioId | bigint | FK | Senaryo | Sistem | H | E |  |
| OwnerUserId | int | FK | Sahibi | Sistem | H | E |  |
| Status | nvarchar(15) |  | Açık \| Kapalı \| Yayınlandı | Sistem | H | E |  |
| CurrentPlanRunId | bigint | FK | Son hesap sonucu | Sistem | H | H |  |
| LastActivityAt | datetime2 |  | Son işlem | Sistem | H | H |  |

### WorkspaceOverride
<sub>21. Veri modeli · Plan</sub>

- Plan · versiyonsuz · Faz 1
- Çalışmadaki geçici değişiklikler: parametreler ve çalışmada değiştirilebilir ana veri alanları.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| WorkspaceId | bigint | FK | Çalışma | Sistem | H | E |  |
| TableName | nvarchar(60) |  | Tablo | Kullanıcı | H | E |  |
| RecordKey | nvarchar(200) |  | Kayıt | Kullanıcı | H | E |  |
| FieldName | nvarchar(60) |  | Alan | Kullanıcı | H | E |  |
| Value | nvarchar(200) |  | Geçici değer | Kullanıcı | H | E |  |
| ChangedAt | datetime2 |  | Zaman | Sistem | H | H |  |

### PlanRun
<sub>21. Veri modeli · Plan</sub>

- Plan · versiyonsuz · Faz 1
- Bir plan hesabı (senaryo ya da çalışma); bütün plan çıktıları buna bağlı.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| ScenarioId | bigint | FK | Senaryo | Sistem | H | H |  |
| WorkspaceId | bigint | FK | Çalışma | Sistem | H | H |  |
| DataVersionId | bigint | FK | Veri versiyonu | Sistem | H | E |  |
| ParameterSetId | int | FK | Parametre seti | Sistem | H | E |  |
| EngineUsed | nvarchar(20) |  | LP \| MILP \| Kurallı \| Kısıtsız MRP | Sistem | H | H |  |
| Solver | nvarchar(20) |  | Çözücü | Sistem | H | H |  |
| StartedAt | datetime2 |  | Başlangıç | Sistem | H | H |  |
| EndedAt | datetime2 |  | Bitiş | Sistem | H | H |  |
| Status | nvarchar(15) |  | Sırada \| Çalışıyor \| Bitti \| Kısmen \| Hata | Sistem | H | H |  |

### PlanVersion
<sub>21. Veri modeli · Plan</sub>

- Plan · versiyonsuz · Faz 1
- Onaylı plan versiyonu; hep saklanır. Aynı anda tek geçerli.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| LocationId | int | FK | Lokasyon | ERP | H | E |  |
| PlanRunId | bigint | FK | Yayınlanan plan hesabı | Sistem | H | E |  |
| WorkspaceId | bigint | FK | Yayınlanan çalışma | Sistem | H | E |  |
| PublishedBy | int | FK | Yayınlayan | Sistem | H | E |  |
| PublishedAt | datetime2 |  | Yayın zamanı | Sistem | H | E |  |
| IsCurrent | bit |  | Geçerli onaylı plan | Sistem | H | E |  |

### PlannedOrder
<sub>21. Veri modeli · Plan</sub>

- Plan · versiyonsuz · Faz 1 · PlanRun'a bağlı; yayınlanmış PlanRun'un satırları değişmez (K-70)
- Planlı sipariş: üretim, satın alma ya da fason önerisi. Satın alma sürekli hesaplanır, yuvarlanmış miktar ayrıca.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| PlanRunId | bigint | FK | Plan hesabı | Motor | H | E |  |
| MaterialId | bigint | FK | Malzeme | Motor | H | E |  |
| OrderType | nvarchar(15) |  | Üretim \| Satın alma \| Fason | Motor | H | E |  |
| SupplierId | bigint | FK | Tedarikçi | Motor | H | H |  |
| ProjectId | bigint | FK | Proje (sahip) | Motor | H | H |  |
| Quantity | decimal(18,4) |  | Motorun miktarı (sürekli) | Motor | H | E |  |
| RoundedQty | decimal(18,4) |  | Yuvarlanmış miktar (son hesap) | Motor | H | H |  |
| StartDate | date |  | Başlangıç | Motor | H | H |  |
| DueDate | date |  | Bitiş | Motor | H | E |  |
| BucketStart | date |  | Dönem | Motor | H | H |  |
| UpdatedAt | datetime2 |  | Yazılma zamanı (UTC) | Sistem | H | E |  |

### SupplyRecommendation
<sub>21. Veri modeli · Plan</sub>

- Plan · versiyonsuz · Faz 1 · PlanRun'a bağlı; yayınlanmış PlanRun'un satırları değişmez (K-70)
- Mevcut arz için öneri: öne çek, ertele, iptal, azalt, hızlandır.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| PlanRunId | bigint | FK | Plan hesabı | Motor | H | E |  |
| SupplyType | nvarchar(15) |  | İş emri \| Satın alma \| Fason \| Transfer | Motor | H | E |  |
| SupplyId | bigint |  | Arz kaydı | Motor | H | E |  |
| Action | nvarchar(15) |  | Öne çek \| Ertele \| İptal \| Azalt \| Hızlandır | Motor | H | E |  |
| CurrentDate | date |  | Mevcut tarih | Motor | H | H |  |
| ProposedDate | date |  | Önerilen tarih | Motor | H | H |  |
| ProposedQty | decimal(18,4) |  | Önerilen miktar | Motor | H | H |  |
| UpdatedAt | datetime2 |  | Yazılma zamanı (UTC) | Sistem | H | E |  |

### DemandFulfillment
<sub>21. Veri modeli · Plan</sub>

- Plan · versiyonsuz · Faz 1 · PlanRun'a bağlı; yayınlanmış PlanRun'un satırları değişmez (K-70)
- Talebin planlanan karşılanması ve gecikmesi.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| PlanRunId | bigint | FK | Plan hesabı | Motor | H | E |  |
| DemandType | nvarchar(15) |  | Sipariş \| Tahmin \| Teklif \| Güvenlik stoğu | Motor | H | E |  |
| DemandId | bigint |  | Talep kaydı | Motor | H | E |  |
| DueDate | date |  | Vade | Motor | H | H |  |
| PlannedDate | date |  | Planlanan karşılama | Motor | H | H |  |
| ShortQty | decimal(18,4) |  | Karşılanamayan miktar | Motor | H | H |  |
| DelayDays | int |  | Gecikme (gün) | Motor | H | H |  |
| UpdatedAt | datetime2 |  | Yazılma zamanı (UTC) | Sistem | H | E |  |

### CapacityLoad
<sub>21. Veri modeli · Plan</sub>

- Plan · versiyonsuz · Faz 1 · PlanRun'a bağlı; yayınlanmış PlanRun'un satırları değişmez (K-70)
- Kaynak ve dönem bazında kapasite ve kapasite yükü.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| PlanRunId | bigint | FK | Plan hesabı | Motor | H | E |  |
| ResourceId | bigint | FK | Kaynak | Motor | H | E |  |
| BucketStart | date |  | Dönem | Motor | H | E |  |
| GrossCapacity | decimal(18,4) |  | Brüt kapasite | Motor | H | H |  |
| DowntimeLoss | decimal(18,4) |  | Duruş kaybı | Motor | H | H |  |
| NetCapacity | decimal(18,4) |  | Kalan kapasite (verim sonrası) | Motor | H | H |  |
| Load | decimal(18,4) |  | Kapasite yükü | Motor | H | H |  |
| Overtime | decimal(18,4) |  | Fazla mesai | Motor | H | H |  |
| UpdatedAt | datetime2 |  | Yazılma zamanı (UTC) | Sistem | H | E |  |

### Pegging
<sub>21. Veri modeli · Plan</sub>

- Plan · versiyonsuz · Faz 1 · PlanRun'a bağlı; yayınlanmış PlanRun'un satırları değişmez (K-70)
- Arz–talep bağı (full pegging).

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| PlanRunId | bigint | FK | Plan hesabı | Motor | H | E |  |
| SupplyType | nvarchar(15) |  | Stok \| İş emri \| Satın alma \| Planlı sipariş … | Motor | H | E |  |
| SupplyId | bigint |  | Arz | Motor | H | E |  |
| DemandType | nvarchar(15) |  | Sipariş \| Bağımlı talep … | Motor | H | E |  |
| DemandId | bigint |  | Talep | Motor | H | E |  |
| RootDemandId | bigint |  | Kök talep | Motor | H | H |  |
| Quantity | decimal(18,4) |  | Miktar | Motor | H | E |  |
| IsFixed | bit |  | Sabit ya da manuel bağ | Kullanıcı | H | H | 0 |
| UpdatedAt | datetime2 |  | Yazılma zamanı (UTC) | Sistem | H | E |  |

### PlanWarning
<sub>21. Veri modeli · Plan</sub>

- Plan · versiyonsuz · Faz 1 · PlanRun'a bağlı; yayınlanmış PlanRun'un satırları değişmez (K-70)
- Plan hesabının ürettiği uyarılar.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| PlanRunId | bigint | FK | Plan hesabı | Motor | H | E |  |
| WarningCode | nvarchar(30) | FK | Uyarı tanımı | Motor | H | E |  |
| ObjectType | nvarchar(20) |  | İlgili nesne tipi | Motor | H | H |  |
| ObjectId | bigint |  | İlgili nesne | Motor | H | H |  |
| Value | decimal(18,4) |  | Ölçülen değer | Motor | H | H |  |
| Message | nvarchar(400) |  | Mesaj (şablon tabanlı açıklama) | Motor | H | H |  |
| UpdatedAt | datetime2 |  | Yazılma zamanı (UTC) | Sistem | H | E |  |

### PlanMetric
<sub>21. Veri modeli · Plan</sub>

- Plan · versiyonsuz · Faz 1
- Senaryo karşılaştırma metrikleri; senaryo silinse de özet kısa süre kalır.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| PlanRunId | bigint | PK,FK | Plan hesabı | Motor | H | E |  |
| MetricCode | nvarchar(40) | PK | Metrik | Motor | H | E |  |
| Value | decimal(18,4) |  | Değer | Motor | H | E |  |

### AppUser
<sub>21. Veri modeli · Sistem</sub>

- Sistem · versiyonsuz · Faz 1
- Uygulama kullanıcısı (Faz 1'de yerel).

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | int | PK | Kullanıcı kimliği | Sistem | H | E |  |
| UserName | nvarchar(60) | UK | Kullanıcı adı | Kullanıcı | H | E |  |
| FullName | nvarchar(150) |  | Ad soyad | Kullanıcı | H | H |  |
| Role | nvarchar(15) |  | Sistem sahibi \| Admin \| Key user \| End user | Kullanıcı | H | E |  |
| PasswordHash | nvarchar(200) |  | Özetlenmiş şifre; Argon2id PHC metni, tuz içinde (K-98); boşsa hesap arayüzden giremez | Sistem | H | H |  |
| MustChangePassword | bit |  | Şifre değiştirilmeli; ilk giriş ya da sıfırlama sonrası | Sistem | H | H | 1 |
| PasswordChangeReason | nvarchar(15) |  | İlk giriş \| Sıfırlama \| Süre doldu | Sistem | H | H |  |
| PasswordChangedAt | datetime2 |  | Şifrenin son değiştiği zaman (UTC) | Sistem | H | H |  |
| PasswordExpiresAt | datetime2 |  | Şifrenin süresinin dolduğu zaman (UTC); değişiklik anındaki politikayla hesaplanır | Sistem | H | H |  |
| FailedAttempts | int |  | Art arda hatalı giriş | Sistem | H | H | 0 |
| LockedUntil | datetime2 |  | Kilit bitişi (UTC); geçmişse ya da boşsa kilit yok | Sistem | H | H |  |
| LastLoginAt | datetime2 |  | Son başarılı giriş (UTC) | Sistem | H | H |  |
| IsActive | bit |  | Aktif | Kullanıcı | H | H | 1 |

- Giriş ve şifre kuralları fonksiyon 89'da ve K-98'de. Şifre ekranda, logda ve denetim izinde düz metin olarak hiç yer almaz.
- Kilit süre dolunca kendiliğinden açılır; admin elle açınca (2.3) `LockedUntil` boşalır ve sayaç sıfırlanır.

### UserSession
<sub>21. Veri modeli · Sistem</sub>

- Sistem · versiyonsuz · Faz 1
- Sunucu tarafı oturum (K-97). Tarayıcıdaki çerez rastgele bir anahtar taşır; tabloda yalnız anahtarın SHA-256 özeti durur.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Oturum kimliği | Sistem | H | E |  |
| TokenHash | varbinary(32) | UK | Çerezdeki anahtarın SHA-256 özeti | Sistem | H | E |  |
| UserId | int | FK | Kullanıcı | Sistem | H | E |  |
| CreatedAt | datetime2 |  | Açılış (UTC) | Sistem | H | E |  |
| LastActivityAt | datetime2 |  | Son kullanıcı etkinliği (UTC); hareketsizlik buna göre ölçülür | Sistem | H | E |  |
| EndedAt | datetime2 |  | Kapanış (UTC); boşsa açık | Sistem | H | H |  |
| EndReason | nvarchar(15) |  | Çıkış \| Zaman aşımı \| Şifre değişti \| Kapatıldı | Sistem | H | H |  |
| ClientAddress | nvarchar(45) |  | İstemci adresi | Sistem | H | H |  |
| UserAgent | nvarchar(200) |  | Tarayıcı | Sistem | H | H |  |

- Aynı kullanıcı birden çok tarayıcıda oturum açabilir. "Kapatıldı": kullanıcı pasif edilince ya da admin kapatınca (2.3).

### PasswordHistory
<sub>21. Veri modeli · Sistem</sub>

- Sistem · versiyonsuz · Faz 1
- Kullanıcının önceki şifre özetleri (K-98): yeni şifre son `PasswordHistoryCount` şifreden farklı olmalı.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| UserId | int | FK | Kullanıcı | Sistem | H | E |  |
| PasswordHash | nvarchar(200) |  | Şifre özeti | Sistem | H | E |  |
| CreatedAt | datetime2 |  | Şifrenin belirlendiği zaman (UTC) | Sistem | H | E |  |

- Her değişiklikte eklenir; en yeni `PasswordHistoryCount` kaydın dışındakiler silinir.

### LoginThrottle
<sub>21. Veri modeli · Sistem</sub>

- Sistem · versiyonsuz · Faz 1
- Bilinmeyen, şifresiz ya da pasif hesap adına yapılan hatalı girişlerin sayacı (K-98). Gerçek hesaptaki sayaçla aynı davranır; giriş cevabından hesabın var olup olmadığı anlaşılmaz.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| UserName | nvarchar(60) | PK | Yazılan kullanıcı adı | Sistem | H | E |  |
| FailedAttempts | int |  | Art arda hatalı giriş | Sistem | H | E | 0 |
| LockedUntil | datetime2 |  | Kilit bitişi (UTC) | Sistem | H | H |  |
| UpdatedAt | datetime2 |  | Son deneme (UTC) | Sistem | H | E |  |

### Job
<sub>21. Veri modeli · Sistem</sub>

- Sistem · versiyonsuz · Faz 1
- İş kuyruğu (SQL Server tablosu): gece senaryoları, çalışma hesapları, yüklemeler.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| JobType | nvarchar(20) |  | Gece senaryosu \| Çalışma \| Yükleme \| Termin sorgusu \| Dışa aktarım … | Sistem | H | E |  |
| Channel | nvarchar(15) |  | Gece \| Etkileşim \| Dışa aktarım | Sistem | H | E |  |
| Priority | int |  | Öncelik | Sistem | H | H |  |
| Status | nvarchar(15) |  | Sırada \| Çalışıyor \| Bitti \| Hata \| İptal | Sistem | H | E |  |
| RequestedBy | int | FK | Başlatan | Sistem | H | H |  |
| Payload | nvarchar(max) |  | İş parametreleri (JSON) | Sistem | H | H |  |
| Progress | nvarchar(100) |  | İlerleme | Sistem | H | H |  |
| HeartbeatAt | datetime2 |  | Son yaşam sinyali | Sistem | H | H |  |
| Attempt | int |  | Deneme sayısı | Sistem | H | H | 0 |
| ErrorText | nvarchar(max) |  | Hata | Sistem | H | H |  |
| CreatedAt | datetime2 |  | İstek zamanı (UTC); sıra buna göre görünür | Sistem | H | E |  |
| StartedAt | datetime2 |  | Çalışmaya başlama (UTC) | Sistem | H | H |  |
| EndedAt | datetime2 |  | Bitiş, hata ya da iptal (UTC) | Sistem | H | H |  |
| UpdatedAt | datetime2 |  | Son değişiklik (UTC); API bildirim için izler (K-69) | Sistem | H | E |  |

- Durum değerleri tabloda yazıldığı gibi saklanır; 'takıldı' saklanmaz, kalp atışından hesaplanır (K-67). İş alma sırası: Priority büyükten küçüğe, sonra Id (K-68).

### SolverLog
<sub>21. Veri modeli · Sistem</sub>

- Sistem · versiyonsuz · Faz 1
- Çözüm logu; ilk günden tutulur.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| PlanRunId | bigint | FK | Plan hesabı | Sistem | H | E |  |
| ModelSize | nvarchar(200) |  | Değişken, kısıt, malzeme, kaynak, dönem sayıları | Sistem | H | H |  |
| SolveSeconds | decimal(9,2) |  | Süre | Sistem | H | H |  |
| Gap | decimal(9,6) |  | Optimallik farkı | Sistem | H | H |  |
| Iterations | int |  | LNS turu | Sistem | H | H |  |

### AuditLog
<sub>21. Veri modeli · Sistem</sub>

- Sistem · versiyonsuz · Faz 1
- Kim, ne zaman, neyi değiştirdi; giriş kayıtları; sistem sahibi işlemleri silinemez.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| UserId | int | FK | Kullanıcı | Sistem | H | H |  |
| At | datetime2 |  | Zaman | Sistem | H | E |  |
| Action | nvarchar(40) |  | İşlem | Sistem | H | E |  |
| ObjectType | nvarchar(40) |  | Nesne | Sistem | H | H |  |
| ObjectKey | nvarchar(200) |  | Kayıt | Sistem | H | H |  |
| OldValue | nvarchar(max) |  | Önceki | Sistem | H | H |  |
| NewValue | nvarchar(max) |  | Yeni | Sistem | H | H |  |

### SystemSetting
<sub>21. Veri modeli · Sistem</sub>

- Sistem · versiyonsuz · Faz 1
- Sistem sahibinin ayarları: çözücü, süre bütçeleri, işçi sayısı, eş zamanlı çalışma sınırı, saklama süreleri.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| SettingKey | nvarchar(60) | PK | Ayar | Sistem | H | E |  |
| Value | nvarchar(200) |  | Değer | Sistem | H | E |  |

- İş kuyruğu ayarları (K-68); satır yoksa varsayılan geçerlidir:
  - `JobLimitInteractive`: etkileşim kanalında aynı anda çalışan iş (3)
  - `JobLimitNight`: gece kanalında aynı anda çalışan iş (2)
  - `JobLimitExport`: dışa aktarım kanalında aynı anda çalışan iş (2; K-93)
  - `JobHeartbeatTimeoutSeconds`: kalp atışı bu kadar saniye gelmezse iş takılmış sayılır (120)
  - `JobMaxAttempts`: takılan iş en fazla bu kadar denenir, sonra Hata (2)
- Motor ayarları (K-71; fonksiyon 34):
  - `EngineTimeBudgetInteractiveSeconds`: etkileşim kanalında hesap süre bütçesi (180)
  - `EngineTimeBudgetNightSeconds`: gece kanalında hesap süre bütçesi (1800; senaryo bazlı bütçe parametrelerde gelecek)
  - `EngineKillGraceSeconds`: bütçe aşıldıktan sonra motor servisinin işi sonlandırmadan önce beklediği pay (60)
  - `EngineHeartbeatSeconds`: motor servisinin çalışan iş için kalp atışı yazma aralığı (15)
- Çözücü ayarları (K-76; fonksiyon 32):
  - `SolverThreads`: bir plan hesabında çözücünün kullanacağı iş parçacığı sayısı (2)
- Liste ayarları (K-87; docs/08 "Liste sorgusu"):
  - `ListChunkSize`: tablonun bir istekte okuduğu en çok satır (parça büyüklüğü) (100; en çok 500, büyüğü 500 sayılır)
  - `ListMaxGroups`: gruplamada en çok yaprak grup (1000; K-90)
- Dışa aktarım ayarları (K-91):
  - `ExportSyncMaxRows`: bu kadar satıra kadar dosya anlık iner, üstü arka planda hazırlanır (10000)
  - `ExportMaxRows`: bir aktarımda en çok satır (500000)
  - `ExportFileHours`: arka planda hazırlanan dosyanın indirilebileceği süre, saat (24)
- Giriş, şifre ve oturum ayarları (K-97, K-98; fonksiyon 89). Şifre kuralı değişikliği bir sonraki şifre değişiminde geçerli olur:
  - `PasswordMinLength`: şifrede en az karakter (10)
  - `PasswordRequireLetterAndDigit`: şifrede harf ve rakam zorunlu, 1 ya da 0 (1)
  - `PasswordHistoryCount`: yeni şifre bu kadar önceki şifreden farklı olmalı (5)
  - `PasswordMaxAgeDays`: şifrenin geçerlilik süresi, gün (90)
  - `SessionIdleMinutes`: bu kadar dakika kullanıcı etkinliği olmazsa oturum kapanır (30)
  - `SessionWarningMinutes`: kapanmadan bu kadar dakika önce uyarı penceresi açılır (5)
  - `LoginMaxFailedAttempts`: art arda bu kadar hatalı girişte hesap kilitlenir (5)
  - `LoginLockMinutes`: kilit süresi, dakika (15)

### TableView
<sub>21. Veri modeli · Sistem</sub>

- Sistem · versiyonsuz · Faz 1
- Kayıtlı tablo görünümü (K-89): kolon seti ve sırası, genişlikler, sabitleme, sıralama, filtreler, gruplama.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | int | PK | Görünüm kimliği | Sistem | H | E |  |
| ListName | nvarchar(60) | UK | Liste adı (ör. materials) | Sistem | H | E |  |
| OwnerUserId | int | FK,UK | Sahibi | Kullanıcı | H | E |  |
| Name | nvarchar(100) | UK | Görünüm adı | Kullanıcı | H | E |  |
| IsShared | bit |  | Paylaşılan | Kullanıcı | H | E | 0 |
| Definition | nvarchar(max) |  | Görünüm içeriği; JSON, sürümlü (docs/08) | Kullanıcı | H | E |  |
| CreatedAt | datetime2 |  | Oluşturulma zamanı | Sistem | H | E |  |
| UpdatedAt | datetime2 |  | Son değişiklik zamanı | Sistem | H | E |  |

- Ad, aynı kullanıcının aynı listesinde tekildir. Paylaşılan görünümü şimdilik herkes görür; yalnız sahibi değiştirir ya da siler (rol kuralı 2.2).

### TableViewDefault
<sub>21. Veri modeli · Sistem</sub>

- Sistem · versiyonsuz · Faz 1
- Kullanıcının bir liste için varsayılan görünümü (K-89). Satır yoksa liste tanımındaki "Standart" görünüm açılır.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| UserId | int | PK,FK | Kullanıcı | Kullanıcı | H | E |  |
| ListName | nvarchar(60) | PK | Liste adı | Sistem | H | E |  |
| ViewId | int | FK | Varsayılan görünüm | Kullanıcı | H | E |  |

### License
<sub>21. Veri modeli · Sistem</sub>

- Sistem · versiyonsuz · Faz 1
- Çevrimdışı imzalı lisans.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | int | PK | Kimlik | Sistem | H | E |  |
| LicenseFile | varbinary(max) |  | İmzalı lisans dosyası | Sistem | H | E |  |
| ValidUntil | date |  | Bitiş | Sistem | H | E |  |
| InstallationId | nvarchar(100) |  | Kurulum kimliği | Sistem | H | E |  |
