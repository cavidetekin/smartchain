# Ara iş · Özel alokasyon alan revizyonu

> **Durum:** plan onaylandı (24.11.2026); açık noktaların kararları sondaki "Kararlar" bölümünde. Adım Cavide'nin demo onayından sonra kapanır (commit, push ve "uygulandı" o zaman).
> **Numaralar:** karar K-198, geçiş 0077, sürüm 0.57.0. Yeni ekran yok, tek parça, tek demo.

## Bağlam

Bugün "özel takip" altı tabloda ERP'den gelen bir bayraktır (`IsCustomTracked`), sahiplik yalnız projeye kuruludur, paylaşım proje grubu ve takip kuralıyla anlatılır (K-17, K-113, K-119; açık konu A-39). 23–24.11 görüşmelerinde tek kural kabul edildi: **anahtarlı arz yalnız sahibine gider, anahtarsız arz herkese açıktır** (not dosyası §1, §2). Bu adım o kuralın **veri tarafını** kurar: ad değişir, arz satırları seviye ve anahtar taşır, satır bayrağını sistem hesaplar, proje grubu ve takip kuralı kalkar. Motor, pegging, `MaterialAllocationRule` (7.15) ve parametreler (7.17) bu adımda yok.

## Bugünkü durum (araştırma)

- `IsCustomTracked`: Material, Customer, SalesOrderLine, Stock, WorkOrder, PurchaseOrderLine; her biri `stg`, `prc`, `core`'da (18 kolon). Malzemede kaynak "Kural ya da elle" (bugün elle girilebilir); ötekilerde "ERP, yoksa kural".
- Arzın sahibi: `stg`'de `ProjectCode`, `CustomerCode`, `SalesOrderNo`, `SalesOrderLineNo`, `SalesOrderLineItemNo`; `core`'da `ProjectId`, `CustomerId`, `SalesOrderLineId`. Stok'ta bu alanlar anahtarın parçası ve "Zorunlu (doluysa)"; iş emri ve satın almada isteğe bağlı (bulunamazsa uyarı, bağ boş yazılır).
- **Kalemi boş sipariş bağı bugün sessizce yanlış çözülüyor:** çok alanlı ilişkide yalnız ilk alan eşleşmek zorunda; yüklemede `ORDER BY Id` ile siparişin **en küçük Id'li satırına** bağlanıyor (`app/transfer/engine.py` `Resolver.resolve`). 4c bunu düzeltmeyi gerektirir.
- `ProjectGroup`: `stg`, `prc`, `core` tablosu; `Project.ProjectGroupId` ve `Project.TrackingRule`; kısmi aktarımda Talep grubunda; İşlem verisi'nde sekme; ilişki kontrolü `PRJ.REF_PROJECT_GROUP`.
- `planning.PlannedOrder.ProjectId`: yalnız modelde; hiçbir kod okumuyor ya da yazmıyor.
- Yüklemede başka tablodan hesaplanan `core` alanı için hazır kaynak adı var: **"Yüklemede diğer tablolardan"** (`app/manual/__init__.py` `NOT_MANUAL_SOURCES`): alan listede görünür, sözlükte satırı olur, elle değiştirilemez. `stg`'de olmayan alan `prc`'de de olmaz; veri kuralı ona yazamaz.
- Başka tablo değişince `core` satırını yeniden hesaplayan bir mekanizma bugün yok (kapasite tetikleyicisi yalnız önbelleği düşürür).
- Motor (`app/engine`) bu alanların hiçbirini okumuyor.

## Kararların uygulanışı

| # | Karar (Onaylı) | Uygulama |
|---|---|---|
| 1 | `IsCustomTracked` → `IsCustomAllocated`, arayüzde "Özel alokasyon" | docs/02, 03 → `db/generate.py`; kolonlar yeniden adlandırılır (veri korunur); kod, sentetik, test |
| 2 | Malzemede yalnız ERP ya da veri kuralı; elle girilmez; boşsa uyarı | kaynak "ERP, yoksa kural"; `app/manual` "Manuel olamaz" listesine eklenir; yeni kontrol `SC.MAT_ALLOC_EMPTY` |
| 3 | Stok, Üretim siparişi, Satın alma satırı: alan `stg`/`prc`'den çıkar, `core`'da kalır (sistem). Müşteri ve Satış siparişi satırı: tamamen kalkar | kaynak "Yüklemede diğer tablolardan" |
| 4 | `AllocationLevel`, `AllocationKey` (üç arz tablosu, `core`) | aşağıda "Hesap" |
| 5 | `PlannedOrder`: `ProjectId` kalkar; üç alan eklenir (motor yazar) | docs/02, docs/09; fikstür ve sahte motor değişmez (alan boş) |
| 6 | `ProjectGroup` ve `TrackingRule` kalkar; `Project` kalır | aşağıdaki listeler |
| 7 | `BorrowPayback` kalır | dokunulmaz |

## Etkilenen tablo ve alanlar

| Tablo | `stg` / `prc` | `core` |
|---|---|---|
| Material | `IsCustomTracked` → `IsCustomAllocated` | aynı; kaynak "ERP, yoksa kural"; Manuel olamaz |
| Customer | `IsCustomTracked` **kalkar** | **kalkar** |
| SalesOrderLine | `IsCustomTracked` **kalkar** | **kalkar** |
| Stock · WorkOrder · PurchaseOrderLine | `IsCustomTracked` **kalkar** (sahip alanları değişmez) | `IsCustomTracked` → `IsCustomAllocated` (bit, sistem); **yeni** `AllocationLevel` nvarchar(10) "Sipariş \| Proje \| Müşteri", **yeni** `AllocationKey` nvarchar(60); 4c için öneri: **yeni** `SalesOrderNo` nvarchar(30) (aşağıda) |
| Project | `ProjectGroupCode`, `TrackingRule` **kalkar** | `ProjectGroupId`, `TrackingRule` **kalkar** |
| ProjectGroup | tablo **kalkar** (`stg`, `prc`) | tablo **kalkar** |
| planning.PlannedOrder | — | `ProjectId` ve indeksi **kalkar**; **yeni** `IsCustomAllocated`, `AllocationLevel`, `AllocationKey` (kaynak Motor) |

Sözleşme sürümü (docs/03 katalog, SÜRÜM) artar: Material, Customer, Project, SalesOrderLine, Stock, WorkOrder, PurchaseOrderLine; ProjectGroup katalogdan çıkar. Şablonlar ve `tests/template_versions.json` buna göre.

## Hesap (seviye, anahtar, satır bayrağı)

Yeni modül `app/allocation/` (tek işlev, SQL; aktarım, sentetik yükleme ve yeniden hesap aynı işlevi kullanır):

- Malzemenin güncel kaydında `IsCustomAllocated` = Evet **değilse** (Hayır ya da boş): satırda `IsCustomAllocated` = Hayır, seviye ve anahtar boş (4e, 4f).
- Evetse, dolu olan en detaylı sahip: sipariş → proje → müşteri (4a).
  - Sipariş satırı: seviye "Sipariş", anahtar `SiparişNo|SatırNo|AltSatırNo` (ör. `SO-1003|10|1`).
  - Kalemi boş sipariş: seviye "Sipariş", anahtar yalnız sipariş no (4c).
  - Proje: `Project.Code`; Müşteri: `Customer.Code`.
  - Lokasyon anahtara girmez (4d).
- Hiç sahip yoksa: Hayır, boş (4g).
- İş emri ve satın almada bulunamayan sahip bağı bugünkü gibi boş yazılır (uyarı); o satır bir alt seviyeye ya da genele düşer.

**Yüklemenin hangi aşaması:** kod→Id çözümünden sonra, değişiklik karşılaştırmasından önce (`transfer_table` içinde `_self_refs` ile `manual.apply_versioned` arasında yeni adım). Alanlar `app/transfer/mapping.py`'de "hesaplanan" olarak kayıtlanır ve karşılaştırmaya girer: değer değişirse satır yeni versiyon açar, Geçmiş'te görünür. Manuel değer bu alanlara uygulanmaz.

**Yeniden hesap (öneri, Claude):** her aktarım koşusunun sonunda (tam ve kısmi), o koşuda yüklenmeyen arz tablolarının güncel satırları için aynı işlev çalışır; değeri değişen satır aynı aktarımın versiyonuyla yeni versiyon açar. Böylece:
- kısmi aktarımda yalnız Malzeme gelip `IsCustomAllocated` değiştiyse arz satırları güncellenir;
- yalnız Talep gelip proje ya da müşteri kodu değiştiyse anahtar güncellenir;
- hata eşiğini aştığı için atlanan arz tablosu eski değerle kalmaz.
Malzemede alan elle girilemediği için (karar 2) aktarım dışında değişme yolu yoktur; manuel değer kancası gerekmez. Sentetik `load` / `reset` doğrudan `core`'a yazdığı için sonunda aynı işlevi çağırır.

## 4c · Kalemsiz arz (karar: A, genişletilmiş)

Stok, Üretim siparişi ve Satın alma satırının `core` tablosuna ERP'den geldiği gibi üç alan eklenir: `SalesOrderNo`, `SalesOrderLineNo`, `SalesOrderLineItemNo` (arayüzde Sipariş no, Satır no, Alt satır no; satın alma satırında "Satış sipariş no / satır no / alt satır no", tablonun kendi "Sipariş no" ve "Satır no" alanlarıyla karışmasın). `SalesOrderLineId` iç bağ olarak kalır: sipariş no ve satır no doluysa ve satır bulunuyorsa dolar; kalemsiz arzda boştur. Kalemsiz arz artık siparişin ilk satırına bağlanmaz; validasyon sipariş no'nun o lokasyonda en az bir satırını arar. Stok'un tekil anahtarında `SalesOrderLineId` yerine bu üç alan vardır.

## Geçiş (tek geçiş: 0077; K-197'ye uygun, değerler geçişte sabit)

Sıra ve veri etkisi:

| Adım | Veri |
|---|---|
| 1. `IsCustomTracked` → `IsCustomAllocated`: Material (`stg`, `prc`, `core`), Stock / WorkOrder / PurchaseOrderLine (`core`); `adm.FieldDefinition` satırları yeniden adlandırılır (kullanıcının etiketi korunur; standart etiket "Özel alokasyon") | korunur |
| 2. Üç arz tablosuna `AllocationLevel`, `AllocationKey` (ve A seçilirse `SalesOrderNo`); `PlannedOrder`'a üç alan | boş gelir; değerler geçişte hesaplanmaz |
| 3. Kalkan kolonlar: Customer ve SalesOrderLine `IsCustomTracked` (üç katman); Stock / WorkOrder / PurchaseOrderLine `IsCustomTracked` (`stg`, `prc`); Project `ProjectGroupCode` / `ProjectGroupId` / `TrackingRule`; `PlannedOrder.ProjectId` ve indeksi | **kayıp** |
| 4. `ProjectGroup` tablosu (`stg`, `prc`, `core`) düşer | **kayıp** |
| 5. `adm` temizliği: kalkan alanların `FieldDefinition`, `ManualValue` ve değer kaynağı satırları; `Material.IsCustomAllocated` için girilmiş manuel değerler; `EntityCatalog`'da ProjectGroup; üç `*.CUSTOM_NO_OWNER` ve `PRJ.REF_PROJECT_GROUP` kuralı ve bulguları (kural eşitlemesi zaten siler) | **kayıp** |

Geri alma (`downgrade`) yapıyı geri kurar, veriyi getirmez. İleri–geri–ileri testi yazılır. `db/sql/0001*.sql` ve eski geçişler değişmez.

Kalkan alanlara bağlı **kullanıcı tanımlı** veri kuralı, validasyon kuralı ve kayıtlı görünüm: açık nokta 6.

**Geliştirme veritabanında Cavide'nin çalıştıracağı komutlar (K-165; ben çalıştırmam), sırayla:**
1. `alembic -c db/alembic.ini current` (beklenen: 0076)
2. `alembic -c db/alembic.ini upgrade head`
3. `python -m app.data.synthetic reset` (yapı ve sentetik veri değişti; `load` yetmez: aktarılmış eski kayıtlar ve Proje grubu izleri temizlenmeli)
4. `python -m app.data.synthetic excel` ve `sql` (kirli hâl ve şablonlar yeni sözleşmeyle; demo öncesi)
5. `python -m app.data.synthetic rules` (demo veri kuralları, kullanıyorsanız)

## Docs (K-54: önce docs)

| Dosya | Değişecek yerler |
|---|---|
| `docs/00-kararlar.md` | **K-198** (yeni; bu planın kararları). Eski kararlara "K-198 ile değişti" notu: K-17 (izolasyon ve grup içi paylaşım), K-113, K-119, K-120, K-123, K-124, K-125 (bayraklar), K-150 ve K-169 (Talep grubu ve sekmeler: Proje grubu çıkar), K-182, K-195 ("Proje grubu hiyerarşiye girmez" cümlesi), K-170 (Manuel olamayan alanlar). A-39 (öneri c) |
| `docs/02-veri-modeli.md` | yukarıdaki tablo ve alanlar; kaynak açıklamaları (L84–93: "Kural ya da elle" örneği değişir, "Yüklemede diğer tablolardan" satırı); tablo listelerinden ProjectGroup; "Proje" ilkesi (L46) |
| `docs/03-entegrasyon.md` | `stg` tabloları; katalog satırı ve sürümler; ilişki tablosundan `PRJ.REF_PROJECT_GROUP`; "proje grubu lokasyondan bağımsız" cümlesi; kalemi boş sipariş bağının kuralı (4c) |
| `docs/05-ekranlar.md` | İşlem verisi sekmeleri (Talep: Satış siparişi · Tahmin · Proje) |
| `docs/06-fonksiyonlar.md` | F04: üç `*.CUSTOM_NO_OWNER` ve `PRJ.REF_PROJECT_GROUP` çıkar, "Müşteri ve Proje grubu" cümlesi; F06 kısmi aktarım grupları ve örneği; F25'teki proje grubu cümlesi; F29'daki proje grubu cümleleri (açık nokta 8) |
| `docs/08-api.md` | İşlem verisi 12 → 11 tablo |
| `docs/09-motor-arayuzu.md` | planlı sipariş alanları (`ProjectId` yok; üç alokasyon alanı, motor yazar) |
| `docs/11-sentetik-veri.md` | yeni örnekler (öneri a), Proje grubu çıkar |
| `docs/07-veritabani.md`, `db/models.py` | üretilir (`python db/generate.py`) |
| `GELISTIRME_ADIMLARI.md` | Ara iş "uygulandı"; 5.3 ve 6. aşamadaki "Proje grubu" geçen satırlara not; A-39 özeti |

`CLAUDE.md` değişmez.

## Kod (güncel sayılar; docs, eski geçişler ve `db/sql` hariç)

- **ProjectGroup:** 28 dosya (sunucu ve veri 16, test 7, ön yüz 5). **IsCustomTracked:** 12 dosya (ön yüzde yok). **TrackingRule:** 6 dosya. **`PlannedOrder.ProjectId`:** yalnız `db/models.py`.
- **Şema:** `db/generate.py` (`REF_TARGET["ProjectGroupId"]`), üretilen `db/models.py`, geçiş 0077.
- **Entegrasyon ve doğrulama:** `app/integration/references.py` (proje grubu ilişkisi; 4c kuralı), `contract.py`, `template_examples.json`; `app/validation/catalog.py` (üç kural, `UNTRACKED`), `sqlkit.py` (`CODE_REFS`).
- **Aktarım:** `app/transfer/groups.py` (Talep grubu), `mapping.py` (hesaplanan alanlar), `engine.py` (hesap adımı, koşu sonu yeniden hesap, kalemi boş sipariş çözümü); yeni `app/allocation/`.
- **Manuel ve sözlük:** `app/manual/__init__.py` (`SCREEN_TABLES`; `Material.IsCustomAllocated` Manuel olamaz), `db/dictionary.py` (değişmez; kaynak adı işi görür).
- **Kalite:** `app/quality/checks.py` (`SC.MAT_ALLOC_EMPTY`).
- **Listeler:** `app/api/lists/master_data.py` (ProjectGroup tanımı ve sekmesi; varsayılan gizli alanlar), `materials.py`, `relations.py`; `app/api/audit_format.py` (yeni alan etiketleri).
- **Sentetik:** `dataset.py`, `examples.py`, `excel.py`, `load.py`, `situations.py`.
- **Ön yüz:** `screens/dataScreenTabs.ts`, `i18n/tr.ts`, `screens/DataScreen.tsx` (genişlik ipucu), `MasterData.test.tsx`, `Transfer.test.tsx`.
- **Motor:** kod değişmez (`app/priorities`'te yalnız yorum).

## Ekranlar

| Ekran | Değişiklik |
|---|---|
| Ana veri › Malzeme | kolon "Özel alokasyon"; ✎ yok (elle girilemez); Alanlar › Manuel ayarında açılamaz |
| Ana veri › Müşteri | "Özel takip" kolonu yok |
| İşlem verisi › Talep | "Proje grubu" tablosu yok (11 tablo); Proje'de "Proje grubu" ve "Takip kuralı" kolonları ve "Proje grubu ·" ilişkili alanları yok; Satış siparişi'nde "Özel takip" yok |
| İşlem verisi › Stok, Üretim siparişi, Satın alma satırı | "Özel alokasyon" (salt okunur, hesaplanan); "Alokasyon seviyesi" ve "Alokasyon anahtarı" Alanlar'da, kapalı gelir (öneri b); A seçilirse "Sipariş no" |
| Veri alma, Şablonlar, Kısmi aktarım | Proje grubu şablonu ve satırı yok; Talep grubu üç tablo; şablonlarda yeni kolon adları |
| Validasyon | üç "özel takipli … sahibi yok" kuralı ve proje grubu ilişki kuralı yok |
| Veri kalitesi | yeni uyarı "Özel alokasyon boş" (Malzeme) |
| Detay kartları | değişmez (Proje, Stok, iş emri ve satın alma kartında yalnız Geçmiş; Geçmiş'te yeni alanlar görünür) |

## Önerilerin değerlendirmesi (onay gerekir)

- **a. Sentetik örnekler:** uygun. Önerilen kayıtlar (kodlar uygulamada kesinleşir, docs/11'e yazılır):
  - Özel alokasyonlu malzemeler: `MAM-006` (bugün de öyle) ve ağacındaki bir hammadde; `IsCustomAllocated` **boş** bir malzeme (4f; "bilerek konmuş durum" 11).
  - Stok: `MAM-006` · `PRJ-01` (var) → Proje / `PRJ-01`; yeni: `MAM-006` · `MUS-A` → Müşteri / `MUS-A`; yeni: `MAM-006` · `SO-1020` satırı → Sipariş / `SO-1020|10|0`.
  - Üretim siparişi: yeni, `MAM-006` · `PRJ-02` → Proje / `PRJ-02`. `WO-5001` (özel alokasyonlu olmayan `MAM-004`, müşteri ve sipariş dolu) **4e örneği olarak bugün zaten var**: Hayır, boş.
  - Satın alma satırı: özel alokasyonlu hammaddede kalemi boş, yalnız sipariş no (4c) → Sipariş / `SO-1021`; bir satır müşteriye ayrılmış.
  - Boş malzemede sahipli bir stok satırı (4f: genel sayılır).
- **b. Gösterim:** uygun; `master_data.py`'deki varsayılan gizli listesine iki alan eklenir.
- **c. A-39'un kapanması:** kısmen. (1), (3), (5) bu adımda çözülür; (2) netleştirme ve pegging sırası ile (4) ölçek motor ve pegging konusudur. Önerim: A-39 kapanır, kalan iki madde için not dosyası §4–§8'e ve 7.17 / 10.x adımlarına atıf yazılır (yeni açık konu açılmaz).
- **d. Eski "7.15 Pegging kuralları" atıfları:** K-192'ye "(24.11.2026: 7.17 oldu)" notu eklenir. `plans/7.12.md` geçmiş bir planın kaydıdır; önerim değiştirmemek (eski planlar güncellenmiyor).

## Testler (Smartchain_test)

- **Hesap:** 4a–4g'nin her dalı (sipariş, kalemi boş sipariş, proje, müşteri, sahipsiz; malzeme Hayır; malzeme boş); anahtar biçimi; lokasyonun girmemesi; iş emrinde bulunamayan sahip.
- **Aktarım:** alanların yazılması ve versiyon açması; kısmi aktarımda yalnız Malzeme, yalnız Talep; atlanan tablo; Talep grubu K-150 ile birebir; eşleme her `core` kolonunu kapsar; kalemi boş sipariş artık en küçük Id'li satıra bağlanmaz.
- **Sözleşme:** şablon sürümleri, örnekler, sözlük (yeni alanlar Manuel olamaz; `Material.IsCustomAllocated` Manuel olamaz).
- **Kalite ve validasyon:** `SC.MAT_ALLOC_EMPTY`; kalkan kurallar katalogda ve docs/06'da yok.
- **Geçiş:** ileri–geri–ileri; sıfırdan kurulum ile adım adım yükseltme aynı (K-197 testi).
- **Listeler ve ön yüz:** İşlem verisi 11 tablo; varsayılan görünür alanlar; Malzeme'de ✎ yok; sekme testleri.
- **Sentetik:** örnek kayıtlar; kirli hâl (Excel, SQL) yeni sözleşmeyle.
- Zincir: `npm run build` → pytest → `npm test` → `tsc`. Görsel kontrol (Playwright, yalnız Smartchain_test): Ana veri › Malzeme ve Müşteri; İşlem verisi › Proje, Satış siparişi, Stok, Üretim siparişi, Satın alma satırı (varsayılan ve alanlar açık); Kısmi aktarım; Veri kalitesi; dar pencere. Perf testi koşulmaz.

## Demo (sentetik veriyle)

| Tarayıcı · kullanıcı | Ne yapılır | Ne görülmeli |
|---|---|---|
| Key user | Ana veri › Malzeme | "Özel alokasyon" kolonu; `MAM-006` Evet; hücrede ✎ yok. Güncel kod işareti: kolon adı "Özel alokasyon" |
| Key user | İşlem verisi › Talep | tablo seçiminde "Proje grubu" yok; Proje'de "Takip kuralı" yok |
| Key user | İşlem verisi › Stok; Alanlar'dan seviye ve anahtarı aç | `MAM-006` satırları: Proje / `PRJ-01`, Müşteri / `MUS-A`, Sipariş / `SO-1020|10|0`; boş malzemenin sahipli stoğu: Hayır, boş |
| Key user | İşlem verisi › Üretim siparişi | `WO-5001`: müşteri ve sipariş dolu, "Özel alokasyon" Hayır, seviye ve anahtar boş (4e); `PRJ-02` iş emri: Proje / `PRJ-02` |
| Key user | İşlem verisi › Satın alma satırı | kalemi boş siparişli satır: Sipariş / `SO-1021` (4c) |
| Key user | Veri kalitesi | "Özel alokasyon boş" uyarısı, boş malzemede |
| Admin | Malzeme Excel'inde `MAM-006`'yı Hayır yapıp yalnız Ana veri grubunu aktar | Stok ve iş emrinde `MAM-006` satırları Hayır, boş; satırın Geçmiş'inde değişiklik |
| End user | aynı listeler | salt okunur; alanlar görünür |

## Kararlar (Cavide, 24.11.2026)

1. **Kalemsiz sipariş bağı:** A, genişletilmiş (yukarıda "4c").
2. **Anahtar biçimi:** kalemli anahtar her zaman üç parça (alt satır yoksa 0): `SO-1003|10|1`, `SO-1003|10|0`. Kalemsiz arzın anahtarı yalnız sipariş no: `SO-1021`.
3. **Kalemsiz sipariş ve lokasyon:** lokasyon anahtara girmez; eşleşme zaten aynı malzeme ve lokasyon içinde yapılır, anahtar ek koşuldur.
4. **Yeniden hesap:** her aktarımın sonunda aktarılmayan arz tabloları da yeniden hesaplanır; değeri değişen satır yeni versiyon açar ve Geçmiş'te görünür.
5. **"Özel alokasyon boş" uyarısı:** `SC.MAT_ALLOC_EMPTY`; önem Normal, malzemenin sahipli arzı varsa Yüksek. Özel alokasyonlu olmayan malzemede sahipli arz için uyarı yok.
6. **Kalkan alanları kullanan kullanıcı tanımları** (veri kuralı, validasyon kuralı, kayıtlı görünüm): silinir ve geçiş çıktısında listelenir; malzemedeki eski adı kullananlar yeni ada çevrilir.
7. **Malzemede elle girilmiş "özel takip" değerleri** geçişte silinir; ERP ya da kural değeri geçerli olur.
8. **Fonksiyon metinleri** (docs/06: 29, 30, 35, 58, 64, 70, 72): yalnız "proje grubu" ve "takip kuralı" geçen cümleler çıkar; yerine "özel alokasyon kuralı (K-198); netleştirme sırası Aşama 10'da yeniden yazılacak" notu. Tam yeniden yazım 10.1 ve 10.6'da.
9. **Arayüz adları:** "Özel alokasyon" · "Alokasyon seviyesi" (Sipariş · Proje · Müşteri) · "Alokasyon anahtarı".
10. **`PlannedOrder`'daki üç alan** yalnız yapı olarak açılır, boş kalır; örnek veri 8.0'da.
11. **A-39 kapanır;** kalan iki maddesi için not dosyasına ve 7.17 / Aşama 10 adımlarına atıf yazılır, yeni açık konu açılmaz. K-192'ye "(24.11.2026: 7.17 oldu)" notu; `plans/7.12.md` değişmez.
12. **Sürüm 0.57.0, geçiş 0077, karar K-198, tek commit.**

**Onaylanan öneriler:** sentetik örnekler (plandaki liste); gösterim ("Özel alokasyon" açık, seviye ve anahtar kapalı); `app/allocation` modülü, hesabın yüklemedeki yeri ve referans kontrolü.

**Uygulamada kesinleşenler (Claude; raporda ayrıca yazıldı):** Sipariş no açık, Satır no ve Alt satır no kapalı gelir. Satın alma satırında üç alanın etiketi "Satış sipariş …" ile başlar. Sentetik kodlar: özel alokasyonlu hammadde `SAT-009`, alanı boş malzeme `SAT-010`, yeni iş emri `WO-5013`, yeni satın alma satırları `PO-2071` (kalemsiz, `SO-1021`) ve `PO-2072` (`MUS-A`).

## Demo kararları (Cavide, 25.11.2026; ilk demodan sonra)

1. **Tek ad takımı:** üç arz tablosunda sahip alanları "Bağlı proje · Bağlı müşteri · Bağlı sipariş no" (açık) ve "Bağlı sipariş satırı · Bağlı sipariş alt satırı" (kapalı). "Sahip" kelimesi bu alanlarda kullanılmaz; adlar tablolarda, Alanlar panelinde, şablonlarda, kural metinlerinde, Geçmiş'te ve sözlükte aynıdır. İlişkili alan grupları "Bağlı proje · …", "Bağlı müşteri · …", "Bağlı sipariş · …".
2. **İç bağ kolonu kalkar:** `SalesOrderLineId` (ve `ProjectId`, `CustomerId`) bu üç tabloda kolon, Alanlar ve şablonda yoktur; veritabanında iç bağ olarak kalır.
3. **Sahibi bulunamayan ya da kapanmış ayrılmış arz genele düşmez;** bir alt seviyeye de düşmez. Anahtar ERP'nin yazdığı en detaylı sahipten kurulur. Uyarı yok.
4. **Kalıcı kural:** aynı alan hangi tabloda olursa olsun aynı etiketi taşır (docs/02; `tests/test_labels.py`).

**Uygulama (Claude):** bulunamayan sahibin kodu kaybolmasın diye arz tablolarının `core`'una `ProjectCode` ve `CustomerCode` eklendi (ERP'den geldiği gibi; sipariş üçlüsü zaten vardı); hesap yalnız bu ham alanlara ve malzemeye bakar. Stok'un sahip ilişkileri "Zorunlu (doluysa)" yerine isteğe bağlı oldu (bulunamayan sahip Uyarı, satır aktarılır); Stok'un tekil anahtarı ham alanlarda. İç bağların kaynağı "Sistem" (veri sözlüğüne girmez). Geçiş 0078.
