import logging

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
    """(ЗАГЛУШКА) Updates user VPN configurations."""
    logger.info(f"[ЗАГЛУШКА] Обновлены конфигурации для пользователя {user_id} на {days} дней.")
    return True
