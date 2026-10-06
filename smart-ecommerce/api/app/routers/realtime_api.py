"""WebSocket endpoint + internal endpoint used by Django to push notifications."""
import hmac

from fastapi import APIRouter, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from ..config import settings
from ..database import SessionLocal
from ..deps import user_from_token
from ..realtime import manager

router = APIRouter()


def _auth_ws(token: str):
    with SessionLocal() as db:
        user = user_from_token(token, db)
        return user.id


@router.websocket("/ws/notifications")
async def notifications_ws(ws: WebSocket, token: str = ""):
    """Connect with ws://host/ws/notifications?token=<access_token>.
    Events: {"event": "notification", ...} | {"event": "cart_updated", ...}"""
    try:
        user_id = await run_in_threadpool(_auth_ws, token)
    except HTTPException:
        await ws.close(code=4401)
        return
    await manager.connect(user_id, ws)
    await ws.send_json({"event": "connected", "user_id": user_id})
    try:
        while True:
            msg = await ws.receive_text()
            if msg == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(user_id, ws)


class InternalNotify(BaseModel):
    user_id: int
    notification: dict


@router.post("/api/internal/notify", tags=["internal"], include_in_schema=False)
async def internal_notify(body: InternalNotify, x_internal_secret: str = Header("")):
    if not hmac.compare_digest(x_internal_secret, settings.INTERNAL_SECRET):
        raise HTTPException(403, "Forbidden")
    await manager.send_to_user(body.user_id, {"event": "notification", "notification": body.notification})
    return {"ok": True}
