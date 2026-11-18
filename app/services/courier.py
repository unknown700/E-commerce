from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.user import User
from app.repositories.order import OrderRepository
from app.repositories.user import UserRepository
from app.services.order import COURIER_STATUSES


class CourierError(Exception):
    pass


class CourierService:
    def __init__(self, session: AsyncSession):
        self.users = UserRepository(session)
        self.orders = OrderRepository(session)

    async def list_couriers(self) -> list[User]:
        return await self.users.get_by_role("courier")

    async def add_courier(self, identifier: str) -> User:
        raw = identifier.strip()
        if raw.startswith("@"):
            user = await self.users.get_by_username(raw[1:])
        elif raw.isascii() and raw.isdigit():
            user = await self.users.get_by_telegram_id(int(raw))
        else:
            user = await self.users.get_by_username(raw)

        if user is None:
            raise CourierError(
                "User not found. Ask them to open the bot and press /start first."
            )
        if user.role == "courier":
            raise CourierError("This user is already a courier.")
        user.role = "courier"
        return user

    async def remove_courier(self, user_id: int) -> User:
        user = await self.users.get_by_id(user_id)
        if user is None or user.role != "courier":
            raise CourierError("Courier not found.")
        active = await self.orders.count_for_courier(user.id, COURIER_STATUSES)
        if active:
            raise CourierError(
                "This courier still has active deliveries. Reassign them first."
            )
        user.role = "customer"
        return user