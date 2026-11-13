from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.category import Category


class CategoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_active(self) -> list[Category]:
        result = await self.session.execute(
            select(Category).where(Category.is_active.is_(True)).order_by(Category.name)
        )
        return list(result.scalars().all())