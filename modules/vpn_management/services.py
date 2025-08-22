import os
from aiogram import types
from aiogram.types import FSInputFile
from aiogram.exceptions import TelegramAPIError
import asyncio # Import asyncio for to_thread
import logging # Ensure logging is imported

from core.bot import bot
from config.settings import VPN_CONFIG_PATH
from services.db_operations import get_user_by_id
from services.messages_manage import non_authorized

logger = logging.getLogger(__name__)

# Тексты конфигураций VPN с префиксами и дополнительной информацией
config_texts = {
    "az_openvpn": {
        "prefix": "AZ-U+T",
        "text": "🌍 Идеальное сочетание скорости и надежности! Используется автоматический выбор сетевого протокола для максимальной гибкости ✨\n\n<b>FAQ по названию файлов:</b>\n\n <code>&lt;вариант_впн&gt;-&lt;протокол&gt;-&lt;дата_активации&gt;.*</code>",
    },
    "gb_openvpn": {
        "prefix": "GL-U+T",
        "text": "🌍 Идеальное сочетание скорости и надежности! Используется автоматический выбор сетевого протокола для максимальной гибкости ✨\n\n<b>FAQ по названию файлов:</b>\n\n <code>&lt;вариант_впн&gt;-&lt;протокол&gt;-&lt;дата_активации&gt;.*</code>",
    },
    "az_amneziawg": {
        "prefix": "AZ-AM",
        "text": "🕊 Ощутите свободу в интернете c <b>улучшенным механизмом скрытия подключения к VPN</b> 🥷\n\n<b>FAQ по названию файлов:</b>\n\n <code>&lt;вариант_впн&gt;-&lt;протокол&gt;-&lt;дата_активации&gt;.*</code>",
    },
    "gb_amneziawg": {
        "prefix": "GL-AM",
        "text": "🙈 Ваше безопасное путешествие по интернету <b>без блокировок</b> начинается здесь! <b>Защитите свою приватность</b> и <b>оставайтесь анонимным!</b> 🕵️‍♂️\n\n<b>FAQ по названию файлов:</b>\n\n <code>&lt;вариант_впн&gt;-&lt;протокол&gt;-&lt;дата_активации&gt;.*</code>",
    },
    "az_wireguard": {
        "prefix": "AZ-WG",
        "text": "⚡ Обходите блокировки и получайте доступ к любимым сайтам с <b>высокой скоростью</b>! 🌊\n\n<b>FAQ по названию файлов:</b>\n\n <code>&lt;вариант_впн&gt;-&lt;протокол&gt;-&lt;дата_активации&gt;.*</code>",
    },
    "gb_wireguard": {
        "prefix": "GL-WG",
        "text": "🔒 Получите <b>максимальную защиту и анонимность</b> при использовании интернета. Ваши данные под надежной защитой! 🔐\n\n<b>FAQ по названию файлов:</b>\n\n <code>&lt;вариант_впн&gt;-&lt;протокол&gt;-&lt;дата_активации&gt;.*</code>",
    },
}

async def send_vpn_config(call: types.CallbackQuery) -> bool:
    user_id = call.from_user.id
    user = await get_user_by_id(user_id)

    if user and user[2] == "accepted":
        config = config_texts[call.data]
        file_type = (
            "conf" if "WG" in config["prefix"] or "AM" in config["prefix"] else "ovpn"
        )
        file_prefix = config["prefix"]
        
        try:
            # Use asyncio.to_thread for blocking os.listdir
            config_dir_path = f"{VPN_CONFIG_PATH}/n{user_id}"
            files_in_dir = await asyncio.to_thread(os.listdir, config_dir_path)

            for file_name in files_in_dir:
                if file_name.startswith(file_prefix) and file_name.endswith(f".{file_type}"):
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

                    markup = (
                        types.InlineKeyboardMarkup(
                            inline_keyboard=[
                                [
                                    types.InlineKeyboardButton(
                                        text="⬇️ Скачать приложение",
                                        web_app=types.WebAppInfo(url=app_url),
                                    )
                                ]
                            ]
                        )
                        if app_url
                        else None
                    )

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

async def get_protos_menu_markup(user_id: int, proto: str) -> types.InlineKeyboardMarkup:
    # This function will generate the markup for protos_menu
    # It will be called from handlers and potentially other services
    user = await get_user_by_id(user_id)
    if not (user and user[2] == "accepted"):
        return None

    inline_keyboard = [
        [
            types.InlineKeyboardButton(
                text="🛡️ OpenVPN",
                callback_data=f"{proto}_openvpn",
            )
        ],
        [
            types.InlineKeyboardButton(
                text="⚡ WireGuard",
                callback_data=f"{proto}_wireguard",
            ),
            types.InlineKeyboardButton(
                text="🕵️ AmneziaWG",
                callback_data=f"{proto}_amneziawg",
            ),
        ],
        [
            types.InlineKeyboardButton(
                text="🔍 О VPN протоколах",
                callback_data=f"{proto}_about",
            )
        ],
    ]
    if (proto) == "az":
        inline_keyboard.insert(
            0,
            [
                types.InlineKeyboardButton(
                    text="🚨 Примечание",
                    web_app=types.WebAppInfo(
                        url="https://teletype.in/@esc_matrix/antizapret_warning"
                    ),
                )
            ],
        )
    inline_keyboard.append(
        [
            types.InlineKeyboardButton(
                text="📜 Инструкции",
                callback_data=f"{proto}_faq",
            )
        ]
    )
    inline_keyboard.append(
        [types.InlineKeyboardButton(text="⬅ Назад", callback_data="vpn_variants")]
    )

    return types.InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

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
