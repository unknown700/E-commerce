from html import escape

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters import IsAdmin
from app.bot.formatting import format_admin_product
from app.bot.keyboards.admin import (
    AdminCb,
    admin_menu_kb,
    cancel_kb,
    product_admin_kb,
    product_categories_kb,
    products_admin_kb,
)
from app.bot.handlers.cart import get_user
from app.bot.states.admin import EditProduct, ReceiveStock
from app.services.admin_catalog import (
    AdminCatalogService,
    CatalogError,
    parse_stock,
)
from app.services.inventory import InventoryError, InventoryService

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

EDIT_PROMPTS = {
    "name": "Send the new product name:",
    "description": "Send the new description (or send - to remove it):",
    "price": "Send the new price in UZS (numbers only, e.g. 3200000):",
    "stock": "Send the new stock quantity (a whole number):",
    "photo": "Send the new product photo:",
}
EDIT_ACTIONS = {f"edit_{field}" for field in EDIT_PROMPTS}


async def send_product_card(target: Message, product, category) -> None:
    text = format_admin_product(product, category)
    keyboard = product_admin_kb(product)
    if product.photo_file_id:
        await target.answer_photo(
            product.photo_file_id, caption=text, reply_markup=keyboard
        )
    else:
        await target.answer(text, reply_markup=keyboard)


async def show_updated_card(target: Message, session: AsyncSession, product_id: int):
    card = await AdminCatalogService(session).get_product_card(product_id)
    if card:
        await send_product_card(target, *card)


# ---------- browse ----------
@router.callback_query(AdminCb.filter(F.action == "products"))
async def choose_category(call: CallbackQuery, session: AsyncSession):
    categories = await AdminCatalogService(session).list_categories()
    if not categories:
        await call.answer("No categories yet.", show_alert=True)
        return
    await call.message.delete()
    await call.message.answer(
        "🛍 <b>Products</b>\nChoose a category:",
        reply_markup=product_categories_kb(categories),
    )
    await call.answer()


@router.callback_query(AdminCb.filter(F.action == "plist"))
async def list_products(
    call: CallbackQuery, callback_data: AdminCb, session: AsyncSession
):
    service = AdminCatalogService(session)
    category = await service.get_category(callback_data.id)
    if category is None:
        await call.answer("Category not found", show_alert=True)
        return

    products = await service.list_products(category.id)
    hint = "Choose a product:" if products else "No products in this category yet."
    await call.message.delete()
    await call.message.answer(
        f"🛍 <b>{escape(category.name)}</b>\n{hint}",
        reply_markup=products_admin_kb(products),
    )
    await call.answer()


@router.callback_query(AdminCb.filter(F.action == "pview"))
async def view_product(
    call: CallbackQuery, callback_data: AdminCb, session: AsyncSession
):
    card = await AdminCatalogService(session).get_product_card(callback_data.id)
    if card is None:
        await call.answer("Product not found", show_alert=True)
        return
    await call.message.delete()
    await send_product_card(call.message, *card)
    await call.answer()


@router.callback_query(AdminCb.filter(F.action == "p_toggle"))
async def toggle_product(
    call: CallbackQuery, callback_data: AdminCb, session: AsyncSession
):
    product = await AdminCatalogService(session).toggle_product(callback_data.id)
    if product is None:
        await call.answer("Product not found", show_alert=True)
        return
    await call.message.delete()
    await show_updated_card(call.message, session, product.id)
    await call.answer("Visible ✅" if product.is_active else "Hidden 🚫")


# ---------- edit ----------
@router.message(Command("cancel"), StateFilter(EditProduct, ReceiveStock))
async def cancel_edit(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Cancelled.", reply_markup=admin_menu_kb())


@router.callback_query(AdminCb.filter(F.action.in_(EDIT_ACTIONS)))
async def edit_start(call: CallbackQuery, callback_data: AdminCb, state: FSMContext):
    field = callback_data.action.removeprefix("edit_")
    await state.clear()
    await state.update_data(product_id=callback_data.id, field=field)
    await state.set_state(EditProduct.value)
    await call.message.answer(EDIT_PROMPTS[field], reply_markup=cancel_kb())
    await call.answer()


@router.message(EditProduct.value, F.text, ~F.text.startswith("/"))
async def edit_text_value(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    if data["field"] == "photo":
        await message.answer("Please send a photo (as a picture), or /cancel.")
        return

    try:
        if data["field"] == "stock":
            new_stock = parse_stock(message.text)
            admin = await get_user(message.from_user, session)
            await InventoryService(session).set_stock(
                data["product_id"], new_stock, admin.id
            )
        else:
            await AdminCatalogService(session).update_product_field(
                data["product_id"], data["field"], message.text
            )
    except (CatalogError, InventoryError) as error:
        await message.answer(f"❌ {error}\nTry again or /cancel.")
        return

    await state.clear()
    await message.answer("✅ Updated.")
    await show_updated_card(message, session, data["product_id"])


@router.message(EditProduct.value, F.photo)
async def edit_photo_value(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    if data["field"] != "photo":
        await message.answer("Please send text, not a photo, or /cancel.")
        return

    try:
        await AdminCatalogService(session).set_product_photo(
            data["product_id"], message.photo[-1].file_id
        )
    except CatalogError as error:
        await message.answer(f"❌ {error}")
        return

    await state.clear()
    await message.answer("✅ Photo updated.")
    await show_updated_card(message, session, data["product_id"])



# ---------- receive stock ----------
@router.callback_query(AdminCb.filter(F.action == "recv"))
async def receive_start(call: CallbackQuery, callback_data: AdminCb, state: FSMContext):
    await state.clear()
    await state.update_data(product_id=callback_data.id)
    await state.set_state(ReceiveStock.quantity)
    await call.message.answer(
        "How many items arrived? (a whole number, e.g. 20)", reply_markup=cancel_kb()
    )
    await call.answer()


@router.message(ReceiveStock.quantity, F.text, ~F.text.startswith("/"))
async def receive_quantity(message: Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    try:
        quantity = parse_stock(message.text)
        admin = await get_user(message.from_user, session)
        product = await InventoryService(session).receive(
            data["product_id"], quantity, admin.id
        )
    except (CatalogError, InventoryError) as error:
        await message.answer(f"❌ {error}\nTry again or /cancel.")
        return

    await state.clear()
    await message.answer(
        f"✅ Received {quantity} × {escape(product.name)}. Stock now: {product.stock}"
    )
    await show_updated_card(message, session, product.id)    