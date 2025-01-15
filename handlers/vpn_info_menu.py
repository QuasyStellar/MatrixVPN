from aiogram import types
from aiogram.fsm.context import FSMContext
from utils.db_utils import get_user_by_id
from utils.messages_manage import send_message_with_cleanup, non_authorized
from handlers.vpn_variants_menu import vpn_variants_menu
from loader import dp, bot


@dp.callback_query(lambda call: call.data in ("more_variants"))
async def vpn_info_callback(call: types.CallbackQuery, state: FSMContext) -> None:
    """Отображает информацию о VPN в зависимости от выбранного протокола."""

    user = await get_user_by_id(call.from_user.id)

    # Проверка авторизации пользователя
    if call.data.startswith("more_variants"):
        # Подготовка текста сообщения о вариантах подключения
        message_text = (
            "ⓘ <b>MatrixVPN</b> 🛡️ предлагает два варианта подключения:\n"
            "<b>АнтиЗапрет VPN 🔒</b> — туннелирует только заблокированные и ограниченные ресурсы, "
            "пропуская обычный трафик вне VPN для сохранения скорости соединения ⚡\n\n"
            "<b>Глобальный VPN 🌍</b> — перенаправляет весь интернет-трафик через защищенное соединение, "
            "предоставляя доступ ко всем сайтам и максимальную приватность 🔒\n\n"
            "Поддерживаются протоколы <b>OpenVPN</b>, <b>WireGuard</b> и <b>AmneziaWG</b>."
        )
        await bot.delete_message(call.from_user.id, call.message.message_id)

        await send_message_with_cleanup(call.from_user.id, message_text, state)

        # Вызов соответствующих функций для отображения конфигураций
        await vpn_variants_menu(user_id=call.from_user.id)

    else:
        # Если пользователь не авторизован, очищаем состояние и уведомляем
        await state.clear()
        await non_authorized(call.from_user.id, call.message.message_id)
