from aiogram import types
from aiogram.fsm.context import FSMContext
from utils.db_utils import get_user_by_id
from utils.messages_manage import send_message_with_cleanup
from handlers.show_protos_menu import show_protos_menu
from handlers.show_start_menu import show_start_menu
from loader import dp, bot

# Текст сообщения с информацией о протоколах VPN
text = (
    "<b>MatrixVPN 🛡️</b> поддерживает три современных VPN протокола:\n\n"
    "<b>🔐 OpenVPN</b> — это один из самых популярных и надежных протоколов для VPN. "
    "Он предлагает стабильное соединение и может работать как через <b>UDP</b>, так и через <b>TCP</b>, "
    "что делает его универсальным выбором для различных условий. "
    "Благодаря специальным патчам OpenVPN может обходить блокировки провайдеров, что очень важно, если вы столкнулись с ограничениями доступа.\n\n"
    "<b>⚡ WireGuard</b> — это новый и быстро развивающийся протокол, который выделяется своей простотой и высокой скоростью. "
    "Он работает только через <b>UDP</b>, что позволяет значительно снизить задержки и повысить скорость соединения, "
    "при этом обеспечивая высокий уровень безопасности. <b>WireGuard</b> идеально подходит для тех, кто ценит скорость и эффективность.\n\n"
    "<b>🛡️ AmneziaWG</b> — это улучшенная версия <b>WireGuard</b>, которая добавляет обфускацию трафика. "
    "Это значит, что ваш интернет-трафик будет выглядеть как обычный, что помогает избежать блокировок. "
    "<b>AmneziaWG</b> также использует <b>UDP</b> и предоставляет пользователям дополнительный уровень конфиденциальности.\n\n"
    "ⓘ Таким образом, <b>MatrixVPN</b> предлагает разнообразные решения для туннелирования трафика, "
    "обеспечивая скорость, безопасность и возможность обхода блокировок в зависимости от ваших нужд. "
    "Вы можете выбрать подходящий протокол в зависимости от своих требований и предпочтений."
)


@dp.callback_query(lambda call: call.data in ("az_about", "gb_about"))
async def info_about_protos(call: types.CallbackQuery, state: FSMContext) -> None:
    """Обработчик для предоставления информации о протоколах VPN."""
    user = await get_user_by_id(call.from_user.id)

    # Проверяем, имеет ли пользователь доступ
    if user and user[2] == "accepted":
        state_data = await state.get_data()
        previous_bot_message_id = state_data.get("previous_bot_message")

        try:
            # Удаляем предыдущее сообщение бота
            await bot.delete_message(call.from_user.id, call.message.message_id)

            # Отправляем новое сообщение с информацией о протоколах и обновляем состояние
            bot_message = await send_message_with_cleanup(
                call.from_user.id, text, state
            )
            await state.update_data(previous_bot_message=bot_message.message_id)

            # Отображаем меню протоколов
            await show_protos_menu(user_id=call.from_user.id, proto=call.data[:2])
        except Exception as e:
            # Логируем ошибку и информируем пользователя о проблеме
            print(f"Ошибка при обработке запроса о протоколах: {e}")

    else:
        # Очистка состояния и возврат к начальному меню для пользователей без доступа
        await state.clear()
        await bot.delete_message(call.from_user.id, call.message.message_id)
        await show_start_menu(call.from_user.id)
