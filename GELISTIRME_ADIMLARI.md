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
- [x] 3.3 SQL view okuyucu → Staging (01), entegrasyon tanımı (91) · K-130, A-38 kapanır: ham tablo + view akışı, `ERP_LoadLog` sinyali, uyum denetimi, view sürümleri · tablo başına yöntem (Excel, SQL; API 11.5'te), Excel'den yükleme her zaman açık · ekran 02: "Yöntem" ve "Çekim" kolonları hücre içi (bileşen 6.x elle değer düzeltmede de kullanılır): yöntem yalnız System owner, çekim Admin ve üstü; Key user yalnız görür (End user ekranı görmez); denetim izine yazılır; çekim kapatılırken sebep zorunlu, sebep, kişi ve tarih ipucunda, açarken uyarı; yöntem SQL olup view tanımlı değilse tablo adının yanında uyarı · "Veri çek" (onay ve sonuç penceresi) · genel kurallar (K-131, K-132, docs/12): tablo içi düzenleme anında kaydedilmez, tablonun sağ üstünde Kaydet ve Vazgeç çıkar, değişiklikler toplu kaydedilir, kaydedilmemiş değişiklikle çıkışta uyarı (Veri yükleme, Entegrasyon ve sonraki bütün tablo içi düzenlemeler); düğme renkleri; pencere ve kartlarda anlatım bandı olmaz; durum çipleri · ekran 23: bağlantı, view, kolon uyumu, test, önizleme, view sürümleri · kanal "Veri çekme"
- [x] 3.4 Validasyon (04), Validasyon kuralları (ekran 27, fonksiyon 100) · K-133…K-139 · **staging'in güncel hâli** (K-133): `stg` satırına `IsCurrent`; Tam güncel hâlin yerine geçer, Ekle / güncelle üzerine işlenir, ön kontrolde düşen satır önceki güncel satırı silmez · **otomatik zincir** (K-134): her batch staging'e alınınca arka planda rules (4.1'e kadar boş) → tablo içi validasyon → tablolar arası validasyon; toplu çekimde tablolar arası kurallar bütün tablolar bitince, tek tabloda o tabloyu okuyan kurallar yenilenir; iş tipi "Validasyon", kanal "Veri işleme", paralellik performans ölçümüyle; Excel'den yükle penceresi iki adım (Dosya → Ön kontrol) · Veri yükleme tablosunda "Validasyon" çipi (Sırada → Kurallar çalışıyor → Valide ediliyor → Geçti / Uyarılı · n / Hatalı · n) ve sağdan çekmece: son parti, dört kart (Hatalı, Uyarılı, Bilgilendirme satırı, Hata oranı), kural bazında Bulgular ve kurala süzülen Kayıtlar, "Hatalı kayıtları indir" (Sınıf kolonuyla), "Yeniden valide et" · **hata eşiği** tablo başına, varsayılansız (K-135); load'a etkisi 5.2'de · **Validasyon kuralları** ekranı (K-136, K-139): yapısal kontroller listede görünmez, hazır kurallar kullanıcı dilinde; koşulu editörle ifade edilen hazır kural pencerede düzenlenir ("İlk hâline döndür"), ötekilerin sınıfı değişir ve kapanır, pastel sınıf çipi, kullanıcı kuralı tek tablo içinde (alan–değer, alan–alan, VE grupları arası VEYA), ortak koşul editörü, toplu kayıt; System owner ve Admin yazar, Key user görür · **hazır kurallar** (K-137, docs/06 fonksiyon 04): ortak kurallar ve tablo kuralları; "boşsa hata" kontrolleri (ör. `Resource.CapacityUnit`, K-117) kurallardan sonra; yeni birim kodu Bilgi (K-112); farklı `BaseQuantity` (K-115); rota kaynağı ve grubu (K-116); `IsNonStockable` stok kaydı (K-113) · **varsayılan değer kavramı kalkar** (K-138): docs/02 ve docs/03'te BOŞSA kolonu, veri alanlarının `server_default`'ları kalkar, veri sözlüğünde "Boşsa" · **demo bulguları** (K-139): iş paneli kartları ve çekim kartı, operatörler sembolle (=, ≠, >, <, ≥, ≤ …, Boş değil), koşul editörünün yeni düzeni, bant taraması; ikinci demo: üst şerit standardı (docs/12) · kirli sentetik veride her hazır kural için örnek · validation staging'e, data quality load edilmiş core veriye aittir (Aşama 6) · "satır sayısı dünden %30 az" uyarısı 5.5'te (tutarlılık sayılarıyla)

## Aşama 4 · Dönüştürme (Transform)

- [x] 4.1 Veri kuralları: uygulama ve ekran (04; 16, 18, 19) · K-140…K-145 · 4.1 ve 4.2 birleşti · **staging iki katman** (K-140): ham `stg.*` hiç değişmez, işlenmiş `prc.*` her çalıştırmada ham katmanın güncel hâlinden kurulur, kurallar sırayla onda çalışır; validasyon (3.4) ve load işlenmiş katmanı okur, `RowStatus` işlenmiş katmanda; kural izi `adm.DataRuleEffect` ("Kural 3 · ham değer: …") · **veri kuralı** (K-141): tek tablo, ana veri ve işlem verisi; ortak koşul editörü; sonuç Değer / Alan / Formül (alan ± × ÷ sabit ya da alan, tarih ± gün) / Boşalt; boş sonuçta hücre değişmez, bölen sıfırsa o satırda boş; "Yalnız boşsa" ya da "Her zaman"; anahtar alan hedef olamaz; sıra tablo başına, sonuncu kazanır; varsayılan kural yok, kural silinir; ERP–kural önceliği staging'de yok (elle değer 5.1); çalışamayan kural "Çalışmadı", öteki kurallar ve validasyon sürer · Lokasyon bayrakları (K-111) kurulumda veri kuralıyla · **tetik** (K-142): her parti zinciri başlatır; kural değişikliği kendiliğinden uygulanmaz, "Kurallar yeniden uygulansın mı?" ve "Kuralları yeniden uygula"; "Yeniden valide et" aynı zincir · önizleme (17) Faz 1 dışı, etki sayısı yok · **ekran 04** Validasyon kuralları deseninde (üst şerit, sıra sürükle-bırak ve Alt + ok, toplu kayıt, D13 penceresi ve Sonuç bölümü) · yetki: Admin ve üstü yazar, Key user görür, End user görmez · menü: Veri yükleme, Veri kuralları, Validasyon kuralları, Ana veri, Veri kalitesi · kirli sentetik veride kurallarla çözülen örnekler ve demo kuralları · **demo bulguları** (K-143): Veri yükleme çekim ve validasyon işleri bitince kendiliğinden yenilenir; koşul değeri serbest yazı, değer listesi öneri (staging ERP'nin dilinde); Location.Type ham ERP değeri (Lokasyon şablonu v3, geçiş 0044); çekmecede Kayıtlar · Bulgulu satırlar / Kuralla değişenler / Tüm satırlar, "Veriyi gör"; sürükle-bırak satırın tamamında · **ikinci demo** (K-144): sıra 1'den boşluksuz, Tablo ilk kolon, ekranlar iş bitince yenilenir, Kayıtlar kolon sırası seçeneğe göre, teknik kolonlar gizli ve "Değiştiren kural", lila hücre izi, ek alan etiketleri veri sözlüğünden, Veri çek penceresi · **üçüncü demo** (K-145): Veri çek başlığında "Yine de oku" toplu kutusu, Sıra kolonu dar ve sola hizalı, sıra yalnız sürükle-bırak, Durum her zaman dolu (Çalıştı / Çalışmadı / Pasif / Uygulanmadı); pasif satır (`IsActive` = Hayır) validasyona girmez; aktarım filtresi (4.3) kalktı
- [—] 4.3 Aktarım filtresi · kaldırıldı (K-145): kapsam veri kurallarıyla belirlenir (kural `IsActive` = Hayır yazar); A-34 kapandı
- [x] 4.4 Referans kontrolü ve kod→Id eşleme · K-146, K-147 · **ilişki haritası** docs/03 (kodda `app/integration/references.py`): her ilişki alanı için ebeveyn tablo ve anahtar, zorunlu / isteğe bağlı, pasif ebeveyn sınıfı; 5.2 load da bunu kullanır · zorunlu ilişki yoksa Hata (satır load edilmez), isteğe bağlı bağlantı doluysa ve yoksa Uyarı (satır load edilir, bağlantı boş); istisna "Zorunlu (doluysa)": rota ve iş emri operasyonunda kaynak ve kaynak grubu sözleşmede isteğe bağlı, doluysa ve yoksa Hata · pasif ebeveyn: talep, açık arz ve plan yapısında Uyarı, Stok ve Üretim versiyonunda Bilgi; satır load edilmez · bütünlük kuralları ebeveynde · ortak `ALL.REF_LOCATION`, `ALL.UOM_CONVERSION` · kirli veride her yeni kural için örnek, H2 `SO.REF_MATERIAL` ve `BOM.REF_COMPONENT` · birim alanları referans kontrolüne girmez (K-112) · `UomConversion` lokasyondan bağımsızdır: dönüşüm satırı aynı `MaterialCode`'a sahip her lokasyonun malzemesine bağlanır (K-112, docs/03) · referans kontrolü (çocuk → ebeveyn: BOM bileşeni, rotadaki kaynak yok) error, satır load edilmez · bütünlük kontrolleri (ebeveyn → çocuk) warning: üretilen malzemede production version, BOM ya da rota yok; satın alınan malzemede tedarikçi yok gibi. Yalnız staging'in güncel hâliyle çalışır, core'a bakmaz (K-133); bütünlük kontrolleri de staging'e bakar; rules'tan sonra, 3.4'ün tablolar arası validasyonunda çalışır (üretilir / satın alınır bilgisi `DefaultSupplyType`'tan, K-121). Otomatik zincirin sonuna eklenir; load sonrası data quality'de issue olarak kalır, eksik gelince kendiliğinden kapanır. Kontrol listesi bu adımda netleşir

## Aşama 5 · Yükleme (Load)

- [—] 5.1 Değer önceliği · kaldırıldı (K-148): değerin kaynağını yazmak (ERP değeri, hangi kural; `DataRuleEffect`) 5.2'ye, elle değerin aktarımda korunması ve veri sözlüğündeki düzenleme 6.2'ye
- [x] 5.2 Tam aktarım ve veri versiyonu (05, 07) · K-149, K-153, K-154 · demo: arayüzde "gelen veri" / "mevcut veri", Yeni / Güncellenen / Silinen / Aktarılmayan, not metinleri, Veri yükleme tablosunda Toplam satır, Hatalı, Uyarılı, Bilgi (5.5'ten öne alındı) · `app/transfer/`: prc → core kolon eşlemesi (ad kuralı ve ilişki haritası), tablo başına küme SQL (çözümle → eşleştir → kapat → ekle) · kimlik iş anahtarıyla, değişen kayıt aynı Id ile yeni satır · Kaynak'ın Smartchain alanları önceki versiyondan · Lokasyon versiyonsuz · `DataVersion.LocationId` boş olabilir, `DataVersionEntity` sayıları (geçiş 0046) · `POST /api/transfers`, onay ve sonuç penceresi, "Tam aktar" düğmesi · anahtarın parçası olan isteğe bağlı bağlantı Zorunlu (doluysa) · validasyonda görünmeyen aktarılmayanlar raporda tablo notunda · geliştirme veritabanı `python -m app.data.synthetic reset` ile sentetik hâle döner · iş tipi "Yükleme" bu adımda "Aktarım" olur, "Yükleme işi iptal edilemez" metni de (K-152) · ana veri ve işlem verisinin hepsi · staging'in güncel hâlinde olmayan kayıt core'da kapatılır (silinmiş sayılır); `IsActive` = Hayır kayıt da core'da kapatılır · Hata bulunan satır aktarılmaz, core'daki önceki hâli açık kalır · **değerin kaynağı** (K-148): ERP değeri `FieldValueSource.ErpValue`'ya, kural değeri ve hangi kural `adm.DataRuleEffect`'ten (staging'de ERP–kural önceliği yok, K-140, K-141) · aktarım `IsActive` = Hayır satırlarını almaz (K-145); `IsActive`'i olmayan tablolarda kapsam ebeveynden gelir (4.4 referans kontrolü), şimdilik ek alan yok · **kod→Id ilişki haritasıyla** (docs/03, `app/integration/references.py`, K-146): ebeveyn tablolar önce; zorunlu ve "Zorunlu (doluysa)" ilişkisi çevrilemeyen satır aktarılmaz (rota ve iş emri operasyonunda kaynak boşaltılarak aktarılmaz), isteğe bağlı bağlantı boş yazılır; pasif ebeveyne bakan satır aktarılmaz (pasif sınıfı olmayan isteğe bağlı bağlantıda bağlantı boş) · aktarım staging'in işlenmiş katmanını okur (`prc.*`, K-140; ham katmanın güncel hâli, K-133); Hata bulunan satır (`RowStatus` Hatalı) aktarılmaz; hata eşiği aşılan tablo aktarılmaz, önceki versiyon kalır (K-135) · aktarımın özet denetim kaydı (K-108) · `core.UnitOfMeasure` diğer tablolarda geçen birim kodlarından otomatik oluşur (`Material.BaseUom`, `Resource.CapacityUnit`, `UomConversion.FromUom` ve `ToUom`, `BOM.ComponentUom`, `SalesOrderLine.Uom`, `Forecast.Uom`, `Stock.Uom`, `WorkOrder.Uom`, `WorkOrderComponent.Uom`, `PurchaseOrderLine.Uom`), `Name` boşsa `FromUomName` ya da `ToUomName`'den dolar, `Decimals` için varsayılan yazılmaz (K-112) · birim dönüşümü kullanılırken ters yön ve zincir kuralı (docs/03, K-112) · çekim anahtarının aktarıma etkisi; aynı tabloda Excel ve SQL partisi varsa en yeni parti (K-130)
- [x] 5.3 Kısmi aktarım (06) · K-150 · yalnız işlem verisi, ana veri aktarılmaz · gruplar: Talep (Satış siparişi, Tahmin, Proje, Proje grubu; Proje ve Proje grubu katalogda Ana veri, istisna), Stok (Stok, Ödünç ve geri ödeme), Üretim (İş emri, İş emri bileşeni, İş emri operasyonu, Üretim gerçekleşmesi), Satın alma (Satın alma siparişi), İzin (Çalışan izni) · seçilmeyen gruplar core'da olduğu gibi kalır; seçilen grupta kapatma tam aktarımdaki gibi · bağlı olduğu ana veri core'da olmayan satır aktarılmaz, raporda "ana verisi aktarılmadı" sayısı, bir sonraki tam aktarımda girer · bağımlılık önerisi yok · elle ya da zamanlanmış akış adımı (gruplar akış tanımında, 5.6) · K-155 · uygulama: tek motor iki kip (`run_transfer(groups=…)`), gruplar `app/transfer/groups.py` (docs ile test karşılaştırır); seçilmeyen tablolar yazılmamış sayılır, ona bağlı eksik satır bekler (notu "bekliyor (kısmi aktarım)", mevcut hâli kalır); gelen veride pasif, mevcut veride aktif ana veri: satır aktarılır · `GET /api/transfers/partial/plan`, `POST /api/transfers/partial` (06; ön koşul yalnız seçilen tablolar) · Veri yükleme'de "Kısmi aktar" (hiçbir grup seçili açılır), sonuç "Veri aktarım raporu"
- [x] 5.4 Veri aktarım raporu, veri aktarım geçmişi, ham veri temizliği (08, 09) · K-151 · rapor tablo başına yalnız özet sayılar: yeni, değişen, kapatılan, aktarılmayan (satır ve neden listesi yok; ayrıntı validasyon çekmecesinde) · iki tek satır not: eşik aşıldığı için tablo aktarılmadı (oran ve eşikle), kısmi aktarımda ana verisi aktarılmadığı için bekleyen satır sayısı · her tablonun son aktarım zamanı (tam / kısmi) ve staging'de aktarılmamış yeni veri var mı · geçmişteki özet kayıtlar temizlikte silinmez, yalnız ayrıntı verisi · yüklenen dosyalar (`SMARTCHAIN_IMPORT_DIR`) ve terk edilen "Ön kontrol" partileri bir hafta sonra silinir (K-129) · ham veri temizliği staging'in güncel satırını silmez (K-133) · K-156 · uygulama: Veri yükleme'de "Veri aktarım geçmişi" çekmecesi (ortak liste `transfer-history`, aktarım işleri), satıra tıklayınca Veri aktarım raporu (`DataVersionEntity`'den, `DataVersion.JobId`; Excel) · ham veri temizliği: `app/cleanup/raw.py`, iş tipi "Temizlik", `RawDataRetentionDays` (varsayılan yok, Sistem ayarları), yalnız System owner başlatır, Admin ve Key user sonucu görür · geçiş 0047 · demo (K-157): üst şeritte "Veri çek" ve "Veri aktarımı ▾" (Tam veri aktarımı, Kısmi veri aktarımı, Veri aktarım geçmişi); temizlik metinleri kullanıcı diliyle; Excel yükleme ayarlarının kaydı düzeldi
- [x] 5.5 Veri yükleme ekranı (02) · K-158 · "Son aktarım" kolonu ve "Yeni veri" çipi (K-151) · üst şeritte "Veri çek", "Veri yükle" (birden çok Excel dosyası, tablo şablondaki teknik addan, tek listede ön kontrol, mod dosya başına) ve "Veri aktarma ▾" · geçmişte "Veri versiyonu" kolonu "Veri" · kapananlar: yeni/değişen/silinen ön izlemesi ve "satır sayısı %n az" uyarısı (5.5b'ye), "Son Excel yüklemesini gör", sağ paneller ve durum satırı, "Seçilenleri yükle (kısmi)", iş özeti için kod (K-107 örneği güncellendi) · demo: bulgu yok
- [~] 5.5b Dünden bugüne ekranı (ekran 28, fonksiyon 101 önerisi) · K-159 · ham veride tablo başına dünkü ve bugünkü satır, değişim %, yeni gelen, gelmeyen, güncellenen; seçilen tablonun Yeni gelenler / Gelmeyenler / Güncellenenler sekmeleri (ortak tablo) · End user da görür · ana sayfa özet sayıları aynı API'den (bağlantı ana sayfa adımında) · temizliğin "dün" verisini koruma kuralı · kod 5.5'ten sonra ayrı planlanır · uygulama K-160: `app/compare/raw.py`, `ImportBatch.AppliedAt` ve `stg.*.SupersededAt` (geçiş 0048, eski veri doldurulur), `RawCompare` ve `RawCompareRow`, temizlikte "dün" koruması · demo eki K-161: ana–detay düzeni (`ui/MasterDetail`, docs/12), kapatma, ayraç (çift tıklayınca ilk oran), büyütme, ilk dolu sekme; Kayıt kolonu varsayılan gizli
- [ ] 5.6 Gece ETL akışı: zamanlanmış işler (92), Entegrasyon ekranı (23) · kısmi aktarım zamanlanmış akış adımı olabilir, gün ortası ikinci bir akış kurulabilir (ör. öğlen Talep ve Stok), gruplar akış tanımında seçilir (K-150; akış yapısı kurulumda, "Sonraya bırakılanlar") · Sistem sağlığında zamanlayıcı satırı (K-106) · Entegrasyon ekranının kalanı: Zamanlanmış işler kartı; 3.3'te bağlantı, tablolar, test ve önizleme açıldı (K-130) · gece çekimi "Veri çekme" kanalını kullanır; "Yeni veri yok" atlanır, yenileme bitmemişse bekleme ve zaman aşımı burada

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
- [ ] 6.2 Değerin kaynağı (11), elle değer girme ve kaldırma (12, 13) · U-15, U-16: yapıştırma, toplu düzenleme, doğrulama, kaydetme · **elle değerin load'da korunması** (5.1'den, K-148): elle değer girme ekranıyla birlikte yapılır ve test edilir; hangi alanların elle değiştirilebileceği burada konuşulur · veri sözlüğünde Sınıf, Değer önceliği, Manuel, Senaryo ve Zorunlu düzenlemesi açılır (pencerede pasif öğeler aktifleşir; Boşsa docs'tan gelir, salt okunur); zorunlu ve `DataRule` kilidi, etki sayısı ve "Şimdi uygula" (K-104)
- [ ] 6.3 Değişiklik geçmişi (14) · denetim izinden okur; denetim izinde "Kayda git" ve bağlı kayıtlar (K-108)
- [ ] 6.4 Excel ile toplu düzeltme (15)
- [ ] 6.5 Veri kalitesi ekranı (05) · kontrol, düzeltme aksiyonu (20, 21) · aktif ve kritik olup kapasitesi tanımsız kaynak uyarı (K-117) · tedarik satırında `FixedLeadTimeDays` ve `VariableLeadTimeDays` ikisi de boşsa uyarı (K-118)

## Aşama 7 · Parametreler

- [ ] 7.1 Parametre seti (22) · tedarikçi seçim kuralı seçilir: en kısa tedarik süresi ya da `Priority` (K-118) · `SafetyStock` ile `StockCoverageDays` ikisi de doluysa hangisinin geçerli olacağı (büyük olan, yalnız miktar, yalnız gün…) motor parametresi olarak burada seçilir (K-113)
- [ ] 7.2 Zaman yapısı (23)
- [ ] 7.3 Kapasite parametreleri (24) · `ShiftPlan.ResourceGroupId` boşsa anlamı (BOŞSA, K-138) vardiya ekranında kararlaştırılır; tablo ekrandan girilir, staging'de yok (K-117) · verim ve hedef doluluk burada tanımlanır, entegre edilmez; vardiyadaki kişi sayısının işçi kaynaklarının kapasitesine nasıl dönüşeceği burada netleşir (K-117)
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
- [ ] 11.5 API adaptörü (Faz 2) · varlık başına yöntem seçimine (A-38) üçüncü seçenek olarak bağlanır · Faz 1'de API hiç görünmez: yöntem listesi ve ekran 23'teki API kartı burada eklenir (K-130)
- [ ] 11.6 Doğruluk raporları (A-22)

---

## Bekleyen kontroller

Adımı kapanmış ama elle denenmesi sonraya bırakılmış işler.

- [x] 1.5 · Arka plan aktarımı: eşiği geçici düşür (`INSERT INTO adm.SystemSetting (SettingKey, Value) VALUES ('ExportSyncMaxRows', '50')`), /tablo'da "Hazırla", iş göstergesi ve "İndir" bildirimi, iş listesinden indirme; sonra ayarı sil (`DELETE FROM adm.SystemSetting WHERE SettingKey = 'ExportSyncMaxRows'`).
- [x] 1.5 · Dışa aktarım izi: `SELECT TOP 5 * FROM adm.AuditLog ORDER BY 1 DESC` ile aktarımların "Dışa aktarım" kaydı olarak yazıldığını gör.
- [ ] 0.6 · Uygulama hesabı yetkisi (K-109): Windows ve SQL kimliğiyle kurulumda `verify.ps1`'in duman testi `adm.AuditLog` için güncelleme ve silme yetkisi olmadığını doğrular; servisler `db_owner` olmadan çalışır.
- [ ] 0.6 · Temiz makine (sanal makine) kurulum testi. Not (2.3): install.ps1 sonunda tek System owner hesabı geçici şifreyle açılır; sanal makine turunda bu da denenir. İlk hesabın geçici şifresi install logunda yer almamalı (K-102). Temiz makinede Excel süresi iki kez ölçülür: antivirüs gerçek zamanlı tarama açıkken ve ürün klasörleri hariç tutulmuşken (`docs/10-kurulum.md`).
- [ ] 0.6 · Excel yükleme eşik ölçümü (`ImportSyncMaxMb`, K-129): temiz makinede ve müşteri sunucusunda ilk kurulumda, ortanca.
- [ ] 0.6 · Entegrasyon veritabanı (K-130): temiz makinede `setup_db.py --integration-database`, servis hesaplarının yalnız okuma yetkisi; kurulum sonunda view'ların uyum denetimi (`verify.ps1`).
- [ ] 1.6 · Excel süresi bu laptopta 0,8–3,2 sn arası dalgalanıyor; sorgular hedefte. Güçlü aday: dosya yazımını tarayan antivirüs (ESET ekrn ~%31). Kapanış 0.6'da.
  - Ölçümler (10.000 satır, ortanca ms; düz / gruplu / 10 kural; hedef 3000): 30.10 10.14: 753 / 869 / 935 · 30.10 11.25: 2588 / 2859 / 3112 · 2.2 kapanışı: 2410 / 2600 / 2910 · 03.11 1. koşu: 2333 / 950 / 953 · 03.11 2. koşu: 786 / 940 / 983 · 03.11 yeniden başlatma sonrası: 1394 / 3163 / 2806.
- [ ] 4.4 · Sıraya bağlı üç test: tam koşuda geçer, alt küme koşusunda düşer (ör. `python -m pytest tests/test_import_dirty.py` tek başına; 4.4 değişiklikleri geri alınmışken de aynı). (1) `tests/test_import_dirty.py::test_only_the_duplicate_is_an_error`: Malzeme ön kontrol notu 2 (beklenen 1); fazladan not "Etiketsiz ek alan yok sayıldı: AdditionalText1." Test veritabanında Malzeme `AdditionalText1` etiketi (`FieldDefinition`, K-104) yokken düşüyor; etiketi tam koşuda daha önceki bir test yazıyor. (2) `tests/test_pull_api.py::test_view_must_exist` ve (3) `test_connection_test_reports_steps_and_only_reads`: `View_Material` uyum durumu "Uyarılı" (beklenen "Uyumlu"); büyük olasılıkla aynı neden (etiketsiz ek alan kolonu), doğrulanmadı. Çözüm: bu testler etiketi kendi kurar ya da beklenen etiketsiz hâle göre yazılır.

## Sonraya bırakılanlar

Konuşulup bilerek ertelenen işler. Sırası gelen adımın planında ele alınır.

- **Akış yapısı kurulumda ayarlanır (5.6'da fonksiyon 92 madde madde gözden geçirilir):** gece akışının yapısını (hangi adımlar, sıra, bağımlılık, başlangıç saati, günler, bitiş sınırı, adım hata verirse devam / dur) kurulumda System owner ayarlar; hangi senaryoların çalışacağı müşterinin kararıdır (7.6, fonksiyon 27, 28). Docs'taki "zincir sırası değiştirilemez" ve sabit değerler (22:00 çekim, 06:00 bitiş, 2 paralel senaryo, hafta sonu açık, Pazar 03:00 temizlik, 22:00–06:00 arası yasaklar) varsayılan olmama prensibine göre düzeltilir. Bakılacaklar: adımların iş türü olarak tanımlanması, zorunlu ön koşullar (ör. doğrulama çekimden sonra), birden fazla akış (ör. gün ortası kısmi yükleme), yetki (K-100).
- **Çoklu dosya ile Excel yükleme (5.5'te ele alınır):** pencerede birden fazla dosya seçilir; her dosyanın tablosu şablondaki teknik addan anlaşılır, hepsi tek listede ön kontrol edilir. Her dosya yine tek tabloya karşılık gelir; docs/06 fonksiyon 03'teki "tek dosya tek varlık" buna göre düzeltilir.
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

- **A-45 · Açık çalışma yeni veri versiyonunda ne olur?** (a) Açıldığı versiyonda kalır, "Yeni veri var" bilgisi, planlamacı hazır olunca yeniden hesaplar (docs'taki bugünkü hâl); (b) kendiliğinden yeni versiyona geçer, elle değişiklikler yeni verinin üzerine yeniden uygulanır; (c) ana veri sabit kalır, işlem verisi her kısmi load'da güncellenir; (d) çalışma başına planlamacı seçer. Aşama 8'den önce karar verilir (docs/00).
- **A-43 · Maliyet verisi.** Alternatif versiyon, fason ve fazla mesai kararları ile raporlar (A-22) için birim üretim maliyeti, fason maliyeti, fazla mesai maliyeti, stok tutma maliyeti ve gecikme cezası gerekebilir. Aşama 10'dan önce karara bağlanır (docs/00).
- **A-42 · Rotada lot bazlı tüketim.** `Routing.IsLotBasedUsage` pratikte hazırlık süresidir; set-up Faz 1 dışı olduğu için alan sözleşmeye girer, motorda kullanımı sonraya kalır. Faz 1 motorunun dolu satırı nasıl ele alacağı Aşama 10'da netleşir (docs/00).
- **A-41 · Alternatif bileşen ve alternatif operasyon kullanımı.** Aynı `AlternativeGroup` koduna sahip ürün ağacı ve rota satırları birbirinin alternatifidir. Tüketim sırası, miktar eşdeğerliği, modeldeki karşılığı ve kritik malzeme etkisi Aşama 10'da karara bağlanır; `Material.IsPhantom` ile `BOM.IsPhantom` çelişirse ağaç satırındaki geçerlidir (docs/00).
- **A-40 · Alternatif versiyon seçimi.** Versiyon seçimi motorun kararıdır, aynı malzeme aynı dönemde birden fazla versiyonla üretilebilir. Modeldeki karşılığı, `Priority`'nin kullanımı, aday versiyonlar, MRP ve pegging etkisi Aşama 10'da karara bağlanır (docs/00).
- **A-39 · Özel takibin proje dışına genişlemesi.** `IsCustomTracked` proje, müşteri ya da siparişe ayrılmayı anlatır; bugünkü motor tasarımı yalnız projeye kurulu. Sahip alanı, netleştirme ve pegging sırası, takip kuralları, `Customer.IsCustomTracked`, `SalesOrderLine.IsCustomTracked`, `Stock.IsCustomTracked`, `WorkOrder.IsCustomTracked` ve `PurchaseOrderLine.IsCustomTracked` ile birlikte okunuş, `Stock`, `WorkOrder` ve `PurchaseOrderLine`'daki proje, müşteri ve sipariş sahipliğinin birlikte okunuşu ve kompakt yöntemin ölçeği Aşama 10'da karara bağlanır; Faz 1 motor davranışı değişmez (docs/00).
- **A-38 · SQL entegrasyonunda ham tablo + view akışı.** Kapandı (3.3, K-130).
- **A-37 · Değişiklik etkisi ve yeniden hesap yönetimi.** Bir girdi değişince hangi sonuçların yenileneceği: türetilmiş hesap ve göstergeler anında, plan motorla; bağımlılık haritası ve girdi damgası. 8.2'den önce karara bağlanır (docs/00).
- **A-34 · Kapandı (K-145):** kapsam veri kurallarıyla belirlenir (kural `IsActive` = Hayır yazar). Eski soru: Kapsam filtresi (pasif malzeme, kapalı sipariş, başka lokasyon gibi) nasıl tanımlanacak? Değişen kayıtlar K-40 ve A-23'e, hatalı satırların ayıklanması 26. adımdaki hata yönetimine bağlı.
