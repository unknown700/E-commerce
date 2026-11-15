import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from sqlalchemy import text

from app.bot.handlers import admin, cart, catalog, checkout, orders, start
from app.bot.middlewares.db import DbSessionMiddleware
from app.config import settings
from app.database.session import async_session, engine
from app.bot.handlers import admin, admin_catalog, cart, catalog, checkout, orders, start
from app.bot.handlers import (
    admin,
    admin_catalog,
    admin_products,
    cart,
    catalog,
    checkout,
    orders,
    start,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
    logger.info("Database connected")

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML, link_preview_is_disabled=True
        ),
    )
    dp = Dispatcher()
    dp.update.middleware(DbSessionMiddleware(async_session))
    dp.include_router(start.router)
    dp.include_router(catalog.router)
    dp.include_router(cart.router)
    dp.include_router(checkout.router)
    dp.include_router(orders.router)
    dp.include_router(admin.router)
    dp.include_router(admin_catalog.router)
    dp.include_router(admin_products.router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())