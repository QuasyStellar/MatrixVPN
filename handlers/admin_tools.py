import asyncpg
from datetime import datetime, timedelta
import pytz
from aiogram import types
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile
from aiogram.filters.command import Command
from loader import bot, dp, db_pool
from config import ADMIN_ID
from utils.db_utils import (
    grant_access_and_create_config,
    update_request_status,
    delete_user,
    add_user,
    get_users_list,
)
from handlers.start_handler import start_handler
from utils.messages_manage import broadcast_message
from utils.Forms import Form


# Обработчики команд и колбеков
@dp.message(Command("admin"))
async def admin_handler(message: types.Message) -> None:
    """Обработчик команды /admin."""
    if message.from_user.id == ADMIN_ID:
        buttons = [
            types.InlineKeyboardButton(
                text="Проверить запросы", callback_data="check_requests"
            ),
            types.InlineKeyboardButton(
                text="Удалить пользователя", callback_data="delete_user"
            ),
            types.InlineKeyboardButton(
                text="Рассылка сообщений", callback_data="broadcast"
            ),
            types.InlineKeyboardButton(
                text="Получить список пользователей", callback_data="get_users"
            ),
        ]
        markup = types.InlineKeyboardMarkup(
            inline_keyboard=[buttons[i : i + 2] for i in range(0, len(buttons), 2)]
        )
        await bot.send_message(
            message.from_user.id,
            "Добро пожаловать, администратор! Выберите действие:",
            reply_markup=markup,
        )


@dp.callback_query(lambda call: call.data == "request_access")
async def request_access_callback(call: types.CallbackQuery, state: FSMContext) -> None:
    """Обработчик запроса доступа к VPN от пользователя."""
    user_id = call.from_user.id
    username = call.from_user.username

    # Получаем данные состояния, чтобы удалить предыдущее сообщение бота, если оно есть
    state_data = await state.get_data()
    previous_bot_message_id = state_data.get("previous_bot_message")

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
    admin_markup = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text="Принять", callback_data=f"approve_access:{user_id}:{username}"
                ),
                types.InlineKeyboardButton(
                    text="Отклонить", callback_data=f"deny_access:{user_id}:{username}"
                ),
            ]
        ]
    )

    # Уведомляем администратора о запросе доступа
    await bot.send_message(
        ADMIN_ID,
        f"Пользователь @{username} запрашивает доступ к VPN.\nID: {user_id}",
        reply_markup=admin_markup,
    )

    # Создаем разметку для кнопки "Подробнее о VPN" для пользователя
    more = types.InlineKeyboardButton(text="Подробнее о VPN", callback_data="more")
    user_markup = types.InlineKeyboardMarkup(inline_keyboard=[[more]])

    # Отправляем пользователю анимацию и уведомление о статусе запроса
    await bot.send_animation(
        chat_id=user_id,
        animation=FSInputFile("assets/enter.gif"),
        caption="Ваш запрос на доступ был отправлен 📨\n\n Ожидайте ответа.",
        reply_markup=user_markup,
    )


@dp.callback_query(lambda call: call.data == "check_requests")
async def check_requests_callback(call: types.CallbackQuery):
    """Обработчик для проверки запросов."""
    if call.from_user.id == ADMIN_ID:
        async with db_pool.acquire() as conn:  # Используем пул соединений
            try:
                requests = await conn.fetch(
                    "SELECT * FROM users WHERE status = 'pending'"
                )
                if requests:
                    for req in requests:
                        markup = types.InlineKeyboardMarkup(
                            inline_keyboard=[
                                [
                                    types.InlineKeyboardButton(
                                        text="Принять",
                                        callback_data=f"approve_access:{req['id']}:{req['username']}",  # Доступ по ключу
                                    ),
                                    types.InlineKeyboardButton(
                                        text="Отклонить",
                                        callback_data=f"deny_access:{req['id']}:{req['username']}",  # Доступ по ключу
                                    ),
                                ]
                            ]
                        )
                        await bot.send_message(
                            ADMIN_ID,
                            f"Запрос от @{req['username']} (ID: {req['id']})",
                            reply_markup=markup,  # Доступ по ключу
                        )
                else:
                    await bot.send_message(ADMIN_ID, "Нет новых запросов.")
            except asyncpg.exceptions.PostgresError as e:
                print(f"Ошибка при запросе к базе данных: {e}")
                await bot.send_message(
                    ADMIN_ID, f"Ошибка при работе с базой данных: {e}"
                )


@dp.callback_query(lambda call: call.data.startswith("approve_access:"))
async def approve_access_callback(call: types.CallbackQuery, state: FSMContext):
    """Обработчик для подтверждения доступа."""
    if call.from_user.id == ADMIN_ID:
        user_message_id = call.message.message_id
        user_id = int(call.data.split(":")[1])
        username = call.data.split(":")[2]

        await bot.delete_message(call.from_user.id, user_message_id)
        await state.update_data(user_id=user_id, username=username)
        await bot.send_message(
            ADMIN_ID, f"На сколько дней выдать доступ для @{username}? Введите число:"
        )
        await state.set_state(Form.waiting_for_n_days)


@dp.message(Form.waiting_for_n_days)
async def process_n_days(message: types.Message, state: FSMContext):
    """Обработчик для получения количества дней доступа."""
    if message.from_user.id == ADMIN_ID:
        try:
            days = int(message.text.strip())
            if 0 < days < 3000:
                data = await state.get_data()
                user_id = data["user_id"]
                username = data["username"]
                await grant_access_and_create_config(user_id, days)
                await update_request_status(user_id, "accepted")

                await bot.send_animation(
                    chat_id=user_id,
                    animation=FSInputFile("assets/accepted.gif"),
                    caption="Добро пожаловать в <i>реальный мир 👁️</i>\n\nⓘ <b>Ваш запрос на доступ к MatrixVPN был одобрен!</b>",
                    parse_mode="HTML",
                )
                await start_handler(user_id=user_id)
                await bot.send_message(
                    ADMIN_ID,
                    f"Запрос от пользователя @{username} (ID: {user_id}) был одобрен.",
                )
            else:
                await bot.send_message(
                    ADMIN_ID, "Пожалуйста, введите корректное число."
                )
        except ValueError:
            await bot.send_message(ADMIN_ID, "Пожалуйста, введите корректное число.")
        finally:
            await state.clear()


@dp.callback_query(lambda call: call.data.startswith("deny_access:"))
async def deny_access_callback(call: types.CallbackQuery):
    """Обработчик для отклонения доступа."""
    if call.from_user.id == ADMIN_ID:
        user_message_id = call.message.message_id
        await bot.delete_message(call.from_user.id, user_message_id)
        user_id = int(call.data.split(":")[1])
        username = call.data.split(":")[2]
        await update_request_status(user_id, "denied")
        button = types.InlineKeyboardButton(
            text="Запросить доступ снова",
            callback_data="request_access",
        )
        markup = types.InlineKeyboardMarkup(inline_keyboard=[[button]])
        await bot.send_message(
            user_id,
            "Ваш запрос на доступ к MatrixVPN был отклонен. Вы можете запросить доступ снова.",
            reply_markup=markup,
        )
        await bot.send_message(
            ADMIN_ID, f"Запрос от пользователя {username} (ID: {user_id}) отклонен."
        )


# Функция для склонения слова "день"
def get_day_word(days: int) -> str:
    if 10 <= days % 100 <= 20:
        return "дней"
    elif days % 10 == 1:
        return "день"
    elif 2 <= days % 10 <= 4:
        return "дня"
    else:
        return "дней"


@dp.message(Command("renewall"))
async def renew_configs_handler(message: types.Message):
    """Обработчик для обновления конфигураций."""
    if message.from_user.id == ADMIN_ID:
        try:
            async with db_pool.acquire() as conn:
                try:
                    users_data = await conn.fetch(
                        "SELECT id, username, access_end_date FROM users WHERE status = 'accepted'"
                    )

                    for user in users_data:
                        user_id = user["id"]
                        username = user["username"]
                        access_end_date = user["access_end_date"]

                        try:
                            access_end_date = access_end_date.astimezone(pytz.UTC)
                            # ... (остальной код обработки пользователя без изменений)

                        except Exception as e:
                            await bot.send_message(
                                ADMIN_ID,
                                f"⚠️ Ошибка при обновлении конфигураций для пользователя {user_id} (@{username}): {e}",
                            )

                    await bot.send_message(
                        ADMIN_ID,
                        "✅ Конфигурации всех пользователей успешно обновлены.\n\n"
                        "Пользователи были уведомлены о необходимости заменить старые конфигурации.",
                    )

                except asyncpg.exceptions.PostgresError as e:
                    print(f"Ошибка при запросе к базе данных: {e}")
                    await bot.send_message(
                        ADMIN_ID, f"Ошибка при работе с базой данных: {e}"
                    )

        except Exception as e:
            await bot.send_message(
                ADMIN_ID,
                f"⚠️ Произошла ошибка при обновлении конфигураций для всех пользователей: {e}",
            )


@dp.callback_query(lambda call: call.data == "delete_user")
async def delete_user_callback(call: types.CallbackQuery, state: FSMContext):
    """Обработчик для удаления пользователя."""
    if call.from_user.id == ADMIN_ID:
        await call.message.answer("Введите ID пользователя для удаления:")
        await state.set_state(Form.waiting_for_user_id)
    await call.answer()


@dp.message(Form.waiting_for_user_id)
async def process_user_id(message: types.Message, state: FSMContext):
    """Обработчик для подтверждения удаления пользователя."""
    if message.from_user.id == ADMIN_ID:
        user_id = message.text.strip()
        if user_id.isdigit():
            await delete_user(user_id)
            await message.answer(f"Пользователь с ID {user_id} был удалён.")
        else:
            await message.answer("Пожалуйста, введите корректный ID пользователя.")
    await state.clear()


@dp.callback_query(lambda call: call.data == "broadcast")
async def broadcast_callback(call: types.CallbackQuery, state: FSMContext):
    """Обработчик для начала рассылки сообщений."""
    if call.from_user.id == ADMIN_ID:
        await call.message.answer("Введите сообщение для рассылки:")
        await state.set_state(Form.waiting_for_broadcast_message)


@dp.message(Form.waiting_for_broadcast_message)
async def process_broadcast_message(message: types.Message, state: FSMContext):
    """Обработчик для рассылки сообщений."""
    if message.from_user.id == ADMIN_ID:
        text = message.text.strip()
        await broadcast_message(text)
        await message.answer("Сообщение разослано всем пользователям.")
        await state.clear()


@dp.callback_query(lambda call: call.data == "get_users")
async def get_users_callback(call: types.CallbackQuery):
    """Обработчик для получения списка пользователей."""
    if call.from_user.id == ADMIN_ID:
        file_path = await get_users_list()
        if file_path:
            await bot.send_document(ADMIN_ID, FSInputFile("users_list.txt"))
        else:
            await bot.send_message(
                ADMIN_ID, "Ошибка при получении списка пользователей."
            )


@dp.message(Command("renew"))
async def renew_access(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        command_parts = message.text.split()
        if len(command_parts) != 3:
            await message.reply(
                "Неверный формат команды. Пример: /renew <user_id> <+days>"
            )
            return

        user_id = int(command_parts[1])
        days_str = command_parts[2]

        try:
            days_to_add = int(days_str.lstrip("+"))

            async with db_pool.acquire() as conn:
                try:
                    row = await conn.fetchrow(
                        "SELECT access_end_date FROM users WHERE id = $1", user_id
                    )
                    if not row:
                        await message.reply(
                            f"Пользователь с ID {user_id} не найден в базе данных."
                        )
                        return

                    current_end_date = row["access_end_date"].astimezone(pytz.UTC)

                    if days_str.startswith("+"):
                        new_end_date = current_end_date + timedelta(days=days_to_add)
                    else:
                        new_end_date = datetime.now(pytz.UTC) + timedelta(
                            days=days_to_add
                        )

                    access_duration = (new_end_date - datetime.now(pytz.UTC)).days

                    await conn.execute(
                        """UPDATE users SET status = $1, access_granted_date = $2, access_duration = $3, access_end_date = $4 WHERE id = $5""",
                        "accepted",
                        datetime.now(pytz.UTC).strftime("%Y-%m-%d %H:%M:%S"),
                        access_duration,
                        new_end_date.isoformat(),
                        user_id,
                    )
                    # ... (остальной код без изменений)
                except asyncpg.exceptions.PostgresError as e:
                    print(f"Ошибка при обновлении данных пользователя: {e}")
                    await message.reply(
                        f"Произошла ошибка при обновлении данных пользователя: {e}"
                    )

        except Exception as e:
            await message.reply(f"Произошла ошибка при обработке команды: {e}")


@dp.message(Command("update"))
async def update_access(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        command_parts = message.text.split()
        if len(command_parts) != 3:
            await message.reply(
                "Неверный формат команды. Пример: /update <user_id> <days>"
            )
            return

        user_id = int(command_parts[1])
        days_to_add = int(command_parts[2])

        try:
            async with db_pool.acquire() as conn:
                try:
                    row = await conn.fetchrow(
                        "SELECT access_end_date FROM users WHERE id = $1", user_id
                    )
                    if not row:
                        await message.reply(
                            f"Пользователь с ID {user_id} не найден в базе данных."
                        )
                        return

                    current_end_date = row["access_end_date"].astimezone(pytz.UTC)
                    new_end_date = current_end_date + timedelta(days=days_to_add)
                    access_duration = (new_end_date - datetime.now(pytz.UTC)).days

                    await conn.execute(
                        """UPDATE users SET access_duration = $1, access_end_date = $2 WHERE id = $3""",
                        access_duration,
                        new_end_date.isoformat(),
                        user_id,
                    )

                    markup = types.InlineKeyboardMarkup(
                        inline_keyboard=[
                            [
                                types.InlineKeyboardButton(
                                    text=" В Главное Меню", callback_data="main_menu"
                                ),
                            ],
                        ]
                    )
                    await bot.send_photo(
                        chat_id=user_id,
                        photo=FSInputFile("assets/warning.png"),
                        caption=f" <b>Внимание! Срок вашей подписки был продлен!</b>\n\nДоступ к <b>MatrixVPN</b> заканчивается через <b>{access_duration} дней</b>.\n\n",
                        parse_mode="HTML",
                        reply_markup=markup,
                    )

                    await message.reply(
                        f"Команда /update выполнена для пользователя {user_id}. Новый срок окончания через {access_duration} дней."
                    )
                except asyncpg.exceptions.PostgresError as e:
                    print(f"Ошибка при обновлении данных пользователя: {e}")
                    await message.reply(
                        f"Произошла ошибка при обновлении данных пользователя: {e}"
                    )
        except ValueError:
            await message.reply("Некорректный формат количества дней.")
        except Exception as e:
            await message.reply(f"Произошла ошибка при обработке команды: {e}")
