"""
©AngelaMos | 2026
notifier.py
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from telehook import Notifier, TelehookConfig
from telehook.formatters import alert_formatter, error_formatter
from telehook.middleware import Dedup, RateLimiter, Retry

if TYPE_CHECKING:
    from codeworm.core.config import TelegramSettings


class CodeWormNotifier:
    """
    Telegram notification wrapper for the CodeWorm daemon
    """
    def __init__(self, settings: TelegramSettings) -> None:
        self._notifier = Notifier(
            config = TelehookConfig(
                bot_token = settings.bot_token,
                chat_id = settings.chat_id,
            ),
            middleware = [
                RateLimiter(max_per_second = 1,
                            burst = 3),
                Dedup(window_seconds = 300),
                Retry(max_attempts = 3),
            ],
        )

    async def send_alert(
        self,
        title: str,
        last_error: str | None = None,
        details: str | None = None,
    ) -> None:
        try:
            msg = alert_formatter(
                title = title,
                app = "CodeWorm",
                last_error = last_error,
                details = details,
            )
            await self._notifier.send(msg)
        except Exception:  # noqa: S110
            pass

    async def send_error(self, exc: BaseException, component: str) -> None:
        try:
            msg = error_formatter(
                exception = exc,
                component = component,
                app = "CodeWorm"
            )
            await self._notifier.send(msg)
        except Exception:  # noqa: S110
            pass

    def send_alert_sync(
        self,
        title: str,
        last_error: str | None = None,
        details: str | None = None,
    ) -> None:
        try:
            msg = alert_formatter(
                title = title,
                app = "CodeWorm",
                last_error = last_error,
                details = details,
            )
            self._notifier.send_sync(msg)
        except Exception:  # noqa: S110
            pass

    def send_error_sync(self, exc: BaseException, component: str) -> None:
        try:
            msg = error_formatter(
                exception = exc,
                component = component,
                app = "CodeWorm"
            )
            self._notifier.send_sync(msg)
        except Exception:  # noqa: S110
            pass

    async def close(self) -> None:
        try:  # noqa: SIM105
            await self._notifier.close()
        except Exception:  # noqa: S110
            pass
