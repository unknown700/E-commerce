import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters import IsAdmin
from app.bot.formatting import STATUS_MESSAGES, format_order_details
from app.bot.keyboards.catalog import NavCb
from app.bot.keyboards.orders import (
    AdminOrderCb,
    StatusCb,
    admin_order_kb,
    admin_orders_kb,
)
from app.services.order import OrderError, OrderService, allowed_statuses
from app.services.user import UserService

logger = logging.getLogger(__name__)
router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.message(Command("admin"))
async def admin_panel(message: Message, session: AsyncSession):
    orders = await OrderService(session).get_active_orders()
    if not orders:
        await message.answer("No active orders.")
        return
    await message.answer("🔄 Active orders:", reply_markup=admin_orders_kb(orders))


@router.callback_query(NavCb.filter(F.to == "admin_orders"))
async def refresh_orders(call: CallbackQuery, session: AsyncSession):
    orders = await OrderService(session).get_active_orders()
    try:
        if not orders:
            await call.message.edit_text("No active orders.")
        else:
            await call.message.edit_text(
                "🔄 Active orders:", reply_markup=admin_orders_kb(orders)
            )
    except TelegramBadRequest:
        pass  # nothing changed
    await call.answer()


@router.callback_query(AdminOrderCb.filter())
async def order_detail(
    call: CallbackQuery, callback_data: AdminOrderCb, session: AsyncSession
):
    order = await OrderService(session).get_order(callback_data.id)
    if order is None:
        await call.answer("Order not found", show_alert=True)
        return
    customer = await UserService(session).get(order.user_id)
    await call.message.edit_text(
        format_order_details(order, customer),
        reply_markup=admin_order_kb(order.id, allowed_statuses(order)),
    )
    await call.answer()


@router.callback_query(StatusCb.filter())
async def change_status(
    call: CallbackQuery, callback_data: StatusCb, session: AsyncSession, bot: Bot
):
    try:
        order = await OrderService(session).change_status(
            callback_data.id, callback_data.status
        )
    except OrderError as error:
        await call.answer(str(error), show_alert=True)
        return

    customer = await UserService(session).get(order.user_id)
    await call.message.edit_text(
        format_order_details(order, customer),
        reply_markup=admin_order_kb(order.id, allowed_statuses(order)),
    )

    try:
        await bot.send_message(
            customer.telegram_id, STATUS_MESSAGES[order.status].format(id=order.id)
        )
    except TelegramAPIError:
        logger.warning("Could not notify customer %s", customer.telegram_id)
    await call.answer("Status updated")