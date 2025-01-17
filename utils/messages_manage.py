from aiogram.fsm.context import FSMContext
import aiosqlite
import handlers
from loader import bot
from config import DATABASE_PATH


async def non_authorized(call_id: int, mess_id: int) -> None:
    """Удаляет сообщение и показывает главное меню для неавторизованных пользователей."""
    await bot.delete_message(call_id, mess_id)
    await handlers.start_handler(call_id)


async def delete_previous_message(user_id: int, previous_bot_message_id: int) -> None:
    """Удаляет предыдущее сообщение бота, если оно существует."""
    if previous_bot_message_id:
        try:
            await bot.delete_message(user_id, previous_bot_message_id)
        except Exception as e:
            print(f"Ошибка при удалении сообщения: {e}")


async def send_message_with_cleanup(
    user_id: int, message_text: str, state: FSMContext, markup: any = None
) -> object:
    """
    Отправляет сообщение пользователю, очищая предыдущее сообщение,
    и сохраняет идентификатор нового сообщения в состоянии.
    """
    state_data = await state.get_data()
    previous_bot_message_id = state_data.get("previous_bot_message")

    # Удаляем предыдущее сообщение, если оно есть
    await delete_previous_message(user_id, previous_bot_message_id)

    # Отправляем новое сообщение
    bot_message = await bot.send_message(
        user_id, message_text, reply_markup=markup, parse_mode="HTML"
    )

    # Сохраняем идентификатор нового сообщения в состоянии
    await state.update_data(previous_bot_message=bot_message.message_id)

    return bot_message


async def broadcast_message(text: str) -> None:
    """Рассылка сообщения всем пользователям."""
    try:
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute("SELECT id FROM users") as cursor:
                users = await cursor.fetchall()

        for user in users:
            try:
                await bot.send_message(user[0], text=text, parse_mode="HTML")
            except Exception as e:
                print(f"Не удалось отправить сообщение пользователю {user[0]}: {e}")
    except Exception as e:
        print(f"Ошибка при рассылке сообщений: {e}")
