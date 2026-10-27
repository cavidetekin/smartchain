"""Anlık bildirim (fonksiyon 48, K-69).

İşi motor ayrı süreçte çalıştırır; durum adm.Job'a yazılır. JobWatcher tabloyu UpdatedAt ile kısa aralıkla
izler ve değişen işi sahibinin açık WebSocket bağlantılarına iter. Her API süreci kendi bağlantılarını
bilir ve tabloyu kendisi izler; ek bileşen yoktur. Takılan işleri geri alma (requeue_stale) da buradan tetiklenir.
"""
import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import WebSocket
from sqlalchemy.orm import sessionmaker

from app.jobs import queue
from app.jobs.settings import read_settings
from .db import get_engine
from .services.jobs import to_public

log = logging.getLogger("smartchain.notify")


class ConnectionManager:
    """Kullanıcı → açık WebSocket bağlantıları (bir kullanıcı birden çok sekmede olabilir)."""

    def __init__(self) -> None:
        self._by_user: dict[int, set[WebSocket]] = defaultdict(set)

    def add(self, user_id: int, ws: WebSocket) -> None:
        self._by_user[user_id].add(ws)

    def remove(self, user_id: int, ws: WebSocket) -> None:
        conns = self._by_user.get(user_id)
        if conns is not None:
            conns.discard(ws)
            if not conns:
                del self._by_user[user_id]

    async def send(self, user_id: int, message: dict) -> None:
        for ws in list(self._by_user.get(user_id, ())):
            try:
                await ws.send_json(message)
            except Exception:  # kopmuş bağlantı; istemci yeniden bağlanınca son durumu sorgular
                self.remove(user_id, ws)


class JobWatcher:
    # Geç biten işlem (transaction) daha eski bir UpdatedAt ile görünebilir; pencere geriye bu kadar taşar.
    OVERLAP = timedelta(seconds=5)
    STALE_CHECK_EVERY = timedelta(seconds=15)

    def __init__(self, manager: ConnectionManager, interval: float) -> None:
        self.manager = manager
        self.interval = interval
        self._since: datetime | None = None
        self._sent: dict[int, datetime] = {}  # iş → gönderilen son UpdatedAt (pencere içindekiler)
        self._last_stale_check: datetime | None = None
        self._failing = False

    async def run(self) -> None:
        log.info("İş kuyruğu izleniyor (her %.1f sn)", self.interval)
        while True:
            try:
                messages = await asyncio.to_thread(self.poll)
                if self._failing:
                    log.info("İş kuyruğu yeniden okunabiliyor")
                self._failing = False
            except Exception as exc:
                if not self._failing:
                    log.warning("İş kuyruğu okunamadı: %s", exc)
                self._failing = True
                messages = []
            for user_id, message in messages:
                await self.manager.send(user_id, message)
            await asyncio.sleep(self.interval)

    def poll(self) -> list[tuple[int, dict]]:
        with sessionmaker(bind=get_engine())() as session:
            settings = read_settings(session)
            now = queue.db_now(session)
            if self._last_stale_check is None or now - self._last_stale_check >= self.STALE_CHECK_EVERY:
                queue.requeue_stale(session, settings)
                self._last_stale_check = now
            since = (self._since or now) - self.OVERLAP
            jobs = queue.changed_since(session, settings, since)
        self._since = now
        messages = []
        for job in jobs:
            if self._sent.get(job["Id"]) == job["UpdatedAt"]:
                continue
            self._sent[job["Id"]] = job["UpdatedAt"]
            if job["RequestedBy"] is not None:
                messages.append((job["RequestedBy"], {"type": "job", "job": to_public(job)}))
        self._sent = {k: v for k, v in self._sent.items() if v > since}
        return messages
