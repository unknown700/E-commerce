from decimal import Decimal
from itertools import count

from sqlalchemy import func, select

from app.database.models.category import Category
from app.database.models.product import Product
from app.repositories.cart import CartRepository
from app.services.order import OrderService
from app.services.user import UserService

_ids = count(1000)


def unique() -> int:
    return next(_ids)


async def make_user(session, language: str = "en", role: str = "customer"):
    telegram_id = unique()
    user, _ = await UserService(session).register(
        telegram_id, f"user{telegram_id}", f"User {telegram_id}"
    )
    user.language = language
    user.role = role
    await session.flush()
    return user


async def make_product(
    session, price: str = "10", stock: int = 10, name: str | None = None, active: bool = True
):
    number = unique()
    category = Category(name=f"Category {number}")
    session.add(category)
    await session.flush()
    product = Product(
        category_id=category.id,
        name=name or f"Product {number}",
        description="Test",
        price=Decimal(price),
        stock=stock,
        is_active=active,
    )
    session.add(product)
    await session.flush()
    return product


async def fill_cart(session, user, *items) -> None:
    """items are (product, quantity) pairs."""
    repo = CartRepository(session)
    for product, quantity in items:
        await repo.add(user.id, product.id, quantity)


async def place_order(session, user, delivery_type: str = "pickup", **kwargs):
    return await OrderService(session).create_order(
        user_id=user.id,
        delivery_type=delivery_type,
        phone="+10000000000",
        address="Test street 1" if delivery_type == "delivery" else None,
        latitude=None,
        longitude=None,
        **kwargs,
    )


async def count_rows(session, model) -> int:
    return await session.scalar(select(func.count()).select_from(model))