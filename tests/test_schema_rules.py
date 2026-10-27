"""Şema kuralları (docs → db/generate.py). K-80: değer listesindeki değerler ve varsayılan alan uzunluğuna sığar."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("generate", ROOT / "db" / "generate.py")
generate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generate)


def test_value_lists_fit_field_lengths():
    assert generate.length_problems(generate.build_spec()) == []


def test_value_list_parsing():
    assert generate.value_list("Takvim günü | İş günü") == ["Takvim günü", "İş günü"]
    assert generate.value_list("Fasonda: İş yeri | Tedarik süresi") == ["İş yeri", "Tedarik süresi"]
    assert generate.value_list("Kendi | Müşteri (müşteri temin malzemesi)") == ["Kendi", "Müşteri"]
    assert generate.value_list("Gece senaryosu | Çalışma | Termin sorgusu …") == ["Gece senaryosu", "Çalışma",
                                                                                   "Termin sorgusu"]
    assert generate.value_list("Kayıt kimliği") == []


def test_length_check_detects_overflow():
    fake = [{"schema": "param", "name": "PriorityRule", "fields": [
        {"name": "Direction", "type": "nvarchar(4)", "desc": "Artan | Azalan", "default": "Artan"}]}]
    problems = generate.length_problems(fake)
    assert len(problems) == 3 and all("PriorityRule.Direction" in p for p in problems)
