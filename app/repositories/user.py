from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self, telegram_id: int, username: str | None, full_name: str
    ) -> User:
        user = User(telegram_id=telegram_id, username=username, full_name=full_name)
        self.session.add(user)
        await self.session.flush()
        return user


    async def get_by_id(self, user_id: int) -> User | None:
        return await self.session.get(User, user_id)


    async def get_by_username(self, username: str) -> User | None:
        result = await self.session.execute(
            select(User).where(func.lower(User.username) == username.lower())
        )
        return result.scalar_one_or_none()

    async def get_by_role(self, role: str) -> list[User]:
        result = await self.session.execute(
            select(User)
            .where(User.role == role, User.is_active.is_(True))
            .order_by(User.full_name)
        )
        return list(result.scalars().all())    