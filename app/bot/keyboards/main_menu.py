from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛍 Catalog"), KeyboardButton(text="🛒 Cart")],
            [KeyboardButton(text="📦 My orders")],
        ],
        resize_keyboard=True,
    )