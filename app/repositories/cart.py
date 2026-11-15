from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.database.models.cart_item import CartItem


class CartRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_items(self, user_id: int) -> list[CartItem]:
        result = await self.session.execute(
            select(CartItem)
            .where(CartItem.user_id == user_id)
            .options(joinedload(CartItem.product))
            .order_by(CartItem.id)
        )
        return list(result.scalars().all())

    async def get_item(self, user_id: int, product_id: int) -> CartItem | None:
        result = await self.session.execute(
            select(CartItem).where(
                CartItem.user_id == user_id, CartItem.product_id == product_id
            )
        )
        return result.scalar_one_or_none()

    async def add(self, user_id: int, product_id: int, quantity: int = 1) -> CartItem:
        item = CartItem(user_id=user_id, product_id=product_id, quantity=quantity)
        self.session.add(item)
        await self.session.flush()
        return item

    async def delete(self, item: CartItem) -> None:
        await self.session.delete(item)

    async def clear(self, user_id: int) -> None:
        await self.session.execute(delete(CartItem).where(CartItem.user_id == user_id))