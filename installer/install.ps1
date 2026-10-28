#Requires -Version 5.1
<#
.SYNOPSIS
    Smartchain kurulumu (docs/10-kurulum.md; K-72…K-75). Yönetici PowerShell'de, paket klasöründen çalıştırılır.
.DESCRIPTION
    İnternetsiz: her şey paketin içindedir. Adımlar tekrar çalıştırılabilir; bir adım başarısız olursa
    yapılanlar geri alınır (ön koşullar ve veritabanı yerinde kalır). Ayrıntı: C:\ProgramData\Smartchain\logs\install-*.log
.EXAMPLE
    .\install.ps1 -SqlInstance ".\SMARTCHAIN" -SqlTrustServerCertificate
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$SqlInstance,
    [string]$Database = 'Smartchain',
    [string]$SqlUser = '',
    [string]$SqlPassword = '',
    [ValidateSet('yes', 'no', 'strict')][string]$SqlEncrypt = 'yes',
    [switch]$SqlTrustServerCertificate,
    [int]$HttpPort = 80,
    [string]$CertThumbprint = '',
    [string]$InstallDir = (Join-Path $env:ProgramFiles 'Smartchain'),
    [string]$DataDir = (Join-Path $env:ProgramData 'Smartchain'),
    [int]$ApiPort = 8000
)

$ErrorActionPreference = 'Stop'
$Package = $PSScriptRoot
. (Join-Path $Package 'common.ps1')

$ConfigDir = Join-Path $DataDir 'config'
$LogDir = Join-Path $DataDir 'logs'
$ExportDir = Join-Path $DataDir 'exports'   # arka planda hazırlanan Excel dosyaları (K-93)
$ConfigFile = Join-Path $ConfigDir 'smartchain.env'
$Python = Join-Path $InstallDir 'python\python.exe'
$SetupDir = Join-Path $InstallDir 'setup'
$WebDir = Join-Path $InstallDir 'web'
$ServicesDir = Join-Path $InstallDir 'services'
$AppCmd = Join-Path $env:windir 'System32\inetsrv\appcmd.exe'
$SiteName = 'Smartchain'
$ServiceSids = @{}
foreach ($n in $script:ServiceNames) { $ServiceSids[$n] = Get-ServiceSid -Name $n }

$undo = New-Object System.Collections.Stack
$state = [ordered]@{ InstallDir = $InstallDir; DataDir = $DataDir; HttpPort = $HttpPort; ApiPort = $ApiPort;
    SqlInstance = $SqlInstance; Database = $Database; SqlEncrypt = $SqlEncrypt
    SqlTrustServerCertificate = [bool]$SqlTrustServerCertificate; SqlUser = $SqlUser
    StoppedDefaultSite = $false; Https = [bool]$CertThumbprint }

function Invoke-Step {
    param([string]$Name, [scriptblock]$Do, [scriptblock]$Undo)
    Write-Log "== $Name" 'STEP'
    & $Do
    if ($Undo) { $undo.Push(@{ Name = $Name; Block = $Undo }) }
}

function Get-Prereq([string]$Name) {
    $item = $script:Prereqs | Where-Object { $_.name -eq $Name }
    $path = Join-Path $Package ('prereqs\' + $item.file)
    if (-not (Test-Path -LiteralPath $path)) { throw "Pakette ön koşul yok: $($item.file)" }
    return $path
}

function Invoke-Python {
    param([string[]]$Arguments)
    & $Python @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Python komutu başarısız ($LASTEXITCODE): $($Arguments -join ' ')" }
}

function Get-DbArguments {
    $a = @('--instance', $SqlInstance, '--database', $Database, '--encrypt', $SqlEncrypt)
    if ($SqlTrustServerCertificate) { $a += '--trust-server-certificate' }
    if ($SqlUser) { $a += @('--sql-user', $SqlUser) }
    return $a
}

function Remove-SmartchainServices {
    foreach ($n in $script:ServiceNames) {
        $svc = Get-Service -Name $n -ErrorAction SilentlyContinue
        if (-not $svc) { continue }
        if ($svc.Status -ne 'Stopped') { Stop-Service -Name $n -Force; $svc.WaitForStatus('Stopped', '00:01:00') }
        $wrapper = Join-Path $ServicesDir "$n.exe"
        if (Test-Path -LiteralPath $wrapper) { Invoke-Native $wrapper @('uninstall') -AllowFailure | Out-Null }
        else { Invoke-Native 'sc.exe' @('delete', $n) -AllowFailure | Out-Null }
        Write-Log "servis kaldırıldı: $n"
    }
}

function Get-IisSites {
    [xml]$xml = (Invoke-Native $AppCmd @('list', 'site', '/xml')).Output -join "`n"
    return @($xml.appcmd.SITE | Where-Object { $_ })
}

function Remove-IisSite {
    if ((Invoke-Native $AppCmd @('list', 'site', "/name:$SiteName") -AllowFailure).Output) {
        Invoke-Native $AppCmd @('delete', 'site', $SiteName) | Out-Null
    }
    if ((Invoke-Native $AppCmd @('list', 'apppool', "/name:$SiteName") -AllowFailure).Output) {
        Invoke-Native $AppCmd @('delete', 'apppool', $SiteName) | Out-Null
    }
}

try {
    New-Item -ItemType Directory -Force -Path $ConfigDir, $LogDir, $ExportDir | Out-Null
    $log = Start-InstallLog -LogDir $LogDir -Prefix 'install'
    $env:SMARTCHAIN_INSTALL_SQL_PASSWORD = $SqlPassword

    # --- 1 · Ön kontrol ---
    Invoke-Step 'Ön kontrol' {
        if (-not (Test-IsAdmin)) { throw 'Kurulum yönetici olarak çalıştırılmalı (Yönetici PowerShell).' }
        $os = Get-CimInstance Win32_OperatingSystem
        Write-Log "İşletim sistemi: $($os.Caption) $($os.Version)"
        if (-not (Test-IsWindowsServer)) { Write-Log 'Windows Server değil; yalnız test için kabul edilir.' 'WARN' }
        $drive = Get-PSDrive -Name ($InstallDir.Substring(0, 1))
        if ($drive.Free -lt 2GB) { throw "Kurulum diski için en az 2 GB boş alan gerekir ($($drive.Name):)." }
        $problems = Get-PackageManifestProblems -Root $Package
        if ($problems.Count) { throw ("Paket bozuk ya da eksik: " + ($problems -join '; ')) }
        $manifest = Get-Content -LiteralPath (Join-Path $Package 'manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
        $script:Version = $manifest.version
        $state.Version = $manifest.version
        $script:Prereqs = (Get-Content -LiteralPath (Join-Path $Package 'prereqs.json') -Raw -Encoding UTF8 | ConvertFrom-Json).items
        Write-Log "Paket sağlam: Smartchain $($manifest.version), $(@($manifest.files.PSObject.Properties).Count) dosya" 'OK'
        # SQL Server belleği (K-94): sınırsızsa ya da %80'in üstündeyse uyarı; kurulumu durdurmaz.
        Test-SqlServerMemory -Instance $SqlInstance -Encrypt $SqlEncrypt -TrustServerCertificate:$SqlTrustServerCertificate `
            -User $SqlUser -Password $SqlPassword | Out-Null
    }

    # --- 2 · Ön koşullar (kuruluysa atlanır; geri alınmaz: ortak bileşen) ---
    Invoke-Step 'Ön koşullar: IIS' {
        if (Test-IsWindowsServer) {
            $r = Install-WindowsFeature -Name Web-Server, Web-Default-Doc, Web-Static-Content, Web-Http-Errors, Web-WebSockets, Web-Mgmt-Console
            if (-not $r.Success) { throw 'IIS rolü kurulamadı.' }
        } else {
            Enable-WindowsOptionalFeature -Online -All -NoRestart -FeatureName IIS-WebServerRole, IIS-WebServer, IIS-DefaultDocument, IIS-StaticContent, IIS-HttpErrors, IIS-WebSockets, IIS-ManagementConsole | Out-Null
        }
        Write-Log 'IIS ve WebSocket özelliği açık' 'OK'
    }
    Invoke-Step 'Ön koşullar: VC++, ODBC 18, URL Rewrite, ARR' {
        $vc = Get-ItemProperty -Path 'HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64' -ErrorAction SilentlyContinue
        if (-not ($vc -and $vc.Installed -eq 1)) {
            Invoke-Exe (Get-Prereq 'vcredist') @('/install', '/quiet', '/norestart') -OkCodes 0, 1638, 3010 | Out-Null
        } else { Write-Log 'VC++ kurulu' }
        if (-not (Get-OdbcDriver -Name 'ODBC Driver 18 for SQL Server' -Platform '64-bit' -ErrorAction SilentlyContinue)) {
            Invoke-Exe 'msiexec.exe' @('/i', ('"{0}"' -f (Get-Prereq 'odbc18')), '/qn', '/norestart', 'IACCEPTMSODBCSQLLICENSETERMS=YES',
                '/l*v', ('"{0}"' -f (Join-Path $LogDir 'msodbcsql.log'))) -OkCodes 0, 3010 | Out-Null
        } else { Write-Log 'ODBC Driver 18 kurulu' }
        if (-not (Test-Path (Join-Path $env:windir 'System32\inetsrv\rewrite.dll'))) {
            Invoke-Exe 'msiexec.exe' @('/i', ('"{0}"' -f (Get-Prereq 'urlrewrite')), '/qn', '/norestart',
                '/l*v', ('"{0}"' -f (Join-Path $LogDir 'urlrewrite.log'))) -OkCodes 0, 3010 | Out-Null
        } else { Write-Log 'URL Rewrite kurulu' }
        if (-not (Test-Path (Join-Path $env:ProgramFiles 'IIS\Application Request Routing\requestRouter.dll'))) {
            Invoke-Exe 'msiexec.exe' @('/i', ('"{0}"' -f (Get-Prereq 'arr')), '/qn', '/norestart',
                '/l*v', ('"{0}"' -f (Join-Path $LogDir 'arr.log'))) -OkCodes 0, 3010 | Out-Null
        } else { Write-Log 'ARR kurulu' }
        Write-Log 'Ön koşullar tamam' 'OK'
    }

    # --- 3 · Python ve paketler ---
    Invoke-Step 'Python ve paketler' {
        Remove-SmartchainServices  # yeniden kurulumda dosyalar kilitli olmasın
        if (-not (Test-Path -LiteralPath $Python)) {
            Invoke-Exe (Get-Prereq 'python') @('/quiet', 'InstallAllUsers=1', ('TargetDir="{0}"' -f (Join-Path $InstallDir 'python')),
                'PrependPath=0', 'Include_launcher=0', 'InstallLauncherAllUsers=0', 'Include_test=0', 'Include_doc=0',
                'Include_tcltk=0', 'Include_dev=0', 'Shortcuts=0', 'AssociateFiles=0', 'Include_pip=1') | Out-Null
            if (-not (Test-Path -LiteralPath $Python)) {
                throw "Python $InstallDir\python'a kurulamadı. Bu Python sürümü makinede başka bir klasörde kurulu olabilir."
            }
        } else { Write-Log 'Python kurulu' }
        Invoke-Python @('-m', 'pip', 'install', '--no-index', '--disable-pip-version-check', '--find-links',
            (Join-Path $Package 'wheels'), '-r', (Join-Path $Package 'requirements-runtime.txt'))
        Write-Log 'Python paketleri kuruldu (internetsiz)' 'OK'
    }

    # --- 4 · Uygulama ve ayarlar ---
    $fresh = -not (Test-Path -LiteralPath (Join-Path $InstallDir 'app'))
    Invoke-Step 'Uygulama ve ayarlar' {
        foreach ($dir in 'app', 'db') {
            $target = Join-Path $InstallDir $dir
            if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Recurse -Force }
            Copy-Item -LiteralPath (Join-Path $Package $dir) -Destination $target -Recurse
        }
        New-Item -ItemType Directory -Force -Path $SetupDir, $WebDir, $ServicesDir | Out-Null
        foreach ($f in 'common.ps1', 'uninstall.ps1', 'verify.ps1', 'setup_db.py', 'smoke.py', 'manifest.json', 'prereqs.json') {
            Copy-Item -LiteralPath (Join-Path $Package $f) -Destination $SetupDir -Force
        }
        Copy-Item -LiteralPath (Get-Prereq 'python') -Destination $SetupDir -Force  # kaldırmada gerekir
        Copy-Item -LiteralPath (Get-Prereq 'winsw') -Destination $SetupDir -Force

        $url = (& $Python (Join-Path $Package 'setup_db.py') url @(Get-DbArguments))
        if ($LASTEXITCODE -ne 0 -or -not $url) { throw 'Bağlantı cümlesi kurulamadı.' }
        $lines = @(
            '# Smartchain ayarları (install.ps1 yazdı; docs/10-kurulum.md). Yalnız SYSTEM, yönetici grubu ve servis hesapları okur.',
            "SMARTCHAIN_DB_URL=$url",
            "SMARTCHAIN_LOG_DIR=$LogDir",
            "SMARTCHAIN_EXPORT_DIR=$ExportDir",
            'SMARTCHAIN_LOG_LEVEL=INFO',
            'SMARTCHAIN_ENABLE_DOCS=false',
            'SMARTCHAIN_JOB_WATCH_SECONDS=1.0'
        )
        Write-Utf8NoBom -Path $ConfigFile -Text (($lines -join "`r`n") + "`r`n")
        Write-Log "Ayarlar yazıldı: $ConfigFile" 'OK'
    } {
        if ($fresh) {
            foreach ($dir in 'app', 'db', 'web', 'services') {
                $p = Join-Path $InstallDir $dir
                if (Test-Path -LiteralPath $p) { Remove-Item -LiteralPath $p -Recurse -Force }
            }
        }
    }

    # --- 5 · Servisler (kurulur, henüz başlatılmaz) ---
    Invoke-Step 'Windows servisleri' {
        $values = @{ PYTHON = $Python; INSTALL_DIR = $InstallDir; CONFIG_FILE = $ConfigFile; LOG_DIR = $LogDir; API_PORT = $ApiPort }
        foreach ($n in $script:ServiceNames) {
            $wrapper = Join-Path $ServicesDir "$n.exe"
            Copy-Item -LiteralPath (Get-Prereq 'winsw') -Destination $wrapper -Force
            Write-Utf8NoBom -Path (Join-Path $ServicesDir "$n.xml") -Text (Expand-Template -Path (Join-Path $Package "templates\$n.xml") -Values $values -Xml)
            Invoke-Native $wrapper @('install') | Out-Null
            # Sanal servis hesabı; ad SID'den bu makinenin dilinde çözülür.
            $account = Resolve-SidName -Sid $ServiceSids[$n]
            Invoke-Native 'sc.exe' @('config', $n, 'obj=', $account) | Out-Null
            # WinSW'nin kendisi çökerse de Windows yeniden başlatsın.
            Invoke-Native 'sc.exe' @('failure', $n, 'reset=', '3600', 'actions=', 'restart/5000/restart/30000/restart/60000') | Out-Null
            Write-Log "servis kuruldu: $n ($account)" 'OK'
        }
        # Yetkiler SID ile (K-73): ayarlar yalnız okunur, loglar yazılır; Excel dosyalarını motor yazar, API okur (K-93).
        $services = @($ServiceSids.Values)
        Set-SidAcl -Path $ConfigDir -FullSids $script:SidSystem, $script:SidAdministrators -ReadSids $services
        Set-SidAcl -Path $ConfigFile -FullSids $script:SidSystem, $script:SidAdministrators -ReadSids $services
        Set-SidAcl -Path $LogDir -FullSids $script:SidSystem, $script:SidAdministrators -ModifySids $services
        Set-SidAcl -Path $ExportDir -FullSids $script:SidSystem, $script:SidAdministrators `
            -ModifySids $ServiceSids['SmartchainEngine'] -ReadSids $ServiceSids['SmartchainApi']
        Write-Log 'Ayar, log ve dışa aktarım klasörü yetkileri verildi (SID)' 'OK'
    } { Remove-SmartchainServices }

    # --- 6 · Veritabanı (geri alınmaz: veri korunur) ---
    Invoke-Step 'Veritabanı' {
        $a = @((Join-Path $Package 'setup_db.py'), 'setup') + (Get-DbArguments) + @('--root', $InstallDir)
        foreach ($sid in $ServiceSids.Values) { $a += @('--service-sid', $sid) }
        Invoke-Python $a
        Write-Log "Veritabanı hazır: $SqlInstance / $Database" 'OK'
    }

    # --- 7 · Servisleri başlat ---
    Invoke-Step 'Servisleri başlat' {
        foreach ($n in $script:ServiceNames) {
            Start-Service -Name $n
            (Get-Service -Name $n).WaitForStatus('Running', '00:01:00')
            Write-Log "çalışıyor: $n" 'OK'
        }
    } { foreach ($n in $script:ServiceNames) { Stop-Service -Name $n -Force -ErrorAction SilentlyContinue } }

    # --- 8 · IIS sitesi ---
    Invoke-Step 'IIS sitesi ve ters vekil' {
        $values = @{ API_PORT = $ApiPort; VERSION = $script:Version }
        Write-Utf8NoBom -Path (Join-Path $WebDir 'web.config') -Text (Expand-Template -Path (Join-Path $Package 'templates\web.config') -Values $values -Xml)
        # Derlenmiş arayüz (K-81): paketteki web\ kopyalanır; yoksa yer tutucu sayfa.
        Get-ChildItem -LiteralPath $WebDir -Force | Where-Object { $_.Name -ne 'web.config' } | Remove-Item -Recurse -Force
        if (Test-Path -LiteralPath (Join-Path $Package 'web\index.html')) {
            Copy-Item -Path (Join-Path $Package 'web\*') -Destination $WebDir -Recurse -Force
            Write-Log 'Arayüz dosyaları kopyalandı' 'OK'
        } else {
            Write-Utf8NoBom -Path (Join-Path $WebDir 'index.html') -Text (Expand-Template -Path (Join-Path $Package 'templates\index.html') -Values $values)
            Write-Log 'Pakette arayüz yok; yer tutucu sayfa yazıldı' 'WARN'
        }

        # ARR ters vekil sunucu düzeyinde açılır.
        Invoke-Native $AppCmd @('set', 'config', '-section:system.webServer/proxy', '/enabled:True', '/preserveHostHeader:True',
            '/reverseRewriteHostInResponseHeaders:False', '/commit:apphost') | Out-Null

        foreach ($site in Get-IisSites) {
            if ($site.'SITE.NAME' -eq $SiteName) { continue }
            if ($site.bindings -match (':{0}:' -f $HttpPort)) {
                if ($site.'SITE.NAME' -eq 'Default Web Site') {
                    Invoke-Native $AppCmd @('stop', 'site', 'Default Web Site') -AllowFailure | Out-Null
                    Invoke-Native $AppCmd @('set', 'site', 'Default Web Site', '/serverAutoStart:false') | Out-Null
                    $state.StoppedDefaultSite = $true
                    Write-Log "Default Web Site durduruldu (port $HttpPort); kaldırmada yeniden başlatılır" 'WARN'
                } else { throw "Port $HttpPort '$($site.'SITE.NAME')' sitesinde kullanılıyor." }
            }
        }
        Remove-IisSite
        Invoke-Native $AppCmd @('add', 'apppool', "/name:$SiteName", '/managedRuntimeVersion:', '/startMode:AlwaysRunning') | Out-Null
        Invoke-Native $AppCmd @('add', 'site', "/name:$SiteName", ('/bindings:http/*:{0}:' -f $HttpPort), "/physicalPath:$WebDir") | Out-Null
        Invoke-Native $AppCmd @('set', 'app', "$SiteName/", "/applicationPool:$SiteName") | Out-Null
        if ($CertThumbprint) {
            $cert = Get-Item -LiteralPath ('Cert:\LocalMachine\My\{0}' -f $CertThumbprint) -ErrorAction SilentlyContinue
            if (-not $cert) { throw "Sertifika bulunamadı: LocalMachine\My\$CertThumbprint" }
            Invoke-Native $AppCmd @('set', 'site', $SiteName, "/+bindings.[protocol='https',bindingInformation='*:443:']") | Out-Null
            Invoke-Native 'netsh.exe' @('http', 'delete', 'sslcert', 'ipport=0.0.0.0:443') -AllowFailure | Out-Null
            Invoke-Native 'netsh.exe' @('http', 'add', 'sslcert', 'ipport=0.0.0.0:443', "certhash=$CertThumbprint",
                'appid={6f2b3a50-9c1e-4c8e-9a52-5b3f0c7d1a11}') | Out-Null
            Write-Log 'HTTPS bağlantısı 443 portunda' 'OK'
        }
        Invoke-Native $AppCmd @('start', 'site', $SiteName) -AllowFailure | Out-Null
        Write-Log "IIS sitesi: $SiteName (port $HttpPort)" 'OK'
    } {
        Remove-IisSite
        if ($state.StoppedDefaultSite) {
            Invoke-Native $AppCmd @('set', 'site', 'Default Web Site', '/serverAutoStart:true') -AllowFailure | Out-Null
            Invoke-Native $AppCmd @('start', 'site', 'Default Web Site') -AllowFailure | Out-Null
        }
    }

    # --- 9 · Sağlık kontrolü (IIS üzerinden) ---
    Invoke-Step 'Sağlık kontrolü' {
        $health = Wait-ApiHealthy -BaseUrl ("http://localhost:{0}" -f $HttpPort)
        Write-Log ("Sağlık ok: sürüm {0}, şema {1}" -f $health.app_version, $health.database.schema_version) 'OK'
    }

    $state.InstalledAt = (Get-Date).ToString('s')
    Write-Utf8NoBom -Path (Join-Path $ConfigDir 'install-state.json') -Text ($state | ConvertTo-Json)
    Write-Log "Smartchain $($script:Version) kuruldu. Adres: http://localhost:$HttpPort  ·  Kontrol: $SetupDir\verify.ps1" 'OK'
    Write-Log "Log: $log"
    exit 0
} catch {
    Write-Log "HATA: $($_.Exception.Message)" 'ERROR'
    Write-Log ($_.ScriptStackTrace) 'ERROR'
    while ($undo.Count -gt 0) {
        $u = $undo.Pop()
        try { Write-Log "geri al: $($u.Name)" 'WARN'; & $u.Block } catch { Write-Log "geri alınamadı ($($u.Name)): $($_.Exception.Message)" 'WARN' }
    }
    Write-Log 'Kurulum tamamlanamadı; ön koşullar ve veritabanı yerinde bırakıldı. Ayrıntı log dosyasında.' 'ERROR'
    exit 1
} finally {
    Remove-Item Env:\SMARTCHAIN_INSTALL_SQL_PASSWORD -ErrorAction SilentlyContinue
}
