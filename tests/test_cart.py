from decimal import Decimal

from app.services.cart import CartService
from tests.factories import make_product, make_user


async def test_adding_twice_increases_the_quantity(session):
    user = await make_user(session)
    product = await make_product(session, price="10", stock=5)
    service = CartService(session)

    assert await service.add_product(user.id, product.id) == "added"
    assert await service.add_product(user.id, product.id) == "added"

    items, total = await service.get_cart(user.id)
    assert len(items) == 1
    assert items[0].quantity == 2
    assert total == Decimal("20")


async def test_cannot_add_more_than_the_stock(session):
    user = await make_user(session)
    product = await make_product(session, stock=2)
    service = CartService(session)

    await service.add_product(user.id, product.id)
    await service.add_product(user.id, product.id)
    assert await service.add_product(user.id, product.id) == "max"


async def test_unavailable_products_are_refused(session):
    user = await make_user(session)
    sold_out = await make_product(session, stock=0)
    hidden = await make_product(session, active=False)
    service = CartService(session)

    assert await service.add_product(user.id, sold_out.id) == "out_of_stock"
    assert await service.add_product(user.id, hidden.id) == "not_found"
    assert await service.add_product(user.id, 999_999) == "not_found"


async def test_decreasing_to_zero_removes_the_item(session):
    user = await make_user(session)
    product = await make_product(session)
    service = CartService(session)

    await service.add_product(user.id, product.id)
    assert await service.change_quantity(user.id, product.id, -1) == "removed"
    items, total = await service.get_cart(user.id)
    assert items == []
    assert total == Decimal("0")


async def test_increasing_beyond_the_stock_is_refused(session):
    user = await make_user(session)
    product = await make_product(session, stock=1)
    service = CartService(session)

    await service.add_product(user.id, product.id)
    assert await service.change_quantity(user.id, product.id, +1) == "max"