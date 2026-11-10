"""Tablo listesi (ekran 02 ve 23, K-110, K-130): veri tablosu yok, katalog sabit değerli alt sorguya çevrilir, tablo başına çekim ayarı eklenir.

Böylece ortak tablo kendiliğinden sıralar, süzer, Excel'e aktarır. Alan sayısına etiketli ek alanlar (K-88) sonradan eklenir.
"""
import sqlalchemy as sa

from app.integration.contract import ENTITIES, MASTER_DATA, TRANSACTION_DATA, base_counts, contract_hash
from db.models import metadata

from .definition import ListDefinition

FD = metadata.tables["adm.FieldDefinition"]
BATCH = metadata.tables["adm.ImportBatch"]
CONFIG = metadata.tables["adm.IntegrationEntity"]
USER = metadata.tables["adm.AppUser"]
RUN = metadata.tables["adm.ValidationRun"]
FINDING = metadata.tables["adm.ValidationFinding"]
JOB = metadata.tables["adm.Job"]
VERSION = metadata.tables["adm.DataVersion"]
VERSION_ENTITY = metadata.tables["adm.DataVersionEntity"]
SQL, EXCEL = "SQL", "Excel"
NO_VIEW, RECHECK = "View tanımlı değil", "Yeniden denetle"
LOADED_STATUSES = ("Alındı", "Doğrulandı", "Yüklendi")  # ham veriye alınmış partiler (K-129)


def _text(value: str) -> sa.ColumnElement:
    return sa.literal_column("N'" + value.replace("'", "''") + "'", sa.Unicode)


def _number(value: int) -> sa.ColumnElement:
    return sa.literal_column(str(int(value)), sa.Integer)


def _row(order: int, entity) -> sa.Select:
    field_count, required_count = base_counts(entity.table)
    return sa.select(_number(order).label("Id"), _text(entity.table).label("Entity"), _text(entity.name).label("Name"),
                     _text(entity.data_class).label("EntityClass"), _text(entity.description).label("Description"),
                     _number(entity.version).label("Version"),
                     _number(field_count).label("BaseFieldCount"), _number(required_count).label("RequiredCount"), _text(contract_hash(entity.table)).label("ContractHash"))


_catalog = sa.union_all(*[_row(i, e) for i, e in enumerate(ENTITIES, 1)]).subquery("catalog")
_labelled = (sa.select(sa.func.count()).select_from(FD)
             .where(FD.c.TableName == _catalog.c.Entity, FD.c.FieldName.like("Additional%"), FD.c.Label.is_not(None), FD.c.Label != "")
             .correlate(_catalog).scalar_subquery())

_last_load = (sa.select(sa.func.max(BATCH.c.ReceivedAt))
              .where(BATCH.c.EntityName == _catalog.c.Entity, BATCH.c.Status.in_(LOADED_STATUSES))
              .correlate(_catalog).scalar_subquery())

# Validasyon çipi (K-134, K-139): son tablo içi çalışma; işi düşmüşse Valide edilemedi; bittiyse sonuç bulgulardan
_last_run = (sa.select(RUN.c.Id).where(RUN.c.EntityName == _catalog.c.Entity, RUN.c.Scope == "Tablo içi")
             .order_by(RUN.c.Id.desc()).limit(1).correlate(_catalog).scalar_subquery())
_run_state = sa.select(RUN.c.State).where(RUN.c.Id == _last_run).scalar_subquery()
_job_status = sa.select(JOB.c.Status).select_from(RUN.join(JOB, JOB.c.Id == RUN.c.JobId)).where(RUN.c.Id == _last_run).scalar_subquery()


def _rows(severity: str) -> sa.ScalarSelect:
    return (sa.select(sa.func.count(sa.distinct(FINDING.c.StagingRowId)))
            .where(FINDING.c.EntityName == _catalog.c.Entity, FINDING.c.Severity == severity).correlate(_catalog).scalar_subquery())


_errors, _warnings, _infos = _rows("Hata"), _rows("Uyarı"), _rows("Bilgi")
# Son aktarım (K-151, K-158): tablonun yazıldığı son aktarım (eşik ya da veri gelmedi notuyla yazılmayan sayılmaz; sentetik yükleme aktarım değildir)
_last_version = (sa.select(VERSION_ENTITY.c.DataVersionId)
                 .select_from(VERSION_ENTITY.join(VERSION, VERSION.c.Id == VERSION_ENTITY.c.DataVersionId))
                 .where(VERSION_ENTITY.c.EntityName == _catalog.c.Entity, VERSION_ENTITY.c.NewCount.is_not(None),
                        sa.func.coalesce(VERSION.c.IsSynthetic, sa.false()) == sa.false())
                 .order_by(VERSION_ENTITY.c.DataVersionId.desc()).limit(1).correlate(_catalog).scalar_subquery())
_last_transfer = sa.select(VERSION.c.CreatedAt).where(VERSION.c.Id == _last_version).scalar_subquery()
_last_transfer_type = sa.select(VERSION.c.LoadType).where(VERSION.c.Id == _last_version).scalar_subquery()
# Yeni veri: son aktarımdan sonra gelen veriye alınmış yükleme (hiç aktarılmadıysa herhangi bir yükleme)
_new_data = sa.cast(sa.case((sa.and_(_last_load.is_not(None), sa.or_(_last_transfer.is_(None), _last_load > _last_transfer)), 1), else_=0), sa.Boolean)
# Gelen verinin özeti (K-154; 5.5'ten öne alındı): güncel satır sayısı tablo başına
_total = sa.case(*[(_catalog.c.Entity == _text(e.table),
                    sa.select(sa.func.count()).select_from(metadata.tables[f"stg.{e.table}"])
                    .where(metadata.tables[f"stg.{e.table}"].c.IsCurrent == sa.true()).scalar_subquery()) for e in ENTITIES], else_=0)
_validation = sa.case(
    (sa.and_(_run_state.in_(["Sırada", "Kurallar çalışıyor", "Valide ediliyor"]), _job_status.is_not(None), _job_status.not_in(["Sırada", "Çalışıyor"])), _text("Valide edilemedi")),
    (_run_state == "Bitti", sa.case((_errors > 0, _text("Hatalı")), (_warnings > 0, _text("Uyarılı")), else_=_text("Geçti"))),
    else_=_run_state).label("Validation")
_method = sa.func.coalesce(CONFIG.c.Method, _text(EXCEL)).label("Method")
_is_sql = sa.func.coalesce(CONFIG.c.Method, _text(EXCEL)) == _text(SQL)
_warning = sa.case((sa.and_(_is_sql, CONFIG.c.ViewName.is_(None)), _text(NO_VIEW)),
                   (sa.and_(_is_sql, CONFIG.c.LastContractHash.is_not(None), CONFIG.c.LastContractHash != _catalog.c.ContractHash), _text(RECHECK)),
                   else_=sa.null()).label("Warning")
_match = sa.case((CONFIG.c.MatchedColumns.is_not(None),
                  sa.cast(CONFIG.c.MatchedColumns, sa.Unicode(10)) + _text(" / ") + sa.cast(CONFIG.c.ExpectedColumns, sa.Unicode(10))), else_=sa.null()).label("ColumnMatch")

SOURCE = (sa.select(_catalog.c.Id, _catalog.c.Id.label("CatalogOrder"), _catalog.c.Entity, _catalog.c.Name, _catalog.c.EntityClass, _catalog.c.Description, _catalog.c.Version,
                    (_catalog.c.BaseFieldCount + _labelled).label("FieldCount"), _catalog.c.RequiredCount, _last_load.label("LastLoadAt"),
                    _validation, _errors.label("ValidationErrors"), _warnings.label("ValidationWarnings"),
                    _total.label("TotalRows"), _errors.label("ErrorRows"), _warnings.label("WarningRows"), _infos.label("InfoRows"),
                    _last_transfer.label("LastTransferAt"), _last_transfer_type.label("LastTransferType"), _new_data.label("HasNewData"),
                    _method, sa.cast(sa.func.coalesce(CONFIG.c.IsPullEnabled, sa.literal_column("1")), sa.Boolean).label("IsPullEnabled"), CONFIG.c.ViewName, _warning, _match,
                    CONFIG.c.LastCheckStatus, CONFIG.c.LastCheckMessage, CONFIG.c.LastPullStatus, CONFIG.c.LastPullMessage, CONFIG.c.LastPullAt,
                    CONFIG.c.DisabledReason, CONFIG.c.DisabledAt, sa.func.coalesce(USER.c.FullName, USER.c.UserName).label("DisabledByName"))
          .select_from(_catalog.outerjoin(CONFIG, CONFIG.c.EntityName == _catalog.c.Entity).outerjoin(USER, USER.c.Id == CONFIG.c.DisabledBy)).subquery("data_entities"))

FIELDS = ("Name", "Method", "IsPullEnabled", "Validation", "TotalRows", "ErrorRows", "WarningRows", "InfoRows", "LastLoadAt", "LastTransferAt", "HasNewData",
          "EntityClass", "Description", "Version", "FieldCount", "RequiredCount", "CatalogOrder", "LastTransferType", "Entity", "ViewName")
# Varsayılan görünümde gizli: teknik alanlar ve şablon bilgisi (ekran genişliğe sığsın; Alanlar panelinden açılır, K-158)
HIDDEN_FIELDS = ("Entity", "ViewName", "LastTransferType", "EntityClass", "Description", "Version", "FieldCount", "RequiredCount")
PULL_KEYS = ("Method", "IsPullEnabled", "ViewName", "Warning", "DisabledReason", "DisabledByName", "DisabledAt")

DATA_ENTITIES = ListDefinition(
    name="data-entities",
    table="stg.*",
    title="Tablolar",
    file_slug="tablolar",
    function=2,  # Excel şablonu indirme (K-100)
    versioned=False,
    source=SOURCE,
    key_fields=("Entity", "Name", "Version", *PULL_KEYS, "ValidationErrors", "ValidationWarnings", "LastTransferType"),  # satır menüsü ve ipucu bunları okur, kolon gizli olsa da
    fields=FIELDS,
    default_visible=tuple(f for f in FIELDS if f not in HIDDEN_FIELDS),
    default_sort=(("CatalogOrder", "asc"),),  # referans verisinden işlem verisine (docs/03)
    labels={"Method": "Yöntem", "IsPullEnabled": "Çekim", "ViewName": "View", "Name": "Tablo", "EntityClass": "Kategori", "Description": "Açıklama", "Version": "Sürüm", "FieldCount": "Toplam alan", "LastLoadAt": "Son yükleme zamanı", "RequiredCount": "Zorunlu alan",
            "Entity": "Teknik tablo adı", "CatalogOrder": "Yükleme sırası", "Validation": "Validasyon",
            "TotalRows": "Toplam satır", "ErrorRows": "Hatalı", "WarningRows": "Uyarılı", "InfoRows": "Bilgi",
            "LastTransferAt": "Son aktarım", "LastTransferType": "Son aktarım türü", "HasNewData": "Yeni veri"},
    values={"EntityClass": [MASTER_DATA, TRANSACTION_DATA], "Method": [EXCEL, SQL], "LastTransferType": ["Tam", "Kısmi"],
            "Validation": ["Sırada", "Kurallar çalışıyor", "Valide ediliyor", "Geçti", "Uyarılı", "Hatalı", "Valide edilemedi"]},
    notes={"LastLoadAt": "Satırların gelen veriye alındığı zaman; aktarım ayrı adımdır.",
           "TotalRows": "Gelen verinin güncel satır sayısı.", "ErrorRows": "Validasyonda Hata bulunan satır sayısı; bu satırlar aktarılmaz.",
           "WarningRows": "Validasyonda Uyarı bulunan satır sayısı.", "InfoRows": "Validasyonda Bilgi bulunan satır sayısı.",
           "Method": "Çekim yöntemi. Excel'den yükleme yöntemden bağımsız her zaman açıktır.",
           "IsPullEnabled": "Yalnız SQL çekimini durdurur; Excel'den yükleme açık kalır.",
           "Validation": "Gelen verinin validasyonu; çipe tıklayınca bulgular açılır.",
           "LastTransferAt": "Tablonun kullanılan veriye son yazıldığı aktarım (tam ya da kısmi).",
           "HasNewData": "Son aktarımdan sonra veri geldi; aktarılınca kullanılan veriye geçer."},
)

INTEGRATION_FIELDS = ("Name", "Method", "ViewName", "ColumnMatch", "LastPullStatus", "LastPullAt", "CatalogOrder", "Entity")

INTEGRATION_ENTITIES = ListDefinition(
    name="integration-entities",
    table="stg.*",
    title="Entegrasyon tabloları",
    file_slug="entegrasyon-tablolari",
    function=91,  # Entegrasyon tanımı (K-130)
    versioned=False,
    source=SOURCE,
    key_fields=("Entity", "Name", "Method", "ViewName", "LastCheckStatus", "LastCheckMessage", "LastPullMessage"),
    fields=INTEGRATION_FIELDS,
    default_visible=("Name", "Method", "ViewName", "ColumnMatch", "LastPullStatus", "LastPullAt"),
    default_sort=(("CatalogOrder", "asc"),),
    labels={"Name": "Tablo", "Method": "Yöntem", "ViewName": "Kaynak", "ColumnMatch": "Alan uyumu", "LastPullStatus": "Son durum",
            "LastPullAt": "Son okuma", "CatalogOrder": "Yükleme sırası", "Entity": "Teknik tablo adı"},
    values={"Method": [EXCEL, SQL]},
    notes={"ColumnMatch": "Sözleşme kolonlarından view'da bulunanlar.", "LastPullAt": "View'ın son okunduğu zaman."},
)
