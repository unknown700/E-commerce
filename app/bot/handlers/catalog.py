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
from app.i18n import all_texts, t
from app.services.catalog import CatalogService

router = Router()


@router.message(Command("catalog"))
@router.message(F.text.in_(all_texts("menu.catalog")))
async def show_categories(message: Message, session: AsyncSession, lang: str):
    categories = await CatalogService(session).list_categories()
    if not categories:
        await message.answer(t(lang, "catalog.empty"))
        return
    await message.answer(
        t(lang, "catalog.choose_category"), reply_markup=categories_kb(categories)
    )


@router.callback_query(NavCb.filter(F.to == "categories"))
async def back_to_categories(call: CallbackQuery, session: AsyncSession, lang: str):
    categories = await CatalogService(session).list_categories()
    await call.message.delete()
    await call.message.answer(
        t(lang, "catalog.choose_category"), reply_markup=categories_kb(categories)
    )
    await call.answer()


@router.callback_query(CategoryCb.filter())
async def show_products(
    call: CallbackQuery, callback_data: CategoryCb, session: AsyncSession, lang: str
):
    products = await CatalogService(session).list_products(callback_data.id)
    await call.message.delete()
    if products:
        await call.message.answer(
            t(lang, "catalog.choose_product"), reply_markup=products_kb(products, lang)
        )
    else:
        await call.message.answer(
            t(lang, "catalog.no_products"), reply_markup=products_kb([], lang)
        )
    await call.answer()


@router.callback_query(ProductCb.filter())
async def show_product(
    call: CallbackQuery, callback_data: ProductCb, session: AsyncSession, lang: str
):
    product = await CatalogService(session).get_product(callback_data.id)
    if product is None or not product.is_active:
        await call.answer(t(lang, "catalog.not_found"), show_alert=True)
        return

    stock = (
        t(lang, "catalog.in_stock", count=product.stock)
        if product.stock > 0
        else t(lang, "catalog.out_of_stock")
    )
    text = (
        f"<b>{escape(product.name)}</b>\n\n"
        f"{escape(product.description or '')}\n\n"
        f"💰 {format_price(product.price)}\n"
        f"📦 {stock}"
    )

    await call.message.delete()
    keyboard = product_kb(product.category_id, product.id, product.stock > 0, lang)
    if product.photo_file_id:
        await call.message.answer_photo(
            product.photo_file_id, caption=text, reply_markup=keyboard
        )
    else:
        await call.message.answer(text, reply_markup=keyboard)
    await call.answer()