"""WS /api/ws: anlık bildirim kanalı (fonksiyon 48). Kullanıcı şimdilik user_id parametresiyle (A-36, oturum 2.1'de)."""
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/ws")
async def notifications(websocket: WebSocket, user_id: int = Query(...)) -> None:
    manager = websocket.app.state.notifier
    await websocket.accept()
    manager.add(user_id, websocket)
    try:
        await websocket.send_json({"type": "hello", "user_id": user_id})
        while True:
            if await websocket.receive_text() == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        manager.remove(user_id, websocket)
