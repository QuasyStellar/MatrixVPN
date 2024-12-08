from aiogram import types
from aiogram.types import FSInputFile
from loader import dp, bot
from utils.db_utils import get_user_by_id
from utils.messages_manage import non_authorized

# Подпись к сообщению с выбором
caption = "ⓘ <b>Выберите VPN протокол:</b>"


@dp.callback_query(lambda call: call.data in ("choose_proto_az", "choose_proto_gb"))
async def show_protos_menu(
    call: types.CallbackQuery = None, user_id: int = None, proto: str = None
) -> None:
    """Отображает меню выбора протоколов VPN."""

    # Получаем данные пользователя
    user = await get_user_by_id(call.from_user.id if user_id is None else user_id)
    proto = call.data[-2:] if user_id is None else proto
    # Проверяем, имеет ли пользователь доступ
    if user and user[2] == "accepted":
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
            inline_keyboard.append(
                [
                    types.InlineKeyboardButton(
                        text="🚨 Примечание",
                        web_app=types.WebAppInfo(
                            url="https://teletype.in/@esc_matrix/antizapret_warning"
                        ),
                    )
                ]
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

        # Разметка для выбора протоколов VPN
        markup = types.InlineKeyboardMarkup(inline_keyboard=inline_keyboard)

        if user_id is None:
            # Редактируем текущее сообщение с новым изображением и разметкой
            await call.message.edit_media(
                media=types.InputMediaPhoto(
                    media=FSInputFile("assets/vpn_protos.png"),
                    caption=caption,
                    parse_mode="HTML",
                ),
                reply_markup=markup,
            )
        else:
            # Отправляем новое сообщение пользователю, если user_id предоставлен
            await bot.send_photo(
                chat_id=user_id,
                photo=FSInputFile("assets/vpn_protos.png"),
                caption=caption,
                parse_mode="HTML",
                reply_markup=markup,
            )
    else:
        # Если пользователь не авторизован, отправляем сообщение о недоступности
        await non_authorized(call.from_user.id, call.message.message_id)
