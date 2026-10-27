#Requires -Version 5.1
<#
.SYNOPSIS
    Kurulum sonrası kontrol listesi (docs/10-kurulum.md · Kontrol). Yönetici PowerShell'de çalıştırılır.
.PARAMETER CheckOffline
    Makineden dışarıya bağlantı kurulamadığını da doğrular (yalnız test ortamında; dışarıya deneme bağlantısı açar).
.PARAMETER SkipRestartTest
    API sürecini öldürüp servisin kendini yeniden başlattığını denemez.
#>
[CmdletBinding()]
param(
    [string]$DataDir = (Join-Path $env:ProgramData 'Smartchain'),
    [switch]$CheckOffline,
    [switch]$SkipRestartTest
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'common.ps1')

$state = Read-InstallState -DataDir $DataDir
if (-not $state) { Write-Host "Kurulum kaydı bulunamadı: $DataDir\config\install-state.json" -ForegroundColor Red; exit 1 }
$InstallDir = $state.InstallDir
$BaseUrl = 'http://localhost:{0}' -f $state.HttpPort
$Python = Join-Path $InstallDir 'python\python.exe'
$results = New-Object System.Collections.ArrayList

function Test-Check([string]$Name, [scriptblock]$Block) {
    try {
        $detail = & $Block
        [void]$results.Add([pscustomobject]@{ Sonuç = 'GEÇTİ'; Kontrol = $Name; Ayrıntı = "$detail" })
    } catch {
        [void]$results.Add([pscustomobject]@{ Sonuç = 'KALDI'; Kontrol = $Name; Ayrıntı = $_.Exception.Message })
    }
}

foreach ($n in $script:ServiceNames) {
    Test-Check "Servis $n çalışıyor, açılışta başlıyor" {
        $svc = Get-CimInstance Win32_Service -Filter "Name='$n'"
        if (-not $svc) { throw 'servis yok' }
        if ($svc.State -ne 'Running') { throw "durum: $($svc.State)" }
        if ($svc.StartMode -ne 'Auto') { throw "başlangıç: $($svc.StartMode)" }
        "hesap $($svc.StartName)"
    }
}

Test-Check 'API yalnız 127.0.0.1:8000 dinliyor' {
    $listen = @(Get-NetTCPConnection -State Listen -LocalPort $state.ApiPort -ErrorAction SilentlyContinue)
    if (-not $listen) { throw "port $($state.ApiPort) dinlenmiyor" }
    $outside = @($listen | Where-Object { $_.LocalAddress -notin @('127.0.0.1', '::1') })
    if ($outside) { throw "dışarıya açık: $($outside.LocalAddress -join ', ')" }
    'yalnız yerel'
}

# Sağlık, WebSocket ve motor: IIS üzerinden, paketteki Python ile.
Test-Check 'Duman testi (sağlık, WebSocket, motor)' {
    $env:SMARTCHAIN_CONFIG = Join-Path $DataDir 'config\smartchain.env'
    Push-Location $InstallDir
    try {
        $r = Invoke-Native $Python @((Join-Path $InstallDir 'setup\smoke.py'), '--base-url', $BaseUrl) -AllowFailure
    } finally { Pop-Location }
    $r.Output | ForEach-Object { Write-Host "  $_" }
    if ($r.Code -ne 0) { throw (($r.Output | Where-Object { $_ -like 'KALDI*' }) -join ' | ') }
    "$(@($r.Output | Where-Object { $_ -like 'GEÇTİ*' }).Count) kontrol"
}

if (-not $SkipRestartTest) {
    Test-Check 'API süreci ölünce servis yeniden başlatıyor' {
        $wrapper = Get-CimInstance Win32_Service -Filter "Name='SmartchainApi'"
        $child = Get-CimInstance Win32_Process -Filter "ParentProcessId=$($wrapper.ProcessId)" |
            Where-Object { $_.Name -eq 'python.exe' } | Select-Object -First 1
        if (-not $child) { throw "API'nin Python süreci bulunamadı" }
        Stop-Process -Id $child.ProcessId -Force
        Start-Sleep -Seconds 2
        $health = Wait-ApiHealthy -BaseUrl $BaseUrl -TimeoutSeconds 90
        "yeniden ayakta (sürüm $($health.app_version))"
    }
}

Test-Check 'Ayar dosyası yetkileri (SID)' {
    $acl = Get-Acl -LiteralPath (Join-Path $DataDir 'config\smartchain.env')
    $sids = @($acl.Access | ForEach-Object { $_.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value })
    $expected = @($script:SidSystem, $script:SidAdministrators) + @($script:ServiceNames | ForEach-Object { Get-ServiceSid $_ })
    $extra = @($sids | Where-Object { $_ -notin $expected })
    if ($extra) { throw "beklenmeyen erişim: $($extra -join ', ')" }
    if ($acl.AreAccessRulesProtected -ne $true) { throw 'kalıtım açık' }
    "$(@($sids | Select-Object -Unique).Count) hesap"
}

if ($CheckOffline) {
    Test-Check 'Makine internete çıkamıyor (yalnız test)' {
        $client = New-Object Net.Sockets.TcpClient
        try {
            $task = $client.ConnectAsync('1.1.1.1', 443)
            if ($task.Wait(5000) -and $client.Connected) { throw 'dışarıya bağlantı kurulabildi' }
        } catch [AggregateException] { } finally { $client.Dispose() }
        'dışarıya bağlantı yok'
    }
}

$results | Format-Table -AutoSize -Wrap
$failedCount = @($results | Where-Object { $_.Sonuç -eq 'KALDI' }).Count
if ($failedCount) { Write-Host "$failedCount kontrol kaldı." -ForegroundColor Red; exit 1 }
Write-Host 'Bütün kontroller geçti.' -ForegroundColor Green
exit 0
