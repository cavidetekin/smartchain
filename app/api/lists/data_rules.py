"""Veri kuralları listesi (ekran 04, fonksiyon 16; K-141, K-142, K-143): Tablo ilk kolon; tablo başına sırayla; Koşul ve Sonuç okunur cümle
(güncel etiketle, texts.refresh), Durum son çalışma. Sıra tabloda her zaman 1, 2, 3… (kayıtta yeniden numaralanır; gösterim de satır numarasıdır)."""
import sqlalchemy as sa

from app.integration.contract import ENTITIES
from app.validation import data_rule
from db.models import metadata

from .definition import ListDefinition

RULE = metadata.tables["adm.DataRule"]

_shown_seq = sa.cast(sa.func.row_number().over(partition_by=RULE.c.EntityName, order_by=(RULE.c.Seq, RULE.c.Id)), sa.Integer).label("Seq")
PASSIVE, NOT_APPLIED = "Pasif", "Uygulanmadı"
# Durum her zaman dolu (K-145): pasif kural "Pasif", hiç çalışmamış "Uygulanmadı", ötekiler son çalışma (Çalıştı / Çalışmadı)
_state = sa.case((RULE.c.IsActive == sa.false(), PASSIVE), (RULE.c.LastRunStatus.is_(None), NOT_APPLIED), else_=RULE.c.LastRunStatus).label("RunState")
_source = (sa.select(RULE.c.Id, RULE.c.EntityName, _shown_seq, RULE.c.Name.label("RuleName"), RULE.c.ConditionText, RULE.c.ResultText,
                     RULE.c.ApplyMode, RULE.c.IsActive, _state, RULE.c.LastRunMessage, RULE.c.LastRunAt, RULE.c.TargetField,
                     sa.case(*[(RULE.c.EntityName == e.table, e.name) for e in ENTITIES], else_=RULE.c.EntityName).label("EntityLabel"),
                     sa.case(*[(RULE.c.EntityName == e.table, i) for i, e in enumerate(ENTITIES, 1)], else_=99).label("EntityOrder"))
           .subquery("data_rules"))

FIELDS = ("EntityLabel", "Seq", "RuleName", "ConditionText", "ResultText", "ApplyMode", "IsActive", "RunState", "LastRunAt", "EntityOrder", "EntityName")

DATA_RULES = ListDefinition(
    name="data-rules", table="adm.DataRule", title="Veri kuralları", file_slug="veri-kurallari", function=16, versioned=False,
    source=_source,
    fields=FIELDS,
    default_visible=("EntityLabel", "Seq", "RuleName", "ConditionText", "ResultText", "ApplyMode", "IsActive", "RunState"),
    default_sort=(("EntityOrder", "asc"), ("Seq", "asc")),
    key_fields=("Id", "EntityName", "Seq", "IsActive", "LastRunMessage", "LastRunAt"),
    labels={"Seq": "Sıra", "RuleName": "Kural", "ConditionText": "Koşul", "ResultText": "Sonuç", "ApplyMode": "Seçenek", "IsActive": "Aktif",
            "RunState": "Durum", "EntityLabel": "Tablo", "LastRunAt": "Son çalışma", "EntityOrder": "Yükleme sırası", "EntityName": "Teknik tablo adı"},
    values={"ApplyMode": list(data_rule.MODES), "RunState": [data_rule.RAN, data_rule.FAILED, PASSIVE, NOT_APPLIED], "EntityLabel": [e.name for e in ENTITIES]},
    notes={"RunState": "Çalıştı: son uygulamada çalıştı (ipucunda zaman). Çalışmadı: nedeni ipucunda. Pasif: aktifliği kapalı. Uygulanmadı: henüz hiç uygulanmadı.",
           "ApplyMode": "Yalnız boşsa: hedef doluysa dokunulmaz. Her zaman: koşula uyan her satırda yazılır."},
)
