from aiogram.fsm.state import State, StatesGroup

# Класс для хранения состояний пользователей в FSM (Finite State Machine)


class Form(StatesGroup):
    """Класс состояний для обработки пользовательских взаимодействий в боте."""

    waiting_for_site_names = State()
    waiting_for_promo_code = State()
    waiting_for_promo_code_data = State()
    waiting_for_promo_code_to_deactivate = State()
    waiting_for_promo_code_to_delete = State()

    # Состояние, когда бот ожидает сообщение для рассылки
    waiting_for_broadcast_message = State()

    # Состояние, когда бот ожидает идентификатор пользователя
    waiting_for_user_id = State()

    # Состояние, когда бот ожидает количество дней
    waiting_for_n_days = State()
