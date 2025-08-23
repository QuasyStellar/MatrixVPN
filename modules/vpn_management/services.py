import os
import json
from aiogram import types
from aiogram.types import FSInputFile
from aiogram.exceptions import TelegramAPIError
import asyncio # Import asyncio for to_thread
import logging # Ensure logging is imported

from core.bot import bot
from config.settings import VPN_CONFIG_PATH
from services.db_operations import get_user_by_id

logger = logging.getLogger(__name__)

# Load VPN config texts from JSON file
with open("config/vpn_configs.json", "r", encoding="utf-8") as f:
    config_texts = json.load(f)

async def send_vpn_config(call: types.CallbackQuery) -> bool:
    user_id = call.from_user.id
    user = await get_user_by_id(user_id)
    if user and user[2] == "accepted":
        config = config_texts[call.data]
        if "WG" in config["prefix"] or "AM" in config["prefix"]:
            file_type = "conf"
        elif "AZ-XR" in config["prefix"]:
            file_type = "json"
        elif "GL-XR" in config["prefix"]:
            file_type = "txt"
        else:
            file_type = "ovpn"
        file_prefix = config["prefix"]
        try:
            # Use asyncio.to_thread for blocking os.listdir
            config_dir_path = os.path.join(VPN_CONFIG_PATH, f"n{user_id}")
            files_in_dir = await asyncio.to_thread(os.listdir, config_dir_path)
            for file_name in files_in_dir:
                if file_name.startswith(file_prefix) and file_name.endswith(f".{file_type}"):
                    print(1)
                    full_file_path = os.path.join(config_dir_path, file_name)
                    
                    # Check if file exists before attempting to send
                    if not await asyncio.to_thread(os.path.exists, full_file_path):
                        logger.warning(f"Конфигурационный файл не найден: {full_file_path} для пользователя {user_id}")
                        continue # Try next file or exit if no other files expected

                    caption = config["text"]
                    if file_type == "ovpn":
                        app_url = "https://openvpn.net/client/"
                    elif "WG" in config["prefix"]:
                        app_url = "https://www.wireguard.com/install/"
                    elif "AM" in config["prefix"]:
                        app_url = "https://docs.amnezia.org/ru/documentation/amnezia-wg/"
                    else:
                        app_url = None

                    markup_buttons = []
                    if app_url:
                        markup_buttons.append(types.InlineKeyboardButton(
                            text="⬇️ Скачать приложение",
                            web_app=types.WebAppInfo(url=app_url),
                        ))

                    # Add button for VLESS text config if it's a VLESS config
                    if file_type in ("json", "txt") and "AZ-XR" in file_prefix:
                        markup_buttons.append(types.InlineKeyboardButton(
                            text="📄 Показать текст конфига",
                            callback_data="az_vless_text",
                        ))
                    elif file_type in ("json", "txt") and "GL-XR" in file_prefix:
                        markup_buttons.append(types.InlineKeyboardButton(
                            text="📄 Показать текст конфига",
                            callback_data="gb_vless_text",
                        ))

                    markup = types.InlineKeyboardMarkup(inline_keyboard=[markup_buttons]) if markup_buttons else None

                    try:
                        await bot.send_document(
                            user_id,
                            FSInputFile(full_file_path),
                            caption=caption,
                            parse_mode="HTML",
                            reply_markup=markup,
                        )
                        return True # Config sent successfully
                    except TelegramAPIError as e:
                        logger.error(f"Ошибка Telegram API при отправке конфигурации {full_file_path} пользователю {user_id}: {e}", exc_info=True)
                        await bot.send_message(user_id, "Произошла ошибка при отправке конфигурационного файла. Пожалуйста, попробуйте позже.")
                        return False # Indicate failure to send config
        except FileNotFoundError:
            logger.warning(f"Каталог конфигураций не найден для пользователя {user_id}: {config_dir_path}")
            await bot.send_message(user_id, "Не удалось найти ваши конфигурационные файлы. Пожалуйста, свяжитесь с администратором.")
            return False
        except Exception as e:
            logger.error(f"Неожиданная ошибка при поиске или отправке конфигурации для пользователя {user_id}: {e}", exc_info=True)
            await bot.send_message(user_id, "Произошла ошибка при получении ваших конфигурационных файлов. Пожалуйста, попробуйте позже или свяжитесь с администратором.")
            return False
    return False # User not accepted or config not sent

async def get_vpn_variants_menu_markup() -> types.InlineKeyboardMarkup:
    # This function will generate the markup for vpn_variants_menu
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(text="🔒 АнтиЗапрет", callback_data="choose_proto_az"),
                types.InlineKeyboardButton(text="🌍 Глобальный", callback_data="choose_proto_gb")
            ],
            [
                types.InlineKeyboardButton(
                    text="📜 Подробнее о вариантах", callback_data="more_variants"
                )
            ],
            [
                types.InlineKeyboardButton(text="⬅ Назад", callback_data="main_menu")
            ],
        ]
    )



async def get_vpn_info_text() -> str:
    # This function will return the text for vpn_info_menu
    return (
        "ⓘ <b>MatrixVPN</b> 🛡️ предлагает два варианта подключения:\n"
        "<b>АнтиЗапрет VPN 🔒</b> — туннелирует только заблокированные и ограниченные ресурсы, "
        "пропуская обычный трафик вне VPN для сохранения скорости соединения ⚡\n\n"
        "<b>Глобальный VPN 🌍</b> — перенаправляет весь интернет-трафик через защищенное соединение, "
        "предоставляя доступ ко всем сайтам и максимальную приватность 🔒\n\n"
        "Поддерживаются протоколы <b>OpenVPN</b>, <b>WireGuard</b> и <b>AmneziaWG</b>."
    )
