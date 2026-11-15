from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.cart_item import CartItem
from app.repositories.cart import CartRepository
from app.repositories.product import ProductRepository


class CartService:
    def __init__(self, session: AsyncSession):
        self.cart = CartRepository(session)
        self.products = ProductRepository(session)

    async def add_product(self, user_id: int, product_id: int) -> str:
        product = await self.products.get_by_id(product_id)
        if product is None or not product.is_active:
            return "not_found"
        if product.stock <= 0:
            return "out_of_stock"

        item = await self.cart.get_item(user_id, product_id)
        if item is None:
            await self.cart.add(user_id, product_id)
            return "added"
        if item.quantity >= product.stock:
            return "max"
        item.quantity += 1
        return "added"

    async def change_quantity(self, user_id: int, product_id: int, delta: int) -> str:
        item = await self.cart.get_item(user_id, product_id)
        if item is None:
            return "not_found"

        new_quantity = item.quantity + delta
        if new_quantity <= 0:
            await self.cart.delete(item)
            return "removed"

        product = await self.products.get_by_id(product_id)
        if product is None or new_quantity > product.stock:
            return "max"
        item.quantity = new_quantity
        return "ok"

    async def remove(self, user_id: int, product_id: int) -> None:
        item = await self.cart.get_item(user_id, product_id)
        if item is not None:
            await self.cart.delete(item)

    async def clear(self, user_id: int) -> None:
        await self.cart.clear(user_id)

    async def get_cart(self, user_id: int) -> tuple[list[CartItem], Decimal]:
        items = await self.cart.get_items(user_id)
        total = sum((i.product.price * i.quantity for i in items), Decimal("0"))
        return items, total