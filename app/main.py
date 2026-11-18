import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import text

from app.bot.handlers import (
    admin,
    admin_catalog,
    admin_products,
    admin_reports,
    admin_warehouse,   
    cart,
    catalog,
    checkout,
    orders,
    start,
)
from app.bot.middlewares.db import DbSessionMiddleware
from app.config import settings
from app.database.session import async_session, engine
from app.scheduler.jobs import send_daily_report


from app.bot.handlers import (
    admin,
    admin_catalog,
    admin_couriers,
    admin_products,
    admin_reports,
    admin_warehouse,
    cart,
    catalog,
    checkout,
    courier,
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
    dp.include_router(admin_reports.router)
    dp.include_router(admin_warehouse.router)
    dp.include_router(admin_couriers.router)
    dp.include_router(courier.router)

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

    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    asyncio.run(main())