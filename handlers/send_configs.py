import os
from aiogram import types
from aiogram.types import FSInputFile
from loader import dp, bot
from utils.db_utils import get_user_by_id
from utils.messages_manage import non_authorized

# Тексты конфигураций VPN с префиксами и дополнительной информацией
config_texts = {
    "az_ut_ovpn": {
        "prefix": "AZ-U+T",
        "text": "🌍 Идеальное сочетание скорости и надежности! Используются <b>оба протокола</b> для максимальной гибкости ✨\n\n<b>FAQ по названию файлов:</b>\n\n <code>&lt;вариант_впн&gt;-&lt;протокол&gt;-&lt;дата_активациин&gt;.*</code>",
    },
    "az_u_ovpn": {
        "prefix": "AZ-UDP",
        "text": "⚡ <b>Высокая скорость и производительность</b>. Идеально подходит для потокового видео и игр! 🎮 \n\n<b>FAQ по названию файлов:</b>\n\n <code>&lt;вариант_впн&gt;-&lt;протокол&gt;-&lt;дата_активациин&gt;.*</code>",
    },
    "az_t_ovpn": {
        "prefix": "AZ-TCP",
        "text": "🔒 <b>Максимальная надежность и стабильность подключения</b>. Подходит для обхода строгих блокировок и защиты конфиденциальности. 🔑\n\n<b>FAQ по названию файлов:</b>\n\n <code>&lt;вариант_впн&gt;-&lt;протокол&gt;-&lt;дата_активациин&gt;.*</code>",
    },
    "gb_ut_ovpn": {
        "prefix": "GL-U+T",
        "text": "🌍 Идеальное сочетание скорости и надежности! Используйте <b>оба протокола</b> для максимальной гибкости ✨\n\n<b>FAQ по названию файлов:</b>\n\n <code>&lt;вариант_впн&gt;-&lt;протокол&gt;-&lt;дата_активациин&gt;.*</code>",
    },
    "gb_u_ovpn": {
        "prefix": "GL-UDP",
        "text": "⚡ <b>Высокая скорость и производительность</b>. Идеально подходит для потокового видео и игр! 🎮📺 \n\n<b>FAQ по названию файлов:</b>\n\n <code>&lt;вариант_впн&gt;-&lt;протокол&gt;-&lt;дата_активациин&gt;.*</code>",
    },
    "gb_t_ovpn": {
        "prefix": "GL-TCP",
        "text": "🔒 <b>Максимальная надежность и стабильное подключение</b>. Подходит для обхода строгих блокировок и защиты конфиденциальности. 🔑\n\n<b>FAQ по названию файлов:</b>\n\n <code>&lt;вариант_впн&gt;-&lt;протокол&gt;-&lt;дата_активациин&gt;.*</code>",
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
                await bot.send_document(
                    user_id,
                    FSInputFile(f"/root/vpn/n{user_id}/{file}"),
                    caption=caption,
                    parse_mode="HTML",
                )
                #
                # # Вызов функций для отображения конкретных протоколов
                # if file_type == "ovpn":
                #     if "AZ" in config["prefix"]:
                #         await ovpn_menu_az(call, thr=1)
                #     else:
                #         await ovpn_menu_gb(call, thr=1)
                # else:
                #     if "AZ" in config["prefix"]:
                #         await protos_menu(user_id=user_id, proto="az")
                #     else:
                #         await protos_menu(user_id=user_id, proto="gb")

                break  # Завершаем цикл после отправки первого соответствующего файла

    else:
        # Если пользователь не авторизован, отправляем соответствующее сообщение
        await non_authorized(call.from_user.id, call.message.message_id)
