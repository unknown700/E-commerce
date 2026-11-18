from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models.product import Product
from app.repositories.inventory import InventoryRepository
from app.repositories.product import ProductRepository


class InventoryError(Exception):
    pass


class InventoryService:
    def __init__(self, session: AsyncSession):
        self.inventory = InventoryRepository(session)
        self.products = ProductRepository(session)

    async def _locked_product(self, product_id: int) -> Product:
        products = await self.products.get_for_update([product_id])
        if not products:
            raise InventoryError("Product not found.")
        return products[0]

    async def receive(self, product_id: int, quantity: int, user_id: int) -> Product:
        if quantity < 1:
            raise InventoryError("Quantity must be at least 1.")
        product = await self._locked_product(product_id)
        product.stock += quantity
        await self.inventory.add_movement(
            product.id, quantity, product.stock, "receipt", user_id=user_id
        )
        return product

    async def set_stock(self, product_id: int, new_stock: int, user_id: int) -> Product:
        product = await self._locked_product(product_id)
        delta = new_stock - product.stock
        if delta == 0:
            return product
        product.stock = new_stock
        await self.inventory.add_movement(
            product.id, delta, new_stock, "adjustment", user_id=user_id
        )
        return product

    async def low_stock(self) -> list[Product]:
        return await self.inventory.low_stock(settings.low_stock_threshold)

    async def recent_movements(self, limit: int = 15):
        return await self.inventory.recent_movements(limit)