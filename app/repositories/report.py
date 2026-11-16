import re
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, cast, func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.order import Order, OrderItem
from app.database.models.user import User


class ReportRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _in_period(start: datetime, end: datetime):
        return (Order.created_at >= start, Order.created_at < end)

    async def summary(self, start: datetime, end: datetime) -> tuple[int, Decimal]:
        """Number of orders and revenue, cancelled orders excluded."""
        result = await self.session.execute(
            select(func.count(Order.id), func.coalesce(func.sum(Order.total), 0)).where(
                *self._in_period(start, end), Order.status != "cancelled"
            )
        )
        count, revenue = result.one()
        return count, Decimal(revenue)

    async def orders_by_status(
        self, start: datetime, end: datetime
    ) -> dict[str, tuple[int, Decimal]]:
        result = await self.session.execute(
            select(
                Order.status,
                func.count(Order.id),
                func.coalesce(func.sum(Order.total), 0),
            )
            .where(*self._in_period(start, end))
            .group_by(Order.status)
        )
        return {
            status: (count, Decimal(total)) for status, count, total in result.all()
        }

    async def delivery_split(self, start: datetime, end: datetime) -> dict[str, int]:
        result = await self.session.execute(
            select(Order.delivery_type, func.count(Order.id))
            .where(*self._in_period(start, end), Order.status != "cancelled")
            .group_by(Order.delivery_type)
        )
        return {kind: count for kind, count in result.all()}

    async def top_products(
        self, start: datetime, end: datetime, limit: int = 5
    ) -> list[tuple[str, int, Decimal]]:
        quantity = func.sum(OrderItem.quantity)
        revenue = func.sum(OrderItem.quantity * OrderItem.unit_price)
        result = await self.session.execute(
            select(OrderItem.product_name, quantity, revenue)
            .join(Order, Order.id == OrderItem.order_id)
            .where(*self._in_period(start, end), Order.status != "cancelled")
            .group_by(OrderItem.product_name)
            .order_by(quantity.desc(), revenue.desc())
            .limit(limit)
        )
        return [(name, int(qty), Decimal(rev)) for name, qty, rev in result.all()]

    async def new_customers(self, start: datetime, end: datetime) -> int:
        result = await self.session.execute(
            select(func.count(User.id)).where(
                User.created_at >= start, User.created_at < end
            )
        )
        return result.scalar_one()

    async def daily(
        self, start: datetime, end: datetime, tz_name: str
    ) -> list[tuple[date, int, Decimal]]:
        """Orders and revenue per local calendar day."""
        if not re.fullmatch(r"[A-Za-z0-9_+\-/]+", tz_name):
            raise ValueError("Invalid timezone name")
        local_day = cast(
            func.timezone(literal_column(f"'{tz_name}'"), Order.created_at), Date
        )
        result = await self.session.execute(
            select(local_day, func.count(Order.id), func.sum(Order.total))
            .where(*self._in_period(start, end), Order.status != "cancelled")
            .group_by(local_day)
            .order_by(local_day)
        )
        return [(day, count, Decimal(total)) for day, count, total in result.all()]