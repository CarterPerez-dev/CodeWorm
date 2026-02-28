"""
ⒸAngelaMos | 2026
dashboard/backend/ws.py
"""
from __future__ import annotations

import asyncio
import contextlib
import os
from collections import deque
from typing import Any

import orjson
from fastapi import APIRouter, WebSocket, WebSocketDisconnect


router = APIRouter()

LOG_BUFFER_SIZE = 200


class ConnectionManager:
    def __init__(self) -> None:
        self.active: list[WebSocket] = []
        self.log_buffer: deque[dict[str, Any]] = deque(maxlen = LOG_BUFFER_SIZE)

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active.append(websocket)
        if self.log_buffer:
            history = orjson.dumps(
                {
                    "channel": "codeworm:history",
                    "data": list(self.log_buffer),
                }
            ).decode("utf-8")
            try:  # noqa: SIM105
                await websocket.send_text(history)
            except Exception:  # noqa: S110
                pass

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active:
            self.active.remove(websocket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        if message.get("channel") in ("codeworm:logs", "codeworm:events"):
            self.log_buffer.append(message)
        payload = orjson.dumps(message).decode("utf-8")
        disconnected: list[WebSocket] = []
        for ws in self.active:
            try:
                await ws.send_text(payload)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self.disconnect(ws)


manager = ConnectionManager()

_subscriber_task: asyncio.Task | None = None


async def start_redis_subscriber() -> None:
    global _subscriber_task
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")

    try:
        import redis.asyncio as aioredis

        client = aioredis.from_url(redis_url, decode_responses = True)
        await client.ping()
    except Exception:
        return

    async def _subscribe() -> None:
        pubsub = client.pubsub()
        await pubsub.subscribe(
            "codeworm:logs",
            "codeworm:events",
            "codeworm:stats",
        )

        async for message in pubsub.listen():
            if message["type"] != "message":
                continue

            channel = message["channel"]
            try:
                data = orjson.loads(message["data"])
            except Exception:
                data = {"raw": message["data"]}

            await manager.broadcast({
                "channel": channel,
                "data": data,
            })

    _subscriber_task = asyncio.create_task(_subscribe())


async def stop_redis_subscriber() -> None:
    global _subscriber_task
    if _subscriber_task and not _subscriber_task.done():
        _subscriber_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _subscriber_task
    _subscriber_task = None


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text(
                    orjson.dumps({
                        "type": "pong"
                    }).decode("utf-8")
                )
    except (WebSocketDisconnect, RuntimeError):
        manager.disconnect(websocket)
