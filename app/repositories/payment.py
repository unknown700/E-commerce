from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.payment import Payment


class PaymentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, payment: Payment) -> Payment:
        self.session.add(payment)
        await self.session.flush()
        return payment

    async def get_by_id(self, payment_id: int, for_update: bool = False) -> Payment | None:
        query = select(Payment).where(Payment.id == payment_id)
        if for_update:
            query = query.with_for_update()
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_order(self, order_id: int) -> Payment | None:
        result = await self.session.execute(
            select(Payment).where(Payment.order_id == order_id)
        )
        return result.scalar_one_or_none()

    async def recent(self, limit: int = 15) -> list[Payment]:
        result = await self.session.execute(
            select(Payment).order_by(Payment.id.desc()).limit(limit)
        )
        return list(result.scalars().all())