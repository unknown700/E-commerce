from aiogram.fsm.state import State, StatesGroup


class AddCategory(StatesGroup):
    name = State()


class AddProduct(StatesGroup):
    category = State()
    name = State()
    description = State()
    price = State()
    stock = State()
    photo = State()
    confirm = State()