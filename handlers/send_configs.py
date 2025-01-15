import os
from aiogram import types
from aiogram.types import FSInputFile
from handlers.protos_menu import protos_menu
from loader import dp, bot
from utils.db_utils import get_user_by_id
from utils.messages_manage import non_authorized

# Тексты конфигураций VPN с префиксами и дополнительной информацией
config_texts = {
    "az_openvpn": {
        "prefix": "AZ-OV",
        "text": "🌍 Идеальное сочетание скорости и надежности! Используется автоматический выбор сетевого протокола для максимальной гибкости ✨\n\n<b>FAQ по названию файлов:</b>\n\n <code>&lt;вариант_впн&gt;-&lt;протокол&gt;-&lt;дата_активациин&gt;.*</code>",
    },
    "gb_openvpn": {
        "prefix": "GL-OV",
        "text": "🌍 Идеальное сочетание скорости и надежности! Используется автоматический выбор сетевого протокола для максимальной гибкости ✨\n\n<b>FAQ по названию файлов:</b>\n\n <code>&lt;вариант_впн&gt;-&lt;протокол&gt;-&lt;дата_активациин&gt;.*</code>",
    },
    "az_amneziawg": {
        "prefix": "AZ-AM",
        "text": "🕊 Ощутите свободу в интернете c <b>улучшенным механизмом скрытия подключения к VPN</b> 🥷\n\n<b>FAQ по названию файлов:</b>\n\n <code>&lt;вариант_впн&gt;-&lt;протокол&gt;-&lt;дата_активациин&gt;.*</code>",
    },
    "gb_amneziawg": {
        "prefix": "GL-AM",
        "text": "🙈 Ваше безопасное путешествие по интернету <b>без блокировок</b> начинается здесь! <b>Защитите свою приватность</b> и <b>оставайтесь анонимным!</b> 🕵️‍♂️\n\n<b>FAQ по названию файлов:</b>\n\n <code>&lt;вариант_впн&gt;-&lt;протокол&gt;-&lt;дата_активациин&gt;.*</code>",
    },
    "az_wireguard": {
        "prefix": "AZ-WG",
        "text": "⚡ Обходите блокировки и получайте доступ к любимым сайтам с <b>высокой скоростью</b>! 🌊\n\n<b>FAQ по названию файлов:</b>\n\n <code>&lt;вариант_впн&gt;-&lt;протокол&gt;-&lt;дата_активациин&gt;.*</code>",
    },
    "gb_wireguard": {
        "prefix": "GL-WG",
        "text": "🔒 Получите <b>максимальную защиту и анонимность</b> при использовании интернета. Ваши данные под надежной защитой! 🔐\n\n<b>FAQ по названию файлов:</b>\n\n <code>&lt;вариант_впн&gt;-&lt;протокол&gt;-&lt;дата_активациин&gt;.*</code>",
    },
}


@dp.callback_query(lambda call: call.data in config_texts.keys())
async def send_configs_callback(call: types.CallbackQuery) -> None:
    """Обработчик отправки конфигураций VPN в ответ на запрос пользователя."""
    user_id = call.from_user.id
    user = await get_user_by_id(user_id)

    # Проверка, имеет ли пользователь доступ к конфигурациям
    if user and user[2] == "accepted":
        config = config_texts[call.data]  # Получаем конфигурацию по ключу
        file_type = (
            "conf" if "WG" in config["prefix"] or "AM" in config["prefix"] else "ovpn"
        )  # Определяем тип файла
        file_prefix = config["prefix"]  # Получаем префикс файла
        # Проходим по всем файлам в директории пользователя
        for file in os.listdir(f"/root/vpn/n{user_id}"):
            # Проверяем, соответствует ли файл префиксу и расширению
            if file.startswith(file_prefix) and file.endswith(f".{file_type}"):
                caption = config["text"]  # Получаем текст для подписи
                # Формируем соответствующую кнопку в зависимости от типа конфигурации
                if file_type == "ovpn":
                    app_url = "https://openvpn.net/client/"
                elif "WG" in config["prefix"]:
                    app_url = "https://www.wireguard.com/install/"
                elif "AM" in config["prefix"]:
                    app_url = "https://docs.amnezia.org/ru/documentation/amnezia-wg/"
                else:
                    app_url = None

                # Создаем Inline-кнопку, если URL определен
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

                # Отправляем файл пользователю
                await bot.send_document(
                    user_id,
                    FSInputFile(f"/root/vpn/n{user_id}/{file}"),
                    caption=caption,
                    parse_mode="HTML",
                    reply_markup=markup,  # Добавляем кнопку, если она есть
                )

                if "AZ" in config["prefix"]:
                    await protos_menu(user_id=user_id, proto="az")
                else:
                    await protos_menu(user_id=user_id, proto="gb")

                break  # Завершаем цикл после отправки первого соответствующего файла

    else:
        # Если пользователь не авторизован, отправляем соответствующее сообщение
        await non_authorized(call.from_user.id, call.message.message_id)
