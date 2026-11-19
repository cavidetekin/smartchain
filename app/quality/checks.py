"""Smartchain'de yönetilen veriden gelen veri kalitesi kontrolleri (K-174, kaynak b). Validasyon kuralları ekranında görünmez, kapatılamaz.

Kapasite kontrolleri (K-185 H) yalnız Baz senaryoya bakar: kapasitesi tanımsız kaynak (ne kendisinde ne grubunda geçerli çalışma düzeni) ve
grupları çelişen kaynak (birden fazla gruba üye, kendi kaydı yok, gruplar farklı değer veriyor). Malzeme blokajı kendi kontrollerini ekleyecek.
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


CHECKS: tuple[SmartchainCheck, ...] = (
    # Bütün gruplar için çıkar; önem: Yüksek = grup kritik ve açık bir talebin zincirinde (K-185 H)
    SmartchainCheck("SC.RES_NO_CAPACITY", "Resource", "Kapasitesi tanımsız kaynak", "Kapasite tanımsız (çalışma düzeni yok):", _no_work_pattern,
                    high_when=_in_critical_group),
    SmartchainCheck("SC.RES_GROUP_CONFLICT", "Resource", "Grupları çelişen kaynak", "Grupları farklı kapasite değeri veriyor:", _group_conflict),
)
BY_CODE = {c.code: c for c in CHECKS}
