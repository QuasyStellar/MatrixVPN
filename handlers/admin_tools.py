import aiosqlite
from datetime import datetime, timedelta
import pytz
from aiogram import types
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile
from aiogram.filters.command import Command
from loader import bot, dp
from config import ADMIN_ID, DATABASE_PATH, DELETE_CLIENT_SCRIPT, ADD_CLIENT_SCRIPT
from utils.db_utils import (
    grant_access_and_create_config,
    update_request_status,
    execute_command,
    delete_user,
    add_user,
    get_users_list,
)
from handlers.start_handler import start_handler
from utils.messages_manage import broadcast_message
from utils.Forms import Form
import logging

logger = logging.getLogger(__name__)


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
        except TelegramAPIError:
            logger.error("Ошибка при удалении сообщения:", exc_info=True)

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
        async with aiosqlite.connect(DATABASE_PATH) as db:
            async with db.execute(
                "SELECT * FROM users WHERE status = 'pending'"
            ) as cursor:
                requests = await cursor.fetchall()
        if requests:
            for req in requests:
                markup = types.InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            types.InlineKeyboardButton(
                                text="Принять",
                                callback_data=f"approve_access:{req[0]}:{req[1]}",
                            ),
                            types.InlineKeyboardButton(
                                text="Отклонить",
                                callback_data=f"deny_access:{req[0]}:{req[1]}",
                            ),
                        ]
                    ]
                )
                await bot.send_message(
                    ADMIN_ID, f"Запрос от @{req[1]} (ID: {req[0]})", reply_markup=markup
                )
        else:
            await bot.send_message(ADMIN_ID, "Нет новых запросов.")


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
            # Подключение к базе данных
            async with aiosqlite.connect(DATABASE_PATH) as db:
                async with db.execute(
                    "SELECT id, username, access_end_date FROM users WHERE status = 'accepted'"
                ) as cursor:
                    users_data = await cursor.fetchall()

            # Обработка данных пользователей
            for user in users_data:
                user_id, username, access_end_date = user
                try:
                    access_end_date = datetime.fromisoformat(
                        access_end_date
                    ).astimezone(pytz.UTC)
                    remaining_time = access_end_date - datetime.now(pytz.UTC)
                    days = int(remaining_time.days)

                    # Получаем правильное склонение для дня
                    day_word = get_day_word(days)

                    # Команды для удаления и добавления новых конфигураций
                    await execute_command([DELETE_CLIENT_SCRIPT, "ov", f"n{user_id}"], user_id, "удаления OpenVPN")
                    await execute_command([DELETE_CLIENT_SCRIPT, "wg", f"n{user_id}"], user_id, "удаления WireGuard")
                    await execute_command([ADD_CLIENT_SCRIPT, "ov", f"n{user_id}", str(days)], user_id, "добавления OpenVPN")
                    await execute_command([ADD_CLIENT_SCRIPT, "wg", f"n{user_id}", str(days)], user_id, "добавления WireGuard")
                    markup = types.InlineKeyboardMarkup(
                        inline_keyboard=[
                            [
                                types.InlineKeyboardButton(
                                    text="🏠 В Главное Меню", callback_data="main_menu"
                                )
                            ],
                        ]
                    )

                    await bot.send_photo(
                        chat_id=user_id,
                        photo=FSInputFile("assets/warning.png"),
                        caption=f"🚨 <b>Внимание! Произошло обновление конфигурации!</b>\n\n"
                        "<b>Ваши конфигурационные файлы были обновлены!</b>\n\n"
                        f"Доступ к <b>MatrixVPN</b> заканчивается через <b>{days} {day_word}</b>.\n\n"
                        "<b>⚠️ ВАЖНО: Пожалуйста, замените предыдущие конфигурационные файлы, чтобы избежать проблем с подключением.</b>",
                        parse_mode="HTML",
                        reply_markup=markup,
                    )

                except (aiosqlite.Error, TelegramAPIError, asyncio.subprocess.SubprocessError, OSError):
                    logger.error(f"Ошибка при обновлении конфигураций для пользователя {user_id} (@{username}):", exc_info=True)

            # Уведомление для администратора
            await bot.send_message(
                ADMIN_ID,
                "✅ Конфигурации всех пользователей успешно обновлены.\n\n" 
                "Пользователи были уведомлены о необходимости заменить старые конфигурации.",
            )

        except aiosqlite.Error:
            logger.error("Произошла ошибка при обновлении конфигураций для всех пользователей:", exc_info=True)


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
    """Обработчик для команды renew."""
    if message.from_user.id == ADMIN_ID:
        command_parts = message.text.split()
        if len(command_parts) != 3:
            await message.reply(
                "Неверный формат команды. Пример: /renew <user_id> <+days>"
            )
            return

        user_id = int(command_parts[1])  # user_id
        days_str = command_parts[2]  # количество дней или +дней

        try:
            # Определяем количество дней для добавления
            days_to_add = int(days_str.lstrip("+"))  # убираем "+" если оно есть

            # Подключаемся к базе данных, чтобы получить текущую дату окончания
            async with aiosqlite.connect(DATABASE_PATH) as db:
                async with db.execute(
                    "SELECT access_end_date FROM users WHERE id = ?", (user_id,)
                ) as cursor:
                    row = await cursor.fetchone()

                if not row:
                    await message.reply(
                        f"Пользователь с ID {user_id} не найден в базе данных."
                    )
                    return

                current_end_date = datetime.fromisoformat(row[0]).astimezone(pytz.UTC)

                # Рассчитываем новую дату окончания
                if days_str.startswith("+"):
                    new_end_date = current_end_date + timedelta(days=days_to_add)
                else:
                    new_end_date = datetime.now(pytz.UTC) + timedelta(days=days_to_add)

                # Вычисляем количество оставшихся дней
                access_duration = (new_end_date - datetime.now(pytz.UTC)).days

                # Обновляем запись в базе данных с новой датой окончания
                async with db.execute(
                    """UPDATE users SET status = ?, access_granted_date = ?, access_duration = ?, access_end_date = ? WHERE id = ?""",
                    (
                        "accepted",
                        datetime.now(pytz.UTC).strftime("%Y-%m-%d %H:%M:%S"),
                        access_duration,
                        new_end_date.isoformat(),
                        user_id,
                    ),
                ) as cursor:
                    await db.commit()

                # Пересоздаем конфигурации
                await execute_command([DELETE_CLIENT_SCRIPT, "ov", f"n{user_id}"], user_id, "удаления OpenVPN")
                await execute_command([DELETE_CLIENT_SCRIPT, "wg", f"n{user_id}"], user_id, "удаления WireGuard")
                await execute_command([ADD_CLIENT_SCRIPT, "ov", f"n{user_id}", str(access_duration+1)], user_id, "добавления OpenVPN")
                await execute_command([ADD_CLIENT_SCRIPT, "wg", f"n{user_id}", str(access_duration+1)], user_id, "добавления WireGuard")

                # Уведомляем пользователя
                markup = types.InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            types.InlineKeyboardButton(
                                text="🏠 В Главное Меню", callback_data="main_menu"
                            )
                        ],
                    ]
                )
                await bot.send_photo(
                    chat_id=user_id,
                    photo=FSInputFile("assets/warning.png"),
                    caption=f"🚨 <b>Внимание! Ваша подписка была продлена!</b>\n\n"
                    f"<b>Конфигурационные файлы были обновлены!</b>\n\n"
                    f"Доступ к <b>MatrixVPN</b> заканчивается через <b>{access_duration} дней</b>.\n\n"
                    "<b>⚠️ ВАЖНО: Пожалуйста, замените предыдущие конфигурационные файлы, чтобы избежать проблем с подключением.</b>",
                    parse_mode="HTML",
                    reply_markup=markup,
                )

            # Ответ админу
            await message.reply(
                f"Команда /renew выполнена для пользователя {user_id}. Новый срок окончания через {access_duration} дней."
            )

        except (ValueError, aiosqlite.Error, TelegramAPIError, asyncio.subprocess.SubprocessError, OSError):
            logger.error(f"Произошла ошибка при обработке команды для пользователя {message.from_user.id}:", exc_info=True)
            await message.reply("Произошла ошибка при обработке команды.")


@dp.message(Command("update"))
async def update_access(message: types.Message):
    """Обработчик для команды update."""
    if message.from_user.id == ADMIN_ID:
        command_parts = message.text.split()
        if len(command_parts) != 3:
            await message.reply(
                "Неверный формат команды. Пример: /update <user_id> <days>"
            )
            return

        user_id = int(command_parts[1])  # user_id
        days_to_add = int(command_parts[2])  # количество дней для добавления

        try:
            # Подключаемся к базе данных, чтобы получить текущую дату окончания
            async with aiosqlite.connect(DATABASE_PATH) as db:
                async with db.execute(
                    "SELECT access_end_date FROM users WHERE id = ?", (user_id,)
                ) as cursor:
                    row = await cursor.fetchone()

                if not row:
                    await message.reply(
                        f"Пользователь с ID {user_id} не найден в базе данных."
                    )
                    return

                current_end_date = datetime.fromisoformat(row[0]).astimezone(pytz.UTC)

                # Рассчитываем новую дату окончания
                new_end_date = current_end_date + timedelta(days=days_to_add)

                # Вычисляем количество оставшихся дней
                access_duration = (new_end_date - datetime.now(pytz.UTC)).days

                # Обновляем запись в базе данных с новой датой окончания
                async with db.execute(
                    """UPDATE users SET access_duration = ?, access_end_date = ? WHERE id = ?""",
                    (access_duration, new_end_date.isoformat(), user_id),
                ) as cursor:
                    await db.commit()

                    # Уведомляем пользователя
                markup = types.InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            types.InlineKeyboardButton(
                                text="🏠 В Главное Меню", callback_data="main_menu"
                            )
                        ],
                    ]
                )
                await bot.send_photo(
                    chat_id=user_id,
                    photo=FSInputFile("assets/warning.png"),
                    caption=f"🚨 <b>Внимание! Срок вашей подписки был продлен!</b>\n\nДоступ к <b>MatrixVPN</b> заканчивается через <b>{access_duration} дней</b>.\n\n",
                    parse_mode="HTML",
                    reply_markup=markup,
                )

            # Ответ админу
            await message.reply(
                f"Команда /update выполнена для пользователя {user_id}. Новый срок окончания через {access_duration} дней."
            )

        except (ValueError, aiosqlite.Error, TelegramAPIError):
            logger.error(f"Произошла ошибка при обработке команды для пользователя {message.from_user.id}:", exc_info=True)
            await message.reply("Произошла ошибка при обработке команды.")
