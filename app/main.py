import asyncio
import logging
from datetime import timedelta

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import text

from app.bot.errors import on_error
from app.bot.handlers import (
    admin,
    admin_catalog,
    admin_couriers,
    admin_payments,
    admin_products,
    admin_promos,
    admin_reports,
    admin_warehouse,
    cart,
    catalog,
    checkout,
    courier,
    language,
    orders,
    payments,
    promo,
    start,
)
from app.bot.middlewares.db import DbSessionMiddleware
from app.bot.middlewares.language import LanguageMiddleware
from app.bot.middlewares.throttling import ThrottlingMiddleware
from app.bot.notifications import send_to_admins
from app.config import settings
from app.database.session import async_session, engine
from app.scheduler.jobs import send_daily_report

logging.basicConfig(
    level=settings.log_level.upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def create_storage():
    """Redis keeps the checkout state when the bot restarts; memory does not."""
    if settings.redis_url:
        logger.info("FSM state is stored in Redis")
        return RedisStorage.from_url(
            settings.redis_url,
            state_ttl=timedelta(hours=24),
            data_ttl=timedelta(hours=24),
        )
    logger.info("FSM state is stored in memory (lost on restart)")
    return MemoryStorage()


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
    dp = Dispatcher(storage=create_storage())
    dp.update.middleware(DbSessionMiddleware(async_session))
    dp.update.middleware(LanguageMiddleware())

    # spam protection for messages and button presses (not for payment checks)
    throttling = ThrottlingMiddleware(limit=8, period=5.0)
    dp.message.outer_middleware(throttling)
    dp.callback_query.outer_middleware(throttling)

    dp.errors.register(on_error)

    dp.include_router(start.router)
    dp.include_router(language.router)
    dp.include_router(catalog.router)
    dp.include_router(cart.router)
    dp.include_router(checkout.router)
    dp.include_router(orders.router)
    dp.include_router(admin.router)
    dp.include_router(admin_catalog.router)
    dp.include_router(admin_products.router)
    dp.include_router(admin_reports.router)
    dp.include_router(admin_warehouse.router)
    dp.include_router(admin_couriers.router)
    dp.include_router(courier.router)
    dp.include_router(admin_promos.router)
    dp.include_router(promo.router)
    dp.include_router(payments.router)
    dp.include_router(admin_payments.router)

    scheduler = AsyncIOScheduler(timezone=settings.timezone)
    scheduler.add_job(
        send_daily_report,
        CronTrigger(
            hour=settings.daily_report_hour,
            minute=settings.daily_report_minute,
            timezone=settings.timezone,
        ),
        args=[bot],
        id="daily_report",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        "Daily report scheduled at %02d:%02d (%s)",
        settings.daily_report_hour,
        settings.daily_report_minute,
        settings.timezone,
    )

    if settings.environment == "production":
        await send_to_admins(bot, "🟢 Bot started")

    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await dp.storage.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())