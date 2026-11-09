"""Kirli hâlde veri kurallarıyla çözülen örnekler ve demo kuralları (docs/11, K-141).

Örnek satırlar ("R-" ile başlayan anahtarlar) kurallar yokken validasyon bulgusu verir; demo kurallarıyla bulgu kalkar.
Kurulumda varsayılan kural yoktur: demo kuralları yalnız `python -m app.data.synthetic rules` ile geliştirme ve demo
veritabanına yazılır. Bir formül kuralında bölen bazı satırlarda sıfırdır (QtyPerBox = 0 örneği): o satırda hücre değişmez.
"""
import sqlalchemy as sa
from sqlalchemy.orm import Session

from .examples import Examples

# Kurallar, kayıt sözleşmesinin biçiminde (PUT /api/data-rules, docs/08)
DEMO_RULES: list[dict] = [
    {"entity": "Location", "name": "Tesis bayrağı", "target": "IsFactory", "mode": "Yalnız boşsa",
     "result": {"kind": "Değer", "value": "1"}, "groups": [[{"field": "Type", "operator": "=", "value": "PLANT"}]]},
    {"entity": "Location", "name": "Depo bayrağı", "target": "IsDepot", "mode": "Yalnız boşsa",
     "result": {"kind": "Değer", "value": "1"}, "groups": [[{"field": "Type", "operator": "=", "value": "WAREHOUSE"}]]},
    {"entity": "Customer", "name": "Aktif müşteri", "target": "IsActive", "mode": "Yalnız boşsa", "result": {"kind": "Değer", "value": "1"}, "groups": []},
    {"entity": "Stock", "name": "Serbest stok kullanılabilir", "target": "IsAvailable", "mode": "Yalnız boşsa",
     "result": {"kind": "Değer", "value": "1"}, "groups": [[{"field": "Status", "operator": "=", "value": "Serbest"}]]},
    {"entity": "Stock", "name": "Kalitedeki stok", "target": "IsInQuality", "mode": "Yalnız boşsa",
     "result": {"kind": "Değer", "value": "1"}, "groups": [[{"field": "Status", "operator": "=", "value": "Kalitede"}]]},
    {"entity": "Stock", "name": "Bloke stok", "target": "IsBlocked", "mode": "Yalnız boşsa",
     "result": {"kind": "Değer", "value": "1"}, "groups": [[{"field": "Status", "operator": "=", "value": "Bloke"}]]},
    {"entity": "SalesOrderLine", "name": "Teklif satırı", "target": "IsQuote", "mode": "Yalnız boşsa",
     "result": {"kind": "Değer", "value": "1"}, "groups": [[{"field": "Type", "operator": "=", "value": "Teklif"}]]},
    {"entity": "PurchaseOrderLine", "name": "Teyit tarihi istenen tarihten", "target": "ConfirmedDate", "mode": "Yalnız boşsa",
     "result": {"kind": "Formül", "source_field": "RequestedDate", "operator": "+", "operand_value": "3"}, "groups": []},
    {"entity": "Material", "name": "Paletteki kutu sayısı", "target": "AdditionalNumber1", "mode": "Her zaman",
     "result": {"kind": "Formül", "source_field": "QtyPerPallet", "operator": "÷", "operand_field": "QtyPerBox"}, "groups": []},
]


def add_rule_examples(x: Examples, loc: str) -> None:
    """Kuralla çözülen satırlar: kurallar yokken beklenen bulgular, demo kurallarıyla hiçbiri."""
    x.add("Location", x.base("Location", Code=loc), ["LOC.NO_FLAG"], with_rules=[], Code="R-LOC-1", Name="Kuralla tesis", Type="PLANT",
          IsFactory=None, IsDepot=None, IsSubcontractor=None)
    customer = x.base("Customer", **{"IsActive": True})
    x.add("Customer", customer, ["STR.REQUIRED"], with_rules=[], Code="R-CUS-1", Name="Kuralla aktif müşteri", IsActive=None)
    stock = x.base("Stock", Status="Serbest", Warehouse="ANA")
    x.add("Stock", stock, ["STK.STATUS_FLAGS"], with_rules=[], LotNo="R-LOT-1", IsAvailable=None, IsInQuality=None, IsBlocked=None)
    quote = x.base("SalesOrderLine", Type="Teklif")
    x.add("SalesOrderLine", quote, [], with_rules=[], OrderNo="R-SO-1", IsQuote=None)
    po = x.base("PurchaseOrderLine")
    x.add("PurchaseOrderLine", po, [], with_rules=[], PurchaseOrderNo="R-PO-1", ConfirmedDate=None)
    # Sıfıra bölme (K-141): kutu içi miktar 0 olan satırda "Paletteki kutu sayısı" hücreyi değiştirmez; 4 olan satırda 40 ÷ 4 = 10
    mat = {**x.base("Material", Code="HAM-001"), "MinLot": None, "MaxLot": None, "LotMultiple": None, "SafetyStock": None, "StockCoverageDays": None,
           "MaxStock": None, "ScrapRatio": None}
    x.add("Material", mat, ["MAT.ZERO_PACK"], with_rules=["MAT.ZERO_PACK"], Code="R-MAT-1", Name="Kutu içi miktarı sıfır", QtyPerBox=0.0, QtyPerPallet=40.0)
    x.add("Material", mat, [], with_rules=[], Code="R-MAT-2", Name="Kutu içi miktarı dört", QtyPerBox=4.0, QtyPerPallet=40.0)


def install(session: Session, user_id: int | None = None) -> int:
    """Demo kurallarını yazar: aynı adlı kural yenisiyle değişir, ötekilere dokunulmaz. Commit eder; yazılan kural sayısı."""
    from app.api.services.data_rules import _definition, _renumber, _values, _write_conditions
    from app.validation import texts
    from app.validation.engine import utcnow
    from app.validation.rules_step import CONDITION, EFFECT, RULE

    for change in DEMO_RULES:
        entity = change["entity"]
        old = session.execute(sa.select(RULE.c.Id).where(RULE.c.EntityName == entity, RULE.c.Name == change["name"])).scalar()
        if old is not None:
            session.execute(sa.delete(EFFECT).where(EFFECT.c.DataRuleId == old))
            session.execute(sa.delete(CONDITION).where(CONDITION.c.DataRuleId == old))
            session.execute(sa.delete(RULE).where(RULE.c.Id == old))
        d = _definition(session, entity, change, None)
        seq = (session.execute(sa.select(sa.func.max(RULE.c.Seq)).where(RULE.c.EntityName == entity)).scalar() or 0) + 1
        rule_id = session.execute(sa.insert(RULE).values(EntityName=entity, Name=change["name"], Seq=seq, IsActive=True, UpdatedBy=user_id,
                                                         UpdatedAt=utcnow(), **_values(d)).returning(RULE.c.Id)).scalar_one()
        _write_conditions(session, rule_id, d["groups"])
    for entity in sorted({r["entity"] for r in DEMO_RULES}):
        _renumber(session, entity)  # sıra her zaman 1, 2, 3… (K-143)
    texts.refresh(session)
    session.commit()
    return len(DEMO_RULES)
