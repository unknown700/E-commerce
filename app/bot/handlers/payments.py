import logging
from decimal import Decimal
from html import escape

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.formatting import format_price
from app.bot.handlers.cart import get_user
from app.bot.handlers.checkout import notify_admins
from app.bot.keyboards.checkout import ConfirmCb
from app.bot.keyboards.main_menu import main_menu_kb
from app.bot.notifications import notify_low_stock, send_to_admins
from app.bot.states.checkout import Checkout
from app.config import settings
from app.services.payment import PaymentError, PaymentService

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(Checkout.confirm, ConfirmCb.filter(F.action == "card"))
async def pay_online(
    call: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot
):
    if not settings.card_payments_enabled:
        await call.answer("Online payment is not available.", show_alert=True)
        return

    data = await state.get_data()
    user = await get_user(call.from_user, session)
    try:
        payment, lines = await PaymentService(session).start(
            user_id=user.id,
            delivery_type=data["delivery_type"],
            phone=data["phone"],
            address=data.get("address"),
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
        )
    except PaymentError as error:
        await call.answer(str(error), show_alert=True)
        return

    await state.clear()
    await call.message.edit_text("💳 Please pay the invoice below to place your order.")
    await bot.send_invoice(
        chat_id=call.from_user.id,
        title="Order payment",
        description=f"Payment for your order from {len(lines)} line(s).",
        payload=f"pay:{payment.id}",
        provider_token=settings.payment_provider_token,
        currency=settings.currency,
        prices=[LabeledPrice(label=label, amount=amount) for label, amount in lines],
    )
    await call.answer()


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery, session: AsyncSession):
    error = await PaymentService(session).validate_pre_checkout(
        query.invoice_payload, query.from_user.id, query.total_amount, query.currency
    )
    if error:
        await query.answer(ok=False, error_message=error)
    else:
        await query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment(message: Message, session: AsyncSession, bot: Bot):
    paid = message.successful_payment
    amount = format_price(Decimal(paid.total_amount) / 100)
    customer = await get_user(message.from_user, session)

    try:
        result = await PaymentService(session).complete(
            payload=paid.invoice_payload,
            telegram_id=message.from_user.id,
            total_amount=paid.total_amount,
            telegram_charge_id=paid.telegram_payment_charge_id,
            provider_charge_id=paid.provider_payment_charge_id,
        )
    except PaymentError as error:
        logger.error("Unmatched payment: %s (%s)", error, paid.provider_payment_charge_id)
        await message.answer(
            "We received your payment but could not match it to an order. "
            "Our team will contact you."
        )
        await send_to_admins(
            bot,
            f"⚠️ <b>Unmatched payment</b> {amount} from {escape(customer.full_name)}.\n"
            f"Provider charge ID: <code>{escape(paid.provider_payment_charge_id)}</code>",
        )
        return

    if not result.fresh:
        return  # the same payment was delivered twice

    if result.order is None:
        await message.answer(
            "😔 Your payment was received, but we could not complete the order: "
            f"{escape(result.problem or 'unknown error')}\n"
            "We will refund you.",
            reply_markup=main_menu_kb(),
        )
        await send_to_admins(
            bot,
            f"⚠️ <b>Refund needed</b>: {amount} from {escape(customer.full_name)}\n"
            f"Reason: {escape(result.problem or 'unknown')}\n"
            f"Provider charge ID: <code>{escape(paid.provider_payment_charge_id)}</code>",
        )
        return

    await message.answer(
        f"✅ <b>Payment received!</b>\nOrder #{result.order.id} placed. "
        "We will contact you soon. Thank you!",
        reply_markup=main_menu_kb(),
    )
    await notify_admins(bot, result.order, customer)
    await notify_low_stock(bot, result.low_stock)