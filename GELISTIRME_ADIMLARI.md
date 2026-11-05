# Smartchain · Geliştirme adımları

Son güncelleme: 27.10.2026

Takvimden bağımsız, sırayla ilerleyen kontrol listesi. Her adım konuşulur, ekran ve fonksiyonları netleşir, geliştirilir ve işaretlenir. Parantez içindeki numaralar 24. adımdaki ekran ve fonksiyon numaralarıdır.

**Durum:** `[ ]` başlanmadı · `[~]` devam ediyor · `[x]` bitti

**Her adımın "bitti" tanımı:** prensip slaytı ve mockup okundu → API, ekran ve test yazıldı → sentetik veriyle çalışıyor → docs'ta "uygulandı" işlendi → demo yapıldı.

**Sıra kuralı:** Önce altyapı, veri ve ekranlar; optimizasyon, çözüm motoru ve simülasyonlar en son. Plan ekranları motordan önce elle hazırlanmış plan fikstürüyle geliştirilir; motor arayüzü baştan sabittir.

---

## Aşama 0 · Altyapı

- [x] 0.1 Repo, CLAUDE.md, docs taşıma (19, 21, 23, 24, 26)
- [x] 0.2 Veritabanı: ana tablolar, stg.*, veri yönetimi ve sistem tabloları; ileri ve geri geçiş betikleri
- [x] 0.3 Uygulama iskeleti: FastAPI katmanları, hata yönetimi, log
- [x] 0.4 İş kuyruğu (Job) ve WebSocket bildirim iskeleti (47, 48 çekirdeği · K-67–K-69, A-36)
- [x] 0.5 Motor arayüzü ve sahte motor (fikstür döndürür) · K-70, K-71; `docs/09-motor-arayuzu.md`
- [~] 0.6 Kurulum iskeleti: Windows servisleri, IIS, ayrı SQL Server; temiz makineye kurulum · K-72–K-75; `docs/10-kurulum.md`. Paket, betikler ve testler hazır; temiz makine (Hyper-V, Windows Server 2025) testi bekliyor; bu turda SQL Server bellek ön kontrolü (K-94) de denenir: sınırsız max server memory'de uyarı, kurulum durmaz
- [x] 0.7 HiGHS paketleme denemesi (yalnız paket, model yok) · K-76; highspy 1.15.1 (MIT) pakette, LP ve MILP paket kontrolü internetsiz geçti; sanal makinede 0.6'nın `verify.ps1` turunda da denenecek
- [x] 0.8 Sentetik veri v0 (22): ana veri ve işlem verisi; temiz hâli ana tablolara, kirli hâli entegrasyon Excel'i (docs/11, K-78) · K-79, K-80

## Aşama 1 · Arayüz temeli

- [x] 1.1 Kabuk: React iskeleti, gruplu menü (iki seviye, arama), daraltılabilir kenar menü, bağlam çubuğu (U-17, U-22, K-81, K-82) · K-83; `app/web`
- [x] 1.2 Stil sistemi: palet, gömülü fontlar, durum renkleri, dört yazı boyutu seviyesi (U-1–U-5, U-23) · K-85, K-86; örnek sayfa /stil
- [x] 1.3 Ortak tablo bileşeni: alan ekle/çıkar, çoklu sıralama, filtre tipleri (U-6–U-8) · K-87, K-88; deneme sayfası /tablo
- [x] 1.4 Görünüm: kayıtlı görünüm, kolon düzeni ve sabitleme, gruplama, aktif filtre, boş değer (U-9–U-13) · K-89, K-90
- [x] 1.5 Dışa aktarım: Excel'e aktarma (86), ekranda ne görünüyorsa (U-14); Türkçe sayı ve tarih biçimi (U-19); biçim tanımı U-24'ün (1.6) Excel'e taşınabileceği yapıda. Yapıştırma ve toplu düzenleme 6.2'de · K-91, K-92, K-93
- [x] 1.6 Koşullu biçimlendirme: kolon bazında kural, hücre ve yazı rengi (paletten), kalın yazı, ikon; görünümle kaydedilir ve Excel'e taşınır (U-24) · K-95, K-96

## Aşama 2 · Yönetim ve sistem

- [x] 2.1 Giriş ve oturum (89) · K-97, K-98
- [x] 2.2 Rol bazlı yetki altyapısı (90) · K-99, K-100
- [x] 2.3 Kullanıcılar ekranı (22) · kullanıcı yönetimi (88) · kullanıcının yazı boyutu tercihinin saklanması (U-23) · kurulumda ilk hesap: install.ps1 sonunda tek System owner hesabı geçici şifreyle açılır · K-101, K-102
- [x] 2.3b Testler ayrı veritabanında (2.3 demosundan sonra, 2.4'ten önce): bütün veritabanı testleri `Smartchain_test`'te koşar; geliştirme veritabanına hiçbir test yazmaz ya da silmez; sentetik veri test veritabanına kurulur; CLAUDE.md'deki "Testler geliştirme veritabanına yıkıcı işlem yapamaz" kuralı bu adım bitince tam karşılanır · K-103
- [x] 2.3c Arayüz metinlerinin sadeleştirilmesi (2.3b'den sonra, 2.4'ten önce): mevcut ekranlardaki "Arayüz metni" kuralına (docs/12) aykırı metinler düzeltilir; her metin için öneri tablo olarak sorulur, seçimi kullanıcı yapar. Geçici yerler ("Bu ekran … adımında gelecek", "… 8.1'de gelir") ve geliştirme sayfaları (`/stil`, `/tablo`) kapsam dışı · docs/12 "Arayüz metni"
- [x] 2.4 Sistem ayarları (25) · veri sözlüğü ve ek alan etiketleri (96) · K-104, K-105
- [x] 2.5 Sistem sağlığı (24) · sağlık (94), iş kuyruğu (93) · K-106, K-107
- [x] 2.6 Denetim izi altyapısı (98) · ekran 26 · K-108, K-109

## Aşama 3 · Veri alma (Extract)

- [x] 3.1 Excel şablonu üretimi (02) · ekran 02 iskeleti · K-110
- [x] 3.1b Alan gözden geçirmesi (A-17; K-111…K-128): 26 tablonun alanları yükleme sırasıyla tablo tablo gözden geçirilir; değişiklikler toplu olarak docs/02, docs/03, şema, şablon, sentetik veri ve kirli Excel'e işlenir. 3.2'den önce yapılır.
- [x] 3.2 Excel yükleme → Staging (03) · K-129 · ekran 02: menüde "Excel'den yükle" açılır, "Son yükleme zamanı" kolonu · `stg` tekil indeksleri kalkar, tekrar kontrolü sözleşmedeki anahtarı okur · yapısal kontrol tek kod (`app/integration/structural.py`), 3.3 ve 3.4 de kullanır · yöntem kısıtı 3.3'e kadar uygulanmaz
- [x] 3.2b Stok tutulamaz malzeme · `Material.IsNonStockable`, K-113 eki, A-44 · ERP, yoksa veri kuralı; varsayılan yok · üretilen ve satın alınan malzemede olabilir (karışım, hamur, sıcak ara ürün gibi); Phantom'dan farkı: malzeme ayrı üretilir ya da teslim alınır ama beklemeden tüketilir · Malzeme şablonu v4, ekran kolonu, sentetik veride iki örnek · uyarı 3.4'te, motor Aşama 10'da
- [ ] 3.3 SQL arayüz okuyucu → Staging (01), entegrasyon tanımı (91) · A-38: ham tablo + view akışı, varlık başına yöntem seçimi (view, Excel, API) · ekran 02: "Yöntem" kolonu (Excel, SQL, API), "Bu tabloyu çekimden çıkar", yönteme göre şablon ve yükleme kısıtı (K-110) · ayarlar formla değil tablo üzerinde, hücre içi düzenleme (bileşen 6.x elle değer düzeltmede de kullanılır): "Yöntem" seçim kutusu, yalnız System owner değiştirir; "Çekim" aç/kapa anahtarı, Admin ve üstü değiştirir; Key user ikisini yalnız görür (End user ekranı görmez). Değişiklik anında kaydedilir, denetim izine yazılır. Çekim kapatılırken sebep zorunlu (küçük kutu); sebep, kapatan ve tarih satırın ipucunda; açarken uyarı. View ve bağlantı bilgisi, API adresi ekran 23'te (91); yöntem SQL olup view tanımlı değilse satırda uyarı
- [ ] 3.4 Yapısal ve mantıksal doğrulama, hata raporu (04): 3.2'nin `app/integration/structural.py` kodu ve `adm.ImportFinding` kullanılır; docs/03'te ANAHTAR kolonu varlık listesindeki anahtarlarla uyumsuz yerler burada denetlenir · "boşsa hata" türündeki kontroller (ör. `Resource.CapacityUnit`, K-117) veri kurallarından sonra çalışır; kuralla dolacak satırlar önceden reddedilmez · yalnız yapısal kontrol (tip, uzunluk, zorunlu alan, tekrar eden anahtar): değer listesi zorlanmaz, dışındaki değerler doğrulamada bilgi olarak gösterilir (K-110) · mantıksal kontroller de burada: negatif miktar, `UomConversion.Factor` sıfırdan büyük olmalı (K-112) gibi; satır hatası · yeni birim kodu ilk görülünce bilgi satırı ("Yeni birim: Kg"), yüklemeyi durdurmaz (K-112) · aynı ağacı kullanan üretim versiyonlarının `BaseQuantity`'si farklıysa uyarı (K-115) · rota satırında `ResourceCode` ya da `ResourceGroupCode` dolu olmalı, ikisi de boşsa satır hatası; ikisi de doluysa `ResourceCode` geçerli, kaynak o grubun üyesi değilse uyarı; bir kaynak grubundaki kaynakların kapasite birimi farklıysa uyarı (K-116) · `IsNonStockable` = 1 olan malzemeye Stok tablosunda kayıt gelirse uyarı (K-113)

## Aşama 4 · Dönüştürme (Transform)

- [ ] 4.1 Veri kuralı uygulama, Staging üzerinde (19) · Lokasyon bayrakları (K-111): boş bayrak kuralla dolar; `Type` ile bayraklar arasında ürün içinde bağ, varsayılan kural ya da varsayılan değer yok, ilişki kurulumda müşteriye göre veri kuralıyla tanımlanır
- [ ] 4.2 Veri kuralları ekranı (04): tanımlama, önizleme, sıralama, aç/kapa (16–18)
- [ ] 4.3 Aktarım filtresi (yeni, 99): tanım ve önizleme · yöntem açık (A-34; teknik kapsam view'da, iş kapsamı burada: A-38)
- [ ] 4.4 Referans kontrolü ve kod→Id eşleme · birim alanları referans kontrolüne girmez (K-112) · `UomConversion` lokasyondan bağımsızdır: dönüşüm satırı aynı `MaterialCode`'a sahip her lokasyonun malzemesine bağlanır (K-112, docs/03)

## Aşama 5 · Yükleme (Load)

- [ ] 5.1 Değer önceliği (ERP, kural, elle, varsayılan) ve ERP değerinin saklanması (FieldValueSource) · veri sözlüğünde Sınıf, Değer önceliği, Manuel, Senaryo, Zorunlu ve Varsayılan değer düzenlemesi açılır (pencerede pasif öğeler aktifleşir); zorunlu ve `DataRule` kilidi, varsayılan tip denetimi, etki sayısı ve "Şimdi uygula" (K-104)
- [ ] 5.2 Tam yükleme ve veri versiyonu (05, 07) · yüklemenin özet denetim kaydı (K-108) · `core.UnitOfMeasure` diğer tablolarda geçen birim kodlarından otomatik oluşur (`Material.BaseUom`, `Resource.CapacityUnit`, `UomConversion.FromUom` ve `ToUom`, `BOM.ComponentUom`, `SalesOrderLine.Uom`, `Forecast.Uom`, `Stock.Uom`, `WorkOrder.Uom`, `WorkOrderComponent.Uom`, `PurchaseOrderLine.Uom`), `Name` boşsa `FromUomName` ya da `ToUomName`'den dolar, `Decimals` için varsayılan yazılmaz (K-112) · birim dönüşümü kullanılırken ters yön ve zincir kuralı (docs/03, K-112)
- [ ] 5.3 Kısmi yükleme (06)
- [ ] 5.4 Aktarım raporu, yükleme geçmişi, ham veri temizliği (08, 09) · yüklenen dosyalar (`SMARTCHAIN_IMPORT_DIR`) ve terk edilen "Ön kontrol" partileri bir hafta sonra silinir (K-129)
- [ ] 5.5 Veri yükleme ekranı (02): ETL'in tamamı tek ekranda, adım adım durumuyla · yükleme işinin özeti (`Job.Summary`: "Tam yükleme · <tarih>"; K-107) · 3.1'deki iskeletin kalanı: sayılar, üst düğmeler, sağ paneller
- [ ] 5.6 Gece ETL akışı: zamanlanmış işler (92), Entegrasyon ekranı (23) · Sistem sağlığında zamanlayıcı satırı (K-106)

## Aşama 6 · Ana veri ve kalite

- [ ] 6.1 Ana veri ekranları (03, fn 10), sekme sekme:
  - [ ] Lokasyon
  - [ ] Birim: ad ve ondalık hane burada elle ya da veri kuralıyla yönetilir (K-112)
  - [ ] Birim dönüşümü
  - [ ] Kaynak: günlük kapasite, paralel adet, kapasite kaynağı, fason parametreleri ve takvim burada tanımlanır, entegre edilmez (K-117)
  - [ ] Malzeme: malzeme blokajı (fonksiyon 99, K-126) bu sekmeden tanımlanır, tablosu bu adımda açılır; motorda uygulanışı Aşama 10
  - [ ] Ürün ağacı: `ScrapRatio` yüzde gösterilir (`percent`, K-113)
  - [ ] Rota
  - [ ] Tedarikçi: `MaterialSupplier.QuotaRatio` yüzde gösterilir (`percent`, K-113, K-118)
  - [ ] Müşteri
  - [ ] Proje
  - [ ] Takvim
  - [ ] Vardiya
- [ ] 6.2 Değerin kaynağı (11), elle değer girme ve kaldırma (12, 13) · U-15, U-16: yapıştırma, toplu düzenleme, doğrulama, kaydetme
- [ ] 6.3 Değişiklik geçmişi (14) · denetim izinden okur; denetim izinde "Kayda git" ve bağlı kayıtlar (K-108)
- [ ] 6.4 Excel ile toplu düzeltme (15)
- [ ] 6.5 Veri kalitesi ekranı (05) · kontrol, düzeltme aksiyonu (20, 21) · aktif ve kritik olup kapasitesi tanımsız kaynak uyarı (K-117) · tedarik satırında `FixedLeadTimeDays` ve `VariableLeadTimeDays` ikisi de boşsa uyarı (K-118)

## Aşama 7 · Parametreler

- [ ] 7.1 Parametre seti (22) · tedarikçi seçim kuralı seçilir: en kısa tedarik süresi ya da `Priority` (K-118) · `SafetyStock` ile `StockCoverageDays` ikisi de doluysa hangisinin geçerli olacağı (büyük olan, yalnız miktar, yalnız gün…) motor parametresi olarak burada seçilir (K-113)
- [ ] 7.2 Zaman yapısı (23)
- [ ] 7.3 Kapasite parametreleri (24) · verim ve hedef doluluk burada tanımlanır, entegre edilmez; vardiyadaki kişi sayısının işçi kaynaklarının kapasitesine nasıl dönüşeceği burada netleşir (K-117)
- [ ] 7.4 Alokasyon ve öncelik kuralı (25)
- [ ] 7.5 Uyarı eşikleri (26)
- [ ] 7.6 Gece senaryo tanımları ekranı (07) · tanım, sıra ve aç/kapa (27, 28)

## Aşama 8 · Plan ekranları (fikstürle)

- [ ] 8.0 Plan fikstürü: sentetik veri için elle hazırlanmış plan (planlı sipariş, doluluk, karşılama, pegging, uyarı, metrik)
- [ ] 8.1 Senaryolar (08) · karşılaştırma (42)
- [ ] 8.2 Çalışma (09) · açma, iz, geri alma, yeniden hesap düğmesi (sahte motorla), eş zamanlı sınır, bildirim, kapatma (43–49) · önce A-37 (değişiklik etkisi ve yeniden hesap) karara bağlanır · iptal edilen işte çalışmanın durumu ve önceki sonuç; çalışma ekranında sıra (K-107) · çalışma işinin özeti (`Job.Summary`: "<çalışma adı> · yeniden hesap"; K-107) · kullanıcının başlattığı plan hesabının denetim kaydı (K-108)
- [ ] 8.3 Kaynak doluluk raporu (10)
- [ ] 8.4 Ürün bazlı planlama (11) · 50, 51
- [ ] 8.5 Kaynak bazlı planlama (12) · 52–55
- [ ] 8.6 Sipariş bazlı planlama (13) · 56–58
- [ ] 8.7 Gantt (14) · 59, 60
- [ ] 8.8 Kilit ve dondurulmuş dönem (61, 63) · A-14 kararı
- [ ] 8.9 Malzeme planı (15) · 64, 65
- [ ] 8.10 Öneriler (16) · 66–69
- [ ] 8.11 Pegging ve gecikme nedeni (17) · 70, 71
- [ ] 8.12 Yayın (19) · 76–81 · yayın zinciri; yayın kayıtları denetim izine yazılır (K-108)

## Aşama 9 · Takip ve rapor

- [ ] 9.1 Ana sayfa (01) · 82 · eşik uyarıları ve Sistem sağlığı hata satırı bağlantısı (K-106)
- [ ] 9.2 Uyarı iş listesi (20) · 83, 84 · uyarı geçmişi denetim izinden (K-108)
- [ ] 9.3 Rapor altyapısı (21) · 85, 87 · dışa aktarım izi raporu denetim izinden (87, K-108)
- [ ] 9.4 Raporlar tek tek: 25. adımdaki gerçekleşme gerektirmeyen raporlar

## Aşama 10 · Motor

- [ ] 10.1 Ön hesap (29) · motor teklifi `SalesOrderLine.IsQuote`'tan okur, plana dahil etme senaryo parametresi bu bayrağa bağlıdır (K-60, K-127) · ürünün kendi geçerli versiyonu yoksa motor `MaterialReference` ile referans ürünün ağacını ve rotasını kullanır; `ReferenceProductionVersionCode` boşsa versiyonu motor seçer, `TimeFactor` süreye uygulanır (K-126) · iş emrinin kendi bileşen ve operasyon satırları geldiyse motor onları kullanır, gelmediyse `ProductionVersionCode`'un ağacına ve rotasına gider; `WorkOrder.IsFixed` iş emrinin tarihi ve miktarı değişmez (K-124) · `Stock.ExpectedAcceptanceDate`: kalitedeki stoğun kullanılabilir hâle gelmesi beklenen tarih motorda nasıl kullanılır (K-9, K-123) · `Forecast.DeliveryPoint`: tahmin miktarı dönemin başında mı sonunda mı hazır olmalı; hangi tahmin tipinin plana gireceği veri kuralıyla (K-122) · beklemedeki satırın (`SalesOrderLine.IsOnHold`) planda nasıl ele alınacağı (K-120) · plana yalnız `IsActive` malzeme girer (K-113) · `ResourceGroupAssignment` geçerlilik tarihleri yalnız girdi, motor şimdilik kullanmaz; `IsFurnace` ve `IsMold` Faz 1 planlamada kullanılmaz (K-117) · birim dönüşümü kullanılırken ters yön ve zincir kuralı, motorun bütün adımlarında (docs/03, K-112)
- [ ] 10.2 MRP patlatma (30) · tedarik süresi = `FixedLeadTimeDays` + miktar × `VariableLeadTimeDays`; ikisi de boşsa süre 0 sayılmaz, satır kullanılmaz; 7.1'deki kurala göre tek tedarikçi (en kısa süre ya da `Priority`), `QuotaRatio` kullanılmaz (K-118) · güvenlik stoğu hedefi 7.1'deki parametreye göre `SafetyStock` ya da `StockCoverageDays`'ten (K-113)
- [ ] 10.3 Kurallı yerleştirme ve sezgisel (33) · rota satırında yalnız grup doluysa operasyon grubun herhangi bir kaynağında yapılabilir, seçim motorun kararı (K-116)
- [ ] 10.4 Model kurma, LP (31) · malzeme kısıtı yalnız `IsCritical` malzemelere uygulanır, kritik olmayanın her zaman temin edilebildiği varsayılır (K-113) · alternatif versiyon seçimi (A-40) · kaynak grubu satırında kaynak seçimi ve tüketim biriminin nasıl okunacağı (K-116) · alternatif bileşen ve operasyon kullanımı (A-41) · `BorrowPayback`: açık ödünçler motora girdi, önerilen ödüncün onay akışı ve geri ödeme kısıtı; tablo hem ERP'den hem Smartchain'in onayladığı ödünçlerden beslenir, kaynak ayrımı (ERP ya da Smartchain) gerekir, tam yükleme Smartchain kayıtlarını silmez, K-18 ile ilişkisi burada netleşir (K-119)
- [ ] 10.5 Çözücü adaptörü ve süre bütçesi (32, 34) · çalışan işi durdur ve en iyi çözümü sakla, iptal; onaylanmayan durdurmayı sonlandırma (K-107)
  - [ ] Çalışan modelin LP dosyası, çözüm (solution) dosyası ve çözücü logu her plan hesabı için ayrı klasöre yazılır (K-77)
- [ ] 10.6 Son hesap (35)
- [ ] 10.7 Mevcut arz önerileri, uyarı üretme, metrikler, açıklama (36–39)
- [ ] 10.8 Sahte motorun yerine gerçek motor; plan fikstürü altın plan kabul testi olur
- [ ] 10.9 MILP
- [ ] 10.10 Anlık etki önizlemesi (62) ve yeniden hesap (46), gerçek motorla
- [ ] 10.11 Gece akışı ve yeniden çalıştırma (40, 41) · gece işinin özeti (`Job.Summary`; K-107)
- [ ] 10.12 Termin sorgusu ve olay senaryoları ekranı (18) · 72–75 · termin sorgusu işinin özeti (`Job.Summary`; K-107)
- [ ] 10.13 Motor ayarları (96): çözücü, süre bütçesi, işçi sayısı, eş zamanlı sınır · Sistem sağlığında süre trendi, bütçe çizgisi ve %90 eşiği; tahmini bekleme; ayrı işçi havuzu kararı (K-106, K-107)

## Aşama 11 · Ürünleşme

- [ ] 11.1 Destek paketi (95) · Sistem sağlığında düğme ve hatadan "Destek paketine ekle" (K-106)
- [ ] 11.2 Sürüm güncelleme (97)
- [ ] 11.3 Yedekleme, geri yükleme, lisans
- [ ] 11.4 Kurulum paketinin tamamı (27. adım)
- [ ] 11.5 API adaptörü (Faz 2) · varlık başına yöntem seçimine (A-38) üçüncü seçenek olarak bağlanır
- [ ] 11.6 Doğruluk raporları (A-22)

---

## Bekleyen kontroller

Adımı kapanmış ama elle denenmesi sonraya bırakılmış işler.

- [x] 1.5 · Arka plan aktarımı: eşiği geçici düşür (`INSERT INTO adm.SystemSetting (SettingKey, Value) VALUES ('ExportSyncMaxRows', '50')`), /tablo'da "Hazırla", iş göstergesi ve "İndir" bildirimi, iş listesinden indirme; sonra ayarı sil (`DELETE FROM adm.SystemSetting WHERE SettingKey = 'ExportSyncMaxRows'`).
- [x] 1.5 · Dışa aktarım izi: `SELECT TOP 5 * FROM adm.AuditLog ORDER BY 1 DESC` ile aktarımların "Dışa aktarım" kaydı olarak yazıldığını gör.
- [ ] 0.6 · Uygulama hesabı yetkisi (K-109): Windows ve SQL kimliğiyle kurulumda `verify.ps1`'in duman testi `adm.AuditLog` için güncelleme ve silme yetkisi olmadığını doğrular; servisler `db_owner` olmadan çalışır.
- [ ] 0.6 · Temiz makine (sanal makine) kurulum testi. Not (2.3): install.ps1 sonunda tek System owner hesabı geçici şifreyle açılır; sanal makine turunda bu da denenir. İlk hesabın geçici şifresi install logunda yer almamalı (K-102). Temiz makinede Excel süresi iki kez ölçülür: antivirüs gerçek zamanlı tarama açıkken ve ürün klasörleri hariç tutulmuşken (`docs/10-kurulum.md`).
- [ ] 0.6 · Excel yükleme eşik ölçümü (`ImportSyncMaxMb`, K-129): temiz makinede ve müşteri sunucusunda ilk kurulumda, ortanca.
- [ ] 1.6 · Excel süresi bu laptopta 0,8–3,2 sn arası dalgalanıyor; sorgular hedefte. Güçlü aday: dosya yazımını tarayan antivirüs (ESET ekrn ~%31). Kapanış 0.6'da.
  - Ölçümler (10.000 satır, ortanca ms; düz / gruplu / 10 kural; hedef 3000): 30.10 10.14: 753 / 869 / 935 · 30.10 11.25: 2588 / 2859 / 3112 · 2.2 kapanışı: 2410 / 2600 / 2910 · 03.11 1. koşu: 2333 / 950 / 953 · 03.11 2. koşu: 786 / 940 / 983 · 03.11 yeniden başlatma sonrası: 1394 / 3163 / 2806.

## Sonraya bırakılanlar

Konuşulup bilerek ertelenen işler. Sırası gelen adımın planında ele alınır.

- **Akış yapısı kurulumda ayarlanır (5.6'da fonksiyon 92 madde madde gözden geçirilir):** gece akışının yapısını (hangi adımlar, sıra, bağımlılık, başlangıç saati, günler, bitiş sınırı, adım hata verirse devam / dur) kurulumda System owner ayarlar; hangi senaryoların çalışacağı müşterinin kararıdır (7.6, fonksiyon 27, 28). Docs'taki "zincir sırası değiştirilemez" ve sabit değerler (22:00 çekim, 06:00 bitiş, 2 paralel senaryo, hafta sonu açık, Pazar 03:00 temizlik, 22:00–06:00 arası yasaklar) varsayılan olmama prensibine göre düzeltilir. Bakılacaklar: adımların iş türü olarak tanımlanması, zorunlu ön koşullar (ör. doğrulama çekimden sonra), birden fazla akış (ör. gün ortası kısmi yükleme), yetki (K-100).
- **Çoklu dosya ile Excel yükleme (3.3 ya da 5.5'te ele alınır):** pencerede birden fazla dosya seçilir; her dosyanın tablosu şablondaki teknik addan anlaşılır, hepsi tek listede ön kontrol edilir. Her dosya yine tek tabloya karşılık gelir; docs/06 fonksiyon 03'teki "tek dosya tek varlık" buna göre düzeltilir.
- **Malzeme bazlı ikame:** ağaçtan bağımsız ikame tablosu şimdilik yok; ağaç içi alternatif `BOM.AlternativeGroup` (A-41), ağaç bazlı alternatif ayrı ağaç kodu ve üretim versiyonu (A-40) ile çözülür (K-115).
- **Yapılandırılabilir grafik (9.3'te ele alınır):** grafik, gruplanmış tablonun başka bir çizimi olarak liste altyapısının (K-87, K-90) üstüne kurulur: X ekseni gruplanan alan, değer toplanan alan ve toplam tipi, seri ikinci gruplama; tipler çubuk, yığılmış çubuk, çizgi, çubuk + çizgi (pasta yok). Görünümle kaydedilir (K-89), Excel'e gerçek grafik olarak taşınır; seri renkleri 1.2'deki sırayla, kırmızı ve kiremit seri rengi olmaz. Kullanıcı kendi grafiğini kurar, kurulumda hazır görünümler bırakılır; End user da kurabilir (K-99). Gantt, kapasite doluluk, pegging gibi planlama ekranlarının görselleri sabittir, yapılandırılmaz. Kütüphane pakete gömülü, internetsiz. Ana sayfanın küçük grafikleri (9.1) aynı altyapıyı kullanır.
- **1.6 Koşullu biçimlendirme:** çoklu koşul (VE/VEYA), renk skalası ve veri çubuğu, grup başlığı ve ara toplam satırlarına kural.
- **Kullanıcılar (2.3):** lisans kullanıcı sınırı ve sayacı (fonksiyon 88; lisans dosyası 11.3'te gelir, sınır ona bağlı; System owner hesapları lisans kullanıcı sayısına girmez); kapatılan kullanıcının uyarılarının devri (9. aşama); kapatılan kullanıcının açık çalışmalarının devri (çalışma adımları); kapatılan kullanıcının paylaşılan görünümleri kalır, kimse değiştiremez (devir yok); kullanılmayan geçici şifrenin süresi yok.
- **Sistem sağlığı (2.5):** genel bakım sayfası (veritabanı kapalıyken bütün ekranlar; docs/06 fonksiyon 94); Admin'e anlık hata bildirimi; kurulum paketinin `VIEW SERVER STATE` vermesi gerekirse veritabanının ayrı diski (0.6 temiz makine testinde bakılır).
- **Denetim izi (2.6):** özet zinciri ile kurcalama tespiti (hash, Faz 2).
- **Kullanıcı e-postası:** kullanıcıya e-posta adresi alanı; geçici şifre kurum içi e-posta sunucusuyla (SMTP, internet gerekmez) gönderilir. "Kapalı ağ, e-posta yok" ifadesi (fonksiyon 88) bu ihtimale göre düzeltilir.
- **Roller:** Admin'in bir paylaşılan görünümü ya da kural setini herkes veya bir rol için varsayılan yapması (K-89 notu); çalışma devralma.
- **9.2 Uyarılar:** rolü bozuk oturum kapatılınca Admin'e uyarı düşmesi (fonksiyon 90; 2.2'de yalnız denetim izine "Geçersiz rol" yazılıyor).
- **Operasyon öncül ve ardılı:** Faz 1'de rota doğrusaldır (`OperationNo` sırası); paralel rota ihtiyacı çıkarsa eklenir.
- **Sentetik veri:** kilogram ve metre birimli malzemelere kesirli miktar (güvenlik stoğu, lot) verilmesi (docs/11 açık iş).
- **Performans:** paralel plan ipucunun (`app/api/lists/query.py`, `PARALLEL_HINT`) bir ayara bağlanması; çok kullanıcılı sunucuda işlemci kapışması. İpucu iki sorguda: gruplama sorgusu (`groups_query`, grup ağacı ve ara toplamlar; K-90) ve Excel'e aktarım sorgusu (`export_query`, bütün satırlar tek sorguda; K-91).

## Açık konular

- **A-43 · Maliyet verisi.** Alternatif versiyon, fason ve fazla mesai kararları ile raporlar (A-22) için birim üretim maliyeti, fason maliyeti, fazla mesai maliyeti, stok tutma maliyeti ve gecikme cezası gerekebilir. Aşama 10'dan önce karara bağlanır (docs/00).
- **A-42 · Rotada lot bazlı tüketim.** `Routing.IsLotBasedUsage` pratikte hazırlık süresidir; set-up Faz 1 dışı olduğu için alan sözleşmeye girer, motorda kullanımı sonraya kalır. Faz 1 motorunun dolu satırı nasıl ele alacağı Aşama 10'da netleşir (docs/00).
- **A-41 · Alternatif bileşen ve alternatif operasyon kullanımı.** Aynı `AlternativeGroup` koduna sahip ürün ağacı ve rota satırları birbirinin alternatifidir. Tüketim sırası, miktar eşdeğerliği, modeldeki karşılığı ve kritik malzeme etkisi Aşama 10'da karara bağlanır; `Material.IsPhantom` ile `BOM.IsPhantom` çelişirse ağaç satırındaki geçerlidir (docs/00).
- **A-40 · Alternatif versiyon seçimi.** Versiyon seçimi motorun kararıdır, aynı malzeme aynı dönemde birden fazla versiyonla üretilebilir. Modeldeki karşılığı, `Priority`'nin kullanımı, aday versiyonlar, MRP ve pegging etkisi Aşama 10'da karara bağlanır (docs/00).
- **A-39 · Özel takibin proje dışına genişlemesi.** `IsCustomTracked` proje, müşteri ya da siparişe ayrılmayı anlatır; bugünkü motor tasarımı yalnız projeye kurulu. Sahip alanı, netleştirme ve pegging sırası, takip kuralları, `Customer.IsCustomTracked`, `SalesOrderLine.IsCustomTracked`, `Stock.IsCustomTracked`, `WorkOrder.IsCustomTracked` ve `PurchaseOrderLine.IsCustomTracked` ile birlikte okunuş, `Stock`, `WorkOrder` ve `PurchaseOrderLine`'daki proje, müşteri ve sipariş sahipliğinin birlikte okunuşu ve kompakt yöntemin ölçeği Aşama 10'da karara bağlanır; Faz 1 motor davranışı değişmez (docs/00).
- **A-38 · SQL entegrasyonunda ham tablo + view akışı.** Müşteri ERP verisini olduğu gibi ham tablolara yazar, kurulumda yazılan view'lar sözleşmeye çevirir, Smartchain view'dan staging'e alır. "Bitti" sinyali, view ile kural sınırı, view bakımı ve uyum denetimi; yöntem varlık başına seçilir (view, Excel, API). 3.3'te karara bağlanır (docs/00).
- **A-37 · Değişiklik etkisi ve yeniden hesap yönetimi.** Bir girdi değişince hangi sonuçların yenileneceği: türetilmiş hesap ve göstergeler anında, plan motorla; bağımlılık haritası ve girdi damgası. 8.2'den önce karara bağlanır (docs/00).
- **A-34 · Aktarım filtresinin yöntemi.** Kapsam filtresi (pasif malzeme, kapalı sipariş, başka lokasyon gibi) nasıl tanımlanacak? Değişen kayıtlar K-40 ve A-23'e, hatalı satırların ayıklanması 26. adımdaki hata yönetimine bağlı.
