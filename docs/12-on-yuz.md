# Ön yüz ve kabuk

Arayüzün teknolojisi ve bütün ekranların içine oturduğu kabuk: kenar menü, bağlam çubuğu, çalışma alanı. Arayüz prensipleri (U-1…U-23, docs/04) burada da bağlayıcıdır. Kararlar: K-81 (teknoloji), K-82 (kabuk ve menü).

## Teknoloji (K-81)

- **React** (TypeScript). Arayüz geliştirme bilgisayarında bir kez derlenir, düz dosyalar (HTML, JS, CSS, font, ikon) olarak pakete girer; müşteride IIS bu dosyaları sunar, `/api` arka uca gider (K-74). Müşteride Node.js ya da başka kurulum gerekmez.
- **İnternetsiz:** CDN, dış font, dış ikon, çevrimiçi servis yok. Fontlar (Instrument Sans, JetBrains Mono) ve ikonlar pakete gömülüdür. İnternetsizlik bekçisi (`tests/test_offline.py`) arayüz kaynaklarını ve derlenmiş dosyaları da tarar.
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
- **İkonlar ve fontlar:** Lucide (ISC); Instrument Sans ve JetBrains Mono (OFL-1.1) `@fontsource` paketlerinden derlemeye gömülür. Dış adres yoktur; `tests/test_offline.py` kaynakları ve derlenmiş `dist`'i tarar.
- **Kullanıcı (A-36):** Oturum 2.1'de gelir. O zamana kadar kullanıcı Id'si adres çubuğunda `?user_id=3` ile bir kez verilir ve tarayıcıda hatırlanır; verilmezse 0. İş göstergesi bu kullanıcının işlerini gösterir.
- **Hatırlanan tercihler:** Açık gruplar, menünün daraltılmış hâli ve yazı boyutu (U-23) tarayıcıda tutulur; 2.3'te kullanıcı ayarına taşınır.
- **Bağlam çubuğu:**
  - **Veri versiyonu:** `GET /api/data-versions/current` → "Veri v35 · 27.10.2026 12:20". Veri yoksa "Veri yüklenmedi"; API cevap vermiyorsa "API'ye ulaşılamıyor"; API veritabanına bağlanamıyorsa (503) "Veritabanına ulaşılamıyor".
  - **İş göstergesi:** `GET /api/jobs` + `WS /api/ws`. Bağlantı koparsa 10 sn'de yeniden bağlanır, arada 30 sn'de bir sorgular (fonksiyon 48).
  - **Senaryo, plan versiyonu, dönem:** pasif yer tutucu (8.1).
- **Boş ekranlar:** Her ekran "Bu ekran X adımında gelecek" yazan sayfayla açılır. Adım, `catalog.ts`'teki GELISTIRME_ADIMLARI eşlemesinden gelir.
- **Kurulum:** Derlenmiş dosyalar paketin `web\` klasörüyle IIS köküne kopyalanır. `web.config` `/api`'yi API'ye yönlendirir, diğer adresleri `index.html`'e verir (tek sayfa uygulaması) ve `.woff2` türünü tanır (docs/10).

## Durum

| Parça | Durum |
|---|---|
| Teknoloji ve kabuk kararları | karar verildi (K-81, K-82) |
| Kabuk | uygulandı (1.1) |
