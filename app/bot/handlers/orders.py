from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.formatting import format_order_details
from app.bot.handlers.cart import get_user
from app.bot.keyboards.catalog import NavCb
from app.bot.keyboards.orders import MyOrderCb, my_order_detail_kb, my_orders_kb
from app.i18n import all_texts, t
from app.services.order import OrderService

router = Router()


@router.message(Command("orders"))
@router.message(F.text.in_(all_texts("menu.orders")))
async def my_orders(message: Message, session: AsyncSession, lang: str):
    user = await get_user(message.from_user, session)
    orders = await OrderService(session).get_user_orders(user.id)
    if not orders:
        await message.answer(t(lang, "orders.none"))
        return
    await message.answer(t(lang, "orders.title"), reply_markup=my_orders_kb(orders, lang))


@router.callback_query(NavCb.filter(F.to == "my_orders"))
async def back_to_my_orders(call: CallbackQuery, session: AsyncSession, lang: str):
    user = await get_user(call.from_user, session)
    orders = await OrderService(session).get_user_orders(user.id)
    if not orders:
        await call.message.edit_text(t(lang, "orders.none"))
    else:
        await call.message.edit_text(
            t(lang, "orders.title"), reply_markup=my_orders_kb(orders, lang)
        )
    await call.answer()


@router.callback_query(MyOrderCb.filter())
async def my_order_detail(
    call: CallbackQuery, callback_data: MyOrderCb, session: AsyncSession, lang: str
):
    user = await get_user(call.from_user, session)
    order = await OrderService(session).get_order(callback_data.id)
    # a customer may only see their own orders
    if order is None or order.user_id != user.id:
        await call.answer(t(lang, "orders.not_found"), show_alert=True)
        return
    await call.message.edit_text(
        format_order_details(order, lang=lang), reply_markup=my_order_detail_kb(lang)
    )
    await call.answer()