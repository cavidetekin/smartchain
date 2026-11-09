"""Kirli veri (docs/11, K-137, K-141): her hazır kural en az bir bulgu verir; hiçbir bulgu beklenmeyen satırda çıkmaz;
demo veri kurallarıyla kuralla çözülen satırların bulguları kalkar."""
import json
from datetime import date, datetime

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.api.permissions import KEY_USER
from app.data.synthetic.rules import DEMO_RULES, install
from app.validation import catalog as cat
from app.validation import engine as validation_engine

from auth_helpers import ensure_user
from auth_helpers import auth
from validation_helpers import clean, new_client, run_validations, upload_dirty

pytestmark = pytest.mark.db

SEP = " · "
H_RULES = {"H3": ["ALL.NEGATIVE"]}


def _key_text(value) -> str:
    if isinstance(value, str) and len(value) == 10 and value[4] == "-" and value[7] == "-":
        value = date.fromisoformat(value)  # manifest tarihi ISO yazar
    if isinstance(value, (date, datetime)):
        return value.strftime("%d.%m.%Y")
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, bool):
        return "1" if value else "0"
    return str(value)


def row_key(key: dict) -> str:
    return SEP.join(_key_text(v) for v in key.values() if v not in (None, ""))[:200]


@pytest.fixture(scope="module")
def validated(db_engine, tmp_path_factory):
    folder = tmp_path_factory.mktemp("kirli")
    clean(db_engine)
    with db_engine.begin() as c:
        user = ensure_user(c, "pytest.dogrulama.key", KEY_USER, "Ad")
    client = new_client()
    upload_dirty(client, user, folder)
    jobs = run_validations(db_engine)
    manifest = json.loads((folder / "beklenen-hatalar.json").read_text(encoding="utf-8"))
    with db_engine.connect() as c:
        found = c.execute(sa.text("SELECT f.EntityName, r.Code, f.RowKey, f.Severity, f.Message FROM adm.ValidationFinding f "
                                  "JOIN adm.ValidationRule r ON r.Id = f.ValidationRuleId")).all()
    yield {"jobs": jobs, "manifest": manifest, "found": found, "folder": folder, "client": client, "user": user, "engine": db_engine}
    clean(db_engine)


def test_every_builtin_rule_has_a_finding(validated):
    codes = {code for _t, code, *_ in validated["found"]}
    builtin = {r.code for r in cat.catalog() if r.kind == cat.BUILTIN_KIND}
    assert sorted(builtin - codes) == []


def _compare(manifest: dict, found, field: str = "rules") -> None:
    """Bulgular beklenenle birebir: beklenmeyen satırda bulgu yok, beklenen her kural bulgu verir. field: rules ya da rules_with_demo."""
    expected: list[tuple[str, set[str], set[str]]] = []  # tablo, anahtarın parçaları, kurallar
    for e in manifest["errors"]:
        rules = e.get(field, e.get("rules")) if e["code"] == "V" else (e.get("rules") or H_RULES.get(e["code"], []))
        if not rules:
            continue
        parts = row_key(e["key"]).split(SEP) if e["code"] == "V" else [p for p in e["key"].split("|") if p]
        expected.append((e.get("table") or e["file"][:-5], set(parts), set(rules)))

    def wanted(table: str, key: str | None, code: str) -> bool:
        have = set((key or "").split(SEP))
        return any(t == table and parts <= have and code in rules for t, parts, rules in expected)

    unexpected = [(t, code, key, msg) for t, code, key, _s, msg in found if not wanted(t, key, code)]
    assert unexpected == [], "\n".join(map(str, unexpected))
    missing = [(t, sorted(parts), r) for t, parts, rules in expected for r in rules
               if not any(tt == t and parts <= set((key or "").split(SEP)) and code == r for tt, code, key, *_ in found)]
    assert missing == [], "\n".join(map(str, missing))


def test_no_finding_on_unexpected_row(validated):
    _compare(validated["manifest"], validated["found"])


def test_changed_batch_is_applied_to_the_current_state(validated):
    """Ekle / güncelle partisi (docs/11, K-133): yalnız bir satır gelir, küme kuralı tablonun güncel ve tam hâline bakar."""
    client, user, eng, folder = validated["client"], validated["user"], validated["engine"], validated["folder"]
    batch = validated["manifest"]["changed_batch"]
    key = batch["key"]
    r = client.post("/api/imports/MaterialSupplier?mode=Değişen", content=(folder / batch["file"]).read_bytes(),
                    headers={**auth(user), "X-File-Name": "MaterialSupplier.xlsx"})
    assert r.status_code == 200, r.text
    assert client.post(f"/api/imports/{r.json()['batch_id']}/continue", headers=auth(user)).status_code == 200
    run_validations(eng)
    with eng.connect() as c:
        quotas = c.execute(sa.text("SELECT SupplierCode, QuotaRatio FROM stg.MaterialSupplier WHERE IsCurrent = 1 AND MaterialCode = :m"), {"m": key["MaterialCode"]}).all()
        hits = c.execute(sa.text("SELECT f.RowKey FROM adm.ValidationFinding f JOIN adm.ValidationRule r ON r.Id = f.ValidationRuleId "
                                 "WHERE r.Code = N'MS.QUOTA_SUM' AND f.RowKey LIKE :k"), {"k": f"%{key['MaterialCode']}%"}).scalars().all()
    assert sorted((s, float(q)) for s, q in quotas if q is not None) == sorted([(key["SupplierCode"], 0.5), (next(s for s, q in quotas if s != key["SupplierCode"]), 0.7)])
    assert len(hits) == 2


def test_demo_rules_clear_their_findings(validated):
    """Demo veri kuralları (docs/11, K-141): kuralla çözülen satırların bulguları kalkar; ham katman değişmez; bölen sıfırsa hücre değişmez."""
    eng = validated["engine"]
    with Session(eng) as s:
        assert install(s) == len(DEMO_RULES)
        validation_engine.enqueue_group(s, sorted({r["entity"] for r in DEMO_RULES}), validation_engine.TRIGGER_RULES, None)
    run_validations(eng)
    with eng.connect() as c:
        found = c.execute(sa.text("SELECT f.EntityName, r.Code, f.RowKey, f.Severity, f.Message FROM adm.ValidationFinding f "
                                  "JOIN adm.ValidationRule r ON r.Id = f.ValidationRuleId")).all()
        failed = c.execute(sa.text("SELECT Name FROM adm.DataRule WHERE LastRunStatus <> N'Çalıştı' OR LastRunStatus IS NULL")).scalars().all()
        po = c.execute(sa.text("SELECT p.ConfirmedDate, s.ConfirmedDate, p.RequestedDate FROM prc.PurchaseOrderLine p "
                               "JOIN stg.PurchaseOrderLine s ON s.StagingRowId = p.StagingRowId WHERE p.PurchaseOrderNo = N'R-PO-1'")).one()
        pack = dict(c.execute(sa.text("SELECT Code, AdditionalNumber1 FROM prc.Material WHERE Code IN (N'R-MAT-1', N'R-MAT-2')")).all())
        traced = c.execute(sa.text("SELECT COUNT(*) FROM adm.DataRuleEffect")).scalar()
    assert failed == []
    batch = validated["manifest"]["changed_batch"]  # önceki testin Ekle / güncelle partisi: iki tedarikçide kota toplamı (K-133)
    changed = {"code": "V", "table": "MaterialSupplier", "key": {k: batch["key"][k] for k in ("LocationCode", "MaterialCode")}, "rules_with_demo": batch["rules"]}
    _compare({**validated["manifest"], "errors": [*validated["manifest"]["errors"], changed]}, found, "rules_with_demo")
    assert po[1] is None and (po[0] - po[2]).days == 3  # ham katman boş kalır, işlenmiş katmanda istenen + 3 gün
    assert pack == {"R-MAT-1": None, "R-MAT-2": 10} and traced > 0  # bölen sıfırsa hücre değişmez (K-141)
