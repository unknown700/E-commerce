from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.product import Product


class ProductRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_active_by_category(self, category_id: int) -> list[Product]:
        result = await self.session.execute(
            select(Product)
            .where(Product.category_id == category_id, Product.is_active.is_(True))
            .order_by(Product.name)
        )
        return list(result.scalars().all())

    async def get_by_id(self, product_id: int) -> Product | None:
        return await self.session.get(Product, product_id)





    async def get_for_update(self, product_ids: list[int]) -> list[Product]:
        result = await self.session.execute(
            select(Product)
            .where(Product.id.in_(product_ids))
            .order_by(Product.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return list(result.scalars().all())


    async def add(self, product: Product) -> Product:
        self.session.add(product)
        await self.session.flush()
        return product    