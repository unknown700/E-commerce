from aiogram.fsm.state import State, StatesGroup


class EnterPromo(StatesGroup):
    code = State()


class AddPromo(StatesGroup):
    code = State()
    kind = State()
    value = State()
    min_order = State()
    max_uses = State()
    days = State()
    confirm = State()