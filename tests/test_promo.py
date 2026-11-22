from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.database.models.order import Order
from app.services.cart import CartService
from app.services.order import OrderService
from app.services.promo import PromoError, PromoService
from tests.factories import count_rows, fill_cart, make_product, make_user, place_order


async def make_promo(session, code="SAVE10", kind="percent", value="10", **kwargs):
    return await PromoService(session).create_promo(
        code=code,
        kind=kind,
        value=Decimal(value),
        min_order=Decimal(kwargs.get("min_order", "0")),
        max_uses=kwargs.get("max_uses"),
        days=kwargs.get("days"),
    )


async def rejection_reason(session, user, code, subtotal) -> str:
    with pytest.raises(PromoError) as error:
        await PromoService(session).apply_code(user.id, code, Decimal(subtotal))
    return error.value.params["reason"].key


async def test_percent_discount(session):
    user = await make_user(session)
    await make_promo(session, value="10")
    promo, discount = await PromoService(session).apply_code(user.id, "save10", Decimal("200"))
    assert promo.code == "SAVE10"  # the code is not case sensitive
    assert discount == Decimal("20.00")


async def test_fixed_discount_never_exceeds_the_subtotal(session):
    user = await make_user(session)
    await make_promo(session, code="FIXED50", kind="fixed", value="50")
    _, discount = await PromoService(session).apply_code(user.id, "FIXED50", Decimal("30"))
    assert discount == Decimal("30")


async def test_unknown_code(session):
    user = await make_user(session)
    with pytest.raises(PromoError) as error:
        await PromoService(session).apply_code(user.id, "NOPE", Decimal("10"))
    assert error.value.key == "promo.not_found"


async def test_minimum_order_amount(session):
    user = await make_user(session)
    await make_promo(session, min_order="100")
    assert await rejection_reason(session, user, "SAVE10", "50") == "promo.reason.min_order"


async def test_expired_code(session):
    user = await make_user(session)
    promo = await make_promo(session)
    promo.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    await session.flush()
    assert await rejection_reason(session, user, "SAVE10", "50") == "promo.reason.expired"


async def test_switched_off_code(session):
    user = await make_user(session)
    promo = await make_promo(session)
    await PromoService(session).toggle(promo.id)
    assert await rejection_reason(session, user, "SAVE10", "50") == "promo.reason.inactive"


async def use_code_in_an_order(session, user, code="SAVE10"):
    product = await make_product(session, price="100", stock=50)
    await fill_cart(session, user, (product, 1))
    _, subtotal = await CartService(session).get_cart(user.id)
    await PromoService(session).apply_code(user.id, code, subtotal)
    order, _ = await place_order(session, user)
    return order


async def test_total_number_of_uses_is_limited(session):
    first = await make_user(session)
    second = await make_user(session)
    await make_promo(session, max_uses=1)

    await use_code_in_an_order(session, first)
    assert await rejection_reason(session, second, "SAVE10", "100") == "promo.reason.used_up"


async def test_each_customer_can_use_a_code_once(session):
    user = await make_user(session)
    await make_promo(session)

    await use_code_in_an_order(session, user)
    assert await rejection_reason(session, user, "SAVE10", "100") == "promo.reason.already_used"


async def test_cancelling_the_order_frees_the_code(session):
    user = await make_user(session)
    await make_promo(session)
    order = await use_code_in_an_order(session, user)

    await OrderService(session).change_status(order.id, "cancelled")

    promo, _ = await PromoService(session).apply_code(user.id, "SAVE10", Decimal("100"))
    assert promo.code == "SAVE10"


async def test_order_stores_the_discount_and_clears_the_applied_code(session):
    user = await make_user(session)
    await make_promo(session, value="10")

    order = await use_code_in_an_order(session, user)

    assert order.discount == Decimal("10.00")
    assert order.total == Decimal("90.00")
    assert order.promo_code == "SAVE10"
    promo, _, _ = await PromoService(session).cart_discount(user.id, Decimal("100"))
    assert promo is None
    assert await count_rows(session, Order) == 1