import logging
from decimal import Decimal
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery
from aiogram.types import User as TgUser
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.formatting import format_price
from app.bot.handlers.cart import get_user
from app.bot.handlers.checkout import notify_admins
from app.bot.keyboards.checkout import ConfirmCb, MockPayCb, mock_pay_kb
from app.bot.keyboards.main_menu import main_menu_kb
from app.bot.notifications import notify_low_stock, send_to_admins
from app.bot.states.checkout import Checkout
from app.config import settings
from app.i18n import t
from app.services.payment import PaymentError, PaymentService, to_cents

logger = logging.getLogger(__name__)
router = Router()


def _signed(amount_cents: int) -> str:
    text = format_price(Decimal(abs(amount_cents)) / 100)
    return f"-{text}" if amount_cents < 0 else text


async def finalize_payment(
    target: Message,
    session: AsyncSession,
    bot: Bot,
    tg_user: TgUser,
    payload: str,
    total_amount: int,
    telegram_charge_id: str,
    provider_charge_id: str,
    lang: str,
) -> None:
    """Runs after the money is taken (real or simulated)."""
    amount = format_price(Decimal(total_amount) / 100)
    customer = await get_user(tg_user, session)

    try:
        result = await PaymentService(session).complete(
            payload=payload,
            telegram_id=tg_user.id,
            total_amount=total_amount,
            telegram_charge_id=telegram_charge_id,
            provider_charge_id=provider_charge_id,
        )
    except PaymentError as error:
        logger.error("Unmatched payment: %s (%s)", error, provider_charge_id)
        await target.answer(t(lang, "pay.unmatched"))
        await send_to_admins(
            bot,
            f"⚠️ <b>Unmatched payment</b> {amount} from {escape(customer.full_name)}.\n"
            f"Provider charge ID: <code>{escape(provider_charge_id)}</code>",
        )
        return

    if not result.fresh:
        return  # the same payment was delivered twice

    if result.order is None:
        await target.answer(
            t(lang, "pay.refund", reason=escape(result.problem or "?")),
            reply_markup=main_menu_kb(lang),
        )
        await send_to_admins(
            bot,
            f"⚠️ <b>Refund needed</b>: {amount} from {escape(customer.full_name)}\n"
            f"Reason: {escape(result.problem or 'unknown')}\n"
            f"Provider charge ID: <code>{escape(provider_charge_id)}</code>",
        )
        return

    await target.answer(
        t(lang, "pay.received", id=result.order.id), reply_markup=main_menu_kb(lang)
    )
    await notify_admins(bot, result.order, customer)
    await notify_low_stock(bot, result.low_stock)


@router.callback_query(Checkout.confirm, ConfirmCb.filter(F.action == "card"))
async def pay_online(
    call: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    bot: Bot,
    lang: str,
):
    if not settings.card_payments_enabled:
        await call.answer(t(lang, "pay.unavailable"), show_alert=True)
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

    if settings.mock_payments_enabled:
        await state.clear()
        total = sum(amount for _, amount in lines)
        text = [t(lang, "pay.sandbox_title"), t(lang, "pay.sandbox_note") + "\n"]
        for label, amount in lines:
            text.append(f"• {escape(label)}: {_signed(amount)}")
        text.append("\n" + t(lang, "cart.total", amount=_signed(total)))
        await call.message.edit_text(
            "\n".join(text), reply_markup=mock_pay_kb(payment.id, lang)
        )
        await call.answer()
        return

    try:
        await bot.send_invoice(
            chat_id=call.from_user.id,
            title=t(lang, "pay.invoice_title"),
            description=t(lang, "pay.invoice_desc"),
            payload=f"pay:{payment.id}",
            provider_token=settings.payment_provider_token,
            currency=settings.currency,
            prices=[LabeledPrice(label=label, amount=amount) for label, amount in lines],
        )
    except TelegramAPIError as error:
        logger.exception("Could not send the invoice")
        text = t(lang, "pay.unavailable_now")
        if call.from_user.id in settings.admin_id_list:
            text += f"\n\n<b>Admin info:</b> <code>{escape(str(error))}</code>"
        await call.message.answer(text)
        await call.answer()
        return

    await state.clear()
    await call.message.edit_text(t(lang, "pay.invoice_sent"))
    await call.answer()


@router.callback_query(MockPayCb.filter())
async def mock_payment(
    call: CallbackQuery,
    callback_data: MockPayCb,
    session: AsyncSession,
    bot: Bot,
    lang: str,
):
    if not settings.mock_payments_enabled:
        await call.answer(t(lang, "pay.sandbox_off"), show_alert=True)
        return

    try:
        service = PaymentService(session)
        payment = await service.payments.get_by_id(callback_data.id)
        user = await get_user(call.from_user, session)
        if payment is None or payment.user_id != user.id or payment.status != "pending":
            await call.answer(t(lang, "pay.invalid"), show_alert=True)
            return

        if callback_data.action == "fail":
            await call.message.edit_text(t(lang, "pay.cancelled"))
            await call.answer()
            return

        cents = to_cents(payment.amount)
        payload = f"pay:{payment.id}"
        # the same checks a real payment goes through
        error = await service.validate_pre_checkout(
            payload, call.from_user.id, cents, payment.currency
        )
        if error:
            await call.answer(error, show_alert=True)
            return

        await call.message.edit_text(t(lang, "pay.sandbox_ok"))
        await call.answer()
        await finalize_payment(
            call.message,
            session,
            bot,
            call.from_user,
            payload,
            cents,
            f"MOCK-{payment.id}",
            f"MOCK-{payment.id}",
            lang,
        )
    except Exception as error:  # development aid: show the real problem in the chat
        logger.exception("Sandbox payment failed")
        await call.message.answer(
            "⚠️ Sandbox payment error:\n"
            f"<code>{escape(type(error).__name__)}: {escape(str(error))[:500]}</code>"
        )
        try:
            await call.answer()
        except Exception:
            pass


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
async def successful_payment(message: Message, session: AsyncSession, bot: Bot, lang: str):
    paid = message.successful_payment
    await finalize_payment(
        message,
        session,
        bot,
        message.from_user,
        paid.invoice_payload,
        paid.total_amount,
        paid.telegram_payment_charge_id,
        paid.provider_payment_charge_id,
        lang,
    )