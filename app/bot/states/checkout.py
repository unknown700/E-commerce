from aiogram.fsm.state import State, StatesGroup


class Checkout(StatesGroup):
    delivery_type = State()
    location = State()
    phone = State()
    confirm = State()