from html import escape

DELIVERY_LABELS = {"delivery": "🚚 Delivery", "pickup": "🏪 Pickup"}

STATUS_LABELS = {
    "new": "🆕 New",
    "confirmed": "✅ Confirmed",
    "preparing": "👨‍🍳 Preparing",
    "ready": "📦 Ready for pickup",
    "on_the_way": "🚚 On the way",
    "delivered": "🎉 Delivered",
    "cancelled": "❌ Cancelled",
}

STATUS_MESSAGES = {
    "confirmed": "✅ Your order #{id} has been confirmed.",
    "preparing": "👨‍🍳 We are preparing your order #{id}.",
    "ready": "📦 Your order #{id} is ready for pickup.",
    "on_the_way": "🚚 Your order #{id} is on the way.",
    "delivered": "🎉 Your order #{id} was delivered. Thank you!",
    "cancelled": "❌ Your order #{id} was cancelled.",
}

ACTION_LABELS = {
    "confirmed": "✅ Confirm",
    "preparing": "👨‍🍳 Start preparing",
    "ready": "📦 Ready for pickup",
    "on_the_way": "🚚 Send out",
    "delivered": "🎉 Mark delivered",
    "cancelled": "❌ Cancel order",
}


def format_price(value) -> str:
    return f"{value:,.0f}".replace(",", " ") + " UZS"


def format_order_details(order, customer=None) -> str:
    created = order.created_at.astimezone().strftime("%d.%m.%Y %H:%M")
    lines = [
        f"📦 <b>Order #{order.id}</b>",
        f"Status: {STATUS_LABELS[order.status]}",
        f"Date: {created}\n",
    ]
    if customer is not None:
        name = escape(customer.full_name)
        if customer.username:
            name += f" (@{escape(customer.username)})"
        lines.append(f"Customer: {name}")
    lines.append(f"Phone: {escape(order.phone)}")
    lines.append(f"Receive: {DELIVERY_LABELS[order.delivery_type]}")
    if order.address:
        lines.append(f"Address: {escape(order.address)}")
    if order.latitude is not None and order.longitude is not None:
        lines.append(
            f'📍 <a href="https://maps.google.com/?q={order.latitude},{order.longitude}">Open on map</a>'
        )

    lines.append("\nItems:")
    for item in order.items:
        subtotal = item.unit_price * item.quantity
        lines.append(
            f"• {escape(item.product_name)} × {item.quantity} = {format_price(subtotal)}"
        )
    lines.append(f"\n<b>Total: {format_price(order.total)}</b>")
    lines.append("Payment: 💵 Cash")
    return "\n".join(lines)



def format_admin_product(product, category) -> str:
    status = "✅ Visible to customers" if product.is_active else "🚫 Hidden from customers"
    description = escape(product.description) if product.description else "—"
    return (
        f"🛍 <b>{escape(product.name)}</b>\n\n"
        f"Category: {escape(category.name)}\n"
        f"Price: {format_price(product.price)}\n"
        f"Stock: {product.stock}\n"
        f"Status: {status}\n"
        f"Description: {description}"
    )
