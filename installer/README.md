# installer

Kurulum iskeleti (adım 0.6). Kurallar ve adımlar: `docs/10-kurulum.md`. MSI ve paketin tamamı 11. aşamada.

| Dosya | Ne | Nerede çalışır |
|---|---|---|
| `build.ps1` | İnternetsiz paketi hazırlar: ön koşulları indirir ve SHA-256 doğrular, wheel'leri indirir, `dist\Smartchain-<sürüm>\` + zip + manifest | Geliştirme bilgisayarı (internetli; hiçbir şey kurmaz) |
| `install.ps1` | Tek komut kurulum; başarısız adımda geri alma | Hedef sunucu (yönetici) |
| `uninstall.ps1` | Kaldırma; `-RemoveData` ile veritabanı ve loglar da | Hedef sunucu |
| `verify.ps1` | Kurulum sonrası kontrol listesi | Hedef sunucu |
| `common.ps1` | Ortak işlevler (log, SID, yetki, manifest, şablon) | — |
| `setup_db.py` | Veritabanı adımı: bağlantı cümlesi, veritabanı, servis hesabı yetkileri, geçişler | Paketteki Python |
| `smoke.py` | Duman testi: IIS üzerinden sağlık ve WebSocket, deneme plan hesabı | Paketteki Python |
| `prereqs.json` | Ön koşulların adresi ve SHA-256'sı | — |
| `requirements-runtime.txt` | Pakete giren Python paketleri (test paketleri hariç) | — |
| `templates\` | WinSW servis tanımları, IIS `web.config`, `index.html` | — |
| `sql\ConfigurationFile.ini` | SQL Server instance'ını sessiz kurmak için örnek | Test sanal makinesi / müşteri |

Kurallar: `.ps1` dosyaları UTF-8 BOM ile kaydedilir; yetkiler yalnız SID ile verilir (`Set-SidAcl`); dış komutlar `Invoke-Native` ile çağrılır (Windows PowerShell 5.1'de stderr yönlendirmesi `Stop` altında hata fırlatır). `tests/test_installer.py` ve `tests/test_offline.py` bunları denetler.

```powershell
powershell -File installer\build.ps1              # paket (ilk kez: -UpdateHashes)
```
