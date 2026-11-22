# Veri modeli (MDD adım 21)

Kaynak: Master Design Document (MDD) 26.10.2026. Bu dosya desteden üretilmiştir; değişiklik önce burada yapılır, deste dilim sonlarında buradan güncellenir (K-54).

### 21. Veri modeli
<sub>tamamlandı</sub>

- **Ne yapılacak:** Varlıklar ve ilişkileri, her tablonun alanları; her alanın tipi, ana kaynağı, sınıfı, çalışmada değiştirilebilir olup olmadığı, zorunluluğu ve boşsa anlamı (K-138). ERP'den bağımsız veri sözleşmesinin temeli. Çıktı: veri modeli, alan sözlüğü ve UML (Excel ve diyagramlar)
  - Bu adımın slaytları
  - 4 İlkeler ve genel görünüm
  - 6 Tablo listesi
  - 5 Ortak
  - 14 Kaynak
  - 10 Malzeme
  - 3 Talep
  - 7 Arz ve stok
  - 6 Parametre
  - 10 Veri yönetimi
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

- **ERP'den bağımsız:** Tek veri sözleşmesi; API, Excel ve SQL view'ları aynı entegrasyon tablolarına (stg.*) iner.
- **Adlandırma:** Tablo ve alan adları İngilizce (Resource.ResourceType), açıklamalar Türkçe. Veritabanı MS SQL Server.
- **Lokasyon:** Lokasyon bütün ana ve işlem verisi tablolarında baştan var; Faz 1'de her lokasyon kendi içinde planlanır.
- **Veri sınıfları:** Ana veri genel ve bütün senaryolarda aynı; parametre Smartchain'de, parametre setine bağlı ve senaryoya özel olabilir; işlem verisi ERP'den gelen hareketler.
- **Değer kaynağı:** Her alanın değeri ERP, kural ya da elle gelir; varsayılan değer yoktur (K-138). Öncelik veri sözlüğünde (FieldDefinition) alan bazında tanımlıdır. ERP değeri ezilse bile saklanır.
- **Boşsa (K-138):** Veri tablolarının BOŞSA kolonu, kurallardan sonra boş kalan alanın anlamını yazar: hata (satır atlanır), hata (kurallardan sonra), yok, sınırsız, bilinmiyor, temel birim ya da alana özgü anlam. Anlamlar docs/03'teki entegrasyon tablolarıyla aynıdır; Id alanı kod alanının anlamını taşır. Parametre, plan ve sistem tablolarında VARSAYILAN kalır: bunlar veri değildir.
- **Veri versiyonları:** Versiyonlu tablolarda her kayıt hangi veri versiyonundan hangisine kadar geçerli olduğunu taşır (VersionFrom, VersionTo). Kısmi aktarımda sadece değişen kayıtlar yazılır; veri kopyalanmaz (K-152).
- **Çalışmalar:** Çalışmadaki geçici değişiklikler tek bir tabloda tutulur (WorkspaceOverride); ana veri değişmez.
- **Plan çıktıları:** Bütün plan çıktıları bir plan hesabına (PlanRun) bağlıdır; onaylı plan yayınlanan hesabı gösterir.
- **Proje:** Stok, iş emri, satın alma ve siparişte sahip alanı (ProjectId); envanter proje sayısıyla çoğaltılmaz.
- **İki katman:** Entegrasyon tabloları kodla (MaterialCode), ana tablolar Id ile; ERP verisi ana tablolara aktarımla geçer.
- **Ek alanlar:** Ana veride 10 (7 metin + 3 sayı), yapı ve işlem verisinde 5 (3 metin + 2 sayı); etiketi FieldDefinition'da.
- **Etiket ve açıklama:** ETİKET kolonu doluysa ekrandaki alan adı odur; açıklama AÇIKLAMA'da ve veritabanı yorumunda kalır. Boşsa etiket AÇIKLAMA'dan kuralla türer (K-88).

### Entegrasyon tabloları ve ana tablolar
<sub>21. Veri modeli · İki katman ve ek alanlar</sub>

- ENTEGRASYON TABLOSU
- **stg.Material:** ERP'nin dili: Id yok, ilişkiler kodla. API, SQL view'ları ve Excel aynı yapıya iner.
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

- **1 · Validasyon Tip, zorunlu alan, tekrar eden anahtar**
- **Kod → Id eşleme Bilinmeyen kod: satır Hatalı, ana tabloya geçmez:** 2
- **3 · Veri kuralları Eksik alanlar kural ya da manuel değerle tamamlanır**
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
| ERP | Entegrasyondan gelir (API, Excel, SQL view'ları). | Material.Code, SalesOrderLine.OpenQuantity |
| ERP, yoksa kural | ERP'de varsa oradan; yoksa veri kuralıyla doldurulur. | Material.MaterialLevel, Resource.IsCritical |
| Kural ya da elle | ERP'de genelde yok; veri kuralıyla ya da ana veri ekranında elle. | Material.IsCustomTracked |
| Smartchain (parametre) | Smartchain'de tanımlanan planlama parametresi; parametre setine bağlı. | ResourceEfficiency.EfficiencyPct, AllocationRule.SharePct |
| Kullanıcı | Kullanıcının ekrandan girdiği tanım. | DataRule, ScenarioDefinition |
| Sistem | Sistemin ürettiği ya da System owner'ın yönettiği değer. | Id alanları, PlanRun, Job |
| Ön hesap | Ön hesapta türetilen değer. | WorkOrderComponent.RemainingQuantity |
| Motor | Planlama motorunun çıktısı. | PlannedOrder, CapacityLoad, Pegging |

### Alan grupları ve veri akışı
<sub>21. Veri modeli · Genel görünüm</sub>

- **Veri yönetimi  19 tablo:** RawCompare · RawCompareRow · ImportBatch · ImportFinding · IntegrationEntity · IntegrationViewVersion · Staging (ham ve işlenmiş katman) · DataRule · DataRuleEffect · FieldDefinition · ManualValue · FieldChange · DataQualityWarning · DemandChain · DemandChainPath · DataVersion
- **Kaynak  10 tablo:** Resource · ResourceGroup · ResourceGroupMember · EmployeeAbsence · WorkPattern · ResourceEfficiency · OvertimeLimit · ResourceDowntime · FactoryCalendar · ResourceGroupConstraint
- **Malzeme  9 tablo:** Material · MaterialSupplier · BOM · Routing · MaterialReference · Project
- **Parametre  7 tablo:** PlanningSetting · TimeBucketDefinition · ObjectiveDefinition · PriorityRule · AllocationRule · WarningThreshold
- yükleme
- **Talep  3 tablo:** Customer · SalesOrderLine · Forecast
- **Arz ve stok  8 tablo:** Stock · BorrowPayback · WorkOrder · PurchaseOrderLine · TransferOrder
- **Plan  13 tablo:** ScenarioDefinition · Scenario · Workspace · PlanRun · PlanVersion · PlannedOrder · CapacityLoad · Pegging · PlanWarning
- versiyon
- **Sistem  8 tablo:** AppUser · Job · SolverLog · SystemEvent · ServiceStatus · AuditLog · SystemSetting · License
- **Ortak  3 tablo:** Location · UnitOfMeasure · UomConversion
- Akış: ERP verisi entegrasyon tablolarına (stg.*) iner, veri kurallarıyla tamamlanır ve yüklemeyle veri versiyonu olur. Senaryolar bir veri versiyonu ve bir parametre setiyle çalışır; çıktılar plan hesabına bağlanır, onaylı plan ERP'ye döner.

### Tablo listesi
<sub>21. Veri modeli · Tablo listesi · 1/6</sub>

#### ORTAK

- **Location:** Lokasyon (tesis, depo)
- **UnitOfMeasure:** Ölçü birimi
- **UomConversion:** Malzeme bazında birim dönüşümü

#### TALEP

- **Customer:** Müşteri
- **SalesOrderLine:** Müşteri sipariş satırı
- **Forecast:** Talep tahmini (netleme ön hesapta)

### Tablo listesi
<sub>21. Veri modeli · Tablo listesi · 2/6</sub>

#### KAYNAK

- **Resource:** Kaynak: tek bir makine, işçi ya da fason iş yeri
- **ResourceGroup:** Kaynak grubu: planlama birimi; tip, kritiklik, kapasite birimi
- **ResourceGroupMember:** Kaynak grup eşleşmesi: kaynağın gruba üyeliği; yetkinlik matrisi
- **WorkPattern:** Çalışma düzeni: günlük kapasite ve haftanın günleri (K-185)
- **ResourceEfficiency:** Verimlilik (kapasite katsayısı)
- **OvertimeLimit:** Ek mesai limiti (günlük, kaynak başına)
- **ResourceDowntime:** Bakım ve duruş
- **FactoryCalendar:** Fabrika takvimi (toplu duruş)
- **ResourceGroupConstraint:** Model kısıtları: kaynak grubunun kısıtsız kapasite çarpanı ve hedef doluluğu (K-189)
- **EmployeeAbsence:** Kişi bazında izin ve rapor

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

- **PlanningSetting:** Senaryonun planlama parametreleri (anahtar–değer)
- **TimeBucketDefinition:** Zaman yapısı: senaryonun ufuk ve dönem dizisi (plan ve raporlama ekseni)
- **ObjectiveDefinition:** Senaryonun hedefleri: sıra, süre bütçesi, ödün payı (leksikografik)
- **PriorityRule:** Sıralama kuralı: kriterlerin sırası (bucket > müşteri > proje > satır > tarih)
- **AllocationRule:** Kapasite alokasyonu: talep sınıfına kaynak (grubu) ve dönem bazında pay
- **WarningDefinition:** Uyarı kataloğu: kod ve kategori (K-190)
- **WarningThreshold:** Senaryonun uyarı eşikleri: kademeli eşik, önem, aktiflik (K-190)

### Tablo listesi
<sub>21. Veri modeli · Tablo listesi · 5/6</sub>

#### VERI YÖNETIMI

- **FieldDefinition:** Veri sözlüğü: her alanın sınıfı ve değer davranışı
- **DataRule:** Veri kuralı: 'X = … ise Alan = …'
- **DataRuleCondition:** Kural koşulları (VE / VEYA)
- **DataRuleEffect:** Kural izi: hücreyi son değiştiren kural ve ham değer (K-140)
- **ManualValue:** Kayıt ve alan başına manuel değer; alttaki değer (ERP ya da kural) saklanır (K-170)
- **FieldChange:** Alan değişikliği: kaydın geçmişi (aktarım, manuel değer, Smartchain girişi; K-173)
- **DataQualityWarning:** Veri kalitesi uyarısı: yüklenmiş veride takipli kural ya da Smartchain kontrolüyle bulunan sorun (K-174)
- **DemandChain:** Talep zinciri kümesi: açık talepten ulaşılan kayıtlar; uyarının önemi (K-174)
- **DemandChainPath:** Talep zinciri yolları: detay kartı açılınca hesaplanan önbellek (K-174)
- **FieldValueSource:** Geçerli değerin kaynağı ve ERP değeri (ezilse bile saklanır)
- **ImportBatch:** Ham veri partisi: her yükleme parti numarası, zaman ve kaynakla
- **ImportFinding:** Partinin bulguları (ön kontrol ve doğrulama)
- **IntegrationEntity:** Tablo başına çekim ayarı: yöntem, çekim anahtarı, view (K-130)
- **IntegrationViewVersion:** View'ın sürüm geçmişi (K-130)
- **stg.*:** Entegrasyon tabloları: her varlık için bir tane (stg.Material…); ilişkiler kodla; ham katman
- **prc.*:** İşlenmiş staging: ham katmanın güncel hâli, veri kuralları uygulanmış (K-140)
- **DataVersion:** Aktarım ile oluşan dondurulmuş veri versiyonu
- **DataVersionEntity:** Aktarımda hangi tabloların aktarıldığı
- **RawCompare:** Dünden bugüne: tablo başına karşılaştırma özeti (K-160)
- **RawCompareRow:** Dünden bugüne: yeni gelen, gelmeyen ve güncellenen kayıtlar (K-160)

### Tablo listesi
<sub>21. Veri modeli · Tablo listesi · 6/6</sub>

#### PLAN

- **ScenarioDefinition:** Senaryo tanımı; parametrelerinin tamamını kendisi taşır (K-175)
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

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | BOŞSA |
|---|---|---|---|---|---|---|---|---|
| Id | int | PK | Lokasyon kimliği |  | Sistem | H | E |  |
| Code | nvarchar(30) | UK | Lokasyon kodu |  | ERP | H | E | hata (satır atlanır) |
| Name | nvarchar(100) |  | Lokasyon adı |  | ERP | H | H | bilinmiyor |
| Type | nvarchar(50) |  | ERP'den ham lokasyon tipi; veri kurallarında kullanılır (bayraklar bundan dolar), değer listesi yok (K-143) | Lokasyon tipi | ERP | H | H | bilinmiyor |
| IsFactory | bit |  | Tesis mi | Tesis | Kural, ERP ya da Excel | H | H | yok |
| IsDepot | bit |  | Depo mu | Depo | Kural, ERP ya da Excel | H | H | yok |
| IsSubcontractor | bit |  | Fason deposu mu | Fason deposu | Kural, ERP ya da Excel | H | H | yok |
| IsActive | bit |  | Aktif mi | Aktif | Kural, ERP ya da Excel | H | E | hata (kurallardan sonra) |
| Country | nvarchar(100) |  | Ülke |  | ERP | H | H | bilinmiyor |
| CountryCode | nvarchar(10) |  | Ülke kodu |  | ERP | H | H | bilinmiyor |
| Region | nvarchar(100) |  | Bölge |  | ERP | H | H | bilinmiyor |
| RegionCode | nvarchar(20) |  | Bölge kodu |  | ERP | H | H | bilinmiyor |
| City | nvarchar(100) |  | Şehir |  | ERP | H | H | bilinmiyor |
| CityCode | nvarchar(20) |  | Şehir kodu |  | ERP | H | H | bilinmiyor |
| AdditionalText1–7 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da |  | ERP | H | H | yok |
| AdditionalNumber1–3 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da |  | ERP | H | H | yok |
| IsSynthetic | bit |  | Sentetik veri (geliştirme ve demo); sentetik veri komutları yalnız bunlara dokunur (K-79) |  | Sistem | H | H |  |

### UnitOfMeasure
<sub>21. Veri modeli · Ortak</sub>

- Ana veri · versiyonsuz · Faz 1
- Ölçü birimi.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | BOŞSA |
|---|---|---|---|---|---|---|---|---|
| Code | nvarchar(10) | PK | Birim kodu (AD, KG, SAAT…) | Birim kodu | Yüklemede diğer tablolardan | H | E | hata (satır atlanır) |
| Name | nvarchar(50) |  | Birim adı |  | Birim dönüşümündeki ad, elle ya da kural | H | H | bilinmiyor |
| Decimals | tinyint |  | Miktar ondalığı; ERP'den gelmez, Smartchain'de tutulur (K-88) |  | Elle ya da kural | H | H | bilinmiyor |

- **Oluşma (K-112):** Entegrasyon tablosu ve şablonu yoktur. Yüklemede (5.2) diğer tablolarda geçen birim kodlarından otomatik oluşur; ad boşsa UomConversion'daki FromUomName ya da ToUomName'den doldurulur. Ad ve ondalık ana veri ekranında elle ya da veri kuralıyla yönetilir (6.1).
- **Decimals:** bu birimdeki miktarlar ekranda bu kadar ondalıkla gösterilir (K-88). ERP aktarımı ezmez. Boşsa bilinmiyor (ekranda değer olduğu gibi gösterilir); kurulumda tanımlanır.

### UomConversion
<sub>21. Veri modeli · Ortak</sub>

- Ana veri · versiyonlu · Faz 1
- Malzeme bazında birim dönüşümü.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | BOŞSA |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| MaterialId | bigint | FK,UK | Malzeme (boşsa genel dönüşüm) | Malzeme | ERP | H | H | bütün malzemeler |
| FromUom | nvarchar(10) | FK,UK | Kaynak birim |  | ERP | H | E | hata (satır atlanır) |
| FromUomName | nvarchar(50) |  | Kaynak birim adı |  | ERP | H | H | bilinmiyor |
| ToUom | nvarchar(10) | FK,UK | Hedef birim |  | ERP | H | E | hata (satır atlanır) |
| ToUomName | nvarchar(50) |  | Hedef birim adı |  | ERP | H | H | bilinmiyor |
| Factor | decimal(18,6) |  | 1 kaynak birim = çarpan × hedef birim | Çarpan | ERP | H | E | hata (satır atlanır) |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

### Resource
<sub>21. Veri modeli · Kaynak</sub>

- Ana veri · versiyonlu · Faz 1
- Kaynak: tek bir makine, işçi ya da fason iş yeri. Planlama birimi kaynak değil kaynak grubudur (K-180): tip bayrakları, kritiklik, kapasite birimi ve fasoncu gruptadır; kaynak gruplarına `ResourceGroupMember` ile bağlanır.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | BOŞSA |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| LocationId | int | FK,UK | Lokasyon |  | ERP | H | E | hata (satır atlanır) |
| Code | nvarchar(50) | UK | Kaynak kodu |  | ERP | H | E | hata (satır atlanır) |
| Name | nvarchar(150) |  | Kaynak adı |  | ERP | H | H | bilinmiyor |
| ResourceType | nvarchar(50) |  | ERP'den gelen ham değer; yalnız bilgi (raporlama ve filtre), planlama grubun bayraklarına bakar | Kaynak tipi | ERP | H | H | bilinmiyor |
| IsActive | bit |  | Aktif mi | Aktif | ERP, yoksa kural | H | H | hata (kurallardan sonra) |
| ProductionLocation | nvarchar(50) |  | Lokasyonun alt tanımı (hol, hat) | Üretim yeri | ERP | H | H | bilinmiyor |
| RemainingOverTimeYear | decimal(9,2) |  | Yıllık kalan fazla mesai (saat) |  | ERP | H | H | sınırsız |
| RemainingOverTimeMonth | decimal(9,2) |  | Aylık kalan fazla mesai (saat) |  | ERP | H | H | sınırsız |
| AdditionalText1–7 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da |  | ERP | H | H | yok |
| AdditionalNumber1–3 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da |  | ERP | H | H | yok |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

- **Kaynakta kalanlar (K-180):** lokasyon, kod, ad, ham tip (yalnız bilgi), aktif, üretim yeri, yıllık ve aylık kalan fazla mesai, ek alanlar. Tip bayrakları, `IsCritical`, `CapacityUnit` ve fasoncu kaynak grubundadır; kaynakta yoktur.
- **Kapasite (K-185):** günlük kapasite, çalışma günleri, verimlilik, duruş ve ek mesai limiti kaynakta alan olarak durmaz; Kapasite yönetimi'nin senaryolu giriş tablolarındadır (`param.WorkPattern` ve ötekiler). Kaynaktaki günlük kapasite, takvim ataması ve fason parametreleri 7.9'da kalktı.
- **Kalkanlar (K-180):** `CapacitySource` ("Kapasite kaynağı"; vardiya kavramıyla birlikte) ve `Quantity` (paralel adet; kaynak adedi grup eşleşmesinden bilinir).
- **İşçi:** İşçiler kaynaktır; işçi grubu (yetkinlik grubu) `IsEmployee` bayraklı kaynak grubudur; işçinin yetkinlikleri `ResourceGroupMember`'dadır (bir işçi birden fazla gruba üye olabilir).

### ResourceGroup
<sub>21. Veri modeli · Kaynak</sub>

- Ana veri · versiyonlu · Faz 1
- Kaynak grubu: planlama birimi (K-180). Rota ve iş emri operasyonu grubu gösterir; plan ve yük grup düzeyindedir. Tip, kritiklik, kapasite birimi ve fasoncu gruptadır. Gruptaki kaynak sayısı `ResourceGroupMember`'dan bilinir, ayrıca girilmez.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | BOŞSA |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| LocationId | int | FK,UK | Lokasyon |  | ERP | H | E | hata (satır atlanır) |
| Code | nvarchar(50) | UK | Grup kodu |  | ERP | H | E | hata (satır atlanır) |
| Name | nvarchar(150) |  | Grup adı |  | ERP | H | H | bilinmiyor |
| Type | nvarchar(50) |  | ERP'den gelen ham değer; tip bayraklarla ifade edilir | Grup tipi | ERP | H | H | bilinmiyor |
| IsEmployee | bit |  | İşçi grubu mu (yetkinlik grubu) | İşçi | ERP, yoksa kural | H | H | yok |
| IsMachine | bit |  | Makine grubu mu | Makine | ERP, yoksa kural | H | H | yok |
| IsFurnace | bit |  | Fırın grubu mu; Faz 1 planlamada kullanılmaz | Fırın | ERP, yoksa kural | H | H | yok |
| IsMold | bit |  | Kalıp grubu mu; Faz 1 planlamada kullanılmaz | Kalıp | ERP, yoksa kural | H | H | yok |
| IsOther | bit |  | Diğer kaynak grubu mu | Diğer | ERP, yoksa kural | H | H | yok |
| IsSubcontractor | bit |  | Fason grubu mu | Fason | ERP, yoksa kural | H | H | yok |
| IsActive | bit |  | Aktif mi | Aktif | ERP, yoksa kural | H | H | hata (kurallardan sonra) |
| IsCritical | bit |  | 1: planda kısıt, 0: sonsuz kapasite (sadece raporlanır) | Kritik | ERP, yoksa kural | H | H | hata (kurallardan sonra) |
| CapacityUnit | nvarchar(10) | FK | Kapasite birimi (Saat, Adet, Ton…); rotadaki tüketim aynı birimde kabul edilir | Kapasite birimi | ERP, yoksa kural | H | E | hata (kurallardan sonra) |
| SubcontractorId | bigint | FK | Fason grubunda fasoncu | Fasoncu | ERP | H | H | bilinmiyor |
| AdditionalText1–7 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da |  | ERP | H | H | yok |
| AdditionalNumber1–3 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da |  | ERP | H | H | yok |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

- **Planlama birimi (K-180):** Kaynak grubu zorunludur. Kaynakla çalışan müşteri entegrasyon view'unda kaynaklarını grup olarak verir (her kaynak için aynı kodla bir grup ve bir eşleşme satırı); eksik alanlar veri kuralıyla doldurulabilir.
- **Tip:** `Type` ERP'den ham değerdir; tip bayraklarla ifade edilir (boşsa veri kuralıyla doldurulur, varsayılan yok). Yetkinlik grubu `IsEmployee` olan gruptur. `IsFurnace` ve `IsMold` yalnız sözleşmededir, Faz 1 planlamada kullanılmaz.
- **Kritik:** Kritik olmayan grup sonsuz kapasiteli sayılır ve yalnız raporlanır. Birden fazla gruba üye kaynağın kapasitesini yalnız kritik grupların yükü kullanır. Kaynağı olmayan kritik grubun kapasitesi sıfırdır (doğrulamada ve veri kalitesinde uyarı).
- **Kapasite birimi:** ERP'den gelir, yoksa veri kuralıyla doldurulur; ikisinden de gelmezse doğrulamada hata. Bir kaynağın üye olduğu grupların kapasite birimi aynı olmalıdır (doğrulamada uyarı).
- **Kapasite (sonraki adım, 7.9):** kapasite kaynakta hesaplanır, grupta toplanır; plan ve yük grup düzeyindedir.

### ResourceGroupMember
<sub>21. Veri modeli · Kaynak</sub>

- Ana veri · versiyonlu · Faz 1
- Kaynak grup eşleşmesi: kaynağın gruba üyeliği. Bir kaynak birden fazla gruba üye olabilir (birden fazla yetkinliği olan işçi). Geçerlilik tarihi yoktur: yüklü eşleşme bugünden itibaren geçerlidir. Gruptaki kaynak sayısı bu tablodan bilinir (K-180).

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | BOŞSA |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| LocationId | int | FK,UK | Lokasyon |  | ERP | H | E | hata (satır atlanır) |
| ResourceGroupId | bigint | FK,UK | Kaynak grubu |  | ERP | H | E | hata (satır atlanır) |
| ResourceId | bigint | FK,UK | Kaynak |  | ERP | H | E | hata (satır atlanır) |
| AdditionalText1–3 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da |  | ERP | H | H | yok |
| AdditionalNumber1–2 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da |  | ERP | H | H | yok |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

### EmployeeAbsence
<sub>21. Veri modeli · Kaynak</sub>

- İşlem verisi · versiyonlu · Faz 1
- Kişi bazında izin ve rapor.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | BOŞSA |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| LocationId | int | FK,UK | Lokasyon |  | ERP | H | E | hata (satır atlanır) |
| ResourceId | bigint | FK,UK | Kaynak |  | ERP | H | E | hata (satır atlanır) |
| AbsenceType | nvarchar(50) | UK | ERP'den gelen ham değer (izin, rapor…) | Devamsızlık tipi | ERP | H | E | hata (satır atlanır) |
| StartDate | date | UK | Başlangıç |  | ERP | H | E | hata (satır atlanır) |
| EndDate | date |  | Bitiş günü dahil | Bitiş | ERP | H | E | hata (satır atlanır) |
| HoursPerDay | decimal(9,2) |  | Günlük devamsız saat; kısmi devamsızlık için, boşsa tam gün | Günlük saat | ERP | H | H | tam gün |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

### Material
<sub>21. Veri modeli · Malzeme · 1/2</sub>

- Ana veri · versiyonlu · Faz 1
- Malzeme ve planlama ana verisi.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | BOŞSA |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| LocationId | int | FK,UK | Lokasyon | ERP | H | E | hata (satır atlanır) |
| Code | nvarchar(50) | UK | Malzeme kodu | ERP | H | E | hata (satır atlanır) |
| Name | nvarchar(200) |  | Malzeme adı | ERP | H | H | bilinmiyor |
| BaseUom | nvarchar(10) | FK | Temel birim | ERP | H | E | hata (satır atlanır) |
| MaterialGroup | nvarchar(50) |  | Malzeme grubu | ERP | H | H | bilinmiyor |
| MaterialLevel | nvarchar(15) |  | Malzeme seviyesi: Hammadde \| Yarı mamul \| Nihai ürün | ERP, yoksa kural | H | H | bilinmiyor |
| MaterialType | nvarchar(50) |  | Malzeme tipi | ERP | H | H | bilinmiyor |
| Brand | nvarchar(50) |  | Marka | ERP | H | H | bilinmiyor |
| PlannerCode | nvarchar(50) |  | Planlamacı | ERP | H | H | bilinmiyor |
| MRPGroup | nvarchar(50) |  | MRP grubu; planlama parametreleri aynı olan malzemeleri gruplar | ERP | H | H | bilinmiyor |
| IsActive | bit |  | Aktif | ERP, yoksa kural | H | H | hata (kurallardan sonra) |
| IsCritical | bit |  | Kritik malzeme; malzeme kısıtı yalnız kritik malzemelere uygulanır, kritik olmayanın her zaman temin edilebildiği varsayılır | ERP, yoksa kural | H | H | yok |
| IsPurchasable | bit |  | Satın alınabilir | ERP, yoksa kural | H | H | yok |
| IsProducible | bit |  | Üretilebilir | ERP, yoksa kural | H | H | yok |
| IsSellable | bit |  | Satılabilir | ERP, yoksa kural | H | H | yok |
| IsSubcontractable | bit |  | Fasona verilebilir | ERP, yoksa kural | H | H | yok |
| DefaultSupplyType | nvarchar(10) |  | Tedarik türü: Üretim \| Satın alma \| Fason | ERP, yoksa kural | H | H | hata (kurallardan sonra) |
| IsCustomerSupplied | bit |  | Müşteri temin malzemesi | Kural ya da elle | H | H | yok |

### Material
<sub>21. Veri modeli · Malzeme · 2/2</sub>

- Ana veri · versiyonlu · Faz 1
- Malzeme ve planlama ana verisi.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | BOŞSA |
|---|---|---|---|---|---|---|---|---|
| IsCustomTracked | bit |  | Malzeme ortak havuzdan değil, belli bir talebe (proje, müşteri ya da sipariş) ayrılmış olarak takip edilir; hangi talebe ayrıldığı talep kaydından gelir | Özel takip | Kural ya da elle | H | H | yok |
| IsPhantom | bit |  | Hayalet yarı mamul |  | ERP | H | H | yok |
| IsNonStockable | bit |  | Stok tutulamaz; üretilen ya da teslim alınan miktar beklemeden tüketilir, dönem sonu stoğu sıfırdır | Stok tutulamaz | ERP, yoksa kural | H | H | yok |
| GoodsReceiptDays | decimal(9,2) |  | Mal kabul süresi (iş günü) |  | ERP, yoksa kural | H | H | yok |
| SafetyStock | decimal(18,4) |  | Güvenlik stoğu |  | ERP | H | H | yok |
| StockCoverageDays | decimal(9,2) |  | Gün cinsinden güvenlik stoğu | Stok gün kapsamı | ERP | H | H | yok |
| MaxStock | decimal(18,4) |  | Maksimum stok |  | ERP | H | H | sınırsız |
| LotSizePolicy | nvarchar(15) |  | Lot politikası (üretimde): Lot-for-lot \| Sabit \| Dönemsel | Lot politikası | ERP, yoksa kural | H | H | yok |
| MinLot | decimal(18,4) |  | Üretimde minimum | Minimum lot | ERP | H | H | yok |
| MaxLot | decimal(18,4) |  | Üretimde maksimum | Maksimum lot | ERP | H | H | sınırsız |
| LotMultiple | decimal(18,4) |  | Üretimde kat | Lot katı | ERP | H | H | yok |
| QtyPerBox | decimal(18,4) |  | Temel birimde kutu içi miktar | Kutu içi miktar | ERP | H | H | bilinmiyor |
| QtyPerPallet | decimal(18,4) |  | Temel birimde palet içi miktar | Palet içi miktar | ERP | H | H | bilinmiyor |
| ScrapRatio | decimal(6,4) |  | Oran olarak fire (0,05 = %5) | Fire oranı | ERP | H | H | yok |
| ShelfLifeDays | int |  | Raf ömrü; şimdilik yalnız uyarı için kullanılır | Raf ömrü (gün) | ERP | H | H | sınırsız |
| AdditionalText1–7 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da |  | ERP | H | H | yok |
| AdditionalNumber1–3 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da |  | ERP | H | H | yok |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

### Supplier
<sub>21. Veri modeli · Malzeme</sub>

- Ana veri · versiyonlu · Faz 1
- Tedarikçi ve fasoncu.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | BOŞSA |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| Code | nvarchar(50) | UK | Tedarikçi kodu |  | ERP | H | E | hata (satır atlanır) |
| Name | nvarchar(200) |  | Ad | Tedarikçi adı | ERP | H | H | bilinmiyor |
| IsSubcontractor | bit |  | Fasoncu mu |  | ERP, yoksa kural | H | H | yok |
| IsActive | bit |  | Aktif mi | Aktif | ERP, yoksa kural | H | H | hata (kurallardan sonra) |
| Country | nvarchar(100) |  | Ülke |  | ERP | H | H | bilinmiyor |
| City | nvarchar(100) |  | Şehir |  | ERP | H | H | bilinmiyor |
| AdditionalText1–7 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da |  | ERP | H | H | yok |
| AdditionalNumber1–3 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da |  | ERP | H | H | yok |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

### MaterialSupplier
<sub>21. Veri modeli · Malzeme</sub>

- Ana veri · versiyonlu · Faz 1
- Malzeme–tedarikçi ilişkisi; satın alma parametreleri. Satın alma her zaman sürekli; yuvarlama son hesapta.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | BOŞSA |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| LocationId | int | FK,UK | Lokasyon |  | ERP | H | E | hata (satır atlanır) |
| MaterialId | bigint | FK,UK | Malzeme |  | ERP | H | E | hata (satır atlanır) |
| SupplierId | bigint | FK,UK | Tedarikçi |  | ERP | H | E | hata (satır atlanır) |
| IsActive | bit |  | Aktif mi | Aktif | ERP, yoksa kural | H | H | hata (kurallardan sonra) |
| Priority | int |  | Öncelik |  | ERP, yoksa kural | H | H | yok |
| QuotaRatio | decimal(6,4) |  | Oran olarak kota (0,30 = %30) | Kota oranı | ERP, yoksa kural | H | H | yok |
| FixedLeadTimeDays | decimal(9,2) |  | Miktardan bağımsız kısım | Sabit tedarik süresi (gün) | ERP | H | H | bilinmiyor |
| VariableLeadTimeDays | decimal(18,6) |  | Birim başına gün; miktar arttıkça uzayan kısım | Değişken tedarik süresi | ERP | H | H | bilinmiyor |
| LeadTimeBasis | nvarchar(15) |  | Takvim günü \| İş günü | Tedarik süresi esası | Kural ya da elle | H | H | tedarik süresi doluysa hata (kurallardan sonra) |
| MinimumOrderQuantity | decimal(18,4) |  | Minimum sipariş miktarı |  | ERP | H | H | yok |
| OrderLotSize | decimal(18,4) |  | Sipariş miktarı bu sayının katı olur | Sipariş katı | ERP | H | H | yok |
| MaximumOrderQuantity | decimal(18,4) |  | Maksimum | Maksimum sipariş miktarı | ERP | H | H | sınırsız |
| ValidFrom | date |  | Geçerlilik başlangıcı |  | ERP | H | H | sınırsız |
| ValidTo | date |  | Geçerlilik bitişi |  | ERP | H | H | sınırsız |
| AdditionalText1–3 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da |  | ERP | H | H | yok |
| AdditionalNumber1–2 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da |  | ERP | H | H | yok |
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
| ScenarioDefinitionId | int | FK | Senaryo |  | Smartchain (parametre) | H | E |  |
| SupplierId | bigint | FK | Tedarikçi |  | Smartchain (parametre) | H | E |  |
| MaterialId | bigint | FK | Malzeme; boşsa tedarikçinin bütün malzemeleri (yalnız kapalı dönem) |  | Smartchain (parametre) | H | H |  |
| ValidFrom | date |  | Başlangıç |  | Smartchain (parametre) | H | E |  |
| ValidTo | date |  | Bitiş |  | Smartchain (parametre) | H | E |  |
| UpperLimit | decimal(18,4) |  | Dönem üst limiti, malzemenin temel biriminde; malzeme boşsa 0 | Dönem üst limiti | Smartchain (parametre) | E | E | 0 |

### ProductionVersion
<sub>21. Veri modeli · Malzeme</sub>

- Ana veri · versiyonlu · Faz 1
- Üretim versiyonu: bir malzemenin ürün ağacı ve rota başlığı; rotaya RouteCode, ürün ağacına BOMCode ile bağlanır. Versiyon seçimi motorun kararıdır; aynı malzeme aynı dönemde birden fazla versiyonla üretilebilir.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | BOŞSA |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| LocationId | int | FK,UK | Lokasyon |  | ERP | H | E | hata (satır atlanır) |
| MaterialId | bigint | FK,UK | Üretilen malzeme |  | ERP | H | E | hata (satır atlanır) |
| Code | nvarchar(30) | UK | Versiyon kodu |  | ERP | H | E | hata (satır atlanır) |
| Name | nvarchar(100) |  | Versiyon adı |  | ERP | H | H | bilinmiyor |
| Type | nvarchar(50) |  | Versiyonları ayrıştırmak için kurallarda kullanılır; değer listesi yok | Versiyon tipi | ERP | H | H | bilinmiyor |
| IsActive | bit |  | Aktif |  | ERP, yoksa kural | H | H | hata (kurallardan sonra) |
| Priority | int |  | Versiyonlar arası tercih bilgisi; motora girdi | Öncelik | ERP | H | H | yok |
| BaseQuantity | decimal(18,4) |  | Baz miktar (rota ve ağaç bu miktar için) | Baz miktar | ERP | H | H | hata (kurallardan sonra) |
| BOMCode | nvarchar(50) |  | Versiyonun kullandığı ürün ağacı | Ürün ağacı kodu | ERP | H | E | hata (satır atlanır) |
| RouteCode | nvarchar(50) |  | Rota kodu | Rota kodu | ERP | H | E | hata (satır atlanır) |
| ValidFrom | date |  | Geçerlilik başlangıcı |  | ERP | H | H | sınırsız |
| ValidTo | date |  | Geçerlilik bitişi |  | ERP | H | H | sınırsız |
| AdditionalText1–3 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da |  | ERP | H | H | yok |
| AdditionalNumber1–2 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da |  | ERP | H | H | yok |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

### BOM
<sub>21. Veri modeli · Malzeme</sub>

- Ana veri · versiyonlu · Faz 1
- Ürün ağacı satırı.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | BOŞSA |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| LocationId | int | FK,UK | Lokasyon |  | ERP | H | E | hata (satır atlanır) |
| MaterialId | bigint | FK,UK | Üretilen malzeme |  | ERP | H | E | hata (satır atlanır) |
| Code | nvarchar(50) | UK | Ürün ağacı kodu |  | ERP | H | E | hata (satır atlanır) |
| ComponentMaterialId | bigint | FK,UK | Bileşen |  | ERP | H | E | hata (satır atlanır) |
| OperationNo | int | UK | Bağlı olduğu operasyon no (ihtiyaç tarihi için) | Operasyon no | ERP | H | H | ilk operasyon |
| SequenceNo | int | UK | Sıra no; aynı bileşen iki kez geçerse operasyon no ile ayrışır | Sıra no | ERP | H | H | bilinmiyor |
| Quantity | decimal(18,6) |  | Baz miktar için bileşen miktarı | Bileşen miktarı | ERP | H | E | hata (satır atlanır) |
| ComponentUom | nvarchar(10) | FK | Bileşen miktarının birimi; boşsa bileşenin temel biriminde kabul edilir, doluysa birim dönüşümüyle çevrilir | Bileşen birimi | ERP | H | H | temel birim |
| ScrapRatio | decimal(6,4) |  | Oran olarak fire (0,05 = %5) | Fire oranı | ERP | H | H | yok |
| IsPhantom | bit |  | Hayalet bileşen |  | ERP | H | H | yok |
| IsLotBasedUsage | bit |  | Doluysa bileşen üretilen miktardan bağımsız, her üretim lotu için sabit kullanılır; değilse birim başına | Lot bazlı kullanım | ERP | H | H | yok |
| AlternativeGroup | nvarchar(50) |  | Aynı grup koduna sahip satırlar birbirinin alternatifidir | Alternatif grubu | ERP | H | H | yok |
| AlternativePriority | int |  | Grup içindeki tercih bilgisi | Alternatif önceliği | ERP | H | H | yok |
| AdditionalText1–3 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da |  | ERP | H | H | yok |
| AdditionalNumber1–2 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da |  | ERP | H | H | yok |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

- **Versiyonla bağ (K-115):** Ürün ağacı kendi koduyla tanımlanır; üretim versiyonu ağacı `ProductionVersion.BOMCode` ile gösterir, aynı ağaç birden fazla versiyonda kullanılabilir.
- **Baz miktar:** Ağaçta yok; `Quantity`, üretim versiyonunun `BaseQuantity`'sine göre okunur. Geçerlilik tarihleri de üretim versiyonundadır.

### Routing
<sub>21. Veri modeli · Malzeme · 1/2</sub>

- Ana veri · versiyonlu · Faz 1
- Rota: her satır bir operasyon–kaynak grubu ilişkisi; sıra önce OperationNo, sonra SequenceNo. Aynı operasyonun kaynak grupları ayrı satırda, ResourceRole ile.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | BOŞSA |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| LocationId | int | FK,UK | Lokasyon |  | ERP | H | E | hata (satır atlanır) |
| RouteCode | nvarchar(50) | UK | Rota kodu |  | ERP | H | E | hata (satır atlanır) |
| OperationNo | int | UK | Operasyon no (birinci sıralama) | Operasyon no | ERP | H | E | hata (satır atlanır) |
| SequenceNo | int | UK | Operasyon içindeki alt sıra (ikinci sıralama) | Sıra no | ERP | H | E | hata (satır atlanır) |
| OperationName | nvarchar(150) |  | Operasyon adı |  | ERP | H | H | bilinmiyor |
| ResourceGroupId | bigint | FK | Kaynak grubu |  | ERP | H | E | hata (satır atlanır) |
| ResourceRole | nvarchar(10) |  | Primary \| Secondary | Kaynak rolü | ERP, yoksa kural | H | E | hata (kurallardan sonra) |
| Consumption | decimal(18,6) |  | Baz miktar için kaynak tüketimi (kaynak grubunun kapasite biriminde) | Kaynak tüketimi | ERP | H | E | hata (satır atlanır) |
| ResourceNumber | int |  | Operasyonda gruptan aynı anda kullanılan kaynak adedi | Kaynak adedi | ERP, yoksa kural | H | E | hata (kurallardan sonra) |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

- **Kaynak grubu (K-180):** Her satırda `ResourceGroupId` zorunludur; boşsa satır yüklenmez. Rotada kaynak alanı yoktur: operasyon grubun kaynaklarında yapılır, `ResourceNumber` gruptan aynı anda kullanılan kaynak sayısıdır. Kaynak adedi gruptaki kaynak sayısından büyükse ve grup pasifse doğrulamada uyarı. Tüketim grubun kapasite birimindedir.
- **İşçilik (K-116, K-180):** Rotada ayrı bir satırdır: kaynak grubu işçi grubu (`IsEmployee`), `ResourceRole` Secondary, `ResourceNumber` kişi sayısı, `Consumption` süre.

### Routing
<sub>21. Veri modeli · Malzeme · 2/2</sub>

- Ana veri · versiyonlu · Faz 1
- Rota: her satır bir operasyon–kaynak grubu ilişkisi; sıra önce OperationNo, sonra SequenceNo. Aynı operasyonun kaynak grupları ayrı satırda, ResourceRole ile.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | BOŞSA |
|---|---|---|---|---|---|---|---|---|
| IsSubcontracted | bit |  | Fason operasyon |  | ERP | H | H | yok |
| TransferQuantity | decimal(18,4) |  | Transfer partisi | Transfer miktarı | ERP | H | H | yok |
| IsActive | bit |  | Operasyon plana dahil mi | Aktif | ERP, yoksa kural | H | H | hata (kurallardan sonra) |
| IsLotBasedUsage | bit |  | Doluysa tüketim üretilen miktardan bağımsız, lot başına sabit; pratikte hazırlık süresi | Lot bazlı kullanım | ERP | H | H | yok |
| ProductionLocation | nvarchar(50) |  | Lokasyonun alt tanımı (hol, hat); ileride kısıtlar için | Üretim yeri | ERP | H | H | bilinmiyor |
| WaitingTimeHours | decimal(9,2) |  | Operasyon öncesi kuyruk beklemesi | Bekleme süresi (saat) | ERP | H | H | yok |
| TransferTimeHours | decimal(9,2) |  | Sonraki operasyona taşıma | Taşıma süresi (saat) | ERP | H | H | yok |
| AlternativeGroup | nvarchar(50) |  | Aynı gruptaki satırlar birbirinin alternatifidir | Alternatif grubu | ERP | H | H | yok |
| AlternativePriority | int |  | Grup içindeki tercih bilgisi | Alternatif önceliği | ERP | H | H | yok |
| AdditionalText1–3 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da |  | ERP | H | H | yok |
| AdditionalNumber1–2 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da |  | ERP | H | H | yok |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

### MaterialReference
<sub>21. Veri modeli · Malzeme</sub>

- Ana veri · versiyonlu · Faz 1
- Benzetilen ürün: kendi ağacı ya da rotası olmayan ürün, başka bir ürünün verisiyle planlanır.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | BOŞSA |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| LocationId | int | FK,UK | Lokasyon |  | ERP | H | E | hata (satır atlanır) |
| MaterialId | bigint | FK,UK | Benzetilen ürün |  | ERP | H | E | hata (satır atlanır) |
| ReferenceMaterialId | bigint | FK,UK | Referans ürün |  | ERP | H | E | hata (satır atlanır) |
| ReferenceProductionVersionId | bigint | FK | Referans ürünün versiyonu; boşsa motor seçer | Referans ürünün versiyonu | ERP | H | H | motor seçer |
| ValidFrom | date | UK | Geçerlilik başlangıcı |  | ERP | H | H | sınırsız |
| ValidTo | date |  | Geçerlilik bitişi |  | ERP | H | H | sınırsız |
| TimeFactor | decimal(9,4) |  | Süre çarpanı; 1,2 = %20 daha uzun | Süre çarpanı | ERP | H | H | yok |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

- **Kullanım (K-126):** Ürünün kendi geçerli versiyonu yoksa motor referans ürünün ağacını ve rotasını kullanır; motorda uygulanışı Aşama 10.

### ProjectGroup
<sub>21. Veri modeli · Malzeme</sub>

- Ana veri · versiyonlu · Faz 1
- Proje grubu (grup içi paylaşım için).

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | BOŞSA |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| Code | nvarchar(50) | UK | Grup kodu |  | ERP ya da kural | H | E | hata (satır atlanır) |
| Name | nvarchar(200) |  | Proje grubu adı |  | ERP ya da kural | H | H | bilinmiyor |
| TrackingRule | nvarchar(20) |  | Tam izolasyon \| Ortaktan beslenir \| Grup içi paylaşım | Takip kuralı | ERP ya da kural | H | H | hata (kurallardan sonra) |
| Priority | int |  | Proje grubu önceliği | Öncelik | ERP ya da kural | H | H | yok |
| IsActive | bit |  | Aktif mi | Aktif | ERP ya da kural | H | H | hata (kurallardan sonra) |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

### Project
<sub>21. Veri modeli · Malzeme</sub>

- Ana veri · versiyonlu · Faz 1
- Proje.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | BOŞSA |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| Code | nvarchar(50) | UK | Proje kodu |  | ERP ya da kural | H | E | hata (satır atlanır) |
| Name | nvarchar(200) |  | Proje adı |  | ERP ya da kural | H | H | bilinmiyor |
| ProjectGroupId | bigint | FK | Proje grubu |  | ERP ya da kural | H | H | yok |
| TrackingRule | nvarchar(20) |  | Proje bazında takip kuralı (grubu ezer) | Takip kuralı | ERP ya da kural | H | H | gruptan |
| Priority | int |  | Proje önceliği |  | ERP ya da kural | H | H | yok |
| IsActive | bit |  | Aktif mi | Aktif | ERP ya da kural | H | H | hata (kurallardan sonra) |
| AdditionalText1–7 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da |  | ERP | H | H | yok |
| AdditionalNumber1–3 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da |  | ERP | H | H | yok |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

### Customer
<sub>21. Veri modeli · Talep</sub>

- Ana veri · versiyonlu · Faz 1
- Müşteri.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | BOŞSA |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| Code | nvarchar(50) | UK | Müşteri kodu |  | ERP | H | E | hata (satır atlanır) |
| Name | nvarchar(200) |  | Ad | Müşteri adı | ERP | H | H | bilinmiyor |
| Priority | int |  | Müşteri önceliği |  | Kural ya da elle | H | H | yok |
| AllowPartialDelivery | bit |  | Kısmi teslimata izin |  | ERP, yoksa kural | H | H | hata (kurallardan sonra) |
| CustomerGroup | nvarchar(50) |  | Müşteri grubu |  | ERP | H | H | bilinmiyor |
| IsActive | bit |  | Aktif mi | Aktif | ERP, yoksa kural | H | H | hata (kurallardan sonra) |
| Country | nvarchar(100) |  | Ülke |  | ERP | H | H | bilinmiyor |
| Region | nvarchar(100) |  | Bölge |  | ERP | H | H | bilinmiyor |
| City | nvarchar(100) |  | Şehir |  | ERP | H | H | bilinmiyor |
| IsCustomTracked | bit |  | Bu müşterinin talepleri ortak havuzdan değil, müşteriye ayrılmış olarak takip edilir | Özel takip | ERP, yoksa kural | H | H | yok |
| AdditionalText1–7 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da |  | ERP | H | H | yok |
| AdditionalNumber1–3 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da |  | ERP | H | H | yok |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

### SalesOrderLine
<sub>21. Veri modeli · Talep</sub>

- İşlem verisi · versiyonlu · Faz 1
- Müşteri sipariş satırı; teklifler IsQuote ile okunur, plana dahil olmaları senaryo parametresi. Vade: teyit tarihi, yoksa istek tarihi.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | BOŞSA |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| LocationId | int | FK,UK | Lokasyon |  | ERP | H | E | hata (satır atlanır) |
| OrderNo | nvarchar(30) | UK | Sipariş no |  | ERP | H | E | hata (satır atlanır) |
| LineNo | int | UK | Satır no |  | ERP | H | E | hata (satır atlanır) |
| LineItemNo | int | UK | Alt satır no (ERP satırı kırılımlıysa) | Alt satır no | ERP | H | H | yok |
| Type | nvarchar(50) |  | ERP'den ham sipariş tipi; veri kurallarında kullanılır, değer listesi yok | Sipariş tipi | ERP | H | H | bilinmiyor |
| CustomerId | bigint | FK | Müşteri |  | ERP | H | E | hata (satır atlanır) |
| MaterialId | bigint | FK | Malzeme |  | ERP | H | E | hata (satır atlanır) |
| ProjectId | bigint | FK | Proje |  | ERP | H | H | yok |
| OpenQuantity | decimal(18,4) |  | Açık miktar |  | ERP | H | E | hata (satır atlanır) |
| OrderedQuantity | decimal(18,4) |  | Satırın orijinal miktarı | Sipariş miktarı | ERP | H | H | bilinmiyor |
| DeliveredQuantity | decimal(18,4) |  | Teslim edilen miktar |  | ERP | H | H | yok |
| Uom | nvarchar(10) | FK | Açık, sipariş ve teslim miktarının birimi; boşsa malzemenin temel biriminde kabul edilir, doluysa birim dönüşümüyle çevrilir | Sipariş birimi | ERP | H | H | temel birim |
| RequestedDate | date |  | İstek tarihi |  | ERP | H | E | hata (satır atlanır) |
| ConfirmedDate | date |  | Teyit tarihi |  | ERP | H | H | bilinmiyor |
| Priority | int |  | Satır önceliği |  | Kural ya da elle | H | H | yok |
| AllowPartialDelivery | bit |  | Kısmi teslimat (müşteriyi ezer) | Kısmi teslimat | ERP | H | H | müşteriden |
| Status | nvarchar(50) |  | ERP'den ham sipariş durumu; veri kurallarında kullanılır, değer listesi yok | Sipariş durumu | ERP | H | H | bilinmiyor |
| IsActive | bit |  | Aktif mi | Aktif | ERP, yoksa kural | H | H | hata (kurallardan sonra) |
| IsOnHold | bit |  | Kredi, teknik onay ya da müşteri talebiyle bekletilen satır | Beklemede | ERP, yoksa kural | H | H | yok |
| IsCustomTracked | bit |  | Satır düzeyinde özel takip | Özel takip | ERP, yoksa kural | H | H | yok |
| IsQuote | bit |  | Teklif satırı; Type'tan veri kuralıyla doldurulur | Teklif | ERP, yoksa kural | H | H | yok |
| AdditionalText1–3 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da |  | ERP | H | H | yok |
| AdditionalNumber1–2 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da |  | ERP | H | H | yok |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

### Forecast
<sub>21. Veri modeli · Talep</sub>

- İşlem verisi · versiyonlu · Faz 1
- Talep tahmini (netleme ön hesapta).

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | BOŞSA |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| LocationId | int | FK,UK | Lokasyon |  | ERP | H | E | hata (satır atlanır) |
| MaterialId | bigint | FK,UK | Malzeme |  | ERP | H | E | hata (satır atlanır) |
| CustomerId | bigint | FK,UK | Müşteri |  | ERP | H | H | yok |
| ProjectId | bigint | FK,UK | Proje |  | ERP | H | H | yok |
| Period | date | UK | Dönem |  | ERP | H | E | hata (satır atlanır) |
| Type | nvarchar(50) | UK | Hangisinin plana gireceği veri kuralıyla seçilir; ERP'den ham değer, değer listesi yok | Tahmin tipi | ERP | H | H | bilinmiyor |
| Quantity | decimal(18,4) |  | Miktar |  | ERP | H | E | hata (satır atlanır) |
| Uom | nvarchar(10) | FK | Miktarın birimi; boşsa malzemenin temel biriminde kabul edilir, doluysa birim dönüşümüyle çevrilir | Birim | ERP | H | H | temel birim |
| DeliveryPoint | nvarchar(10) |  | Miktarın dönemin başında mı sonunda mı hazır olması gerektiği: Başı \| Sonu | Teslim noktası | ERP, yoksa kural | H | H | hata (kurallardan sonra) |
| IsActive | bit |  | Aktif mi | Aktif | ERP, yoksa kural | H | H | hata (kurallardan sonra) |
| AdditionalText1–3 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da |  | ERP | H | H | yok |
| AdditionalNumber1–2 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da |  | ERP | H | H | yok |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

### BorrowPayback
<sub>21. Veri modeli · Arz ve stok</sub>

- İşlem verisi · versiyonlu · Faz 1
- Projeler arası ödünç ve geri ödeme kaydı: devreye almada açık olan ve ERP'de doğrudan yapılan ödünçlerin motora bildirilmesi; onaylanan öneriler de buraya yazılır.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | BOŞSA |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| LocationId | int | FK,UK | Lokasyon |  | ERP | H | E | hata (satır atlanır) |
| MaterialId | bigint | FK,UK | Malzeme |  | ERP | H | E | hata (satır atlanır) |
| LendingProjectId | bigint | FK,UK | Ödünç veren proje |  | ERP | H | E | hata (satır atlanır) |
| BorrowingProjectId | bigint | FK,UK | Ödünç alan proje |  | ERP | H | E | hata (satır atlanır) |
| BorrowedQuantity | decimal(18,4) |  | Ödünç miktarı |  | ERP | H | E | hata (satır atlanır) |
| PaidBackQuantity | decimal(18,4) |  | Geri ödenen miktar |  | ERP | H | H | yok |
| BorrowDate | date | UK | Ödünç tarihi |  | ERP | H | E | hata (satır atlanır) |
| PaybackDueDate | date |  | Geri ödeme tarihi |  | ERP | H | H | bilinmiyor |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

### Stock
<sub>21. Veri modeli · Arz ve stok</sub>

- İşlem verisi · versiyonlu · Faz 1
- Stok; lot ve durum bazında. Sahip: proje, müşteri, sipariş ya da ortak.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | BOŞSA |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| LocationId | int | FK,UK | Lokasyon |  | ERP | H | E | hata (satır atlanır) |
| MaterialId | bigint | FK,UK | Malzeme |  | ERP | H | E | hata (satır atlanır) |
| Warehouse | nvarchar(30) | UK | Depo |  | ERP | H | H | bilinmiyor |
| LotNo | nvarchar(50) | UK | Lot / seri |  | ERP | H | H | bilinmiyor |
| Status | nvarchar(50) | UK | ERP'den ham stok durumu; veri kurallarında kullanılır, değer listesi yok | Stok durumu | ERP | H | H | bilinmiyor |
| ProjectId | bigint | FK,UK | Sahip proje; proje, müşteri ve sipariş boşsa stok ortaktır | Sahip proje | ERP | H | H | yok |
| CustomerId | bigint | FK,UK | Sahip müşteri; stoğun ayrıldığı müşteri, ileride kullanılmak üzere | Sahip müşteri | ERP | H | H | yok |
| SalesOrderLineId | bigint | FK,UK | Sahip sipariş satırı; stoğun ayrıldığı sipariş satırı, ileride kullanılmak üzere | Sahip sipariş satırı | ERP | H | H | yok |
| Quantity | decimal(18,4) |  | Miktar |  | ERP | H | E | hata (satır atlanır) |
| Uom | nvarchar(10) | FK | Miktarın birimi; boşsa malzemenin temel biriminde kabul edilir, doluysa birim dönüşümüyle çevrilir | Birim | ERP | H | H | temel birim |
| QualityEntryDate | date |  | Kaliteye giriş tarihi |  | ERP | H | H | bilinmiyor |
| ExpectedAcceptanceDate | date |  | Kalitedeki stoğun kullanılabilir hâle gelmesi beklenen tarih | Beklenen kabul tarihi | ERP | H | H | bilinmiyor |
| ExpiryDate | date |  | Son kullanma tarihi (raf ömrü sonraki faz) | Son kullanma tarihi | ERP | H | H | sınırsız |
| IsAvailable | bit |  | Stok planda kullanılabilir; Status ve depoya göre veri kuralıyla doldurulur | Kullanılabilir | ERP, yoksa kural | H | H | yok |
| IsInQuality | bit |  | Stok planda kalitede sayılır; Status ve depoya göre veri kuralıyla doldurulur | Kalitede | ERP, yoksa kural | H | H | yok |
| IsBlocked | bit |  | Stok planda bloke sayılır; Status ve depoya göre veri kuralıyla doldurulur | Bloke | ERP, yoksa kural | H | H | yok |
| IsActive | bit |  | Aktif mi | Aktif | ERP, yoksa kural | H | H | hata (kurallardan sonra) |
| IsCustomTracked | bit |  | Stok düzeyinde özel takip | Özel takip | ERP, yoksa kural | H | H | yok |
| AdditionalText1–3 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da |  | ERP | H | H | yok |
| AdditionalNumber1–2 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da |  | ERP | H | H | yok |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

### WorkOrder
<sub>21. Veri modeli · Arz ve stok</sub>

- İşlem verisi · versiyonlu · Faz 1
- Açık iş emri (üretim, fason, yeniden işleme).

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | BOŞSA |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| LocationId | int | FK,UK | Lokasyon |  | ERP | H | E | hata (satır atlanır) |
| WorkOrderNo | nvarchar(30) | UK | İş emri no |  | ERP | H | E | hata (satır atlanır) |
| MaterialId | bigint | FK | Üretilen malzeme |  | ERP | H | E | hata (satır atlanır) |
| ProductionVersionId | bigint | FK | Üretim versiyonu; iş emrinin kendi bileşen ve operasyon satırları geldiyse motor onları kullanır, gelmediyse bu versiyonun ağacına ve rotasına gider | Üretim versiyonu | ERP | H | H | bilinmiyor |
| ProductionOrderType | nvarchar(50) |  | ERP'den ham iş emri tipi; veri kurallarında kullanılır, değer listesi yok | İş emri tipi | ERP | H | H | bilinmiyor |
| Status | nvarchar(50) |  | ERP'den ham iş emri durumu; veri kurallarında kullanılır, değer listesi yok | İş emri durumu | ERP | H | H | bilinmiyor |
| Priority | int |  | İş emri önceliği | Öncelik | ERP | H | H | yok |
| OrderedQuantity | decimal(18,4) |  | İş emri miktarı |  | ERP | H | E | hata (satır atlanır) |
| OpenQuantity | decimal(18,4) |  | Açık miktar |  | ERP | H | E | hata (satır atlanır) |
| CompletedQuantity | decimal(18,4) |  | Tamamlanan miktar |  | ERP | H | H | yok |
| ScrapQuantity | decimal(18,4) |  | Hurda miktarı |  | ERP | H | H | yok |
| Uom | nvarchar(10) | FK | Miktarların birimi; boşsa malzemenin temel biriminde kabul edilir, doluysa birim dönüşümüyle çevrilir | Birim | ERP | H | H | temel birim |
| StartDate | date |  | Başlangıç |  | ERP | H | H | bilinmiyor |
| DueDate | date |  | Bitiş |  | ERP | H | E | hata (satır atlanır) |
| ProjectId | bigint | FK | Proje (ayraç) | Proje | ERP | H | H | yok |
| CustomerId | bigint | FK | Müşteri |  | ERP | H | H | yok |
| SalesOrderLineId | bigint | FK | Bağlı sipariş satırı (ayraç) | Bağlı sipariş satırı | ERP | H | H | yok |
| ParentWorkOrderId | bigint | FK | Yeniden işlemede orijinal iş emri | Orijinal iş emri | Kural ya da elle | H | H | yok |
| LastActivityDate | date |  | Son hareket tarihi (eskime kontrolü) | Son hareket tarihi | ERP | H | H | bilinmiyor |
| IsFixed | bit |  | Motor bu iş emrinin tarihini ve miktarını değiştirmez | Sabit | ERP, yoksa kural | H | H | yok |
| IsReleased | bit |  | İş emri yayınlandı; Status'tan veri kuralıyla doldurulur | Yayınlandı | ERP, yoksa kural | H | H | yok |
| IsStarted | bit |  | İş emri başladı; Status'tan veri kuralıyla doldurulur | Başladı | ERP, yoksa kural | H | H | yok |
| IsProduction | bit |  | Üretim iş emri; ProductionOrderType'tan veri kuralıyla doldurulur | Üretim | ERP, yoksa kural | H | H | yok |
| IsSubcontract | bit |  | Fason iş emri; ProductionOrderType'tan veri kuralıyla doldurulur | Fason | ERP, yoksa kural | H | H | yok |
| IsRework | bit |  | Yeniden işleme iş emri; ProductionOrderType'tan veri kuralıyla doldurulur | Yeniden işleme | ERP, yoksa kural | H | H | yok |
| IsOnHold | bit |  | Bekletilen iş emri | Beklemede | ERP, yoksa kural | H | H | yok |
| IsCustomTracked | bit |  | İş emri düzeyinde özel takip | Özel takip | ERP, yoksa kural | H | H | yok |
| AdditionalText1–3 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da |  | ERP | H | H | yok |
| AdditionalNumber1–2 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da |  | ERP | H | H | yok |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

- **Kendi satırları önce (K-124):** İş emrinin kendi bileşen ve operasyon satırları geldiyse motor onları kullanır; gelmediyse `ProductionVersionId`'nin ağacına ve rotasına gider. Motorda uygulanışı 10.1.

### WorkOrderComponent
<sub>21. Veri modeli · Arz ve stok</sub>

- İşlem verisi · versiyonlu · Faz 1
- İş emrinin bileşenleri ve çekilen miktar.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | BOŞSA |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| LocationId | int | FK,UK | Lokasyon |  | ERP | H | E | hata (satır atlanır) |
| WorkOrderId | bigint | FK,UK | İş emri |  | ERP | H | E | hata (satır atlanır) |
| MaterialId | bigint | FK,UK | Bileşen |  | ERP | H | E | hata (satır atlanır) |
| OperationNo | int | UK | Bağlı olduğu operasyon no (ihtiyaç tarihi için) | Operasyon no | ERP | H | H | ilk operasyon |
| SequenceNo | int | UK | Sıra no; aynı bileşen iki kez geçerse operasyon no ile ayrışır | Sıra no | ERP | H | H | bilinmiyor |
| RequiredQuantity | decimal(18,4) |  | Gereken miktar |  | ERP | H | E | hata (satır atlanır) |
| IssuedQuantity | decimal(18,4) |  | Çekilen miktar |  | ERP | H | H | yok |
| RemainingQuantity | decimal(18,4) |  | Kalan ihtiyaç |  | Ön hesap | H | H |  |
| UnitUsage | decimal(18,6) |  | Üretilen bir birim için bileşen miktarı | Birim kullanım | ERP | H | H | bilinmiyor |
| Uom | nvarchar(10) | FK | Bileşen miktarlarının birimi; boşsa bileşenin temel biriminde kabul edilir, doluysa birim dönüşümüyle çevrilir | Birim | ERP | H | H | temel birim |
| ScrapRatio | decimal(6,4) |  | Oran olarak fire (0,05 = %5) | Fire oranı | ERP | H | H | yok |
| IsLotBasedUsage | bit |  | Doluysa bileşen üretilen miktardan bağımsız, her üretim lotu için sabit kullanılır; değilse birim başına | Lot bazlı kullanım | ERP | H | H | yok |
| IsPhantom | bit |  | Hayalet bileşen |  | ERP | H | H | yok |
| AdditionalText1–3 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da |  | ERP | H | H | yok |
| AdditionalNumber1–2 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da |  | ERP | H | H | yok |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

### WorkOrderOperation
<sub>21. Veri modeli · Arz ve stok</sub>

- İşlem verisi · versiyonlu · Faz 1
- İş emrinin operasyonları ve kalan iş.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | BOŞSA |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| LocationId | int | FK,UK | Lokasyon |  | ERP | H | E | hata (satır atlanır) |
| WorkOrderId | bigint | FK,UK | İş emri |  | ERP | H | E | hata (satır atlanır) |
| OperationNo | int | UK | Operasyon no |  | ERP | H | E | hata (satır atlanır) |
| SequenceNo | int | UK | Operasyon içindeki alt sıra | Sıra no | ERP | H | E | hata (satır atlanır) |
| OperationName | nvarchar(150) |  | Operasyon adı |  | ERP | H | H | bilinmiyor |
| ResourceGroupId | bigint | FK | Kaynak grubu |  | ERP | H | E | hata (satır atlanır) |
| ResourceRole | nvarchar(10) |  | Primary \| Secondary | Kaynak rolü | ERP, yoksa kural | H | E | hata (kurallardan sonra) |
| ResourceNumber | int |  | Operasyonda aynı anda kullanılan kaynak adedi | Kaynak adedi | ERP, yoksa kural | H | E | hata (kurallardan sonra) |
| PlannedConsumption | decimal(18,6) |  | Planlanan tüketim |  | ERP | H | H | bilinmiyor |
| ConfirmedConsumption | decimal(18,6) |  | Teyit edilen tüketim |  | ERP | H | H | yok |
| RemainingConsumption | decimal(18,6) |  | Kalan yük |  | Ön hesap | H | H |  |
| Status | nvarchar(50) |  | ERP'den ham operasyon durumu; veri kurallarında kullanılır, değer listesi yok | Operasyon durumu | ERP | H | H | bilinmiyor |
| IsCompleted | bit |  | Operasyon tamamlandı; Status'tan veri kuralıyla doldurulur | Tamamlandı | ERP, yoksa kural | H | H | yok |
| IsLotBasedUsage | bit |  | Doluysa tüketim üretilen miktardan bağımsız, lot başına sabit; pratikte hazırlık süresi | Lot bazlı kullanım | ERP | H | H | yok |
| IsSubcontracted | bit |  | Fason operasyon |  | ERP | H | H | yok |
| IsActive | bit |  | Operasyon plana dahil mi | Aktif | ERP, yoksa kural | H | H | hata (kurallardan sonra) |
| ProductionLocation | nvarchar(50) |  | Lokasyonun alt tanımı (hol, hat); ileride kısıtlar için | Üretim yeri | ERP | H | H | bilinmiyor |
| TransferQuantity | decimal(18,4) |  | Transfer partisi | Transfer miktarı | ERP | H | H | yok |
| WaitingTimeHours | decimal(9,2) |  | Operasyon öncesi kuyruk beklemesi | Bekleme süresi (saat) | ERP | H | H | yok |
| TransferTimeHours | decimal(9,2) |  | Sonraki operasyona taşıma | Taşıma süresi (saat) | ERP | H | H | yok |
| AdditionalText1–3 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da |  | ERP | H | H | yok |
| AdditionalNumber1–2 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da |  | ERP | H | H | yok |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

- **Kaynak grubu (K-124, K-180):** Rotadaki gibi her satırda `ResourceGroupId` zorunludur; boşsa satır yüklenmez. Kaynak alanı yoktur.

### PurchaseOrderLine
<sub>21. Veri modeli · Arz ve stok</sub>

- İşlem verisi · versiyonlu · Faz 1
- Açık satın alma ve fason siparişi satırı (ve talep).

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | BOŞSA |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| LocationId | int | FK,UK | Lokasyon |  | ERP | H | E | hata (satır atlanır) |
| PurchaseOrderNo | nvarchar(30) | UK | Sipariş no |  | ERP | H | E | hata (satır atlanır) |
| LineNo | int | UK | Satır no |  | ERP | H | E | hata (satır atlanır) |
| OrderType | nvarchar(50) |  | ERP'den ham sipariş tipi; veri kurallarında kullanılır, değer listesi yok | Sipariş tipi | ERP | H | H | bilinmiyor |
| SupplierId | bigint | FK | Tedarikçi |  | ERP | H | H | bilinmiyor |
| MaterialId | bigint | FK | Malzeme |  | ERP | H | E | hata (satır atlanır) |
| OpenQuantity | decimal(18,4) |  | Açık miktar |  | ERP | H | E | hata (satır atlanır) |
| OrderedQuantity | decimal(18,4) |  | Sipariş miktarı |  | ERP | H | H | bilinmiyor |
| ReceivedQuantity | decimal(18,4) |  | Teslim alınan miktar |  | ERP | H | H | yok |
| Uom | nvarchar(10) | FK | Miktarların birimi; boşsa malzemenin temel biriminde kabul edilir, doluysa birim dönüşümüyle çevrilir | Birim | ERP | H | H | temel birim |
| RequestedDate | date |  | İstenen tarih |  | ERP | H | H | bilinmiyor |
| ConfirmedDate | date |  | Tedarikçi teyit tarihi |  | ERP | H | H | bilinmiyor |
| ProjectId | bigint | FK | Proje |  | ERP | H | H | yok |
| CustomerId | bigint | FK | Müşteri |  | ERP | H | H | yok |
| SalesOrderLineId | bigint | FK | Bağlı sipariş satırı |  | ERP | H | H | yok |
| WorkOrderId | bigint | FK | Fasonda bağlı iş emri | Bağlı iş emri | ERP | H | H | yok |
| Status | nvarchar(50) |  | ERP'den ham sipariş durumu; veri kurallarında kullanılır, değer listesi yok | Durum | ERP | H | H | bilinmiyor |
| IsPurchaseRequest | bit |  | Satın alma talebi; OrderType'tan veri kuralıyla doldurulur | Satın alma talebi | ERP, yoksa kural | H | H | yok |
| IsPurchase | bit |  | Satın alma siparişi; OrderType'tan veri kuralıyla doldurulur | Satın alma | ERP, yoksa kural | H | H | yok |
| IsSubcontract | bit |  | Fason siparişi; OrderType'tan veri kuralıyla doldurulur | Fason | ERP, yoksa kural | H | H | yok |
| IsActive | bit |  | Aktif mi | Aktif | ERP, yoksa kural | H | H | hata (kurallardan sonra) |
| IsCustomTracked | bit |  | Satır düzeyinde özel takip | Özel takip | ERP, yoksa kural | H | H | yok |
| AdditionalText1–3 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da |  | ERP | H | H | yok |
| AdditionalNumber1–2 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da |  | ERP | H | H | yok |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

### TransferOrder
<sub>21. Veri modeli · Arz ve stok</sub>

- İşlem verisi · versiyonlu · Faz 1
- Açık lokasyonlar arası transfer; Faz 1'de sabit hareket (gelen arz, giden talep).

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | BOŞSA |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| OrderNo | nvarchar(30) | UK | Transfer no | ERP | H | E | hata (satır atlanır) |
| FromLocationId | int | FK | Çıkış lokasyonu | ERP | H | E | hata (satır atlanır) |
| ToLocationId | int | FK | Varış lokasyonu | ERP | H | E | hata (satır atlanır) |
| MaterialId | bigint | FK | Malzeme | ERP | H | E | hata (satır atlanır) |
| OpenQty | decimal(18,4) |  | Açık miktar | ERP | H | E | hata (satır atlanır) |
| ShipDate | date |  | Çıkış tarihi | ERP | H | H | bilinmiyor |
| ReceiptDate | date |  | Varış tarihi | ERP | H | H | bilinmiyor |
| AdditionalText1–3 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da | ERP | H | H | yok |
| AdditionalNumber1–2 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da | ERP | H | H | yok |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |

### ProductionConfirmation
<sub>21. Veri modeli · Arz ve stok</sub>

- İşlem verisi · versiyonlu · Faz 1
- Üretim gerçekleşmeleri: iş emri bazında stoğa girişler.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | BOŞSA |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| LocationId | int | FK,UK | Lokasyon |  | ERP | H | E | hata (satır atlanır) |
| ConfirmationNo | nvarchar(30) | UK | Teyit no |  | ERP | H | E | hata (satır atlanır) |
| WorkOrderId | bigint | FK | İş emri |  | ERP | H | E | hata (satır atlanır) |
| MaterialId | bigint | FK | Üretilen malzeme |  | ERP | H | E | hata (satır atlanır) |
| ConfirmedQuantity | decimal(18,4) |  | Teyit miktarı |  | ERP | H | E | hata (satır atlanır) |
| StartDate | date |  | Başlangıç |  | ERP | H | H | bilinmiyor |
| EndDate | date |  | Bitiş |  | ERP | H | H | bilinmiyor |
| AdditionalText1–3 | nvarchar(255) |  | Ek metin alanları; etiketi FieldDefinition'da |  | ERP | H | H | yok |
| AdditionalNumber1–2 | decimal(18,4) |  | Ek sayı alanları; etiketi FieldDefinition'da |  | ERP | H | H | yok |
| Ortak alanlar: VersionFrom, VersionTo, ImportBatchId, BusinessKey, UpdatedAt |  |  |  |  |  |  |  |  |

### PlanningSetting
<sub>21. Veri modeli · Parametre</sub>

- Parametre · versiyonsuz · Faz 1
- Senaryonun planlama parametreleri (anahtar–değer; K-175). Anahtarlar, tipleri, seçenekleri ve başlangıç değerleri docs/06 fonksiyon 22'deki tabloda (`app/params/catalog.py`).

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|---|
| ScenarioDefinitionId | int | PK,FK | Senaryo |  | Smartchain (parametre) | H | E |  |
| SettingKey | nvarchar(60) | PK | Parametre adı | Parametre adı | Smartchain (parametre) | H | E |  |
| Value | nvarchar(200) |  | Değer |  | Smartchain (parametre) | E | E |  |

### TimeBucketDefinition
<sub>21. Veri modeli · Parametre</sub>

- Parametre · versiyonsuz · Faz 1
- Zaman yapısı: senaryonun ufuk ve dönem dizisi. Kullanıcı tarih girmez; her satır bir parçadır: dönem tipi (dönemlerin büyüklüğü) ve kapsam (parçanın ne kadar sürdüğü). Başlangıç ve bitiş plan başlangıcına göre hesaplanır (fonksiyon 23, K-175). Raporlama ekseni ayrı diziyse `Axis` = Rapor satırları. Dönem tipleri ve kapsam birimleri iki eksende aynıdır; kapsam birimi dönem tipinden küçük olamaz (çeyrek ve yıl dönem tipinde Ay da olabilir).

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|---|
| ScenarioDefinitionId | int | PK,FK | Senaryo |  | Smartchain (parametre) | H | E |  |
| Axis | nvarchar(10) | PK | Plan \| Rapor | Eksen | Smartchain (parametre) | H | E | Plan |
| Seq | int | PK | Sıra |  | Smartchain (parametre) | H | E |  |
| BucketType | nvarchar(10) |  | Gün \| Hafta \| Ay \| Çeyrek \| Yıl | Dönem tipi | Smartchain (parametre) | H | E |  |
| Count | int |  | Kapsam: parçanın kapsam birimi cinsinden uzunluğu | Kapsam | Smartchain (parametre) | H | E |  |
| SpanUnit | nvarchar(10) |  | Gün \| Hafta \| Ay \| Çeyrek \| Yıl | Kapsam birimi | Smartchain (parametre) | H | E |  |

### ObjectiveDefinition
<sub>21. Veri modeli · Parametre</sub>

- Parametre · versiyonsuz · Faz 1
- Senaryonun hedefleri (leksikografik, ağırlık yok; K-175): motor hedefleri sırayla çözer. Senaryonun süre bütçesi aktif hedeflerin sürelerinin toplamıdır.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| ScenarioDefinitionId | int | FK,UK | Senaryo |  | Smartchain (parametre) | H | E |  |
| Code | nvarchar(30) | UK | Hedefin kodu (UNMET_DEMAND, LATENESS, UNMET_FORECAST…; fonksiyon 22) | Hedef | Smartchain (parametre) | H | E |  |
| PriorityGroup | int | UK | Sipariş öncelik grubu; boş = bütün siparişler (gruplar öncelik kuralları adımında) | Öncelik grubu | Smartchain (parametre) | H | H |  |
| Seq | int |  | Çözüm sırası; aktif hedeflerde 1'den boşluksuz, kapalı hedefte boş | Sıra | Smartchain (parametre) | H | H |  |
| TimeBudgetSeconds | int |  | Süre bütçesi (sn); kapalı hedefte boş | Süre bütçesi | Smartchain (parametre) | H | H |  |
| TolerancePct | decimal(5,2) |  | Ödün payı (%): üst hedeften verilebilecek en çok ödün; 0 = katı | Ödün payı | Smartchain (parametre) | H | H |  |
| IsActive | bit |  | Kapalı hedef çözülmez | Aktif | Smartchain (parametre) | H | H | 1 |

### PriorityRule
<sub>21. Veri modeli · Parametre</sub>

- Parametre · versiyonsuz · Faz 1
- Sıralama kuralı: kriterlerin sırası (bucket > müşteri > proje > satır > tarih).

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|---|
| ScenarioDefinitionId | int | PK,FK | Senaryo |  | Smartchain (parametre) | H | E |  |
| Seq | int | PK | Sıra |  | Smartchain (parametre) | H | E |  |
| Criterion | nvarchar(30) |  | Kriter |  | Smartchain (parametre) | E | E |  |
| Direction | nvarchar(10) |  | Artan \| Azalan | Yön | Smartchain (parametre) | H | H | Artan |

### AllocationRule
<sub>21. Veri modeli · Parametre</sub>

- Parametre · versiyonsuz · Faz 1
- Kapasite alokasyonu: talep sınıfına kaynak grubu ve dönem bazında pay (K-180).

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| ScenarioDefinitionId | int | FK | Senaryo |  | Smartchain (parametre) | H | E |  |
| DemandClass | nvarchar(100) |  | Talep sınıfı tanımı (müşteri, proje, ürün grubu) | Talep sınıfı | Smartchain (parametre) | H | E |  |
| ResourceGroupId | bigint | FK | Kaynak grubu |  | Smartchain (parametre) | H | H |  |
| ValidFrom | date |  | Başlangıç |  | Smartchain (parametre) | H | H |  |
| ValidTo | date |  | Bitiş |  | Smartchain (parametre) | H | H |  |
| SharePct | decimal(6,2) |  | Pay (%) |  | Smartchain (parametre) | E | E |  |
| Hardness | nvarchar(10) |  | Taban \| Tavan \| Yumuşak | Sınır tipi | Smartchain (parametre) | H | H | Yumuşak |

### WarningDefinition
<sub>21. Veri modeli · Parametre</sub>

- Parametre · versiyonsuz · Faz 1
- Uyarı kataloğu (K-190): sistemin tanıdığı uyarı kodları ve kategorileri. Satırları sistem yazar; eşik, önem ve aktiflik senaryoya bağlıdır (WarningThreshold).

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Code | nvarchar(30) | PK | Uyarı kodu | Sistem | H | E |  |
| Category | nvarchar(20) |  | Talep \| Malzeme \| Kapasite \| Plan kalitesi | Sistem | H | E |  |

### WarningThreshold
<sub>21. Veri modeli · Parametre</sub>

- Parametre · versiyonsuz · Faz 1
- Senaryonun uyarı eşikleri (K-190): her senaryoda her uyarı için bir satır. Kademeli: her önem için ayrı eşik; boş kademe kullanılmaz. Yön uyarıya göre sabittir ve eşik dahil değildir.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| ScenarioDefinitionId | int | FK,UK | Senaryo |  | Smartchain (parametre) | H | E |  |
| WarningCode | nvarchar(30) | FK,UK | Uyarı kodu (ORDER_LATE, CAP_OVERLOAD…; fonksiyon 26) | Uyarı | Smartchain (parametre) | H | E |  |
| ThresholdLow | decimal(18,4) |  | Düşük önemin eşiği; boşsa kademe kullanılmaz | Düşük | Smartchain (parametre) | H | H |  |
| ThresholdMedium | decimal(18,4) |  | Orta önemin eşiği; boşsa kademe kullanılmaz | Orta | Smartchain (parametre) | H | H |  |
| ThresholdHigh | decimal(18,4) |  | Yüksek önemin eşiği; boşsa kademe kullanılmaz | Yüksek | Smartchain (parametre) | H | H |  |
| ThresholdCritical | decimal(18,4) |  | Kritik önemin eşiği; boşsa kademe kullanılmaz | Kritik | Smartchain (parametre) | H | H |  |
| Severity | nvarchar(10) |  | Düşük \| Orta \| Yüksek \| Kritik | Önem | Smartchain (parametre) | H | H |  |
| IsActive | bit |  | Kapalı uyarı üretilmez; değerleri durur | Aktif | Smartchain (parametre) | H | H | 1 |

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
| ValuePriority | nvarchar(10) |  | Kullanılmıyor: öncelik sabit, manuel > kural > ERP (K-170) | Sistem | H | H | ERP ezer |
| ManualOverrides | bit |  | Manuel: manuel değer girilebilir mi (K-170); kurulumda Hayır, System owner açar; anahtar, ilişki ve sistem alanlarında açılmaz | Sistem | H | H | 0 |
| IfEmpty | nvarchar(60) |  | Boşsa: docs/02 BOŞSA'dan, geçişte güncellenir, System owner değiştirmez (K-138) | Sistem | H | H |  |
| IsRequired | bit |  | Zorunlu mu | Sistem | H | H | 0 |
| Label | nvarchar(100) |  | Ekranda görünen etiket; standart alanın etiketini ezer, ek alanda boşsa alan gösterilmez (K-88); en çok 40 karakter girilir | Sistem | H | H |  |
| StandardLabel | nvarchar(100) |  | docs'tan gelen etiket; kurulumda yazılır, System owner değiştirmez (K-104) | Sistem | H | H |  |
| Description | nvarchar(200) |  | Alan açıklaması; docs/02 AÇIKLAMA'dan, geçişte güncellenir, System owner değiştirmez (K-104) | Sistem | H | H |  |

### DataRule
<sub>21. Veri modeli · Veri yönetimi</sub>

- Veri yönetimi · versiyonsuz · Faz 1
- Veri kuralı (K-141, ekran 04): tek tablo içinde "koşul ise hedef alan = sonuç". Staging'in işlenmiş katmanında tablo başına sırayla çalışır (K-140); varsayılan kural yoktur, kurulumda eklenir.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| EntityName | nvarchar(60) | UK | Tablo (`stg` adı) | Kullanıcı | H | E |  |
| Name | nvarchar(200) | UK | Kural; tabloda tekil | Kullanıcı | H | E |  |
| Seq | int |  | Sıra: tablo başına 1'den, sonra çalışan önceki kuralın sonucunu görür, aynı alanda sonuncu kazanır | Kullanıcı | H | E |  |
| TargetField | nvarchar(60) |  | Hedef alan; anahtar alan ve sistem alanı olamaz | Kullanıcı | H | E |  |
| ResultKind | nvarchar(10) |  | Değer \| Alan \| Formül \| Boşalt | Kullanıcı | H | E |  |
| Value | nvarchar(200) |  | Değer sonucunda sabit; hedef tipine göre çözülür (sayı, tarih, bayrak 1 / 0) | Kullanıcı | H | H |  |
| SourceField | nvarchar(60) |  | Alan ve Formül sonucunda kaynak alan | Kullanıcı | H | H |  |
| FormulaOperator | nvarchar(5) |  | + \| − \| × \| ÷ (tarihte + ve − gün) | Kullanıcı | H | H |  |
| OperandValue | nvarchar(200) |  | Formülde sabit operand | Kullanıcı | H | H |  |
| OperandField | nvarchar(60) |  | Formülde alan operand | Kullanıcı | H | H |  |
| ApplyMode | nvarchar(15) |  | Yalnız boşsa \| Her zaman (Boşalt'ta Her zaman) | Kullanıcı | H | E |  |
| ConditionText | nvarchar(400) |  | Koşulun okunur cümlesi; kayıtta yazılır, koşulsuzsa boş | Sistem | H | H |  |
| ResultText | nvarchar(400) |  | Sonucun okunur cümlesi ("Tesis = Evet", "Temin süresi + 2"); kayıtta yazılır | Sistem | H | H |  |
| IsActive | bit |  | Aktif; pasif kural çalışmaz | Kullanıcı | H | E |  |
| LastRunStatus | nvarchar(15) |  | Çalıştı \| Çalışmadı | Sistem | H | H |  |
| LastRunMessage | nvarchar(400) |  | Çalışmadıysa neden | Sistem | H | H |  |
| LastRunAt | datetime2 |  | Son çalışma | Sistem | H | H |  |
| UpdatedBy | int | FK | Son değiştiren | Sistem | H | H |  |
| UpdatedAt | datetime2 |  | Son değişiklik | Sistem | H | H |  |

### DataRuleCondition
<sub>21. Veri modeli · Veri yönetimi</sub>

- Veri yönetimi · versiyonsuz · Faz 1
- Kural koşulları: aynı GroupNo'daki koşullar VE, gruplar arası VEYA (K-136); koşul editörü validasyon kurallarıyla ortaktır.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| DataRuleId | bigint | FK | Kural | Kullanıcı | H | E |  |
| GroupNo | int |  | VE grubu; gruplar arası VEYA | Kullanıcı | H | E |  |
| FieldName | nvarchar(60) |  | Alan | Kullanıcı | H | E |  |
| Operator | nvarchar(15) |  | = \| ≠ \| > \| < \| ≥ \| ≤ \| İçerir \| İle başlar \| Listede \| Boş \| Boş değil (K-139; ≠ boşu da kapsar) | Kullanıcı | H | E |  |
| Value | nvarchar(200) |  | Değer | Kullanıcı | H | H |  |
| CompareField | nvarchar(60) |  | Alan–alan karşılaştırmasında öteki alan (K-136) | Kullanıcı | H | H |  |

### DataRuleEffect
<sub>21. Veri modeli · Veri yönetimi</sub>

- Veri yönetimi · versiyonsuz · Faz 1
- Kural izi (K-140): işlenmiş katmanda hangi hücreyi hangi kuralın son değiştirdiği ve ham değer; her çalıştırmada tablo için yeniden yazılır. İpucu: "Kural 3 · Lokasyon bayrakları · ham değer: boş".

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| EntityName | nvarchar(60) | PK | Tablo (`stg` adı) | Sistem | H | E |  |
| StagingRowId | bigint | PK | Satır; ham ve işlenmiş katmanda aynı | Sistem | H | E |  |
| FieldName | nvarchar(60) | PK | Alan | Sistem | H | E |  |
| DataRuleId | bigint |  | Hücreyi son değiştiren kural | Sistem | H | E |  |
| RawValue | nvarchar(200) |  | Ham katmandaki değer, okunur biçimde; boşsa boş | Sistem | H | H |  |

### ManualValue
<sub>21. Veri modeli · Veri yönetimi</sub>

- Veri yönetimi · versiyonsuz · Faz 1
- Manuel değer (K-170): ana veri ve işlem verisinde kayıt ve alan başına; kuralı ve ERP'yi ezer, aktarımda korunur, süresi yoktur. Alttaki değer (ERP ya da kural sonucu) girişte ve her aktarımda saklanır; kaldırılınca hücreye son alttaki değer döner. Değerler alanın tipinden metne çevrilmiş hâldedir.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| TableName | nvarchar(60) | UK | Tablo (core adı) | Sistem | H | E |  |
| RecordKey | nvarchar(60) | UK | Kaydın kimliği: Id, bütün versiyonlarda aynı (K-63); birimde kod | Sistem | H | E |  |
| FieldName | nvarchar(60) | UK | Alan | Sistem | H | E |  |
| Value | nvarchar(200) |  | Manuel değer; boş olabilir (zorunlu olmayan alanda) | Kullanıcı | H | H |  |
| BaseValue | nvarchar(200) |  | Manuel değer girildiğindeki alttaki değer | Sistem | H | H |  |
| UnderlyingValue | nvarchar(200) |  | Son aktarımdaki alttaki değer; kaldırılınca hücreye döner | Sistem | H | H |  |
| UnderlyingSource | nvarchar(10) |  | Alttaki değerin kaynağı: ERP \| Kural | Sistem | H | E | ERP |
| UnderlyingRuleId | bigint |  | Alttaki değeri veren kural | Sistem | H | H |  |
| IsBaseChanged | bit |  | Alttaki değer manuel değer girildiğinden beri güncellendi mi ("Var / ERP Güncellendi", "Var / Kural Güncellendi") | Sistem | H | E | 0 |
| CreatedBy | int | FK | Giren kullanıcı | Sistem | H | E |  |
| CreatedAt | datetime2 |  | Giriş zamanı | Sistem | H | E |  |
| UpdatedBy | int | FK | Son değiştiren | Sistem | H | E |  |
| UpdatedAt | datetime2 |  | Son değişiklik | Sistem | H | E |  |

### FieldChange
<sub>21. Veri modeli · Veri yönetimi</sub>

- Veri yönetimi · versiyonsuz · Faz 1
- Alan değişikliği (K-173): ana veri ve işlem verisinde kaydın alanı her değiştiğinde, değişiklik anında aynı işlemde yazılır; detay kartının Geçmiş sekmesi buradan okunur. Yazanlar aktarım, manuel değer girme ve kaldırma ve Smartchain girişleridir. Değerler alanın tipinden metne çevrilmiş hâldedir. Silinmez.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| TableName | nvarchar(60) |  | Tablo (core adı) | Sistem | H | E |  |
| RecordKey | nvarchar(60) | IX | Kaydın kimliği: Id, bütün versiyonlarda aynı (K-63); birimde kod | Sistem | H | E |  |
| FieldName | nvarchar(60) |  | Alan; kayıt oluştu ya da kapandı satırında boş | Sistem | H | H |  |
| ChangeType | nvarchar(10) |  | Oluştu \| Değişti \| Kapandı | Sistem | H | E |  |
| OldValue | nvarchar(400) |  | Eski değer (metin) | Sistem | H | H |  |
| NewValue | nvarchar(400) |  | Yeni değer (metin) | Sistem | H | H |  |
| DataVersionId | bigint |  | Değişikliğin olduğu veri versiyonu; Smartchain girişinde o anki güncel versiyon | Sistem | H | H |  |
| At | datetime2 |  | Zaman (UTC) | Sistem | H | E |  |
| Source | nvarchar(40) |  | Aktarım \| Manuel değer \| Manuel değer kaldırma \| Kapasite yönetimi \| Malzeme blokajı | Sistem | H | E |  |
| UserId | int |  | Değiştiren kullanıcı; aktarımda aktarımı başlatan, zamanlanmış işte boş | Sistem | H | H |  |
| DataRuleId | bigint |  | Aktarımda hücreyi değiştiren kural | Sistem | H | H |  |
| Note | nvarchar(100) |  | Not (ör. "Manuel değer korundu") | Sistem | H | H |  |

### FieldValueSource
<sub>21. Veri modeli · Veri yönetimi</sub>

- Veri yönetimi · versiyonsuz · Faz 1
- Geçerli değerin kaynağı ve ERP değeri (ezilse bile saklanır).

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| TableName | nvarchar(60) | PK | Tablo | Sistem | H | E |  |
| RecordId | bigint | PK | Kayıt | Sistem | H | E |  |
| FieldName | nvarchar(60) | PK | Alan | Sistem | H | E |  |
| Source | nvarchar(10) |  | ERP \| Kural \| Elle (K-138) | Sistem | H | E |  |
| DataRuleId | bigint | FK | Uygulanan kural | Sistem | H | H |  |
| ErpValue | nvarchar(200) |  | ERP'den gelen değer | Sistem | H | H |  |

### ImportBatch
<sub>21. Veri modeli · Veri yönetimi</sub>

- Veri yönetimi · versiyonsuz · Faz 1
- Ham veri partisi: her yükleme parti numarası, zaman ve kaynakla. Ham veri saklama süresi kadar saklanır (`RawDataRetentionDays`; boşsa temizlik çalışmaz, K-156); parti kaydı ve sayıları silinmez. LoadType Değişen: arayüzde "Ekle / güncelle" (K-129).

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| Method | nvarchar(10) |  | API \| Excel \| SQL | Sistem | H | E |  |
| EntityName | nvarchar(60) |  | Varlık | Sistem | H | E |  |
| LoadType | nvarchar(10) |  | Tam \| Değişen | Sistem | H | E |  |
| ReceivedAt | datetime2 |  | Alınma zamanı | Sistem | H | E |  |
| Status | nvarchar(15) |  | Ön kontrol \| Alındı \| Doğrulandı \| Hatalı \| Yüklendi \| Tamamlanmadı \| Vazgeçildi | Sistem | H | E |  |
| RowCount | int |  | Satır sayısı | Sistem | H | H |  |
| ErrorCount | int |  | Hatalı satır | Sistem | H | H |  |
| UploadedBy | int | FK | Yükleyen kullanıcı; Excel yüklemesinde ve elle çekimde dolu | Sistem | H | H |  |
| FileName | nvarchar(255) |  | Yüklenen dosyanın adı | Sistem | H | H |  |
| FilePath | nvarchar(400) |  | Sunucuda saklanan dosyanın yolu | Sistem | H | H |  |
| TemplateVersion | int |  | Dosyanın şablon sürümü | Sistem | H | H |  |
| JobId | bigint |  | Büyük dosyada ön kontrol işi; SQL partisinde çekim işi | Sistem | H | H |  |
| SourceObject | nvarchar(128) |  | SQL partisinde okunan view | Sistem | H | H |  |
| SignalId | bigint |  | SQL partisinde okunan `ERP_LoadLog` satırı | Sistem | H | H |  |
| AppliedAt | datetime2 |  | Partinin güncel hâle işlendiği zaman (UTC); Dünden bugüne karşılaştırması buna göre | Sistem | H | H |  |
| RawDeletedAt | datetime2 |  | Ham verinin silindiği zaman; temizlik partinin güncel olmayan satırlarını, bulgularını ve dosyasını siler (UTC) | Sistem | H | H |  |

### ImportFinding
<sub>21. Veri modeli · Veri yönetimi</sub>

- Veri yönetimi · versiyonsuz · Faz 1
- Partinin ön kontrol bulguları (fonksiyon 03). Validasyon (fonksiyon 04) partiye değil staging'in güncel hâline aittir, bulguları `ValidationFinding`'dedir (K-134).

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| ImportBatchId | bigint | FK,IX | Parti | Sistem | H | E |  |
| RowNo | int |  | Dosyadaki satır no; dosya düzeyi bulguda boş | Sistem | H | H |  |
| Severity | nvarchar(10) |  | Hata \| Uyarı \| Bilgi | Sistem | H | E |  |
| CheckCode | nvarchar(30) |  | Kontrolün kodu | Sistem | H | E |  |
| FieldName | nvarchar(200) |  | Alanın etiketi; tekrar eden anahtarda boş | Sistem | H | H |  |
| Value | nvarchar(255) |  | Dosyadaki değer | Sistem | H | H |  |
| Message | nvarchar(400) |  | Sorun | Sistem | H | E |  |
| RowKey | nvarchar(200) |  | Kaydın anahtarı | Sistem | H | H |  |

### IntegrationEntity
<sub>21. Veri modeli · Veri yönetimi</sub>

- Veri yönetimi · versiyonsuz · Faz 1
- Tablo başına çekim ayarı (K-130). Satır yoksa ya da yöntem boşsa tablo Excel sayılır, çekim açıktır.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| EntityName | nvarchar(60) | PK | Tablo (`stg` adı) | Sistem | H | E |  |
| Method | nvarchar(10) |  | Excel \| SQL | Kullanıcı | H | H |  |
| IsPullEnabled | bit |  | Çekim açık; kapalıysa SQL çekimi bu tabloyu atlar, Excel yükleme etkilenmez | Kullanıcı | H | E | 1 |
| DisabledReason | nvarchar(400) |  | Çekimin kapatılma sebebi | Kullanıcı | H | H |  |
| DisabledBy | int | FK | Çekimi kapatan | Sistem | H | H |  |
| DisabledAt | datetime2 |  | Çekimin kapatıldığı zaman | Sistem | H | H |  |
| ViewName | nvarchar(128) |  | Entegrasyon veritabanındaki view | Kullanıcı | H | H |  |
| ErrorThresholdPct | decimal(5,2) |  | Hata eşiği (%); boşsa eşik kontrolü yapılmaz, varsayılanı yok (K-135) | Kullanıcı | H | H |  |
| LastCheckAt | datetime2 |  | Son uyum denetimi | Sistem | H | H |  |
| LastCheckStatus | nvarchar(20) |  | Uyumlu \| Uyarılı \| Hatalı | Sistem | H | H |  |
| LastCheckMessage | nvarchar(400) |  | Son denetimin özeti | Sistem | H | H |  |
| MatchedColumns | int |  | Uyan sözleşme kolonu | Sistem | H | H |  |
| ExpectedColumns | int |  | Sözleşme kolonu | Sistem | H | H |  |
| LastContractHash | nvarchar(32) |  | Son denetimdeki sözleşme özeti; değiştiyse yeniden denetlenir | Sistem | H | H |  |
| LastPullAt | datetime2 |  | Son okuma | Sistem | H | H |  |
| LastPullStatus | nvarchar(40) |  | Son çekim durumu | Sistem | H | H |  |
| LastPullMessage | nvarchar(400) |  | Son çekim durumunun nedeni | Sistem | H | H |  |
| UpdatedBy | int | FK | Son değiştiren | Sistem | H | H |  |
| UpdatedAt | datetime2 |  | Son değişiklik | Sistem | H | H |  |

### IntegrationViewVersion
<sub>21. Veri modeli · Veri yönetimi</sub>

- Veri yönetimi · versiyonsuz · Faz 1
- View'ın sürüm geçmişi (K-130): tanım değişince yeni sürüm. Smartchain view oluşturmaz, yalnız okur ve saklar.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| EntityName | nvarchar(60) | IX | Tablo | Sistem | H | E |  |
| ViewName | nvarchar(128) |  | View | Sistem | H | E |  |
| VersionNo | int |  | Sürüm numarası | Sistem | H | E |  |
| DefinitionHash | nvarchar(64) |  | Tanımın özeti | Sistem | H | E |  |
| Definition | nvarchar(max) |  | View tanımı; şifrelenmiş view'da boş | Sistem | H | H |  |
| SeenAt | datetime2 |  | İlk görüldüğü zaman | Sistem | H | E |  |
| AppVersion | nvarchar(20) |  | Smartchain sürümü | Sistem | H | E |  |

### ValidationRule
<sub>21. Veri modeli · Veri yönetimi</sub>

- Veri yönetimi · versiyonsuz · Faz 1
- Validasyon kuralı (K-136, ekran 27). Yapısal kontroller ve hazır kurallar koddaki katalogdan kurulur (geçişte eksik olan eklenir; sınıfı ve aktifliği kullanıcıda kalır); kullanıcı kuralı ekrandan eklenir.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | int | PK | Kayıt kimliği | Sistem | H | E |  |
| EntityName | nvarchar(60) | UK | Tablo (`stg` adı) | Sistem | H | E |  |
| Code | nvarchar(60) | UK | Yapısal ve hazır kuralda katalog kodu (ör. BOM.SELF); kullanıcı kuralında KUL-n | Sistem | H | E |  |
| Name | nvarchar(200) |  | Kural; hazır kuralda kullanıcı dilinde ad (K-139) | Kullanıcı | H | E |  |
| Kind | nvarchar(10) |  | Yapısal \| Hazır \| Kullanıcı | Sistem | H | E |  |
| CheckType | nvarchar(20) |  | Yapısal \| Mantıksal \| Tablolar arası | Sistem | H | E |  |
| Severity | nvarchar(10) |  | Hata \| Uyarı \| Bilgi | Kullanıcı | H | E |  |
| TrackQuality | bit |  | Veri kalitesinde takip (K-174): Uyarı kuralı yüklenmiş veride (`core`) çalışır, bulgusu veri kalitesi uyarısı olur; yalnız Uyarı'da anlamlı. İlk değer katalogdan, kullanıcıda kalır; "İlk hâline döndür" sıfırlar | Kullanıcı | H | E | 0 |
| Message | nvarchar(400) |  | Bulguda görünen mesaj | Kullanıcı | H | E |  |
| ConditionText | nvarchar(400) |  | Koşulun okunur cümlesi; hazır kuralda katalogdan, kullanıcı kuralında kayıtta yazılır | Sistem | H | H |  |
| IsActive | bit |  | Aktif; yapısal kontrol kapatılamaz | Kullanıcı | H | E |  |
| IsCustomized | bit |  | Hazır kural düzenlendi: ad, mesaj ve koşul kullanıcıda, katalog ezmez; "İlk hâline döndür" sıfırlar (K-139) | Sistem | H | E |  |
| UpdatedBy | int | FK | Son değiştiren | Sistem | H | H |  |
| UpdatedAt | datetime2 |  | Son değişiklik | Sistem | H | H |  |

### ValidationRuleCondition
<sub>21. Veri modeli · Veri yönetimi</sub>

- Veri yönetimi · versiyonsuz · Faz 1
- Kullanıcı kuralının ve düzenlenmiş hazır kuralın koşulları (K-136, K-139): aynı GroupNo'daki koşullar VE, gruplar arası VEYA. Operatörler `DataRuleCondition` ile aynıdır.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| ValidationRuleId | int | FK | Kural | Sistem | H | E |  |
| GroupNo | int |  | VE grubu; gruplar arası VEYA | Kullanıcı | H | E |  |
| FieldName | nvarchar(60) |  | Alan | Kullanıcı | H | E |  |
| Operator | nvarchar(15) |  | = \| ≠ \| > \| < \| ≥ \| ≤ \| İçerir \| İle başlar \| Listede \| Boş \| Boş değil (K-139; ≠ boşu da kapsar) | Kullanıcı | H | E |  |
| Value | nvarchar(400) |  | Değer; Listede'de virgülle ayrılmış liste | Kullanıcı | H | H |  |
| CompareField | nvarchar(60) |  | Alan–alan karşılaştırmasında öteki alan; doluysa Value boştur | Kullanıcı | H | H |  |

### ValidationRun
<sub>21. Veri modeli · Veri yönetimi</sub>

- Veri yönetimi · versiyonsuz · Faz 1
- Tablo başına validasyon çalışması (K-134): çipin durumu son çalışmadan, sonucu bulgulardan okunur.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| EntityName | nvarchar(60) | IX | Tablo; tablolar arası toplu çalışmada boş | Sistem | H | H |  |
| Scope | nvarchar(15) |  | Tablo içi \| Tablolar arası | Sistem | H | E |  |
| TriggerType | nvarchar(20) |  | Yükleme \| Çekim \| Toplu çekim \| Yeniden valide et \| Kural değişikliği (K-142) | Sistem | H | E |  |
| BatchId | bigint |  | Çalışmayı başlatan parti (`ImportBatch.Id`); FK yok, ham veri temizliğinde parti silinse de çalışma kalır | Sistem | H | H |  |
| JobId | bigint |  | Çalışmanın işi | Sistem | H | H |  |
| GroupId | bigint | IX | Toplu çekimde çekim işinin Id'si; tablolar arası çalışma grubun çekimi ve bütün tablo içi çalışmaları bitince başlar (K-134) | Sistem | H | H |  |
| State | nvarchar(20) |  | Sırada \| Kurallar çalışıyor \| Valide ediliyor \| Bitti \| Valide edilemedi | Sistem | H | E |  |
| CurrentRows | int |  | Güncel kayıt sayısı | Sistem | H | H |  |
| ErrorRows | int |  | Hata bulunan güncel kayıt | Sistem | H | H |  |
| WarningRows | int |  | Uyarı bulunan güncel kayıt | Sistem | H | H |  |
| InfoRows | int |  | Bilgi bulunan güncel kayıt | Sistem | H | H |  |
| RequestedBy | int | FK | Başlatan kullanıcı; otomatik zincirde partiyi alan | Sistem | H | H |  |
| CreatedAt | datetime2 |  | Sıraya girdiği zaman | Sistem | H | E |  |
| StartedAt | datetime2 |  | Başlangıç | Sistem | H | H |  |
| FinishedAt | datetime2 |  | Bitiş | Sistem | H | H |  |

### ValidationFinding
<sub>21. Veri modeli · Veri yönetimi</sub>

- Veri yönetimi · versiyonsuz · Faz 1
- Staging'in güncel hâlinin validasyon bulguları (K-134). Bir kural yeniden çalışınca o kuralın o tablodaki bulguları yenilenir; güncel hâlden çıkan satırın bulguları silinir. Ön kontrol bulguları `ImportFinding`'dedir.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| EntityName | nvarchar(60) | IX | Satırın tablosu | Sistem | H | E |  |
| StagingRowId | bigint | IX | Güncel satır; tablo düzeyi bulguda boş | Sistem | H | H |  |
| ValidationRuleId | int | FK,IX | Kural | Sistem | H | E |  |
| Severity | nvarchar(10) |  | Hata \| Uyarı \| Bilgi (bulgu anındaki sınıf) | Sistem | H | E |  |
| FieldName | nvarchar(60) |  | Alan | Sistem | H | H |  |
| Value | nvarchar(255) |  | Alanın değeri | Sistem | H | H |  |
| Message | nvarchar(400) |  | Sorun | Sistem | H | E |  |
| RowKey | nvarchar(200) |  | Kaydın anahtarı | Sistem | H | H |  |
| RunId | bigint | FK | Bulguyu yazan çalışma | Sistem | H | E |  |

### DataQualityWarning
<sub>21. Veri modeli · Veri yönetimi</sub>

- Veri yönetimi · versiyonsuz · Faz 1
- Veri kalitesi uyarısı (K-174, ekran 05): yüklenmiş veride (`core`) takipli Uyarı kuralı ya da Smartchain verisi kontrolüyle bulunan sorun. Kimliği kural + kayıt; her kontrolde var olan uyarı devam eder, sorun kalkınca (yok sayılmış olsa da) silinir.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| Source | nvarchar(12) |  | Kural \| Smartchain | Sistem | H | E |  |
| ValidationRuleId | int | FK,IX | Kural; Smartchain kontrolünde boş | Sistem | H | H |  |
| CheckCode | nvarchar(60) | UK | Kuralın kodu (MS.NO_LEADTIME, KUL-3) ya da Smartchain kontrolünün kodu (SC.RES_NO_CAPACITY) | Sistem | H | E |  |
| EntityName | nvarchar(60) | UK | Tablo (core adı) | Sistem | H | E |  |
| RecordKey | nvarchar(60) | UK | Kaydın kimliği: Id (K-63); birimde kod | Sistem | H | E |  |
| RecordLabel | nvarchar(200) |  | Ekrandaki Kayıt: iş anahtarı alan etiketleriyle (ör. Malzeme: HAM-012 · Tedarikçi: TED-03) | Sistem | H | E |  |
| RuleName | nvarchar(200) |  | Kontrol: kuralın ya da Smartchain kontrolünün adı | Sistem | H | E |  |
| Message | nvarchar(400) |  | Mesaj | Sistem | H | E |  |
| FixField | nvarchar(60) |  | Kural oluştur'un hedef alanı; boşsa Kural oluştur pasif | Sistem | H | H |  |
| Importance | nvarchar(10) |  | Yüksek \| Normal (her kontrolde yeniden) | Sistem | H | E |  |
| State | nvarchar(15) |  | Yeni \| Açık \| Yok sayıldı | Sistem | H | E |  |
| FirstSeenAt | datetime2 |  | Tespit tarihi: uyarının ilk çıktığı kontrol (UTC) | Sistem | H | E |  |
| LastSeenAt | datetime2 |  | Son kontrolde görülme (UTC) | Sistem | H | E |  |
| IgnoreReason | nvarchar(400) |  | Yok sayma gerekçesi | Kullanıcı | H | H |  |
| IgnoredBy | int | FK | Yok sayan | Sistem | H | H |  |
| IgnoredAt | datetime2 |  | Yok sayma zamanı (UTC); sonrasında kayıt değişirse (FieldChange) uyarı yeniden Açık | Sistem | H | H |  |

### DemandChain
<sub>21. Veri modeli · Veri yönetimi</sub>

- Veri yönetimi · versiyonsuz · Faz 1
- Talep zinciri kümesi (K-174): açık satış siparişi ve ufuktaki tahminden ulaşılan kayıtlar; her veri kalitesi kontrolünde baştan hesaplanır. Uyarının önemi buradan (kayıt ya da malzemesi kümedeyse Yüksek).

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| EntityName | nvarchar(60) | PK | Tablo (core adı) | Sistem | H | E |  |
| RecordId | bigint | PK | Kaydın Id'si | Sistem | H | E |  |

### DemandChainPath
<sub>21. Veri modeli · Veri yönetimi</sub>

- Veri yönetimi · versiyonsuz · Faz 1
- Detay kartının Talep zinciri sekmesi (K-174): kart açılınca uyarının kaydından yukarı çıkılarak bulunan talepler ve malzeme yolları; uyarı başına en çok 1.000 yol. Önbellektir: her veri kalitesi kontrolünde silinir.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| WarningId | bigint | IX | Uyarı | Sistem | H | E |  |
| DemandEntity | nvarchar(60) |  | SalesOrderLine \| Forecast | Sistem | H | E |  |
| DemandId | bigint |  | Talebin Id'si | Sistem | H | E |  |
| DemandLabel | nvarchar(100) |  | Talep (SO-1182 / 1; MAM-001 · Ara 2026) | Sistem | H | E |  |
| DemandType | nvarchar(20) |  | Satış siparişi \| Tahmin | Sistem | H | E |  |
| MaterialPath | nvarchar(400) |  | Malzeme yolu (MAM-002 → ALT-001 → HAM-012) | Sistem | H | E |  |
| DemandDate | date |  | Talep tarihi (istek tarihi ya da tahmin dönemi) | Sistem | H | E |  |
| OpenQuantity | decimal(18,6) |  | Açık miktar | Sistem | H | E |  |

### stg.*
<sub>21. Veri modeli · Veri yönetimi</sub>

- Entegrasyon · versiyonsuz · Faz 1
- Entegrasyon tabloları: her varlık için bir tane (stg.Material…). ERP'nin dili: Id yok, ilişkiler kodla. API, SQL ve Excel buraya iner. Ham katmandır, hiç değişmez (K-140).

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| StagingRowId | bigint | PK | Satır kimliği | Sistem | H | E |  |
| ImportBatchId | bigint | FK | Yükleme partisi | Sistem | H | E |  |
| IsCurrent | bit |  | Tablonun güncel hâlinde mi (K-133); güncel hâlde anahtar bir kez bulunur | Sistem | H | E |  |
| ErrorText | nvarchar(400) |  | Hata açıklaması (ör. bilinmeyen MaterialCode) | Sistem | H | H |  |
| …Code | nvarchar(50) | REF | İlişkiler kodla (LocationCode, MaterialCode…); aktarımda Id'ye eşlenir | ERP | H | E |  |
| … |  |  | Varlığın sözleşme alanları ve ek alanları (26. adım) | ERP | H |  |  |

### prc.*
<sub>21. Veri modeli · Veri yönetimi</sub>

- Entegrasyon · versiyonsuz · Faz 1
- İşlenmiş staging (K-140): her `stg` tablosunun aynı alanlı kopyası (prc.Material…). Her çalıştırmada boşaltılır, ham katmanın güncel satırları (`IsCurrent = 1`) kopyalanır, veri kuralları sırayla bu kopyada çalışır (K-141). Validasyon ve load yalnız bu katmanı okur. Bu katmandaki her satır günceldir; `IsCurrent` yoktur.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| StagingRowId | bigint | PK | Ham satırın kimliği (kopyalanır, kimlik değil) | Sistem | H | E |  |
| ImportBatchId | bigint | FK | Satırın geldiği parti | Sistem | H | E |  |
| SourceRowNo | int |  | Kaynaktaki satır no | Sistem | H | H |  |
| RowStatus | nvarchar(15) |  | Yeni \| Hatalı \| Aktarıldı; Hata bulgusu varsa Hatalı, load almaz (K-134) | Sistem | H | E | Yeni |
| … |  |  | `stg` tablosunun sözleşme alanları ve ek alanları; kurallar bunları değiştirir | Kural | H |  |  |

### DataVersion
<sub>21. Veri modeli · Veri yönetimi</sub>

- Veri yönetimi · versiyonsuz · Faz 1
- Aktarım ile oluşan dondurulmuş veri versiyonu; tam ya da kısmi (K-152).

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| LocationId | int | FK | Lokasyon; tam aktarım bütün lokasyonları kapsar, boş (K-153) | ERP | H | H |  |
| CreatedAt | datetime2 |  | Oluşma zamanı | Sistem | H | E |  |
| LoadType | nvarchar(10) |  | Tam \| Kısmi | Sistem | H | E |  |
| CreatedBy | int | FK | Kullanıcı ya da sistem kullanıcısı | Sistem | H | H |  |
| IsPinned | bit |  | Onaylı plana bağlı; silinmez | Sistem | H | H | 0 |
| IsSynthetic | bit |  | Sentetik veri (geliştirme ve demo); sentetik veri komutları yalnız bunlara dokunur (K-79) | Sistem | H | H | 0 |
| JobId | bigint |  | Aktarım işi; versiyonu açan iş (`Job.Id`), veri aktarım geçmişi ve raporu buradan bağlanır | Sistem | H | H |  |

### DataVersionEntity
<sub>21. Veri modeli · Veri yönetimi</sub>

- Veri yönetimi · versiyonsuz · Faz 1
- Aktarımda hangi tabloların aktarıldığı (kısmi aktarımda seçilen grupların tabloları).

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| DataVersionId | bigint | PK,FK | Veri versiyonu | Sistem | H | E |  |
| EntityName | nvarchar(60) | PK | Varlık | Sistem | H | E |  |
| ImportBatchId | bigint | FK | Kaynak parti | Sistem | H | H |  |
| NewCount | int |  | Yeni kayıt sayısı (K-151) | Sistem | H | H |  |
| ChangedCount | int |  | Güncellenen kayıt sayısı | Sistem | H | H |  |
| ClosedCount | int |  | Silinen (kapatılan) kayıt sayısı | Sistem | H | H |  |
| NotTransferredCount | int |  | Aktarılmayan satır sayısı (Hatalı, zorunlu ilişkisi çevrilemeyen) | Sistem | H | H |  |
| Note | nvarchar(400) |  | Tek satır not: eşik aşıldı, veri gelmedi, ana verisi aktarılmadı (K-151) | Sistem | H | H |  |

### RawCompare
<sub>21. Veri modeli · Veri yönetimi</sub>

- Veri yönetimi · versiyonsuz · Faz 1
- Dünden bugüne (K-160): tablo başına ham verinin son hâli ile önceki günün son hâlinin karşılaştırma özeti. Yükleme sonrası hesaplanır.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| EntityName | nvarchar(60) | PK | Tablo | Sistem | H | E |  |
| TodayAt | datetime2 |  | Son verinin işlendiği zaman (UTC) | Sistem | H | E |  |
| YesterdayAt | datetime2 |  | Önceki günün son verisinin işlendiği zaman (UTC); yoksa boş | Sistem | H | H |  |
| TodayLoad | nvarchar(20) |  | Tam \| Ekle / güncelle \| Karma | Sistem | H | E |  |
| YesterdayRows | int |  | Dünkü satır sayısı | Sistem | H | H |  |
| TodayRows | int |  | Bugünkü satır sayısı | Sistem | H | E |  |
| NewCount | int |  | Yeni gelen kayıt sayısı | Sistem | H | H |  |
| MissingCount | int |  | Dün gelip bugün gelmeyen kayıt sayısı | Sistem | H | H |  |
| ChangedCount | int |  | Güncellenen kayıt sayısı | Sistem | H | H |  |
| State | nvarchar(20) |  | Hazır \| Önceki veri yok \| Hesaplanamadı | Sistem | H | E |  |
| ComputedAt | datetime2 |  | Hesap zamanı (UTC) | Sistem | H | E |  |

### RawCompareRow
<sub>21. Veri modeli · Veri yönetimi</sub>

- Veri yönetimi · versiyonsuz · Faz 1
- Dünden bugüne (K-160): yeni gelen, gelmeyen ve güncellenen kayıtlar; güncellenen kayıtta değişen alan başına bir satır. Tablonun her hesabında yeniden yazılır.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| EntityName | nvarchar(60) | IX | Tablo | Sistem | H | E |  |
| Kind | nvarchar(15) |  | Yeni \| Gelmeyen \| Güncellenen | Sistem | H | E |  |
| StagingRowId | bigint |  | Ham satır: yeni gelende bugünkü, gelmeyende dünkü, güncellenende bugünkü satır | Sistem | H | E |  |
| RowKey | nvarchar(200) |  | Kayıt: tablonun anahtar alanları | Sistem | H | E |  |
| FieldLabel | nvarchar(200) |  | Alan; yalnız güncellenende dolu | Sistem | H | H |  |
| OldValue | nvarchar(400) |  | Dünkü değer | Sistem | H | H |  |
| NewValue | nvarchar(400) |  | Bugünkü değer | Sistem | H | H |  |

### ScenarioDefinition
<sub>21. Veri modeli · Plan</sub>

- Parametre · versiyonsuz · Faz 1
- Senaryo tanımı (K-175): parametrelerinin tamamını kendisi taşır (PlanningSetting, TimeBucketDefinition, ObjectiveDefinition ve senaryoya bağlı öteki tablolar); senaryolar arasında paylaşılan set yoktur. Kurulumda tek senaryo "Baz" gelir; silinemez, pasif yapılamaz.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|---|
| Id | int | PK | Tanım kimliği |  | Sistem | H | E |  |
| LocationId | int | FK | Lokasyon; Baz kurulumda veri gelmeden açıldığı için boş olabilir |  | ERP | H | H |  |
| Name | nvarchar(100) | UK | Senaryo adı |  | Kullanıcı | H | E |  |
| IsBase | bit |  | Baz senaryo: silinemez, pasif yapılamaz; tek kayıtta Evet | Baz senaryo | Sistem | H | H | 0 |
| IsActive | bit |  | Aktif; pasif senaryo bağlam çubuğundaki listede görünmez ve gece çalışmaz, parametreleri durur (K-177) | Aktif | Kullanıcı | H | H | 1 |
| FollowsBase | bit |  | Baz'ı izler: veri tablolarında Baz'ın değerlerini okur, yalnız farkını tutar (K-176); Baz'da boş; Hayır'a dönen senaryo yeniden bağlanmaz | Baz'ı izler | Kullanıcı | H | H |  |
| RunsNightly | bit |  | Gece çalışsın: kapalı senaryo yeniden açılana kadar gece akışında hesaplanmaz (K-177) | Gece çalışsın | Kullanıcı | H | H | 0 |
| NightlyPriority | int |  | Gece sırası: gece çalışan senaryolar arasında 1'den boşluksuz; gece çalışmayanda boş | Gece sırası | Kullanıcı | H | H |  |
| IsSynthetic | bit |  | Sentetik veri (geliştirme ve demo); sentetik veri komutları yalnız bunlara dokunur (K-79) |  | Sistem | H | H | 0 |

### Scenario
<sub>21. Veri modeli · Plan</sub>

- Plan · versiyonsuz · Faz 1
- Senaryo sonucu: bir senaryonun bir veri versiyonuyla hesaplanmış planı. Bir sonraki gece silinmez, saklanır; saklama süresi sistem ayarıdır (K-177; ekranda "plan versiyonu").

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
| ScenarioDefinitionId | int | FK | Senaryo tanımı: hesabın parametreleri | Sistem | H | E |  |
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
- Kaynak grubu ve dönem bazında kapasite ve kapasite yükü (plan ve yük grup düzeyindedir, K-180).

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| PlanRunId | bigint | FK | Plan hesabı | Motor | H | E |  |
| ResourceGroupId | bigint | FK | Kaynak grubu | Motor | H | E |  |
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
| ScenarioDefinitionId | int |  | Kullanıcının son seçtiği senaryo (K-177); boşsa, senaryo pasifse ya da silinmişse Baz açılır | Kullanıcı | H | H |  |

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
- İş kuyruğu (SQL Server tablosu): gece senaryoları, çalışma hesapları, aktarımlar.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği | Sistem | H | E |  |
| JobType | nvarchar(20) |  | Gece senaryosu \| Çalışma \| Aktarım \| Termin sorgusu \| Dışa aktarım \| Excel ön kontrol \| Veri çekme \| Validasyon \| Temizlik \| Veri kalitesi … | Sistem | H | E |  |
| Channel | nvarchar(15) |  | Gece \| Hesaplama \| Excel \| Veri çekme \| Veri işleme | Sistem | H | E |  |
| Priority | int |  | Öncelik | Sistem | H | H |  |
| Status | nvarchar(15) |  | Sırada \| Çalışıyor \| Bitti \| Hata \| İptal | Sistem | H | E |  |
| RequestedBy | int | FK | Başlatan | Sistem | H | H |  |
| Payload | nvarchar(max) |  | İş parametreleri (JSON) | Sistem | H | H |  |
| Result | nvarchar(max) |  | İşin sonucu (JSON); Veri çekme: tablo başına durum (K-130) | Sistem | H | H |  |
| DismissedAt | datetime2 |  | Kullanıcı bildirimi kapattı; yeniden çıkmaz (K-132) | Sistem | H | H |  |
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
| ScenarioName | nvarchar(100) |  | Senaryoya bağlı işlemde senaryonun adı (K-177); veri yönetimi işlemlerinde boş. Ad olarak saklanır: senaryo silinse de iz okunur | Sistem | H | H |  |

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
  - `JobLimitExport`: Excel kanalında aynı anda çalışan iş (2; K-93, K-129)
  - `JobLimitPull`: Veri çekme kanalında aynı anda çalışan iş (1; K-130)
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
- Zamanlanmış işler (K-163, K-164; fonksiyon 92, Sistem ayarları → Zamanlanmış işler): `FlowWaitMinutes`: elle başlatılmış işin bitmesini ve servisin geri gelmesini bekleme (60; 5–720); `FlowRefreshWaitMinutes`: ERP yenilemesinin bitmesini bekleme (120; 5–720).
- Ham veri temizliği (K-156; fonksiyon 09): `RawDataRetentionDays`: ham verinin saklama süresi, gün (1–30); varsayılan yok, boşsa temizlik çalışmaz.
- Excel yükleme (K-129; fonksiyon 03): `ImportSyncMaxMb`: bu boyuta kadar ön kontrol istek içinde, üstü iş kuyruğunda (5); `ImportMaxMb`: en büyük dosya (100); `ImportMaxRows`: bir dosyada en çok satır (200000).
- SQL çekimi (K-130; fonksiyon 01, 91): `IntegrationDatabase`: entegrasyon veritabanının adı, boşsa SQL yolu kapalı; `PullRetryWaitSeconds`: geçici hatada denemeler arası bekleme (30).
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

### TableViewStandard
<sub>21. Veri modeli · Sistem</sub>

- Sistem · versiyonsuz · Faz 1
- Şirket Standart görünümü (K-162): System owner ya da Admin'in kaydettiği Standart, liste başına tek satır. Satır yoksa liste tanımındaki Standart geçerlidir.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| ListName | nvarchar(60) | PK | Liste adı | Sistem | H | E |  |
| Definition | nvarchar(max) |  | Görünüm içeriği; JSON, sürümlü (docs/08) | Kullanıcı | H | E |  |
| KnownFields | nvarchar(max) |  | Kaydedildiği anda listedeki alanlar; JSON. Sonradan eklenen alan ürünün varsayılanına göre gelir | Sistem | H | E |  |
| UpdatedAt | datetime2 |  | Son değişiklik zamanı | Sistem | H | E |  |
| UpdatedBy | int | FK | Kaydeden | Kullanıcı | H | E |  |

### Flow
<sub>21. Veri modeli · Sistem</sub>

- Sistem · versiyonsuz · Faz 1
- Zamanlanmış iş (K-163, K-164): zaman, Veri çek kapsamı, aktarım türü, isteğe bağlı temizlik. Adımların sırası sabittir.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | int | PK | Zamanlanmış iş kimliği | Sistem | H | E |  |
| Name | nvarchar(100) | UK | Zamanlanmış işin adı | Kullanıcı | H | E |  |
| IsActive | bit |  | Aktif | Kullanıcı | H | E | 1 |
| RunTime | nvarchar(5) |  | Saat (SS:DD, sunucunun yerel saati) | Kullanıcı | H | E |  |
| Days | nvarchar(20) |  | Haftanın günleri; 1 Pazartesi … 7 Pazar, virgülle | Kullanıcı | H | E |  |
| PullScope | nvarchar(10) |  | Tümü \| Seçilen | Kullanıcı | H | E |  |
| PullTables | nvarchar(max) |  | Seçilen SQL tabloları; JSON | Kullanıcı | H | H |  |
| TransferMode | nvarchar(10) |  | Tam \| Kısmi | Kullanıcı | H | E |  |
| TransferGroups | nvarchar(200) |  | Kısmi aktarımın grupları; JSON | Kullanıcı | H | H |  |
| Cleanup | bit |  | Ham veri temizliği adımı | Kullanıcı | H | E | 0 |
| NextRunAt | datetime2 |  | Sıradaki saat (UTC); kaydederken ve zamanlayıcının her turunda hesaplanır, pasifte boş (K-164) | Sistem | H | H |  |
| UpdatedAt | datetime2 |  | Son değişiklik zamanı (UTC) | Sistem | H | E |  |
| UpdatedBy | int | FK | Değiştiren | Kullanıcı | H | E |  |

### FlowRun
<sub>21. Veri modeli · Sistem</sub>

- Sistem · versiyonsuz · Faz 1
- Zamanlanmış işin her çalıştırması (K-163): zaman, adım, durum ve nedeni, işler, veri versiyonu.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Çalıştırma kimliği | Sistem | H | E |  |
| FlowId | int | FK,IX | Zamanlanmış iş | Sistem | H | E |  |
| FlowName | nvarchar(100) |  | Çalıştığı andaki adı | Sistem | H | E |  |
| TriggerType | nvarchar(15) |  | Zamanlanmış \| Elle | Sistem | H | E |  |
| ScheduledAt | datetime2 |  | Saati (UTC) | Sistem | H | E |  |
| StartedAt | datetime2 |  | Başlama (UTC) | Sistem | H | H |  |
| EndedAt | datetime2 |  | Bitiş (UTC) | Sistem | H | H |  |
| State | nvarchar(15) |  | Bekliyor \| Çalışıyor \| Bitti \| Durdu \| Başlamadı | Sistem | H | E |  |
| Step | nvarchar(20) |  | Başlangıç \| Veri çekme \| Validasyon \| Aktarım \| Temizlik | Sistem | H | E |  |
| Reason | nvarchar(400) |  | Durma ya da başlamama nedeni; bitende not | Sistem | H | H |  |
| Detail | nvarchar(max) |  | Adım ayrıntısı; JSON (tablo durumları, yeniden çekim) | Sistem | H | H |  |
| PullJobId | bigint |  | Son çekim işi | Sistem | H | H |  |
| TransferJobId | bigint |  | Aktarım işi | Sistem | H | H |  |
| CleanupJobId | bigint |  | Temizlik işi | Sistem | H | H |  |
| DataVersionId | bigint |  | Açılan veri versiyonu | Sistem | H | H |  |
| RequestedBy | int | FK | Elle başlatan | Kullanıcı | H | H |  |

### FlowRunDismissal
<sub>21. Veri modeli · Sistem</sub>

- Sistem · versiyonsuz · Faz 1
- Kullanıcının kapattığı zamanlanmış iş bildirimi (K-163); kapatılan çip o kullanıcıda yeniden görünmez.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| FlowRunId | bigint | PK,FK | Çalıştırma | Sistem | H | E |  |
| UserId | int | PK,FK | Kullanıcı | Sistem | H | E |  |
| DismissedAt | datetime2 |  | Kapatma zamanı (UTC) | Sistem | H | E |  |

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

## Kapasite girişleri (7.9, K-185)

Kapasitenin girişleri Kapasite yönetimi ekranında (ekran 30) girilir; `param` şemasında, senaryoludur ve "Baz + fark" tutulur (K-176). Her giriş kaynak grubu ya da kaynak içindir (tam biri dolu). Baz'ın satırları temel veridir; Baz'ı izleyen senaryo yalnız farkını tutar: fark satırı Baz satırını `BaseRowId` ile gösterir, değiştirdiği alanlar `OverriddenFields`'tadır; senaryonun kendi satırında `BaseRowId` boştur. Geçerli satırlar tek yerden çözülür (`app/params/resolve.py`). Kaynak ve kaynak grubu kimlikleri versiyonlu tabloya fiziksel bağ taşımaz (K-63).

### WorkPattern
<sub>21. Veri modeli · Kaynak</sub>

- Parametre · versiyonsuz · Faz 1
- Çalışma düzeni (K-185): günlük kapasite ve haftanın günleri. Çalışma günü yalnız buradan gelir. Geçerlilik: önce seviye (kaynakta o günü kapsayan kayıt varsa kaynağınkiler, yoksa grubunkiler), sonra başlangıcı en ileri olan.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| ScenarioDefinitionId | int | FK | Senaryo |  | Smartchain (parametre) | H | E |  |
| BaseRowId | bigint |  | Baz'ı izleyen senaryoda Baz'daki satırın farkıysa o satırın kimliği; senaryonun kendi satırında ve Baz'da boş | Baz satırı | Sistem | H | H |  |
| OverriddenFields | nvarchar(400) |  | Fark satırında senaryonun değiştirdiği alanların adları (virgüllerle çevrili: ",ValidTo,DailyCapacity,"); yalnız bu alanlar senaryodan, gerisi Baz satırından okunur | Değişen alanlar | Sistem | H | H |  |
| IsValid | bit |  | Geçerli (K-176): Hayır ise kayıt bu senaryoda uygulanmaz ("Geçersiz yap") | Geçerli | Smartchain (parametre) | H | E | 1 |
| ResourceGroupId | bigint | FK | Kaynak grubu (gruba girilen kayıt); kaynak doluysa boş | Kaynak grubu | Smartchain (parametre) | H | H |  |
| ResourceId | bigint | FK | Kaynak (kaynağa girilen kayıt); grup doluysa boş | Kaynak | Smartchain (parametre) | H | H |  |
| ValidFrom | date |  | Başlangıç | Başlangıç | Smartchain (parametre) | E | E |  |
| ValidTo | date |  | Bitiş (dahil); boşsa süresiz | Bitiş | Smartchain (parametre) | E | H |  |
| DailyCapacity | decimal(18,4) |  | Tam çalışma günündeki kapasite, kaynak başına, grubun kapasite biriminde; yarım günde yarısı | Günlük kapasite | Smartchain (parametre) | E | E |  |
| DayMon | decimal(2,1) |  | Pazartesi: 1 Tam · 0,5 Yarım · 0 Çalışılmıyor | Pazartesi | Smartchain (parametre) | E | E | 1 |
| DayTue | decimal(2,1) |  | Salı: 1 Tam · 0,5 Yarım · 0 Çalışılmıyor | Salı | Smartchain (parametre) | E | E | 1 |
| DayWed | decimal(2,1) |  | Çarşamba: 1 Tam · 0,5 Yarım · 0 Çalışılmıyor | Çarşamba | Smartchain (parametre) | E | E | 1 |
| DayThu | decimal(2,1) |  | Perşembe: 1 Tam · 0,5 Yarım · 0 Çalışılmıyor | Perşembe | Smartchain (parametre) | E | E | 1 |
| DayFri | decimal(2,1) |  | Cuma: 1 Tam · 0,5 Yarım · 0 Çalışılmıyor | Cuma | Smartchain (parametre) | E | E | 1 |
| DaySat | decimal(2,1) |  | Cumartesi: 1 Tam · 0,5 Yarım · 0 Çalışılmıyor | Cumartesi | Smartchain (parametre) | E | E | 0 |
| DaySun | decimal(2,1) |  | Pazar: 1 Tam · 0,5 Yarım · 0 Çalışılmıyor | Pazar | Smartchain (parametre) | E | E | 0 |
| UpdatedAt | datetime2 |  | Son değişiklik zamanı (UTC) |  | Sistem | H | E |  |
| UpdatedBy | int |  | Son değiştiren kullanıcı; sentetik ve geçişle gelen satırda boş | Değiştiren | Sistem | H | H |  |

### ResourceEfficiency
<sub>21. Veri modeli · Kaynak</sub>

- Parametre · versiyonsuz · Faz 1
- Verimlilik (K-185): kapasite katsayısı, yüzde. Giriş yoksa %100. Geçerlilik kuralı çalışma düzenindeki gibi, kendi kayıtlarından.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| ScenarioDefinitionId | int | FK | Senaryo |  | Smartchain (parametre) | H | E |  |
| BaseRowId | bigint |  | Baz'ı izleyen senaryoda Baz'daki satırın farkıysa o satırın kimliği; senaryonun kendi satırında ve Baz'da boş | Baz satırı | Sistem | H | H |  |
| OverriddenFields | nvarchar(400) |  | Fark satırında senaryonun değiştirdiği alanların adları (virgüllerle çevrili: ",ValidTo,DailyCapacity,"); yalnız bu alanlar senaryodan, gerisi Baz satırından okunur | Değişen alanlar | Sistem | H | H |  |
| IsValid | bit |  | Geçerli (K-176): Hayır ise kayıt bu senaryoda uygulanmaz ("Geçersiz yap") | Geçerli | Smartchain (parametre) | H | E | 1 |
| ResourceGroupId | bigint | FK | Kaynak grubu (gruba girilen kayıt); kaynak doluysa boş | Kaynak grubu | Smartchain (parametre) | H | H |  |
| ResourceId | bigint | FK | Kaynak (kaynağa girilen kayıt); grup doluysa boş | Kaynak | Smartchain (parametre) | H | H |  |
| ValidFrom | date |  | Başlangıç | Başlangıç | Smartchain (parametre) | E | E |  |
| ValidTo | date |  | Bitiş (dahil); boşsa süresiz | Bitiş | Smartchain (parametre) | E | H |  |
| EfficiencyPct | decimal(6,2) |  | Verimlilik (%) | Verimlilik (%) | Smartchain (parametre) | E | E | 100 |
| UpdatedAt | datetime2 |  | Son değişiklik zamanı (UTC) |  | Sistem | H | E |  |
| UpdatedBy | int |  | Son değiştiren kullanıcı; sentetik ve geçişle gelen satırda boş | Değiştiren | Sistem | H | H |  |

### ResourceGroupConstraint
<sub>21. Veri modeli · Kaynak</sub>

- Parametre · versiyonsuz · Faz 1
- Model kısıtları (K-189): kaynak grubu başına, tarihsiz iki değer. Kısıtsız kapasite çarpanı: Kaynak kısıtı = Kısıtsız olan senaryoda grubun dönem üst sınırı = kullanılabilir kapasite × çarpan (boşsa sınır yok). Hedef doluluk: kesin sınır değil, "Hedef doluluğun üstü" hedefinin eşiği (boşsa hedef yok). Yalnız kritik gruplarda uygulanır; kritik olmaktan çıkan grubun değeri saklanır ama uygulanmaz. Senaryo ve kaynak grubu başına en çok bir kendi satırı; iki değeri de boş kalan satır silinir.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| ScenarioDefinitionId | int | FK | Senaryo |  | Smartchain (parametre) | H | E |  |
| BaseRowId | bigint |  | Baz'ı izleyen senaryoda Baz'daki satırın farkıysa o satırın kimliği; senaryonun kendi satırında ve Baz'da boş | Baz satırı | Sistem | H | H |  |
| OverriddenFields | nvarchar(400) |  | Fark satırında senaryonun değiştirdiği alanların adları (virgüllerle çevrili: ",TargetUtilizationPct,"); yalnız bu alanlar senaryodan, gerisi Baz satırından okunur | Değişen alanlar | Sistem | H | H |  |
| IsValid | bit |  | Ortak yapı gereği durur; bu tabloda her zaman Evet (değer boşaltılarak kaldırılır) | Geçerli | Smartchain (parametre) | H | E | 1 |
| ResourceGroupId | bigint | FK | Kaynak grubu | Kaynak grubu | Smartchain (parametre) | H | E |  |
| UnconstrainedCapacityFactor | decimal(9,4) |  | Kısıtsız kapasite çarpanı (en az 1); boşsa sınır yok | Kısıtsız kapasite çarpanı | Smartchain (parametre) | E | H |  |
| TargetUtilizationPct | decimal(6,2) |  | Hedef doluluk, yüzde (0'dan büyük, en çok 100); boşsa hedef yok | Hedef doluluk (%) | Smartchain (parametre) | E | H |  |
| UpdatedAt | datetime2 |  | Son değişiklik zamanı (UTC) |  | Sistem | H | E |  |
| UpdatedBy | int |  | Son değiştiren kullanıcı; sentetik ve geçişle gelen satırda boş | Değiştiren | Sistem | H | H |  |

### OvertimeLimit
<sub>21. Veri modeli · Kaynak</sub>

- Parametre · versiyonsuz · Faz 1
- Ek mesai limiti (K-185): çalışılan günde kaynak başına yapılabilecek ek mesai, grubun kapasite biriminde. Giriş yoksa ek mesai yok. Her gruba girilebilir. ERP'den gelen kalan fazla mesai (kaynakta) ayrıdır, birleştirilmez.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| ScenarioDefinitionId | int | FK | Senaryo |  | Smartchain (parametre) | H | E |  |
| BaseRowId | bigint |  | Baz'ı izleyen senaryoda Baz'daki satırın farkıysa o satırın kimliği; senaryonun kendi satırında ve Baz'da boş | Baz satırı | Sistem | H | H |  |
| OverriddenFields | nvarchar(400) |  | Fark satırında senaryonun değiştirdiği alanların adları (virgüllerle çevrili: ",ValidTo,DailyCapacity,"); yalnız bu alanlar senaryodan, gerisi Baz satırından okunur | Değişen alanlar | Sistem | H | H |  |
| IsValid | bit |  | Geçerli (K-176): Hayır ise kayıt bu senaryoda uygulanmaz ("Geçersiz yap") | Geçerli | Smartchain (parametre) | H | E | 1 |
| ResourceGroupId | bigint | FK | Kaynak grubu (gruba girilen kayıt); kaynak doluysa boş | Kaynak grubu | Smartchain (parametre) | H | H |  |
| ResourceId | bigint | FK | Kaynak (kaynağa girilen kayıt); grup doluysa boş | Kaynak | Smartchain (parametre) | H | H |  |
| ValidFrom | date |  | Başlangıç | Başlangıç | Smartchain (parametre) | E | E |  |
| ValidTo | date |  | Bitiş (dahil); boşsa süresiz | Bitiş | Smartchain (parametre) | E | H |  |
| DailyLimit | decimal(18,4) |  | Günlük ek mesai limiti, kaynak başına | Günlük limit | Smartchain (parametre) | E | E |  |
| UpdatedAt | datetime2 |  | Son değişiklik zamanı (UTC) |  | Sistem | H | E |  |
| UpdatedBy | int |  | Son değiştiren kullanıcı; sentetik ve geçişle gelen satırda boş | Değiştiren | Sistem | H | H |  |

### ResourceDowntime
<sub>21. Veri modeli · Kaynak</sub>

- Parametre · versiyonsuz · Faz 1
- Bakım ve duruş (K-185): kapasiteden düşülür. Gruba girilen duruş grubun bütün kaynaklarına uygulanır. Geçerlilik kuralının dışındadır: duruşlar birleşir, gün bir kez düşer. Çalışan izni ERP'den gelir (`core.EmployeeAbsence`), burada tutulmaz.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| ScenarioDefinitionId | int | FK | Senaryo |  | Smartchain (parametre) | H | E |  |
| BaseRowId | bigint |  | Baz'ı izleyen senaryoda Baz'daki satırın farkıysa o satırın kimliği; senaryonun kendi satırında ve Baz'da boş | Baz satırı | Sistem | H | H |  |
| OverriddenFields | nvarchar(400) |  | Fark satırında senaryonun değiştirdiği alanların adları (virgüllerle çevrili: ",ValidTo,DailyCapacity,"); yalnız bu alanlar senaryodan, gerisi Baz satırından okunur | Değişen alanlar | Sistem | H | H |  |
| IsValid | bit |  | Geçerli (K-176): Hayır ise kayıt bu senaryoda uygulanmaz ("Geçersiz yap") | Geçerli | Smartchain (parametre) | H | E | 1 |
| ResourceGroupId | bigint | FK | Kaynak grubu (gruba girilen kayıt); kaynak doluysa boş | Kaynak grubu | Smartchain (parametre) | H | H |  |
| ResourceId | bigint | FK | Kaynak (kaynağa girilen kayıt); grup doluysa boş | Kaynak | Smartchain (parametre) | H | H |  |
| StartDate | date |  | Başlangıç | Başlangıç | Smartchain (parametre) | E | E |  |
| EndDate | date |  | Bitiş (dahil) | Bitiş | Smartchain (parametre) | E | E |  |
| DowntimeType | nvarchar(20) |  | Planlı bakım \| Arıza \| Diğer | Tip | Smartchain (parametre) | E | E |  |
| Reason | nvarchar(255) |  | Sebep (serbest metin) | Sebep | Smartchain (parametre) | E | H |  |
| UpdatedAt | datetime2 |  | Son değişiklik zamanı (UTC) |  | Sistem | H | E |  |
| UpdatedBy | int |  | Son değiştiren kullanıcı; sentetik ve geçişle gelen satırda boş | Değiştiren | Sistem | H | H |  |

### FactoryCalendar
<sub>21. Veri modeli · Kaynak</sub>

- Parametre · versiyonsuz · Faz 1
- Fabrika takvimi (K-185): bütün kaynak gruplarına uygulanan toplu duruş (tatil, toplu izin, yarım gün). Tek günde başlangıç ve bitiş aynıdır.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ETİKET | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|---|
| Id | bigint | PK | Kayıt kimliği |  | Sistem | H | E |  |
| ScenarioDefinitionId | int | FK | Senaryo |  | Smartchain (parametre) | H | E |  |
| BaseRowId | bigint |  | Baz'ı izleyen senaryoda Baz'daki satırın farkıysa o satırın kimliği; senaryonun kendi satırında ve Baz'da boş | Baz satırı | Sistem | H | H |  |
| OverriddenFields | nvarchar(400) |  | Fark satırında senaryonun değiştirdiği alanların adları (virgüllerle çevrili: ",ValidTo,DailyCapacity,"); yalnız bu alanlar senaryodan, gerisi Baz satırından okunur | Değişen alanlar | Sistem | H | H |  |
| IsValid | bit |  | Geçerli (K-176): Hayır ise kayıt bu senaryoda uygulanmaz ("Geçersiz yap") | Geçerli | Smartchain (parametre) | H | E | 1 |
| StartDate | date |  | Başlangıç | Başlangıç | Smartchain (parametre) | E | E |  |
| EndDate | date |  | Bitiş (dahil) | Bitiş | Smartchain (parametre) | E | E |  |
| Name | nvarchar(100) |  | Ad (ör. Yılbaşı) | Ad | Smartchain (parametre) | E | E |  |
| DayValue | decimal(2,1) |  | O günlerde çalışılan oran: 0 Çalışılmıyor · 0,5 Yarım gün | Çalışma | Smartchain (parametre) | E | E | 0 |
| UpdatedAt | datetime2 |  | Son değişiklik zamanı (UTC) |  | Sistem | H | E |  |
| UpdatedBy | int |  | Son değiştiren kullanıcı; sentetik ve geçişle gelen satırda boş | Değiştiren | Sistem | H | H |  |

## Önbellek (7.8, K-184)

Önbellek tabloları veri değildir: girişlerden hesaplanan ara sonuçtur, kullanıcıya tablo olarak sunulmaz, üzerinde giriş yapılmaz, silinirse yeniden üretilir (`python -m app.periods rebuild`). Ayrı şemada (`cache`) dururlar; yedekten dönüşte boş olmaları sorun değildir. Dış anahtar taşımazlar (yazma ucuz kalsın); bütünlüğü önbellek kodu sağlar (`app/periods/cache.py`).

### ResourceCapacityDay
<sub>21. Veri modeli · Önbellek</sub>

- Önbellek · versiyonsuz · Faz 1
- Kaynak grubu × kaynak × gün kapasite ara sonucu (K-184, K-185): dönem tablosu "Kaynak grubu × dönem" bundan toplanır. Grup kaydı o grubun içinde uygulandığı için birden fazla gruba üye kaynak her grubunda ayrı satırdır. Yalnız planlama ufkundaki günler; Baz'ı izleyen senaryoda yalnız Baz'dan farklı çıkan satırlar (gerisi Baz'ın satırlarından okunur). Kümelenmiş anahtar senaryo, kaynak, grup, gün: tek kaynağın yenilenmesi ve senaryonun gün aralığı okuması aynı sıradan.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| ScenarioDefinitionId | int | PK | Senaryo | Sistem | H | E |  |
| ResourceId | bigint | PK | Kaynak | Sistem | H | E |  |
| ResourceGroupId | bigint | PK | Kaynak grubu | Sistem | H | E |  |
| Date | date | PK | Gün | Sistem | H | E |  |
| WorkingDay | decimal(2,1) |  | Çalışma günü (Tam 1, Yarım 0,5, Çalışılmıyor 0; çalışma düzeni yoksa 0) | Sistem | H | E |  |
| Downtime | decimal(5,4) |  | Duruş (gün; çalışma gününü aşmaz) | Sistem | H | E |  |
| DailyCapacity | decimal(18,4) |  | O gün geçerli günlük kapasite (çalışma düzeni yoksa 0) | Sistem | H | E |  |
| Capacity | decimal(18,4) |  | Toplam kapasite: çalışma günü × günlük kapasite × verimlilik | Sistem | H | E |  |
| AvailableCapacity | decimal(18,4) |  | Kullanılabilir kapasite: (çalışma günü − duruş) × günlük kapasite × verimlilik | Sistem | H | E |  |
| OvertimeLimit | decimal(18,4) |  | Ek mesai limiti: (çalışma günü − duruş) × günlük limit | Sistem | H | E |  |

### PeriodCacheState
<sub>21. Veri modeli · Önbellek</sub>

- Önbellek · versiyonsuz · Faz 1
- Önbelleğin durumu (K-184): önbellek ve senaryo başına tek satır. Satır yoksa önbellek kurulmamıştır; hesap kodunun sürümü ya da veri versiyonu farklıysa önbellek düşürülüp yeniden kurulur; gün aralığı ufkun gerisinde kaldıysa geçmiş günler temizlenir, ufuk ilerlediyse yalnız eksik günler hesaplanır.

| ALAN | TIP | ANAHTAR | AÇIKLAMA | ANA KAYNAK | ÇALIŞ. | ZOR. | VARSAYILAN |
|---|---|---|---|---|---|---|---|
| CacheName | nvarchar(60) | PK | Önbelleğin adı (ör. resource-capacity-day) | Sistem | H | E |  |
| ScenarioDefinitionId | int | PK | Senaryo | Sistem | H | E |  |
| CodeVersion | int |  | Hesap kodunun sürümü | Sistem | H | E |  |
| DataVersionId | int |  | Kurulduğu veri versiyonu | Sistem | H | H |  |
| DateFrom | date |  | Tutulan ilk gün | Sistem | H | E |  |
| DateTo | date |  | Tutulan son gün | Sistem | H | E |  |
| BuiltAt | datetime2 |  | Son tam kurulum zamanı (UTC) | Sistem | H | E |  |
