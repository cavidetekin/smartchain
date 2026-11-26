# Veritabanı haritası

Üretilmiş dosya: `db/generate.py`. Kaynak `docs/02-veri-modeli.md` ve `docs/03-entegrasyon.md`.

## Kurallar

- **Altı şema:** `stg` entegrasyon (ham), `prc` işlenmiş staging, `core` ana veri ve işlem verisi, `param` parametreler, `planning` plan çıktıları, `adm` veri yönetimi ve sistem (K-62, K-140).
- **Aynı ad, üç katman:** `stg.Material` ERP'den geldiği haliyle (kodlarla, hiç değişmez), `prc.Material` güncel hâli veri kuralları uygulanmış, `core.Material` Smartchain'in tablosu (Id ile). Kurallar `prc`'de çalışır, aktarım `prc`'den `core`'a yapılır (K-58, K-140).
- **Versiyonlu tablolar:** `VersionFrom`, `VersionTo`, `ImportBatchId`, `BusinessKey`, `UpdatedAt` alanlarını taşır. Birincil anahtar `Id + VersionFrom`; `Id` bir kaydın bütün versiyonlarında aynıdır. Güncel kayıtta `VersionTo` boştur; tekillik (UK) yalnız güncel kayıtlarda aranır.
- **İlişkiler:** Versiyonsuz tabloya giden ilişkiler veritabanında yabancı anahtarla (FK) korunur. Versiyonlu tabloya giden ilişkilerde FK yoktur, yalnız indeks vardır; bütünlüğü aktarım adımı (kod→Id) sağlar.
- **Entegrasyon tablolarının standart alanları:** `stg`'de `StagingRowId`, `ImportBatchId`, `ErrorText`, `SourceRowNo`, `IsCurrent` (K-133), `SupersededAt` (K-160); `prc`'de `StagingRowId` (ham satırdan), `ImportBatchId`, `SourceRowNo`, `RowStatus` (Yeni, Hatalı, Aktarıldı). Bu tablolarda zorunluluk veritabanında değil, doğrulama adımında kontrol edilir.
- **Açıklamalar:** Her tablo ve alanın Türkçe açıklaması veritabanına da yazılır; SQL Server Management Studio'da tablo ve kolon özelliklerinde görünür.

## `stg` · Entegrasyon tabloları: ERP'nin dili, ilişkiler kodla (K-58); ham katman, hiç değişmez (K-140) (24 tablo)

| Tablo | Açıklama | Sınıf | Versiyonlu | Alan |
|---|---|---|---|---|
| `stg.Material` | Malzeme ve planlama ana verisi. | Entegrasyon |  | 43 |
| `stg.Location` | Lokasyon (tesis, depo). Faz 1'de her lokasyon kendi içinde planlanır. | Entegrasyon |  | 23 |
| `stg.UomConversion` | Malzeme bazında birim dönüşümü. | Entegrasyon |  | 6 |
| `stg.ProductionVersion` | Üretim versiyonu: bir malzemenin ürün ağacı ve rota başlığı; rotaya RouteCode, ürün ağacına BOMCode ile bağlanır. Versiyon seçimi motorun kararıdır; aynı malzeme aynı dönemde birden fazla versiyonla üretilebilir. | Entegrasyon |  | 17 |
| `stg.BOM` | Ürün ağacı satırı. | Entegrasyon |  | 18 |
| `stg.Routing` | Rota: her satır bir operasyon–kaynak grubu ilişkisi; sıra önce OperationNo, sonra SequenceNo. Aynı operasyonun kaynak grupları ayrı satırda, ResourceRole ile. | Entegrasyon |  | 23 |
| `stg.MaterialReference` | Benzetilen ürün: kendi ağacı ya da rotası olmayan ürün, başka bir ürünün verisiyle planlanır. | Entegrasyon |  | 7 |
| `stg.Resource` | Kaynak: tek bir makine, işçi ya da fason iş yeri. Planlama birimi kaynak değil kaynak grubudur (K-180): tip bayrakları, kritiklik, kapasite birimi ve fasoncu gruptadır; kaynak gruplarına `ResourceGroupMember` ile bağlanır. | Entegrasyon |  | 18 |
| `stg.ResourceGroup` | Kaynak grubu: planlama birimi (K-180). Rota ve iş emri operasyonu grubu gösterir; plan ve yük grup düzeyindedir. Tip, kritiklik, kapasite birimi ve fasoncu gruptadır. Gruptaki kaynak sayısı `ResourceGroupMember`'dan bilinir, ayrıca girilmez. | Entegrasyon |  | 24 |
| `stg.ResourceGroupMember` | Kaynak grup eşleşmesi: kaynağın gruba üyeliği. Bir kaynak birden fazla gruba üye olabilir (birden fazla yetkinliği olan işçi). Geçerlilik tarihi yoktur: yüklü eşleşme bugünden itibaren geçerlidir. Gruptaki kaynak sayısı bu tablodan bilinir (K-180). | Entegrasyon |  | 8 |
| `stg.EmployeeAbsence` | Kişi bazında izin ve rapor. | Entegrasyon |  | 6 |
| `stg.Supplier` | Tedarikçi ve fasoncu. | Entegrasyon |  | 16 |
| `stg.MaterialSupplier` | Malzeme–tedarikçi ilişkisi; satın alma parametreleri. Satın alma her zaman sürekli; yuvarlama son hesapta. | Entegrasyon |  | 19 |
| `stg.Customer` | Müşteri. | Entegrasyon |  | 19 |
| `stg.Project` | Proje. | Entegrasyon |  | 14 |
| `stg.SalesOrderLine` | Müşteri sipariş satırı; teklifler IsQuote ile okunur. Vade: teyit tarihi, yoksa istek tarihi. | Entegrasyon |  | 25 |
| `stg.Forecast` | Talep tahmini (netleme ön hesapta). | Entegrasyon |  | 15 |
| `stg.BorrowPayback` | Projeler arası ödünç ve geri ödeme kaydı: devreye almada açık olan ve ERP'de doğrudan yapılan ödünçlerin motora bildirilmesi; onaylanan öneriler de buraya yazılır. | Entegrasyon |  | 8 |
| `stg.Stock` | Stok; lot ve durum bazında. Bağlı proje, müşteri ya da sipariş doluysa stok ona ayrılmıştır; boşsa geneldir. | Entegrasyon |  | 24 |
| `stg.WorkOrder` | Açık iş emri (üretim, fason, yeniden işleme). | Entegrasyon |  | 33 |
| `stg.WorkOrderComponent` | İş emrinin bileşenleri ve çekilen miktar. | Entegrasyon |  | 17 |
| `stg.WorkOrderOperation` | İş emrinin operasyonları ve kalan iş. | Entegrasyon |  | 24 |
| `stg.PurchaseOrderLine` | Açık satın alma ve fason siparişi satırı (ve talep). | Entegrasyon |  | 28 |
| `stg.ProductionConfirmation` | Üretim gerçekleşmeleri: iş emri bazında stoğa girişler. | Entegrasyon |  | 12 |

## `prc` · İşlenmiş staging: ham katmanın güncel hâli, veri kuralları uygulanmış; validasyon ve load bunu okur (K-140) (24 tablo)

| Tablo | Açıklama | Sınıf | Versiyonlu | Alan |
|---|---|---|---|---|
| `prc.Material` | Malzeme ve planlama ana verisi. | Entegrasyon |  | 43 |
| `prc.Location` | Lokasyon (tesis, depo). Faz 1'de her lokasyon kendi içinde planlanır. | Entegrasyon |  | 23 |
| `prc.UomConversion` | Malzeme bazında birim dönüşümü. | Entegrasyon |  | 6 |
| `prc.ProductionVersion` | Üretim versiyonu: bir malzemenin ürün ağacı ve rota başlığı; rotaya RouteCode, ürün ağacına BOMCode ile bağlanır. Versiyon seçimi motorun kararıdır; aynı malzeme aynı dönemde birden fazla versiyonla üretilebilir. | Entegrasyon |  | 17 |
| `prc.BOM` | Ürün ağacı satırı. | Entegrasyon |  | 18 |
| `prc.Routing` | Rota: her satır bir operasyon–kaynak grubu ilişkisi; sıra önce OperationNo, sonra SequenceNo. Aynı operasyonun kaynak grupları ayrı satırda, ResourceRole ile. | Entegrasyon |  | 23 |
| `prc.MaterialReference` | Benzetilen ürün: kendi ağacı ya da rotası olmayan ürün, başka bir ürünün verisiyle planlanır. | Entegrasyon |  | 7 |
| `prc.Resource` | Kaynak: tek bir makine, işçi ya da fason iş yeri. Planlama birimi kaynak değil kaynak grubudur (K-180): tip bayrakları, kritiklik, kapasite birimi ve fasoncu gruptadır; kaynak gruplarına `ResourceGroupMember` ile bağlanır. | Entegrasyon |  | 18 |
| `prc.ResourceGroup` | Kaynak grubu: planlama birimi (K-180). Rota ve iş emri operasyonu grubu gösterir; plan ve yük grup düzeyindedir. Tip, kritiklik, kapasite birimi ve fasoncu gruptadır. Gruptaki kaynak sayısı `ResourceGroupMember`'dan bilinir, ayrıca girilmez. | Entegrasyon |  | 24 |
| `prc.ResourceGroupMember` | Kaynak grup eşleşmesi: kaynağın gruba üyeliği. Bir kaynak birden fazla gruba üye olabilir (birden fazla yetkinliği olan işçi). Geçerlilik tarihi yoktur: yüklü eşleşme bugünden itibaren geçerlidir. Gruptaki kaynak sayısı bu tablodan bilinir (K-180). | Entegrasyon |  | 8 |
| `prc.EmployeeAbsence` | Kişi bazında izin ve rapor. | Entegrasyon |  | 6 |
| `prc.Supplier` | Tedarikçi ve fasoncu. | Entegrasyon |  | 16 |
| `prc.MaterialSupplier` | Malzeme–tedarikçi ilişkisi; satın alma parametreleri. Satın alma her zaman sürekli; yuvarlama son hesapta. | Entegrasyon |  | 19 |
| `prc.Customer` | Müşteri. | Entegrasyon |  | 19 |
| `prc.Project` | Proje. | Entegrasyon |  | 14 |
| `prc.SalesOrderLine` | Müşteri sipariş satırı; teklifler IsQuote ile okunur. Vade: teyit tarihi, yoksa istek tarihi. | Entegrasyon |  | 25 |
| `prc.Forecast` | Talep tahmini (netleme ön hesapta). | Entegrasyon |  | 15 |
| `prc.BorrowPayback` | Projeler arası ödünç ve geri ödeme kaydı: devreye almada açık olan ve ERP'de doğrudan yapılan ödünçlerin motora bildirilmesi; onaylanan öneriler de buraya yazılır. | Entegrasyon |  | 8 |
| `prc.Stock` | Stok; lot ve durum bazında. Bağlı proje, müşteri ya da sipariş doluysa stok ona ayrılmıştır; boşsa geneldir. | Entegrasyon |  | 24 |
| `prc.WorkOrder` | Açık iş emri (üretim, fason, yeniden işleme). | Entegrasyon |  | 33 |
| `prc.WorkOrderComponent` | İş emrinin bileşenleri ve çekilen miktar. | Entegrasyon |  | 17 |
| `prc.WorkOrderOperation` | İş emrinin operasyonları ve kalan iş. | Entegrasyon |  | 24 |
| `prc.PurchaseOrderLine` | Açık satın alma ve fason siparişi satırı (ve talep). | Entegrasyon |  | 28 |
| `prc.ProductionConfirmation` | Üretim gerçekleşmeleri: iş emri bazında stoğa girişler. | Entegrasyon |  | 12 |

## `core` · Ana veri ve işlem verisi (27 tablo)

| Tablo | Açıklama | Sınıf | Versiyonlu | Alan |
|---|---|---|---|---|
| `core.Location` | Lokasyon (tesis, depo). Faz 1'de her lokasyon kendi içinde planlanır. | Ana veri |  | 25 |
| `core.UnitOfMeasure` | Ölçü birimi. | Ana veri |  | 3 |
| `core.UomConversion` | Malzeme bazında birim dönüşümü. | Ana veri | evet | 7 |
| `core.Resource` | Kaynak: tek bir makine, işçi ya da fason iş yeri. Planlama birimi kaynak değil kaynak grubudur (K-180): tip bayrakları, kritiklik, kapasite birimi ve fasoncu gruptadır; kaynak gruplarına `ResourceGroupMember` ile bağlanır. | Ana veri | evet | 19 |
| `core.ResourceGroup` | Kaynak grubu: planlama birimi (K-180). Rota ve iş emri operasyonu grubu gösterir; plan ve yük grup düzeyindedir. Tip, kritiklik, kapasite birimi ve fasoncu gruptadır. Gruptaki kaynak sayısı `ResourceGroupMember`'dan bilinir, ayrıca girilmez. | Ana veri | evet | 25 |
| `core.ResourceGroupMember` | Kaynak grup eşleşmesi: kaynağın gruba üyeliği. Bir kaynak birden fazla gruba üye olabilir (birden fazla yetkinliği olan işçi). Geçerlilik tarihi yoktur: yüklü eşleşme bugünden itibaren geçerlidir. Gruptaki kaynak sayısı bu tablodan bilinir (K-180). | Ana veri | evet | 9 |
| `core.EmployeeAbsence` | Kişi bazında izin ve rapor. | İşlem verisi | evet | 7 |
| `core.Material` | Malzeme ve planlama ana verisi. | Ana veri | evet | 44 |
| `core.Supplier` | Tedarikçi ve fasoncu. | Ana veri | evet | 17 |
| `core.MaterialSupplier` | Malzeme–tedarikçi ilişkisi; satın alma parametreleri. Satın alma her zaman sürekli; yuvarlama son hesapta. | Ana veri | evet | 20 |
| `core.ProductionVersion` | Üretim versiyonu: bir malzemenin ürün ağacı ve rota başlığı; rotaya RouteCode, ürün ağacına BOMCode ile bağlanır. Versiyon seçimi motorun kararıdır; aynı malzeme aynı dönemde birden fazla versiyonla üretilebilir. | Ana veri | evet | 18 |
| `core.BOM` | Ürün ağacı satırı. | Ana veri | evet | 19 |
| `core.Routing` | Rota: her satır bir operasyon–kaynak grubu ilişkisi; sıra önce OperationNo, sonra SequenceNo. Aynı operasyonun kaynak grupları ayrı satırda, ResourceRole ile. | Ana veri | evet | 24 |
| `core.MaterialReference` | Benzetilen ürün: kendi ağacı ya da rotası olmayan ürün, başka bir ürünün verisiyle planlanır. | Ana veri | evet | 8 |
| `core.MaterialAllocationRule` | Alokasyon kuralı: bir malzemenin hangi sahip (sipariş, proje, müşteri) adına ayrı izleneceği. Sistem üretir: her aktarımın sonunda ve sentetik yüklemede taleplerden ürün ağacında aşağı yürünerek hesaplanır (K-199). ERP sözleşmesinde yoktur, elle değiştirilemez, veri kuralı yazamaz, senaryoya bağlı değildir. Model ve pegging ağaçta yeniden yürümez, bu tabloyu okur. | Ana veri | evet | 7 |
| `core.Project` | Proje. | Ana veri | evet | 15 |
| `core.Customer` | Müşteri. | Ana veri | evet | 20 |
| `core.SalesOrderLine` | Müşteri sipariş satırı; teklifler IsQuote ile okunur, plana dahil olmaları senaryo parametresi. Vade: teyit tarihi, yoksa istek tarihi. | İşlem verisi | evet | 26 |
| `core.Forecast` | Talep tahmini (netleme ön hesapta). | İşlem verisi | evet | 16 |
| `core.BorrowPayback` | Projeler arası ödünç ve geri ödeme kaydı: devreye almada açık olan ve ERP'de doğrudan yapılan ödünçlerin motora bildirilmesi; onaylanan öneriler de buraya yazılır. | İşlem verisi | evet | 9 |
| `core.Stock` | Stok; lot ve durum bazında. Bağlı proje, müşteri ya da sipariş doluysa stok ona ayrılmıştır; boşsa geneldir. | İşlem verisi | evet | 31 |
| `core.WorkOrder` | Açık iş emri (üretim, fason, yeniden işleme). | İşlem verisi | evet | 40 |
| `core.WorkOrderComponent` | İş emrinin bileşenleri ve çekilen miktar. | İşlem verisi | evet | 19 |
| `core.WorkOrderOperation` | İş emrinin operasyonları ve kalan iş. | İşlem verisi | evet | 26 |
| `core.PurchaseOrderLine` | Açık satın alma ve fason siparişi satırı (ve talep). | İşlem verisi | evet | 35 |
| `core.TransferOrder` | Açık lokasyonlar arası transfer; Faz 1'de sabit hareket (gelen arz, giden talep). | İşlem verisi | evet | 13 |
| `core.ProductionConfirmation` | Üretim gerçekleşmeleri: iş emri bazında stoğa girişler. | İşlem verisi | evet | 13 |

## `param` · Planlama parametreleri ve senaryo tanımları (16 tablo)

| Tablo | Açıklama | Sınıf | Versiyonlu | Alan |
|---|---|---|---|---|
| `param.SupplierLimit` | Tedarikçi limiti (K-191; problem 39): satın alınan malzemede tedarikçi üst limiti ve tedarikçi kapanışı; iki kayıt türü tek tabloda. Senaryoya bağlı, Baz + fark (K-176). Model kısıtları ekranından girilir. | Parametre |  | 16 |
| `param.MaterialHold` | Malzeme blokajı (K-193): malzeme için belli tarihlerde yeni tedarik planı (üretim, satın alma ya da ikisi) çıkarılmaz. Senaryoya bağlı, Baz + fark (K-176). Model kısıtları ekranından girilir. | Parametre |  | 14 |
| `param.PlanningSetting` | Senaryonun planlama parametreleri (anahtar–değer; K-175). Anahtarlar, tipleri, seçenekleri ve başlangıç değerleri docs/06 fonksiyon 22'deki tabloda (`app/params/catalog.py`). | Parametre |  | 3 |
| `param.TimeBucketDefinition` | Zaman yapısı: senaryonun ufuk ve dönem dizisi. Kullanıcı tarih girmez; her satır bir parçadır: dönem tipi (dönemlerin büyüklüğü) ve kapsam (parçanın ne kadar sürdüğü). Başlangıç ve bitiş plan başlangıcına göre hesaplanır (fonksiyon 23, K-175). Raporlama ekseni ayrı diziyse `Axis` = Rapor satırları. Dönem tipleri ve kapsam birimleri iki eksende aynıdır; kapsam birimi dönem tipinden küçük olamaz (çeyrek ve yıl dönem tipinde Ay da olabilir). | Parametre |  | 6 |
| `param.DemandPriority` | Öncelik grubu (K-195): müşteri, proje ya da sipariş satırı için bu ekranda girilen 1–5 öncelik grubu. Senaryoya bağlı, Baz + fark (K-176); kayıt başına tek satır. Öncelik yönetimi ekranından girilir. | Parametre |  | 10 |
| `param.ObjectiveDefinition` | Senaryonun hedef satırları (leksikografik, ağırlık yok; K-175): motor satırları sırayla çözer. Senaryonun süre bütçesi aktif satırların sürelerinin toplamıdır. Hedef listesi kullanıcınındır (K-196): her satır bir hedef ve bir kapsamdır (Scope); kapsamlar örtüşebilir, hiçbir satırın kapsamadığı kayıt hiçbir hedefe girmez. | Parametre |  | 9 |
| `param.WarningDefinition` | Uyarı kataloğu (K-190): sistemin tanıdığı uyarı kodları ve kategorileri. Satırları sistem yazar; eşik, önem ve aktiflik senaryoya bağlıdır (WarningThreshold). | Parametre |  | 2 |
| `param.PeggingCriterion` | Pegging sıralama ölçütleri (K-201): senaryonun İhtiyaç sırası ve Arz sırası listeleri; her satır bir ölçüttür, sırasıyla. Ölçütler yukarıdan aşağı uygulanır. Senaryoda satır yoksa başlangıç sırası geçerlidir (`app/params/pegging.py`); ilk kayıtta listenin tamamı yazılır. Bir listede her ölçüt bir kez bulunur. Yön yalnız yönlü ölçütte doludur ("İhtiyaca en yakın" yalnız arzın Dönem ölçütünde). | Parametre |  | 5 |
| `param.WarningThreshold` | Senaryonun uyarı eşikleri (K-190): her senaryoda her uyarı için bir satır. Kademeli: her önem için ayrı eşik; boş kademe kullanılmaz. Yön uyarıya göre sabittir ve eşik dahil değildir. | Parametre |  | 9 |
| `param.ScenarioDefinition` | Senaryo tanımı (K-175): parametrelerinin tamamını kendisi taşır (PlanningSetting, TimeBucketDefinition, ObjectiveDefinition ve senaryoya bağlı öteki tablolar); senaryolar arasında paylaşılan set yoktur. Kurulumda tek senaryo "Baz" gelir; silinemez, pasif yapılamaz. | Parametre |  | 9 |
| `param.WorkPattern` | Çalışma düzeni (K-185): günlük kapasite ve haftanın günleri. Çalışma günü yalnız buradan gelir. Geçerlilik: önce seviye (kaynakta o günü kapsayan kayıt varsa kaynağınkiler, yoksa grubunkiler), sonra başlangıcı en ileri olan. | Parametre |  | 19 |
| `param.ResourceEfficiency` | Verimlilik (K-185): kapasite katsayısı, yüzde. Giriş yoksa %100. Geçerlilik kuralı çalışma düzenindeki gibi, kendi kayıtlarından. | Parametre |  | 12 |
| `param.ResourceGroupConstraint` | Model kısıtları (K-189): kaynak grubu başına, tarihsiz iki değer. Kısıtsız kapasite çarpanı: Kaynak kısıtı = Kısıtsız olan senaryoda grubun dönem üst sınırı = kullanılabilir kapasite × çarpan (boşsa sınır yok). Hedef doluluk: kesin sınır değil, "Hedef doluluğun üstü" hedefinin eşiği (boşsa hedef yok). Yalnız kritik gruplarda uygulanır; kritik olmaktan çıkan grubun değeri saklanır ama uygulanmaz. Senaryo ve kaynak grubu başına en çok bir kendi satırı; iki değeri de boş kalan satır silinir. | Parametre |  | 10 |
| `param.OvertimeLimit` | Ek mesai limiti (K-185): çalışılan günde kaynak başına yapılabilecek ek mesai, grubun kapasite biriminde. Giriş yoksa ek mesai yok. Her gruba girilebilir. ERP'den gelen kalan fazla mesai (kaynakta) ayrıdır, birleştirilmez. | Parametre |  | 12 |
| `param.ResourceDowntime` | Bakım ve duruş (K-185): kapasiteden düşülür. Gruba girilen duruş grubun bütün kaynaklarına uygulanır. Geçerlilik kuralının dışındadır: duruşlar birleşir, gün bir kez düşer. Çalışan izni ERP'den gelir (`core.EmployeeAbsence`), burada tutulmaz. | Parametre |  | 13 |
| `param.FactoryCalendar` | Fabrika takvimi (K-185, K-194): lokasyonun bütün kaynak gruplarına ve kaynaklarına uygulanan toplu duruş (tatil, toplu izin, yarım gün). Tek günde başlangıç ve bitiş aynıdır. | Parametre |  | 12 |

## `planning` · Senaryo, çalışma ve plan çıktıları (12 tablo)

| Tablo | Açıklama | Sınıf | Versiyonlu | Alan |
|---|---|---|---|---|
| `planning.Scenario` | Senaryo sonucu: bir senaryonun bir veri versiyonuyla hesaplanmış planı. Bir sonraki gece silinmez, saklanır; saklama süresi sistem ayarıdır (K-177; ekranda "plan versiyonu"). | Plan |  | 6 |
| `planning.Workspace` | Kullanıcının bir senaryo üzerindeki çalışması; yayınlanmazsa gece silinir. | Plan |  | 6 |
| `planning.WorkspaceOverride` | Çalışmadaki geçici değişiklikler: parametreler ve çalışmada değiştirilebilir ana veri alanları. | Plan |  | 7 |
| `planning.PlanRun` | Bir plan hesabı (senaryo ya da çalışma); bütün plan çıktıları buna bağlı. | Plan |  | 10 |
| `planning.PlanVersion` | Onaylı plan versiyonu; hep saklanır. Aynı anda tek geçerli. | Plan |  | 7 |
| `planning.PlannedOrder` | Planlı sipariş: üretim, satın alma ya da fason önerisi. Satın alma sürekli hesaplanır, yuvarlanmış miktar ayrıca. | Plan |  | 14 |
| `planning.SupplyRecommendation` | Mevcut arz için öneri: öne çek, ertele, iptal, azalt, hızlandır. | Plan |  | 9 |
| `planning.DemandFulfillment` | Talebin planlanan karşılanması ve gecikmesi. | Plan |  | 9 |
| `planning.CapacityLoad` | Kaynak grubu ve dönem bazında kapasite ve kapasite yükü (plan ve yük grup düzeyindedir, K-180). | Plan |  | 10 |
| `planning.Pegging` | Arz–talep bağı (full pegging). | Plan |  | 10 |
| `planning.PlanWarning` | Plan hesabının ürettiği uyarılar. | Plan |  | 8 |
| `planning.PlanMetric` | Senaryo karşılaştırma metrikleri; senaryo silinse de özet kısa süre kalır. | Plan |  | 3 |

## `adm` · Veri yönetimi ve sistem (SQL Server'da `sys` ayrılmış olduğu için `adm`) (39 tablo)

| Tablo | Açıklama | Sınıf | Versiyonlu | Alan |
|---|---|---|---|---|
| `adm.FieldDefinition` | Veri sözlüğü: her alanın sınıfı ve değer davranışı. Yapısını System owner yönetir. | Veri yönetimi |  | 11 |
| `adm.DataRule` | Veri kuralı (K-141, ekran 04): tek tablo içinde "koşul ise hedef alan = sonuç". Staging'in işlenmiş katmanında tablo başına sırayla çalışır (K-140); varsayılan kural yoktur, kurulumda eklenir. | Veri yönetimi |  | 20 |
| `adm.DataRuleCondition` | Kural koşulları: aynı GroupNo'daki koşullar VE, gruplar arası VEYA (K-136); koşul editörü validasyon kurallarıyla ortaktır. | Veri yönetimi |  | 7 |
| `adm.DataRuleEffect` | Kural izi (K-140): işlenmiş katmanda hangi hücreyi hangi kuralın son değiştirdiği ve ham değer; her çalıştırmada tablo için yeniden yazılır. İpucu: "Kural 3 · Lokasyon bayrakları · ham değer: boş". | Veri yönetimi |  | 5 |
| `adm.ManualValue` | Manuel değer (K-170): ana veri ve işlem verisinde kayıt ve alan başına; kuralı ve ERP'yi ezer, aktarımda korunur, süresi yoktur. Alttaki değer (ERP ya da kural sonucu) girişte ve her aktarımda saklanır; kaldırılınca hücreye son alttaki değer döner. Değerler alanın tipinden metne çevrilmiş hâldedir. | Veri yönetimi |  | 14 |
| `adm.FieldChange` | Alan değişikliği (K-173): ana veri ve işlem verisinde kaydın alanı her değiştiğinde, değişiklik anında aynı işlemde yazılır; detay kartının Geçmiş sekmesi buradan okunur. Yazanlar aktarım, manuel değer girme ve kaldırma ve Smartchain girişleridir. Değerler alanın tipinden metne çevrilmiş hâldedir. Silinmez. | Veri yönetimi |  | 13 |
| `adm.FieldValueSource` | Geçerli değerin kaynağı ve ERP değeri (ezilse bile saklanır). | Veri yönetimi |  | 6 |
| `adm.ImportBatch` | Ham veri partisi: her yükleme parti numarası, zaman ve kaynakla. Ham veri saklama süresi kadar saklanır (`RawDataRetentionDays`; boşsa temizlik çalışmaz, K-156); parti kaydı ve sayıları silinmez. LoadType Değişen: arayüzde "Ekle / güncelle" (K-129). | Veri yönetimi |  | 17 |
| `adm.ImportFinding` | Partinin ön kontrol bulguları (fonksiyon 03). Validasyon (fonksiyon 04) partiye değil staging'in güncel hâline aittir, bulguları `ValidationFinding`'dedir (K-134). | Veri yönetimi |  | 9 |
| `adm.IntegrationEntity` | Tablo başına çekim ayarı (K-130). Satır yoksa ya da yöntem boşsa tablo Excel sayılır, çekim açıktır. | Veri yönetimi |  | 19 |
| `adm.IntegrationViewVersion` | View'ın sürüm geçmişi (K-130): tanım değişince yeni sürüm. Smartchain view oluşturmaz, yalnız okur ve saklar. | Veri yönetimi |  | 8 |
| `adm.ValidationRule` | Validasyon kuralı (K-136, ekran 27). Yapısal kontroller ve hazır kurallar koddaki katalogdan kurulur (geçişte eksik olan eklenir; sınıfı ve aktifliği kullanıcıda kalır); kullanıcı kuralı ekrandan eklenir. | Veri yönetimi |  | 14 |
| `adm.ValidationRuleCondition` | Kullanıcı kuralının ve düzenlenmiş hazır kuralın koşulları (K-136, K-139): aynı GroupNo'daki koşullar VE, gruplar arası VEYA. Operatörler `DataRuleCondition` ile aynıdır. | Veri yönetimi |  | 7 |
| `adm.ValidationRun` | Tablo başına validasyon çalışması (K-134): çipin durumu son çalışmadan, sonucu bulgulardan okunur. | Veri yönetimi |  | 16 |
| `adm.ValidationFinding` | Staging'in güncel hâlinin validasyon bulguları (K-134). Bir kural yeniden çalışınca o kuralın o tablodaki bulguları yenilenir; güncel hâlden çıkan satırın bulguları silinir. Ön kontrol bulguları `ImportFinding`'dedir. | Veri yönetimi |  | 10 |
| `adm.DataQualityWarning` | Veri kalitesi uyarısı (K-174, ekran 05): yüklenmiş veride (`core`) takipli Uyarı kuralı ya da Smartchain verisi kontrolüyle bulunan sorun. Kimliği kural + kayıt; her kontrolde var olan uyarı devam eder, sorun kalkınca (yok sayılmış olsa da) silinir. | Veri yönetimi |  | 17 |
| `adm.DemandChain` | Talep zinciri kümesi (K-174): açık satış siparişi ve ufuktaki tahminden ulaşılan kayıtlar; her veri kalitesi kontrolünde baştan hesaplanır. Uyarının önemi buradan (kayıt ya da malzemesi kümedeyse Yüksek). | Veri yönetimi |  | 2 |
| `adm.DemandChainPath` | Detay kartının Talep zinciri sekmesi (K-174): kart açılınca uyarının kaydından yukarı çıkılarak bulunan talepler ve malzeme yolları; uyarı başına en çok 1.000 yol. Önbellektir: her veri kalitesi kontrolünde silinir. | Veri yönetimi |  | 9 |
| `adm.DataVersion` | Aktarım ile oluşan dondurulmuş veri versiyonu; tam ya da kısmi (K-152). | Veri yönetimi |  | 8 |
| `adm.DataVersionEntity` | Aktarımda hangi tabloların aktarıldığı (kısmi aktarımda seçilen grupların tabloları). | Veri yönetimi |  | 8 |
| `adm.RawCompare` | Dünden bugüne (K-160): tablo başına ham verinin son hâli ile önceki günün son hâlinin karşılaştırma özeti. Yükleme sonrası hesaplanır. | Veri yönetimi |  | 11 |
| `adm.RawCompareRow` | Dünden bugüne (K-160): yeni gelen, gelmeyen ve güncellenen kayıtlar; güncellenen kayıtta değişen alan başına bir satır. Tablonun her hesabında yeniden yazılır. | Veri yönetimi |  | 8 |
| `adm.AppUser` | Uygulama kullanıcısı (Faz 1'de yerel). | Sistem |  | 15 |
| `adm.UserSession` | Sunucu tarafı oturum (K-97). Tarayıcıdaki çerez rastgele bir anahtar taşır; tabloda yalnız anahtarın SHA-256 özeti durur. | Sistem |  | 9 |
| `adm.PasswordHistory` | Kullanıcının önceki şifre özetleri (K-98): yeni şifre son `PasswordHistoryCount` şifreden farklı olmalı. | Sistem |  | 4 |
| `adm.LoginThrottle` | Bilinmeyen, şifresiz ya da pasif hesap adına yapılan hatalı girişlerin sayacı (K-98). Gerçek hesaptaki sayaçla aynı davranır; giriş cevabından hesabın var olup olmadığı anlaşılmaz. | Sistem |  | 4 |
| `adm.Job` | İş kuyruğu (SQL Server tablosu): gece senaryoları, çalışma hesapları, aktarımlar. | Sistem |  | 20 |
| `adm.SolverLog` | Çözüm logu; ilk günden tutulur. | Sistem |  | 6 |
| `adm.SystemEvent` | Sistem hataları ve sistem aksiyonu (K-106). Saklama `SystemEventRetentionDays`; motor servisi eskileri siler. | Sistem |  | 9 |
| `adm.ServiceStatus` | Motor servisinin kalp atışı (K-106). Durum saklanmaz, okurken hesaplanır. | Sistem |  | 5 |
| `adm.AuditLog` | Kim, ne zaman, neyi değiştirdi; giriş kayıtları; kayıtlar silinemez (K-109). | Sistem |  | 9 |
| `adm.SystemSetting` | System owner'ın ayarları: çözücü, süre bütçeleri, işçi sayısı, eş zamanlı çalışma sınırı, saklama süreleri. | Sistem |  | 2 |
| `adm.TableView` | Kayıtlı tablo görünümü (K-89): kolon seti ve sırası, genişlikler, sabitleme, sıralama, filtreler, gruplama. | Sistem |  | 8 |
| `adm.TableViewDefault` | Kullanıcının bir liste için varsayılan görünümü (K-89). Satır yoksa liste tanımındaki "Standart" görünüm açılır. | Sistem |  | 3 |
| `adm.TableViewStandard` | Şirket Standart görünümü (K-162): System owner ya da Admin'in kaydettiği Standart, liste başına tek satır. Satır yoksa liste tanımındaki Standart geçerlidir. | Sistem |  | 5 |
| `adm.Flow` | Zamanlanmış iş (K-163, K-164): zaman, Veri çek kapsamı, aktarım türü, isteğe bağlı temizlik. Adımların sırası sabittir. | Sistem |  | 13 |
| `adm.FlowRun` | Zamanlanmış işin her çalıştırması (K-163): zaman, adım, durum ve nedeni, işler, veri versiyonu. | Sistem |  | 16 |
| `adm.FlowRunDismissal` | Kullanıcının kapattığı zamanlanmış iş bildirimi (K-163); kapatılan çip o kullanıcıda yeniden görünmez. | Sistem |  | 3 |
| `adm.License` | Çevrimdışı imzalı lisans. | Sistem |  | 4 |

## `cache` · Önbellek: girişlerden hesaplanan ara sonuçlar; veri değildir, silinirse yeniden üretilir (K-184) (2 tablo)

| Tablo | Açıklama | Sınıf | Versiyonlu | Alan |
|---|---|---|---|---|
| `cache.ResourceCapacityDay` | Kaynak grubu × kaynak × gün kapasite ara sonucu (K-184, K-185): dönem tablosu "Kaynak grubu × dönem" bundan toplanır. Grup kaydı o grubun içinde uygulandığı için birden fazla gruba üye kaynak her grubunda ayrı satırdır. Yalnız planlama ufkundaki günler; Baz'ı izleyen senaryoda yalnız Baz'dan farklı çıkan satırlar (gerisi Baz'ın satırlarından okunur). Kümelenmiş anahtar senaryo, kaynak, grup, gün: tek kaynağın yenilenmesi ve senaryonun gün aralığı okuması aynı sıradan. | Önbellek |  | 10 |
| `cache.PeriodCacheState` | Önbelleğin durumu (K-184): önbellek ve senaryo başına tek satır. Satır yoksa önbellek kurulmamıştır; hesap kodunun sürümü ya da veri versiyonu farklıysa önbellek düşürülüp yeniden kurulur; gün aralığı ufkun gerisinde kaldıysa geçmiş günler temizlenir, ufuk ilerlediyse yalnız eksik günler hesaplanır. | Önbellek |  | 7 |

