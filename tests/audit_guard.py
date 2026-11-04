"""İz okunur mu (K-108): conftest test sırasında yazılan her izi buradan geçirir, test_audit_format doğrudan kullanır."""
import json
import re

from app.api.audit_format import FIELD_LABELS, FIELD_NAME_KEYS, VALUE_LABELS

CODE = re.compile(r"^[a-z]+(_[a-z]+)*$")
SNAKE = re.compile(r"^[a-z]+(_[a-z]+)+$")
# Serbest metin ya da ad: kod gibi görünse de koddur denemez (kullanıcı adı, görünüm adı, iptal nedeni)
FREE_TEXT_KEYS = frozenset({"UserName", "FullName", "Name", "Label", "target", "cancel_reason", "Value", "title", "list", "path", "user_agent"})


def _walk(key: str | None, value, problems: list[str]) -> None:
    if isinstance(value, dict):
        for k, v in value.items():
            if k not in FIELD_LABELS:
                problems.append(f"çevirisi olmayan anahtar: {k}")
            _walk(k, v, problems)
    elif isinstance(value, list):
        if key not in FIELD_NAME_KEYS:
            for v in value:
                _walk(key, v, problems)
    elif isinstance(value, str) and key not in FREE_TEXT_KEYS:
        coded = key in VALUE_LABELS and bool(CODE.match(value))
        if key not in FIELD_NAME_KEYS and value not in VALUE_LABELS.get(key, {}) and (coded or SNAKE.match(value)):
            problems.append(f"çevirisi olmayan değer: {key} = {value}")


def unreadable(raw: str | None) -> list[str]:
    """Saklanan JSON'da okunur adı olmayan anahtar ve kodlu değerler."""
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except ValueError:
        return []
    problems: list[str] = []
    _walk(None, parsed, problems)
    return problems
