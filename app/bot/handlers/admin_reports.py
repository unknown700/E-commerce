from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters import IsAdmin
from app.bot.formatting import format_report
from app.bot.keyboards.admin import AdminCb, reports_kb
from app.services.report import ReportService

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

REPORT_ACTIONS = {"report_today", "report_week", "report_month"}


@router.message(Command("report"))
async def report_command(message: Message, session: AsyncSession):
    report = await ReportService(session).build("today")
    await message.answer(format_report(report), reply_markup=reports_kb("today"))


@router.callback_query(AdminCb.filter(F.action.in_(REPORT_ACTIONS)))
async def show_report(call: CallbackQuery, callback_data: AdminCb, session: AsyncSession):
    period = callback_data.action.removeprefix("report_")
    report = await ReportService(session).build(period)
    try:
        await call.message.edit_text(
            format_report(report), reply_markup=reports_kb(period)
        )
    except TelegramBadRequest:
        pass  # same content, nothing to update
    await call.answer()