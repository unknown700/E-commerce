from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


class LangCb(CallbackData, prefix="lang"):
    code: str


def language_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🇬🇧 English", callback_data=LangCb(code="en"))
    builder.button(text="🇺🇿 O'zbekcha", callback_data=LangCb(code="uz"))
    builder.button(text="🇩🇪 Deutsch", callback_data=LangCb(code="de"))
    builder.adjust(1)
    return builder.as_markup()