from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from app.i18n import DEFAULT_LANGUAGE, detect_language
from app.repositories.user import UserRepository


class LanguageMiddleware(BaseMiddleware):
    """Puts the user's language into every handler as the `lang` argument."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        lang = DEFAULT_LANGUAGE
        tg_user = data.get("event_from_user")
        if tg_user is not None:
            user = await UserRepository(data["session"]).get_by_telegram_id(tg_user.id)
            lang = user.language if user else detect_language(tg_user.language_code)
        data["lang"] = lang
        return await handler(event, data)