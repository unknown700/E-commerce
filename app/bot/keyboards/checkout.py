from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.i18n import t


class DeliveryCb(CallbackData, prefix="deliv"):
    kind: str  # delivery / pickup


class ConfirmCb(CallbackData, prefix="confirm"):
    action: str  # yes / card / no


class MockPayCb(CallbackData, prefix="mockpay"):
    action: str  # ok / fail
    id: int


def delivery_type_kb(lang: str = "en") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t(lang, "btn.delivery"), callback_data=DeliveryCb(kind="delivery"))
    builder.button(text=t(lang, "btn.pickup"), callback_data=DeliveryCb(kind="pickup"))
    builder.button(text=t(lang, "btn.cancel"), callback_data=ConfirmCb(action="no"))
    builder.adjust(2, 1)
    return builder.as_markup()


def confirm_kb(online: bool = False, lang: str = "en") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=t(lang, "btn.pay_cash"), callback_data=ConfirmCb(action="yes"))
    if online:
        builder.button(text=t(lang, "btn.pay_online"), callback_data=ConfirmCb(action="card"))
    builder.button(text=t(lang, "btn.cancel"), callback_data=ConfirmCb(action="no"))
    builder.adjust(1)
    return builder.as_markup()


def location_kb(lang: str = "en") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "btn.send_location"), request_location=True)],
            [KeyboardButton(text=t(lang, "btn.cancel"))],
        ],
        resize_keyboard=True,
    )


def phone_kb(lang: str = "en") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "btn.share_phone"), request_contact=True)],
            [KeyboardButton(text=t(lang, "btn.cancel"))],
        ],
        resize_keyboard=True,
    )


def mock_pay_kb(payment_id: int, lang: str = "en") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=t(lang, "btn.sim_ok"), callback_data=MockPayCb(action="ok", id=payment_id)
    )
    builder.button(
        text=t(lang, "btn.sim_cancel"),
        callback_data=MockPayCb(action="fail", id=payment_id),
    )
    builder.adjust(1)
    return builder.as_markup()