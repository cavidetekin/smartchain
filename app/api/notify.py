"""Anlık bildirim (fonksiyon 48, K-69).

İşi motor ayrı süreçte çalıştırır; durum adm.Job'a yazılır. JobWatcher tabloyu UpdatedAt ile kısa aralıkla
izler ve değişen işi sahibinin açık WebSocket bağlantılarına iter. Her API süreci kendi bağlantılarını
bilir ve tabloyu kendisi izler; ek bileşen yoktur. Takılan işleri geri alma (requeue_stale) da buradan tetiklenir.

Bağlantılar oturuma bağlıdır (K-97): oturum biterse (çıkış, şifre değişikliği, zaman aşımı, pasif kullanıcı) soket
4401 koduyla kapanır. Zaman aşımı ve kapanmış oturumlar SESSION_CHECK_EVERY aralığında taranır.
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
from .repositories import auth as auth_repo
from .services import auth as auth_service
from .services.jobs import to_public

log = logging.getLogger("smartchain.notify")


SESSION_CLOSED = 4401  # oturum bitti; istemci yeniden bağlanmaz, oturumu denetler


class ConnectionManager:
    """Kullanıcı → açık WebSocket bağlantıları (bir kullanıcı birden çok sekmede ve tarayıcıda olabilir);
    her bağlantının oturumu da tutulur."""

    def __init__(self) -> None:
        self._by_user: dict[int, set[WebSocket]] = defaultdict(set)
        self._session_of: dict[WebSocket, int] = {}

    def add(self, user_id: int, ws: WebSocket, session_id: int | None = None) -> None:
        self._by_user[user_id].add(ws)
        if session_id is not None:
            self._session_of[ws] = session_id

    def remove(self, user_id: int, ws: WebSocket) -> None:
        self._session_of.pop(ws, None)
        conns = self._by_user.get(user_id)
        if conns is not None:
            conns.discard(ws)
            if not conns:
                del self._by_user[user_id]

    def session_ids(self) -> list[int]:
        return sorted(set(self._session_of.values()))

    async def close_sessions(self, session_ids) -> None:
        """Bu oturumların soketlerini 4401 ile kapatır (çıkış, şifre değişikliği, zaman aşımı)."""
        ended = set(session_ids)
        if not ended:
            return
        for user_id, conns in list(self._by_user.items()):
            for ws in list(conns):
                if self._session_of.get(ws) in ended:
                    self.remove(user_id, ws)
                    try:
                        await ws.close(code=SESSION_CLOSED)
                    except Exception:  # zaten kopmuş
                        pass

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
    SESSION_CHECK_EVERY = timedelta(seconds=30)

    def __init__(self, manager: ConnectionManager, interval: float) -> None:
        self.manager = manager
        self.interval = interval
        self._since: datetime | None = None
        self._sent: dict[int, datetime] = {}  # iş → gönderilen son UpdatedAt (pencere içindekiler)
        self._last_stale_check: datetime | None = None
        self._last_session_check: datetime | None = None
        self._ended: list[int] = []
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
            if self._ended:
                ended, self._ended = self._ended, []
                await self.manager.close_sessions(ended)
            await asyncio.sleep(self.interval)

    def poll(self) -> list[tuple[int, dict]]:
        with sessionmaker(bind=get_engine())() as session:
            settings = read_settings(session)
            now = queue.db_now(session)
            if self._last_stale_check is None or now - self._last_stale_check >= self.STALE_CHECK_EVERY:
                queue.requeue_stale(session, settings)
                self._last_stale_check = now
            if self._last_session_check is None or now - self._last_session_check >= self.SESSION_CHECK_EVERY:
                self._ended = self.check_sessions(session)
                self._last_session_check = now
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

    def check_sessions(self, session) -> list[int]:
        """Hareketsizlik sınırını geçen oturumları kapatır (denetim izine "Zaman aşımı"); soketi açık olup oturumu
        bitmiş ya da kullanıcısı pasif olanlarla birlikte kapatılacak oturumları döndürür."""
        ended = set(auth_service.expire_idle_sessions(session))
        ended |= auth_repo.closed_among(session, self.manager.session_ids())
        return sorted(ended)
