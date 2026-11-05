# Entegrasyon ve veri sözleşmesi (MDD adım 26)

Kaynak: Master Design Document (MDD) 26.10.2026. Bu dosya desteden üretilmiştir; değişiklik önce burada yapılır, deste dilim sonlarında buradan güncellenir (K-54).

### 26. Entegrasyon tasarımı
<sub>tamamlandı</sub>

- **Ne yapılacak:** ERP bağımsız, tek veri sözleşmesi, üç yöntem (API, SQL arayüz tabloları, Excel). İlkeler, mimari, varlık ve alan düzeyi sözleşme, yöntem detayları, eşleme ve dönüşüm, veri sahipliği, zamanlama, hata yönetimi, çıkış, güvenlik, devreye alma, raporlar için ek veri. Çıktı: entegrasyon tasarımı ve veri sözleşmesi
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
  - K-46  Tek veri sözleşmesi: şablon, SC_* arayüz tabloları ve API şeması aynı veri sözlüğünden üretilir; her varlık tek yöntemle beslenir.
  - K-47  Faz 1 yalnız okuma; plan çıktıları Excel listesi olarak ERP'ye elle girilir. Faz 2'de API ile geri yazma (yalnız yeni belge).
  - K-48  ERP ana veri ve işlem verisinde master; Kapasite tanımları (günlük kapasite, verim…) entegre edilmez, Smartchain ekranında tanımlanır (K-117); entegre edilen alanlarda ERP değeri FieldValueSource'ta saklanır.
  - K-49  SQL arayüz tablolarını müşteri ETL'i doldurur; Smartchain ERP veritabanına doğrudan girmez.
- **Açık konular**
  - A-23  Artımlı çekimde silinen kayıtlar: SC_ACTION mi, haftalık tam çekim mi?
  - A-24  ERP belge numarası ↔ Smartchain öneri bağı: ERP'de dış referans alanı var mı?
  - A-25  Rota tüketim birimi dönüşümü adaptörde mi, veri kuralında mı?

### Entegrasyon tasarım ilkeleri
<sub>26. Entegrasyon tasarımı · Entegrasyon ilkeleri</sub>

- **Tek veri sözleşmesi:** Hangi yöntemle gelirse gelsin veri aynı sözleşmeye (varlık, alan, tip, anahtar, zorunluluk) iner. Sözleşme bu dosyadaki `stg.*` tablolarıdır; şablon, arayüz tablosu ve API şeması aynı kaynaktan türer. `FieldDefinition` yalnız etiket verir (K-110).
- **ERP bağımsız:** Ürün hiçbir ERP'ye özel alan taşımaz. ERP'ye özgü her şey adaptörde ve eşleme tanımında kalır; yeni ERP yeni adaptör demektir, ürün değişmez.
- **Yalnız okuma (Faz 1):** Smartchain ERP'den okur, ERP'ye yazmaz. Plan çıktıları Excel listesi olarak çıkar ve ERP'ye elle girilir. Geri yazma Faz 2 (API).
- **Üç yöntem, varlık başına bir tane:** API, SQL arayüz tabloları ve Excel. Her varlık tek yöntemle beslenir; yöntem müşteriye göre seçilir, karışık kurulum normaldir (ör. siparişler API, kaynaklar Excel).
- **Ham veri önce, dönüşüm sonra:** Gelen veri önce olduğu gibi ham tablolara (Staging) yazılır; doğrulama ve dönüşüm sonra. Sorunlu yükleme geriye dönük incelenebilir, ham veri 1 hafta saklanır.
- **Ham değer kurala girdidir (K-121):** ERP'den gelen ham değerler (Status, Type gibi) yalnız veri kurallarına girdidir; motor ve ekranlar bayrakları okur (IsActive, IsOnHold, IsReleased…). Bayraklar kurallarla ham değerden doldurulur. Ham değer ile bayrak çelişirse bayrak geçerlidir. Bütün tablolar için geçerlidir.
- **ERP ana veri sahibidir:** Ana veri ve işlem verisinde ERP master'dır. Smartchain'e özgü alanlar (verim, kritik kaynak, parametreler) Smartchain'de tutulur; ERP'de yoksa kural ya da elle değerle tamamlanır.
- **Hata izole edilir:** Bir varlığın hatası diğerlerini durdurmaz; satır hatası satırı atlatır, eşik aşımı varlığı dışarıda bırakır. Gece akışı bu kurallarla kendi kendine ilerler.
- **Versiyonlu ve ya hep ya hiç:** Her yükleme yeni veri versiyonu açar; ortada kalan yükleme geri alınır. Açık çalışmalar kendi versiyonunda kalır.
- **İzlenebilir:** Her çağrı, parti, satır sayısı ve hata loglanır; Entegrasyon ekranında 'son çağrı', Sistem sağlığında süreler. Müşteriyle konuşma dili: varlık, parti numarası, hata sınıfı.
- **Kapalı ağ:** Entegrasyon müşteri ağı içinde kalır: API ERP sunucusuna, arayüz tabloları aynı SQL Server'a ya da müşteri veritabanına. İnternet yok, servis hesapları salt okunur.

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
- **Ara veritabanı (SQL arayüz)**
  - Müşteri ETL'i SC_* tablolarını doldurur
  - Aynı SQL Server ya da ayrı
- **SQL okuyucu**
  - SC_* tablolarını toplu okur
  - LAST_MODIFIED ile artımlı
  - Eşleme: sütun adı = sözleşme
- **Doğrulama → yükleme**
  - Yapısal, referans, mantıksal, tutarlılık
  - Alan önceliği: ERP / kural / elle / varsayılan
  - Veri kuralları, türetilmiş alanlar (LLC)
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
- Tüm akış müşteri ağı içinde; internet yok. Her varlık tek yöntemle beslenir, üç yöntem aynı ham tabloya iner.

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

- Şablonu ve ekran 02'yi besler; sıra referans verisinden işlem verisine. Kod bu tablodan üretilir (`python db/generate.py`, K-64). Sürüm, sözleşme değişince burada artar. Transfer (TransferOrder) çok lokasyonda geldiği için `stg` tablosu ve şablonu yoktur (Faz 2).

| VARLIK | AD | SINIF | AÇIKLAMA | DOSYA ADI | SÜRÜM |
|---|---|---|---|---|---|
| Location | Lokasyon | Ana veri | Tesisler, depolar ve fason depoları | lokasyon | 2 |
| UomConversion | Birim dönüşümü | Ana veri | Malzeme bazında birimler arası çevrim oranları | birim-donusumu | 2 |
| Material | Malzeme | Ana veri | Hammadde, yarı mamul ve nihai ürünler ile planlama bilgileri | malzeme | 3 |
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

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| LocationCode | nvarchar(30) | UK,REF | E | Lokasyon kodu | ERP | hata (satır atlanır) |
| Code | nvarchar(50) | UK | E | Malzeme kodu | ERP | hata (satır atlanır) |
| Name | nvarchar(200) |  | H | Malzeme adı | ERP | boş kalır |
| BaseUom | nvarchar(10) | REF | E | Temel birim | ERP | hata (satır atlanır) |
| MaterialGroup | nvarchar(50) |  | H | Malzeme grubu | ERP | boş kalır |
| MaterialLevel | nvarchar(15) |  | H | Hammadde \| Yarı mamul \| Nihai ürün | ERP, yoksa kural | kural ya da elle |
| MaterialType | nvarchar(50) |  | H | Malzeme tipi | ERP | boş kalır |
| Brand | nvarchar(50) |  | H | Marka | ERP | boş kalır |
| PlannerCode | nvarchar(50) |  | H | Planlamacı | ERP | boş kalır |
| MRPGroup | nvarchar(50) |  | H | MRP grubu; planlama parametreleri aynı olan malzemeleri gruplar | ERP | boş kalır |
| IsActive | bit |  | H | Aktif | ERP, yoksa kural | kural ya da elle |
| IsCritical | bit |  | H | Kritik malzeme; malzeme kısıtı yalnız kritik malzemelere uygulanır, kritik olmayanın her zaman temin edilebildiği varsayılır | ERP, yoksa kural | kural ya da elle |
| IsPurchasable | bit |  | H | Satın alınabilir | ERP, yoksa kural | kural ya da elle |
| IsProducible | bit |  | H | Üretilebilir | ERP, yoksa kural | kural ya da elle |
| IsSellable | bit |  | H | Satılabilir | ERP, yoksa kural | kural ya da elle |
| IsSubcontractable | bit |  | H | Fasona verilebilir | ERP, yoksa kural | kural ya da elle |
| DefaultSupplyType | nvarchar(10) |  | H | Üretim \| Satın alma \| Fason | ERP, yoksa kural | kural ya da elle |
| IsCustomerSupplied | bit |  | H | Müşteri temin malzemesi | Kural ya da elle | kural ya da elle |

### stg.Material
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Malzeme · 2/2</sub>

- Malzeme ve planlama ana verisi.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| IsCustomTracked | bit |  | H | Malzeme ortak havuzdan değil, belli bir talebe (proje, müşteri ya da sipariş) ayrılmış olarak takip edilir; hangi talebe ayrıldığı talep kaydından gelir | Kural ya da elle | varsayılan 0 |
| IsPhantom | bit |  | H | Hayalet yarı mamul | ERP | varsayılan 0 |
| GoodsReceiptDays | decimal(9,2) |  | H | Mal kabul süresi (iş günü) | ERP, yoksa kural | kural ya da elle |
| SafetyStock | decimal(18,4) |  | H | Güvenlik stoğu | ERP | varsayılan 0 |
| StockCoverageDays | decimal(9,2) |  | H | Gün cinsinden güvenlik stoğu | ERP | boş kalır |
| MaxStock | decimal(18,4) |  | H | Maksimum stok | ERP | boş kalır |
| LotSizePolicy | nvarchar(15) |  | H | Üretimde: Lot-for-lot \| Sabit \| Dönemsel | ERP, yoksa kural | kural ya da elle |
| MinLot | decimal(18,4) |  | H | Üretimde minimum | ERP | boş kalır |
| MaxLot | decimal(18,4) |  | H | Üretimde maksimum | ERP | boş kalır |
| LotMultiple | decimal(18,4) |  | H | Üretimde kat | ERP | boş kalır |
| QtyPerBox | decimal(18,4) |  | H | Temel birimde kutu içi miktar | ERP | boş kalır |
| QtyPerPallet | decimal(18,4) |  | H | Temel birimde palet içi miktar | ERP | boş kalır |
| ScrapRatio | decimal(6,4) |  | H | Oran olarak fire (0,05 = %5) | ERP | varsayılan 0 |
| ShelfLifeDays | int |  | H | Raf ömrü (gün); Faz 1'de yalnız uyarı | ERP | boş kalır |
| AdditionalText1–7 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | boş kalır |
| AdditionalNumber1–3 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | boş kalır |

### stg.Location
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Ortak</sub>

- Lokasyon (tesis, depo). Faz 1'de her lokasyon kendi içinde planlanır.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| Code | nvarchar(30) | UK | E | Lokasyon kodu | ERP | hata (satır atlanır) |
| Name | nvarchar(100) |  | H | Lokasyon adı | ERP | boş kalır |
| Type | nvarchar(15) |  | E | Tesis \| Depo \| Fason deposu | ERP, yoksa kural | varsayılan Tesis |
| IsFactory | bit |  | H | Tesis mi | Kural, ERP ya da Excel | kural, yoksa varsayılan 0 |
| IsDepot | bit |  | H | Depo mu | Kural, ERP ya da Excel | kural, yoksa varsayılan 0 |
| IsSubcontractor | bit |  | H | Fason deposu mu | Kural, ERP ya da Excel | kural, yoksa varsayılan 0 |
| IsActive | bit |  | H | Aktif mi | Kural, ERP ya da Excel | kural, yoksa varsayılan 1 |
| Country | nvarchar(100) |  | H | Ülke | ERP | boş kalır |
| CountryCode | nvarchar(10) |  | H | Ülke kodu | ERP | boş kalır |
| Region | nvarchar(100) |  | H | Bölge | ERP | boş kalır |
| RegionCode | nvarchar(20) |  | H | Bölge kodu | ERP | boş kalır |
| City | nvarchar(100) |  | H | Şehir | ERP | boş kalır |
| CityCode | nvarchar(20) |  | H | Şehir kodu | ERP | boş kalır |
| AdditionalText1–7 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | boş kalır |
| AdditionalNumber1–3 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | boş kalır |

### stg.UomConversion
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Ortak</sub>

- Malzeme bazında birim dönüşümü.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| MaterialCode | nvarchar(50) | UK,REF | H | Malzeme (boşsa genel dönüşüm) | ERP | boş kalır |
| FromUom | nvarchar(10) | UK,REF | E | Kaynak birim | ERP | hata (satır atlanır) |
| FromUomName | nvarchar(50) |  | H | Kaynak birim adı | ERP | boş kalır |
| ToUom | nvarchar(10) | UK,REF | E | Hedef birim | ERP | hata (satır atlanır) |
| ToUomName | nvarchar(50) |  | H | Hedef birim adı | ERP | boş kalır |
| Factor | decimal(18,6) |  | E | 1 kaynak birim = çarpan × hedef birim | ERP | hata (satır atlanır) |

### stg.ProductionVersion
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Malzeme</sub>

- Üretim versiyonu: bir malzemenin ürün ağacı ve rota başlığı; rotaya RouteCode, ürün ağacına BOMCode ile bağlanır. Versiyon seçimi motorun kararıdır; aynı malzeme aynı dönemde birden fazla versiyonla üretilebilir.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| LocationCode | nvarchar(30) | UK,REF | E | Lokasyon kodu | ERP | hata (satır atlanır) |
| MaterialCode | nvarchar(50) | UK,REF | E | Üretilen malzeme | ERP | hata (satır atlanır) |
| Code | nvarchar(30) | UK | E | Versiyon kodu | ERP | hata (satır atlanır) |
| Name | nvarchar(100) |  | H | Versiyon adı | ERP | boş kalır |
| Type | nvarchar(50) |  | H | Versiyonları ayrıştırmak için kurallarda kullanılır; değer listesi yok | ERP | boş kalır |
| IsActive | bit |  | H | Aktif | ERP, yoksa kural | kural ya da elle |
| Priority | int |  | H | Versiyonlar arası tercih bilgisi; motora girdi | ERP | boş kalır |
| BaseQuantity | decimal(18,4) |  | H | Baz miktar (rota ve ağaç bu miktar için) | ERP | varsayılan 1 |
| BOMCode | nvarchar(50) |  | E | Versiyonun kullandığı ürün ağacı | ERP | hata (satır atlanır) |
| RouteCode | nvarchar(50) |  | E | Rota kodu (Routing.RouteCode) | ERP | hata (satır atlanır) |
| ValidFrom | date |  | H | Geçerlilik başlangıcı | ERP | boş kalır |
| ValidTo | date |  | H | Geçerlilik bitişi | ERP | boş kalır |
| AdditionalText1–3 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | boş kalır |
| AdditionalNumber1–2 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | boş kalır |

### stg.BOM
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Malzeme</sub>

- Ürün ağacı satırı.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| LocationCode | nvarchar(30) | UK,REF | E | Lokasyon kodu | ERP | hata (satır atlanır) |
| MaterialCode | nvarchar(50) | UK | E | Üretilen malzeme kodu | ERP | hata (satır atlanır) |
| Code | nvarchar(50) | UK | E | Ürün ağacı kodu | ERP | hata (satır atlanır) |
| ComponentMaterialCode | nvarchar(50) | UK,REF | E | Bileşen kodu | ERP | hata (satır atlanır) |
| OperationNo | int | UK | H | Bağlı olduğu operasyon no (ihtiyaç tarihi için) | ERP | boş kalır |
| SequenceNo | int | UK | H | Sıra no; aynı bileşen iki kez geçerse operasyon no ile ayrışır | ERP | boş kalır |
| Quantity | decimal(18,6) |  | E | Baz miktar için bileşen miktarı | ERP | hata (satır atlanır) |
| ComponentUom | nvarchar(10) | REF | H | Bileşen miktarının birimi; boşsa bileşenin temel biriminde kabul edilir, doluysa birim dönüşümüyle çevrilir | ERP | varsayılan Bileşenin temel birimi |
| ScrapRatio | decimal(6,4) |  | H | Oran olarak fire (0,05 = %5) | ERP | varsayılan 0 |
| IsPhantom | bit |  | H | Hayalet bileşen | ERP | varsayılan 0 |
| IsLotBasedUsage | bit |  | H | Doluysa bileşen üretilen miktardan bağımsız, her üretim lotu için sabit kullanılır; değilse birim başına | ERP | varsayılan 0 |
| AlternativeGroup | nvarchar(50) |  | H | Aynı grup koduna sahip satırlar birbirinin alternatifidir | ERP | boş kalır |
| AlternativePriority | int |  | H | Grup içindeki tercih bilgisi | ERP | boş kalır |
| AdditionalText1–3 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | boş kalır |
| AdditionalNumber1–2 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | boş kalır |

### stg.Routing
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Malzeme · 1/2</sub>

- Rota: her satır bir operasyon–kaynak ilişkisi; sıra önce OperationNo, sonra SequenceNo. Aynı operasyonun kaynakları ayrı satırda, ResourceRole ile.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| LocationCode | nvarchar(30) | UK,REF | E | Lokasyon kodu | ERP | hata (satır atlanır) |
| RouteCode | nvarchar(50) | UK | E | Rota kodu | ERP | hata (satır atlanır) |
| OperationNo | int | UK | E | Operasyon no (birinci sıralama) | ERP | hata (satır atlanır) |
| SequenceNo | int | UK | E | Operasyon içindeki alt sıra (ikinci sıralama) | ERP | hata (satır atlanır) |
| OperationName | nvarchar(150) |  | H | Operasyon adı | ERP | boş kalır |
| ResourceCode | nvarchar(50) | REF | H | Kaynak kodu | ERP | alternatif Kaynak grubu |
| ResourceGroupCode | nvarchar(50) | REF | H | Kaynak grubu | ERP | alternatif Kaynak |
| ResourceRole | nvarchar(10) |  | E | Primary \| Secondary | ERP, yoksa kural | varsayılan Primary |
| Consumption | decimal(18,6) |  | E | Baz miktar için kaynak tüketimi (kaynağın kapasite biriminde) | ERP | hata (satır atlanır) |
| ResourceNumber | int |  | E | Operasyonda aynı anda kullanılan kaynak adedi | ERP, yoksa kural | varsayılan 1 |
| IsSubcontracted | bit |  | H | Fason operasyon | ERP | varsayılan 0 |

### stg.Routing
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Malzeme · 2/2</sub>

- Rota: her satır bir operasyon–kaynak ilişkisi; sıra önce OperationNo, sonra SequenceNo. Aynı operasyonun kaynakları ayrı satırda, ResourceRole ile.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| TransferQuantity | decimal(18,4) |  | H | Transfer partisi | ERP | boş kalır |
| IsActive | bit |  | H | Operasyon plana dahil mi | ERP, yoksa kural | kural ya da elle |
| IsLotBasedUsage | bit |  | H | Doluysa tüketim üretilen miktardan bağımsız, lot başına sabit; pratikte hazırlık süresi | ERP | varsayılan 0 |
| ProductionLocation | nvarchar(50) |  | H | Lokasyonun alt tanımı (hol, hat); ileride kısıtlar için | ERP | boş kalır |
| WaitingTimeHours | decimal(9,2) |  | H | Operasyon öncesi kuyruk beklemesi | ERP | boş kalır |
| TransferTimeHours | decimal(9,2) |  | H | Sonraki operasyona taşıma | ERP | boş kalır |
| AlternativeGroup | nvarchar(50) |  | H | Aynı gruptaki satırlar birbirinin alternatifidir | ERP | boş kalır |
| AlternativePriority | int |  | H | Grup içindeki tercih bilgisi | ERP | boş kalır |
| AdditionalText1–3 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | boş kalır |
| AdditionalNumber1–2 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | boş kalır |

### stg.MaterialReference
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Malzeme</sub>

- Benzetilen ürün: kendi ağacı ya da rotası olmayan ürün, başka bir ürünün verisiyle planlanır.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| LocationCode | nvarchar(30) | UK,REF | E | Lokasyon kodu | ERP | hata (satır atlanır) |
| MaterialCode | nvarchar(50) | UK,REF | E | Benzetilen ürün | ERP | hata (satır atlanır) |
| ReferenceMaterialCode | nvarchar(50) | UK,REF | E | Referans ürün | ERP | hata (satır atlanır) |
| ReferenceProductionVersionCode | nvarchar(30) | REF | H | Referans ürünün versiyonu; boşsa motor seçer | ERP | boş kalır |
| ValidFrom | date | UK | H | Geçerlilik başlangıcı | ERP | boş kalır |
| ValidTo | date |  | H | Geçerlilik bitişi | ERP | boş kalır |
| TimeFactor | decimal(9,4) |  | H | Süre çarpanı; 1,2 = %20 daha uzun | ERP | varsayılan 1 |

### stg.Resource
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Kaynak · 1/2</sub>

- Kaynak: makine, işçi, fason, diğer. Kapasite kaynağın kendi biriminde günlük kapasite olarak tutulur.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| LocationCode | nvarchar(30) | UK,REF | E | Lokasyon kodu | ERP | hata (satır atlanır) |
| Code | nvarchar(50) | UK | E | Kaynak kodu | ERP | hata (satır atlanır) |
| Name | nvarchar(150) |  | H | Kaynak adı | ERP | boş kalır |
| ResourceType | nvarchar(50) |  | H | ERP'den gelen ham değer; tip bayraklarla ifade edilir | ERP | boş kalır |
| IsEmployee | bit |  | H | Kaynak işçi mi | ERP, yoksa kural | kural ya da elle |
| IsMachine | bit |  | H | Kaynak makine mi | ERP, yoksa kural | kural ya da elle |
| IsFurnace | bit |  | H | Kaynak fırın mı; Faz 1 planlamada kullanılmaz | ERP, yoksa kural | kural ya da elle |
| IsMold | bit |  | H | Kaynak kalıp mı; Faz 1 planlamada kullanılmaz | ERP, yoksa kural | kural ya da elle |
| IsOther | bit |  | H | Diğer kaynak mı | ERP, yoksa kural | kural ya da elle |
| IsSubcontractor | bit |  | H | Kaynak fason mu | ERP, yoksa kural | kural ya da elle |

### stg.Resource
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Kaynak · 2/2</sub>

- Kaynak: makine, işçi, fason, diğer. Kapasite kaynağın kendi biriminde günlük kapasite olarak tutulur.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| CapacityUnit | nvarchar(10) | REF | E | Kapasite birimi (Saat, Adet, Ton…); rotadaki tüketim aynı birimde kabul edilir | ERP, yoksa kural | kural ya da elle |
| SubcontractorCode | nvarchar(50) | REF | H | Fasoncu | ERP | boş kalır |
| ProductionLocation | nvarchar(50) |  | H | Lokasyonun alt tanımı (hol, hat) | ERP | boş kalır |
| IsActive | bit |  | H | Aktif mi | ERP, yoksa kural | kural ya da elle |
| IsCritical | bit |  | H | 1: planda kısıt, 0: sonsuz kapasite (sadece raporlanır) | ERP, yoksa kural | kural ya da elle |
| RemainingOverTimeYear | decimal(9,2) |  | H | Yıllık kalan fazla mesai (saat) | ERP | boş kalır |
| RemainingOverTimeMonth | decimal(9,2) |  | H | Aylık kalan fazla mesai (saat) | ERP | boş kalır |
| AdditionalText1–7 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | boş kalır |
| AdditionalNumber1–3 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | boş kalır |

- **Entegre edilmeyenler (K-117):** Günlük kapasite, paralel adet, kapasite kaynağı, verim, hedef doluluk, fason parametreleri, takvim, vardiya, kaynak duruşları ve kapasite profili entegre edilmez; Smartchain ekranlarında tanımlanır (6.1 Kaynak sekmesi, 7.3 Kapasite parametreleri). `core`'da kalır.

### stg.ResourceGroup
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Kaynak</sub>

- Kaynak ve yetkinlik grubu. Kapasite havuzu değil, uygun kaynaklar listesidir; kapasite yalnız kaynakta tutulur.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| LocationCode | nvarchar(30) | UK,REF | E | Lokasyon kodu | ERP | hata (satır atlanır) |
| Code | nvarchar(50) | UK | E | Grup kodu | ERP | hata (satır atlanır) |
| Name | nvarchar(150) |  | H | Grup adı | ERP | boş kalır |
| Type | nvarchar(50) |  | H | Grup tipi; ERP'den gelen ham değer | ERP | boş kalır |
| IsResourceGroup | bit |  | H | Kaynak grubu | ERP, yoksa kural | kural ya da elle |
| IsCompetenceGroup | bit |  | H | Yetkinlik grubu | ERP, yoksa kural | kural ya da elle |
| IsActive | bit |  | H | Aktif | ERP, yoksa kural | kural ya da elle |
| AdditionalText1–7 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | boş kalır |
| AdditionalNumber1–3 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | boş kalır |

### stg.ResourceGroupAssignment
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Kaynak</sub>

- Kaynağın gruba ataması; bir kaynak birden fazla gruba atanabilir, yetkinlik matrisi bu tablodur. Geçerlilik tarihleri yalnız girdi.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| LocationCode | nvarchar(30) | UK,REF | E | Lokasyon kodu | ERP | hata (satır atlanır) |
| ResourceGroupCode | nvarchar(50) | UK,REF | E | Kaynak ya da yetkinlik grubu | ERP | hata (satır atlanır) |
| ResourceCode | nvarchar(50) | UK,REF | E | Kaynak kodu | ERP | hata (satır atlanır) |
| ValidFrom | date |  | H | Geçerlilik başlangıcı | ERP | boş kalır |
| ValidTo | date |  | H | Geçerlilik bitişi | ERP | boş kalır |

### stg.EmployeeAbsence
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Kaynak</sub>

- Kişi bazında izin ve rapor.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| LocationCode | nvarchar(30) | UK,REF | E | Lokasyon kodu | ERP | hata (satır atlanır) |
| ResourceCode | nvarchar(50) | UK,REF | E | Kaynak kodu | ERP | hata (satır atlanır) |
| AbsenceType | nvarchar(50) | UK | E | ERP'den gelen ham değer (izin, rapor…) | ERP | hata (satır atlanır) |
| StartDate | date | UK | E | Başlangıç | ERP | hata (satır atlanır) |
| EndDate | date |  | E | Bitiş günü dahil | ERP | hata (satır atlanır) |
| HoursPerDay | decimal(9,2) |  | H | Günlük devamsız saat; kısmi devamsızlık için, boşsa tam gün | ERP | varsayılan Tam gün |

### stg.Supplier
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Malzeme</sub>

- Tedarikçi ve fasoncu.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| Code | nvarchar(50) | UK | E | Tedarikçi kodu | ERP | hata (satır atlanır) |
| Name | nvarchar(200) |  | H | Ad | ERP | boş kalır |
| IsSubcontractor | bit |  | H | Fasoncu mu | ERP, yoksa kural | kural ya da elle |
| IsActive | bit |  | H | Aktif mi | ERP, yoksa kural | kural ya da elle |
| Country | nvarchar(100) |  | H | Ülke | ERP | boş kalır |
| City | nvarchar(100) |  | H | Şehir | ERP | boş kalır |
| AdditionalText1–7 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | boş kalır |
| AdditionalNumber1–3 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | boş kalır |

### stg.MaterialSupplier
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Malzeme</sub>

- Malzeme–tedarikçi ilişkisi; satın alma parametreleri. Satın alma her zaman sürekli; yuvarlama son hesapta.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| LocationCode | nvarchar(30) | UK,REF | E | Lokasyon kodu | ERP | hata (satır atlanır) |
| MaterialCode | nvarchar(50) | UK,REF | E | Malzeme | ERP | hata (satır atlanır) |
| SupplierCode | nvarchar(50) | UK,REF | E | Tedarikçi | ERP | hata (satır atlanır) |
| IsActive | bit |  | H | Aktif mi | ERP, yoksa kural | kural ya da elle |
| Priority | int |  | H | Öncelik | ERP, yoksa kural | kural ya da elle |
| QuotaRatio | decimal(6,4) |  | H | Oran olarak kota (0,30 = %30) | ERP, yoksa kural | kural ya da elle |
| FixedLeadTimeDays | decimal(9,2) |  | H | Miktardan bağımsız kısım | ERP | boş kalır |
| VariableLeadTimeDays | decimal(18,6) |  | H | Birim başına gün; miktar arttıkça uzayan kısım | ERP | boş kalır |
| LeadTimeBasis | nvarchar(15) |  | H | Takvim günü \| İş günü | Kural ya da elle | varsayılan Takvim günü |
| MinimumOrderQuantity | decimal(18,4) |  | H | Minimum sipariş miktarı | ERP | boş kalır |
| OrderLotSize | decimal(18,4) |  | H | Sipariş miktarı bu sayının katı olur | ERP | boş kalır |
| MaximumOrderQuantity | decimal(18,4) |  | H | Maksimum | ERP | boş kalır |
| ValidFrom | date |  | H | Geçerlilik başlangıcı | ERP | boş kalır |
| ValidTo | date |  | H | Geçerlilik bitişi | ERP | boş kalır |
| AdditionalText1–3 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | boş kalır |
| AdditionalNumber1–2 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | boş kalır |

### stg.Customer
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Talep</sub>

- Müşteri.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| Code | nvarchar(50) | UK | E | Müşteri kodu | ERP | hata (satır atlanır) |
| Name | nvarchar(200) |  | H | Ad | ERP | boş kalır |
| Priority | int |  | H | Müşteri önceliği | Kural ya da elle | boş kalır |
| AllowPartialDelivery | bit |  | H | Kısmi teslimata izin | ERP, yoksa kural | kural ya da elle |
| CustomerGroup | nvarchar(50) |  | H | Müşteri grubu | ERP | boş kalır |
| IsActive | bit |  | H | Aktif mi | ERP, yoksa kural | kural ya da elle |
| Country | nvarchar(100) |  | H | Ülke | ERP | boş kalır |
| Region | nvarchar(100) |  | H | Bölge | ERP | boş kalır |
| City | nvarchar(100) |  | H | Şehir | ERP | boş kalır |
| IsCustomTracked | bit |  | H | Bu müşterinin talepleri ortak havuzdan değil, müşteriye ayrılmış olarak takip edilir | ERP, yoksa kural | kural ya da elle |
| AdditionalText1–7 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | boş kalır |
| AdditionalNumber1–3 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | boş kalır |

### stg.ProjectGroup
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Malzeme</sub>

- Proje grubu (grup içi paylaşım için).  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| Code | nvarchar(50) | UK | E | Grup kodu | ERP ya da kural | hata (satır atlanır) |
| Name | nvarchar(200) |  | H | Proje grubu adı | ERP ya da kural | kural ya da elle |
| TrackingRule | nvarchar(20) |  | H | Tam izolasyon \| Ortaktan beslenir \| Grup içi paylaşım | ERP ya da kural | varsayılan Ortaktan beslenir |
| Priority | int |  | H | Proje grubu önceliği | ERP ya da kural | kural ya da elle |
| IsActive | bit |  | H | Aktif mi | ERP ya da kural | kural ya da elle |

### stg.Project
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Malzeme</sub>

- Proje.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| Code | nvarchar(50) | UK | E | Proje kodu | ERP ya da kural | hata (satır atlanır) |
| Name | nvarchar(200) |  | H | Proje adı | ERP ya da kural | boş kalır |
| ProjectGroupCode | nvarchar(50) | REF | H | Proje grubu kodu | ERP ya da kural | boş kalır |
| TrackingRule | nvarchar(20) |  | H | Proje bazında takip kuralı (grubu ezer) | ERP ya da kural | boş kalır |
| Priority | int |  | H | Proje önceliği | ERP ya da kural | boş kalır |
| IsActive | bit |  | H | Aktif mi | ERP ya da kural | kural ya da elle |
| AdditionalText1–7 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | boş kalır |
| AdditionalNumber1–3 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | boş kalır |

### stg.SalesOrderLine
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Talep</sub>

- Müşteri sipariş satırı; teklifler IsQuote ile okunur. Vade: teyit tarihi, yoksa istek tarihi.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| LocationCode | nvarchar(30) | UK,REF | E | Lokasyon kodu | ERP | hata (satır atlanır) |
| OrderNo | nvarchar(30) | UK | E | Sipariş no | ERP | hata (satır atlanır) |
| LineNo | int | UK | E | Satır no | ERP | hata (satır atlanır) |
| LineItemNo | int | UK | H | Alt satır no (ERP satırı kırılımlıysa) | ERP | varsayılan 0 |
| Type | nvarchar(50) |  | H | ERP'den ham sipariş tipi; veri kurallarında kullanılır, değer listesi yok | ERP | boş kalır |
| CustomerCode | nvarchar(50) | REF | E | Müşteri kodu | ERP | hata (satır atlanır) |
| MaterialCode | nvarchar(50) | REF | E | Malzeme | ERP | hata (satır atlanır) |
| ProjectCode | nvarchar(50) | REF | H | Proje | ERP | boş kalır |
| OpenQuantity | decimal(18,4) |  | E | Açık miktar | ERP | hata (satır atlanır) |
| OrderedQuantity | decimal(18,4) |  | H | Satırın orijinal miktarı | ERP | boş kalır |
| DeliveredQuantity | decimal(18,4) |  | H | Teslim edilen miktar | ERP | boş kalır |
| Uom | nvarchar(10) | REF | H | Açık, sipariş ve teslim miktarının birimi; boşsa malzemenin temel biriminde kabul edilir, doluysa birim dönüşümüyle çevrilir | ERP | varsayılan Malzemenin temel birimi |
| RequestedDate | date |  | E | İstek tarihi | ERP | hata (satır atlanır) |
| ConfirmedDate | date |  | H | Teyit tarihi | ERP | boş kalır |
| Priority | int |  | H | Satır önceliği | Kural ya da elle | boş kalır |
| AllowPartialDelivery | bit |  | H | Kısmi teslimat (müşteriyi ezer) | ERP | boş kalır |
| Status | nvarchar(50) |  | H | ERP'den ham sipariş durumu; veri kurallarında kullanılır, değer listesi yok | ERP | boş kalır |
| IsActive | bit |  | H | Aktif mi | ERP, yoksa kural | kural ya da elle |
| IsOnHold | bit |  | H | Kredi, teknik onay ya da müşteri talebiyle bekletilen satır | ERP, yoksa kural | kural ya da elle |
| IsCustomTracked | bit |  | H | Satır düzeyinde özel takip | ERP, yoksa kural | kural ya da elle |
| IsQuote | bit |  | H | Teklif satırı; Type'tan veri kuralıyla doldurulur | ERP, yoksa kural | kural ya da elle |
| AdditionalText1–3 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | boş kalır |
| AdditionalNumber1–2 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | boş kalır |

### stg.Forecast
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Talep</sub>

- Talep tahmini (netleme ön hesapta).  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| LocationCode | nvarchar(30) | UK,REF | E | Lokasyon kodu | ERP | hata (satır atlanır) |
| MaterialCode | nvarchar(50) | UK,REF | E | Malzeme | ERP | hata (satır atlanır) |
| CustomerCode | nvarchar(50) | UK,REF | H | Müşteri kodu | ERP | boş kalır |
| ProjectCode | nvarchar(50) | UK,REF | H | Proje | ERP | boş kalır |
| Period | date | UK | E | Dönem | ERP | hata (satır atlanır) |
| Type | nvarchar(50) | UK | H | Hangisinin plana gireceği veri kuralıyla seçilir; ERP'den ham değer, değer listesi yok | ERP | boş kalır |
| Quantity | decimal(18,4) |  | E | Miktar | ERP | hata (satır atlanır) |
| Uom | nvarchar(10) | REF | H | Miktarın birimi; boşsa malzemenin temel biriminde kabul edilir, doluysa birim dönüşümüyle çevrilir | ERP | varsayılan Malzemenin temel birimi |
| DeliveryPoint | nvarchar(10) |  | H | Miktarın dönemin başında mı sonunda mı hazır olması gerektiği: Başı \| Sonu | ERP, yoksa kural | kural ya da elle |
| IsActive | bit |  | H | Aktif mi | ERP, yoksa kural | kural ya da elle |
| AdditionalText1–3 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | boş kalır |
| AdditionalNumber1–2 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | boş kalır |

### stg.BorrowPayback
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Arz ve stok</sub>

- Projeler arası ödünç ve geri ödeme kaydı: devreye almada açık olan ve ERP'de doğrudan yapılan ödünçlerin motora bildirilmesi; onaylanan öneriler de buraya yazılır.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| LocationCode | nvarchar(30) | UK,REF | E | Lokasyon kodu | ERP | hata (satır atlanır) |
| MaterialCode | nvarchar(50) | UK,REF | E | Malzeme | ERP | hata (satır atlanır) |
| LendingProjectCode | nvarchar(50) | UK,REF | E | Ödünç veren proje | ERP | hata (satır atlanır) |
| BorrowingProjectCode | nvarchar(50) | UK,REF | E | Ödünç alan proje | ERP | hata (satır atlanır) |
| BorrowedQuantity | decimal(18,4) |  | E | Ödünç miktarı | ERP | hata (satır atlanır) |
| PaidBackQuantity | decimal(18,4) |  | H | Geri ödenen miktar | ERP | boş kalır |
| BorrowDate | date | UK | E | Ödünç tarihi | ERP | hata (satır atlanır) |
| PaybackDueDate | date |  | H | Geri ödeme tarihi | ERP | boş kalır |

### stg.Stock
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Arz ve stok</sub>

- Stok; lot ve durum bazında. Sahip: proje, müşteri, sipariş ya da ortak.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| LocationCode | nvarchar(30) | UK,REF | E | Lokasyon kodu | ERP | hata (satır atlanır) |
| MaterialCode | nvarchar(50) | UK,REF | E | Malzeme | ERP | hata (satır atlanır) |
| Warehouse | nvarchar(30) | UK | H | Depo | ERP | boş kalır |
| LotNo | nvarchar(50) | UK | H | Lot / seri | ERP | boş kalır |
| Status | nvarchar(50) | UK | H | ERP'den ham stok durumu; veri kurallarında kullanılır, değer listesi yok | ERP | boş kalır |
| ProjectCode | nvarchar(50) | UK,REF | H | Sahip proje; proje, müşteri ve sipariş boşsa stok ortaktır | ERP | boş kalır |
| CustomerCode | nvarchar(50) | UK,REF | H | Sahip müşteri; stoğun ayrıldığı müşteri, ileride kullanılmak üzere | ERP | boş kalır |
| SalesOrderNo | nvarchar(30) | UK,REF | H | Sahip sipariş no; stoğun ayrıldığı sipariş, ileride kullanılmak üzere | ERP | boş kalır |
| SalesOrderLineNo | int | UK,REF | H | Sahip sipariş satırı; stoğun ayrıldığı sipariş satırı, ileride kullanılmak üzere | ERP | boş kalır |
| SalesOrderLineItemNo | int | UK,REF | H | Bağlı sipariş alt satırı | ERP | boş kalır |
| Quantity | decimal(18,4) |  | E | Miktar | ERP | hata (satır atlanır) |
| Uom | nvarchar(10) | REF | H | Miktarın birimi; boşsa malzemenin temel biriminde kabul edilir, doluysa birim dönüşümüyle çevrilir | ERP | varsayılan Malzemenin temel birimi |
| QualityEntryDate | date |  | H | Kaliteye giriş tarihi | ERP | boş kalır |
| ExpectedAcceptanceDate | date |  | H | Kalitedeki stoğun kullanılabilir hâle gelmesi beklenen tarih | ERP | boş kalır |
| ExpiryDate | date |  | H | Son kullanma tarihi (raf ömrü sonraki faz) | ERP | boş kalır |
| IsAvailable | bit |  | H | Stok planda kullanılabilir; Status ve depoya göre veri kuralıyla doldurulur | ERP, yoksa kural | kural ya da elle |
| IsInQuality | bit |  | H | Stok planda kalitede sayılır; Status ve depoya göre veri kuralıyla doldurulur | ERP, yoksa kural | kural ya da elle |
| IsBlocked | bit |  | H | Stok planda bloke sayılır; Status ve depoya göre veri kuralıyla doldurulur | ERP, yoksa kural | kural ya da elle |
| IsActive | bit |  | H | Aktif mi | ERP, yoksa kural | kural ya da elle |
| IsCustomTracked | bit |  | H | Stok düzeyinde özel takip | ERP, yoksa kural | kural ya da elle |
| AdditionalText1–3 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | boş kalır |
| AdditionalNumber1–2 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | boş kalır |

### stg.WorkOrder
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Arz ve stok</sub>

- Açık iş emri (üretim, fason, yeniden işleme).  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| LocationCode | nvarchar(30) | UK,REF | E | Lokasyon kodu | ERP | hata (satır atlanır) |
| WorkOrderNo | nvarchar(30) | UK | E | İş emri no | ERP | hata (satır atlanır) |
| MaterialCode | nvarchar(50) | REF | E | Üretilen malzeme | ERP | hata (satır atlanır) |
| ProductionVersionCode | nvarchar(30) | REF | H | Üretim versiyonu; iş emrinin kendi bileşen ve operasyon satırları geldiyse motor onları kullanır, gelmediyse bu versiyonun ağacına ve rotasına gider | ERP | boş kalır |
| ProductionOrderType | nvarchar(50) |  | H | ERP'den ham iş emri tipi; veri kurallarında kullanılır, değer listesi yok | ERP | boş kalır |
| Status | nvarchar(50) |  | H | ERP'den ham iş emri durumu; veri kurallarında kullanılır, değer listesi yok | ERP | boş kalır |
| Priority | int |  | H | İş emri önceliği | ERP | boş kalır |
| OrderedQuantity | decimal(18,4) |  | E | İş emri miktarı | ERP | hata (satır atlanır) |
| OpenQuantity | decimal(18,4) |  | E | Açık miktar | ERP | hata (satır atlanır) |
| CompletedQuantity | decimal(18,4) |  | H | Tamamlanan miktar | ERP | boş kalır |
| ScrapQuantity | decimal(18,4) |  | H | Hurda miktarı | ERP | boş kalır |
| Uom | nvarchar(10) | REF | H | Miktarların birimi; boşsa malzemenin temel biriminde kabul edilir, doluysa birim dönüşümüyle çevrilir | ERP | varsayılan Malzemenin temel birimi |
| StartDate | date |  | H | Başlangıç | ERP | boş kalır |
| DueDate | date |  | E | Bitiş | ERP | hata (satır atlanır) |
| ProjectCode | nvarchar(50) | REF | H | Proje (ayraç) | ERP | boş kalır |
| CustomerCode | nvarchar(50) | REF | H | Müşteri | ERP | boş kalır |
| SalesOrderNo | nvarchar(30) | REF | H | Bağlı sipariş no (ayraç) | ERP | boş kalır |
| SalesOrderLineNo | int | REF | H | Bağlı sipariş satır no | ERP | boş kalır |
| SalesOrderLineItemNo | int | REF | H | Bağlı sipariş alt satırı | ERP | boş kalır |
| ParentWorkOrderNo | nvarchar(30) | REF | H | Yeniden işlemede orijinal iş emri | Kural ya da elle | boş kalır |
| LastActivityDate | date |  | H | Son hareket tarihi (eskime kontrolü) | ERP | boş kalır |
| IsFixed | bit |  | H | Motor bu iş emrinin tarihini ve miktarını değiştirmez | ERP, yoksa kural | kural ya da elle |
| IsReleased | bit |  | H | İş emri yayınlandı; Status'tan veri kuralıyla doldurulur | ERP, yoksa kural | kural ya da elle |
| IsStarted | bit |  | H | İş emri başladı; Status'tan veri kuralıyla doldurulur | ERP, yoksa kural | kural ya da elle |
| IsProduction | bit |  | H | Üretim iş emri; ProductionOrderType'tan veri kuralıyla doldurulur | ERP, yoksa kural | kural ya da elle |
| IsSubcontract | bit |  | H | Fason iş emri; ProductionOrderType'tan veri kuralıyla doldurulur | ERP, yoksa kural | kural ya da elle |
| IsRework | bit |  | H | Yeniden işleme iş emri; ProductionOrderType'tan veri kuralıyla doldurulur | ERP, yoksa kural | kural ya da elle |
| IsOnHold | bit |  | H | Bekletilen iş emri | ERP, yoksa kural | kural ya da elle |
| IsCustomTracked | bit |  | H | İş emri düzeyinde özel takip | ERP, yoksa kural | kural ya da elle |
| AdditionalText1–3 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | boş kalır |
| AdditionalNumber1–2 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | boş kalır |

### stg.WorkOrderComponent
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Arz ve stok</sub>

- İş emrinin bileşenleri ve çekilen miktar.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| LocationCode | nvarchar(30) | UK,REF | E | Lokasyon kodu | ERP | hata (satır atlanır) |
| WorkOrderNo | nvarchar(30) | UK,REF | E | İş emri | ERP | hata (satır atlanır) |
| MaterialCode | nvarchar(50) | UK,REF | E | Bileşen | ERP | hata (satır atlanır) |
| OperationNo | int | UK | H | Bağlı olduğu operasyon no (ihtiyaç tarihi için) | ERP | boş kalır |
| SequenceNo | int | UK | H | Sıra no; aynı bileşen iki kez geçerse operasyon no ile ayrışır | ERP | boş kalır |
| RequiredQuantity | decimal(18,4) |  | E | Gereken miktar | ERP | hata (satır atlanır) |
| IssuedQuantity | decimal(18,4) |  | H | Çekilen miktar | ERP | varsayılan 0 |
| UnitUsage | decimal(18,6) |  | H | Üretilen bir birim için bileşen miktarı | ERP | boş kalır |
| Uom | nvarchar(10) | REF | H | Bileşen miktarlarının birimi; boşsa bileşenin temel biriminde kabul edilir, doluysa birim dönüşümüyle çevrilir | ERP | varsayılan Bileşenin temel birimi |
| ScrapRatio | decimal(6,4) |  | H | Oran olarak fire (0,05 = %5) | ERP | varsayılan 0 |
| IsLotBasedUsage | bit |  | H | Doluysa bileşen üretilen miktardan bağımsız, her üretim lotu için sabit kullanılır; değilse birim başına | ERP | varsayılan 0 |
| IsPhantom | bit |  | H | Hayalet bileşen | ERP | varsayılan 0 |
| AdditionalText1–3 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | boş kalır |
| AdditionalNumber1–2 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | boş kalır |

### stg.WorkOrderOperation
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Arz ve stok</sub>

- İş emrinin operasyonları ve kalan iş.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| LocationCode | nvarchar(30) | UK,REF | E | Lokasyon kodu | ERP | hata (satır atlanır) |
| WorkOrderNo | nvarchar(30) | UK,REF | E | İş emri | ERP | hata (satır atlanır) |
| OperationNo | int | UK | E | Operasyon no | ERP | hata (satır atlanır) |
| SequenceNo | int | UK | E | Operasyon içindeki alt sıra | ERP | hata (satır atlanır) |
| OperationName | nvarchar(150) |  | H | Operasyon adı | ERP | boş kalır |
| ResourceCode | nvarchar(50) | REF | H | Kaynak kodu | ERP | alternatif Kaynak grubu |
| ResourceGroupCode | nvarchar(50) | REF | H | Kaynak grubu | ERP | alternatif Kaynak |
| ResourceRole | nvarchar(10) |  | E | Primary \| Secondary | ERP, yoksa kural | varsayılan Primary |
| ResourceNumber | int |  | E | Operasyonda aynı anda kullanılan kaynak adedi | ERP, yoksa kural | varsayılan 1 |
| PlannedConsumption | decimal(18,6) |  | H | Planlanan tüketim | ERP | boş kalır |
| ConfirmedConsumption | decimal(18,6) |  | H | Teyit edilen tüketim | ERP | varsayılan 0 |
| Status | nvarchar(50) |  | H | ERP'den ham operasyon durumu; veri kurallarında kullanılır, değer listesi yok | ERP | boş kalır |
| IsCompleted | bit |  | H | Operasyon tamamlandı; Status'tan veri kuralıyla doldurulur | ERP, yoksa kural | kural ya da elle |
| IsLotBasedUsage | bit |  | H | Doluysa tüketim üretilen miktardan bağımsız, lot başına sabit; pratikte hazırlık süresi | ERP | varsayılan 0 |
| IsSubcontracted | bit |  | H | Fason operasyon | ERP | varsayılan 0 |
| IsActive | bit |  | H | Operasyon plana dahil mi | ERP, yoksa kural | kural ya da elle |
| ProductionLocation | nvarchar(50) |  | H | Lokasyonun alt tanımı (hol, hat); ileride kısıtlar için | ERP | boş kalır |
| TransferQuantity | decimal(18,4) |  | H | Transfer partisi | ERP | boş kalır |
| WaitingTimeHours | decimal(9,2) |  | H | Operasyon öncesi kuyruk beklemesi | ERP | boş kalır |
| TransferTimeHours | decimal(9,2) |  | H | Sonraki operasyona taşıma | ERP | boş kalır |
| AdditionalText1–3 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | boş kalır |
| AdditionalNumber1–2 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | boş kalır |

### stg.PurchaseOrderLine
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Arz ve stok</sub>

- Açık satın alma ve fason siparişi satırı (ve talep).  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| LocationCode | nvarchar(30) | UK,REF | E | Lokasyon kodu | ERP | hata (satır atlanır) |
| PurchaseOrderNo | nvarchar(30) | UK | E | Sipariş no | ERP | hata (satır atlanır) |
| LineNo | int | UK | E | Satır no | ERP | hata (satır atlanır) |
| OrderType | nvarchar(50) |  | H | ERP'den ham sipariş tipi; veri kurallarında kullanılır, değer listesi yok | ERP | boş kalır |
| SupplierCode | nvarchar(50) | REF | H | Tedarikçi | ERP | boş kalır |
| MaterialCode | nvarchar(50) | REF | E | Malzeme | ERP | hata (satır atlanır) |
| OpenQuantity | decimal(18,4) |  | E | Açık miktar | ERP | hata (satır atlanır) |
| OrderedQuantity | decimal(18,4) |  | H | Sipariş miktarı | ERP | boş kalır |
| ReceivedQuantity | decimal(18,4) |  | H | Teslim alınan miktar | ERP | boş kalır |
| Uom | nvarchar(10) | REF | H | Miktarların birimi; boşsa malzemenin temel biriminde kabul edilir, doluysa birim dönüşümüyle çevrilir | ERP | varsayılan Malzemenin temel birimi |
| RequestedDate | date |  | H | İstenen tarih | ERP | boş kalır |
| ConfirmedDate | date |  | H | Tedarikçi teyit tarihi | ERP | boş kalır |
| ProjectCode | nvarchar(50) | REF | H | Proje | ERP | boş kalır |
| CustomerCode | nvarchar(50) | REF | H | Müşteri | ERP | boş kalır |
| SalesOrderNo | nvarchar(30) | REF | H | Bağlı sipariş no | ERP | boş kalır |
| SalesOrderLineNo | int | REF | H | Bağlı sipariş satırı | ERP | boş kalır |
| SalesOrderLineItemNo | int | REF | H | Bağlı sipariş alt satırı | ERP | boş kalır |
| WorkOrderNo | nvarchar(30) | REF | H | Fasonda bağlı iş emri | ERP | boş kalır |
| Status | nvarchar(50) |  | H | ERP'den ham sipariş durumu; veri kurallarında kullanılır, değer listesi yok | ERP | boş kalır |
| IsPurchaseRequest | bit |  | H | Satın alma talebi; OrderType'tan veri kuralıyla doldurulur | ERP, yoksa kural | kural ya da elle |
| IsPurchase | bit |  | H | Satın alma siparişi; OrderType'tan veri kuralıyla doldurulur | ERP, yoksa kural | kural ya da elle |
| IsSubcontract | bit |  | H | Fason siparişi; OrderType'tan veri kuralıyla doldurulur | ERP, yoksa kural | kural ya da elle |
| IsActive | bit |  | H | Aktif mi | ERP, yoksa kural | kural ya da elle |
| IsCustomTracked | bit |  | H | Satır düzeyinde özel takip | ERP, yoksa kural | kural ya da elle |
| AdditionalText1–3 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | boş kalır |
| AdditionalNumber1–2 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | boş kalır |

### stg.ProductionConfirmation
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Arz ve stok</sub>

- Üretim gerçekleşmeleri: iş emri bazında stoğa girişler.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| LocationCode | nvarchar(30) | UK,REF | E | Lokasyon kodu | ERP | hata (satır atlanır) |
| ConfirmationNo | nvarchar(30) | UK | E | Teyit no | ERP | hata (satır atlanır) |
| WorkOrderNo | nvarchar(30) | REF | E | İş emri | ERP | hata (satır atlanır) |
| MaterialCode | nvarchar(50) | REF | E | Üretilen malzeme | ERP | hata (satır atlanır) |
| ConfirmedQuantity | decimal(18,4) |  | E | Teyit miktarı | ERP | hata (satır atlanır) |
| StartDate | date |  | H | Başlangıç | ERP | boş kalır |
| EndDate | date |  | H | Bitiş | ERP | boş kalır |
| AdditionalText1–3 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | boş kalır |
| AdditionalNumber1–2 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | boş kalır |

### Yöntem 1 · API (ERP'nin servisleri)
<sub>26. Entegrasyon tasarımı · Yöntem 1 · API</sub>

- **Ne zaman:** ERP'nin REST (ya da SOAP) servisi varsa ve müşteri BT servis hesabı açabiliyorsa. Tercih edilen yol: artımlı çekim ve gün içi tazeleme mümkün.
- **Adaptör:** ERP başına bir adaptör: uç nokta listesi, kimlik doğrulama (servis hesabı, anahtar ya da token), sayfalama, alan eşlemesi. Adaptör ürünün dışında, kurulum paketinde 'entegrasyon tanımı' olarak gelir.
- **Çekim:** Varlık sırası referans verisinden işlem verisine. Sayfa sayfa (ör. 500 kayıt), her sayfa ham tabloya yazılır. Artımlı: LastModified ya da değişiklik günlüğü varsa yalnız değişenler; yoksa tam çekim.
- **Dayanıklılık:** Zaman aşımı 30 sn (parametre), geçici hatada 3 deneme artan aralıkla; kalıcı hatada varlık 'hata', diğerleri devam. Çağrı ve yanıt özetleri loglanır (gövde değil).
- **Şema değişikliği:** Yanıtta beklenen alan yoksa varlık hata, Entegrasyon ekranında 'eşlenmemiş alan'. Yeni alanlar yok sayılır.
- **Ağ:** ERP sunucusuna müşteri ağı içinden; güvenlik duvarında tek yön, tek port. Servis hesabı yalnız okuma yetkili.

### Yöntem 2 · SQL arayüz tabloları
<sub>26. Entegrasyon tasarımı · Yöntem 2 · SQL arayüz tabloları</sub>

- **Ne zaman:** ERP'nin servisi yoksa ya da müşteri BT'si veritabanı düzeyinde çalışmayı tercih ediyorsa. ERP veritabanına doğrudan girilmez; müşteri ETL'i ara tabloları doldurur.
- **Tablolar:** Varlık başına bir SC_* tablosu (SC_MATERIAL, SC_BOM, SC_ROUTING, SC_RESOURCE, SC_STOCK, SC_SALES_ORDER, SC_PURCHASE_ORDER, SC_WORK_ORDER, SC_CONFIRMATION…). Sütun adları sözleşme alan adlarıyla birebir; şema veri sözlüğünden üretilir ve kurulum paketiyle verilir.
- **Standart sütunlar:** Her tabloda: SC_BATCH (müşteri parti no), SC_LAST_MODIFIED, SC_ACTION (I / U / D, isteğe bağlı), SC_STATUS (Smartchain yazar: okundu / hata) ve SC_ERROR_TEXT. Smartchain yalnız durum sütunlarına yazar.
- **Okuma:** Gece 22:00 ve elle tetiklemede toplu okuma; LAST_MODIFIED ile artımlı. Okunan satırlar ham tabloya kopyalanır, SC_STATUS = okundu; müşteri ETL'i okunanları temizleyebilir ya da üzerine yazabilir.
- **Yer:** Ara veritabanı Smartchain'in SQL Server'ında ayrı bir veritabanı (önerilen) ya da müşterinin SQL Server'ında; bağlantı dizesi Entegrasyon ekranında, servis hesabı okuma + SC_STATUS yazma yetkili.
- **Sorumluluk:** Tabloları doldurma ve zamanlama müşteri BT'sinde; Smartchain şemayı, örnek veriyi ve doğrulama raporunu verir. Devreye almada birlikte test edilir.

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

- Eşleme tanımı kurulumda varlık başına yapılır ve Entegrasyon ekranında görünür: ERP alanı → sözleşme alanı, dönüşüm, yoksa ne olur. Eşleme ürünün parçası değil, kurulum verisidir.

| DÖNÜŞÜM TÜRÜ | ÖRNEK | KURAL |
|---|---|---|
| Doğrudan | ITEM_CODE → Material.Code | Tip ve uzunluk kontrolü; kırpma yok, uzunsa hata. |
| Kod listesi | ERP birim 'ADET' → 'adet'; tedarik türü 'S' → DefaultSupplyType = Satın alma | Eşleme tablosu; listede olmayan kod hata ya da varsayılan (alan ayarı). |
| Birim dönüşümü | Rota süresi dakika → kaynak kapasite birimi saat | Kaynağın CapacityUnit'ine çevrilir; dönüşüm yoksa uyarı, kaynak kısıtsız sayılır. |
| Birim dönüşümü · ters yön | M → KG tanımlı, KG → M tanımlı değil | Açıkça yazılan dönüşüm her zaman olduğu gibi kullanılır. 1/Factor yalnız ters yön hiç tanımlanmamışsa, kullanıldığı anda tam hassasiyetle hesaplanır, saklanmaz. |
| Birim dönüşümü · zincir | KOLİ → ADET ve ADET → KG tanımlı | Zincirleme dönüşüm türetilmez: KOLİ → KG hesaplanmaz; gerekiyorsa ayrıca tanımlanır. |
| Birim dönüşümü · lokasyon | HAM-001 iki lokasyonda var, dönüşüm satırı bir tane | UomConversion lokasyondan bağımsızdır, LocationCode taşımaz. MaterialCode, o koda sahip bütün lokasyonlardaki malzemeye uygulanır; kod→Id çevirisinde dönüşüm satırı aynı koddaki her lokasyonun malzemesine bağlanır. |
| Tarih | '20261023' → 2026-10-23; vade: ConfirmedDate yoksa RequestedDate | Biçim adaptörde; boş tarih kural ya da varsayılanla. |
| Türetme | SC_WORK_ORDER.OPEN_QTY = ORDER_QTY − CONFIRMED_QTY | Türetme adaptörde ya da ara tabloda; sözleşme alanı tek değer alır. |
| Birleştirme | Stok: depo + lot + durum + proje → tek satır | Anahtar sözleşmede; ERP daha ayrıntılıysa toplanır, daha kabasa boş alanlar varsayılan. |
| Smartchain alanı | Resource.DailyCapacity, verim | Entegre edilmez (K-117); Smartchain ekranında tanımlanır. |

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
- **Gün içi kısmi · elle:** Stok ve siparişler (satış, satın alma, iş emri) Key user tarafından çekilip kısmi yüklenir; 'yeni veri var' bildirimi. Hedef 5 dk altı.
- **Haftalık ve elle:** Tahmin ve kaynak: haftalık ya da değişince Excel ile; takvim ve vardiya ekrandan (K-65). Ham veri temizliği Pazar 03:00.
- **Artımlı çekim:** API'de LastModified, SQL'de SC_LAST_MODIFIED varsa yalnız değişenler; silinenler için tam liste ya da SC_ACTION = D gerekir. Artımlı destek yoksa tam çekim (varsayılan).
- **Zamanlama ayarı:** Saatler ve paralellik Entegrasyon ekranında (Admin); bitiş sınırı ve işçi sayısı System owner ayarı. Müşterinin ERP gece işleriyle çakışmaması için saat devreye almada belirlenir.
- **Çakışma yönetimi:** Gece akışı sırasında elle çekim kapalı; gün içi kısmi yükleme sırasında ikinci yükleme kuyrukta bekler. Yükleme açık çalışmaları etkilemez.

### Hata yönetimi
<sub>26. Entegrasyon tasarımı · Hata yönetimi</sub>

- Hata dört düzeyde ele alınır: bağlantı, varlık, satır, alan. Her düzeyin davranışı sabit; kullanıcıya nerede ne olduğu ve ne yapması gerektiği söylenir.

| DÜZEY | ÖRNEK | DAVRANIŞ | NEREDE GÖRÜNÜR |
|---|---|---|---|
| Bağlantı | API ulaşılamıyor, SQL kimlik hatası, zaman aşımı | 3 deneme artan aralıkla; sonra varlık 'hata', önceki ham veri korunur; diğer varlıklar devam | Veri yükleme ekranı, Entegrasyon 'son çağrı', Sistem sağlığı |
| Varlık | Şema uyumsuzluğu, eşlenmemiş alan, hata eşiği (%5) aşımı | Varlık yüklenmez, önceki versiyonun satırları taşınır (kısmi); ana sayfada kırmızı | Veri yükleme, Entegrasyon 'eşlenmemiş alan', Ana sayfa |
| Satır | Zorunlu alan boş, referans yok, negatif süre, döngü | Satır atlanır, bulgu listesine yazılır; eşik altındaysa varlık yüklenir | Doğrulama detayı, hata raporu (xlsx) |
| Alan | Boş malzeme seviyesi, boş tedarik türü | Veri kuralı ya da varsayılan ile tamamlanır; uyarı olarak Veri kalitesi listesine düşer | Veri kalitesi, Ana veri (kaynak etiketi) |
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

- **Servis hesapları:** API ve SQL için ayrı hesaplar; yalnız okuma (SQL'de SC_STATUS yazma). Şifre ve anahtarlar sunucuda şifreli saklanır, ekranda gösterilmez, destek paketine girmez.
- **Ağ:** Kapalı ağ; Smartchain sunucusu → ERP sunucusu tek yön. Güvenlik duvarı kuralı kurulum dokümanında; internet gerekmez.
- **Veri:** Ham veri ve geçerli veri Smartchain SQL Server'ında; yedekleme kurulum tasarımında (27). Kişisel veri: işçi adı yalnız vardiya planı için, parametreyle anonim kod kullanılabilir (öneri).
- **Log ve iz:** Her çağrı ve parti loglanır (gövde değil); elle tetiklemeler denetim izinde. Loglar destek paketiyle dışa alınır.
- **Değişiklik yönetimi:** Eşleme ve bağlantı değişikliği 'test et' zorunlu; değişiklik denetim izinde; bir önceki tanıma geri dönülebilir (öneri).
- **Yetki:** Entegrasyon tanımı: Admin ve üstü. Çekim ve yükleme: Key user ve üstü. End user hiçbirini görmez.

### Entegrasyon devreye alma adımları
<sub>26. Entegrasyon tasarımı · Devreye alma</sub>

- **1 · Keşif:** ERP ve sürüm, servis var mı, veritabanı erişimi, hangi varlık nerede tutuluyor, hangi alanlar boş. Çıktı: yöntem kararı varlık başına.
- **2 · Eşleme:** Alan eşleme tanımı varlık başına; kod listeleri; Smartchain'e özgü alanlar için kural taslakları. Çıktı: entegrasyon tanımı ve şablonlar.
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
| SQL arayüz tabloları | Şema, örnek veri, doğrulama raporu | ETL yazma, zamanlama, tabloları doldurma |
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

- **Artımlı çekim ve silinenler:** Artımlı çekimde silinen kayıtları yakalamak için tam liste karşılaştırması mı, SC_ACTION = D mi? Öneri: SQL'de SC_ACTION, API'de haftada bir tam çekim.
- **ERP belge numarası eşlemesi:** Faz 1'de ERP'de açılan siparişin Smartchain önerisine bağı: ERP'de dış referans alanı var mı, yoksa aksiyon listesinde elle mi? Kurulumda müşteriye göre.
- **Sessiz hata eşiği:** Satır sayısı dünden %30 az ise 'şüpheli parti' uyarısı: eşik parametre mi, sabit mi? (öneri: parametre, varsayılan %30).
- **Kişisel veri:** İşçi adı yerine anonim kod kullanımı: müşteri tercihi; parametre olarak öneriyoruz.
- **Rota tüketim birimi:** Rota süresi ERP'de dakika ise kapasite birimine dönüşüm adaptörde mi, veri kuralında mı? Öneri: adaptörde; kural istisna için.
- **Faz 2 geri yazma kapsamı:** Yalnız satın alma talebi mi, planlı iş emri de mi? Müşteri ERP'sinin planlı sipariş kavramına bağlı; keşifte netleşir.
