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

### Beklenen plan çıktıları

v0'da yoktur. Beklenen plan 8.0'daki plan fikstürüdür (bu setin üzerine elle hazırlanır); 10.8'de gerçek motorun kabul testine dönüşür.

### Kapsam dışı

Faz 1 dışı konular (set-up, kalıp, fırın, raf ömrü kuralları, çoklu lokasyon). Talep tahmini üretilmez.

## Durum

| Parça | Durum |
|---|---|
| v0 tasarımı | karar verildi (K-78) |
| v0 üretici ve temiz hâl | 0.8 |
| Kirli hâl (entegrasyon Excel'i) | 0.8'de üretilir; ETL ile denenmesi Aşama 3–5 |
