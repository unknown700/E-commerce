import logging

from aiogram import Bot
from aiogram.types import ErrorEvent

from app.i18n import t

logger = logging.getLogger(__name__)

# harmless Telegram errors that need no apology (a stale button, nothing to edit)
IGNORED = ("query is too old", "message is not modified")


async def on_error(event: ErrorEvent, bot: Bot) -> bool:
    text = str(event.exception)
    if any(part in text for part in IGNORED):
        logger.info("Ignored a harmless error: %s", text)
        return True

    logger.error("Unhandled error", exc_info=event.exception)

    update = event.update
    chat_id = None
    if update.message:
        chat_id = update.message.chat.id
    elif update.callback_query:
        chat_id = update.callback_query.from_user.id
    if chat_id is not None:
        try:
            await bot.send_message(chat_id, t("en", "error.generic"))
        except Exception:
            pass
    return True