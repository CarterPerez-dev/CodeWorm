"""
ⒸAngelaMos | 2026
core/events.py
"""
from __future__ import annotations

import threading
from datetime import datetime
from typing import Any

import orjson


_publisher: EventPublisher | None = None


class EventPublisher:
    CHANNEL_LOGS = "codeworm:logs"
    CHANNEL_EVENTS = "codeworm:events"
    CHANNEL_STATS = "codeworm:stats"

    def __init__(self, redis_url: str) -> None:
        import redis as redis_lib

        self._client = redis_lib.Redis.from_url(
            redis_url,
            decode_responses = False,
            socket_connect_timeout = 2,
            socket_timeout = 2,
        )
        self._lock = threading.Lock()
        self._connected = False
        self._check_connection()

    def _check_connection(self) -> bool:
        try:
            self._client.ping()
            self._connected = True
            return True
        except Exception:
            self._connected = False
            return False

    def _publish(self, channel: str, data: dict) -> None:
        if not self._connected and not self._check_connection():
            return
        try:
            payload = orjson.dumps(data, default = str)
            with self._lock:
                self._client.publish(channel, payload)
        except Exception:
            self._connected = False

    def publish_log(self, event_dict: dict) -> None:
        self._publish(self.CHANNEL_LOGS, event_dict)

    def publish_event(self, event_type: str, data: dict | None = None) -> None:
        payload = {
            "type": event_type,
            "timestamp": datetime.now().isoformat(),
            "data": data or {},
        }
        self._publish(self.CHANNEL_EVENTS, payload)

    def publish_stats(self, stats: dict) -> None:
        payload = {
            "timestamp": datetime.now().isoformat(),
            **stats,
        }
        self._publish(self.CHANNEL_STATS, payload)

    def close(self) -> None:
        try:  # noqa: SIM105
            self._client.close()
        except Exception:  # noqa: S110
            pass


def redis_log_processor(
    logger: Any,
    method_name: str,
    event_dict: dict,
) -> dict:
    publisher = get_publisher()
    if publisher is not None:
        publisher.publish_log(event_dict)
    return event_dict


def init_publisher(redis_url: str) -> EventPublisher:
    global _publisher
    _publisher = EventPublisher(redis_url)
    return _publisher


def get_publisher() -> EventPublisher | None:
    return _publisher
