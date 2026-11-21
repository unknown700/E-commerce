import logging
import re
from decimal import Decimal
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.formatting import PAYMENT_LABELS, format_price
from app.bot.handlers.cart import get_user
from app.bot.keyboards.cart import CartCb
from app.bot.keyboards.checkout import (
    ConfirmCb,
    DeliveryCb,
    confirm_kb,
    delivery_type_kb,
    location_kb,
    phone_kb,
)
from app.bot.keyboards.main_menu import main_menu_kb
from app.bot.notifications import notify_low_stock
from app.bot.states.checkout import Checkout
from app.config import settings
from app.database.models.order import Order
from app.database.models.user import User
from app.i18n import all_texts, t
from app.services.cart import CartService
from app.services.order import OrderError, OrderService
from app.services.promo import PromoService

logger = logging.getLogger(__name__)
router = Router()

DELIVERY_LABELS = {"delivery": "🚚 Delivery", "pickup": "🏪 Pickup"}  # admin messages
PHONE_RE = re.compile(r"\+?\d[\d\s\-()]{7,18}")


def build_summary(
    data: dict, items, subtotal, promo=None, discount=Decimal("0"), lang: str = "en"
) -> str:
    lines = [t(lang, "checkout.summary_title") + "\n"]
    for item in items:
        line_total = item.product.price * item.quantity
        lines.append(
            f"• {escape(item.product.name)} × {item.quantity} = {format_price(line_total)}"
        )
    if promo is not None:
        lines.append("\n" + t(lang, "cart.subtotal", amount=format_price(subtotal)))
        lines.append(
            t(lang, "order.promo", code=escape(promo.code), amount=format_price(discount))
        )
    lines.append(
        "\n" + t(lang, "cart.total", amount=format_price(subtotal - discount)) + "\n"
    )
    lines.append(
        t(lang, "order.receive", label=t(lang, f"btn.{data['delivery_type']}"))
    )
    if data.get("address"):
        lines.append(t(lang, "order.address", address=escape(data["address"])))
    lines.append(t(lang, "order.phone", phone=escape(data["phone"])))
    lines.append("\n" + t(lang, "checkout.choose_pay"))
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
    if order.discount and order.discount > 0:
        lines.append(
            f"\n🎟 Promo {escape(order.promo_code or '')}: -{format_price(order.discount)}"
        )
    lines.append(f"\n<b>Total: {format_price(order.total)}</b>")
    lines.append(
        f"Payment: {PAYMENT_LABELS.get(order.payment_method, order.payment_method)}"
    )
    text = "\n".join(lines)

    for admin_id in settings.admin_id_list:
        try:
            await bot.send_message(admin_id, text)
            if order.latitude is not None and order.longitude is not None:
                await bot.send_location(admin_id, order.latitude, order.longitude)
        except TelegramAPIError:
            logger.warning("Could not notify admin %s", admin_id)


async def ask_phone(message: Message, state: FSMContext, lang: str) -> None:
    await state.set_state(Checkout.phone)
    await message.answer(t(lang, "checkout.ask_phone"), reply_markup=phone_kb(lang))


async def show_summary(
    message: Message, state: FSMContext, session: AsyncSession, lang: str
) -> None:
    data = await state.get_data()
    user = await get_user(message.from_user, session)
    items, subtotal = await CartService(session).get_cart(user.id)
    if not items:
        await state.clear()
        await message.answer(t(lang, "cart.empty"), reply_markup=main_menu_kb(lang))
        return

    promo, discount, error = await PromoService(session).cart_discount(user.id, subtotal)
    if promo is not None and error:
        await state.clear()
        await message.answer(
            t(lang, "checkout.promo_invalid", code=escape(promo.code), reason=error),
            reply_markup=main_menu_kb(lang),
        )
        return

    await state.set_state(Checkout.confirm)
    await message.answer(t(lang, "checkout.review"), reply_markup=ReplyKeyboardRemove())
    await message.answer(
        build_summary(data, items, subtotal, promo, discount, lang),
        reply_markup=confirm_kb(online=settings.card_payments_enabled, lang=lang),
    )


# ---- cancel (must be registered before the other state handlers) ----
@router.message(StateFilter(Checkout), F.text.in_(all_texts("btn.cancel")))
async def cancel_by_text(message: Message, state: FSMContext, lang: str):
    await state.clear()
    await message.answer(t(lang, "checkout.cancelled"), reply_markup=main_menu_kb(lang))


@router.callback_query(ConfirmCb.filter(F.action == "no"))
async def cancel_by_button(call: CallbackQuery, state: FSMContext, lang: str):
    await state.clear()
    await call.message.edit_text(t(lang, "checkout.cancelled"))
    await call.message.answer(t(lang, "checkout.main_menu"), reply_markup=main_menu_kb(lang))
    await call.answer()


# ---- step 1: start checkout from the cart ----
@router.callback_query(CartCb.filter(F.action == "checkout"))
async def start_checkout(
    call: CallbackQuery, state: FSMContext, session: AsyncSession, lang: str
):
    user = await get_user(call.from_user, session)
    items, _ = await CartService(session).get_cart(user.id)
    if not items:
        await call.answer(t(lang, "cart.empty"), show_alert=True)
        return

    await state.clear()
    await state.set_state(Checkout.delivery_type)
    await call.message.answer(
        t(lang, "checkout.how_receive"), reply_markup=delivery_type_kb(lang)
    )
    await call.answer()


# ---- step 2: delivery or pickup ----
@router.callback_query(Checkout.delivery_type, DeliveryCb.filter())
async def choose_delivery(
    call: CallbackQuery, callback_data: DeliveryCb, state: FSMContext, lang: str
):
    kind = callback_data.kind
    await state.update_data(delivery_type=kind)
    await call.message.edit_text(
        t(lang, "checkout.selected", label=t(lang, f"btn.{kind}"))
    )

    if kind == "delivery":
        await state.set_state(Checkout.location)
        await call.message.answer(
            t(lang, "checkout.ask_location"), reply_markup=location_kb(lang)
        )
    else:
        await state.update_data(address=None, latitude=None, longitude=None)
        await ask_phone(call.message, state, lang)
    await call.answer()


# ---- step 3: location or address (delivery only) ----
@router.message(Checkout.location, F.location)
async def got_location(message: Message, state: FSMContext, lang: str):
    await state.update_data(
        latitude=message.location.latitude,
        longitude=message.location.longitude,
        address="📍",
    )
    await ask_phone(message, state, lang)


@router.message(Checkout.location, F.text)
async def got_address(message: Message, state: FSMContext, lang: str):
    address = message.text.strip()
    if len(address) < 5:
        await message.answer(t(lang, "checkout.address_short"))
        return
    await state.update_data(address=address, latitude=None, longitude=None)
    await ask_phone(message, state, lang)


# ---- step 4: phone number ----
@router.message(Checkout.phone, F.contact)
async def got_contact(
    message: Message, state: FSMContext, session: AsyncSession, lang: str
):
    await state.update_data(phone=message.contact.phone_number)
    await show_summary(message, state, session, lang)


@router.message(Checkout.phone, F.text)
async def got_phone_text(
    message: Message, state: FSMContext, session: AsyncSession, lang: str
):
    text = message.text.strip()
    if not PHONE_RE.fullmatch(text):
        await message.answer(t(lang, "checkout.bad_phone"))
        return
    await state.update_data(phone=re.sub(r"[\s\-()]", "", text))
    await show_summary(message, state, session, lang)


# ---- step 5: pay cash on delivery ----
@router.callback_query(Checkout.confirm, ConfirmCb.filter(F.action == "yes"))
async def confirm_order(
    call: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    bot: Bot,
    lang: str,
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
        await call.message.edit_text(
            t(lang, "checkout.error", error=escape(str(error)))
        )
        await call.message.answer(
            t(lang, "checkout.main_menu"), reply_markup=main_menu_kb(lang)
        )
        await call.answer()
        return

    await state.clear()
    await call.message.edit_text(t(lang, "checkout.placed", id=order.id))
    await call.message.answer(t(lang, "checkout.main_menu"), reply_markup=main_menu_kb(lang))
    await notify_admins(bot, order, user)
    await notify_low_stock(bot, low_stock)
    await call.answer()