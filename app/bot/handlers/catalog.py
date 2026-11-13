
from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.formatting import format_price
from app.bot.keyboards.catalog import (
    CategoryCb,
    NavCb,
    ProductCb,
    categories_kb,
    product_kb,
    products_kb,
)
from app.services.catalog import CatalogService

router = Router()


@router.message(Command("catalog"))
@router.message(F.text == "🛍 Catalog")
async def show_categories(message: Message, session: AsyncSession):
    categories = await CatalogService(session).list_categories()
    if not categories:
        await message.answer("The catalog is currently empty.")
        return
    await message.answer("Choose a category:", reply_markup=categories_kb(categories))


@router.callback_query(NavCb.filter(F.to == "categories"))
async def back_to_categories(call: CallbackQuery, session: AsyncSession):
    categories = await CatalogService(session).list_categories()
    await call.message.delete()
    await call.message.answer(
        "Choose a category:", reply_markup=categories_kb(categories)
    )
    await call.answer()


@router.callback_query(CategoryCb.filter())
async def show_products(
    call: CallbackQuery, callback_data: CategoryCb, session: AsyncSession
):
    products = await CatalogService(session).list_products(callback_data.id)
    await call.message.delete()
    if products:
        await call.message.answer(
            "Choose a product:", reply_markup=products_kb(products)
        )
    else:
        await call.message.answer(
            "There are currently no products in this category.",
            reply_markup=products_kb([]),
        )
    await call.answer()


@router.callback_query(ProductCb.filter())
async def show_product(
    call: CallbackQuery, callback_data: ProductCb, session: AsyncSession
):
    product = await CatalogService(session).get_product(callback_data.id)
    if product is None or not product.is_active:
        await call.answer("Product not found.", show_alert=True)
        return

    stock = f"Available: {product.stock} units" if product.stock > 0 else "Out of stock"
    text = (
        f"<b>{escape(product.name)}</b>\n\n"
        f"{escape(product.description or '')}\n\n"
        f"💰 {format_price(product.price)}\n"
        f"📦 {stock}"
    )

    await call.message.delete()
    if product.photo_file_id:
        await call.message.answer_photo(
            product.photo_file_id,
            caption=text,
            reply_markup=product_kb(product.category_id),
        )
    else:
        await call.message.answer(text, reply_markup=product_kb(product.category_id))
    await call.answer()
