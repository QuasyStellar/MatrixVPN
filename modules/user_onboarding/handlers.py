from aiogram import types, Router
from aiogram.types import FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.filters.command import Command
from aiogram.exceptions import TelegramAPIError

from core.bot import bot
from services.db_operations import get_user_by_id
from services.messages_manage import non_authorized
from modules.common.handlers import main_menu
from modules.user_onboarding.services import common_caption, after_caption

import logging

logger = logging.getLogger(__name__)

user_onboarding_router = Router()

@user_onboarding_router.message(Command("start"))
async def start_handler(
    message: types.Message = None, user_id: int = None, state: FSMContext = None
) -> None:
    """Отображает начальное меню в зависимости от статуса пользователя."""

    try:
        if state:
            await state.clear()
    except Exception:
        logger.error("Error clearing state:", exc_info=True)

    user_id = message.from_user.id if message else user_id
    user = await get_user_by_id(user_id)

    if user:
        status = user[2]

        if status == "accepted":
            await main_menu(user_id=user_id)

        elif status == "denied":
            markup = types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text="Запросить доступ снова",
                            callback_data="request_access",
                        )
                    ]
                ]
            )
            await bot.send_message(
                user_id, 
                text="Ваш предыдущий запрос был отклонен. Нажмите на кнопку ниже, чтобы запросить доступ снова.",
                reply_markup=markup,
            )

        elif status == "pending":
            markup = types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text="Подробнее о VPN", callback_data="more"
                        )
                    ]
                ]
            )
            await bot.send_animation(
                chat_id=user_id,
                animation=FSInputFile("assets/pending.gif"),
                caption=common_caption.partition("\n")[0] + after_caption,
                reply_markup=markup,
                parse_mode="HTML",
            )

        elif status == "expired":
            markup = types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        types.InlineKeyboardButton(
                            text="🔴   Возобновить доступ",
                            callback_data="request_access",
                        )
                    ],
                    [
                        types.InlineKeyboardButton(
                            text="Подробнее о VPN 📜", callback_data="more"
                        )
                    ],
                ]
            )
            await bot.send_photo(
                chat_id=user_id,
                photo=FSInputFile("assets/matrix.png"),
                caption=common_caption,
                reply_markup=markup,
                parse_mode="HTML",
            )
    else:
        markup = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    types.InlineKeyboardButton(
                        text="🔴   Получить доступ", callback_data="request_access"
                    )
                ],
                [
                    types.InlineKeyboardButton(
                        text="Подробнее о VPN 📜", callback_data="more"
                    )
                    
                ],
            ]
        )
        await bot.send_photo(
            chat_id=user_id,
            photo=FSInputFile("assets/matrix.png"),
            caption=common_caption,
            reply_markup=markup,
            parse_mode="HTML",
        )


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
                        web_app=types.WebAppInfo(
                            url="https://teletype.in/@esc_matrix/Matrix_VPN_OVPN_Instruction"
                        ),
                    )
                ],
                [
                    types.InlineKeyboardButton(
                        text="⚡ WireGuard/AmnesiaWG",
                        web_app=types.WebAppInfo(
                            url="https://teletype.in/@esc_matrix/Matrix_VPN_AMWG_Instruction"
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
