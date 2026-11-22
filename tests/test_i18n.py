import re
from decimal import Decimal
from pathlib import Path

from app.bot.formatting import format_price
from app.errors import AppError
from app.i18n import all_texts, detect_language, t
from app.locales import de, en, uz

PLACEHOLDER = re.compile(r"{(\w+)}")
APP_DIR = Path(__file__).resolve().parent.parent / "app"


def test_every_language_has_every_key():
    for module in (uz, de):
        assert set(module.MESSAGES) == set(en.MESSAGES)


def test_placeholders_match_english():
    for module in (uz, de):
        for key, text in module.MESSAGES.items():
            assert set(PLACEHOLDER.findall(text)) == set(
                PLACEHOLDER.findall(en.MESSAGES[key])
            ), key


def test_every_key_used_in_code_exists():
    """Catches typos such as t(lang, "cart.emtpy") before a user sees them."""
    patterns = [
        re.compile(r'\bt\(\s*[^,()]+,\s*"([a-z_]+(?:\.[a-z_]+)+)"'),
        re.compile(r'all_texts\(\s*"([a-z_]+(?:\.[a-z_]+)+)"'),
        re.compile(r'Error\(\s*"((?:err|promo|pay)\.[a-z_.]+)"'),
    ]
    used: dict[str, str] = {}
    for path in APP_DIR.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        for pattern in patterns:
            for key in pattern.findall(source):
                used[key] = path.name
    missing = {key: file for key, file in used.items() if key not in en.MESSAGES}
    assert not missing, f"keys missing from the translations: {missing}"


def test_translate_and_fall_back():
    assert t("uz", "cart.empty") == uz.MESSAGES["cart.empty"]
    assert t("xx", "cart.empty") == en.MESSAGES["cart.empty"]  # unknown language
    assert t("en", "no.such.key") == "no.such.key"  # unknown key
    assert t("en", "catalog.in_stock", count=3) == "In stock: 3"


def test_menu_button_texts_cover_all_languages():
    assert len(all_texts("menu.cart")) == 3


def test_detect_language():
    assert detect_language("uz") == "uz"
    assert detect_language("de-DE") == "de"
    assert detect_language("ru") == "en"
    assert detect_language(None) == "en"


def test_error_reason_is_translated_inside_the_message():
    error = AppError("promo.sorry", reason=AppError("promo.reason.expired"))
    assert "expired" in error.text("en")
    assert "muddati tugagan" in error.text("uz")
    assert "abgelaufen" in error.text("de")


def test_plain_text_errors_still_work():
    error = AppError("Order not found.")
    assert error.text("uz") == "Order not found."
    assert str(error) == "Order not found."


def test_format_price():
    assert format_price(Decimal("1899")) == "$1,899"
    assert format_price(Decimal("49.5")) == "$49.50"