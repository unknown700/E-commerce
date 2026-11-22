from decimal import Decimal

import pytest

from app.services.admin_catalog import CatalogError, parse_price, parse_stock
from app.services.promo import (
    PromoError,
    parse_days,
    parse_max_uses,
    parse_min_order,
    parse_percent,
)


@pytest.mark.parametrize(
    "text, expected",
    [("499", "499.00"), ("499.99", "499.99"), ("$1,299.50", "1299.50"), (" 5 ", "5.00")],
)
def test_parse_price_accepts_dollars_and_cents(text, expected):
    assert parse_price(text) == Decimal(expected)


@pytest.mark.parametrize("text", ["abc", "-5", "0", "", "NaN", "Infinity", "99999999999"])
def test_parse_price_rejects_bad_input(text):
    with pytest.raises(CatalogError):
        parse_price(text)


@pytest.mark.parametrize("text, expected", [("0", 0), ("10", 10), (" 7 ", 7)])
def test_parse_stock_valid(text, expected):
    assert parse_stock(text) == expected


@pytest.mark.parametrize("text", ["-1", "ten", "1.5", "", "1000001", "²"])
def test_parse_stock_invalid(text):
    with pytest.raises(CatalogError):
        parse_stock(text)


def test_parse_percent():
    assert parse_percent("10") == Decimal(10)
    assert parse_percent("15%") == Decimal(15)
    for bad in ("0", "91", "abc", ""):
        with pytest.raises(PromoError):
            parse_percent(bad)


def test_parse_days_and_limits():
    assert parse_days("-") is None
    assert parse_days("30") == 30
    for bad in ("0", "366", "x"):
        with pytest.raises(PromoError):
            parse_days(bad)
    assert parse_max_uses("-") is None
    assert parse_max_uses("5") == 5
    with pytest.raises(PromoError):
        parse_max_uses("0")
    assert parse_min_order("0") == Decimal("0")
    assert parse_min_order("100") == Decimal("100.00")