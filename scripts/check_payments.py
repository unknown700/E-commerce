import inspect
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def check(ok: bool, text: str) -> None:
    print(("✅ " if ok else "❌ ") + text)


def main() -> None:
    # 1) .env: duplicate keys (the last one wins)
    keys: dict[str, int] = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            key = line.partition("=")[0].strip()
            keys[key] = keys.get(key, 0) + 1
    duplicates = [key for key, count in keys.items() if count > 1]
    check(not duplicates, f".env has no duplicate keys {duplicates or ''}")

    # 2) settings as the bot sees them (the token itself is not printed)
    from app.config import settings

    token = getattr(settings, "payment_provider_token", None)
    check(bool(token), f"payment token is set (length: {len(token or '')})")
    check(token == (token or "").strip(), "token has no spaces around it")
    print(
        "   payment_mock =", getattr(settings, "payment_mock", "MISSING"),
        "| mock_payments_enabled =", getattr(settings, "mock_payments_enabled", "MISSING"),
        "| card_payments_enabled =", getattr(settings, "card_payments_enabled", "MISSING"),
        "| currency =", getattr(settings, "currency", "MISSING"),
    )

    # 3) the code of the payment steps
    try:
        from app.services.order import OrderService

        params = inspect.signature(OrderService.create_order).parameters
        check(
            "payment_method" in params and "expected_total" in params,
            "services/order.py: create_order accepts payment_method and expected_total",
        )
    except Exception as error:
        check(False, f"services/order.py cannot be imported: {error}")

    try:
        from app.bot.handlers import payments

        check(hasattr(payments, "finalize_payment"), "handlers/payments.py: latest version")
        check(hasattr(payments, "mock_payment"), "handlers/payments.py: sandbox handler exists")
    except Exception as error:
        check(False, f"handlers/payments.py cannot be imported: {error}")

    try:
        from app.bot.keyboards.checkout import MockPayCb, confirm_kb, mock_pay_kb  # noqa: F401

        check("online" in inspect.signature(confirm_kb).parameters, "keyboards/checkout.py: confirm_kb(online)")
    except Exception as error:
        check(False, f"keyboards/checkout.py is outdated: {error}")

    main_text = (ROOT / "app" / "main.py").read_text(encoding="utf-8")
    check("payments.router" in main_text, "main.py: payments.router is included")
    check("admin_payments.router" in main_text, "main.py: admin_payments.router is included")
    checkout_text = (ROOT / "app" / "bot" / "handlers" / "checkout.py").read_text(encoding="utf-8")
    check("confirm_kb(online=" in checkout_text, "handlers/checkout.py: passes online to confirm_kb")


main()