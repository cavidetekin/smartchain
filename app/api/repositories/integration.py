"""Entegrasyon tanımı ve veri çekme sorguları (fonksiyon 01 ve 91, K-130). Commit çağıranın."""
import json
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.jobs.settings import read_int_settings
from db.models import metadata

from . import imports as imports_repo

ENTITY = metadata.tables["adm.IntegrationEntity"]
VERSION = metadata.tables["adm.IntegrationViewVersion"]
SETTING = metadata.tables["adm.SystemSetting"]
JOB = metadata.tables["adm.Job"]
USER = metadata.tables["adm.AppUser"]
BATCH = imports_repo.BATCH

METHOD_EXCEL, METHOD_SQL = "Excel", "SQL"
METHODS = (METHOD_EXCEL, METHOD_SQL)  # API 11.5'te (K-130)
DATABASE_KEY = "IntegrationDatabase"
PULL_DEFAULTS = {"PullRetryWaitSeconds": 30}
READ_STATUSES = (imports_repo.RECEIVED, imports_repo.FAILED, "Doğrulandı", "Yüklendi")  # sinyali okunmuş partiler


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def get_entity(session: Session, table: str) -> dict | None:
    row = session.execute(sa.select(ENTITY).where(ENTITY.c.EntityName == table)).mappings().first()
    return dict(row) if row else None


def all_entities(session: Session) -> dict[str, dict]:
    return {r["EntityName"]: dict(r) for r in session.execute(sa.select(ENTITY)).mappings()}


def method_of(row: dict | None) -> str:
    """Satır yoksa ya da yöntem boşsa tablo Excel sayılır (K-130)."""
    return (row or {}).get("Method") or METHOD_EXCEL


def is_pull_enabled(row: dict | None) -> bool:
    return True if row is None else bool(row["IsPullEnabled"])


def save_entity(session: Session, table: str, **values) -> None:
    if session.execute(sa.select(ENTITY.c.EntityName).where(ENTITY.c.EntityName == table)).first():
        session.execute(sa.update(ENTITY).where(ENTITY.c.EntityName == table).values(**values))
    else:
        session.execute(sa.insert(ENTITY).values(EntityName=table, **values))


def read_database(session: Session) -> str | None:
    return session.execute(sa.select(SETTING.c.Value).where(SETTING.c.SettingKey == DATABASE_KEY)).scalar_one_or_none() or None


def read_pull_settings(session: Session) -> dict[str, int]:
    return read_int_settings(session, PULL_DEFAULTS, minimum=0)


def last_signal(session: Session, table: str) -> int | None:
    """Bu tabloda okunmuş son sinyal."""
    return session.execute(sa.select(BATCH.c.SignalId)
                           .where(BATCH.c.EntityName == table, BATCH.c.Method == METHOD_SQL, BATCH.c.SignalId.is_not(None), BATCH.c.Status.in_(READ_STATUSES))
                           .order_by(BATCH.c.Id.desc())).scalars().first()


def create_batch(session: Session, table: str, view: str, signal_id: int | None, user_id: int | None, job_id: int) -> int:
    """SQL partisi; okuma bitene kadar "Ön kontrol": kimse okumaz, yarıda kalırsa satırları silinir."""
    return session.execute(sa.insert(BATCH).values(
        Method=METHOD_SQL, EntityName=table, LoadType="Tam", ReceivedAt=utcnow(), Status=imports_repo.PENDING,
        UploadedBy=user_id, SourceObject=view, SignalId=signal_id, JobId=job_id).returning(BATCH.c.Id)).scalar_one()


def open_job_batches(session: Session, job_id: int) -> list[int]:
    return list(session.execute(sa.select(BATCH.c.Id).where(BATCH.c.JobId == job_id, BATCH.c.Method == METHOD_SQL,
                                                            BATCH.c.Status == imports_repo.PENDING)).scalars())


def last_version(session: Session, table: str, view: str) -> dict | None:
    row = session.execute(sa.select(VERSION).where(VERSION.c.EntityName == table, VERSION.c.ViewName == view)
                          .order_by(VERSION.c.VersionNo.desc())).mappings().first()
    return dict(row) if row else None


def add_version(session: Session, table: str, view: str, number: int, digest: str, definition: str | None, app_version: str) -> None:
    session.execute(sa.insert(VERSION).values(EntityName=table, ViewName=view, VersionNo=number, DefinitionHash=digest,
                                              Definition=definition, SeenAt=utcnow(), AppVersion=app_version))


def versions(session: Session, table: str) -> list[dict]:
    rows = session.execute(sa.select(VERSION).where(VERSION.c.EntityName == table).order_by(VERSION.c.Id.desc())).mappings().all()
    return [dict(r) for r in rows]


def set_job_result(session: Session, job_id: int, results: list[dict]) -> None:
    session.execute(sa.update(JOB).where(JOB.c.Id == job_id).values(Result=json.dumps(results, ensure_ascii=False, default=str)))


def job_row(session: Session, job_id: int) -> dict | None:
    row = session.execute(sa.select(JOB).where(JOB.c.Id == job_id)).mappings().first()
    return dict(row) if row else None


def last_pull(session: Session) -> dict | None:
    """Son çekim işi: zaman ve başlatan (onay penceresinin altı)."""
    row = session.execute(sa.select(JOB.c.Id, JOB.c.Status, JOB.c.CreatedAt, USER.c.FullName, USER.c.UserName)
                          .select_from(JOB.outerjoin(USER, USER.c.Id == JOB.c.RequestedBy))
                          .where(JOB.c.JobType == "Veri çekme").order_by(JOB.c.Id.desc())).mappings().first()
    return dict(row) if row else None


def batch_counts(session: Session) -> dict:
    """Kartlar: son SQL okuması ve son Excel yüklemesi."""
    def latest(method: str):
        return session.execute(sa.select(sa.func.max(BATCH.c.ReceivedAt)).where(BATCH.c.Method == method, BATCH.c.Status.in_(READ_STATUSES))).scalar()
    return {"last_read": latest(METHOD_SQL), "last_upload": latest(METHOD_EXCEL)}


def account(session: Session) -> str:
    return session.execute(sa.text("SELECT SUSER_SNAME()")).scalar_one()
