from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    admin_ids: str = ""
    timezone: str = "Asia/Tashkent"
    daily_report_hour: int = 21
    daily_report_minute: int = 0
    low_stock_threshold: int = 5

    payment_provider_token: str = ""
    currency: str = "USD"
    payment_mock: bool = False
    redis_url: str = ""
    log_level: str = "INFO"
    environment: str = "development"  # set to "production" on the server

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def admin_id_list(self) -> list[int]:
        return [int(x) for x in self.admin_ids.split(",") if x.strip()]

    @property
    def mock_payments_enabled(self) -> bool:
        return self.payment_mock and not self.payment_provider_token

    @property
    def card_payments_enabled(self) -> bool:
        return bool(self.payment_provider_token) or self.payment_mock


settings = Settings()