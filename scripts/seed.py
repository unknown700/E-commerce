
import asyncio
from decimal import Decimal

from sqlalchemy import func, select

from app.database.models import Category, Product
from app.database.session import async_session


async def seed():
    async with async_session() as session:
        count = await session.scalar(
            select(func.count()).select_from(Category)
        )

        if count:
            print("The database is already populated. Skipping seeding.")
            return

        phones = Category(name="Phones")
        laptops = Category(name="Laptops")
        accessories = Category(name="Accessories")

        session.add_all([phones, laptops, accessories])
        await session.flush()

        session.add_all(
            [
                Product(
                    category_id=phones.id,
                    name="Smartphone X1",
                    description="6.5-inch display, 128 GB storage",
                    price=Decimal("3200000"),
                    stock=12,
                ),
                Product(
                    category_id=phones.id,
                    name="Smartphone X2 Pro",
                    description="6.7-inch display, 256 GB storage",
                    price=Decimal("5400000"),
                    stock=5,
                ),
                Product(
                    category_id=laptops.id,
                    name="Laptop Air 14",
                    description="14-inch, 8 GB RAM, 256 GB SSD",
                    price=Decimal("7800000"),
                    stock=3,
                ),
                Product(
                    category_id=accessories.id,
                    name="Wireless Earbuds",
                    description="Bluetooth 5.3, 20-hour battery life",
                    price=Decimal("450000"),
                    stock=30,
                ),
                Product(
                    category_id=accessories.id,
                    name="65W Fast Charger",
                    description="USB-C, dual ports",
                    price=Decimal("190000"),
                    stock=0,
                ),
            ]
        )

        await session.commit()
        print("Test data has been added successfully.")


if __name__ == "__main__":
    asyncio.run(seed())
