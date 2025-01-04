from aiogram import types
from aiogram.types import FSInputFile
from utils.db_utils import get_user_by_id
from utils.messages_manage import non_authorized
from loader import dp, bot


async def send_protocol_message(
    call: types.CallbackQuery, protocol_type: str, thr: bool = None
) -> None:
    """Отправляет сообщение с вариантами сетевых протоколов для указанного типа VPN."""
    user = await get_user_by_id(call.from_user.id)

    # Проверка, имеет ли пользователь доступ
    if user and user[2] == "accepted":
        # Создание кнопок для выбора протокола
        ut = types.InlineKeyboardButton(
            text="⚖️ AUTO", callback_data=f"{protocol_type}_ut_ovpn"
        )
        t = types.InlineKeyboardButton(
            text="🏠 TCP", callback_data=f"{protocol_type}_t_ovpn"
        )
        u = types.InlineKeyboardButton(
            text="🚀 UDP", callback_data=f"{protocol_type}_u_ovpn"
        )
        more = types.InlineKeyboardButton(
            text="📜 Подробнее о сетевых протоколах",
            callback_data=f"more_proto_{protocol_type}",
        )
        ret = types.InlineKeyboardButton(
            text="⬅ Назад", callback_data=f"choose_proto_{protocol_type}"
        )
        markup = types.InlineKeyboardMarkup(
            inline_keyboard=[[ut], [u, t], [more], [ret]]
        )
        caption = "ⓘ <b>Выберите вариант сетевого протокола:</b>"
        if thr is None:
            # Обновление сообщения с новой медиаграфикой
            await call.message.edit_media(
                media=types.InputMediaPhoto(
                    media=FSInputFile("assets/ovpn_protos.png"),
                    caption=caption,
                    parse_mode="HTML",
                ),
                reply_markup=markup,
            )
        else:
            # Отправка нового сообщения, если предыдущая была удалена
            await bot.delete_message(call.from_user.id, call.message.message_id)
            await bot.send_photo(
                chat_id=call.from_user.id,
                photo=FSInputFile("assets/ovpn_protos.png"),
                caption=caption,
                parse_mode="HTML",
                reply_markup=markup,
            )
    else:
        # Если пользователь не авторизован, отправляем соответствующее сообщение
        await non_authorized(call.from_user.id, call.message.message_id)


@dp.callback_query(lambda call: call.data == "az_openvpn")
async def ovpn_menu_az(call: types.CallbackQuery, thr: bool = None) -> None:
    """Обработчик для отображения протоколов OpenVPN для AZ."""
    await send_protocol_message(call, "az", thr)


@dp.callback_query(lambda call: call.data == "gb_openvpn")
async def ovpn_menu_gb(call: types.CallbackQuery, thr: bool = None) -> None:
    """Обработчик для отображения протоколов OpenVPN для GB."""
    await send_protocol_message(call, "gb", thr)
