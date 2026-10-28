#Requires -Version 5.1
<#
.SYNOPSIS
    İnternetsiz kurulum paketini hazırlar (K-72, docs/10-kurulum.md). Yalnız geliştirme bilgisayarında, internetle.
.DESCRIPTION
    Hiçbir şey kurmaz. Ön koşulları installer\cache'e indirir ve SHA-256'larını prereqs.json ile doğrular,
    çalışma zamanı wheel'lerini indirir, dist\Smartchain-<sürüm>\ klasörünü, manifest.json'u ve zip'i üretir.
.PARAMETER UpdateHashes
    prereqs.json'da boş olan SHA-256'ları indirilen dosyadan doldurur (ilk hazırlıkta; sonra commit edilir).
#>
[CmdletBinding()]
param([switch]$UpdateHashes, [switch]$NoZip)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'  # Invoke-WebRequest ilerleme çubuğu indirmeyi çok yavaşlatır
. (Join-Path $PSScriptRoot 'common.ps1')

$Root = Split-Path $PSScriptRoot -Parent
$Cache = Join-Path $PSScriptRoot 'cache'
$DevPython = Join-Path $Root '.venv\Scripts\python.exe'
$PrereqsFile = Join-Path $PSScriptRoot 'prereqs.json'

$version = [regex]::Match((Get-Content -LiteralPath (Join-Path $Root 'app\__init__.py') -Raw), '__version__ = "([^"]+)"').Groups[1].Value
if (-not $version) { throw 'Sürüm okunamadı (app\__init__.py).' }
$Dist = Join-Path $Root "dist\Smartchain-$version"
Write-Log "Smartchain $version paketi hazırlanıyor" 'STEP'
# Açık geliştirme sunucusu npm ci'yi yarıda bırakır (node_modules silinir); en başta dur.
Assert-NoWebDevServer -WebDir (Join-Path $Root 'app\web')

# --- Ön koşullar ---
New-Item -ItemType Directory -Force -Path $Cache | Out-Null
$prereqs = Get-Content -LiteralPath $PrereqsFile -Raw -Encoding UTF8 | ConvertFrom-Json
$changed = $false
foreach ($item in $prereqs.items) {
    $file = Join-Path $Cache $item.file
    if (-not (Test-Path -LiteralPath $file)) {
        Write-Log "indiriliyor: $($item.title)"
        Invoke-WebRequest -Uri $item.url -OutFile $file -UseBasicParsing
    }
    $hash = (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant()
    if (-not $item.sha256) {
        if (-not $UpdateHashes) { throw "$($item.file) için SHA-256 tanımlı değil. İlk hazırlıkta: build.ps1 -UpdateHashes" }
        $item.sha256 = $hash
        $changed = $true
        Write-Log "SHA-256 kaydedildi: $($item.file) $hash" 'WARN'
    } elseif ($item.sha256 -ne $hash) {
        throw "$($item.file) SHA-256 tutmuyor (beklenen $($item.sha256), gelen $hash). Adres yeni sürüme işaret ediyor olabilir; kontrol edip prereqs.json'u güncelleyin."
    }
}
if ($changed) {
    Write-Utf8NoBom -Path $PrereqsFile -Text (($prereqs | ConvertTo-Json -Depth 5) + "`n")
    Write-Log 'prereqs.json güncellendi; commit edin.' 'WARN'
}
Write-Log 'Ön koşullar doğrulandı' 'OK'

# --- Wheel'ler (yalnız çalışma zamanı, Windows x64, Python 3.13) ---
$wheels = Join-Path $Cache 'wheels'
New-Item -ItemType Directory -Force -Path $wheels | Out-Null
Invoke-Native $DevPython @('-m', 'pip', 'download', '--disable-pip-version-check', '--only-binary=:all:',
    '--platform', 'win_amd64', '--python-version', '3.13', '--implementation', 'cp',
    '-r', (Join-Path $PSScriptRoot 'requirements-runtime.txt'), '-d', $wheels) | Out-Null
Write-Log "Wheel'ler hazır: $(@(Get-ChildItem $wheels -Filter *.whl).Count) dosya" 'OK'

# --- Arayüz (K-81, K-83): derlenir, pakete web\ olarak girer ---
$WebSrc = Join-Path $Root 'app\web'
if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
    throw 'Arayüzü derlemek için Node.js (npm) gerekir; yalnız geliştirme bilgisayarında. Müşteride gerekmez.'
}
Push-Location $WebSrc
try {
    Invoke-Native 'npm.cmd' @('ci', '--no-audit', '--no-fund') | Out-Null
    Invoke-Native 'npm.cmd' @('run', 'build') | Out-Null
} finally { Pop-Location }
Write-Log "Arayüz derlendi: $(@(Get-ChildItem (Join-Path $WebSrc 'dist') -Recurse -File).Count) dosya" 'OK'

# --- Paket klasörü ---
if (Test-Path -LiteralPath $Dist) { Remove-Item -LiteralPath $Dist -Recurse -Force }
New-Item -ItemType Directory -Force -Path $Dist | Out-Null

function Copy-Tree([string]$From, [string]$To, [string[]]$ExcludeDirs = @()) {
    # __pycache__ ve derlenmiş dosyalar pakete girmez.
    $r = Invoke-Native 'robocopy.exe' (@($From, $To, '/E', '/NFL', '/NDL', '/NJH', '/NJS', '/NP',
        '/XD', '__pycache__') + $ExcludeDirs + @('/XF', '*.pyc', '*.pyo')) -AllowFailure
    if ($r.Code -ge 8) { throw "Kopyalanamadı: $From ($($r.Code)) $($r.Output -join ' ')" }
}

Copy-Tree (Join-Path $Root 'app') (Join-Path $Dist 'app') @($WebSrc)  # arayüz kaynağı değil, derlenmiş hâli
Copy-Tree (Join-Path $WebSrc 'dist') (Join-Path $Dist 'web')
New-Item -ItemType Directory -Force -Path (Join-Path $Dist 'db') | Out-Null
Copy-Item -LiteralPath (Join-Path $Root 'db\models.py'), (Join-Path $Root 'db\alembic.ini') -Destination (Join-Path $Dist 'db')
Copy-Tree (Join-Path $Root 'db\migrations') (Join-Path $Dist 'db\migrations')
Copy-Tree (Join-Path $Root 'db\sql') (Join-Path $Dist 'db\sql')
foreach ($f in 'install.ps1', 'uninstall.ps1', 'verify.ps1', 'common.ps1', 'setup_db.py', 'smoke.py',
               'requirements-runtime.txt', 'prereqs.json') {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $f) -Destination $Dist
}
Copy-Tree (Join-Path $PSScriptRoot 'templates') (Join-Path $Dist 'templates')
Copy-Tree (Join-Path $PSScriptRoot 'sql') (Join-Path $Dist 'sql')
Copy-Tree $wheels (Join-Path $Dist 'wheels')
New-Item -ItemType Directory -Force -Path (Join-Path $Dist 'prereqs') | Out-Null
foreach ($item in $prereqs.items) { Copy-Item -LiteralPath (Join-Path $Cache $item.file) -Destination (Join-Path $Dist 'prereqs') }

# --- Manifest: her dosyanın SHA-256'sı; kurulum başta doğrular ---
$files = [ordered]@{}
Get-ChildItem -LiteralPath $Dist -Recurse -File | Sort-Object FullName | ForEach-Object {
    $rel = $_.FullName.Substring($Dist.Length + 1) -replace '\\', '/'
    $files[$rel] = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
}
$manifest = [ordered]@{ product = 'Smartchain'; version = $version; built_at = (Get-Date).ToString('s'); files = $files }
Write-Utf8NoBom -Path (Join-Path $Dist 'manifest.json') -Text ($manifest | ConvertTo-Json -Depth 4)
$size = (Get-ChildItem -LiteralPath $Dist -Recurse -File | Measure-Object Length -Sum).Sum / 1MB
Write-Log ("Paket: {0} ({1} dosya, {2:N0} MB)" -f $Dist, $files.Count, $size) 'OK'

$problems = Get-PackageManifestProblems -Root $Dist
if ($problems.Count) { throw "Manifest doğrulanamadı: $($problems -join '; ')" }

if (-not $NoZip) {
    $zip = "$Dist.zip"
    if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force }
    Compress-Archive -Path (Join-Path $Dist '*') -DestinationPath $zip
    Write-Log "Zip: $zip" 'OK'
}
