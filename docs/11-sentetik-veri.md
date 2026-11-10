# Sentetik veri seti (MDD adım 22)

Hayali bir üreticinin ana verisi ve işlem verisi. Geliştirmede test zemini, satışta demo zemini. Müşteri verisi dışarı alınamadığı için (01-mimari · Anonimleştirme ve sentetik veri) hatalar da bu setle yeniden üretilir.

## v0 (geliştirme 0.8)

### Hayali şirket

**Örnek Makina A.Ş.** Orta ölçekli, siparişe göre üreten talaşlı imalat ve montaj firması; tek lokasyon. Sektöre özgü çağrışım taşımaz.

- **Mamuller:** 8–10 montajlı ürün (pompa gövdesi, redüktör, bağlantı ünitesi gibi).
- **Ürün ağacı:** 3–4 seviye. Mamul → alt montaj → işlenmiş parça → hammadde (çubuk, levha) ve satın alma parçası (rulman, cıvata, conta).
- **Fason operasyonlar:** ısıl işlem ve kaplama.
- **Kaynaklar:** CNC torna, 3 ve 5 eksen işleme merkezleri, taşlama, montaj hattı, kalite kontrol.

### Boyut

| Ne | Adet |
|---|---|
| Malzeme | ~200 |
| Kaynak | 40 (15 tezgâh, 25 çalışan) |
| Açık müşteri siparişi | 40 |
| Müşteri | 3 |
| Tedarikçi | 8 |
| Çalışan | 25 (kaynak olarak; yetkinlikleri `ResourceGroupAssignment`'ta) |
| Planlama ufku | 13 hafta |

Her ana veri ve işlem tablosu en az birkaç satırla dolu gelir; hiçbir ekran boş açılmaz. Büyük veriyle performans denemesi bu setin işi değildir (Aşama 10, A-31).

### Bilerek konmuş durumlar

Planın düz çıkmaması ve ekranlarda gösterilecek bir şey olması için:

- 5 eksen işleme merkezi 3.–5. haftalarda aşırı yüklü (darboğaz).
- Uzun temin süreli bir hammadde bir siparişi geciktirir.
- Bir tedarikçinin aylık limiti (SupplierLimit, K-66) dolu.
- Bir siparişin termini imkânsızdır; uyarı üretmesi beklenir.
- Bir tezgâhta planlı bakım duruşu, bir çalışanda izin vardır.

### Tarihler

Bütün tarihler verinin üretildiği güne göre hesaplanır (bugün + n gün, hafta başına hizalı). Veri aylar sonra yapılan bir demoda da güncel görünür. Üretici sabit tohumla çalışır; aynı gün aynı tohumla aynı veri çıkar (K-78).

### İki hâl

| Hâl | Biçim | Nereye | Ne için |
|---|---|---|---|
| Temiz | Ana tablolar | Doğrudan `core.*` (K-78 istisnası) | Ekranlar ETL yazılmadan çalışır (Aşama 1–9) |
| Kirli | Entegrasyon biçiminde Excel (`stg.*` alanları, kodlarla) | Excel yükleme (Aşama 3) | ETL ve veri kalitesi testleri (Aşama 3–6) |

Kirli hâldeki kasıtlı hatalar: eksik rota, tanımsız malzeme kodu, negatif miktar, tekrar eden anahtar. Her hatanın beklenen sonucu (hangi adımda, hangi mesajla yakalanacağı) setle birlikte listelenir.

### v0 uygulaması (geliştirme 0.8, K-79)

**Üretici:** `app/data/synthetic/`. Set bellekte tek yerde tanımlıdır (`dataset.py`); yükleyici, Excel yazıcısı ve denetimler aynı tanımı kullanır.

```
python -m app.data.synthetic load   [--date 2026-10-27] [--seed 22]   # temiz hâli ana tablolara yükler (öncekini siler)
python -m app.data.synthetic unload                                    # sentetik veriyi siler
python -m app.data.synthetic excel  [--out data/synthetic/v0/kirli]    # kirli hâl: Excel + beklenen-hatalar.json
python -m app.data.synthetic sql                                       # kirli hâl: entegrasyon veritabanına ham tablolar, view'lar, ERP_LoadLog (K-130)
python -m app.data.synthetic check                                     # sayılar ve bilerek konmuş durumlar
```

- **Tohum ve tarih:** Tohum 22 (MDD adım 22). Hafta 1, üretim gününün Pazartesi'sidir; bütün tarihler hafta ve gün olarak göreli tanımlanır. Tek istisna aylık tedarikçi limitidir (durum 3); takvim ayına bağlıdır.
- **Kodlama:** mamul `MAM-001…010`, alt montaj `ALT-`, işlenmiş parça `PRC-`, hammadde `HAM-`, satın alma parçası `SAT-`, tedarikçi `TED-`, müşteri `MUS-`, satış siparişi `SO-`, satın alma `PO-`, iş emri `WO-`, çalışan `W-`.
- **Yükleme:** Lokasyon `ORM-01` (hem tesis hem depo: `IsFactory` ve `IsDepot` 1, `IsSubcontractor` 0, `IsActive` 1; K-111), her yüklemede yeni veri versiyonu (LoadType Tam). Satırlarda `VersionFrom` = bu versiyon, `VersionTo` ve `ImportBatchId` boş, `BusinessKey` sözleşmedeki iş anahtarı. Id'ler tablo başına 1'den.
- **Yeniden yükleme:** Önce `ORM-01`'in veri versiyonlarına bağlı her şey silinir: ana tablo satırları, o versiyonlarla açılmış plan hesapları, senaryolar, çalışmalar ve "Sentetik v0" parametre seti. Hepsi tek işlemde yapılır.
- **Güvenlik kilidi:** Sentetik kayıtlar `IsSynthetic = 1` taşır (DataVersion, Location, ParameterSet). Veritabanında sentetik olmayan bir kayıt varsa `load` ve `unload` hiçbir şey silmeden durur ve kayıtları adıyla yazar.
- **Parametre seti "Sentetik v0":** ModelType LP, 13 haftalık zaman yapısı, öncelik kuralı ve tedarikçi limiti.
- **Boş kalanlar:** Forecast (tahmin üretilmez), TransferOrder (tek lokasyon), MaterialReference (her üretilen malzemenin kendi versiyonu var); ek alanlar (K-59); yalnız Material.AdditionalText1 doludur: FieldDefinition etiketi "Malzeme sınıfı", değerler A / B / C (tablo bileşeni denemesi, 1.3).
- **Malzeme (K-113):** Üretim süresi tabloda değil, senaryoların iç hesabında kullanılır (`Dataset.lead_days`; K-12). `MAM-006` özel takipli, `SAT` grubunda marka ve kutu miktarları dolu, fason operasyonu olan malzemeler fasona verilebilir, rulmanlar ve `HAM-012` kritik. `ALT-013` (üretilen) ve `SAT-030` (satın alınan) stok tutulamaz: ikisinde de stok yok, temiz veride uyarı çıkmaz.
- **Üretim versiyonu (K-114):** Her üretilen malzemede tek versiyon (`V1`, öncelik 1); `BOMCode` `B-<malzeme>`. Alternatif versiyon sentetik veride yok (A-40).
- **Ürün ağacı (K-115):** Her ağaç tek versiyonda; ağaç kodu versiyonun `BOMCode`'u, sıra no 1. Alternatif bileşen sentetik veride yok (A-41).
- **Tedarik (K-118):** Eski tedarik süresi sabit süreye geçti, değişken süre boş; ikinci kaynağı olan malzemede kota birincide %70, ikincide %30 (toplam 1; MS.QUOTA_SUM, 3.4). Tedarikçiler aktif, ülke ve şehir dolu.
- **Satış siparişi (K-120):** Alt satır no 0, sipariş miktarı açık miktara eşit, teslim 0, birim boş (temel birim). Satırlar aktif, bekleyen yok; projeye bağlı satırlar özel takipli; `IsQuote` teklif satırlarında 1, kesin satırlarda 0 (K-127).
- **Stok (K-123):** Ham durum `Serbest`, `Kalitede` ya da `Bloke`; bayraklar durumla uyumlu, stoklar aktif, projeli stok özel takipli. Birim boş (temel birim), sahip müşteri ve sipariş boş. Kalitedeki lotun kaliteye giriş tarihi üretim gününden 4 gün önce, beklenen kabul tarihi üretim günü + 3.
- **İş emri (K-124):** Ham tip `Üretim`, ham durum `Yayınlandı` ya da `Başladı`; bayraklar bunlarla uyumlu, sabit ve beklemede yok. Her iş emri malzemenin üretim versiyonuna bağlı; tamamlanan miktar emir − açık, hurda 0, birim boş. Sipariş bağlı `WO-5001` siparişin müşterisini taşır. Bileşenler ağaçtan (operasyon, sıra, birim kullanım, fire, bayraklar); operasyonlar rotanın Primary satırlarından (ad, rol, kaynak adedi, bayraklar), tamamlanan yok.
- **Satın alma (K-125):** Ham tip `Satın alma`, `Fason` ya da `Satın alma talebi`; bayraklar tiple uyumlu, satırlar aktif, özel takip yok. Sipariş miktarı açık miktara eşit, teslim alınan 0, birim boş; müşteri ve bağlı sipariş boş. Fason siparişler fason operasyonu olan iş emrine bağlıdır (PO.SUBCON_NO_WO, 3.4).
- **Üretim gerçekleşmesi (K-125):** Başlamış her iş emrinde bir teyit: no `T-<iş emri>`, malzeme iş emrinden, miktar emir − açık, başlangıç ve bitiş üretim başlangıcından 3 gün önce.
- **Müşteri ve proje (K-119):** Müşteriler yurt içi, `MUS-A` özel takipli. Proje grubu ve projeler aktif. Bir açık ödünç var: `MAM-006`, `PRJ-01` → `PRJ-02`, 2 adet, geri ödeme hafta 3.
- **Rota (K-116):** Montaj operasyonlarında işçilik ayrı satırdır: sıra no 2, yetkinlik grubu `CG-MON`, Secondary, 2 kişi, süre ana satırla aynı. İş emri operasyonları yalnız Primary satırlardan üretilir.
- **Kaynak (K-117):** Kapasite birimi `SAAT`. İşçiler `IsEmployee` bayraklı kaynaktır (`W-…`; 7,5 saat/gün, kısıtlı); yetkinlikler (`CG-…`) `IsCompetenceGroup` bayraklı gruptur. Tezgâhlar ve işçiler gruplarına `ResourceGroupAssignment` ile atanır; işçi hem bağlı olduğu kaynak grubunda hem yetkinlik grubundadır. Vardiya planı yetkinlik grubunu gösterir. `W-021` izni günde 4 saatlik kısmi devamsızlıktır.
- **Birimler:** ADET (0 ondalık), KG (3), M (2), SAAT (2); UnitOfMeasure.Decimals (K-88).

**Bilerek konmuş durumların kurulumu.** `check` ve testler bunları veriden hesaplayarak doğrular; ölçüler kabadır, plan değildir.

| # | Durum | Veride | Denetim |
|---|---|---|---|
| 1 | 5 eksen darboğazı | `M5-01` 75 s/hafta. `MAM-001…003`'ün gövde parçaları yalnız 5 eksende, 3 s/adet. `SO-1011…1016` termini hafta 3–5 | Hafta 3, 4, 5 her biri ≥ %130. Hafta 1–5 toplam ihtiyaç > toplam kapasite. Diğer haftalar ≤ %70 |
| 2 | Uzun temin süreli hammadde | `HAM-012` dövme flanş: tek tedarikçi `TED-04`, 56 gün; stok ve açık sipariş yok. Yalnız `MAM-008` ağacında. `SO-1027` termini hafta 5 | En erken temin + üretim süresi > termin |
| 3 | Tedarikçi limiti dolu | `TED-05` · `SAT-003` (rulman), üretim gününden 4 hafta sonraki ay için limit 400; `PO-2041` + `PO-2042` = 400 teyitli | Limit ayındaki teyitli sipariş = limit; aynı ayda ihtiyaç − stok > 0 |
| 4 | İmkânsız termin | `SO-1040` (`MAM-010`, 20 adet) termini üretim günü + 2 iş günü; stok ve iş emri yok; üretim zinciri 10 iş günü | Termin < en erken tarih |
| 5 | Bakım ve izin | `T-02` bakım hafta 2 Salı–Çarşamba · `W-007` izin hafta 3 · `W-015` rapor hafta 1 | Kayıtlar ufukta, var olan kaynak ve çalışanda |

**Kirli hâl.** `data/synthetic/v0/kirli/` altında varlık başına bir Excel (25 dosya; benzetilen ürün ve tahmin yalnız hazır kural örnekleriyle) ve `beklenen-hatalar.json`; her gün yeniden üretilebildiği için git'e girmez.
- **Sayfa düzeni (K-110):** şablon üreticisiyle yazılır (`app/integration/template.py`): 1. satır `stg` alan adı, veri 2. satırdan; Açıklama sayfası; gizli `_Surum` sayfasında tablo, sürüm, set, tohum ve üretim günü. Etiketsiz ek alan kolonu yoktur. Etiket veri setinden gelir, veritabanı gerekmez.
- **Kapsam:** Takvim, vardiya ve duruş entegrasyonla gelmediği için yoktur (K-65). Sipariş, stok ve iş emri üretimde API veya SQL ile gelir; ETL testleri için aynı `stg` biçiminde Excel'e konur.
- **Hataların yeri:** Başka satırı zincirleme etkilemez. ETL sonrası ana veri = temiz hâl − aşağıdaki fark. Satır numaraları `beklenen-hatalar.json`'dadır.
- **Mesaj metni:** H1 ve H2'nin mesajı 4.4'te kesinleşti (K-146): kataloğun mesajı ve değer ("Rota bulunamadı: R-PRC-033", "Malzeme bulunamadı: MAM-099"); H3 ve H4'ün mesajı 3.4'te kesinleşti: kataloğun mesajı (H3 "Negatif olamaz.", alan ve değer bulgunun kolonlarında) ve ön kontrolün tekrar eden anahtar mesajı.

| Kod | Hata | Nerede | Adım · sınıf · davranış | Mesaj (öneri) | Ana veride fark |
|---|---|---|---|---|---|
| H1 | Eksik rota | `ProductionVersion`: `PRC-033` → `R-PRC-033`; `Routing`'de bu rota yok | `PV.REF_ROUTE` (4.4, K-146; versiyonun rotası zorunlu ilişki) · hata · satır yüklenmez | "Rota bulunamadı: R-PRC-033" | `R-PRC-033` rota satırları ve `PRC-033` V1 versiyonu yok |
| H2 | Tanımsız malzeme kodu | `SalesOrderLine`: `SO-1099` → `MAM-099` · `BOM`: `ALT-005` → `SAT-999` | `SO.REF_MATERIAL` ve `BOM.REF_COMPONENT` (4.4, K-146) · hata · satır yüklenmez | "Malzeme bulunamadı: MAM-099" · "Bileşen bulunamadı: SAT-999" | Yok (fazladan satırlar) |
| H3 | Negatif miktar | `PurchaseOrderLine`: `PO-2060/1` OpenQuantity −50 · `BOM`: `ALT-012` → `SAT-010` Quantity −2 | ALL.NEGATIVE (3.4) · hata · satır yüklenmez | "Negatif olamaz." (Alan: Açık miktar, Değer: -50) | `PO-2060/1` ve `ALT-012 → SAT-010` eksik |
| H4 | Tekrar eden anahtar | `Material`: `SAT-040` iki satır, adları farklı | Fonksiyon 03 ön kontrol ve 04-01 yapısal (3.2, 3.4; aynı kod) · hata · iki satır da ham veriye alınmaz | "Aynı kayıt n ve n+1. satırlarda" | `SAT-040` eksik (başka dosyada geçmez) |

**Ek alan etiketi (K-104):** yükleme etiketi yalnız boşsa yazar; System owner'ın etiketi korunur.

**Tazeleme (K-103):** testler artık geliştirme veritabanına dokunmaz; geliştirme verisi son `load`'daki hâliyle kalır, tarihler zamanla eskir. Gerektiğinde `python -m app.data.synthetic load` (ya da `veri_demo.bat`). Test veritabanının verisini testler kendisi kurar.

**Sıfırlama (K-153):** geliştirme ya da demo veritabanında tam aktarım yapıldıktan sonra `load` durur (sentetik olmayan veri versiyonu var, K-79). `python -m app.data.synthetic reset` aktarımları geri alır (sentetik olmayan veri versiyonları, onların core satırları ve plan verisi, kural kaynağı satırları, aktarımın eklediği lokasyonlar), aktarımın kapattığı sentetik satırları açar ve sentetik veriyi yeniden yükler; tek işlemdir, staging değişmez. Yalnız sentetik veriyle kurulmuş veritabanında (sentetik veri versiyonu var), onaylı plana bağlı versiyon ve sentetik olmayan parametre seti yokken çalışır; silinecekleri gösterip veritabanının adının yazılmasını ister.

### SQL çekimi (geliştirme 3.3, K-130)

`python -m app.data.synthetic sql` kirli hâli entegrasyon veritabanına yazar (varsayılan `SmartchainIntegration`; testte `_test` ile biter): `ERP_*` ham tablolar, `View_*` ve `ERP_LoadLog`'da biten bir toplu satır. Kaynak Excel'le aynı olduğu için H1–H4 aynıdır; `tests/test_pull_dirty.py` iki yolun sonucunu birebir karşılaştırır.

- **Gerçekçi üç tablo:** Malzeme (`ERP_Material` ve `ERP_ItemGroup`, başka kolon adları, join), Ürün ağacı (`ERP_BOM`, başka kolon adları), Satış siparişi (`ERP_SalesOrder`, başka kolon adları, tarih metin). Kurulumda örnek alınabilir.
- **Düz 20 tablo:** `ERP_<tablo>` ve `SELECT <kolonlar>`. Yalnız test içindir, müşteriye örnek değildir.
- **Demo:** Malzeme, Ürün ağacı, Rota, Stok, Satış siparişi ve İş emri SQL; kalanı Excel.
- **Kilit:** Yalnız `_test` ile biten ya da bu komutun açtığı veritabanına yazar; ham tablolar ve view'lar yeniden açılır.

### Hazır kural örnekleri (geliştirme 3.4, K-137)

- **Kapsam:** Kirli hâlde her hazır validasyon kuralı için en az bir satır bulunur (docs/06 fonksiyon 04 tablosu; yapısal kontroller H1–H4 ve ön kontrol testleriyle zaten kapsanır). Excel ve SQL aynı kaynaktan yazılır; iki yol aynı bulguları verir.
- **Yer:** Örnekler kendi satırlarındadır (`V-` ile başlayan kodlar ya da ayrı malzeme ve sipariş numaraları); bilerek konmuş durumlara (1–5) ve H1–H4'e dokunmaz, başka satırı zincirleme etkilemez. Tablolar arası kurallar için öteki tablodaki karşılığı da eklenir (ör. `IsNonStockable` malzemeye stok satırı).
- **Beklenen:** `beklenen-hatalar.json`'da kural kodu, tablo, satır anahtarı, sınıf ve mesaj; test (`tests/test_validation_dirty.py`) her aktif hazır kuralın en az bir bulgu verdiğini ve beklenmeyen satırda bulgu çıkmadığını denetler. H3 negatif miktar `ALL.NEGATIVE`'dir; H2 `SO.REF_MATERIAL` ve `BOM.REF_COMPONENT`'tir (4.4).
- **Ekle / güncelle partisi:** Demo için ikinci bir küçük dosya (`kirli/ekle-guncelle/`): güncel hâlde bir kaydı değiştirir ve bir küme kuralını tetikler (ör. MaterialSupplier kota toplamı); güncel hâlin işlenişini gösterir (K-133).
- **Mesajlar:** H1–H4 mesajları 3.4'te kesinleşir; hazır kuralların mesajları kataloğun mesajıdır.

### Referans ve bütünlük örnekleri (geliştirme 4.4, K-146)

- **Kapsam:** Kirli hâlde her referans, pasif ebeveyn ve bütünlük kuralı için en az bir satır bulunur (docs/06 fonksiyon 04; ilişki haritası docs/03). Zorunlu ilişkide tanımsız kod (Hata), isteğe bağlı bağlantıda tanımsız kod (Uyarı), pasif ebeveyne bakan satır (`L-` ile başlayan pasif malzeme, müşteri, tedarikçi ve kaynak; Uyarı ya da Bilgi), bağı eksik ebeveyn (aktif versiyonu olmayan üretilen malzeme, tedarikçisi olmayan satın alınan malzeme, kaynaksız grup…).
- **Yer:** Örnekler kendi satırlarındadır (`V-` ve `L-` ile başlayan kodlar, ayrı sipariş ve iş emri numaraları); bilerek konmuş durumlara ve H1–H4'e dokunmaz. Temiz hâlde yeni kurallar bulgu vermez; önceki örneklerin yeni kurallara takılan satırları düzeltilir ya da beklenene eklenir.
- **H2:** `SO.REF_MATERIAL` ("Malzeme bulunamadı: MAM-099") ve `BOM.REF_COMPONENT` ("Bileşen bulunamadı: SAT-999"); ikisi de Hata, satır yüklenmez.
- **Beklenen:** `beklenen-hatalar.json`'da kural kodu, tablo, satır anahtarı, sınıf ve mesaj; test (`tests/test_validation_dirty.py`) her yeni kuralın en az bir bulgu verdiğini, beklenmeyen satırda bulgu çıkmadığını ve Excel ile SQL yolunun aynı sonucu verdiğini denetler.

### Veri kuralı örnekleri (geliştirme 4.1, K-141)

- **Kapsam:** Kirli hâlde kurallarla çözülen satırlar bulunur; kurallar yokken validasyon bulgusu verirler, demo kurallarıyla bulgu kalkar. Excel ve SQL aynı kaynaktan yazılır.
- **Örnekler:** Lokasyon bayrakları boş, `Type` dolu; `Type` ERP'nin dilindedir (PLANT, K-143): Tip = PLANT ise Tesis = Evet, Yalnız boşsa; ERP'nin `IsActive` göndermediği bir tablo (Her zaman → Evet); Stok bayrakları (`IsAvailable`, `IsInQuality`, `IsBlocked`) boş, `Status` dolu; Satış siparişinde `IsQuote` boş, `Type` Teklif; bir tarih + gün örneği (satın alma siparişinde `ConfirmedDate` boşsa `RequestedDate` + gün). Sıfıra bölme örneği: R-MAT-1 kutu içi miktar 0, palet 40 ("Paletteki kutu sayısı" hücreyi değiştirmez, MAT.ZERO_PACK bulgusu kalır); R-MAT-2 kutu 4, palet 40 (sonuç 10) (K-141, K-144).
- **Demo kuralları:** `python -m app.data.synthetic rules` geliştirme ve demo veritabanına bu örneklerin kurallarını yazar; kurulumda varsayılan kural yoktur (K-141). Komut var olan aynı adlı kuralı yeniden yazar, ötekilere dokunmaz.
- **Beklenen:** `beklenen-hatalar.json`'daki her örnek satır iki hâli taşır: kurallar yokken (`rules`) ve demo kurallarıyla (`rules_with_demo`); `demo_rules` kuralların listesidir. Test (`tests/test_validation_dirty.py`) ikisini de denetler.

### Kullanıcılar (geliştirme 2.1, K-98)

Örnek Makina A.Ş.'nin dört hesabı, her rol için bir tane:

| Kullanıcı adı | Ad soyad | Rol |
|---|---|---|
| `sahip` | System owner | System owner |
| `yonetici` | Ayşe Yönetici | Admin |
| `planlama` | Mert Planlama | Key user |
| `izleme` | Deniz İzleme | End user |

```
python -m app.data.synthetic users   # hesapları açar ya da geçici şifreye döndürür, şifreleri bir kez gösterir
```

- Her çalıştırmada her hesaba yeni, rastgele bir geçici şifre verilir (12 karakter, harf ve rakam; politikaya uygun). Hesap "İlk giriş" ile şifre değiştirmeye zorlanır; şifre geçmişi, hatalı deneme sayacı ve kilit temizlenir, açık oturumları kapanır. Demoda her çalıştırma ilk giriş akışını yeniden gösterir.
- Geçici şifreler kodda ve repoda yer almaz. Konsola bir kez yazılır ve git dışı `.local/gecici-sifreler.txt` dosyasına kaydedilir (yalnız geliştirme; kurulum paketine girmez).
- `load` ve `unload` kullanıcılara dokunmaz.

### Beklenen plan çıktıları

v0'da yoktur. Beklenen plan 8.0'daki plan fikstürüdür (bu setin üzerine elle hazırlanır); 10.8'de gerçek motorun kabul testine dönüşür.

### Kapsam dışı

Faz 1 dışı konular (set-up, kalıp, fırın, raf ömrü kuralları, çoklu lokasyon). Talep tahmini üretilmez.

## Durum

| Parça | Durum |
|---|---|
| v0 tasarımı | karar verildi (K-78) |
| v0 üretici ve temiz hâl | uygulandı (0.8) |
| Kirli hâl (entegrasyon Excel'i) | üretildi (0.8); ETL ile denenmesi Aşama 3–5 |
| Birim ondalıkları (ADET 0, KG 3, M 2, SAAT 2) | uygulandı (1.3) |
| Kullanıcılar ve geçici şifre komutu | uygulandı (2.1) |
| Veri kuralı örnekleri ve demo kuralları komutu (`rules`) | uygulandı (4.1) |
| Kilogramlı malzemelere miktar (güvenlik stoğu, lot) | açık: sonraya bırakıldı (1.3 demosu); KG'de 3 ondalık şimdilik yalnız testte görülür |
