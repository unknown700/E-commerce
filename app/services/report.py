from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.repositories.report import ReportRepository

PERIOD_DAYS = {"today": 1, "week": 7, "month": 30}


@dataclass
class Report:
    period: str
    start: datetime
    end: datetime
    orders_count: int  # valid orders (not cancelled)
    revenue: Decimal  # total sales (not cancelled)
    average: Decimal
    prev_revenue: Decimal  # total sales of the previous period
    new_customers: int
    by_status: dict[str, tuple[int, Decimal]]
    delivery_split: dict[str, int]
    top_products: list[tuple[str, int, Decimal]]
    daily: list[tuple[date, int, Decimal]]


def period_bounds(period: str, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """Local midnight to local midnight, end is exclusive."""
    days = PERIOD_DAYS[period]
    today_start = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    start = today_start - timedelta(days=days - 1)
    end = today_start + timedelta(days=1)
    return start, end


class ReportService:
    def __init__(self, session: AsyncSession):
        self.repo = ReportRepository(session)

    async def build(self, period: str) -> Report:
        tz = ZoneInfo(settings.timezone)
        days = PERIOD_DAYS[period]
        start, end = period_bounds(period, tz)

        orders_count, revenue = await self.repo.summary(start, end)
        average = revenue / orders_count if orders_count else Decimal("0")

        # the same-length period right before this one, for comparison
        _, prev_revenue = await self.repo.summary(start - timedelta(days=days), start)

        daily: list[tuple[date, int, Decimal]] = []
        if period == "week":
            rows = {
                day: (count, total)
                for day, count, total in await self.repo.daily(
                    start, end, settings.timezone
                )
            }
            for i in range(days):
                day = start.date() + timedelta(days=i)
                count, total = rows.get(day, (0, Decimal("0")))
                daily.append((day, count, total))

        return Report(
            period=period,
            start=start,
            end=end,
            orders_count=orders_count,
            revenue=revenue,
            average=average,
            prev_revenue=prev_revenue,
            new_customers=await self.repo.new_customers(start, end),
            by_status=await self.repo.orders_by_status(start, end),
            delivery_split=await self.repo.delivery_split(start, end),
            top_products=await self.repo.top_products(start, end),
            daily=daily,
        )