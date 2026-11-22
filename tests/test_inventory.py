import pytest

from app.config import settings
from app.services.inventory import InventoryError, InventoryService
from tests.factories import make_product, make_user


async def movements_of(session, product):
    rows = await InventoryService(session).recent_movements(20)
    return [m for m, name, _ in rows if name == product.name]


async def test_receiving_stock_increases_it_and_is_logged(session):
    admin = await make_user(session)
    product = await make_product(session, stock=5)

    await InventoryService(session).receive(product.id, 20, admin.id)

    await session.refresh(product)
    assert product.stock == 25
    movement = (await movements_of(session, product))[0]
    assert (movement.delta, movement.stock_after, movement.reason) == (20, 25, "receipt")
    assert movement.user_id == admin.id


async def test_receiving_needs_a_positive_quantity(session):
    admin = await make_user(session)
    product = await make_product(session, stock=5)
    with pytest.raises(InventoryError):
        await InventoryService(session).receive(product.id, 0, admin.id)


async def test_manual_stock_change_is_an_adjustment(session):
    admin = await make_user(session)
    product = await make_product(session, stock=10)
    service = InventoryService(session)

    await service.set_stock(product.id, 7, admin.id)
    await service.set_stock(product.id, 7, admin.id)  # no change: nothing is logged

    movements = await movements_of(session, product)
    assert len(movements) == 1
    assert (movements[0].delta, movements[0].reason) == (-3, "adjustment")


async def test_low_stock_list(session, monkeypatch):
    monkeypatch.setattr(settings, "low_stock_threshold", 5)
    low = await make_product(session, stock=3)
    enough = await make_product(session, stock=50)

    names = [product.name for product in await InventoryService(session).low_stock()]
    assert low.name in names
    assert enough.name not in names