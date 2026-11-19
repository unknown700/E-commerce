from io import BytesIO
from zoneinfo import ZoneInfo

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.repositories.inventory import InventoryRepository

REASON_NAMES = {
    "receipt": "Receipt",
    "sale": "Sale",
    "cancel_return": "Cancelled order return",
    "adjustment": "Manual adjustment",
}


def _finish_sheet(sheet) -> None:
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    sheet.freeze_panes = "A2"
    for index, column in enumerate(sheet.columns, start=1):
        longest = max(len(str(cell.value)) if cell.value is not None else 0 for cell in column)
        sheet.column_dimensions[get_column_letter(index)].width = min(longest + 3, 45)


class ExportService:
    def __init__(self, session: AsyncSession):
        self.inventory = InventoryRepository(session)

    async def warehouse_xlsx(self) -> bytes:
        products = await self.inventory.products_with_category()
        movements = await self.inventory.recent_movements(limit=5000)
        tz = ZoneInfo(settings.timezone)

        workbook = Workbook()
        stock_sheet = workbook.active
        stock_sheet.title = "Stock"
        stock_sheet.append(["ID", "Category", "Product", "Price (USD)", "Stock", "Status"])
        for product, category_name in products:
            stock_sheet.append(
                [
                    product.id,
                    category_name,
                    product.name,
                    float(product.price),
                    product.stock,
                    "Active" if product.is_active else "Hidden",
                ]
            )
        _finish_sheet(stock_sheet)

        history_sheet = workbook.create_sheet("Movements")
        history_sheet.append(
            ["Date", "Product", "Change", "Stock after", "Reason", "Order #", "By"]
        )
        for movement, product_name, user_name in movements:
            # Excel does not support time zones, so store local time without tzinfo
            local_time = movement.created_at.astimezone(tz).replace(tzinfo=None)
            history_sheet.append(
                [
                    local_time,
                    product_name,
                    movement.delta,
                    movement.stock_after,
                    REASON_NAMES.get(movement.reason, movement.reason),
                    movement.order_id,
                    user_name,
                ]
            )
        for row in history_sheet.iter_rows(min_row=2, max_col=1):
            row[0].number_format = "dd.mm.yyyy hh:mm"
        _finish_sheet(history_sheet)

        buffer = BytesIO()
        workbook.save(buffer)
        return buffer.getvalue()