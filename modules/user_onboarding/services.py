import logging
from aiogram import types
from aiogram.types import FSInputFile
from core.bot import bot
from services.db_operations import get_user_by_id, add_user
from modules.common.services import main_menu

logger = logging.getLogger(__name__)

# Общая подпись для приветственного сообщения
common_caption = """
<b>Добро пожаловать в MatrixVPN 🛡️</b> — ваш надежный инструмент для обеспечения <b>свободы</b> и <b>приватности</b> в интернете

🔵   <b><i>Примешь синюю таблетку</i></b> — и <b>сказке конец</b>
Ты проснешься в своей постели и поверишь, что это был <i>сон</i>

🔴   <b><i>Примешь красную таблетку</i></b> — войдешь в <b>страну чудес</b>
Я покажу тебе, глубока ли кроличья нора 🐇
"""

# Подпись, отображаемая после запроса
enter_caption = """<b>Добро пожаловать в реальный мир</b> 🐇"""


async def process_start_command(message: types.Message = None, user_id: int = None):
    """Processes the start command and displays the appropriate menu."""
    user_id = message.from_user.id if message else user_id
    username = message.from_user.username if message else None
    user = await get_user_by_id(user_id)

    if not user:
        await add_user(user_id, username)
        user = await get_user_by_id(user_id)

    status = user[2]

    if status == "accepted":
        await main_menu(user_id=user_id)

    elif status in ("pending", "denied", "expired"):
        trial_button = types.InlineKeyboardButton(
            text="Получить тестовую подписку (3 дня)", callback_data="get_trial"
        )
        buy_button = types.InlineKeyboardButton(
            text="Купить подписку", callback_data="buy_subscription"
        )
        more_info_button = types.InlineKeyboardButton(
            text="Подробнее о VPN", callback_data="more"
        )

        user_markup = types.InlineKeyboardMarkup(
            inline_keyboard=[[trial_button], [buy_button], [more_info_button]]
        )

        caption = common_caption
        if status == "denied":
            caption = "Ваш предыдущий запрос был отклонен.\n\n" + caption
        elif status == "expired":
            caption = "Срок вашей подписки истек.\n\n" + caption

        await bot.send_photo(
            chat_id=user_id,
            photo=FSInputFile("assets/matrix.png"),
            caption=caption,
            reply_markup=user_markup,
            parse_mode="HTML",
        )
