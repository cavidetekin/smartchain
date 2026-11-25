# Pegging ve özel alokasyon: karar notları

Tarih: 23–24.11.2026 görüşmeleri.

**Durum: not. Bu dosya bağlayıcı değildir; kod bu dosyaya göre değiştirilmez.** Ara iş kapandı (K-198, 0.57.0). 7.15 kapandı (K-199, 0.58.0). 7.16 kapandı (K-200, 0.59.0). Buradaki kararlar henüz sözleşme dosyalarına (`00-kararlar`, `02-veri-modeli`, `03-entegrasyon` ve diğerleri) işlenmedi ve K numarası almadı. Adımları `GELISTIRME_ADIMLARI.md`'ye eklendi (24.11.2026: Ara iş, 7.15, 7.16, 7.17, 9.5 ve ilgili adımlara notlar); her adım başlarken ilgili kararlar önce sözleşme dosyalarına işlenir (K-54), sonra kod yazılır. Motorla ilgili ayrıntılar Aşama 10'da konuşulacak.

İşaretler: ✔ karar · ◻ öneri (onay yok) · ? açık konu

---

## 1. Özel alokasyon (sahiplik) kuralı

- ✔ Tek kural: **anahtarlı arz yalnız sahibine gider; anahtarsız arz herkese açıktır.** (K-198)
- ✔ Paylaşım kuralları yok. **Proje grubu tablosu ve Takip kuralı kaldırılır.** (K-198)
- ✔ Ödünç ve geri ödeme tablosu (`BorrowPayback`) **kalır.**
- ? Ödünç kayıtlarının modelde kullanılıp kullanılmayacağı yeniden ele alınacak; kullanılırsa siparişten pek farkı olmayan bir kayıt gibi düşünülebilir.
- ✔ Sahiplik hiyerarşisi: **sipariş → proje → müşteri** (en detaylıdan genele). Hiyerarşi talepten okunur. (K-198)
- ✔ Arzın anahtarı, dolu olan **en detaylı tek alandır** (siparişe ayrılmış arz yalnız siparişi taşır; müşteri ve proje yazılmaz). (K-198)
- ✔ Bir malzeme, bir sahip için ayrı izlenir (kendi üretimi, satın alması, bakiyesi) ancak **malzemenin kendisinde ya da alt seviyelerinde, özel alokasyonlu bir malzemede o sahibe ayrılmış arz varsa.** Yoksa genele (grup) düşer.
- ✔ Belirleme modelden bağımsızdır: her sipariş için ürün ağacında (bütün alternatifler, üretim siparişleri dâhil) aşağı yürünür.
- ✔ Takip seviyesi, malzemenin kendisinde ve altında bulunan en detaylı seviyedir. Alt seviyede sipariş bazlı takip varsa o siparişin akışı üstteki bütün seviyelerde ayrı kalır (yukarı doğru gevşemez, aşağı doğru gevşeyebilir).
- ✔ Özel bakiye genel arzı kullanabilir; bu tek yönlü bir **aktarım** kararıdır ve yalnız mevcut genel arzın geldiği dönemlerde gerekir (1. dönem stok, açık siparişler).
- ✔ Anahtarlı bakiyeler arasında aktarım yoktur. Bir malzemede müşteri, proje ve sipariş arzı birlikte varsa birbirine karışmaz; aktarım yalnız genelden gelir.
- ✔ Kullanılmayan anahtarlı arz (fazla) boşta kalır ve listelenir. Yeni arz sahip başına ayrı açılır, partiler birleştirilmez, yuvarlama fazlası sahibinindir.
- ✔ Kural tablosuna yalnız kullanacak talebi ve açık arzı olan sahipler girer; talebi olmayan, sahibi bulunamayan ya da kapanmış ayrılmış arz satır açmaz, model onu plana almaz (K-199).
- ✔ Senaryo parametresi (Parametreler › Malzeme): **"Özel alokasyon": Dikkate al · Dikkate alma.**
- ◻ "Dikkate alma" seçilince anahtarlı arz da genele girer; bu durumda "sahibi dışında kullanılan ayrılmış arzlar" listesi çıkarılır.
- ◻ Ayrılmış bir talep, her malzemede "o malzemenin kendisinde arzı olan en detaylı seviye + genel"i kullanır (ayrıntı teyit edilmedi).
- ? Bugünkü "model proje görmez, tek havuz" ifadesi kıtlık durumunda yanlış sonuç veriyor; değişecek.

## 2. Veri alanları ve tablolar

- ✔ Ad her yerde **`IsCustomAllocated`** (`IsCustomTracked` yerine); arayüzde "Özel alokasyon". Faz 1'den çıkarılan "alokasyon / pay ayırma" konusu ile ilgisi yok. (K-198)
- ✔ **Malzemede** `IsCustomAllocated`: kuraldır; yalnız ERP'den ya da veri kuralıyla gelir, **elle girilmez**. Boşsa veri kalitesi uyarısı. (K-198)
- ✔ **Arz ve öneri satırlarında** `IsCustomAllocated`: süzme için vardır, **sistem hesaplar** (malzeme özel alokasyonluysa ve satırda sahip bilgisi varsa Evet). (K-198)
- ✔ ERP'den gelen satır bayrakları (stok, üretim siparişi, satın alma satırı, müşteri, satış siparişi satırı) sözleşmeden çıkar. (K-198)
- ✔ Bütün arzlarda (stok, üretim siparişi, satın alma) yüklemede sistem doldurur: **`AllocationLevel`** (Sipariş · Proje · Müşteri) ve **`AllocationKey`** (ör. `MUS-A`, `PRJ-01`, `SO-1003|10|1`). (K-198)
- ✔ Eşleşme seviye + anahtar ile yapılır (içeride Id). **Lokasyon anahtarın parçası değildir.** (K-198)
- ✔ Malzeme özel alokasyonlu değilse, arz satırında sahip bilgisi (proje, müşteri, sipariş) dolu olsa bile `AllocationLevel` ve `AllocationKey` **boş kalır**; satır geneldir. Seviye ve anahtar doluysa arz ayrılmış demektir. (K-198)
- ✔ Malzemede `IsCustomAllocated` **boşsa** arz satırları genel sayılır (`IsCustomAllocated` = Hayır, seviye ve anahtar boş); malzemedeki alan boş kalır ve veri kalitesi uyarısı çıkar. (K-198)
- ✔ Siparişe ayrılmış arzda kalem boşsa anahtar yalnız sipariş numarasıdır ve o siparişin bütün kalemlerine açıktır. (K-198)
- ✔ `planning.PlannedOrder`: **`ProjectId` kalkar**; `IsCustomAllocated`, `AllocationLevel`, `AllocationKey` eklenir (motor yazar). (K-198)
- ✔ Stok, üretim siparişi ve satın alma satırının ana tablosunda sipariş no, satır no ve alt satır no ayrı alanlar olarak durur; kalemli anahtar her zaman üç parçadır (K-198).
- ✔ Üç arz tablosunda sahip alanlarının adı: Bağlı proje · Bağlı müşteri · Bağlı sipariş no · Bağlı sipariş satırı · Bağlı sipariş alt satırı; ilişkili alanlar da aynı adı taşır; iç bağ kolonu gösterilmez (K-198).
- ✔ Sahibi bulunamayan ya da kapanmış ayrılmış arz genele düşmez; anahtar ERP'nin yazdığı gibi kalır, arz boşta bekler; uyarı yok, raporda görünür (K-198).
- ✔ Bakılacak: `PlannedOrder` çok dar (üretim alternatifi, lokasyon, kaynak yok); yapısı sonra yeniden ele alınacak.
- ✔ Yeni **core** tablo **`MaterialAllocationRule`**: malzeme, lokasyon, `AllocationLevel`, `AllocationKey`, **sebep** (Kendi arzı · Alt seviye arzı). Sistem üretir; elle değişmez; senaryo değildir; veri versiyonu değişince (yükleme dâhil) yeniden hesaplanır. Kaynak malzeme kolonu; versiyonlu; Ana veri › Malzeme sekmesinde ve malzeme kartında gösterilir (K-199).

## 3. Üretim akışı ekranı

- ✔ Ad: **Üretim akışı** ("Ürün yapısı" reddedildi).
- ✔ Bir malzemenin altındaki ve üstündeki bütün olası akışları ürün ağacından çizer; plandan, modelden ve senaryodan bağımsızdır.
- ✔ **Kapalı açılır**: yalnız seçili malzeme görünür; her basış bir seviye açar.
- ✔ Birden çok ürün ağacı alternatifi varsa önce "Alternatif 1, 2, 3" kutuları gelir, basılan alternatifin malzemeleri açılır; tek alternatif varsa malzemeler doğrudan açılır.
- ✔ **Sol: beni kullananlar. Sağ: benim kullandıklarım.**
- ✔ Okların ucu vardır ve malzemenin gittiği yönü gösterir.
- ✔ Malzeme satırının ⋯ menüsünden geniş pencere olarak açılır (kartta sekme yok); "Tümünü kapat" düğmesi; çift tıklama seçili malzemeyi değiştirir; aynı malzeme iki yolda açılırsa iki kutu görünür (K-200).
- ✔ Bir basışta 20'den çok kutu açılacaksa ilk 20 ve "+N malzeme" kutusu (K-200).
- ✔ Alternatif kutusu farklı ürün ağacı başınadır (aynı ağaçlı versiyonlar birleşir); ağaç satırındaki alternatif grubu kutunun köşesinde "veya G1" etiketi; hayalet malzeme kutu olarak görünür; benzetilen ürün benzetildiği ürünün ağacını notuyla açar; miktar birimli, fire yok (K-200).
- ✔ Kutular malzeme seviyesine göre renkli (nihai ürün erik, yarı mamul petrol, hammadde hardal; hayalet gri; seçili nane); yakınlaştırma (− · + · Sığdır · %100, Ctrl + tekerlek); PNG olarak indirme; benzetilen notu yalnız seçili malzemede başlığın altında (K-200).
- ✔ Geliştirme adımı: 7.16.
- Mockup: `plans/7.15-mockups/uretim-akisi.html`

## 4. Pegging: genel ilkeler ve öncelik (sıralama) kararları

- ✔ Ad şimdilik **pegging**.
- ✔ Pegging **modelden sonra** hesaplanır; **elle müdahale yoktur**, tamamen parametreyle yönetilir.
- ✔ Tek seviyeli pegging ve **full (çok seviyeli) pegging** birlikte vardır.
- ✔ Pegging **senaryo bazlıdır.**
- ✔ Sürekli hesaplanan bir şey olmamalı; **üretim kararı ya da öncelik değişince** yeniden hesaplanır.
- ✔ Parametre **"Full pegging yöntemi": FIFO · Talep termini.**
  - FIFO: her seviye kendi ihtiyaç tarihine göre sıralanır.
  - Talep termini: yalnız en üstteki talebin terminine göre sıralanır.
- ✔ Bu ayrı bir parametredir; **Hedefler sırasından bağımsızdır** (model kararını vermiştir, pegging ayrıdır).
- ✔ Müşteri ihtiyacı: uygulanabilir olduğu ve gecikme yaratmadığı sürece, ortak bir alt malzemenin ilk üretimi **termini en yakın siparişe** gitmelidir.
- ✔ Tek seviyeli pegging'de sıralama kuralı işler.
- ✔ İhtiyaç satırları: **talep karşılama, üretim ihtiyacı.**
- ✔ **Güvenlik stoğu ihtiyaç satırı değildir**; artan arz "Güvenlik stoğu için" / "Fazla arz" olarak etiketlenir.
- ✔ Arz satırları: stok, kalitedeki stok, üretim siparişi, satın alma siparişi, üretim planı, satın alma önerisi.
- ✔ Stok ve satın almada sıralamaya **raf ömrü** de girer.
- ◻ Algoritma: sipariş sipariş, yukarıdan aşağı; her malzemede planın bütün ihtiyaçlarına karşı uygulanabilirlik kontrolü (öncelikli sipariş yalnız başkasını geciktirmeyeni alır).
- ? Sıralama ölçütlerinin kullanıcı tarafından sıralanabilir olması ve nihai ürün / yarı mamul / hammadde için ayrı sıralama isteği: mockup karmaşık bulundu, **çözülmedi**, yeniden ele alınacak. Mockup: `plans/7.15-mockups/pegging.html`

## 5. Pegging'de eşleşme

- ✔ Herkes allocation key üzerinden, hiyerarşiyle eşleşir. Bir ihtiyacın bakacağı arz sırası: Sipariş → Proje → Müşteri → Anahtarsız (genel).
- ✔ Sipariş seviyesinde sıra: önce kendi kalemine ayrılmış arz (kalemli anahtar), sonra siparişin geneline ayrılmış arz (kalemsiz anahtar), sonra proje, müşteri, genel.
- ✔ **Genelden gelen miktar:** model aktarım miktarını plan çıktısına yazar; pegging o miktarı **aşamaz ve altında kalamaz**, yalnız arkasındaki gerçek arzı (hangi stok, hangi sipariş) kendi sıralamasıyla seçer. Amaç: pegging modelle çelişmesin.
- ✔ **Sipariş ve tahminde anahtar yoktur**; talep yalnız kimliğini taşır (sipariş, proje, müşteri). Anahtar her malzemede `MaterialAllocationRule`'dan okunur, çünkü aynı sipariş bir malzemede özel, başka malzemede genel olabilir.
- ✔ Her malzemede sorulur: kural tablosunda Sipariş var mı → Proje var mı → Müşteri var mı → yoksa genel. İlk bulunanda durur.
- ✔ **Müşterili tahmin o müşteriye ayrılmış arzı kullanır.** Müşterisi boş tahmin her malzemede geneldir.
- ✔ Tahmin de sipariş de aynı kontrolden geçer; tahminde sipariş no olmadığı için proje → müşteri seviyesinde eşleşir (K-199).
- ✔ Üretim ihtiyacı, hizmet ettiği talebin kimliğini taşır; genel üretimin bileşen ihtiyacı kimliksizdir.

## 6. Pegging sonuç tablosu ve görünümler

- ✔ Üç görünüm: **Tek seviye · Çok seviye ağaç · Çok seviye akış.** Görsel olarak uygun bulundu; alt ayrıntılar yapım sırasında konuşulacak.
- ✔ Çok seviyeli görünümler kapalı açılır; akış görünümü Üretim akışı ile aynı çizim bileşenini kullanır.
- ◻ Tek tablo, **her satır bir bağ** (bir arzın bir ihtiyaca verdiği miktar). Bugünkü `planning.Pegging`'e eklenecekler: malzeme, lokasyon, arz tarihi, ihtiyaç tarihi, `AllocationLevel`, `AllocationKey`, genelden mi, kök talep türü, seviye, üst bağ. "Sabit ya da manuel bağ" alanı kalkar.
- ◻ Pegging veritabanına yazılır (plan hesabına bağlı). Yeniden hesaplama: senaryo çalışınca, plan elle değiştirilip kaydedilince, pegging parametresi değişince. Ekran açılışında hesap yapılmaz.
- ◻ Kaba boyut tahmini 250 bin – 1 milyon satır / plan hesabı; Aşama 10'da ölçülecek.
- Mockup: `plans/7.15-mockups/pegging-sonuc.html`

## 7. Pegging raporu ve plan satırları

- ✔ **`PlannedOrder` genel kalır**, sahibe göre bölünmez.
- ✔ Üretimin kime gittiğini (sipariş, proje, müşteri) **pegging'den türeyen ayrı bir rapor** gösterir: **Pegging raporu.**
- ✔ Raporlar aşamasında konuşulacak; raporlar listesinde yoksa eklenecek. Müşterinin ERP'sine ne gideceği sorusu da bu raporla şekillenecek.

## 8. Model kısıtları

- ✔ Modele tek yeni boyut eklenir: **bakiye.** Her malzemede genel bakiye hep vardır; özel bakiye yalnız `MaterialAllocationRule`'da satır olan yerde açılır.
- ✔ **Kapasite ortaktır**; bakiye yalnız malzeme tarafını böler.
- ✔ Model yazılırken iki şeye bakılır: **"Özel alokasyon" parametresi** ve **`MaterialAllocationRule`.** Talebin kimliği ve arzın anahtarı veri olarak okunur. Model ürün ağacında yeniden yürümez.
- ✔ Parametre "Dikkate alma" ise tek bakiye (genel) vardır.
- ✔ Ayrıntı Aşama 10'da (motor) konuşulacak.
- ◻ Bakiye modelleme katmanında bir indeks (0 = genel); bakiye listesi senaryo başında bellekte kurulur; aktarım miktarları için yeni bir plan çıktı tablosu; çalışma logunda özel bakiye ve değişken sayıları; "budanmış" ile "her şey ayrı" modelin küçük örneklerde aynı sonucu verdiğini gösteren otomatik test.
- Deneme sonuçları (kesin değil, Aşama 10'da gerçek ölçek, kapasite, MILP ve sıralı hedeflerle tekrarlanacak): küçük örneklerde budanmış model tam modelle aynı sonucu verdi; 30 proje, 10.000 malzeme, 17 seviye, 12 dönemde model yaklaşık 1,3 kat büyüdü; tek havuz modeli ayrılmış arzları ihlal etti.

## 9. Sözleşme dosyalarına işlenirken değişecekler

- `IsCustomTracked` → `IsCustomAllocated` (bütün tablolar, arayüz, sözleşme). (K-198, uygulandı)
- Arzlara `AllocationLevel`, `AllocationKey`; ERP satır bayrakları sözleşmeden çıkar. (K-198, uygulandı)
- Yeni tablo `MaterialAllocationRule`. (K-199, uygulandı)
- `PlannedOrder`: `ProjectId` kalkar, alokasyon alanları eklenir. (K-198, uygulandı)
- `ProjectGroup` tablosu ve `TrackingRule` kalkar. (K-198, uygulandı)
- "Özel alokasyon" parametresi (Parametreler › Malzeme).
- "Full pegging yöntemi" parametresi.
- `planning.Pegging` yapısı; aktarım çıktısı.
- Model artık tek havuz değil: bakiye boyutu.
- Yeni ekran: Üretim akışı (K-200, uygulandı). Yeni rapor: Pegging raporu.
