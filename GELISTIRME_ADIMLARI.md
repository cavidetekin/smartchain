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
- [ ] 1.6 Koşullu biçimlendirme: kolon bazında kural, hücre ve yazı rengi (paletten), kalın yazı, ikon; görünümle kaydedilir ve Excel'e taşınır (U-24)

## Aşama 2 · Yönetim ve sistem

- [ ] 2.1 Giriş ve oturum (89)
- [ ] 2.2 Rol bazlı yetki altyapısı (90)
- [ ] 2.3 Kullanıcılar ekranı (22) · kullanıcı yönetimi (88) · kullanıcının yazı boyutu tercihinin saklanması (U-23)
- [ ] 2.4 Sistem sahibi ayarları (25) · veri sözlüğü ve ek alan etiketleri (96)
- [ ] 2.5 Sistem sağlığı (24) · sağlık (94), iş kuyruğu (93)
- [ ] 2.6 Denetim izi altyapısı (98)

## Aşama 3 · Veri alma (Extract)

- [ ] 3.1 Excel şablonu üretimi (02)
- [ ] 3.2 Excel yükleme → Staging (03)
- [ ] 3.3 SQL arayüz okuyucu → Staging (01), entegrasyon tanımı (91)
- [ ] 3.4 Yapısal doğrulama ve hata raporu (04): tip, zorunlu alan, tekrar eden anahtar

## Aşama 4 · Dönüştürme (Transform)

- [ ] 4.1 Veri kuralı uygulama, Staging üzerinde (19)
- [ ] 4.2 Veri kuralları ekranı (04): tanımlama, önizleme, sıralama, aç/kapa (16–18)
- [ ] 4.3 Aktarım filtresi (yeni, 99): tanım ve önizleme · yöntem açık (A-34)
- [ ] 4.4 Referans kontrolü ve kod→Id eşleme

## Aşama 5 · Yükleme (Load)

- [ ] 5.1 Değer önceliği (ERP, kural, elle, varsayılan) ve ERP değerinin saklanması (FieldValueSource)
- [ ] 5.2 Tam yükleme ve veri versiyonu (05, 07)
- [ ] 5.3 Kısmi yükleme (06)
- [ ] 5.4 Aktarım raporu, yükleme geçmişi, ham veri temizliği (08, 09)
- [ ] 5.5 Veri yükleme ekranı (02): ETL'in tamamı tek ekranda, adım adım durumuyla
- [ ] 5.6 Gece ETL akışı: zamanlanmış işler (92), Entegrasyon ekranı (23)

## Aşama 6 · Ana veri ve kalite

- [ ] 6.1 Ana veri ekranları (03, fn 10), sekme sekme:
  - [ ] Lokasyon
  - [ ] Kaynak
  - [ ] Malzeme
  - [ ] Ürün ağacı
  - [ ] Rota
  - [ ] Tedarikçi
  - [ ] Müşteri
  - [ ] Proje
  - [ ] Takvim
  - [ ] Vardiya
- [ ] 6.2 Değerin kaynağı (11), elle değer girme ve kaldırma (12, 13) · U-15, U-16: yapıştırma, toplu düzenleme, doğrulama, kaydetme
- [ ] 6.3 Değişiklik geçmişi (14)
- [ ] 6.4 Excel ile toplu düzeltme (15)
- [ ] 6.5 Veri kalitesi ekranı (05) · kontrol, düzeltme aksiyonu (20, 21)

## Aşama 7 · Parametreler

- [ ] 7.1 Parametre seti (22)
- [ ] 7.2 Zaman yapısı (23)
- [ ] 7.3 Kapasite parametreleri (24)
- [ ] 7.4 Alokasyon ve öncelik kuralı (25)
- [ ] 7.5 Uyarı eşikleri (26)
- [ ] 7.6 Gece senaryo tanımları ekranı (07) · tanım, sıra ve aç/kapa (27, 28)

## Aşama 8 · Plan ekranları (fikstürle)

- [ ] 8.0 Plan fikstürü: sentetik veri için elle hazırlanmış plan (planlı sipariş, doluluk, karşılama, pegging, uyarı, metrik)
- [ ] 8.1 Senaryolar (08) · karşılaştırma (42)
- [ ] 8.2 Çalışma (09) · açma, iz, geri alma, yeniden hesap düğmesi (sahte motorla), eş zamanlı sınır, bildirim, kapatma (43–49)
- [ ] 8.3 Kaynak doluluk raporu (10)
- [ ] 8.4 Ürün bazlı planlama (11) · 50, 51
- [ ] 8.5 Kaynak bazlı planlama (12) · 52–55
- [ ] 8.6 Sipariş bazlı planlama (13) · 56–58
- [ ] 8.7 Gantt (14) · 59, 60
- [ ] 8.8 Kilit ve dondurulmuş dönem (61, 63) · A-14 kararı
- [ ] 8.9 Malzeme planı (15) · 64, 65
- [ ] 8.10 Öneriler (16) · 66–69
- [ ] 8.11 Pegging ve gecikme nedeni (17) · 70, 71
- [ ] 8.12 Yayın (19) · 76–81

## Aşama 9 · Takip ve rapor

- [ ] 9.1 Ana sayfa (01) · 82
- [ ] 9.2 Uyarı iş listesi (20) · 83, 84
- [ ] 9.3 Rapor altyapısı (21) · 85, 87
- [ ] 9.4 Raporlar tek tek: 25. adımdaki gerçekleşme gerektirmeyen raporlar

## Aşama 10 · Motor

- [ ] 10.1 Ön hesap (29)
- [ ] 10.2 MRP patlatma (30)
- [ ] 10.3 Kurallı yerleştirme ve sezgisel (33)
- [ ] 10.4 Model kurma, LP (31)
- [ ] 10.5 Çözücü adaptörü ve süre bütçesi (32, 34)
  - [ ] Çalışan modelin LP dosyası, çözüm (solution) dosyası ve çözücü logu her plan hesabı için ayrı klasöre yazılır (K-77)
- [ ] 10.6 Son hesap (35)
- [ ] 10.7 Mevcut arz önerileri, uyarı üretme, metrikler, açıklama (36–39)
- [ ] 10.8 Sahte motorun yerine gerçek motor; plan fikstürü altın plan kabul testi olur
- [ ] 10.9 MILP
- [ ] 10.10 Anlık etki önizlemesi (62) ve yeniden hesap (46), gerçek motorla
- [ ] 10.11 Gece akışı ve yeniden çalıştırma (40, 41)
- [ ] 10.12 Termin sorgusu ve olay senaryoları ekranı (18) · 72–75

## Aşama 11 · Ürünleşme

- [ ] 11.1 Destek paketi (95)
- [ ] 11.2 Sürüm güncelleme (97)
- [ ] 11.3 Yedekleme, geri yükleme, lisans
- [ ] 11.4 Kurulum paketinin tamamı (27. adım)
- [ ] 11.5 API adaptörü (Faz 2)
- [ ] 11.6 Doğruluk raporları (A-22)

---

## Bekleyen kontroller

Adımı kapanmış ama elle denenmesi sonraya bırakılmış işler.

- [ ] 1.5 · Arka plan aktarımı: eşiği geçici düşür (`INSERT INTO adm.SystemSetting (SettingKey, Value) VALUES ('ExportSyncMaxRows', '50')`), /tablo'da "Hazırla", iş göstergesi ve "İndir" bildirimi, iş listesinden indirme; sonra ayarı sil (`DELETE FROM adm.SystemSetting WHERE SettingKey = 'ExportSyncMaxRows'`).
- [ ] 1.5 · Dışa aktarım izi: `SELECT TOP 5 * FROM adm.AuditLog ORDER BY 1 DESC` ile aktarımların "Dışa aktarım" kaydı olarak yazıldığını gör.
- [ ] 0.6 · Temiz makine (sanal makine) kurulum testi.

## Sonraya bırakılanlar

Konuşulup bilerek ertelenen işler. Sırası gelen adımın planında ele alınır.

- **1.6 Koşullu biçimlendirme:** çoklu koşul (VE/VEYA), renk skalası ve veri çubuğu, grup başlığı ve ara toplam satırlarına kural.
- **2.2 Roller:** admin'in bir paylaşılan görünümü ya da kural setini herkes veya bir rol için varsayılan yapması (K-89 notu).
- **Sentetik veri:** kilogram ve metre birimli malzemelere kesirli miktar (güvenlik stoğu, lot) verilmesi (docs/11 açık iş).
- **Performans:** gruplama sorgusundaki paralel plan ipucunun bir ayara bağlanması; çok kullanıcılı sunucuda işlemci kapışması (K-90).
- **Tablo görünümü:** ilk kolonun farklı renkte gösterilmesi fikri (denenmedi).

## Açık konular

- **A-34 · Aktarım filtresinin yöntemi.** Kapsam filtresi (pasif malzeme, kapalı sipariş, başka lokasyon gibi) nasıl tanımlanacak? Değişen kayıtlar K-40 ve A-23'e, hatalı satırların ayıklanması 26. adımdaki hata yönetimine bağlı.
