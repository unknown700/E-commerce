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


class EditProduct(StatesGroup):
    value = State()



class ReceiveStock(StatesGroup):
    quantity = State()



class AddCourier(StatesGroup):
    identifier = State()    