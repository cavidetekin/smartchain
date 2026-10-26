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
  - K-48  ERP ana veri ve işlem verisinde master; Smartchain planlama alanları (verim, kapasite birimi, kritik…) Smartchain'de, ERP değeri FieldValueSource'ta saklanır.
  - K-49  SQL arayüz tablolarını müşteri ETL'i doldurur; Smartchain ERP veritabanına doğrudan girmez.
- **Açık konular**
  - A-23  Artımlı çekimde silinen kayıtlar: SC_ACTION mi, haftalık tam çekim mi?
  - A-24  ERP belge numarası ↔ Smartchain öneri bağı: ERP'de dış referans alanı var mı?
  - A-25  Rota tüketim birimi dönüşümü adaptörde mi, veri kuralında mı?

### Entegrasyon tasarım ilkeleri
<sub>26. Entegrasyon tasarımı · Entegrasyon ilkeleri</sub>

- **Tek veri sözleşmesi:** Hangi yöntemle gelirse gelsin veri aynı sözleşmeye (varlık, alan, tip, anahtar, zorunluluk) iner. Sözleşme veri sözlüğünden (FieldDefinition) üretilir; şablon, arayüz tablosu ve API şeması aynı kaynaktan türer.
- **ERP bağımsız:** Ürün hiçbir ERP'ye özel alan taşımaz. ERP'ye özgü her şey adaptörde ve eşleme tanımında kalır; yeni ERP yeni adaptör demektir, ürün değişmez.
- **Yalnız okuma (Faz 1):** Smartchain ERP'den okur, ERP'ye yazmaz. Plan çıktıları Excel listesi olarak çıkar ve ERP'ye elle girilir. Geri yazma Faz 2 (API).
- **Üç yöntem, varlık başına bir tane:** API, SQL arayüz tabloları ve Excel. Her varlık tek yöntemle beslenir; yöntem müşteriye göre seçilir, karışık kurulum normaldir (ör. siparişler API, kaynaklar Excel).
- **Ham veri önce, dönüşüm sonra:** Gelen veri önce olduğu gibi ham tablolara (Staging) yazılır; doğrulama ve dönüşüm sonra. Sorunlu yükleme geriye dönük incelenebilir, ham veri 1 hafta saklanır.
- **ERP ana veri sahibidir:** Ana veri ve işlem verisinde ERP master'dır. Smartchain'e özgü alanlar (verim, kritik kaynak, kapasite birimi, parametreler) Smartchain'de tutulur; ERP'de yoksa kural ya da elle değerle tamamlanır.
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
  - Sözlükten üretilen şablon
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
| Malzeme (Material) | Ana veri | API · SQL · Excel | ERP | Gece tam | Code | Zorunlu |
| Lokasyon ve birim (Location, UnitOfMeasure, UomConversion) | Ana veri | API · SQL · Excel | ERP | Gece tam | Code · MaterialCode + From + To | Zorunlu |
| Ürün ağacı (ProductionVersion, BOM) | Ana veri | API · SQL · Excel | ERP | Gece tam | MaterialCode + VersionCode · + ComponentMaterialCode | Zorunlu |
| Rota (Routing) | Ana veri | API · SQL · Excel | ERP | Gece tam | RouteCode + OpNo + SeqNo + ResourceCode | Zorunlu |
| Kaynak (Resource, ResourceGroup, ResourceCapacityProfile) | Ana veri | Excel · SQL · API | ERP, Smartchain alanları ayrı | Gece tam / elle | Code | Zorunlu |
| Takvim ve gün (Calendar, CalendarDay) | Ana veri | Excel · SQL | ERP ya da Smartchain | Haftalık / elle | Code · CalendarCode + Date | Zorunlu |
| Vardiya ve plan (Shift, ShiftPlan) | Ana veri | Excel · SQL | Smartchain (ERP'de yoksa) | Elle | Code · grup+vardiya+tarih | İşçi grubu varsa |
| Duruş (ResourceDowntime) | Ana veri | Excel · API | ERP bakım ya da Smartchain | Gece / elle | ResourceCode + StartAt | İsteğe bağlı |
| Tedarikçi ve malzeme-tedarikçi (Supplier, MaterialSupplier) | Ana veri | API · SQL · Excel | ERP | Gece tam | Code · MaterialCode + SupplierCode | Zorunlu |
| Müşteri (Customer) | Ana veri | API · SQL | ERP | Gece tam | Code | Zorunlu |
| Proje (Project, ProjectGroup) | Ana veri | API · SQL · Excel | ERP | Gece tam | Code | Proje bazlı planlamada |

### Veri sözleşmesi · varlıklar
<sub>26. Entegrasyon tasarımı · Veri sözleşmesi · varlık listesi · 2/2</sub>

- Her varlık için: yöntem seçenekleri (öncelik sırasıyla), master'ı kim, çekim sıklığı, iş anahtarı. Entegrasyon tabloları sonraki slaytlarda; alan adları 21. adımla aynı, ilişkiler Id yerine kodla.

| VARLIK | SINIF | YÖNTEM | MASTER | SIKLIK | ANAHTAR | ZORUNLULUK / FAZ |
|---|---|---|---|---|---|---|
| Satış siparişi ve teklif satırı (SalesOrderLine) | İşlem verisi | API · SQL | ERP | Gece tam + gün içi kısmi | OrderNo + LineNo + LineItemNo | Zorunlu |
| Tahmin (Forecast) | İşlem verisi | Excel · API | ERP ya da Excel | Haftalık | MaterialCode + CustomerCode + Period | İsteğe bağlı |
| Stok (Stock) | İşlem verisi | API · SQL | ERP | Gece tam + gün içi kısmi | MaterialCode + Warehouse + Lot + Status + ProjectCode | Zorunlu |
| İş emri (WorkOrder, Component, Operation) | İşlem verisi | API · SQL | ERP | Gece tam + gün içi kısmi | OrderNo · + MaterialCode · + OpNo + SeqNo | Zorunlu |
| Satın alma / fason siparişi (PurchaseOrderLine) | İşlem verisi | API · SQL | ERP | Gece tam + gün içi kısmi | OrderNo+LineNo | Zorunlu |
| Transfer (TransferOrder) | İşlem verisi | API · SQL | ERP | Gece | OrderNo | Çok lokasyonda (Faz 2) |
| Üretim gerçekleşmesi (ProductionConfirmation) | İşlem verisi | API · SQL | ERP | Gece artımlı | WorkOrderNo + OpNo + SeqNo + StartAt | Doğruluk raporları için (A-22) |
| Sevkiyat / sipariş kapanışı (yeni) | İşlem verisi | API · SQL | ERP | Gece artımlı | OrderNo+LineNo+ShipDate | A-22 · raporlar 17, 19 |
| Birim maliyet (Material ek alanı, yeni) | Ana veri | API · SQL · Excel | ERP | Gece tam | MaterialCode | A-22 · stok değeri, tutar |
| Çıkış: satın alma talebi, iş emri açma, fason listesi | Plan çıktısı | Excel (Faz 1) · API (Faz 2) | Smartchain | Yayın sonrası, istek üzerine | PlannedOrder.Id | Faz 1 Excel |

### stg.Material
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Malzeme · 1/2</sub>

- Malzeme ve planlama ana verisi.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| LocationCode | nvarchar(30) | REF | E | Lokasyon kodu | ERP | hata (satır atlanır) |
| Code | nvarchar(50) | UK | E | Malzeme kodu | ERP | hata (satır atlanır) |
| Name | nvarchar(200) |  | H | Malzeme adı | ERP | boş kalır |
| BaseUom | nvarchar(10) | REF | E | Temel birim | ERP | hata (satır atlanır) |
| MaterialGroup | nvarchar(50) |  | H | Malzeme grubu | ERP | boş kalır |
| MaterialLevel | nvarchar(15) |  | H | Hammadde \| Yarı mamul \| Nihai ürün | ERP, yoksa kural | kural ya da elle |
| IsPurchasable | bit |  | H | Satın alınabilir | ERP, yoksa kural | kural ya da elle |
| IsProducible | bit |  | H | Üretilebilir | ERP, yoksa kural | kural ya da elle |
| IsSellable | bit |  | H | Satılabilir | ERP, yoksa kural | kural ya da elle |
| DefaultProcurement | nvarchar(10) |  | H | Üretim \| Satın alma \| Fason | ERP, yoksa kural | kural ya da elle |
| Ownership | nvarchar(10) |  | H | Kendi \| Müşteri (müşteri temin malzemesi) | Kural ya da elle | varsayılan Kendi |

### stg.Material
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Malzeme · 2/2</sub>

- Malzeme ve planlama ana verisi.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| IsProjectTracked | bit |  | H | Proje bazlı takip edilir mi (değilse her zaman ortak) | Kural ya da elle | varsayılan 0 |
| IsPhantom | bit |  | H | Hayalet yarı mamul | ERP | varsayılan 0 |
| ProductionLeadTimeDays | decimal(9,2) |  | H | Üretim süresi (gün) | ERP, yoksa kural | kural ya da elle |
| GoodsReceiptDays | decimal(9,2) |  | H | Mal kabul süresi (iş günü) | ERP, yoksa kural | kural ya da elle |
| SafetyStock | decimal(18,4) |  | H | Güvenlik stoğu | ERP | varsayılan 0 |
| MaxStock | decimal(18,4) |  | H | Maksimum stok | ERP | boş kalır |
| LotSizePolicy | nvarchar(15) |  | H | Üretimde: Lot-for-lot \| Sabit \| Dönemsel | ERP, yoksa kural | kural ya da elle |
| MinLot | decimal(18,4) |  | H | Üretimde minimum | ERP | boş kalır |
| MaxLot | decimal(18,4) |  | H | Üretimde maksimum | ERP | boş kalır |
| LotMultiple | decimal(18,4) |  | H | Üretimde kat | ERP | boş kalır |
| AssemblyScrapPct | decimal(6,2) |  | H | Montaj firesi (%) | ERP | varsayılan 0 |
| ShelfLifeDays | int |  | H | Raf ömrü (gün); Faz 1'de yalnız uyarı | ERP | boş kalır |
| AdditionalText1–7 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | boş kalır |
| AdditionalNumber1–3 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | boş kalır |

### stg.Location
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Ortak</sub>

- Lokasyon (tesis, depo). Faz 1'de her lokasyon kendi içinde planlanır.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| Code | nvarchar(30) | UK | E | Lokasyon kodu | ERP | hata (satır atlanır) |
| Name | nvarchar(100) |  | E | Lokasyon adı | ERP | hata (satır atlanır) |
| Type | nvarchar(15) |  | E | Tesis \| Depo \| Fason deposu | ERP, yoksa kural | varsayılan Tesis |
| Country | nvarchar(100) |  | H | Ülke | ERP | boş kalır |
| CountryCode | nvarchar(10) |  | H | Ülke kodu | ERP | boş kalır |
| Region | nvarchar(100) |  | H | Bölge | ERP | boş kalır |
| RegionCode | nvarchar(20) |  | H | Bölge kodu | ERP | boş kalır |
| City | nvarchar(100) |  | H | Şehir | ERP | boş kalır |
| CityCode | nvarchar(20) |  | H | Şehir kodu | ERP | boş kalır |
| AdditionalText1–7 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | boş kalır |
| AdditionalNumber1–3 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | boş kalır |

### stg.UnitOfMeasure
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Ortak</sub>

- Ölçü birimi.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| Code | nvarchar(10) | PK | E | Birim kodu (AD, KG, SAAT…) | ERP | hata (satır atlanır) |
| Name | nvarchar(50) |  | H | Birim adı | ERP | boş kalır |

### stg.UomConversion
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Ortak</sub>

- Malzeme bazında birim dönüşümü.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| MaterialCode | nvarchar(50) | REF | H | Malzeme (boşsa genel dönüşüm) | ERP | boş kalır |
| FromUom | nvarchar(10) | REF | E | Kaynak birim | ERP | hata (satır atlanır) |
| ToUom | nvarchar(10) | REF | E | Hedef birim | ERP | hata (satır atlanır) |
| Factor | decimal(18,6) |  | E | Çarpan | ERP | hata (satır atlanır) |

### stg.ProductionVersion
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Malzeme</sub>

- Üretim versiyonu: bir malzemenin ürün ağacı ve rota başlığı; rotaya RouteCode ile bağlanır. Faz 1'de varsayılan versiyon kullanılır.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| MaterialCode | nvarchar(50) | REF | E | Üretilen malzeme | ERP | hata (satır atlanır) |
| Code | nvarchar(30) |  | E | Versiyon kodu | ERP | hata (satır atlanır) |
| IsDefault | bit |  | E | Varsayılan versiyon | ERP, yoksa kural | kural ya da elle |
| BaseQuantity | decimal(18,4) |  | H | Baz miktar (rota ve ağaç bu miktar için) | ERP | varsayılan 1 |
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
| MaterialCode | nvarchar(50) | UK | E | Üretilen malzeme kodu | ERP | hata (satır atlanır) |
| ProductionVersionCode | nvarchar(30) | UK | E | Üretim versiyonu kodu | ERP | hata (satır atlanır) |
| ComponentMaterialCode | nvarchar(50) | REF | E | Bileşen kodu | ERP | hata (satır atlanır) |
| Quantity | decimal(18,6) |  | E | Baz miktar için bileşen miktarı | ERP | hata (satır atlanır) |
| ScrapPct | decimal(6,2) |  | H | Bileşen firesi (%) | ERP | varsayılan 0 |
| IsFixedQuantity | bit |  | H | Sabit miktarlı bileşen | ERP | varsayılan 0 |
| OpNo | int |  | H | Bağlı olduğu operasyon no (ihtiyaç tarihi için) | ERP | boş kalır |
| AdditionalText1–3 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | boş kalır |
| AdditionalNumber1–2 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | boş kalır |

### stg.Routing
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Malzeme · 1/2</sub>

- Rota: her satır bir operasyon–kaynak ilişkisi; sıra önce OpNo, sonra SeqNo. Aynı operasyonun kaynakları ayrı satırda, ResourceRole ile.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| RouteCode | nvarchar(50) | UK | E | Rota kodu | ERP | hata (satır atlanır) |
| OpNo | int | UK | E | Operasyon no (birinci sıralama) | ERP | hata (satır atlanır) |
| SeqNo | int | UK | E | Operasyon içindeki alt sıra (ikinci sıralama) | ERP | hata (satır atlanır) |
| OperationName | nvarchar(150) |  | H | Operasyon adı | ERP | boş kalır |
| ResourceCode | nvarchar(50) | REF | E | Kaynak kodu | ERP | hata (satır atlanır) |
| ResourceRole | nvarchar(10) |  | E | Primary \| Secondary | ERP, yoksa kural | varsayılan Primary |
| Consumption | decimal(18,6) |  | E | Baz miktar için kaynak tüketimi (kaynağın kapasite biriminde) | ERP | hata (satır atlanır) |
| ResourceNumber | int |  | E | Operasyonda aynı anda kullanılan kaynak adedi | ERP, yoksa kural | varsayılan 1 |
| IsSubcontracted | bit |  | H | Fason operasyon | ERP | varsayılan 0 |

### stg.Routing
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Malzeme · 2/2</sub>

- Rota: her satır bir operasyon–kaynak ilişkisi; sıra önce OpNo, sonra SeqNo. Aynı operasyonun kaynakları ayrı satırda, ResourceRole ile.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| TransferLotQty | decimal(18,4) |  | H | Transfer partisi | ERP | boş kalır |
| LaborType | nvarchar(15) |  | H | İşçi: Yetkinlik grubu \| Kaynak grubu \| Yok | Kural ya da elle | varsayılan Yok |
| LaborRefCode | nvarchar(50) | REF | H | İlgili yetkinlik ya da kaynak grubu | Kural ya da elle | kural ya da elle |
| LaborBasis | nvarchar(10) |  | H | Ekip (süre × kişi) \| Toplam (adam-saat) | Kural ya da elle | varsayılan Ekip |
| CrewSize | int |  | H | Gerekli işçi sayısı | Kural ya da elle | varsayılan 1 |
| LaborTime | decimal(18,6) |  | H | Toplam işçilik (adam-saat), LaborBasis = Toplam ise | Kural ya da elle | kural ya da elle |
| AdditionalText1–3 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | boş kalır |
| AdditionalNumber1–2 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | boş kalır |

### stg.Resource
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Kaynak · 1/2</sub>

- Kaynak: makine, işçi, fason, diğer. Kapasite kaynağın kendi biriminde günlük kapasite olarak tutulur.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| LocationCode | nvarchar(30) | REF | E | Lokasyon kodu | ERP | hata (satır atlanır) |
| Code | nvarchar(50) | UK | E | Kaynak kodu | ERP | hata (satır atlanır) |
| Name | nvarchar(150) |  | H | Kaynak adı | ERP | boş kalır |
| ResourceGroupCode | nvarchar(50) | REF | H | Kaynak grubu | ERP, yoksa kural | kural ya da elle |
| ResourceType | nvarchar(20) |  | E | Makine \| İşçi \| Fason \| Kalıp \| Fırın \| Diğer | ERP, yoksa kural | kural ya da elle |
| ResourceRole | nvarchar(10) |  | E | Primary \| Secondary | Kural ya da elle | varsayılan Primary |
| IsConstrained | bit |  | E | 1: planda kısıt, 0: sonsuz kapasite (sadece raporlanır) | Kural ya da elle | varsayılan 0 |
| CapacityUnit | nvarchar(10) | REF | E | Kapasite birimi (Saat, Adet, Ton…); rotadaki tüketim aynı birimde kabul edilir | ERP, yoksa kural | kural ya da elle |
| DailyCapacity | decimal(18,4) |  | E | Bir adet kaynağın bir çalışma günündeki kapasitesi | ERP, yoksa kural | kural ya da elle |

### stg.Resource
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Kaynak · 2/2</sub>

- Kaynak: makine, işçi, fason, diğer. Kapasite kaynağın kendi biriminde günlük kapasite olarak tutulur.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| Quantity | int |  | E | Paralel kaynak adedi | ERP, yoksa kural | kural ya da elle |
| CalendarCode | nvarchar(30) | REF | E | Çalışma takvimi | ERP, yoksa kural | kural ya da elle |
| CapacitySource | nvarchar(10) |  | H | İşçi gruplarında: Vardiyadan \| Doğrudan | Kural ya da elle | varsayılan Doğrudan |
| SubconPlanningType | nvarchar(15) |  | H | Fasonda: İş yeri \| Tedarik süresi | Kural ya da elle | boş kalır |
| SupplierCode | nvarchar(50) | REF | H | Fasonda fasoncu | ERP | boş kalır |
| SubconFixedLeadTimeDays | decimal(9,2) |  | H | Fasonda sabit süre (taşıma ve kuyruk) | Kural ya da elle | boş kalır |
| SubconVariableDaysPerUnit | decimal(18,6) |  | H | Fasonda birim başına gün (fasoncunun hızı) | Kural ya da elle | boş kalır |
| AdditionalText1–7 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | boş kalır |
| AdditionalNumber1–3 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | boş kalır |

### stg.ResourceGroup
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Kaynak</sub>

- Kaynak grubu (makine grubu, işçi kaynak grubu).  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| LocationCode | nvarchar(30) | REF | E | Lokasyon kodu | ERP | hata (satır atlanır) |
| Code | nvarchar(50) | UK | E | Grup kodu | ERP | hata (satır atlanır) |
| Name | nvarchar(150) |  | H | Grup adı | ERP | boş kalır |
| AdditionalText1–7 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | boş kalır |
| AdditionalNumber1–3 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | boş kalır |

### stg.ResourceCapacityProfile
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Kaynak</sub>

- Günlük kapasitenin dönemsel değişikliği. Birim kontrol için gelir; ana tabloda saklanmaz.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| ResourceCode | nvarchar(50) | UK,REF | E | Kaynak kodu | Kural ya da elle | hata (satır atlanır) |
| CapacityUnit | nvarchar(10) |  | E | Kapasite birimi; Resource.CapacityUnit'ten farklıysa satır hata | Kural ya da elle | hata (satır atlanır) |
| ValidFrom | date | UK | E | Başlangıç | Kural ya da elle | hata (satır atlanır) |
| ValidTo | date |  | E | Bitiş | Kural ya da elle | hata (satır atlanır) |
| DailyCapacity | decimal(18,4) |  | E | Bu aralıktaki günlük kapasite | Kural ya da elle | hata (satır atlanır) |

### stg.Calendar
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Ortak</sub>

- Çalışma takvimi başlığı (kaynaklara bağlanır).  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| Code | nvarchar(30) | UK | E | Takvim kodu | ERP, yoksa kural | kural ya da elle |
| Name | nvarchar(100) |  | H | Takvim adı | ERP, yoksa kural | kural ya da elle |

### stg.CalendarDay
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Ortak</sub>

- Takvimin gün bazında çalışma durumu.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| CalendarCode | nvarchar(30) | UK,REF | E | Takvim | ERP, yoksa kural | kural ya da elle |
| Date | date | PK | E | Gün | ERP, yoksa kural | kural ya da elle |
| IsWorkingDay | bit |  | E | Çalışma günü mü | ERP, yoksa kural | kural ya da elle |
| WorkingFraction | decimal(5,4) |  | H | Günün çalışılan oranı (yarım gün 0,5) | Kural ya da elle | varsayılan 1 |

### stg.Shift
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Kaynak</sub>

- Vardiya tanımı.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| LocationCode | nvarchar(30) | REF | E | Lokasyon kodu | ERP | hata (satır atlanır) |
| Code | nvarchar(20) | UK | E | Vardiya kodu | ERP, yoksa kural | kural ya da elle |
| StartTime | time |  | E | Başlangıç saati | ERP, yoksa kural | kural ya da elle |
| EndTime | time |  | E | Bitiş saati | ERP, yoksa kural | kural ya da elle |
| BreakMinutes | int |  | H | Mola süresi (dk) | ERP, yoksa kural | kural ya da elle |

### stg.ShiftPlan
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Kaynak</sub>

- Dönem bazında grup–vardiya–kişi sayısı. Çalışmada geçici değiştirilebilir.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| CompetenceGroupCode | nvarchar(50) | REF | H | Yetkinlik grubu (ya da) | ERP, yoksa kural | kural ya da elle |
| ResourceGroupCode | nvarchar(50) | REF | H | İşçi kaynak grubu | ERP, yoksa kural | kural ya da elle |
| ShiftCode | nvarchar(30) | REF | E | Vardiya kodu | ERP, yoksa kural | kural ya da elle |
| ValidFrom | date |  | E | Başlangıç | ERP, yoksa kural | kural ya da elle |
| ValidTo | date |  | E | Bitiş | ERP, yoksa kural | kural ya da elle |
| Headcount | int |  | E | Kişi sayısı | ERP, yoksa kural | kural ya da elle |

### stg.ResourceDowntime
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Kaynak</sub>

- Bakım ve arıza takvimi; kapasiteden düşülür. Çalışmada geçici değiştirilebilir.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| ResourceCode | nvarchar(50) | REF | E | Kaynak kodu | ERP, yoksa kural | kural ya da elle |
| DowntimeType | nvarchar(10) |  | E | Bakım \| Arıza | ERP, yoksa kural | kural ya da elle |
| StartAt | datetime2 |  | E | Başlangıç | ERP, yoksa kural | kural ya da elle |
| EndAt | datetime2 |  | E | Bitiş | ERP, yoksa kural | kural ya da elle |
| AffectedQuantity | int |  | E | Etkilenen kaynak adedi | ERP, yoksa kural | kural ya da elle |

### stg.Supplier
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Malzeme</sub>

- Tedarikçi ve fasoncu.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| Code | nvarchar(50) | UK | E | Tedarikçi kodu | ERP | hata (satır atlanır) |
| Name | nvarchar(200) |  | H | Ad | ERP | boş kalır |
| IsSubcontractor | bit |  | H | Fasoncu mu | ERP, yoksa kural | kural ya da elle |
| CalendarCode | nvarchar(30) | REF | H | Tedarikçi takvimi (kapalı dönemler) | Kural ya da elle | boş kalır |
| AdditionalText1–7 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | boş kalır |
| AdditionalNumber1–3 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | boş kalır |

### stg.MaterialSupplier
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Malzeme</sub>

- Malzeme–tedarikçi ilişkisi; satın alma parametreleri. Satın alma her zaman sürekli; yuvarlama son hesapta.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| MaterialCode | nvarchar(50) | REF | E | Malzeme | ERP | hata (satır atlanır) |
| SupplierCode | nvarchar(50) | REF | E | Tedarikçi | ERP | hata (satır atlanır) |
| Priority | int |  | H | Öncelik | ERP, yoksa kural | kural ya da elle |
| QuotaPct | decimal(6,2) |  | H | Kota (%) | ERP, yoksa kural | kural ya da elle |
| LeadTimeDays | decimal(9,2) |  | E | Tedarik süresi | ERP | hata (satır atlanır) |
| LeadTimeBasis | nvarchar(10) |  | H | Takvim günü \| İş günü | Kural ya da elle | varsayılan Takvim günü |
| MinOrderQty | decimal(18,4) |  | H | Minimum sipariş miktarı | ERP | boş kalır |
| OrderMultiple | decimal(18,4) |  | H | Kat | ERP | boş kalır |
| MaxOrderQty | decimal(18,4) |  | H | Maksimum | ERP | boş kalır |
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
| AdditionalText1–7 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | boş kalır |
| AdditionalNumber1–3 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | boş kalır |

### stg.ProjectGroup
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Malzeme</sub>

- Proje grubu (grup içi paylaşım için).  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| Code | nvarchar(50) | UK | E | Grup kodu | Kural ya da elle | hata (satır atlanır) |
| Name | nvarchar(200) |  | H | Proje grubu adı | Kural ya da elle | kural ya da elle |
| IsolationRule | nvarchar(20) |  | H | Tam izolasyon \| Ortaktan beslenir \| Grup içi paylaşım | Kural ya da elle | varsayılan Ortaktan beslenir |

### stg.Project
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Malzeme</sub>

- Proje.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| Code | nvarchar(50) | UK | E | Proje kodu | ERP | hata (satır atlanır) |
| Name | nvarchar(200) |  | H | Proje adı | ERP | boş kalır |
| ProjectGroupCode | nvarchar(50) | REF | H | Proje grubu kodu | Kural ya da elle | boş kalır |
| IsolationRule | nvarchar(20) |  | H | Proje bazında izolasyon (grubu ezer) | Kural ya da elle | boş kalır |
| Priority | int |  | H | Proje önceliği | Kural ya da elle | boş kalır |
| IsClosed | bit |  | H | Kapandı mı | ERP | varsayılan 0 |
| AdditionalText1–7 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | boş kalır |
| AdditionalNumber1–3 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | boş kalır |

### stg.SalesOrderLine
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Talep</sub>

- Müşteri sipariş satırı; teklifler Type = Teklif ile gelir. Vade: teyit tarihi, yoksa istek tarihi.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| LocationCode | nvarchar(30) | REF | E | Lokasyon kodu | ERP | hata (satır atlanır) |
| OrderNo | nvarchar(30) | UK | E | Sipariş no | ERP | hata (satır atlanır) |
| LineNo | int | UK | E | Satır no | ERP | hata (satır atlanır) |
| LineItemNo | int | UK | H | Alt satır no (ERP satırı kırılımlıysa) | ERP | varsayılan 0 |
| Type | nvarchar(10) |  | E | Kesin \| Teklif | ERP, yoksa kural | varsayılan Kesin |
| CustomerCode | nvarchar(50) | REF | E | Müşteri kodu | ERP | hata (satır atlanır) |
| MaterialCode | nvarchar(50) | REF | E | Malzeme | ERP | hata (satır atlanır) |
| ProjectCode | nvarchar(50) | REF | H | Proje | ERP | boş kalır |
| OpenQty | decimal(18,4) |  | E | Açık miktar | ERP | hata (satır atlanır) |
| RequestedDate | date |  | E | İstek tarihi | ERP | hata (satır atlanır) |
| ConfirmedDate | date |  | H | Teyit tarihi | ERP | boş kalır |
| Priority | int |  | H | Satır önceliği | Kural ya da elle | boş kalır |
| AllowPartialDelivery | bit |  | H | Kısmi teslimat (müşteriyi ezer) | ERP | boş kalır |
| Status | nvarchar(15) |  | E | Açık \| Kapandı \| İptal | ERP | hata (satır atlanır) |
| AdditionalText1–3 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | boş kalır |
| AdditionalNumber1–2 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | boş kalır |

### stg.Forecast
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Talep</sub>

- Talep tahmini (netleme ön hesapta).  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| LocationCode | nvarchar(30) | REF | E | Lokasyon kodu | ERP | hata (satır atlanır) |
| MaterialCode | nvarchar(50) | REF | E | Malzeme | ERP | hata (satır atlanır) |
| CustomerCode | nvarchar(50) | REF | H | Müşteri kodu | ERP | boş kalır |
| ProjectCode | nvarchar(50) | REF | H | Proje | ERP | boş kalır |
| Period | date |  | E | Dönem | ERP | hata (satır atlanır) |
| Quantity | decimal(18,4) |  | E | Miktar | ERP | hata (satır atlanır) |
| AdditionalText1–3 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | boş kalır |
| AdditionalNumber1–2 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | boş kalır |

### stg.Stock
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Arz ve stok</sub>

- Stok; lot ve durum bazında. Sahip: proje ya da ortak.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| LocationCode | nvarchar(30) | REF | E | Lokasyon kodu | ERP | hata (satır atlanır) |
| MaterialCode | nvarchar(50) | REF | E | Malzeme | ERP | hata (satır atlanır) |
| Warehouse | nvarchar(30) |  | H | Depo | ERP | boş kalır |
| LotNo | nvarchar(50) |  | H | Lot / seri | ERP | boş kalır |
| StockStatus | nvarchar(15) |  | E | Serbest \| Kalitede \| Bloke | ERP | varsayılan Serbest |
| ProjectCode | nvarchar(50) | REF | H | Sahip proje (boşsa ortak) | ERP | boş kalır |
| Quantity | decimal(18,4) |  | E | Miktar | ERP | hata (satır atlanır) |
| QualityEntryDate | date |  | H | Kaliteye giriş tarihi | ERP | boş kalır |
| ExpiryDate | date |  | H | Son kullanma tarihi (raf ömrü sonraki faz) | ERP | boş kalır |
| AdditionalText1–3 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | boş kalır |
| AdditionalNumber1–2 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | boş kalır |

### stg.WorkOrder
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Arz ve stok</sub>

- Açık iş emri (üretim, fason, yeniden işleme).  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| LocationCode | nvarchar(30) | REF | E | Lokasyon kodu | ERP | hata (satır atlanır) |
| OrderNo | nvarchar(30) | UK | E | İş emri no | ERP | hata (satır atlanır) |
| MaterialCode | nvarchar(50) | REF | E | Üretilen malzeme | ERP | hata (satır atlanır) |
| OrderType | nvarchar(15) |  | E | Üretim \| Fason \| Yeniden işleme | ERP, yoksa kural | kural ya da elle |
| Status | nvarchar(15) |  | E | Planlı \| Yayınlandı \| Başladı \| Kısmi \| Bitti | ERP | hata (satır atlanır) |
| OrderQty | decimal(18,4) |  | E | İş emri miktarı | ERP | hata (satır atlanır) |
| OpenQty | decimal(18,4) |  | E | Açık miktar | ERP | hata (satır atlanır) |
| StartDate | date |  | H | Başlangıç | ERP | boş kalır |
| DueDate | date |  | E | Bitiş | ERP | hata (satır atlanır) |
| ProjectCode | nvarchar(50) | REF | H | Proje (ayraç) | ERP | boş kalır |
| SalesOrderNo | nvarchar(30) | REF | H | Bağlı sipariş no (ayraç) | ERP | boş kalır |
| SalesOrderLineNo | int | REF | H | Bağlı sipariş satır no | ERP | boş kalır |
| ParentWorkOrderNo | nvarchar(30) | REF | H | Yeniden işlemede orijinal iş emri | Kural ya da elle | boş kalır |
| LastActivityDate | date |  | H | Son hareket tarihi (eskime kontrolü) | ERP | boş kalır |
| AdditionalText1–3 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | boş kalır |
| AdditionalNumber1–2 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | boş kalır |

### stg.WorkOrderComponent
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Arz ve stok</sub>

- İş emrinin bileşenleri ve çekilen miktar.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| WorkOrderNo | nvarchar(30) | REF | E | İş emri | ERP | hata (satır atlanır) |
| MaterialCode | nvarchar(50) | REF | E | Bileşen | ERP | hata (satır atlanır) |
| RequiredQty | decimal(18,4) |  | E | Gereken miktar | ERP | hata (satır atlanır) |
| IssuedQty | decimal(18,4) |  | H | Çekilen miktar | ERP | varsayılan 0 |
| AdditionalText1–3 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | boş kalır |
| AdditionalNumber1–2 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | boş kalır |

### stg.WorkOrderOperation
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Arz ve stok</sub>

- İş emrinin operasyonları ve kalan iş.  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| WorkOrderNo | nvarchar(30) | REF | E | İş emri | ERP | hata (satır atlanır) |
| OpNo | int |  | E | Operasyon no | ERP | hata (satır atlanır) |
| SeqNo | int |  | E | Operasyon içindeki alt sıra | ERP | hata (satır atlanır) |
| ResourceCode | nvarchar(50) | REF | E | Kaynak kodu | ERP | hata (satır atlanır) |
| PlannedConsumption | decimal(18,6) |  | H | Planlanan tüketim | ERP | boş kalır |
| ConfirmedConsumption | decimal(18,6) |  | H | Teyit edilen tüketim | ERP | varsayılan 0 |
| Status | nvarchar(15) |  | H | Açık \| Bitti | ERP | boş kalır |
| AdditionalText1–3 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | boş kalır |
| AdditionalNumber1–2 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | boş kalır |

### stg.PurchaseOrderLine
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Arz ve stok</sub>

- Açık satın alma ve fason siparişi satırı (ve talep).  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| LocationCode | nvarchar(30) | REF | E | Lokasyon kodu | ERP | hata (satır atlanır) |
| OrderNo | nvarchar(30) | UK | E | Sipariş no | ERP | hata (satır atlanır) |
| LineNo | int | UK | E | Satır no | ERP | hata (satır atlanır) |
| OrderType | nvarchar(15) |  | E | Satın alma talebi \| Satın alma \| Fason | ERP | hata (satır atlanır) |
| SupplierCode | nvarchar(50) | REF | H | Tedarikçi | ERP | boş kalır |
| MaterialCode | nvarchar(50) | REF | E | Malzeme | ERP | hata (satır atlanır) |
| OpenQty | decimal(18,4) |  | E | Açık miktar | ERP | hata (satır atlanır) |
| RequestedDate | date |  | H | İstenen tarih | ERP | boş kalır |
| ConfirmedDate | date |  | H | Tedarikçi teyit tarihi | ERP | boş kalır |
| ProjectCode | nvarchar(50) | REF | H | Proje | ERP | boş kalır |
| WorkOrderNo | nvarchar(30) | REF | H | Fasonda bağlı iş emri | ERP | boş kalır |
| Status | nvarchar(15) |  | E | Durum | ERP | hata (satır atlanır) |
| AdditionalText1–3 | nvarchar(255) |  | H | Ek metin alanları; etiketi FieldDefinition'da | ERP | boş kalır |
| AdditionalNumber1–2 | decimal(18,4) |  | H | Ek sayı alanları; etiketi FieldDefinition'da | ERP | boş kalır |

### stg.ProductionConfirmation
<sub>26. Entegrasyon tasarımı · Entegrasyon tabloları · Arz ve stok</sub>

- Üretim gerçekleşmeleri; ilk günden tutulur (verim önerisi ve ileriki fazlar).  ·  Entegrasyon tablosu: ERP'nin dili, ilişkiler kodla; sistem alanları ve Smartchain parametreleri hariç.

| ALAN | TIP | ANAHTAR | ZOR. | AÇIKLAMA | KAYNAK | YOKSA |
|---|---|---|---|---|---|---|
| WorkOrderNo | nvarchar(30) | REF | E | İş emri | ERP | hata (satır atlanır) |
| OpNo | int |  | H | Operasyon no | ERP | boş kalır |
| SeqNo | int |  | H | Operasyon içindeki alt sıra | ERP | boş kalır |
| ResourceCode | nvarchar(50) | REF | H | Kaynak kodu | ERP | boş kalır |
| ConfirmedQty | decimal(18,4) |  | E | Teyit miktarı | ERP | hata (satır atlanır) |
| ActualConsumption | decimal(18,6) |  | H | Gerçekleşen tüketim (süre) | ERP | boş kalır |
| StartAt | datetime2 |  | H | Başlangıç | ERP | boş kalır |
| EndAt | datetime2 |  | H | Bitiş | ERP | boş kalır |
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

- **Ne zaman:** ERP'de tutulmayan ya da entegrasyonu olmayan varlıklar: kaynaklar, takvim, vardiya, duruş, tahmin; ilk kurulumda tüm ana veri; ERP'den gelen veriyi düzeltmek için toplu düzeltme (15).
- **Şablon:** Veri sözlüğünden üretilir (02): 1. satır alan adı, 2. satır açıklama ve kural, 3. satır örnek; kod listeleri açılır liste; 'Kodlar' ve 'Açıklama' sayfaları; gizli sürüm bilgisi.
- **Yükleme:** Ekrandan sürükle-bırak (03): varlık ve sürüm tanıma, mod (ekle / güncelle ya da tam), satır bazlı ön kontrol, hata raporu, geçerli satırlarla devam.
- **Sınırlar:** Tek dosya tek varlık; 200.000 satır (parametre); eski şablon sürümü uyarı verir. Excel yolu ERP'den gelen varlığın master'ı olamaz (çakışma: ERP ezer, alan ayarına göre).
- **Dışa aktarma:** Aynı şablonlarla ana veri dışa aktarılır, düzeltilir ve elle değer olarak geri yüklenir; plan çıktıları (satın alma talebi, iş emri açma) ERP'nin alışık olduğu sütun düzeninde Excel listesi.

### Alan eşleme ve dönüşüm kuralları
<sub>26. Entegrasyon tasarımı · Alan eşleme ve dönüşüm</sub>

- Eşleme tanımı kurulumda varlık başına yapılır ve Entegrasyon ekranında görünür: ERP alanı → sözleşme alanı, dönüşüm, yoksa ne olur. Eşleme ürünün parçası değil, kurulum verisidir.

| DÖNÜŞÜM TÜRÜ | ÖRNEK | KURAL |
|---|---|---|
| Doğrudan | ITEM_CODE → Material.Code | Tip ve uzunluk kontrolü; kırpma yok, uzunsa hata. |
| Kod listesi | ERP birim 'ADET' → 'adet'; tedarik türü 'S' → DefaultProcurement = Satın alma | Eşleme tablosu; listede olmayan kod hata ya da varsayılan (alan ayarı). |
| Birim dönüşümü | Rota süresi dakika → kaynak kapasite birimi saat | Kaynağın CapacityUnit'ine çevrilir; dönüşüm yoksa uyarı, kaynak kısıtsız sayılır. |
| Tarih | '20261023' → 2026-10-23; vade: ConfirmedDate yoksa RequestedDate | Biçim adaptörde; boş tarih kural ya da varsayılanla. |
| Türetme | SC_WORK_ORDER.OPEN_QTY = ORDER_QTY − CONFIRMED_QTY | Türetme adaptörde ya da ara tabloda; sözleşme alanı tek değer alır. |
| Birleştirme | Stok: depo + lot + durum + proje → tek satır | Anahtar sözleşmede; ERP daha ayrıntılıysa toplanır, daha kabasa boş alanlar varsayılan. |
| Smartchain alanı | Resource.IsConstrained, CapacityUnit, DailyCapacity verim | ERP'de yoksa veri kuralı ya da elle değer; FieldValueSource kaynağı tutar. |

### Hangi veri nerede master
<sub>26. Entegrasyon tasarımı · Veri sahipliği</sub>

- Çift yönlü senkron yok. Her alanın tek bir sahibi var; sahibi dışındaki yerde yapılan değişiklik bir sonraki yüklemede alan ayarına göre ezilir ya da korunur.

| VERI | MASTER | SMARTCHAIN'DE | ÇAKIŞMA KURALI |
|---|---|---|---|
| Ana veri (malzeme, ağaç, rota, tedarikçi, müşteri, proje) | ERP | Salt okunur; elle değer alan bazında | ERP ezer; elle değer alan ayarına göre kalır (FieldDefinition.ManualOverrides) |
| Kaynak temel bilgisi (kod, ad, grup) | ERP ya da Excel | Salt okunur | Kaynağa göre |
| Kaynak planlama alanları (tip, kapasite birimi, günlük kapasite, verim, kritik, sonsuz limit) | Smartchain | Kural ya da elle; ERP'de varsa başlangıç değeri | Smartchain değeri kalır; ERP değeri FieldValueSource.ErpValue'da görünür |
| Takvim, vardiya, duruş | ERP varsa ERP, yoksa Smartchain (Excel) | Elle düzenlenebilir | Kaynağa göre |
| Siparişler, stok, iş emirleri, gerçekleşmeler | ERP | Salt okunur | Her yüklemede ERP; elle değişiklik yok (öncelik ve hedef tarih plan alanıdır, veri değil) |
| Tahmin | ERP ya da Excel | Excel ile yüklenir | Son yükleme geçerli; versiyonlu |
| Parametreler, senaryo tanımları, kurallar, elle değerler | Smartchain | Ekrandan | ERP'ye gitmez |
| Plan çıktıları (planlı sipariş, öneri) | Smartchain | Onaylı plan | Faz 1: Excel ile ERP'ye elle; Faz 2: API geri yazma, ERP belge no geri okunur |

### Senkron sıklığı ve zamanlama
<sub>26. Entegrasyon tasarımı · Senkron sıklığı</sub>

- **Gece tam çekim · 22:00:** Tüm ERP varlıkları tam çekim, doğrulama, tam yükleme (v+1), ardından senaryolar. Bitiş sınırı 06:00. Excel varlıkları son yüklenen haliyle kalır.
- **Gün içi kısmi · elle:** Stok ve siparişler (satış, satın alma, iş emri) key user tarafından çekilip kısmi yüklenir; 'yeni veri var' bildirimi. Hedef 5 dk altı.
- **Haftalık ve elle:** Takvim, vardiya, tahmin, kaynak: haftalık ya da değişince Excel ile. Ham veri temizliği Pazar 03:00.
- **Artımlı çekim:** API'de LastModified, SQL'de SC_LAST_MODIFIED varsa yalnız değişenler; silinenler için tam liste ya da SC_ACTION = D gerekir. Artımlı destek yoksa tam çekim (varsayılan).
- **Zamanlama ayarı:** Saatler ve paralellik Entegrasyon ekranında (admin); bitiş sınırı ve işçi sayısı sistem sahibi ayarı. Müşterinin ERP gece işleriyle çakışmaması için saat devreye almada belirlenir.
- **Çakışma yönetimi:** Gece akışı sırasında elle çekim kapalı; gün içi kısmi yükleme sırasında ikinci yükleme kuyrukta bekler. Yükleme açık çalışmaları etkilemez.

### Hata yönetimi
<sub>26. Entegrasyon tasarımı · Hata yönetimi</sub>

- Hata dört düzeyde ele alınır: bağlantı, varlık, satır, alan. Her düzeyin davranışı sabit; kullanıcıya nerede ne olduğu ve ne yapması gerektiği söylenir.

| DÜZEY | ÖRNEK | DAVRANIŞ | NEREDE GÖRÜNÜR |
|---|---|---|---|
| Bağlantı | API ulaşılamıyor, SQL kimlik hatası, zaman aşımı | 3 deneme artan aralıkla; sonra varlık 'hata', önceki ham veri korunur; diğer varlıklar devam | Veri yükleme ekranı, Entegrasyon 'son çağrı', Sistem sağlığı |
| Varlık | Şema uyumsuzluğu, eşlenmemiş alan, hata eşiği (%5) aşımı | Varlık yüklenmez, önceki versiyonun satırları taşınır (kısmi); sabah ekranında kırmızı | Veri yükleme, Entegrasyon 'eşlenmemiş alan', Sabah ekranı |
| Satır | Zorunlu alan boş, referans yok, negatif süre, döngü | Satır atlanır, bulgu listesine yazılır; eşik altındaysa varlık yüklenir | Doğrulama detayı, hata raporu (xlsx) |
| Alan | Boş temin süresi, boş takvim, bilinmeyen birim | Veri kuralı ya da varsayılan ile tamamlanır; uyarı olarak Veri kalitesi listesine düşer | Veri kalitesi, Ana veri (kaynak etiketi) |
| Yükleme | Veritabanı hatası, süre aşımı (30 dk) | Ya hep ya hiç: geri alınır, önceki versiyon geçerli; parti yeniden kullanılabilir | Veri yükleme, Sistem sağlığı, destek paketi |
| Sessiz hata | Satır sayısı dünden %30 az, sipariş sayısı sıfır | Tutarlılık uyarısı: yükleme durmaz ama 'şüpheli parti' etiketi, sabah ekranında (öneri) | Sabah ekranı, Veri yükleme |

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
- **Yetki:** Entegrasyon tanımı: admin ve üstü. Çekim ve yükleme: key user ve üstü. End user hiçbirini görmez.

### Entegrasyon devreye alma adımları
<sub>26. Entegrasyon tasarımı · Devreye alma</sub>

- **1 · Keşif:** ERP ve sürüm, servis var mı, veritabanı erişimi, hangi varlık nerede tutuluyor, hangi alanlar boş. Çıktı: yöntem kararı varlık başına.
- **2 · Eşleme:** Alan eşleme tanımı varlık başına; kod listeleri; Smartchain'e özgü alanlar için kural taslakları. Çıktı: entegrasyon tanımı ve şablonlar.
- **3 · Test çekimi:** Her varlık için örnek çekim (ilk 200 satır), doğrulama raporu, eşlenmemiş alan ve hata listesi. Çıktı: düzeltme listesi (müşteri BT + biz).
- **4 · Tam yükleme ve kalite:** İlk tam yükleme, veri kalitesi raporu, kurallarla tamamlama; sentetik yerine gerçek veriyle ilk plan. Çıktı: v1 veri versiyonu.
- **5 · Paralel çalışma:** 2–4 hafta gece akışı; sabah ekranı ve dünden bugüne ile izleme; ERP'ye Excel listesiyle giriş denemesi. Çıktı: hata eşiği ve zamanlama kararı.
- **6 · Canlı:** Onaylı plan yayını; aksiyon listesi ile ERP girişi; destek paketi ve geri bildirim düzeni.

### Devreye almada sorumluluklar
<sub>26. Entegrasyon tasarımı · Sorumluluk paylaşımı</sub>

- Kapalı ağ ve uzaktan erişim yokluğu nedeniyle müşteri BT'sinin payı büyüktür; her adımda kimin ne yapacağı yazılıdır.

| KONU | BIZ (SMARTCHAIN) | MÜŞTERI BT / KEY USER |
|---|---|---|
| Yöntem seçimi | Keşif, öneri, karar kaydı | ERP erişim bilgisi, servis / veritabanı imkânı |
| API adaptörü | Geliştirme, test, paket | Servis hesabı, uç nokta dokümanı, güvenlik duvarı |
| SQL arayüz tabloları | Şema, örnek veri, doğrulama raporu | ETL yazma, zamanlama, tabloları doldurma |
| Excel | Şablonlar, yükleme eğitimi | Doldurma ve yükleme (key user) |
| Eşleme ve kurallar | Taslak, kalite kontrolü | Onay, kod listelerinin anlamı |
| Zamanlama | Varsayılan 22:00, bitiş 06:00 | ERP gece işleriyle çakışma kontrolü |
| İzleme ve destek | Destek paketi, sürüm güncelleme | Sabah ekranı, hata bildirimi, paket iletimi |

### Doğruluk raporları için ek veri ihtiyacı (A-22)
<sub>26. Entegrasyon tasarımı · Raporlar için ek veri (A-22)</sub>

- 25. adımdaki gerçekleşme raporları (16–20) ve değer göstergeleri için ERP'den ek veri gerekir. Hepsi 'isteğe bağlı' sınıfında: gelmezse ilgili rapor kapalı kalır, plan etkilenmez.

| VERI | ALANLAR | KULLANAN | YÖNTEM / SIKLIK |
|---|---|---|---|
| Sevkiyat / sipariş kapanışı (yeni varlık) | OrderNo, LineNo, ShipDate, ShippedQty, IsClosed | R17 Teslim performansı, R19 Öneri takibi, R18 | API · SQL · gece artımlı |
| Üretim gerçekleşmesi (mevcut, ek alan) | ReasonCode (sapma nedeni), ActualResourceId | R16 Plan–gerçekleşen | API · SQL · gece artımlı |
| Satın alma teslimatı (ek alan) | PurchaseOrderLine.ReceivedDate, ReceivedQty | R19 Öneri takibi, R05 | API · SQL · gece |
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
