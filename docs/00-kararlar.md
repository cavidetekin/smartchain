# Kararlar ve açık konular

Kaynak: MDD 26.10.2026 adım kartları. Numaralar proje genelinde sıralıdır (K-n karar, A-n açık konu). Yeni karar ya da açık konu önce buraya yazılır.

## Kararlar

| No | Karar | Adım |
|---|---|---|
| K-1 | Kaynak tipleri: makine, ekipman, kalıp, işçi, fırın ve dış kaynak (fason). | 2 |
| K-2 | Kaynaklar primary ve secondary resource olarak kategorize edilir. | 2 |
| K-3 | Ekipman kısıt olarak kapsam dışında tutulur. | 2 |
| K-4 | Makine bazında detay verim kapsam dışıdır; ürün detaylı çizelgeleme sunmaz. | 2 |
| K-5 | Yetenek ve kalifikasyon makine kısıtı değil, rotadan gelen bilgidir. | 2 |
| K-6 | Malzeme üç eksende: yapısal seviye, işlem bayrakları, sahiplik. | 3 |
| K-7 | Sarf malzeme kapsam dışıdır. | 3 |
| K-8 | Stok iki eksende: kullanılabilirlik ve ayrılmışlık. | 3 |
| K-9 | Kalitedeki stok beklenen serbest kalma tarihiyle plana girer. | 3 |
| K-10 | Min., maks., kat ve parti politikası ortak sipariş düzelticilerdir. | 3 |
| K-11 | Satın alma optimizasyonu yapılmaz; ilgili kısıtlar kapsam dışı. | 3 |
| K-12 | Üretim süresi malzeme değil, rota verisidir. | 3 |
| K-13 | Revizyon uyumu, kullanım olasılığı, yan/eş ürün kapsam dışı. | 3 |
| K-14 | Alternatif bileşen ağaca bağlı ya da havuz; tüketim önceliği kriterdir. | 3 |
| K-15 | Raf ömrü standart ve kalan; minimum kalan ömür ve FEFO zorunlu. | 3 |
| K-16 | Projeye bağlama sıkı (hard) ya da gevşek (soft) olabilir. | 4 |
| K-17 | Tam izolasyon, genel stoktan besleme ve grup içi paylaşım rutin; ödünç ve geri ödeme istisna. | 4 |
| K-18 | Projeler arası aktarım müşterinin ERP'sinde yapılır; araç sonucunu okur. | 4 |
| K-19 | Planlama hedefi sipariş satırının teslim tarihidir; proje ana tarihi, kilometre taşı ve ceza hedef değildir. | 4 |
| K-20 | Mühendislik değişikliği, prototip/seri, ilk ürün onayı ve proje maliyeti kapsam dışı. | 4 |
| K-21 | Proje bazında fazla stok ve onu tetikleyen kararın görünürlüğü zorunludur. | 4 |
| K-22 | Problemler çözüm eksenleri boyunca ele alınır; her problem her ekseni doldurmak zorunda değil, bir eksende birden fazla alternatif olabilir. | 17 |
| K-23 | Set-up, kalıp, fırın ve faz bazlı işçi kapasite tüketimi Faz 1 dışındadır. | 17 |
| K-24 | ERP'den gelmeyen ya da hatalı veri veri kurallarıyla tamamlanır; değer önceliği (ERP ezer ya da kural ezer; elle ezer ya da ezmez) alan bazında seçilir. | 17 |
| K-25 | Kaynak kapasitesi, kaynağın kendi biriminde günlük kapasite olarak alınır; rotadaki tüketim aynı birimde kabul edilir. | 17 |
| K-26 | İki optimizasyon modeli kurulur: LP ve MILP. Her zaman MILP çalışmaz; model tipi parametriktir. | 18 |
| K-27 | Satın alma kararları hiçbir zaman tamsayı değildir; gerekirse sonradan yuvarlanır. | 18 |
| K-28 | Proje bazlı planlama, envanteri proje sayısıyla çoğaltmadan kompakt bir yöntemle çözülür. | 18 |
| K-29 | MRP patlatmadaki öncelikler ve kısıtlar parametrik yönetilir. | 18 |
| K-30 | Ürün paleti indigo + kurşun; durum renkleri hardal (risk) ve kiremit (aşırı yük). Yazı tipleri Instrument Sans ve JetBrains Mono (sayı fontu K-86 ile Inter oldu). | 23 |
| K-31 | U-1…U-23 arayüz prensipleri tüm ekran ve raporlar için bağlayıcıdır; yeni ekran bu listeye göre gözden geçirilir. | 23 |
| K-32 | Faz 1 hedefi müşterinin sunucusu, kapalı ağ; işletme bizde, uzaktan erişim yok. Tek paket bulutu engellemez. | 19 |
| K-33 | Windows Server, Python; ürüne ayrılmış, en güncel sürümde MS SQL Server. | 19 |
| K-34 | Entegrasyon ERP'den bağımsız: API, Excel, SQL arayüz tabloları; tek veri sözleşmesi. | 19 |
| K-35 | Modelleme katmanı çözücüden bağımsız. LLM Faz 1'de kapalı. | 19 |
| K-36 | Kullanıcı seviyeleri: sistem sahibi, admin, key user, end user. | 19 |
| K-37 | Onaylı plan sadece çalışmadan yayınlanır. Faz 1'de tek lokasyon. | 19 |
| K-38 | Tablo ve alan adları İngilizce, açıklamalar Türkçe; ERP'den bağımsız tek veri sözleşmesi. | 21 |
| K-39 | Veri sınıfları: ana veri, işlem verisi, parametre; her alanın sınıfı ve değer önceliği veri sözlüğünde. | 21 |
| K-40 | Veri versiyonları kayıt bazında (VersionFrom, VersionTo); kısmi yüklemede veri kopyalanmaz. | 21 |
| K-41 | Çalışmadaki geçici değişiklikler tek tabloda; plan çıktıları plan hesabına bağlı. | 21 |
| K-42 | Manuel planlama dört görünümle yapılır: ürün bazlı, kaynak bazlı, sipariş bazlı ve bucket bazlı Gantt (sürükle-bırak). Dördü aynı planın farklı yüzleridir. | 24 |
| K-43 | Planlama ekranları bir çalışmanın içinde açılır; end user onaylı planı salt okunur görür. | 24 |
| K-44 | Her rapor bağlamını (onaylı plan / senaryo / çalışma, veri versiyonu, hesap zamanı) üstte taşır; göstergeler tek sözlükten (PlanMetric) hesaplanır. | 25 |
| K-45 | Pano ve rapor ayrılır: pano sürekli açık ve az sayıda büyük sayı; rapor filtreli tablo ve Excel. End user varsayılan onaylı planı görür. | 25 |
| K-46 | Tek veri sözleşmesi: şablon, SC_* arayüz tabloları ve API şeması aynı veri sözlüğünden üretilir; her varlık tek yöntemle beslenir. | 26 |
| K-47 | Faz 1 yalnız okuma; plan çıktıları Excel listesi olarak ERP'ye elle girilir. Faz 2'de API ile geri yazma (yalnız yeni belge). | 26 |
| K-48 | ERP ana veri ve işlem verisinde master; Smartchain planlama alanları (verim, kapasite birimi, kritik…) Smartchain'de, ERP değeri FieldValueSource'ta saklanır. | 26 |
| K-49 | SQL arayüz tablolarını müşteri ETL'i doldurur; Smartchain ERP veritabanına doğrudan girmez. | 26 |
| K-50 | Yükleyici (MSI) ile tek komut kurulum ve güncelleme; güncelleme öncesi otomatik yedek, sağlık kontrolü geçmezse otomatik geri alma. | 27 |
| K-51 | Günlük tam + saatlik işlem günlüğü yedeği, 30 gün; 3 ayda bir geri yükleme testi; hedef RPO 1 saat, RTO yarım gün. | 27 |
| K-52 | Geliştirme dikey dilimlerle yapılır; ilk dilim Excel'den plana ve Excel'e uçtan uca çalışır. Bitiş kriteri sentetik veriyle ölçülür. | 28 |
| K-53 | Faz 1 kapsamı sabit: set-up, kalıp, fırın, faz bazlı işçi tüketimi, raf ömrü (yalnız uyarı), LLM, çoklu lokasyon, geri yazma, AD / SSO ve bulut Faz 3. | 28 |
| K-54 | Tek kaynak kuralı: değişiklik önce docs'ta, sonra kodda; deste dilim sonlarında docs'tan güncellenir. | 29 |
| K-55 | Bitti tanımı: kod + test + docs güncel + sentetik veriyle çalışır + kurulum paketinde + demo yapıldı. | 29 |
| K-56 | Hikâye kalıbı: '<Rol> olarak <hedef> istiyorum, böylece <fayda>'; kabul kriterleri Verilen / Olduğunda / O zaman; öncelik MoSCoW (Must = Faz 1 çekirdek). | 20 |
| K-57 | Hikâye 'ne ve neden', prensip slaytı 'nasıl': her hikâye bir ekran, fonksiyon ya da rapor numarasına bağlanır; kabul kriteri otomatik teste dönüşür. | 20 |
| K-58 | İki katman: entegrasyon tabloları (stg.*) kodla, ana tablolar Id ile; ERP verisi ana tablolara aktarımla geçer. | 21 |
| K-59 | Ek alanlar: ana veride 10 (7 metin + 3 sayı), yapı ve işlem verisinde 5 (3 metin + 2 sayı); etiketi FieldDefinition'da. | 21 |
| K-60 | Teklif ayrı tablo değil: SalesOrderLine.Type = Kesin \| Teklif; kazanma olasılığı tutulmaz. | 21 |
| K-61 | Rota satırı operasyon–kaynak: RouteCode + OpNo + SeqNo + ResourceCode; sıra önce OpNo, sonra SeqNo. | 21 |
| K-62 | Veritabanı beş şemadır: stg (entegrasyon), core (ana veri ve işlem verisi), param (parametre), planning (plan çıktıları), adm (veri yönetimi ve sistem). Entegrasyon ve ana tablo aynı adı taşır: stg.Material → core.Material. | Geliştirme 0.2 |
| K-63 | Versiyonlu tablolarda birincil anahtar Id + VersionFrom; Id kaydın bütün versiyonlarında sabittir. Versiyonlu tabloya fiziksel FK konmaz, bütünlüğü aktarım (kod→Id) sağlar; tekillik yalnız güncel kayıtta (VersionTo boş) aranır. | Geliştirme 0.2 |
| K-64 | Veritabanı şeması docs'tan üretilir (db/generate.py); geçişler Alembic ile, her geçişin geri adımı vardır. Tablo ve alan açıklamaları veritabanına da yazılır. | Geliştirme 0.2 |
| K-65 | Takvim (Calendar, CalendarDay), vardiya (Shift, ShiftPlan), duruş (ResourceDowntime) ve kapasite profili (ResourceCapacityProfile) Smartchain'de ekrandan tek tek girilir; entegrasyondan ve Excel'den gelmez, stg tabloları yoktur. Yetkinlik grubu, işçi, işçi–yetkinlik ve izin (CompetenceGroup, Worker, WorkerCompetence, WorkerAbsence) ERP'den gelir. | Geliştirme 0.2 |
| K-66 | Tedarikçi kapasitesi ve kapalı dönemleri SupplierLimit parametre tablosunda tutulur (problem 39): malzeme bazında dönem üst limiti; malzeme boşsa tedarikçi o dönemde kapalıdır (limit 0). Tedarikçide takvim alanı yoktur; Smartchain'de ekrandan girilir. | Geliştirme 0.2 |
| K-67 | İş kuyruğu adm.Job tablosudur. Durum değerleri veri modelinde yazıldığı gibi saklanır (Sırada, Çalışıyor, Bitti, Hata, İptal); 'takıldı' ayrı durum değildir, kalp atışından hesaplanır. Takılan iş JobMaxAttempts'e kadar yeniden sıraya döner, sonra Hata olur (fonksiyon 47, 93). | Geliştirme 0.4 |
| K-68 | İş alma tek SQL işleminde uygulama kilidiyle (sp_getapplock) sıraya konur; kanalın çalışan iş sayısı sınırın altındaysa en yüksek öncelikli, sonra en eski Sırada iş Çalışıyor olur. Sınır kanal bazındadır (etkileşim 3, gece ayrı) ve SystemSetting'den okunur, satır yoksa varsayılan geçerlidir (fonksiyon 47). | Geliştirme 0.4 |
| K-69 | İşi motor ayrı süreçte çalıştırır; API Job tablosunu UpdatedAt ile kısa aralıkla izler ve değişen işi sahibine WebSocket'le iter. Ek bileşen (mesaj kuyruğu, Service Broker) yoktur (fonksiyon 48). | Geliştirme 0.4 |
| K-70 | Plan çıktı tabloları (PlannedOrder, SupplyRecommendation, DemandFulfillment, CapacityLoad, Pegging, PlanWarning) versiyonsuzdur; PlanRun'a bağlıdır, veri versiyonu PlanRun'dan gelir (K-41). Yayınlanmamış PlanRun'un çıktıları tekrar çalıştırmada silinip tek işlemde yeniden yazılır; yayınlanmış (PlanVersion'da geçen) PlanRun'un çıktıları hiç silinmez ve değişmez; yeniden hesap yeni PlanRun açar. | Geliştirme 0.5 |
| K-71 | Kalp atışını iş süreci değil, onu başlatan motor servisi (üst süreç) yazar: iş süreci yaşadıkça kalp atışı gider; çözücü GIL'i bırakmasa da etkilenmez. İş süreci yalnız adım geçişlerinde ilerleme (Progress) yazar. Süre bütçesi + pay aşılırsa servis süreci sonlandırır, iş ve PlanRun Hata olur. İş süreci beklenmedik biterse servis işi hemen yeniden sıraya alır (deneme hakkı varsa, K-67). | Geliştirme 0.5 |
| K-72 | Kurulum iskeleti PowerShell'dir (tek komut, yönetici); MSI (11.4) bunu sarar. Paket internetsizdir: Python kurulum dosyası, wheel'ler ve ön koşul MSI'ları paketin içindedir; kurulum hiçbir adreste internete çıkmaz. Paket yalnız geliştirme bilgisayarında, bir kez internetle hazırlanır; ön koşulların SHA-256'sı repoda sabittir. | Geliştirme 0.6 |
| K-73 | API ve motor iki Windows servisidir (WinSW ile sarılır, sanal servis hesaplarıyla çalışır: NT SERVICE\SmartchainApi, NT SERVICE\SmartchainEngine). Hata durumunda kendini yeniden başlatır, açılışta otomatik başlar. Yetkilerde grup adı değil SID kullanılır (Türkçe Windows'ta grup adları farklıdır). | Geliştirme 0.6 |
| K-74 | IIS ters vekildir (URL Rewrite + ARR, WebSocket açık). API yalnız 127.0.0.1:8000'i dinler; dışarıya yalnız IIS açılır. HTTPS bağlantısı müşterinin sertifikasıyla kurulur; sertifika yoksa (yalnız test) HTTP. | Geliştirme 0.6 |
| K-75 | SQL Server'ı müşteri kurar (ürüne ayrılmış instance, lisans müşteride). Kurulum verilen instance'ta veritabanını bizim collation'la açar, servis hesaplarına kendi veritabanında yetki verir ve geçişleri çalıştırır. Bağlantı Windows kimliğiyle, SQL kimliği seçeneğiyle (A-27). ODBC Driver 18 şifreli bağlantıyı varsayılan ister: Encrypt açık; SQL Server'da güvenilir sertifika yoksa TrustServerCertificate açılır. | Geliştirme 0.6 |
| K-76 | HiGHS (Python paketi highspy, MIT lisansı) kurulum paketine girer. Çözücüye yalnız app/engine/solvers/ altındaki adaptör erişir; motorun başka hiçbir yeri highspy'yi import etmez (K-35, fonksiyon 32). Çözücü seçimi (A-16, A-31) açıktır; HiGHS adaydır. | Geliştirme 0.7 |
| K-77 | Model ve çözüm dosyaları saklanır. Her plan hesabı için ayrı klasör açılır (`ProgramData\Smartchain\solver\<tarih>\PlanRun-<Id>\`); içinde model dosyası (LP), çözüm dosyası ve çözücü logu bulunur. Değişken ve kısıt adları okunur yazılır (ör. `Uretim[MAT-001,H44]`). Ne zaman yazılacağı (her zaman / yalnız hata ya da süre aşımında / kapalı) ve saklama süresi (ör. 30 gün, sonra otomatik silinir) sistem ayarıdır. Dosyalar destek paketine (fonksiyon 95) girer; kapalı ağda müşterideki sorun bu dosyalarla geliştirmede aynen yeniden üretilir. | 18 · Geliştirme 10.5 |
| K-78 | Sentetik veri seti v0 (docs/11): hayali talaşlı imalat ve montaj firması, ~200 malzeme, 15 tezgâh, 40 açık sipariş, 3 müşteri, 8 tedarikçi, ~25 çalışan, 13 hafta ufuk; darboğaz, gecikme, tedarikçi limiti, imkânsız termin, duruş ve izin bilerek konur. Sabit tohumlu üreticiyle üretilir, tarihler üretim gününe göre kayar. Temiz hâli geliştirmede ana tablolara doğrudan yüklenir; bu, ERP verisinin ana tablolara doğrudan yazılmaması kuralının (K-58) yalnız geliştirme ve demo için istisnasıdır. Kirli hâli entegrasyon biçiminde Excel'dir, kasıtlı hatalar taşır ve ETL testlerinde kullanılır. | 22 · Geliştirme 0.8 |
| K-79 | Sentetik v0 uygulama kuralları: set tek lokasyondadır (ORM-01) ve her yüklemede kendi veri versiyonunu açar. Yeniden yükleme önce o lokasyonun veri versiyonlarına bağlı her şeyi (ana tablo satırları, o versiyonlarla hesaplanmış plan hesapları, senaryolar, çalışmalar) ve setin parametre setini siler. Id'ler tablo başına 1'den sıralıdır; hafta 1 üretim gününün haftasıdır (Pazartesi). Kirli Excel'in satır düzeni 3.1'deki şablonla kesinleşir. Güvenlik kilidi: sentetik kayıtlar IsSynthetic = 1 ile işaretlenir (DataVersion, Location, ParameterSet); yükleme ve silme, veritabanında sentetik olmayan bir veri versiyonu, lokasyon ya da parametre seti varsa hiçbir şey silmeden durur ve nedenini kayıtlarıyla yazar. Sentetik set yalnız geliştirme ve demo veritabanında kullanılır. | Geliştirme 0.8 |
| K-80 | Değer listesi olan her alanda (açıklamada 'A \| B \| C') en uzun değer ve varsayılan değer alan uzunluğuna sığar; db/generate.py üretimde denetler, sığmayan varsa durur. İlk denetimde sığmayanlar uzatıldı (0005): MaterialSupplier.LeadTimeBasis nvarchar(15), PurchaseOrderLine.OrderType nvarchar(20) (ana ve entegrasyon tablosu), PriorityRule.Direction nvarchar(10). | Geliştirme 0.8 |
| K-81 | Ön yüz React (TypeScript) ile yazılır; geliştirmede derlenir, düz dosyalar olarak pakete girer ve IIS'ten sunulur; internetsizdir (CDN, dış font ve ikon yok). Tablolar TanStack Table altyapısı üzerine kendi bileşenimizdir (U-6…U-16 bu bileşende). Arayüz metinleri tek sözlük dosyasında, Faz 1'de yalnız Türkçe. Yalnız açık tema; en küçük hedef ekran 1366×768. | 23 · Geliştirme 1.1 |
| K-82 | Kabuk ve menü (docs/12): ekranlar kenar menüde gruplar hâlinde durur, ekranlar arası geçişte üst sekme kullanılmaz. Menü sırası: Ana sayfa · Planlama · Takip · Veri · Parametre · Yönetim. Çalışmanın ekranları (10–19) menüde Çalışma'nın, raporlar Raporlar'ın altında listelenir; en çok iki seviye; gruplar açılıp kapanır ve hatırlanır; menüde arama (Ctrl+K); daraltılmış menüde ikon ve yandan açılan alt panel. Ekran 01'in adı Ana sayfa'dır. Bağlam çubuğunda senaryo, plan versiyonu, dönem, çalışma adı, veri versiyonu, iş göstergesi ve kullanıcı menüsü durur. | 24 · Geliştirme 1.1 |
| K-83 | Ön yüz araçları: derleme Vite, yönlendirme react-router; ikon seti Lucide (lucide-react, ISC), yalnız kullanılan ikonlar pakete girer; fontlar @fontsource/instrument-sans ve @fontsource/inter (OFL-1.1; K-86), woff2 dosyaları pakete gömülü. Paket sürümleri package-lock.json ile sabit; tablo altyapısı @tanstack/react-table ve @tanstack/react-virtual (MIT; 1.3). Arayüz installer/build.ps1'de derlenir ve pakete web\ olarak girer. Geliştirmede Vite /api ve /api/ws'i 127.0.0.1:8000'e yönlendirir. Oturum gelene kadar arayüz kullanıcıyı ?user_id= ile alır (A-36); menü ve yazı boyutu tercihleri tarayıcıda tutulur, 2.3'te kullanıcı ayarına taşınır. | Geliştirme 1.1 |
| K-84 | Kenar menü açık indigodur (görsel seçenek F, docs/12): zemin #EEF0FB, sağda #DCE0F7 çizgi, genişlik standart yazı boyutunda 256 px (1rem = yazı boyutu olduğundan 19,69rem; yazı boyutuyla ölçeklenir; daraltılmış hâl değişmez). Ekran adı koyu, grup başlığı indigo-gri yarı kalın küçük harf aralıklı; seçili ekran indigo zemin üzerinde beyaz yarı kalın; çalışma kapalıyken ekranlar okunur renkte (en az 4,5:1) ve kilit ikonlu, soluk görünüm yok (U-3). Çalışma alanı zemini #F7F8FA, kart ve tablolar beyaz. Değerler yalnız tokens.css'tedir. | Geliştirme 1.1 |
| K-85 | Stil sistemi (docs/12): bütün renk, yazı ve boşluk değerleri app/web/src/styles/tokens.css'te tek yerde; diğer CSS'lerde renk sabiti yoktur. Durum, doluluk, uyarı ve rozet renkleri mockup'lardan alınır; her yazı-zemin çifti en az 4,5:1. Aşırı yük hücresi dolu kiremit değil, risk hücresiyle aynı yoğunlukta açık kiremit zemin (#F4CFC4) üzerinde koyu kiremit kalın yazıdır (#8A3612, 5,6:1); lejant da öyledir (/stil gözden geçirmesi). Doluluk skalası varsayılan eşikleri <40 · 40–69 · 70–89 · 90–100 risk · >100 aşırı yük; eşik ekranda yazan yuvarlanmış değere uygulanır; eşikler koda sabit yazılmaz, parametredir ve müşteriye göre değişir (7.5 uyarı eşikleri). Yazı ve boşluk ölçeği rem cinsindendir (1rem = kullanıcının yazı boyutu, U-23). Geri alınamaz işlem butonu kiremittir (mockup m24f-0757; U-2'nin tek istisnası, yalnız onay penceresinde). Tablo renkleri (bütün tablolar için ortak, /tablo gözden geçirmesi; seçenek C, belirgin indigo): başlık zemini #DCE0F7, yazısı #1E2257 yarı kalın, alt çizgisi ve tablonun dış çerçevesi #C5CBF2; 1. düzey grup #ECEEF7 (alt çizgi #E1E4EE, kalın yazı), 2. ve alt düzeyler #F7F8FC; veri satırı beyaz; seçili satır #EEF0FB, üzerine gelince #F4F5FB; grup satırı üzerine gelince renk değiştirmez. Başlık, grup, seçili ve normal satır birbirinden ayırt edilir; yazı her zeminde en az 4,5:1. Grafik serisi sırası (U-5): indigo #4F5BD5 · petrol #2E7D7A · hardal #B8860B (grafik tonu; durum rengi #D9A521 beyazda 2,2:1 kalır) · kurşun #5A606B · erik #8E4585 · kahve #8A6440; her seri beyaz zeminde en az 3:1; kiremit ve kırmızı hiçbir zaman seri olmaz (durum rengidir). Ortak bileşenler app/web/src/ui/'de; hepsi /stil örnek sayfasında gösterilir. | 23 · Geliştirme 1.2 |
| K-86 | Yazı tipleri (K-30'u günceller): metin Instrument Sans; sayı, tarih ve kod Inter (sıfırda nokta ya da çizgi yok), rakamlar eşit genişlikte (font-variant-numeric: tabular-nums), böylece tablo sütunları hizalı durur. Inter pakete gömülüdür (@fontsource/inter, OFL-1.1); JetBrains Mono paketten çıkar. Değişken --font-num (eski --font-mono). | 23 · Geliştirme 1.2 |
| K-87 | Liste sorgu sözleşmesi (docs/08): her liste aynı üç uç noktayı kullanır: kolonlar (`GET /api/<liste>/columns`), sorgu (`POST …/query`) ve değerler (`POST …/values`). Alan seçimi, çoklu sıralama, filtre, parça parça yükleme (offset/limit; parça büyüklüğü SystemSetting ListChunkSize, varsayılan 100, en çok 500) ve sayılar (`filtered` / `total`) sunucuda yapılır (U-21). Alan ve operatör beyaz listeden, değerler parametreyle gider. Metin karşılaştırma ve sıralama Türkçe ve büyük/küçük harf duyarsızdır (Turkish_100_CI_AS). Liste güncel veri versiyonunu okur. Sayı kolonunun ondalığı liste tanımından gelir, veritabanı ölçeğinden değil. | 23 · Geliştirme 1.3 |
| K-88 | Alan etiketi: kolon başlığı docs/02 AÇIKLAMA'sından kuralla üretilir: değer listeli alanda ':' öncesi ('Malzeme seviyesi: Hammadde \| …'), diğerlerinde ilk ';' öncesi. generate.py etiketi modele yazar (info label) ve liste tanımı olan tablolarda eksik ya da 40 karakterden uzun etiketi hata sayar (K-80 gibi); diğer tablolar kendi ekran adımında kontrole girer. FieldDefinition.Label standart alanın etiketini ezer; ek alan (K-59) yalnız Label'ı varsa listede görünür. Sayı gösterimi: ondalık veritabanı ölçeğinden değil liste tanımından gelir; gün, adet gibi tam sayı anlamındaki alanlar 0. Miktar kolonları (güvenlik stoğu, maksimum stok, lot alanları…) liste tanımında "ondalık birimden" diye işaretlenir ve her satırda malzemenin temel biriminin ondalığıyla (UnitOfMeasure.Decimals: ADET 0, KG 3, M 2, SAAT 2, bilinmeyen 2) gösterilir. | 21, 23 · Geliştirme 1.3 |
| K-89 | Kayıtlı görünüm (U-9, docs/12): görünüm veritabanında tutulur (adm.TableView), tarayıcıda değil. İçeriği kolon seti ve sırası, genişlikler (rem; yazı boyutuyla ölçeklenir, U-23), sabitlenen ilk kolon sayısı, sıralama, filtreler, gruplama ve kullanıcının seçtiği ara toplam türleridir (K-90). Kişisel ya da paylaşılan olur; yalnız sahibi değiştirir ya da siler; paylaşılanı şimdilik herkes görür (rol kuralı 2.2). Kullanıcı her liste için varsayılanını seçer (adm.TableViewDefault); seçmediyse liste tanımındaki silinemez "Standart" görünüm açılır. İçerik kaydederken liste tanımına göre doğrulanır; açılırken artık olmayan alan atlanır ve kullanıcıya söylenir. Göreli tarih filtreleri (bu hafta, sonraki 4 hafta) göreli saklanır, tarih değil; görünüm başka gün açılınca o günün haftasına göre çalışır. Admin'in bir paylaşılan görünümü herkes ya da bir rol için varsayılan yapması 2.2'de (rol kurallarıyla); şimdi yapılmaz. | 23 · Geliştirme 1.4 |
| K-90 | Gruplama sunucuda (U-11, U-21): bir ya da birden çok alana göre gruplanır; sunucu grup ağacını satır sayısı ve ara toplamlarla döndürür, satırlar grup anahtarıyla parça parça okunur (K-87). Ara toplam türünü kullanıcı sayı kolonunun menüsünden seçer: toplam, ortalama (boşlar hariç), ortalama (sıfırlar hariç), ağırlıklı ortalama (ağırlık alanı seçilir; değeri ya da ağırlığı boş satırlar hesaba girmez, ağırlıkların toplamı 0 ise sonuç boş), en küçük, en büyük, sayı (dolu satır), yok. Varsayılan liste tanımından; seçim görünümle kaydedilir (K-89). Hesap sunucuda; üst gruplar alt gruplardan tam olarak türetilir (ortalamalar satır sayısıyla ağırlıklı). Miktar kolonlarında (ya da ağırlık miktarsa) katkı veren satırların birimi farklıysa sayı dışındaki türler gösterilmez ("birimler farklı"; K-88). En çok ListMaxGroups (SystemSetting, 1.000) yaprak grup; fazlasında 422. Grup sırası, grup alanı sıralamadaysa onun yönüyle, değilse artan (Türkçe); boş grup en sonda. Gruplama sorgusu paralel plan tercihiyle çalışır (USE HINT ENABLE_PARALLEL_PLAN_PREFERENCE): maliyet tahmini seri plan seçiyor, paralel plan 50.000 satırda ~4 kat hızlı. | 23 · Geliştirme 1.4 |

## Açık konular

| No | Konu | Adım |
|---|---|---|
| A-1 | Ürünün hangi problemleri çözeceğine karar verilmesi gerekiyor. | 1 |
| A-2 | Kalıp ömrü dolduğunda yeni kalıp tedarik sürecinin nasıl ele alınacağı düşünülecek. | 2 |
| A-3 | Plan seviyesi: kapasite yükü planı mı, iş emri bazında tarihler mi? Çözümde belirlenecek. | 2 |
| A-4 | Verimin makine grubu seviyesinde tek oranla tanımlanması çözümde değerlendirilecek. | 2 |
| A-5 | Transfer partisinin MRP patlatırken bucket yönetiminde nasıl ele alınacağı çözümde düşünülecek. | 3 |
| A-6 | · D2 | 20 |
| A-7 | Dönem bazlı öncelik (önce dönem, sonra proje önceliği, sonra teslim tarihi) müşteri siparişleri başlığında detaylandırılacak. | 4 |
| A-8 | Raf ömrü Faz 1'de sadece uyarı mı olacak? | 17 |
| A-9 | İşçi gruplarında kapasite vardiyadan mı hesaplanacak, doğrudan mı girilecek? | 17 |
| A-10 | İç üretim ya da fason tercihi listeye geri gelecek mi? | 17 |
| A-11 | MRP ile optimizasyon modelinin iş bölümü (Faz 1 çalışma akışı). | 18 |
| A-12 | Bucket ile üretim ve tedarik süreleri arasındaki uyumsuzluk. | 18 |
| A-13 | Sabit arz çelişkisinde yeni arz önerilsin mi; satın almada projeler birleştirilsin mi? | 18 |
| A-14 | Manuel girilen miktar, optimizasyon yeniden çalıştığında sabit mi kalır, yoksa başlangıç önerisi mi sayılır? Cevaba göre hücre bazında kilit gerekir. | 23 |
| A-15 | Çakışma kuralları taslak; sonra değerlendirilecek. | 19 |
| A-16 | Çözücü seçimi geliştirme aşamasında yapılacak. | 19 |
| A-17 | Alanların tablo tablo birlikte gözden geçirilmesi. | 21 |
| A-18 | Faz 1 dışı konuların (set-up, kalıp, fırın, raf ömrü) tabloları sonraki fazda. | 21 |
| A-19 | Fonksiyon listesi, prensipleri ve mockupları ilk taslak; öneri olanlar konuşulacak. | 24 |
| A-20 | Mockuplar ilk taslak; ekran ekran gözden geçirilecek. | 24 |
| A-21 | Rapor listesi ilk taslak; 25 rapor ve pano gözden geçirilecek. | 25 |
| A-22 | Gerçekleşme raporları (16–20) için ERP'den sevkiyat ve üretim gerçekleşmesi verisi gerekir; veri sözleşmesine eklenecek (26. adım). | 25 |
| A-23 | Artımlı çekimde silinen kayıtlar: SC_ACTION mi, haftalık tam çekim mi? | 26 |
| A-24 | ERP belge numarası ↔ Smartchain öneri bağı: ERP'de dış referans alanı var mı? | 26 |
| A-25 | Rota tüketim birimi dönüşümü adaptörde mi, veri kuralında mı? | 26 |
| A-26 | SQL Server lisansı müşteride mi, bizde mi; küçük müşteride Express yeterli mi? | 27 |
| A-27 | Küçük müşteride tek sunucu mu, iki sunucu mu? Ölçek testinden sonra. | 27 |
| A-28 | Pilot müşteri: kim, ne zaman, hangi ERP? Faz 1 kapısı pilota bağlı. | 28 |
| A-29 | Dilim süreleri tek geliştirici + Claude Code varsayımı; D1 sonunda yeniden ölçeklenir. | 28 |
| A-30 | Başlangıç tarihi ve haftalık kapasite; plan tam zamanlı varsayımıyla. | 29 |
| A-31 | Çözücü kararı D3 sonunda (H10); MILP ölçeği D9'da. | 29 |
| A-32 | Satın alma ve satış personaları end user ise aksiyon tamamlama ve ERP numarası girme hikâyeleri salt okunur kuralıyla çelişir; 'sınırlı key user' rolü mü? | 20 |
| A-33 | Kalan 56 hikâyenin kabul kriterleri dilime alınırken yazılacak. | 20 |
| A-34 | Aktarım filtresinin yöntemi: kapsam filtresi (pasif malzeme, kapalı sipariş, başka lokasyon gibi) nasıl tanımlanacak? Değişen kayıtlar K-40 ve A-23'e, hatalı satırlar 26. adımdaki hata yönetimine bağlı. | Geliştirme 4.3 |
| A-35 | Kaynağın takvimi (Resource.CalendarId) şimdilik Smartchain'de atanır, entegrasyonla gelmez; ERP'den takvim kodu alınıp alınmayacağına sonra bakılacak. | Geliştirme 0.2 |
| A-36 | Oturum (2.1) gelene kadar WebSocket (/api/ws) ve iş listesi (/api/jobs) kullanıcıyı user_id sorgu parametresiyle alır; geçicidir, 2.1'de oturumdan okunur. Admin'e sistem olayı ve başkasının işini iptal yetkisi 2.2'de. | Geliştirme 0.4 |
