from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.keyboards.catalog import NavCb, ProductCb


class CartCb(CallbackData, prefix="cart"):
    action: str  # inc / dec / del / clear
    product_id: int = 0


def cart_kb(items, has_promo: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for item in items:
        builder.row(
            InlineKeyboardButton(
                text="➖",
                callback_data=CartCb(action="dec", product_id=item.product_id).pack(),
            ),
            InlineKeyboardButton(
                text=f"{item.quantity}× {item.product.name}",
                callback_data=ProductCb(id=item.product_id).pack(),
            ),
            InlineKeyboardButton(
                text="➕",
                callback_data=CartCb(action="inc", product_id=item.product_id).pack(),
            ),
            InlineKeyboardButton(
                text="❌",
                callback_data=CartCb(action="del", product_id=item.product_id).pack(),
            ),
        )
    if has_promo:
        builder.row(
            InlineKeyboardButton(
                text="❌ Remove promo code",
                callback_data=CartCb(action="promo_remove").pack(),
            )
        )
    else:
        builder.row(
            InlineKeyboardButton(
                text="🎟 Promo code", callback_data=CartCb(action="promo").pack()
            )
        )
    builder.row(
        InlineKeyboardButton(
            text="✅ Checkout", callback_data=CartCb(action="checkout").pack()
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🗑 Clear cart", callback_data=CartCb(action="clear").pack()
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🛍 Continue shopping", callback_data=NavCb(to="categories").pack()
        )
    )
    return builder.as_markup()