from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import BufferedInputFile, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters import IsAdmin
from app.bot.formatting import format_low_stock, format_movements
from app.bot.keyboards.admin import AdminCb, warehouse_kb
from app.config import settings
from app.services.export import ExportService
from app.services.inventory import InventoryService

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


async def show(call: CallbackQuery, text: str) -> None:
    try:
        await call.message.edit_text(text, reply_markup=warehouse_kb())
    except TelegramBadRequest:
        pass  # same content, nothing to update


@router.callback_query(AdminCb.filter(F.action == "wh"))
async def warehouse_menu(call: CallbackQuery):
    await show(call, "🏬 <b>Warehouse</b>\nChoose what to open:")
    await call.answer()


@router.callback_query(AdminCb.filter(F.action == "wh_low"))
async def low_stock(call: CallbackQuery, session: AsyncSession):
    products = await InventoryService(session).low_stock()
    await show(call, format_low_stock(products, settings.low_stock_threshold))
    await call.answer()


@router.callback_query(AdminCb.filter(F.action == "wh_history"))
async def history(call: CallbackQuery, session: AsyncSession):
    rows = await InventoryService(session).recent_movements(15)
    await show(call, format_movements(rows))
    await call.answer()


@router.callback_query(AdminCb.filter(F.action == "wh_export"))
async def export_excel(call: CallbackQuery, session: AsyncSession):
    await call.answer("Preparing the file...")
    data = await ExportService(session).warehouse_xlsx()
    stamp = datetime.now(ZoneInfo(settings.timezone)).strftime("%Y-%m-%d_%H%M")
    await call.message.answer_document(
        BufferedInputFile(data, filename=f"warehouse_{stamp}.xlsx"),
        caption="📥 Warehouse export: current stock and movement history",
    )