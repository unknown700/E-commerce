import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from app.bot.formatting import format_report
from app.config import settings
from app.database.session import async_session
from app.services.report import ReportService

logger = logging.getLogger(__name__)


async def send_daily_report(bot: Bot) -> None:
    async with async_session() as session:
        report = await ReportService(session).build("today")
    text = "🗓 <b>Daily report</b>\n\n" + format_report(report)

    for admin_id in settings.admin_id_list:
        try:
            await bot.send_message(admin_id, text)
        except TelegramAPIError:
            logger.warning("Could not send the daily report to admin %s", admin_id)