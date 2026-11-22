from app.i18n import t


class AppError(Exception):
    """An error with a translation key.

    If the key is not in the translation catalog, it is used as plain text,
    so old `raise SomeError("plain text")` lines keep working.
    """

    def __init__(self, key: str, **params):
        self.key = key
        self.params = params
        super().__init__(self.text("en"))

    def text(self, lang: str = "en") -> str:
        # a parameter can itself be an error (e.g. the reason a promo code was rejected)
        params = {
            name: value.text(lang) if isinstance(value, AppError) else value
            for name, value in self.params.items()
        }
        return t(lang, self.key, **params)