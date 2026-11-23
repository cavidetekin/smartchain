# Lokasyon revizyonu (7.14'ten önce ara iş)

> Onaylandı (23.11.2026): kendi verdiğim üç karar ve öneriler a–d onaylı; tedarikçi limiti penceresinde sıra Lokasyon · Tür · Tedarikçi · Malzeme; çok lokasyonlu geçişte kopyalama geçiş çıktısına yazılır (kaç kayıt, hangi lokasyonlara). Uygulandı ve kapandı (sürüm 0.54.0; geçiş 0073). Demo bulgusu: yedi pencerenin lokasyon listesi verideki bütün lokasyonlardır; kaydı olmayan lokasyonda kod listesi boş ("Bu lokasyonda kayıt yok."); tek lokasyon kuralı veride tek lokasyon olmasına bakar (K-194 madde 9).
> **Numaralar:** K-194 (yeni karar). Geçiş 0073. Kapanışta sürüm 0.54.0. Ekran ve fonksiyon numarası değişmez (ekran 30 ve 31; fonksiyon 24, 103, 99).
> **İşaretler:** "Onaylı" = Cavide'nin kararı. "Öneri" = Cavide'nin ayrıca onaylamadığı öneriler (a–d); planda uygulanacak hâliyle yazıldı, istemezseniz çıkarırım. "Öneri (Claude)" = benim eklediğim.
> Tek parça, tek demo. İş demo onayından önce kapanmaz.

## Bağlam

Lokasyon bugün giriş pencerelerinde ayrı alan değil: kod listesinde "lokasyon · kod · ad" olarak yazılıyor (7.10), Fabrika takvimi ise lokasyonsuz ve bütün kaynaklara uygulanıyor. Aktarımla ikinci lokasyon gelince (V-LOC-1, R-LOC-1) aynı kodlu kayıtlar karışıyor ve bir fabrikanın tatili ötekinin kapasitesini düşürüyor. Bu iş lokasyonu her pencerede anahtarın görünen ilk parçası yapar ve Fabrika takvimini lokasyon bazına çevirir.

## Bugünkü durum

- **Pencereler:** `CapacityEntryDialog.tsx` (beş kapasite girişi; Seviye + kod, lokasyon kod listesinde), `SupplierLimits.tsx` (tedarikçi anahtarı `lokasyon|tedarikçi`), `MaterialHolds.tsx` (malzeme anahtarı `lokasyon|malzeme`). Üçünde de `manyLocations` ile "lokasyon · kod" yazımı var.
- **Fabrika takvimi:** `param.FactoryCalendar` lokasyonsuz; giriş altyapısında sahipsiz tür (`entries.py` `Kind(owner=None)`); hesapta gün bazında tek kayıp (`compute.py` `#cap_fc` → `#cap_d.factory`); tetikleyici bütün kaynakları yeniler (`triggers.factory_calendar_changed`); liste `capacity-factory-calendar` lokasyonsuz.
- **Zaman çubuğu:** kapasite girişlerinde birden çok lokasyonda "lokasyon · kod" yazıyor (`CapacityValidity.tsx`); tedarikçi limiti ve malzeme blokajında ve kart başlıklarında yazmıyor.
- **Sentetik kilit:** `load.py` `_lock` mesajı ne yapılacağını söylemiyor.

## Kararlar (K-194)

| # | Karar | Durum |
|---|---|---|
| 1 | Lokasyon her zaman anahtarın parçasıdır; lokasyon taşıyan kayıt giren her Yeni kayıt ve Düzenle penceresinde ayrı ve ilk alandır | Onaylı |
| 2 | Lokasyon seçilince kod listeleri yalnız o lokasyonun kayıtlarını gösterir; lokasyon değişirse seçilmiş kod temizlenir | Onaylı |
| 3 | Veride tek lokasyon varsa alan dolu gelir, yine görünür | Onaylı |
| 4 | Düzenle'de Lokasyon kilitlidir | Onaylı |
| 5 | Bundan sonraki bütün pencereler bu kurala uyar (docs/12 pencere standardı) | Onaylı |
| 6 | Kapsam: Kapasite yönetimi'nin beş girişi, Tedarikçi limiti (Lokasyon → Tedarikçi → Malzeme), Malzeme blokajı (Lokasyon → Malzeme) | Onaylı |
| 7 | Karttan ya da zaman çubuğundan açılan Yeni kayıt'ta lokasyon da dolu gelir | Onaylı |
| 8 | Fabrika takvimi lokasyon bazlı: `LocationId` zorunlu; kayıt yalnız o lokasyonun kaynak gruplarına ve kaynaklarına uygulanır; tabloda Lokasyon kolonu ve İlişkili alanlar'da Lokasyon | Onaylı |
| 9 | Kapasite hesabı, önbellek tetikleyicisi ve Kapasite özeti lokasyona göre; Baz + fark değişmez | Onaylı |
| 10 | Zaman çubuğunun sol kolonu ve kart başlıkları: birden çok lokasyonda kod lokasyonla; tek lokasyonda bugünkü gibi | Onaylı |
| 11 | Sentetik durma mesajına ne yapılacağı eklenir; raporlarda `load` / `reset` ayrımı açık yazılır | Onaylı |
| a | Aramalı listelerde satır "kod · ad"; "lokasyon · kod · ad" yazımı kalkar | Öneri |
| b | Görsel kontrol kurulumunda (yalnız Smartchain_test) ikinci lokasyon ve aynı kodlu kaynak; sentetik sete dokunulmaz | Öneri |
| c | Öteki ekranların lokasyon taşıyan kayıt giren pencereleri listelenir, değiştirilmez; Bekleyen kontroller'e yazılır | Öneri |
| d | Raporda: geliştirme veritabanında çok lokasyonlu durumun nasıl kurulacağı | Öneri |

## Veri modeli ve geçiş 0073

- `param.FactoryCalendar.LocationId` (int, FK `core.Location`, IX, zorunlu). Sıra: docs/02 → `python db/generate.py` → geçiş (K-64).
- `resolve.FIELDS["FactoryCalendar"]` başına `LocationId` (fark satırında sahip gibi Baz'daki değerle durur; ayırmada kopyalanır).
- **Geçişte mevcut kayıtlar:**
  - Tek lokasyon: bütün kayıtlar ona bağlanır.
  - **Birden çok lokasyon:** kayıt bugün bütün kaynaklara uygulanıyor; davranış değişmesin diye **her lokasyona kopyalanır**. Var olan satır koda göre ilk lokasyona bağlanır; öteki lokasyonlar için Baz ve senaryonun kendi satırları kopyalanır, fark satırları (`BaseRowId`) yeni Baz kopyasına bağlanarak kopyalanır. Alan geçmişi ilk lokasyonun satırında kalır. Fazla kopyayı kullanıcı siler.
  - Hiç lokasyon yok ama kayıt varsa (kurulum sonrası, aktarım öncesi): kayıt uygulanacak lokasyon olmadığı için silinir; geçiş çıktısına yazılır.
- Geri alış kolonu düşürür; çok lokasyonda kopyalar birleştirilmez (aynı tarihli kayıtlar zaten birleşerek uygulanır).
- Önbellek (`cache.ResourceCapacityDay`) geçişte boşaltılır; ilk kullanımda yeniden kurulur.

## Sunucu

- **Giriş altyapısı (`app/capacity/entries.py`):** Fabrika takvimi sahipli tür olur: `Owner(("LocationId",), …)`; denetim: lokasyon seçilmeli ve `core.Location`'da olmalı; kayıttan sonra kilitli (`LocationCode`). Kaydın okunur adı bugünkü gibi ad + tarih; birden çok lokasyonda başına lokasyon kodu. `_refresh` sahibe değil tabloya bakar.
- **Tetikleyici (`triggers.factory_calendar_changed`):** `location_id` alır; yalnız o lokasyonun güncel kaynakları yenilenir.
- **Hesap (`app/capacity/compute.py`):** `#cap_fc`'ye `LocationId`; üyelik tablosuna (`#cap_m`) kaynağın lokasyonu eklenir; günün fabrika kaybı gün × lokasyon bazında hesaplanır (bugünkü `#cap_d.factory` yerine). Kapasite özeti aynı önbellekten okuduğu için kendiliğinden doğru olur. Performans: sorgu şekli aynı, gün × lokasyon küçük bir ara tablo (ölçüm ayrı iş, istenirse).
- **Liste (`app/api/lists/capacity.py`):** `capacity-factory-calendar`'a `LocationCode` (ilk kolon), `LocationId` (anahtar alan) ve Lokasyon ilişkisi.
- **Seçenekler:** `GET /api/capacity/locations` → `[{id, code, name}]` (`core.Location`; fonksiyon 24 okuma): Fabrika takvimi penceresinin lokasyon listesi. Öteki pencereler lokasyonları kendi kod listelerinden türetir (yalnız kaydı olan lokasyonlar).
- **Sahip doğrulaması (öneri, Claude):** tedarikçi limiti ve malzeme blokajında gönderilen `LocationId` ile kodun lokasyonu zaten birlikte denetleniyor; kapasite girişlerinde `LocationId` gönderilmez (kaynak ve grup kimliği lokasyonu taşır), değişmez.
- **Sentetik (`app/data/synthetic/load.py`):** `_lock` mesajına: "Aktarımları geri alıp temiz sentetik hâle dönmek için: python -m app.data.synthetic reset". Sentetik Fabrika takvimi satırları yüklemede lokasyona bağlanır (`place` zaten `LocationId` kolonuna bakıyor).
- **Veri kalitesi:** değişiklik yok.

## Ön yüz

- **Ortak (`capacityModel.ts`):** `Owner.locationId` bütün sahiplerde dolu gelir (satırdan, karttan, zaman çubuğundan); lokasyon seçimi için küçük ortak parça (seçenekler, tek lokasyonda dolu gelme, değişince kodu temizleme) üç pencerede kullanılır.
- **`CapacityEntryDialog.tsx`:** ilk alan Lokasyon (aramalı seçim; Düzenle'de kilitli metin). Seviye + kod listesi seçili lokasyona süzülür; lokasyon seçilmeden kod listesi pasif. Fabrika takviminde yalnız Lokasyon (seviye ve kod yok); lokasyonlar `/api/capacity/locations`'tan.
- **`SupplierLimits.tsx`:** Lokasyon → Tür → Tedarikçi → Malzeme sırası değil; karar gereği **Lokasyon ilk alan**, sonra Tür, Tedarikçi (lokasyona süzülü), Malzeme. Düzenle'de Lokasyon, Tür, Tedarikçi, Malzeme kilitli.
- **`MaterialHolds.tsx`:** Lokasyon → Malzeme (lokasyona süzülü) → Tür …; Düzenle'de Lokasyon ve Malzeme kilitli.
- **Listelerde yazım (öneri a):** seçenek "kod · ad"; `manyLocations` yazımı üç pencereden kalkar.
- **Zaman çubuğu ve kart başlıkları:** birden çok lokasyonda "lokasyon · kod": `CapacityValidity.tsx`'teki mevcut kural `ValidityCustom` kullanan iki sekmeye (tedarikçi limiti, malzeme blokajı) ve kart başlıklarına (`CapacityManagement.tsx`, `SupplierLimits.tsx`, `MaterialHolds.tsx`, `ModelConstraints.tsx`) taşınır; yükleme anındaki satırların lokasyon sayısına bakılır.
- **Fabrika takvimi tablosu:** Lokasyon kolonu; satır menüsünden Yeni kayıt lokasyon dolu açılır.

## Docs

`docs/00` (K-194; K-185, K-189, K-191, K-193'e "pencerede lokasyon: K-194" notu) · `docs/02` (`FactoryCalendar.LocationId`, açıklama) · `docs/06` (Fabrika takvimi: lokasyon bazlı) · `docs/08` (liste alanı, `/api/capacity/locations`, doğrulama) · `docs/09` (kapasite hesabında fabrika takvimi lokasyona göre) · `docs/11` (sentetik takvim kayıtları lokasyonlu; `load` / `reset` ayrımı) · `docs/12` (Pencere ve form standardı: lokasyon kuralı; Kapasite yönetimi ve Model kısıtları satırları) · `GELISTIRME_ADIMLARI.md` (ara iş satırı; Bekleyen kontroller: öneri c listesi) · `CLAUDE.md`'ye dokunulmaz.

## Uygulama sırası

docs → `db/generate.py` ve geçiş 0073 → `resolve`, `entries`, `triggers`, `compute` → liste ve `/api/capacity/locations` → sentetik mesaj → ön yüz (ortak parça, üç pencere, zaman çubuğu ve kart başlıkları) → testler → zincir → görsel kontrol → "demo hazır" raporu ve dur.

## Testler (Smartchain_test)

- **Sunucu:** Fabrika takvimi kaydı lokasyon ister (boş ve bilinmeyen lokasyon reddedilir); lokasyon kayıttan sonra değişmez; liste alanı ve ilişki; Baz + fark (fark, geçersiz yapma, ayırma) lokasyonu korur. **İki lokasyonlu hesap:** test içinde ikinci lokasyon, kaynak grubu, kaynak ve çalışma düzeni kurulur (yeni satırlar; sonunda silinir): bir lokasyonun takvim kaydı yalnız kendi kaynaklarının kapasitesini düşürür, Kapasite özeti de öyle; tetikleyici yalnız o lokasyonun kaynaklarını yeniler. Geçiş: tek lokasyonda bağlama; çok lokasyonda kopyalama ve fark satırlarının eşlenmesi (geçişin SQL'i test veritabanında ayrı bir denemeyle). `/api/capacity/locations`; sentetik kilit mesajı. Var olan kapasite, tedarikçi limiti ve malzeme blokajı testleri değişmeden geçer.
- **Ön yüz (vitest):** yedi pencerede Lokasyon ilk alan; tek lokasyonda dolu; iki lokasyonda boş, seçilince kod listesi süzülür, değişince kod temizlenir; Düzenle'de kilitli; karttan ve zaman çubuğundan dolu gelir; listede "kod · ad"; zaman çubuğu ve kart başlığında çok lokasyonda "lokasyon · kod".

## Görsel kontrol (yalnız Smartchain_test; Playwright)

- **Tek lokasyon:** yedi pencere (Çalışma düzeni, Bakım ve duruşlar, Verimlilik, Ek mesai limitleri, Fabrika takvimi, Tedarikçi limiti, Malzeme blokajı): Yeni kayıt ve Düzenle; Fabrika takvimi tablosu.
- **İki lokasyon (öneri b):** kurulumda ikinci lokasyon, aynı kodlu kaynak grubu ve kaynak, bir malzeme ve malzeme tedarikçisi (yeni satırlar; sonunda silinir, sentetik set değişmez). Yedi pencere, Fabrika takvimi tablosu ve Kapasite özeti (bir lokasyonun tatili ötekini etkilemiyor), zaman çubukları ve kart başlıkları.
- Açılanlar raporda listelenir.

## Demo

Güncel kod işareti: Fabrika takvimi tablosunda "Lokasyon" kolonu ve pencerelerde ilk alan "Lokasyon".

Rapor ayrıca şunları yazar: geliştirme veritabanında çalıştırılacak komutlar (0073; sentetik için hangi durumda `load`, hangi durumda `reset`); çok lokasyonlu durumun nasıl kurulacağı (öneri d: kirli sentetik Excel'in aktarımı V-LOC-1 ve R-LOC-1'i getirir).

## Açık nokta

Yok. Kendi verdiğim kararlar (itirazınız olursa değiştiririm): çok lokasyonlu geçişte kayıtların her lokasyona kopyalanması; Fabrika takvimi penceresinde `core.Location`'daki bütün lokasyonların listelenmesi; öneri a–d'nin uygulanması.
