import logging
from html import escape

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from app.config import settings

logger = logging.getLogger(__name__)


async def send_to_admins(bot: Bot, text: str) -> None:
    for admin_id in settings.admin_id_list:
        try:
            await bot.send_message(admin_id, text)
        except TelegramAPIError:
            logger.warning("Could not notify admin %s", admin_id)


async def notify_low_stock(bot: Bot, alerts: list[tuple[str, int]]) -> None:
    if not alerts:
        return
    lines = ["⚠️ <b>Low stock alert</b>\n"]
    for name, left in alerts:
        status = "🚨 out of stock" if left == 0 else f"{left} left"
        lines.append(f"• {escape(name)}: {status}")
    await send_to_admins(bot, "\n".join(lines))