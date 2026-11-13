from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.user import User
from app.repositories.user import UserRepository


class UserService:
    def __init__(self, session: AsyncSession):
        self.repo = UserRepository(session)

    async def register(
        self, telegram_id: int, username: str | None, full_name: str
    ) -> tuple[User, bool]:
        user = await self.repo.get_by_telegram_id(telegram_id)
        if user:
            return user, False
        user = await self.repo.create(telegram_id, username, full_name)
        return user, True