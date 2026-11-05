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
  - K-60  Teklif ayrı tablo değil: SalesOrderLine.IsQuote (ham Type'tan veri kuralıyla dolar; K-127); plana dahil etme senaryo parametresi bu bayrağa bağlıdır; kazanma olasılığı tutulmaz.
  - K-61  Rota satırı operasyon–kaynak; sıra önce OperationNo, sonra SequenceNo. Anahtar K-116'da: LocationCode + RouteCode + OperationNo + SequenceNo.
- **Açık konular**
  - A-17  Kapandı (3.1b, K-111…K-128): alanlar tablo tablo birlikte gözden geçirildi.
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
- **Etiket ve açıklama:** ETİKET kolonu doluysa ekrandaki alan adı odur; açıklama AÇIKLAMA'da ve veritabanı yorumunda kalır. Boşsa etiket AÇIKLAMA'dan kuralla türer (K-88).

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
  - AdditionalText1–7 ve AdditionalNumber1–3. Location, Resource, ResourceGroup, Material, Supplier, Customer, Project.
  - Yapı ve işlem verisi · 5 alan
  - AdditionalText1–3 ve AdditionalNumber1–2. ProductionVersion, BOM, Routing, MaterialSupplier, SalesOrderLine, Forecast, Stock, iş emri tabloları, PurchaseOrderLine, TransferOrder, ProductionConfirmation.
  - Kullanım
  - Etiket ve görünürlük FieldDefinition'da (ör. AdditionalText3 = 'Malzeme sınıfı'): Label'ı olmayan ek alan listede görünmez (K-88). Ekranda sıralanır ve filtrelenir (U-6–U-8); veri kurallarında koşul olarak kullanılabilir.

### Alanların ana kaynağı
<sub>21. Veri modeli · Alan kaynakları</sub>

| KAYNAK | ANLAMI | ÖRNEK ALAN |
|---|---|---|
| ERP | Entegrasyondan gelir (API, Excel, SQL arayüz tabloları). | Material.Code, SalesOrderLine.OpenQuantity |
| ERP, yoksa kural | ERP'de varsa oradan; yoksa veri kuralıyla doldurulur. | Material.MaterialLevel, Resource.IsCritical |
| Kural ya da elle | ERP'de genelde yok; veri kuralıyla ya da ana veri ekranında elle. | Resource.DailyCapacity, Material.IsCustomTracked |
| Smartchain (parametre) | Smartchain'de tanımlanan planlama parametresi; parametre setine bağlı. | ResourceEfficiency.EfficiencyPct, AllocationRule.SharePct |
| Kullanıcı | Kullanıcının ekrandan girdiği tanım. | DataRule, ScenarioDefinition |
| Sistem | Sistemin ürettiği ya da System owner'ın yönettiği değer. | Id alanları, PlanRun, Job |
| Ön hesap | Ön hesapta türetilen değer. | WorkOrderComponent.RemainingQuantity, ResourceDowntime.DurationDays |
| Motor | Planlama motorunun çıktısı. | PlannedOrder, CapacityLoad, Pegging |

### Alan grupları ve veri akışı
<sub>21. Veri modeli · Genel görünüm</sub>

- **Veri yönetimi  9 tablo:** ImportBatch · Staging · DataRule · FieldDefinition · ManualValue · DataVersion
- **Kaynak  11 tablo:** Resource · ResourceGroupAssignment · ShiftPlan · ResourceDowntime
- **Malzeme  9 tablo:** Material · MaterialSupplier · BOM · Routing · MaterialReference · Project
- **Parametre  6 tablo:** ParameterSet · PlanningSetting · PriorityRule · AllocationRule
- yükleme
- **Talep  3 tablo:** Customer · SalesOrderLine · Forecast
- **Arz ve stok  8 tablo:** Stock · BorrowPayback · WorkOrder · PurchaseOrderLine · TransferOrder
- **Plan  13 tablo:** ScenarioDefinition · Scenario · Workspace · PlanRun · PlanVersion · PlannedOrder · CapacityLoad · Pegging · PlanWarning
- versiyon
- **Sistem  8 tablo:** AppUser · Job · SolverLog · SystemEvent · ServiceStatus · AuditLog · SystemSetting · License
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
- **ResourceGroup:** Kaynak ve yetkinlik grubu; uygun kaynaklar listesi
- **ResourceGroupAssignment:** Kaynağın gruba ataması; yetkinlik matrisi
- **ResourceCapacityProfile:** Günlük kapasitenin dönemsel değişikliği (ör
- **ResourceDowntime:** Bakım ve arıza takvimi
- **ResourceEfficiency:** Kaynak ve dönem bazında verim (kapasite katsayısı)
- **ResourcePeriodLimit:** Dönem bazlı üst limit
- **Shift:** Vardiya tanımı
- **ShiftPlan:** Dönem bazında grup–vardiya–kişi sayısı
- **EmployeeAbsence:** Kişi bazında izin ve rapor
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
- **MaterialReference:** Benzetilen ürün: kendi ağacı ya da rotası olmayan ürün, başka bir ürünün verisiyle planlanır
- Proje grubu (grup içi paylaşım için)
- Proje

#### SISTEM

- **AppUser:** Uygulama kullanıcısı (Faz 1'de yerel)
- **Job:** İş kuyruğu (SQL Server tablosu): gece senaryoları, çalışma hesapları, yüklemeler
- **SolverLog:** Çözüm logu
- **SystemEvent:** Sistem hataları ve sistem aksiyonu
- **ServiceStatus:** Motor servisinin kalp atışı
- **AuditLog:** Kim, ne zaman, neyi değiştirdi
- **SystemSetting:** System owner'ın ayarları: çözücü, süre bütçeleri, işçi sayısı, eş zamanlı çalışma sınırı, saklama süreleri
- **License:** Çevrimdışı imzalı lisans

#### BOM

- Routing
- ProjectGroup
- Project

### Tablo listesi
<sub>21. Veri modeli · Tablo listesi · 4/6</sub>

#### ARZ VE STOK

- **Stock:** Stok
- **BorrowPayback:** Projeler arası ödünç ve geri ödeme
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

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|---|
| Id | int | PK | Lokasyon kimliği |  | Sistem | H | E |  |
| Code | nvarchar(30) | UK | Lokasyon kodu |  | ERP | H | E |  |
| Name | nvarchar(100) |  | Lokasyon adı |  | ERP | H | H |  |
| Type | nvarchar(15) |  | Tesis \| Depo \| Fason deposu | Lokasyon tipi | ERP, yoksa kural | H | E | Tesis |
| IsFactory | bit |  | Tesis mi | Tesis | Kural, ERP ya da Excel | H | E | 0 |
| IsDepot | bit |  | Depo mu | Depo | Kural, ERP ya da Excel | H | E | 0 |
| IsSubcontractor | bit |  | Fason deposu mu | Fason deposu | Kural, ERP ya da Excel | H | E | 0 |
| IsActive | bit |  | Aktif mi | Aktif | Kural, ERP ya da Excel | H | E | 1 |
| Country | nvarchar(100) |  | Ülke |  | ERP | H | H |  |
| CountryCode | nvarchar(10) |  | Ülke kodu |  | ERP | H | H |  |
| Region | nvarchar(100) |  | Bölge |  | ERP | H | H |  |
| RegionCode | nvarchar(20) |  | Bölge kodu |  | ERP | H | H |  |
| City | nvarchar(100) |  | Şehir |  | ERP | H | H |  |
| CityCode | nvarchar(20) |  | Şehir kodu |  | ERP | H | H |  |
| AdditionalText1–7 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da |  | ERP | H | H |  |
| AdditionalNumber1–3 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da |  | ERP | H | H |  |
| IsSynthetic | bit |  | Sentetik veri (geliştirme ve demo); sentetik veri komutları yalnız bunlara dokunur (K-79) |  | Sistem | H | H | 0 |

### UnitOfMeasure
<sub>21. Veri modeli · Ortak</sub>

- Ana veri · versiyonsuz · Faz 1
- Ölçü birimi.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|---|
| Code | nvarchar(10) | PK | Birim kodu (AD, KG, SAAT…) | Birim kodu | Yüklemede diğer tablolardan | H | E |  |
| Name | nvarchar(50) |  | Birim adı |  | Birim dönüşümündeki ad, elle ya da kural | H | H |  |
| Decimals | tinyint |  | Miktar ondalığı; ERP'den gelmez, Smartchain'de tutulur (K-88) |  | Elle ya da kural | H | H |  |

- **Oluşma (K-112):** Entegrasyon tablosu ve şablonu yoktur. Yüklemede (5.2) diğer tablolarda geçen birim kodlarından otomatik oluşur; ad boşsa UomConversion'daki FromUomName ya da ToUomName'den doldurulur. Ad ve ondalık ana veri ekranında elle ya da veri kuralıyla yönetilir (6.1).
- **Decimals:** bu birimdeki miktarlar ekranda bu kadar ondalıkla gösterilir (K-88). ERP aktarımı ezmez. Varsayılan değeri yoktur, kurulumda tanımlanır.

### UomConversion
<sub>21. Veri modeli · Ortak</sub>

- Ana veri · versiyonlu · Faz 1
- Malzeme bazında birim dönüşümü.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| MaterialId | bigint | FK,UK | Malzeme (boşsa genel dönüşüm) | Malzeme | ERP | H | H |  |
| FromUom | nvarchar(10) | FK,UK | Kaynak birim |  | ERP | H | E |  |
| FromUomName | nvarchar(50) |  | Kaynak birim adı |  | ERP | H | H |  |
| ToUom | nvarchar(10) | FK,UK | Hedef birim |  | ERP | H | E |  |
| ToUomName | nvarchar(50) |  | Hedef birim adı |  | ERP | H | H |  |
| Factor | decimal(18,6) |  | 1 kaynak birim = çarpan × hedef birim | Çarpan | ERP | H | E |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

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

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|---|
| CalendarId | int | PK,FK | Takvim |  | Kural ya da elle | H | E |  |
| Date | date | PK | Gün |  | Kural ya da elle | H | E |  |
| IsWorkingDay | bit |  | Çalışma günü mü |  | Kural ya da elle | H | E | 1 |
| WorkingFraction | decimal(5,4) |  | Günün çalışılan oranı (yarım gün 0,5) | Çalışma oranı | Kural ya da elle | H | H | 1 |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

### Resource
<sub>21. Veri modeli · Kaynak · 1/2</sub>

- Ana veri · versiyonlu · Faz 1
- Kaynak: makine, işçi, fason, diğer. Kapasite kaynağın kendi biriminde günlük kapasite olarak tutulur.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| LocationId | int | FK,UK | Lokasyon |  | ERP | H | E |  |
| Code | nvarchar(50) | UK | Kaynak kodu |  | ERP | H | E |  |
| Name | nvarchar(150) |  | Kaynak adı |  | ERP | H | H |  |
| ResourceType | nvarchar(50) |  | ERP'den gelen ham değer; tip bayraklarla ifade edilir | Kaynak tipi | ERP | H | H |  |
| IsEmployee | bit |  | Kaynak işçi mi | İşçi | ERP, yoksa kural | H | H |  |
| IsMachine | bit |  | Kaynak makine mi | Makine | ERP, yoksa kural | H | H |  |
| IsFurnace | bit |  | Kaynak fırın mı; Faz 1 planlamada kullanılmaz | Fırın | ERP, yoksa kural | H | H |  |
| IsMold | bit |  | Kaynak kalıp mı; Faz 1 planlamada kullanılmaz | Kalıp | ERP, yoksa kural | H | H |  |
| IsOther | bit |  | Diğer kaynak mı | Diğer | ERP, yoksa kural | H | H |  |
| IsSubcontractor | bit |  | Kaynak fason mu | Fason | ERP, yoksa kural | H | H |  |
| IsActive | bit |  | Aktif mi | Aktif | ERP, yoksa kural | H | H |  |
| IsCritical | bit |  | 1: planda kısıt, 0: sonsuz kapasite (sadece raporlanır) | Kritik kaynak | ERP, yoksa kural | H | H |  |
| CapacityUnit | nvarchar(10) | FK | Kapasite birimi (Saat, Adet, Ton…); rotadaki tüketim aynı birimde kabul edilir | Kapasite birimi | ERP, yoksa kural | H | E |  |
| DailyCapacity | decimal(18,4) |  | Bir adet kaynağın bir çalışma günündeki kapasitesi | Günlük kapasite | Kural ya da elle | H | H |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

### Resource
<sub>21. Veri modeli · Kaynak · 2/2</sub>

- Ana veri · versiyonlu · Faz 1
- Kaynak: makine, işçi, fason, diğer. Kapasite kaynağın kendi biriminde günlük kapasite olarak tutulur.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|---|
| Quantity | int |  | Paralel kaynak adedi |  | Kural ya da elle | H | E | 1 |
| CalendarId | int | FK | Çalışma takvimi (Smartchain ekranında atanır) | Çalışma takvimi | Kural ya da elle | H | H |  |
| CapacitySource | nvarchar(10) |  | İşçi gruplarında: Vardiyadan \| Doğrudan | Kapasite kaynağı | Kural ya da elle | H | H | Doğrudan |
| SubconPlanningType | nvarchar(15) |  | Fasonda: İş yeri \| Tedarik süresi | Fason planlama tipi | Kural ya da elle | H | H |  |
| SubcontractorId | bigint | FK | Fasonda fasoncu | Fasoncu | ERP | H | H |  |
| SubconFixedLeadTimeDays | decimal(9,2) |  | Fasonda sabit süre (taşıma ve kuyruk) | Fason sabit süresi (gün) | Kural ya da elle | H | H |  |
| SubconVariableDaysPerUnit | decimal(18,6) |  | Fasonda birim başına gün (fasoncunun hızı) | Fason birim süresi (gün) | Kural ya da elle | H | H |  |
| ProductionLocation | nvarchar(50) |  | Lokasyonun alt tanımı (hol, hat) | Üretim yeri | ERP | H | H |  |
| RemainingOverTimeYear | decimal(9,2) |  | Yıllık kalan fazla mesai (saat) |  | ERP | H | H |  |
| RemainingOverTimeMonth | decimal(9,2) |  | Aylık kalan fazla mesai (saat) |  | ERP | H | H |  |
| AdditionalText1–7 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da |  | ERP | H | H |  |
| AdditionalNumber1–3 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da |  | ERP | H | H |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

- **Entegrasyon (K-117):** Kimlik ve ilişkiler entegrasyonla gelir. Kapasite birimi ERP'den gelir, yoksa veri kuralıyla doldurulur; ikisinden de gelmezse doğrulamada hata. Öteki kapasite tanımları (günlük kapasite, paralel adet, kapasite kaynağı), fason parametreleri ve takvim entegre edilmez; Smartchain ekranlarında tanımlanır (6.1, 7.3). Tanımlanana kadar boş kalabilir; aktif ve kritik olup kapasitesi tanımsız kaynak veri kalitesinde uyarı verir (6.5).
- **Tip:** `ResourceType` ERP'den ham değerdir; tip bayraklarla ifade edilir. `IsFurnace` ve `IsMold` yalnız sözleşmededir, Faz 1 planlamada kullanılmaz.
- **İşçi:** İşçiler kaynaktır (`IsEmployee`), yetkinlikler kaynak grubudur (`IsCompetenceGroup`), işçi yetkinlikleri `ResourceGroupAssignment`'tadır.

### ResourceGroup
<sub>21. Veri modeli · Kaynak</sub>

- Ana veri · versiyonlu · Faz 1
- Kaynak ve yetkinlik grubu. Kapasite havuzu değil, uygun kaynaklar listesidir; kapasite yalnız kaynakta tutulur.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| LocationId | int | FK,UK | Lokasyon | ERP | H | E |  |
| Code | nvarchar(50) | UK | Grup kodu | ERP | H | E |  |
| Name | nvarchar(150) |  | Grup adı | ERP | H | H |  |
| Type | nvarchar(50) |  | Grup tipi; ERP'den gelen ham değer | ERP | H | H |  |
| IsResourceGroup | bit |  | Kaynak grubu | ERP, yoksa kural | H | H |  |
| IsCompetenceGroup | bit |  | Yetkinlik grubu | ERP, yoksa kural | H | H |  |
| IsActive | bit |  | Aktif | ERP, yoksa kural | H | H |  |
| AdditionalText1–7 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da | ERP | H | H |  |
| AdditionalNumber1–3 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da | ERP | H | H |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |

### ResourceCapacityProfile
<sub>21. Veri modeli · Kaynak</sub>

- Ana veri · versiyonlu · Faz 1
- Günlük kapasitenin dönemsel değişikliği (ör. ikinci vardiya açıldı). Birim kaynağın CapacityUnit'i; ekranda gösterilir, ayrı saklanmaz. Smartchain'de ekrandan girilir; entegrasyondan gelmez (K-65).

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| ResourceId | bigint | FK | Kaynak |  | Kural ya da elle | H | E |  |
| ValidFrom | date |  | Başlangıç |  | Kural ya da elle | H | E |  |
| ValidTo | date |  | Bitiş |  | Kural ya da elle | H | E |  |
| DailyCapacity | decimal(18,4) |  | Bu aralıktaki günlük kapasite | Günlük kapasite | Kural ya da elle | E | E |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

### ResourceDowntime
<sub>21. Veri modeli · Kaynak</sub>

- Ana veri · versiyonlu · Faz 1
- Bakım ve arıza takvimi; kapasiteden düşülür. Çalışmada geçici değiştirilebilir. Smartchain'de ekrandan girilir; entegrasyondan gelmez (K-65).

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| ResourceId | bigint | FK | Kaynak |  | Kural ya da elle | H | E |  |
| DowntimeType | nvarchar(10) |  | Bakım \| Arıza | Duruş tipi | Kural ya da elle | H | E |  |
| StartAt | datetime2 |  | Başlangıç |  | Kural ya da elle | E | E |  |
| EndAt | datetime2 |  | Bitiş |  | Kural ya da elle | E | E |  |
| AffectedQuantity | int |  | Etkilenen kaynak adedi |  | Kural ya da elle | E | E | 1 |
| DurationDays | decimal(9,4) |  | Süre, gün olarak (yarım gün 0,5) | Süre (gün) | Ön hesap | H | H |  |
| Note | nvarchar(400) |  | Açıklama |  | Kullanıcı | H | H |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

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

### ResourceGroupAssignment
<sub>21. Veri modeli · Kaynak</sub>

- Ana veri · versiyonlu · Faz 1
- Kaynağın gruba ataması; bir kaynak birden fazla gruba atanabilir, yetkinlik matrisi bu tablodur. Geçerlilik tarihleri yalnız girdi.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| LocationId | int | FK,UK | Lokasyon |  | ERP | H | E |  |
| ResourceGroupId | bigint | FK,UK | Kaynak ya da yetkinlik grubu | Grup | ERP | H | E |  |
| ResourceId | bigint | FK,UK | Kaynak |  | ERP | H | E |  |
| ValidFrom | date |  | Geçerlilik başlangıcı |  | ERP | H | H |  |
| ValidTo | date |  | Geçerlilik bitişi |  | ERP | H | H |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

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

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| ResourceGroupId | bigint | FK | Kaynak ya da yetkinlik grubu |  | Kural ya da elle | H | H |  |
| ShiftId | bigint | FK | Vardiya |  | Kural ya da elle | H | E |  |
| ValidFrom | date |  | Başlangıç |  | Kural ya da elle | H | E |  |
| ValidTo | date |  | Bitiş |  | Kural ya da elle | H | E |  |
| Headcount | int |  | Kişi sayısı |  | Kural ya da elle | E | E |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

### EmployeeAbsence
<sub>21. Veri modeli · Kaynak</sub>

- İşlem verisi · versiyonlu · Faz 1
- Kişi bazında izin ve rapor.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| LocationId | int | FK,UK | Lokasyon |  | ERP | H | E |  |
| ResourceId | bigint | FK,UK | Kaynak |  | ERP | H | E |  |
| AbsenceType | nvarchar(50) | UK | ERP'den gelen ham değer (izin, rapor…) | Devamsızlık tipi | ERP | H | E |  |
| StartDate | date | UK | Başlangıç |  | ERP | H | E |  |
| EndDate | date |  | Bitiş günü dahil | Bitiş | ERP | H | E |  |
| HoursPerDay | decimal(9,2) |  | Günlük devamsız saat; kısmi devamsızlık için, boşsa tam gün | Günlük saat | ERP | H | H |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

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
| LocationId | int | FK,UK | Lokasyon | ERP | H | E |  |
| Code | nvarchar(50) | UK | Malzeme kodu | ERP | H | E |  |
| Name | nvarchar(200) |  | Malzeme adı | ERP | H | H |  |
| BaseUom | nvarchar(10) | FK | Temel birim | ERP | H | E |  |
| MaterialGroup | nvarchar(50) |  | Malzeme grubu | ERP | H | H |  |
| MaterialLevel | nvarchar(15) |  | Malzeme seviyesi: Hammadde \| Yarı mamul \| Nihai ürün | ERP, yoksa kural | H | H |  |
| MaterialType | nvarchar(50) |  | Malzeme tipi | ERP | H | H |  |
| Brand | nvarchar(50) |  | Marka | ERP | H | H |  |
| PlannerCode | nvarchar(50) |  | Planlamacı | ERP | H | H |  |
| MRPGroup | nvarchar(50) |  | MRP grubu; planlama parametreleri aynı olan malzemeleri gruplar | ERP | H | H |  |
| IsActive | bit |  | Aktif | ERP, yoksa kural | H | H |  |
| IsCritical | bit |  | Kritik malzeme; malzeme kısıtı yalnız kritik malzemelere uygulanır, kritik olmayanın her zaman temin edilebildiği varsayılır | ERP, yoksa kural | H | H |  |
| IsPurchasable | bit |  | Satın alınabilir | ERP, yoksa kural | H | H | 0 |
| IsProducible | bit |  | Üretilebilir | ERP, yoksa kural | H | H | 0 |
| IsSellable | bit |  | Satılabilir | ERP, yoksa kural | H | H | 0 |
| IsSubcontractable | bit |  | Fasona verilebilir | ERP, yoksa kural | H | H |  |
| DefaultSupplyType | nvarchar(10) |  | Tedarik türü: Üretim \| Satın alma \| Fason | ERP, yoksa kural | H | H |  |
| IsCustomerSupplied | bit |  | Müşteri temin malzemesi | Kural ya da elle | H | H |  |

### Material
<sub>21. Veri modeli · Malzeme · 2/2</sub>

- Ana veri · versiyonlu · Faz 1
- Malzeme ve planlama ana verisi.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|---|
| IsCustomTracked | bit |  | Malzeme ortak havuzdan değil, belli bir talebe (proje, müşteri ya da sipariş) ayrılmış olarak takip edilir; hangi talebe ayrıldığı talep kaydından gelir | Özel takip | Kural ya da elle | H | H | 0 |
| IsPhantom | bit |  | Hayalet yarı mamul |  | ERP | H | H | 0 |
| GoodsReceiptDays | decimal(9,2) |  | Mal kabul süresi (iş günü) |  | ERP, yoksa kural | H | H | 0 |
| SafetyStock | decimal(18,4) |  | Güvenlik stoğu |  | ERP | H | H | 0 |
| StockCoverageDays | decimal(9,2) |  | Gün cinsinden güvenlik stoğu | Stok gün kapsamı | ERP | H | H |  |
| MaxStock | decimal(18,4) |  | Maksimum stok |  | ERP | H | H |  |
| LotSizePolicy | nvarchar(15) |  | Lot politikası (üretimde): Lot-for-lot \| Sabit \| Dönemsel | Lot politikası | ERP, yoksa kural | H | H | Lot-for-lot |
| MinLot | decimal(18,4) |  | Üretimde minimum | Minimum lot | ERP | H | H |  |
| MaxLot | decimal(18,4) |  | Üretimde maksimum | Maksimum lot | ERP | H | H |  |
| LotMultiple | decimal(18,4) |  | Üretimde kat | Lot katı | ERP | H | H |  |
| QtyPerBox | decimal(18,4) |  | Temel birimde kutu içi miktar | Kutu içi miktar | ERP | H | H |  |
| QtyPerPallet | decimal(18,4) |  | Temel birimde palet içi miktar | Palet içi miktar | ERP | H | H |  |
| ScrapRatio | decimal(6,4) |  | Oran olarak fire (0,05 = %5) | Fire oranı | ERP | H | H | 0 |
| ShelfLifeDays | int |  | Raf ömrü; şimdilik yalnız uyarı için kullanılır | Raf ömrü (gün) | ERP | H | H |  |
| AdditionalText1–7 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da |  | ERP | H | H |  |
| AdditionalNumber1–3 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da |  | ERP | H | H |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

### Supplier
<sub>21. Veri modeli · Malzeme</sub>

- Ana veri · versiyonlu · Faz 1
- Tedarikçi ve fasoncu.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| Code | nvarchar(50) | UK | Tedarikçi kodu |  | ERP | H | E |  |
| Name | nvarchar(200) |  | Ad | Tedarikçi adı | ERP | H | H |  |
| IsSubcontractor | bit |  | Fasoncu mu |  | ERP, yoksa kural | H | H | 0 |
| IsActive | bit |  | Aktif mi | Aktif | ERP, yoksa kural | H | H |  |
| Country | nvarchar(100) |  | Ülke |  | ERP | H | H |  |
| City | nvarchar(100) |  | Şehir |  | ERP | H | H |  |
| AdditionalText1–7 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da |  | ERP | H | H |  |
| AdditionalNumber1–3 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da |  | ERP | H | H |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

### MaterialSupplier
<sub>21. Veri modeli · Malzeme</sub>

- Ana veri · versiyonlu · Faz 1
- Malzeme–tedarikçi ilişkisi; satın alma parametreleri. Satın alma her zaman sürekli; yuvarlama son hesapta.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| LocationId | int | FK,UK | Lokasyon |  | ERP | H | E |  |
| MaterialId | bigint | FK,UK | Malzeme |  | ERP | H | E |  |
| SupplierId | bigint | FK,UK | Tedarikçi |  | ERP | H | E |  |
| IsActive | bit |  | Aktif mi | Aktif | ERP, yoksa kural | H | H |  |
| Priority | int |  | Öncelik |  | ERP, yoksa kural | H | H | 1 |
| QuotaRatio | decimal(6,4) |  | Oran olarak kota (0,30 = %30) | Kota oranı | ERP, yoksa kural | H | H |  |
| FixedLeadTimeDays | decimal(9,2) |  | Miktardan bağımsız kısım | Sabit tedarik süresi (gün) | ERP | H | H |  |
| VariableLeadTimeDays | decimal(18,6) |  | Birim başına gün; miktar arttıkça uzayan kısım | Değişken tedarik süresi | ERP | H | H |  |
| LeadTimeBasis | nvarchar(15) |  | Takvim günü \| İş günü | Tedarik süresi esası | Kural ya da elle | H | H | Takvim günü |
| MinimumOrderQuantity | decimal(18,4) |  | Minimum sipariş miktarı |  | ERP | H | H |  |
| OrderLotSize | decimal(18,4) |  | Sipariş miktarı bu sayının katı olur | Sipariş katı | ERP | H | H |  |
| MaximumOrderQuantity | decimal(18,4) |  | Maksimum | Maksimum sipariş miktarı | ERP | H | H |  |
| ValidFrom | date |  | Geçerlilik başlangıcı |  | ERP | H | H |  |
| ValidTo | date |  | Geçerlilik bitişi |  | ERP | H | H |  |
| AdditionalText1–3 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da |  | ERP | H | H |  |
| AdditionalNumber1–2 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da |  | ERP | H | H |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

- **Tedarik süresi (K-118):** Toplam süre = sabit + miktar × değişken. İkisi de zorunlu değil, boşsa boş kalır. İkisi de boşsa süre 0 sayılmaz: veri kalitesinde uyarı, motor bu satırı kullanmaz.
- **Tedarikçi seçimi:** Optimizasyon ya da MRP kararı değil, parametrik bir kuraldır. Motor, parametre setinde seçilen kurala göre tek tedarikçi kullanır: en kısa tedarik süresi (sabit + miktar × değişken) ya da önceliğe göre (`Priority`).
- **Kota:** `QuotaRatio` veride oran (0,30), ekranda ve Excel'de yüzde gösterilir (%30,00). Şimdilik yalnız veri olarak tutulur, ileride kullanılır.

### SupplierLimit
<sub>21. Veri modeli · Malzeme</sub>

- Parametre · versiyonsuz · Faz 1
- Tedarikçi dönem üst limiti (problem 39): malzeme bazında maksimum miktar. Malzeme boşsa tedarikçi o dönemde kapalıdır (limit 0). Smartchain'de ekrandan girilir (K-65, K-66).

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| ParameterSetId | int | FK | Parametre seti |  | Smartchain (parametre) | H | E |  |
| SupplierId | bigint | FK | Tedarikçi |  | Smartchain (parametre) | H | E |  |
| MaterialId | bigint | FK | Malzeme; boşsa tedarikçinin bütün malzemeleri (yalnız kapalı dönem) |  | Smartchain (parametre) | H | H |  |
| ValidFrom | date |  | Başlangıç |  | Smartchain (parametre) | H | E |  |
| ValidTo | date |  | Bitiş |  | Smartchain (parametre) | H | E |  |
| UpperLimit | decimal(18,4) |  | Dönem üst limiti, malzemenin temel biriminde; malzeme boşsa 0 | Dönem üst limiti | Smartchain (parametre) | E | E | 0 |

### ProductionVersion
<sub>21. Veri modeli · Malzeme</sub>

- Ana veri · versiyonlu · Faz 1
- Üretim versiyonu: bir malzemenin ürün ağacı ve rota başlığı; rotaya RouteCode, ürün ağacına BOMCode ile bağlanır. Versiyon seçimi motorun kararıdır; aynı malzeme aynı dönemde birden fazla versiyonla üretilebilir.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| LocationId | int | FK,UK | Lokasyon |  | ERP | H | E |  |
| MaterialId | bigint | FK,UK | Üretilen malzeme |  | ERP | H | E |  |
| Code | nvarchar(30) | UK | Versiyon kodu |  | ERP | H | E |  |
| Name | nvarchar(100) |  | Versiyon adı |  | ERP | H | H |  |
| Type | nvarchar(50) |  | Versiyonları ayrıştırmak için kurallarda kullanılır; değer listesi yok | Versiyon tipi | ERP | H | H |  |
| IsActive | bit |  | Aktif |  | ERP, yoksa kural | H | H |  |
| Priority | int |  | Versiyonlar arası tercih bilgisi; motora girdi | Öncelik | ERP | H | H |  |
| BaseQuantity | decimal(18,4) |  | Baz miktar (rota ve ağaç bu miktar için) | Baz miktar | ERP | H | H | 1 |
| BOMCode | nvarchar(50) |  | Versiyonun kullandığı ürün ağacı | Ürün ağacı kodu | ERP | H | E |  |
| RouteCode | nvarchar(50) |  | Rota kodu | Rota kodu | ERP | H | E |  |
| ValidFrom | date |  | Geçerlilik başlangıcı |  | ERP | H | H |  |
| ValidTo | date |  | Geçerlilik bitişi |  | ERP | H | H |  |
| AdditionalText1–3 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da |  | ERP | H | H |  |
| AdditionalNumber1–2 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da |  | ERP | H | H |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

### BOM
<sub>21. Veri modeli · Malzeme</sub>

- Ana veri · versiyonlu · Faz 1
- Ürün ağacı satırı.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| LocationId | int | FK,UK | Lokasyon |  | ERP | H | E |  |
| MaterialId | bigint | FK,UK | Üretilen malzeme |  | ERP | H | E |  |
| Code | nvarchar(50) | UK | Ürün ağacı kodu |  | ERP | H | E |  |
| ComponentMaterialId | bigint | FK,UK | Bileşen |  | ERP | H | E |  |
| OperationNo | int | UK | Bağlı olduğu operasyon no (ihtiyaç tarihi için) | Operasyon no | ERP | H | H |  |
| SequenceNo | int | UK | Sıra no; aynı bileşen iki kez geçerse operasyon no ile ayrışır | Sıra no | ERP | H | H |  |
| Quantity | decimal(18,6) |  | Baz miktar için bileşen miktarı | Bileşen miktarı | ERP | H | E |  |
| ComponentUom | nvarchar(10) | FK | Bileşen miktarının birimi; boşsa bileşenin temel biriminde kabul edilir, doluysa birim dönüşümüyle çevrilir | Bileşen birimi | ERP | H | H |  |
| ScrapRatio | decimal(6,4) |  | Oran olarak fire (0,05 = %5) | Fire oranı | ERP | H | H | 0 |
| IsPhantom | bit |  | Hayalet bileşen |  | ERP | H | H | 0 |
| IsLotBasedUsage | bit |  | Doluysa bileşen üretilen miktardan bağımsız, her üretim lotu için sabit kullanılır; değilse birim başına | Lot bazlı kullanım | ERP | H | H | 0 |
| AlternativeGroup | nvarchar(50) |  | Aynı grup koduna sahip satırlar birbirinin alternatifidir | Alternatif grubu | ERP | H | H |  |
| AlternativePriority | int |  | Grup içindeki tercih bilgisi | Alternatif önceliği | ERP | H | H |  |
| AdditionalText1–3 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da |  | ERP | H | H |  |
| AdditionalNumber1–2 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da |  | ERP | H | H |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

- **Versiyonla bağ (K-115):** Ürün ağacı kendi koduyla tanımlanır; üretim versiyonu ağacı `ProductionVersion.BOMCode` ile gösterir, aynı ağaç birden fazla versiyonda kullanılabilir.
- **Baz miktar:** Ağaçta yok; `Quantity`, üretim versiyonunun `BaseQuantity`'sine göre okunur. Geçerlilik tarihleri de üretim versiyonundadır.

### Routing
<sub>21. Veri modeli · Malzeme · 1/2</sub>

- Ana veri · versiyonlu · Faz 1
- Rota: her satır bir operasyon–kaynak ilişkisi; sıra önce OperationNo, sonra SequenceNo. Aynı operasyonun kaynakları ayrı satırda, ResourceRole ile.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| LocationId | int | FK,UK | Lokasyon |  | ERP | H | E |  |
| RouteCode | nvarchar(50) | UK | Rota kodu |  | ERP | H | E |  |
| OperationNo | int | UK | Operasyon no (birinci sıralama) | Operasyon no | ERP | H | E |  |
| SequenceNo | int | UK | Operasyon içindeki alt sıra (ikinci sıralama) | Sıra no | ERP | H | E |  |
| OperationName | nvarchar(150) |  | Operasyon adı |  | ERP | H | H |  |
| ResourceId | bigint | FK | Kaynak |  | ERP | H | H |  |
| ResourceGroupId | bigint | FK | Kaynak grubu |  | ERP | H | H |  |
| ResourceRole | nvarchar(10) |  | Primary \| Secondary | Kaynak rolü | ERP, yoksa kural | H | E | Primary |
| Consumption | decimal(18,6) |  | Baz miktar için kaynak tüketimi (kaynağın kapasite biriminde) | Kaynak tüketimi | ERP | H | E |  |
| ResourceNumber | int |  | Operasyonda aynı anda kullanılan kaynak adedi | Kaynak adedi | ERP, yoksa kural | H | E | 1 |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

- **Kaynak ya da kaynak grubu (K-116):** Her satırda `ResourceId` ya da `ResourceGroupId`'den biri dolu olmalı. İkisi de doluysa kaynak geçerlidir; kaynak o grubun üyesi değilse doğrulamada uyarı. Yalnız grup doluysa operasyon grubun herhangi bir kaynağında yapılabilir; seçim motorun kararıdır. Gruptaki kaynakların kapasite birimi farklıysa doğrulamada uyarı.
- **İşçilik (K-116):** Rotada ayrı bir kaynak satırıdır: kaynak ya da kaynak grubu işçi grubu, `ResourceRole` Secondary, `ResourceNumber` kişi sayısı, `Consumption` süre.

### Routing
<sub>21. Veri modeli · Malzeme · 2/2</sub>

- Ana veri · versiyonlu · Faz 1
- Rota: her satır bir operasyon–kaynak ilişkisi; sıra önce OperationNo, sonra SequenceNo. Aynı operasyonun kaynakları ayrı satırda, ResourceRole ile.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|---|
| IsSubcontracted | bit |  | Fason operasyon |  | ERP | H | H | 0 |
| TransferQuantity | decimal(18,4) |  | Transfer partisi | Transfer miktarı | ERP | H | H |  |
| IsActive | bit |  | Operasyon plana dahil mi | Aktif | ERP, yoksa kural | H | H |  |
| IsLotBasedUsage | bit |  | Doluysa tüketim üretilen miktardan bağımsız, lot başına sabit; pratikte hazırlık süresi | Lot bazlı kullanım | ERP | H | H | 0 |
| ProductionLocation | nvarchar(50) |  | Lokasyonun alt tanımı (hol, hat); ileride kısıtlar için | Üretim yeri | ERP | H | H |  |
| WaitingTimeHours | decimal(9,2) |  | Operasyon öncesi kuyruk beklemesi | Bekleme süresi (saat) | ERP | H | H |  |
| TransferTimeHours | decimal(9,2) |  | Sonraki operasyona taşıma | Taşıma süresi (saat) | ERP | H | H |  |
| AlternativeGroup | nvarchar(50) |  | Aynı gruptaki satırlar birbirinin alternatifidir | Alternatif grubu | ERP | H | H |  |
| AlternativePriority | int |  | Grup içindeki tercih bilgisi | Alternatif önceliği | ERP | H | H |  |
| AdditionalText1–3 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da |  | ERP | H | H |  |
| AdditionalNumber1–2 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da |  | ERP | H | H |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

### MaterialReference
<sub>21. Veri modeli · Malzeme</sub>

- Ana veri · versiyonlu · Faz 1
- Benzetilen ürün: kendi ağacı ya da rotası olmayan ürün, başka bir ürünün verisiyle planlanır.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| LocationId | int | FK,UK | Lokasyon |  | ERP | H | E |  |
| MaterialId | bigint | FK,UK | Benzetilen ürün |  | ERP | H | E |  |
| ReferenceMaterialId | bigint | FK,UK | Referans ürün |  | ERP | H | E |  |
| ReferenceProductionVersionId | bigint | FK | Referans ürünün versiyonu; boşsa motor seçer | Referans ürünün versiyonu | ERP | H | H |  |
| ValidFrom | date | UK | Geçerlilik başlangıcı |  | ERP | H | H |  |
| ValidTo | date |  | Geçerlilik bitişi |  | ERP | H | H |  |
| TimeFactor | decimal(9,4) |  | Süre çarpanı; 1,2 = %20 daha uzun | Süre çarpanı | ERP | H | H | 1 |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

- **Kullanım (K-126):** Ürünün kendi geçerli versiyonu yoksa motor referans ürünün ağacını ve rotasını kullanır; motorda uygulanışı Aşama 10.

### ProjectGroup
<sub>21. Veri modeli · Malzeme</sub>

- Ana veri · versiyonlu · Faz 1
- Proje grubu (grup içi paylaşım için).

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| Code | nvarchar(50) | UK | Grup kodu |  | ERP ya da kural | H | E |  |
| Name | nvarchar(200) |  | Proje grubu adı |  | ERP ya da kural | H | H |  |
| TrackingRule | nvarchar(20) |  | Tam izolasyon \| Ortaktan beslenir \| Grup içi paylaşım | Takip kuralı | ERP ya da kural | H | H | Ortaktan beslenir |
| Priority | int |  | Proje grubu önceliği | Öncelik | ERP ya da kural | H | H |  |
| IsActive | bit |  | Aktif mi | Aktif | ERP ya da kural | H | H |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

### Project
<sub>21. Veri modeli · Malzeme</sub>

- Ana veri · versiyonlu · Faz 1
- Proje.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| Code | nvarchar(50) | UK | Proje kodu |  | ERP ya da kural | H | E |  |
| Name | nvarchar(200) |  | Proje adı |  | ERP ya da kural | H | H |  |
| ProjectGroupId | bigint | FK | Proje grubu |  | ERP ya da kural | H | H |  |
| TrackingRule | nvarchar(20) |  | Proje bazında takip kuralı (grubu ezer) | Takip kuralı | ERP ya da kural | H | H |  |
| Priority | int |  | Proje önceliği |  | ERP ya da kural | H | H |  |
| IsActive | bit |  | Aktif mi | Aktif | ERP ya da kural | H | H |  |
| AdditionalText1–7 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da |  | ERP | H | H |  |
| AdditionalNumber1–3 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da |  | ERP | H | H |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

### Customer
<sub>21. Veri modeli · Talep</sub>

- Ana veri · versiyonlu · Faz 1
- Müşteri.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| Code | nvarchar(50) | UK | Müşteri kodu |  | ERP | H | E |  |
| Name | nvarchar(200) |  | Ad | Müşteri adı | ERP | H | H |  |
| Priority | int |  | Müşteri önceliği |  | Kural ya da elle | H | H |  |
| AllowPartialDelivery | bit |  | Kısmi teslimata izin |  | ERP, yoksa kural | H | H | 1 |
| CustomerGroup | nvarchar(50) |  | Müşteri grubu |  | ERP | H | H |  |
| IsActive | bit |  | Aktif mi | Aktif | ERP, yoksa kural | H | H |  |
| Country | nvarchar(100) |  | Ülke |  | ERP | H | H |  |
| Region | nvarchar(100) |  | Bölge |  | ERP | H | H |  |
| City | nvarchar(100) |  | Şehir |  | ERP | H | H |  |
| IsCustomTracked | bit |  | Bu müşterinin talepleri ortak havuzdan değil, müşteriye ayrılmış olarak takip edilir | Özel takip | ERP, yoksa kural | H | H |  |
| AdditionalText1–7 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da |  | ERP | H | H |  |
| AdditionalNumber1–3 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da |  | ERP | H | H |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

### SalesOrderLine
<sub>21. Veri modeli · Talep</sub>

- İşlem verisi · versiyonlu · Faz 1
- Müşteri sipariş satırı; teklifler IsQuote ile okunur, plana dahil olmaları senaryo parametresi. Vade: teyit tarihi, yoksa istek tarihi.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| LocationId | int | FK,UK | Lokasyon |  | ERP | H | E |  |
| OrderNo | nvarchar(30) | UK | Sipariş no |  | ERP | H | E |  |
| LineNo | int | UK | Satır no |  | ERP | H | E |  |
| LineItemNo | int | UK | Alt satır no (ERP satırı kırılımlıysa) | Alt satır no | ERP | H | H | 0 |
| Type | nvarchar(50) |  | ERP'den ham sipariş tipi; veri kurallarında kullanılır, değer listesi yok | Sipariş tipi | ERP | H | H |  |
| CustomerId | bigint | FK | Müşteri |  | ERP | H | E |  |
| MaterialId | bigint | FK | Malzeme |  | ERP | H | E |  |
| ProjectId | bigint | FK | Proje |  | ERP | H | H |  |
| OpenQuantity | decimal(18,4) |  | Açık miktar |  | ERP | H | E |  |
| OrderedQuantity | decimal(18,4) |  | Satırın orijinal miktarı | Sipariş miktarı | ERP | H | H |  |
| DeliveredQuantity | decimal(18,4) |  | Teslim edilen miktar |  | ERP | H | H |  |
| Uom | nvarchar(10) | FK | Açık, sipariş ve teslim miktarının birimi; boşsa malzemenin temel biriminde kabul edilir, doluysa birim dönüşümüyle çevrilir | Sipariş birimi | ERP | H | H |  |
| RequestedDate | date |  | İstek tarihi |  | ERP | H | E |  |
| ConfirmedDate | date |  | Teyit tarihi |  | ERP | H | H |  |
| Priority | int |  | Satır önceliği |  | Kural ya da elle | H | H |  |
| AllowPartialDelivery | bit |  | Kısmi teslimat (müşteriyi ezer) | Kısmi teslimat | ERP | H | H |  |
| Status | nvarchar(50) |  | ERP'den ham sipariş durumu; veri kurallarında kullanılır, değer listesi yok | Sipariş durumu | ERP | H | H |  |
| IsActive | bit |  | Aktif mi | Aktif | ERP, yoksa kural | H | H |  |
| IsOnHold | bit |  | Kredi, teknik onay ya da müşteri talebiyle bekletilen satır | Beklemede | ERP, yoksa kural | H | H |  |
| IsCustomTracked | bit |  | Satır düzeyinde özel takip | Özel takip | ERP, yoksa kural | H | H |  |
| IsQuote | bit |  | Teklif satırı; Type'tan veri kuralıyla doldurulur | Teklif | ERP, yoksa kural | H | H |  |
| AdditionalText1–3 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da |  | ERP | H | H |  |
| AdditionalNumber1–2 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da |  | ERP | H | H |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

### Forecast
<sub>21. Veri modeli · Talep</sub>

- İşlem verisi · versiyonlu · Faz 1
- Talep tahmini (netleme ön hesapta).

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| LocationId | int | FK,UK | Lokasyon |  | ERP | H | E |  |
| MaterialId | bigint | FK,UK | Malzeme |  | ERP | H | E |  |
| CustomerId | bigint | FK,UK | Müşteri |  | ERP | H | H |  |
| ProjectId | bigint | FK,UK | Proje |  | ERP | H | H |  |
| Period | date | UK | Dönem |  | ERP | H | E |  |
| Type | nvarchar(50) | UK | Hangisinin plana gireceği veri kuralıyla seçilir; ERP'den ham değer, değer listesi yok | Tahmin tipi | ERP | H | H |  |
| Quantity | decimal(18,4) |  | Miktar |  | ERP | H | E |  |
| Uom | nvarchar(10) | FK | Miktarın birimi; boşsa malzemenin temel biriminde kabul edilir, doluysa birim dönüşümüyle çevrilir | Birim | ERP | H | H |  |
| DeliveryPoint | nvarchar(10) |  | Miktarın dönemin başında mı sonunda mı hazır olması gerektiği: Başı \| Sonu | Teslim noktası | ERP, yoksa kural | H | H |  |
| IsActive | bit |  | Aktif mi | Aktif | ERP, yoksa kural | H | H |  |
| AdditionalText1–3 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da |  | ERP | H | H |  |
| AdditionalNumber1–2 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da |  | ERP | H | H |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

### BorrowPayback
<sub>21. Veri modeli · Arz ve stok</sub>

- İşlem verisi · versiyonlu · Faz 1
- Projeler arası ödünç ve geri ödeme kaydı: devreye almada açık olan ve ERP'de doğrudan yapılan ödünçlerin motora bildirilmesi; onaylanan öneriler de buraya yazılır.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| LocationId | int | FK,UK | Lokasyon |  | ERP | H | E |  |
| MaterialId | bigint | FK,UK | Malzeme |  | ERP | H | E |  |
| LendingProjectId | bigint | FK,UK | Ödünç veren proje |  | ERP | H | E |  |
| BorrowingProjectId | bigint | FK,UK | Ödünç alan proje |  | ERP | H | E |  |
| BorrowedQuantity | decimal(18,4) |  | Ödünç miktarı |  | ERP | H | E |  |
| PaidBackQuantity | decimal(18,4) |  | Geri ödenen miktar |  | ERP | H | H |  |
| BorrowDate | date | UK | Ödünç tarihi |  | ERP | H | E |  |
| PaybackDueDate | date |  | Geri ödeme tarihi |  | ERP | H | H |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

### Stock
<sub>21. Veri modeli · Arz ve stok</sub>

- İşlem verisi · versiyonlu · Faz 1
- Stok; lot ve durum bazında. Sahip: proje, müşteri, sipariş ya da ortak.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| LocationId | int | FK,UK | Lokasyon |  | ERP | H | E |  |
| MaterialId | bigint | FK,UK | Malzeme |  | ERP | H | E |  |
| Warehouse | nvarchar(30) | UK | Depo |  | ERP | H | H |  |
| LotNo | nvarchar(50) | UK | Lot / seri |  | ERP | H | H |  |
| Status | nvarchar(50) | UK | ERP'den ham stok durumu; veri kurallarında kullanılır, değer listesi yok | Stok durumu | ERP | H | H |  |
| ProjectId | bigint | FK,UK | Sahip proje; proje, müşteri ve sipariş boşsa stok ortaktır | Sahip proje | ERP | H | H |  |
| CustomerId | bigint | FK,UK | Sahip müşteri; stoğun ayrıldığı müşteri, ileride kullanılmak üzere | Sahip müşteri | ERP | H | H |  |
| SalesOrderLineId | bigint | FK,UK | Sahip sipariş satırı; stoğun ayrıldığı sipariş satırı, ileride kullanılmak üzere | Sahip sipariş satırı | ERP | H | H |  |
| Quantity | decimal(18,4) |  | Miktar |  | ERP | H | E |  |
| Uom | nvarchar(10) | FK | Miktarın birimi; boşsa malzemenin temel biriminde kabul edilir, doluysa birim dönüşümüyle çevrilir | Birim | ERP | H | H |  |
| QualityEntryDate | date |  | Kaliteye giriş tarihi |  | ERP | H | H |  |
| ExpectedAcceptanceDate | date |  | Kalitedeki stoğun kullanılabilir hâle gelmesi beklenen tarih | Beklenen kabul tarihi | ERP | H | H |  |
| ExpiryDate | date |  | Son kullanma tarihi (raf ömrü sonraki faz) | Son kullanma tarihi | ERP | H | H |  |
| IsAvailable | bit |  | Stok planda kullanılabilir; Status ve depoya göre veri kuralıyla doldurulur | Kullanılabilir | ERP, yoksa kural | H | H |  |
| IsInQuality | bit |  | Stok planda kalitede sayılır; Status ve depoya göre veri kuralıyla doldurulur | Kalitede | ERP, yoksa kural | H | H |  |
| IsBlocked | bit |  | Stok planda bloke sayılır; Status ve depoya göre veri kuralıyla doldurulur | Bloke | ERP, yoksa kural | H | H |  |
| IsActive | bit |  | Aktif mi | Aktif | ERP, yoksa kural | H | H |  |
| IsCustomTracked | bit |  | Stok düzeyinde özel takip | Özel takip | ERP, yoksa kural | H | H |  |
| AdditionalText1–3 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da |  | ERP | H | H |  |
| AdditionalNumber1–2 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da |  | ERP | H | H |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

### WorkOrder
<sub>21. Veri modeli · Arz ve stok</sub>

- İşlem verisi · versiyonlu · Faz 1
- Açık iş emri (üretim, fason, yeniden işleme).

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| LocationId | int | FK,UK | Lokasyon |  | ERP | H | E |  |
| WorkOrderNo | nvarchar(30) | UK | İş emri no |  | ERP | H | E |  |
| MaterialId | bigint | FK | Üretilen malzeme |  | ERP | H | E |  |
| ProductionVersionId | bigint | FK | Üretim versiyonu; iş emrinin kendi bileşen ve operasyon satırları geldiyse motor onları kullanır, gelmediyse bu versiyonun ağacına ve rotasına gider | Üretim versiyonu | ERP | H | H |  |
| ProductionOrderType | nvarchar(50) |  | ERP'den ham iş emri tipi; veri kurallarında kullanılır, değer listesi yok | İş emri tipi | ERP | H | H |  |
| Status | nvarchar(50) |  | ERP'den ham iş emri durumu; veri kurallarında kullanılır, değer listesi yok | İş emri durumu | ERP | H | H |  |
| Priority | int |  | İş emri önceliği | Öncelik | ERP | H | H |  |
| OrderedQuantity | decimal(18,4) |  | İş emri miktarı |  | ERP | H | E |  |
| OpenQuantity | decimal(18,4) |  | Açık miktar |  | ERP | H | E |  |
| CompletedQuantity | decimal(18,4) |  | Tamamlanan miktar |  | ERP | H | H |  |
| ScrapQuantity | decimal(18,4) |  | Hurda miktarı |  | ERP | H | H |  |
| Uom | nvarchar(10) | FK | Miktarların birimi; boşsa malzemenin temel biriminde kabul edilir, doluysa birim dönüşümüyle çevrilir | Birim | ERP | H | H |  |
| StartDate | date |  | Başlangıç |  | ERP | H | H |  |
| DueDate | date |  | Bitiş |  | ERP | H | E |  |
| ProjectId | bigint | FK | Proje (ayraç) | Proje | ERP | H | H |  |
| CustomerId | bigint | FK | Müşteri |  | ERP | H | H |  |
| SalesOrderLineId | bigint | FK | Bağlı sipariş satırı (ayraç) | Bağlı sipariş satırı | ERP | H | H |  |
| ParentWorkOrderId | bigint | FK | Yeniden işlemede orijinal iş emri | Orijinal iş emri | Kural ya da elle | H | H |  |
| LastActivityDate | date |  | Son hareket tarihi (eskime kontrolü) | Son hareket tarihi | ERP | H | H |  |
| IsFixed | bit |  | Motor bu iş emrinin tarihini ve miktarını değiştirmez | Sabit | ERP, yoksa kural | H | H |  |
| IsReleased | bit |  | İş emri yayınlandı; Status'tan veri kuralıyla doldurulur | Yayınlandı | ERP, yoksa kural | H | H |  |
| IsStarted | bit |  | İş emri başladı; Status'tan veri kuralıyla doldurulur | Başladı | ERP, yoksa kural | H | H |  |
| IsProduction | bit |  | Üretim iş emri; ProductionOrderType'tan veri kuralıyla doldurulur | Üretim | ERP, yoksa kural | H | H |  |
| IsSubcontract | bit |  | Fason iş emri; ProductionOrderType'tan veri kuralıyla doldurulur | Fason | ERP, yoksa kural | H | H |  |
| IsRework | bit |  | Yeniden işleme iş emri; ProductionOrderType'tan veri kuralıyla doldurulur | Yeniden işleme | ERP, yoksa kural | H | H |  |
| IsOnHold | bit |  | Bekletilen iş emri | Beklemede | ERP, yoksa kural | H | H |  |
| IsCustomTracked | bit |  | İş emri düzeyinde özel takip | Özel takip | ERP, yoksa kural | H | H |  |
| AdditionalText1–3 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da |  | ERP | H | H |  |
| AdditionalNumber1–2 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da |  | ERP | H | H |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

- **Kendi satırları önce (K-124):** İş emrinin kendi bileşen ve operasyon satırları geldiyse motor onları kullanır; gelmediyse `ProductionVersionId`'nin ağacına ve rotasına gider. Motorda uygulanışı 10.1.

### WorkOrderComponent
<sub>21. Veri modeli · Arz ve stok</sub>

- İşlem verisi · versiyonlu · Faz 1
- İş emrinin bileşenleri ve çekilen miktar.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| LocationId | int | FK,UK | Lokasyon |  | ERP | H | E |  |
| WorkOrderId | bigint | FK,UK | İş emri |  | ERP | H | E |  |
| MaterialId | bigint | FK,UK | Bileşen |  | ERP | H | E |  |
| OperationNo | int | UK | Bağlı olduğu operasyon no (ihtiyaç tarihi için) | Operasyon no | ERP | H | H |  |
| SequenceNo | int | UK | Sıra no; aynı bileşen iki kez geçerse operasyon no ile ayrışır | Sıra no | ERP | H | H |  |
| RequiredQuantity | decimal(18,4) |  | Gereken miktar |  | ERP | H | E |  |
| IssuedQuantity | decimal(18,4) |  | Çekilen miktar |  | ERP | H | H | 0 |
| RemainingQuantity | decimal(18,4) |  | Kalan ihtiyaç |  | Ön hesap | H | H |  |
| UnitUsage | decimal(18,6) |  | Üretilen bir birim için bileşen miktarı | Birim kullanım | ERP | H | H |  |
| Uom | nvarchar(10) | FK | Bileşen miktarlarının birimi; boşsa bileşenin temel biriminde kabul edilir, doluysa birim dönüşümüyle çevrilir | Birim | ERP | H | H |  |
| ScrapRatio | decimal(6,4) |  | Oran olarak fire (0,05 = %5) | Fire oranı | ERP | H | H | 0 |
| IsLotBasedUsage | bit |  | Doluysa bileşen üretilen miktardan bağımsız, her üretim lotu için sabit kullanılır; değilse birim başına | Lot bazlı kullanım | ERP | H | H | 0 |
| IsPhantom | bit |  | Hayalet bileşen |  | ERP | H | H | 0 |
| AdditionalText1–3 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da |  | ERP | H | H |  |
| AdditionalNumber1–2 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da |  | ERP | H | H |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

### WorkOrderOperation
<sub>21. Veri modeli · Arz ve stok</sub>

- İşlem verisi · versiyonlu · Faz 1
- İş emrinin operasyonları ve kalan iş.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| LocationId | int | FK,UK | Lokasyon |  | ERP | H | E |  |
| WorkOrderId | bigint | FK,UK | İş emri |  | ERP | H | E |  |
| OperationNo | int | UK | Operasyon no |  | ERP | H | E |  |
| SequenceNo | int | UK | Operasyon içindeki alt sıra | Sıra no | ERP | H | E |  |
| OperationName | nvarchar(150) |  | Operasyon adı |  | ERP | H | H |  |
| ResourceId | bigint | FK | Kaynak |  | ERP | H | H |  |
| ResourceGroupId | bigint | FK | Kaynak grubu |  | ERP | H | H |  |
| ResourceRole | nvarchar(10) |  | Primary \| Secondary | Kaynak rolü | ERP, yoksa kural | H | E | Primary |
| ResourceNumber | int |  | Operasyonda aynı anda kullanılan kaynak adedi | Kaynak adedi | ERP, yoksa kural | H | E | 1 |
| PlannedConsumption | decimal(18,6) |  | Planlanan tüketim |  | ERP | H | H |  |
| ConfirmedConsumption | decimal(18,6) |  | Teyit edilen tüketim |  | ERP | H | H | 0 |
| RemainingConsumption | decimal(18,6) |  | Kalan yük |  | Ön hesap | H | H |  |
| Status | nvarchar(50) |  | ERP'den ham operasyon durumu; veri kurallarında kullanılır, değer listesi yok | Operasyon durumu | ERP | H | H |  |
| IsCompleted | bit |  | Operasyon tamamlandı; Status'tan veri kuralıyla doldurulur | Tamamlandı | ERP, yoksa kural | H | H |  |
| IsLotBasedUsage | bit |  | Doluysa tüketim üretilen miktardan bağımsız, lot başına sabit; pratikte hazırlık süresi | Lot bazlı kullanım | ERP | H | H | 0 |
| IsSubcontracted | bit |  | Fason operasyon |  | ERP | H | H | 0 |
| IsActive | bit |  | Operasyon plana dahil mi | Aktif | ERP, yoksa kural | H | H |  |
| ProductionLocation | nvarchar(50) |  | Lokasyonun alt tanımı (hol, hat); ileride kısıtlar için | Üretim yeri | ERP | H | H |  |
| TransferQuantity | decimal(18,4) |  | Transfer partisi | Transfer miktarı | ERP | H | H |  |
| WaitingTimeHours | decimal(9,2) |  | Operasyon öncesi kuyruk beklemesi | Bekleme süresi (saat) | ERP | H | H |  |
| TransferTimeHours | decimal(9,2) |  | Sonraki operasyona taşıma | Taşıma süresi (saat) | ERP | H | H |  |
| AdditionalText1–3 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da |  | ERP | H | H |  |
| AdditionalNumber1–2 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da |  | ERP | H | H |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

- **Kaynak ya da kaynak grubu (K-124):** Rotadaki gibi her satırda `ResourceId` ya da `ResourceGroupId`'den biri dolu olmalı; ikisi de boşsa satır yüklenmez.

### PurchaseOrderLine
<sub>21. Veri modeli · Arz ve stok</sub>

- İşlem verisi · versiyonlu · Faz 1
- Açık satın alma ve fason siparişi satırı (ve talep).

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| LocationId | int | FK,UK | Lokasyon |  | ERP | H | E |  |
| PurchaseOrderNo | nvarchar(30) | UK | Sipariş no |  | ERP | H | E |  |
| LineNo | int | UK | Satır no |  | ERP | H | E |  |
| OrderType | nvarchar(50) |  | ERP'den ham sipariş tipi; veri kurallarında kullanılır, değer listesi yok | Sipariş tipi | ERP | H | H |  |
| SupplierId | bigint | FK | Tedarikçi |  | ERP | H | H |  |
| MaterialId | bigint | FK | Malzeme |  | ERP | H | E |  |
| OpenQuantity | decimal(18,4) |  | Açık miktar |  | ERP | H | E |  |
| OrderedQuantity | decimal(18,4) |  | Sipariş miktarı |  | ERP | H | H |  |
| ReceivedQuantity | decimal(18,4) |  | Teslim alınan miktar |  | ERP | H | H |  |
| Uom | nvarchar(10) | FK | Miktarların birimi; boşsa malzemenin temel biriminde kabul edilir, doluysa birim dönüşümüyle çevrilir | Birim | ERP | H | H |  |
| RequestedDate | date |  | İstenen tarih |  | ERP | H | H |  |
| ConfirmedDate | date |  | Tedarikçi teyit tarihi |  | ERP | H | H |  |
| ProjectId | bigint | FK | Proje |  | ERP | H | H |  |
| CustomerId | bigint | FK | Müşteri |  | ERP | H | H |  |
| SalesOrderLineId | bigint | FK | Bağlı sipariş satırı |  | ERP | H | H |  |
| WorkOrderId | bigint | FK | Fasonda bağlı iş emri | Bağlı iş emri | ERP | H | H |  |
| Status | nvarchar(50) |  | ERP'den ham sipariş durumu; veri kurallarında kullanılır, değer listesi yok | Durum | ERP | H | H |  |
| IsPurchaseRequest | bit |  | Satın alma talebi; OrderType'tan veri kuralıyla doldurulur | Satın alma talebi | ERP, yoksa kural | H | H |  |
| IsPurchase | bit |  | Satın alma siparişi; OrderType'tan veri kuralıyla doldurulur | Satın alma | ERP, yoksa kural | H | H |  |
| IsSubcontract | bit |  | Fason siparişi; OrderType'tan veri kuralıyla doldurulur | Fason | ERP, yoksa kural | H | H |  |
| IsActive | bit |  | Aktif mi | Aktif | ERP, yoksa kural | H | H |  |
| IsCustomTracked | bit |  | Satır düzeyinde özel takip | Özel takip | ERP, yoksa kural | H | H |  |
| AdditionalText1–3 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da |  | ERP | H | H |  |
| AdditionalNumber1–2 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da |  | ERP | H | H |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

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
- Üretim gerçekleşmeleri: iş emri bazında stoğa girişler.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| LocationId | int | FK,UK | Lokasyon |  | ERP | H | E |  |
| ConfirmationNo | nvarchar(30) | UK | Teyit no |  | ERP | H | E |  |
| WorkOrderId | bigint | FK | İş emri |  | ERP | H | E |  |
| MaterialId | bigint | FK | Üretilen malzeme |  | ERP | H | E |  |
| ConfirmedQuantity | decimal(18,4) |  | Teyit miktarı |  | ERP | H | E |  |
| StartDate | date |  | Başlangıç |  | ERP | H | H |  |
| EndDate | date |  | Bitiş |  | ERP | H | H |  |
| AdditionalText1–3 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da |  | ERP | H | H |  |
| AdditionalNumber1–2 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da |  | ERP | H | H |  |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

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

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|---|
| ParameterSetId | int | PK,FK | Parametre seti |  | Smartchain (parametre) | H | E |  |
| SettingKey | nvarchar(60) | PK | Parametre adı | Parametre adı | Smartchain (parametre) | H | E |  |
| Value | nvarchar(200) |  | Değer |  | Smartchain (parametre) | E | E |  |

### TimeBucketDefinition
<sub>21. Veri modeli · Parametre</sub>

- Parametre · versiyonsuz · Faz 1
- Zaman yapısı: planlama ufku ve dinamik bucket dizisi.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|---|
| ParameterSetId | int | PK,FK | Parametre seti |  | Smartchain (parametre) | H | E |  |
| Seq | int | PK | Sıra |  | Smartchain (parametre) | H | E |  |
| BucketType | nvarchar(10) |  | Gün \| Hafta \| Ay \| Çeyrek \| Yıl | Dönem tipi | Smartchain (parametre) | H | E |  |
| Count | int |  | Bu tipten kaç bucket | Dönem sayısı | Smartchain (parametre) | H | E |  |

### PriorityRule
<sub>21. Veri modeli · Parametre</sub>

- Parametre · versiyonsuz · Faz 1
- Sıralama kuralı: kriterlerin sırası (bucket > müşteri > proje > satır > tarih).

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|---|
| ParameterSetId | int | PK,FK | Parametre seti |  | Smartchain (parametre) | H | E |  |
| Seq | int | PK | Sıra |  | Smartchain (parametre) | H | E |  |
| Criterion | nvarchar(30) |  | Kriter |  | Smartchain (parametre) | E | E |  |
| Direction | nvarchar(10) |  | Artan \| Azalan | Yön | Smartchain (parametre) | H | H | Artan |

### AllocationRule
<sub>21. Veri modeli · Parametre</sub>

- Parametre · versiyonsuz · Faz 1
- Kapasite alokasyonu: talep sınıfına kaynak (grubu) ve dönem bazında pay.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| ParameterSetId | int | FK | Parametre seti |  | Smartchain (parametre) | H | E |  |
| DemandClass | nvarchar(100) |  | Talep sınıfı tanımı (müşteri, proje, ürün grubu) | Talep sınıfı | Smartchain (parametre) | H | E |  |
| ResourceId | bigint | FK | Kaynak |  | Smartchain (parametre) | H | H |  |
| ResourceGroupId | bigint | FK | Kaynak grubu |  | Smartchain (parametre) | H | H |  |
| ValidFrom | date |  | Başlangıç |  | Smartchain (parametre) | H | H |  |
| ValidTo | date |  | Bitiş |  | Smartchain (parametre) | H | H |  |
| SharePct | decimal(6,2) |  | Pay (%) |  | Smartchain (parametre) | E | E |  |
| Hardness | nvarchar(10) |  | Taban \| Tavan \| Yumuşak | Sınır tipi | Smartchain (parametre) | H | H | Yumuşak |

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
- Veri sözlüğü: her alanın sınıfı ve değer davranışı. Yapısını System owner yönetir.

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
| Label | nvarchar(100) |  | Ekranda görünen etiket; standart alanın etiketini ezer, ek alanda boşsa alan gösterilmez (K-88); en çok 40 karakter girilir | Sistem | H | H |  |
| StandardLabel | nvarchar(100) |  | docs'tan gelen etiket; kurulumda yazılır, System owner değiştirmez (K-104) | Sistem | H | H |  |
| Description | nvarchar(200) |  | Alan açıklaması; docs/02 AÇIKLAMA'dan, geçişte güncellenir, System owner değiştirmez (K-104) | Sistem | H | H |  |

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

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|---|
| Id | int | PK | Tanım kimliği |  | Sistem | H | E |  |
| LocationId | int | FK | Lokasyon |  | ERP | H | E |  |
| Name | nvarchar(100) |  | Senaryo adı |  | Kullanıcı | H | E |  |
| ParameterSetId | int | FK | Parametre seti |  | Kullanıcı | H | E |  |
| ResourceConstraint | nvarchar(15) |  | Kısıtsız \| Kısıtlı \| Kısmi | Kaynak kısıtı | Kullanıcı | H | H | Kısıtlı |
| MaterialConstraint | bit |  | Malzeme kısıtı |  | Kullanıcı | H | H | 1 |
| ModelType | nvarchar(5) |  | LP \| MILP | Model tipi | Kullanıcı | H | H | LP |
| NightlyPriority | int |  | Gece çalışma önceliği |  | Kullanıcı | H | H |  |
| IsActive | bit |  | Gece çalışsın mı |  | Kullanıcı | H | H | 1 |

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
| Role | nvarchar(15) |  | System owner \| Admin \| Key user \| End user | Kullanıcı | H | E |  |
| PasswordHash | nvarchar(200) |  | Özetlenmiş şifre; Argon2id PHC metni, tuz içinde (K-98); boşsa hesap arayüzden giremez | Sistem | H | H |  |
| MustChangePassword | bit |  | Şifre değiştirilmeli; ilk giriş ya da sıfırlama sonrası | Sistem | H | H | 1 |
| PasswordChangeReason | nvarchar(15) |  | İlk giriş \| Sıfırlama \| Süre doldu | Sistem | H | H |  |
| PasswordChangedAt | datetime2 |  | Şifrenin son değiştiği zaman (UTC) | Sistem | H | H |  |
| PasswordExpiresAt | datetime2 |  | Şifrenin süresinin dolduğu zaman (UTC); değişiklik anındaki politikayla hesaplanır | Sistem | H | H |  |
| FailedAttempts | int |  | Art arda hatalı giriş | Sistem | H | H | 0 |
| LockedUntil | datetime2 |  | Kilit bitişi (UTC); geçmişse ya da boşsa kilit yok | Sistem | H | H |  |
| LastLoginAt | datetime2 |  | Son başarılı giriş (UTC) | Sistem | H | H |  |
| IsActive | bit |  | Aktif | Kullanıcı | H | H | 1 |
| FontSize | int |  | Yazı boyutu tercihi, px: 12, 13, 14 ya da 16 (U-23); boşsa seçilmedi, standart 13 geçerli | Kullanıcı | H | H |  |

- Giriş ve şifre kuralları fonksiyon 89'da ve K-98'de. Şifre ekranda, logda ve denetim izinde düz metin olarak hiç yer almaz.
- Kilit süre dolunca kendiliğinden açılır; Admin elle açınca (K-101) `LockedUntil` boşalır ve sayaç sıfırlanır.

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

- Aynı kullanıcı birden çok tarayıcıda oturum açabilir. "Kapatıldı": kullanıcı pasif edilince ya da rolü bozuk bulununca (K-100, K-101); Admin şifre sıfırlayınca "Şifre değişti".

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
| Channel | nvarchar(15) |  | Gece \| Hesaplama \| Dışa aktarım | Sistem | H | E |  |
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
| CancelReason | nvarchar(200) |  | İptal nedeni; başkasının işinde zorunlu (K-107) | Sistem | H | H |  |
| CancelledBy | int | FK | İptal eden | Sistem | H | H |  |
| Summary | nvarchar(200) |  | İş özeti; kuyruğa girerken iş türü yazar (K-107) | Sistem | H | H |  |

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

### SystemEvent
<sub>21. Veri modeli · Sistem</sub>

- Sistem · versiyonsuz · Faz 1
- Sistem hataları ve sistem aksiyonu (K-106). Saklama `SystemEventRetentionDays`; motor servisi eskileri siler.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| OccurredAt | datetime2 |  | Zaman (UTC) | Sistem | H | E |  |
| Component | nvarchar(20) |  | Motor \| Uygulama \| İş kuyruğu \| Dışa aktarım \| Denetim izi | Sistem | H | E |  |
| Message | nvarchar(500) |  | Hata | Sistem | H | E |  |
| Resolution | nvarchar(200) |  | Sistem aksiyonu | Sistem | H | H |  |
| IsResolved | bit |  | Sistem kendisi çözdü mü | Sistem | H | E | 0 |
| JobId | bigint |  | İlgili iş; olay işten uzun yaşayabilir, bağ tutulmaz | Sistem | H | H |  |
| TraceId | nvarchar(12) |  | Takip numarası | Sistem | H | H |  |
| Detail | nvarchar(1000) |  | Teknik özet; yalnız System owner görür, yığın izi yazılmaz | Sistem | H | H |  |

### ServiceStatus
<sub>21. Veri modeli · Sistem</sub>

- Sistem · versiyonsuz · Faz 1
- Motor servisinin kalp atışı (K-106). Durum saklanmaz, okurken hesaplanır.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| ServiceName | nvarchar(20) | PK | Servis | Sistem | H | E |  |
| HeartbeatAt | datetime2 |  | Son kalp atışı (UTC) | Sistem | H | E |  |
| StartedAt | datetime2 |  | Açılış (UTC) | Sistem | H | E |  |
| StoppedAt | datetime2 |  | Düzgün kapanış (UTC); çalışırken boş | Sistem | H | H |  |
| AppVersion | nvarchar(20) |  | Sürüm | Sistem | H | H |  |

### AuditLog
<sub>21. Veri modeli · Sistem</sub>

- Sistem · versiyonsuz · Faz 1
- Kim, ne zaman, neyi değiştirdi; giriş kayıtları; kayıtlar silinemez (K-109).

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| UserId | int | FK | Kullanıcı | Sistem | H | H |  |
| At | datetime2 | IX | Zaman | Sistem | H | E |  |
| Action | nvarchar(40) |  | İşlem | Sistem | H | E |  |
| ObjectType | nvarchar(40) |  | Nesne | Sistem | H | H |  |
| ObjectKey | nvarchar(200) | IX | Kayıt | Sistem | H | H |  |
| OldValue | nvarchar(max) |  | Önceki | Sistem | H | H |  |
| NewValue | nvarchar(max) |  | Yeni | Sistem | H | H |  |

### SystemSetting
<sub>21. Veri modeli · Sistem</sub>

- Sistem · versiyonsuz · Faz 1
- System owner'ın ayarları: çözücü, süre bütçeleri, işçi sayısı, eş zamanlı çalışma sınırı, saklama süreleri.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| SettingKey | nvarchar(60) | PK | Ayar | Sistem | H | E |  |
| Value | nvarchar(200) |  | Değer | Sistem | H | E |  |

- İş kuyruğu ayarları (K-68); satır yoksa varsayılan geçerlidir:
  - `JobLimitInteractive`: hesaplama kanalında aynı anda çalışan iş (3)
  - `JobLimitNight`: gece kanalında aynı anda çalışan iş (2)
  - `JobLimitExport`: dışa aktarım kanalında aynı anda çalışan iş (2; K-93)
  - `JobHeartbeatTimeoutSeconds`: kalp atışı bu kadar saniye gelmezse iş takılmış sayılır (120)
  - `JobMaxAttempts`: takılan iş en fazla bu kadar denenir, sonra Hata (2)
- Motor ayarları (K-71; fonksiyon 34):
  - `EngineTimeBudgetInteractiveSeconds`: hesaplama kanalında hesap süre bütçesi (180)
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
- Sistem sağlığı (K-106; fonksiyon 94): `DiskWarnPercent` (85), `QueueWaitWarnMinutes` (10), `SystemEventRetentionDays` (90).
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
