from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.user import UserService

router = Router()


@router.message(CommandStart())
async def start(message: Message, session: AsyncSession):
    tg_user = message.from_user
    service = UserService(session)
    user, created = await service.register(
        telegram_id=tg_user.id,
        username=tg_user.username,
        full_name=tg_user.full_name,
    )

    if created:
        await message.answer(f"Xush kelibsiz, {user.full_name}! Siz ro'yxatdan o'tdingiz.")
    else:
        await message.answer(f"Qaytganingiz bilan, {user.full_name}!")