import asyncio
import locale
import logging

from handlers import *
from loader import bot, dp
from utils.db_utils import init_conn_db
from utils.scheduler import start_scheduler

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
    await dp.start_polling(bot)  # Запускаем бота


if __name__ == "__main__":
    # Инициализируем соединение с базой данных и запускаем основную функцию
    asyncio.run(main())  # Запуск основной функции
