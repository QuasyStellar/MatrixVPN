import logging

from services import vpn_manager

logger = logging.getLogger(__name__)


def get_day_word(days: int) -> str:
    if 10 <= days % 100 <= 20:
        return "дней"
    elif days % 10 == 1:
        return "день"
    elif 2 <= days % 10 <= 4:
        return "дня"
    else:
        return "дней"


async def update_user_configs(user_id: int, days: int) -> bool:
    """Updates user VPN configurations."""
    try:
        # Recreate configurations (vpn_manager.create_user handles existing ones)
        await vpn_manager.create_user(user_id)
        logger.info(f"Обновлены конфигурации для пользователя {user_id}.")
        return True
    except Exception as e:
        logger.error(f"Ошибка при обновлении конфигураций для пользователя {user_id}: {e}", exc_info=True)
        return False
