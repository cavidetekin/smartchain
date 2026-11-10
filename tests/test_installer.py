"""Kurulum iskeleti (0.6; K-72…K-75). Geliştirme bilgisayarında hiçbir şey kurmadan çalışır.

PowerShell gerektiren testler Windows PowerShell 5.1 ile (hedef sunucudaki sürüm) çalışır.
"""
import hashlib
import importlib.metadata as md
import importlib.util
import json
import os
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "installer"
PS1 = sorted(INSTALLER.glob("*.ps1"))
POWERSHELL = shutil.which("powershell.exe")
needs_ps = pytest.mark.skipif(POWERSHELL is None, reason="Windows PowerShell yok")

spec = importlib.util.spec_from_file_location("setup_db", INSTALLER / "setup_db.py")
setup_db = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup_db)


def ps(script: str) -> str:
    """common.ps1 yüklü Windows PowerShell 5.1'de betik çalıştırır, çıktıyı (UTF-8) döndürür."""
    cmd = ("[Console]::OutputEncoding = [Text.Encoding]::UTF8; $ErrorActionPreference = 'Stop'; "
           f". '{INSTALLER / 'common.ps1'}'; " + script)
    r = subprocess.run([POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", cmd],
                       capture_output=True, timeout=60)
    out, err = r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")
    assert r.returncode == 0, err or out
    return out.strip()


# --- Dosya kuralları ---

def test_ps1_files_are_utf8_with_bom():
    assert PS1, "installer/*.ps1 yok"
    missing = [p.name for p in PS1 if not p.read_bytes().startswith(b"\xef\xbb\xbf")]
    assert not missing, f"UTF-8 BOM'suz: {missing}"


@needs_ps
def test_ps1_files_parse_in_windows_powershell():
    files = ",".join(f"'{p}'" for p in PS1)
    out = ps(f"@({files}) | ForEach-Object {{ $t = $null; $e = $null; "
             "[void][Management.Automation.Language.Parser]::ParseFile($_, [ref]$t, [ref]$e); "
             "foreach ($x in $e) { '{0}:{1}: {2}' -f (Split-Path $_ -Leaf), $x.Extent.StartLineNumber, $x.Message } }")
    assert out == "", out


GROUP_NAMES = re.compile(r"(?<!Sid)Administrators|Yöneticiler|BUILTIN|Everyone|Herkes|NT AUTHORITY|IIS_IUSRS|\bUsers\b",
                         re.IGNORECASE)


def code_lines(path: Path):
    for n, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            yield n, line


def test_permissions_use_sids_not_group_names():
    problems = []
    for p in PS1:
        for n, line in code_lines(p):
            if GROUP_NAMES.search(line):
                problems.append(f"{p.name}:{n}: grup adı: {line.strip()}")
            if "icacls" in line.lower() and p.name != "common.ps1":
                problems.append(f"{p.name}:{n}: icacls yalnız Set-SidAcl'de kullanılır")
            if "/grant" in line and "*{0}:" not in line:
                problems.append(f"{p.name}:{n}: /grant SID biçiminde değil: {line.strip()}")
    assert not problems, "\n".join(problems)


# --- SID ---

def service_sid(name: str, authority: int = 80) -> str:
    h = hashlib.sha1(name.upper().encode("utf-16-le")).digest()
    return f"S-1-5-{authority}-" + "-".join(str(int.from_bytes(h[i:i + 4], "little")) for i in range(0, 20, 4))


def test_service_sid_algorithm_matches_windows():
    # NT SERVICE\TrustedInstaller'ın SID'i her Windows'ta aynıdır.
    assert service_sid("TrustedInstaller") == "S-1-5-80-956008885-3418522649-1831038044-1853292631-2271478464"


@needs_ps
def test_powershell_service_sid_matches():
    out = ps("Get-ServiceSid TrustedInstaller; Get-ServiceSid SmartchainApi; Get-ServiceSid SmartchainEngine")
    assert out.splitlines() == [service_sid("TrustedInstaller"), service_sid("SmartchainApi"),
                                service_sid("SmartchainEngine")]


def test_sid_to_bytes():
    assert setup_db.sid_to_bytes("S-1-5-18") == bytes([1, 1, 0, 0, 0, 0, 0, 5, 18, 0, 0, 0])
    b = setup_db.sid_to_bytes(service_sid("SmartchainApi"))
    assert b[:8] == bytes([1, 6, 0, 0, 0, 0, 0, 5]) and len(b) == 8 + 6 * 4
    with pytest.raises(ValueError):
        setup_db.sid_to_bytes("X-1-5")


# --- SQL bağlantısı (K-75): Encrypt ve TrustServerCertificate parametreden ---

def test_odbc_string_defaults_to_encrypted_and_verified():
    s = setup_db.odbc_string(r".\SMARTCHAIN", "Smartchain")
    assert "DRIVER={ODBC Driver 18 for SQL Server}" in s
    assert r"SERVER=.\SMARTCHAIN" in s and "DATABASE=Smartchain" in s
    assert "Encrypt=yes" in s and "TrustServerCertificate=no" in s and "Trusted_Connection=yes" in s


def test_odbc_string_trust_and_sql_login():
    s = setup_db.odbc_string("db01,1433", "Smartchain", encrypt="strict", trust_server_certificate=True,
                             sql_user="smartchain", sql_password="a;b}c")
    assert "Encrypt=strict" in s and "TrustServerCertificate=yes" in s
    assert "UID={smartchain}" in s and "PWD={a;b}}c}" in s and "Trusted_Connection" not in s
    with pytest.raises(ValueError):
        setup_db.odbc_string("x", "y", encrypt="maybe")


def test_url_command_output(capsys):
    setup_db.main(["url", "--instance", r".\SMARTCHAIN", "--trust-server-certificate"])
    url = capsys.readouterr().out.strip()
    assert url.startswith("mssql+pyodbc:///?odbc_connect=") and " " not in url
    assert "TrustServerCertificate%3Dyes" in url and "Encrypt%3Dyes" in url


# --- Şablonlar ---

def render(name: str, **values) -> str:
    text = (INSTALLER / "templates" / name).read_text(encoding="utf-8")
    for k, v in values.items():
        text = text.replace("{{" + k + "}}", str(v))
    assert not re.search(r"\{\{[A-Z_]+\}\}", text), "doldurulmamış yer tutucu"
    return text


SERVICE_VALUES = dict(PYTHON=r"C:\Program Files\Smartchain\python\python.exe", INSTALL_DIR=r"C:\Program Files\Smartchain",
                      CONFIG_FILE=r"C:\ProgramData\Smartchain\config\smartchain.env",
                      LOG_DIR=r"C:\ProgramData\Smartchain\logs", API_PORT=8000)


@pytest.mark.parametrize("name, module", [("SmartchainApi", "uvicorn app.api.main:app"),
                                          ("SmartchainEngine", "app.engine.service")])
def test_service_templates(name, module):
    root = ET.fromstring(render(f"{name}.xml", **SERVICE_VALUES))
    assert root.findtext("id") == name
    assert root.findtext("startmode") == "Automatic"
    assert root.findtext("executable").endswith(r"python\python.exe")
    assert module in root.findtext("arguments")
    assert [e.get("action") for e in root.findall("onfailure")] == ["restart"] * 3
    assert {e.get("name"): e.get("value") for e in root.findall("env")}["SMARTCHAIN_CONFIG"].endswith("smartchain.env")
    if name == "SmartchainApi":
        assert "--host 127.0.0.1" in root.findtext("arguments")  # K-74: dışarıya yalnız IIS


def test_web_config_allows_the_largest_upload():
    """K-129: ImportMaxMb varsayılanı 100 MB; IIS varsayılanı 30 MB olduğu için yükleme sınırda kalırdı."""
    from app.jobs.settings import IMPORT_DEFAULTS
    root = ET.fromstring(render("web.config", API_PORT=8000))
    assert int(root.find("./system.webServer/security/requestFiltering/requestLimits").get("maxAllowedContentLength")) == IMPORT_DEFAULTS["ImportMaxMb"] * 1024 * 1024


def test_upload_folder_and_reader_are_in_the_package():
    """K-129: yükleme klasörü kurulur, API ve motor yazabilir; dosya okuyucu pakette."""
    install = (INSTALLER / "install.ps1").read_text(encoding="utf-8")
    assert "SMARTCHAIN_IMPORT_DIR=$ImportDir" in install and "Set-SidAcl -Path $ImportDir" in install
    runtime = (INSTALLER / "requirements-runtime.txt").read_text(encoding="utf-8")
    assert "openpyxl==" in runtime and "et_xmlfile==" in runtime


def test_web_config_proxies_api_and_websocket():
    root = ET.fromstring(render("web.config", API_PORT=8000))
    rule = root.find("./system.webServer/rewrite/rules/rule")
    pattern = re.compile(rule.find("match").get("url"))
    for path in ("api", "api/health", "api/ws", "api/jobs/5/cancel"):
        assert pattern.match(path), path
    assert not pattern.match("index.html")
    assert rule.find("action").get("url") == "http://127.0.0.1:8000/{R:0}"
    assert root.find("./system.webServer/httpErrors").get("existingResponse") == "PassThrough"


def test_index_html_has_no_external_resources():
    html = render("index.html", VERSION="0.6.0")
    assert "Smartchain 0.6.0" in html and "<script" not in html and "<link" not in html


@needs_ps
def test_expand_template_rejects_missing_placeholder(tmp_path):
    f = tmp_path / "t.xml"
    f.write_text("<a>{{X}}{{Y}}</a>", encoding="utf-8")
    out = ps(f"try {{ Expand-Template -Path '{f}' -Values @{{ X = 'a&b' }} -Xml }} catch {{ 'HATA: ' + $_.Exception.Message }}")
    assert out.startswith("HATA") and "{{Y}}" in out
    assert ps(f"Expand-Template -Path '{f}' -Values @{{ X = 'a&b'; Y = 1 }} -Xml") == "<a>a&amp;b1</a>"


# --- Paket bütünlüğü ---

@needs_ps
def test_manifest_check(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "a.py").write_text("print('a')", encoding="utf-8")
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")
    files = {rel: hashlib.sha256((tmp_path / rel).read_bytes()).hexdigest() for rel in ("app/a.py", "b.txt")}
    (tmp_path / "manifest.json").write_text(json.dumps({"version": "0.6.0", "files": files}), encoding="utf-8")
    check = f"(Get-PackageManifestProblems -Root '{tmp_path}') -join '|'"
    assert ps(check) == ""
    (tmp_path / "b.txt").write_text("değişti", encoding="utf-8")
    (tmp_path / "app" / "a.py").unlink()
    assert sorted(ps(check).split("|")) == ["değişmiş: b.txt", "eksik: app/a.py"]


# --- Paket içeriği ve sürümler ---

def test_prereqs_cover_install_script():
    items = json.loads((INSTALLER / "prereqs.json").read_text(encoding="utf-8"))["items"]
    assert {i["name"] for i in items} == {"python", "vcredist", "odbc18", "urlrewrite", "arr", "winsw"}
    for i in items:
        assert i["file"] and i["url"].startswith("https://") and "sha256" in i
    install = (INSTALLER / "install.ps1").read_text(encoding="utf-8-sig")
    for name in ("python", "vcredist", "odbc18", "urlrewrite", "arr", "winsw"):
        assert f"Get-Prereq '{name}'" in install, name


def test_runtime_requirements_match_dev_environment():
    """Paketteki sürümler geliştirmede test edilenlerle aynı; test paketleri pakete girmez."""
    pins = {}
    for line in (INSTALLER / "requirements-runtime.txt").read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            name, version = line.split("==")
            pins[name.split("[")[0]] = version
    assert "pytest" not in pins and "httpx" not in pins
    for name, version in pins.items():
        assert md.version(name) == version, f"{name}: geliştirme {md.version(name)}, paket {version}"


# --- Ayarlar: servisler SMARTCHAIN_CONFIG dosyasını okur ---

def test_settings_read_config_file(tmp_path, monkeypatch):
    from app.api.settings import Settings, config_files
    cfg = tmp_path / "smartchain.env"
    cfg.write_text("SMARTCHAIN_LOG_LEVEL=DEBUG\nSMARTCHAIN_JOB_WATCH_SECONDS=2.5\n", encoding="utf-8")
    monkeypatch.setenv("SMARTCHAIN_CONFIG", str(cfg))
    monkeypatch.delenv("SMARTCHAIN_LOG_LEVEL", raising=False)
    monkeypatch.delenv("SMARTCHAIN_JOB_WATCH_SECONDS", raising=False)
    s = Settings(_env_file=config_files())
    assert s.log_level == "DEBUG" and s.job_watch_seconds == 2.5
    monkeypatch.setenv("SMARTCHAIN_LOG_LEVEL", "WARNING")  # ortam değişkeni dosyayı ezer
    assert Settings(_env_file=config_files()).log_level == "WARNING"


# --- Veritabanı adımı, yerel SQL Server'da (geçici veritabanı açılır ve silinir) ---

@pytest.mark.db
def test_setup_db_on_local_server(monkeypatch):
    name = "Smartchain_install_test"  # silinir; koruma: setup_db.refuse_in_tests, tests/test_db_guard.py
    monkeypatch.setenv("SMARTCHAIN_DB_URL", os.environ.get("SMARTCHAIN_DB_URL", ""))  # migrate değiştirir, test sonunda geri gelir
    conn = dict(encrypt="yes", trust_server_certificate=True)
    master = setup_db.odbc_string("localhost", "master", **conn)
    db = setup_db.odbc_string("localhost", name, **conn)
    setup_db.drop_database(master, name)
    try:
        assert setup_db.ensure_database(master, name) is True
        assert setup_db.ensure_database(master, name) is False
        # Var olan bir servis hesabı (SQL Server'ın kendi servisi) üzerinden SID → ad → kullanıcı.
        names = setup_db.ensure_service_logins(master, db, [service_sid("MSSQLSERVER")])
        assert names and names[0].upper().endswith("\\MSSQLSERVER")
        setup_db.migrate(ROOT, db)
        # K-109: geçişlerden sonra servis hesabı uygulama rolünde, db_owner değil; yeniden kurulum aynı sonucu verir.
        with setup_db._connect(db) as c:
            c.execute(f"ALTER ROLE db_owner ADD MEMBER {setup_db.quote_name(names[0])}")  # eski kurulumdan kalma
        for _ in range(2):
            assert setup_db.apply_app_permissions(db, sids=[service_sid("MSSQLSERVER")])
        with setup_db._connect(db) as c:
            assert setup_db.audit_permission_problems(c) == []
            members = [u.upper() for u in setup_db._role_members(c, setup_db.APP_ROLE)]
            assert names[0].upper() in members and names[0].upper() not in [u.upper() for u in setup_db._role_members(c, "db_owner")]
        with setup_db._connect(db) as c:
            assert c.execute("SELECT version_num FROM dbo.alembic_version").fetchone()[0] == "0046"
            assert c.execute("SELECT DATABASEPROPERTYEX(DB_NAME(), 'Collation')").fetchone()[0] == setup_db.COLLATION
        # İlk hesap (K-102): temiz veritabanında açılır, ikinci çalıştırmada dokunulmaz, --reset yeni şifre verir.
        user_name, password = setup_db.first_account(ROOT, db, reset=False)
        assert user_name == "smartchain" and len(password) >= 12
        assert setup_db.first_account(ROOT, db, reset=False) is None
        assert setup_db.first_account(ROOT, db, reset=True)[1] != password
        with setup_db._connect(db) as c:
            assert c.execute("SELECT COUNT(*) FROM adm.AppUser WHERE Role = N'System owner'").fetchone()[0] == 1
    finally:
        setup_db.drop_database(master, name)


def test_write_env_db_url_changes_only_that_line(tmp_path):
    env = tmp_path / "smartchain.env"
    env.write_bytes(b"# ayarlar\r\nSMARTCHAIN_DB_URL=eski\r\nSMARTCHAIN_LOG_LEVEL=INFO\r\n")
    setup_db.write_env_db_url(env, r"mssql+pyodbc:///?odbc_connect=a%3Db\c")
    assert env.read_bytes() == b"# ayarlar\r\nSMARTCHAIN_DB_URL=mssql+pyodbc:///?odbc_connect=a%3Db\\c\r\nSMARTCHAIN_LOG_LEVEL=INFO\r\n"
    env.write_text("BASKA=1\n", encoding="utf-8")
    with pytest.raises(RuntimeError):
        setup_db.write_env_db_url(env, "x")


def test_sql_login_password_is_not_printed(monkeypatch, capsys, tmp_path):
    """K-109: SQL kimliğiyle kurulumda uygulama hesabının şifresi yalnız ayar dosyasına gider."""
    env = tmp_path / "smartchain.env"
    env.write_text("SMARTCHAIN_DB_URL=eski\n", encoding="utf-8")
    monkeypatch.setenv("SMARTCHAIN_INSTALL_SQL_PASSWORD", "kurulum-sifresi")
    monkeypatch.setattr(setup_db, "ensure_database", lambda *a: False)
    monkeypatch.setattr(setup_db, "migrate", lambda *a: None)
    monkeypatch.setattr(setup_db, "ensure_sql_app_login", lambda *a: "Uygulama-Sifresi-1")
    calls = []
    monkeypatch.setattr(setup_db, "apply_app_permissions", lambda db, sids=(), users=(): calls.append(users) or list(users))
    assert setup_db.main(["setup", "--instance", "db01", "--sql-user", "kurulum", "--env-file", str(env), "--trust-server-certificate"]) == 0
    assert calls == [[setup_db.SQL_APP_LOGIN]]
    out = capsys.readouterr().out
    assert "Uygulama-Sifresi-1" not in out and "kurulum-sifresi" not in out
    text = env.read_text(encoding="utf-8")
    assert "Uygulama-Sifresi" in text and "UID%3D%7Bsmartchain_app%7D" in text.replace("+", "") and "kurulum-sifresi" not in text


def test_new_app_password_meets_policy():
    password = setup_db.new_app_password()
    assert len(password) >= 20 and any(c.isupper() for c in password) and any(c.islower() for c in password) and "'" not in password


def test_first_account_command_prints_password_only_on_its_line(monkeypatch, capsys):
    args = ["first-account", "--instance", "localhost", "--trust-server-certificate"]
    monkeypatch.setattr(setup_db, "first_account", lambda root, db, reset: ("smartchain", "Gecici12345a"))
    assert setup_db.main(args) == 0
    assert capsys.readouterr().out.strip() == "FIRST_ACCOUNT smartchain Gecici12345a"
    monkeypatch.setattr(setup_db, "first_account", lambda root, db, reset: None)
    assert setup_db.main(args) == 0
    assert capsys.readouterr().out.strip() == "FIRST_ACCOUNT_EXISTS"


def test_install_shows_first_password_without_logging_it():
    """K-102: geçici şifre log dosyasına gitmez; son adımda açılır, kurulum özetinden sonra Write-Host ile gösterilir."""
    install = (INSTALLER / "install.ps1").read_text(encoding="utf-8-sig")
    lines = install.splitlines()
    assert not [l for l in lines if "FirstAccount[2]" in l and "Write-Host" not in l]
    assert not [l for l in lines if "Write-Log" in l and "FirstAccount[2]" in l]
    assert "Invoke-Native $Python $a" in install  # çıktı akıtılmaz, değişkene alınır
    assert install.index("'Sağlık kontrolü'") < install.index("'install-state.json'") < install.index("'İlk hesap'")
    assert install.index("'İlk hesap'") < install.index("FirstAccount[2]")
    verify = (INSTALLER / "smoke.py").read_text(encoding="utf-8")
    assert "check_owner" in verify


def test_web_config_serves_single_page_app_and_fonts():
    """Arayüz (K-81): /api dışındaki dosya olmayan adresler index.html'e; woff2 türü tanımlı."""
    root = ET.fromstring(render("web.config", API_PORT=8000))
    rules = root.findall("./system.webServer/rewrite/rules/rule")
    assert [r.get("name") for r in rules] == ["Smartchain API", "Smartchain arayüz"]  # API önce, stopProcessing
    assert all(r.get("stopProcessing") == "true" for r in rules)
    spa = rules[1]
    conds = {(c.get("input"), c.get("matchType"), c.get("negate")) for c in spa.findall("./conditions/add")}
    assert conds == {("{REQUEST_FILENAME}", "IsFile", "true"), ("{REQUEST_FILENAME}", "IsDirectory", "true")}
    assert spa.find("action").get("url") == "/index.html"
    mimes = {m.get("fileExtension"): m.get("mimeType") for m in root.findall("./system.webServer/staticContent/mimeMap")}
    assert mimes[".woff2"] == "font/woff2"


def test_build_and_install_handle_web():
    build = (INSTALLER / "build.ps1").read_text(encoding="utf-8-sig")
    assert "'npm.cmd' @('ci'" in build and "'npm.cmd' @('run', 'build')" in build
    assert "Copy-Tree (Join-Path $WebSrc 'dist') (Join-Path $Dist 'web')" in build
    install = (INSTALLER / "install.ps1").read_text(encoding="utf-8-sig")
    assert "Join-Path $Package 'web\*'" in install


# --- SQL Server belleği ön kontrolü (K-94): uyarı verir, kurulumu durdurmaz ---

def memory_advice(max_mb: int, total_mb: int) -> str:
    return ps(f"$a = Get-SqlMemoryAdvice -MaxServerMemoryMB {max_mb} -TotalMemoryMB {total_mb}; "
              "if ($null -eq $a) { 'UYGUN' } else { $a }")


@needs_ps
def test_sql_memory_advice_thresholds():
    unlimited = memory_advice(2147483647, 16384)
    assert "sınırsız" in unlimited
    assert "max server memory 8192–11264 MB, min server memory 2048 MB" in unlimited  # docs/10 tablosu
    assert "max server memory 16384–22528 MB, min server memory 4096 MB" in memory_advice(2147483647, 32768)
    over = memory_advice(14000, 16384)  # %85
    assert "%80'inden fazla" in over and "%85" in over
    assert memory_advice(13107, 16384) == "UYGUN"   # %80 sınırı: uyarı yok
    assert memory_advice(13108, 16384) != "UYGUN"   # sınırın hemen üstü
    assert memory_advice(3072, 16024) == "UYGUN"
    assert "min server memory 1024 MB" in memory_advice(2147483647, 4096)  # taban en az 1024 MB


@needs_ps
def test_sql_memory_check_warns_but_never_throws_when_unreachable():
    out = ps("$ok = Test-SqlServerMemory -Instance 'tcp:127.0.0.1,1' -TimeoutSeconds 3 -TrustServerCertificate; "
             "\"SONUC=$ok\"")
    assert "WARN" in out and "SQL Server bellek ayarı okunamadı (tcp:127.0.0.1,1)" in out
    assert "Kurulum devam ediyor." in out and out.endswith("SONUC=False")


@needs_ps
@pytest.mark.db
def test_sql_memory_check_reads_local_server():
    """Yerel SQL Server'dan okunan değerler pyodbc ile okunanla aynı; karar aynı eşikle verilir."""
    try:
        with setup_db._connect(setup_db.odbc_string("localhost", "master", encrypt="yes",
                                                    trust_server_certificate=True)) as c:
            expected = c.execute(
                "SELECT (SELECT CAST(value_in_use AS bigint) FROM sys.configurations WHERE name = 'max server memory (MB)'), "
                "(SELECT physical_memory_kb / 1024 FROM sys.dm_os_sys_info)").fetchone()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Yerel SQL Server'a bağlanılamadı: {exc}")
    out = ps("$m = Get-SqlServerMemory -Instance 'localhost' -TrustServerCertificate; \"$($m.MaxMB)|$($m.TotalMB)\"; "
             "$ok = Test-SqlServerMemory -Instance 'localhost' -TrustServerCertificate; \"SONUC=$ok\"")
    assert out.splitlines()[0] == f"{expected[0]}|{expected[1]}"
    fits = expected[0] < 2147483647 and expected[0] <= expected[1] * 0.8
    assert out.endswith(f"SONUC={fits}")
    assert ("SQL Server belleği uygun" in out) == fits


def test_install_runs_sql_memory_check_in_precheck():
    text = (INSTALLER / "install.ps1").read_text(encoding="utf-8-sig")
    precheck = text[text.index("Invoke-Step 'Ön kontrol'"):text.index("# --- 2 ·")]
    call = re.search(r"Test-SqlServerMemory -Instance \$SqlInstance -Encrypt \$SqlEncrypt "
                     r"-TrustServerCertificate:\$SqlTrustServerCertificate `\s+-User \$SqlUser -Password \$SqlPassword \| Out-Null",
                     precheck)
    assert call, "Ön kontrol adımı SQL Server belleğini denetlemeli (K-94)"


# --- build.ps1: açık arayüz geliştirme sunucusu varken durur (npm ci node_modules'u yarıda bırakmasın) ---

@needs_ps
def test_find_web_dev_processes():
    web = str(ROOT / "app" / "web")
    procs = [
        (1, "node.exe", rf'"node" "{web}\node_modules\.bin\..\vite\bin\vite.js"'),           # npm run dev'in vite'ı
        (2, "node.exe", f"node {web.replace(chr(92), '/')}/node_modules/vitest/vitest.mjs run"),  # eğik çizgili yol
        (3, "node.exe", rf"node C:\Users\Hp\.cache\codex\node_modules\server.mjs"),              # başka klasör
        (4, "node.exe", rf"node {web}-eski\node_modules\vite\bin\vite.js"),                       # benzer adlı klasör
        (5, "python.exe", rf"python {web}\scripts\x.py"),                                         # node değil
        (6, "node.exe", None),                                                                    # komut satırı okunamadı
    ]
    objs = ", ".join(
        f"[pscustomobject]@{{ ProcessId = {pid}; Name = '{name}'; CommandLine = "
        + ("$null" if cmd is None else "'" + cmd.replace("'", "''") + "'") + " }"
        for pid, name, cmd in procs)
    out = ps(f"(Find-WebDevProcesses -WebDir '{web}' -Processes @({objs}) | ForEach-Object {{ $_.ProcessId }}) -join ','")
    assert out == "1,2"


def test_build_checks_dev_server_before_npm_ci():
    text = (INSTALLER / "build.ps1").read_text(encoding="utf-8-sig")
    check = text.index(r"Assert-NoWebDevServer -WebDir (Join-Path $Root 'app\web')")
    assert check < text.index("# --- Ön koşullar ---") < text.index("'ci', '--no-audit'")


@needs_ps
def test_assert_no_web_dev_server():
    r"""Süreç yokken sessiz geçer (StrictMode altında); app\web'de node süreci varsa durur ve listeler."""
    # Süreç yok: Get-CimInstance boş döner (testin kendi vitest'i çalışıyor olabilir; gerçek süreç listesi kullanılmaz)
    assert ps("function Get-CimInstance { @() }; "
              rf"Assert-NoWebDevServer -WebDir '{ROOT / 'app' / 'web'}'; 'GECTI'") == "GECTI"
    out = ps("function Get-CimInstance { @([pscustomobject]@{ ProcessId = 42; Name = 'node.exe'; "
             r"CommandLine = 'node C:\x\app\web\node_modules\vite\bin\vite.js' }) }; "
             r"try { Assert-NoWebDevServer -WebDir 'C:\x\app\web'; 'GECTI' } catch { $_.Exception.Message }")
    assert out.startswith("Arayüz klasöründe çalışan node süreci var") and "#42" in out
