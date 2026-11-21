from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.formatting import format_order_details
from app.bot.handlers.cart import get_user
from app.bot.keyboards.catalog import NavCb
from app.bot.keyboards.orders import MyOrderCb, my_order_detail_kb, my_orders_kb
from app.services.order import OrderService
from app.i18n import all_texts
router = Router()


@router.message(Command("orders"))
@router.message(F.text.in_(all_texts("menu.orders")))
async def my_orders(message: Message, session: AsyncSession):
    user = await get_user(message.from_user, session)
    orders = await OrderService(session).get_user_orders(user.id)
    if not orders:
        await message.answer("You have no orders yet.")
        return
    await message.answer("Your orders:", reply_markup=my_orders_kb(orders))


@router.callback_query(NavCb.filter(F.to == "my_orders"))
async def back_to_my_orders(call: CallbackQuery, session: AsyncSession):
    user = await get_user(call.from_user, session)
    orders = await OrderService(session).get_user_orders(user.id)
    if not orders:
        await call.message.edit_text("You have no orders yet.")
    else:
        await call.message.edit_text("Your orders:", reply_markup=my_orders_kb(orders))
    await call.answer()


@router.callback_query(MyOrderCb.filter())
async def my_order_detail(
    call: CallbackQuery, callback_data: MyOrderCb, session: AsyncSession
):
    user = await get_user(call.from_user, session)
    order = await OrderService(session).get_order(callback_data.id)
    # a customer may only see their own orders
    if order is None or order.user_id != user.id:
        await call.answer("Order not found", show_alert=True)
        return
    await call.message.edit_text(
        format_order_details(order), reply_markup=my_order_detail_kb()
    )
    await call.answer()