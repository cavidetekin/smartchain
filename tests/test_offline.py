"""İnternetsizlik bekçisi (K-32, K-72): ürün kodunda ve kurulum paketinde internet adresi, CDN ya da dış servis yok.

Yalnız paket hazırlama (installer/build.ps1, installer/prereqs.json) internet adresi içerebilir; o da geliştirme
bilgisayarında çalışır. Yerel adresler (localhost, 127.0.0.1) serbesttir.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCANNED = ["app", "db", "installer"]
ALLOWED_FILES = {"installer/build.ps1", "installer/prereqs.json",
                 "app/web/package-lock.json"}  # paket adresleri yalnız geliştirmede (npm ci)
SUFFIXES = {".py", ".ps1", ".html", ".js", ".css", ".xml", ".config", ".json", ".ini", ".txt", ".mako", ".sql",
            ".ts", ".tsx"}
SKIP_DIRS = {"__pycache__", "cache", "node_modules", "dist"}  # dist ayrıca, kendi kurallarıyla taranır

URL = re.compile(r"\b(?:https?|wss?|ftp)://(?!(?:localhost|127\.0\.0\.1|\{\{))[^\s\"'<>)]+", re.IGNORECASE)
CDN = re.compile(r"cdnjs|jsdelivr|unpkg|googleapis|gstatic|\bcdn\b", re.IGNORECASE)


def scanned_files():
    for top in SCANNED:
        for p in (ROOT / top).rglob("*"):
            if p.is_file() and p.suffix.lower() in SUFFIXES and not SKIP_DIRS & set(p.parts):
                rel = p.relative_to(ROOT).as_posix()
                if rel not in ALLOWED_FILES:
                    yield rel, p


def test_no_internet_addresses_or_cdn():
    problems = []
    for rel, p in scanned_files():
        text = p.read_text(encoding="utf-8-sig", errors="replace")
        for n, line in enumerate(text.splitlines(), 1):
            for m in URL.finditer(line):
                problems.append(f"{rel}:{n}: {m.group(0)}")
            if CDN.search(line):
                problems.append(f"{rel}:{n}: CDN: {line.strip()[:80]}")
    assert not problems, "İnternet bağımlılığı:\n" + "\n".join(problems)


def test_scanner_catches_addresses():
    assert URL.search('src="https://cdn.example.com/x.js"')
    assert URL.search("ws://example.com/api/ws")
    assert not URL.search("http://127.0.0.1:{{API_PORT}}/{R:0}")
    assert not URL.search("ws://localhost:8000/api/ws")


# --- Çözücüden bağımsızlık bekçisi (K-35, K-76) ---

SOLVER_IMPORT = re.compile(r"^\s*(?:import\s+highspy|from\s+highspy\b)", re.MULTILINE)
SOLVER_DIR = "app/engine/solvers/"


def test_solver_package_only_imported_by_adapters():
    offenders = []
    for top in ("app", "installer", "scripts", "db"):
        for p in (ROOT / top).rglob("*.py"):
            rel = p.relative_to(ROOT).as_posix()
            if not rel.startswith(SOLVER_DIR) and SOLVER_IMPORT.search(p.read_text(encoding="utf-8")):
                offenders.append(rel)
    assert not offenders, f"highspy yalnız {SOLVER_DIR} altında import edilir: {offenders}"
    assert SOLVER_IMPORT.search((ROOT / SOLVER_DIR / "highs.py").read_text(encoding="utf-8"))


# --- Derlenmiş arayüz (K-81, K-83): app/web/dist ---

WEB_DIST = ROOT / "app" / "web" / "dist"
# Kütüphanelerin içinde geçen ama hiçbir şey indirmeyen adresler:
DIST_ALLOWED = (
    "http://www.w3.org/",              # SVG/MathML/XML ad alanları (xmlns), ağ isteği değil
    "https://react.dev/errors/",       # React'in hata mesajındaki belge bağlantısı (yalnız metin)
    "https://reactrouter.com/",        # react-router uyarı mesajındaki belge bağlantısı (yalnız metin)
    "http://localhost",                # react-router'ın adres ayrıştırmada kullandığı taban (ağ isteği değil)
)
DIST_URL = re.compile(r"(?:https?|wss?)://[^\s\"'`<>)]+", re.IGNORECASE)
LOAD = re.compile(r"""(?:src|href)\s*=\s*["']?(?:https?:)?//|url\(\s*["']?(?:https?:)?//|@import\s+["']?(?:https?:)?//|"""
                  r"""fetch\(\s*["'`](?:https?|wss?):|import\(\s*["'`]https?:|WebSocket\(\s*["'`]wss?:""", re.IGNORECASE)


def test_built_web_has_no_external_resources():
    if not (WEB_DIST / "index.html").exists():
        import pytest
        pytest.skip("app/web/dist yok (npm run build ile üretilir)")
    problems = []
    for p in WEB_DIST.rglob("*"):
        if p.suffix.lower() not in (".html", ".js", ".css"):
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        rel = p.relative_to(ROOT).as_posix()
        problems += [f"{rel}: dış kaynak yükleme: {m.group(0)}" for m in LOAD.finditer(text)]
        problems += [f"{rel}: {u}" for u in DIST_URL.findall(text) if not u.startswith(DIST_ALLOWED)]
    fonts = list(WEB_DIST.rglob("*.woff2"))
    assert fonts and any("instrument-sans" in f.name for f in fonts) and any("inter-" in f.name for f in fonts)
    assert not any("jetbrains" in f.name for f in fonts)  # K-86: paketten çıktı
    assert not problems, "\n".join(sorted(set(problems)))


def test_dist_scanner_catches_loads():
    assert LOAD.search('<link href="https://fonts.googleapis.com/css2">')
    assert LOAD.search("src:url(//cdn.example.com/a.woff2)")
    assert LOAD.search('fetch("https://example.com/api")')
    assert not LOAD.search('fetch("/api/jobs")')
    assert not LOAD.search('src:url(/assets/a.woff2)')
