from aiogram import types, Router
from aiogram.fsm.context import FSMContext
from aiogram.filters.command import Command
from aiogram.exceptions import TelegramAPIError

import re

from core.bot import bot
from services.db_operations import get_user_by_id
from services.messages_manage import non_authorized, send_message_with_cleanup
from services.forms import Form
from modules.common.services import (
    quotes,
    message_text_vpn_variants,
    message_text_protos_info,
    get_protos_menu_markup,
    main_menu,
)
from config.settings import ADMIN_ID, SUPPORT_ID

common_router = Router()


@common_router.callback_query(lambda call: call.data == "main_menu")
async def main_menu_handler(call: types.CallbackQuery = None, user_id: int = None):
    """Обработчик для главного меню VPN."""
    await main_menu(call=call, user_id=user_id)


@common_router.callback_query(lambda call: call.data == "settings")
async def settings_menu(
    call: types.CallbackQuery = None, user_id: int = None, state: FSMContext = None
) -> None:
    """Отображает конфигурации выбранного протокола VPN."""
    if state:
        await state.clear()
    user = await get_user_by_id(call.from_user.id if user_id is None else user_id)

    if user and user[2] == "accepted":
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
        caption = "ⓘ <b>Выберите нужную опцию</b>:"

        if user_id is None:
            try:
                await call.message.edit_media(
                    media=types.InputMediaPhoto(
                        media=types.FSInputFile("assets/settings.png"),
                        caption=caption,
                        parse_mode="HTML",
                    ),
                    reply_markup=markup,
                )
            except TelegramAPIError:
                await bot.send_photo(
                    chat_id=call.from_user.id,
                    photo=types.FSInputFile("assets/settings.png"),
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=markup,
                )
        else:
            await bot.send_photo(
                chat_id=user_id,
                photo=types.FSInputFile("assets/settings.png"),
                caption=caption,
                parse_mode="HTML",
                reply_markup=markup,
            )
    else:
        await non_authorized(call.from_user.id, call.message.message_id)


@common_router.callback_query(lambda call: call.data == "add_site")
async def ask_for_site_names_callback(call: types.CallbackQuery, state: FSMContext):
    """Запрос на ввод сайта/сайтов для добавления в АнтиЗапрет."""
    markup = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="⬅ Назад", callback_data="settings")],
        ]
    )

    try:
        await call.message.edit_media(
            media=types.InputMediaPhoto(
                media=types.FSInputFile("assets/settings.png"),
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
    except TelegramAPIError:
        await bot.send_photo(
            chat_id=call.from_user.id,
            photo=types.FSInputFile("assets/settings.png"),
            caption=(
                "ⓘ <b>Пожалуйста</b>, введите сайт/сайты, которые вы хотите запросить для добавления в <b>АнтиЗапрет</b>.\n\n"
                "<b>Каждый сайт должен быть на новой строке.</b>\n\n"
                "<b>Формат ввода:</b> <code>&lt;example&gt;.&lt;com&gt;</code>\n\n"
                "⚠️ <b>Обратите внимание:</b> Ваш запрос будет передан администратору для рассмотрения, убедитесь в правильности введённых данных.\n"
            ),
            parse_mode="HTML",
            reply_markup=markup,
        )
    await state.update_data(bot_message_id=call.message.message_id)
    # Переводим пользователя в состояние ожидания ввода сайтов
    await state.set_state(Form.waiting_for_site_names)


@common_router.message(Form.waiting_for_site_names)
async def handle_site_names(message: types.Message, state: FSMContext):
    """Обрабатывает введённые пользователем сайты и отправляет запрос админу."""
    data = await state.get_data()
    await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
    bot_message_id = data.get("bot_message_id")

    sites = message.text.strip()
    site_list = [site.strip() for site in sites.splitlines() if site.strip()]
    site_pattern = re.compile(
        r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,6}$"
    )

    formatted_sites = [site for site in site_list if site_pattern.match(site)]
    invalid_sites = [site for site in site_list if not site_pattern.match(site)]

    if invalid_sites:
        markup = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text="⬅ Назад", callback_data="settings")],
            ]
        )
        try:
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
        except TelegramAPIError:
            await bot.send_message(
                chat_id=message.chat.id,
                text=(
                    "ⓘ <b>Пожалуйста</b>, введите сайт/сайты, которые вы хотите запросить для добавления в <b>АнтиЗапрет MatrixVPN</b>.\n\n"
                    "⚠️ <b>Некорректный формат для:</b>\n"
                    + "\n".join([f"<code>{site}</code>" for site in invalid_sites])
                    + "\n\nФормат должен быть:\n<code>&lt;example&gt;.&lt;com&gt;</code>."
                ),
                parse_mode="HTML",
                reply_markup=markup,
            )
        return

    await state.update_data(formatted_sites=formatted_sites)

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
    try:
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
    except TelegramAPIError:
        await bot.send_message(
            chat_id=message.chat.id,
            text=(
                "<b>ⓘ Вы хотите отправить запрос для добавления:</b>\n"
                + "\n".join([f"<b>{site}</b>" for site in formatted_sites])
            ),
            parse_mode="HTML",
            reply_markup=markup,
        )


@common_router.callback_query(lambda call: call.data == "confirm")
async def confirm_action_callback(call: types.CallbackQuery, state: FSMContext):
    action = call.data
    data = await state.get_data()
    bot_message_id = data.get("bot_message_id")

    formatted_sites = data.get("formatted_sites", [])

    admin_message = "Запрос на добавление сайтов в VPN:\n\n" + "\n".join(
        formatted_sites
    )
    admin_message += (
        f"\n\nОтправитель: {call.from_user.id} (@{call.from_user.username})"
    )
    await bot.send_message(ADMIN_ID, admin_message)

    markup = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="⬅ Назад", callback_data="settings")],
        ]
    )

    try:
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
    except TelegramAPIError:
        await bot.send_message(
            chat_id=call.message.chat.id,
            text=(
                "📨 <b>Ваш запрос был успешно отправлен.</b>\n\n"
                "<b>Список сайтов для добавления:</b>\n"
                + "\n".join([f"<b>{site}</b>" for site in formatted_sites])
            ),
            parse_mode="HTML",
            reply_markup=markup,
        )
    await state.clear()


@common_router.callback_query(lambda call: call.data in ("az_about", "gb_about"))
async def info_about_protos_callback(
    call: types.CallbackQuery, state: FSMContext
) -> None:
    """Обработчик для предоставления информации о протоколах VPN."""
    user = await get_user_by_id(call.from_user.id)

    if user and user[2] == "accepted":
        state_data = await state.get_data()
        previous_bot_message_id = state_data.get("previous_bot_message")

        try:
            try:
                await bot.delete_message(call.from_user.id, call.message.message_id)
            except TelegramAPIError:
                logger.error(
                    "Ошибка при удалении сообщения в info_about_protos_callback:",
                    exc_info=True,
                )

            bot_message = await send_message_with_cleanup(
                call.from_user.id, message_text_protos_info, state
            )
            await state.update_data(previous_bot_message=bot_message.message_id)

            markup = await get_protos_menu_markup(call.from_user.id, call.data[:2])
            caption = "ⓘ Выберите VPN протокол:"
            await bot.send_photo(
                chat_id=call.from_user.id,
                photo=types.FSInputFile("assets/vpn_protos.png"),
                caption=caption,
                parse_mode="HTML",
                reply_markup=markup,
            )

        except TelegramAPIError:
            logger.error("Ошибка при обработке запроса о протоколах:", exc_info=True)

    else:
        await state.clear()
        await bot.delete_message(call.from_user.id, call.message.message_id)
        from modules.user_onboarding.handlers import start_handler

        await start_handler(user_id=call.from_user.id)


@common_router.callback_query(lambda call: call.data == "more")
async def info_about_vpn_callback(call: types.CallbackQuery, state: FSMContext) -> None:
    """Обработчик для кнопки 'Больше информации о VPN'."""
    try:
        try:
            await bot.delete_message(call.from_user.id, call.message.message_id)
        except TelegramAPIError:
            logger.error(
                "Ошибка при удалении сообщения в info_about_vpn_callback:", exc_info=True
            )

        await send_message_with_cleanup(
            call.from_user.id, message_text_vpn_variants, state
        )

        from modules.user_onboarding.handlers import start_handler

        await start_handler(user_id=call.from_user.id)

    except TelegramAPIError:
        logger.error("Ошибка при обработке запроса о VPN:", exc_info=True)


@common_router.message(Command("more"))
async def info_about_vpn_handler(message: types.Message) -> None:
    """Обработчик для команды '/more'."""
    user_id = message.from_user.id

    try:
        await bot.send_message(
            user_id,
            message_text_vpn_variants,
            parse_mode="HTML",
        )
    except TelegramAPIError:
        logger.error("Ошибка при обработке команды 'more':", exc_info=True)
