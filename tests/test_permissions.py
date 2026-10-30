"""Yetki matrisi (fonksiyon 90; K-99, K-100): yapı, docs ile birebirlik, rol kuralları, uç nokta kapsamı."""
import re
from pathlib import Path

from fastapi.routing import APIRoute, APIWebSocketRoute

from app.api import permissions as perm
from app.api.main import create_app
from app.api.permissions import ADMIN, END_USER, KEY_USER, ROLES, SYSTEM_OWNER, Access, Level

ROOT = Path(__file__).resolve().parents[1]
DOCS06 = (ROOT / "docs" / "06-fonksiyonlar.md").read_text(encoding="utf-8")
WORDS = {"tam": Level.FULL, "sahibi": Level.OWNER, "kendi": Level.SELF, "salt okunur": Level.READ, "yok": Level.NONE}


def test_roles_and_names():
    assert ROLES == ("System owner", "Admin", "Key user", "End user")  # K-99


def test_98_functions_match_docs():
    documented = {}
    for m in re.finditer(r"^- \*\*(\d{2}) · (.+?):\*\*", DOCS06, re.M):
        documented.setdefault(int(m.group(1)), m.group(2))
    assert sorted(perm.FUNCTIONS) == list(range(1, 99))
    assert {no: f.name for no, f in perm.FUNCTIONS.items()} == documented


def test_groups_cover_functions_once_and_match_mockup_ranges():
    covered = [no for g in perm.GROUP_ROWS for no in range(g.first, g.last + 1)]
    assert covered == list(range(1, 99))
    assert [(g.letter, g.first, g.last) for g in perm.GROUP_ROWS] == [
        ("A", 1, 9), ("B", 10, 21), ("C", 22, 28), ("D", 29, 39), ("E", 40, 49), ("F", 50, 63), ("G", 64, 69),
        ("H", 70, 75), ("I", 76, 81), ("J", 82, 87), ("K", 88, 95), ("K", 96, 97), ("K", 98, 98)]


def test_group_table_in_docs_matches_code():
    start = DOCS06.index("**Yetki matrisi (K-100")
    rows = []
    for line in DOCS06[start:].splitlines()[2:]:
        if not line.startswith("|"):
            break
        rows.append([c.strip() for c in line.strip("|").split("|")])
    header, body = rows[0], rows[2:]
    assert header == ["Grup", "Fonksiyonlar", *ROLES]
    expected = [[f"{g.letter} · {g.name}", f"{g.first:02d}–{g.last:02d}" if g.first != g.last else f"{g.first:02d}",
                 *[next(w for w, lv in WORDS.items() if lv == level) for level in g.levels]] for g in perm.GROUP_ROWS]
    assert body == expected


def test_role_rules():
    for no in perm.FUNCTIONS:
        assert perm.level(SYSTEM_OWNER, no) == Level.FULL
        assert perm.level(ADMIN, no) == (Level.NONE if no in (96, 97) else Level.READ if no == 90 else Level.FULL)
        if 88 <= no <= 97 and no != 89:
            assert perm.level(KEY_USER, no) == Level.NONE
    end_writes = {no for no in perm.FUNCTIONS if perm.allows(END_USER, no, Access.WRITE, own=False)}
    assert end_writes == {86, 89}  # End user fonksiyon çalıştıramaz; Excel ve oturum dışında (K-99)
    end_self = {no for no in perm.FUNCTIONS if perm.level(END_USER, no) == Level.SELF}
    assert end_self == {48, 87}
    assert all(perm.level(END_USER, no) == Level.NONE for no in range(22, 29))  # Parametre End user'da yok (K-99)
    assert all(perm.level(KEY_USER, no) == Level.OWNER for no in range(50, 64))  # kendi çalışması
    assert perm.level("Sistem sahibi", 10) == Level.NONE  # tanınmayan rol hiçbir şey yapamaz


def test_access_and_required_role():
    assert perm.allows(KEY_USER, 55, Access.WRITE, own=True) and not perm.allows(KEY_USER, 55, Access.WRITE, own=False)
    assert perm.allows(KEY_USER, 55, Access.READ, own=False)  # başkasının çalışmasını salt okunur görür
    assert perm.allows(END_USER, 48, Access.READ) and not perm.allows(END_USER, 48, Access.READ, own=False)
    assert perm.required_role(10, Access.READ) == END_USER
    assert perm.required_role(12, Access.WRITE) == KEY_USER
    assert perm.required_role(93, Access.WRITE) == ADMIN
    assert perm.required_role(96, Access.READ) == SYSTEM_OWNER
    assert perm.forbidden_message(12, Access.WRITE) == "Bu işlem için Key user yetkisi gerekir. Yetki için yöneticinize başvurun."
    assert perm.forbidden_message(96, Access.READ) == "Bu işlem için System owner yetkisi gerekir. Smartchain desteğine başvurun."
    assert perm.role_permissions(END_USER)["86"] == "full" and len(perm.role_permissions(ADMIN)) == 98


def test_shared_copy_is_up_to_date():
    assert perm.SHARED.read_text(encoding="utf-8") == perm.render(), "python -m app.api.permissions"


OPEN = {("GET", "/api/health"), ("POST", "/api/auth/login")}


def _permissions(dependant) -> list:
    found = [getattr(dependant.call, "permission", None)] if dependant.call else []
    for d in dependant.dependencies:
        found += _permissions(d)
    return [p for p in found if p]


def _flat(routes, prefix=""):
    """Uygulamanın yolları; bu FastAPI sürümünde eklenen router'lar _IncludedRouter içinde durur."""
    for route in routes:
        included = getattr(route, "original_router", None)
        if included is not None:
            yield from _flat(included.routes, prefix + route.include_context.prefix)
        else:
            yield prefix + getattr(route, "path", ""), route


def test_every_endpoint_has_a_permission():
    """K-100: /api altındaki her uç nokta bir fonksiyona ve erişime bağlı; açık olanlar yalnız sağlık ve giriş."""
    missing, seen = [], 0
    for path, route in _flat(create_app().routes):
        if isinstance(route, APIWebSocketRoute):
            seen += 1
            assert getattr(route.endpoint, "permission", None) == (48, Access.READ), path
        elif isinstance(route, APIRoute):
            for method in route.methods:
                seen += 1
                if (method, path) not in OPEN and not _permissions(route.dependant):
                    missing.append(f"{method} {path}")
        elif path.startswith("/api"):
            missing.append(f"(yetkisiz yol) {path}")
    assert seen > 20 and missing == []


def test_openapi_only_with_docs():
    paths = {path for path, _ in _flat(create_app().routes)}
    assert "/api/openapi.json" not in paths and "/api/docs" not in paths
