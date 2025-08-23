import asyncio
import locale
import logging

from core.bot import dp, bot
from core.database import init_conn_db, close_db_connection
from services.scheduler import start_scheduler

# Import handlers from modules
# This will be updated as we move handlers to their new locations
# For now, we'll just import the main ones that were in the original __init__.py
from modules.admin.handlers import admin_router
from modules.vpn_management.handlers import vpn_management_router
from modules.user_onboarding.handlers import user_onboarding_router
from modules.common.handlers import common_router


# Устанавливаем локаль для форматирования времени
locale.setlocale(locale.LC_TIME, "ru_RU.UTF8")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Главная асинхронная функция для инициализации бота"""
    await init_conn_db()  # Инициализация соединения с БД
    await start_scheduler(bot)  # Запускаем планировщик задач
    await bot.delete_webhook(
        drop_pending_updates=True
    )  # Удаляем вебхуки, если они есть

    # Register routers from modules
    dp.include_router(admin_router)
    dp.include_router(vpn_management_router)
    dp.include_router(user_onboarding_router)
    dp.include_router(user_onboarding_entry_router)
    dp.include_router(common_router)

    try:
        await dp.start_polling(bot)  # Запускаем бота
    finally:
        await close_db_connection()


if __name__ == "__main__":
    # Инициализируем соединение с базой данных и запускаем основную функцию
    asyncio.run(main())  # Запуск основной функции
