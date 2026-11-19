from decimal import Decimal
from html import escape

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters import IsAdmin
from app.bot.formatting import format_price, format_promos
from app.bot.keyboards.admin import (
    AdminCb,
    admin_menu_kb,
    cancel_kb,
    promo_confirm_kb,
    promo_kind_kb,
    promos_admin_kb,
)
from app.bot.states.promo import AddPromo
from app.services.admin_catalog import CatalogError, parse_price
from app.services.promo import (
    PromoError,
    PromoService,
    parse_days,
    parse_max_uses,
    parse_min_order,
    parse_percent,
)

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

TEXT_ONLY = (F.text, ~F.text.startswith("/"))


async def render_promos(session: AsyncSession):
    rows = await PromoService(session).list_with_usage()
    return format_promos(rows), promos_admin_kb(rows)


def build_promo_summary(data: dict) -> str:
    value = Decimal(data["value"])
    discount = f"{value:.0f}%" if data["kind"] == "percent" else format_price(value)
    min_order = Decimal(data["min_order"])
    minimum = format_price(min_order) if min_order > 0 else "none"
    uses = str(data["max_uses"]) if data["max_uses"] else "unlimited"
    valid = f"{data['days']} days" if data["days"] else "no expiry"
    return (
        "🎟 <b>New promo code</b>\n\n"
        f"Code: <b>{escape(data['code'])}</b>\n"
        f"Discount: {discount}\n"
        f"Minimum order: {minimum}\n"
        f"Total uses: {uses} (each customer can use it once)\n"
        f"Valid: {valid}"
    )


# ---------- list and on/off ----------
@router.callback_query(AdminCb.filter(F.action == "promos"))
async def show_promos(call: CallbackQuery, session: AsyncSession):
    text, keyboard = await render_promos(session)
    await call.message.edit_text(text, reply_markup=keyboard)
    await call.answer()


@router.callback_query(AdminCb.filter(F.action == "promo_toggle"))
async def toggle_promo(call: CallbackQuery, callback_data: AdminCb, session: AsyncSession):
    promo = await PromoService(session).toggle(callback_data.id)
    if promo is None:
        await call.answer("Promo code not found", show_alert=True)
        return
    text, keyboard = await render_promos(session)
    try:
        await call.message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest:
        pass
    await call.answer("Enabled ✅" if promo.is_active else "Disabled 🚫")


# ---------- create ----------
@router.message(Command("cancel"), StateFilter(AddPromo))
async def cancel_new(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Cancelled.", reply_markup=admin_menu_kb())


@router.callback_query(AdminCb.filter(F.action == "promo_new"))
async def new_start(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(AddPromo.code)
    await call.message.answer(
        "Send the promo code (3-20 letters or digits, e.g. WELCOME10):",
        reply_markup=cancel_kb(),
    )
    await call.answer()


@router.message(AddPromo.code, *TEXT_ONLY)
async def new_code(message: Message, state: FSMContext, session: AsyncSession):
    code = message.text.strip().upper()
    try:
        await PromoService(session).check_new_code(code)
    except PromoError as error:
        await message.answer(f"❌ {error}\nTry again or /cancel.")
        return
    await state.update_data(code=code)
    await state.set_state(AddPromo.kind)
    await message.answer("Choose the discount type:", reply_markup=promo_kind_kb())


@router.callback_query(
    AddPromo.kind, AdminCb.filter(F.action.in_({"pk_percent", "pk_fixed"}))
)
async def new_kind(call: CallbackQuery, callback_data: AdminCb, state: FSMContext):
    kind = callback_data.action.removeprefix("pk_")
    await state.update_data(kind=kind)
    await state.set_state(AddPromo.value)
    await call.message.edit_text(f"Type: {kind}")
    prompt = (
        "Send the discount percent (1-90):"
        if kind == "percent"
        else "Send the discount amount in USD (e.g. 5):"
    )
    await call.message.answer(prompt, reply_markup=cancel_kb())
    await call.answer()


@router.message(AddPromo.value, *TEXT_ONLY)
async def new_value(message: Message, state: FSMContext):
    data = await state.get_data()
    try:
        value = (
            parse_percent(message.text)
            if data["kind"] == "percent"
            else parse_price(message.text)
        )
    except (PromoError, CatalogError) as error:
        await message.answer(f"❌ {error}")
        return
    await state.update_data(value=str(value))
    await state.set_state(AddPromo.min_order)
    await message.answer(
        "Minimum order amount in USD (send 0 for no minimum):", reply_markup=cancel_kb()
    )


@router.message(AddPromo.min_order, *TEXT_ONLY)
async def new_min_order(message: Message, state: FSMContext):
    try:
        min_order = parse_min_order(message.text)
    except (PromoError, CatalogError) as error:
        await message.answer(f"❌ {error}")
        return
    await state.update_data(min_order=str(min_order))
    await state.set_state(AddPromo.max_uses)
    await message.answer(
        "How many times can this code be used in total? (a number, or - for unlimited)",
        reply_markup=cancel_kb(),
    )


@router.message(AddPromo.max_uses, *TEXT_ONLY)
async def new_max_uses(message: Message, state: FSMContext):
    try:
        max_uses = parse_max_uses(message.text)
    except (PromoError, CatalogError) as error:
        await message.answer(f"❌ {error}")
        return
    await state.update_data(max_uses=max_uses)
    await state.set_state(AddPromo.days)
    await message.answer(
        "How many days is it valid? (1-365, or - for no expiry)", reply_markup=cancel_kb()
    )


@router.message(AddPromo.days, *TEXT_ONLY)
async def new_days(message: Message, state: FSMContext):
    try:
        days = parse_days(message.text)
    except PromoError as error:
        await message.answer(f"❌ {error}")
        return
    await state.update_data(days=days)
    await state.set_state(AddPromo.confirm)
    data = await state.get_data()
    await message.answer(build_promo_summary(data), reply_markup=promo_confirm_kb())


@router.callback_query(AddPromo.confirm, AdminCb.filter(F.action == "promo_save"))
async def save_promo(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    await call.message.edit_reply_markup(reply_markup=None)
    try:
        promo = await PromoService(session).create_promo(
            code=data["code"],
            kind=data["kind"],
            value=Decimal(data["value"]),
            min_order=Decimal(data["min_order"]),
            max_uses=data["max_uses"],
            days=data["days"],
        )
    except PromoError as error:
        await state.clear()
        await call.message.answer(f"❌ {error}", reply_markup=admin_menu_kb())
        await call.answer()
        return

    await state.clear()
    await call.message.answer(f"✅ Promo code <b>{escape(promo.code)}</b> created.")
    text, keyboard = await render_promos(session)
    await call.message.answer(text, reply_markup=keyboard)
    await call.answer()