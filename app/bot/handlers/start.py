from html import escape

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.language import language_kb
from app.bot.keyboards.main_menu import main_menu_kb
from app.i18n import detect_language, t
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
        
        await service.set_language(user.id, detect_language(tg_user.language_code))
        await message.answer(t("en", "lang.choose"), reply_markup=language_kb())
        return

    await message.answer(
        t(user.language, "start.welcome_back", name=escape(user.full_name)),
        reply_markup=main_menu_kb(user.language),
    )