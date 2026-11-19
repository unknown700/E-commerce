from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.cart import get_user, render_cart
from app.bot.keyboards.cart import CartCb
from app.bot.states.promo import EnterPromo
from app.services.cart import CartService
from app.services.promo import PromoError, PromoService

router = Router()

MENU_TEXTS = {"🛍 Catalog", "🛒 Cart", "📦 My orders"}


@router.callback_query(CartCb.filter(F.action == "promo"))
async def promo_start(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    user = await get_user(call.from_user, session)
    items, _ = await CartService(session).get_cart(user.id)
    if not items:
        await call.answer("Your cart is empty.", show_alert=True)
        return
    await state.clear()
    await state.set_state(EnterPromo.code)
    await call.message.answer("🎟 Send your promo code (or /cancel):")
    await call.answer()


@router.message(Command("cancel"), StateFilter(EnterPromo))
async def promo_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Cancelled.")


@router.message(
    EnterPromo.code, F.text, ~F.text.startswith("/"), ~F.text.in_(MENU_TEXTS)
)
async def promo_code(message: Message, state: FSMContext, session: AsyncSession):
    user = await get_user(message.from_user, session)
    items, subtotal = await CartService(session).get_cart(user.id)
    if not items:
        await state.clear()
        await message.answer("Your cart is empty.")
        return

    try:
        promo, _discount = await PromoService(session).apply_code(
            user.id, message.text, subtotal
        )
    except PromoError as error:
        await message.answer(f"❌ {error}\nTry another code or /cancel.")
        return

    await state.clear()
    await message.answer(f"✅ Promo code <b>{promo.code}</b> applied.")
    text, keyboard = await render_cart(user.id, session)
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(CartCb.filter(F.action == "promo_remove"))
async def promo_remove(call: CallbackQuery, session: AsyncSession):
    user = await get_user(call.from_user, session)
    await PromoService(session).remove(user.id)
    text, keyboard = await render_cart(user.id, session)
    try:
        await call.message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest:
        pass
    await call.answer("Promo code removed")