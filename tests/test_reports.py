from decimal import Decimal

from app.services.order import OrderService
from app.services.report import ReportService
from tests.factories import fill_cart, make_product, make_user, place_order


async def test_report_excludes_cancelled_orders_and_groups_by_status(session):
    user = await make_user(session)
    product = await make_product(session, price="10", stock=100)
    service = OrderService(session)

    await fill_cart(session, user, (product, 2))
    await place_order(session, user)  # $20
    await fill_cart(session, user, (product, 1))
    cancelled, _ = await place_order(session, user)  # $10, cancelled below
    await service.change_status(cancelled.id, "cancelled")
    await fill_cart(session, user, (product, 3))
    await place_order(session, user)  # $30

    report = await ReportService(session).build("week")

    assert report.orders_count == 2
    assert report.revenue == Decimal("50")
    assert report.average == Decimal("25")
    assert report.by_status["new"] == (2, Decimal("50"))
    assert report.by_status["cancelled"] == (1, Decimal("10"))
    assert report.top_products == [(product.name, 5, Decimal("50"))]
    assert sum(total for _, _, total in report.daily) == Decimal("50")
    assert report.new_customers == 1


async def test_report_of_an_empty_period(session):
    report = await ReportService(session).build("today")
    assert report.orders_count == 0
    assert report.revenue == Decimal("0")
    assert report.top_products == []