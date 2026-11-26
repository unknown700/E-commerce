import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from app.config import settings
from app.i18n import t


class ThrottlingMiddleware(BaseMiddleware):
    """Drops a user's requests when they send too many in a short time."""

    def __init__(self, limit: int = 8, period: float = 5.0, warn_every: float = 10.0):
        self.limit = limit
        self.period = period
        self.warn_every = warn_every
        self._hits: dict[int, deque[float]] = defaultdict(deque)
        self._last_warning: dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = data.get("event_from_user")
        # admins and payment confirmations must never be dropped
        if (
            tg_user is None
            or tg_user.id in settings.admin_id_list
            or (isinstance(event, Message) and event.successful_payment)
        ):
            return await handler(event, data)

        now = time.monotonic()
        hits = self._hits[tg_user.id]
        while hits and now - hits[0] > self.period:
            hits.popleft()

        if len(hits) >= self.limit:
            last = self._last_warning.get(tg_user.id)
            if last is None or now - last >= self.warn_every:
                self._last_warning[tg_user.id] = now
                await self._warn(event, data.get("lang", "en"))
            return None

        hits.append(now)
        return await handler(event, data)

    @staticmethod
    async def _warn(event: Any, lang: str) -> None:
        try:
            await event.answer(t(lang, "throttle.warn"))
        except Exception:
            pass  # the warning is optional