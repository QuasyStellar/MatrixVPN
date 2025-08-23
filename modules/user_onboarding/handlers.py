from aiogram import types, Router
from aiogram.fsm.context import FSMContext

from services.db_operations import get_user_by_id
from services.messages_manage import non_authorized
from config.settings import OPENVPN_INSTRUCTION_URL, WIREGUARD_INSTRUCTION_URL

import logging

logger = logging.getLogger(__name__)

user_onboarding_router = Router()


@user_onboarding_router.callback_query(lambda call: call.data in ("az_faq", "gb_faq"))
async def instructions_callback(call: types.CallbackQuery, state: FSMContext) -> None:
    """Обработчик для предоставления инструкций по протоколам VPN"""
    user = await get_user_by_id(call.from_user.id)

    if user and user[2] == "accepted":
        markup = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text="🔐 OpenVPN",
                        web_app=types.WebAppInfo(url=OPENVPN_INSTRUCTION_URL),
                    )
                ],
                [
                    types.InlineKeyboardButton(
                        text="⚡ WireGuard/AmnesiaWG",
                        web_app=types.WebAppInfo(url=WIREGUARD_INSTRUCTION_URL),
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
                media="assets/instructions.png",
                caption="ⓘ <b>Инструкции для протоколов 📖</b>",
                parse_mode="HTML",
            ),
            reply_markup=markup,
        )

    else:
        await non_authorized(call.from_user.id, call.message.message_id)
