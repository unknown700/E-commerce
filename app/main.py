import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from sqlalchemy import text

from app.bot.handlers import catalog, start
from app.bot.middlewares.db import DbSessionMiddleware
from app.config import settings
from app.database.session import async_session, engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
    logger.info("Database connected")

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.update.middleware(DbSessionMiddleware(async_session))
    dp.include_router(start.router)
    dp.include_router(catalog.router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())