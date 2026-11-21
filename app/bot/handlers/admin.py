import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from app.bot.filters import IsAdmin
from app.bot.formatting import STATUS_MESSAGES, format_order_details
from app.bot.keyboards.catalog import NavCb
from app.bot.keyboards.orders import (
    AdminOrderCb,
    StatusCb,
    admin_order_kb,
    admin_orders_kb,
)
from app.services.order import (
    OrderError,
    OrderService,
    allowed_statuses,
    can_assign_courier,
)
from app.bot.keyboards.couriers import courier_open_kb
from app.services.user import UserService
from app.bot.keyboards.admin import admin_menu_kb
from html import escape
from app.services.payment import PaymentService
from app.i18n import t


logger = logging.getLogger(__name__)
router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.message(Command("admin"))
async def admin_panel(message: Message):
    await message.answer("🛠 <b>Admin panel</b>", reply_markup=admin_menu_kb())


@router.callback_query(NavCb.filter(F.to == "admin_orders"))
async def refresh_orders(call: CallbackQuery, session: AsyncSession):
    orders = await OrderService(session).get_active_orders()
    try:
        if not orders:
            await call.message.edit_text(
                "No active orders.", reply_markup=admin_menu_kb()
            )
        else:
            await call.message.edit_text(
                "🔄 Active orders:", reply_markup=admin_orders_kb(orders)
            )
    except TelegramBadRequest:
        pass  
    await call.answer()


@router.callback_query(AdminOrderCb.filter())
async def order_detail(
    call: CallbackQuery, callback_data: AdminOrderCb, session: AsyncSession
):
    order = await OrderService(session).get_order(callback_data.id)
    if order is None:
        await call.answer("Order not found", show_alert=True)
        return
    users = UserService(session)
    customer = await users.get(order.user_id)
    courier = await users.get(order.courier_id) if order.courier_id else None
    await call.message.edit_text(
        format_order_details(order, customer, courier),
        reply_markup=admin_order_kb(
            order.id, allowed_statuses(order), can_assign_courier(order)
        ),
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

    users = UserService(session)
    customer = await users.get(order.user_id)
    courier = await users.get(order.courier_id) if order.courier_id else None
    await call.message.edit_text(
        format_order_details(order, customer, courier),
        reply_markup=admin_order_kb(
            order.id, allowed_statuses(order), can_assign_courier(order)
        ),
    )

    try:
        await bot.send_message(
            customer.telegram_id,
            t(customer.language, f"notify.{order.status}", id=order.id),
        )
    except TelegramAPIError:
        logger.warning("Could not notify customer %s", customer.telegram_id)

    # tell the courier when the order is ready or cancelled
    if courier is not None and order.status in ("preparing", "cancelled"):
        text = (
            f"📦 Order #{order.id} is ready for pickup."
            if order.status == "preparing"
            else f"❌ Order #{order.id} was cancelled."
        )
        try:
            await bot.send_message(
                courier.telegram_id,
                text,
                reply_markup=courier_open_kb(order.id)
                if order.status == "preparing"
                else None,
            )
        except TelegramAPIError:
            logger.warning("Could not notify courier %s", courier.telegram_id)



    if order.status == "cancelled" and order.payment_method == "card":
        payment = await PaymentService(session).get_by_order(order.id)
        charge = payment.provider_charge_id if payment else "unknown"
        await call.message.answer(
            f"⚠️ Order #{order.id} was paid by card. Refund it in your payment "
            "provider dashboard.\n"
            f"Provider charge ID: <code>{escape(charge or 'unknown')}</code>"
        )


    await call.answer("Status updated")