# Kurulum

Adım 0.6'da kurulan iskelet. Kurulum paketinin tamamı (MSI, imza, kod koruması, sürüm güncelleme, yedek, lisans) 11. aşamadadır (MDD 27); MSI bu iskeleti sarar (K-50, K-72). Kod: `installer/`.

## İlkeler

- **İnternetsiz (K-72):** Paket her şeyi içerir; kurulum hiçbir adreste internete çıkmaz. Paket yalnız geliştirme bilgisayarında, bir kez internetle hazırlanır (`installer/build.ps1`). Ön koşulların adresi ve SHA-256'sı `installer/prereqs.json`'da sabittir. `build.ps1` arayüzü `npm ci` ile temiz kurup derler; `app\web`'de çalışan bir node süreci (ör. `npm run dev`'in vite'ı, vitest) varsa en başta durur ve süreçleri listeler: açık süreç dosyaları kilitlediği için `npm ci` node_modules'u yarıda silip bırakabilir.
- **Tek komut, yönetici:** `install.ps1`. Adımlar tekrar çalıştırılabilir; bir adım başarısız olursa yapılanlar geri alınır.
- **Servisler (K-73):** API ve motor iki Windows servisidir (WinSW). Sanal servis hesaplarıyla çalışırlar, açılışta başlarlar, çökünce kendilerini yeniden başlatırlar.
- **IIS ters vekil (K-74):** API yalnız `127.0.0.1:8000`'i dinler; dışarıya IIS açılır.
- **SQL Server müşteride (K-75):** Ürüne ayrılmış instance'ı müşteri kurar; kurulum veritabanını açar, yetkileri verir, geçişleri çalıştırır.
- **Yetkilerde SID:** Klasör ve dosya yetkileri SID ile verilir (Yöneticiler `S-1-5-32-544`, SYSTEM `S-1-5-18`, servis hesapları `S-1-5-80-…`). Türkçe Windows'ta grup adları farklıdır ("Administrators" = "Yöneticiler").
- **Betikler UTF-8 BOM:** Windows PowerShell 5.1 Türkçe karakterleri ancak BOM'lu dosyada doğru okur.

## Paket

`dist\Smartchain-<sürüm>\` (ve aynı adla `.zip`):

| Klasör / dosya | İçerik |
|---|---|
| `install.ps1`, `uninstall.ps1`, `verify.ps1`, `common.ps1` | Kurulum, kaldırma, kontrol |
| `setup_db.py`, `smoke.py` | Veritabanı adımı ve kurulum sonrası duman testi (paketteki Python ile çalışır) |
| `app\`, `db\` | Uygulama ve veritabanı geçişleri |
| `requirements-runtime.txt`, `wheels\` | Çalışma zamanı paketleri (test paketleri girmez) |
| `prereqs\` | Python 3.13 (amd64), VC++ yeniden dağıtılabilir, ODBC Driver 18, IIS URL Rewrite 2.1, IIS ARR 3.0, WinSW 2.12 |
| `web\` | Derlenmiş arayüz (`index.html`, `assets\`: JS, CSS, woff2); IIS köküne kopyalanır |
| `templates\` | WinSW servis tanımları, IIS `web.config`, yer tutucu `index.html` (arayüz yoksa) |
| `sql\ConfigurationFile.ini` | SQL Server instance'ını sessiz kurmak için örnek yanıt dosyası |
| `manifest.json` | Sürüm ve her dosyanın SHA-256'sı; kurulum başta doğrular |

## Hedef makinedeki düzen

| Yer | İçerik |
|---|---|
| `C:\Program Files\Smartchain\` | `python\` (ürüne ait Python), `app\`, `db\`, `services\` (WinSW ve XML), `web\` (IIS kökü) |
| `C:\ProgramData\Smartchain\config\smartchain.env` | Ayarlar: bağlantı, log klasörü, oturum çerezinin `Secure` bayrağı (`SMARTCHAIN_SESSION_COOKIE_SECURE`: `-CertThumbprint` verildiyse `true`, HTTPS'siz test kurulumunda `false`; K-97). Yalnız SYSTEM, Yöneticiler ve servis hesapları okur. |
| `C:\ProgramData\Smartchain\logs\` | `smartchain.log` (API), `engine.log` (motor), servis çıktıları, `install-<tarih>.log` |
| `C:\ProgramData\Smartchain\exports\` | Arka planda hazırlanan Excel dosyaları (`SMARTCHAIN_EXPORT_DIR`, K-93); motor servisi yazar (değiştirme yetkisi), API okur (okuma yetkisi; SID ile, K-73); süresi geçince motor servisi siler |

Servisler ayarları `SMARTCHAIN_CONFIG` ortam değişkeniyle verilen dosyadan okur. Ortam değişkeni dosyadaki değeri ezer.

## Ön koşullar (müşteri)

- Windows Server 2022 ya da 2025, yönetici hesabı. Test için Windows 11 de kabul edilir.
- Ürüne ayrılmış SQL Server instance'ı (en güncel sürüm). Önerilen collation `Latin1_General_100_CI_AS_SC`; veritabanı collation'ını kurulum zaten bununla açar. Kurulumu yapan kullanıcının instance'ta `sysadmin` olması gerekir (yalnız kurulum sırasında).
- **SQL Server belleği (K-94):** ürüne ayrılmış instance'ta `max server memory` mutlaka ayarlanır: sunucu belleğinin yaklaşık %50–70'i, işletim sistemine ve Smartchain süreçlerine (API, motor servisi, her iş için ayrı süreç) yer kalacak şekilde. `min server memory` bir taban verir: SQL Server bellek baskısında bu sınırın altına inmez. Sınırsız (varsayılan 2.147.483.647 MB) bırakılan instance, işletim sistemi "bellek az" bildirdikçe önbelleklerini atar; bir süre sonra oturum kabul etmez ve 802 ("insufficient memory available in the buffer pool") hatası verir. API'de bu durum havuz zaman aşımı ve 503 olarak görünür. Örnek değerler:

  | Sunucu belleği | max server memory | min server memory |
  |---|---|---|
  | 16 GB | 8192–11264 MB | 2048 MB |
  | 32 GB | 16384–22528 MB | 4096 MB |

  ```sql
  -- 16 GB sunucu
  EXEC sp_configure 'show advanced options', 1; RECONFIGURE;
  EXEC sp_configure 'min server memory (MB)', 2048;
  EXEC sp_configure 'max server memory (MB)', 10240;
  RECONFIGURE;
  ```

  Instance yeni kuruluyorsa aynı değerler kurulum yanıt dosyasında da verilebilir (`SQLMINMEMORY`, `SQLMAXMEMORY`).
- Güvenlik duvarı: kullanıcılara yalnız IIS portu (80 ya da 443). 8000 dışarıya açılmaz. SQL Server başka sunucudaysa Smartchain → SQL 1433.

## Kurulum

```powershell
# Yönetici PowerShell, paket klasöründe
.\install.ps1 -SqlInstance ".\SMARTCHAIN" -SqlTrustServerCertificate
.\verify.ps1
```

| Parametre | Varsayılan | Ne |
|---|---|---|
| `-SqlInstance` | (zorunlu) | `SUNUCU\INSTANCE` ya da `SUNUCU,PORT` |
| `-Database` | `Smartchain` | Veritabanı adı |
| `-SqlUser` / `-SqlPassword` | boş | SQL kimliği; boşsa Windows kimliği (servis hesapları) |
| `-SqlEncrypt` | açık | Bağlantı şifreli (ODBC Driver 18 varsayılanı). Kapatmak önerilmez. |
| `-SqlTrustServerCertificate` | kapalı | SQL Server'da güvenilir (müşteri CA'sının verdiği) sertifika yoksa açılır; bağlantı yine şifrelidir ama sunucu sertifikası doğrulanmaz. |
| `-HttpPort` | 80 | IIS portu (HTTP) |
| `-CertThumbprint` | boş | Verilirse 443'te HTTPS bağlantısı (sertifika `LocalMachine\My`'da, müşterinin iç CA'sından) |
| `-InstallDir` | `C:\Program Files\Smartchain` | Uygulama klasörü |

**SQL bağlantısında şifreleme:** ODBC Driver 18 bağlantıyı varsayılan olarak şifreler ve sunucu sertifikasını doğrular. Yeni kurulmuş bir SQL Server kendi imzaladığı sertifikayı kullanır; bu durumda doğrulama başarısız olur. İki yol var: müşterinin BT'si SQL Server'a güvenilir sertifika yükler (önerilen), ya da kurulum `-SqlTrustServerCertificate` ile yapılır. Ayar `smartchain.env`'deki bağlantı cümlesine (`Encrypt`, `TrustServerCertificate`) yazılır.

**Adımlar:**
1. Ön kontrol: yönetici, işletim sistemi, disk, paket bütünlüğü (manifest). SQL Server instance'ında `max server memory` sınırsızsa ya da sunucu belleğinin %80'inden fazlaysa **uyarı** verilir (K-94): neden ve önerilen değer yazılır, kurulum durmaz.
2. Ön koşullar paketten sessiz kurulur (kuruluysa atlanır). IIS ve WebSocket özelliği açılır.
3. Python ve paketler `C:\Program Files\Smartchain\python`'a kurulur (`pip --no-index`).
4. Uygulama kopyalanır, `smartchain.env` yazılır.
5. Servisler kurulur (henüz başlatılmaz).
6. Veritabanı: yoksa açılır, servis hesaplarına login ve kullanıcı açılır (şimdilik kendi veritabanında `db_owner`), geçişler çalışır.
7. Servisler başlatılır; IIS sitesi ve ters vekil kurulur.
8. Sağlık kontrolü IIS üzerinden yapılır (`/api/health`). Geçmezse 7 → 3 geri alınır (ön koşullar ve veritabanı yerinde kalır), neden yazılır.

**Arayüz:** `web.config` `/api` ve `/api/ws`'i API servisine yönlendirir; dosya olmayan diğer adresler `index.html`'e gider (tek sayfa uygulaması, adres yenilenince de çalışır); `.woff2` türü tanımlıdır.

IIS portunu "Default Web Site" kullanıyorsa o site durdurulur ve kaldırmada yeniden başlatılır. Başka bir site kullanıyorsa kurulum durur.

## Üçüncü taraf bileşenler ve lisansları

Pakete giren bütün bileşenler yeniden dağıtılabilir. Lisans metinlerinin pakete toplanması 11.4'te.

| Bileşen | Sürüm | Lisans |
|---|---|---|
| Python | 3.13.7 | PSF-2.0 |
| **HiGHS (highspy)** — çözücü | 1.15.1 | **MIT** |
| numpy (highspy bağımlılığı) | 2.5.4 | BSD-3-Clause (içinde 0BSD, MIT, Zlib, CC0-1.0 parçaları) |
| FastAPI, pydantic, pydantic-core, pydantic-settings, annotated-doc, annotated-types, typing-inspection | 0.162.0 · 2.14.1 · 2.50.1 · 2.16.1 · 0.0.5 · 0.8.0 · 0.4.4 | MIT |
| starlette, uvicorn, websockets, click, idna, python-dotenv, MarkupSafe | 1.10.0 · 0.54.0 · 17.3 · 8.5.0 · 3.20 · 1.2.4 · 3.0.4 | BSD-3-Clause |
| XlsxWriter (Excel'e aktarım, K-91) | 3.3.0 | BSD-2-Clause |
| argon2-cffi, argon2-cffi-bindings (şifre özeti, K-98) | 25.1.0 · 26.1.0 | MIT |
| cffi (argon2-cffi-bindings bağımlılığı) | 2.1.1 | MIT-0 |
| pycparser (cffi bağımlılığı) | 3.12 | BSD-3-Clause |
| SQLAlchemy, alembic, Mako, pyodbc, anyio, h11, httptools, watchfiles, PyYAML | 2.1.6 · 1.20.1 · 1.4.3 · 5.3.0 · 4.15.1 · 0.16.0 · 0.9.0 · 1.3.0 · 6.0.3 | MIT |
| typing_extensions | 4.16.0 | PSF-2.0 |
| opentelemetry-api | 1.45.1 | Apache-2.0 |
| WinSW (servis sarmalayıcı) | 2.12.0 | MIT |
| React, react-dom, react-router (arayüz) | 19.3 · 19.3 · 8.5 | MIT |
| Lucide ikonları (lucide-react) | 1.62 | ISC |
| TanStack Table, TanStack Virtual (@tanstack/react-table, @tanstack/react-virtual) | 9.3 · 3.14 | MIT |
| Instrument Sans, Inter (@fontsource) | 5.3 | OFL-1.1 |
| ODBC Driver 18 for SQL Server, Visual C++ yeniden dağıtılabilir, IIS URL Rewrite 2.1, IIS ARR 3.0 | — | Microsoft lisansları; yeniden dağıtım ürünle birlikte kurulum amacıyla |

## Kaldırma

`.\uninstall.ps1`: servisler, IIS sitesi ve uygulama klasörü kaldırılır. Veritabanı, ayarlar ve loglar yalnız `-RemoveData` ile silinir. Ön koşullar (Python dışında) ortak bileşen olduğu için kalır.

## Kontrol (`verify.ps1`)

- Servisler çalışıyor ve açılışta otomatik başlıyor.
- IIS üzerinden `/api/health` ok; WebSocket isteği IIS'ten API'ye ulaşıyor: oturumsuz el sıkışma API tarafından reddediliyor (403; oturum K-97). Kurulumda kullanıcı hesabı olmadığı için `hello` beklenmez; ilk hesap 2.3'te kurulumla açılır.
- Motor bir deneme plan hesabını bitiriyor (deneme verisi açılır ve silinir).
- Çözücü (HiGHS) pakette çalışıyor: sabit LP ve MILP modelleri bilinen sonuçla çözülüyor (K-76).
- API süreci öldürülünce servis kendini yeniden başlatıyor.
- `-CheckOffline`: makineden dışarıya bağlantı kurulamadığını doğrular (yalnız test ortamında).

## Temiz makine testi

Hyper-V'de Windows Server 2025 Evaluation sanal makinesi; SQL Server ayrı `SMARTCHAIN` instance'ı olarak (`sql\ConfigurationFile.ini`) kurulur, ağ kartı kapatılır, "Temiz" checkpoint alınır. Her denemede: checkpoint'e dön → paketi Gelişmiş Oturum ile kopyala → `install.ps1` → `verify.ps1` → yeniden başlat → `verify.ps1` → `uninstall.ps1`. Windows Sandbox kullanılmaz: Windows Server değildir ve her açılışta SQL Server'ın yeniden kurulması gerekir.

## Durum

| Parça | Durum |
|---|---|
| Paket hazırlama, kurulum, kaldırma, kontrol betikleri | uygulandı (0.6), sanal makine testi bekliyor |
| SQL Server bellek ön kontrolü (K-94; sınırsızsa ya da %80'in üstündeyse uyarı, kurulum durmaz) | uygulandı (1.5; `common.ps1` `Test-SqlServerMemory`, install.ps1 adım 1), sanal makine testi bekliyor (0.6) |
| Oturum: çerezin `Secure` ayarı (`-CertThumbprint`'e göre), WebSocket duman testi oturumsuz reddi bekler, argon2-cffi wheel'leri (K-97, K-98) | uygulandı (2.1), sanal makine testi bekliyor (0.6) |
| MSI, imza, kod koruması, sürüm güncelleme, yedek, lisans | 11. aşama |
