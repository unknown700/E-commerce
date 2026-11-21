from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from app.i18n import t


def main_menu_kb(lang: str = "en") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=t(lang, "menu.catalog")),
                KeyboardButton(text=t(lang, "menu.cart")),
            ],
            [
                KeyboardButton(text=t(lang, "menu.orders")),
                KeyboardButton(text=t(lang, "menu.language")),
            ],
        ],
        resize_keyboard=True,
    )