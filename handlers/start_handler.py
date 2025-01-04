from aiogram import types
from aiogram.types import FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.filters.command import Command
from loader import bot, dp
from utils.db_utils import get_user_by_id
from handlers.main_menu import main_menu

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


@dp.message(Command("start"))
async def start_handler(
    message: types.Message = None, user_id: int = None, state: FSMContext = None
) -> None:
    """Отображает начальное меню в зависимости от статуса пользователя."""

    # Получаем данные о пользователе из базы данных
    try:
        await state.clear()
    except:
        pass
    user_id = message.from_user.id if user_id is None else user_id
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
        # Если пользователь не найден, предлагается получить доступ
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
