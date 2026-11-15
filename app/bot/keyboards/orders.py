from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.formatting import ACTION_LABELS, STATUS_LABELS, format_price
from app.bot.keyboards.catalog import NavCb
from app.bot.keyboards.admin import AdminCb


class MyOrderCb(CallbackData, prefix="myorder"):
    id: int


class AdminOrderCb(CallbackData, prefix="aorder"):
    id: int


class StatusCb(CallbackData, prefix="ostatus"):
    id: int
    status: str


def _order_label(order) -> str:
    return f"#{order.id} · {STATUS_LABELS[order.status]} · {format_price(order.total)}"


def my_orders_kb(orders) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for order in orders:
        builder.button(text=_order_label(order), callback_data=MyOrderCb(id=order.id))
    builder.adjust(1)
    return builder.as_markup()


def my_order_detail_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ My orders", callback_data=NavCb(to="my_orders"))
    return builder.as_markup()


def admin_orders_kb(orders) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for order in orders:
        builder.button(text=_order_label(order), callback_data=AdminOrderCb(id=order.id))
    builder.button(text="🔄 Refresh", callback_data=NavCb(to="admin_orders"))
    builder.button(text="⬅️ Admin menu", callback_data=AdminCb(action="menu"))
    builder.adjust(1)
    return builder.as_markup()


def admin_order_kb(order_id: int, statuses: list[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for status in statuses:
        builder.button(
            text=ACTION_LABELS[status],
            callback_data=StatusCb(id=order_id, status=status),
        )
    builder.button(text="⬅️ Back to orders", callback_data=NavCb(to="admin_orders"))
    builder.adjust(1)
    return builder.as_markup()