"""Arayüz metni kuralı (docs/12 "Arayüz metni"): kullanıcıya görünen metinlerde bilinen yasak kalıplar olmaz.

Sınırlı bir listedir, kuralın bütününü denetlemez: unutulan bilinen kalıpları yakalar. Geliştirme sayfaları (`/stil`,
`/tablo`) ve sistem yöneticisine yazılan sağlık mesajları kapsam dışıdır.
"""
import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BANNED = re.compile(r"\bAPI\b|Veritaban[ıi]|[İi]stek\b|[Pp]olitika|[Hh]areketsizlik|[Yy]ıkıcı işlem|[Oo]nay gerekli")
# tr.ts'de geliştirme sayfalarının bölümleri ve sistem yöneticisine yazılan sağlık metinleri (ör. "Veritabanı")
DEV_SECTIONS = (("  style: {", "  table: {"), ("  demo: {", "  screen: {"), ("  systemHealth: {", "  // Sistem ayarları (ekran 25"))


def banned(texts: list[str]) -> list[str]:
    return [t for t in texts if BANNED.search(t)]


def ui_texts() -> list[str]:
    source = (ROOT / "app/web/src/i18n/tr.ts").read_text(encoding="utf-8")
    for start, end in DEV_SECTIONS:
        source = source[:source.index(start)] + source[source.index(end):]
    source = re.sub(r"^\s*//.*$", "", source, flags=re.M)
    return [m.group(0) for m in re.finditer(r'"(?:[^"\\\n]|\\.)*"|`(?:[^`\\]|\\.)*`', source)]


def _literal(node: ast.AST) -> str:
    """Düz metin ya da f-string'in sabit parçaları."""
    return " ".join(n.value for n in ast.walk(node) if isinstance(n, ast.Constant) and isinstance(n.value, str))


def server_texts() -> list[str]:
    """AppError mesajları, genel hata metinleri ve doğrudan yazılan hata gövdeleri."""
    out = []
    for path in (ROOT / "app/api").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) in ("AppError", "error_body") and len(node.args) >= 2:
                out.append(_literal(node.args[1]))
            elif isinstance(node, ast.Assign) and any(getattr(t, "id", "") in ("HTTP_MESSAGES", "DB_UNAVAILABLE") for t in node.targets):
                out.append(_literal(node.value))
    return out


def test_scanner_finds_known_patterns():
    for text in ("API'ye ulaşılamıyor", "Veritabanına bağlanılamıyor", "İstek geçersiz.", "politika belirlenir",
                 "hareketsizlik sınırı", "yıkıcı işlem", "onay gerekli"):
        assert banned([text]) == [text]
    assert banned(["Sunucuya ulaşılamıyor", "Şifre kuralları", "Veriye ulaşılamıyor."]) == []


def test_scanner_sees_the_sources():
    assert any("Kural yok." in t for t in ui_texts())
    assert any("Veriye ulaşılamıyor." in t for t in server_texts())


@pytest.mark.parametrize("source", [ui_texts, server_texts], ids=["arayüz", "sunucu"])
def test_no_banned_pattern(source):
    assert banned(source()) == []
