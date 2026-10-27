"""Arayüz testleri (app/web, vitest): Node.js ve paketler varsa pytest'in parçası olarak çalışır, yoksa atlanır."""
import shutil
import subprocess
from pathlib import Path

import pytest

WEB = Path(__file__).resolve().parents[1] / "app" / "web"
NPM = shutil.which("npm.cmd") or shutil.which("npm")


@pytest.mark.skipif(NPM is None or not (WEB / "node_modules").exists(),
                    reason="Node.js ya da app/web/node_modules yok (cd app/web; npm ci)")
def test_web_unit_tests():
    r = subprocess.run([NPM, "test", "--", "--reporter=dot"], cwd=WEB, capture_output=True, timeout=600)
    out = (r.stdout + r.stderr).decode("utf-8", "replace")
    assert r.returncode == 0, out[-3000:]
