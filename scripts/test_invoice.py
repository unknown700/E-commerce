import asyncio
import sys

from aiogram import Bot
from aiogram.types import LabeledPrice

from app.config import settings


async def main() -> None:
    currency = sys.argv[1] if len(sys.argv) > 1 else settings.currency
    bot = Bot(token=settings.bot_token)
    try:
        await bot.send_invoice(
            chat_id=settings.admin_id_list[0],
            title="Test invoice",
            description="Checking the payment provider",
            payload="pay:0",
            provider_token=settings.payment_provider_token,
            currency=currency,
            prices=[LabeledPrice(label="Test item", amount=500)],
        )
        print(f"OK: invoice sent ({currency})")
    except Exception as error:
        print(f"ERROR ({currency}): {type(error).__name__}: {error}")
    finally:
        await bot.session.close()


asyncio.run(main())