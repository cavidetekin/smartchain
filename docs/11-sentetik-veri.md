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
| Kaynak | 41 (16 tezgâh, 25 çalışan; `T-05` 6.5'te, K-174) |
| Açık müşteri siparişi | 40 |
| Müşteri | 3 |
| Tedarikçi | 8 |
| Çalışan | 25 (kaynak olarak; yetkinlikleri `ResourceGroupMember`'da, K-180) |
| Kaynak grubu | 11 (6 tezgâh grubu, 3 işçi grubu, 2 fason grubu; K-180) |
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

- **Tohum ve tarih:** Tohum 22 (MDD adım 22). Hafta 1, üretim gününün Pazartesi'sidir; bütün tarihler hafta ve gün olarak göreli tanımlanır. Tek istisna aylık tedarikçi limitidir (durum 3); takvim ayına bağlıdır. Rastgele satın alma siparişlerinin tarihi en erken üretim gününden sonraki ilk iş günüdür: hafta 1'in geçmişte kalan gününe düşen tarih oraya çekilir (set haftanın hangi günü üretilirse üretilsin beklenmeyen PO.PAST_DUE vermez).
- **Kodlama:** mamul `MAM-001…010`, alt montaj `ALT-`, işlenmiş parça `PRC-`, hammadde `HAM-`, satın alma parçası `SAT-`, tedarikçi `TED-`, müşteri `MUS-`, satış siparişi `SO-`, satın alma `PO-`, üretim siparişi `WO-`, çalışan `W-`.
- **Yükleme:** Lokasyon `ORM-01` (hem tesis hem depo: `IsFactory` ve `IsDepot` 1, `IsSubcontractor` 0, `IsActive` 1; K-111), her yüklemede yeni veri versiyonu (LoadType Tam). Satırlarda `VersionFrom` = bu versiyon, `VersionTo` ve `ImportBatchId` boş, `BusinessKey` sözleşmedeki iş anahtarı. Id'ler tablo başına 1'den.
- **Yeniden yükleme:** Önce `ORM-01`'in veri versiyonlarına bağlı her şey silinir: ana tablo satırları, o versiyonlarla açılmış plan hesapları, senaryolar, çalışmalar ve Baz senaryoya bağlanmış sentetik satırlar (öncelik kuralı, tedarikçi limiti). Baz'ın parametrelerine dokunulmaz (K-175). Hepsi tek işlemde yapılır.
- **Güvenlik kilidi:** Sentetik kayıtlar `IsSynthetic = 1` taşır (DataVersion, Location, ScenarioDefinition). Baz senaryo sentetik değildir ve kilide girmez; Baz dışında sentetik olmayan senaryo kilittir. Veritabanında sentetik olmayan bir kayıt varsa `load` ve `unload` hiçbir şey silmeden durur ve kayıtları adıyla yazar.
- **Senaryoya bağlı satırlar (K-175):** parametre seti açılmaz; öncelik kuralı (4 satır) ve tedarikçi limiti (1 satır) Baz senaryoya bağlanır. Model tipi, zaman yapısı ve öteki parametreler Baz'ın kendi değerleridir (kurulumdaki başlangıç değerleri ya da kullanıcının değiştirdikleri); sentetik yükleme onlara dokunmaz. Baz yoksa yükleme durur ("önce veritabanını güncelleyin").
- **Sentetik senaryolar (K-177):** yükleme Baz'dan kopyalayarak üç senaryo açar (`IsSynthetic` = 1; yeniden yüklemede ve `unload`'da silinir; güvenlik kilidine girmezler): **Fazla mesaili** (Kapasite › Ek mesai Evet; Baz'ı izler; gece 2. sırada), **Kısıtsız kapasite** (Kaynak kısıtı Kısıtsız, hedeflerin süre bütçesi yarı; Baz'ı izler; gece 3. sırada), **MILP deneme** (Model tipi MILP, üretimde minimum lot ve lot katı açık; Baz'ı izlemez; gece çalışmaz). Baz gece 1. sırada çalışır; yükleme Baz'ın gece ayarını yazar, parametrelerine dokunmaz. **Hedef satırları (7.14b, K-196):** sentetik senaryolar başlangıç düzenindedir (24 satır; Baz'ın hedeflerine dokunulmaz: Baz geçişle taşınmış hâlinde kalır, ekrandaki "Başlangıç düzenine getir" ile çevrilir). **Fazla mesaili**de kullanıcının eklediği gibi üç satır daha vardır: en üstte "Karşılanmayan talep · Talep türü: Kesin sipariş · Öncelik grubu: 1, 2" (60 sn; açıklaması "Öncelikli siparişler önce"; "Talep türü: Kesin sipariş" satırıyla **örtüşür**, ikisi de durur); hemen altında "Hedef doluluğun üstü · Kaynak grubu tipi: Makine" (açılmış, 20 sn; farklı hedeflerin satırları iç içe); hammadde satırının üstünde "Güvenlik stoğunun altı · Malzeme seviyesi: Hammadde · Malzeme grubu: Rulman" (20 sn). Nihai ürünlerin tek malzeme grubu (Mamul) olduğu için grup örneği hammaddededir.
- **Tahmin ve benzetilen ürün (6.5, K-174):** `MAM-001` için gelecek iki ayın tahmini (ay başı, ufuk içinde); `MAM-011` kendi versiyonu olmayan mamuldür, `MAM-001`'in ağacı ve rotası benzetilen ürün satırıyla izlenir (talep zinciri ve veri kalitesi demosu).
- **Boş kalanlar:** TransferOrder (tek lokasyon); ek alanlar (K-59); yalnız Material.AdditionalText1 doludur: FieldDefinition etiketi "Malzeme sınıfı", değerler A / B / C (tablo bileşeni denemesi, 1.3).
- **Malzeme (K-113):** Üretim süresi tabloda değil, senaryoların iç hesabında kullanılır (`Dataset.lead_days`; K-12). `MAM-006` ve ağacındaki `SAT-009` özel alokasyonlu, `SAT-010`'un özel alokasyonu boş (durum 11; K-198), `SAT` grubunda marka ve kutu miktarları dolu, fason operasyonu olan malzemeler fasona verilebilir, rulmanlar ve `HAM-012` kritik. `ALT-013` (üretilen) ve `SAT-030` (satın alınan) stok tutulamaz: ikisinde de stok yok, temiz veride uyarı çıkmaz.
- **Üretim versiyonu (K-114):** Her üretilen malzemede tek versiyon (`V1`, öncelik 1); `BOMCode` `B-<malzeme>`. Tek istisna alternatifli örnektir (K-199; 7.16 Üretim akışı demosunda da kullanılır): `ALT-017`'nin ikinci versiyonu `V2` (öncelik 2, ağaç `B-ALT-017-2`, rota `V1` ile aynı); ikinci ağaç birincinin bileşenlerine ek olarak `SAT-001`'i kullanır. Sentetik durum hesapları ve üretim siparişleri birinci versiyonu kullanır (A-40).
- **Ürün ağacı (K-115):** Her ağaç tek versiyonda (alternatifli örnek `B-ALT-017-2` dışında); ağaç kodu versiyonun `BOMCode`'u, sıra no 1. Alternatif bileşen sentetik veride yok (A-41).
- **Tedarik (K-118):** Eski tedarik süresi sabit süreye geçti, değişken süre boş; ikinci kaynağı olan malzemede kota birincide %70, ikincide %30 (toplam 1; MS.QUOTA_SUM, 3.4). Tedarikçiler aktif, ülke ve şehir dolu.
- **Satış siparişi (K-120):** Alt satır no 0, sipariş miktarı açık miktara eşit, teslim 0, birim boş (temel birim). Satırlar aktif, bekleyen yok; `IsQuote` teklif satırlarında 1, kesin satırlarda 0 (K-127).
- **Stok (K-123):** Ham durum `Serbest`, `Kalitede` ya da `Bloke`; bayraklar durumla uyumlu, stoklar aktif. Birim boş (temel birim). Özel alokasyon örnekleri (K-198): `MAM-006`'da projeye (`PRJ-01`, 3 adet), müşteriye (`MUS-A`, 2 adet) ve siparişe (`SO-1020`, 1 adet) ayrılmış stok; özel alokasyonu boş `SAT-010`'da `PRJ-02`'ye bağlı 20 adet stok genel sayılır. Sahibi sistemde olmayan ayrılmış stok genele düşmez: `MAM-006`'da `PRJ-77`'ye (böyle proje yok) bağlı 1 adet → Proje / `PRJ-77`; `SAT-009`'da `MUS-Z`'ye (kapanmış müşteri; güncel veride yok) bağlı 30 adet → Müşteri / `MUS-Z`. Öteki stoklarda bağlı proje, müşteri ve sipariş boş. Kalitedeki lotun kaliteye giriş tarihi üretim gününden 4 gün önce, beklenen kabul tarihi üretim günü + 3.
- **Üretim siparişi (K-124):** Ham tip `Üretim`, ham durum `Yayınlandı` ya da `Başladı`; bayraklar bunlarla uyumlu, sabit ve beklemede yok. Her üretim siparişi malzemenin üretim versiyonuna bağlı; tamamlanan miktar emir − açık, hurda 0, birim boş. Sipariş bağlı `WO-5001` siparişin müşterisini taşır; malzemesi (`MAM-004`) özel alokasyonlu olmadığı için satır geneldir. `WO-5013` (`MAM-006`, 4 adet) `PRJ-02`'ye ayrılmıştır (K-198). Bileşenler ağaçtan (operasyon, sıra, birim kullanım, fire, bayraklar); operasyonlar rotanın Primary satırlarından (ad, rol, kaynak adedi, bayraklar), tamamlanan yok.
- **Satın alma (K-125):** Ham tip `Satın alma`, `Fason` ya da `Satın alma talebi`; bayraklar tiple uyumlu, satırlar aktif. Sipariş miktarı açık miktara eşit, teslim alınan 0, birim boş. Özel alokasyon örnekleri (K-198): `PO-2071` (`SAT-009`) kalemsiz olarak `SO-1021`'e (yalnız sipariş no), `PO-2072` (`SAT-009`) `MUS-A`'ya ayrılmıştır; `PO-2073` (`SAT-009`) olmayan bir siparişe (`SO-9999`) bağlıdır ve genele düşmez: Sipariş / `SO-9999`. Ötekilerde bağlı müşteri ve sipariş boş. Fason siparişler fason operasyonu olan üretim siparişine bağlıdır (PO.SUBCON_NO_WO, 3.4).
- **Üretim gerçekleşmesi (K-125):** Başlamış her üretim siparişinde bir teyit: no `T-<üretim siparişi>`, malzeme üretim siparişinden, miktar emir − açık, başlangıç ve bitiş üretim başlangıcından 3 gün önce.
- **Müşteri ve proje (K-119):** Müşteriler yurt içi. Projeler aktif; proje grubu yoktur (K-198). Bir açık ödünç var: `MAM-006`, `PRJ-01` → `PRJ-02`, 2 adet, geri ödeme hafta 3.
- **Rota (K-116, K-180):** Rota satırı kaynağı değil kaynak grubunu gösterir (tezgâhın grubu: `TORNA`, `ISL3`, `ISL5`, `TASLAMA`, `MONTAJ`, `KALITE`; fason operasyonda `F-ISIL`, `F-KAPLA`). Montaj operasyonlarında işçilik ayrı satırdır: sıra no 2, işçi grubu `CG-MON`, Secondary, 2 kişi, süre ana satırla aynı. Üretim siparişi operasyonları yalnız Primary satırlardan üretilir ve aynı grubu taşır.
- **Kaynak ve kaynak grubu (K-117, K-180):** Planlama birimi kaynak grubudur. Tip bayrağı, kritiklik, kapasite birimi (`SAAT`) ve fasoncu gruptadır: tezgâh grupları `IsMachine` ve kritik; işçi grupları (yetkinlikler, `CG-…`) `IsEmployee` ve kritik; fason grupları (`F-ISIL`, `F-KAPLA`) `IsSubcontractor`, kritik değil, fasoncuya bağlı ve kaynağıyla aynı kodda tek üyeli (kaynağını grup olarak veren müşteri örneği). Kaynakta kimlik ve ham tip (Makine, İşçi, Fason) durur; kapasite alanı yoktur (K-185). Kaynaklar gruplarına `ResourceGroupMember` ile bağlanır (tarihsiz); işçiler **yalnız** işçi gruplarına üyedir (gruptaki kaynak sayısı kapasiteyi belirlediği için tezgâh grubunda değiller), bazıları iki yetkinliklidir. Darboğaz grubu `ISL5` tek üyelidir (`M5-01`). Vardiya ve vardiya planı yoktur. `W-021` izni günde 4 saatlik kısmi devamsızlıktır.
- **Kapasite girişleri (7.9, K-185; Baz senaryoya yüklenir):**
  - Çalışma düzeni: grup düzeyinde `ISL3`, `ISL5`, `TASLAMA`, `MONTAJ` 15 saat/gün; `KALITE`, `CG-CNC`, `CG-MON` 7,5; `CG-KAL` 7,0; `F-ISIL` 24 (fason grubuna da girilebilir). `TORNA`'nın grup kaydı yoktur: `T-01…T-04` kendi kayıtlarıyla 15 saat/gün. Hafta içi tam, hafta sonu çalışılmıyor; `Q-01` Cumartesi yarım gün. Geçici kayıtlar: `G-02` hafta 9–10 7,5 saat; `T-04` hafta 12–13 22,5 saat (bitince öncekine döner).
  - Verimlilik: `TASLAMA` %85 (süresiz); `A-01` hafta 4–8 %110. Ek mesai limiti: `CG-MON` 2 saat/gün, `CG-CNC` 1,5 saat/gün, `ISL5` 1 saat/gün (K-205: darboğazda aşım ve ek mesai aynı grupta).
  - Bakım ve duruş: `T-02` hafta 2 Salı–Çarşamba (Planlı bakım), `G-01` bir gün (Planlı bakım), `M3-02` iki gün (Arıza), `KALITE` grubuna bir gün (Planlı bakım). Fabrika takvimi: Yılbaşı arifesi (yarım gün), Yılbaşı, yıllık toplu izin (hafta 16).
  - Fabrika takvimi lokasyon bazlıdır (K-194): sentetik takvim kayıtları sentetik lokasyona (`ORM-01`) bağlanır.
  - Bilerek konmuş durumlar: `T-05` ne kendisinde ne grubunda çalışma düzeni (kritik grup, talep zincirinde: Yüksek); `F-KAPLA` fason, çalışma düzeni yok (kritik değil: Normal); `CG-MON` (7,5) ve `CG-KAL` (7,0) gruplarının ikisine üye işçilerde "Grupları çelişen kaynak".
  - Model kısıtları (7.10, K-189): Baz'da `TORNA` hedef doluluk %85, `ISL3` hedef doluluk %90, `MONTAJ` kısıtsız kapasite çarpanı 1,50. **Kısıtsız kapasite** senaryosu `MONTAJ` çarpanını 2,00'a çıkarır (fark) ve `TASLAMA`'ya 1,25 çarpanını kendisi ekler. Kritik olmayan grupta (`F-KAPLA`, `F-ISIL`) değer yok.
  - Uyarı eşikleri (7.11, K-190): bütün senaryolar başlangıç değerleriyle (geçiş 0069). **Kısıtsız kapasite** senaryosunda Aşırı yük eşikleri boş / 110 / 125 / 150 ve Düşük doluluk kapalıdır (senaryolar arasında farklı eşik örneği).
  - Tedarikçi limiti (7.12, K-191): Baz'da durum 3'ün limiti (`TED-05` · `SAT-003`, limit ayı için 400 / ay), `TED-01` · `HAM-001` 600 / ay (süresiz) ve 8. haftadan itibaren 800 / ay (ileri başlangıçlı ikinci kayıt), `TED-02` · `HAM-002` 150 / hafta; `TED-03` yıl sonu tatilinde (28 Aralık – 3 Ocak) bütün malzemelerde kapalı (genel kapanış); `TED-01` · `HAM-002` 5. haftada kapalı (malzemeye özel kapanış; `HAM-002` iki tedarikçilidir). **Kısıtsız kapasite** senaryosunda `TED-02` · `HAM-002` limiti 300 / hafta (fark). Örnek malzemeler tedarikçinin koda göre ilk malzemeleridir (`dataset.supplier_material`).
  - Malzeme blokajı (7.13, K-193): Baz'da üç kayıt, hepsi dönemi kapatma oranı %50 ile; aylar plan ekseninin aylık dönemleridir (üretim gününden 3, 4 ve 5 ay sonraki takvim ayları). `ALT-020` (hem üretilen hem satın alınan tek malzeme: Üretilebilir ve Satın alınabilir Evet, malzeme tedarikçisi `TED-06`, tedarik süresi 14 gün; üç tür de girilebilir. Öteki sentetik üretimler tamamlandıktan sonra işaretlenir: stok, sipariş ve satın alma satırları değişmez): 3. ayın ilk 10 günü "Üretim" (oranın altı: ay açık) ve 4. ayın ilk 20 günü "Üretim ve satın alma" (oranın üstü: ay iki tedarik biçiminde kapalı). `SAT-030`: 5. ayın başından itibaren süresiz "Satın alma" (sonraki bütün dönemler kapalı). **Kısıtsız kapasite** senaryosunda 20 günlük blokaj geçersizdir (fark). Malzemeler kodla seçilir (`dataset.HOLD_*`); bilerek konmuş durumlara (1–9) dokunmaz.
  - Öncelik yönetimi (7.14a, K-195): Baz'da müşteri `MUS-A` öncelik grubu 1, `MUS-C` 4; proje `PRJ-02` 3 (ERP önceliği 2: girilen ezer); sipariş düzeyinde ezen iki satır (`SO-1003` 5: müşterisi `MUS-A`'dan düşük; `SO-1033` 1: müşterisi `MUS-C`'den yüksek). `MUS-B`'ye öncelik grubu girilmemiştir: ERP önceliği (2) geçerlidir. `PRJ-01`'in ERP önceliği aralık dışıdır (durum 10): siparişlerinde hiyerarşi müşteriye geçer. **Kısıtsız kapasite** senaryosunda `MUS-C` öncelik grubu 2 (fark). Mamul tahminleri `MUS-A` müşterilidir (öncelikleri müşteriden gelir: 1); benzetilen ürünün tahmini müşterisizdir (Yok: 5). Kayıtlar koddaki sabitlerdir (`dataset.PRIORITY_*`).
  - Tarihten bağımsızlık (7.11, K-190): set haftanın hangi günü üretilirse üretilsin, bilerek konan sipariş (durum 9) dışında açık sipariş, üretim siparişi ve satın alma siparişi "tarihi geçmiş" olmaz. Üretim günü Cumartesi ya da Pazar'a gelirse 1. haftanın üretim gününden önceye düşen sipariş ve üretim siparişi tarihleri üretim gününe çekilir (satın almada tarih en erken sonraki iş günüdür).
  - Senaryo farkları: **Fazla mesaili** `CG-MON` ek mesai limitini 4 saate, `ISL5`'inkini 3 saate çıkarır (fark satırları) ve `MONTAJ`'a 3 saatlik kendi limitini ekler; **Kısıtsız kapasite** `T-02` bakımını kendisi için geçersiz yapar; **MILP deneme** Baz'ı izlemez (tam kopya).
  - Bağımsız doğrulama: `app/data/synthetic/capacity.py` aynı kuralın saf Python hesabıdır; veritabanındaki hesap bununla birebir karşılaştırılır (test).
- **Birimler:** ADET (0 ondalık), KG (3), M (2), SAAT (2); UnitOfMeasure.Decimals (K-88).

**Bilerek konmuş durumların kurulumu.** `check` ve testler bunları veriden hesaplayarak doğrular; ölçüler kabadır, plan değildir.

| # | Durum | Veride | Denetim |
|---|---|---|---|
| 1 | 5 eksen darboğazı | `M5-01` 75 s/hafta. `MAM-001…003`'ün gövde parçaları yalnız 5 eksende, 3 s/adet. `SO-1011…1016` termini hafta 3–5 | Hafta 3, 4, 5 her biri ≥ %130. Hafta 1–5 toplam ihtiyaç > toplam kapasite. Diğer haftalar ≤ %70 |
| 2 | Uzun temin süreli hammadde | `HAM-012` dövme flanş: tek tedarikçi `TED-04`, 56 gün; stok ve açık sipariş yok. Yalnız `MAM-008` ağacında. `SO-1027` termini hafta 5 | En erken temin + üretim süresi > termin |
| 3 | Tedarikçi limiti dolu | `TED-05` · `SAT-003` (rulman), üretim gününden 4 hafta sonraki ay için limit 400; `PO-2041` + `PO-2042` = 400 teyitli | Limit ayındaki teyitli sipariş = limit; aynı ayda ihtiyaç − stok > 0 |
| 4 | İmkânsız termin | `SO-1040` (`MAM-010`, 20 adet) termini üretim günü + 2 iş günü; stok ve üretim siparişi yok; üretim zinciri 10 iş günü | Termin < en erken tarih |
| 5 | Bakım ve izin | `T-02` bakım hafta 2 Salı–Çarşamba · `W-007` izin hafta 3 · `W-015` rapor hafta 1 | Kayıtlar ufukta, var olan kaynak ve çalışanda |
| 6 | Zincirin derininde Yüksek uyarı (6.5) | `HAM-022`'nin tedarikçi satırında sabit ve değişken tedarik süresi boş (MS.NO_LEADTIME); `HAM-022` açık siparişli `MAM-002`'nin üç seviye altında, iki yolda (MAM-002 → ALT-004 → PRC-011 → HAM-022 ve MAM-002 → ALT-005 → PRC-012 → HAM-022) | Uyarı Yüksek; talep zincirinde o siparişin yolu |
| 7 | Talebi olmayan malzemede Normal uyarı (6.5) | `ALT-099` hiçbir talebin ağacında değil; ağacında bir bileşen miktarı 0 (BOM.ZERO_QTY) | Uyarı Normal |
| 8 | Yok sayılıp kaydı değişince yeniden açılan (6.5) | Durum 6'nın kaydı; yok sayma ve değişiklik (manuel değer ya da yeni versiyon) test ve demo akışındadır | Yok sayıldı → Açık |
| 9 | Tarih geçince çıkan uyarı (6.5) | `SO-1043` istek tarihi üretim günü − 1, açık; `SO-1044` istek tarihi üretim günü, açık · `T-05` kritik gruba (`TORNA`) üye tezgâh, ne kendisinde ne grubunda çalışma düzeni var (K-185); `T-04`'ün grubunda | SO-1043 bugün, SO-1044 ertesi gün SO.PAST_DUE; T-05 SC.RES_NO_CAPACITY (grubu kritik ve rotada olduğu için talep zincirinde: Yüksek; K-185); F-KAPLA aynı uyarı, Normal |
| 10 | Aralık dışı ERP önceliği (7.14a, K-195) | Proje `PRJ-01` ERP önceliği 9 (1–5 dışında) | Veri kalitesinde `SC.PRIORITY_RANGE` (Normal); değer yok sayılır, projenin siparişlerinde hiyerarşi müşteriye geçer |
| 11 | Özel alokasyonu boş malzeme (K-198) | `SAT-010`'un `IsCustomAllocated` alanı boş; `PRJ-02`'ye bağlı 20 adet stoğu var | Veri kalitesinde `SC.MAT_ALLOC_EMPTY` (Yüksek: sahipli arzı var); stok satırı genel sayılır: "Özel alokasyon" Hayır, seviye ve anahtar boş |
| 12 | Sahibi bulunamayan ayrılmış arz (K-198) | `MAM-006` stoğu `PRJ-77`'ye, `SAT-009` stoğu `MUS-Z`'ye, `PO-2073` `SO-9999`'a bağlı; üçü de sistemde yok | Satır genele düşmez: Proje / `PRJ-77`, Müşteri / `MUS-Z`, Sipariş / `SO-9999`. Validasyonda "Bağlı proje / müşteri / sipariş bulunamadı" (Uyarı; veri kalitesinde takip edilmez); satır aktarılır |
| 13 | Alokasyon kuralı: çok seviye ve alternatif (K-199) | `HAM-008` özel alokasyonlu (`MAM-006` → `ALT-017` → `PRC-046` → `HAM-008`): `PRJ-01`'e ayrılmış 50 adet stok ve `SO-1020` satırına ayrılmış `PO-2074`. `SAT-001` özel alokasyonlu; `MAM-006`'nın ağacında yalnız `ALT-017`'nin ikinci ağacında geçer (ayrıca `ALT-012`'de kullanılır): `MUS-B`'ye ayrılmış 15 adet stok | `PRC-046`, `ALT-017` ve `MAM-006`'da Proje / `PRJ-01` ve Sipariş / `SO-1020\|1\|0` "Alt seviye arzı" (kaynak `HAM-008`); `ALT-017` ve `MAM-006`'da Müşteri / `MUS-B` "Alt seviye arzı" (kaynak `SAT-001`). `SAT-009`'daki `MUS-Z` ve `SO-9999` arzları ile `MAM-006`'daki `PRJ-77` stoğu kural satırı açmaz (kullanacak talep yok) |

**Kirli hâl.** `data/synthetic/v0/kirli/` altında varlık başına bir Excel (25 dosya; benzetilen ürün ve tahmin yalnız hazır kural örnekleriyle) ve `beklenen-hatalar.json`; her gün yeniden üretilebildiği için git'e girmez. Komut yazmadan önce klasördeki kendi ürettiği eski dosyaları siler (şablon sürüm sayfası taşıyan `.xlsx` dosyaları, `ekle-guncelle/` altındakiler ve `beklenen-hatalar.json`): artık üretilmeyen tablonun dosyası klasörde kalmaz; başka dosyaya dokunmaz (K-181).
- **Sayfa düzeni (K-110):** şablon üreticisiyle yazılır (`app/integration/template.py`): 1. satır `stg` alan adı, veri 2. satırdan; Açıklama sayfası; gizli `_Surum` sayfasında tablo, sürüm, set, tohum ve üretim günü. Etiketsiz ek alan kolonu yoktur. Etiket veri setinden gelir, veritabanı gerekmez.
- **Kapsam:** Takvim ve duruş entegrasyonla gelmediği için yoktur (K-65). Sipariş, stok ve üretim siparişi üretimde API veya SQL ile gelir; ETL testleri için aynı `stg` biçiminde Excel'e konur.
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

**Veri kalitesi (K-195 madde 12):** `load` ve `reset` işinin sonunda tam kapsamlı "Veri kalitesi" işini kuyruğa koyar (tetikleyen "Geliştirme"; sırada bekleyen iş varsa onunla birleşir). İşi motor servisi çalıştırır (`python -m app.engine.service` açık olmalı; kapalıysa iş kuyrukta bekler, servis açılınca çalışır). Böylece bilerek konmuş durumların uyarıları yüklemeden sonra Veri kalitesi ekranında görünür (ör. Normal sekmesinde `PRJ-01` için "ERP önceliği 1–5 dışında"). Kütüphane işlevleri (`load.load`, `load.reset`; testler bunları çağırır) kuyruğa iş koymaz; işi komut satırı koyar (`load.queue_quality`).

**Hangi komut (K-194):** veritabanında yalnız sentetik veri varsa (aktarım yapılmadıysa) `load` yeter. Aktarım yapıldıysa (sentetik olmayan veri versiyonu ya da lokasyon var; ör. kirli Excel'in aktarımıyla gelen `V-LOC-1`, `R-LOC-1`) `load` durur ve ne yapılacağını söyler; o durumda `reset` gerekir. Emin değilseniz `reset`.

**Sıfırlama (K-153):** geliştirme ya da demo veritabanında tam aktarım yapıldıktan sonra `load` durur (sentetik olmayan veri versiyonu var, K-79). `python -m app.data.synthetic reset` aktarımları geri alır (sentetik olmayan veri versiyonları, onların core satırları ve plan verisi, kural kaynağı satırları, aktarımın eklediği lokasyonlar), aktarımın kapattığı sentetik satırları açar ve sentetik veriyi yeniden yükler; tek işlemdir, staging değişmez. Yalnız sentetik veriyle kurulmuş veritabanında (sentetik veri versiyonu var), onaylı plana bağlı versiyon ve sentetik olmayan parametre seti yokken çalışır; silinecekleri gösterip veritabanının adının yazılmasını ister.

### SQL çekimi (geliştirme 3.3, K-130)

`python -m app.data.synthetic sql` kirli hâli entegrasyon veritabanına yazar (varsayılan `SmartchainIntegration`; testte `_test` ile biter): `ERP_*` ham tablolar, `View_*` ve `ERP_LoadLog`'da biten bir toplu satır. Kaynak Excel'le aynı olduğu için H1–H4 aynıdır; `tests/test_pull_dirty.py` iki yolun sonucunu birebir karşılaştırır.

- **Gerçekçi üç tablo:** Malzeme (`ERP_Material` ve `ERP_ItemGroup`, başka kolon adları, join), Ürün ağacı (`ERP_BOM`, başka kolon adları), Satış siparişi (`ERP_SalesOrder`, başka kolon adları, tarih metin). Kurulumda örnek alınabilir.
- **Düz 20 tablo:** `ERP_<tablo>` ve `SELECT <kolonlar>`. Yalnız test içindir, müşteriye örnek değildir.
- **Demo:** Malzeme, Ürün ağacı, Rota, Stok, Satış siparişi ve Üretim siparişi SQL; kalanı Excel.
- **Kilit:** Yalnız `_test` ile biten ya da bu komutun açtığı veritabanına yazar; ham tablolar ve view'lar yeniden açılır.

### Hazır kural örnekleri (geliştirme 3.4, K-137)

- **Kapsam:** Kirli hâlde her hazır validasyon kuralı için en az bir satır bulunur (docs/06 fonksiyon 04 tablosu; yapısal kontroller H1–H4 ve ön kontrol testleriyle zaten kapsanır). Excel ve SQL aynı kaynaktan yazılır; iki yol aynı bulguları verir.
- **Yer:** Örnekler kendi satırlarındadır (`V-` ile başlayan kodlar ya da ayrı malzeme ve sipariş numaraları); bilerek konmuş durumlara (1–5) ve H1–H4'e dokunmaz, başka satırı zincirleme etkilemez. Tablolar arası kurallar için öteki tablodaki karşılığı da eklenir (ör. `IsNonStockable` malzemeye stok satırı).
- **Beklenen:** `beklenen-hatalar.json`'da kural kodu, tablo, satır anahtarı, sınıf ve mesaj; test (`tests/test_validation_dirty.py`) her aktif hazır kuralın en az bir bulgu verdiğini ve beklenmeyen satırda bulgu çıkmadığını denetler. H3 negatif miktar `ALL.NEGATIVE`'dir; H2 `SO.REF_MATERIAL` ve `BOM.REF_COMPONENT`'tir (4.4).
- **Ekle / güncelle partisi:** Demo için ikinci bir küçük dosya (`kirli/ekle-guncelle/`): güncel hâlde bir kaydı değiştirir ve bir küme kuralını tetikler (ör. MaterialSupplier kota toplamı); güncel hâlin işlenişini gösterir (K-133).
- **Mesajlar:** H1–H4 mesajları 3.4'te kesinleşir; hazır kuralların mesajları kataloğun mesajıdır.

### Referans ve bütünlük örnekleri (geliştirme 4.4, K-146)

- **Kapsam:** Kirli hâlde her referans, pasif ebeveyn ve bütünlük kuralı için en az bir satır bulunur (docs/06 fonksiyon 04; ilişki haritası docs/03). Zorunlu ilişkide tanımsız kod (Hata), isteğe bağlı bağlantıda tanımsız kod (Uyarı), pasif ebeveyne bakan satır (`L-` ile başlayan pasif malzeme, müşteri, tedarikçi, kaynak ve kaynak grubu; Uyarı ya da Bilgi), bağı eksik ebeveyn (aktif versiyonu olmayan üretilen malzeme, tedarikçisi olmayan satın alınan malzeme, kaynaksız grup…).
- **Yer:** Örnekler kendi satırlarındadır (`V-` ve `L-` ile başlayan kodlar, ayrı sipariş ve üretim siparişi numaraları); bilerek konmuş durumlara ve H1–H4'e dokunmaz. Temiz hâlde yeni kurallar bulgu vermez; önceki örneklerin yeni kurallara takılan satırları düzeltilir ya da beklenene eklenir.
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

Plan fikstürü (K-205, geliştirme 8.0): elle yazılmaz; sentetik veri tarafındaki basit bir betik (`app/data/synthetic/plan.py`) bütün sentetik veri için üretir ve dondurur (`plan_fixture.json`, repoda). Kural bilerek basittir: talepten geriye, ağacı patlatarak, kapasite sınırı olmadan; optimizasyon yok. Amaç doğru plan değil, tutarlı ve dolu plan; betik ürünün planlama mantığına girmez. 10.8'de gerçek motorun kabul testine dönüşür.

- **Kural (hafta hafta):** malzemeler düşük seviye koduyla (talepten hammaddeye) netlenir; her malzeme × alokasyon anahtarı ayrı hesap. Brüt ihtiyaç (talep ve üst seviyeden bağımlı ihtiyaç) önce mevcut arzdan (stok ilk haftada, açık satın alma siparişi teslim haftasında, açık üretim siparişi bitiş haftasında) karşılanır; eksik aynı haftada tek tedarik planı kaydıyla kapanır: üretilebilen malzemede üretim planı (varsayılan versiyon; fason rotada tedarikçi ve sipariş tarihi), öteki malzemede satın alma planı (öncelikli tedarikçi; asgari sipariş miktarı ve sipariş lotuyla yuvarlanır; sipariş tarihi = dönem başı − tedarik süresi, dönem kaydırılmaz). Özel anahtarlı eksik önce genel serbest arzdan alokasyon transferiyle, kalanı anahtarlı kayıtla kapanır. Üretim kaydının bileşen ihtiyacı türetmeyle aynı kuralla bir alt seviyeye geçer. Grup × hafta yükü kullanılabilir kapasiteyi aşarsa aşan kısım ek mesai limitine kadar ek mesai olur. Pegging netlemenin eşleşmelerinden kurulur (K-202 transfer kuralıyla).
- **Zaman ve kayıtlar:** dosyada zaman sentetik verinin haftasıdır (1 = üretim gününün haftası), kayıtlar iş anahtarıyla tutulur; Id ve tarih yoktur. Yükleyici kodları güncel veri versiyonunda Id'ye, haftaları senaryonun plan dönemlerine çevirir. Dosya üretildiği günü taşır: sentetik verinin bazı tarihleri (tahmin dönemleri, iş günüyle hesaplanan teslimler) üretim gününe göre hafta değiştirdiği için veri başka bir günde üretildiyse aynı betik o gün için planı bellekte üretir (bakiye bozulmasın diye); dosya kendi gününün planıdır.
- **Üç plan:** **Baz · güncel** (12 durumun hepsi; ek mesai açık), **Baz · önceki gece** (dünkü gece sonucu; birkaç kayıt farklı: iki satın alma planı bir hafta önde, iki üretim planı %10 fazla, elle değiştirilmiş kayıt yok) ve **Fazla mesaili** (sentetik senaryo; daha çok ek mesai, daha az gecikme). Her plan bir gece sonucu (`planning.Scenario`) ve bir plan hesabıdır (`PlanRun`; EngineUsed "Kısıtsız MRP", Solver "Fikstür").
- **Bilerek konmuş durumlar (12):** kısmen zamanında, kısmen geç sipariş (SO-1027, ayrıca ISL5 siparişleri SO-1012 ve SO-1014) · hiç karşılanamayan sipariş (SO-1040) · kapasitesi dolan kaynak grubu ve ek mesai (ISL5; aşım ek mesaiden sonra da kalır) · özel alokasyonlu talep ve genelden transfer (SAT-009, MUS-A; pegging'de arz Stok, Genelden = Evet) · kullanılmayan ayrılmış arz (MUS-Z stoğu, SO-9999 satın alma satırı) · fason üretim (F-KAPLA rotalı parçalar, tedarikçi TED-08, sipariş tarihiyle) · iki haftaya bölünmüş mevcut üretim siparişi (WO-5012) · sabitlenmiş (ALT-001) ve elle değiştirilmiş (ALT-002) kayıt · alternatif üretim versiyonu (ALT-017 V2) · yuvarlanmış satın alma (asgari 50'lik malzemeler; artan stok) · sipariş tarihi geçmişte kalan satın alma planı (HAM-012, 56 gün) · plana dahil olmayan talep (SO-1041, SO-1042 teklif).
- **Uyarı ve metrik:** ORDER_LATE, ORDER_UNMET, FORECAST_UNMET, CAP_OVERLOAD, OVERTIME_USE, PURCHASE_LATE, MAT_EXCESS (değer, mesaj, dönem ve ilgili kayıtla, K-206; önem yazılmaz) ve `app/planning/metrics.py` kataloğu.
- **Komutlar:** `python -m app.data.synthetic plan` yükler (önceki fikstür planları silinir; geliştirme veritabanında onay ister) · `plan --regenerate` yalnız dosyayı yeniden üretir · `plan --summary` plan başına satır sayıları, 12 durumun kanıt satırları ve tutarlılık denetimleri. `load` ve `reset` sonunda planı da yükler.
- **Tutarlılık:** yükleme tek işlemdir; denetimlerden (`app/planning/checks.py`: bakiye, talep, arz, yük ve ek mesai, pegging, uyarı) biri düşerse hiçbir şey yazılmaz. Dosya bayatlarsa (sentetik veri ya da kural değişti) test düşer.
- **Ufuk ön koşulu (K-209):** fikstür haftalarla kurulduğu için senaryonun plan ekseni fikstürün 13 haftasını tam haftalık dönemlerle kapsamalıdır (ay sonunda kesilen kısa hafta ya da aylık dönem kapsamaz). `plan`, `load` ve `reset` onaydan ve silmeden önce denetler; kapsamıyorsa durur ve ne yapılacağını yazar ("Parametreler › Ufuk: haftalık kısım en az 13 hafta olmalı (ör. Hafta · 4 ay)"). Varsayılan "Hafta · 3 ay" ayın son günlerinde 10–12 hafta verir; sentetik veriyle çalışılan veritabanında haftalık kısım en az 4 ay olmalıdır. Kullanıcının ufuk ayarına dokunulmaz (K-175); test veritabanında Baz oturum başında "Hafta · 4 ay"a çekilir.

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
| Kaynak modeli revizyonu: tip, kritik, birim ve fasoncu grupta; işçiler yalnız yetkinlik gruplarında; fason grupları; vardiya yok (K-180, K-181) | uygulandı (7.5) |
| Kilogramlı malzemelere miktar (güvenlik stoğu, lot) | açık: sonraya bırakıldı (1.3 demosu); KG'de 3 ondalık şimdilik yalnız testte görülür |
