"""İnternetsizlik bekçisi (K-32, K-72): ürün kodunda ve kurulum paketinde internet adresi, CDN ya da dış servis yok.

Yalnız paket hazırlama (installer/build.ps1, installer/prereqs.json) internet adresi içerebilir; o da geliştirme
bilgisayarında çalışır. Yerel adresler (localhost, 127.0.0.1) serbesttir.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCANNED = ["app", "db", "installer"]
ALLOWED_FILES = {"installer/build.ps1", "installer/prereqs.json"}
SUFFIXES = {".py", ".ps1", ".html", ".js", ".css", ".xml", ".config", ".json", ".ini", ".txt", ".mako", ".sql"}
SKIP_DIRS = {"__pycache__", "cache"}

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
