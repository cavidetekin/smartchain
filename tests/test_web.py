"""Arayüz testleri (app/web, vitest): Node.js ve paketler varsa pytest'in parçası olarak çalışır, yoksa atlanır.

Commit zinciri vitest'i ayrıca `npm test` ile koşar; zincir pytest'i SMARTCHAIN_SKIP_WEB_TESTS=1 ile çalıştırır, bu test o zaman atlanır
(aynı testler iki kez koşmaz). Değişken yokken `python -m pytest` tek başına arayüz testlerini de kapsar (docs/08)."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

WEB = Path(__file__).resolve().parents[1] / "app" / "web"
NPM = shutil.which("npm.cmd") or shutil.which("npm")


@pytest.mark.skipif(os.environ.get("SMARTCHAIN_SKIP_WEB_TESTS") == "1", reason="Commit zinciri: arayüz testleri ayrıca npm test ile koşar")
@pytest.mark.skipif(NPM is None or not (WEB / "node_modules").exists(),
                    reason="Node.js ya da app/web/node_modules yok (cd app/web; npm ci)")
def test_web_unit_tests():
    r = subprocess.run([NPM, "test", "--", "--reporter=dot"], cwd=WEB, capture_output=True, timeout=600)
    out = (r.stdout + r.stderr).decode("utf-8", "replace")
    assert r.returncode == 0, out[-3000:]
