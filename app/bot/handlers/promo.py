from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.cart import get_user, render_cart
from app.bot.keyboards.cart import CartCb
from app.bot.states.promo import EnterPromo
from app.i18n import all_texts, t
from app.services.cart import CartService
from app.services.promo import PromoError, PromoService

router = Router()

MENU_TEXTS = (
    all_texts("menu.catalog")
    | all_texts("menu.cart")
    | all_texts("menu.orders")
    | all_texts("menu.language")
)


@router.callback_query(CartCb.filter(F.action == "promo"))
async def promo_start(
    call: CallbackQuery, state: FSMContext, session: AsyncSession, lang: str
):
    user = await get_user(call.from_user, session)
    items, _ = await CartService(session).get_cart(user.id)
    if not items:
        await call.answer(t(lang, "cart.empty"), show_alert=True)
        return
    await state.clear()
    await state.set_state(EnterPromo.code)
    await call.message.answer(t(lang, "promo.ask"))
    await call.answer()


@router.message(Command("cancel"), StateFilter(EnterPromo))
async def promo_cancel(message: Message, state: FSMContext, lang: str):
    await state.clear()
    await message.answer(t(lang, "promo.cancelled"))


@router.message(
    EnterPromo.code, F.text, ~F.text.startswith("/"), ~F.text.in_(MENU_TEXTS)
)
async def promo_code(
    message: Message, state: FSMContext, session: AsyncSession, lang: str
):
    user = await get_user(message.from_user, session)
    items, subtotal = await CartService(session).get_cart(user.id)
    if not items:
        await state.clear()
        await message.answer(t(lang, "cart.empty"))
        return

    try:
        promo, _discount = await PromoService(session).apply_code(
            user.id, message.text, subtotal
        )
    except PromoError as error:
        await message.answer(t(lang, "promo.try_again", error=error))
        return

    await state.clear()
    await message.answer(t(lang, "promo.applied", code=promo.code))
    text, keyboard = await render_cart(user.id, session, lang)
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(CartCb.filter(F.action == "promo_remove"))
async def promo_remove(call: CallbackQuery, session: AsyncSession, lang: str):
    user = await get_user(call.from_user, session)
    await PromoService(session).remove(user.id)
    text, keyboard = await render_cart(user.id, session, lang)
    try:
        await call.message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest:
        pass
    await call.answer(t(lang, "promo.removed"))