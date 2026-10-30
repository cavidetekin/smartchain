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
| Tezgâh (kaynak) | 15 |
| Açık müşteri siparişi | 40 |
| Müşteri | 3 |
| Tedarikçi | 8 |
| Çalışan | ~25 (yetkinlik gruplarıyla) |
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
python -m app.data.synthetic check                                     # sayılar ve bilerek konmuş durumlar
```

- **Tohum ve tarih:** Tohum 22 (MDD adım 22). Hafta 1, üretim gününün Pazartesi'sidir; bütün tarihler hafta ve gün olarak göreli tanımlanır. Tek istisna aylık tedarikçi limitidir (durum 3); takvim ayına bağlıdır.
- **Kodlama:** mamul `MAM-001…010`, alt montaj `ALT-`, işlenmiş parça `PRC-`, hammadde `HAM-`, satın alma parçası `SAT-`, tedarikçi `TED-`, müşteri `MUS-`, satış siparişi `SO-`, satın alma `PO-`, iş emri `WO-`, çalışan `W-`.
- **Yükleme:** Lokasyon `ORM-01`, her yüklemede yeni veri versiyonu (LoadType Tam). Satırlarda `VersionFrom` = bu versiyon, `VersionTo` ve `ImportBatchId` boş, `BusinessKey` sözleşmedeki iş anahtarı. Id'ler tablo başına 1'den.
- **Yeniden yükleme:** Önce `ORM-01`'in veri versiyonlarına bağlı her şey silinir: ana tablo satırları, o versiyonlarla açılmış plan hesapları, senaryolar, çalışmalar ve "Sentetik v0" parametre seti. Hepsi tek işlemde yapılır.
- **Güvenlik kilidi:** Sentetik kayıtlar `IsSynthetic = 1` taşır (DataVersion, Location, ParameterSet). Veritabanında sentetik olmayan bir kayıt varsa `load` ve `unload` hiçbir şey silmeden durur ve kayıtları adıyla yazar.
- **Parametre seti "Sentetik v0":** ModelType LP, 13 haftalık zaman yapısı, öncelik kuralı ve tedarikçi limiti.
- **Boş kalanlar:** Forecast (tahmin üretilmez), TransferOrder (tek lokasyon); ek alanlar (K-59); yalnız Material.AdditionalText1 doludur: FieldDefinition etiketi "Malzeme sınıfı", değerler A / B / C (tablo bileşeni denemesi, 1.3).
- **Birimler:** ADET (0 ondalık), KG (3), M (2), SAAT (2); UnitOfMeasure.Decimals (K-88).

**Bilerek konmuş durumların kurulumu.** `check` ve testler bunları veriden hesaplayarak doğrular; ölçüler kabadır, plan değildir.

| # | Durum | Veride | Denetim |
|---|---|---|---|
| 1 | 5 eksen darboğazı | `M5-01` 75 s/hafta. `MAM-001…003`'ün gövde parçaları yalnız 5 eksende, 3 s/adet. `SO-1011…1016` termini hafta 3–5 | Hafta 3, 4, 5 her biri ≥ %130. Hafta 1–5 toplam ihtiyaç > toplam kapasite. Diğer haftalar ≤ %70 |
| 2 | Uzun temin süreli hammadde | `HAM-012` dövme flanş: tek tedarikçi `TED-04`, 56 gün; stok ve açık sipariş yok. Yalnız `MAM-008` ağacında. `SO-1027` termini hafta 5 | En erken temin + üretim süresi > termin |
| 3 | Tedarikçi limiti dolu | `TED-05` · `SAT-003` (rulman), üretim gününden 4 hafta sonraki ay için limit 400; `PO-2041` + `PO-2042` = 400 teyitli | Limit ayındaki teyitli sipariş = limit; aynı ayda ihtiyaç − stok > 0 |
| 4 | İmkânsız termin | `SO-1040` (`MAM-010`, 20 adet) termini üretim günü + 2 iş günü; stok ve iş emri yok; üretim zinciri 10 iş günü | Termin < en erken tarih |
| 5 | Bakım ve izin | `T-02` bakım hafta 2 Salı–Çarşamba · `W-007` izin hafta 3 · `W-015` rapor hafta 1 | Kayıtlar ufukta, var olan kaynak ve çalışanda |

**Kirli hâl.** `data/synthetic/v0/kirli/` altında varlık başına bir Excel (25 dosya) ve `beklenen-hatalar.json`; her gün yeniden üretilebildiği için git'e girmez.
- **Sayfa düzeni (geçici; 3.1'deki şablonla kesinleşir):** 1. satır `stg` alan adı, 2. satır açıklama, veri 3. satırdan. Gizli `_Surum` sayfasında set, tohum ve üretim günü.
- **Kapsam:** Takvim, vardiya ve duruş entegrasyonla gelmediği için yoktur (K-65). Sipariş, stok ve iş emri üretimde API veya SQL ile gelir; ETL testleri için aynı `stg` biçiminde Excel'e konur.
- **Hataların yeri:** Başka satırı zincirleme etkilemez. ETL sonrası ana veri = temiz hâl − aşağıdaki fark. Satır numaraları `beklenen-hatalar.json`'dadır.
- **Mesaj metni:** Burada öneridir; 3.4'te kesinleşir ve oradaki test bu dosyayla karşılaştırır.

| Kod | Hata | Nerede | Adım · sınıf · davranış | Mesaj (öneri) | Ana veride fark |
|---|---|---|---|---|---|
| H1 | Eksik rota | `ProductionVersion`: `PRC-033` → `R-PRC-033`; `Routing`'de bu rota yok | Fonksiyon 20 veri kalitesi (6.5), ön hesapta da (29) · uyarı · satır yüklenir | "Malzeme PRC-033'ün rotası yok (R-PRC-033); kapasite tüketmeden planlanır." | `R-PRC-033` rota satırları yok |
| H2 | Tanımsız malzeme kodu | `SalesOrderLine`: `SO-1099` → `MAM-099` · `BOM`: `ALT-005` → `SAT-999` | 04-02 referans (3.4, 4.4) · hata · satır yüklenmez | "Malzeme bulunamadı: MAM-099 (partide ve geçerli veride yok)." | Yok (fazladan satırlar) |
| H3 | Negatif miktar | `PurchaseOrderLine`: `PO-2060/1` OpenQty −50 · `BOM`: `ALT-012` → `SAT-010` Quantity −2 | 04-03 mantıksal (3.4) · hata · satır yüklenmez | "OpenQty negatif olamaz (-50)." | `PO-2060/1` ve `ALT-012 → SAT-010` eksik |
| H4 | Tekrar eden anahtar | `Material`: `SAT-040` iki satır, adları farklı | 04-01 yapısal (3.4) · hata · iki satır da yüklenmez | "Tekrar eden anahtar: Material.Code = SAT-040 (satır n ve n+1)." | `SAT-040` eksik (başka dosyada geçmez) |

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
| Kilogramlı malzemelere miktar (güvenlik stoğu, lot) | açık: sonraya bırakıldı (1.3 demosu); KG'de 3 ondalık şimdilik yalnız testte görülür |
