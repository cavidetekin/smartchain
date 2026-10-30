"""WS /api/ws: anlık bildirim kanalı (fonksiyon 48). Oturumla açılır (K-97): çerez ve Origin el sıkışmada denetlenir;
oturum yoksa ya da şifre değişikliği bekliyorsa bağlantı kabul edilmez (403). Oturum bitince soket 4401 ile kapanır."""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool

from ..deps import COOKIE, authenticate, origin_allowed
from ..errors import AppError
from ..notify import SESSION_CLOSED

router = APIRouter()


@router.websocket("/ws")
async def notifications(websocket: WebSocket) -> None:
    manager = websocket.app.state.notifier
    if not origin_allowed(websocket.headers.get("origin"), websocket.headers.get("host")):
        await websocket.close(code=SESSION_CLOSED)
        return
    try:
        user = await run_in_threadpool(authenticate, websocket.cookies.get(COOKIE))
    except AppError:
        user = None
    if user is None or user.must_change_password:
        await websocket.close(code=SESSION_CLOSED)  # kabul edilmeden kapanır: el sıkışma 403
        return
    await websocket.accept()
    manager.add(user.id, websocket, user.session_id)
    try:
        await websocket.send_json({"type": "hello", "user_id": user.id})
        while True:
            if await websocket.receive_text() == "ping":  # bağlantı denetimi; oturumu uzatmaz
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        manager.remove(user.id, websocket)
