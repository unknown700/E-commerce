import re
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.promo import PromoCode
from app.errors import AppError
from app.repositories.promo import PromoRepository
from app.services.admin_catalog import parse_price, parse_stock

ZERO = Decimal("0")


class PromoError(AppError):
    pass


def _money(value: Decimal) -> str:
    text = f"${value:,.2f}"
    return text[:-3] if text.endswith(".00") else text


def parse_percent(text: str) -> Decimal:
    cleaned = text.strip().rstrip("%").strip()
    if not (cleaned.isascii() and cleaned.isdigit()):
        raise PromoError("Send a whole number from 1 to 90.")
    value = int(cleaned)
    if not 1 <= value <= 90:
        raise PromoError("The percent must be between 1 and 90.")
    return Decimal(value)


def parse_min_order(text: str) -> Decimal:
    if text.strip() in {"0", "-"}:
        return ZERO
    return parse_price(text)  # raises CatalogError on bad input


def parse_max_uses(text: str) -> int | None:
    if text.strip() == "-":
        return None
    value = parse_stock(text)  # raises CatalogError on bad input
    if value < 1:
        raise PromoError("Send a number of at least 1, or - for unlimited.")
    return value


def parse_days(text: str) -> int | None:
    cleaned = text.strip()
    if cleaned == "-":
        return None
    if not (cleaned.isascii() and cleaned.isdigit()) or not 1 <= int(cleaned) <= 365:
        raise PromoError("Send a number of days from 1 to 365, or - for no expiry.")
    return int(cleaned)


class PromoService:
    def __init__(self, session: AsyncSession):
        self.repo = PromoRepository(session)

    # ---------- discount rules ----------
    @staticmethod
    def _discount(promo: PromoCode, subtotal: Decimal) -> Decimal:
        if promo.kind == "percent":
            amount = (subtotal * promo.value / Decimal(100)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        else:
            amount = promo.value
        return min(amount, subtotal)

    async def _check(
        self, promo: PromoCode, user_id: int, subtotal: Decimal
    ) -> tuple[Decimal, PromoError | None]:
        """Returns (discount, error). The error is None when the code can be used."""
        if not promo.is_active:
            return ZERO, PromoError("promo.reason.inactive")
        if promo.expires_at is not None and promo.expires_at <= datetime.now(timezone.utc):
            return ZERO, PromoError("promo.reason.expired")
        if subtotal < promo.min_order:
            return ZERO, PromoError(
                "promo.reason.min_order", amount=_money(promo.min_order)
            )
        if promo.max_uses is not None and await self.repo.count_uses(promo.id) >= promo.max_uses:
            return ZERO, PromoError("promo.reason.used_up")
        if await self.repo.count_user_uses(promo.id, user_id) >= 1:
            return ZERO, PromoError("promo.reason.already_used")
        return self._discount(promo, subtotal), None

    # ---------- customer ----------
    async def apply_code(
        self, user_id: int, code: str, subtotal: Decimal
    ) -> tuple[PromoCode, Decimal]:
        promo = await self.repo.get_by_code(code.strip().upper())
        if promo is None:
            raise PromoError("promo.not_found")
        discount, error = await self._check(promo, user_id, subtotal)
        if error:
            raise PromoError("promo.sorry", reason=error)
        await self.repo.set_cart_promo(user_id, promo.id)
        return promo, discount

    async def remove(self, user_id: int) -> None:
        await self.repo.clear_cart_promo(user_id)

    async def cart_discount(
        self, user_id: int, subtotal: Decimal, lock: bool = False
    ) -> tuple[PromoCode | None, Decimal, PromoError | None]:
        """The promo applied to the cart: (promo, discount, error)."""
        cart_promo = await self.repo.get_cart_promo(user_id)
        if cart_promo is None:
            return None, ZERO, None
        promo = await self.repo.get_by_id(cart_promo.promo_id, for_update=lock)
        if promo is None:
            return None, ZERO, None
        discount, error = await self._check(promo, user_id, subtotal)
        return promo, discount, error

    # ---------- admin ----------
    async def check_new_code(self, code: str) -> None:
        if not re.fullmatch(r"[A-Z0-9]{3,20}", code):
            raise PromoError("Use 3-20 letters or digits, no spaces.")
        if await self.repo.get_by_code(code):
            raise PromoError("This code already exists.")

    async def create_promo(
        self,
        code: str,
        kind: str,
        value: Decimal,
        min_order: Decimal,
        max_uses: int | None,
        days: int | None,
    ) -> PromoCode:
        await self.check_new_code(code)
        expires_at = (
            datetime.now(timezone.utc) + timedelta(days=days) if days else None
        )
        promo = PromoCode(
            code=code,
            kind=kind,
            value=value,
            min_order=min_order,
            max_uses=max_uses,
            expires_at=expires_at,
            is_active=True,
        )
        return await self.repo.add(promo)

    async def list_with_usage(self):
        return await self.repo.list_with_usage()

    async def toggle(self, promo_id: int) -> PromoCode | None:
        promo = await self.repo.get_by_id(promo_id)
        if promo is None:
            return None
        promo.is_active = not promo.is_active
        return promo