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
    message_text_vpn_variants,
    message_text_protos_info,
    get_protos_menu_markup,
    main_menu,
)
from config.settings import ADMIN_ID, TELEGRAM_STARS_PAYMENT_TOKEN
from services import vpn_manager

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
        from modules.user_onboarding.entry import start_handler

        await start_handler(user_id=call.from_user.id)


@common_router.callback_query(lambda call: call.data == "more")
async def info_about_vpn_callback(call: types.CallbackQuery, state: FSMContext) -> None:
    """Обработчик для кнопки 'Больше информации о VPN'."""
    try:
        try:
            await bot.delete_message(call.from_user.id, call.message.message_id)
        except TelegramAPIError:
            logger.error(
                "Ошибка при удалении сообщения в info_about_vpn_callback:",
                exc_info=True,
            )

        await send_message_with_cleanup(
            call.from_user.id, message_text_vpn_variants, state
        )

        from modules.user_onboarding.entry import start_handler

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


@common_router.callback_query(lambda call: call.data == "activate_promo")
async def activate_promo_callback(call: types.CallbackQuery, state: FSMContext) -> None:
    """Обработчик для кнопки 'Активировать промокод'."""
    await call.message.answer("Пожалуйста, введите ваш промокод:")
    await state.set_state(Form.waiting_for_promo_code)
    await call.answer() # Acknowledge the callback query


@common_router.message(Form.waiting_for_promo_code)
async def process_promo_code(message: types.Message, state: FSMContext):
    """Обработчик для получения промокода от пользователя."""
    promo_code_str = message.text.strip()
    user_id = message.from_user.id

    promo = await get_promo_code(promo_code_str)

    if promo and promo[2] == 1:  # promo[2] is is_active
        days_to_add = promo[1]  # promo[1] is days_duration

        user = await get_user_by_id(user_id)
        if user:
            current_end_date = datetime.fromisoformat(user[5]).astimezone(pytz.UTC) # user[5] is access_end_date
            new_end_date = current_end_date + timedelta(days=days_to_add)

            await update_user_access(user_id, new_end_date.isoformat())
            await mark_promo_code_as_used(promo_code_str)
            await vpn_manager.create_user(user_id) # Regenerate and send config

            await message.answer(
                f"Промокод '{promo_code_str}' успешно активирован! "
                f"Ваша подписка продлена на {days_to_add} дней. "
                "Новые конфигурационные файлы будут отправлены."
            )
        else:
            await message.answer("Произошла ошибка при активации промокода. Пользователь не найден.")
            logger.error(f"User {user_id} not found when activating promo code {promo_code_str}")
    else:
        await message.answer("Неверный или неактивный промокод.")

    await state.clear()


@common_router.callback_query(lambda call: call.data == "buy_subscription")
async def buy_subscription_callback(call: types.CallbackQuery) -> None:
    """Обработчик для кнопки 'Купить подписку'."""
    # For now, let's offer a fixed price for a fixed duration.
    # This should ideally be configurable.
    price_stars = 100 # Example price in Telegram Stars
    subscription_days = 30 # Example subscription duration

    # Telegram Stars payment requires a specific invoice structure.
    # The title, description, payload, currency, and prices are important.
    # The currency for Telegram Stars is 'XTR'.

    # You might want to offer different subscription tiers (e.g., 1 month, 3 months, 1 year)
    # For simplicity, let's start with one option.

    # The payload can be used to identify the transaction later.
    # It's good practice to include user_id and a unique identifier.
    payload = f"subscription_{call.from_user.id}_{subscription_days}days"

    # Send the invoice
    try:
        await bot.send_invoice(
            chat_id=call.from_user.id,
            title=f"Подписка на MatrixVPN на {subscription_days} дней",
            description=f"Доступ к MatrixVPN на {subscription_days} дней.",
            payload=payload,
            provider_token=TELEGRAM_STARS_PAYMENT_TOKEN, # From config.settings
            currency="XTR", # Telegram Stars currency
            prices=[types.LabeledPrice(label=f"Подписка на {subscription_days} дней", amount=price_stars)],
            start_parameter="matrixvpn_subscription", # Optional, for deep linking
            # photo_url="URL_TO_YOUR_PRODUCT_PHOTO", # Optional, but good for UX
            # photo_width=400,
            # photo_height=400,
            # photo_size=400,
            need_name=False,
            need_phone_number=False,
            need_email=False,
            need_shipping_address=False,
            send_email_to_provider=False,
            send_phone_number_to_provider=False,
            is_flexible=False, # Not a flexible shipping invoice
        )
    except TelegramAPIError as e:
        logger.error(f"Error sending invoice to user {call.from_user.id}: {e}", exc_info=True)
        await call.message.answer("Произошла ошибка при создании счета. Пожалуйста, попробуйте позже.")
    
    await call.answer() # Acknowledge the callback query


@common_router.pre_checkout_query()
async def pre_checkout_query_handler(pre_checkout_query: types.PreCheckoutQuery):
    """Обработчик для предварительной проверки платежа."""
    # You can add logic here to validate the payment, e.g., check payload, user status, etc.
    # For now, we'll just confirm it's okay.
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)


@common_router.message(content_types=types.ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment_handler(message: types.Message):
    """Обработчик для успешного платежа."""
    user_id = message.from_user.id
    total_amount = message.successful_payment.total_amount
    invoice_payload = message.successful_payment.invoice_payload

    # Extract subscription days from payload (e.g., "subscription_12345_30days")
    try:
        # Assuming payload format is "subscription_{user_id}_{days}days"
        parts = invoice_payload.split('_')
        subscription_days = int(parts[2].replace('days', ''))
    except (IndexError, ValueError):
        logger.error(f"Could not parse subscription days from payload: {invoice_payload}", exc_info=True)
        subscription_days = 0 # Default to 0 or handle error appropriately

    if subscription_days > 0:
        user = await get_user_by_id(user_id)
        if user:
            current_end_date = datetime.fromisoformat(user[5]).astimezone(pytz.UTC) # user[5] is access_end_date
            new_end_date = current_end_date + timedelta(days=subscription_days)

            await update_user_access(user_id, new_end_date.isoformat())
            await vpn_manager.create_user(user_id) # Regenerate and send config

            await bot.send_message(
                user_id,
                f"✅ Ваша подписка успешно оплачена! "
                f"Доступ продлен на {subscription_days} дней. "
                "Новые конфигурационные файлы будут отправлены."
            )
            logger.info(f"User {user_id} successfully paid {total_amount} stars for {subscription_days} days.")
        else:
            logger.error(f"User {user_id} not found after successful payment.", exc_info=True)
            await bot.send_message(user_id, "Произошла ошибка при обработке вашей оплаты. Пожалуйста, свяжитесь с поддержкой.")
    else:
        logger.error(f"Invalid subscription days ({subscription_days}) from payload: {invoice_payload}", exc_info=True)
        await bot.send_message(user_id, "Произошла ошибка при обработке вашей оплаты. Не удалось определить срок подписки. Пожалуйста, свяжитесь с поддержкой.")

    # Optional: Notify admin about successful payment
    await bot.send_message(
        ADMIN_ID,
        f"💰 Успешная оплата от пользователя @{message.from_user.username} (ID: {user_id}).\n"
        f"Сумма: {total_amount} Stars.\n"
        f"Продлено на: {subscription_days} дней."
    )
