from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters import IsAdmin
from app.bot.formatting import format_payments
from app.bot.keyboards.admin import AdminCb, admin_menu_kb
from app.services.payment import PaymentService

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.callback_query(AdminCb.filter(F.action == "payments"))
async def show_payments(call: CallbackQuery, session: AsyncSession):
    payments = await PaymentService(session).recent()
    try:
        await call.message.edit_text(
            format_payments(payments), reply_markup=admin_menu_kb()
        )
    except TelegramBadRequest:
        pass  # nothing changed
    await call.answer()