from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models.order import Order


class OrderRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, order: Order) -> Order:
        self.session.add(order)
        await self.session.flush()
        return order

    async def get_by_id(self, order_id: int, for_update: bool = False) -> Order | None:
        query = (
            select(Order)
            .where(Order.id == order_id)
            .options(selectinload(Order.items))
        )
        if for_update:
            query = query.with_for_update(of=Order)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_user(self, user_id: int, limit: int = 10) -> list[Order]:
        result = await self.session.execute(
            select(Order)
            .where(Order.user_id == user_id)
            .order_by(Order.id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_statuses(self, statuses: list[str], limit: int = 20) -> list[Order]:
        result = await self.session.execute(
            select(Order)
            .where(Order.status.in_(statuses))
            .order_by(Order.id)
            .limit(limit)
        )
        return list(result.scalars().all())


    async def get_by_courier(
        self, courier_id: int, statuses: list[str], limit: int = 20
    ) -> list[Order]:
        result = await self.session.execute(
            select(Order)
            .where(Order.courier_id == courier_id, Order.status.in_(statuses))
            .order_by(Order.id)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_for_courier(self, courier_id: int, statuses: list[str]) -> int:
        result = await self.session.execute(
            select(func.count(Order.id)).where(
                Order.courier_id == courier_id, Order.status.in_(statuses)
            )
        )
        return result.scalar_one()    