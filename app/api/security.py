"""Şifre ve oturum anahtarı yardımcıları (K-97, K-98). Veritabanına dokunmaz.

- Şifre Argon2id ile özetlenir (argon2-cffi; m = 19 MiB, t = 2, p = 1, OWASP alt sınırı). Tuz şifre başınadır ve PHC
  metninin içindedir; parametre değişirse eski özet bir sonraki girişte yeniden özetlenir (needs_rehash).
- Oturum anahtarı 32 rastgele bayttır; tarayıcıya base64url, veritabanına yalnız SHA-256 özeti gider.
- Şifre hiçbir yerde düz metin olarak saklanmaz ve loga yazılmaz.
"""
import base64
import binascii
import hashlib
import secrets
import string
from dataclasses import dataclass

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_HASHER = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1, hash_len=32, salt_len=16, type=Type.ID)

# Bilinmeyen ya da şifresiz hesapta da bir doğrulama yapılır: cevap süresi hesabın varlığını ele vermesin (K-98).
_DUMMY_HASH = _HASHER.hash(secrets.token_urlsafe(16))

MAX_PASSWORD = 256  # daha uzun girdi özetlenmez (istek doğrulaması)


def hash_password(password: str) -> str:
    return _HASHER.hash(password)


def verify_password(stored: str | None, password: str) -> bool:
    """Özet boşsa (şifresiz hesap) sahte özete karşı doğrular ve False döner."""
    try:
        return _HASHER.verify(stored or _DUMMY_HASH, password) and bool(stored)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(stored: str) -> bool:
    try:
        return _HASHER.check_needs_rehash(stored)
    except InvalidHashError:
        return True


def new_token() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode("ascii")


def token_hash(token: str) -> bytes | None:
    """Çerezdeki anahtarın özeti; biçim bozuksa None (oturum yok sayılır)."""
    try:
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
    except (binascii.Error, ValueError):
        return None
    return hashlib.sha256(raw).digest() if len(raw) == 32 else None


# --- Politika (fonksiyon 89; ayarlar SystemSetting'te) ---

@dataclass(frozen=True)
class Policy:
    min_length: int = 10
    require_letter_and_digit: bool = True
    history_count: int = 5
    max_age_days: int = 90
    idle_minutes: int = 30
    warning_minutes: int = 5
    lock_after: int = 5
    lock_minutes: int = 15

    def public(self) -> dict:
        return {"min_length": self.min_length, "require_letter_and_digit": self.require_letter_and_digit,
                "history_count": self.history_count, "lock_after": self.lock_after, "lock_minutes": self.lock_minutes}


def _fold(text: str) -> str:
    """Türkçe harf duyarsız karşılaştırma: İ/I/ı/i aynı sayılır."""
    return text.replace("İ", "i").replace("I", "i").replace("ı", "i").casefold()


def policy_problems(policy: Policy, user_name: str, password: str) -> list[str]:
    """Sunucusuz denetlenebilen kurallar; geçmiş ve mevcut şifreyle aynılık serviste (özetle) denetlenir."""
    problems = []
    if len(password) < policy.min_length:
        problems.append("min_length")
    if policy.require_letter_and_digit and not (any(c.isalpha() for c in password) and any(c.isdigit() for c in password)):
        problems.append("letter_and_digit")
    if user_name and _fold(user_name) in _fold(password):
        problems.append("contains_user_name")
    return problems


_ALPHABET = "".join(c for c in string.ascii_letters + string.digits if c not in "0OoIl1")


def temporary_password(length: int = 12) -> str:
    """Politikaya uygun rastgele geçici şifre (harf ve rakam; karışan karakterler yok)."""
    while True:
        p = "".join(secrets.choice(_ALPHABET) for _ in range(length))
        if any(c.isalpha() for c in p) and any(c.isdigit() for c in p):
            return p
