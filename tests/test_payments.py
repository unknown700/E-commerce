from decimal import Decimal

import pytest
from sqlalchemy import select

from app.config import settings
from app.database.models.order import Order
from app.services.payment import PaymentError, PaymentService, parse_payload, to_cents
from app.services.promo import PromoService
from tests.factories import count_rows, fill_cart, make_product, make_user


def test_amounts_are_converted_to_cents():
    assert to_cents(Decimal("12.34")) == 1234
    assert to_cents(Decimal("10")) == 1000
    assert to_cents(Decimal("0.005")) == 1  # rounds half up


def test_payload_parsing():
    assert parse_payload("pay:15") == 15
    for bad in ("pay:", "pay:x", "abc", "15"):
        assert parse_payload(bad) is None


async def start_payment(session, user, product, quantity=3):
    await fill_cart(session, user, (product, quantity))
    return await PaymentService(session).start(
        user.id, "pickup", "+10000000000", None, None, None
    )


async def test_invoice_lines_add_up_to_the_total(session):
    user = await make_user(session)
    product = await make_product(session, price="10", stock=20)
    await PromoService(session).create_promo(
        "SAVE10", "percent", Decimal("10"), Decimal("0"), None, None
    )
    await fill_cart(session, user, (product, 3))
    await PromoService(session).apply_code(user.id, "SAVE10", Decimal("30"))

    payment, lines = await PaymentService(session).start(
        user.id, "pickup", "+10000000000", None, None, None
    )

    assert payment.status == "pending"
    assert payment.amount == Decimal("27.00")
    assert [amount for _, amount in lines] == [3000, -300]  # items, then the discount
    assert sum(amount for _, amount in lines) == to_cents(payment.amount)


async def test_online_payment_has_a_minimum_amount(session):
    user = await make_user(session)
    cheap = await make_product(session, price="0.50", stock=10)
    await fill_cart(session, user, (cheap, 1))
    with pytest.raises(PaymentError) as error:
        await PaymentService(session).start(user.id, "pickup", "+10000000000", None, None, None)
    assert error.value.key == "err.pay_min"


async def test_pre_checkout_accepts_a_valid_payment(session):
    user = await make_user(session)
    product = await make_product(session, price="10", stock=20)
    payment, _ = await start_payment(session, user, product)

    error = await PaymentService(session).validate_pre_checkout(
        f"pay:{payment.id}", user.telegram_id, to_cents(payment.amount), payment.currency
    )
    assert error is None


async def test_pre_checkout_refuses_a_changed_cart(session):
    user = await make_user(session)
    product = await make_product(session, price="10", stock=20)
    payment, _ = await start_payment(session, user, product, quantity=3)
    await fill_cart(session, user, (await make_product(session, price="5"), 1))

    error = await PaymentService(session).validate_pre_checkout(
        f"pay:{payment.id}", user.telegram_id, to_cents(payment.amount), payment.currency
    )
    assert error.key == "err.pay_cart_changed"


async def test_pre_checkout_refuses_wrong_amount_payer_and_payload(session):
    user = await make_user(session)
    stranger = await make_user(session)
    product = await make_product(session, price="10", stock=20)
    payment, _ = await start_payment(session, user, product)
    service = PaymentService(session)
    cents = to_cents(payment.amount)

    wrong_amount = await service.validate_pre_checkout(
        f"pay:{payment.id}", user.telegram_id, cents + 1, payment.currency
    )
    wrong_payer = await service.validate_pre_checkout(
        f"pay:{payment.id}", stranger.telegram_id, cents, payment.currency
    )
    unknown = await service.validate_pre_checkout(
        "pay:999999", user.telegram_id, cents, payment.currency
    )
    assert wrong_amount.key == "err.pay_amount"
    assert wrong_payer.key == "err.pay_other_account"
    assert unknown.key == "err.pay_invalid"


async def test_successful_payment_creates_a_paid_card_order(session):
    user = await make_user(session)
    product = await make_product(session, price="10", stock=20)
    payment, _ = await start_payment(session, user, product, quantity=3)

    result = await PaymentService(session).complete(
        payload=f"pay:{payment.id}",
        telegram_id=user.telegram_id,
        total_amount=to_cents(payment.amount),
        telegram_charge_id="tg-1",
        provider_charge_id="prov-1",
    )

    assert result.fresh and result.problem is None
    assert result.order.payment_method == "card"
    assert result.order.total == Decimal("30.00")
    assert payment.status == "paid"
    assert payment.order_id == result.order.id
    await session.refresh(product)
    assert product.stock == 17


async def test_the_same_payment_delivered_twice_creates_one_order(session):
    user = await make_user(session)
    product = await make_product(session, price="10", stock=20)
    payment, _ = await start_payment(session, user, product)
    service = PaymentService(session)
    arguments = dict(
        payload=f"pay:{payment.id}",
        telegram_id=user.telegram_id,
        total_amount=to_cents(payment.amount),
        telegram_charge_id="tg-1",
        provider_charge_id="prov-1",
    )

    first = await service.complete(**arguments)
    second = await service.complete(**arguments)

    assert first.fresh is True
    assert second.fresh is False
    assert await count_rows(session, Order) == 1


async def test_paid_but_sold_out_is_marked_for_refund(session):
    user = await make_user(session)
    product = await make_product(session, price="10", stock=20)
    payment, _ = await start_payment(session, user, product, quantity=3)
    product.stock = 0  # sold out between the invoice and the payment
    await session.flush()

    result = await PaymentService(session).complete(
        payload=f"pay:{payment.id}",
        telegram_id=user.telegram_id,
        total_amount=to_cents(payment.amount),
        telegram_charge_id="tg-2",
        provider_charge_id="prov-2",
    )

    assert result.order is None
    assert result.problem.key == "err.no_stock"
    assert payment.status == "needs_refund"
    assert payment.provider_charge_id == "prov-2"  # kept, so the money can be refunded
    assert await count_rows(session, Order) == 0


def test_payments_use_the_configured_currency():
    assert len(settings.currency) == 3