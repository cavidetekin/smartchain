"""Senaryolar (ekran 07; fonksiyon 27, 28; K-177): seçili senaryo ve geçiş, kopyalayarak yeni senaryo, yeniden adlandırma, pasif / aktif,
Baz'dan ayır, silme, "Gece çalışsın" ve gece sırası. İş kuralları `app/params/scenarios.py`'de; burada yetki, işlem ve denetim izi.

Yetki işlem bazındadır (yeni fonksiyon numarası yok): yeni senaryo, kopyalama, silme, yeniden adlandırma, pasif / aktif ve Baz'dan ayır Admin ve
üstü; "Gece çalışsın" ve gece sırası Key user ve üstü (fonksiyon 28); senaryo listesi ve geçiş herkes (82 okuma).
"""
from sqlalchemy.orm import Session

from app.params import scenarios

from ..errors import AppError
from ..permissions import ADMIN, SYSTEM_OWNER
from ..repositories import audit
from . import auth
from .auth import CurrentUser

OBJECT = "Senaryo"
ADMIN_ONLY = "Bu işlemi Admin yapabilir: yeni senaryo, kopyalama, yeniden adlandırma, pasif yapma, Baz'dan ayırma ve silme."
A_CREATED, A_RENAMED, A_PASSIVE, A_ACTIVE = "Senaryo oluşturuldu", "Senaryo adı değişti", "Senaryo pasif yapıldı", "Senaryo aktif yapıldı"
A_DETACHED, A_DELETED, A_NIGHTLY = "Senaryo Baz'dan ayrıldı", "Senaryo silindi", "Gece ayarı değişti"


def _error(err: scenarios.ScenarioError) -> AppError:
    details = [{"field": err.field, "problem": err.message}] if err.field else None
    return AppError(err.code, err.message, err.status, details)


def _run(session: Session | None, work):
    """İşi işlem içinde çalıştırır; iş kuralı hatasında geri alır."""
    session = auth._require(session)

    def inner():
        try:
            result = work(session)
        except scenarios.ScenarioError as err:
            session.rollback()
            raise _error(err) from None
        session.commit()
        return result

    return auth._db(inner)


def _admin(actor: CurrentUser) -> None:
    if actor.role not in (SYSTEM_OWNER, ADMIN):
        raise AppError("forbidden", ADMIN_ONLY, 403, [{"required_role": ADMIN}])


def _public(row: dict) -> dict:
    return {"id": row["Id"], "name": row["Name"], "is_base": bool(row["IsBase"]), "is_active": row["IsActive"] is not False}


def options(session: Session | None) -> dict:
    return _run(session, lambda s: {"scenarios": scenarios.options(s)})


def current(session: Session | None, user: CurrentUser, scenario_id: int | None = None) -> dict:
    """Kullanıcının senaryosu: verilen (Senaryolar ekranından açılan pasif senaryo da olabilir), yoksa hatırlanan, o da geçersizse Baz."""
    return _run(session, lambda s: _public(scenarios.resolve(s, user.id, scenario_id)))


def select(session: Session | None, user: CurrentUser, scenario_id: int) -> dict:
    """Seçim kullanıcı bazında hatırlanır; denetim izine yazılmaz."""
    return _run(session, lambda s: _public(scenarios.remember(s, user.id, scenario_id)))


def create(session: Session | None, actor: CurrentUser, name: str | None, source_id: int, follows_base: bool) -> dict:
    _admin(actor)

    def work(s):
        source = scenarios.get(s, source_id)
        row = scenarios.create_copy(s, name, source_id, follows_base)
        audit.write_audit(s, A_CREATED, actor.id, OBJECT, row["Name"], {"source": source["Name"], "FollowsBase": bool(follows_base)}, scenario=row["Name"])
        return _public(row)

    return _run(session, work)


def rename(session: Session | None, actor: CurrentUser, scenario_id: int, name: str | None) -> dict:
    _admin(actor)

    def work(s):
        old, new = scenarios.rename(s, scenario_id, name)
        if old != new:
            audit.write_audit(s, A_RENAMED, actor.id, OBJECT, new, {"Name": new}, {"Name": old}, scenario=new)
        return _public(scenarios.get(s, scenario_id))

    return _run(session, work)


def set_active(session: Session | None, actor: CurrentUser, scenario_id: int, active: bool) -> dict:
    _admin(actor)

    def work(s):
        row = scenarios.set_active(s, scenario_id, active)
        if (row["IsActive"] is not False) != active:
            audit.write_audit(s, A_ACTIVE if active else A_PASSIVE, actor.id, OBJECT, row["Name"], {"IsActive": active},
                              {"IsActive": row["IsActive"] is not False}, scenario=row["Name"])
        return _public(scenarios.get(s, scenario_id))

    return _run(session, work)


def detach(session: Session | None, actor: CurrentUser, scenario_id: int) -> dict:
    _admin(actor)

    def work(s):
        row = scenarios.detach(s, scenario_id)
        audit.write_audit(s, A_DETACHED, actor.id, OBJECT, row["Name"], {"FollowsBase": False}, {"FollowsBase": True}, scenario=row["Name"])
        return _public(scenarios.get(s, scenario_id))

    return _run(session, work)


def delete_info(session: Session | None, actor: CurrentUser, scenario_id: int) -> dict:
    """Silme onayının bilgisi: silinecek plan versiyonu sayısı; yayınlanmış planı varsa silinemez."""
    _admin(actor)

    def work(s):
        row = scenarios.get(s, scenario_id)
        counts = scenarios.plan_counts(s, scenario_id)
        return {"name": row["Name"], "plan_versions": counts["plan_versions"], "deletable": not row["IsBase"] and not counts["published"],
                "reason": scenarios.BASE_LOCKED if row["IsBase"] else "Yayınlanmış planı olan senaryo silinemez; pasif yapılabilir." if counts["published"] else None}

    return _run(session, work)


def delete(session: Session | None, actor: CurrentUser, scenario_id: int) -> dict:
    _admin(actor)

    def work(s):
        row = scenarios.delete(s, scenario_id)
        audit.write_audit(s, A_DELETED, actor.id, OBJECT, row["Name"], None, {"Name": row["Name"], "plan_versions": row["plan_versions"]}, scenario=row["Name"])
        return {"deleted": row["Name"], "plan_versions": row["plan_versions"]}

    return _run(session, work)


def save_nightly(session: Session | None, actor: CurrentUser, rows: list[dict]) -> dict:
    def work(s):
        changed = scenarios.save_nightly(s, rows)
        for c in changed:
            audit.write_audit(s, A_NIGHTLY, actor.id, OBJECT, c["name"], c["new"], c["old"], scenario=c["name"])
        return {"changed": len(changed)}

    return _run(session, work)
