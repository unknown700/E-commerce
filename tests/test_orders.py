from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.config import settings
from app.database.models.order import Order, OrderItem
from app.repositories.inventory import InventoryRepository
from app.services.cart import CartService
from app.services.order import OrderError, OrderService, allowed_statuses
from tests.factories import count_rows, fill_cart, make_product, make_user, place_order


async def test_order_decreases_stock_and_clears_the_cart(session):
    user = await make_user(session)
    product = await make_product(session, price="25.50", stock=10)
    await fill_cart(session, user, (product, 2))

    order, _ = await place_order(session, user)

    assert order.status == "new"
    assert order.total == Decimal("51.00")
    assert order.payment_method == "cash"
    await session.refresh(product)
    assert product.stock == 8
    items, _ = await CartService(session).get_cart(user.id)
    assert items == []


async def test_order_keeps_the_price_it_was_bought_at(session):
    user = await make_user(session)
    product = await make_product(session, price="20", stock=5)
    await fill_cart(session, user, (product, 1))
    order, _ = await place_order(session, user)

    product.price = Decimal("99")  # the price changes later
    await session.flush()

    result = await session.execute(
        select(OrderItem.unit_price).where(OrderItem.order_id == order.id)
    )
    assert result.scalar_one() == Decimal("20.00")


async def test_not_enough_stock_changes_nothing(session):
    user = await make_user(session)
    product = await make_product(session, stock=10)
    await fill_cart(session, user, (product, 3))
    product.stock = 1  # someone else bought the rest
    await session.flush()

    with pytest.raises(OrderError) as error:
        await place_order(session, user)

    assert error.value.key == "err.no_stock"
    await session.refresh(product)
    assert product.stock == 1
    items, _ = await CartService(session).get_cart(user.id)
    assert len(items) == 1  # the cart is untouched
    assert await count_rows(session, Order) == 0


async def test_empty_cart_cannot_be_ordered(session):
    user = await make_user(session)
    with pytest.raises(OrderError) as error:
        await place_order(session, user)
    assert error.value.key == "err.cart_empty"


async def test_every_stock_change_is_written_to_the_history(session):
    user = await make_user(session)
    product = await make_product(session, stock=10)
    await fill_cart(session, user, (product, 2))
    order, _ = await place_order(session, user)

    rows = await InventoryRepository(session).recent_movements(10)
    movements = [m for m, name, _ in rows if name == product.name]
    assert len(movements) == 1
    assert movements[0].delta == -2
    assert movements[0].stock_after == 8
    assert movements[0].reason == "sale"
    assert movements[0].order_id == order.id


async def test_cancelling_an_order_returns_the_stock(session):
    user = await make_user(session)
    product = await make_product(session, stock=10)
    await fill_cart(session, user, (product, 4))
    order, _ = await place_order(session, user)

    await OrderService(session).change_status(order.id, "cancelled")

    await session.refresh(product)
    assert product.stock == 10
    rows = await InventoryRepository(session).recent_movements(10)
    reasons = [m.reason for m, name, _ in rows if name == product.name]
    assert reasons == ["cancel_return", "sale"]  # newest first


async def test_invalid_status_change_is_refused(session):
    user = await make_user(session)
    product = await make_product(session)
    await fill_cart(session, user, (product, 1))
    order, _ = await place_order(session, user)

    with pytest.raises(OrderError):
        await OrderService(session).change_status(order.id, "delivered")  # new -> delivered


@pytest.mark.parametrize(
    "status, delivery_type, expected",
    [
        ("new", "delivery", ["confirmed", "cancelled"]),
        ("confirmed", "pickup", ["preparing", "cancelled"]),
        ("preparing", "delivery", ["on_the_way", "cancelled"]),
        ("preparing", "pickup", ["ready", "cancelled"]),
        ("on_the_way", "delivery", ["delivered"]),
        ("ready", "pickup", ["delivered"]),
        ("delivered", "delivery", []),
        ("cancelled", "pickup", []),
    ],
)
def test_allowed_status_transitions(status, delivery_type, expected):
    order = SimpleNamespace(status=status, delivery_type=delivery_type)
    assert allowed_statuses(order) == expected


async def test_low_stock_alert_is_sent_only_when_crossing_the_threshold(
    session, monkeypatch
):
    monkeypatch.setattr(settings, "low_stock_threshold", 5)
    user = await make_user(session)
    product = await make_product(session, stock=8)

    await fill_cart(session, user, (product, 4))  # 8 -> 4: crosses the threshold
    _, alerts = await place_order(session, user)
    assert alerts == [(product.name, 4)]

    await fill_cart(session, user, (product, 1))  # 4 -> 3: already low, no new alert
    _, alerts = await place_order(session, user)
    assert alerts == []

    await fill_cart(session, user, (product, 3))  # 3 -> 0: sold out
    _, alerts = await place_order(session, user)
    assert alerts == [(product.name, 0)]


async def test_courier_can_only_work_with_his_own_order(session):
    customer = await make_user(session)
    courier = await make_user(session, role="courier")
    other_courier = await make_user(session, role="courier")
    product = await make_product(session)
    await fill_cart(session, customer, (product, 1))
    order, _ = await place_order(session, customer, delivery_type="delivery")

    service = OrderService(session)
    await service.assign_courier(order.id, courier.id)
    await service.change_status(order.id, "confirmed")

    with pytest.raises(OrderError):  # not prepared yet
        await service.courier_action(order.id, courier.id, "pickup")

    await service.change_status(order.id, "preparing")
    with pytest.raises(OrderError):  # somebody else's delivery
        await service.courier_action(order.id, other_courier.id, "pickup")

    picked_up = await service.courier_action(order.id, courier.id, "pickup")
    assert picked_up.status == "on_the_way"
    delivered = await service.courier_action(order.id, courier.id, "deliver")
    assert delivered.status == "delivered"