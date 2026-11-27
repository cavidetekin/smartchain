# Ara iş · Plan çıktı tabloları (8.0 Plan fikstürü öncesi)

> **Durum:** plan onaylandı (26.11.2026); açık noktaların kararları en altta, metin kararlara göre düzeltildi. İki parça: 1 ad seti (kapandı, 27.11.2026; sürüm 0.61.0, geçiş 0082), 2 plan tabloları (27.11.2026'da başlandı). Her parça kendi zinciri ve commit'iyle; hiçbir parça demo onayı olmadan kapanmaz.
> **Numaralar:** karar K-202; 1. parça geçiş 0082 ve sürüm 0.61.0; 2. parça geçiş 0083 ve sürüm 0.62.0.
> **İşaretler:** bölüm 1–8 ve açık noktaların kararları Cavide'nindir. Onay isteğindeki iki öneri (a: liste tanımlarının Aşama 8'e taşınması; b: fason ayracının adı `IsSubcontract`) 27.11.2026'da onaylandı; metne işlendi.
> **Kapsam dışı (Aşama 10'a not):** hareket tarihi kuralı ve modelin dönem varsayımı; modelin mevcut üretim siparişlerine dokunma kuralları; satın alma siparişleri için öne çek, ertele, iptal uyarıları; full pegging yöntemi ve seviye bazında sıralama.

## Bağlam

Aşama 8'in ekranları plan fikstürüyle çalışacak; fikstür de plan çıktı tablolarının biçiminde yazılacak. Bugünkü tablolar bu iş için dar: `PlannedOrder`'da lokasyon, üretim versiyonu, dönem ve elle değişiklik izi yok; talep karşılama talep başına tek satır; pegging'de malzeme, tarih ve kök talep bilgisi yok; malzeme hareketlerini tek yerden okuyacak tablo yok. Bu iş tabloları yeni yapıya çevirir (karar → sonuç → dönem tabloları) ve ad setini teke indirir. Sonunda 8.0'daki "pegging sonuç tablosunun alanları ve `PlannedOrder` yapısı önce netleşmeli" notu kapanır.

## Bugünkü durum (araştırma)

- **`planning` şemasında 12 tablo:** Scenario, Workspace, WorkspaceOverride, PlanRun, PlanVersion, PlannedOrder, SupplyRecommendation, DemandFulfillment, CapacityLoad, Pegging, PlanWarning, PlanMetric. Çıktı tablolarının tek anahtarı `PlanRunId`; veri versiyonu yalnız `PlanRun.DataVersionId`'de. `core` kayıtlarına çıplak `Id` ile bağlanırlar (fiziksel FK yok, K-63).
- **Kullanan çok az:** hiçbir liste ya da ekran bu tabloları okumuyor. Yazan tek yer sahte motor (`app/engine/fake.py`, `fixtures/plan_v0.json`: 3 planlı sipariş, 1 öneri, 2 karşılama, 2 doluluk, 3 pegging) ve yazıcı (`app/engine/writer.py`). Tablo adları beş yerde elle yazılı: `writer.OUTPUTS`, `app/data/cleanup.OUTPUT_TABLES`, `installer/smoke.py`, `scripts/engine_demo.py`, `tests/test_engine_writer.py`.
- **Motor arayüzü:** `PlanResult` satırları sözlük listesi olarak taşır (`planned_orders`, `supply_recommendations`, `demand_fulfillment`, `capacity_loads`, `pegging`, `warnings`, `metrics`); `ref` / `supply_ref` ile planlı sipariş ve pegging bağlanır (`app/engine/interface.py`, docs/09).
- **Ek mesai bugün yalnız `CapacityLoad.Overtime` kolonunda** (motorun kararı). Ayrı tablosu yok. Sınırı girdidir (`param.OvertimeLimit`). Kapasitenin kendisi kapasite hesabından gelir (`app/capacity/compute.py`, `cache.ResourceCapacityDay`); `CapacityLoad`'daki brüt, duruş ve net kapasiteyi hesaplayan kod yok, yalnız fikstür dolduruyor.
- **Dönem tabloları:** yalnız "Kaynak grubu × dönem" yazılı (`period-resource-group`); malzeme, müşteri, proje, tedarikçi × dönem Aşama 8'de. Hiçbiri `planning.*` okumuyor.
- **Veri sözlüğü** yalnız `core` ve `param` tablolarını alır (`db/dictionary.py`); plan tabloları bugün sözlükte yok.
- **İlişkili alanlar** verilen veri versiyonuna göre çözmeyi zaten biliyor (`relations.py` `_valid(t, version)`); ama liste servisi yalnız güncel versiyonu geçiriyor. Plan tabloları için `PlanRun.DataVersionId`'yi geçiren yol yok; yalnız `core.*` tabloları ve elle kaydedilen listeler ilişki alabiliyor.
- **Talep kimliği:** açık talep, talep türü ve öncelik grubu için hazır işlevler var (`app/params/objectives.demand_type`, `app/priorities.orders_sql` / `forecasts_sql`, `app/allocation/rules.py` açık talep koşulu). Talep türleri tek kaynakta (`catalog.DEMAND_TYPES`).
- **Ad seti:** "iş emri" 79 dosyada 616 satırda geçiyor (aşağıda döküm). "Satın alma planı" hiç geçmiyor. Pegging ölçütleri "Üretim siparişi", "Üretim planı" adlarını zaten kullanıyor.

## Tablolar (kararlar, kolon adı önerileriyle)

Bütün tablolar `planning` şemasında, `PlanRunId` taşır, versiyonsuzdur. Kolon adları önerimdir; görünen adlar veri sözlüğünden değişebilir.

### PlannedSupply · "Tedarik planı" (`PlannedOrder`'ın yerine; motor yazar)

| Alan | Görünen ad | Not |
|---|---|---|
| `SupplyNo` | No | ÜP-000071, SP-000214; `Source` = Sipariş satırında üretim siparişinin numarası |
| `SupplyType` | Tür | Üretim · Satın alma |
| `Source` | Kaynak | Plan · Sipariş |
| `WorkOrderId` | (iç bağ) | Bağlı üretim siparişi; "Üretim siparişi · …" ilişkili alanları buradan |
| `MaterialId` · `LocationId` · `Uom` | Malzeme · Lokasyon · Birim | |
| `PeriodStart` · `PeriodEnd` | Başlangıç · Bitiş | Dönemin ilk ve son günü; "Dönem" etiketi (H47 2026) dönem alanı standardıyla hesaplanır |
| `OrderDate` | Sipariş tarihi | Başlangıç − tedarik süresi (satın alma ve fason) |
| `ProductionVersionId` · `BOMCode` · `RouteCode` | Üretim versiyonu · Ürün ağacı kodu · Rota kodu | Üçü de saklanır |
| `SupplierId` | Tedarikçi | |
| `IsCustomAllocated` · `AllocationLevel` · `AllocationKey` | Özel alokasyon · Alokasyon seviyesi · Alokasyon anahtarı | K-198 |
| `Quantity` · `RoundedQuantity` | Miktar · Yuvarlanmış miktar | |
| `ProposedQuantity` · `ProposedPeriodStart` | Öneri miktarı · Öneri dönemi | İlk hesap; elle değişiklikten önceki hâl |
| `IsManual` · `IsFixed` · `IsIncluded` | Elle değiştirildi · Sabitlendi · Plana dahil | |
| `IsSubcontract` | Fason | Evet · Hayır; `WorkOrder`'daki alanla aynı ad ve etiket. Kaynak = Plan satırında rotadan (`Routing.IsSubcontracted`, `ResourceGroup.IsSubcontractor`); Kaynak = Sipariş satırında üretim siparişinin kendi alanından (çelişkide ERP'nin dediği geçerli) |

Mevcut üretim siparişlerinin plan kaydı da buradadır (`Source` = Sipariş; döneme bölünürse dönem başına satır). Satın alma siparişleri burada yoktur. `SupplyRecommendation` kalkar.

### PlannedDemand · "Talep karşılama" (yeni; sistem kopyalar, motor yazmaz)

Girdi: `DemandType` (Tür) · `OrderNo` · `LineNo` · `LineItemNo` · `CustomerId` · `ProjectId` · `MaterialId` · `LocationId` · `Uom` · `DemandQuantity` (Talep miktarı) · `DueDate` (Vade tarihi) · `DuePeriodStart` (Vade dönemi) · `PriorityGroup` · `IsIncluded` · iç bağ: `SalesOrderLineId`, `ForecastId` (iki kolon). Her tahmin kaydı bir talep satırıdır (sipariş alanları boş). "Plana dahil: Hayır" yalnız parametreyle kapalı türlerdedir; ufuk dışındaki talep "Evet" kalır.
Sonuç (hesaptan sonra karşılama satırlarından): `FulfilledQuantity` · `OnTimeQuantity` · `LateQuantity` · `UnmetQuantity` · `FulfillmentPct` · `LastFulfillmentPeriodStart`.
Plan hesabı başlarken, hesabın veri versiyonundaki açık bütün talepler kopyalanır (yeni modül `app/planning/demand.py`; açık talep, tür ve öncelik için yukarıdaki hazır işlevler kullanılır).

### DemandFulfillment · "Talep karşılama kırılımı" (motorun talep tarafında yazdığı tek tablo)

`PlannedDemandId` (iç bağ) · `DemandType` · `OrderNo` · `LineNo` · `LineItemNo` · `CustomerId` · `ProjectId` · `MaterialId` · `LocationId` · `PeriodStart` · `PeriodEnd` · `Quantity` (Karşılama adedi) · `Uom` · `IsTardy` (Gecikmeli). Bugünkü "talep başına tek satır" yapısı (`DueDate`, `PlannedDate`, `ShortQty`, `DelayDays`) kalkar; "Güvenlik stoğu" talep türü de kalkar (not dosyası: güvenlik stoğu ihtiyaç satırı değildir).

### MaterialTransaction · "Malzeme hareketleri" (yeni; türetilir; tablo adı tekil)

`MaterialId` · `LocationId` · `Uom` · `Direction` (+ · −) · `MainMovement` (Ana hareket) · `MovementType` (Hareket türü) · `DocumentNo` (No) · `Quantity` · `PeriodStart` · `PeriodEnd` · `MovementDate` · `IsCustomAllocated` · `AllocationLevel` · `AllocationKey` · `ExpiryDate` · `PriorityGroup` · `OrderNo` · `LineNo` · `LineItemNo` · `CustomerId` · `ProjectId` · iç bağlar: `StockId` · `PurchaseOrderLineId` · `PlannedSupplyId` · `DemandFulfillmentId`.

Ana hareket → Hareket türü: Stok (Stok · Kalitedeki stok) · Satın alma (Satın alma siparişi · Satın alma planı) · Üretim (Üretim siparişi · Üretim planı) · Talep (Kesin sipariş · Teklif · Beklemedeki sipariş · Tahmin) · Üretim ihtiyacı (Üretim siparişi ihtiyacı · Üretim planı ihtiyacı) · Transfer (Alokasyon transferi; iki satır: genelden −, özele +; `PlannedAllocationTransfer`'dan türetilir).

**No:** Üretim planı ve Satın alma planı: tedarik planı no · Üretim siparişi ve Satın alma siparişi: sipariş no · Kesin sipariş, Teklif, Beklemedeki sipariş: satış sipariş no · Üretim ihtiyacı: ihtiyacı doğuran üretimin no'su · Stok, Tahmin, Alokasyon transferi: boş.

**Hareket tarihi:** şimdilik her satırda dönem başı; kuralı sonra ele alınacak (pegging, Aşama 10).

**Tek kaynak:** hareket türleri yeni bir modülde tanımlanır (`app/planning/movements.py`); Pegging sekmesinin ölçüt adları (`app/params/pegging.py`) tür adlarını oradan alır, talep türleri yine `catalog.DEMAND_TYPES`'tan. Test: ölçüt listesindeki türler ile hareket türleri birebir.

### CapacityLoad · "Kapasite yükleri" (yeniden tanımlanır; yalnız yükler, sistem hesaplar)

Satır = tedarik planı kaydı × kaynak grubu × dönem: `ResourceGroupId` · `LocationId` · `PlannedSupplyId` (iç bağ) · `MaterialId` · `ProductionQuantity` (Üretim adedi) · `UnitUsage` (Birim kullanım) · `CapacityUsage` (Kapasite kullanımı) · `CapacityUnit` (Birim) · `PeriodStart` · `PeriodEnd`. Rotada aynı gruba düşen operasyonlar toplanır.

Bugünkü alanlar nereye gidiyor:

| Bugün | Yeni yapıda |
|---|---|
| `GrossCapacity`, `DowntimeLoss`, `NetCapacity` | Saklanmaz; kapasite hesabından okunur (Kaynak grubu × dönem: Toplam kapasite, Duruş, Kullanılabilir kapasite) |
| `Load` | Saklanmaz; `CapacityUsage`'ın grup ve dönem toplamı |
| `Overtime` | Yeni karar tablosu `PlannedOvertime` ("Ek mesai planı"); `CapacityLoad`'a girmez |

### Pegging · "Pegging" (yeniden tanımlanır)

Satır = bir + hareketini bir − hareketine bir miktarla bağlar: `MaterialId` · `LocationId` · `Quantity` · `Uom` · `SupplyTransactionId` · `DemandTransactionId` (iki hareket bağı) · `ConsumingMaterialId` (Kullanan malzeme) · `PlannedDemandId` (Kök talep; boş olabilir) · `Level` (Seviye; 0 = nihai ürün) · `ParentPeggingId` (Üst bağ) · `IsFromGeneral` (Genelden). Her satır tek kök talep taşır; `IsFixed` kalkar. **İki tarafın alanları satıra da yazılır** (ölçüm yapılmaz): arz ve ihtiyaç için ayrı ayrı Ana hareket · Hareket türü · No · Başlangıç · Bitiş · Hareket tarihi · Alokasyon seviyesi · Alokasyon anahtarı; kök talebin alanları da (Tür · Sipariş no, satır, alt satır · Müşteri · Proje). İki hareket bağı da durur.

### PlannedOvertime · "Ek mesai planı" (yeni karar tablosu; motor yazar)

`ResourceGroupId` · `LocationId` · `PeriodStart` · `PeriodEnd` · `Overtime` (Ek mesai) · `CapacityUnit` (Birim). Kaynak grubu × dönem raporunda kapasite ve yükün yanında okunur.

### PlannedAllocationTransfer · "Alokasyon transfer planı" (yeni karar tablosu; motor yazar)

`MaterialId` · `LocationId` · `PeriodStart` · `PeriodEnd` · `AllocationLevel` · `AllocationKey` · `Quantity` · `Uom`. Malzeme hareketlerindeki iki satır (genelden −, özele +) bu tablodan türetilir.

### Değişmeyenler

PlanRun, Scenario, Workspace, WorkspaceOverride, PlanVersion, PlanWarning, PlanMetric. Dönem tabloları (K-184) değişmez; kaynakları ileride bu tablolar olur (Aşama 8).

## Kim yazar, ne zaman

| Tablo | Yazan | Zaman |
|---|---|---|
| PlannedDemand (girdi alanları) | Sistem | Plan hesabı başlarken, motor çağrılmadan önce |
| PlannedSupply, DemandFulfillment, PlannedOvertime, PlannedAllocationTransfer | Motor (bugün sahte motor) | Hesap |
| PlannedDemand (sonuç alanları) | Sistem | Hesaptan sonra, karşılama satırlarından |
| CapacityLoad | Sistem (türetme 8.0'da, fikstürle birlikte) | Hesaptan sonra ve tedarik planı elle değişince; rotadan |
| MaterialTransaction | Sistem (türetme 8.0'da, fikstürle birlikte) | Hesaptan sonra ve tedarik planı elle değişince |
| Pegging | Pegging hesabı (10.6); o güne kadar fikstür | Hesaptan sonra |

Bu işte: şema, motor arayüzü, `PlannedDemand` kopyası ve özet alanları. `MaterialTransaction` ve `CapacityLoad` türetmesi 8.0'da.

## Etkilenen yerler

### Docs (K-54: önce docs; `db/models.py` ve `docs/07` üretilir)

| Dosya | Değişecek yerler |
|---|---|
| `docs/00-kararlar.md` | K-202; K-198 ve K-199'daki `PlannedOrder` atıflarına not; A-10 (fason tercihi) ile ilişki |
| `docs/02-veri-modeli.md` | Plan tablo listesi; `PlannedOrder`, `SupplyRecommendation`, `DemandFulfillment`, `CapacityLoad`, `Pegging` bölümleri yeniden; yeni `PlannedSupply`, `PlannedDemand`, `MaterialTransaction`; `WorkOrder` ve bağlı tabloların etiketleri (ad seti) |
| `docs/03-entegrasyon.md` | Varlık kataloğunda görünen adlar (İş emri → Üretim siparişi); alan etiketleri |
| `docs/05-ekranlar.md`, `docs/06-fonksiyonlar.md` | Ad seti (06'da 104 satır "iş emri", 68 satır "planlı sipariş"); fonksiyon 36, 66–69 (mevcut arz önerileri: `SupplyRecommendation` kalkıyor), 58 (manuel pegging), 70, 71 |
| `docs/08-api.md` | Plan tablolarının liste uçları; ilişkili alanların plan hesabının veri versiyonundan çözülmesi |
| `docs/09-motor-arayuzu.md` | `PlanResult` satırları, yazım kuralları, sahte motor fikstürü |
| `docs/11-sentetik-veri.md`, `docs/12-on-yuz.md` | Ad seti; plan tablolarında dönem alanları |
| `docs/notlar-pegging-ve-ozel-alokasyon.md` | §2 ("`PlannedOrder` çok dar"), §6 (pegging alanları), §7; kapanışta, değişecek cümleleri önce listeleyerek |
| `GELISTIRME_ADIMLARI.md` | Yeni ara iş; 8.0 notu kapanır; 8.10, 9.5, 10.x notları |

### Geçişler

- **0082 · ad seti:** `param.PeggingCriterion.Criterion`'da "Satın alma önerisi" → "Satın alma planı" (değer metin olarak saklı; geçiş olmazsa kullanıcının kaydettiği sıra sessizce bozulur). 0059'daki kalıp: sabit değerlerle `UPDATE`, geri alışı var (K-197). Etiketler (`FieldDefinition.StandardLabel`) ve özelleştirilmemiş validasyon kuralları kendiliğinden yenilenir.
- **0083 · plan tabloları:** `PlannedOrder`, `SupplyRecommendation` ve eski `DemandFulfillment`, `CapacityLoad`, `Pegging` düşer; yeni altı tablo açılır; plan tabloları veri sözlüğüne girer. **Veri kaybı:** yalnız sahte motorun yazdığı plan çıktıları (yeniden üretilir).
- Sizin çalıştıracağınız komutlar (K-165): `alembic -c db/alembic.ini current` → `alembic -c db/alembic.ini upgrade head`. Sentetik `reset` gerekip gerekmediğini uygulamada netleştirip raporda yazarım.

### Kod, sahte motor, fikstür, testler

- **Motor arayüzü ve yazıcı:** `app/engine/interface.py` (`PlanResult`), `writer.py` (`OUTPUTS`, bağ çözme), `fake.py`, `fixtures/plan_v0.json`.
- **Temizlik ve kurulum:** `app/data/cleanup.py`, `installer/smoke.py`, `scripts/engine_demo.py`.
- **Yeni:** `app/planning/` (talep kopyası, özet alanları, hareket türleri); `db/dictionary.py` (plan tabloları veri sözlüğüne girer). Liste tanımları ve ilişkili alanların `PlanRun.DataVersionId`'den çözülmesi Aşama 8'de (öneri a).
- **Testler:** `test_engine_writer.py`, `test_engine_service.py`, `test_template_contract.py`, `test_dictionary.py`, `conftest.py` (plan ortamı); ad seti için `test_labels.py`, `test_related_fields.py`, `test_validation_references.py`, `test_pegging_parameters.py`, ön yüzde `Pegging.test.tsx`, `Parameters.test.tsx`.

## Ad seti dökümü (bölüm 2)

ERP'den gelen: **Üretim siparişi · Satın alma siparişi**. Smartchain'in ürettiği: **Üretim planı · Satın alma planı**.

| Nerede | Bugün | Olacak |
|---|---|---|
| Tablo adları (docs/03 varlık kataloğu → liste başlıkları, Excel şablon sayfası, ön yüz `tr.ts`) | İş emri · İş emri bileşeni · İş emri operasyonu | Üretim siparişi · Üretim siparişi bileşeni · Üretim siparişi operasyonu |
| Adres ve dosya adları | `is-emri`, `is-emri-bileseni`, `is-emri-operasyonu` | `uretim-siparisi`, `uretim-siparisi-bileseni`, `uretim-siparisi-operasyonu` (sayfa adresi, Excel şablon ve dışa aktarım dosya adı) |
| Alan etiketleri (docs/02, 03) | İş emri no, tipi, durumu, miktarı · Orijinal iş emri · Bağlı iş emri | Üretim siparişi no, tipi, durumu, miktarı · Orijinal üretim siparişi · Bağlı üretim siparişi |
| İlişkili alan başlıkları | "İş emri · …" | "Üretim siparişi · …" (etiketten türer) |
| Validasyon kuralları (`app/validation/catalog.py`, 12 satır) ve referans mesajları (`app/integration/references.py`) | "… iş emri …" | "… üretim siparişi …" |
| Parametre `OpenWorkOrders` | Açık iş emirleri | Açık üretim siparişleri |
| Pegging ölçütü | Satın alma önerisi | Satın alma planı (geçiş 0082) |
| Parametre `RoundPurchaseToLot` | Satın alma önerisini sipariş lotuna yuvarla | Satın alma planını sipariş lotuna yuvarla |
| Uyarı `PURCHASE_LATE` | Geciken satın alma önerisi | Geciken satın alma planı |
| docs'ta "planlı sipariş" (87 satır) | Planlı sipariş | Tedarik planı; türüne göre Üretim planı ya da Satın alma planı (**2. parçada**, tabloyla birlikte) |
| Plan tablolarındaki değer listeleri | "İş emri", "Planlı sipariş", "Fason" | Yeni hareket türleri; Tür: Üretim · Satın alma (**2. parçada**) |
| Sentetik veri | Yorumlar, iki görünen metin | Güncellenir |
| Testler | 14 Python ve 3 ön yüz dosyasında metin beklentisi | Güncellenir |

**Dokunulmayacaklar:** kod ve tablo adları (`WorkOrder` İngilizce kalır); eski geçişlerin içindeki metinler (K-197); denetim izindeki eski kayıtlar; kullanıcının elle değiştirdiği etiketler ve özelleştirdiği kurallar (tasarım gereği eski metinle kalır); "Öneriler" ekranının adı ve "öneri" sözcüğünün öteki anlamları ("Yalnız öteleme önerisi", "(öneri)" işaretli fonksiyonlar).

**Fason:** plan tablolarında ayrı tür olmaz (Tür: Üretim · Satın alma). Bugün fasonu üretim versiyonu değil, rotadaki operasyon ve kaynak grubu işaretler (`Routing.IsSubcontracted`, `ResourceGroup.IsSubcontractor`); versiyonda bayrak yoktur. ERP sözleşmesindeki fason alanlarına dokunulmaz (Aşama 8'de konuşulacak).

## GELISTIRME_ADIMLARI.md'deki yeri (öneri a: uygun)

Aşama 8'in başında, 8.0'dan önce: "**Ara iş · Plan çıktı tabloları** (K-202)". İki parça öneriyorum; her biri kendi zinciri ve commit'iyle:

1. **Ad seti** (küçük; yalnız metinler ve geçiş 0082).
2. **Plan tabloları** (docs, şema, motor arayüzü, yazıcı, sistemin yazdığı kısımlar, veri sözlüğü kaydı; liste tanımları Aşama 8'de).

8.0 Plan fikstürü bu tablolara göre yazılır; 8.0'daki not bu işin kapanışında kalkar.

## Demo (motor yok)

Sahte motor küçük bir örnek plan yazar (yeni biçimde `plan_v0.json`); sistem talep kopyasını ve sonuç alanlarını üretir. Gösterilecekler:

- Sentetik veride bir plan hesabı başlatılır; **Talep karşılama** tablosunda bütün açık talepler, türleri, öncelik grupları ve "Plana dahil" görülür.
- **Tedarik planı**nda ÜP ve SP numaralı kayıtlar ile bir üretim siparişinin plan kaydı; "Üretim siparişi · …", "Malzeme · …", "Üretim versiyonu · …" ilişkili alanları açılır ve plan hesabının veri versiyonundan gelir (veri yeniden aktarılınca eski hesabın satırı değişmez).
- Veri sözlüğünde plan tablolarının alan adı değiştirilir; tabloda yeni ad görülür.
- Ad seti: İşlem verisi'nde "Üretim siparişi" tabloları; Pegging sekmesinde "Satın alma planı"; kaydedilmiş sıranın korunduğu.

İnceleme sayfası yoktur: demo ekran görüntüsü ve sorgu çıktısıyla hafif geçer; asıl deneme Aşama 8 ekranlarında.

## Açık noktaların kararları (Cavide, 26.11.2026)

1. Ayrı ara iş, 8.0'dan önce; iki parça (1: ad seti, 2: plan tabloları), her biri kendi zinciri ve commit'iyle.
2. Bu işte şema, motor arayüzü, `PlannedDemand` kopyası ve özet alanları. `MaterialTransaction` ve `CapacityLoad` türetmesi 8.0'da fikstürle birlikte.
3. İnceleme sayfası yok; demo ekran görüntüsü ve sorgu çıktısıyla.
4. Tablo adı `MaterialTransaction` (tekil).
5. Dönem `PeriodStart` ve `PeriodEnd` ile saklanır; etiket hesaplanır.
6. Talebin iç bağı iki kolon (`SalesOrderLineId`, `ForecastId`).
7. `PlannedDemand`'de hem vade tarihi hem vade dönemi.
8. Her tahmin kaydı bir talep satırı; sipariş alanları boş.
9. Ek mesai ayrı karar tablosunda: `planning.PlannedOvertime` ("Ek mesai planı"): PlanRun · Kaynak grubu · Lokasyon · Başlangıç · Bitiş · Ek mesai · Birim. Motor yazar; `CapacityLoad`'a girmez.
10. Aktarım kararı ayrı karar tablosunda: `planning.PlannedAllocationTransfer` ("Alokasyon transfer planı"): PlanRun · Malzeme · Lokasyon · Başlangıç · Bitiş · Alokasyon seviyesi · Alokasyon anahtarı · Miktar · Birim. Motor yazar; hareket tablosundaki iki satır bundan türer.
11. İki tarafın alanları Pegging satırına yazılır (ölçüm yapılmaz); kök talebin alanları da. İki hareket bağı durur.
12. `MaterialTransaction`'a "No" (`DocumentNo`); türlere göre içeriği yukarıda.
13. Hareket tarihi şimdilik her satırda dönem başı; kural sonra (pegging, Aşama 10).
14. ERP sözleşmesindeki fason alanlarına dokunulmaz; Aşama 8'de konuşulacak.
15. `PlannedSupply`'a "Fason" ayracı (Evet · Hayır); kaydın rotasından.
16. ÜP / SP plan hesabı içinde sıra; numarayı taşıma kuralı 8.8'de.
17. Öneri dönemi tek alan.
18. "Plana dahil: Hayır" yalnız parametreyle kapalı türlerde; ufuk dışındaki talep "Evet"; "neden dahil değil" alanı yok.
19. `PlannedDemand` özet alanları tabloda saklanır.
20. Talep türü dört değer, `catalog.DEMAND_TYPES`'tan; `PlannedDemand` ve `DemandFulfillment`'ta.
21. Ekran adları: PlannedSupply = Tedarik planı · PlannedDemand = Talep karşılama · DemandFulfillment = Talep karşılama kırılımı · MaterialTransaction = Malzeme hareketleri · CapacityLoad = Kapasite yükleri · Pegging = Pegging · PlannedOvertime = Ek mesai planı · PlannedAllocationTransfer = Alokasyon transfer planı. Hareket adı: Ana hareket "Transfer", Hareket türü "Alokasyon transferi". Pegging'deki "Genelden (Evet · Hayır)" aynı kalır.
22. Adres ve dosya adlarında "is-emri" → "uretim-siparisi" (sayfa adresi, Excel şablon dosya adı, ilgili testler).
23. Fonksiyon 36 ve 66–69 ile "Öneriler" ekranına docs'ta "yeniden ele alınacak (8.10)" notu; metinler ve ekran adı şimdilik kalır.
24. docs/06'daki eski metinlerin hepsi yeni ada çevrilir; görsellere dokunulmaz.
25. Uygun: "Açık üretim siparişleri", "Satın alma planını sipariş lotuna yuvarla", "Geciken satın alma planı".
26. Sentetik veriye plan verisi konmaz; sahte motor fikstürü yeni biçime çevrilir; asıl fikstür 8.0'da.
27. Geçiş eski beş tabloyu ve sahte motor çıktılarını siler; dönüştürme yazılmaz.

## Yapı (özet)

- **Karar tabloları (motor yazar):** PlannedSupply · DemandFulfillment · PlannedOvertime · PlannedAllocationTransfer
- **Girdi kopyası (sistem yazar):** PlannedDemand (özet alanları hesaptan sonra türetilir)
- **Sonuç tabloları (türetilir, elle değişmez):** MaterialTransaction · CapacityLoad · Pegging
- **Dönem tabloları (K-184):** bunlardan toplanır.

## İki önerinin kararı (Cavide, 27.11.2026)

- **a. Onaylandı:** bu işte yalnız tablolar ve veri sözlüğü kaydı. Liste tanımları ve ilişkili alanların plan hesabının veri versiyonundan çözülmesi, tabloyu ilk kullanan Aşama 8 ekranıyla birlikte yazılır (GELISTIRME 8.3'e not düşüldü).
- **b. Onaylandı:** `PlannedSupply`'daki fason ayracı `IsSubcontract` (`WorkOrder`'daki alanla aynı ad ve etiket). Kaynak = Plan satırında rotadan beslenir (`Routing.IsSubcontracted`, `ResourceGroup.IsSubcontractor`); Kaynak = Sipariş satırında üretim siparişinin kendi alanından gelir (çelişkide ERP'nin dediği geçerli).

## 1. parçanın kapsamı (ad seti)

Yalnız görünen metinler, adres ve dosya adları ve geçiş 0082: "İş emri" → "Üretim siparişi" (tablo adları, alan etiketleri, ilişkili alan başlıkları, validasyon ve referans mesajları, sentetik veri metinleri, docs); "Satın alma önerisi" → "Satın alma planı" (pegging ölçütü; kayıtlı sıralar geçişle çevrilir); parametre ve uyarı adları (karar 25); adres ve dosya adları (karar 22). Kod ve tablo adları (`WorkOrder`) değişmez; eski geçişler, eski kararlar (`docs/00`), `plans/` ve denetim izindeki eski kayıtlar olduğu gibi kalır. "Planlı sipariş" metinleri ve plan tablolarındaki değer listeleri 2. parçadadır.
