import logging
import re
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.formatting import format_price
from app.bot.handlers.cart import get_user
from app.bot.keyboards.cart import CartCb
from app.bot.keyboards.checkout import (
    CANCEL_TEXT,
    ConfirmCb,
    DeliveryCb,
    confirm_kb,
    delivery_type_kb,
    location_kb,
    phone_kb,
)
from app.bot.keyboards.main_menu import main_menu_kb
from app.bot.states.checkout import Checkout
from app.config import settings
from app.database.models.order import Order
from app.database.models.user import User
from app.services.cart import CartService
from app.services.order import OrderError, OrderService
from app.bot.notifications import notify_low_stock

logger = logging.getLogger(__name__)
router = Router()

DELIVERY_LABELS = {"delivery": "🚚 Delivery", "pickup": "🏪 Pickup"}
PHONE_RE = re.compile(r"\+?\d[\d\s\-()]{7,18}")


def build_summary(data: dict, items, total) -> str:
    lines = ["📋 <b>Order summary</b>\n"]
    for item in items:
        subtotal = item.product.price * item.quantity
        lines.append(
            f"• {escape(item.product.name)} × {item.quantity} = {format_price(subtotal)}"
        )
    lines.append(f"\n<b>Total: {format_price(total)}</b>\n")
    lines.append(f"Receive: {DELIVERY_LABELS[data['delivery_type']]}")
    if data.get("address"):
        lines.append(f"Address: {escape(data['address'])}")
    lines.append(f"Phone: {escape(data['phone'])}")
    lines.append("Payment: 💵 Cash")
    return "\n".join(lines)


async def notify_admins(bot: Bot, order: Order, customer: User) -> None:
    name = escape(customer.full_name)
    if customer.username:
        name += f" (@{escape(customer.username)})"

    lines = [f"🆕 <b>New order #{order.id}</b>\n", f"Customer: {name}"]
    lines.append(f"Phone: {escape(order.phone)}")
    lines.append(f"Receive: {DELIVERY_LABELS[order.delivery_type]}")
    if order.address:
        lines.append(f"Address: {escape(order.address)}")
    lines.append("\nItems:")
    for item in order.items:
        subtotal = item.unit_price * item.quantity
        lines.append(
            f"• {escape(item.product_name)} × {item.quantity} = {format_price(subtotal)}"
        )
    lines.append(f"\n<b>Total: {format_price(order.total)}</b>")
    lines.append("Payment: 💵 Cash")
    text = "\n".join(lines)

    for admin_id in settings.admin_id_list:
        try:
            await bot.send_message(admin_id, text)
            if order.latitude is not None and order.longitude is not None:
                await bot.send_location(admin_id, order.latitude, order.longitude)
        except TelegramAPIError:
            logger.warning("Could not notify admin %s", admin_id)


async def ask_phone(message: Message, state: FSMContext) -> None:
    await state.set_state(Checkout.phone)
    await message.answer(
        "Please share your phone number with the button below, or type it (e.g. +998901234567):",
        reply_markup=phone_kb(),
    )


async def show_summary(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    user = await get_user(message.from_user, session)
    items, total = await CartService(session).get_cart(user.id)
    if not items:
        await state.clear()
        await message.answer("Your cart is empty.", reply_markup=main_menu_kb())
        return

    await state.set_state(Checkout.confirm)
    await message.answer("Thanks! Please review your order.", reply_markup=ReplyKeyboardRemove())
    await message.answer(build_summary(data, items, total), reply_markup=confirm_kb())


# ---- cancel (must be registered before the other state handlers) ----
@router.message(StateFilter(Checkout), F.text == CANCEL_TEXT)
async def cancel_by_text(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Order cancelled. Your cart is still saved.", reply_markup=main_menu_kb()
    )


@router.callback_query(ConfirmCb.filter(F.action == "no"))
async def cancel_by_button(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("Order cancelled. Your cart is still saved.")
    await call.message.answer("Back to the main menu.", reply_markup=main_menu_kb())
    await call.answer()


# ---- step 1: start checkout from the cart ----
@router.callback_query(CartCb.filter(F.action == "checkout"))
async def start_checkout(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    user = await get_user(call.from_user, session)
    items, _ = await CartService(session).get_cart(user.id)
    if not items:
        await call.answer("Your cart is empty.", show_alert=True)
        return

    await state.clear()
    await state.set_state(Checkout.delivery_type)
    await call.message.answer(
        "How would you like to receive your order?", reply_markup=delivery_type_kb()
    )
    await call.answer()


# ---- step 2: delivery or pickup ----
@router.callback_query(Checkout.delivery_type, DeliveryCb.filter())
async def choose_delivery(
    call: CallbackQuery, callback_data: DeliveryCb, state: FSMContext
):
    kind = callback_data.kind
    await state.update_data(delivery_type=kind)
    await call.message.edit_text(f"Selected: {DELIVERY_LABELS[kind]}")

    if kind == "delivery":
        await state.set_state(Checkout.location)
        await call.message.answer(
            "Send your location with the button below, or type your delivery address:",
            reply_markup=location_kb(),
        )
    else:
        await state.update_data(address=None, latitude=None, longitude=None)
        await ask_phone(call.message, state)
    await call.answer()


# ---- step 3: location or address (delivery only) ----
@router.message(Checkout.location, F.location)
async def got_location(message: Message, state: FSMContext):
    await state.update_data(
        latitude=message.location.latitude,
        longitude=message.location.longitude,
        address="Shared location",
    )
    await ask_phone(message, state)


@router.message(Checkout.location, F.text)
async def got_address(message: Message, state: FSMContext):
    address = message.text.strip()
    if len(address) < 5:
        await message.answer("Please send a more detailed address.")
        return
    await state.update_data(address=address, latitude=None, longitude=None)
    await ask_phone(message, state)


# ---- step 4: phone number ----
@router.message(Checkout.phone, F.contact)
async def got_contact(message: Message, state: FSMContext, session: AsyncSession):
    await state.update_data(phone=message.contact.phone_number)
    await show_summary(message, state, session)


@router.message(Checkout.phone, F.text)
async def got_phone_text(message: Message, state: FSMContext, session: AsyncSession):
    text = message.text.strip()
    if not PHONE_RE.fullmatch(text):
        await message.answer("That doesn't look like a phone number. Please try again.")
        return
    await state.update_data(phone=re.sub(r"[\s\-()]", "", text))
    await show_summary(message, state, session)


# ---- step 5: confirm ----
@router.callback_query(Checkout.confirm, ConfirmCb.filter(F.action == "yes"))
async def confirm_order(
    call: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot
):
    data = await state.get_data()
    user = await get_user(call.from_user, session)

    try:
            order, low_stock = await OrderService(session).create_order(
            user_id=user.id,
            delivery_type=data["delivery_type"],
            phone=data["phone"],
            address=data.get("address"),
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
        )
    except OrderError as error:
        await state.clear()
        await call.message.edit_text(f"❌ {error}\n\nPlease check your cart and try again.")
        await call.message.answer("Back to the main menu.", reply_markup=main_menu_kb())
        await call.answer()
        return

    await state.clear()
    await call.message.edit_text(
        f"✅ <b>Order #{order.id} placed!</b>\n\nWe will contact you soon. Thank you!"
    )
    await call.message.answer("Back to the main menu.", reply_markup=main_menu_kb())
    await notify_admins(bot, order, user)
    await notify_low_stock(bot, low_stock)
    await call.answer()