from datetime import timedelta
from decimal import Decimal
from html import escape
from zoneinfo import ZoneInfo
from app.config import settings


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


def format_order_details(order, customer=None, courier=None) -> str:
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
    if courier is not None:
        courier_name = escape(courier.full_name)
        if courier.username:
            courier_name += f" (@{escape(courier.username)})"
        lines.append(f"🚚 Courier: {courier_name}")

    lines.append("\nItems:")
    for item in order.items:
        subtotal = item.unit_price * item.quantity
        lines.append(
            f"• {escape(item.product_name)} × {item.quantity} = {format_price(subtotal)}"
        )
    lines.append(f"\n<b>Total: {format_price(order.total)}</b>")
    lines.append("Payment: 💵 Cash")
    return "\n".join(lines)


COURIER_HINTS = {
    "new": "⏳ Waiting for confirmation.",
    "confirmed": "⏳ Being prepared. You will get a message when it is ready.",
    "preparing": "📦 Tap “Picked up” when you take the order.",
    "on_the_way": "🚚 Tap “Delivered” after you hand it over and collect the payment.",
}


def format_courier_order(order, customer=None) -> str:
    lines = [
        format_order_details(order, customer),
        "",
        f"💵 <b>Collect cash: {format_price(order.total)}</b>",
    ]
    hint = COURIER_HINTS.get(order.status)
    if hint:
        lines.append(hint)
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



PERIOD_TITLES = {"today": "Today", "week": "Last 7 days", "month": "Last 30 days"}
PREVIOUS_LABELS = {
    "today": "yesterday",
    "week": "the previous 7 days",
    "month": "the previous 30 days",
}
IN_PROGRESS_STATUSES = ("new", "confirmed", "preparing", "ready", "on_the_way")
STATUS_NAMES = {
    "new": "New",
    "confirmed": "Confirmed",
    "preparing": "Preparing",
    "ready": "Ready",
    "on_the_way": "On the way",
    "delivered": "Delivered",
    "cancelled": "Cancelled",
}


def _amount(value) -> str:
    return f"{value:,.0f}".replace(",", " ")


def _cut(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 1] + "…"


def _table(rows: list[str]) -> str:
    return "<pre>" + escape("\n".join(rows)) + "</pre>"


def _comparison(current: Decimal, previous: Decimal, label: str) -> str:
    if previous == 0:
        return "➖ No previous period to compare with yet"
    pct = (current - previous) / previous * 100
    if pct > 0:
        trend = f"📈 +{pct:.0f}%"
    elif pct < 0:
        trend = f"📉 -{abs(pct):.0f}%"
    else:
        trend = "➖ no change"
    return f"{trend} vs {label} ({format_price(previous)})"


def format_report(report) -> str:
    first = report.start.strftime("%d.%m.%Y")
    last = (report.end - timedelta(days=1)).strftime("%d.%m.%Y")
    dates = first if first == last else f"{first} – {last}"
    header = [
        f"📊 <b>Sales report: {PERIOD_TITLES[report.period]}</b>",
        f"📅 {dates}",
    ]

    zero = (0, Decimal("0"))
    placed = sum(count for count, _ in report.by_status.values())
    if placed == 0:
        return "\n".join(
            header
            + ["", "No orders in this period.", f"👥 New customers: {report.new_customers}"]
        )

    all_sum = sum((amount for _, amount in report.by_status.values()), Decimal("0"))
    delivered_count, delivered_sum = report.by_status.get("delivered", zero)
    cancelled_count, cancelled_sum = report.by_status.get("cancelled", zero)
    progress_count = sum(report.by_status.get(s, zero)[0] for s in IN_PROGRESS_STATUSES)
    progress_sum = sum(
        (report.by_status.get(s, zero)[1] for s in IN_PROGRESS_STATUSES), Decimal("0")
    )
    average = format_price(report.average) if report.orders_count else "—"
    cancel_rate = cancelled_count / placed * 100

    line = "-" * 33

    def row(label: str, count: int, amount) -> str:
        return f"{label:<13} {count:>6} {_amount(amount):>12}"


    # ---- sales summary ----
    lines = header + ["", "💰 <b>SALES</b>", ""]
    lines.append(f"💵 Total sales: <b>{format_price(report.revenue)}</b>")
    lines.append(
        _comparison(report.revenue, report.prev_revenue, PREVIOUS_LABELS[report.period])
    )
    lines.append("")
    lines.append(f"🧾 Average order: {average}")
    lines.append(f"🚫 Cancel rate: {cancel_rate:.0f}% ({cancelled_count} of {placed} orders)")
    lines.append(f"👥 New customers: {report.new_customers}")
    lines.append("")

    money = [
        f"{'Group':<13} {'Orders':>6} {'Total, UZS':>12}",
        line,
        row("In progress", progress_count, progress_sum),
        row("Delivered", delivered_count, delivered_sum),
        row("Cancelled", cancelled_count, cancelled_sum),
        line,
        row("Valid orders", report.orders_count, report.revenue),
        row("All orders", placed, all_sum),
    ]
    lines.append(_table(money))

    # ---- orders by status ----
    status_rows = [f"{'Status':<13} {'Orders':>6} {'Total, UZS':>12}", line]
    for status, name in STATUS_NAMES.items():
        count, amount = report.by_status.get(status, zero)
        if count:
            status_rows.append(row(name, count, amount))

    receive_rows = [
        f"{'Receive':<13} {'Orders':>6}",
        "-" * 20,
        f"{'Delivery':<13} {report.delivery_split.get('delivery', 0):>6}",
        f"{'Pickup':<13} {report.delivery_split.get('pickup', 0):>6}",
    ]
    lines += ["", "📦 <b>ORDERS BY STATUS</b>", _table(status_rows), _table(receive_rows)]

    # ---- top products ----
    if report.top_products:
        product_rows = [f"{'Product':<16} {'Pcs':>4} {'Total, UZS':>12}", "-" * 34]
        for i, (name, qty, revenue) in enumerate(report.top_products, start=1):
            label = f"{i}. {_cut(name, 13)}"
            product_rows.append(f"{label:<16} {qty:>4} {_amount(revenue):>12}")
        lines += ["", "🏆 <b>TOP PRODUCTS</b> (by units sold)", _table(product_rows)]

    # ---- by day (7 days report) ----
    if report.daily:
        max_total = max(total for _, _, total in report.daily)
        day_rows = [f"{'Day':<9} {'Orders':>6} {'Total, UZS':>12} Chart", "-" * 36]
        for day, count, total in report.daily:
            bar = "█" * max(1, round(6 * total / max_total)) if count else ""
            day_rows.append(
                f"{day.strftime('%a %d.%m'):<9} {count:>6} {_amount(total):>12} {bar}"
            )
        lines += ["", "📅 <b>BY DAY</b>", _table(day_rows)]

    lines += [
        "",
        "<i>ℹ️ Total sales = all orders except cancelled (includes orders still in "
        "progress). Receive, top products and daily figures also exclude cancelled "
        "orders.</i>",
    ]
    return "\n".join(lines)



REASON_CODES = {
    "receipt": "REC",
    "sale": "SAL",
    "cancel_return": "CAN",
    "adjustment": "ADJ",
}


def format_low_stock(products, threshold: int) -> str:
    if not products:
        return (
            "✅ <b>Low stock</b>\n"
            f"No active products at or below {threshold} pcs."
        )
    rows = [f"{'Product':<22} {'Left':>5}", "-" * 28]
    for product in products:
        rows.append(f"{_cut(product.name, 22):<22} {product.stock:>5}")
    return f"⚠️ <b>Low stock</b> (at or below {threshold} pcs)\n" + _table(rows)


def format_movements(rows) -> str:
    if not rows:
        return (
            "📜 <b>Movement history</b>\n"
            "No movements yet. Changes are recorded from now on."
        )
    tz = ZoneInfo(settings.timezone)
    table = [
        f"{'Date':<11} {'Product':<10} {'Type':<4} {'Chg':>5} {'Left':>4}",
        "-" * 38,
    ]
    for movement, product_name, _user_name in rows:
        when = movement.created_at.astimezone(tz).strftime("%d.%m %H:%M")
        table.append(
            f"{when:<11} {_cut(product_name, 10):<10} "
            f"{REASON_CODES.get(movement.reason, '?'):<4} "
            f"{movement.delta:>+5d} {movement.stock_after:>4}"
        )
    legend = "REC receipt · SAL sale · CAN cancelled order · ADJ manual change"
    return "📜 <b>Movement history</b> (latest)\n" + _table(table) + f"\n<i>{legend}</i>"