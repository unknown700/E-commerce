from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.order import Order, OrderItem
from app.repositories.cart import CartRepository
from app.repositories.order import OrderRepository
from app.repositories.product import ProductRepository


class OrderError(Exception):
    pass


class OrderService:
    def __init__(self, session: AsyncSession):
        self.cart = CartRepository(session)
        self.products = ProductRepository(session)
        self.orders = OrderRepository(session)

    async def create_order(
        self,
        user_id: int,
        delivery_type: str,
        phone: str,
        address: str | None,
        latitude: float | None,
        longitude: float | None,
    ) -> Order:
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

        # 2) create the order, decrease stock, clear the cart
        order = Order(
            user_id=user_id,
            status="new",
            delivery_type=delivery_type,
            payment_method="cash",
            phone=phone,
            address=address,
            latitude=latitude,
            longitude=longitude,
            total=Decimal("0"),
        )
        total = Decimal("0")
        for item in cart_items:
            product = by_id[item.product_id]
            product.stock -= item.quantity
            total += product.price * item.quantity
            order.items.append(
                OrderItem(
                    product_id=product.id,
                    product_name=product.name,
                    unit_price=product.price,
                    quantity=item.quantity,
                )
            )
        order.total = total

        await self.orders.add(order)
        await self.cart.clear(user_id)
        return order