# Ön yüz ve kabuk

Arayüzün teknolojisi ve bütün ekranların içine oturduğu kabuk: kenar menü, bağlam çubuğu, çalışma alanı. Arayüz prensipleri (U-1…U-24, docs/04) burada da bağlayıcıdır. Kararlar: K-81 (teknoloji), K-82 (kabuk ve menü).

## Teknoloji (K-81)

- **React** (TypeScript). Arayüz geliştirme bilgisayarında bir kez derlenir, düz dosyalar (HTML, JS, CSS, font, ikon) olarak pakete girer; müşteride IIS bu dosyaları sunar, `/api` arka uca gider (K-74). Müşteride Node.js ya da başka kurulum gerekmez.
- **İnternetsiz:** CDN, dış font, dış ikon, çevrimiçi servis yok. Fontlar (Instrument Sans; sayılar için Inter, K-86) ve ikonlar pakete gömülüdür. İnternetsizlik bekçisi (`tests/test_offline.py`) arayüz kaynaklarını ve derlenmiş dosyaları da tarar.
- **Tablo bileşeni bizim:** Tablolar hazır bir tablo ürünü değil, TanStack Table (MIT, yalnız altyapı) üzerine kendi bileşenimizdir. Alan ekle/çıkar, çoklu sıralama, filtre tipleri, kayıtlı görünüm, kolon düzeni, gruplama, Excel'e aktarım ve Excel'den yapıştırma (U-6…U-16) bu bileşende toplanır; lisans kısıtı yoktur. Filtre, sıralama ve gruplama sunucuda yapılır (U-21).
- **Metinler tek yerde:** Bütün arayüz metinleri tek bir sözlük dosyasındadır. Faz 1'de yalnız Türkçe; sayı ve tarih Türkçe biçimde (U-19).
- **Tema ve ekran:** Faz 1'de yalnız açık tema. En küçük hedef ekran 1366×768; büyük ekranda alan doldurulur (U-22).

## Kabuk (K-82)

### Kenar menü

Ekranlar menüde gruplar hâlinde durur; ekranlar arası geçiş için üstte sekme kullanılmaz. Ekran sayısı arttıkça liste aşağı uzar, hiçbir ekran gizlenmez.

| Grup | Ekranlar |
|---|---|
| (grup yok) | Ana sayfa (01) |
| Planlama | Senaryolar (08) · Çalışma (09) ve altında çalışmanın ekranları (10–19) |
| Takip | Uyarılar (20) · Raporlar (21) ve altında raporlar |
| Veri | Veri yükleme (02) · Veri kuralları (04) · Validasyon kuralları (27) · Ana veri (03) · Veri kalitesi (05) (K-142) |
| Parametre | Parametre setleri (06) · Gece senaryoları (07) |
| Yönetim | Kullanıcılar (22) · Entegrasyon (23) · Sistem sağlığı (24) · Denetim izi (26) · Sistem ayarları (25) |

- **Çalışmanın ekranları** (doluluk, ürün / kaynak / sipariş bazlı planlama, Gantt, malzeme, öneriler, pegging, termin ve olaylar, yayın) menüde Çalışma'nın altında listelenir (K-43). Çalışma açık değilken gri ve kapalıdır; üzerine gelince "Önce bir çalışma açın" yazar.
- **Raporlar** menüde Raporlar'ın altında listelenir; çoğaldıkça alt gruplara ayrılır (ör. Raporlar › Kapasite › Kaynak doluluk).
- **En çok iki seviye:** grup › ekran ya da grup › alt grup › ekran. Daha derin seviye açılmaz.
- **Gruplar açılır kapanır;** hangi grupların açık bırakıldığı kullanıcı için hatırlanır.
- **Menüde arama:** Menünün üstünde arama kutusu; ekran adıyla bulur. Klavyeden Ctrl+K ile açılır.
- **Daraltılmış menü (U-22):** Yalnız ikonlar kalır; üzerine gelince ekranın adı görünür. Grup ikonuna basınca menü açılmaz; ikonun yanında küçük bir liste açılır ve grubun ekranlarını gösterir. Bir ekran seçilince o ekran açılır, liste kapanır, menü kapalı kalır. Ana sayfa gibi tek ekranlı ikonlar (grupta görünen tek ekran kaldıysa o grup da) doğrudan ekrana gider. Liste dışına tıklama ve Esc listeyi kapatır. Klavye: ok tuşları, Home ve End listede gezer, Enter seçer, Esc odağı ikona döndürür. Yetkisiz ekranlar listede de görünmez; çalışma kapalıyken çalışmanın ekranları kilitli görünür, seçilemez. Menünün açık ya da daraltılmış hâli hatırlanır.
- **Rol bazlı görünürlük (2.2, K-100):** okuma yetkisi olmayan ekran menüde görünmez, içi boş kalan grup da görünmez; menü araması da yalnız görünen ekranlarda arar. Ayrıntı "Yetki (2.2)" bölümünde.

### Bağlam çubuğu (U-17)

Her ekranın üstünde aynı yerde:

- senaryo, plan versiyonu ve dönem (bucket) seçimi; çalışma açıksa çalışmanın adı ve çalışma aksiyonları (ör. çalışmayı kapat);
- veri versiyonu;
- arka planda süren işlerin göstergesi (iş kuyruğu bildirimleri, K-69);
- kullanıcı menüsü: ad ve rol, yazı boyutu (U-23), şifre değiştir, çıkış (2.1).

- **Akış çipi (5.6, K-163):** bağlam çubuğunda "İş yok" çipinin yanında, yalnız son akış durduğunda ya da başlamadığında: kırmızı "Gece akışı durdu · 02:14 · Veri çekme" ya da "Gece akışı başlamadı · 02:00". Tıklayınca akışın adı, adımı ve nedeni; "Kapat" o kullanıcı için kapatır, System owner ve Admin için "Akış geçmişi" bağlantısı. Yeni bir durma ilk görüldüğünde bildirim de çıkar. End user'da yok.
- **Akış sürerken (K-163):** Veri çek, Veri yükle, Veri aktarma menüsü, Excel'den yükle, ham veri temizliği ve kural kaydetme düğmeleri pasif; ipucu "Zamanlanmış akış sürüyor: Hafta içi kısmi (başlama 02:00). Bitince yeniden deneyin."

### Çalışma alanı

Kenar menü ve bağlam çubuğu dışında kalan alanın tamamı ekranındır; ana tablo bu alanı doldurur (U-22).

## Kenar menü görünüşü (K-84, seçenek F)

Kenar menü açık indigodur. Değerler yalnız `app/web/src/styles/tokens.css`'te durur; kodda renk ve ölçü sabit yazılmaz. Kontrastlar menü zeminine göredir.

| Öğe | Değer | Kontrast |
|---|---|---|
| Menü zemini · sağ çizgi | #EEF0FB · 1 px #DCE0F7 | — |
| Genişlik | standart yazı boyutunda 256 px; yazı boyutuyla ölçeklenir (bu projede 1rem = yazı boyutu, standart 13 px → 19,69rem); daraltılmış hâl değişmez | — |
| Logo yazısı | #1E2257 | — |
| İç boşluk | menü içeriği kenardan 10 px içeride (0,7692rem), öğelerin kendi iç boşluğu 8 px (0,6154rem); standart boyutta, yazı boyutuyla ölçeklenir. Seçili öğenin zemini kenarlara değmez. Logo, arama kutusunun içi, grup başlıkları ve ekran ikonları aynı sol hizadadır (10 + 8 px) | — |
| Grup başlığı (PLANLAMA, TAKİP…) | #4A5180, 11 px (standart boyutta; yazı boyutuyla ölçeklenir), yarı kalın, harf aralığı 0.08em | 6,7:1 |
| Ekran adı · ikonu | #1F2329 · #5A6290 | 13,9:1 · 5,2:1 |
| Çalışma altındaki ekranlar · ikonu | #3F444D · #6E76A8 | 8,6:1 · 3,8:1 |
| Seçili ekran | zemin #4F5BD5, yazı ve ikon beyaz, yarı kalın | 5,5:1 |
| Üzerine gelince | zemin #DCE0F7 | ekran adı 12,1:1 |
| Çalışma kapalıyken ekranlar | yazı #5A6290 ve sağda küçük kilit ikonu; soluk görünüm yok (U-3) | 5,2:1 |
| Arama kutusu | beyaz, çerçeve #DCE0F7 | — |
| Çalışma alanı | zemin #F7F8FA; kart ve tablolar beyaz | — |

Daraltılmış menü ve yandan açılan alt panel aynı renkleri kullanır.

## Uygulama (1.1, K-83)

- **Yer:** `app/web/` (Vite + React + TypeScript). Paket sürümleri `package-lock.json`'da sabit; `node_modules` ve `dist` git dışı.
- **Komutlar** (`app/web` klasöründe): `npm ci` (paketleri kur) · `npm run dev` (http://localhost:5173; `/api` ve `/api/ws` 127.0.0.1:8000'deki API'ye gider) · `npm test` · `npm run build` (`dist/`).
- **Menünün tek tanımı:** `src/screens/catalog.ts`. Her ekranın numarası, adı, adresi, grubu, ikonu, geleceği geliştirme adımı ve tek satırlık tanımı buradadır. Yeni ekran önce buraya eklenir.
- **Metinler:** `src/i18n/tr.ts`; sayı ve tarih biçimi `src/format.ts` (U-19).
- **İkonlar ve fontlar:** Lucide (ISC); Instrument Sans ve Inter (OFL-1.1) `@fontsource` paketlerinden derlemeye gömülür. Dış adres yoktur; `tests/test_offline.py` kaynakları ve derlenmiş `dist`'i tarar.
- **Kullanıcı (K-97):** oturumdan gelir (2.1). Adreslerde kullanıcı Id'si yoktur; iş göstergesi oturumdaki kullanıcının işlerini gösterir. Kişisel tercihlerin tarayıcıdaki anahtarı kullanıcı Id'sine göredir.
- **Hatırlanan tercihler:** Açık gruplar ve menünün daraltılmış hâli tarayıcıda tutulur. Yazı boyutu (U-23) kullanıcı kaydındadır (`AppUser.FontSize`; 2.3): her bilgisayarda aynı gelir, tarayıcıda eski bir değer varsa bir kez sunucuya taşınır, çıkışta giriş sayfası standart boyuta döner.
- **Bağlam çubuğu:**
  - **Veri versiyonu:** `GET /api/data-versions/current` → "Veri v35 · 27.10.2026 12:20". Veri yoksa "Veri yüklenmedi"; API cevap vermiyorsa "Sunucuya ulaşılamıyor"; API veritabanına bağlanamıyorsa (503) "Veriye ulaşılamıyor".
  - **İş göstergesi:** `GET /api/jobs` + `WS /api/ws`. Bağlantı koparsa 10 sn'de yeniden bağlanır, arada 30 sn'de bir sorgular (fonksiyon 48); kullanıcı "Bildirimler gecikebilir." görür, bağlıyken metin yoktur.
  - **Senaryo, plan versiyonu, dönem:** pasif yer tutucu (8.1).
- **Boş ekranlar:** Her ekran "Bu ekran X adımında gelecek" yazan sayfayla açılır. Adım, `catalog.ts`'teki GELISTIRME_ADIMLARI eşlemesinden gelir.
- **Kurulum:** Derlenmiş dosyalar paketin `web\` klasörüyle IIS köküne kopyalanır. `web.config` `/api`'yi API'ye yönlendirir, diğer adresleri `index.html`'e verir (tek sayfa uygulaması) ve `.woff2` türünü tanır (docs/10).

## Stil sistemi (1.2, K-85)

Bütün değerler `app/web/src/styles/tokens.css`'te durur; bileşen ve kabuk CSS'leri yalnız bu değişkenleri kullanır. Renkler docs/04'teki palet (K-30) ve mockup'lardan (m23-0291, m23-0292, m24e-0310, m24f-0539, m24f-0757) alınmıştır. Kontrastlar testte hesaplanır (`tokens.test.ts`).

### Durum renkleri (U-2, U-3)

Durum renkleri yalnız durum gösterir; her zaman bir yazı, değer ya da ikonla birlikte kullanılır.

| Durum | Ana | Zemin | Yazı (kontrast) | Çerçeve | Nerede |
|---|---|---|---|---|---|
| Risk (hardal) | #D9A521 | #F7EBC4 (rozet) · #FBF3DA (kutu) | #6B5200 (6,2:1) | #EDD99A | "yüksek" rozeti, risk uyarısı |
| Aşırı yük, gecikme, hata (kiremit) | #C8452F | #F7DCD5 (rozet) · #FBEDE8 (kutu) | #9A2E1A (5,8:1) · #8A3612 (7,0:1) | #EBCAB8 | "kritik", "süre aşımı", hata kutusu, form hatası |
| Olumlu (yeşil) | #2F8F5B | #DDF0E4 (rozet) · #E8F5EC (kutu) | #254D3B (8,0:1) | #BFE0CB | "tamam" rozeti, olumlu uyarı |
| Bilgi (indigo, U-4) | #4F5BD5 | #EEF0FB | #1E2257 (13,0:1) | #DCE0F7 | bilgi rozeti ve kutusu |

**Geri alınamaz işlem butonu** kiremit zemin üzerinde beyazdır (4,8:1). U-2'nin tek istisnasıdır; yalnız onay penceresinde kullanılır.

### Doluluk skalası

| Seviye | Varsayılan aralık | Zemin | Yazı (kontrast) |
|---|---|---|---|
| Düşük | < %40 | #F4F5F7 | #5A606B (5,8:1) |
| Normal | %40–69 | #EEF0FB | #1F2329 (13,9:1) |
| Yüksek | %70–89 | #C5CBF2 | #1E2257 (9,3:1) |
| Risk | %90–100 | #F2D98E | #5C4300 (6,7:1) |
| Aşırı yük | > %100 | #F4CFC4 (açık kiremit, risk hücresiyle aynı yoğunlukta) | #8A3612 kalın (5,6:1) |

- Her hücrede değer yazar (U-3); renk yalnız vurgudur.
- Eşik, ekranda yazan yuvarlanmış değere uygulanır: %100,4 "%100" yazar ve risk rengindedir.
- **Eşikler parametredir:** `occupancyLevel(değer, eşikler)` ve doluluk bileşenleri eşikleri alır. Varsayılan `{ low: 40, normal: 70, risk: 90, over: 100 }`. Eşikler müşteriye göre değişir; 7.5'te uyarı eşikleri ekranından (WarningDefinition, fonksiyon 26) gelir.
- Lejant metinleri eşiklerden üretilir.

### Grafik serileri (U-5)

Sıra sabittir: indigo #4F5BD5 · petrol #2E7D7A · hardal #B8860B · kurşun #5A606B · erik #8E4585 · kahve #8A6440. Her seri beyaz zeminde en az 3:1 (testte). Grafikteki hardal, durum rengi hardalın (#D9A521, beyazda 2,2:1) koyu tonudur. Kiremit ve kırmızı hiçbir zaman seri olmaz; durum rengidir.

### Yazı ve boşluk

1rem kullanıcının yazı boyutudur (U-23: 12 / 13 / 14 / 16 px); bütün ölçüler rem olduğundan arayüz birlikte ölçeklenir. Değerler standart 13 px'e göre seçilmiştir.

| Ad | rem | Standartta | Kullanım |
|---|---|---|---|
| xs | 0,846 | 11 px | grup başlığı, küçük etiket |
| sm | 0,923 | 12 px | yardım metni, lejant |
| base | 1 | 13 px | gövde, tablo |
| md | 1,077 | 14 px | kart başlığı |
| lg | 1,231 | 16 px | bölüm başlığı |
| xl | 1,385 | 18 px | kart başlığı (büyük) |
| 2xl | 1,846 | 24 px | sayfa başlığı |
| kpi | 2,154 | 28 px | KPI değeri |

Boşluk ölçeği `--space-1…8`: 4, 8, 12, 16, 20, 24, 32 px karşılığı. Metin Instrument Sans (`--font-sans`); sayı, tarih ve kod Inter, rakamlar eşit genişlikte (`--font-num`, `tabular-nums`; K-86).

### Ortak bileşenler (`app/web/src/ui/`)

| Bileşen | Çeşitler |
|---|---|
| Button | birincil, ikincil, sessiz, geri alınamaz işlem; normal ve küçük; ikonlu; pasif; meşgul |
| Badge | nötr, bilgi, olumlu, risk, kritik; her zaman yazılı |
| Card, KpiCard | başlık, alt başlık, aksiyon; KPI değeri mono, durum varsa durum renginde |
| Form alanları | metin, sayı (Türkçe 1.234,5; sağa yaslı), tarih (gg.aa.yyyy elle ya da takvimden: alanın yanındaki düğme Türkçe ay ve gün adlarıyla takvim açar, hafta Pazartesi başlar, her satırda ISO hafta numarası H44, "Bugün" düğmesi; ok tuşları gün/hafta, Page Up/Down ay, Enter seçer, Esc kapatır; görünür alana sığacak şekilde açılır; kendi bileşenimiz; giriş kutusu, takvim düğmesi hariç, her yazı boyutunda "gg.aa.yyyy"nin tamamını gösterecek en küçük genişlikte: `ch` cinsinden, eşit genişlikte rakamlarla), seçim, çok satırlı metin, onay kutusu, seçenek grubu, segment, arama; etiket, yardım, zorunlu işareti, hata. Etiket alanın üstünde, her alanda aynı boşlukla (seçenek grubu ve segment dahil). Arama kutusu tek satır yüksekliğinde, genişliği içeriğine göre. Çerçeve #B4B9C2 (mockup değeri) |
| Alert | bilgi, olumlu, risk, hata; her tonun ikonu var; hata `role="alert"` |
| TopStrip | ekranın üstündeki ayar ve filtre alanlarının şeridi (bkz. Üst şerit) |
| MasterDetail | ana tablo ve detay kartı: kapatma, ayraç, ilk dolu sekme (bkz. Ana–detay düzeni) |
| OccupancyCell, OccupancyLegend | doluluk hücresi ve lejantı (eşikler parametre) |
| Hücre işaretleri | manuel değişiklik (indigo çerçeve, U-4/U-16), dondurulmuş (gri ve kilit), kümülatif eksik (kiremit yazı); tablo 1.3'te kullanır |

**Örnek sayfa:** `/stil`. Menüde yoktur (ekran değildir); bütün renkleri ve bileşenleri dört yazı boyutunda gösterir; geliştirme ve gözden geçirme içindir.

## Tablo bileşeni (1.3, K-87)

Bütün ekranların tabloları tek bileşendir (`app/web/src/table/`), TanStack Table (manuel mod) ve TanStack Virtual üzerine kurulur. Veri liste sorgu sözleşmesiyle sunucudan gelir (docs/08, K-87); filtre ve sıralama sunucuda yapılır (U-21).

| Parça | Davranış |
|---|---|
| Araç çubuğu (U-22) | Tablonun hemen üstünde, sayfa zemininde tek satır: kendi zemini, çerçevesi ve ayırıcı çizgisi yoktur; tabloyla arasında 0.5rem boşluk (`--table-toolbar-gap`). Tablo çerçevesi başlık satırından başlar. Solda yalnız görünüm seçici (görünür etiketi yok; ekran okuyucu için adı "Görünüm"), görünüm "⋯" düğmesi ve soluk kayıt sayacı "120 / 840" (filtreli / toplam, Türkçe biçim; U-12). Kaydet ve Farklı kaydet "⋯" menüsündedir; "⋯" düğmesinin hemen yanında dışarıda "Sıralamayı temizle" ikonu (sıralama yokken pasif, ipucu "Sıralamayı temizle"); araç çubuğunda ayrı Kaydet düğmesi ya da "Kaydedilmedi" yazısı yoktur (1.6 demosu). Sağda Grupla, gruplama açıkken daralt / aç ikon grubu ve "Alanlar (9/34)" ve "Excel'e aktar". Dar ekranda (1366) tek satıra sığar; sığmazsa sağ grup alt satıra sarar. Filtre etiketleri, "Filtreleri temizle" ve gruplama bilgisi ("Malzeme seviyesi › Malzeme grubu ile gruplu") yalnız aktif filtre ya da gruplama varken araç çubuğunun altında, yine sayfa zemininde tek ince satırda durur, sığmazsa sarar; hiçbiri yoksa bu satır yoktur |
| Alan paneli (U-6) | Listenin bütün alanları aramalı onay kutusu listesinde; kapalı alanlar buradan geri açılır. "Varsayılana dön". En az bir alan açık kalır. Kapatılan alan sunucudan istenmez. Panel en az 18rem genişliktedir; etiket tek satır, sığmazsa üç noktayla kısalır, tam adı ipucunda (title) |
| Sıralama (U-7) | Başlığa tıklama: artan → azalan → kapalı (tek sıralama). Shift+tıklama: ek sıralama ekler ya da yönünü değiştirir. Birden çok sıralamada başlıkta ok ve öncelik numarası (1, 2…) görünür |
| Filtre (U-8) | Başlıktaki filtre ikonundan alan tipine göre menü: metin (içerir, içermez, eşittir, ile başlar), liste (aramalı çoklu seçim, değer sayılarıyla), sayı (aralık, eşit, büyük, küçük; Türkçe giriş), tarih (aralık; "Bu hafta", "Sonraki 4 hafta"). Uygula ve Temizle. Filtreli alanın ikonu indigo (U-4); filtreler birlikte uygulanır. Menü görünür alana sığacak şekilde açılır: sağ kenara yakınsa sola, altta yer yoksa yukarı. Menü içeriğine göre genişler: iki tarih (ya da iki sayı) alanı yan yana sığar, ekrana sığmazsa alt alta dizilir |
| Gövde | Sanal kaydırma: yalnız görünen satırlar ve kısa bir tampon çizilir; veri parça parça, kaydırdıkça gelir (parça büyüklüğü SystemSetting `ListChunkSize`, varsayılan 100, en çok 500; tablo bir istekte bundan fazlasını istemez). Başlık yapışkan. Sayılar sağa yaslı, Inter, eşit genişlikte rakamlar (K-86); tarih gg.aa.yyyy; evet/hayır yazıyla; boş hücre boş |
| Durumlar | Yükleniyor; hata ve "Yeniden dene"; eşleşme yoksa "Eşleşen kayıt yok" ve "Filtreleri temizle" |

- **Ekrana sığar (U-22):** tablo çalışma alanının kalan yüksekliğini doldurur, kaydırma tablonun içindedir; kenar menü daraltılınca tablo genişler.
- **Ondalık (K-88):** sayı kolonunun ondalığı liste tanımında yazılır (`app/api/lists/`), veritabanı ölçeğinden alınmaz. Gün, adet gibi tam sayı anlamındaki alanlar ondalıksız (0); oran ve yüzde 1. Yüzde gösterim (`ListDefinition.percent`, K-113): `Material.ScrapRatio`, `BOM.ScrapRatio` ve `MaterialSupplier.QuotaRatio` veride oran kalır (0,05), ekranda ve Excel'de yüzde gösterilir (%5,00); filtre ve koşullu biçim değeri de yüzde olarak girilir, saklanan değer orandır. Miktar kolonları "ondalık birimden" işaretlenir: her satır malzemenin temel biriminin ondalığıyla yazılır (UnitOfMeasure.Decimals; ADET 0, KG 3, M 2, SAAT 2, bilinmeyen 2), aynı kolonda birimi farklı satırlar farklı ondalık taşıyabilir. Ondalığı belirsiz sayı alanı testte hata verir.
- **Satır yüksekliği (U-23):** `--row-height: 2.1538rem` (standart 13 px'te 28 px); yazı boyutuyla birlikte ölçeklenir.
- **Tercihler:** alanlar, sıra, genişlik, sabitleme, sıralama, filtre ve gruplama kayıtlı görünümde saklanır (1.4, K-89).
- **Performans hedefi:** 50.000 satırlık tabloda filtre + iki alanlı sıralama + ilk 100 satır + iki sayım geliştirme makinesinde ortanca 300 ms altında (`tests/test_lists_perf.py`); 100.000 satırda DOM'da yalnız görünen satırlar ve en çok 2 × 10 tampon satır bulunur; aynı parça ikinci kez istenmez.
- **Deneme sayfası:** `/tablo` menüde yer almaz; sentetik malzeme listesini gösterir (geliştirme ve gözden geçirme içindir). Gerçek malzeme ekranı 6.1'de.
- 1.4'te: kayıtlı görünüm, kolon sürükleme ve sabitleme, gruplama, aktif filtre etiketleri, boş değer filtresi. 1.5'te: Excel'e aktarım ve yapıştırma.

### Üst şerit (K-139; 3.4 ikinci demo)

Ekranın üstündeki ayar ve filtre alanları (Entegrasyon'da SQL kaynağı; Validasyon kuralları'nda Tablo, Hata eşiği, Yeni kural) her ekranda aynı biçimdedir ve ortak bileşenle kurulur (`ui/TopStrip`):

- **Kart:** beyaz kart (kart çerçevesi ve köşesi) içinde tek satır; sığmazsa alt satıra sarar.
- **Etiket:** alanın solunda, aynı satırda; alan, düğme ve yazılar dikeyde ortalı, alan ve düğme aynı yükseklikte (normal boy). Yardım metni yok.
- **Boşluk:** şerit ile tablo araç çubuğu (görünüm seçimi, Grupla, Alanlar) arasında her ekranda aynı boşluk, `--top-strip-gap` (`--space-3`). Hata bandı şeridin üstündedir, şerit ile araç çubuğu arasına girmez.
- **Tek tanım:** ekrana özel şerit sınıfı yazılmaz (stil testi denetler). İlerleme ya da rol gösteren şeritler ve durum kartları (Sistem sağlığı servis şeridi) bu kurala girmez.

## Ana–detay düzeni (5.5b demosu, K-161; `ui/MasterDetail`)

Tablodan seçilen kaydın ayrıntısı aynı ekranda gösterilecekse standart budur; ilk kullanan Dünden bugüne (ekran 28), sonraki ekranlar da bunu kullanır.

- **Yerleşim:** üstte ana tablo, satır seçilince altta detay kartı; kart başlığında kaydın adı ve sekmeler. İkisi de ekrana sığar, kaydırma tablo içindedir.
- **Kapatma:** kart başlığının sağında ×, Esc ve seçili satıra yeniden tıklamak. Açık pencere, çekmece ya da açılır menü varken Esc önce onu kapatır. Kapanınca ana tablo bütün yüksekliği alır, seçim işareti kalkar.
- **Boyut:** iki tablo arasında sürüklenebilir ayraç; klavyeyle yukarı ve aşağı ok. Her tablo en az yüksekliğin %15'ini korur. Oran kullanıcının tarayıcısında ekran başına hatırlanır. Ayraca çift tıklayınca ilk orana döner.
- **Büyütme:** kart başlığında × düğmesinin solunda "Büyüt": ana tablo seçili kaydın adını gösteren tek satırlık şeride iner (filtre, sıralama ve seçim korunur), kart ekranın neredeyse tamamını alır; aynı düğme ("Küçült") önceki orana döndürür. Kart kapanınca büyütme sona erer, kaydedilmez.
- **Sekme:** kart kayıt olan ilk sekmeyle açılır (hepsi 0 ise ilk sekme); başka satır seçilince aynı kural yeniden uygulanır. Sekme adında kayıt sayısı yazar.
- **Kullanım:** `useMasterDetail` seçimi ve sekmeyi tutar (`toggle(kayıt)`, `close()`); `MasterDetail` yerleşimi, ayracı ve kapatmayı çizer; ana tablo `DataTable` `selectedRowId` ile seçili satırı gösterir.

## Görünüm (1.4, K-89, K-90)

| Parça | Davranış |
|---|---|
| Görünüm seçici (U-9) | Araç çubuğunun solunda, görünür etiketsiz (ekran okuyucu adı "Görünüm"): "Standart" (liste tanımından, silinemez), kendi görünümlerim, paylaşılanlar (sahibin adıyla); varsayılanın yanında "(varsayılan)". Yanında "⋯" menüsü, sırasıyla: Kaydet, Farklı kaydet (ad, "Paylaşılan"), Varsayılan yap (varsayılansa "Varsayılanı kaldır"), Sil. "⋯"nin hemen yanında "Sıralamayı temizle" ikonu. Kaydedilmemiş değişiklik varken "⋯" düğmesinin köşesinde küçük indigo nokta (ipucu "Kaydedilmemiş değişiklik") ve menüde "Kaydet" koyu; değişiklik yoksa Kaydet pasif. Sahibi olunmayan görünümde (paylaşılan, Standart) Kaydet ve Sil pasif; sıralama yoksa Sıralamayı temizle ikonu pasif. "Filtreleri temizle" filtre etiketlerinin yanında kalır. Değişiklik varken başka görünüme geçince onay penceresi |
| Kolon menüsü | Başlıktaki "⋯": sola / sağa taşı, buraya kadar sabitle / sabitlemeyi kaldır, bu alana göre grupla, sayı alanında "Ara toplam ▸", alanı gizle, genişliği sıfırla. Başlıktaki filtre ve "⋯" ikonları yalnız başlığın üzerine gelince ya da başlık klavyeyle odaklanınca görünür (başlık metninin üstüne biner, yer kaplamaz); aktif filtresi olan kolonun filtre ikonu her zaman görünür (indigo) |
| Genişlik (U-10) | Başlığın sağ kenarındaki tutamak sürüklenir; tutamaktayken ← / → 0,5rem. En az 4rem. Genişlik rem olarak saklanır, yazı boyutuyla ölçeklenir (U-23) |
| Sıra (U-10) | Başlık sürüklenip bırakılır, bırakılacak yer indigo çizgiyle görünür; başlıktayken Alt+← / Alt+→ |
| Sabitleme (U-10) | İlk N kolon yatay kaydırmada yerinde kalır; sabit bölgenin sağında ince çizgi |
| Gruplama (U-11) | "Grupla ▾" ile bir ya da birden çok alan (sıralı). Tablonun üstünde "Malzeme seviyesi › Malzeme grubu ile gruplu". Gruplar açık başlar (mockup m24f-0720). Gruplama açıkken "Grupla" düğmesinin yanında ikonlu küçük düğme grubu: "Tümünü daralt", "Tümünü aç" ve iki ya da daha çok düzeyde "1. düzeye kadar aç" (adları ipucunda). Grup satırına tıklayınca ya da Enter / boşlukla o grup, Alt+tıklama ya da Alt+Enter ile o düzeydeki bütün gruplar birlikte açılır ya da kapanır. Grup başlığı düzeye göre girintili, 1. düzey adı kalın (600), alt düzeyler yarı kalın (500); veri satırlarının ilk görünen hücresi en alt grubun adıyla aynı hizada başlar; ad, satır sayısı, ara toplamlar kendi kolonlarında (türü ipucunda); birimleri farklı miktarda "—", ipucunda "birimler farklı" |
| Ara toplam (K-90) | Sayı kolonunun "⋯" menüsünde "Ara toplam" alt menüsü: Toplam · Ortalama (boşlar hariç) · Ortalama (sıfırlar hariç) · Ağırlıklı ortalama (ağırlık alanı seçilir) · En küçük · En büyük · Sayı (dolu satır) · Yok. Varsayılan liste tanımından; seçim görünümle kaydedilir. Ortalamalar kolonun ondalığından bir fazla, sayı ondalıksız yazılır. Grup satırında değerin önünde tür soluk ve küçük yazar: Σ (toplam), ort. (ortalama), ağ. ort. (ağırlıklı ortalama), en az, en çok, n (sayı) |
| Tablo renkleri (K-85) | Bütün tablolar için ortak, değerler tokens.css'te (`--table-*`). Başlık #DCE0F7 zemin, #1E2257 yarı kalın yazı, alt çizgi #C5CBF2; tablonun dış çerçevesi #C5CBF2. Grup satırları başlıktan belirgin açık: 1. düzey #ECEEF7 (alt çizgi #E1E4EE, kalın yazı), 2. ve alt düzeyler #F7F8FC (orta kalın). Veri satırı beyaz; satıra tıklayınca seçilir (#EEF0FB), üzerine gelince #F4F5FB; grup satırı üzerine gelince değişmez. Yazı her zeminde en az 4,5:1 (testte) |
| Aktif filtreler (U-12) | Sayacın yanında her filtre bir etiket ("Malzeme adı: içerir 'mil'", "Güvenlik stoğu: 10–100", "Son değişiklik: bu hafta", "Malzeme grubu: Çubuk, Levha +2", "…: boş"). Etikete tıklayınca filtre menüsü açılır; × tek tıkla kaldırır |
| Boş (U-13) | Metin, sayı ve tarih menüsünde "Boş olanlar"; liste menüsünde değerlerin başında "(Boş)" ve sayısı |

- **Açılır menülerin yerleşimi:** bütün açılır menüler (filtre, kolon menüsü ve alt menüleri, görünüm menüsü, Grupla, Alanlar, takvim) tek ortak yardımcıyla (`ui/popover.ts`) ekranda sabit konumda açılır ve görünür alana sığar: altta yer yoksa yukarı, sağ kenara yakınsa sola. Alt menü (ör. "Ara toplam") ana menünün sağında, yer yoksa solunda açılır. Pencere boyu değişince ya da kaydırılınca yeniden yerleşir.
- **Göreli tarih filtresi** görünümde göreli saklanır; görünüm başka gün açılınca o günün haftasına göre çalışır.
- **Şirket Standart'ı (K-162):** "Standart" seçiliyken "Kaydet" System owner ve Admin için açılır; kaydettikleri Standart, kendi varsayılanını seçmemiş herkese açılır. Görünüm menüsünde "Ürün Standart'ına döndür" (onaylı) liste tanımındaki Standart'a döndürür. Sonradan listeye eklenen alan ürünün varsayılanına göre gelir; Standart'ta gizlenmiş alan gizli kalır. Öteki rollerde Standart'ta "Kaydet" pasif, ipucu "Standart görünümü yalnız System owner ve Admin değiştirebilir."
- **Yetki (2.2):** görünüm kaydetmek listeyi okuma yetkisiyle olur, End user dahil (K-99). Görünümü yalnız sahibi değiştirir ve siler; başkasının görünümünde "Kaydet" ve "Sil" pasif, ipucu "Bu görünümü yalnız sahibi değiştirebilir; sizin için salt okunur." Paylaşılan görünümü herkes görür. Admin'in bir görünümü herkes ya da bir rol için varsayılan yapması sonraya bırakıldı (GELISTIRME).
- **Performans hedefi:** 50.000 satırda iki alanla gruplama + filtre + ara toplamlar ortanca 300 ms altında; 1.000 grup ve 100.000 satırda DOM'da yalnız görünen satırlar ve tampon.

## Dışa aktarım (1.5, K-91, K-92)

- **Excel'e aktar** (araç çubuğunun sağında) kapsam penceresini açar (mockup m24f-0724, 1.5 demosunda sadeleşti): yalnız Satırlar Filtrelenmiş (n) / Tümü (toplam) (filtre yoksa yalnız Tümü); Sütunlar Görünen (k) / Tümü; dosya adı önizlemesi; Vazgeç / İndir. Gruplama ve ara toplamlar ekrandaki gibi her zaman, Bilgi sayfası her dosyada gelir; seçenek olarak sorulmaz. Pencerede bilgi kutusu ve "ize yazılır" notu yoktur; iz yine yazılır (K-91). "Dosya sisteme geri yüklenemez" bilgisi yükleme ekranında (3.2) verilir. Yalnız duruma bağlı mesajlar çıkar: arka planda hazırlanacaksa, üst sınır aşıldıysa, sunucu hata verdiyse.
- **Anlık:** 10.000 satıra kadar (`ExportSyncMaxRows`) dosya hemen iner (hedef 3 sn altı).
- **Arka plan:** üstünde pencere "Arka planda hazırlanır; hazır olunca bildirim gelir" der; ilerleme iş göstergesinde görünür, bitince sağ altta "Malzeme listesi hazır · 4,8 MB · İndir" bildirimi (mockup m24f-0725). 500.000 satırı aşarsa İndir kapalı, "filtreyi daraltın". Dosya 24 saat indirilebilir; bildirim kapansa ya da sayfa yenilense de iş göstergesinin listesinde biten aktarımın yanında "İndir" vardır. Pencerenin eşikleri ve adları kolonlar cevabındaki `export`'tan gelir (docs/08).
- **Biçim tanımı (K-92):** ekran ve Excel aynı kolon tanımından biçimlenir. Renkler tokens.css'te; derlemede `design-tokens.json` üretilir (`npm run build` öncesi `scripts/tokens.mjs`), Excel yazıcısı renkleri oradan okur. Hücre biçimi `CellFormat {zemin, yazı rengi, kalın, ikon}`; koşullu biçimler (U-24, 1.6) aynı yapıdan geçer.

## Koşullu biçimlendirme (1.6, U-24, K-95, K-96)

- **Kolon menüsü (⋯), kuralların tek girişi (1.6 demosu):** "Koşullu biçim ekle…" (pencere bu kolonla açılır) ve "Biçimi yönet…" (bütün kuralların listesi, kolon başlığının yanında açılır). Araç çubuğunda biçim düğmesi yoktur.
- **Kural listesi:** satırda sıra, aktif anahtarı, alan, koşul özeti (filtre etiketiyle aynı metin; alan karşılaştırmasında "Stok < Güvenlik stoğu"), biçim örneği, düzenle, sil (satır sayısı gösterilmez). "Her zaman" koşulu "Kolon biçimi" diye görünür. Sıra sürükle-bırak ya da Alt+↑/↓ ile değişir (mockup m24f-0413'teki düzen); aynı biçim özelliğinde üstteki kural geçerlidir (listede açıklama satırı yok). Gizli kolonun kuralı soluk, "alan gizli". "Kural ekle".
- **Kural penceresi:** alan; koşul (operatör tipe göre, her tipte en sonda "Her zaman": koşulsuz kolon biçimi, değer alanı gizlenir, kolonun bütün hücrelerine boşlar dahil uygulanır; değer girişleri filtre menüsündekilerle aynı bileşenler; tarih yazılırken geçerli olur olmaz işlenir); sayı ve tarihte büyük, küçük ve eşitte "Değer / Alan" seçimi (alanlar yalnız aynı tipte, gizliler dahil); sayı alanı karşılaştırmasında "Boşları 0 say" (varsayılan açık); biçim: zemin, yazı rengi, kalın, ikon (8 ikon ve "yok"; nokta, uyarı, bayrak ve yıldız içi dolu, uyarı ünlemsiz üçgen) ve ikon rengi; önizleme hücresi. Biçim seçilmeden Kaydet kapalı.
- **Renk seçici:** Ürün renkleri, Tema renkleri (10 × 6), Standart renkler, Renksiz (ikon renginde "Varsayılan"), "Diğer renk: #rrggbb". Ok tuşlarıyla ızgarada gezilir. Değerler tokens.css'te (`--cf-*`).
- **Okunurluk:** yazı rengi "Renksiz" ise zemine göre okunur yazı rengi kendiliğinden (K-96); uyarı yok.
- **Hücrede:** zemin, yazı rengi, kalın; ikon kendi renginde, değerin ters tarafında (sayıda hücrenin başında, metin ve tarihte sonunda; değerlerin hizası bozulmaz). Değer her zaman yazar; hücrenin ipucu tutan kuralları yazar (U-3).
- **Seçili satır:** satırın tamamında aynı işaret: solda indigo şerit ve satır tonu; kural zemini olan hücrelerin zemini korunur.
- **Akış:** kurallar sunucuda değerlendirilir (K-95); kural değişince ekrandaki satırlar yeni parça gelene kadar kalır, yer tutucu görünmez.
- **Çizim:** veri satırı belleğe alınır (memo): kaydırmada yalnız yeni giren ya da değişen satırlar çizilir, kural biçimi ve ipucu yalnız onlarda kurulur; kural özetleri kural başına bir kez, sayı biçimlendiricisi ondalık sayısı başına bir kez kurulur. Tarayıcıda ölçüm (1.6 demosu, bu geliştirme bilgisayarı, görünmez Chrome, 5 tekrarın ortancası; derleme / geliştirme modu): ilk satır kuralsız 293 / 647 ms, 5 kuralla 337 / 760 ms; kaydırma adımı kuralsız 21 / 90 ms, kurallı 21 / 92 ms. Geliştirme modu React'ın denetimleri nedeniyle birkaç kat yavaştır; kurulumdaki uygulama derlemedir.

## Giriş ve oturum (2.1, K-97, K-98; fonksiyon 89)

- **Yer:** `app/web/src/auth/`. Giriş sayfası `/giris` kabuğun dışındadır; diğer bütün adresler oturum kapısından (`AuthGate`) geçer. Açılışta `GET /api/auth/me`: oturum yoksa giriş sayfasına (dönülecek adres `?next=` ile, yalnız uygulama içi adres), şifre değişikliği bekliyorsa zorunlu şifre penceresine, değilse kabuğa.
- **Giriş sayfası (mockup m24f-0738):** logo, "Kullanıcı adı", "Şifre", tek "Giriş" düğmesi. Hata şifre alanının altında: "Kullanıcı adı ya da şifre hatalı. 2 deneme hakkınız kaldı." (hesabın varlığı belli olmaz); kilitli ve kapalı hesapta sunucunun mesajı. Hatadan sonra şifre alanı boşalır. Not satırı "Şifrenizi unuttuysanız yöneticinize başvurun."; altta "v0.17.1" (sürüm `/api/health`'ten; kurum adı lisansla, 2.4). Çıkış ya da zaman aşımından sonra üstte bilgi kutusu.
- **Zorunlu şifre değişikliği (mockup m24f-0739):** bulanık arka plan üstünde "Şifrenizi belirleyin"; alt başlık sebep. Alanlar: Geçici şifre (süre dolduysa "Mevcut şifre"), Yeni şifre, Yeni şifre (tekrar). "Şifre kuralları" listesi yazarken ✓ / ✗: en az N karakter, harf ve rakam (politikada açıksa), kullanıcı adını içermez (Türkçe harf duyarsız), son N şifreden farklı (sunucuda özetle denetlenir: kaydedene kadar nötr, sunucu reddederse ✗), tekrar alanı eşleşiyor. Eşleşmezse alan altında "Şifreler henüz eşleşmiyor.". "Kaydet ve devam et" kurallar sağlanınca açılır. Vazgeç yok, Esc kapatmaz.
- **Kullanıcı menüsü:** ad soyad, kullanıcı adı ve rol; yazı boyutu; "Şifre değiştir" (aynı pencere, Vazgeç'li; başarıda "Şifreniz değiştirildi."); "Çıkış".
- **Hareketsizlik (mockup m24f-0740):** yalnız kullanıcı girdisi etkinliktir (tuş, tıklama, tekerlek, dokunma; fare gezdirmek değil). Girdi olunca sunucuya en çok dakikada bir etkinlik bildirilir (`POST /api/auth/activity`); süre bu bildirimden ölçülür, böylece arayüz ve sunucu aynı anda doldurur. Arka plan istekleri (iş göstergesi, veri versiyonu) oturumu uzatmaz. Sekmeler etkinliği, girişi ve çıkışı paylaşır (BroadcastChannel). Sınırdan `SessionWarningMinutes` önce (25. dakika) pencere: "Oturumunuz kapanmak üzere", "25 dakikadır işlem yapılmadı", büyük geri sayım (Inter); "Şimdi çıkış yap" · "Devam et" (birincil, odakta). Pencere açılmadan sunucuya sorulur: başka sekmede çalışılıyorsa açılmaz. Pencere açıkken yalnız "Devam et" süreyi uzatır; Esc kapatmaz. Süre dolunca giriş sayfası ve "30 dakika işlem yapılmadığı için oturumunuz kapandı.". Kaydedilmemiş planlama taslağı kutusu taslak tutan ilk ekranla gelir.
- **Oturum biterse:** herhangi bir istek 401 (`not_authenticated`, `session_expired`) dönerse ya da WebSocket 4401 ile kapanırsa (çıkış, şifre değişikliği, zaman aşımı) giriş sayfasına dönülür; WebSocket yeniden bağlanmaz.
- **Testlerde** uygulama başlangıç kullanıcısıyla açılır (`App initialMe`); gerçek açılışta kullanıcı her zaman sunucudan gelir.

## Yetki (2.2, K-99, K-100; fonksiyon 90)

- **Kaynak:** rolün yetkileri `GET /api/auth/me`'nin `permissions` alanında (`{fonksiyon: full | owner | self | read | none}`); arayüz yalnız görünürlüğü ayarlar, güvenlik sunucudadır. Yardımcılar `app/web/src/auth/permissions.ts`: `can(me, fn, "read" | "write")`, gereken rol ve ipucu metni.
- **Menü:** her ekranın bir fonksiyonu vardır (`catalog.ts`): Ana sayfa 82 · Senaryolar 42 · Çalışma 43 (çalışmanın ekranları onunla) · Uyarılar 83 · Raporlar 85 · Veri yükleme 03 · Ana veri 10 · Veri kuralları 16 · Veri kalitesi 20 · Parametre setleri 22 · Gece senaryoları 27 · Kullanıcılar 88 · Entegrasyon 91 · Sistem sağlığı 94 · Denetim izi 98 · Sistem ayarları 96. Okuma yetkisi olmayan ekran gizlenir.

  | Rol | Menü |
  |---|---|
  | System owner | hepsi |
  | Admin | Sistem ayarları dışında hepsi |
  | Key user | Yönetim grubunda yalnız Denetim izi (kendi kayıtları), ötekiler hepsi |
  | End user | Ana sayfa · Takip · Veri (Veri yükleme dışında) |

- **Yetkisiz ekran:** adres çubuğundan açılırsa "Bu ekranı açma yetkiniz yok" sayfası: gereken rol, kimden isteneceği, Ana sayfa bağlantısı.
- **Rol:** kullanıcı menüsünde ad ve rolle görünür; bağlam çubuğunda ayrı rol etiketi ya da mockup m24f-0744'teki gibi şerit yoktur (demo kararı, 2.2).

- **Pasif düğme:** bağlam dışı düğme gizlenmez, pasifleşir ve nedenini araç ipucunda söyler (`Button disabledReason`), ör. "Bu işlem için Admin yetkisi gerekir. Yetki için yöneticinize başvurun."
- **403 tek yerde:** sunucu `forbidden` ya da sahiplik 403'ü dönerse (`*_not_owner`) sağ altta bildirim sunucunun mesajını gösterir. Giriş akışının 403'leri (kilit, kapalı hesap, şifre değişikliği, köken) buraya girmez.
- **Rol değişikliği:** sunucu her cevapta `X-Smartchain-Role` gönderir; oturumdakinden farklıysa `me` yeniden alınır, menü ve kullanıcı menüsündeki rol değişir; oturum kapanmaz.
- **İş paneli (fonksiyon 48, 93):** sıradaki işte "İptal" (kendi işi herkese açık, tek tık). "Herkesin işleri" seçeneği Admin ve System owner'da açıktır; başkasının sıradaki işinde "İptal" neden penceresini açar. Diğer rollerde seçenek pasif ve ipuçludur. Herkesin işlerinde işin sahibi yazar. Panelde ve bildirimde işin özeti yazar. İşi başkası iptal edince sahibine sağ altta bildirim gider, panelde neden yazar.

## Arayüz metni

Bütün ekranlarda geçerlidir (2.3 demosu):

- Tek cümle yetiyorsa tek cümle.
- Teknik ifade yok ("istek", "oturum sonlanır" gibi).
- Kendini anlatan etiket yok ("yıkıcı işlem", "onay gerekli" gibi).
- Öneri ve tavsiye yok.
- Kullanıcının bilmesi gereken sonucu söyle, mekanizmayı değil.

Mevcut ekranlar 2.3c'de bu kurala getirildi. `tests/test_ui_text.py` bilinen yasak kalıpları arayüz ve sunucu mesajlarında arar; liste sınırlıdır, kuralın yerine geçmez. Geliştirme sayfaları (`/stil`, `/tablo`), geçici yerler ve sistem yöneticisine yazılan sağlık mesajları kapsam dışıdır.

## Kullanıcılar (2.3, K-101; ekran 22, fonksiyon 88)

Başlık "Kullanıcılar", sağda "+ Kullanıcı ekle"; altında ekranı dolduran ortak tablo (U-22): ad soyad, kullanıcı adı, rol, durum (rozetle), son giriş. Sıralama, filtre, gruplama, görünüm, koşullu biçim ve Excel öteki tablolardaki gibidir. Tablo bileşeninin üç seçeneği bu ekranla geldi: `cellRender` (hücreyi rozet gibi çizer; Excel düz metin kalır), `rowMenu` (sağda sabit "⋯" kolonu; alan paneline, görünüme ve Excel'e girmez), `reloadKey` (işlemden sonra yeniler).

**Satır menüsü:** açılınca kayıt sunucudan okunur (`GET /api/users/{id}`). Rol değiştir · Ad soyad düzelt · Şifre sıfırla · Kilidi aç · Kapat ya da Geri aç. İzin yoksa öğe pasiftir, nedeni ipucunda ve ekran okuyucuda; neden sunucudan gelir.

| Pencere | İçerik |
|---|---|
| Kullanıcı ekle | Ad soyad; kullanıcı adı ("Sonradan değiştirilemez.", yazarken küçülür; çakışmada alan altında hata ve tıklanabilir öneri); rol ve altında seçilen rolün kapsamı. System owner seçeneği yalnız System owner'da |
| Geçici şifre | Başlık "Kullanıcı oluşturuldu" ya da "Şifre sıfırlandı"; alt satır ad soyad · kullanıcı adı · rol. Şifre ve Kopyala (basınca düğmede "Kopyalandı"; HTTPS dışında da çalışır). "Bu şifre bir daha gösterilmez." Tek düğme Kapat; Esc kapatmaz, şifre pencere kapanınca bellekten silinir |
| Rol değiştir | Alt satır ad soyad · kullanıcı adı; yeni rol ve altında kapsamı; System owner seçilirse "Bu hesap bir daha kapatılamaz, rolü değiştirilemez." |
| Ad soyad düzelt | Alt satır kullanıcı adı; tek alan |
| Şifre sıfırla | "<Ad soyad> için yeni geçici şifre üretilecek. Mevcut şifre geçersiz olur." Vazgeç · Sıfırla |
| Kilidi aç | "<Ad soyad> yeniden giriş yapabilir." Vazgeç · Kilidi aç |
| Geri aç | "<Ad soyad> yeniden giriş yapabilir. Şifresi değişmez." Vazgeç · Geri aç |
| Kullanıcıyı kapat | "<Ad soyad> artık giriş yapamaz. Geçmiş kayıtları korunur; hesabı sonra geri açabilirsiniz." Açık oturumu varsa "Açık oturumu kapanır." Kiremit düğme: Vazgeç · Kapat |

**Rol kapsamı metinleri:**

| Rol | Kapsam |
|---|---|
| System owner | Bütün yetkiler. |
| Admin | Key user yetkileri ile kullanıcı ve sistem yönetimi. |
| Key user | Veri, parametre ve planlama. |
| End user | Verileri ve raporları görür, Excel'e aktarır; veri değiştiremez. |

**System owner gizli:** Admin bu hesapları listede görmez (K-101); Rol filtresinin değerleri de sunucudan geldiği için System owner çıkmaz.

**Rol değişince:** `me` yenilendiğinde rol farklıysa kabukta geçici bildirim: "Rolünüz Key user olarak değiştirildi."

## Sistem ayarları (2.4, K-104, K-105; ekran 25, fonksiyon 96)

Menüde ve başlıkta "Sistem ayarları", adres `/yonetim/sistem-ayarlari` (eski `/yonetim/system-owner` yeni adrese yönlenir); altında "Sürüm 0.18.0". Rol adı System owner olarak kalır; yetki mesajları değişmez. İki bölüm (`Segment`; K-82 ekranlar arası sekmeyi yasaklar, bu aynı ekranın bölümleri):

- **Veri sözlüğü:** ekranı dolduran ortak tablo: Tablo, Alan, Etiket, Sınıf, Değer önceliği, Manuel, Senaryo, Zorunlu, Varsayılan değer, Ek alan; "Açıklama" varsayılan gizlidir, Alanlar panelinden açılır, Excel'e kolon açıksa ya da Sütunlar "Tümü" seçilirse çıkar. Satır sonundaki "Düzenle" pencereyi açar: alt satır `Material · AdditionalText1`, onun altında tek satır salt okunur açıklama; pencere tablo düzenindedir (solda alan adı, sağda değer, satırlar ince çizgiyle ayrılır). Etiket düzenlenir, yardımında standart etiket, ek alanda "Boşsa alan listelerde görünmez."; öteki alanlar pasif form öğesidir: Sınıf ve Değer önceliği liste; Manuel, Senaryo ve Zorunlu onay kutusu; Varsayılan değer metin kutusu. 5.1'de bunlar yalnız aktifleşir. Kullanılan ek alanın etiketi silinirken: "Bu alan 3 görünümde ve 1 kuralda kullanılıyor. Etiket silinirse bu görünümlerde görünmez; etiket yeniden yazılınca geri gelir." ve kiremit "Etiketi sil".
- **Giriş ve oturum:** iki küme (Şifre; Giriş ve oturum), tablo düzeninde: solda alan adı, sağda içeriğe göre kısa sayı kutusu; form ekranı doldurmaz, sağdan taşmaz. Kayıtlı olmayan ayar varsayılan değeriyle görünür. Kaydet değişiklik yoksa pasif.

**Yetki matrisi (K-100; ekran 22):** Kullanıcılar başlığının yanında "Yetki matrisi"; en geniş pencere, hücrelerde satır kayması olmaz: 14 grup satırı × 4 rol (Tam, Sahibi, Kendi, Salt okunur, Yok), grup yalnız adıyla; altında "Excel'e aktar", Kapat. İstisnalar pencerede yoktur; Excel fonksiyon düzeyindedir ve onları gösterir (98 satır; No, Fonksiyon, Grup, dört rol).

## Sistem sağlığı (2.5, K-106, K-107; ekran 24, fonksiyon 94, 93)

Başlık "Sistem sağlığı", sağda sunucu saati. Sırayla:

- **Kartlar:** Kuyruk (bekleyen, en uzun bekleme), Aktif hesaplama (2 / 3), Son 7 gün hata (kaçı çözüldü; hata yoksa alt satır yok), Disk (doluluk, boş). Eşik aşımı kırmızı; motor çalışmıyorsa Kuyruk da kırmızı.
- **Servis şeridi:** tek satır dört kolon: Uygulama (sürüm), Motor (son kalp atışı, çalışan iş), Veritabanı (ms, "2 / 5 bağlantı", boyut), Anlık bildirim (bağlantı). Rozet: Çalışıyor, Yavaş, Yanıt vermiyor, Kapalı.
- **Bölümler** (`Segment`) ve ekranı dolduran ortak tablo:
  - **İş kuyruğu:** No, Tür, İş, Kanal, Kullanıcı, Durum, Sıra, İlerleme, Süre (sn), Deneme, İstek zamanı. Satır menüsü: Öne al, İptal et; izin yoksa pasif, neden ipucunda.
  - **Son çalışmalar:** No, Tür, İş, Kanal, Kullanıcı, Sonuç, Başlangıç, Bitiş, Süre (sn), Deneme, Hata, İptal nedeni.
  - **Hatalar:** Zaman, Bileşen, Hata, Sistem aksiyonu, Çözüldü, İş no, Takip no. Satırdan detay penceresi (`sc-field-rows`); System owner'da Teknik özet.
- **Canlılık:** `health` mesajıyla en sık 2 sn'de bir, 30 sn yedek yenileme. Sunucuya ya da veritabanına ulaşılamazsa uyarı ve "son bilgi" zamanı, son değerler kalır.

**İptal penceresi** (ekran 24 ve iş paneli, yalnız başkasının işinde): "İşi iptal et", alt satır "Malzeme listesi · 142.000 satır · Mert · sıra 2" (özeti olmayan işte tür), "İş sahibine bildirim gider.", Neden (zorunlu, en çok 200), kiremit "İptal et". Öne al pencere açmaz: "İş öne alındı · Malzeme listesi · 142.000 satır" (özeti olmayan işte numara).

**Sistem ayarları, üçüncü bölüm "Sistem sağlığı":** Disk uyarı eşiği (%), Kuyruk bekleme eşiği (dk), Hataların saklanma süresi (gün); Giriş ve oturum formuyla aynı düzen.

## Denetim izi (2.6, K-108; ekran 26, fonksiyon 98)

Başlık "Denetim izi", altında ekranı dolduran ortak tablo: Zaman, Kullanıcı, İşlem, Nesne tipi, Nesne, Eski değer, Yeni değer. En yeni üstte. Süzme kolon filtreleriyle: tarih, kullanıcı, işlem, nesne tipi listeleri ve Nesne'de metin araması. Ayar kayıtlarında Nesne, Sistem ayarları formundaki addır. Saatler yerel. "Eski değer (ham)" ve "Yeni değer (ham)" varsayılan gizli, Alanlar panelinden açılır. Excel ortaktır, aktarım ize yazılır; Eski ve Yeni değer ekrandaki gibi okunur.

**Detay penceresi:** satır sonundaki göz. Zaman (saniyeli), Kullanıcı, İşlem, Nesne tipi, Nesne; altında Alan · Eski · Yeni tablosu. "Bu nesnenin tüm geçmişi" aynı pencerede zaman sırasıyla listeler (son 200); satır o kaydı açar, "Geri" döner. Nesnesi olmayan kayıtta düğme pasif, nedeni ipucunda. Key user'da yalnız kendi kayıtları.

## Veri yükleme (3.1, K-110; ekran 02, fonksiyon 02)

İskelet. Başlık "Veri yükleme", altında ekranı dolduran ortak tablo: Tablo, Kategori, Açıklama (tek cümle, docs/03 kataloğundan), Sürüm, Toplam alan, Zorunlu alan, Yükleme sırası; Teknik tablo adı Alanlar panelinden. Satır menüsü: Şablonu indir (v1) tek tıkla; Şablon bilgisi penceresi (sürüm, dosya, toplam alan, zorunlu alanlar; İndir). Değeri olmayan satır görünmez. Boş bırakılınca ne olacağı Excel'in Açıklama sayfasında. Son Excel yüklemesini gör pasif, ipucunda geleceği adım. Son yükleme zamanı 3.2'de. Yükleme düğmeleri, sağ paneller ve sayı kolonları 5.5'te.

**Uygulama (3.3, K-130).** Yöntem ve Çekim kolonları hücre içi düzenlenir. Yöntem: seçim kutusu (Excel, SQL), yalnız System owner. Çekim: aç/kapa anahtarı, bütün satırlarda, Admin ve üstü; kapatırken küçük sebep kutusu zorunlu, açarken uyarı; kapalıyken ipucu üç satır: "Çekim kapalı", "Sebep: …", "Kişi · tarih". Key user salt okunur görür. Uyarı kolon değildir: tablo adının yanında sade sarı üçgen, metni ipucunda (view tanımlı değil, yeniden denetle). Satır menüsünde Excel'den yükle her zaman açık, yöntemi SQL ise Veri çek. Üstte Veri çek.

**Veri çek penceresi:** Yalnız SQL tabloları. Kolonlar Tablo, Kaynak, Durum; neden durum çipinin ipucunda. "Yeni veri yok" satırında "Yine de oku" seçimi. Düğmede sayı yazar ("3 tabloyu çek"). Okunacak satırda çip yok.

**Çekim sonucu penceresi:** Tablo, Kaynak, Okunan, Geçerli, Hatalı, Durum, Neden; okunmayan tabloda sayılar "—". Yalnız gerektiğinde küçük tonal mor düğme: bulgusu olan satırda "Bulgular", hatalı satırda "Yeniden dene"; satır yüksekliğini bozmaz. İlerleme iş panelinde ve pencerede, bitince bildirim.

### Excel'den yükle penceresi (3.3)

İki adım: Dosya → Ön kontrol (3.4, K-134); "Devam" pencereyi kapatır, doğrulama arka planda çalışır. Dosya alanı yüksek, ortada yükleme ikonu; dosya seçilince adı ve boyutu aynı alanda. Yükleme modu yan yana iki seçim kartı (`ui` `ChoiceCards`): kalın başlık, altında açıklama, seçili kart indigo çerçeve. Hatalı satır bandı: "2 satır hatalı, ham veriye alınmaz."; hepsi hatalıysa "Geçerli satır yok, ham veriye alınmaz."

### Entegrasyon (ekran 23, 3.3, K-130)

Üstte üst şerit (bkz. Üst şerit): SQL kaynağı alanı, Kaydet, Bağlantıyı test et, "Hesap: …" yan yana. Ortak tablo: Tablo, Yöntem (seçim kutusu, System owner), Kaynak (view adı, hücre içi; System owner), Alan uyumu, Son durum, Son okuma. Alan uyumu tek kolon: tam uyumda "13 / 13" yeşil, yalnız isteğe bağlı kolon eksikse sarı, zorunlu kolon eksikse kırmızı (tablo okunamaz); bağlantı testi penceresinde de aynı. Bağlantı testinin özeti hizalı üç kolon: sabit genişlikte durum çipi, kontrol adı, ayrıntı. Satır menüsü: Önizleme (20 satır, satır bulgularıyla), View sürümleri. API kartı yok (11.5), Zamanlanmış işler kartı 5.6'da. Menüde Admin ve üstü görür.

### Tablo içi düzenleme (K-132)

Hücre düzenleyicileri `table/CellEditors.tsx`, ortak tablonun `cellRender`'ıyla kullanılır; taslak ve kayıt `table/useTableEdits.tsx`. Değişiklik anında kaydedilmez: tablonun sağ üstünde Kaydet ve Vazgeç çıkar, değişiklikler toplu ve tek işlemde kaydedilir, biri geçersizse hiçbiri yazılmaz. Vazgeç kaydedilmemişleri geri alır. Değişen hücre indigo çerçevelidir (U-4). Kaydedilmemiş değişiklikle ekrandan çıkılırsa ya da sayfa kapatılırsa uyarı çıkar. Seçim kutuları hep görünür. Veri yükleme, Entegrasyon ve sonraki bütün tablo içi düzenlemeler (6.x) bu kuralla çalışır.

### Bilgi bandı, durum çipi, ipucu (K-132)

- **Bilgi bandı:** Pencere ve kartlarda ekranın nasıl çalıştığını anlatan bant olmaz. Bant yalnız durum, uyarı ya da hata içindir; yapılan işin onayı ("sıraya girdi", "dosya hazırlanıyor") bant değildir, çip, iş paneli ya da bildirim gösterir (K-139). 3.4 taramasında kaldırılanlar: Validasyon kuralları "n tablonun doğrulaması sıraya girdi", çekmecede "Doğrulama sıraya girdi." ve "Dosya arka planda hazırlanıyor; bitince bildirim gelir.".
- **Durum çipleri:** Yeşil Alındı, Uyumlu, Geçti. Sarı Uyarılı, Tamamlanmadı. Kırmızı Hata, Hatalı, Valide edilemedi. Gri Atlandı, Yeni veri yok, Veri güncellemesi devam ediyor, Sırada. Süren iş (Kurallar çalışıyor, Valide ediliyor) nötr çip ve dönen gösterge. Validasyon sınıfı (Hata, Uyarı, Bilgi) saydam pastel çiptir (K-139). Okunacak durum değildir, çip olmaz.
- **İpucu:** Açıklama taşıyan ipucu `ui/Tooltip`'le; odakta da görünür, klavyeyle okunur.
- **Pencere tabloları:** `table/LocalTable.tsx`: ortak tablonun görünümü (renkli başlık, tek satır, sıralama), satırlar sunucu listesinden değil pencerenin verisinden gelir. Önizleme, Veri çek, Çekim sonucu, Bağlantı testi. **Tek satır kuralının istisnası:** uzun metin kolonları (Not, Neden, Sorun) gerektiğinde alt satıra kayar. Pencere tabloları pencereye sığar, yatay kaydırma gerekmez: kolon genişliği içerikten, uzun metin kolonu kalan genişliği alır. Sunucu listesi olan pencere tablosu (bulgular) ortak tablonun pencere kipindedir (`DataTable fit wrapFields`): sabitleme ve genişlik ayarı yok, satır yüksekliği ölçülür. Kolonu çok olan önizlemede (ör. Malzeme, 33 alan) yatay kaydırma kalır.
- **Sayı kartı (`KpiCard`):** yarı yükseklik; etiket üstte küçük, sayı altında; bütün ekranlarda aynı.
- **Düğmeler (K-131):** `primary` indigo, `secondary` tonal mor, `danger` kiremit çerçeve, `neutral` Vazgeç ve araç çubuğu, `ghost` sessiz.

### Validasyon çipi ve çekmece (3.4, K-134, K-139; ekran 02, fonksiyon 04)

Veri yükleme tablosunda "Validasyon" kolonu: tablo başına çip, sayıyla ("Uyarılı · 3"); çip düğmedir, tıklayınca çekmece açılır. Validasyonu hiç çalışmamış tabloda çip yok; çip her durumda tıklanır (Geçti dahil, K-143). Satır menüsünde "Veriyi gör" çekmeceyi Kayıtlar · Tüm satırlar ile açar, validasyonu hiç çalışmamış tabloda da. **Veri çek penceresi** (K-144, K-145): yatay kaydırmasız ve yüksek; "Yine de oku" kolonunda yalnız onay kutusu; kolon başlığındaki kutu bütün "Yeni veri yok" satırlarını seçer ya da kaldırır, bir kısmı seçiliyse kısmen seçili görünür. Tablo, kullanıcının çekim ve validasyon işleri bitince (tablolar arası iş dahil) kendiliğinden yenilenir: iş göstergesinin anlık bildirimi `smartchain:job` olayıyla ekrana iletilir; başkasının işleri süren çip varken periyodik yenilemeyle görünür. **Çekmece** (`ui/Drawer.tsx`, ortak bileşen): sağdan açılır, sayfanın üstünde durur, arkası karartılmaz, Esc ve kapatma düğmesiyle kapanır, odak içinde kalır; genişliği pencerenin yarısı, en az 640 px. Üstte başlık ("Validasyon · Malzeme" ve çip), altında son parti satırı (zaman · yöntem · kişi) ve güncel kayıt sayısı. Dört küçük sayı kartı: Hatalı satır, Uyarılı satır, Bilgilendirme satırı, Hata oranı (büyük "%0,97", altında küçük "eşik yok" ya da "eşik %0,50"); kontrol türü kırılımı yok. Segment: "Bulgular" kural bazındadır (pencere tablosu: Kural, Sınıf çipi, Satır sayısı; ağırdan hafife, çoktan aza; tablo düzeyi bulguda mesaj ve "—"); kural adı bağlantıdır, tıklayınca "Kayıtlar" o kurala süzülmüş açılır, üstte kaldırılabilir "Kural: …" çipi (süzme `RuleIds` alanıyla, kolonu görünmez). "Kayıtlar": ortak tablo, işlenmiş katmandan (K-140); üstte üç seçenek: Bulgulu satırlar (varsayılan) / Kuralla değişenler / Tüm satırlar (K-143). Bulgulu satırlar'da ilk kolonlar Sorun ve Sınıf, sonra Satır ve kaydın alanları; Kuralla değişenler ve Tüm satırlar'da Satır ve kaydın alanları, "Değiştiren kural", en sonda Sorun ve Sınıf (K-144). Teknik alanlar (kural numaraları, bayraklar) kolon değildir. Kuralla değişen hücrenin zemini açık lila (`--rule-trace-bg`), metin aynı; ipucu "Tesis bayrağı · Ham değer: boş"; yatay kaydırma. Sağ altta "Hatalı kayıtları indir" (ikincil) ve "Yeniden valide et" (ikincil; Key user ve üstü). Bildirim: "Validasyon bitti · Malzeme · Uyarılı · 3", "Sonucu aç" Veri yükleme ekranını açar ve çekmeceyi gösterir.

### İş paneli (K-69, K-139)

Kabuktaki iş göstergesine tıklayınca açılan panel kartlardan oluşur. Her iş iki satırlı kart: üstte kalın iş ve tablo ("Validasyon · Stok"); altta durum çipi (bitmiş validasyonda kırmızı Hatalı · 2, sarı Uyarılı · 3, yeşil Geçti; öteki durumlar gri, sürende dönen gösterge) ve saat; sağda kısa "Aç" (validasyonda çekmece, ön kontrolde pencere, çekimde sonuç penceresi; Excel aktarımında "İndir"). Bir çekim ve onun validasyonları (toplu çekim, `validation.group`) tek karttır: başlık "Veri çekme · 6 tablo · 15:41", altında özet ("2 Hatalı · 1 Uyarılı · 3 Geçti"; tablolar arası validasyon bittiyse tabloların onun sonundaki sonucu); başlığa tıklayınca tablo satırları açılır (tablo, çip, "Aç"), tablolar arası validasyon satırı en sonda. Panelde son 5 kart; altta "Tümünü gör" Sistem sağlığının iş listesine gider (yetkisi olana). Sıradaki işte "İptal" ve "Herkesin işleri" seçeneği (K-100) kalır.

### Validasyon kuralları (3.4, K-136, K-139; ekran 27, fonksiyon 100)

Veri menüsünde Veri kurallarından sonra, adres `/veri/validasyon-kurallari`. Üstte üst şerit (bkz. Üst şerit): tablo seçimi ("Tümü" ya da tablo), seçili tablonun hata eşiği (sayı, %) ve "Yeni kural" (birincil); "Tümü"de eşik ve Yeni kural pasif. Ortak tablo: Tablo, Kural (kullanıcı dilinde ad), Koşul (okunur cümle, alt satıra kayar), Sınıf, Mesaj, Tür (çip: Hazır nötr, Kullanıcı mor), Aktif (anahtar); Kod kolonu varsayılan görünümde gizli, Alanlar'dan açılır. Yapısal kontroller listede yok. **Sınıf** saydam pastel çiptir (Hata açık kırmızı, Uyarı açık sarı, Bilgi açık mavi-gri); yazma yetkisinde çip seçim kutusudur, tıklayınca seçenekler açılır. Satır menüsü: "Düzenle" (kullanıcı kuralı ve koşulu editörle ifade edilen hazır kural; ötekilerde pasif, ipucu "yalnız sınıf ve aktiflik değişir"), hazır kuralda "İlk hâline döndür" (onay penceresi), kullanıcı kuralında "Sil". Sınıf ve aktiflik K-132 ile toplu kaydedilir; kayıttan sonra "Yeniden valide et" önerisi bir onay penceresidir (değişen tablolar listelenir); kabul edilince bant çıkmaz, işler iş panelinde görünür. Key user salt okunur görür.

**Kural penceresi:** başlığın sağında Aktif anahtarı; Kural adı ve Mesaj yan yana; Sınıf üç parçalı seçim, seçili olan kendi pastel renginde; altında koşul editörü. Hazır kuralda alt satırda "İlk hâline döndür" (nötr düğme). Hazır kuralda yalnız değişen parçalar kaydedilir: yalnız sınıf ya da aktiflik değişirse kural "düzenlenmiş" sayılmaz.

**Koşul editörü** (`table/ConditionEditor.tsx`, ortak bileşen; veri kuralları da kullanır, 4.1): bölüm başlığı "Koşullar"; her grup "Koşul Grubu 1", "Koşul Grubu 2" başlıklı kart, kartlar arasında belirgin "VEYA" ayırıcı. Her koşul tek satır: solda ikinci satırdan itibaren küçük "ve", alan, operatör, küçük "Değer / Alan" anahtarı, değer kutusu (Alan seçiliyse öteki alanın seçimi), kaldır düğmesi; satır etiketleri yalnız ekran okuyucuda. Operatörler: =, ≠, >, <, ≥, ≤, İçerir, İle başlar, Listede, Boş, Boş değil; metin dışı alanda İçerir ve İle başlar yok; "Değer / Alan" anahtarı yalnız karşılaştırmalarda. Boş ve Boş değil seçilince değer kutusu ve anahtar gizlenir. Değer girişi alan tipine göre (sayı, tarih); değer kutusu her zaman serbest yazıdır, alanın değer listesi varsa değerler öneri olarak çıkar: staging ERP'nin dilindedir (ör. Type = "PLANT", K-143); Listede virgülle. "+ Koşul ekle" grubun içinde, "+ VEYA grubu ekle" en altta mor ikincil düğme. Okunur cümle satırı yoktur (cümle listede Koşul kolonundadır).

### Veri kuralları (4.1, K-140, K-141, K-142; ekran 04, fonksiyon 16, 18, 19)

Veri menüsünde Veri yüklemeden sonra, adres `/veri/veri-kurallari`; Validasyon kuralları ile aynı desende. Tablo kolonu görünür ve ilk kolondur; "Tümü"de liste Tablo, sonra Sıra'ya göre sıralıdır; Sıra her tabloda 1'den boşluksuzdur (K-144). Liste, "Kuralları yeniden uygula" işi bitince kendiliğinden yenilenir. Üstte üst şerit (bkz. Üst şerit): tablo seçimi ("Tümü" ya da tablo), "Yeni kural" (birincil; "Tümü"de pasif) ve "Kuralları yeniden uygula" (ikincil). Ortak tablo: Sıra, Kural, Koşul (okunur cümle, alt satıra kayar), Sonuç (okunur cümle), Seçenek, Aktif (anahtar), Durum (her zaman dolu: soluk yeşil "Çalıştı" ve ipucunda son çalışma zamanı, kırmızı "Çalışmadı" ve ipucunda neden, gri "Pasif" ve gri "Uygulanmadı"; K-145); "Tümü"de Tablo kolonu. Satır menüsü: "Düzenle", "Sil" (onay penceresi). Key user salt okunur görür.

**Sıra:** Sıra kolonu dar, başlık ve içerik (tutamak ve numara) sola hizalı; tablo seçiliyken satır sürüklenir (tutamak işarettir), satırın tamamı bırakma yeridir, hedef konum çizgiyle görünür (K-143). Sıra yalnız sürükle-bırakla değişir, klavyeyle taşıma yoktur (K-145). "Tümü"de tutamak pasif, ipucu "Sırayı değiştirmek için tablo seçin". Yeni sıra ve aktiflik taslaktır; tablonun sağ üstündeki Kaydet / Vazgeç ile toplu kaydedilir (K-132). Kayıttan sonra "Kurallar yeniden uygulansın mı?" onay penceresi (değişen tablolar listelenir); kabul edilince bant çıkmaz, iş iş panelinde görünür.

**Kural penceresi:** Validasyon kuralı penceresinin düzeni: başlığın sağında Aktif anahtarı; Kural adı ve Hedef alan yan yana; altında koşul editörü. Koşul editörünün altında **Sonuç** bölümü: dört parçalı seçim Değer / Alan / Formül / Boşalt. Değer'de hedef tipine göre giriş (koşul editörünün değer girişi; değer listesi olan alanda seçim kutusu, Smartchain değeri); Alan'da alan seçimi; Formül'de kaynak alan, operatör (sayıda + − × ÷, tarihte + gün, − gün) ve "Değer / Alan" anahtarıyla operand; Boşalt'ta ek giriş yok. Altında **Seçenek** iki parçalı: Yalnız boşsa / Her zaman; Boşalt'ta Her zaman ve pasif. Tip uyuşmazlığında alanın altında mesaj, Kaydet pasif.

**Hücre izi:** Validasyon çekmecesinin Kayıtlar görünümünde kuralın değiştirdiği hücrenin zemini açık lila (#F3EEFF, `--rule-trace-bg`), metin aynı; ipucu "Tesis bayrağı · Ham değer: boş" (K-144). Ortak tablonun hücre sınıfı (`cellClass`) ve sarmalayıcısıdır (`cellWrap`), Ana veri (6.x) de kullanır.

**Alanlar ve etiketler (K-144):** kural editörlerinde (veri ve validasyon) yalnız etiketi tanımlı ek alanlar listelenir, etiket adıyla; listedeki Koşul ve Sonuç metinleri güncel etiketle yazılır (etiket değişince yeniden üretilir).

## Durum

| Parça | Durum |
|---|---|
| Teknoloji ve kabuk kararları | karar verildi (K-81, K-82) |
| Kabuk | uygulandı (1.1) |
| Hücre içi düzenleme, Yöntem ve Çekim kolonları, Yeniden çek, ekran 23 (K-130) | uygulandı (3.3) |
| Stil sistemi ve ortak bileşenler | uygulandı (1.2) |
| Tablo bileşeni ve liste sorgu sözleşmesi | uygulandı (1.3) |
| Görünüm: kayıtlı görünüm, kolon düzeni, gruplama, filtre etiketleri, boş | uygulandı (1.4) |
| Dışa aktarım: Excel'e aktarım, kapsam penceresi, arka plan ve bildirim | uygulandı (1.5) |
| Excel yükleme penceresi (ekran 02, fonksiyon 03): Dosya, Ön kontrol (3.4'te iki adım); "Ön kontrol bitti" bildirimi ve "Sonucu aç"; tablonun sabit filtresi (`baseFilters`) | uygulandı (3.2) |
| Kolon başlığı ipucu: yalnız alanın açıklaması (veri sözlüğü ya da kolon notu); açıklama yoksa ipucu çıkmaz, kullanım metni yok (K-129) | uygulandı (3.2) |
| Koşullu biçimlendirme: kurallar, palet, okunurluk, ikon, Excel'e taşınma | uygulandı (1.6) |
| Giriş ve oturum: giriş sayfası, zorunlu şifre değişikliği, kullanıcı menüsü, hareketsizlik | uygulandı (2.1) |
| Arayüz metinleri kurala göre sadeleşti | uygulandı (2.3c) |
| Sistem ayarları: veri sözlüğü etiketi, şifre ve oturum ayarları; yetki matrisi | uygulandı (2.4) |
| Denetim izi: ortak tablo, detay, nesne geçmişi, Excel | uygulandı (2.6) |
| Sistem sağlığı: kartlar, servis şeridi, iş kuyruğu, son çalışmalar, hatalar; iptal nedeni, öne alma | uygulandı (2.5) |
| Kullanıcılar ekranı: liste, satır menüsü, pencereler, geçici şifre; yazı boyutu kullanıcı kaydında | uygulandı (2.3) |
| Yetki: role göre menü, yetkisiz ekran, pasif düğme ipucu, 403 bildirimi, iş panelinde iptal | uygulandı (2.2) |
| Validasyon çipi ve çekmece (`ui/Drawer`), bildirim; Validasyon kuralları (ekran 27), ortak koşul editörü (`table/ConditionEditor`); Excel'den yükle iki adım | uygulandı (3.4) |
| İş paneli kartları, çekim kartı; kural bazında Bulgular; pastel sınıf çipi; kural penceresi ve koşul editörünün yeni düzeni; bant taraması (K-139) | uygulandı (3.4) |
| Üst şerit standardı (`ui/TopStrip`): Entegrasyon ve Validasyon kuralları (K-139) | uygulandı (3.4) |
| Veri kuralları (ekran 04): liste, Sıra hücresinde sürükle-bırak ve Alt + ok (`DataTable` `rowOrder`), kural penceresi ve Sonuç bölümü, yeniden uygulama sorusu; çekmecede hücre izi (`DataTable` `cellWrap`); menü sırası (K-140…K-142) | uygulandı (4.1) |
| 4.1 demo bulguları: Veri yükleme kendiliğinden yenilenir (`smartchain:job`), Kayıtlar · Bulgulu / Kuralla değişenler / Tüm satırlar, "Veriyi gör", koşul değerinde öneri (datalist), satırdan sürükle-bırak (`DataTable` `rowProps`) (K-143) | uygulandı (4.1) |
| 4.1 ikinci ve üçüncü demo: sıra 1'den ve yalnız sürükle-bırak, Sıra kolonu dar ve sola hizalı (`DataTable` `fieldHints`), Durum her zaman dolu, lila hücre izi (`cellClass`), Kayıtlar kolon sırası seçeneğe göre, teknik kolonlar gizli (`filter_only`), ek alan etiketleri veri sözlüğünden, Veri çek penceresi ve başlıktaki toplu kutu (K-144, K-145) | uygulandı (4.1) |
| Ana–detay düzeni (`ui/MasterDetail`): Dünden bugüne'de kapatma, ayraç, ilk dolu sekme | uygulandı (5.5b, K-161) |
| Şirket Standart görünümü: Kaydet (System owner, Admin), Ürün Standart'ına döndür, sonradan eklenen alan | uygulandı (K-162) |
| Zamanlanmış akışlar: Entegrasyon'da liste, pencere, geçmiş; bağlam çubuğunda akış çipi; akış sürerken pasif düğmeler | uygulandı (5.6, K-163) |
