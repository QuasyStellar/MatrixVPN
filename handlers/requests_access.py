from aiogram import types
from aiogram.types import FSInputFile
from aiogram.fsm.context import FSMContext
from loader import bot, dp
from utils.db_utils import add_user
from config import ADMIN_ID


@dp.callback_query(lambda call: call.data == "request_access")
async def request_access_handler(call: types.CallbackQuery, state: FSMContext) -> None:
    """Обработчик запроса доступа к VPN от пользователя."""
    user_id = call.from_user.id
    username = call.from_user.username

    # Получаем данные состояния, чтобы удалить предыдущее сообщение бота, если оно есть
    state_data = await state.get_data()
    previous_bot_message_id = state_data.get('previous_bot_message')
    
    # Удаляем предыдущее сообщение бота, если оно существует
    if previous_bot_message_id:
        try:
            await bot.delete_message(user_id, previous_bot_message_id)
        except Exception as e:
            print(f"Ошибка при удалении сообщения: {e}")

    # Удаляем сообщение, с которым взаимодействовал пользователь
    await bot.delete_message(user_id, call.message.message_id)

    # Добавляем пользователя в базу данных
    await add_user(user_id, username)

    # Создаем разметку для кнопок "Принять" и "Отклонить" для администратора
    admin_markup = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="Принять", callback_data=f"approve_access:{user_id}:{username}"),
            types.InlineKeyboardButton(text="Отклонить", callback_data=f"deny_access:{user_id}:{username}")
        ]
    ])
    
    # Уведомляем администратора о запросе доступа
    await bot.send_message(ADMIN_ID, 
                           f"Пользователь @{username} запрашивает доступ к VPN.\nID: {user_id}", 
                           reply_markup=admin_markup)

    # Создаем разметку для кнопки "Подробнее о VPN" для пользователя
    more = types.InlineKeyboardButton(text="Подробнее о VPN", callback_data="more")
    user_markup = types.InlineKeyboardMarkup(inline_keyboard=[[more]])
    
    # Отправляем пользователю анимацию и уведомление о статусе запроса
    await bot.send_animation(
        chat_id=user_id,
        animation=FSInputFile("assets/enter.gif"),
        caption="Ваш запрос на доступ был отправлен 📨\n\n Ожидайте ответа.",
        reply_markup=user_markup
    )
