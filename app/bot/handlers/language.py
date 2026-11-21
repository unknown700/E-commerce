from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.language import LangCb, language_kb
from app.bot.keyboards.main_menu import main_menu_kb
from app.i18n import LANGUAGES, all_texts, t
from app.services.user import UserService

router = Router()


@router.message(Command("language"))
@router.message(F.text.in_(all_texts("menu.language")))
async def language_menu(message: Message):
    await message.answer(t("en", "lang.choose"), reply_markup=language_kb())


@router.callback_query(LangCb.filter())
async def choose_language(
    call: CallbackQuery, callback_data: LangCb, session: AsyncSession
):
    code = callback_data.code
    if code not in LANGUAGES:
        await call.answer()
        return

    tg_user = call.from_user
    service = UserService(session)
    user, _ = await service.register(tg_user.id, tg_user.username, tg_user.full_name)
    await service.set_language(user.id, code)

    await call.message.edit_text(t(code, "lang.changed"))
    await call.message.answer(
        t(code, "start.welcome", name=escape(user.full_name)),
        reply_markup=main_menu_kb(code),
    )
    await call.answer()