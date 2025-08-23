from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.filters.command import Command
from aiogram.exceptions import TelegramAPIError

from datetime import datetime, timedelta
import pytz
import logging

from core.bot import bot
from config.settings import ADMIN_ID
from services.db_operations import (
    grant_access_and_create_config,
    update_request_status,
    delete_user,
    add_user,
    get_users_list,
    get_pending_requests,
    get_accepted_users,
    get_user_by_id,
    update_user_access,
)
from services.messages_manage import broadcast_message
from services.forms import Form
from modules.admin.services import get_day_word, update_user_configs
from modules.admin.filters import IsAdmin
from modules.user_onboarding.services import process_start_command

logger = logging.getLogger(__name__)

admin_router = Router()


@admin_router.message(Command("admin"), IsAdmin())
async def admin_handler(message: types.Message) -> None:
    """Обработчик команды /admin."""
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


@admin_router.callback_query(lambda call: call.data == "request_access")
async def request_access_callback(call: types.CallbackQuery, state: FSMContext) -> None:
    """Обработчик запроса доступа к VPN от пользователя."""
    user_id = call.from_user.id
    username = call.from_user.username

    state_data = await state.get_data()
    previous_bot_message_id = state_data.get("previous_bot_message")

    if previous_bot_message_id:
        try:
            await bot.delete_message(user_id, previous_bot_message_id)
        except TelegramAPIError:
            logger.error("Ошибка при удалении сообщения:", exc_info=True)

    await bot.delete_message(user_id, call.message.message_id)

    await add_user(user_id, username)

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

    await bot.send_message(
        ADMIN_ID,
        f"Пользователь @{username} запрашивает доступ к VPN.\nID: {user_id}",
        reply_markup=admin_markup,
    )

    more = types.InlineKeyboardButton(text="Подробнее о VPN", callback_data="more")
    user_markup = types.InlineKeyboardMarkup(inline_keyboard=[[more]])

    await bot.send_animation(
        chat_id=user_id,
        animation=types.FSInputFile("assets/enter.gif"),
        caption="Ваш запрос на доступ был отправлен 📨\n\n Ожидайте ответа.",
        reply_markup=user_markup,
    )


@admin_router.callback_query(lambda call: call.data == "check_requests", IsAdmin())
async def check_requests_callback(call: types.CallbackQuery):
    """Обработчик для проверки запросов."""
    requests = await get_pending_requests()
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


@admin_router.callback_query(
    lambda call: call.data.startswith("approve_access:"), IsAdmin()
)
async def approve_access_callback(call: types.CallbackQuery, state: FSMContext):
    """Обработчик для подтверждения доступа."""
    user_message_id = call.message.message_id
    user_id = int(call.data.split(":")[1])
    username = call.data.split(":")[2]

    await bot.delete_message(call.from_user.id, user_message_id)
    await state.update_data(user_id=user_id, username=username)
    await bot.send_message(
        ADMIN_ID, f"На сколько дней выдать доступ для @{username}? Введите число:"
    )
    await state.set_state(Form.waiting_for_n_days)


@admin_router.message(Form.waiting_for_n_days, IsAdmin())
async def process_n_days(message: types.Message, state: FSMContext):
    """Обработчик для получения количества дней доступа."""
    try:
        days = int(message.text.strip())
        if 0 < days < 3000:
            data = await state.get_data()
            user_id = data["user_id"]
            username = data["username"]
            await grant_access_and_create_config(user_id, days)

            await bot.send_animation(
                chat_id=user_id,
                animation=types.FSInputFile("assets/accepted.gif"),
                caption="Добро пожаловать в <i>реальный мир 👁️</i>\n\nⓘ <b>Ваш запрос на доступ к MatrixVPN был одобрен!</b>",
                parse_mode="HTML",
            )
            await process_start_command(user_id=user_id)
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


@admin_router.callback_query(lambda call: call.data.startswith("deny_access:"), IsAdmin())
async def deny_access_callback(call: types.CallbackQuery):
    """Обработчик для отклонения доступа."""
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


@admin_router.message(Command("renewall"), IsAdmin())
async def renew_configs_handler(message: types.Message):
    """Обработчик для обновления конфигураций."""
    users_data = await get_accepted_users()
    failed_users = []
    for user in users_data:
        user_id, username, access_end_date = user
        try:
            access_end_date = datetime.fromisoformat(access_end_date).astimezone(
                pytz.UTC
            )
            remaining_time = access_end_date - datetime.now(pytz.UTC)
            days = int(remaining_time.days)

            if await update_user_configs(user_id, days):
                day_word = get_day_word(days)
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
                    photo=types.FSInputFile("assets/warning.png"),
                    caption=f"🚨 <b>Внимание! Произошло обновление конфигурации!</b>\n\n"
                    "<b>Ваши конфигурационные файлы были обновлены!</b>\n\n"
                    f"Доступ к <b>MatrixVPN</b> заканчивается через <b>{days} {day_word}</b>.\n\n"
                    "<b>⚠️ ВАЖНО: Пожалуйста, замените предыдущие конфигурационные файлы, чтобы избежать проблем с подключением.</b>",
                    parse_mode="HTML",
                    reply_markup=markup,
                )
            else:
                failed_users.append(f"@{username} (ID: {user_id})")

        except (TelegramAPIError) as e:
            logger.error(
                f"Ошибка при обновлении конфигураций для пользователя {user_id} (@{username}): {e}",
                exc_info=True,
            )
            failed_users.append(f"@{username} (ID: {user_id})")

    if failed_users:
        await bot.send_message(
            ADMIN_ID,
            "⚠️ Конфигурации обновлены не для всех пользователей. Ошибки для:\n"
            + "\n".join(failed_users),
        )
    else:
        await bot.send_message(
            ADMIN_ID,
            "✅ Конфигурации всех пользователей успешно обновлены.\n\n"
            "Пользователи были уведомлены о необходимости заменить старые конфигурации.",
        )


@admin_router.callback_query(lambda call: call.data == "delete_user", IsAdmin())
async def delete_user_callback(call: types.CallbackQuery, state: FSMContext):
    """Обработчик для удаления пользователя."""
    await call.message.answer("Введите ID пользователя для удаления:")
    await state.set_state(Form.waiting_for_user_id)
    await call.answer()


@admin_router.message(Form.waiting_for_user_id, IsAdmin())
async def process_user_id(message: types.Message, state: FSMContext):
    """Обработчик для подтверждения удаления пользователя."""
    user_id = message.text.strip()
    if user_id.isdigit():
        if await delete_user(int(user_id)):
            await message.answer(f"Пользователь с ID {user_id} был удалён.")
        else:
            await message.answer(f"Пользователь с ID {user_id} не найден.")
    else:
        await message.answer("Пожалуйста, введите корректный ID пользователя.")
    await state.clear()


@admin_router.callback_query(lambda call: call.data == "broadcast", IsAdmin())
async def broadcast_callback(call: types.CallbackQuery, state: FSMContext):
    """Обработчик для начала рассылки сообщений."""
    await call.message.answer("Введите сообщение для рассылки:")
    await state.set_state(Form.waiting_for_broadcast_message)


@admin_router.message(Form.waiting_for_broadcast_message, IsAdmin())
async def process_broadcast_message(message: types.Message, state: FSMContext):
    """Обработчик для рассылки сообщений."""
    text = message.text.strip()
    await broadcast_message(text)
    await message.answer("Сообщение разослано всем пользователям.")
    await state.clear()


@admin_router.callback_query(lambda call: call.data == "get_users", IsAdmin())
async def get_users_callback(call: types.CallbackQuery):
    """Обработчик для получения списка пользователей."""
    file_path = await get_users_list()
    if file_path:
        await bot.send_document(ADMIN_ID, types.FSInputFile("users_list.txt"))
    else:
        await bot.send_message(
            ADMIN_ID, "Ошибка при получении списка пользователей."
        )


@admin_router.message(Command("renew"), IsAdmin())
async def renew_access(message: types.Message):
    """Обработчик для команды renew."""
    command_parts = message.text.split()
    if len(command_parts) != 3:
        await message.reply(
            "Неверный формат команды. Пример: /renew <user_id> <+days>"
        )
        return

    try:
        user_id = int(command_parts[1])
        days_str = command_parts[2]
        days_to_add = int(days_str.lstrip("+"))
    except (ValueError, IndexError):
        await message.reply(
            "Неверный формат команды. Пример: /renew <user_id> <+days>"
        )
        return

    try:
        user = await get_user_by_id(user_id)

        if not user:
            await message.reply(f"Пользователь с ID {user_id} не найден в базе данных.")
            return

        current_end_date = datetime.fromisoformat(user[5]).astimezone(pytz.UTC)

        if days_str.startswith("+"):
            new_end_date = current_end_date + timedelta(days=days_to_add)
        else:
            new_end_date = datetime.now(pytz.UTC) + timedelta(days=days_to_add)

        access_duration = (new_end_date - datetime.now(pytz.UTC)).days

        if await update_user_configs(user_id, access_duration + 1):
            await update_user_access(user_id, new_end_date.isoformat())
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
                photo=types.FSInputFile("assets/warning.png"),
                caption=f"🚨 <b>Внимание! Ваша подписка была продлена!</b>\n\n"
                f"<b>Конфигурационные файлы были обновлены!</b>\n\n"
                f"Доступ к <b>MatrixVPN</b> заканчивается через <b>{access_duration} дней</b>.\n\n"
                "<b>⚠️ ВАЖНО: Пожалуйста, замените предыдущие конфигурационные файлы, чтобы избежать проблем с подключением.</b>",
                parse_mode="HTML",
                reply_markup=markup,
            )
            await message.reply(
                f"Команда /renew выполнена для пользователя {user_id}. Новый срок окончания через {access_duration} дней."
            )
        else:
            await message.reply(
                f"Произошла ошибка при обновлении VPN конфигурации для пользователя {user_id}. База данных не была изменена."
            )

    except (ValueError, TelegramAPIError) as e:
        logger.error(
            f"Произошла ошибка при обработке команды для пользователя {message.from_user.id}: {e}",
            exc_info=True,
        )
        await message.reply("Произошла ошибка при обработке команды.")
    except Exception as e:
        logger.error(
            f"Неожиданная ошибка при обработке команды для пользователя {message.from_user.id}: {e}",
            exc_info=True,
        )



@admin_router.message(Command("update"), IsAdmin())
async def update_access(message: types.Message):
    """Обработчик для команды update."""
    command_parts = message.text.split()
    if len(command_parts) != 3:
        await message.reply(
            "Неверный формат команды. Пример: /update <user_id> <days>"
        )
        return

    try:
        user_id = int(command_parts[1])
        days_to_add = int(command_parts[2])
    except (ValueError, IndexError):
        await message.reply(
            "Неверный формат команды. Пример: /update <user_id> <days>"
        )
        return

    try:
        user = await get_user_by_id(user_id)

        if not user:
            await message.reply(f"Пользователь с ID {user_id} не найден в базе данных.")
            return

        current_end_date = datetime.fromisoformat(user[5]).astimezone(pytz.UTC)

        new_end_date = current_end_date + timedelta(days=days_to_add)

        access_duration = (new_end_date - datetime.now(pytz.UTC)).days

        if await update_user_configs(user_id, access_duration + 1):
            await update_user_access(user_id, new_end_date.isoformat())
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
                photo=types.FSInputFile("assets/warning.png"),
                caption=f"🚨 <b>Внимание! Срок вашей подписки был продлен!</b>\n\nДоступ к <b>MatrixVPN</b> заканчивается через <b>{access_duration} дней</b>.\n\n",
                parse_mode="HTML",
                reply_markup=markup,
            )
            await message.reply(
                f"Команда /update выполнена для пользователя {user_id}. Новый срок окончания через {access_duration} дней."
            )
        else:
            await message.reply(
                f"Произошла ошибка при обновлении VPN конфигурации для пользователя {user_id}. База данных не была изменена."
            )

    except (ValueError, TelegramAPIError) as e:
        logger.error(
            f"Произошла ошибка при обработке команды для пользователя {message.from_user.id}: {e}",
            exc_info=True,
        )
        await message.reply("Произошла ошибка при обработке команды.")
    except Exception as e:
        logger.error(
            f"Неожиданная ошибка при обработке команды для пользователя {message.from_user.id}: {e}",
            exc_info=True,
        )
