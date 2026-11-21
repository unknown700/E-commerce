from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models.order import Order, OrderItem
from app.repositories.cart import CartRepository
from app.repositories.inventory import InventoryRepository
from app.repositories.order import OrderRepository
from app.repositories.product import ProductRepository
from app.repositories.user import UserRepository
from app.services.promo import PromoService

ACTIVE_STATUSES = ["new", "confirmed", "preparing", "ready", "on_the_way"]
COURIER_STATUSES = ["new", "confirmed", "preparing", "on_the_way"]
ASSIGNABLE_STATUSES = ("new", "confirmed", "preparing")


def can_assign_courier(order: Order) -> bool:
    return order.delivery_type == "delivery" and order.status in ASSIGNABLE_STATUSES


class OrderError(Exception):
    pass


def allowed_statuses(order: Order) -> list[str]:
    """Which statuses can this order move to next."""
    if order.status == "new":
        return ["confirmed", "cancelled"]
    if order.status == "confirmed":
        return ["preparing", "cancelled"]
    if order.status == "preparing":
        next_status = "on_the_way" if order.delivery_type == "delivery" else "ready"
        return [next_status, "cancelled"]
    if order.status in ("on_the_way", "ready"):
        return ["delivered"]
    return []


class OrderService:
    def __init__(self, session: AsyncSession):
        self.cart = CartRepository(session)
        self.products = ProductRepository(session)
        self.orders = OrderRepository(session)
        self.inventory = InventoryRepository(session)
        self.users = UserRepository(session)
        self.promos = PromoService(session)

        

    async def create_order(
        self,
        user_id: int,
        delivery_type: str,
        phone: str,
        address: str | None,
        latitude: float | None,
        longitude: float | None,
        payment_method: str = "cash",
        expected_total: Decimal | None = None,
    ) -> tuple[Order, list[tuple[str, int]]]:
        cart_items = await self.cart.get_items(user_id)
        if not cart_items:
            raise OrderError("Your cart is empty.")

        products = await self.products.get_for_update(
            [item.product_id for item in cart_items]
        )
        by_id = {product.id: product for product in products}

        # 1) validate everything before changing any data
        for item in cart_items:
            product = by_id.get(item.product_id)
            if product is None or not product.is_active:
                raise OrderError(f"{item.product.name} is no longer available.")
            if item.quantity > product.stock:
                raise OrderError(
                    f"Not enough stock for {product.name} (available: {product.stock})."
                )

        subtotal = sum(
            (by_id[item.product_id].price * item.quantity for item in cart_items),
            Decimal("0"),
        )
        # the promo row is locked, so two orders cannot use the last "use" at once
        promo, discount, promo_error = await self.promos.cart_discount(
            user_id, subtotal, lock=True
        )
        if promo is not None and promo_error:
            raise OrderError(
                f"Promo code {promo.code} is not valid: {promo_error}. "
                "Remove it in your cart and try again."
            )

        if expected_total is not None and subtotal - discount != expected_total:
            raise OrderError("Your cart changed after the payment started.")    

        # 2) create the order, decrease stock, remember low-stock products
        order = Order(
            user_id=user_id,
            status="new",
            delivery_type=delivery_type,
            payment_method=payment_method,
            phone=phone,
            address=address,
            latitude=latitude,
            longitude=longitude,
            discount=discount,
            promo_code=promo.code if promo else None,
            promo_code_id=promo.id if promo else None,
            total=Decimal("0"),
        )
        total = Decimal("0")
        low_stock: list[tuple[str, int]] = []
        threshold = settings.low_stock_threshold

        for item in cart_items:
            product = by_id[item.product_id]
            old_stock = product.stock
            product.stock -= item.quantity
            total += product.price * item.quantity

            crossed = old_stock > threshold >= product.stock
            sold_out = product.stock == 0 and old_stock > 0
            if crossed or sold_out:
                low_stock.append((product.name, product.stock))

            order.items.append(
                OrderItem(
                    product_id=product.id,
                    product_name=product.name,
                    unit_price=product.price,
                    quantity=item.quantity,
                )
            )
        order.total = total - discount  # the amount the customer pays

        await self.orders.add(order)  # order.id is known after this

        # 3) write the stock history, clear the cart and the applied promo
        for item in cart_items:
            product = by_id[item.product_id]
            await self.inventory.add_movement(
                product.id,
                -item.quantity,
                product.stock,
                "sale",
                order_id=order.id,
                user_id=user_id,
            )
        await self.cart.clear(user_id)
        await self.promos.remove(user_id)
        return order, low_stock

    async def get_order(self, order_id: int) -> Order | None:
        return await self.orders.get_by_id(order_id)

    async def get_user_orders(self, user_id: int) -> list[Order]:
        return await self.orders.get_by_user(user_id)

    async def get_active_orders(self) -> list[Order]:
        return await self.orders.get_by_statuses(ACTIVE_STATUSES)

    async def change_status(self, order_id: int, new_status: str) -> Order:
        order = await self.orders.get_by_id(order_id, for_update=True)
        if order is None:
            raise OrderError("Order not found.")
        if new_status not in allowed_statuses(order):
            raise OrderError("This status change is not allowed.")

        if new_status == "cancelled":
            await self._restock(order)
        order.status = new_status
        return order

    async def _restock(self, order: Order) -> None:
        product_ids = [i.product_id for i in order.items if i.product_id is not None]
        if not product_ids:
            return
        products = await self.products.get_for_update(product_ids)
        by_id = {product.id: product for product in products}
        for item in order.items:
            product = by_id.get(item.product_id)
            if product is None:
                continue
            product.stock += item.quantity
            await self.inventory.add_movement(
                product.id,
                item.quantity,
                product.stock,
                "cancel_return",
                order_id=order.id,
            )


    async def get_courier_orders(self, courier_id: int) -> list[Order]:
        return await self.orders.get_by_courier(courier_id, COURIER_STATUSES)

    async def assign_courier(
        self, order_id: int, courier_id: int
    ) -> tuple[Order, int | None]:
        order = await self.orders.get_by_id(order_id, for_update=True)
        if order is None:
            raise OrderError("Order not found.")
        if not can_assign_courier(order):
            raise OrderError("A courier cannot be assigned to this order.")

        courier = await self.users.get_by_id(courier_id)
        if courier is None or courier.role != "courier" or not courier.is_active:
            raise OrderError("Courier not found.")

        previous_id = order.courier_id
        order.courier_id = courier.id
        return order, previous_id

    async def courier_action(self, order_id: int, courier_id: int, action: str) -> Order:
        order = await self.orders.get_by_id(order_id)
        if order is None or order.courier_id != courier_id:
            raise OrderError("This order is not assigned to you.")

        if action == "pickup":
            if order.status != "preparing":
                raise OrderError("The order is not ready for pickup yet.")
            new_status = "on_the_way"
        elif action == "deliver":
            if order.status != "on_the_way":
                raise OrderError("Pick the order up first.")
            new_status = "delivered"
        else:
            raise OrderError("Unknown action.")
        return await self.change_status(order_id, new_status)