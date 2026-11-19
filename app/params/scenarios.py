"""Senaryo yönetimi (fonksiyon 27, 28; K-176, K-177): senaryolar, kopyalayarak yeni senaryo, yeniden adlandırma, pasif, silme, "Baz'ı izler" ve
"Baz'dan ayır", "Gece çalışsın" ve gece sırası, kullanıcının seçili senaryosu. HTTP'den bağımsızdır; yazma çağıranın işlemindedir.

Baz silinemez, pasif yapılamaz, yeniden adlandırılamaz. Senaryoya bağlı tabloların kopyalanması, silinmesi ve ayrılması kayıt defterinden
(`scenario_tables.py`). "Gece çalışsın" ve gece sırası 7.3'te saklanır; gece akışı (10.11) `nightly_scenarios` ile okur.
"""
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.data.cleanup import delete_scenario_plans
from db.models import metadata

from . import scenario_tables as registry

S = metadata.tables["param.ScenarioDefinition"]
USER = metadata.tables["adm.AppUser"]
RUN = metadata.tables["planning.PlanRun"]
PLAN_VERSION = metadata.tables["planning.PlanVersion"]
NAME_MAX = 100


class ScenarioError(Exception):
    """İşlem yapılamadı: `code` hata kodu, `status` HTTP durumu, `field` varsa hatalı alan."""

    def __init__(self, code: str, message: str, status: int = 422, field: str | None = None):
        super().__init__(message)
        self.code, self.message, self.status, self.field = code, message, status, field


NOT_FOUND = "Senaryo bulunamadı."
BASE_LOCKED = "Baz senaryo silinemez, pasif yapılamaz ve yeniden adlandırılamaz."


# ------------------------------------------------------------------ okuma

def get(session: Session, scenario_id: int) -> dict:
    row = session.execute(sa.select(S).where(S.c.Id == scenario_id)).mappings().first()
    if row is None:
        raise ScenarioError("scenario_not_found", NOT_FOUND, 404)
    return dict(row)


def base(session: Session) -> dict:
    row = session.execute(sa.select(S).where(S.c.IsBase == sa.true()).order_by(S.c.Id)).mappings().first()
    if row is None:
        raise ScenarioError("scenario_not_found", "Baz senaryo bulunamadı.", 404)
    return dict(row)


def options(session: Session) -> list[dict]:
    """Bağlam çubuğunun listesi: aktif senaryolar, Baz başta, sonra ada göre. Pasif senaryo yok."""
    rows = session.execute(sa.select(S.c.Id, S.c.Name, S.c.IsBase).where(sa.func.coalesce(S.c.IsActive, sa.true()) == sa.true())
                           .order_by(sa.func.coalesce(S.c.IsBase, sa.false()).desc(), S.c.Name)).all()
    return [{"id": r.Id, "name": r.Name, "is_base": bool(r.IsBase)} for r in rows]


def resolve(session: Session, user_id: int | None, scenario_id: int | None = None) -> dict:
    """İsteğin senaryosu: açıkça verilen (pasif de olabilir: parametreleri Senaryolar ekranından açılır); verilmezse kullanıcının hatırlanan
    senaryosu, o da yoksa, pasifse ya da silinmişse Baz."""
    if scenario_id is not None:
        return get(session, scenario_id)
    remembered = session.execute(sa.select(USER.c.ScenarioDefinitionId).where(USER.c.Id == user_id)).scalar() if user_id is not None else None
    if remembered is not None:
        row = session.execute(sa.select(S).where(S.c.Id == remembered)).mappings().first()
        if row is not None and row["IsActive"] is not False:
            return dict(row)
    return base(session)


def remember(session: Session, user_id: int, scenario_id: int) -> dict:
    row = get(session, scenario_id)
    session.execute(sa.update(USER).where(USER.c.Id == user_id).values(ScenarioDefinitionId=scenario_id))
    return row


def plan_counts(session: Session, scenario_id: int) -> dict:
    """Senaryonun plan versiyonları (plan hesapları) ve yayınlanmış planı var mı."""
    runs = session.execute(sa.select(sa.func.count()).select_from(RUN).where(RUN.c.ScenarioDefinitionId == scenario_id)).scalar_one()
    published = session.execute(sa.select(sa.func.count()).select_from(PLAN_VERSION.join(RUN, RUN.c.Id == PLAN_VERSION.c.PlanRunId))
                                .where(RUN.c.ScenarioDefinitionId == scenario_id)).scalar_one()
    return {"plan_versions": int(runs), "published": int(published)}


def nightly_scenarios(session: Session) -> list[dict]:
    """Gece akışının hesaplayacağı senaryolar, gece sırasıyla: aktif ve "Gece çalışsın: Evet" (10.11 çağırır)."""
    rows = session.execute(sa.select(S.c.Id, S.c.Name, S.c.NightlyPriority)
                           .where(sa.func.coalesce(S.c.IsActive, sa.true()) == sa.true(), S.c.RunsNightly == sa.true())
                           .order_by(sa.func.coalesce(S.c.NightlyPriority, 2147483647), S.c.Id)).all()
    return [{"id": r.Id, "name": r.Name, "priority": r.NightlyPriority} for r in rows]


# ------------------------------------------------------------------ yazma

def _name(session: Session, name: str | None, except_id: int | None = None) -> str:
    text = (name or "").strip()
    if not text:
        raise ScenarioError("validation", "Senaryo adı boş olamaz.", field="name")
    if len(text) > NAME_MAX:
        raise ScenarioError("validation", f"En çok {NAME_MAX} karakter.", field="name")
    q = sa.select(S.c.Id).where(S.c.Name == text)
    if except_id is not None:
        q = q.where(S.c.Id != except_id)
    if session.execute(q).first() is not None:
        raise ScenarioError("validation", "Bu adla bir senaryo var.", field="name")
    return text


def create_copy(session: Session, name: str | None, source_id: int, follows_base: bool, synthetic: bool = False) -> dict:
    """Yeni senaryo her zaman var olan bir senaryodan kopyalanır: parametrelerinin tamamı gelir. Aktif, gece çalışmaz ve sırasız açılır."""
    source = get(session, source_id)
    text = _name(session, name)
    new_id = session.execute(sa.insert(S).values(
        Name=text, LocationId=source["LocationId"], IsBase=False, IsActive=True, RunsNightly=False, NightlyPriority=None,
        FollowsBase=bool(follows_base), IsSynthetic=synthetic).returning(S.c.Id)).scalar_one()
    registry.copy_rows(session, source_id, new_id, source_is_base=bool(source["IsBase"]))
    if not follows_base:
        registry.materialize(session, new_id)
    return get(session, new_id)


def _editable(session: Session, scenario_id: int) -> dict:
    row = get(session, scenario_id)
    if row["IsBase"]:
        raise ScenarioError("base_scenario", BASE_LOCKED)
    return row


def rename(session: Session, scenario_id: int, name: str | None) -> tuple[str, str]:
    row = _editable(session, scenario_id)
    text = _name(session, name, except_id=scenario_id)
    session.execute(sa.update(S).where(S.c.Id == scenario_id).values(Name=text))
    return row["Name"], text


def _renumber(session: Session) -> None:
    """Gece sırası gece çalışanlar arasında 1'den boşluksuz; gece çalışmayanda boş."""
    session.execute(sa.update(S).where(sa.or_(S.c.RunsNightly.is_(None), S.c.RunsNightly == sa.false())).values(NightlyPriority=None))
    for i, row in enumerate(nightly_scenarios(session), start=1):
        if row["priority"] != i:
            session.execute(sa.update(S).where(S.c.Id == row["id"]).values(NightlyPriority=i))


def _drop_period_cache(session: Session, scenario_id: int) -> None:
    """Dönem tablosu önbelleği veri değildir (K-184): senaryo silinince, pasif yapılınca ve Baz'dan ayrılınca düşer."""
    from app import periods  # döngüsel içe aktarma: dönemler parametreleri okur
    periods.drop_scenario(session, scenario_id)


def set_active(session: Session, scenario_id: int, active: bool) -> dict:
    """Pasif senaryo gece çalışmaz ve bağlam çubuğunda görünmez; parametreleri durur. Geri alınır."""
    row = _editable(session, scenario_id)
    values = {"IsActive": active} if active else {"IsActive": False, "RunsNightly": False, "NightlyPriority": None}
    session.execute(sa.update(S).where(S.c.Id == scenario_id).values(**values))
    if not active:
        _renumber(session)
        _drop_period_cache(session, scenario_id)  # pasif senaryonun dönem önbelleği tutulmaz (K-184)
    return row


def detach(session: Session, scenario_id: int) -> dict:
    """Baz'dan ayır: tek yönlü; Baz'ın o anki değerleri veri tablolarına tam kopyalanır ve akış durur."""
    row = get(session, scenario_id)
    if row["IsBase"] or not row["FollowsBase"]:
        raise ScenarioError("not_following", "Bu senaryo Baz'ı izlemiyor.")
    session.execute(sa.update(S).where(S.c.Id == scenario_id).values(FollowsBase=False))
    registry.materialize(session, scenario_id)
    _drop_period_cache(session, scenario_id)  # artık kendi satırlarının tamamını tutar: ilk kullanımda baştan kurulur (K-184)
    return row


def delete(session: Session, scenario_id: int) -> dict:
    """Senaryoyu parametreleri ve plan versiyonlarıyla (plan hesapları ve çıktıları) siler. Yayınlanmış planı olan senaryo silinemez."""
    row = _editable(session, scenario_id)
    counts = plan_counts(session, scenario_id)
    if counts["published"]:
        raise ScenarioError("scenario_published", "Yayınlanmış planı olan senaryo silinemez; pasif yapılabilir.")
    delete_scenario_plans(session.connection(), scenario_id)
    registry.delete_rows(session, scenario_id)
    _drop_period_cache(session, scenario_id)
    session.execute(sa.update(USER).where(USER.c.ScenarioDefinitionId == scenario_id).values(ScenarioDefinitionId=None))
    session.execute(sa.delete(S).where(S.c.Id == scenario_id))
    _renumber(session)
    return {**row, **counts}


def save_nightly(session: Session, rows: list[dict]) -> list[dict]:
    """ "Gece çalışsın" ve gece sırası, toplu: rows listedeki sırasıyla `{id, runs_nightly}`; gece çalışanların sırası bu sıradan 1'den yazılır.
    Listede olmayan senaryo değişmez (sırası sona kalır). Dönen: değişen senaryolar (ad, eski ve yeni değer)."""
    before = {r["Id"]: dict(r) for r in session.execute(sa.select(S)).mappings()}
    seen = set()
    for row in rows:
        sid = row.get("id")
        if sid not in before or sid in seen:
            raise ScenarioError("validation", "Senaryo listesi değişmiş; sayfayı yenileyin.", field="rows")
        seen.add(sid)
        if row.get("runs_nightly") and before[sid]["IsActive"] is False:
            raise ScenarioError("validation", f"Pasif senaryo gece çalışmaz: {before[sid]['Name']}.", field="rows")
    order = [r["id"] for r in rows if r.get("runs_nightly")]
    rest = [s["id"] for s in nightly_scenarios(session) if s["id"] not in seen]  # listede olmayan gece senaryoları sonda, kendi sırasıyla
    off = [r["id"] for r in rows if not r.get("runs_nightly")]
    for i, sid in enumerate([*order, *rest], start=1):
        session.execute(sa.update(S).where(S.c.Id == sid).values(RunsNightly=True, NightlyPriority=i))
    if off:
        session.execute(sa.update(S).where(S.c.Id.in_(off)).values(RunsNightly=False, NightlyPriority=None))
    changed = []
    for r in session.execute(sa.select(S)).mappings():
        old = before[r["Id"]]
        was, now = (bool(old["RunsNightly"]), old["NightlyPriority"]), (bool(r["RunsNightly"]), r["NightlyPriority"])
        if was != now:
            changed.append({"name": r["Name"], "old": {"RunsNightly": was[0], "NightlyPriority": was[1]},
                            "new": {"RunsNightly": now[0], "NightlyPriority": now[1]}})
    return changed
