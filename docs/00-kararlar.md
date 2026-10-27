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
| K-30 | Ürün paleti indigo + kurşun; durum renkleri hardal (risk) ve kiremit (aşırı yük). Yazı tipleri Instrument Sans ve JetBrains Mono. | 23 |
| K-31 | U-1…U-22 arayüz prensipleri tüm ekran ve raporlar için bağlayıcıdır; yeni ekran bu listeye göre gözden geçirilir. | 23 |
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
