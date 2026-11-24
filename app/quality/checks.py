"""Smartchain'de yönetilen veriden gelen veri kalitesi kontrolleri (K-174, kaynak b). Validasyon kuralları ekranında görünmez, kapatılamaz.

Kapasite kontrolleri (K-185 H) yalnız Baz senaryoya bakar: kapasitesi tanımsız kaynak (ne kendisinde ne grubunda geçerli çalışma düzeni) ve
grupları çelişen kaynak (birden fazla gruba üye, kendi kaydı yok, gruplar farklı değer veriyor). Malzeme blokajı: kapanan malzemeye girilmiş blokaj (K-193).
"""
from collections.abc import Callable
from dataclasses import dataclass

import sqlalchemy as sa

from db.models import metadata


@dataclass(frozen=True)
class SmartchainCheck:
    code: str
    table: str                # core tablosu
    title: str                # listede "Kural"
    message: str              # mesajın başı; sonuna kaydın kodu
    where: Callable[[sa.Table], sa.ColumnElement]
    fix_field: str | None = None  # Kural oluştur'un hedefi; Smartchain alanı veri kuralıyla doldurulamaz
    # Bu kontrole özel önem (K-185): verilirse genel kural (talep zinciri) yerine "Yüksek = zincirde VE bu koşul"; değilse Normal
    high_when: Callable[[sa.Table], sa.ColumnElement] | None = None
    # Kapanmış kayıtlara bakar (K-188): güncel veride olmayan kaydın son versiyonu (ör. kapanan kaynağa girilmiş kapasite kaydı)
    closed: bool = False
    # Önem yalnız `high_when` koşuluna bakar, talep zincirine bakmaz (K-198)
    high_only: bool = False


def _active(t) -> sa.ColumnElement:
    return sa.or_(t.c.IsActive.is_(None), t.c.IsActive == sa.true())


def _in_critical_group(t) -> sa.ColumnElement:
    """Kaynak en az bir aktif kritik gruba üye (K-180: kritiklik kaynak grubundadır)."""
    m = metadata.tables["core.ResourceGroupMember"].alias("sc_member")
    g = metadata.tables["core.ResourceGroup"].alias("sc_group")
    return sa.exists().where(m.c.ResourceId == t.c.Id, m.c.VersionTo.is_(None), g.c.Id == m.c.ResourceGroupId, g.c.VersionTo.is_(None),
                             _active(g), g.c.IsCritical == sa.true())


SCENARIO = metadata.tables["param.ScenarioDefinition"]
MEMBER = metadata.tables["core.ResourceGroupMember"]


def _base() -> sa.ScalarSelect:
    return sa.select(SCENARIO.c.Id).where(SCENARIO.c.IsBase == sa.true()).scalar_subquery()


def _today() -> sa.ColumnElement:
    return sa.cast(sa.func.sysdatetime(), sa.Date)


def _valid(w, ahead: bool = False) -> sa.ColumnElement:
    """Baz'ın geçerli kaydı. ahead: bugün ya da ileride geçerli (bitmemiş); değilse bugünü kapsayan."""
    started = sa.true() if ahead else w.c.ValidFrom <= _today()
    return sa.and_(w.c.ScenarioDefinitionId == _base(), w.c.BaseRowId.is_(None), w.c.IsValid == sa.true(), started,
                   sa.or_(w.c.ValidTo.is_(None), w.c.ValidTo >= _today()))


def _no_work_pattern(t) -> sa.ColumnElement:
    """Ne kendisinde ne üye olduğu gruplardan birinde geçerli (bitmemiş) çalışma düzeni olan kaynak (K-185 H); gruba üye olmayan kaynak dahil."""
    pattern = metadata.tables["param.WorkPattern"]
    own, grouped, m = pattern.alias("sc_wp_own"), pattern.alias("sc_wp_group"), MEMBER.alias("sc_wp_member")
    has_own = sa.exists().where(_valid(own, ahead=True), own.c.ResourceId == t.c.Id)
    in_group = sa.exists().where(m.c.ResourceId == t.c.Id, m.c.VersionTo.is_(None), _valid(grouped, ahead=True),
                                 grouped.c.ResourceGroupId == m.c.ResourceGroupId)
    return sa.and_(_active(t), ~has_own, ~in_group)


def _pattern_text(w) -> sa.ColumnElement:
    return sa.func.concat(w.c.DailyCapacity, "|", w.c.DayMon, w.c.DayTue, w.c.DayWed, w.c.DayThu, w.c.DayFri, w.c.DaySat, w.c.DaySun)


CONFLICTS = (  # tablo, grubun bugün uyguladığı değerin metni
    ("WorkPattern", _pattern_text),
    ("ResourceEfficiency", lambda w: sa.cast(w.c.EfficiencyPct, sa.Unicode(30))),
    ("OvertimeLimit", lambda w: sa.cast(w.c.DailyLimit, sa.Unicode(30))),
)


def _group_conflict(t) -> sa.ColumnElement:
    """Birden fazla gruba üye, kendi kaydı olmayan kaynakta grupların bugün farklı değer vermesi (K-185 C); kaynağa özel kayıt beklenir.
    Bir grubun kaydı olup ötekinin olmaması da farktır."""
    parts = []
    for name, text_of in CONFLICTS:
        table = metadata.tables[f"param.{name}"]
        own = table.alias(f"sc_{name}_own")
        m1, m2 = MEMBER.alias(f"sc_{name}_m1"), MEMBER.alias(f"sc_{name}_m2")

        def applied(m, tag):
            w = table.alias(f"sc_{name}_{tag}")
            return sa.func.coalesce(sa.select(text_of(w)).where(_valid(w), w.c.ResourceGroupId == m.c.ResourceGroupId)
                                    .order_by(w.c.ValidFrom.desc(), w.c.Id.desc()).limit(1).correlate(m).scalar_subquery(), "-")
        has_own = sa.exists().where(_valid(own), own.c.ResourceId == t.c.Id)
        differs = sa.exists().where(m1.c.ResourceId == t.c.Id, m1.c.VersionTo.is_(None), m2.c.ResourceId == t.c.Id, m2.c.VersionTo.is_(None),
                                    m2.c.ResourceGroupId > m1.c.ResourceGroupId, applied(m1, "a") != applied(m2, "b"))
        parts.append(sa.and_(~has_own, differs))
    return sa.and_(_active(t), sa.or_(*parts))


ENTRY_TABLES = ("WorkPattern", "ResourceEfficiency", "OvertimeLimit", "ResourceDowntime")


def _orphan(column: str) -> Callable[[sa.Table], sa.ColumnElement]:
    """Kapanan kaynağa ya da gruba Baz'da girilmiş, geçerli ve bitmemiş kapasite kaydı var (K-188). Kayıt silinmez; kaynak geri gelirse uyarı kalkar."""
    def where(t) -> sa.ColumnElement:
        found = []
        for name in ENTRY_TABLES:
            w = metadata.tables[f"param.{name}"].alias(f"sc_orphan_{name}")
            end = w.c.ValidTo if "ValidTo" in w.c else w.c.EndDate
            found.append(sa.exists().where(w.c.ScenarioDefinitionId == _base(), w.c.BaseRowId.is_(None), w.c.IsValid == sa.true(), w.c[column] == t.c.Id,
                                           sa.or_(end.is_(None), end >= _today())))
        return sa.or_(*found)
    return where


def _supplier_limit(t) -> sa.ColumnElement:
    """Bu malzeme tedarikçisi kaydına Baz'da girilmiş, geçerli ve bitmemiş tedarikçi limiti ya da kapanışı var (K-191)."""
    w = metadata.tables["param.SupplierLimit"].alias("sc_suplim")
    return sa.exists().where(w.c.ScenarioDefinitionId == _base(), w.c.BaseRowId.is_(None), w.c.IsValid == sa.true(), w.c.LocationId == t.c.LocationId,
                             w.c.SupplierId == t.c.SupplierId, w.c.MaterialId == t.c.MaterialId, sa.or_(w.c.ValidTo.is_(None), w.c.ValidTo >= _today()))


def _material_hold(t) -> sa.ColumnElement:
    """Bu malzemeye Baz'da girilmiş, geçerli ve bitmemiş malzeme blokajı var (K-193). Kayıt silinmez; malzeme geri gelirse uyarı kalkar."""
    w = metadata.tables["param.MaterialHold"].alias("sc_hold")
    return sa.exists().where(w.c.ScenarioDefinitionId == _base(), w.c.BaseRowId.is_(None), w.c.IsValid == sa.true(), w.c.MaterialId == t.c.Id,
                             sa.or_(w.c.EndDate.is_(None), w.c.EndDate >= _today()))


def _priority_out_of_range(t) -> sa.ColumnElement:
    """ERP önceliği 1–5 dışında (K-195): değer yok sayılır, hiyerarşi bir alt basamağa geçer."""
    return sa.and_(t.c.Priority.is_not(None), sa.not_(t.c.Priority.between(1, 5)))


def _allocation_empty(t) -> sa.ColumnElement:
    """Özel alokasyonu boş malzeme (K-198): arzı genel sayılır; alan yalnız ERP'den ya da veri kuralıyla dolar."""
    return sa.and_(_active(t), t.c.IsCustomAllocated.is_(None))


def _has_owned_supply(t) -> sa.ColumnElement:
    """Malzemenin sahip bilgisi taşıyan (sipariş, proje ya da müşteri) güncel arzı var: boş alan burada sonucu değiştirir."""
    parts = []
    for name in ("Stock", "WorkOrder", "PurchaseOrderLine"):
        s = metadata.tables[f"core.{name}"].alias(f"sc_alloc_{name.lower()}")
        parts.append(sa.exists().where(s.c.MaterialId == t.c.Id, s.c.VersionTo.is_(None),
                                       sa.or_(s.c.SalesOrderNo.is_not(None), s.c.ProjectCode.is_not(None), s.c.CustomerCode.is_not(None))))
    return sa.or_(*parts)


def _never(t) -> sa.ColumnElement:
    return sa.false()


def _passive_with_limit(t) -> sa.ColumnElement:
    return sa.and_(t.c.IsActive == sa.false(), _supplier_limit(t))


CHECKS: tuple[SmartchainCheck, ...] = (
    # Bütün gruplar için çıkar; önem: Yüksek = grup kritik ve açık bir talebin zincirinde (K-185 H)
    SmartchainCheck("SC.RES_NO_CAPACITY", "Resource", "Kapasitesi tanımsız kaynak", "Kapasite tanımsız (çalışma düzeni yok):", _no_work_pattern,
                    high_when=_in_critical_group),
    SmartchainCheck("SC.RES_GROUP_CONFLICT", "Resource", "Grupları çelişen kaynak", "Grupları farklı kapasite değeri veriyor:", _group_conflict),
    SmartchainCheck("SC.CAP_ORPHAN", "Resource", "Kapanan kaynağa girilmiş kapasite kaydı", "Güncel veride olmayan kaynağa kapasite kaydı girilmiş:",
                    _orphan("ResourceId"), closed=True),
    SmartchainCheck("SC.CAP_ORPHAN", "ResourceGroup", "Kapanan kaynak grubuna girilmiş kapasite kaydı", "Güncel veride olmayan kaynak grubuna kapasite kaydı girilmiş:",
                    _orphan("ResourceGroupId"), closed=True),
    # Tedarikçi limiti (K-191): limit yalnız aktif ve güncel malzeme tedarikçisi kaydına girilir; kayıt sonradan kapanır ya da pasifleşirse limit durur, uygulanmaz
    SmartchainCheck("SC.SUPLIM_ORPHAN", "MaterialSupplier", "Kapanan malzeme tedarikçisine girilmiş tedarikçi limiti",
                    "Güncel veride olmayan malzeme tedarikçisine tedarikçi limiti girilmiş:", _supplier_limit, closed=True),
    SmartchainCheck("SC.SUPLIM_PASSIVE", "MaterialSupplier", "Pasif malzeme tedarikçisine girilmiş tedarikçi limiti",
                    "Pasif malzeme tedarikçisine tedarikçi limiti girilmiş:", _passive_with_limit),
    # Malzeme blokajı (K-193): malzeme aktarımla kapanırsa blokaj kaydı durur, uygulanacak malzeme yoktur
    # Öncelik yönetimi (K-195): öncelik grubu 1–5'tir; aralık dışı ERP önceliği kullanılmaz. Önem her zaman Normal
    *[SmartchainCheck("SC.PRIORITY_RANGE", table, "ERP önceliği 1–5 dışında", "ERP önceliği 1–5 dışında (yok sayılır):", _priority_out_of_range, high_when=_never)
      for table in ("Customer", "Project", "SalesOrderLine")],
    # Özel alokasyon (K-198): alan boşsa malzemenin arzı genel sayılır; sahipli arzı varsa Yüksek, yoksa Normal
    SmartchainCheck("SC.MAT_ALLOC_EMPTY", "Material", "Özel alokasyon boş", "Özel alokasyon boş (arz genel sayılır):", _allocation_empty,
                    fix_field="IsCustomAllocated", high_when=_has_owned_supply, high_only=True),
    SmartchainCheck("SC.HOLD_ORPHAN", "Material", "Kapanan malzemeye girilmiş malzeme blokajı", "Güncel veride olmayan malzemeye malzeme blokajı girilmiş:",
                    _material_hold, closed=True),
)
BY_CODE = {(c.code, c.table): c for c in CHECKS}
