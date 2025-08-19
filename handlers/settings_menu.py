import re
import aiosqlite
from aiogram import types
from aiogram.fsm.context import FSMContext
from config import ADMIN_ID, DATABASE_PATH
from loader import bot, dp
from utils.Forms import Form
from aiogram.types import FSInputFile
from utils.db_utils import get_user_by_id
from utils.messages_manage import non_authorized
import logging

logger = logging.getLogger(__name__)


@dp.callback_query(lambda call: call.data == "settings")
async def settings_menu(
    call: types.CallbackQuery = None, user_id: int = None, state: FSMContext = None
) -> None:
    """Отображает конфигурации выбранного протокола VPN."""
    await state.clear()
    user = await get_user_by_id(call.from_user.id if user_id is None else user_id)

    # Проверка авторизации пользователя
    if user and user[2] == "accepted":
        # Создание кнопок для выбора конфигурации
        markup = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text="📩 Запрос на добавление сайтов в АнтиЗапрет",
                        callback_data="add_site",
                    )
                ],
                [types.InlineKeyboardButton(text="⬅ Назад", callback_data="main_menu")],
            ]
        )
        # Подготовка текста сообщения
        caption = "ⓘ <b>Выберите нужную опцию</b>:"

        # Обновление сообщения или отправка нового в зависимости от передачи user_id
        if user_id is None:
            await call.message.edit_media(
                media=types.InputMediaPhoto(
                    media=FSInputFile("assets/settings.png"),
                    caption=caption,
                    parse_mode="HTML",
                ),
                reply_markup=markup,
            )
        else:
            await bot.send_photo(
                chat_id=user_id,
                photo=FSInputFile("assets/settings.png"),
                caption=caption,
                parse_mode="HTML",
                reply_markup=markup,
            )
    else:
        # Обработка случая, если пользователь не авторизован
        await non_authorized(call.from_user.id, call.message.message_id)


@dp.callback_query(lambda call: call.data == "add_site")
async def ask_for_site_names_callback(call: types.CallbackQuery, state: FSMContext):
    """Запрос на ввод сайта/сайтов для добавления в АнтиЗапрет."""
    # Отправляем сообщение с запросом пользователю, добавляем эмодзи, форматирование и выделение важного
    markup = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="⬅ Назад", callback_data="settings")],
        ]
    )

    await call.message.edit_media(
        media=types.InputMediaPhoto(
            media=FSInputFile("assets/settings.png"),
            caption=(
                "ⓘ <b>Пожалуйста</b>, введите сайт/сайты, которые вы хотите запросить для добавления в <b>АнтиЗапрет</b>.\n\n"
                "<b>Каждый сайт должен быть на новой строке.</b>\n\n"
                "<b>Формат ввода:</b> <code>&lt;example&gt;.&lt;com&gt;</code>\n\n"
                "⚠️ <b>Обратите внимание:</b> Ваш запрос будет передан администратору для рассмотрения, убедитесь в правильности введённых данных.\n"
            ),
            parse_mode="HTML",
        ),
        reply_markup=markup,
    )
    await state.update_data(bot_message_id=call.message.message_id)
    # Переводим пользователя в состояние ожидания ввода сайтов
    await state.set_state(Form.waiting_for_site_names)


@dp.message(Form.waiting_for_site_names)
async def handle_site_names(message: types.Message, state: FSMContext):
    """Обрабатывает введённые пользователем сайты и отправляет запрос админу."""
    # Получаем ID сообщения бота
    data = await state.get_data()
    await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
    bot_message_id = data.get("bot_message_id")

    # Разделяем введённые сайты
    sites = message.text.strip()
    site_list = [site.strip() for site in sites.splitlines() if site.strip()]
    site_pattern = re.compile(r"^[a-zA-Z0-9-]+\.[a-zA-Z]{2,}$")

    # Проверяем сайты
    formatted_sites = [site for site in site_list if site_pattern.match(site)]
    invalid_sites = [site for site in site_list if not site_pattern.match(site)]

    if invalid_sites:
        # Если есть некорректные сайты, редактируем сообщение бота
        markup = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text="⬅ Назад", callback_data="settings")],
            ]
        )
        await bot.edit_message_caption(
            chat_id=message.chat.id,
            message_id=bot_message_id,
            caption=(
                "ⓘ <b>Пожалуйста</b>, введите сайт/сайты, которые вы хотите запросить для добавления в <b>АнтиЗапрет MatrixVPN</b>.\n\n"
                "⚠️ <b>Некорректный формат для:</b>\n"
                + "\n".join([f"<code>{site}</code>" for site in invalid_sites])
                + "\n\nФормат должен быть:\n<code>&lt;example&gt;.&lt;com&gt;</code>."
            ),
            parse_mode="HTML",
            reply_markup=markup,
        )
        return

    # Сохраняем список корректных сайтов в состояние
    await state.update_data(formatted_sites=formatted_sites)

    # Спрашиваем подтверждение у пользователя
    markup = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text="✅ Да",
                    callback_data="confirm",
                ),
                types.InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data="settings",
                ),
            ],
        ]
    )
    await bot.edit_message_caption(
        chat_id=message.chat.id,
        message_id=bot_message_id,
        caption=(
            "<b>ⓘ Вы хотите отправить запрос для добавления:</b>\n"
            + "\n".join([f"<b>{site}</b>" for site in formatted_sites])
        ),
        parse_mode="HTML",
        reply_markup=markup,
    )


# Обработчик для подтверждения
@dp.callback_query(lambda call: call.data == "confirm")
async def confirm_action_callback(call: types.CallbackQuery, state: FSMContext):
    action = call.data
    data = await state.get_data()
    bot_message_id = data.get("bot_message_id")

    # Получаем сохранённые сайты
    formatted_sites = data.get("formatted_sites", [])

    # Отправляем запрос админу
    admin_message = "Запрос на добавление сайтов в VPN:\n\n" + "\n".join(
        formatted_sites
    )
    admin_message += (
        f"\n\nОтправитель: {call.from_user.id} (@{call.from_user.username})"
    )
    await bot.send_message(ADMIN_ID, admin_message)

    # Подтверждаем пользователю
    markup = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="⬅ Назад", callback_data="settings")],
        ]
    )

    await bot.edit_message_caption(
        chat_id=call.message.chat.id,
        message_id=bot_message_id,
        caption=(
            "📨 <b>Ваш запрос был успешно отправлен.</b>\n\n"
            "<b>Список сайтов для добавления:</b>\n"
            + "\n".join([f"<b>{site}</b>" for site in formatted_sites])
        ),
        parse_mode="HTML",
        reply_markup=markup,
    )
    await state.clear()



