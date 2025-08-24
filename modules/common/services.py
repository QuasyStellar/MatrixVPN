import random
from aiogram import types
from services.db_operations import get_user_by_id
from core.bot import bot
from aiogram.exceptions import TelegramAPIError
from config.settings import SUPPORT_ID
from pytils import numeral
from babel.dates import format_datetime
import pytz
from datetime import datetime
from services.messages_manage import non_authorized
import logging

logger = logging.getLogger(__name__)

quotes = [
    "Вставай, Тринити. Вставай! Надо встать!",
    "Проснись, Нео…",
    "Ты увяз в Матрице.",
    "Следуй за белым кроликом.",
    "Тук-тук, Нео.",
    "Эту дорогу ты видел. И знаешь, куда она ведёт. Тебе туда не нужно, я уверена.",
    "Нео, я больше не боюсь. Провидица предсказала мне, что я должна влюбиться. И мой любимый — Избранный. А значит, ты не умрёшь.",
    "Догадываюсь, сейчас ты чувствуешь себя Алисой, падающей в кроличью нору…",
    "Время всегда против нас.",
    "Случалось видеть сон, казавшийся реальностью? Что, если бы ты не смог проснуться? Как бы ты узнал, что такое сон, а что действительность?",
    "Добро пожаловать в реальный мир.",
    "Что есть реальность? И как определить её? Есть набор ощущений, зрительных, осязательных, обонятельных — это сигналы рецепторов, электрические импульсы, воспринятые мозгом.",
    "Что такое «Матрица»? Диктат.",
    "Я не говорил, что будет легко, Нео. Я лишь обещал, что это будет правда.",
    "Ты думаешь, что моя реакция или сила здесь, в этом мире, зависят от мускулов? Ты думаешь, что дышишь воздухом сейчас?…",
    "Ты можешь быстрее. Не думай, что ты быстр — знай, что ты быстр. Хватит попыток. Не пытайся ударить меня и просто ударь меня.",
    "Пора освободить твой разум. Но я могу лишь указать дверь. Ты сам должен выйти на волю. … Отвлекись от всего, Нео. Страх, неверие, сомнения отбрось — очисти свой разум.",
    "Реально то, что осознаешь.",
    "Матрица — это система. Система — есть наш враг. Но когда ты в ней — оглянись, кого ты видишь? Бизнесменов, учителей, адвокатов, работяг, обычных людей, чей разум мы и спасаем.",
    "Рано или поздно ты поймёшь, как и я. Знать путь и пройти его — не одно и тоже.",
    "Он начинает верить.",
    "Пристегни ремень, Дороти, и скажи Канзасу: «Прости и прощай».",
    "Все мы падали в первый раз.",
    "Информации, получаемой из Матрицы, гораздо больше, чем ты можешь расшифровать. Ты привыкнешь к этому.",
    "Я знаю, он не настоящий, и когда я положу его в рот, вкус внушит мне Матрица. Знаете, что я решил за те десять лет, что свободен? Счастье в неведении.",
    "Всё, что я делал — это то, что он говорил мне делать.",
    "Как видите, мы за Вами давненько наблюдаем, мистер Андерсон.",
    "Вам случалось любоваться Матрицей? Её гениальностью…",
    "Никогда не посылайте человека делать работу машины.",
    "Я хочу поделиться теорией, которую недавно создал. Я занимался классификацией биологических видов и пришёл к выводу, что вы — не млекопитающие.",
    "Я этот город… ненавижу. Этот зоопарк, тюрьму, эту реальность — называйте как хотите.",
    "Убить Вас — наслаждение, мистер Андерсон.",
    "Быть Избранным всё равно что быть влюблённым. Никто не говорит тебе, что ты влюблён. Ты просто знаешь это.",
    "Дар у тебя есть, но, кажется, ты чего-то ждёшь.",
    "Главное, не верь всякой ерунде насчёт судьбы. Ты хозяин своей жизни.",
    "Так, положено проводить тех. подготовку. Но это тоска зелёная. Как насчёт предмета повеселей?",
    "Может машины не знали какой на вкус цыплёнок, поэтому цыплёнок на вкус как вообще всё.",
    "Это всего лишь белок одноклеточных, смешанный с синтетическими аминокислотами, витаминами и минеральными веществами.",
    "Не обращай внимания на этих лицемеров. Инстинкты и слабости как раз и отличают нас от мерзких машин.",
    "Обратите внимание. Зажглись табло «Не курить» и «Пристегнуть ремни». Экипаж желает Вам приятного полёта.",
]

message_text_vpn_variants = (
    "ⓘ <b>MatrixVPN 🛡️</b> предлагает два варианта подключения:\n\n"
    "<b>АнтиЗапрет VPN 🔒</b> туннелирует только заблокированные и ограниченные ресурсы, "
    "пропуская обычный трафик вне VPN для сохранения скорости соединения ⚡\n\n"
    "<b>Глобальный VPN 🌍</b> перенаправляет весь интернет-трафик через защищенное соединение, "
    "предоставляя доступ ко всем сайтам и максимальную приватность 🔒\n\n"
    "Поддерживаются протоколы <b>VLESS</b>, <b>AmneziaWG</b>, <b>WireGuard</b> и <b>OpenVPN</b>."
)

message_text_protos_info = (
    "<b>MatrixVPN 🛡️</b> поддерживает несколько современных VPN и прокси протоколов:\n\n"
    "<b>🌐 VLESS</b> — это современный протокол для безопасного и быстрого проксирования."
    "Он обеспечивает высокую скорость соединения и эффективно обходит блокировки благодаря минимальной нагрузке на трафик и поддержке различных методов маскировки. "
    "<b>VLESS</b> подходит для пользователей, которым важна скорость, стабильность и конфедициальность.\n\n"
    "<b>🛡️ AmneziaWG</b> — это улучшенная версия <b>WireGuard</b>, которая добавляет обфускацию трафика. "
    "Это значит, что ваш интернет-трафик будет выглядеть как обычный, что помогает избежать блокировок. "
    "<b>AmneziaWG</b> также использует <b>UDP</b> и предоставляет пользователям дополнительный уровень конфиденциальности.\n\n"
    "<b>⚡ WireGuard</b> — это новый и быстро развивающийся протокол, который выделяется своей простотой и высокой скоростью. "
    "Он работает только через <b>UDP</b>, что позволяет значительно снизить задержки и повысить скорость соединения, "
    "при этом обеспечивая высокий уровень безопасности. <b>WireGuard</b> идеально подходит для тех, кто ценит скорость и эффективность.\n\n"
    "<b>🔐 OpenVPN</b> — это один из самых популярных и надежных протоколов для VPN. "
    "Он предлагает стабильное соединение и может работать как через <b>UDP</b>, так и через <b>TCP</b>, "
    "что делает его универсальным выбором для различных условий. "
    "Благодаря специальным патчам OpenVPN может обходить блокировки провайдеров, что очень важно, если вы столкнулись с ограничениями доступа.\n\n"
    "ⓘ Таким образом, <b>MatrixVPN</b> предлагает разнообразные решения для туннелирования трафика, "
    "обеспечивая скорость, безопасность и возможность обхода блокировок в зависимости от ваших нужд. "
    "Вы можете выбрать подходящий протокол в зависимости от своих требований и предпочтений."
)


async def get_protos_menu_markup(
    user_id: int, proto: str
) -> types.InlineKeyboardMarkup:
    # This function will generate the markup for protos_menu
    # It will be called from handlers and potentially other services
    user = await get_user_by_id(user_id)
    if not (user and user[2] == "accepted"):
        return None

    inline_keyboard = [
        [
            types.InlineKeyboardButton(
                text="🔮 VLESS",
                callback_data=f"{proto}_vless",
            ),
        ],
        [
            types.InlineKeyboardButton(
                text="🕵️ AmneziaWG",
                callback_data=f"{proto}_amneziawg",
            ),
            types.InlineKeyboardButton(
                text="⚡ WireGuard",
                callback_data=f"{proto}_wireguard",
            ),
        ],
        [
            types.InlineKeyboardButton(
                text="🛡️ OpenVPN",
                callback_data=f"{proto}_openvpn",
            )
        ],
        [
            types.InlineKeyboardButton(
                text="🔍 О VPN протоколах",
                callback_data=f"{proto}_about",
            )
        ],
    ]
    if (proto) == "az":
        inline_keyboard.insert(
            0,
            [
                types.InlineKeyboardButton(
                    text="🚨 Примечание",
                    web_app=types.WebAppInfo(
                        url="https://teletype.in/@esc_matrix/antizapret_warning"
                    ),
                )
            ],
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

    return types.InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


async def main_menu(call: types.CallbackQuery = None, user_id: int = None):
    """Обработчик для главного меню VPN."""

    user_id = user_id or call.from_user.id

    user = await get_user_by_id(user_id)
    if not (user and user[2] == "accepted"):
        await non_authorized(user_id, call.message.message_id if call else None)
        return

    access_end_date = user[5]

    access_end_date = datetime.fromisoformat(access_end_date)
    current_date = datetime.now(pytz.utc)

    remaining_time = access_end_date - current_date
    remaining_days = remaining_time.days
    remaining_hours = remaining_time.total_seconds() // 3600

    end_date_formatted = format_datetime(
        access_end_date.replace(tzinfo=pytz.utc).astimezone(
            pytz.timezone("Europe/Moscow")
        ),
        "d MMMM yyyy 'в' HH:mm",
        locale="ru",
    )

    if remaining_days < 3:
        time_text = f"{numeral.get_plural(int(remaining_hours), 'час, часа, часов')}"
    else:
        time_text = f"{numeral.get_plural(remaining_days, 'день, дня, дней')}"

    menu = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text="💡 Подключение к VPN", callback_data="vpn_variants"
                ),
            ],
            [
                types.InlineKeyboardButton(
                    text="🎁 Активировать промокод", callback_data="activate_promo"
                ),
            ],
            [
                types.InlineKeyboardButton(
                    text="🛠 Настройки", callback_data="settings"
                ),
            ],
            [
                types.InlineKeyboardButton(
                    text="❓ Поддержка", url=f"tg://user?id={SUPPORT_ID}"
                ),
            ],
        ]
    )

    caption_text = f"""
ⓘ <b>Добро пожаловать!</b>

<blockquote><b>⏳ Осталось: {time_text}
📅 Дата окончания: {end_date_formatted}</b></blockquote>

<blockquote><b>💬 «{random.choice(quotes)}»</b></blockquote>
"""

    if call:
        try:
            await call.message.edit_media(
                media=types.InputMediaPhoto(
                    media=types.FSInputFile("assets/matrix.png"),
                    caption=caption_text,
                    parse_mode="HTML",
                ),
                reply_markup=menu,
            )
        except TelegramAPIError:
            await bot.send_photo(
                chat_id=user_id,
                photo=types.FSInputFile("assets/matrix.png"),
                caption=caption_text,
                parse_mode="HTML",
                reply_markup=menu,
            )
    else:
        await bot.send_photo(
            chat_id=user_id,
            photo=types.FSInputFile("assets/matrix.png"),
            caption=caption_text,
            parse_mode="HTML",
            reply_markup=menu,
        )
