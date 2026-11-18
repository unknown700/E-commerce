from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.category import Category
from app.database.models.product import Product
from app.database.models.stock_movement import StockMovement
from app.database.models.user import User


class InventoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_movement(
        self,
        product_id: int,
        delta: int,
        stock_after: int,
        reason: str,
        order_id: int | None = None,
        user_id: int | None = None,
    ) -> StockMovement:
        movement = StockMovement(
            product_id=product_id,
            delta=delta,
            stock_after=stock_after,
            reason=reason,
            order_id=order_id,
            user_id=user_id,
        )
        self.session.add(movement)
        await self.session.flush()
        return movement

    async def recent_movements(self, limit: int = 20):
        result = await self.session.execute(
            select(StockMovement, Product.name, User.full_name)
            .join(Product, Product.id == StockMovement.product_id)
            .outerjoin(User, User.id == StockMovement.user_id)
            .order_by(StockMovement.id.desc())
            .limit(limit)
        )
        return [(m, product_name, user_name) for m, product_name, user_name in result.all()]

    async def low_stock(self, threshold: int) -> list[Product]:
        result = await self.session.execute(
            select(Product)
            .where(Product.is_active.is_(True), Product.stock <= threshold)
            .order_by(Product.stock, Product.name)
        )
        return list(result.scalars().all())

    async def products_with_category(self):
        result = await self.session.execute(
            select(Product, Category.name)
            .join(Category, Category.id == Product.category_id)
            .order_by(Category.name, Product.name)
        )
        return [(product, category_name) for product, category_name in result.all()]