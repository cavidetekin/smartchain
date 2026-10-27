# Smartchain kurulum ortak işlevleri (docs/10-kurulum.md). UTF-8 BOM ile kaydedilir (Windows PowerShell 5.1).
Set-StrictMode -Version 2.0

# İyi bilinen SID'ler. Grup adı kullanılmaz: Türkçe Windows'ta "Administrators" = "Yöneticiler" (K-73).
$script:SidAdministrators = 'S-1-5-32-544'
$script:SidSystem = 'S-1-5-18'
$script:ServiceNames = @('SmartchainApi', 'SmartchainEngine')
$script:LogFile = $null

function Write-Log {
    param([string]$Message, [string]$Level = 'INFO')
    $line = '{0} {1,-5} {2}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Level, $Message
    $color = @{ 'INFO' = 'Gray'; 'OK' = 'Green'; 'WARN' = 'Yellow'; 'ERROR' = 'Red'; 'STEP' = 'Cyan' }[$Level]
    if (-not $color) { $color = 'Gray' }
    Write-Host $line -ForegroundColor $color
    if ($script:LogFile) { Add-Content -LiteralPath $script:LogFile -Value $line -Encoding UTF8 }
}

function Start-InstallLog {
    param([string]$LogDir, [string]$Prefix)
    New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
    $script:LogFile = Join-Path $LogDir ('{0}-{1}.log' -f $Prefix, (Get-Date -Format 'yyyyMMdd-HHmmss'))
    return $script:LogFile
}

function Test-IsAdmin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    return (New-Object Security.Principal.WindowsPrincipal($id)).IsInRole([Security.Principal.SecurityIdentifier]$script:SidAdministrators)
}

function Test-IsWindowsServer {
    return (Get-CimInstance Win32_OperatingSystem).ProductType -ne 1
}

function Get-VirtualAccountSid {
    # Sanal hesap SID'i: S-1-5-<yetki>-<SHA1(büyük harf adın UTF-16LE'si) beş adet little-endian DWORD>.
    # Servis hesabı (NT SERVICE\ad) için 80, IIS uygulama havuzu (IIS APPPOOL\ad) için 82.
    param([Parameter(Mandatory = $true)][string]$Name, [int]$Authority = 80)
    $sha = [System.Security.Cryptography.SHA1]::Create()
    try {
        $hash = $sha.ComputeHash([System.Text.Encoding]::Unicode.GetBytes($Name.ToUpperInvariant()))
    } finally { $sha.Dispose() }
    $parts = for ($i = 0; $i -lt 20; $i += 4) { [BitConverter]::ToUInt32($hash, $i) }
    return ('S-1-5-{0}-{1}' -f $Authority, ($parts -join '-'))
}

function Get-ServiceSid {
    param([Parameter(Mandatory = $true)][string]$Name)
    return Get-VirtualAccountSid -Name $Name -Authority 80
}

function Resolve-SidName {
    # SID'i bu makinenin dilindeki hesap adına çevirir (ör. sc.exe obj= için).
    param([Parameter(Mandatory = $true)][string]$Sid)
    return (New-Object Security.Principal.SecurityIdentifier($Sid)).Translate([Security.Principal.NTAccount]).Value
}

function Set-SidAcl {
    # Kalıtımı keser; yalnız verilen SID'lere yetki verir. Yetkiler yalnız burada ve yalnız SID ile verilir.
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [string[]]$FullSids = @(),
        [string[]]$ModifySids = @(),
        [string[]]$ReadSids = @()
    )
    $inherit = ''
    if ((Get-Item -LiteralPath $Path).PSIsContainer) { $inherit = '(OI)(CI)' }
    $arguments = @($Path, '/inheritance:r')
    foreach ($sid in $FullSids) { $arguments += @('/grant:r', ('*{0}:{1}F' -f $sid, $inherit)) }
    foreach ($sid in $ModifySids) { $arguments += @('/grant:r', ('*{0}:{1}M' -f $sid, $inherit)) }
    foreach ($sid in $ReadSids) { $arguments += @('/grant:r', ('*{0}:{1}RX' -f $sid, $inherit)) }
    $r = Invoke-Native -File 'icacls.exe' -Arguments $arguments -AllowFailure
    if ($r.Code -ne 0) { throw "Yetki verilemedi ($Path): $($r.Output -join ' ')" }
}

function Invoke-Native {
    # Dış komutu çalıştırır, stderr dahil çıktıyı toplar. Windows PowerShell 5.1'de 'Stop' altında stderr
    # yönlendirmesi hata fırlattığı için geçici olarak 'Continue'. -AllowFailure yoksa sıfır dışı kod hatadır.
    param([Parameter(Mandatory = $true)][string]$File, [string[]]$Arguments = @(), [switch]$AllowFailure)
    $old = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $out = @(& $File @Arguments 2>&1 | ForEach-Object { "$_" })
        $code = $LASTEXITCODE
    } finally { $ErrorActionPreference = $old }
    if ($code -ne 0 -and -not $AllowFailure) {
        throw ('{0} başarısız ({1}): {2}' -f [IO.Path]::GetFileName($File), $code, ($out -join ' '))
    }
    return [pscustomobject]@{ Code = $code; Output = $out }
}

function Invoke-Exe {
    # Dış programı çalıştırır; izin verilen çıkış kodları dışında hata fırlatır.
    param([Parameter(Mandatory = $true)][string]$File, [string[]]$Arguments = @(), [int[]]$OkCodes = @(0))
    Write-Log ('çalıştır: {0} {1}' -f [IO.Path]::GetFileName($File), ($Arguments -join ' '))
    if ($Arguments.Count) {
        $p = Start-Process -FilePath $File -ArgumentList $Arguments -Wait -PassThru -NoNewWindow
    } else {
        $p = Start-Process -FilePath $File -Wait -PassThru -NoNewWindow
    }
    if ($OkCodes -notcontains $p.ExitCode) {
        throw ('{0} çıkış kodu {1}' -f [IO.Path]::GetFileName($File), $p.ExitCode)
    }
    return $p.ExitCode
}

function Get-PackageManifestProblems {
    # manifest.json'daki her dosya var mı ve SHA-256'sı tutuyor mu; sorunların listesini döndürür (boşsa paket sağlam).
    param([Parameter(Mandatory = $true)][string]$Root)
    $manifestPath = Join-Path $Root 'manifest.json'
    if (-not (Test-Path -LiteralPath $manifestPath)) { return @('manifest.json yok') }
    $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $problems = @()
    foreach ($entry in $manifest.files.PSObject.Properties) {
        $file = Join-Path $Root ($entry.Name -replace '/', '\')
        if (-not (Test-Path -LiteralPath $file)) { $problems += "eksik: $($entry.Name)"; continue }
        $hash = (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($hash -ne $entry.Value) { $problems += "değişmiş: $($entry.Name)" }
    }
    return , $problems
}

function Expand-Template {
    # {{AD}} yer tutucularını doldurur. -Xml: değerler XML için kaçırılır.
    param([Parameter(Mandatory = $true)][string]$Path, [hashtable]$Values, [switch]$Xml)
    $text = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
    foreach ($key in $Values.Keys) {
        $value = [string]$Values[$key]
        if ($Xml) { $value = [Security.SecurityElement]::Escape($value) }
        $text = $text.Replace('{{' + $key + '}}', $value)
    }
    if ($text -match '\{\{[A-Z_]+\}\}') { throw "Doldurulmamış yer tutucu: $($Matches[0]) ($Path)" }
    return $text
}

function Write-Utf8NoBom {
    # .env ve XML dosyaları BOM'suz yazılır (python-dotenv ilk satırı BOM'la okumaz).
    param([Parameter(Mandatory = $true)][string]$Path, [Parameter(Mandatory = $true)][string]$Text)
    [IO.File]::WriteAllText($Path, $Text, (New-Object Text.UTF8Encoding($false)))
}

function Get-ApiHealth {
    # /api/health; 503 de gövdeyle döner. Bağlanılamazsa $null.
    param([Parameter(Mandatory = $true)][string]$BaseUrl)
    try {
        $r = Invoke-WebRequest -Uri "$BaseUrl/api/health" -UseBasicParsing -TimeoutSec 10
        return ($r.Content | ConvertFrom-Json)
    } catch [System.Net.WebException] {
        if ($_.Exception.Response) {
            $reader = New-Object IO.StreamReader($_.Exception.Response.GetResponseStream())
            try { return ($reader.ReadToEnd() | ConvertFrom-Json) } catch { return $null } finally { $reader.Dispose() }
        }
        return $null
    }
}

function Wait-ApiHealthy {
    param([Parameter(Mandatory = $true)][string]$BaseUrl, [int]$TimeoutSeconds = 90)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $last = $null
    while ((Get-Date) -lt $deadline) {
        $last = Get-ApiHealth -BaseUrl $BaseUrl
        if ($last -and $last.status -eq 'ok') { return $last }
        Start-Sleep -Seconds 3
    }
    if ($last) { throw ("Sağlık kontrolü geçmedi: {0}" -f $last.database.message) }
    throw "API'ye ulaşılamadı: $BaseUrl/api/health"
}

function Read-InstallState {
    param([Parameter(Mandatory = $true)][string]$DataDir)
    $path = Join-Path $DataDir 'config\install-state.json'
    if (-not (Test-Path -LiteralPath $path)) { return $null }
    return (Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json)
}
