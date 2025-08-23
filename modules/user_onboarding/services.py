import logging
from aiogram import types
from aiogram.types import FSInputFile
from core.bot import bot
from services.db_operations import get_user_by_id
from modules.common.services import main_menu

logger = logging.getLogger(__name__)

# Общая подпись для приветственного сообщения
common_caption = """
<b>Добро пожаловать в MatrixVPN 🛡️</b> — ваш надежный инструмент для обеспечения <b>свободы</b> и <b>приватности</b> в интернете 🌐

🔵   <b><i>Примешь синюю таблетку</i></b> — и <b>сказке конец</b>.
Ты проснешься в своей постели и поверишь, что это был <i>сон</i>.

🔴   <b><i>Примешь красную таблетку</i></b> — войдешь в <b>страну чудес</b>.

Я покажу тебе, глубока ли кроличья нора. 🐇
"""

# Подпись, отображаемая после запроса
after_caption = """
<i> ⟳ Ожидайте перехода</i> в <b>реальный мир</b>.

<b>Обратного пути больше нет...</b> 🐇

ⓘ Запрос уже отправлен, ожидайте ответ ⌛
"""

async def process_start_command(message: types.Message = None, user_id: int = None):
    """Processes the start command and displays the appropriate menu."""
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