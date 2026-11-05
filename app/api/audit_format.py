"""Denetim izi değerlerinin okunur biçimi (K-108). Saklanan satır değişmez; ekran, detay ve Excel buradan okur.

Yeni iz anahtarı ya da kodlu değer eklenince karşılığı burada eklenir; unutulursa test düşer (tests/test_audit_format.py, tests/audit_guard.py).
"""
import json
import re
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

EMPTY = "—"
YES, NO = "Evet", "Hayır"
SEPARATOR = " · "
UTC_TEXT = re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}")

FIELD_LABELS = {
    # Kullanıcı ve oturum
    "UserName": "Kullanıcı adı", "FullName": "Ad soyad", "Role": "Rol", "role": "Rol", "IsActive": "Aktif",
    "LockedUntil": "Kilit bitişi", "locked_until": "Kilit bitişi", "FailedAttempts": "Hatalı giriş sayısı",
    "MustChangePassword": "Şifre değişmeli", "PasswordChangeReason": "Şifre değişikliği nedeni",
    "ended_sessions": "Kapanan oturumlar", "session_id": "Oturum no", "idle_minutes": "Hareketsizlik süresi (dk)",
    "reason": "Neden", "remaining_attempts": "Kalan deneme", "source": "Kaynak", "address": "IP adresi", "user_agent": "Tarayıcı",
    # Ayar, etiket, görünüm
    "Value": "Değer", "Label": "Etiket", "Name": "Ad", "IsShared": "Paylaşılan", "Definition": "Tanım", "view_id": "Görünüm no",
    # İş
    "status": "Durum", "cancel_reason": "İptal nedeni", "job_type": "İş türü", "requested_by": "İşi başlatan no", "channel": "Kanal", "job_id": "İş no",
    # Yetkisiz istek
    "function": "Fonksiyon no", "function_name": "Fonksiyon", "access": "Erişim", "action": "İşlem", "target": "Hedef", "target_id": "Hedef no",
    "method": "İstek türü", "path": "İstek adresi",
    # Dışa aktarım
    "list": "Liste", "title": "Liste", "rows": "Satır", "size": "Boyut (bayt)", "seconds": "Süre (sn)", "background": "Arka planda",
    "columns": "Kolonlar", "filters": "Filtreler", "sort": "Sıralama", "group_by": "Gruplama", "scope": "Kapsam", "data_version": "Veri versiyonu",
    "field": "Alan", "dir": "Yön",
    # Şablon indirme
    "entity_name": "Tablo", "version": "Sürüm", "field_count": "Alan sayısı",
    # Excel yükleme (K-129)
    "mode": "Mod", "valid": "Geçerli satır", "errors": "Hatalı satır", "template_version": "Şablon sürümü", "file_name": "Dosya adı",
}

# Kodlu değerler; anahtara göre. Burada olmayan değer (ad, adres, serbest metin) olduğu gibi görünür.
VALUE_LABELS = {
    "reason": {
        "password": "Hatalı şifre", "inactive": "Hesap kapalı", "locked": "Hesap kilitli", "current_password_wrong": "Mevcut şifre hatalı",
        "hidden_account": "Gizli hesap", "sahibi değil": "Sahibi değil", "self": "Kendi hesabı", "system_owner": "System owner hesabı",
        "last_admin": "Son aktif Admin", "already_active": "Hesap zaten açık", "already_inactive": "Hesap zaten kapalı", "not_locked": "Hesap kilitli değil",
    },
    "access": {"read": "Okuma", "write": "Yazma"},
    "action": {"create": "Kullanıcı oluşturma", "role": "Rol değişikliği", "name": "Ad soyad değişikliği", "reset": "Şifre sıfırlama", "unlock": "Kilit açma", "close": "Kapatma", "reopen": "Geri açma"},
    "method": {"GET": "Görüntüleme", "POST": "Gönderme", "PUT": "Güncelleme", "PATCH": "Güncelleme", "DELETE": "Silme"},
    "scope": {"all": "Tümü"},
    "rows": {"filtered": "Ekrandaki filtrelerle", "all": "Tümü"},
    "columns": {"visible": "Görünen", "all": "Tümü"},
    "dir": {"asc": "Artan", "desc": "Azalan"},
    "filters": {"yok": "Yok"},
    "source": {"kurulum": "Kurulum"},
    "Definition": {"değişti": "Değişti"},
}

FIELD_NAME_KEYS = frozenset({"columns", "group_by", "field"})  # değeri listenin alan adı: listenin etiketiyle gösterilir
GROUPED_NUMBERS = frozenset({"rows", "size"})  # numara değil miktar: binlik ayraçlı
# Ayar anahtarları: Sistem ayarları formundaki adlar (app/web/src/i18n/tr.ts; test ikisini karşılaştırır)
SETTING_LABELS = {
    "PasswordMinLength": "En az karakter", "PasswordRequireLetterAndDigit": "Harf ve rakam zorunlu", "PasswordHistoryCount": "Son kaç şifreden farklı",
    "PasswordMaxAgeDays": "Geçerlilik süresi (gün)", "LoginMaxFailedAttempts": "Kilit için hatalı giriş sayısı", "LoginLockMinutes": "Kilit süresi (dk)",
    "SessionIdleMinutes": "Oturumun kapandığı süre (dk)", "SessionWarningMinutes": "Kapanmadan önce uyarı (dk)",
    "DiskWarnPercent": "Disk uyarı eşiği (%)", "QueueWaitWarnMinutes": "Kuyruk bekleme eşiği (dk)", "ImportSyncMaxMb": "Beklemeden kontrol edilen en büyük dosya (MB)", "ImportMaxMb": "En büyük dosya (MB)", "ImportMaxRows": "Dosyada en çok satır", "SystemEventRetentionDays": "Hataların saklanma süresi (gün)",
}
OTHER_LISTS = {"permissions": "Yetki matrisi"}  # ortak liste olmayan dışa aktarımlar
RETIRED_FIELDS = {"IsPermanent": "Silinemez"}  # listeden kalkan alanlar: eski aktarım kayıtlarında geçer


@lru_cache(maxsize=1)
def _lists() -> dict:
    from .lists import LISTS  # lists/audit_log bu modülü okur
    return {defn.name: defn for defn in LISTS}


def _list_title(name: str) -> str:
    defn = _lists().get(name)
    return defn.title if defn else OTHER_LISTS.get(name, name)


def list_field_label(list_name: str | None, field: str) -> str:
    """Kolon ve sıralama alanı, listenin etiketiyle; liste ya da alan bilinmiyorsa olduğu gibi."""
    from .lists.definition import field_title
    defn = _lists().get(list_name)
    if field in RETIRED_FIELDS:
        return RETIRED_FIELDS[field]
    return (defn.labels.get(field) or field_title(defn, field)) if defn else field


def _parsed(raw: str | None) -> dict | None:
    """JSON sözlük; düz metinse {"Değer": metin}, boşsa None."""
    if raw is None or raw == "":
        return None
    try:
        value = json.loads(raw)
    except ValueError:
        return {"Değer": raw}
    return value if isinstance(value, dict) else {"Değer": value}


def _shown(parsed: dict) -> dict:
    """Listenin adı varken kod adı tekrar edilmez."""
    return {k: v for k, v in parsed.items() if not (k == "list" and "title" in parsed)}


def _label(key: str) -> str:
    return FIELD_LABELS.get(key, key)


def _local_time(text: str) -> str | None:
    """Saklanan zamanlar UTC; ekranda sunucunun yerel saati."""
    if not UTC_TEXT.match(text):
        return None
    try:
        at = datetime.fromisoformat(text)
    except ValueError:
        return None
    at = at.replace(tzinfo=timezone.utc) if at.tzinfo is None else at
    return f"{at.astimezone():%d.%m.%Y %H:%M}"


def _string(text: str, key: str | None, list_name: str | None) -> str:
    known = VALUE_LABELS.get(key, {}).get(text)
    if known:
        return known
    if key == "list":
        return _list_title(text)
    if key in FIELD_NAME_KEYS:
        return list_field_label(list_name, text)
    return _local_time(text) or text


def _number(value: int | float, key: str | None) -> str:
    if isinstance(value, float):
        return str(value).replace(".", ",")
    return f"{value:,}".replace(",", ".") if key in GROUPED_NUMBERS else str(value)


def value_text(value: Any, key: str | None = None, list_name: str | None = None) -> str:
    if value is None or value == "":
        return EMPTY
    if isinstance(value, bool):
        return YES if value else NO
    if isinstance(value, str):
        return _string(value, key, list_name)
    if isinstance(value, list):
        return ", ".join(value_text(v, key, list_name) for v in value) or EMPTY
    if isinstance(value, dict):
        return ", ".join(f"{_label(k)}: {value_text(v, k, list_name)}" for k, v in value.items()) or EMPTY
    return _number(value, key)


def readable(raw: str | None) -> str | None:
    """"Rol: Admin · Ad soyad: Burak"; boşsa None."""
    parsed = _parsed(raw)
    if not parsed:
        return None
    return SEPARATOR.join(f"{_label(k)}: {value_text(v, k, parsed.get('list'))}" for k, v in _shown(parsed).items())


def changes(old_raw: str | None, new_raw: str | None) -> list[dict]:
    """Detay penceresi: alan, eski, yeni (yan yana). Önce yeni değerdeki alanlar."""
    old, new = _parsed(old_raw) or {}, _parsed(new_raw) or {}
    list_name = new.get("list") or old.get("list")
    keys = list(_shown(new)) + [k for k in _shown(old) if k not in new]
    return [{"field": _label(k), "old": value_text(old.get(k), k, list_name), "new": value_text(new.get(k), k, list_name)} for k in keys]
