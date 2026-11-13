import asyncio
import logging

from aiogram import Bot, Dispatcher
from sqlalchemy import text

from app.bot.handlers import start
from app.config import settings
from app.database.session import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
    logger.info("Database connected")

    bot = Bot(token=settings.bot_token)
    dp = Dispatcher()
    dp.include_router(start.router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())