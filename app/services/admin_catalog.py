from decimal import Decimal, InvalidOperation

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.category import Category
from app.database.models.product import Product
from app.repositories.category import CategoryRepository
from app.repositories.product import ProductRepository


class CatalogError(Exception):
    pass


def parse_price(text: str) -> Decimal:
    cleaned = text.strip().replace("$", "").replace(" ", "").replace(",", "")
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        raise CatalogError("Please send the price as a number, e.g. 499 or 499.99.")
    if not value.is_finite() or value <= 0 or value >= Decimal("10000000"):
        raise CatalogError("Price must be greater than $0 and less than $10,000,000.")
    return value.quantize(Decimal("0.01"))


def parse_stock(text: str) -> int:
    cleaned = text.strip()
    if not (cleaned.isascii() and cleaned.isdigit()):
        raise CatalogError("Please send a whole number, e.g. 10.")
    value = int(cleaned)
    if value > 1_000_000:
        raise CatalogError("That number is too large.")
    return value


class AdminCatalogService:
    def __init__(self, session: AsyncSession):
        self.categories = CategoryRepository(session)
        self.products = ProductRepository(session)

    async def list_categories(self) -> list[Category]:
        return await self.categories.get_all()

    async def get_category(self, category_id: int) -> Category | None:
        return await self.categories.get_by_id(category_id)

    async def create_category(self, name: str) -> Category:
        name = name.strip()
        if not 2 <= len(name) <= 100:
            raise CatalogError("Category name must be 2-100 characters.")
        if await self.categories.get_by_name(name):
            raise CatalogError("A category with this name already exists.")
        return await self.categories.add(Category(name=name))

    async def toggle_category(self, category_id: int) -> Category | None:
        category = await self.categories.get_by_id(category_id)
        if category is None:
            return None
        category.is_active = not category.is_active
        return category

    async def create_product(
        self,
        category_id: int,
        name: str,
        description: str | None,
        price: Decimal,
        stock: int,
        photo_file_id: str | None,
    ) -> Product:
        category = await self.categories.get_by_id(category_id)
        if category is None:
            raise CatalogError("Category not found.")
        name = name.strip()
        if not 2 <= len(name) <= 200:
            raise CatalogError("Product name must be 2-200 characters.")
        if price <= 0 or stock < 0:
            raise CatalogError("Invalid price or stock.")

        product = Product(
            category_id=category_id,
            name=name,
            description=description,
            price=price,
            stock=stock,
            photo_file_id=photo_file_id,
        )
        return await self.products.add(product)


    async def list_products(self, category_id: int) -> list[Product]:
        return await self.products.get_all_by_category(category_id)

    async def get_product_card(
        self, product_id: int
    ) -> tuple[Product, Category] | None:
        product = await self.products.get_by_id(product_id)
        if product is None:
            return None
        category = await self.categories.get_by_id(product.category_id)
        return product, category

    async def update_product_field(
        self, product_id: int, field: str, raw: str
    ) -> Product:
        product = await self.products.get_by_id(product_id)
        if product is None:
            raise CatalogError("Product not found.")

        if field == "name":
            name = raw.strip()
            if not 2 <= len(name) <= 200:
                raise CatalogError("The name must be 2-200 characters.")
            product.name = name
        elif field == "description":
            text = raw.strip()
            if text == "-":
                product.description = None
            elif len(text) > 500:
                raise CatalogError("The description is too long (max 500 characters).")
            else:
                product.description = text
        elif field == "price":
            product.price = parse_price(raw)
        elif field == "stock":
            product.stock = parse_stock(raw)
        else:
            raise CatalogError("Unknown field.")
        return product

    async def set_product_photo(self, product_id: int, file_id: str) -> Product:
        product = await self.products.get_by_id(product_id)
        if product is None:
            raise CatalogError("Product not found.")
        product.photo_file_id = file_id
        return product

    async def toggle_product(self, product_id: int) -> Product | None:
        product = await self.products.get_by_id(product_id)
        if product is None:
            return None
        product.is_active = not product.is_active
        return product    