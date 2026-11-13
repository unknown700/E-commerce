from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.main_menu import main_menu_kb
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
        await message.answer(
            f"Welcome, {user.full_name}! You have successfully registered.",
            reply_markup=main_menu_kb(),
        )
    else:
        await message.answer(
            f"Welcome back, {user.full_name}!",
            reply_markup=main_menu_kb(),
        )