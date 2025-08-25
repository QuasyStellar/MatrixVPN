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
    delete_user,
    get_users_list,
    get_accepted_users,
    get_user_by_id,
    update_user_access,
    add_promo_code,
    delete_promo_code,
    get_all_promo_codes,
    grant_access_and_create_config,
    get_pending_requests,
)
from services.messages_manage import broadcast_message
from services.forms import Form
from modules.admin.services import get_day_word, update_user_configs
from modules.admin.filters import IsAdmin
from modules.common.services import main_menu
from modules.user_onboarding.services import enter_caption

logger = logging.getLogger(__name__)

admin_router = Router()


@admin_router.message(Command("admin"), IsAdmin())
async def admin_handler(message: types.Message) -> None:
    """Обработчик команды /admin."""
    await admin_menu(message)


async def admin_menu(message: types.Message):
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
        types.InlineKeyboardButton(text="Промокоды", callback_data="promo_codes"),
    ]
    markup = types.InlineKeyboardMarkup(
        inline_keyboard=[buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    )
    await bot.send_message(
        message.from_user.id,
        "Добро пожаловать, администратор! Выберите действие:",
        reply_markup=markup,
    )


@admin_router.callback_query(lambda call: call.data == "admin_menu", IsAdmin())
async def admin_menu_callback(call: types.CallbackQuery):
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
        types.InlineKeyboardButton(text="Промокоды", callback_data="promo_codes"),
    ]
    markup = types.InlineKeyboardMarkup(
        inline_keyboard=[buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    )
    await call.message.edit_text(
        "Добро пожаловать, администратор! Выберите действие:",
        reply_markup=markup,
    )


@admin_router.callback_query(lambda call: call.data == "check_requests", IsAdmin())
async def check_requests_callback(call: types.CallbackQuery):
    """Обработчик для проверки ожидающих запросов."""
    pending_requests = await get_pending_requests()

    if pending_requests:
        response_text = "<b>Ожидающие запросы:</b>"

        for user in pending_requests:
            user_id, username, status, _, _, _, _, _ = user  # Unpack all fields
            response_text += f"ID: <code>{user_id}</code>\n"
            response_text += f"Username: @{username}\n"
            response_text += f"Статус: {status}\n"

            markup = types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text="✅ Принять", callback_data=f"accept_request_{user_id}"
                        ),
                    ]
                ]
            )
            await call.message.answer(
                response_text, parse_mode="HTML", reply_markup=markup
            )
            response_text = ""  # Clear for next request

        # Add a back button to the last message or send a separate one
        back_markup = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text="⬅ Назад", callback_data="admin_menu")]
            ]
        )
        await call.message.answer(
            "Пользователи в ожидание выведены", reply_markup=back_markup
        )  # Send a blank message with back button

    else:
        markup = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text="⬅ Назад", callback_data="admin_menu")]
            ]
        )
        await call.message.edit_text(
            "Нет ожидающих запросов.",
            reply_markup=markup,
        )
    await call.answer()


@admin_router.callback_query(
    lambda call: call.data.startswith("accept_request_"), IsAdmin()
)
async def accept_request_callback(call: types.CallbackQuery):
    user_id = int(call.data.split("_")[2])

    # Assuming a default trial period, or you can make it configurable
    trial_days = 30  # Example: 30 days access

    try:
        await grant_access_and_create_config(user_id, trial_days)

        await call.message.edit_text(
            f"✅ Запрос пользователя <code>{user_id}</code> принят. Доступ предоставлен на {trial_days} дней.",
            parse_mode="HTML",
        )
        await bot.send_animation(
            chat_id=user_id,
            animation=types.FSInputFile("assets/accepted.gif"),
            caption=(
                enter_caption + "\n\n" "💳 <b>Вам был выдан доступ к MatrixVPN</b>\n"
            ),
            parse_mode="HTML",
        )
        await main_menu(user_id=user_id)  # Send main menu to the user
    except Exception as e:
        await call.message.edit_text(
            f"❌ Ошибка при принятии запроса пользователя <code>{user_id}</code>: {e}",
            parse_mode="HTML",
        )
        logger.error(f"Error accepting request for user {user_id}: {e}", exc_info=True)
    await call.answer()


@admin_router.callback_query(lambda call: call.data == "promo_codes", IsAdmin())
async def promo_codes_menu(call: types.CallbackQuery):
    """Displays the promo code management menu."""
    buttons = [
        types.InlineKeyboardButton(text="Добавить промокод", callback_data="add_promo"),
        types.InlineKeyboardButton(
            text="Список промокодов", callback_data="list_promos_menu"
        ),
        types.InlineKeyboardButton(
            text="Удалить промокод", callback_data="delete_promo"
        ),
        types.InlineKeyboardButton(text="⬅ Назад", callback_data="admin_menu"),
    ]
    markup = types.InlineKeyboardMarkup(
        inline_keyboard=[buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    )
    await call.message.edit_text(
        "Управление промокодами:",
        reply_markup=markup,
    )


@admin_router.callback_query(lambda call: call.data == "add_promo", IsAdmin())
async def add_promo_callback(call: types.CallbackQuery, state: FSMContext):
    """Handler for adding a new promo code."""
    await call.message.answer(
        "Введите промокод, количество дней и количество использований в формате: <code>&lt;код&gt; &lt;дни&gt; &lt;использования&gt;</code>",
        parse_mode="HTML",
    )
    await state.set_state(Form.waiting_for_promo_code_data)
    await call.answer()


@admin_router.message(Form.waiting_for_promo_code_data, IsAdmin())
async def process_promo_code_data(message: types.Message, state: FSMContext):
    """Handler for processing the new promo code data."""
    parts = message.text.split()
    if len(parts) != 3:
        await message.answer(
            "Неверный формат. Пожалуйста, введите промокод, количество дней и количество использований, разделенные пробелом."
        )
        return

    code, days_str, usage_count_str = parts
    try:
        days = int(days_str)
        usage_count = int(usage_count_str)
        if days <= 0 or usage_count <= 0:
            raise ValueError
    except ValueError:
        await message.answer(
            "Количество дней и количество использований должны быть положительными числами."
        )
        return

    if await add_promo_code(code, days, usage_count):
        await message.answer(
            f"Промокод '{code}' на {days} дней с {usage_count} использованиями успешно добавлен."
        )
    else:
        await message.answer(
            f"Не удалось добавить промокод '{code}'. Возможно, он уже существует."
        )
    await state.clear()


@admin_router.callback_query(lambda call: call.data == "list_promos_menu", IsAdmin())
async def list_promos_menu_callback(call: types.CallbackQuery):
    """Handler for listing all promo codes."""
    promo_codes = await get_all_promo_codes()
    if promo_codes:
        response = "Список промокодов:\n\n"
        for promo in promo_codes:
            response += f"Код: `{promo[0]}`, Дни: {promo[1]}, Активен: {'Да' if promo[2] == 1 else 'Нет'}, Использований осталось: {promo[3]}\n"
    else:
        response = "Промокодов нет."

    await call.message.answer(response, parse_mode="Markdown")
    await call.answer()


@admin_router.callback_query(lambda call: call.data == "delete_promo", IsAdmin())
async def delete_promo_callback(call: types.CallbackQuery, state: FSMContext):
    """Handler for deleting a promo code."""
    await call.message.answer("Введите промокод для удаления:")
    await state.set_state(Form.waiting_for_promo_code_to_delete)
    await call.answer()


@admin_router.message(Form.waiting_for_promo_code_to_delete, IsAdmin())
async def process_promo_code_to_delete(message: types.Message, state: FSMContext):
    """Handler for processing the promo code to delete."""
    promo_code = message.text.strip()
    if await delete_promo_code(promo_code):
        await message.answer(f"Промокод '{promo_code}' был удален.")
    else:
        await message.answer(f"Промокод '{promo_code}' не найден.")
    await state.clear()

    await call.answer()


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

        except TelegramAPIError as e:
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
        await bot.send_document(ADMIN_ID, types.FSInputFile("users_list.csv"))
    else:
        await bot.send_message(ADMIN_ID, "Ошибка при получении списка пользователей.")


@admin_router.message(Command("renew"), IsAdmin())
async def renew_access(message: types.Message):
    """Обработчик для команды renew."""
    command_parts = message.text.split()
    if len(command_parts) != 3:
        await message.reply("Неверный формат команды. Пример: /renew <user_id> <+days>")
        return

    try:
        user_id = int(command_parts[1])
        days_str = command_parts[2]
        days_to_add = int(days_str.lstrip("+"))
    except (ValueError, IndexError):
        await message.reply("Неверный формат команды. Пример: /renew <user_id> <+days>")
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
                caption=f"🚨 <b>Внимание! Ваша подписка была обновлена!</b>\n\n"
                f"<b>Конфигурационные файлы были обновлены!</b>\n\n"
                f"Доступ к <b>MatrixVPN</b> заканчивается через <b>{access_duration} {get_day_word(access_duration)}</b>.\n\n"
                "<b>⚠️ ВАЖНО: Пожалуйста, замените предыдущие конфигурационные файлы, чтобы избежать проблем с подключением.</b>",
                parse_mode="HTML",
                reply_markup=markup,
            )
            await message.reply(
                f"Команда /renew выполнена для пользователя {user_id}. Новый срок окончания через {access_duration} {get_day_word(access_duration)}."
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
        await message.reply("Неверный формат команды. Пример: /update <user_id> <days>")
        return

    try:
        user_id = int(command_parts[1])
        days_to_add = int(command_parts[2])
    except (ValueError, IndexError):
        await message.reply("Неверный формат команды. Пример: /update <user_id> <days>")
        return

    try:
        user = await get_user_by_id(user_id)

        if not user:
            await message.reply(f"Пользователь с ID {user_id} не найден в базе данных.")
            return

        current_end_date = datetime.fromisoformat(user[5]).astimezone(pytz.UTC)

        new_end_date = current_end_date + timedelta(days=days_to_add)

        access_duration = (new_end_date - datetime.now(pytz.UTC)).days

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
            caption=f"🚨 <b>Внимание! Срок вашей подписки был продлен!</b>\n\nДоступ к <b>MatrixVPN</b> заканчивается через <b>{access_duration} {get_day_word(access_duration)}</b>.\n\n",
            parse_mode="HTML",
            reply_markup=markup,
        )
        await message.reply(
            f"Команда /update выполнена для пользователя {user_id}. Новый срок окончания через {access_duration} {get_day_word(access_duration)}."
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


@admin_router.message(Command("refund"), IsAdmin())
async def refund_stars_handler(message: types.Message):
    """Обработчик для команды /refund."""
    command_parts = message.text.split()
    if len(command_parts) != 3:
        await message.reply(
            "Неверный формат команды. Пример: /refund <user_id> <telegram_payment_charge_id>"
        )
        return

    try:
        user_id = int(command_parts[1])
        payment_charge_id = command_parts[2]
    except (ValueError, IndexError):
        await message.reply(
            "Неверный формат команды. Пример: /refund <user_id> <telegram_payment_charge_id>"
        )
        return

    try:
        # Attempt to refund the stars
        await bot.refund_star_payment(
            user_id=user_id, telegram_payment_charge_id=payment_charge_id
        )
        await message.reply(
            f"✅ Запрос на возврат звезд для пользователя {user_id} (ID платежа: {payment_charge_id}) отправлен."
        )
        logger.info(
            f"Refund request sent for user {user_id} with payment ID {payment_charge_id}"
        )
    except TelegramAPIError as e:
        await message.reply(
            f"❌ Ошибка при возврате звезд для пользователя {user_id}: {e}"
        )
        logger.error(
            f"Error refunding stars for user {user_id} with payment ID {payment_charge_id}: {e}",
            exc_info=True,
        )
    except Exception as e:
        await message.reply(
            f"❌ Неожиданная ошибка при обработке команды /refund для пользователя {user_id}: {e}"
        )
        logger.error(
            f"Unexpected error processing /refund for user {user_id}: {e}",
            exc_info=True,
        )
