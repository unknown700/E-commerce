from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.keyboards.catalog import NavCb
from app.bot.formatting import format_price

class AdminCb(CallbackData, prefix="adm"):
    action: str
    id: int = 0


def admin_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Orders", callback_data=NavCb(to="admin_orders"))
    builder.button(text="🛍 Products", callback_data=AdminCb(action="products"))
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



def product_categories_kb(categories) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for category in categories:
        icon = "✅" if category.is_active else "🚫"
        builder.button(
            text=f"{icon} {category.name}",
            callback_data=AdminCb(action="plist", id=category.id),
        )
    builder.button(text="⬅️ Admin menu", callback_data=AdminCb(action="menu"))
    builder.adjust(1)
    return builder.as_markup()


def products_admin_kb(products) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for product in products:
        icon = "✅" if product.is_active else "🚫"
        builder.button(
            text=f"{icon} {product.name} · {format_price(product.price)} · {product.stock} pcs",
            callback_data=AdminCb(action="pview", id=product.id),
        )
    builder.button(text="⬅️ Categories", callback_data=AdminCb(action="products"))
    builder.adjust(1)
    return builder.as_markup()


def product_admin_kb(product) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Name", callback_data=AdminCb(action="edit_name", id=product.id))
    builder.button(
        text="📝 Description",
        callback_data=AdminCb(action="edit_description", id=product.id),
    )
    builder.button(text="💰 Price", callback_data=AdminCb(action="edit_price", id=product.id))
    builder.button(text="📦 Stock", callback_data=AdminCb(action="edit_stock", id=product.id))
    builder.button(text="🖼 Photo", callback_data=AdminCb(action="edit_photo", id=product.id))
    toggle_text = (
        "🚫 Hide from customers" if product.is_active else "✅ Show to customers"
    )
    builder.button(text=toggle_text, callback_data=AdminCb(action="p_toggle", id=product.id))
    builder.button(
        text="⬅️ Back",
        callback_data=AdminCb(action="plist", id=product.category_id),
    )
    builder.adjust(2, 2, 1, 1, 1)
    return builder.as_markup()