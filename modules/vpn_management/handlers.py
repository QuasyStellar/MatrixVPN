import os
import asyncio
import aiofiles

from aiogram import types, Router
from aiogram.types import FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramAPIError

from core.bot import bot
from services.db_operations import get_user_by_id
from services.messages_manage import non_authorized, send_message_with_cleanup
from modules.common.services import message_text_vpn_variants
from modules.vpn_management.services import (
    send_vpn_config,
    get_vpn_variants_menu_markup,
    config_texts,
)
from modules.common.services import get_protos_menu_markup
from config.settings import VPN_CONFIG_PATH
import logging

logger = logging.getLogger(__name__)

vpn_management_router = Router()


@vpn_management_router.callback_query(lambda call: call.data in config_texts.keys())
async def send_configs_callback(call: types.CallbackQuery, state: FSMContext) -> None:
    """Обработчик отправки конфигураций VPN в ответ на запрос пользователя."""
    user_id = call.from_user.id
    user = await get_user_by_id(user_id)

    if user and user[2] == "accepted":
        await bot.delete_message(user_id, call.message.message_id)
        config_sent = await send_vpn_config(call)  # Call the service function
        if config_sent:
            try:
                # After sending config, determine which proto menu to show
                config = config_texts[call.data]
                proto = "az" if "AZ" in config["prefix"] else "gb"
                markup = await get_protos_menu_markup(user_id, proto)
                caption = "ⓘ Выберите VPN протокол:"  # This should come from config/messages.py later
                bot_message = await bot.send_photo(
                    chat_id=user_id,
                    photo=types.FSInputFile(
                        "assets/vpn_protos.png"
                    ),  # This should be dynamic or from config
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=markup,
                )
                await state.update_data(previous_bot_message=bot_message.message_id)
            except TelegramAPIError:
                await bot.send_message(
                    user_id, "Произошла ошибка при отправке меню протоколов."
                )  # Error message

    else:
        await non_authorized(call.from_user.id, call.message.message_id)


@vpn_management_router.callback_query(
    lambda call: call.data in ("choose_proto_az", "choose_proto_gb")
)
async def protos_menu_handler(call: types.CallbackQuery) -> None:
    """Отображает меню выбора протоколов VPN."""
    user_id = call.from_user.id
    proto = call.data[-2:]
    user = await get_user_by_id(user_id)

    if user and user[2] == "accepted":
        markup = await get_protos_menu_markup(user_id, proto)
        caption = (
            "ⓘ Выберите VPN протокол:"  # This should come from config/messages.py later
        )
        try:
            await call.message.edit_media(
                media=types.InputMediaPhoto(
                    media=types.FSInputFile("assets/vpn_protos.png"),
                    caption=caption,
                    parse_mode="HTML",
                ),
                reply_markup=markup,
            )
        except TelegramAPIError:
            await bot.send_photo(
                chat_id=user_id,
                photo=types.FSInputFile("assets/vpn_protos.png"),
                caption=caption,
                parse_mode="HTML",
                reply_markup=markup,
            )
    else:
        await non_authorized(user_id, call.message.message_id)


@vpn_management_router.callback_query(lambda call: call.data == "vpn_variants")
async def vpn_variants_menu_handler(call: types.CallbackQuery) -> None:
    """Отображает конфигурации выбранного протокола VPN."""
    user_id = call.from_user.id
    user = await get_user_by_id(user_id)

    if user and user[2] == "accepted":
        markup = await get_vpn_variants_menu_markup()
        caption = "ⓘ Выберите вариант MatrixVPN🛡️:"  # This should come from config/messages.py later
        try:
            await call.message.edit_media(
                media=types.InputMediaPhoto(
                    media=types.FSInputFile("assets/vpn_variants.png"),
                    caption=caption,
                    parse_mode="HTML",
                ),
                reply_markup=markup,
            )
        except TelegramAPIError:
            await bot.send_photo(
                chat_id=user_id,
                photo=types.FSInputFile("assets/vpn_variants.png"),
                caption=caption,
                parse_mode="HTML",
                reply_markup=markup,
            )
    else:
        await non_authorized(user_id, call.message.message_id)


@vpn_management_router.callback_query(lambda call: call.data == "more_variants")
async def vpn_info_callback_handler(
    call: types.CallbackQuery, state: FSMContext
) -> None:
    """Отображает информацию о VPN в зависимости от выбранного протокола."""
    user_id = call.from_user.id
    user = await get_user_by_id(user_id)

    if user and user[2] == "accepted":
        try:
            await bot.delete_message(user_id, call.message.message_id)
        except TelegramAPIError:
            logger.error(
                "Ошибка при удалении сообщения в vpn_info_callback_handler:",
                exc_info=True,
            )
        await send_message_with_cleanup(user_id, message_text_vpn_variants, state)
        # After showing info, return to vpn variants menu
        await vpn_variants_menu_handler(call)  # Re-use the handler
    else:
        await non_authorized(user_id, call.message.message_id)


@vpn_management_router.callback_query(
    lambda call: call.data in ("az_vless_text", "gb_vless_text")
)
async def send_vless_text_config(call: types.CallbackQuery, state: FSMContext) -> None:
    user_id = call.from_user.id
    user = await get_user_by_id(user_id)

    if user and user[2] == "accepted":
        config_type = call.data.split("_")[0]  # "az" or "gb"

        if config_type == "az":
            file_prefix = "AZ-XR"
            file_type = "json"
        else:  # "gb"
            file_prefix = "GL-XR"
            file_type = "txt"

        client_name = f"n{user_id}"
        config_dir_path = os.path.join(VPN_CONFIG_PATH, client_name)

        found_file_path = None
        if await asyncio.to_thread(os.path.exists, config_dir_path):
            files_in_dir = await asyncio.to_thread(os.listdir, config_dir_path)
            for file_name in files_in_dir:
                if file_name.startswith(file_prefix) and file_name.endswith(
                    f".{file_type}"
                ):
                    found_file_path = os.path.join(config_dir_path, file_name)
                    break

        if found_file_path:
            async with aiofiles.open(found_file_path, "r") as f:
                config_content = await f.read()

            # Отправляем текстом отдельным сообщением
            await send_message_with_cleanup(
                user_id, f"<pre><code>{config_content}</code></pre>", state
            )

            # Вызываем меню протоколов через функцию
            proto = "az" if config_type == "az" else "gb"
            markup = await get_protos_menu_markup(user_id, proto)
            caption = "ⓘ Выберите VPN протокол:"
            await call.message.edit_reply_markup(reply_markup=None)
            bot_message = await bot.send_photo(
                chat_id=user_id,
                photo=FSInputFile("assets/vpn_protos.png"),
                caption=caption,
                parse_mode="HTML",
                reply_markup=markup,
            )
        else:
            await call.message.answer(
                "Не удалось найти текстовую версию конфига. Возможно, файл не был сгенерирован."
            )
    else:
        await non_authorized(user_id, call.message.message_id)

    await call.answer()
