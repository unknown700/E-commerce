import logging
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters import IsCourier
from app.bot.formatting import STATUS_MESSAGES, format_courier_order
from app.bot.handlers.cart import get_user
from app.bot.keyboards.couriers import (
    CourierCb,
    courier_order_kb,
    courier_orders_kb,
    courier_refresh_kb,
)
from app.bot.notifications import send_to_admins
from app.services.order import OrderError, OrderService
from app.services.user import UserService

logger = logging.getLogger(__name__)
router = Router()
router.message.filter(IsCourier())
router.callback_query.filter(IsCourier())


async def render_list(session: AsyncSession, courier_id: int):
    orders = await OrderService(session).get_courier_orders(courier_id)
    if not orders:
        return "🚚 No deliveries assigned to you right now.", courier_refresh_kb()
    return "🚚 <b>Your deliveries</b>", courier_orders_kb(orders)


@router.message(Command("courier"))
async def courier_panel(message: Message, session: AsyncSession):
    courier = await get_user(message.from_user, session)
    text, keyboard = await render_list(session, courier.id)
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(CourierCb.filter(F.action == "list"))
async def list_deliveries(call: CallbackQuery, session: AsyncSession):
    courier = await get_user(call.from_user, session)
    text, keyboard = await render_list(session, courier.id)
    try:
        await call.message.edit_text(text, reply_markup=keyboard)
    except TelegramBadRequest:
        pass  # nothing changed
    await call.answer()


@router.callback_query(CourierCb.filter(F.action == "view"))
async def view_delivery(
    call: CallbackQuery, callback_data: CourierCb, session: AsyncSession
):
    courier = await get_user(call.from_user, session)
    order = await OrderService(session).get_order(callback_data.id)
    # a courier may only see orders assigned to them
    if order is None or order.courier_id != courier.id:
        await call.answer("Order not found", show_alert=True)
        return
    customer = await UserService(session).get(order.user_id)
    try:
        await call.message.edit_text(
            format_courier_order(order, customer), reply_markup=courier_order_kb(order)
        )
    except TelegramBadRequest:
        pass
    await call.answer()


@router.callback_query(CourierCb.filter(F.action.in_({"pickup", "deliver"})))
async def courier_action(
    call: CallbackQuery, callback_data: CourierCb, session: AsyncSession, bot: Bot
):
    courier = await get_user(call.from_user, session)
    try:
        order = await OrderService(session).courier_action(
            callback_data.id, courier.id, callback_data.action
        )
    except OrderError as error:
        await call.answer(str(error), show_alert=True)
        return

    customer = await UserService(session).get(order.user_id)
    await call.message.edit_text(
        format_courier_order(order, customer), reply_markup=courier_order_kb(order)
    )
    await call.answer("Done ✅")

    try:
        await bot.send_message(
            customer.telegram_id, STATUS_MESSAGES[order.status].format(id=order.id)
        )
    except Exception:
        logger.warning("Could not notify customer %s", customer.telegram_id)

    if order.status == "delivered":
        await send_to_admins(
            bot, f"✅ Order #{order.id} was delivered by {escape(courier.full_name)}."
        )