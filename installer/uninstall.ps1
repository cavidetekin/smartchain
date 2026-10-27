#Requires -Version 5.1
<#
.SYNOPSIS
    Smartchain'i kaldırır (docs/10-kurulum.md). Yönetici PowerShell'de çalıştırılır.
.DESCRIPTION
    Servisler, IIS sitesi, uygulama klasörü ve ürüne ait Python kaldırılır. Veritabanı, ayarlar ve loglar
    yalnız -RemoveData ile silinir. Ortak ön koşullar (VC++, ODBC, URL Rewrite, ARR, IIS) kalır.
#>
[CmdletBinding()]
param(
    [string]$DataDir = (Join-Path $env:ProgramData 'Smartchain'),
    [switch]$RemoveData
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'common.ps1')

$state = Read-InstallState -DataDir $DataDir
if (-not $state) { Write-Log "Kurulum kaydı bulunamadı: $DataDir\config\install-state.json" 'ERROR'; exit 1 }
if (-not (Test-IsAdmin)) { Write-Log 'Yönetici olarak çalıştırılmalı.' 'ERROR'; exit 1 }

$InstallDir = $state.InstallDir
$AppCmd = Join-Path $env:windir 'System32\inetsrv\appcmd.exe'
$SiteName = 'Smartchain'
$Python = Join-Path $InstallDir 'python\python.exe'
$SetupDir = Join-Path $InstallDir 'setup'
$failed = $false

function Invoke-Safely([string]$Name, [scriptblock]$Block) {
    # Kaldırma her adımı dener; biri başarısız olsa da diğerlerine geçer.
    Write-Log "== $Name" 'STEP'
    try { & $Block } catch { $script:failed = $true; Write-Log "$Name başarısız: $($_.Exception.Message)" 'ERROR' }
}

Start-InstallLog -LogDir (Join-Path $DataDir 'logs') -Prefix 'uninstall' | Out-Null

Invoke-Safely 'Servisler' {
    foreach ($n in $script:ServiceNames) {
        $svc = Get-Service -Name $n -ErrorAction SilentlyContinue
        if (-not $svc) { continue }
        if ($svc.Status -ne 'Stopped') { Stop-Service -Name $n -Force; $svc.WaitForStatus('Stopped', '00:01:00') }
        $wrapper = Join-Path $InstallDir "services\$n.exe"
        if (Test-Path -LiteralPath $wrapper) { Invoke-Native $wrapper @('uninstall') | Out-Null }
        else { Invoke-Native 'sc.exe' @('delete', $n) | Out-Null }
        Write-Log "kaldırıldı: $n" 'OK'
    }
}

Invoke-Safely 'IIS sitesi' {
    if (Test-Path -LiteralPath $AppCmd) {
        if ((Invoke-Native $AppCmd @('list', 'site', "/name:$SiteName") -AllowFailure).Output) {
            Invoke-Native $AppCmd @('delete', 'site', $SiteName) | Out-Null
        }
        if ((Invoke-Native $AppCmd @('list', 'apppool', "/name:$SiteName") -AllowFailure).Output) {
            Invoke-Native $AppCmd @('delete', 'apppool', $SiteName) | Out-Null
        }
        if ($state.Https) { Invoke-Native 'netsh.exe' @('http', 'delete', 'sslcert', 'ipport=0.0.0.0:443') -AllowFailure | Out-Null }
        if ($state.StoppedDefaultSite) {
            Invoke-Native $AppCmd @('set', 'site', 'Default Web Site', '/serverAutoStart:true') -AllowFailure | Out-Null
            Invoke-Native $AppCmd @('start', 'site', 'Default Web Site') -AllowFailure | Out-Null
            Write-Log 'Default Web Site yeniden başlatıldı'
        }
        Write-Log 'IIS sitesi kaldırıldı' 'OK'
    }
}

if ($RemoveData) {
    Invoke-Safely 'Veritabanı' {
        # Bağlantı bilgisi kurulum kaydından; Windows kimliğiyle (yöneticinin) bağlanılır.
        # SQL kimliğiyle kurulduysa şifre SMARTCHAIN_INSTALL_SQL_PASSWORD ortam değişkeninde verilmelidir.
        $a = @((Join-Path $SetupDir 'setup_db.py'), 'drop', '--instance', $state.SqlInstance, '--database', $state.Database,
            '--encrypt', $state.SqlEncrypt)
        if ($state.SqlTrustServerCertificate) { $a += '--trust-server-certificate' }
        if ($state.SqlUser) { $a += @('--sql-user', $state.SqlUser) }
        Invoke-Native $Python $a | Out-Null
        Write-Log "Veritabanı silindi: $($state.Database)" 'OK'
    }
}

Invoke-Safely 'Python' {
    $installer = Get-ChildItem -LiteralPath $SetupDir -Filter 'python-*-amd64.exe' -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($installer -and (Test-Path -LiteralPath $Python)) {
        Invoke-Exe $installer.FullName @('/uninstall', '/quiet') | Out-Null
        Write-Log 'Python kaldırıldı' 'OK'
    }
}

Invoke-Safely 'Uygulama klasörü' {
    if (Test-Path -LiteralPath $InstallDir) {
        # Bu betik setup klasöründen çalışıyor olabilir: dosyalar silinir, kilitli kalan klasör yeniden başlatmada gider.
        Get-ChildItem -LiteralPath $InstallDir -Force | Where-Object { $_.FullName -ne $SetupDir } |
            Remove-Item -Recurse -Force
        Remove-Item -LiteralPath $SetupDir -Recurse -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $InstallDir -Recurse -Force -ErrorAction SilentlyContinue
        Write-Log "Kaldırıldı: $InstallDir" 'OK'
    }
}

if ($RemoveData) {
    Invoke-Safely 'Ayarlar ve loglar' {
        $script:LogFile = $null
        Remove-Item -LiteralPath $DataDir -Recurse -Force
        Write-Host "Kaldırıldı: $DataDir"
    }
} else {
    Write-Log "Veritabanı, ayarlar ve loglar korundu ($DataDir). Silmek için: -RemoveData"
}

if ($failed) { Write-Host 'Kaldırma bazı adımlarda hata verdi; yukarıya bakın.' -ForegroundColor Red; exit 1 }
Write-Host 'Smartchain kaldırıldı.' -ForegroundColor Green
exit 0
