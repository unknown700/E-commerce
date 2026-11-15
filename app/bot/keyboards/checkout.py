from aiogram.filters.callback_data import CallbackData
from aiogram.types import (
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

CANCEL_TEXT = "❌ Cancel"


class DeliveryCb(CallbackData, prefix="deliv"):
    kind: str  # delivery / pickup


class ConfirmCb(CallbackData, prefix="confirm"):
    action: str  # yes / no


def delivery_type_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🚚 Delivery", callback_data=DeliveryCb(kind="delivery"))
    builder.button(text="🏪 Pickup", callback_data=DeliveryCb(kind="pickup"))
    builder.button(text=CANCEL_TEXT, callback_data=ConfirmCb(action="no"))
    builder.adjust(2, 1)
    return builder.as_markup()


def confirm_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Confirm order", callback_data=ConfirmCb(action="yes"))
    builder.button(text=CANCEL_TEXT, callback_data=ConfirmCb(action="no"))
    builder.adjust(1)
    return builder.as_markup()


def location_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📍 Send location", request_location=True)],
            [KeyboardButton(text=CANCEL_TEXT)],
        ],
        resize_keyboard=True,
    )


def phone_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Share phone number", request_contact=True)],
            [KeyboardButton(text=CANCEL_TEXT)],
        ],
        resize_keyboard=True,
    )