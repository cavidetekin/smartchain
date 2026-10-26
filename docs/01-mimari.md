# Mimari kararlar (MDD adım 19)

Kaynak: Master Design Document (MDD) 26.10.2026. Bu dosya desteden üretilmiştir; değişiklik önce burada yapılır, deste dilim sonlarında buradan güncellenir (K-54).

### 19. Mimari kararlar
<sub>tamamlandı</sub>

- **Ne yapılacak:** Kurulum ve işletme, platform ve teknoloji, veritabanı, entegrasyon, modelleme katmanı ve çözücü, kullanıcılar ve yetkiler, senaryo ve çalışma mekanizması, veri yükleme ve veri katmanları, hata yönetimi, lokasyon. Her biri bir karar ve gerekçesiyle. Çıktı: mimari karar listesi
  - Bu adımın slaytları
  - 01 Kurulum
  - 02 İşletme ve destek
  - 03 Bulut hazırlığı
  - 04 Platform ve teknoloji
  - 05 Veritabanı
  - 06 Entegrasyon
  - 07 Modelleme katmanı ve çözücü
  - 08 LLM
  - 09 Kullanıcı bağlantısı
  - 10 Kullanıcı tipleri
  - 11 Senaryo, çalışma ve yayın
  - 12 Çalışma mekanizması
  - 13 Veri yükleme
  - 14 Veri katmanları
  - 15 Ana veri ve parametre
  - 16 Hata yönetimi
  - 17 Lokasyon
  - 18 Çakışma kuralları
- **Kararlar**
  - K-32  Faz 1 hedefi müşterinin sunucusu, kapalı ağ; işletme bizde, uzaktan erişim yok. Tek paket bulutu engellemez.
  - K-33  Windows Server, Python; ürüne ayrılmış, en güncel sürümde MS SQL Server.
  - K-34  Entegrasyon ERP'den bağımsız: API, Excel, SQL arayüz tabloları; tek veri sözleşmesi.
  - K-35  Modelleme katmanı çözücüden bağımsız. LLM Faz 1'de kapalı.
  - K-36  Kullanıcı seviyeleri: sistem sahibi, admin, key user, end user.
  - K-37  Onaylı plan sadece çalışmadan yayınlanır. Faz 1'de tek lokasyon.
- **Açık konular**
  - A-15  Çakışma kuralları taslak; sonra değerlendirilecek.
  - A-16  Çözücü seçimi geliştirme aşamasında yapılacak.

### Kurulum modeli
<sub>19. Mimari kararlar · Kurulum</sub>

| SEÇENEK | VERI NEREDE | KIM IŞLETIR | FAZ 1 |
|---|---|---|---|
| Müşterinin sunucusu, kapalı ağ | Müşteride | Biz, yerinde; uzaktan erişim yok | Hedef |
| Müşterinin bulutu | Müşteride | Biz; uzaktan erişim olmadığı varsayılır | Destekli; aynı paket |
| Bizim bulutumuz (SaaS) | Bizde | Biz | Sonraki faz |
| Neden kapalı ağ | Hedef müşteriler verisini dışarı çıkarmak istemiyor; internete bağlı olmayan kapalı ağ kurulumu bekleniyor. |  |  |
| Tek paket | Aynı paket üç ortamda da çalışır; fark sadece yapılandırmada. Üç seçenek sonradan ek iş olmadan açılabilir. |  |  |
| Karar: Faz 1 hedefi müşterinin sunucusu, internete bağlı olmayan kapalı ağ. Tek paket üç ortamda da çalışır. İşletme bizde; uzaktan erişim yok. |  |  |  |

### Kapalı ağda işletme ve destek
<sub>19. Mimari kararlar · İşletme ve destek</sub>

- **Çevrimdışı paket:** Uygulama, çalışma ortamı, kütüphaneler, çözücü ve arayüz dosyaları tek, imzalı pakette; medyayla taşınır. İnternete hiçbir bağımlılık yok.
- **Kurulum ve güncelleme:** Tek komut. Güncellemeden önce otomatik yedek; geri alma mümkün; veritabanı geçişleri geri alınabilir yazılır.
- **Lisans:** Çevrimdışı, imzalı, süreli lisans dosyası; kuruluma bağlı. Çevrimiçi aktivasyon yok.
- **Sistem sağlığı ekranı:** Son çalışmalar, hatalar, çözüm süreleri, veri çekimi durumu. Uzaktan bakamayacağımız için sistem kendini anlatmalı.
- **Destek paketi:** Tek tuşla loglar, sürüm bilgisi, çözüm logları ve anonim model dosyası dışa alınır; müşteri medyayla bize verir.
- **Anonimleştirme ve sentetik veri:** Müşteri verisi dışarı alınamadığı için hatalar anonimleştirilmiş veri ve sentetik veri setiyle (Adım 22) üretilir.
- **Donanım boyutlandırma:** Müşteri büyüklüğüne göre minimum ve önerilen sunucu tanımı; ölçek testiyle netleşir.
- Not: Her güncelleme ve destek talebi yerinde ziyaret ya da müşterinin BT'siyle koordinasyon demek; destek modeli ve fiyatlama bunu hesaba katmalı.

### Bulutu engellemeyen tasarım
<sub>19. Mimari kararlar · Bulut hazırlığı</sub>

- Buluttan hizmet vermek Faz 1'de yok; ama şimdi konan üç kuralla bulut sonradan kod değişikliği değil, işletme işi olur.

#### ŞIMDI UYGULANAN KURALLAR

- **Bir kurulum = bir müşteri:** Bulutta her müşteriye ayrı kurulum ve ayrı veritabanı. Aynı veritabanında çok müşteri yok; kapalı ağdaki paket bulutta değişmeden çalışır, veriler fiziksel olarak ayrı kalır.
- **Entegrasyon veri paketi üzerinden:** Motor verinin nereden geldiğini bilmez. Aynı paket doğrudan okumayla, müşterinin ağındaki bir ajanla ya da Excel'le gelir.
- **Ortam farkları yapılandırmada:** Bağlantılar, şifreler, LLM, çözücü ve kimlik doğrulama yapılandırma ve özellik anahtarlarıyla yönetilir; kodda 'kapalı ağdayız' varsayımı yok.

#### SONRADAN YAPILACAKLAR

- **Bulut açılınca:** Bağlantı ajanı · kurulumları açan ve güncelleyen altyapı · merkezi izleme ve yedekleme · KVKK ve verinin yeri · şifreleme, sızma testi, ISO 27001 · kurumsal giriş · abonelik.

### Platform ve teknoloji
<sub>19. Mimari kararlar · Platform ve teknoloji</sub>

- **İşletim sistemi:** Sadece Windows Server. Konteyner yok; Windows'a doğal yükleyici paket.
- **Dil:** Python. Uygulama, API ve planlama motoru aynı dilde.
- **Web ve API:** FastAPI; IIS arkasında, Windows servisi olarak. Eş zamanlı çok kullanıcı ve anlık bildirim (WebSocket) desteği.
- **Arayüz:** Ayrı bir web uygulaması; tarayıcıda çalışır.
- **Planlama motoru:** Ayrı Windows servisi; her iş kendi işletim sistemi sürecinde. Paralellik ve yalıtım: bir iş çökerse diğerleri etkilenmez.
- **İş kuyruğu:** SQL Server'da iş tablosu, satır kilitlemeli okuma. Ek bileşen yok; plan sonuçlarıyla aynı işlem içinde.
- **Kod koruması:** Python kodu derlenerek dağıtılır.
- **Neden Python:** Motor ürünün kalbi ve optimizasyon ekosistemi Python'da. Ekip küçük, geliştirme Claude Code ile; tek dil en hızlısı. .NET Windows uyumunda önde; motor ayrı servis olduğu için API katmanı ileride değiştirilebilir.

### Veritabanı: MS SQL Server
<sub>19. Mimari kararlar · Veritabanı</sub>

- **Sunucu:** Ürüne ayrılmış ayrı bir SQL Server. ERP'nin veritabanı sunucusu kullanılmaz.
- **Neden ayrı:** Plan çalışırken yoğun okuma ve yazma ERP'yi yavaşlatmasın; sürümü ve ayarları biz belirleyelim.
- **Sürüm:** Başlangıçta en güncel SQL Server sürümü.
- **Lisans:** Müşteride. Ücretsiz Express sürümünün sınırları planlama verisine yetmez.
- **Collation:** Veritabanı collation'ını biz belirleriz; Türkçe collation'daki I / ı dönüşümü kodda hataya yol açabilir.
- **Yetkiler:** Kendi veritabanımızda tam yetki; arayüz tablolarına yazan kullanıcıya ayrı, kısıtlı rol.
- **Yedekleme:** Yedekleme ve kurtarma prosedürünü biz veririz; müşterinin bakım planına girer.
- Karar: MS SQL Server, ürüne ayrılmış ayrı bir sunucuda, en güncel sürümle. Müşteriye minimum gereksinim listesi verilir.

### Entegrasyon: ERP'den bağımsız
<sub>19. Mimari kararlar · Entegrasyon</sub>

- Ürün hangi ERP olursa olsun aynı veri sözleşmesiyle çalışır. Üç yöntem de aynı ham veri katmanına iner; yöntem sadece taşıma şeklidir.

| YÖNTEM | NASIL | KIM IÇIN | SONUÇLARIN DÖNÜŞÜ |
|---|---|---|---|
| API | Müşterinin sistemi veriyi REST servisleriyle gönderir. | Entegratörler; ileride bulut | Servisten okunur |
| Excel yükleme | Kullanıcı şablonla ekrandan yükler; doğrulama raporu. | İlk kurulum, küçük müşteri, eksik veri | Excel'e indirilir |
| SQL arayüz tabloları | Müşteri ya da ETL işi arayüz tablolarına yazar, biz okuruz; durum alanları ve hata tablosu. | SQL'e yazabilen her ERP ve ETL aracı | Giden arayüz tablolarına yazılır |
| Ortak kurallar | Her yükleme parti numarası, zamanı ve kaynağıyla kaydedilir · tam ya da değişen kayıt, tablo bazında · yöntemler karışabilir · hatalı kayıtlar uyarı ekranına düşer. |  |  |
| Veri sözleşmesi | Tablo ve alan sözlüğü; üç yöntem için tek. Adım 21'de. |  |  |

### Modelleme katmanı ve çözücü
<sub>19. Mimari kararlar · Modelleme katmanı ve çözücü</sub>

- KATMAN · NE YAPAR
- **İş modeli:** Değişkenler ve kısıtlar iş diliyle tanımlanır ('kaynak kapasitesi, CNC-01, Mart'). Her kısıt sert ya da yumuşak ve iş anlamı etiketi taşır; açıklama ve raporlar bundan beslenir. Hiçbir çözücüyü tanımaz.
- **Çeviri:** İş modelini seçilen çözücünün girdisine çevirir; çözücü başına ince bir adaptör. Yedek olarak bütün çözücülerin okuduğu standart model dosyası (MPS); destek paketindeki anonim model de bu.
- **Yetenek eşleştirme:** Çözücünün neyi desteklediğini bilir: IIS, sıcak başlangıç, süre limiti, gap. Desteklemiyorsa motor buna göre davranır; örneğin IIS yoksa elastik modele dayanır.
- **Çözücü seçimi:** Parametrik: kurulum, çalışma tipi ya da senaryo bazında. Hangi çözücüyle ilerleneceğine geliştirme aşamasında karar verilecek; aday HiGHS (açık kaynak, kapalı ağda lisans sorunu yok).
- **Uygulama:** İş modeli katmanını kendimiz yazarız; çeviriyi hazır ve hızlı bir kütüphanenin üzerine kurarız.
- Karar: Modelleme katmanı çözücüden bağımsız; iş modeli hangi çözücü seçilirse ona girdi üretir.

### LLM
<sub>19. Mimari kararlar · LLM</sub>

- **Neden kapalı:** Kapalı ağda bulut LLM servisi kullanılamaz; yerel model GPU'lu sunucu ister, her müşteride yok.
- **Faz 1'de açıklama:** Şablon tabanlı: 'Şu sipariş, şu kaynak ve şu malzeme yüzünden şu kadar geç' gibi cümleler kısıt etiketlerinden kuralla üretilir.
- **Sonraki faz:** LLM ile açıklama, doğal dille soru ve senaryo; kurulum ortamına göre yerel model ya da bulut servis. Sağlayıcıdan bağımsız arayüz.
- Karar: LLM Faz 1'de kapalı.

### Kullanıcı bağlantısı ve giriş
<sub>19. Mimari kararlar · Kullanıcı bağlantısı</sub>

- **Bağlantı:** Şirket içi ağda web tarayıcısıyla (Edge, Chrome). Kullanıcının bilgisayarına kurulum yok.
- **Güvenli bağlantı:** HTTPS; sertifikayı müşterinin iç sertifika otoritesi verir.
- **Uzaktan çalışma:** Müşterinin VPN'i ile iç ağa girilir; müşterinin ağ politikası.
- **Kullanıcılar:** Faz 1'de kullanıcılar ve roller uygulamanın içinde tanımlanır. Active Directory sonraki faz; giriş yapısı değiştirilebilir kurulur.
- **Şifre güvenliği:** Şifreler özetlenerek saklanır; şifre kuralı ayarlanabilir; hatalı denemelerde hesap kilitlenir.
- **Şifre sıfırlama:** Admin geçici şifre verir, kullanıcı ilk girişte değiştirir; kapalı ağda e-posta olmayabilir.
- **Oturum ve kayıt:** Zaman aşımı; kim ne zaman girdi, neyi değiştirdi kaydı.
- Kapsam dışı: Masaüstü uygulaması, Excel eklentisi ve mobil kapsam dışı.

### Kullanıcı tipleri ve yetkiler
<sub>19. Mimari kararlar · Kullanıcı tipleri</sub>

| SEVIYE | KIM | YETKI |
|---|---|---|
| Sistem sahibi | Biz (kurulum hesabı) | Her şey + lisans ve sürüm · motor ve teknik ayarlar (çözücü, süre bütçesi, işçi sayısı, eş zamanlı çalışma sınırı) · veri sözlüğü yapısı · teşhis ve destek paketi · admin hesaplarını kurtarma. Admin bu hesabı göremez ve değiştiremez; her işlemi silinemez kayıtla tutulur. |
| Admin | Müşterinin yöneticisi | Kullanıcı ve rol yönetimi · entegrasyon bağlantıları ve servis hesapları · zamanlanmış işler + key user'ın her şeyi. |
| Key user | Planlamacı | Veri kuralları ve elle değerler · veri yükleme · parametreler ve gece senaryo tanımları · senaryo ve çalışma · onaylı plan yayını · görüntüleme ve Excel. |
| End user | Diğer herkes | Sadece görüntüleme ve Excel'e indirme; onaylı plan ve raporlar. Hiçbir fonksiyon çalıştıramaz, termin sorgusu dahil. |
| İnsan olmayan hesaplar | Entegrasyon servis hesabı (API ve SQL arayüz tabloları) ve sistem kullanıcısı (gece işleri). Kullanıcı tipi değil; admin yönetir. |  |

### Senaryo, çalışma ve yayın
<sub>19. Mimari kararlar · Senaryo, çalışma ve yayın</sub>

- **Senaryo:** Gece tanımlı listeden üretilen plan. Tanımı: veri versiyonu + parametre seti + eksen ayarları.
- **Çalışma:** Kullanıcının bir gece senaryosu üzerinde açtığı çalışma alanı. Senaryo üzerindeki değişiklikler yeni senaryo değil, çalışmadır.
- **Yayın:** Onaylı plan sadece bir çalışmadan yayınlanır; değişiklik yapmadan da olur. Aynı anda tek geçerli onaylı plan; ERP'ye dönüş ondan. Yetki: key user ve admin.
- **Saklama:** Yayınlanmayan senaryo ve çalışmalar bir sonraki gece akışında silinir. Onaylı plan versiyonları ve dayandıkları veri versiyonları hep kalır; silinen senaryoların özet metrikleri kısa süre tutulur.
- **Varsayılan yap:** Çalışmada değiştirilen parametreler yayında istenirse yeni varsayılan olur; otomatik olmaz.
- **Eski veri uyarısı:** Çalışma, sonradan yeni veri yüklenmiş bir versiyona dayanıyorsa yayında uyarı çıkar.

### Smartchain'in çalışma mekanizması
<sub>19. Mimari kararlar · Çalışma mekanizması</sub>

- GECE KANALI · ETKILEŞIM KANALI
- **Ne çalışır:** Tanımlı gece senaryoları Kullanıcı çalışmaları ve termin sorgusu
- **Öncelik:** Sabaha yetişmek; öncelikli senaryolar önce Kullanıcıyı bekletmemek
- **İşçiler:** Paralel; sayısı sunucu kapasitesine göre parametre Çalışma başına ayrılmış, hep hazır işçi
- **Eş zamanlılık:** Gece belirlenen kadar senaryo 3 aktif çalışma (parametre); fazlası sıraya girer ve sırasını görür
- **Sıcak çalışma:** Çalışma açıkken verisi ve çözümü motor sürecinin belleğinde durur. Değişiklikte sadece etkilenen kısım yeniden hesaplanır, optimizasyon mevcut çözümden başlar.
- **Anlık bildirim:** İlerleme ve sonuç ekrana itilir (WebSocket); ekran sürekli sormaz.
- **Gece akışı:** Ön kontroller → veri çekimi → otomatik yükleme → senaryolar paralel → sabah ekranında özet: bitti, kısmen, hata.

### Veri yükleme (ETL) ve veri versiyonları
<sub>19. Mimari kararlar · Veri yükleme</sub>

- **Çekim:** ERP'den, API'den, Excel'den ya da SQL arayüz tablolarından gelen veri ham veri katmanına düşer. Planlama ekranları değişmez.
- **Doğrulama:** Veri kuralları çalışır, uyarılar çıkar; kullanıcı ne geldiğini ve farkları görür.
- **Yükleme:** Kullanıcı ya da gece akışı yüklemeyi başlatır; yeni bir veri versiyonu oluşur.
- **Kısmi yükleme:** Sadece seçilen varlıklar yüklenebilir (ör. siparişler ve stok, ya da bir proje). Yeni versiyon yüklenmeyenleri öncekinden alır; sadece değişen kısım yazılır.
- **Tutarlılık:** Kısmi yüklemede eksik ilişki varsa uyarı ve öneri: ör. yeni siparişin malzemesi ana veride yoksa ilgili ana veriyi de yüklemesi önerilir.
- **Dondurma:** Her senaryo ve çalışma bir veri versiyonuna bağlıdır; yeni yükleme açık çalışmaları bozmaz.

### Veri katmanları ve saklama
<sub>19. Mimari kararlar · Veri katmanları</sub>

| KATMAN | İÇERIK | SAKLAMA |
|---|---|---|
| Ham veri | Gelen veri; parti numarası, zaman ve kaynakla | Bir hafta |
| Geçerli veri | Veri kuralları ve elle değerler uygulanmış hali; her alanın kaynağı izlenir | Sürekli (güncel hali) |
| Veri versiyonu | Yükleme ile oluşan dondurulmuş hali; tam ya da kısmi | Onaylı plana bağlıysa hep; değilse senaryosuyla silinir |
| Senaryolar ve çalışmalar | Bir veri versiyonuna bağlı planlar ve üzerlerindeki değişiklikler | Bir sonraki gece akışına kadar |
| Onaylı plan versiyonları | Yayınlanan planlar ve tarihçesi | Hep |
| Kayıtlar | Çözüm logları, plan farkları, kullanıcı değişiklikleri, uyarılar ve aksiyonlar | İlk günden tutulur |

### Ana veri ve planlama parametresi
<sub>19. Mimari kararlar · Ana veri ve parametre</sub>

- ANA VERI · PLANLAMA PARAMETRESI
- **Örnek:** ResourceType, IsConstrained, kapasite birimi, günlük kapasite, kaynak adedi Kapasite katsayısı, fazla mesai dahil mi, alokasyon oranları, öncelik kuralı, model tipi
- **Nereden gelir:** ERP; gelmiyorsa ETL'deki veri kuralları; gerekirse ana veri ekranında elle düzeltme Smartchain'de tanımlanır
- **Kapsam:** Genel; bütün senaryolarda aynı Senaryoya özel olabilir
- **Nerede değişir:** Ana veri yönetimi ekranında; sonraki yüklemeyle veri versiyonuna girer Senaryo tanımında ya da çalışmada
- **Karma alanlar:** Değeri ana veriden gelir ama çalışmada geçici olarak üzerine yazılabilir (ör. vardiya planı, bakım takvimi). Geçici değer sadece o çalışmada geçerlidir.
- **Veri sözlüğünde:** Her alan için: sınıf (ana veri ya da parametre) · çalışmada değiştirilebilir mi · değer önceliği · varsayılan ve zorunluluk. Adım 21'de alanlar belirlenirken.

### Hata yönetimi
<sub>19. Mimari kararlar · Hata yönetimi</sub>

- KURAL · AÇIKLAMA
- **Yarım plan görünmez:** Sonuç önce ara tabloya yazılır, tamamlanınca tek işlemle yayınlanır; hata olursa önceki versiyon geçerli kalır.
- **İş yalıtımı:** Her iş ayrı süreçte; biri çökerse servis ve diğer işler etkilenmez, işçi yeniden başlatılır.
- **Hata tipine göre tekrar:** Geçici hatalar 2–3 kez artan aralıkla otomatik tekrarlanır; kalıcı hatalar (veri hatası, çözümsüz model) nedeniyle raporlanır.
- **Yedek motor zinciri:** Optimizasyon süresinde bitmezse en iyi çözüm; hiç çözüm yoksa kurallı yerleştirme; o da olmazsa kısıtsız MRP. Hangi motorun çalıştığı ekranda yazar.
- **Takılan işin tespiti:** Çalışan iş düzenli 'yaşıyorum' sinyali verir; sinyal kesilirse başarısız sayılır, gerekirse yeniden kuyruğa alınır.
- **Güvenle tekrar çalıştırma:** Aynı iş tekrar çalışınca çift kayıt ya da bozulma olmaz.
- **Anlaşılır mesaj ve iz:** Kullanıcıya iş diliyle mesaj; her işin kendi numarasıyla logu tutulur ve destek paketine girer.

### Lokasyon
<sub>19. Mimari kararlar · Lokasyon</sub>

- **Veri modeli:** Lokasyon bütün tablolarda baştan var.
- **Planlama:** Her lokasyon kendi içinde planlanır; her senaryo ve çalışma bir lokasyona bağlı. Çok lokasyonlu müşteri her lokasyon için ayrı gece senaryoları tanımlar.
- **Açık transferler:** ERP'deki mevcut transferler sabit hareket olarak okunur: gelen transfer arz, giden transfer talep. Motor yeni transfer önermez.
- **Diğer lokasyonların stoğu:** Planda kullanılmaz; raporda bilgi olarak gösterilebilir.
- Karar: Faz 1'de tek lokasyon planlanır. Lokasyonlar arası transfer ve ağ kararları bu fazda yok.

### Çakışma kuralları (taslak)
<sub>19. Mimari kararlar · Çakışma kuralları</sub>

- DURUM · ÖNERILEN KURAL
- **Aynı senaryoda birden fazla kullanıcı:** Serbest; her kullanıcı kendi çalışmasını açar, çalışmalar yalıtılmış ve sadece sahibine görünür.
- **İki kişinin yayın yapması:** Yayın tek seferde bir kişiyle sınırlı. Kullanıcı çalışmasını açtığından bu yana başka biri yayın yaptıysa uyarı ve fark gösterilir; onaylarsa yayınlar.
- **Gece akışı ve açık çalışmalar:** Gün içinde 'bu gece silinecek' uyarısı; gece akışında açık çalışmalar önce salt okunur olur, sonra silinir.
- **Gün içinde yeni veri yükleme:** Açık çalışmaları etkilemez; yayında eski veri uyarısı.
- **Aynı kaydı iki kişinin değiştirmesi:** İlk kaydeden kazanır; ikinci kişi 'kayıt sen açtıktan sonra değişti' uyarısı alır ve güncel hali görür. Kilitleme yok.
- **Parametreyi varsayılan yapma:** Aynı kural; her değişiklik kim ve ne zamanla kaydedilir.
- Durum: Taslak; sonra değerlendirilecek.
