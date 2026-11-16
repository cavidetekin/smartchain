"""Veri kalitesi listeleri (ekran 05, fonksiyon 20; K-174): uyarılar ve detay kartının Talep zinciri, liste sözleşmesiyle. Sürümsüz.

Uyarılar: sekmeler `Importance` ve `State` süzgeciyle (yalnız süzmede). Kolonlar Durum, Tablo, Kayıt, Mesaj, Tespit tarihi; gizli Kontrol (kural
ya da Smartchain kontrolünün adı, gruplamak için) ve Gerekçe. Yok sayılan sekmesi ayrı liste (`data-quality-ignored`): aynı kaynak, Standart
görünümünde Gerekçe açık; görünümleri sekmeye özgü. Sıralama Durum (Yeni önce), sonra Tespit tarihi. Satırda Kayda git hedefi (`TargetList`: Ana
veri ya da İşlem verisi listesi, `RecordKey`) ve Kural oluştur'un hedef alanı (`FixField`).
"""
import sqlalchemy as sa

from app.integration.contract import ENTITIES
from app.quality import STATE_IGNORED, STATE_NEW, STATE_OPEN
from db.models import metadata

from .definition import ListDefinition
from .master_data import BY_NAME

W = metadata.tables["adm.DataQualityWarning"]
PATH = metadata.tables["adm.DemandChainPath"]
NAMES = {e.table: e.name for e in ENTITIES}
TARGETS = {}  # uyarı çıkabilen tablo (entegrasyon tablosu) → Kayda git'in listesi; liste kaydı Id ile süzer
for _d in BY_NAME.values():
    if _d.table_name in NAMES:
        TARGETS.setdefault(_d.table_name, _d.name)

_source = sa.select(
    W.c.Id, W.c.State, W.c.Importance, W.c.EntityName, W.c.RecordKey, W.c.RecordLabel, W.c.RuleName, W.c.Message, W.c.FirstSeenAt,
    W.c.IgnoreReason, W.c.FixField, W.c.CheckCode, W.c.Source,
    sa.case(*[(W.c.EntityName == t, n) for t, n in NAMES.items()], else_=W.c.EntityName).label("EntityLabel"),
    sa.case(*[(W.c.EntityName == t, n) for t, n in TARGETS.items()], else_=sa.null()).label("TargetList"),
    sa.case((W.c.State == STATE_NEW, 1), (W.c.State == STATE_OPEN, 2), else_=3).label("StateOrder"),
).subquery("data_quality_warnings")

_WARNING_LIST = dict(
    table="adm.DataQualityWarning", title="Veri kalitesi", file_slug="veri-kalitesi", function=20, versioned=False, source=_source,
    default_sort=(("StateOrder", "asc"), ("FirstSeenAt", "desc")),
    labels={"State": "Durum", "EntityLabel": "Tablo", "RecordLabel": "Kayıt", "RuleName": "Kontrol", "Message": "Mesaj", "FirstSeenAt": "Tespit tarihi",
            "IgnoreReason": "Gerekçe", "CheckCode": "Kod", "StateOrder": "Durum sırası", "Importance": "Önem", "EntityName": "Teknik tablo adı",
            "Id": "Uyarı no"},
    values={"State": [STATE_NEW, STATE_OPEN, STATE_IGNORED], "Importance": ["Yüksek", "Normal"], "EntityLabel": sorted(set(NAMES.values()))},
    server_values=frozenset({"RuleName", "CheckCode", "Id"}),
    filter_only=("Importance", "EntityName", "Id"),  # Id: çoklu seçimde kart (K-171)
    key_fields=("Id", "EntityName", "RecordKey", "FixField", "State", "Importance", "TargetList", "Source"),
)
DATA_QUALITY_WARNINGS = ListDefinition(
    name="data-quality-warnings", **_WARNING_LIST,
    fields=("State", "EntityLabel", "RecordLabel", "Message", "FirstSeenAt", "RuleName", "IgnoreReason", "CheckCode", "StateOrder"),
    default_visible=("State", "EntityLabel", "RecordLabel", "Message", "FirstSeenAt"))
DATA_QUALITY_IGNORED = ListDefinition(  # Gerekçe Mesaj'ın yanında
    name="data-quality-ignored", **_WARNING_LIST,
    fields=("State", "EntityLabel", "RecordLabel", "Message", "IgnoreReason", "FirstSeenAt", "RuleName", "CheckCode", "StateOrder"),
    default_visible=("State", "EntityLabel", "RecordLabel", "Message", "IgnoreReason", "FirstSeenAt"))

DATA_QUALITY_DEMAND_CHAIN = ListDefinition(
    name="data-quality-demand-chain", table="adm.DemandChainPath", title="Talep zinciri", file_slug="talep-zinciri", function=20, versioned=False,
    source=sa.select(PATH.c.Id, PATH.c.WarningId, PATH.c.DemandLabel, PATH.c.DemandType, PATH.c.MaterialPath, PATH.c.DemandDate, PATH.c.OpenQuantity)
    .subquery("demand_chain"),
    fields=("DemandLabel", "DemandType", "MaterialPath", "DemandDate", "OpenQuantity"),
    default_visible=("DemandLabel", "DemandType", "MaterialPath", "DemandDate", "OpenQuantity"),
    default_sort=(("DemandDate", "asc"), ("DemandLabel", "asc")),
    labels={"DemandLabel": "Talep", "DemandType": "Talep tipi", "MaterialPath": "Malzeme yolu", "DemandDate": "Talep tarihi", "OpenQuantity": "Açık miktar",
            "WarningId": "Uyarı"},
    values={"DemandType": ["Satış siparişi", "Tahmin"]},
    decimals={"OpenQuantity": 2},
    server_values=frozenset({"WarningId"}),
    filter_only=("WarningId",),
)
