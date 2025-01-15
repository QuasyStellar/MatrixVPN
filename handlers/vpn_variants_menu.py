from aiogram import types
from aiogram.types import FSInputFile
from loader import dp, bot
from utils.db_utils import get_user_by_id
from utils.messages_manage import non_authorized

# Создание кнопок для выбора конфигурации
markup = types.InlineKeyboardMarkup(
    inline_keyboard=[
        [
            types.InlineKeyboardButton(
                text="🔒 АнтиЗапрет", callback_data="choose_proto_az"
            ),
            types.InlineKeyboardButton(
                text="🌍 Глобальный", callback_data="choose_proto_gb"
            ),
        ],
        [
            types.InlineKeyboardButton(
                text="📜 Подробнее о вариантах", callback_data="more_variants"
            )
        ],
        [types.InlineKeyboardButton(text="⬅ Назад", callback_data="main_menu")],
    ]
)


@dp.callback_query(lambda call: call.data == "vpn_variants")
async def vpn_variants_menu(
    call: types.CallbackQuery = None, user_id: int = None
) -> None:
    """Отображает конфигурации выбранного протокола VPN."""

    user = await get_user_by_id(call.from_user.id if user_id is None else user_id)

    # Проверка авторизации пользователя
    if user and user[2] == "accepted":
        # Подготовка текста сообщения
        caption = "ⓘ <b>Выберите вариант MatrixVPN🛡️</b>:"

        # Обновление сообщения или отправка нового в зависимости от передачи user_id
        if user_id is None:
            await call.message.edit_media(
                media=types.InputMediaPhoto(
                    media=FSInputFile("assets/vpn_variants.png"),
                    caption=caption,
                    parse_mode="HTML",
                ),
                reply_markup=markup,
            )
        else:
            await bot.send_photo(
                chat_id=user_id,
                photo=FSInputFile("assets/vpn_variants.png"),
                caption=caption,
                parse_mode="HTML",
                reply_markup=markup,
            )
    else:
        # Обработка случая, если пользователь не авторизован
        await non_authorized(call.from_user.id, call.message.message_id)
