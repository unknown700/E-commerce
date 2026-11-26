from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.bot.middlewares.throttling import ThrottlingMiddleware


async def test_extra_requests_are_dropped_and_warned_once():
    middleware = ThrottlingMiddleware(limit=3, period=60)
    handled = []

    async def handler(event, data):
        handled.append(1)
        return "ok"

    event = SimpleNamespace(answer=AsyncMock())
    data = {"event_from_user": SimpleNamespace(id=777_000_001), "lang": "en"}

    results = [await middleware(handler, event, data) for _ in range(6)]

    assert results == ["ok", "ok", "ok", None, None, None]
    assert len(handled) == 3
    event.answer.assert_awaited_once()  # one warning, not one per dropped request


async def test_different_users_do_not_affect_each_other():
    middleware = ThrottlingMiddleware(limit=1, period=60)

    async def handler(event, data):
        return "ok"

    event = SimpleNamespace(answer=AsyncMock())
    first = {"event_from_user": SimpleNamespace(id=777_000_002), "lang": "en"}
    second = {"event_from_user": SimpleNamespace(id=777_000_003), "lang": "en"}

    assert await middleware(handler, event, first) == "ok"
    assert await middleware(handler, event, second) == "ok"