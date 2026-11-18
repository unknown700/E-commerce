import logging
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters import IsAdmin
from app.bot.formatting import format_order_details
from app.bot.keyboards.admin import AdminCb, admin_menu_kb, cancel_kb
from app.bot.keyboards.couriers import (
    AssignCb,
    assign_kb,
    courier_open_kb,
    couriers_admin_kb,
)
from app.bot.keyboards.orders import admin_order_kb
from app.bot.states.admin import AddCourier
from app.services.courier import CourierError, CourierService
from app.services.order import (
    OrderError,
    OrderService,
    allowed_statuses,
    can_assign_courier,
)
from app.services.user import UserService

logger = logging.getLogger(__name__)
router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


async def safe_send(bot: Bot, chat_id: int, text: str, **kwargs) -> None:
    try:
        await bot.send_message(chat_id, text, **kwargs)
    except TelegramAPIError:
        logger.warning("Could not send a message to %s", chat_id)


async def render_couriers(session: AsyncSession):
    couriers = await CourierService(session).list_couriers()
    hint = "Tap ❌ to remove a courier." if couriers else "No couriers yet."
    return f"🚚 <b>Couriers</b>\n{hint}", couriers_admin_kb(couriers)


# ---------- manage couriers ----------
@router.callback_query(AdminCb.filter(F.action == "couriers"))
async def show_couriers(call: CallbackQuery, session: AsyncSession):
    text, keyboard = await render_couriers(session)
    await call.message.edit_text(text, reply_markup=keyboard)
    await call.answer()


@router.message(Command("cancel"), StateFilter(AddCourier))
async def cancel_add(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Cancelled.", reply_markup=admin_menu_kb())


@router.callback_query(AdminCb.filter(F.action == "cour_add"))
async def add_courier_start(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(AddCourier.identifier)
    await call.message.answer(
        "Send the courier's Telegram ID or @username.\n"
        "They must have pressed /start in this bot first.",
        reply_markup=cancel_kb(),
    )
    await call.answer()


@router.message(AddCourier.identifier, F.text, ~F.text.startswith("/"))
async def add_courier_identifier(
    message: Message, state: FSMContext, session: AsyncSession, bot: Bot
):
    try:
        courier = await CourierService(session).add_courier(message.text)
    except CourierError as error:
        await message.answer(f"❌ {error}\nTry again or /cancel.")
        return

    await state.clear()
    await message.answer(f"✅ {escape(courier.full_name)} is now a courier.")
    text, keyboard = await render_couriers(session)
    await message.answer(text, reply_markup=keyboard)
    await safe_send(
        bot,
        courier.telegram_id,
        "🚚 You are now a courier. Send /courier to see your deliveries.",
    )


@router.callback_query(AdminCb.filter(F.action == "cour_remove"))
async def remove_courier(
    call: CallbackQuery, callback_data: AdminCb, session: AsyncSession, bot: Bot
):
    try:
        courier = await CourierService(session).remove_courier(callback_data.id)
    except CourierError as error:
        await call.answer(str(error), show_alert=True)
        return

    text, keyboard = await render_couriers(session)
    await call.message.edit_text(text, reply_markup=keyboard)
    await call.answer("Courier removed")
    await safe_send(bot, courier.telegram_id, "You are no longer a courier.")


# ---------- assign a courier to an order ----------
@router.callback_query(AdminCb.filter(F.action == "assign"))
async def choose_courier(
    call: CallbackQuery, callback_data: AdminCb, session: AsyncSession
):
    couriers = await CourierService(session).list_couriers()
    if not couriers:
        await call.answer(
            "No couriers yet. Add one in Admin panel → 🚚 Couriers.", show_alert=True
        )
        return
    await call.message.edit_text(
        f"Choose a courier for order #{callback_data.id}:",
        reply_markup=assign_kb(callback_data.id, couriers),
    )
    await call.answer()


@router.callback_query(AssignCb.filter())
async def assign_courier(
    call: CallbackQuery, callback_data: AssignCb, session: AsyncSession, bot: Bot
):
    try:
        order, previous_id = await OrderService(session).assign_courier(
            callback_data.order_id, callback_data.courier_id
        )
    except OrderError as error:
        await call.answer(str(error), show_alert=True)
        return

    users = UserService(session)
    customer = await users.get(order.user_id)
    courier = await users.get(order.courier_id)
    await call.message.edit_text(
        format_order_details(order, customer, courier),
        reply_markup=admin_order_kb(
            order.id, allowed_statuses(order), can_assign_courier(order)
        ),
    )
    await call.answer("Courier assigned ✅")

    await safe_send(
        bot,
        courier.telegram_id,
        f"🚚 New delivery assigned: order #{order.id}",
        reply_markup=courier_open_kb(order.id),
    )
    if previous_id and previous_id != courier.id:
        previous = await users.get(previous_id)
        if previous is not None:
            await safe_send(
                bot,
                previous.telegram_id,
                f"Order #{order.id} was reassigned to another courier.",
            )