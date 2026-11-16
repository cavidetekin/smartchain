"""Veri kalitesi (K-174; ekran 05, fonksiyon 20, 21): yüklenmiş veride (`core`) takipli Uyarı kuralları ve Smartchain verisi kontrolleri.

Uyarının kimliği kural + kayıt; durum Yeni · Açık · Yok sayıldı; önem Yüksek · Normal (açık talep zinciri). Kontrol ayrı iştir ("Veri kalitesi"):
aktarımdan, manuel değerden sonra ve gün dönümünde kuyruğa girer; kuyrukta bekleyen varsa yenisi eklenmez, kapsamı birleşir.
"""
import json
from datetime import date, datetime

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.jobs import queue
from app.jobs.constants import CHANNEL_PROCESSING, STATUS_QUEUED, TYPE_QUALITY
from db.models import metadata

STATE_NEW, STATE_OPEN, STATE_IGNORED = "Yeni", "Açık", "Yok sayıldı"
HIGH, NORMAL = "Yüksek", "Normal"
SOURCE_RULE, SOURCE_SMARTCHAIN = "Kural", "Smartchain"
TRIGGER_TRANSFER, TRIGGER_DAILY, TRIGGER_MANUAL, TRIGGER_DEV = "Aktarım", "Gün dönümü", "Manuel değer", "Geliştirme"
PATH_LIMIT = 1000
PRIORITY = -1  # aynı kanalda bekleyen aktarım ve validasyon işlerinden sonra alınır (kuyruk yüksek önceliği önce alır)

JOB = metadata.tables["adm.Job"]


def enqueue(session: Session, tables: set[str] | None = None, trigger: str = TRIGGER_TRANSFER, user_id: int | None = None,
            day: date | None = None, commit: bool = True) -> int:
    """"Veri kalitesi" işini kuyruğa koyar. Sırada bekleyen iş varsa yenisi eklenmez: kapsamı birleşir (biri tam ise tam).
    day: geliştirme aracında tarihli kuralların günü (ürün işlevi değildir); verilirse ayrı iş olarak eklenir."""
    if day is None:
        waiting = session.execute(sa.select(JOB.c.Id, JOB.c.Payload).where(JOB.c.JobType == TYPE_QUALITY, JOB.c.Status == STATUS_QUEUED)
                                  .order_by(JOB.c.Id).with_for_update()).first()
        if waiting is not None:
            payload = json.loads(waiting.Payload or "{}")
            if payload.get("today") is None:
                old = payload.get("tables")
                merged = None if old is None or tables is None else sorted(set(old) | set(tables))
                payload["tables"] = merged
                session.execute(sa.update(JOB).where(JOB.c.Id == waiting.Id).values(Payload=json.dumps(payload, ensure_ascii=False)))
                if commit:
                    session.commit()
                return waiting.Id
    payload = {"tables": sorted(tables) if tables is not None else None, "trigger": trigger, "user_id": user_id,
               "today": day.isoformat() if day else None}
    return queue.enqueue(session, TYPE_QUALITY, CHANNEL_PROCESSING, requested_by=user_id, payload=payload, priority=PRIORITY,
                         summary=f"Veri kalitesi · {trigger}", commit=commit)


def last_run_day(session: Session) -> date | None:
    """Son "Veri kalitesi" işinin yerel günü (gün dönümü için; durumundan bağımsız)."""
    from app.flows.schedule import utc_to_local
    at = session.execute(sa.select(sa.func.max(JOB.c.CreatedAt)).where(JOB.c.JobType == TYPE_QUALITY)).scalar()
    return utc_to_local(at).date() if at else None


def daily_due(session: Session, now_local: datetime) -> bool:
    """Gün dönümü (K-174): bugün henüz "Veri kalitesi" işi yoksa ve veri yüklenmişse."""
    version = metadata.tables["adm.DataVersion"]
    if session.execute(sa.select(sa.func.count()).select_from(version)).scalar_one() == 0:
        return False
    last = last_run_day(session)
    return last is None or last < now_local.date()
