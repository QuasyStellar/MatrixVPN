import aiosqlite
from datetime import datetime
import pytz
from aiogram import types
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile
from aiogram.filters.command import Command
import logging
from loader import bot, dp
from config import ADMIN_ID, DATABASE_PATH
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
            types.InlineKeyboardButton(
                text="Обновить конфигурацию", callback_data="renew"
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
        user_id, username = map(int, call.data.split(":")[1:3])
        await update_request_status(user_id, "denied")
        button = types.InlineKeyboardButton(
            text="Запросить доступ снова",
            callback_data=f"request_access:{user_id}:{username}",
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


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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


@dp.callback_query(lambda call: call.data == "renew")
async def renew_configs_callback(call: types.CallbackQuery):
    """Обработчик для обновления конфигураций."""
    if call.from_user.id == ADMIN_ID:
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
                    days = int(remaining_time.days + 1)

                    # Получаем правильное склонение для дня
                    day_word = get_day_word(days)

                    # Команды для удаления и добавления новых конфигураций
                    delete_command = f"/root/delete-client.sh ov n{user_id} && /root/delete-client.sh wg n{user_id}"
                    add_command = f"/root/add-client.sh ov n{user_id} {days} && /root/add-client.sh wg n{user_id} {days}"

                    # Выполнение команд
                    await execute_command(delete_command, user_id, "удаления")
                    await execute_command(add_command, user_id, "добавления", days)
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

                except Exception as e:
                    # Логируем ошибку и продолжаем с другими пользователями
                    logger.error(
                        f"Ошибка обновления конфигураций для пользователя {user_id}: {e}"
                    )
                    await bot.send_message(
                        ADMIN_ID,
                        f"⚠️ Ошибка при обновлении конфигураций для пользователя {user_id} (@{username}): {e}",
                    )

            # Уведомление для администратора
            await bot.send_message(
                ADMIN_ID,
                "✅ Конфигурации всех пользователей успешно обновлены.\n\n"
                "Пользователи были уведомлены о необходимости заменить старые конфигурации.",
            )

        except Exception as e:
            # Логируем ошибку, если не удалось получить или обработать данные пользователей
            logger.error(
                f"Ошибка при обновлении конфигураций для всех пользователей: {e}"
            )
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
