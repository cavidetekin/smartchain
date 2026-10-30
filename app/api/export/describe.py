"""Bilgi sayfası metinleri (K-91): filtre, sıralama, gruplama ve ara toplam açıklamaları; ekrandaki etiketlerle aynı dil (U-12)."""
from datetime import date

TEXT_OPS = {"contains": "içerir", "not_contains": "içermez", "equals": "eşittir", "starts_with": "ile başlar"}
RELATIVE = {"this_week": "bu hafta", "next_4_weeks": "sonraki 4 hafta"}
AGG = {"sum": "toplam", "avg": "ortalama (boşlar hariç)", "avg_nonzero": "ortalama (sıfırlar hariç)", "wavg": "ağırlıklı ortalama",
       "min": "en küçük", "max": "en büyük", "count": "sayı (dolu satır)"}


def tr_number(v: float, decimals: int | None = None) -> str:
    """Türkçe sayı: 1.234,5 (U-19)."""
    d = decimals if decimals is not None else (0 if float(v).is_integer() else 2)
    s = f"{float(v):,.{d}f}"
    return s.replace(",", "\0").replace(".", ",").replace("\0", ".")


def tr_date(iso: str | date) -> str:
    d = iso if isinstance(iso, date) else date.fromisoformat(str(iso))
    return d.strftime("%d.%m.%Y")


def value_label(v) -> str:
    return ("Evet" if v else "Hayır") if isinstance(v, bool) else str(v)


def describe_filter(f: dict, label: str, decimals: int | None = None) -> str:
    op = f.get("op")
    if op == "empty":
        text = "boş"
    elif op in TEXT_OPS:
        text = f"{TEXT_OPS[op]} '{f.get('value')}'"
    elif op == "in":
        labels = [value_label(v) for v in f.get("values") or []] + (["boş"] if f.get("empty") else [])
        text = ", ".join(labels)
    elif op in ("eq", "gt", "lt"):
        text = {"eq": "=", "gt": ">", "lt": "<"}[op] + " " + tr_number(f["value"], decimals)
    elif op == "relative":
        text = RELATIVE.get(f.get("value"), str(f.get("value")))
    elif op == "between" and ("from" in f or "to" in f):
        a, b = f.get("from"), f.get("to")
        text = f"{tr_date(a)}–{tr_date(b)}" if a and b else (f"{tr_date(a)} ve sonrası" if a else f"{tr_date(b)} ve öncesi")
    elif op == "between":
        lo, hi = f.get("min"), f.get("max")
        text = (f"{tr_number(lo, decimals)}–{tr_number(hi, decimals)}" if lo is not None and hi is not None
                else f"≥ {tr_number(lo, decimals)}" if lo is not None else f"≤ {tr_number(hi, decimals)}")
    else:
        text = str(op)
    return f"{label}: {text}"


CMP = {"gt": ">", "lt": "<", "eq": "="}
RULE_TEXT_OPS = {"equals": "eşittir", "contains": "içerir", "starts_with": "ile başlar"}
ICON_NAMES = {"arrow_up": "yukarı ok", "arrow_down": "aşağı ok", "dot": "nokta", "warning": "uyarı", "check": "onay",
              "cross": "çarpı", "flag": "bayrak", "star": "yıldız"}


def describe_rule(rule: dict, label: str, labels: dict[str, str], decimals: int | None = None) -> str:
    """Koşullu biçim kuralı (K-95): "Güvenlik stoğu: < Maksimum stok → zemin #f4cfc4, kalın"."""
    c = rule["condition"]
    op = c["op"]
    if op == "always":
        cond = "kolon biçimi"
    elif c.get("field_ref"):
        cond = f"{CMP[op]} {labels.get(c['field_ref'], c['field_ref'])}"
    elif op in CMP:
        v = c.get("value")
        cond = f"{CMP[op]} " + (tr_number(v, decimals) if isinstance(v, (int, float)) and not isinstance(v, bool)
                                else tr_date(v))
    elif op in RULE_TEXT_OPS:
        cond = f"{RULE_TEXT_OPS[op]} '{c.get('value')}'"
    else:
        cond = describe_filter({**c, "field": rule["field"]}, label, decimals).split(": ", 1)[1]
    f = rule["format"]
    parts = ([f"zemin {f['fill']}"] if f.get("fill") else []) + ([f"yazı {f['color']}"] if f.get("color") else [])         + (["kalın"] if f.get("bold") else []) + ([f"ikon {ICON_NAMES[f['icon']]}"] if f.get("icon") else [])
    return f"{label}: {cond} → {', '.join(parts)}"


def describe_sort(sort: list[dict], labels: dict[str, str]) -> str:
    return ", ".join(f"{labels.get(s['field'], s['field'])} ({'azalan' if s.get('dir') == 'desc' else 'artan'})" for s in sort)


def describe_aggregates(specs: dict[str, dict], labels: dict[str, str]) -> str:
    parts = []
    for f, s in specs.items():
        kind = AGG.get(s["fn"], s["fn"])
        if s["fn"] == "wavg":
            kind += f" (ağırlık: {labels.get(s.get('weight'), s.get('weight'))})"
        parts.append(f"{labels.get(f, f)}: {kind}")
    return ", ".join(parts)
