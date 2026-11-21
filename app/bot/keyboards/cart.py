from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.keyboards.catalog import NavCb, ProductCb
from app.i18n import t

class CartCb(CallbackData, prefix="cart"):
    action: str  # inc / dec / del / clear
    product_id: int = 0


def cart_kb(items, has_promo: bool = False, lang: str = "en") -> InlineKeyboardMarkup:
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
    promo_text, promo_action = (
        (t(lang, "btn.promo_remove"), "promo_remove")
        if has_promo
        else (t(lang, "btn.promo"), "promo")
    )
    builder.row(
        InlineKeyboardButton(
            text=promo_text, callback_data=CartCb(action=promo_action).pack()
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=t(lang, "btn.checkout"), callback_data=CartCb(action="checkout").pack()
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=t(lang, "btn.clear_cart"), callback_data=CartCb(action="clear").pack()
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=t(lang, "btn.continue"), callback_data=NavCb(to="categories").pack()
        )
    )
    return builder.as_markup()