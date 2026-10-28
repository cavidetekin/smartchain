# Ön yüz ve kabuk

Arayüzün teknolojisi ve bütün ekranların içine oturduğu kabuk: kenar menü, bağlam çubuğu, çalışma alanı. Arayüz prensipleri (U-1…U-23, docs/04) burada da bağlayıcıdır. Kararlar: K-81 (teknoloji), K-82 (kabuk ve menü).

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
| Veri | Veri yükleme (02) · Ana veri (03) · Veri kuralları (04) · Veri kalitesi (05) |
| Parametre | Parametre setleri (06) · Gece senaryoları (07) |
| Yönetim | Kullanıcılar (22) · Entegrasyon (23) · Sistem sağlığı (24) · Sistem sahibi (25) |

- **Çalışmanın ekranları** (doluluk, ürün / kaynak / sipariş bazlı planlama, Gantt, malzeme, öneriler, pegging, termin ve olaylar, yayın) menüde Çalışma'nın altında listelenir (K-43). Çalışma açık değilken gri ve kapalıdır; üzerine gelince "Önce bir çalışma açın" yazar.
- **Raporlar** menüde Raporlar'ın altında listelenir; çoğaldıkça alt gruplara ayrılır (ör. Raporlar › Kapasite › Kaynak doluluk).
- **En çok iki seviye:** grup › ekran ya da grup › alt grup › ekran. Daha derin seviye açılmaz.
- **Gruplar açılır kapanır;** hangi grupların açık bırakıldığı kullanıcı için hatırlanır.
- **Menüde arama:** Menünün üstünde arama kutusu; ekran adıyla bulur. Klavyeden Ctrl+K ile açılır.
- **Daraltılmış menü (U-22):** Yalnız ikonlar kalır; üzerine gelince ekranın adı görünür. Bir grubun üzerine gelince alt ekranları yanda küçük bir panelde açılır. Menünün açık ya da daraltılmış hâli hatırlanır.
- **Rol bazlı görünürlük** 2.2'de eklenir (ör. end user yönetim grubunu görmez).

### Bağlam çubuğu (U-17)

Her ekranın üstünde aynı yerde:

- senaryo, plan versiyonu ve dönem (bucket) seçimi; çalışma açıksa çalışmanın adı ve çalışma aksiyonları (ör. çalışmayı kapat);
- veri versiyonu;
- arka planda süren işlerin göstergesi (iş kuyruğu bildirimleri, K-69);
- kullanıcı menüsü: yazı boyutu (U-23), çıkış (2.1).

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
- **Kullanıcı (A-36):** Oturum 2.1'de gelir. O zamana kadar kullanıcı Id'si adres çubuğunda `?user_id=3` ile bir kez verilir ve tarayıcıda hatırlanır; verilmezse 0. İş göstergesi bu kullanıcının işlerini gösterir.
- **Hatırlanan tercihler:** Açık gruplar, menünün daraltılmış hâli ve yazı boyutu (U-23) tarayıcıda tutulur; 2.3'te kullanıcı ayarına taşınır.
- **Bağlam çubuğu:**
  - **Veri versiyonu:** `GET /api/data-versions/current` → "Veri v35 · 27.10.2026 12:20". Veri yoksa "Veri yüklenmedi"; API cevap vermiyorsa "API'ye ulaşılamıyor"; API veritabanına bağlanamıyorsa (503) "Veritabanına ulaşılamıyor".
  - **İş göstergesi:** `GET /api/jobs` + `WS /api/ws`. Bağlantı koparsa 10 sn'de yeniden bağlanır, arada 30 sn'de bir sorgular (fonksiyon 48).
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
| OccupancyCell, OccupancyLegend | doluluk hücresi ve lejantı (eşikler parametre) |
| Hücre işaretleri | manuel değişiklik (indigo çerçeve, U-4/U-16), dondurulmuş (gri ve kilit), kümülatif eksik (kiremit yazı); tablo 1.3'te kullanır |

**Örnek sayfa:** `/stil`. Menüde yoktur (ekran değildir); bütün renkleri ve bileşenleri dört yazı boyutunda gösterir; geliştirme ve gözden geçirme içindir.

## Tablo bileşeni (1.3, K-87)

Bütün ekranların tabloları tek bileşendir (`app/web/src/table/`), TanStack Table (manuel mod) ve TanStack Virtual üzerine kurulur. Veri liste sorgu sözleşmesiyle sunucudan gelir (docs/08, K-87); filtre ve sıralama sunucuda yapılır (U-21).

| Parça | Davranış |
|---|---|
| Araç çubuğu (U-22) | Tablonun hemen üstünde, sayfa zemininde tek satır: kendi zemini, çerçevesi ve ayırıcı çizgisi yoktur; tabloyla arasında 0.5rem boşluk (`--table-toolbar-gap`). Tablo çerçevesi başlık satırından başlar. Solda görünüm seçici, "Kaydedilmedi", "Kaydet" / "Farklı kaydet" ve soluk kayıt sayacı "120 / 840" (filtreli / toplam, Türkçe biçim; U-12); sıralama varken "Sıralamayı temizle" ikonu. Sağda Grupla, gruplama açıkken daralt / aç ikon grubu ve "Alanlar (9/34)" (1.5'te Excel de buraya gelir). Dar ekranda (1366) tek satıra sığar; sığmazsa sağ grup alt satıra sarar. Filtre etiketleri, "Filtreleri temizle" ve gruplama bilgisi ("Malzeme seviyesi › Malzeme grubu ile gruplu") yalnız aktif filtre ya da gruplama varken araç çubuğunun altında, yine sayfa zemininde tek ince satırda durur, sığmazsa sarar; hiçbiri yoksa bu satır yoktur |
| Alan paneli (U-6) | Listenin bütün alanları aramalı onay kutusu listesinde; kapalı alanlar buradan geri açılır. "Varsayılana dön". En az bir alan açık kalır. Kapatılan alan sunucudan istenmez. Panel en az 18rem genişliktedir; etiket tek satır, sığmazsa üç noktayla kısalır, tam adı ipucunda (title) |
| Sıralama (U-7) | Başlığa tıklama: artan → azalan → kapalı (tek sıralama). Shift+tıklama: ek sıralama ekler ya da yönünü değiştirir. Birden çok sıralamada başlıkta ok ve öncelik numarası (1, 2…) görünür |
| Filtre (U-8) | Başlıktaki filtre ikonundan alan tipine göre menü: metin (içerir, içermez, eşittir, ile başlar), liste (aramalı çoklu seçim, değer sayılarıyla), sayı (aralık, eşit, büyük, küçük; Türkçe giriş), tarih (aralık; "Bu hafta", "Sonraki 4 hafta"). Uygula ve Temizle. Filtreli alanın ikonu indigo (U-4); filtreler birlikte uygulanır. Menü görünür alana sığacak şekilde açılır: sağ kenara yakınsa sola, altta yer yoksa yukarı. Menü içeriğine göre genişler: iki tarih (ya da iki sayı) alanı yan yana sığar, ekrana sığmazsa alt alta dizilir |
| Gövde | Sanal kaydırma: yalnız görünen satırlar ve kısa bir tampon çizilir; veri parça parça, kaydırdıkça gelir (parça büyüklüğü SystemSetting `ListChunkSize`, varsayılan 100, en çok 500; tablo bir istekte bundan fazlasını istemez). Başlık yapışkan. Sayılar sağa yaslı, Inter, eşit genişlikte rakamlar (K-86); tarih gg.aa.yyyy; evet/hayır yazıyla; boş hücre boş |
| Durumlar | Yükleniyor; hata ve "Yeniden dene"; eşleşme yoksa "Eşleşen kayıt yok" ve "Filtreleri temizle" |

- **Ekrana sığar (U-22):** tablo çalışma alanının kalan yüksekliğini doldurur, kaydırma tablonun içindedir; kenar menü daraltılınca tablo genişler.
- **Ondalık (K-88):** sayı kolonunun ondalığı liste tanımında yazılır (`app/api/lists/`), veritabanı ölçeğinden alınmaz. Gün, adet gibi tam sayı anlamındaki alanlar ondalıksız (0); oran ve yüzde 1. Miktar kolonları "ondalık birimden" işaretlenir: her satır malzemenin temel biriminin ondalığıyla yazılır (UnitOfMeasure.Decimals; ADET 0, KG 3, M 2, SAAT 2, bilinmeyen 2), aynı kolonda birimi farklı satırlar farklı ondalık taşıyabilir. Ondalığı belirsiz sayı alanı testte hata verir.
- **Satır yüksekliği (U-23):** `--row-height: 2.1538rem` (standart 13 px'te 28 px); yazı boyutuyla birlikte ölçeklenir.
- **Tercihler:** alanlar, sıra, genişlik, sabitleme, sıralama, filtre ve gruplama kayıtlı görünümde saklanır (1.4, K-89).
- **Performans hedefi:** 50.000 satırlık tabloda filtre + iki alanlı sıralama + ilk 100 satır + iki sayım geliştirme makinesinde ortanca 300 ms altında (`tests/test_lists_perf.py`); 100.000 satırda DOM'da yalnız görünen satırlar ve en çok 2 × 10 tampon satır bulunur; aynı parça ikinci kez istenmez.
- **Deneme sayfası:** `/tablo` menüde yer almaz; sentetik malzeme listesini gösterir (geliştirme ve gözden geçirme içindir). Gerçek malzeme ekranı 6.1'de.
- 1.4'te: kayıtlı görünüm, kolon sürükleme ve sabitleme, gruplama, aktif filtre etiketleri, boş değer filtresi. 1.5'te: Excel'e aktarım ve yapıştırma.

## Görünüm (1.4, K-89, K-90)

| Parça | Davranış |
|---|---|
| Görünüm seçici (U-9) | Araç çubuğunun solunda: "Standart" (liste tanımından, silinemez), kendi görünümlerim, paylaşılanlar (sahibin adıyla). Varsayılan görünümün yanında yıldız. Değişiklik varsa adın yanında "•" ve soluk "Kaydedilmedi" yazısı (ipucu "Kaydedilmemiş değişiklik"); "Kaydet" (yalnız sahibiysem) ve "Farklı kaydet" (ad, "Paylaşılan"). Menüde "Varsayılan yap" ve "Sil". Değişiklik varken başka görünüme geçince onay penceresi |
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
- **2.2'de:** paylaşılan görünümü kimin göreceğine rol kuralı; admin'in bir paylaşılan görünümü herkes ya da bir rol için varsayılan yapması. Şimdi yapılmaz.
- **Performans hedefi:** 50.000 satırda iki alanla gruplama + filtre + ara toplamlar ortanca 300 ms altında; 1.000 grup ve 100.000 satırda DOM'da yalnız görünen satırlar ve tampon.

## Durum

| Parça | Durum |
|---|---|
| Teknoloji ve kabuk kararları | karar verildi (K-81, K-82) |
| Kabuk | uygulandı (1.1) |
| Stil sistemi ve ortak bileşenler | uygulandı (1.2) |
| Tablo bileşeni ve liste sorgu sözleşmesi | uygulandı (1.3) |
| Görünüm: kayıtlı görünüm, kolon düzeni, gruplama, filtre etiketleri, boş | uygulandı (1.4) |
