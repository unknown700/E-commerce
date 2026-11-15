from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.keyboards.catalog import NavCb


class AdminCb(CallbackData, prefix="adm"):
    action: str
    id: int = 0


def admin_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Orders", callback_data=NavCb(to="admin_orders"))
    builder.button(text="🗂 Categories", callback_data=AdminCb(action="categories"))
    builder.button(text="➕ Add product", callback_data=AdminCb(action="prod_add"))
    builder.adjust(1)
    return builder.as_markup()


def categories_admin_kb(categories) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for category in categories:
        icon = "✅" if category.is_active else "🚫"
        builder.button(
            text=f"{icon} {category.name}",
            callback_data=AdminCb(action="cat_toggle", id=category.id),
        )
    builder.button(text="➕ Add category", callback_data=AdminCb(action="cat_add"))
    builder.button(text="⬅️ Admin menu", callback_data=AdminCb(action="menu"))
    builder.adjust(1)
    return builder.as_markup()


def choose_category_kb(categories) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for category in categories:
        builder.button(
            text=category.name, callback_data=AdminCb(action="prod_cat", id=category.id)
        )
    builder.button(text="❌ Cancel", callback_data=AdminCb(action="cancel"))
    builder.adjust(1)
    return builder.as_markup()


def cancel_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Cancel", callback_data=AdminCb(action="cancel"))
    return builder.as_markup()


def skip_kb(action: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⏭ Skip", callback_data=AdminCb(action=action))
    builder.button(text="❌ Cancel", callback_data=AdminCb(action="cancel"))
    builder.adjust(2)
    return builder.as_markup()


def confirm_product_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Save product", callback_data=AdminCb(action="prod_save"))
    builder.button(text="❌ Cancel", callback_data=AdminCb(action="cancel"))
    builder.adjust(1)
    return builder.as_markup()