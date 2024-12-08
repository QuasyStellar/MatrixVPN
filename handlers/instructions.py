from utils.db_utils import get_user_by_id
from utils.messages_manage import non_authorized
from aiogram.types import FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram import types
from loader import dp


@dp.callback_query(lambda call: call.data in ("az_faq", "gb_faq"))
async def instructions(call: types.CallbackQuery, state: FSMContext) -> None:
    """Обработчик для предоставления инструкций по протоколам VPN"""
    user = await get_user_by_id(call.from_user.id)

    # Проверяем, имеет ли пользователь доступ
    if user and user[2] == "accepted":
        markup = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text="🔐 OpenVPN",
                        web_app=types.WebAppInfo(
                            url="https://teletype.in/@esc_matrix/Matrix_VPN_OVPN_Instruction"
                        ),
                    )
                ],
                [
                    types.InlineKeyboardButton(
                        text="⚡ WireGuard/AmnesiaWG",
                        web_app=types.WebAppInfo(
                            url="https://teletype.in/@esc_matrix/Matrix_VPN_OVPN_Instruction"
                        ),
                    )
                ],
                [
                    types.InlineKeyboardButton(
                        text="⬅ Назад", callback_data=f"choose_proto_{call.data[:2]}"
                    )
                ],
            ]
        )
        await call.message.edit_media(
            media=types.InputMediaPhoto(
                media=FSInputFile("assets/instructions.png"),
                caption="ⓘ <b>Инструкции для протоколов 📖</b>",
                parse_mode="HTML",
            ),
            reply_markup=markup,
        )

    else:
        await non_authorized(call.from_user.id, call.message.message_id)
