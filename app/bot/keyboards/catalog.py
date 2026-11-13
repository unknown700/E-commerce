from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.formatting import format_price


class CategoryCb(CallbackData, prefix="cat"):
    id: int


class ProductCb(CallbackData, prefix="prod"):
    id: int


class NavCb(CallbackData, prefix="nav"):
    to: str


def categories_kb(categories) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for category in categories:
        builder.button(text=category.name, callback_data=CategoryCb(id=category.id))
    builder.adjust(1)
    return builder.as_markup()


def products_kb(products) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for product in products:
        builder.button(
            text=f"{product.name} — {format_price(product.price)}",
            callback_data=ProductCb(id=product.id),
        )
    builder.button(text="⬅️ Categories", callback_data=NavCb(to="categories"))
    builder.adjust(1)
    return builder.as_markup()


def product_kb(category_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Before", callback_data=CategoryCb(id=category_id))
    return builder.as_markup()