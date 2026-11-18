from aiogram.filters import BaseFilter
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.repositories.user import UserRepository


class IsAdmin(BaseFilter):
    async def __call__(self, event: TelegramObject) -> bool:
        user = getattr(event, "from_user", None)
        return user is not None and user.id in settings.admin_id_list


class IsCourier(BaseFilter):
    async def __call__(self, event: TelegramObject, session: AsyncSession) -> bool:
        user = getattr(event, "from_user", None)
        if user is None:
            return False
        db_user = await UserRepository(session).get_by_telegram_id(user.id)
        return db_user is not None and db_user.role == "courier" and db_user.is_active