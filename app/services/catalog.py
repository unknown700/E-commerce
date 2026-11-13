from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.category import Category
from app.database.models.product import Product
from app.repositories.category import CategoryRepository
from app.repositories.product import ProductRepository


class CatalogService:
    def __init__(self, session: AsyncSession):
        self.categories = CategoryRepository(session)
        self.products = ProductRepository(session)

    async def list_categories(self) -> list[Category]:
        return await self.categories.get_active()

    async def list_products(self, category_id: int) -> list[Product]:
        return await self.products.get_active_by_category(category_id)

    async def get_product(self, product_id: int) -> Product | None:
        return await self.products.get_by_id(product_id)