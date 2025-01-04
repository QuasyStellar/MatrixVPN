from aiogram import types
from aiogram.fsm.context import FSMContext
from aiogram.filters.command import Command
from loader import bot, dp
from utils.messages_manage import send_message_with_cleanup

# Сообщение с информацией о вариантах подключения VPN
message_text = (
    "ⓘ <b>MatrixVPN 🛡️</b> предлагает два варианта подключения:\n\n"
    "<b>АнтиЗапрет VPN 🔒</b> туннелирует только заблокированные и ограниченные ресурсы, "
    "пропуская обычный трафик вне VPN для сохранения скорости соединения ⚡\n\n"
    "<b>Глобальный VPN 🌍</b> перенаправляет весь интернет-трафик через защищенное соединение, "
    "предоставляя доступ ко всем сайтам и максимальную приватность 🔒\n\n"
    "Поддерживаются протоколы <b>OpenVPN</b>, <b>WireGuard</b> и <b>AmneziaWG</b>."
)


@dp.callback_query(lambda call: call.data == "more")
async def info_about_vpn_callback(call: types.CallbackQuery, state: FSMContext) -> None:
    """Обработчик для кнопки 'Больше информации о VPN'."""
    try:
        # Удаляем предыдущее сообщение пользователя
        await bot.delete_message(call.from_user.id, call.message.message_id)

        # Отправляем сообщение с информацией о VPN и обновляем состояние
        await send_message_with_cleanup(call.from_user.id, message_text, state)

    except Exception as e:
        # Логируем ошибку при обработке запроса
        print(f"Ошибка при обработке запроса о VPN: {e}")


@dp.message(Command("more"))
async def info_about_vpn_handler(message: types.Message) -> None:
    """Обработчик для команды '/more'."""
    user_id = message.from_user.id

    try:

        # Отправляем сообщение с информацией о VPN
        await bot.send_message(
            user_id,
            message_text,  # Исправлено на 'message_text' вместо 'VPN_MESSAGE_TEXT'
            parse_mode="HTML",
        )
    except Exception as e:
        # Логируем ошибку при обработке команды
        print(f"Ошибка при обработке команды 'more': {e}")
