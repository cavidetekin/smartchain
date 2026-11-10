# Entegrasyon ve veri sözleşmesi (MDD adım 26)

Kaynak: Master Design Document (MDD) 26.10.2026. Bu dosya desteden üretilmiştir; değişiklik önce burada yapılır, deste dilim sonlarında buradan güncellenir (K-54).

### 26. Entegrasyon tasarımı
<sub>tamamlandı</sub>

- **Ne yapılacak:** ERP bağımsız, tek veri sözleşmesi, yöntemler (SQL view ve Excel; API Faz 2). İlkeler, mimari, varlık ve alan düzeyi sözleşme, yöntem detayları, eşleme ve dönüşüm, veri sahipliği, zamanlama, hata yönetimi, çıkış, güvenlik, devreye alma, raporlar için ek veri. Çıktı: entegrasyon tasarımı ve veri sözleşmesi
  - Bu adımın slaytları
  - 01 İlkeler
  - 02 Mimari ve veri akışı
  - 03–04 Varlık listesi
  - 05–35 Entegrasyon tabloları (stg.*)
  - 36–38 Üç yöntem · API, SQL, Excel
  - 39–42 Eşleme, sahiplik, zamanlama, hata
  - 43–46 Çıkış, güvenlik, devreye alma
  - 47–48 Ek veri (A-22), açık konular
- **Kararlar**
  - K-46  Tek veri sözleşmesi: şablon, SQL view'ları ve API şeması aynı sözleşmeye bağlıdır; çekim yöntemi tablo başına tektir, Excel'den yükleme her zaman açıktır (K-130).
  - K-47  Faz 1 yalnız okuma; plan çıktıları Excel listesi olarak ERP'ye elle girilir. Faz 2'de API ile geri yazma (yalnız yeni belge).
  - K-48  ERP ana veri ve işlem verisinde master; Kapasite tanımları (günlük kapasite, verim…) entegre edilmez, Smartchain ekranında tanımlanır (K-117); entegre edilen alanlarda ERP değeri FieldValueSource'ta saklanır.
  - K-49  SQL ham tablolarını müşteri ETL'i doldurur; Smartchain ERP veritabanına doğrudan girmez (K-130).
- **Açık konular**
  - A-23  Artımlı çekimde silinen kayıtlar: API'de açık (11.5); SQL her zaman tam okur (K-130).
  - A-24  ERP belge numarası ↔ Smartchain öneri bağı: ERP'de dış referans alanı var mı?
  - A-25  Kapandı (K-130): rota tüketim birimi dönüşümü view'da.

### Entegrasyon tasarım ilkeleri
<sub>26. Entegrasyon tasarımı · Entegrasyon ilkeleri</sub>

- **Tek veri sözleşmesi:** Hangi yöntemle gelirse gelsin veri aynı sözleşmeye (varlık, alan, tip, anahtar, zorunluluk) iner. Sözleşme bu dosyadaki `stg.*` tablolarıdır; şablon ve API şeması bu kaynaktan türer, SQL view'ları buna uyar. `FieldDefinition` yalnız etiket verir (K-110).
- **ERP bağımsız:** Ürün hiçbir ERP'ye özel alan taşımaz. ERP'ye özgü her şey adaptörde ve eşleme tanımında kalır; yeni ERP yeni adaptör demektir, ürün değişmez.
- **Yalnız okuma (Faz 1):** Smartchain ERP'den okur, ERP'ye yazmaz. Plan çıktıları Excel listesi olarak çıkar ve ERP'ye elle girilir. Geri yazma Faz 2 (API).
- **Yöntemler (K-130):** Faz 1'de SQL view ve Excel; API Faz 2 (11.5). Çekim yöntemi tablo başına tektir, müşteriye göre seçilir, karışık kurulum normaldir (ör. siparişler SQL, kaynaklar Excel). Excel'den yükleme yöntemden bağımsız her zaman açıktır; partide yöntem kayıtlı kalır, yükleme en yeni partiyi alır (5.2).
- **Ham veri önce, dönüşüm sonra:** Gelen veri önce olduğu gibi ham tablolara (Staging) yazılır; doğrulama ve dönüşüm sonra. Sorunlu yükleme geriye dönük incelenebilir, ham veri 1 hafta saklanır.
- **Staging iki katman (K-140):** Ham katman (`stg.<Tablo>`) gelen veridir, hiç değişmez. İşlenmiş katman (`prc.<Tablo>`) ham katmanın güncel satırlarının kopyasıdır; her çalıştırmada ham veriden baştan kurulur, veri kuralları sırayla bu kopyada çalışır (K-141). Formül birikmez, kapatılan kuralın etkisi kendiliğinden kalkar. Validasyon ve load yalnız işlenmiş katmanı okur; hangi hücreyi hangi kuralın değiştirdiği kural izinde (`adm.DataRuleEffect`) tutulur.
- **Staging'in güncel hâli (K-133):** Her `stg` tablosu, ham partilerin yanında tablonun güncel ve tam hâlini taşır (`IsCurrent`). Tam parti güncel hâlin yerine geçer (partide olmayan kayıt silinmiş sayılır); Ekle / güncelle aynı anahtarlı kaydı değiştirir, ötekiler kalır; SQL çekimi her zaman Tam'dır. Ön kontrolde düşen satır güncel hâle girmez, o anahtarın önceki güncel satırı kalır. Güncel hâl ham katmana aittir; rules, validasyon ve load onun işlenmiş kopyasını okur (K-140); core'a bakılmaz. Ham veri temizliği güncel satırı silmez.
- **Ham değer kurala girdidir (K-121):** ERP'den gelen ham değerler (Status, Type gibi) yalnız veri kurallarına girdidir; motor ve ekranlar bayrakları okur (IsActive, IsOnHold, IsReleased…). Bayraklar kurallarla ham değerden doldurulur. Ham değer ile bayrak çelişirse bayrak geçerlidir. Bütün tablolar için geçerlidir.
- **ERP ana veri sahibidir:** Ana veri ve işlem verisinde ERP master'dır. Smartchain'e özgü alanlar (verim, kritik kaynak, parametreler) Smartchain'de tutulur; ERP'de yoksa kural ya da elle değerle tamamlanır.
- **Hata izole edilir:** Bir varlığın hatası diğerlerini durdurmaz; satır hatası satırı atlatır, eşik aşımı varlığı dışarıda bırakır. Gece akışı bu kurallarla kendi kendine ilerler.
- **Versiyonlu ve ya hep ya hiç:** Her yükleme yeni veri versiyonu açar; ortada kalan yükleme geri alınır. Açık çalışmalar kendi versiyonunda kalır.
- **İzlenebilir:** Her çağrı, parti, satır sayısı ve hata loglanır; Entegrasyon ekranında 'son çağrı', Sistem sağlığında süreler. Müşteriyle konuşma dili: varlık, parti numarası, hata sınıfı.
- **Kapalı ağ:** Entegrasyon müşteri ağı içinde kalır: ham tablolar Smartchain'in SQL Server instance'ında ayrı veritabanında, API ERP sunucusuna (Faz 2). İnternet yok, servis hesapları salt okunur.

### Entegrasyon mimarisi · veri akışı
<sub>26. Entegrasyon tasarımı · Genel görünüm</sub>

- **ERP (müşteri)**
  - Ana veri, siparişler, stok, iş emirleri, gerçekleşmeler
  - Ürün ERP'ye özel alan taşımaz
- **API adaptörü**
  - REST çağrısı, sayfalama, artımlı çekim
  - Alan eşleme tanımı (ERP → sözleşme)
  - 3 deneme, zaman aşımı
- **Ham veri (stg.*)**
  - Her yöntem aynı ham tabloya yazar
  - ImportBatch: parti, zaman, yöntem, satır, hata
  - 1 hafta saklama
- **Smartchain**
  - Geçerli ana veri ve işlem verisi
  - Parametreler ve elle değerler (Smartchain sahibi)
  - Planlama motoru, ekranlar, raporlar
- **Entegrasyon veritabanı (ham tablolar ve view'lar)**
  - Müşteri ETL'i ERP_* ham tablolarını doldurur, ERP_LoadLog'a bitti yazar
  - Aynı SQL Server ya da ayrı
- **SQL okuyucu**
  - View_* okur, her zaman tam
  - Önce sinyal ve uyum denetimi
  - Eşleme yok: kolon adı = sözleşme
- **Veri kuralları → validasyon → yükleme**
  - Veri kuralları işlenmiş katmanda (K-140, K-141)
  - Yapısal, referans, mantıksal, tutarlılık
  - Alan önceliği: ERP / kural / elle (varsayılan yok, K-138; elle değerin korunması yüklemede)
  - Türetilmiş alanlar (LLC)
  - Veri versiyonu (tam / kısmi)
- **Çıkış (Faz 1: Excel)**
  - Satın alma talebi listesi
  - İş emri açma listesi, fason listesi
  - Raporlar (Excel / PDF)
  - Faz 2: ERP'ye API ile geri yazma
- **Excel şablonları**
  - Key user doldurur, ekrandan yükler
  - Sözleşmeden üretilen şablon
- **Excel okuyucu**
  - Şablon sürümü ve varlık tanıma
  - Satır bazlı ön kontrol
- Faz 1: Excel listesi elle ERP'ye girilir · Faz 2: API ile geri yazma
- Tüm akış müşteri ağı içinde; internet yok. Çekim yöntemi tablo başına tektir, Excel'den yükleme her zaman açıktır, üç yöntem aynı ham tabloya iner.

### Veri sözleşmesi · varlıklar
<sub>26. Entegrasyon tasarımı · Veri sözleşmesi · varlık listesi · 1/2</sub>

- Her varlık için: yöntem seçenekleri (öncelik sırasıyla), master'ı kim, çekim sıklığı, iş anahtarı. Entegrasyon tabloları sonraki slaytlarda; alan adları 21. adımla aynı, ilişkiler Id yerine kodla.

| VARLIK | SINIF | YÖNTEM | MASTER | SIKLIK | ANAHTAR | ZORUNLULUK / FAZ |
|---|---|---|---|---|---|---|
| Malzeme (Material) | Ana veri | API · SQL · Excel | ERP | Gece tam | LocationCode + Code | Zorunlu |
| Lokasyon ve birim dönüşümü (Location, UomConversion) | Ana veri | API · SQL · Excel | ERP | Gece tam | Code · MaterialCode + From + To | Zorunlu |
| Ürün ağacı (ProductionVersion, BOM) | Ana veri | API · SQL · Excel | ERP | Gece tam | LocationCode + MaterialCode + Code · LocationCode + MaterialCode + Code + ComponentMaterialCode + OperationNo + SequenceNo | Zorunlu |
| Rota (Routing) | Ana veri | API · SQL · Excel | ERP | Gece tam | LocationCode + RouteCode + OperationNo + SequenceNo | Zorunlu |
| Benzetilen ürün (MaterialReference) | Ana veri | API · SQL · Excel | ERP | Gece tam | LocationCode + MaterialCode + ReferenceMaterialCode + ValidFrom | İsteğe bağlı |
| Kaynak (Resource, ResourceGroup) | Ana veri | Excel · SQL · API | ERP, kapasite tanımları Smartchain ekranında | Gece tam / elle | LocationCode + Code | Zorunlu |
| Grup ataması ve devamsızlık (ResourceGroupAssignment, EmployeeAbsence) | Ana veri · İşlem verisi | API · SQL · Excel | ERP | Gece tam | LocationCode + ResourceGroupCode + ResourceCode · LocationCode + ResourceCode + StartDate + AbsenceType | İşçi grubu varsa |
| Takvim ve gün (Calendar, CalendarDay) | Ana veri | Smartchain (ekran) | Smartchain | Elle | — | Zorunlu |
| Vardiya ve plan (Shift, ShiftPlan) | Ana veri | Smartchain (ekran) | Smartchain | Elle | — | İşçi grubu varsa |
| Duruş ve kapasite profili (ResourceDowntime, ResourceCapacityProfile) | Ana veri | Smartchain (ekran) | Smartchain | Elle | — | İsteğe bağlı |
| Tedarikçi ve malzeme-tedarikçi (Supplier, MaterialSupplier) | Ana veri | API · SQL · Excel | ERP | Gece tam | Code · LocationCode + MaterialCode + SupplierCode | Zorunlu |
| Müşteri (Customer) | Ana veri | API · SQL | ERP | Gece tam | Code | Zorunlu |
| Proje (Project, ProjectGroup) | Ana veri | API · SQL · Excel | ERP | Gece tam | Code | Proje bazlı planlamada |

### Veri sözleşmesi · varlıklar
<sub>26. Entegrasyon tasarımı · Veri sözleşmesi · varlık listesi · 2/2</sub>

- Her varlık için: yöntem seçenekleri (öncelik sırasıyla), master'ı kim, çekim sıklığı, iş anahtarı. Entegrasyon tabloları sonraki slaytlarda; alan adları 21. adımla aynı, ilişkiler Id yerine kodla.

| VARLIK | SINIF | YÖNTEM | MASTER | SIKLIK | ANAHTAR | ZORUNLULUK / FAZ |
|---|---|---|---|---|---|---|
| Satış siparişi ve teklif satırı (SalesOrderLine) | İşlem verisi | API · SQL | ERP | Gece tam + gün içi kısmi | LocationCode + OrderNo + LineNo + LineItemNo | Zorunlu |
| Tahmin (Forecast) | İşlem verisi | Excel · API | ERP ya da Excel | Haftalık | LocationCode + MaterialCode + CustomerCode + ProjectCode + Period + Type | İsteğe bağlı |
| Ödünç ve geri ödeme (BorrowPayback) | İşlem verisi | API · SQL · Excel | ERP | Gece tam | LocationCode + MaterialCode + LendingProjectCode + BorrowingProjectCode + BorrowDate | Proje bazlı planlamada |
| Stok (Stock) | İşlem verisi | API · SQL | ERP | Gece tam + gün içi kısmi | LocationCode + MaterialCode + Warehouse + LotNo + Status + ProjectCode + CustomerCode + SalesOrderNo + SalesOrderLineNo + SalesOrderLineItemNo | Zorunlu |
| İş emri (WorkOrder, Component, Operation) | İşlem verisi | API · SQL | ERP | Gece tam + gün içi kısmi | LocationCode + WorkOrderNo · LocationCode + WorkOrderNo + MaterialCode + OperationNo + SequenceNo · LocationCode + WorkOrderNo + OperationNo + SequenceNo | Zorunlu |
| Satın alma / fason siparişi (PurchaseOrderLine) | İşlem verisi | API · SQL | ERP | Gece tam + gün içi kısmi | LocationCode + PurchaseOrderNo + LineNo | Zorunlu |
| Transfer (TransferOrder) | İşlem verisi | API · SQL | ERP | Gece | OrderNo | Çok lokasyonda (Faz 2) |
| Üretim gerçekleşmesi (ProductionConfirmation) | İşlem verisi | API · SQL | ERP | Gece artımlı | LocationCode + ConfirmationNo | Doğruluk raporları için (A-22) |
| Sevkiyat / sipariş kapanışı (yeni) | İşlem verisi | API · SQL | ERP | Gece artımlı | OrderNo+LineNo+ShipDate | A-22 · raporlar 17, 19 |
| Birim maliyet (Material ek alanı, yeni) | Ana veri | API · SQL · Excel | ERP | Gece tam | MaterialCode | A-22 · stok değeri, tutar |
| Çıkış: satın alma talebi, iş emri açma, fason listesi | Plan çıktısı | Excel (Faz 1) · API (Faz 2) | Smartchain | Yayın sonrası, istek üzerine | PlannedOrder.Id | Faz 1 Excel |

### Veri sözleşmesi · varlık kataloğu
<sub>26. Entegrasyon tasarımı · Veri sözleşmesi · Geliştirme 3.1 (K-110)</sub>

- Şablonu ve ekran 02'yi besler; sıra referans verisinden işlem verisine. Kod bu tablodan üretilir (`python db/generate.py`, K-64). Sürüm, sözleşme değişince burada artar: alan, tip, anahtar, değer listesi ya da ön kontrolde zorunluluk; BOŞSA'nın anlam metni sürüm artırmaz, şablonun Açıklama sayfası yeni metni gösterir (K-138). Transfer (TransferOrder) çok lokasyonda geldiği için `stg` tablosu ve şablonu yoktur (Faz 2).
- **Entegrasyon tablolarının kolonları:** ZOR. E ise kolon dosyada ya da view'da bulunmak zorundadır. KAYNAK değerin nereden geldiğini yazar (ERP, kural, elle; varsayılan yoktur, K-138). BOŞSA, kurallardan sonra alan boş kalırsa ne olacağını yazar: **hata (satır atlanır)** ön kontrolde satır ham veriye alınmaz; **hata (kurallardan sonra)** alan veri kuralıyla dolabilir, dolmazsa validasyonda Hata, satır load edilmez; **tedarik süresi doluysa hata (kurallardan sonra)** yalnız FixedLeadTimeDays ya da VariableLeadTimeDays doluyken (MS.NO_BASIS); **yok** özellik ya da miktar yoktur (fire yok, bayrak taşımıyor); **sınırsız** sınır yoktur; **bilinmiyor** bilgi yoktur, motor ve raporlar kullanmaz; **temel birim** miktar malzemenin (bileşende bileşenin) temel birimindedir (K-112); **alternatif X** X de boşsa satır atlanır; alana özgü anlamlar (tam gün, ilk operasyon, motor seçer, gruptan, müşteriden, bütün malzemeler) satırında yazar.

| VARLIK | AD | SINIF | AÇIKLAMA | DOSYA ADI | SÜRÜM |
|---|---|---|---|---|---|
| Location | Lokasyon | Ana veri | Tesisler, depolar ve fason depoları | lokasyon | 3 |
| UomConversion | Birim dönüşümü | Ana veri | Malzeme bazında birimler arası çevrim oranları | birim-donusumu | 2 |
| Material | Malzeme | Ana veri | Hammadde, yarı mamul ve nihai ürünler ile planlama bilgileri | malzeme | 4 |
| ProductionVersion | Üretim versiyonu | Ana veri | Bir malzemenin ürün ağacı ve rotasını belirleyen üretim versiyonları | uretim-versiyonu | 2 |
| BOM | Ürün ağacı | Ana veri | Malzemelerin bileşenleri ve miktarları | urun-agaci | 2 |
| Routing | Rota | Ana veri | Üretim operasyonları, kullandıkları kaynaklar ve süreleri | rota | 2 |
| MaterialReference | Benzetilen ürün | Ana veri | Kendi ağacı ya da rotası olmayan ürünlerin referans ürünleri | benzetilen-urun | 1 |
| ResourceGroup | Kaynak grubu | Ana veri | Kaynak ve yetkinlik grupları | kaynak-grubu | 2 |
| Resource | Kaynak | Ana veri | Makine, işçi ve fason kaynakları | kaynak | 3 |
| ResourceGroupAssignment | Kaynak grubu ataması | Ana veri | Kaynakların gruplara atanması ve yetkinlik matrisi | kaynak-grubu-atamasi | 1 |
| EmployeeAbsence | Çalışan izni | İşlem verisi | Çalışanların izin ve rapor kayıtları | calisan-izni | 1 |
| Supplier | Tedarikçi | Ana veri | Tedarikçiler ve fasoncular | tedarikci | 2 |
| MaterialSupplier | Malzeme tedarikçisi | Ana veri | Malzemelerin tedarikçileri, temin süreleri ve sipariş koşulları | malzeme-tedarikcisi | 2 |
| Customer | Müşteri | Ana veri | Müşteriler | musteri | 2 |
| ProjectGroup | Proje grubu | Ana veri | Stok ve kapasiteyi paylaşan proje grupları | proje-grubu | 2 |
| Project | Proje | Ana veri | Proje bazlı planlanan işler | proje | 2 |
| SalesOrderLine | Satış siparişi | İşlem verisi | Müşteri sipariş ve teklif satırları | satis-siparisi | 3 |
| Forecast | Tahmin | İşlem verisi | Malzeme ve dönem bazında talep tahminleri | tahmin | 2 |
| Stock | Stok | İşlem verisi | Lot ve duruma göre eldeki stok | stok | 3 |
| BorrowPayback | Ödünç ve geri ödeme | İşlem verisi | Projeler arası ödünç kayıtları ve geri ödemeleri | odunc-ve-geri-odeme | 1 |
| WorkOrder | İş emri | İşlem verisi | Açık üretim, fason ve yeniden işleme emirleri | is-emri | 3 |
| WorkOrderComponent | İş emri bileşeni | İşlem verisi | İş emirlerinin bileşenleri ve çekilen miktarlar | is-emri-bileseni | 2 |
| WorkOrderOperation | İş emri operasyonu | İşlem verisi | İş emirlerinin operasyonları ve kalan işi | is-emri-operasyonu | 2 |
| PurchaseOrderLine | Satın alma siparişi | İşlem verisi | Açık satın alma ve fason sipariş satırları, talepler dahil | satin-alma-siparisi | 3 |
| ProductionConfirmation | Üretim gerçekleşmesi | İşlem verisi | İş emri bazında stoğa girişler | uretim-gerceklesmesi | 2 |

### stg.Material
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Malzeme · 1/2</sub>

- Malzeme ve planlama ana verisi.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | BOŞSA |
|---|---|---|---|---|---|---|
| LocationCode | nvarchar(30) | UK,REF | E | Lokasyon kodu | ERP | hata (satır atlanır) |
| Code | nvarchar(50) | UK | E | Malzeme kodu | ERP | hata (satır atlanır) |
| Name | nvarchar(200) |  | H | Malzeme adı | ERP | bilinmiyor |
| BaseUom | nvarchar(10) | REF | E | Temel birim | ERP | hata (satır atlanır) |
| MaterialGroup | nvarchar(50) |  | H | Malzeme grubu | ERP | bilinmiyor |
| MaterialLevel | nvarchar(15) |  | H | Hammadde \| Yarı mamul \| Nihai ürün | ERP, yoksa kural | bilinmiyor |
| MaterialType | nvarchar(50) |  | H | Malzeme tipi | ERP | bilinmiyor |
| Brand | nvarchar(50) |  | H | Marka | ERP | bilinmiyor |
| PlannerCode | nvarchar(50) |  | H | Planlamacı | ERP | bilinmiyor |
| MRPGroup | nvarchar(50) |  | H | MRP grubu; planlama parametreleri aynı olan malzemeleri gruplar | ERP | bilinmiyor |
| IsActive | bit |  | H | Aktif | ERP, yoksa kural | hata (kurallardan sonra) |
| IsCritical | bit |  | H | Kritik malzeme; malzeme kısıtı yalnız kritik malzemelere uygulanır, kritik olmayanın her zaman temin edilebildiği varsayılır | ERP, yoksa kural | yok |
| IsPurchasable | bit |  | H | Satın alınabilir | ERP, yoksa kural | yok |
| IsProducible | bit |  | H | Üretilebilir | ERP, yoksa kural | yok |
| IsSellable | bit |  | H | Satılabilir | ERP, yoksa kural | yok |
| IsSubcontractable | bit |  | H | Fasona verilebilir | ERP, yoksa kural | yok |
| DefaultSupplyType | nvarchar(10) |  | H | Üretim \| Satın alma \| Fason | ERP, yoksa kural | hata (kurallardan sonra) |
| IsCustomerSupplied | bit |  | H | Müşteri temin malzemesi | Kural ya da elle | yok |

### stg.Material
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Malzeme · 2/2</sub>

- Malzeme ve planlama ana verisi.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | BOŞSA |
|---|---|---|---|---|---|---|
| IsCustomTracked | bit |  | H | Malzeme ortak havuzdan değil, belli bir talebe (proje, müşteri ya da sipariş) ayrılmış olarak takip edilir; hangi talebe ayrıldığı talep kaydından gelir | Kural ya da elle | yok |
| IsPhantom | bit |  | H | Hayalet yarı mamul | ERP | yok |
| IsNonStockable | bit |  | H | Stok tutulamaz; üretilen ya da teslim alınan miktar beklemeden tüketilir, dönem sonu stoğu sıfırdır | ERP, yoksa kural | yok |
| GoodsReceiptDays | decimal(9,2) |  | H | Mal kabul süresi (iş günü) | ERP, yoksa kural | yok |
| SafetyStock | decimal(18,4) |  | H | Güvenlik stoğu | ERP | yok |
| StockCoverageDays | decimal(9,2) |  | H | Gün cinsinden güvenlik stoğu | ERP | yok |
| MaxStock | decimal(18,4) |  | H | Maksimum stok | ERP | sınırsız |
| LotSizePolicy | nvarchar(15) |  | H | Üretimde: Lot-for-lot \| Sabit \| Dönemsel | ERP, yoksa kural | yok |
| MinLot | decimal(18,4) |  | H | Üretimde minimum | ERP | yok |
| MaxLot | decimal(18,4) |  | H | Üretimde maksimum | ERP | sınırsız |
| LotMultiple | decimal(18,4) |  | H | Üretimde kat | ERP | yok |
| QtyPerBox | decimal(18,4) |  | H | Temel birimde kutu içi miktar | ERP | bilinmiyor |
| QtyPerPallet | decimal(18,4) |  | H | Temel birimde palet içi miktar | ERP | bilinmiyor |
| ScrapRatio | decimal(6,4) |  | H | Oran olarak fire (0,05 = %5) | ERP | yok |
| ShelfLifeDays | int |  | H | Raf ömrü (gün); Faz 1'de yalnız uyarı | ERP | sınırsız |
| AdditionalText1–7 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | yok |
| AdditionalNumber1–3 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | yok |

### stg.Location
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Ortak</sub>

- Lokasyon (tesis, depo). Faz 1'de her lokasyon kendi içinde planlanır.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | BOŞSA |
|---|---|---|---|---|---|---|
| Code | nvarchar(30) | UK | E | Lokasyon kodu | ERP | hata (satır atlanır) |
| Name | nvarchar(100) |  | H | Lokasyon adı | ERP | bilinmiyor |
| Type | nvarchar(50) |  | H | ERP'den ham lokasyon tipi; veri kurallarında kullanılır (bayraklar bundan dolar), değer listesi yok (K-143) | ERP | bilinmiyor |
| IsFactory | bit |  | H | Tesis mi | Kural, ERP ya da Excel | yok |
| IsDepot | bit |  | H | Depo mu | Kural, ERP ya da Excel | yok |
| IsSubcontractor | bit |  | H | Fason deposu mu | Kural, ERP ya da Excel | yok |
| IsActive | bit |  | H | Aktif mi | Kural, ERP ya da Excel | hata (kurallardan sonra) |
| Country | nvarchar(100) |  | H | Ülke | ERP | bilinmiyor |
| CountryCode | nvarchar(10) |  | H | Ülke kodu | ERP | bilinmiyor |
| Region | nvarchar(100) |  | H | Bölge | ERP | bilinmiyor |
| RegionCode | nvarchar(20) |  | H | Bölge kodu | ERP | bilinmiyor |
| City | nvarchar(100) |  | H | Şehir | ERP | bilinmiyor |
| CityCode | nvarchar(20) |  | H | Şehir kodu | ERP | bilinmiyor |
| AdditionalText1–7 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | yok |
| AdditionalNumber1–3 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | yok |

### stg.UomConversion
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Ortak</sub>

- Malzeme bazında birim dönüşümü.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | BOŞSA |
|---|---|---|---|---|---|---|
| MaterialCode | nvarchar(50) | UK,REF | H | Malzeme (boşsa genel dönüşüm) | ERP | bütün malzemeler |
| FromUom | nvarchar(10) | UK,REF | E | Kaynak birim | ERP | hata (satır atlanır) |
| FromUomName | nvarchar(50) |  | H | Kaynak birim adı | ERP | bilinmiyor |
| ToUom | nvarchar(10) | UK,REF | E | Hedef birim | ERP | hata (satır atlanır) |
| ToUomName | nvarchar(50) |  | H | Hedef birim adı | ERP | bilinmiyor |
| Factor | decimal(18,6) |  | E | 1 kaynak birim = çarpan × hedef birim | ERP | hata (satır atlanır) |

### stg.ProductionVersion
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Malzeme</sub>

- Üretim versiyonu: bir malzemenin ürün ağacı ve rota başlığı; rotaya RouteCode, ürün ağacına BOMCode ile bağlanır. Versiyon seçimi motorun kararıdır; aynı malzeme aynı dönemde birden fazla versiyonla üretilebilir.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | BOŞSA |
|---|---|---|---|---|---|---|
| LocationCode | nvarchar(30) | UK,REF | E | Lokasyon kodu | ERP | hata (satır atlanır) |
| MaterialCode | nvarchar(50) | UK,REF | E | Üretilen malzeme | ERP | hata (satır atlanır) |
| Code | nvarchar(30) | UK | E | Versiyon kodu | ERP | hata (satır atlanır) |
| Name | nvarchar(100) |  | H | Versiyon adı | ERP | bilinmiyor |
| Type | nvarchar(50) |  | H | Versiyonları ayrıştırmak için kurallarda kullanılır; değer listesi yok | ERP | bilinmiyor |
| IsActive | bit |  | H | Aktif | ERP, yoksa kural | hata (kurallardan sonra) |
| Priority | int |  | H | Versiyonlar arası tercih bilgisi; motora girdi | ERP | yok |
| BaseQuantity | decimal(18,4) |  | H | Baz miktar (rota ve ağaç bu miktar için) | ERP | hata (kurallardan sonra) |
| BOMCode | nvarchar(50) |  | E | Versiyonun kullandığı ürün ağacı | ERP | hata (satır atlanır) |
| RouteCode | nvarchar(50) |  | E | Rota kodu (Routing.RouteCode) | ERP | hata (satır atlanır) |
| ValidFrom | date |  | H | Geçerlilik başlangıcı | ERP | sınırsız |
| ValidTo | date |  | H | Geçerlilik bitişi | ERP | sınırsız |
| AdditionalText1–3 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | yok |
| AdditionalNumber1–2 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | yok |

### stg.BOM
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Malzeme</sub>

- Ürün ağacı satırı.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | BOŞSA |
|---|---|---|---|---|---|---|
| LocationCode | nvarchar(30) | UK,REF | E | Lokasyon kodu | ERP | hata (satır atlanır) |
| MaterialCode | nvarchar(50) | UK | E | Üretilen malzeme kodu | ERP | hata (satır atlanır) |
| Code | nvarchar(50) | UK | E | Ürün ağacı kodu | ERP | hata (satır atlanır) |
| ComponentMaterialCode | nvarchar(50) | UK,REF | E | Bileşen kodu | ERP | hata (satır atlanır) |
| OperationNo | int | UK | H | Bağlı olduğu operasyon no (ihtiyaç tarihi için) | ERP | ilk operasyon |
| SequenceNo | int | UK | H | Sıra no; aynı bileşen iki kez geçerse operasyon no ile ayrışır | ERP | bilinmiyor |
| Quantity | decimal(18,6) |  | E | Baz miktar için bileşen miktarı | ERP | hata (satır atlanır) |
| ComponentUom | nvarchar(10) | REF | H | Bileşen miktarının birimi; boşsa bileşenin temel biriminde kabul edilir, doluysa birim dönüşümüyle çevrilir | ERP | temel birim |
| ScrapRatio | decimal(6,4) |  | H | Oran olarak fire (0,05 = %5) | ERP | yok |
| IsPhantom | bit |  | H | Hayalet bileşen | ERP | yok |
| IsLotBasedUsage | bit |  | H | Doluysa bileşen üretilen miktardan bağımsız, her üretim lotu için sabit kullanılır; değilse birim başına | ERP | yok |
| AlternativeGroup | nvarchar(50) |  | H | Aynı grup koduna sahip satırlar birbirinin alternatifidir | ERP | yok |
| AlternativePriority | int |  | H | Grup içindeki tercih bilgisi | ERP | yok |
| AdditionalText1–3 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | yok |
| AdditionalNumber1–2 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | yok |

### stg.Routing
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Malzeme · 1/2</sub>

- Rota: her satır bir operasyon–kaynak ilişkisi; sıra önce OperationNo, sonra SequenceNo. Aynı operasyonun kaynakları ayrı satırda, ResourceRole ile.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | BOŞSA |
|---|---|---|---|---|---|---|
| LocationCode | nvarchar(30) | UK,REF | E | Lokasyon kodu | ERP | hata (satır atlanır) |
| RouteCode | nvarchar(50) | UK | E | Rota kodu | ERP | hata (satır atlanır) |
| OperationNo | int | UK | E | Operasyon no (birinci sıralama) | ERP | hata (satır atlanır) |
| SequenceNo | int | UK | E | Operasyon içindeki alt sıra (ikinci sıralama) | ERP | hata (satır atlanır) |
| OperationName | nvarchar(150) |  | H | Operasyon adı | ERP | bilinmiyor |
| ResourceCode | nvarchar(50) | REF | H | Kaynak kodu | ERP | alternatif Kaynak grubu |
| ResourceGroupCode | nvarchar(50) | REF | H | Kaynak grubu | ERP | alternatif Kaynak |
| ResourceRole | nvarchar(10) |  | E | Primary \| Secondary | ERP, yoksa kural | hata (kurallardan sonra) |
| Consumption | decimal(18,6) |  | E | Baz miktar için kaynak tüketimi (kaynağın kapasite biriminde) | ERP | hata (satır atlanır) |
| ResourceNumber | int |  | E | Operasyonda aynı anda kullanılan kaynak adedi | ERP, yoksa kural | hata (kurallardan sonra) |
| IsSubcontracted | bit |  | H | Fason operasyon | ERP | yok |

### stg.Routing
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Malzeme · 2/2</sub>

- Rota: her satır bir operasyon–kaynak ilişkisi; sıra önce OperationNo, sonra SequenceNo. Aynı operasyonun kaynakları ayrı satırda, ResourceRole ile.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | BOŞSA |
|---|---|---|---|---|---|---|
| TransferQuantity | decimal(18,4) |  | H | Transfer partisi | ERP | yok |
| IsActive | bit |  | H | Operasyon plana dahil mi | ERP, yoksa kural | hata (kurallardan sonra) |
| IsLotBasedUsage | bit |  | H | Doluysa tüketim üretilen miktardan bağımsız, lot başına sabit; pratikte hazırlık süresi | ERP | yok |
| ProductionLocation | nvarchar(50) |  | H | Lokasyonun alt tanımı (hol, hat); ileride kısıtlar için | ERP | bilinmiyor |
| WaitingTimeHours | decimal(9,2) |  | H | Operasyon öncesi kuyruk beklemesi | ERP | yok |
| TransferTimeHours | decimal(9,2) |  | H | Sonraki operasyona taşıma | ERP | yok |
| AlternativeGroup | nvarchar(50) |  | H | Aynı gruptaki satırlar birbirinin alternatifidir | ERP | yok |
| AlternativePriority | int |  | H | Grup içindeki tercih bilgisi | ERP | yok |
| AdditionalText1–3 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | yok |
| AdditionalNumber1–2 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | yok |

### stg.MaterialReference
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Malzeme</sub>

- Benzetilen ürün: kendi ağacı ya da rotası olmayan ürün, başka bir ürünün verisiyle planlanır.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | BOŞSA |
|---|---|---|---|---|---|---|
| LocationCode | nvarchar(30) | UK,REF | E | Lokasyon kodu | ERP | hata (satır atlanır) |
| MaterialCode | nvarchar(50) | UK,REF | E | Benzetilen ürün | ERP | hata (satır atlanır) |
| ReferenceMaterialCode | nvarchar(50) | UK,REF | E | Referans ürün | ERP | hata (satır atlanır) |
| ReferenceProductionVersionCode | nvarchar(30) | REF | H | Referans ürünün versiyonu; boşsa motor seçer | ERP | motor seçer |
| ValidFrom | date | UK | H | Geçerlilik başlangıcı | ERP | sınırsız |
| ValidTo | date |  | H | Geçerlilik bitişi | ERP | sınırsız |
| TimeFactor | decimal(9,4) |  | H | Süre çarpanı; 1,2 = %20 daha uzun | ERP | yok |

### stg.Resource
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Kaynak · 1/2</sub>

- Kaynak: makine, işçi, fason, diğer. Kapasite kaynağın kendi biriminde günlük kapasite olarak tutulur.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | BOŞSA |
|---|---|---|---|---|---|---|
| LocationCode | nvarchar(30) | UK,REF | E | Lokasyon kodu | ERP | hata (satır atlanır) |
| Code | nvarchar(50) | UK | E | Kaynak kodu | ERP | hata (satır atlanır) |
| Name | nvarchar(150) |  | H | Kaynak adı | ERP | bilinmiyor |
| ResourceType | nvarchar(50) |  | H | ERP'den gelen ham değer; tip bayraklarla ifade edilir | ERP | bilinmiyor |
| IsEmployee | bit |  | H | Kaynak işçi mi | ERP, yoksa kural | yok |
| IsMachine | bit |  | H | Kaynak makine mi | ERP, yoksa kural | yok |
| IsFurnace | bit |  | H | Kaynak fırın mı; Faz 1 planlamada kullanılmaz | ERP, yoksa kural | yok |
| IsMold | bit |  | H | Kaynak kalıp mı; Faz 1 planlamada kullanılmaz | ERP, yoksa kural | yok |
| IsOther | bit |  | H | Diğer kaynak mı | ERP, yoksa kural | yok |
| IsSubcontractor | bit |  | H | Kaynak fason mu | ERP, yoksa kural | yok |

### stg.Resource
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Kaynak · 2/2</sub>

- Kaynak: makine, işçi, fason, diğer. Kapasite kaynağın kendi biriminde günlük kapasite olarak tutulur.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | BOŞSA |
|---|---|---|---|---|---|---|
| CapacityUnit | nvarchar(10) | REF | E | Kapasite birimi (Saat, Adet, Ton…); rotadaki tüketim aynı birimde kabul edilir | ERP, yoksa kural | hata (kurallardan sonra) |
| SubcontractorCode | nvarchar(50) | REF | H | Fasoncu | ERP | bilinmiyor |
| ProductionLocation | nvarchar(50) |  | H | Lokasyonun alt tanımı (hol, hat) | ERP | bilinmiyor |
| IsActive | bit |  | H | Aktif mi | ERP, yoksa kural | hata (kurallardan sonra) |
| IsCritical | bit |  | H | 1: planda kısıt, 0: sonsuz kapasite (sadece raporlanır) | ERP, yoksa kural | hata (kurallardan sonra) |
| RemainingOverTimeYear | decimal(9,2) |  | H | Yıllık kalan fazla mesai (saat) | ERP | sınırsız |
| RemainingOverTimeMonth | decimal(9,2) |  | H | Aylık kalan fazla mesai (saat) | ERP | sınırsız |
| AdditionalText1–7 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | yok |
| AdditionalNumber1–3 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | yok |

- **Entegre edilmeyenler (K-117):** Günlük kapasite, paralel adet, kapasite kaynağı, verim, hedef doluluk, fason parametreleri, takvim, vardiya, kaynak duruşları ve kapasite profili entegre edilmez; Smartchain ekranlarında tanımlanır (6.1 Kaynak sekmesi, 7.3 Kapasite parametreleri). `core`'da kalır.

### stg.ResourceGroup
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Kaynak</sub>

- Kaynak ve yetkinlik grubu. Kapasite havuzu değil, uygun kaynaklar listesidir; kapasite yalnız kaynakta tutulur.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | BOŞSA |
|---|---|---|---|---|---|---|
| LocationCode | nvarchar(30) | UK,REF | E | Lokasyon kodu | ERP | hata (satır atlanır) |
| Code | nvarchar(50) | UK | E | Grup kodu | ERP | hata (satır atlanır) |
| Name | nvarchar(150) |  | H | Grup adı | ERP | bilinmiyor |
| Type | nvarchar(50) |  | H | Grup tipi; ERP'den gelen ham değer | ERP | bilinmiyor |
| IsResourceGroup | bit |  | H | Kaynak grubu | ERP, yoksa kural | yok |
| IsCompetenceGroup | bit |  | H | Yetkinlik grubu | ERP, yoksa kural | yok |
| IsActive | bit |  | H | Aktif | ERP, yoksa kural | hata (kurallardan sonra) |
| AdditionalText1–7 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | yok |
| AdditionalNumber1–3 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | yok |

### stg.ResourceGroupAssignment
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Kaynak</sub>

- Kaynağın gruba ataması; bir kaynak birden fazla gruba atanabilir, yetkinlik matrisi bu tablodur. Geçerlilik tarihleri yalnız girdi.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | BOŞSA |
|---|---|---|---|---|---|---|
| LocationCode | nvarchar(30) | UK,REF | E | Lokasyon kodu | ERP | hata (satır atlanır) |
| ResourceGroupCode | nvarchar(50) | UK,REF | E | Kaynak ya da yetkinlik grubu | ERP | hata (satır atlanır) |
| ResourceCode | nvarchar(50) | UK,REF | E | Kaynak kodu | ERP | hata (satır atlanır) |
| ValidFrom | date |  | H | Geçerlilik başlangıcı | ERP | sınırsız |
| ValidTo | date |  | H | Geçerlilik bitişi | ERP | sınırsız |

### stg.EmployeeAbsence
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Kaynak</sub>

- Kişi bazında izin ve rapor.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | BOŞSA |
|---|---|---|---|---|---|---|
| LocationCode | nvarchar(30) | UK,REF | E | Lokasyon kodu | ERP | hata (satır atlanır) |
| ResourceCode | nvarchar(50) | UK,REF | E | Kaynak kodu | ERP | hata (satır atlanır) |
| AbsenceType | nvarchar(50) | UK | E | ERP'den gelen ham değer (izin, rapor…) | ERP | hata (satır atlanır) |
| StartDate | date | UK | E | Başlangıç | ERP | hata (satır atlanır) |
| EndDate | date |  | E | Bitiş günü dahil | ERP | hata (satır atlanır) |
| HoursPerDay | decimal(9,2) |  | H | Günlük devamsız saat; kısmi devamsızlık için, boşsa tam gün | ERP | tam gün |

### stg.Supplier
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Malzeme</sub>

- Tedarikçi ve fasoncu.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | BOŞSA |
|---|---|---|---|---|---|---|
| Code | nvarchar(50) | UK | E | Tedarikçi kodu | ERP | hata (satır atlanır) |
| Name | nvarchar(200) |  | H | Ad | ERP | bilinmiyor |
| IsSubcontractor | bit |  | H | Fasoncu mu | ERP, yoksa kural | yok |
| IsActive | bit |  | H | Aktif mi | ERP, yoksa kural | hata (kurallardan sonra) |
| Country | nvarchar(100) |  | H | Ülke | ERP | bilinmiyor |
| City | nvarchar(100) |  | H | Şehir | ERP | bilinmiyor |
| AdditionalText1–7 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | yok |
| AdditionalNumber1–3 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | yok |

### stg.MaterialSupplier
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Malzeme</sub>

- Malzeme–tedarikçi ilişkisi; satın alma parametreleri. Satın alma her zaman sürekli; yuvarlama son hesapta.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | BOŞSA |
|---|---|---|---|---|---|---|
| LocationCode | nvarchar(30) | UK,REF | E | Lokasyon kodu | ERP | hata (satır atlanır) |
| MaterialCode | nvarchar(50) | UK,REF | E | Malzeme | ERP | hata (satır atlanır) |
| SupplierCode | nvarchar(50) | UK,REF | E | Tedarikçi | ERP | hata (satır atlanır) |
| IsActive | bit |  | H | Aktif mi | ERP, yoksa kural | hata (kurallardan sonra) |
| Priority | int |  | H | Öncelik | ERP, yoksa kural | yok |
| QuotaRatio | decimal(6,4) |  | H | Oran olarak kota (0,30 = %30) | ERP, yoksa kural | yok |
| FixedLeadTimeDays | decimal(9,2) |  | H | Miktardan bağımsız kısım | ERP | bilinmiyor |
| VariableLeadTimeDays | decimal(18,6) |  | H | Birim başına gün; miktar arttıkça uzayan kısım | ERP | bilinmiyor |
| LeadTimeBasis | nvarchar(15) |  | H | Takvim günü \| İş günü | Kural ya da elle | tedarik süresi doluysa hata (kurallardan sonra) |
| MinimumOrderQuantity | decimal(18,4) |  | H | Minimum sipariş miktarı | ERP | yok |
| OrderLotSize | decimal(18,4) |  | H | Sipariş miktarı bu sayının katı olur | ERP | yok |
| MaximumOrderQuantity | decimal(18,4) |  | H | Maksimum | ERP | sınırsız |
| ValidFrom | date |  | H | Geçerlilik başlangıcı | ERP | sınırsız |
| ValidTo | date |  | H | Geçerlilik bitişi | ERP | sınırsız |
| AdditionalText1–3 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | yok |
| AdditionalNumber1–2 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | yok |

### stg.Customer
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Talep</sub>

- Müşteri.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | BOŞSA |
|---|---|---|---|---|---|---|
| Code | nvarchar(50) | UK | E | Müşteri kodu | ERP | hata (satır atlanır) |
| Name | nvarchar(200) |  | H | Ad | ERP | bilinmiyor |
| Priority | int |  | H | Müşteri önceliği | Kural ya da elle | yok |
| AllowPartialDelivery | bit |  | H | Kısmi teslimata izin | ERP, yoksa kural | hata (kurallardan sonra) |
| CustomerGroup | nvarchar(50) |  | H | Müşteri grubu | ERP | bilinmiyor |
| IsActive | bit |  | H | Aktif mi | ERP, yoksa kural | hata (kurallardan sonra) |
| Country | nvarchar(100) |  | H | Ülke | ERP | bilinmiyor |
| Region | nvarchar(100) |  | H | Bölge | ERP | bilinmiyor |
| City | nvarchar(100) |  | H | Şehir | ERP | bilinmiyor |
| IsCustomTracked | bit |  | H | Bu müşterinin talepleri ortak havuzdan değil, müşteriye ayrılmış olarak takip edilir | ERP, yoksa kural | yok |
| AdditionalText1–7 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | yok |
| AdditionalNumber1–3 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | yok |

### stg.ProjectGroup
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Malzeme</sub>

- Proje grubu (grup içi paylaşım için).  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | BOŞSA |
|---|---|---|---|---|---|---|
| Code | nvarchar(50) | UK | E | Grup kodu | ERP ya da kural | hata (satır atlanır) |
| Name | nvarchar(200) |  | H | Proje grubu adı | ERP ya da kural | bilinmiyor |
| TrackingRule | nvarchar(20) |  | H | Tam izolasyon \| Ortaktan beslenir \| Grup içi paylaşım | ERP ya da kural | hata (kurallardan sonra) |
| Priority | int |  | H | Proje grubu önceliği | ERP ya da kural | yok |
| IsActive | bit |  | H | Aktif mi | ERP ya da kural | hata (kurallardan sonra) |

### stg.Project
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Malzeme</sub>

- Proje.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | BOŞSA |
|---|---|---|---|---|---|---|
| Code | nvarchar(50) | UK | E | Proje kodu | ERP ya da kural | hata (satır atlanır) |
| Name | nvarchar(200) |  | H | Proje adı | ERP ya da kural | bilinmiyor |
| ProjectGroupCode | nvarchar(50) | REF | H | Proje grubu kodu | ERP ya da kural | yok |
| TrackingRule | nvarchar(20) |  | H | Proje bazında takip kuralı (grubu ezer) | ERP ya da kural | gruptan |
| Priority | int |  | H | Proje önceliği | ERP ya da kural | yok |
| IsActive | bit |  | H | Aktif mi | ERP ya da kural | hata (kurallardan sonra) |
| AdditionalText1–7 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | yok |
| AdditionalNumber1–3 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | yok |

### stg.SalesOrderLine
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Talep</sub>

- Müşteri sipariş satırı; teklifler IsQuote ile okunur. Vade: teyit tarihi, yoksa istek tarihi.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | BOŞSA |
|---|---|---|---|---|---|---|
| LocationCode | nvarchar(30) | UK,REF | E | Lokasyon kodu | ERP | hata (satır atlanır) |
| OrderNo | nvarchar(30) | UK | E | Sipariş no | ERP | hata (satır atlanır) |
| LineNo | int | UK | E | Satır no | ERP | hata (satır atlanır) |
| LineItemNo | int | UK | H | Alt satır no (ERP satırı kırılımlıysa) | ERP | yok |
| Type | nvarchar(50) |  | H | ERP'den ham sipariş tipi; veri kurallarında kullanılır, değer listesi yok | ERP | bilinmiyor |
| CustomerCode | nvarchar(50) | REF | E | Müşteri kodu | ERP | hata (satır atlanır) |
| MaterialCode | nvarchar(50) | REF | E | Malzeme | ERP | hata (satır atlanır) |
| ProjectCode | nvarchar(50) | REF | H | Proje | ERP | yok |
| OpenQuantity | decimal(18,4) |  | E | Açık miktar | ERP | hata (satır atlanır) |
| OrderedQuantity | decimal(18,4) |  | H | Satırın orijinal miktarı | ERP | bilinmiyor |
| DeliveredQuantity | decimal(18,4) |  | H | Teslim edilen miktar | ERP | yok |
| Uom | nvarchar(10) | REF | H | Açık, sipariş ve teslim miktarının birimi; boşsa malzemenin temel biriminde kabul edilir, doluysa birim dönüşümüyle çevrilir | ERP | temel birim |
| RequestedDate | date |  | E | İstek tarihi | ERP | hata (satır atlanır) |
| ConfirmedDate | date |  | H | Teyit tarihi | ERP | bilinmiyor |
| Priority | int |  | H | Satır önceliği | Kural ya da elle | yok |
| AllowPartialDelivery | bit |  | H | Kısmi teslimat (müşteriyi ezer) | ERP | müşteriden |
| Status | nvarchar(50) |  | H | ERP'den ham sipariş durumu; veri kurallarında kullanılır, değer listesi yok | ERP | bilinmiyor |
| IsActive | bit |  | H | Aktif mi | ERP, yoksa kural | hata (kurallardan sonra) |
| IsOnHold | bit |  | H | Kredi, teknik onay ya da müşteri talebiyle bekletilen satır | ERP, yoksa kural | yok |
| IsCustomTracked | bit |  | H | Satır düzeyinde özel takip | ERP, yoksa kural | yok |
| IsQuote | bit |  | H | Teklif satırı; Type'tan veri kuralıyla doldurulur | ERP, yoksa kural | yok |
| AdditionalText1–3 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | yok |
| AdditionalNumber1–2 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | yok |

### stg.Forecast
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Talep</sub>

- Talep tahmini (netleme ön hesapta).  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | BOŞSA |
|---|---|---|---|---|---|---|
| LocationCode | nvarchar(30) | UK,REF | E | Lokasyon kodu | ERP | hata (satır atlanır) |
| MaterialCode | nvarchar(50) | UK,REF | E | Malzeme | ERP | hata (satır atlanır) |
| CustomerCode | nvarchar(50) | UK,REF | H | Müşteri kodu | ERP | yok |
| ProjectCode | nvarchar(50) | UK,REF | H | Proje | ERP | yok |
| Period | date | UK | E | Dönem | ERP | hata (satır atlanır) |
| Type | nvarchar(50) | UK | H | Hangisinin plana gireceği veri kuralıyla seçilir; ERP'den ham değer, değer listesi yok | ERP | bilinmiyor |
| Quantity | decimal(18,4) |  | E | Miktar | ERP | hata (satır atlanır) |
| Uom | nvarchar(10) | REF | H | Miktarın birimi; boşsa malzemenin temel biriminde kabul edilir, doluysa birim dönüşümüyle çevrilir | ERP | temel birim |
| DeliveryPoint | nvarchar(10) |  | H | Miktarın dönemin başında mı sonunda mı hazır olması gerektiği: Başı \| Sonu | ERP, yoksa kural | hata (kurallardan sonra) |
| IsActive | bit |  | H | Aktif mi | ERP, yoksa kural | hata (kurallardan sonra) |
| AdditionalText1–3 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | yok |
| AdditionalNumber1–2 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | yok |

### stg.BorrowPayback
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Arz ve stok</sub>

- Projeler arası ödünç ve geri ödeme kaydı: devreye almada açık olan ve ERP'de doğrudan yapılan ödünçlerin motora bildirilmesi; onaylanan öneriler de buraya yazılır.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | BOŞSA |
|---|---|---|---|---|---|---|
| LocationCode | nvarchar(30) | UK,REF | E | Lokasyon kodu | ERP | hata (satır atlanır) |
| MaterialCode | nvarchar(50) | UK,REF | E | Malzeme | ERP | hata (satır atlanır) |
| LendingProjectCode | nvarchar(50) | UK,REF | E | Ödünç veren proje | ERP | hata (satır atlanır) |
| BorrowingProjectCode | nvarchar(50) | UK,REF | E | Ödünç alan proje | ERP | hata (satır atlanır) |
| BorrowedQuantity | decimal(18,4) |  | E | Ödünç miktarı | ERP | hata (satır atlanır) |
| PaidBackQuantity | decimal(18,4) |  | H | Geri ödenen miktar | ERP | yok |
| BorrowDate | date | UK | E | Ödünç tarihi | ERP | hata (satır atlanır) |
| PaybackDueDate | date |  | H | Geri ödeme tarihi | ERP | bilinmiyor |

### stg.Stock
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Arz ve stok</sub>

- Stok; lot ve durum bazında. Sahip: proje, müşteri, sipariş ya da ortak.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | BOŞSA |
|---|---|---|---|---|---|---|
| LocationCode | nvarchar(30) | UK,REF | E | Lokasyon kodu | ERP | hata (satır atlanır) |
| MaterialCode | nvarchar(50) | UK,REF | E | Malzeme | ERP | hata (satır atlanır) |
| Warehouse | nvarchar(30) | UK | H | Depo | ERP | bilinmiyor |
| LotNo | nvarchar(50) | UK | H | Lot / seri | ERP | bilinmiyor |
| Status | nvarchar(50) | UK | H | ERP'den ham stok durumu; veri kurallarında kullanılır, değer listesi yok | ERP | bilinmiyor |
| ProjectCode | nvarchar(50) | UK,REF | H | Sahip proje; proje, müşteri ve sipariş boşsa stok ortaktır | ERP | yok |
| CustomerCode | nvarchar(50) | UK,REF | H | Sahip müşteri; stoğun ayrıldığı müşteri, ileride kullanılmak üzere | ERP | yok |
| SalesOrderNo | nvarchar(30) | UK,REF | H | Sahip sipariş no; stoğun ayrıldığı sipariş, ileride kullanılmak üzere | ERP | yok |
| SalesOrderLineNo | int | UK,REF | H | Sahip sipariş satırı; stoğun ayrıldığı sipariş satırı, ileride kullanılmak üzere | ERP | yok |
| SalesOrderLineItemNo | int | UK,REF | H | Bağlı sipariş alt satırı | ERP | yok |
| Quantity | decimal(18,4) |  | E | Miktar | ERP | hata (satır atlanır) |
| Uom | nvarchar(10) | REF | H | Miktarın birimi; boşsa malzemenin temel biriminde kabul edilir, doluysa birim dönüşümüyle çevrilir | ERP | temel birim |
| QualityEntryDate | date |  | H | Kaliteye giriş tarihi | ERP | bilinmiyor |
| ExpectedAcceptanceDate | date |  | H | Kalitedeki stoğun kullanılabilir hâle gelmesi beklenen tarih | ERP | bilinmiyor |
| ExpiryDate | date |  | H | Son kullanma tarihi (raf ömrü sonraki faz) | ERP | sınırsız |
| IsAvailable | bit |  | H | Stok planda kullanılabilir; Status ve depoya göre veri kuralıyla doldurulur | ERP, yoksa kural | yok |
| IsInQuality | bit |  | H | Stok planda kalitede sayılır; Status ve depoya göre veri kuralıyla doldurulur | ERP, yoksa kural | yok |
| IsBlocked | bit |  | H | Stok planda bloke sayılır; Status ve depoya göre veri kuralıyla doldurulur | ERP, yoksa kural | yok |
| IsActive | bit |  | H | Aktif mi | ERP, yoksa kural | hata (kurallardan sonra) |
| IsCustomTracked | bit |  | H | Stok düzeyinde özel takip | ERP, yoksa kural | yok |
| AdditionalText1–3 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | yok |
| AdditionalNumber1–2 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | yok |

### stg.WorkOrder
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Arz ve stok</sub>

- Açık iş emri (üretim, fason, yeniden işleme).  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | BOŞSA |
|---|---|---|---|---|---|---|
| LocationCode | nvarchar(30) | UK,REF | E | Lokasyon kodu | ERP | hata (satır atlanır) |
| WorkOrderNo | nvarchar(30) | UK | E | İş emri no | ERP | hata (satır atlanır) |
| MaterialCode | nvarchar(50) | REF | E | Üretilen malzeme | ERP | hata (satır atlanır) |
| ProductionVersionCode | nvarchar(30) | REF | H | Üretim versiyonu; iş emrinin kendi bileşen ve operasyon satırları geldiyse motor onları kullanır, gelmediyse bu versiyonun ağacına ve rotasına gider | ERP | bilinmiyor |
| ProductionOrderType | nvarchar(50) |  | H | ERP'den ham iş emri tipi; veri kurallarında kullanılır, değer listesi yok | ERP | bilinmiyor |
| Status | nvarchar(50) |  | H | ERP'den ham iş emri durumu; veri kurallarında kullanılır, değer listesi yok | ERP | bilinmiyor |
| Priority | int |  | H | İş emri önceliği | ERP | yok |
| OrderedQuantity | decimal(18,4) |  | E | İş emri miktarı | ERP | hata (satır atlanır) |
| OpenQuantity | decimal(18,4) |  | E | Açık miktar | ERP | hata (satır atlanır) |
| CompletedQuantity | decimal(18,4) |  | H | Tamamlanan miktar | ERP | yok |
| ScrapQuantity | decimal(18,4) |  | H | Hurda miktarı | ERP | yok |
| Uom | nvarchar(10) | REF | H | Miktarların birimi; boşsa malzemenin temel biriminde kabul edilir, doluysa birim dönüşümüyle çevrilir | ERP | temel birim |
| StartDate | date |  | H | Başlangıç | ERP | bilinmiyor |
| DueDate | date |  | E | Bitiş | ERP | hata (satır atlanır) |
| ProjectCode | nvarchar(50) | REF | H | Proje (ayraç) | ERP | yok |
| CustomerCode | nvarchar(50) | REF | H | Müşteri | ERP | yok |
| SalesOrderNo | nvarchar(30) | REF | H | Bağlı sipariş no (ayraç) | ERP | yok |
| SalesOrderLineNo | int | REF | H | Bağlı sipariş satır no | ERP | yok |
| SalesOrderLineItemNo | int | REF | H | Bağlı sipariş alt satırı | ERP | yok |
| ParentWorkOrderNo | nvarchar(30) | REF | H | Yeniden işlemede orijinal iş emri | Kural ya da elle | yok |
| LastActivityDate | date |  | H | Son hareket tarihi (eskime kontrolü) | ERP | bilinmiyor |
| IsFixed | bit |  | H | Motor bu iş emrinin tarihini ve miktarını değiştirmez | ERP, yoksa kural | yok |
| IsReleased | bit |  | H | İş emri yayınlandı; Status'tan veri kuralıyla doldurulur | ERP, yoksa kural | yok |
| IsStarted | bit |  | H | İş emri başladı; Status'tan veri kuralıyla doldurulur | ERP, yoksa kural | yok |
| IsProduction | bit |  | H | Üretim iş emri; ProductionOrderType'tan veri kuralıyla doldurulur | ERP, yoksa kural | yok |
| IsSubcontract | bit |  | H | Fason iş emri; ProductionOrderType'tan veri kuralıyla doldurulur | ERP, yoksa kural | yok |
| IsRework | bit |  | H | Yeniden işleme iş emri; ProductionOrderType'tan veri kuralıyla doldurulur | ERP, yoksa kural | yok |
| IsOnHold | bit |  | H | Bekletilen iş emri | ERP, yoksa kural | yok |
| IsCustomTracked | bit |  | H | İş emri düzeyinde özel takip | ERP, yoksa kural | yok |
| AdditionalText1–3 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | yok |
| AdditionalNumber1–2 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | yok |

### stg.WorkOrderComponent
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Arz ve stok</sub>

- İş emrinin bileşenleri ve çekilen miktar.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | BOŞSA |
|---|---|---|---|---|---|---|
| LocationCode | nvarchar(30) | UK,REF | E | Lokasyon kodu | ERP | hata (satır atlanır) |
| WorkOrderNo | nvarchar(30) | UK,REF | E | İş emri | ERP | hata (satır atlanır) |
| MaterialCode | nvarchar(50) | UK,REF | E | Bileşen | ERP | hata (satır atlanır) |
| OperationNo | int | UK | H | Bağlı olduğu operasyon no (ihtiyaç tarihi için) | ERP | ilk operasyon |
| SequenceNo | int | UK | H | Sıra no; aynı bileşen iki kez geçerse operasyon no ile ayrışır | ERP | bilinmiyor |
| RequiredQuantity | decimal(18,4) |  | E | Gereken miktar | ERP | hata (satır atlanır) |
| IssuedQuantity | decimal(18,4) |  | H | Çekilen miktar | ERP | yok |
| UnitUsage | decimal(18,6) |  | H | Üretilen bir birim için bileşen miktarı | ERP | bilinmiyor |
| Uom | nvarchar(10) | REF | H | Bileşen miktarlarının birimi; boşsa bileşenin temel biriminde kabul edilir, doluysa birim dönüşümüyle çevrilir | ERP | temel birim |
| ScrapRatio | decimal(6,4) |  | H | Oran olarak fire (0,05 = %5) | ERP | yok |
| IsLotBasedUsage | bit |  | H | Doluysa bileşen üretilen miktardan bağımsız, her üretim lotu için sabit kullanılır; değilse birim başına | ERP | yok |
| IsPhantom | bit |  | H | Hayalet bileşen | ERP | yok |
| AdditionalText1–3 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | yok |
| AdditionalNumber1–2 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | yok |

### stg.WorkOrderOperation
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Arz ve stok</sub>

- İş emrinin operasyonları ve kalan iş.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | BOŞSA |
|---|---|---|---|---|---|---|
| LocationCode | nvarchar(30) | UK,REF | E | Lokasyon kodu | ERP | hata (satır atlanır) |
| WorkOrderNo | nvarchar(30) | UK,REF | E | İş emri | ERP | hata (satır atlanır) |
| OperationNo | int | UK | E | Operasyon no | ERP | hata (satır atlanır) |
| SequenceNo | int | UK | E | Operasyon içindeki alt sıra | ERP | hata (satır atlanır) |
| OperationName | nvarchar(150) |  | H | Operasyon adı | ERP | bilinmiyor |
| ResourceCode | nvarchar(50) | REF | H | Kaynak kodu | ERP | alternatif Kaynak grubu |
| ResourceGroupCode | nvarchar(50) | REF | H | Kaynak grubu | ERP | alternatif Kaynak |
| ResourceRole | nvarchar(10) |  | E | Primary \| Secondary | ERP, yoksa kural | hata (kurallardan sonra) |
| ResourceNumber | int |  | E | Operasyonda aynı anda kullanılan kaynak adedi | ERP, yoksa kural | hata (kurallardan sonra) |
| PlannedConsumption | decimal(18,6) |  | H | Planlanan tüketim | ERP | bilinmiyor |
| ConfirmedConsumption | decimal(18,6) |  | H | Teyit edilen tüketim | ERP | yok |
| Status | nvarchar(50) |  | H | ERP'den ham operasyon durumu; veri kurallarında kullanılır, değer listesi yok | ERP | bilinmiyor |
| IsCompleted | bit |  | H | Operasyon tamamlandı; Status'tan veri kuralıyla doldurulur | ERP, yoksa kural | yok |
| IsLotBasedUsage | bit |  | H | Doluysa tüketim üretilen miktardan bağımsız, lot başına sabit; pratikte hazırlık süresi | ERP | yok |
| IsSubcontracted | bit |  | H | Fason operasyon | ERP | yok |
| IsActive | bit |  | H | Operasyon plana dahil mi | ERP, yoksa kural | hata (kurallardan sonra) |
| ProductionLocation | nvarchar(50) |  | H | Lokasyonun alt tanımı (hol, hat); ileride kısıtlar için | ERP | bilinmiyor |
| TransferQuantity | decimal(18,4) |  | H | Transfer partisi | ERP | yok |
| WaitingTimeHours | decimal(9,2) |  | H | Operasyon öncesi kuyruk beklemesi | ERP | yok |
| TransferTimeHours | decimal(9,2) |  | H | Sonraki operasyona taşıma | ERP | yok |
| AdditionalText1–3 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | yok |
| AdditionalNumber1–2 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | yok |

### stg.PurchaseOrderLine
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Arz ve stok</sub>

- Açık satın alma ve fason siparişi satırı (ve talep).  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | BOŞSA |
|---|---|---|---|---|---|---|
| LocationCode | nvarchar(30) | UK,REF | E | Lokasyon kodu | ERP | hata (satır atlanır) |
| PurchaseOrderNo | nvarchar(30) | UK | E | Sipariş no | ERP | hata (satır atlanır) |
| LineNo | int | UK | E | Satır no | ERP | hata (satır atlanır) |
| OrderType | nvarchar(50) |  | H | ERP'den ham sipariş tipi; veri kurallarında kullanılır, değer listesi yok | ERP | bilinmiyor |
| SupplierCode | nvarchar(50) | REF | H | Tedarikçi | ERP | bilinmiyor |
| MaterialCode | nvarchar(50) | REF | E | Malzeme | ERP | hata (satır atlanır) |
| OpenQuantity | decimal(18,4) |  | E | Açık miktar | ERP | hata (satır atlanır) |
| OrderedQuantity | decimal(18,4) |  | H | Sipariş miktarı | ERP | bilinmiyor |
| ReceivedQuantity | decimal(18,4) |  | H | Teslim alınan miktar | ERP | yok |
| Uom | nvarchar(10) | REF | H | Miktarların birimi; boşsa malzemenin temel biriminde kabul edilir, doluysa birim dönüşümüyle çevrilir | ERP | temel birim |
| RequestedDate | date |  | H | İstenen tarih | ERP | bilinmiyor |
| ConfirmedDate | date |  | H | Tedarikçi teyit tarihi | ERP | bilinmiyor |
| ProjectCode | nvarchar(50) | REF | H | Proje | ERP | yok |
| CustomerCode | nvarchar(50) | REF | H | Müşteri | ERP | yok |
| SalesOrderNo | nvarchar(30) | REF | H | Bağlı sipariş no | ERP | yok |
| SalesOrderLineNo | int | REF | H | Bağlı sipariş satırı | ERP | yok |
| SalesOrderLineItemNo | int | REF | H | Bağlı sipariş alt satırı | ERP | yok |
| WorkOrderNo | nvarchar(30) | REF | H | Fasonda bağlı iş emri | ERP | yok |
| Status | nvarchar(50) |  | H | ERP'den ham sipariş durumu; veri kurallarında kullanılır, değer listesi yok | ERP | bilinmiyor |
| IsPurchaseRequest | bit |  | H | Satın alma talebi; OrderType'tan veri kuralıyla doldurulur | ERP, yoksa kural | yok |
| IsPurchase | bit |  | H | Satın alma siparişi; OrderType'tan veri kuralıyla doldurulur | ERP, yoksa kural | yok |
| IsSubcontract | bit |  | H | Fason siparişi; OrderType'tan veri kuralıyla doldurulur | ERP, yoksa kural | yok |
| IsActive | bit |  | H | Aktif mi | ERP, yoksa kural | hata (kurallardan sonra) |
| IsCustomTracked | bit |  | H | Satır düzeyinde özel takip | ERP, yoksa kural | yok |
| AdditionalText1–3 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | yok |
| AdditionalNumber1–2 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | yok |

### stg.ProductionConfirmation
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Arz ve stok</sub>

- Üretim gerçekleşmeleri: iş emri bazında stoğa girişler.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | BOŞSA |
|---|---|---|---|---|---|---|
| LocationCode | nvarchar(30) | UK,REF | E | Lokasyon kodu | ERP | hata (satır atlanır) |
| ConfirmationNo | nvarchar(30) | UK | E | Teyit no | ERP | hata (satır atlanır) |
| WorkOrderNo | nvarchar(30) | REF | E | İş emri | ERP | hata (satır atlanır) |
| MaterialCode | nvarchar(50) | REF | E | Üretilen malzeme | ERP | hata (satır atlanır) |
| ConfirmedQuantity | decimal(18,4) |  | E | Teyit miktarı | ERP | hata (satır atlanır) |
| StartDate | date |  | H | Başlangıç | ERP | bilinmiyor |
| EndDate | date |  | H | Bitiş | ERP | bilinmiyor |
| AdditionalText1–3 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | yok |
| AdditionalNumber1–2 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | yok |

### Yöntem 1 · API (ERP'nin servisleri)
<sub>26. Entegrasyon tasarımı · Yöntem 1 · API</sub>

- **Ne zaman:** ERP'nin REST (ya da SOAP) servisi varsa ve müşteri BT servis hesabı açabiliyorsa. Tercih edilen yol: artımlı çekim ve gün içi tazeleme mümkün.
- **Adaptör:** ERP başına bir adaptör: uç nokta listesi, kimlik doğrulama (servis hesabı, anahtar ya da token), sayfalama, alan eşlemesi. Adaptör ürünün dışında, kurulum paketinde 'entegrasyon tanımı' olarak gelir.
- **Çekim:** Varlık sırası referans verisinden işlem verisine. Sayfa sayfa (ör. 500 kayıt), her sayfa ham tabloya yazılır. Artımlı: LastModified ya da değişiklik günlüğü varsa yalnız değişenler; yoksa tam çekim.
- **Dayanıklılık:** Zaman aşımı 30 sn (parametre), geçici hatada 3 deneme artan aralıkla; kalıcı hatada varlık 'hata', diğerleri devam. Çağrı ve yanıt özetleri loglanır (gövde değil).
- **Şema değişikliği:** Yanıtta beklenen alan yoksa varlık hata, Entegrasyon ekranında 'eşlenmemiş alan'. Yeni alanlar yok sayılır.
- **Ağ:** ERP sunucusuna müşteri ağı içinden; güvenlik duvarında tek yön, tek port. Servis hesabı yalnız okuma yetkili.

### Yöntem 2 · SQL ham tablo + view (K-130)
<sub>26. Entegrasyon tasarımı · Yöntem 2 · SQL ham tablo + view</sub>

- **Ne zaman:** ERP'nin servisi yoksa ya da müşteri BT'si veritabanı düzeyinde çalışmayı tercih ediyorsa. Smartchain ERP veritabanına girmez; müşteri ETL'i ham tabloları doldurur.
- **Yer:** Smartchain'in SQL Server instance'ında ayrı entegrasyon veritabanı. Bağlantı tek ayardır (`IntegrationDatabase`): aynı instance, Windows kimliği, şifre saklanmaz. Servis hesapları bu veritabanında yalnız okur; müşteri ETL hesabı yalnız bu veritabanına yazar (docs/10).
- **Ham tablolar:** Müşteri ERP verisini kendi biçiminde `ERP_*` tablolarına yazar (ör. `ERP_Material`) ve belirli saatlerde yeniler. Biçim serbesttir, Smartchain bu tabloları okumaz.
- **View'lar:** Kurulumda tablo başına bir view `dbo` şemasına yazılır (ör. `View_Material`): sonucu sözleşme kolonlarıyla birebirdir (bu dosyadaki `stg.*` alan adları), eşleme tablosu yoktur. Ürün kodu müşteriye göre değişmez; view müşteriye özel kurulum verisidir.
- **Bitti sinyali:** Müşteri yenilemeye başlarken `ERP_LoadLog`'a satır açar, bitince `FinishedAt` yazar. Tablo zorunludur.

| KOLON | TİP | AÇIKLAMA |
|---|---|---|
| Id | bigint identity | Sinyal numarası |
| EntityName | nvarchar(60), boş olabilir | `stg` tablo adı (Material, BOM…); boşsa bütün tablolar |
| StartedAt | datetime2 | Yenilemenin başlangıcı |
| FinishedAt | datetime2, boş olabilir | Bitiş; yenileme sürerken boş |

- **Kurulum tavsiyesi:** Gece tam yenilemede toplu satır (`EntityName` boş), gün içi yenilemede tablo bazında satır.
- **Sinyal kuralı:** Bir tablo için kendi satırı ile toplu satırlara birlikte bakılır. En son başlayan bitmemişse "Veri güncellemesi devam ediyor": hata yazılmaz, önceki ham veri korunur. Değilse en son biten geçerlidir; son okunanla aynıysa "Yeni veri yok": atlanır, elle çekimde o satırda "Yine de oku" seçilebilir. Okuma sırasında yenileme başladıysa parti Tamamlanmadı olur.
- **Okuma:** Her zaman tam. Smartchain entegrasyon veritabanına yazmaz, DDL çalıştırmaz; okuma kaydı kendi tarafındadır (`ImportBatch.SourceObject`, `SignalId`). Satırlar Excel'le aynı kontrol kodundan geçer (K-129).
- **Uyum denetimi:** Her okumadan önce ve Bağlantıyı test et ile. Kolon adı birebir. Eksik zorunlu kolon ya da okunamayan view: tablo hatası, okunmaz, önceki ham veri korunur. Eksik isteğe bağlı kolon, fazla kolon, tip farkı: uyarı. Dönüşmeyen satır: satır hatası. Sözleşme değiştiyse satırda "yeniden denetle" görünür. Yeni ürün sürümü zorunlu alan eklerse sürüm notunda "view güncellemesi gerekir" yazılır.
- **View sürümleri:** Her denetim ve okumada tanım okunur, değiştiyse yeni sürüm kaydedilir (`adm.IntegrationViewVersion`), uyum denetimi başarısız olsa da. Smartchain view oluşturmaz ve geri yüklemez; geri dönüş kurulumcunundur.
- **Sorumluluk:** Ham tabloları doldurma, sinyal ve zamanlama müşteri BT'sinde; view'ları kurulum yazar; Smartchain sözleşmeyi (şablon), uyum denetimini ve önizlemeyi verir.

### View ile veri kuralı sınırı (K-130)
<sub>26. Entegrasyon tasarımı · View ve kural sınırı</sub>

- **Ölçüt:** Smartchain'in hiçbir zaman görmemesi gereken satır (başka şirket, test kaydı) view'da elenir; bugün dışarıda kalıp yarın girebilecek satır (pasif malzeme, kapalı sipariş) bir veri kuralıyla `IsActive` = Hayır olur (K-145; ayrı aktarım filtresi yok). Pasif satır validasyona girmez, load almaz.

| NEREDE | NE | ÖRNEK |
|---|---|---|
| View | Join, kolon adı, tip, birim dönüşümü, türetme, kesin kapsam | Rota süresi dk → saat; açık miktar = sipariş − teslim; başka şirket kodu elenir |
| Veri kuralı | Değer listeleri ve bayraklar; ham değer view'dan çevrilmeden gelir (K-110, K-121) | `Status` → `IsOnHold`; tedarik türü 'S' → `DefaultSupplyType` = Satın alma |
| Veri kuralı ile kapsam | Planlamacının görmesi gereken iş kapsamı: kural `IsActive` = Hayır yazar (K-145) | Pasif malzeme, kapalı sipariş |

- Kod bu sınırı zorlayamaz; kurulumda bu tabloya göre yazılır.

### Yöntem 3 · Excel şablonları
<sub>26. Entegrasyon tasarımı · Yöntem 3 · Excel şablonları</sub>

- **Ne zaman:** ERP'de tutulmayan ya da entegrasyonu olmayan varlıklar: kaynaklar, tahmin; ilk kurulumda tüm ana veri (takvim, vardiya ve duruş Excel'den gelmez, ekrandan girilir: K-65); ERP'den gelen veriyi düzeltmek için toplu düzeltme (15).
- **Şablon:** Sözleşmeden üretilir (02, K-110): 1. satır teknik alan adı, veri 2. satırdan; zorunlu alanın başlığı koyu. Etiket, açıklama, tip, boş bırakılırsa ne olacağı, Smartchain değerleri ve örnek 'Açıklama' sayfasında; gizli sürüm bilgisi. Eşleme yok: kolon adla bulunur. Açılır liste ve Excel doğrulaması yok: staging ERP'nin dilidir (K-58); değer listeli alanlarda farklı değerler veri kuralıyla bu değerlere çevrilir, ham alanlar bayrağa dönüştürülür (K-121); tutarsızlık doğrulamada görünür.
- **Yükleme:** Ekrandan sürükle-bırak (03): varlık ve sürüm tanıma, mod (ekle / güncelle ya da tam), satır bazlı ön kontrol, hata raporu, geçerli satırlarla devam. Hatalı satır ham veriye alınmaz, bulgu listesinde ve hata raporunda durur (K-129).
- **Anahtar:** Tablolardaki ANAHTAR kolonu veritabanı indeksi değildir: `stg` ham veridir, aynı anahtar aynı partide (hata) ve sonraki partide (normal) gelebilir. Tekrar kontrolü bu tanımı okur (K-129). `stg` tablolarının standart alanları: `StagingRowId`, `ImportBatchId`, `RowStatus`, `ErrorText`, `SourceRowNo` (kaynaktaki satır no).
- **Sınırlar:** Tek dosya tek varlık; 200.000 satır ve 100 MB (parametre); eski şablon sürümü uyarı verir. Excel yolu ERP'den gelen varlığın master'ı olamaz (çakışma: ERP ezer, alan ayarına göre).
- **Dışa aktarma:** Aynı şablonlarla ana veri dışa aktarılır, düzeltilir ve elle değer olarak geri yüklenir; plan çıktıları (satın alma talebi, iş emri açma) ERP'nin alışık olduğu sütun düzeninde Excel listesi.

### Alan eşleme ve dönüşüm kuralları
<sub>26. Entegrasyon tasarımı · Alan eşleme ve dönüşüm</sub>

- SQL yönteminde eşleme tanımı yoktur: dönüşümler view'dadır, sonuç sözleşme kolonlarıyla birebirdir (K-130). API yönteminde (Faz 2) adaptördedir. Hangisi nerede yapılır: "View ile veri kuralı sınırı".

| DÖNÜŞÜM TÜRÜ | ÖRNEK | KURAL |
|---|---|---|
| Doğrudan | ITEM_CODE → Material.Code | Tip ve uzunluk kontrolü; kırpma yok, uzunsa hata. |
| Kod listesi | Tedarik türü 'S' → DefaultSupplyType = Satın alma | Veri kuralı (K-110, K-121); view çevirmez. Birim kodu olduğu gibi gelir (K-112). |
| Birim dönüşümü | Rota süresi dakika → kaynak kapasite birimi saat | Kaynağın CapacityUnit'ine çevrilir; dönüşüm yoksa uyarı, kaynak kısıtsız sayılır. |
| Birim dönüşümü · ters yön | M → KG tanımlı, KG → M tanımlı değil | Açıkça yazılan dönüşüm her zaman olduğu gibi kullanılır. 1/Factor yalnız ters yön hiç tanımlanmamışsa, kullanıldığı anda tam hassasiyetle hesaplanır, saklanmaz. |
| Birim dönüşümü · zincir | KOLİ → ADET ve ADET → KG tanımlı | Zincirleme dönüşüm türetilmez: KOLİ → KG hesaplanmaz; gerekiyorsa ayrıca tanımlanır. |
| Birim dönüşümü · lokasyon | HAM-001 iki lokasyonda var, dönüşüm satırı bir tane | UomConversion lokasyondan bağımsızdır, LocationCode taşımaz. MaterialCode, o koda sahip bütün lokasyonlardaki malzemeye uygulanır; kod→Id çevirisinde dönüşüm satırı aynı koddaki her lokasyonun malzemesine bağlanır. |
| Tarih | '20261023' → 2026-10-23; vade: ConfirmedDate yoksa RequestedDate | Biçim view'da ya da adaptörde; boş tarihin anlamı alanın BOŞSA kolonundadır, gerekirse veri kuralıyla doldurulur. |
| Türetme | İş emri: açık miktar = sipariş − teslim | View'da ya da adaptörde; sözleşme alanı tek değer alır. |
| Birleştirme | Stok: depo + lot + durum + proje → tek satır | Anahtar sözleşmede; ERP daha ayrıntılıysa toplanır, daha kabasa alanlar boş kalır (anlamı BOŞSA kolonunda). |
| Smartchain alanı | Resource.DailyCapacity, verim | Entegre edilmez (K-117); Smartchain ekranında tanımlanır. |

### İlişki haritası (K-146)
<sub>26. Entegrasyon tasarımı · Referans kontrolü ve kod→Id</sub>

- Her ilişki alanının baktığı tablo ve anahtar. Validasyon (fonksiyon 04) referans ve pasif ebeveyn kurallarını buradan üretir; load (fonksiyon 05, 5.2) kodu `core` Id'sine bu haritayla çevirir. Kodda `app/integration/references.py`; test ikisini karşılaştırır.
- **İLİŞKİ:** Zorunlu: sözleşmede alan zorunludur (ZOR. E); yoksa Hata, satır load edilmez. İsteğe bağlı: alan boş bırakılabilir; doluysa ve yoksa Uyarı, satır load edilir, bağlantı boş yazılır. **Zorunlu (doluysa)** istisnadır: rota ve iş emri operasyonundaki kaynak ve kaynak grubu sözleşmede isteğe bağlıdır (biri dolu olmalı, K-116), ama doluysa ve yoksa Hata, satır load edilmez: kaynağı boşaltılarak yüklenen operasyon kapasite tüketmez, rota sessizce bozulur.
- **PASİF EBEVEYN:** ebeveyn bulunur ama `IsActive` = Hayır ise satırdaki bulgunun sınıfı; satır load edilmez. "—": bulgu yazılmaz, load ebeveyn yokmuş gibi davranır (zorunluysa satır yüklenmez, isteğe bağlıysa bağlantı boş).
- **Eşleşme:** ALAN ve EBEVEYN ANAHTARI aynı sırayla eşleşir. Birden çok alanlı ilişkide (bağlı sipariş satırı) ilk alan doluysa bakılır; öteki alanlar boşsa eşleşmeyi daraltmaz. Proje, müşteri, tedarikçi ve proje grubu lokasyondan bağımsızdır; birim dönüşümünün malzemesi herhangi bir lokasyonda bulunursa yeter (K-112).
- **Ortak ve dışarıda:** `LocationCode` → Lokasyon (`Code`) her tabloda zorunludur (`ALL.REF_LOCATION`), tabloda ayrıca yazılmaz. Birim alanları (`BaseUom`, `FromUom`, `ToUom`, `ComponentUom`, `Uom`, `CapacityUnit`) referans kontrolüne girmez (K-112); dönüşümü `ALL.UOM_CONVERSION` denetler.

| TABLO | ALAN | EBEVEYN | EBEVEYN ANAHTARI | İLİŞKİ | PASİF EBEVEYN | KOD |
|---|---|---|---|---|---|---|
| UomConversion | MaterialCode | Material | Code | İsteğe bağlı | — | UOM.REF_MATERIAL |
| ProductionVersion | LocationCode + MaterialCode | Material | LocationCode + Code | Zorunlu | Bilgi | PV.REF_MATERIAL |
| ProductionVersion | LocationCode + BOMCode + MaterialCode | BOM | LocationCode + Code + MaterialCode | Zorunlu | — | PV.REF_BOM |
| ProductionVersion | LocationCode + RouteCode | Routing | LocationCode + RouteCode | Zorunlu | — | PV.REF_ROUTE |
| BOM | LocationCode + MaterialCode | Material | LocationCode + Code | Zorunlu | — | BOM.REF_MATERIAL |
| BOM | LocationCode + ComponentMaterialCode | Material | LocationCode + Code | Zorunlu | Uyarı | BOM.REF_COMPONENT |
| Routing | LocationCode + ResourceCode | Resource | LocationCode + Code | Zorunlu (doluysa) | Uyarı | RTG.REF_RESOURCE |
| Routing | LocationCode + ResourceGroupCode | ResourceGroup | LocationCode + Code | Zorunlu (doluysa) | — | RTG.REF_RESOURCE_GROUP |
| MaterialReference | LocationCode + MaterialCode | Material | LocationCode + Code | Zorunlu | — | REF.REF_MATERIAL |
| MaterialReference | LocationCode + ReferenceMaterialCode | Material | LocationCode + Code | Zorunlu | — | REF.REF_REFERENCE_MATERIAL |
| MaterialReference | LocationCode + ReferenceProductionVersionCode + ReferenceMaterialCode | ProductionVersion | LocationCode + Code + MaterialCode | İsteğe bağlı | — | REF.REF_REFERENCE_VERSION |
| Resource | SubcontractorCode | Supplier | Code | İsteğe bağlı | — | RES.REF_SUBCONTRACTOR |
| ResourceGroupAssignment | LocationCode + ResourceGroupCode | ResourceGroup | LocationCode + Code | Zorunlu | — | RGA.REF_RESOURCE_GROUP |
| ResourceGroupAssignment | LocationCode + ResourceCode | Resource | LocationCode + Code | Zorunlu | — | RGA.REF_RESOURCE |
| EmployeeAbsence | LocationCode + ResourceCode | Resource | LocationCode + Code | Zorunlu | — | ABS.REF_RESOURCE |
| MaterialSupplier | LocationCode + MaterialCode | Material | LocationCode + Code | Zorunlu | — | MS.REF_MATERIAL |
| MaterialSupplier | SupplierCode | Supplier | Code | Zorunlu | Uyarı | MS.REF_SUPPLIER |
| Project | ProjectGroupCode | ProjectGroup | Code | İsteğe bağlı | — | PRJ.REF_PROJECT_GROUP |
| SalesOrderLine | CustomerCode | Customer | Code | Zorunlu | Uyarı | SO.REF_CUSTOMER |
| SalesOrderLine | LocationCode + MaterialCode | Material | LocationCode + Code | Zorunlu | Uyarı | SO.REF_MATERIAL |
| SalesOrderLine | ProjectCode | Project | Code | İsteğe bağlı | — | SO.REF_PROJECT |
| Forecast | LocationCode + MaterialCode | Material | LocationCode + Code | Zorunlu | Uyarı | FC.REF_MATERIAL |
| Forecast | CustomerCode | Customer | Code | İsteğe bağlı | — | FC.REF_CUSTOMER |
| Forecast | ProjectCode | Project | Code | İsteğe bağlı | — | FC.REF_PROJECT |
| Stock | LocationCode + MaterialCode | Material | LocationCode + Code | Zorunlu | Bilgi | STK.REF_MATERIAL |
| Stock | ProjectCode | Project | Code | İsteğe bağlı | — | STK.REF_PROJECT |
| Stock | CustomerCode | Customer | Code | İsteğe bağlı | — | STK.REF_CUSTOMER |
| Stock | LocationCode + SalesOrderNo + SalesOrderLineNo + SalesOrderLineItemNo | SalesOrderLine | LocationCode + OrderNo + LineNo + LineItemNo | İsteğe bağlı | — | STK.REF_SALES_ORDER |
| BorrowPayback | LocationCode + MaterialCode | Material | LocationCode + Code | Zorunlu | — | BP.REF_MATERIAL |
| BorrowPayback | LendingProjectCode | Project | Code | Zorunlu | — | BP.REF_LENDING_PROJECT |
| BorrowPayback | BorrowingProjectCode | Project | Code | Zorunlu | — | BP.REF_BORROWING_PROJECT |
| WorkOrder | LocationCode + MaterialCode | Material | LocationCode + Code | Zorunlu | Uyarı | WO.REF_MATERIAL |
| WorkOrder | LocationCode + ProductionVersionCode + MaterialCode | ProductionVersion | LocationCode + Code + MaterialCode | İsteğe bağlı | — | WO.REF_VERSION |
| WorkOrder | ProjectCode | Project | Code | İsteğe bağlı | — | WO.REF_PROJECT |
| WorkOrder | CustomerCode | Customer | Code | İsteğe bağlı | — | WO.REF_CUSTOMER |
| WorkOrder | LocationCode + SalesOrderNo + SalesOrderLineNo + SalesOrderLineItemNo | SalesOrderLine | LocationCode + OrderNo + LineNo + LineItemNo | İsteğe bağlı | — | WO.REF_SALES_ORDER |
| WorkOrder | LocationCode + ParentWorkOrderNo | WorkOrder | LocationCode + WorkOrderNo | İsteğe bağlı | — | WO.REF_PARENT_WORK_ORDER |
| WorkOrderComponent | LocationCode + WorkOrderNo | WorkOrder | LocationCode + WorkOrderNo | Zorunlu | — | WOC.REF_WORK_ORDER |
| WorkOrderComponent | LocationCode + MaterialCode | Material | LocationCode + Code | Zorunlu | — | WOC.REF_MATERIAL |
| WorkOrderOperation | LocationCode + WorkOrderNo | WorkOrder | LocationCode + WorkOrderNo | Zorunlu | — | WOO.REF_WORK_ORDER |
| WorkOrderOperation | LocationCode + ResourceCode | Resource | LocationCode + Code | Zorunlu (doluysa) | — | WOO.REF_RESOURCE |
| WorkOrderOperation | LocationCode + ResourceGroupCode | ResourceGroup | LocationCode + Code | Zorunlu (doluysa) | — | WOO.REF_RESOURCE_GROUP |
| PurchaseOrderLine | LocationCode + MaterialCode | Material | LocationCode + Code | Zorunlu | Uyarı | PO.REF_MATERIAL |
| PurchaseOrderLine | SupplierCode | Supplier | Code | İsteğe bağlı | Uyarı | PO.REF_SUPPLIER |
| PurchaseOrderLine | ProjectCode | Project | Code | İsteğe bağlı | — | PO.REF_PROJECT |
| PurchaseOrderLine | CustomerCode | Customer | Code | İsteğe bağlı | — | PO.REF_CUSTOMER |
| PurchaseOrderLine | LocationCode + SalesOrderNo + SalesOrderLineNo + SalesOrderLineItemNo | SalesOrderLine | LocationCode + OrderNo + LineNo + LineItemNo | İsteğe bağlı | — | PO.REF_SALES_ORDER |
| PurchaseOrderLine | LocationCode + WorkOrderNo | WorkOrder | LocationCode + WorkOrderNo | İsteğe bağlı | — | PO.REF_WORK_ORDER |
| ProductionConfirmation | LocationCode + WorkOrderNo | WorkOrder | LocationCode + WorkOrderNo | Zorunlu | — | PC.REF_WORK_ORDER |
| ProductionConfirmation | LocationCode + MaterialCode | Material | LocationCode + Code | Zorunlu | — | PC.REF_MATERIAL |

### Hangi veri nerede master
<sub>26. Entegrasyon tasarımı · Veri sahipliği</sub>

- Çift yönlü senkron yok. Her alanın tek bir sahibi var; sahibi dışındaki yerde yapılan değişiklik bir sonraki yüklemede alan ayarına göre ezilir ya da korunur.

| VERI | MASTER | SMARTCHAIN'DE | ÇAKIŞMA KURALI |
|---|---|---|---|
| Ana veri (malzeme, ağaç, rota, tedarikçi, müşteri, proje) | ERP | Salt okunur; elle değer alan bazında | ERP ezer; elle değer alan ayarına göre kalır (FieldDefinition.ManualOverrides) |
| Kaynak temel bilgisi (kod, ad, grup) | ERP ya da Excel | Salt okunur | Kaynağa göre |
| Kaynak planlama alanları (günlük kapasite, paralel adet, kapasite kaynağı, verim, hedef doluluk, fason parametreleri) | Smartchain | Ekranda tanımlanır, entegre edilmez (K-117) | Yüklemede ezilmez |
| Takvim, vardiya, duruş | Smartchain (K-65) | Ekrandan girilir | Smartchain değeri kalır |
| Siparişler, stok, iş emirleri, gerçekleşmeler | ERP | Salt okunur | Her yüklemede ERP; elle değişiklik yok (öncelik ve hedef tarih plan alanıdır, veri değil) |
| Tahmin | ERP ya da Excel | Excel ile yüklenir | Son yükleme geçerli; versiyonlu |
| Parametreler, senaryo tanımları, kurallar, elle değerler | Smartchain | Ekrandan | ERP'ye gitmez |
| Plan çıktıları (planlı sipariş, öneri) | Smartchain | Onaylı plan | Faz 1: Excel ile ERP'ye elle; Faz 2: API geri yazma, ERP belge no geri okunur |

### Senkron sıklığı ve zamanlama
<sub>26. Entegrasyon tasarımı · Senkron sıklığı</sub>

- **Gece tam çekim · 22:00:** Tüm ERP varlıkları tam çekim, doğrulama, tam yükleme (v+1), ardından senaryolar. Bitiş sınırı 06:00. Excel varlıkları son yüklenen haliyle kalır.
- **Gün içi kısmi · elle ya da zamanlanmış:** İşlem verisi grupları (Talep, Stok, Üretim, Satın alma, İzin) Key user tarafından ya da System owner'ın kurulumda tanımladığı ikinci bir akışla (ör. öğlen Talep ve Stok) kısmi yüklenir; ana veri yalnız tam yüklemede gelir (K-150). Hedef 5 dk altı.
- **Haftalık ve elle:** Tahmin ve kaynak: haftalık ya da değişince Excel ile; takvim ve vardiya ekrandan (K-65). Ham veri temizliği Pazar 03:00.
- **Artımlı çekim:** SQL her zaman tam okur (K-130). API'de (Faz 2) LastModified varsa yalnız değişenler; silinenler için tam liste gerekir (A-23). Artımlı destek yoksa tam çekim (varsayılan).
- **Zamanlama ayarı:** Saatler ve paralellik Entegrasyon ekranında (Admin); bitiş sınırı ve işçi sayısı System owner ayarı. Müşterinin ERP gece işleriyle çakışmaması için saat devreye almada belirlenir.
- **Çakışma yönetimi:** Gece akışı sırasında elle çekim kapalı; gün içi kısmi yükleme sırasında ikinci yükleme kuyrukta bekler. Yükleme açık çalışmaları etkilemez.

### Hata yönetimi
<sub>26. Entegrasyon tasarımı · Hata yönetimi</sub>

- Hata dört düzeyde ele alınır: bağlantı, varlık, satır, alan. Her düzeyin davranışı sabit; kullanıcıya nerede ne olduğu ve ne yapması gerektiği söylenir.

| DÜZEY | ÖRNEK | DAVRANIŞ | NEREDE GÖRÜNÜR |
|---|---|---|---|
| Bağlantı | API ulaşılamıyor, SQL kimlik hatası, zaman aşımı | 3 deneme artan aralıkla; sonra varlık 'hata', önceki ham veri korunur; diğer varlıklar devam | Veri yükleme ekranı, Entegrasyon 'son çağrı', Sistem sağlığı |
| Varlık | Şema uyumsuzluğu, eşlenmemiş alan, hata eşiği aşımı (tablo başına, varsayılansız, K-135) | Varlık yüklenmez, önceki versiyonun satırları taşınır (kısmi); ana sayfada kırmızı | Veri yükleme, Entegrasyon 'eşlenmemiş alan', Ana sayfa |
| Satır | Zorunlu alan boş, zorunlu referans yok, negatif süre, döngü | Ön kontrolde satır atlanır; validasyonda Hata bulunan satır load edilmez; bulgu listesine yazılır; eşik altındaysa varlık yüklenir. İsteğe bağlı bağlantı yoksa Uyarı, satır yüklenir, bağlantı boş (K-146) | Doğrulama detayı, hata raporu (xlsx) |
| Alan | Boş malzeme seviyesi, boş tedarik türü | Veri kuralıyla tamamlanır; dolmazsa BOŞSA kolonu geçerlidir: "hata (kurallardan sonra)" ise satır Hata, değilse alan boş kalır (K-138) | Doğrulama, Veri kalitesi, Ana veri (kaynak etiketi) |
| Yükleme | Veritabanı hatası, süre aşımı (30 dk) | Ya hep ya hiç: geri alınır, önceki versiyon geçerli; parti yeniden kullanılabilir | Veri yükleme, Sistem sağlığı, destek paketi |
| Sessiz hata | Satır sayısı dünden %30 az, sipariş sayısı sıfır | Tutarlılık uyarısı: yükleme durmaz ama 'şüpheli parti' etiketi, ana sayfada (öneri) | Ana sayfa, Veri yükleme |

### Smartchain'den ERP'ye · Faz 1 Excel, Faz 2 API
<sub>26. Entegrasyon tasarımı · Smartchain'den ERP'ye</sub>

- **Faz 1 · Excel listeleri:** Onaylı plandan: satın alma talebi listesi (tedarikçi, malzeme, yuvarlanmış miktar, tarih), iş emri açma listesi (ürün, miktar, kaynak, dönem), fason listesi, öneri aksiyonları (öne çek / ertele / iptal). Sütun düzeni müşterinin ERP ithalat şablonuna göre ayarlanır (kurulum verisi).
- **ERP belge numarası geri:** ERP'de açılan sipariş bir sonraki gece çekimde gelir; eşleme ERP referans alanı ile (sipariş notu ya da dış belge no, kurulumda belirlenir) ya da aksiyon listesinde elle girilen numarayla. Öneri takibi (R19) bu bağı kullanır.
- **Kapsam dışı:** Stok hareketi, üretim teyidi, sevkiyat gibi işlem kayıtları Smartchain'den ERP'ye hiçbir fazda yazılmaz; bunlar ERP'nin işi.
- **Faz 2 · API geri yazma:** Onaylanan planlı siparişler ERP'ye API ile yazılır (satın alma talebi, planlı iş emri); ERP belge numarası anında geri alınır. Yazma yetkisi ayrı servis hesabı; her yazma denetim izinde. Yalnız yeni belge; ERP'deki belgeyi değiştirme yok.

### Güvenlik ve erişim
<sub>26. Entegrasyon tasarımı · Güvenlik ve erişim</sub>

- **Servis hesapları:** API ve SQL için ayrı hesaplar; yalnız okuma. SQL'de Windows kimliği, şifre saklanmaz (K-130). API anahtarları (Faz 2) sunucuda şifreli saklanır, ekranda gösterilmez, destek paketine girmez.
- **Ağ:** Kapalı ağ; Smartchain sunucusu → ERP sunucusu tek yön. Güvenlik duvarı kuralı kurulum dokümanında; internet gerekmez.
- **Veri:** Ham veri ve geçerli veri Smartchain SQL Server'ında; yedekleme kurulum tasarımında (27). Kişisel veri: işçi adı yalnız vardiya planı için, parametreyle anonim kod kullanılabilir (öneri).
- **Log ve iz:** Her çağrı ve parti loglanır (gövde değil); elle tetiklemeler denetim izinde. Loglar destek paketiyle dışa alınır.
- **Değişiklik yönetimi:** Yöntem, bağlantı ve view adı değişikliği denetim izinde; view'ın önceki sürümleri okunabilir, geri dönüş kurulumcunundur (K-130).
- **Yetki (K-130):** Yöntem, veritabanı ve view adı: System owner. Çekim anahtarı, test ve önizleme: Admin ve üstü. Çekim ve yükleme: Key user ve üstü. Key user ayarları salt okunur görür, End user hiçbirini görmez.

### Entegrasyon devreye alma adımları
<sub>26. Entegrasyon tasarımı · Devreye alma</sub>

- **1 · Keşif:** ERP ve sürüm, servis var mı, veritabanı erişimi, hangi varlık nerede tutuluyor, hangi alanlar boş. Çıktı: yöntem kararı varlık başına.
- **2 · View'lar:** Tablo başına view, uyum denetimi ve önizleme; değer listeleri için veri kuralları; Smartchain'e özgü alanlar için kural taslakları. Çıktı: entegrasyon tanımı ve şablonlar.
- **3 · Test çekimi:** Her varlık için örnek çekim (ilk 200 satır), doğrulama raporu, eşlenmemiş alan ve hata listesi. Çıktı: düzeltme listesi (müşteri BT + biz).
- **4 · Tam yükleme ve kalite:** İlk tam yükleme, veri kalitesi raporu, kurallarla tamamlama; sentetik yerine gerçek veriyle ilk plan. Çıktı: v1 veri versiyonu.
- **5 · Paralel çalışma:** 2–4 hafta gece akışı; ana sayfa ve dünden bugüne ile izleme; ERP'ye Excel listesiyle giriş denemesi. Çıktı: hata eşiği ve zamanlama kararı.
- **6 · Canlı:** Onaylı plan yayını; aksiyon listesi ile ERP girişi; destek paketi ve geri bildirim düzeni.

### Devreye almada sorumluluklar
<sub>26. Entegrasyon tasarımı · Sorumluluk paylaşımı</sub>

- Kapalı ağ ve uzaktan erişim yokluğu nedeniyle müşteri BT'sinin payı büyüktür; her adımda kimin ne yapacağı yazılıdır.

| KONU | BIZ (SMARTCHAIN) | MÜŞTERI BT / KEY USER |
|---|---|---|
| Yöntem seçimi | Keşif, öneri, karar kaydı | ERP erişim bilgisi, servis / veritabanı imkânı |
| API adaptörü | Geliştirme, test, paket | Servis hesabı, uç nokta dokümanı, güvenlik duvarı |
| SQL ham tablo + view | Sözleşme, uyum denetimi, önizleme; view'ların kurulumda yazılması | ETL yazma, zamanlama, ham tabloları ve `ERP_LoadLog`'u doldurma |
| Excel | Şablonlar, yükleme eğitimi | Doldurma ve yükleme (Key user) |
| Eşleme ve kurallar | Taslak, kalite kontrolü | Onay, kod listelerinin anlamı |
| Zamanlama | Varsayılan 22:00, bitiş 06:00 | ERP gece işleriyle çakışma kontrolü |
| İzleme ve destek | Destek paketi, sürüm güncelleme | Ana sayfa, hata bildirimi, paket iletimi |

### Doğruluk raporları için ek veri ihtiyacı (A-22)
<sub>26. Entegrasyon tasarımı · Raporlar için ek veri (A-22)</sub>

- 25. adımdaki gerçekleşme raporları (16–20) ve değer göstergeleri için ERP'den ek veri gerekir. Hepsi 'isteğe bağlı' sınıfında: gelmezse ilgili rapor kapalı kalır, plan etkilenmez.

| VERI | ALANLAR | KULLANAN | YÖNTEM / SIKLIK |
|---|---|---|---|
| Sevkiyat / sipariş kapanışı (yeni varlık) | OrderNo, LineNo, ShipDate, ShippedQty, IsClosed | R17 Teslim performansı, R19 Öneri takibi, R18 | API · SQL · gece artımlı |
| Üretim gerçekleşmesi (mevcut, ek alan) | ReasonCode (sapma nedeni) | R16 Plan–gerçekleşen: iş emri ve miktar düzeyinde; kaynak ve operasyon kırılımı yok (K-128) | API · SQL · gece artımlı |
| Satın alma teslimatı (ek alan) | PurchaseOrderLine.ReceivedQuantity (K-125); ReceivedDate henüz sözleşmede yok | R19 Öneri takibi, R05 | API · SQL · gece |
| ERP belge eşlemesi (ek alan) | PurchaseOrderLine / WorkOrder.ExternalRef (Smartchain öneri no) | R19, Aksiyon listesi | API · SQL · gece |
| Tahmin geçmişi (versiyonlu) | Forecast.VersionDate (ay başı dondurulmuş tahmin) | R20 Tahmin doğruluğu | Excel · aylık |
| Birim maliyet (ek alan) | Material.UnitCost, Currency | R08 Stok projeksiyonu, R05 tutar, KPI panosu | API · SQL · Excel · gece |
| Sipariş iptal bilgisi (ek alan) | SalesOrderLine.CancelledAt, CancelReason | R20, Dünden bugüne | API · SQL · gece |

### Açık konular ve kararlar
<sub>26. Entegrasyon tasarımı · Açık konular</sub>

- **Artımlı çekim ve silinenler:** SQL her zaman tam okur (K-130). API'de: haftada bir tam çekim önerilir (A-23, 11.5).
- **ERP belge numarası eşlemesi:** Faz 1'de ERP'de açılan siparişin Smartchain önerisine bağı: ERP'de dış referans alanı var mı, yoksa aksiyon listesinde elle mi? Kurulumda müşteriye göre.
- **Sessiz hata eşiği:** Satır sayısı dünden %30 az ise 'şüpheli parti' uyarısı: eşik parametre mi, sabit mi? (öneri: parametre, varsayılan %30).
- **Kişisel veri:** İşçi adı yerine anonim kod kullanımı: müşteri tercihi; parametre olarak öneriyoruz.
- **Rota tüketim birimi:** Kapandı (K-130): dönüşüm view'da; kural istisna için.
- **Faz 2 geri yazma kapsamı:** Yalnız satın alma talebi mi, planlı iş emri de mi? Müşteri ERP'sinin planlı sipariş kavramına bağlı; keşifte netleşir.
