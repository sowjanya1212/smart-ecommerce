"""WebSocket connection hub. Sync endpoints push via `push()` (thread-safe)."""
import asyncio
import logging
from collections import defaultdict

from fastapi import WebSocket

log = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self._sockets: dict[int, set[WebSocket]] = defaultdict(set)
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop):
        self._loop = loop

    async def connect(self, user_id: int, ws: WebSocket):
        await ws.accept()
        self._sockets[user_id].add(ws)

    def disconnect(self, user_id: int, ws: WebSocket):
        self._sockets[user_id].discard(ws)
        if not self._sockets[user_id]:
            self._sockets.pop(user_id, None)

    async def send_to_user(self, user_id: int, payload: dict):
        for ws in list(self._sockets.get(user_id, ())):
            try:
                await ws.send_json(payload)
            except Exception:
                self.disconnect(user_id, ws)

    def push(self, user_id: int, payload: dict):
        """Callable from sync code running in a worker thread."""
        if self._loop is None or self._loop.is_closed() or user_id not in self._sockets:
            return
        asyncio.run_coroutine_threadsafe(self.send_to_user(user_id, payload), self._loop)

    def online_users(self) -> int:
        return len(self._sockets)


manager = ConnectionManager()
