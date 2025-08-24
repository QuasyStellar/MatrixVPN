from aiogram import types, Router, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile
from services.db_operations import get_user_by_id, update_user_access, grant_access_and_create_config
from services.messages_manage import non_authorized
from config.settings import TRIAL_CHANNEL_ID
from core.bot import bot

import logging
from datetime import datetime, timedelta
import pytz

logger = logging.getLogger(__name__)

user_onboarding_router = Router()


@user_onboarding_router.callback_query(lambda call: call.data == "get_trial")
async def get_trial_callback(call: types.CallbackQuery) -> None:
    user_id = call.from_user.id
    username = call.from_user.username

    user = await get_user_by_id(user_id)

    if not user:
        await call.message.answer("Произошла ошибка. Пожалуйста, попробуйте снова или свяжитесь с поддержкой.")
        logger.error(f"User {user_id} not found in DB when trying to get trial.")
        return

    if user[7] == 1:
        await call.message.answer("Вы уже использовали свой тестовый период.")
        return

    try:
        chat_member = await bot.get_chat_member(TRIAL_CHANNEL_ID, user_id)
        if chat_member.status in ["member", "administrator", "creator"]:
            trial_days = 3
            access_end_date = datetime.now(pytz.UTC) + timedelta(days=trial_days)
            
            await grant_access_and_create_config(user_id, trial_days)
            await update_user_access(user_id, access_end_date.isoformat(), has_used_trial=1)

            await call.message.answer(
                f"Поздравляем! Вам предоставлен тестовый доступ на {trial_days} дня. "
                "Ваши конфигурационные файлы будут отправлены в ближайшее время."
            )

        else:
            channel_link_markup = types.InlineKeyboardMarkup(
                inline_keyboard=[
                    [types.InlineKeyboardButton(text="Подписаться на канал", url=f"https://t.me/c/{str(TRIAL_CHANNEL_ID)[4:]}")]
                ]
            )
            await call.message.answer(
                "Для получения тестового доступа, пожалуйста, подпишитесь на наш канал:",
                reply_markup=channel_link_markup
            )

    except Exception as e:
        logger.error(f"Error checking channel subscription for user {user_id}: {e}", exc_info=True)
        await call.message.answer("Произошла ошибка при проверке подписки. Пожалуйста, попробуйте позже.")


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
                        web_app=types.WebAppInfo(url="https://teletype.in/@esc_matrix/Matrix_VPN_OVPN_Instruction"),
                    )
                ],
                [
                    types.InlineKeyboardButton(
                        text="⚡ WireGuard/AmnesiaWG",
                        web_app=types.WebAppInfo(url="https://teletype.in/@esc_matrix/Matrix_VPN_AMWG_Instruction"),
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
