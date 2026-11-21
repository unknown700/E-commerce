from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models.order import Order
from app.database.models.payment import Payment
from app.database.models.promo import PromoCode
from app.repositories.cart import CartRepository
from app.repositories.order import OrderRepository
from app.repositories.payment import PaymentRepository
from app.repositories.user import UserRepository
from app.services.order import OrderError, OrderService
from app.services.promo import PromoService

MIN_CARD_AMOUNT = Decimal("1.00")


class PaymentError(Exception):
    pass


def to_cents(value: Decimal) -> int:
    """Telegram wants amounts in the smallest unit (cents)."""
    return int((value * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def parse_payload(payload: str) -> int | None:
    if payload.startswith("pay:") and payload[4:].isdigit():
        return int(payload[4:])
    return None


def _label(text: str) -> str:
    return text if len(text) <= 32 else text[:31] + "…"


@dataclass
class Quote:
    items: list
    subtotal: Decimal
    promo: PromoCode | None
    discount: Decimal
    total: Decimal


@dataclass
class PaymentResult:
    payment: Payment
    order: Order | None
    low_stock: list[tuple[str, int]]
    fresh: bool  # False when Telegram delivered the same payment twice
    problem: str | None = None


class PaymentService:
    def __init__(self, session: AsyncSession):
        self.payments = PaymentRepository(session)
        self.cart = CartRepository(session)
        self.promos = PromoService(session)
        self.users = UserRepository(session)
        self.orders = OrderService(session)
        self.order_repo = OrderRepository(session)

    async def _quote(self, user_id: int) -> Quote:
        items = await self.cart.get_items(user_id)
        if not items:
            raise PaymentError("Your cart is empty.")
        for item in items:
            product = item.product
            if not product.is_active:
                raise PaymentError(f"{product.name} is no longer available.")
            if item.quantity > product.stock:
                raise PaymentError(
                    f"Not enough stock for {product.name} (available: {product.stock})."
                )

        subtotal = sum((i.product.price * i.quantity for i in items), Decimal("0"))
        promo, discount, error = await self.promos.cart_discount(user_id, subtotal)
        if promo is not None and error:
            raise PaymentError(
                f"Promo code {promo.code} is not valid: {error}. "
                "Remove it in your cart and try again."
            )
        total = subtotal - discount
        if total < MIN_CARD_AMOUNT:
            raise PaymentError("Online payment is available for orders of at least $1.")
        return Quote(items, subtotal, promo, discount, total)

    async def start(
        self,
        user_id: int,
        delivery_type: str,
        phone: str,
        address: str | None,
        latitude: float | None,
        longitude: float | None,
    ) -> tuple[Payment, list[tuple[str, int]]]:
        """Saves the checkout data and returns the invoice lines (label, cents)."""
        quote = await self._quote(user_id)
        payment = await self.payments.add(
            Payment(
                user_id=user_id,
                amount=quote.total,
                currency=settings.currency,
                status="pending",
                delivery_type=delivery_type,
                phone=phone,
                address=address,
                latitude=latitude,
                longitude=longitude,
            )
        )
        lines = [
            (_label(f"{i.product.name} × {i.quantity}"), to_cents(i.product.price * i.quantity))
            for i in quote.items
        ]
        if quote.promo is not None and quote.discount > 0:
            lines.append((_label(f"Promo {quote.promo.code}"), -to_cents(quote.discount)))
        return payment, lines

    async def validate_pre_checkout(
        self, payload: str, telegram_id: int, total_amount: int, currency: str
    ) -> str | None:
        """Runs right before the money is taken. Returns an error text or None."""
        payment_id = parse_payload(payload)
        payment = await self.payments.get_by_id(payment_id) if payment_id else None
        if payment is None or payment.status != "pending":
            return "This payment is no longer valid. Please start checkout again."

        user = await self.users.get_by_telegram_id(telegram_id)
        if user is None or user.id != payment.user_id:
            return "This payment belongs to another account."
        if currency != payment.currency or total_amount != to_cents(payment.amount):
            return "The payment amount does not match your order. Please start again."

        try:
            quote = await self._quote(user.id)
        except PaymentError as error:
            return str(error)
        if to_cents(quote.total) != total_amount:
            return "Your cart has changed. Please open your cart and start checkout again."
        return None

    async def complete(
        self,
        payload: str,
        telegram_id: int,
        total_amount: int,
        telegram_charge_id: str,
        provider_charge_id: str,
    ) -> PaymentResult:
        payment_id = parse_payload(payload)
        payment = (
            await self.payments.get_by_id(payment_id, for_update=True)
            if payment_id
            else None
        )
        if payment is None:
            raise PaymentError("Unknown payment.")
        user = await self.users.get_by_telegram_id(telegram_id)
        if user is None or user.id != payment.user_id:
            raise PaymentError("The payment does not belong to this user.")

        if payment.status != "pending":  # duplicate delivery
            order = (
                await self.order_repo.get_by_id(payment.order_id)
                if payment.order_id
                else None
            )
            return PaymentResult(payment, order, [], fresh=False)

        payment.telegram_charge_id = telegram_charge_id
        payment.provider_charge_id = provider_charge_id
        payment.paid_at = datetime.now(timezone.utc)

        if total_amount != to_cents(payment.amount):
            payment.status = "needs_refund"
            return PaymentResult(
                payment, None, [], True, "The paid amount does not match the order."
            )

        try:
            order, low_stock = await self.orders.create_order(
                user_id=user.id,
                delivery_type=payment.delivery_type,
                phone=payment.phone,
                address=payment.address,
                latitude=payment.latitude,
                longitude=payment.longitude,
                payment_method="card",
                expected_total=payment.amount,
            )
        except OrderError as error:
            payment.status = "needs_refund"
            return PaymentResult(payment, None, [], True, str(error))

        payment.status = "paid"
        payment.order_id = order.id
        return PaymentResult(payment, order, low_stock, True)

    async def get_by_order(self, order_id: int) -> Payment | None:
        return await self.payments.get_by_order(order_id)

    async def recent(self) -> list[Payment]:
        return await self.payments.recent()