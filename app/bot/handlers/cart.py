from html import escape

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.types import User as TgUser
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.formatting import format_price
from app.bot.keyboards.catalog import AddCb
from app.bot.keyboards.cart import CartCb, cart_kb
from app.database.models.user import User
from app.services.cart import CartService
from app.services.user import UserService
from app.services.promo import PromoService

router = Router()


async def get_user(tg_user: TgUser, session: AsyncSession) -> User:
    user, _ = await UserService(session).register(
        telegram_id=tg_user.id,
        username=tg_user.username,
        full_name=tg_user.full_name,
    )
    return user


async def render_cart(
    user_id: int, session: AsyncSession
) -> tuple[str, InlineKeyboardMarkup | None]:
    items, subtotal = await CartService(session).get_cart(user_id)
    if not items:
        return "Your cart is empty.", None

    promo, discount, error = await PromoService(session).cart_discount(
        user_id, subtotal
    )

    lines = ["🛒 <b>Your cart</b>\n"]
    for item in items:
        line_total = item.product.price * item.quantity
        lines.append(
            f"{escape(item.product.name)}\n"
            f"   {item.quantity} × {format_price(item.product.price)} = {format_price(line_total)}"
        )

    if promo is None:
        lines.append(f"\n<b>Total: {format_price(subtotal)}</b>")
    else:
        lines.append(f"\nSubtotal: {format_price(subtotal)}")
        if error:
            lines.append(f"⚠️ Promo <b>{escape(promo.code)}</b> is not valid: {error}")
            payable = subtotal
        else:
            lines.append(f"🎟 Promo <b>{escape(promo.code)}</b>: -{format_price(discount)}")
            payable = subtotal - discount
        lines.append(f"<b>Total: {format_price(payable)}</b>")

    return "\n".join(lines), cart_kb(items, has_promo=promo is not None)


@router.message(Command("cart"))
@router.message(F.text == "🛒 Cart")
async def show_cart(message: Message, session: AsyncSession):
    user = await get_user(message.from_user, session)
    text, keyboard = await render_cart(user.id, session)
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(AddCb.filter())
async def add_to_cart(call: CallbackQuery, callback_data: AddCb, session: AsyncSession):
    user = await get_user(call.from_user, session)
    result = await CartService(session).add_product(user.id, callback_data.product_id)

    messages = {
        "added": "Added to cart ✅",
        "max": "You already have the maximum available quantity",
        "out_of_stock": "Sorry, this product is out of stock",
        "not_found": "Product not found",
    }
    await call.answer(messages[result], show_alert=result != "added")


@router.callback_query(CartCb.filter(F.action.in_({"inc", "dec", "del", "clear"})))
async def cart_action(call: CallbackQuery, callback_data: CartCb, session: AsyncSession):
    user = await get_user(call.from_user, session)
    service = CartService(session)

    if callback_data.action == "inc":
        result = await service.change_quantity(user.id, callback_data.product_id, +1)
        if result == "max":
            await call.answer("No more items in stock", show_alert=True)
            return
    elif callback_data.action == "dec":
        await service.change_quantity(user.id, callback_data.product_id, -1)
    elif callback_data.action == "del":
        await service.remove(user.id, callback_data.product_id)
    elif callback_data.action == "clear":
        await service.clear(user.id)

    text, keyboard = await render_cart(user.id, session)
    try:
        await call.message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest:
        pass  # message content did not change
    await call.answer()