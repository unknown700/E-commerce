from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.order import Order
from app.database.models.promo import CartPromo, PromoCode


class PromoRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_code(self, code: str) -> PromoCode | None:
        result = await self.session.execute(
            select(PromoCode).where(PromoCode.code == code)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, promo_id: int, for_update: bool = False) -> PromoCode | None:
        query = select(PromoCode).where(PromoCode.id == promo_id)
        if for_update:
            query = query.with_for_update()
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def add(self, promo: PromoCode) -> PromoCode:
        self.session.add(promo)
        await self.session.flush()
        return promo

    async def list_with_usage(self, limit: int = 30) -> list[tuple[PromoCode, int]]:
        """Each promo code with the number of non-cancelled orders that used it."""
        result = await self.session.execute(
            select(PromoCode, func.count(Order.id))
            .outerjoin(
                Order,
                and_(Order.promo_code_id == PromoCode.id, Order.status != "cancelled"),
            )
            .group_by(PromoCode.id)
            .order_by(PromoCode.id.desc())
            .limit(limit)
        )
        return [(promo, uses) for promo, uses in result.all()]

    async def count_uses(self, promo_id: int) -> int:
        result = await self.session.execute(
            select(func.count(Order.id)).where(
                Order.promo_code_id == promo_id, Order.status != "cancelled"
            )
        )
        return result.scalar_one()

    async def count_user_uses(self, promo_id: int, user_id: int) -> int:
        result = await self.session.execute(
            select(func.count(Order.id)).where(
                Order.promo_code_id == promo_id,
                Order.user_id == user_id,
                Order.status != "cancelled",
            )
        )
        return result.scalar_one()

    async def get_cart_promo(self, user_id: int) -> CartPromo | None:
        result = await self.session.execute(
            select(CartPromo).where(CartPromo.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def set_cart_promo(self, user_id: int, promo_id: int) -> None:
        existing = await self.get_cart_promo(user_id)
        if existing is None:
            self.session.add(CartPromo(user_id=user_id, promo_id=promo_id))
        else:
            existing.promo_id = promo_id
        await self.session.flush()

    async def clear_cart_promo(self, user_id: int) -> None:
        existing = await self.get_cart_promo(user_id)
        if existing is not None:
            await self.session.delete(existing)
            await self.session.flush()