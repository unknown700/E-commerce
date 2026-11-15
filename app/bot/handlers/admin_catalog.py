from decimal import Decimal
from html import escape

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.filters import IsAdmin
from app.bot.formatting import format_price
from app.bot.keyboards.admin import (
    AdminCb,
    admin_menu_kb,
    cancel_kb,
    categories_admin_kb,
    choose_category_kb,
    confirm_product_kb,
    skip_kb,
)
from app.bot.states.admin import AddCategory, AddProduct
from app.services.admin_catalog import (
    AdminCatalogService,
    CatalogError,
    parse_price,
    parse_stock,
)

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


# ---------- menu and cancel ----------
@router.callback_query(AdminCb.filter(F.action == "menu"))
async def admin_menu(call: CallbackQuery):
    await call.message.edit_text("🛠 <b>Admin panel</b>", reply_markup=admin_menu_kb())
    await call.answer()


@router.callback_query(AdminCb.filter(F.action == "cancel"))
async def cancel_by_button(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.answer("Cancelled.", reply_markup=admin_menu_kb())
    await call.answer()


@router.message(Command("cancel"), StateFilter(AddCategory, AddProduct))
async def cancel_by_command(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Cancelled.", reply_markup=admin_menu_kb())


# ---------- categories ----------
async def render_categories(session: AsyncSession):
    categories = await AdminCatalogService(session).list_categories()
    if categories:
        text = "🗂 <b>Categories</b>\nTap a category to enable ✅ or disable 🚫 it."
    else:
        text = "🗂 <b>Categories</b>\nNo categories yet."
    return text, categories_admin_kb(categories)


@router.callback_query(AdminCb.filter(F.action == "categories"))
async def show_categories(call: CallbackQuery, session: AsyncSession):
    text, keyboard = await render_categories(session)
    await call.message.edit_text(text, reply_markup=keyboard)
    await call.answer()


@router.callback_query(AdminCb.filter(F.action == "cat_toggle"))
async def toggle_category(
    call: CallbackQuery, callback_data: AdminCb, session: AsyncSession
):
    category = await AdminCatalogService(session).toggle_category(callback_data.id)
    if category is None:
        await call.answer("Category not found", show_alert=True)
        return
    text, keyboard = await render_categories(session)
    await call.message.edit_text(text, reply_markup=keyboard)
    await call.answer("Enabled ✅" if category.is_active else "Disabled 🚫")


@router.callback_query(AdminCb.filter(F.action == "cat_add"))
async def add_category_start(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(AddCategory.name)
    await call.message.answer("Send the new category name:", reply_markup=cancel_kb())
    await call.answer()


@router.message(AddCategory.name, F.text, ~F.text.startswith("/"))
async def add_category_name(message: Message, state: FSMContext, session: AsyncSession):
    try:
        category = await AdminCatalogService(session).create_category(message.text)
    except CatalogError as error:
        await message.answer(f"❌ {error}\nTry another name or /cancel.")
        return

    await state.clear()
    await message.answer(f"✅ Category <b>{escape(category.name)}</b> created.")
    text, keyboard = await render_categories(session)
    await message.answer(text, reply_markup=keyboard)


# ---------- add product ----------
@router.callback_query(AdminCb.filter(F.action == "prod_add"))
async def add_product_start(
    call: CallbackQuery, state: FSMContext, session: AsyncSession
):
    categories = [
        c for c in await AdminCatalogService(session).list_categories() if c.is_active
    ]
    if not categories:
        await call.answer("Create an active category first.", show_alert=True)
        return

    await state.clear()
    await state.set_state(AddProduct.category)
    await call.message.answer(
        "Choose a category for the new product:",
        reply_markup=choose_category_kb(categories),
    )
    await call.answer()


@router.callback_query(AddProduct.category, AdminCb.filter(F.action == "prod_cat"))
async def add_product_category(
    call: CallbackQuery,
    callback_data: AdminCb,
    state: FSMContext,
    session: AsyncSession,
):
    category = await AdminCatalogService(session).get_category(callback_data.id)
    if category is None or not category.is_active:
        await call.answer("Category not available", show_alert=True)
        return

    await state.update_data(category_id=category.id, category_name=category.name)
    await state.set_state(AddProduct.name)
    await call.message.edit_text(f"Category: <b>{escape(category.name)}</b>")
    await call.message.answer("Send the product name:", reply_markup=cancel_kb())
    await call.answer()


@router.message(AddProduct.name, F.text, ~F.text.startswith("/"))
async def add_product_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if not 2 <= len(name) <= 200:
        await message.answer("The name must be 2-200 characters. Try again.")
        return
    await state.update_data(name=name)
    await state.set_state(AddProduct.description)
    await message.answer(
        "Send a short description, or tap Skip:", reply_markup=skip_kb("skip_desc")
    )


async def ask_price(message: Message, state: FSMContext):
    await state.set_state(AddProduct.price)
    await message.answer(
        "Send the price in UZS (numbers only, e.g. 3200000):", reply_markup=cancel_kb()
    )


@router.message(AddProduct.description, F.text, ~F.text.startswith("/"))
async def add_product_description(message: Message, state: FSMContext):
    description = message.text.strip()
    if len(description) > 500:
        await message.answer("The description is too long (max 500 characters).")
        return
    await state.update_data(description=description)
    await ask_price(message, state)


@router.callback_query(AddProduct.description, AdminCb.filter(F.action == "skip_desc"))
async def skip_description(call: CallbackQuery, state: FSMContext):
    await state.update_data(description=None)
    await call.message.edit_reply_markup(reply_markup=None)
    await ask_price(call.message, state)
    await call.answer()


@router.message(AddProduct.price, F.text, ~F.text.startswith("/"))
async def add_product_price(message: Message, state: FSMContext):
    try:
        price = parse_price(message.text)
    except CatalogError as error:
        await message.answer(f"❌ {error}")
        return
    await state.update_data(price=str(price))
    await state.set_state(AddProduct.stock)
    await message.answer(
        "How many items are in stock? (a whole number, e.g. 10)",
        reply_markup=cancel_kb(),
    )


@router.message(AddProduct.stock, F.text, ~F.text.startswith("/"))
async def add_product_stock(message: Message, state: FSMContext):
    try:
        stock = parse_stock(message.text)
    except CatalogError as error:
        await message.answer(f"❌ {error}")
        return
    await state.update_data(stock=stock)
    await state.set_state(AddProduct.photo)
    await message.answer(
        "Send a product photo, or tap Skip:", reply_markup=skip_kb("skip_photo")
    )


async def show_product_summary(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.set_state(AddProduct.confirm)

    description = escape(data["description"]) if data.get("description") else "—"
    text = (
        "📋 <b>New product</b>\n\n"
        f"Category: {escape(data['category_name'])}\n"
        f"Name: {escape(data['name'])}\n"
        f"Description: {description}\n"
        f"Price: {format_price(Decimal(data['price']))}\n"
        f"Stock: {data['stock']}\n"
        f"Photo: {'yes' if data.get('photo_file_id') else 'no'}"
    )
    if data.get("photo_file_id"):
        await message.answer_photo(
            data["photo_file_id"], caption=text, reply_markup=confirm_product_kb()
        )
    else:
        await message.answer(text, reply_markup=confirm_product_kb())


@router.message(AddProduct.photo, F.photo)
async def add_product_photo(message: Message, state: FSMContext):
    await state.update_data(photo_file_id=message.photo[-1].file_id)
    await show_product_summary(message, state)


@router.message(AddProduct.photo, ~F.text.startswith("/"))
async def add_product_photo_invalid(message: Message):
    await message.answer("Please send a photo (as a picture, not a file), or tap Skip.")


@router.callback_query(AddProduct.photo, AdminCb.filter(F.action == "skip_photo"))
async def skip_photo(call: CallbackQuery, state: FSMContext):
    await state.update_data(photo_file_id=None)
    await call.message.edit_reply_markup(reply_markup=None)
    await show_product_summary(call.message, state)
    await call.answer()


@router.callback_query(AddProduct.confirm, AdminCb.filter(F.action == "prod_save"))
async def save_product(call: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    await call.message.edit_reply_markup(reply_markup=None)

    try:
        product = await AdminCatalogService(session).create_product(
            category_id=data["category_id"],
            name=data["name"],
            description=data.get("description"),
            price=Decimal(data["price"]),
            stock=data["stock"],
            photo_file_id=data.get("photo_file_id"),
        )
    except CatalogError as error:
        await state.clear()
        await call.message.answer(f"❌ {error}", reply_markup=admin_menu_kb())
        await call.answer()
        return

    await state.clear()
    await call.message.answer(
        f"✅ Product <b>{escape(product.name)}</b> created.\n"
        "Customers can see it in the catalog now.",
        reply_markup=admin_menu_kb(),
    )
    await call.answer()