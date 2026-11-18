from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.formatting import STATUS_LABELS
from app.bot.keyboards.admin import AdminCb
from app.bot.keyboards.orders import AdminOrderCb


class CourierCb(CallbackData, prefix="cour"):
    action: str  # list / view / pickup / deliver
    id: int = 0


class AssignCb(CallbackData, prefix="assign"):
    order_id: int
    courier_id: int


def _name(user) -> str:
    return user.full_name + (f" (@{user.username})" if user.username else "")


def couriers_admin_kb(couriers) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for courier in couriers:
        builder.button(
            text=f"❌ {_name(courier)}",
            callback_data=AdminCb(action="cour_remove", id=courier.id),
        )
    builder.button(text="➕ Add courier", callback_data=AdminCb(action="cour_add"))
    builder.button(text="⬅️ Admin menu", callback_data=AdminCb(action="menu"))
    builder.adjust(1)
    return builder.as_markup()


def assign_kb(order_id: int, couriers) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for courier in couriers:
        builder.button(
            text=_name(courier),
            callback_data=AssignCb(order_id=order_id, courier_id=courier.id),
        )
    builder.button(text="⬅️ Back", callback_data=AdminOrderCb(id=order_id))
    builder.adjust(1)
    return builder.as_markup()


def courier_open_kb(order_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📦 Open order", callback_data=CourierCb(action="view", id=order_id))
    return builder.as_markup()


def courier_orders_kb(orders) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for order in orders:
        builder.button(
            text=f"#{order.id} · {STATUS_LABELS[order.status]}",
            callback_data=CourierCb(action="view", id=order.id),
        )
    builder.button(text="🔄 Refresh", callback_data=CourierCb(action="list"))
    builder.adjust(1)
    return builder.as_markup()


def courier_refresh_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Refresh", callback_data=CourierCb(action="list"))
    return builder.as_markup()


def courier_order_kb(order) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if order.status == "preparing":
        builder.button(
            text="📦 Picked up", callback_data=CourierCb(action="pickup", id=order.id)
        )
    elif order.status == "on_the_way":
        builder.button(
            text="✅ Delivered", callback_data=CourierCb(action="deliver", id=order.id)
        )
    builder.button(text="⬅️ My deliveries", callback_data=CourierCb(action="list"))
    builder.adjust(1)
    return builder.as_markup()