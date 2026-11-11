"""Denetim izinin okunur biçimi (K-108): yazılan her anahtar ve kodlu değerin Türkçe karşılığı olur. Veritabanı istemez."""
import ast
import json
from pathlib import Path
from typing import get_args

import pytest

from app.api import audit_format
from app.api.audit_format import FIELD_LABELS, SETTING_LABELS, VALUE_LABELS, changes, list_field_label, readable
from app.api.lists import LISTS
from app.api.lists.request import ExportScope
from app.api.permissions import Access
from app.api.services import flows, health_settings, login_policy

from audit_guard import unreadable

APP = Path(__file__).resolve().parents[1] / "app"
AUDIT_CALLS = {"write_audit", "record_denial", "ensure", "ensure_owner", "forbidden"}


def _name(call: ast.Call) -> str | None:
    return call.func.attr if isinstance(call.func, ast.Attribute) else getattr(call.func, "id", None)


def _dict_keys(node: ast.Dict) -> set[str]:
    return {k.value for k in node.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)}


def _modules():
    for path in APP.rglob("*.py"):
        yield ast.parse(path.read_text(encoding="utf-8"))


def _dicts_fed_to_audit(tree: ast.Module):
    """İz yazan çağrıya giden sözlükler: çağrının içindekiler, çağırdığı yardımcının döndürdükleri, adıyla verilen değişkenler."""
    functions = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assigned: dict[str, list[ast.Dict]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assigned.setdefault(target.id, []).append(node.value)
    for call in (n for n in ast.walk(tree) if isinstance(n, ast.Call) and _name(n) in AUDIT_CALLS):
        read_from = {id(n.value) for n in ast.walk(call) if isinstance(n, (ast.Subscript, ast.Attribute))}  # payload["x"]: sözlüğün kendisi gitmiyor
        for node in ast.walk(call):
            if isinstance(node, ast.Dict):
                yield node
            elif isinstance(node, ast.Name) and id(node) not in read_from:
                yield from assigned.get(node.id, [])
            elif isinstance(node, ast.Call) and _name(node) in functions and _name(node) not in AUDIT_CALLS:
                for inner in ast.walk(functions[_name(node)]):
                    if isinstance(inner, ast.Return) and isinstance(inner.value, ast.Dict):
                        yield inner.value


def test_every_key_written_to_the_trail_has_a_label():
    written = {key for tree in _modules() for d in _dicts_fed_to_audit(tree) for key in _dict_keys(d)}
    assert {"remaining_attempts", "user_agent", "session_id", "rows", "cancel_reason", "function_name", "method"} <= written  # tarama boş dönmesin
    assert sorted(written - set(FIELD_LABELS)) == []


def _constant_args(tree: ast.Module, function: str, index: int) -> set[str]:
    return {n.args[index].value for n in ast.walk(tree) if isinstance(n, ast.Call) and _name(n) == function
            and len(n.args) > index and isinstance(n.args[index], ast.Constant)}


def test_every_coded_value_has_a_label():
    reasons, actions = set(), set()
    for tree in _modules():
        reasons |= _constant_args(tree, "Refusal", 0) | _constant_args(tree, "_audit_failed", 3)
        actions |= _constant_args(tree, "_guarded", 2) | _constant_args(tree, "_refuse", 2)
        for d in _dicts_fed_to_audit(tree):
            reasons |= {v.value for k, v in zip(d.keys, d.values) if isinstance(k, ast.Constant) and k.value == "reason" and isinstance(v, ast.Constant)}
    assert {"password", "locked", "inactive", "last_admin", "current_password_wrong", "hidden_account"} <= reasons
    assert sorted(r for r in reasons if r.isascii() and r != "System owner işi" and r not in VALUE_LABELS["reason"]) == []
    assert sorted(actions - set(VALUE_LABELS["action"])) == [] and {"unlock", "create"} <= actions
    assert {a.value for a in Access} == set(VALUE_LABELS["access"])
    assert set(get_args(ExportScope.model_fields["rows"].annotation)) == set(VALUE_LABELS["rows"])
    assert set(get_args(ExportScope.model_fields["columns"].annotation)) == set(VALUE_LABELS["columns"])


@pytest.mark.parametrize("defn", LISTS, ids=lambda d: d.name)
def test_every_list_field_has_a_label_in_export_details(defn):
    assert defn.title and audit_format._list_title(defn.name) == defn.title
    assert [f for f in defn.fields if list_field_label(defn.name, f) == f] == []


@pytest.mark.parametrize("new, text", [
    ({"reason": "password", "remaining_attempts": 1}, "Neden: Hatalı şifre · Kalan deneme: 1"),
    ({"reason": "inactive", "remaining_attempts": None}, "Neden: Hesap kapalı · Kalan deneme: —"),
    ({"reason": "current_password_wrong", "session_id": 12}, "Neden: Mevcut şifre hatalı · Oturum no: 12"),
    ({"address": "10.0.0.5", "user_agent": "Mozilla/5.0", "session_id": 3}, "IP adresi: 10.0.0.5 · Tarayıcı: Mozilla/5.0 · Oturum no: 3"),
    ({"reason": "Zaman aşımı", "session_id": 1, "idle_minutes": 30}, "Neden: Zaman aşımı · Oturum no: 1 · Hareketsizlik süresi (dk): 30"),
    ({"role": "Key user", "function": 90, "function_name": "Yetki matrisi", "access": "write", "method": "PUT", "path": "/api/x"},
     "Rol: Key user · Fonksiyon no: 90 · Fonksiyon: Yetki matrisi · Erişim: Yazma · İstek türü: Güncelleme · İstek adresi: /api/x"),
    ({"action": "unlock", "reason": "not_locked", "target": "burak"}, "İşlem: Kilit açma · Neden: Hesap kilitli değil · Hedef: burak"),
    ({"reason": "hidden_account", "target_id": 7}, "Neden: Gizli hesap · Hedef no: 7"),
    ({"reason": "sahibi değil", "list": "materials", "view_id": 4}, "Neden: Sahibi değil · Liste: Malzeme listesi · Görünüm no: 4"),
    ({"status": "İptal", "cancel_reason": "password"}, "Durum: İptal · İptal nedeni: password"),  # serbest metin çevrilmez
    ({"IsShared": True, "Definition": "değişti"}, "Paylaşılan: Evet · Tanım: Değişti"),
    ({"list": "permissions", "rows": 98}, "Liste: Yetki matrisi · Satır: 98"),
])
def test_readable_text(new, text):
    assert readable(json.dumps(new, ensure_ascii=False)) == text
    assert unreadable(json.dumps(new, ensure_ascii=False)) == []


def test_export_details_are_fully_readable():
    raw = json.dumps({
        "list": "users", "title": "Kullanıcı listesi", "data_version": None, "scope": {"rows": "filtered", "columns": "visible"},
        "columns": ["FullName", "UserName", "LastLoginAt"], "filters": "yok", "sort": [{"field": "UserName", "dir": "desc"}], "group_by": ["Role"],
        "rows": 1250, "size": 11320, "seconds": 0.17, "background": True, "job_id": 534}, ensure_ascii=False)
    assert unreadable(raw) == []
    assert readable(raw) == (
        "Liste: Kullanıcı listesi · Veri versiyonu: — · Kapsam: Satır: Ekrandaki filtrelerle, Kolonlar: Görünen · "
        "Kolonlar: Ad soyad, Kullanıcı adı, Son giriş · Filtreler: Yok · Sıralama: Alan: Kullanıcı adı, Yön: Azalan · Gruplama: Rol · "
        "Satır: 1.250 · Boyut (bayt): 11.320 · Süre (sn): 0,17 · Arka planda: Evet · İş no: 534")
    fields = {c["field"]: c["new"] for c in changes(None, raw)}
    assert fields["Kolonlar"] == "Ad soyad, Kullanıcı adı, Son giriş" and "list" not in fields and fields["Liste"] == "Kullanıcı listesi"


def test_setting_names_match_the_form():
    """Yazılabilen her ayarın adı var ve Sistem ayarları formundakiyle aynı."""
    keys = set(login_policy.LIMITS) | set(health_settings.LIMITS) | set(flows.SETTING_LIMITS)  # K-164: bekleme süreleri kendi sekmesinde
    assert set(SETTING_LABELS) == keys
    source = (APP / "web" / "src" / "i18n" / "tr.ts").read_text(encoding="utf-8")
    for key, label in SETTING_LABELS.items():
        assert f'{key}: "{label}"' in source, key


def test_retired_field_in_old_export_record():
    assert readable('{"list": "audit-log", "columns": ["At", "IsPermanent"]}') == "Liste: Denetim izi · Kolonlar: Zaman, Silinemez"


def test_detail_uses_the_same_words():
    assert changes('{"access": "read"}', '{"access": "write"}') == [{"field": "Erişim", "old": "Okuma", "new": "Yazma"}]


def test_unknown_key_stays_visible_but_guard_catches_it():
    """Üretimde bilgi kaybolmaz; testte yakalanır."""
    assert readable('{"yeni_anahtar": 3}') == "yeni_anahtar: 3"
    assert unreadable('{"yeni_anahtar": 3}') == ["çevirisi olmayan anahtar: yeni_anahtar"]
    assert unreadable('{"scope": {"yeni": 1}}') == ["çevirisi olmayan anahtar: yeni"]
    assert unreadable('{"reason": "yeni_kural"}') == ["çevirisi olmayan değer: reason = yeni_kural"]
    assert unreadable('{"status": "bir_kod"}') == ["çevirisi olmayan değer: status = bir_kod"]
    assert unreadable('{"reason": "Zaman aşımı"}') == []
    assert unreadable("düz metin") == []
