from app.locales import de, en, uz

LANGUAGES = {"en": "English", "uz": "O'zbekcha", "de": "Deutsch"}
DEFAULT_LANGUAGE = "en"

_CATALOGS = {"en": en.MESSAGES, "uz": uz.MESSAGES, "de": de.MESSAGES}


def t(lang: str, key: str, **params) -> str:
    """Translate a key. Falls back to English, then to the key itself."""
    text = (
        _CATALOGS.get(lang, {}).get(key)
        or _CATALOGS[DEFAULT_LANGUAGE].get(key)
        or key
    )
    return text.format(**params) if params else text


def all_texts(key: str) -> set[str]:
    """The text of a key in every language (to match reply-keyboard buttons)."""
    return {catalog[key] for catalog in _CATALOGS.values() if key in catalog}


def detect_language(telegram_code: str | None) -> str:
    if telegram_code and telegram_code[:2].lower() in LANGUAGES:
        return telegram_code[:2].lower()
    return DEFAULT_LANGUAGE